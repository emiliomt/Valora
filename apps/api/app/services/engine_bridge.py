"""Maps normalized DB financial line items <-> financial_engine dataclasses,
and orchestrates a full forecast + DCF + model-check run for one scenario.

This module contains NO calculation logic itself (PRD 21: keep financial
logic in the pure-Python engine, not scattered through the API layer) — it
only aggregates approved FinancialLineItem rows into the engine's input
shapes and translates engine outputs back into API schemas.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from financial_engine.checks import run_full_check_suite
from financial_engine.dcf import compute_dcf
from financial_engine.forecast import build_forecast
from financial_engine.net_debt import build_net_debt_bridge
from financial_engine.schemas import (
    DCFInputs,
    ForecastYear,
    HistoricalFinancials,
    ScenarioAssumptions,
)

OPEX_KEYS = {
    "sales_and_marketing",
    "research_and_development",
    "general_and_administrative",
    "other_operating_expenses",
}
CURRENT_ASSET_KEYS = {"accounts_receivable", "inventory", "other_current_assets"}
CURRENT_LIABILITY_KEYS = {"accounts_payable", "accrued_expenses", "deferred_revenue", "other_current_liabilities"}

ASSUMPTION_KEYS = (
    "revenue_growth_rate",
    "gross_margin",
    "opex_pct_of_revenue",
    "d_and_a_pct_of_revenue",
    "capex_pct_of_revenue",
    "nwc_pct_of_revenue",
    "tax_rate",
)


@dataclass
class HistoricalBuildResult:
    historicals: list[HistoricalFinancials]
    currencies: set[str]
    unit_scales: set[str]
    warnings: list[str]


def build_historicals_for_deal(db: Session, deal_id: uuid.UUID) -> HistoricalBuildResult:
    periods = (
        db.query(models.FinancialPeriod)
        .filter_by(deal_id=deal_id, is_historical=True)
        .order_by(models.FinancialPeriod.fiscal_year)
        .all()
    )
    historicals: list[HistoricalFinancials] = []
    currencies: set[str] = set()
    unit_scales: set[str] = set()
    warnings: list[str] = []

    for period in periods:
        approved_items = [li for li in period.line_items if li.mapping_status == "approved" and li.normalized_key]
        by_key: dict[str, float] = {}
        for li in approved_items:
            by_key[li.normalized_key] = by_key.get(li.normalized_key, 0.0) + li.value
            currencies.add(li.currency)
            unit_scales.add(li.unit_scale)

        revenue = by_key.get("revenue")
        if revenue is None:
            warnings.append(f"FY{period.fiscal_year}: no approved 'revenue' line item; skipping this period.")
            continue

        cogs = by_key.get("cost_of_revenue")
        if cogs is None:
            gross_profit = by_key.get("gross_profit")
            cogs = (revenue - gross_profit) if gross_profit is not None else 0.0
            if gross_profit is None:
                warnings.append(f"FY{period.fiscal_year}: no 'cost_of_revenue' or 'gross_profit' mapped; COGS defaulted to 0.")

        opex = sum(by_key.get(k, 0.0) for k in OPEX_KEYS)
        d_and_a = by_key.get("d_and_a") or by_key.get("depreciation_and_amortization") or 0.0
        capex = abs(by_key.get("capex", 0.0))

        current_assets = sum(by_key.get(k, 0.0) for k in CURRENT_ASSET_KEYS)
        current_liabilities = sum(by_key.get(k, 0.0) for k in CURRENT_LIABILITY_KEYS)
        nwc = current_assets - current_liabilities

        income_taxes = by_key.get("income_taxes", 0.0)
        ebit_estimate = revenue - cogs - opex - d_and_a
        tax_rate = (income_taxes / ebit_estimate) if ebit_estimate > 0 else 0.0

        historicals.append(
            HistoricalFinancials(
                fiscal_year=period.fiscal_year,
                revenue=revenue,
                cogs=cogs,
                operating_expenses=opex,
                d_and_a=d_and_a,
                capex=capex,
                net_working_capital=nwc,
                tax_rate=max(min(tax_rate, 1.0), 0.0),
                cash=by_key.get("cash_and_equivalents", 0.0),
                debt=by_key.get("debt", 0.0),
                lease_liabilities=by_key.get("lease_liabilities", 0.0),
                preferred_claims=0.0,
                other_non_operating_assets=0.0,
                diluted_shares_outstanding=by_key.get("diluted_shares_outstanding"),
            )
        )

    return HistoricalBuildResult(historicals=historicals, currencies=currencies, unit_scales=unit_scales, warnings=warnings)


def build_scenario_assumptions(assumption_set: models.AssumptionSet, forecast_years: list[int]) -> ScenarioAssumptions:
    by_year: dict[int, dict[str, float]] = {y: {} for y in forecast_years}
    for a in assumption_set.assumptions:
        if a.fiscal_year in by_year:
            by_year[a.fiscal_year][a.key] = a.value

    years: list[ForecastYear] = []
    missing: list[str] = []
    for fy in forecast_years:
        values = by_year.get(fy, {})
        row = {}
        for key in ASSUMPTION_KEYS:
            if key not in values:
                missing.append(f"FY{fy}:{key}")
            row[key] = values.get(key, 0.0)
        years.append(
            ForecastYear(
                fiscal_year=fy,
                revenue_growth_rate=row["revenue_growth_rate"],
                gross_margin=row["gross_margin"],
                opex_pct_of_revenue=row["opex_pct_of_revenue"],
                d_and_a_pct_of_revenue=row["d_and_a_pct_of_revenue"],
                capex_pct_of_revenue=row["capex_pct_of_revenue"],
                nwc_pct_of_revenue=row["nwc_pct_of_revenue"],
                tax_rate=row["tax_rate"],
            )
        )
    if missing:
        raise ValueError(f"Missing assumption values for: {missing}")
    return ScenarioAssumptions(scenario=assumption_set.scenario, years=years)


def run_scenario(
    db: Session,
    deal: models.Deal,
    assumption_set: models.AssumptionSet,
) -> dict:
    """Run the full forecast -> UFCF -> DCF -> model-checks pipeline for one scenario.

    Returns a plain dict matching schemas.ScenarioResultOut (kept dict-shaped
    here so routers can build the Pydantic model without a second translation
    layer).
    """
    settings = get_settings()
    hist_result = build_historicals_for_deal(db, deal.id)
    if not hist_result.historicals:
        raise ValueError("No approved historical financials with a 'revenue' mapping are available for this deal.")

    last_hist_year = max(h.fiscal_year for h in hist_result.historicals)
    forecast_years = [last_hist_year + i for i in range(1, deal.forecast_years + 1)]

    scenario = build_scenario_assumptions(assumption_set, forecast_years)
    forecast = build_forecast(hist_result.historicals, scenario)

    latest_actual = max(hist_result.historicals, key=lambda h: h.fiscal_year)
    net_debt = build_net_debt_bridge(latest_actual)

    dcf_inputs = DCFInputs(
        ufcf_by_year=forecast.ufcf_by_year(),
        wacc=assumption_set.wacc,
        terminal_growth_rate=assumption_set.terminal_growth_rate,
        valuation_date_fiscal_year=latest_actual.fiscal_year,
        cash=net_debt.cash,
        debt=net_debt.debt,
        lease_liabilities=net_debt.lease_liabilities,
        preferred_claims=net_debt.preferred_claims,
        other_non_operating_assets=net_debt.other_non_operating_assets,
        diluted_shares_outstanding=latest_actual.diluted_shares_outstanding,
    )
    dcf_result = compute_dcf(dcf_inputs, scenario=assumption_set.scenario)

    check_report = run_full_check_suite(
        historicals=hist_result.historicals,
        dcf_result=dcf_result,
        currencies=hist_result.currencies or {deal.currency or "USD"},
        unit_scales=hist_result.unit_scales or {deal.unit_scale},
        terminal_value_threshold_pct=settings.terminal_value_threshold_pct,
    )

    forecast_rows = []
    cf_by_year = {cf.fiscal_year: cf for cf in forecast.cash_flow}
    for line in forecast.income_statement:
        cf = cf_by_year[line.fiscal_year]
        forecast_rows.append(
            {
                "fiscal_year": line.fiscal_year,
                "revenue": line.revenue,
                "cogs": line.cogs,
                "gross_profit": line.gross_profit,
                "operating_expenses": line.operating_expenses,
                "ebitda": line.ebitda,
                "d_and_a": line.d_and_a,
                "ebit": line.ebit,
                "taxes": line.taxes,
                "nopat": line.nopat,
                "capex": cf.capex,
                "change_in_nwc": cf.change_in_nwc,
                "ufcf": cf.ufcf,
            }
        )

    return {
        "scenario": assumption_set.scenario,
        "forecast": forecast_rows,
        "dcf": {
            "scenario": dcf_result.scenario,
            "discounted_years": [
                {
                    "fiscal_year": dy.fiscal_year,
                    "period": dy.period,
                    "ufcf": dy.ufcf,
                    "discount_factor": dy.discount_factor,
                    "present_value": dy.present_value,
                }
                for dy in dcf_result.discounted_years
            ],
            "terminal_year_ufcf": dcf_result.terminal_year_ufcf,
            "terminal_value_undiscounted": dcf_result.terminal_value_undiscounted,
            "pv_terminal_value": dcf_result.pv_terminal_value,
            "pv_explicit_period": dcf_result.pv_explicit_period,
            "enterprise_value": dcf_result.enterprise_value,
            "equity_value": dcf_result.equity_value,
            "implied_value_per_share": dcf_result.implied_value_per_share,
            "terminal_value_pct_of_ev": dcf_result.terminal_value_pct_of_ev,
            "wacc": dcf_result.wacc,
            "terminal_growth_rate": dcf_result.terminal_growth_rate,
        },
        "model_checks": {
            "checks": [
                {"check_id": c.check_id, "passed": c.passed, "message": c.message, "severity": c.severity}
                for c in check_report.checks
            ],
            "has_blocking_failures": check_report.has_blocking_failures,
        },
    }
