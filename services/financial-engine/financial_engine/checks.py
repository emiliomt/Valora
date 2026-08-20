"""Model validation checks (PRD 7.4, 7.7, 7.8, 12).

These checks never mutate inputs; they only observe and report. A blocking
("error" severity) failure should prevent a model version from being marked
Approved unless the user records an explicit override (enforced at the API
layer, not here).
"""

from __future__ import annotations

from financial_engine.schemas import (
    DCFResult,
    HistoricalFinancials,
    ModelCheckReport,
    ModelCheckResult,
)

DEFAULT_BALANCE_SHEET_TOLERANCE_PCT = 0.005  # 0.5% of total assets, PRD 12
DEFAULT_TERMINAL_VALUE_PCT_THRESHOLD = 0.75  # PRD 7.8 default 75%
DEFAULT_RECONCILIATION_TOLERANCE_PCT = 0.005  # 0.5%, PRD 12


def check_balance_sheet(
    total_assets: float,
    total_liabilities_and_equity: float,
    tolerance_pct: float = DEFAULT_BALANCE_SHEET_TOLERANCE_PCT,
) -> ModelCheckResult:
    if total_assets == 0:
        passed = total_liabilities_and_equity == 0
        variance_pct = 0.0 if passed else float("inf")
    else:
        variance_pct = abs(total_assets - total_liabilities_and_equity) / abs(total_assets)
        passed = variance_pct <= tolerance_pct
    return ModelCheckResult(
        check_id="balance_sheet_balances",
        passed=passed,
        message=(
            f"Assets ({total_assets:,.2f}) vs Liabilities+Equity ({total_liabilities_and_equity:,.2f}); "
            f"variance {variance_pct:.4%} (tolerance {tolerance_pct:.2%})"
        ),
        severity="error",
    )


def check_gross_profit_reconciliation(revenue: float, cogs: float, gross_profit: float) -> ModelCheckResult:
    expected = revenue - cogs
    passed = abs(expected - gross_profit) < 1e-6
    return ModelCheckResult(
        check_id="gross_profit_reconciles",
        passed=passed,
        message=f"Revenue - COGS = {expected:,.2f}, reported Gross Profit = {gross_profit:,.2f}",
        severity="error",
    )


def check_wacc_greater_than_terminal_growth(wacc: float, terminal_growth_rate: float) -> ModelCheckResult:
    passed = wacc > terminal_growth_rate
    return ModelCheckResult(
        check_id="wacc_gt_terminal_growth",
        passed=passed,
        message=f"WACC={wacc:.4%}, Terminal Growth={terminal_growth_rate:.4%}",
        severity="error",
    )


def check_terminal_value_concentration(
    dcf_result: DCFResult,
    threshold_pct: float = DEFAULT_TERMINAL_VALUE_PCT_THRESHOLD,
) -> ModelCheckResult:
    passed = dcf_result.terminal_value_pct_of_ev <= threshold_pct
    return ModelCheckResult(
        check_id="terminal_value_concentration",
        passed=passed,
        message=(
            f"Terminal value is {dcf_result.terminal_value_pct_of_ev:.2%} of enterprise value "
            f"(threshold {threshold_pct:.2%})"
        ),
        severity="warning",
    )


def check_no_missing_periods(historicals: list[HistoricalFinancials]) -> ModelCheckResult:
    years = sorted(h.fiscal_year for h in historicals)
    gaps = [b - a for a, b in zip(years, years[1:])]
    passed = all(g == 1 for g in gaps) if years else False
    return ModelCheckResult(
        check_id="no_missing_historical_periods",
        passed=passed,
        message=f"Historical fiscal years: {years}" if years else "No historical periods supplied",
        severity="error",
    )


def check_currency_and_unit_consistency(currencies: set[str], unit_scales: set[str]) -> ModelCheckResult:
    passed = len(currencies) <= 1 and len(unit_scales) <= 1
    return ModelCheckResult(
        check_id="currency_and_unit_consistency",
        passed=passed,
        message=f"Currencies observed: {sorted(currencies)}; unit scales observed: {sorted(unit_scales)}",
        severity="error",
    )


def run_full_check_suite(
    *,
    historicals: list[HistoricalFinancials],
    dcf_result: DCFResult,
    currencies: set[str],
    unit_scales: set[str],
    terminal_value_threshold_pct: float = DEFAULT_TERMINAL_VALUE_PCT_THRESHOLD,
) -> ModelCheckReport:
    checks = [
        check_no_missing_periods(historicals),
        check_wacc_greater_than_terminal_growth(dcf_result.wacc, dcf_result.terminal_growth_rate),
        check_terminal_value_concentration(dcf_result, terminal_value_threshold_pct),
        check_currency_and_unit_consistency(currencies, unit_scales),
    ]
    return ModelCheckReport(checks=checks)
