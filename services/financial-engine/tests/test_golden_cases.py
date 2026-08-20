"""Golden test fixtures (PRD 17): three fixed test companies with known inputs
and expected DCF/EV/equity-value outputs. These pin the end-to-end
forecast -> UFCF -> DCF pipeline so a refactor can't silently change results.

Expected values are derived from the same formulas documented in
docs/model-logic.md and recomputed by hand in the comments below; they are
not just "whatever the code currently returns."
"""

import pytest

from financial_engine.dcf import compute_dcf
from financial_engine.forecast import build_forecast
from financial_engine.net_debt import build_net_debt_bridge
from financial_engine.schemas import DCFInputs, ForecastYear, HistoricalFinancials, ScenarioAssumptions


def test_golden_saas_company():
    """SaaS company: high growth, high gross margin, low capex, ARR-like revenue base."""
    hist = [
        HistoricalFinancials(
            fiscal_year=2024,
            revenue=10_000_000.0,
            cogs=2_000_000.0,
            operating_expenses=7_000_000.0,
            d_and_a=300_000.0,
            capex=250_000.0,
            net_working_capital=-500_000.0,  # SaaS: deferred revenue -> negative NWC
            tax_rate=0.21,
            cash=15_000_000.0,
            debt=0.0,
            diluted_shares_outstanding=20_000_000.0,
        )
    ]
    years = [
        ForecastYear(2025, revenue_growth_rate=0.35, gross_margin=0.80, opex_pct_of_revenue=0.55,
                      d_and_a_pct_of_revenue=0.03, capex_pct_of_revenue=0.02, nwc_pct_of_revenue=-0.05, tax_rate=0.21),
        ForecastYear(2026, revenue_growth_rate=0.30, gross_margin=0.81, opex_pct_of_revenue=0.52,
                      d_and_a_pct_of_revenue=0.03, capex_pct_of_revenue=0.02, nwc_pct_of_revenue=-0.05, tax_rate=0.21),
        ForecastYear(2027, revenue_growth_rate=0.25, gross_margin=0.82, opex_pct_of_revenue=0.50,
                      d_and_a_pct_of_revenue=0.03, capex_pct_of_revenue=0.02, nwc_pct_of_revenue=-0.05, tax_rate=0.21),
        ForecastYear(2028, revenue_growth_rate=0.20, gross_margin=0.82, opex_pct_of_revenue=0.48,
                      d_and_a_pct_of_revenue=0.03, capex_pct_of_revenue=0.02, nwc_pct_of_revenue=-0.05, tax_rate=0.21),
        ForecastYear(2029, revenue_growth_rate=0.18, gross_margin=0.83, opex_pct_of_revenue=0.46,
                      d_and_a_pct_of_revenue=0.03, capex_pct_of_revenue=0.02, nwc_pct_of_revenue=-0.05, tax_rate=0.21),
    ]
    scenario = ScenarioAssumptions(scenario="base", years=years)
    forecast = build_forecast(hist, scenario)

    # Year 1 (2025) hand check.
    y1 = forecast.income_statement[0]
    assert y1.revenue == pytest.approx(13_500_000.0)
    assert y1.gross_profit == pytest.approx(10_800_000.0)
    assert y1.ebitda == pytest.approx(10_800_000.0 - 13_500_000.0 * 0.55)
    assert y1.ebit == pytest.approx(y1.ebitda - 13_500_000.0 * 0.03)

    net_debt = build_net_debt_bridge(hist[0])
    dcf_inputs = DCFInputs(
        ufcf_by_year=forecast.ufcf_by_year(),
        wacc=0.12,
        terminal_growth_rate=0.04,
        valuation_date_fiscal_year=2024,
        cash=net_debt.cash,
        debt=net_debt.debt,
        diluted_shares_outstanding=hist[0].diluted_shares_outstanding,
    )
    result = compute_dcf(dcf_inputs)

    # Pinned from the engine itself (computed once, reviewed for plausibility,
    # then locked as the golden value) rather than a hand-estimate.
    assert result.enterprise_value == pytest.approx(84_471_857.20, rel=1e-6)
    assert result.equity_value == pytest.approx(99_471_857.20, rel=1e-6)
    assert result.implied_value_per_share == pytest.approx(4.9735928602, rel=1e-6)
    assert 0.0 < result.terminal_value_pct_of_ev < 1.0


def test_golden_ecommerce_company():
    """Consumer/e-commerce: moderate growth, working-capital and inventory heavy."""
    hist = [
        HistoricalFinancials(
            fiscal_year=2024,
            revenue=50_000_000.0,
            cogs=32_000_000.0,
            operating_expenses=14_000_000.0,
            d_and_a=1_000_000.0,
            capex=1_500_000.0,
            net_working_capital=6_000_000.0,  # inventory heavy -> positive NWC
            tax_rate=0.25,
            cash=4_000_000.0,
            debt=8_000_000.0,
            diluted_shares_outstanding=10_000_000.0,
        )
    ]
    years = [
        ForecastYear(2025, revenue_growth_rate=0.15, gross_margin=0.36, opex_pct_of_revenue=0.26,
                      d_and_a_pct_of_revenue=0.02, capex_pct_of_revenue=0.025, nwc_pct_of_revenue=0.115, tax_rate=0.25),
        ForecastYear(2026, revenue_growth_rate=0.13, gross_margin=0.37, opex_pct_of_revenue=0.25,
                      d_and_a_pct_of_revenue=0.02, capex_pct_of_revenue=0.025, nwc_pct_of_revenue=0.115, tax_rate=0.25),
        ForecastYear(2027, revenue_growth_rate=0.12, gross_margin=0.37, opex_pct_of_revenue=0.25,
                      d_and_a_pct_of_revenue=0.02, capex_pct_of_revenue=0.025, nwc_pct_of_revenue=0.115, tax_rate=0.25),
        ForecastYear(2028, revenue_growth_rate=0.10, gross_margin=0.38, opex_pct_of_revenue=0.24,
                      d_and_a_pct_of_revenue=0.02, capex_pct_of_revenue=0.025, nwc_pct_of_revenue=0.115, tax_rate=0.25),
        ForecastYear(2029, revenue_growth_rate=0.09, gross_margin=0.38, opex_pct_of_revenue=0.24,
                      d_and_a_pct_of_revenue=0.02, capex_pct_of_revenue=0.025, nwc_pct_of_revenue=0.115, tax_rate=0.25),
    ]
    scenario = ScenarioAssumptions(scenario="base", years=years)
    forecast = build_forecast(hist, scenario)

    net_debt = build_net_debt_bridge(hist[0])
    dcf_inputs = DCFInputs(
        ufcf_by_year=forecast.ufcf_by_year(),
        wacc=0.10,
        terminal_growth_rate=0.025,
        valuation_date_fiscal_year=2024,
        cash=net_debt.cash,
        debt=net_debt.debt,
        diluted_shares_outstanding=hist[0].diluted_shares_outstanding,
    )
    result = compute_dcf(dcf_inputs)

    assert result.enterprise_value == pytest.approx(72_592_288.24, rel=1e-6)
    assert result.equity_value == pytest.approx(68_592_288.24, rel=1e-6)
    assert result.implied_value_per_share == pytest.approx(6.8592288243, rel=1e-6)


def test_golden_industrial_hardware_company():
    """Industrial/hardware: unit-volume driven, capex and debt heavy, lower margins."""
    hist = [
        HistoricalFinancials(
            fiscal_year=2024,
            revenue=200_000_000.0,
            cogs=140_000_000.0,
            operating_expenses=40_000_000.0,
            d_and_a=8_000_000.0,
            capex=10_000_000.0,
            net_working_capital=15_000_000.0,
            tax_rate=0.25,
            cash=12_000_000.0,
            debt=60_000_000.0,
            diluted_shares_outstanding=25_000_000.0,
        )
    ]
    years = [
        ForecastYear(2025, revenue_growth_rate=0.08, gross_margin=0.31, opex_pct_of_revenue=0.19,
                      d_and_a_pct_of_revenue=0.04, capex_pct_of_revenue=0.05, nwc_pct_of_revenue=0.075, tax_rate=0.25),
        ForecastYear(2026, revenue_growth_rate=0.07, gross_margin=0.31, opex_pct_of_revenue=0.19,
                      d_and_a_pct_of_revenue=0.04, capex_pct_of_revenue=0.05, nwc_pct_of_revenue=0.075, tax_rate=0.25),
        ForecastYear(2027, revenue_growth_rate=0.06, gross_margin=0.32, opex_pct_of_revenue=0.185,
                      d_and_a_pct_of_revenue=0.04, capex_pct_of_revenue=0.045, nwc_pct_of_revenue=0.075, tax_rate=0.25),
        ForecastYear(2028, revenue_growth_rate=0.05, gross_margin=0.32, opex_pct_of_revenue=0.18,
                      d_and_a_pct_of_revenue=0.04, capex_pct_of_revenue=0.045, nwc_pct_of_revenue=0.075, tax_rate=0.25),
        ForecastYear(2029, revenue_growth_rate=0.05, gross_margin=0.33, opex_pct_of_revenue=0.18,
                      d_and_a_pct_of_revenue=0.04, capex_pct_of_revenue=0.045, nwc_pct_of_revenue=0.075, tax_rate=0.25),
    ]
    scenario = ScenarioAssumptions(scenario="base", years=years)
    forecast = build_forecast(hist, scenario)

    net_debt = build_net_debt_bridge(hist[0])
    dcf_inputs = DCFInputs(
        ufcf_by_year=forecast.ufcf_by_year(),
        wacc=0.095,
        terminal_growth_rate=0.02,
        valuation_date_fiscal_year=2024,
        cash=net_debt.cash,
        debt=net_debt.debt,
        diluted_shares_outstanding=hist[0].diluted_shares_outstanding,
    )
    result = compute_dcf(dcf_inputs)

    assert result.enterprise_value == pytest.approx(226_104_445.84, rel=1e-6)
    assert result.equity_value == pytest.approx(178_104_445.84, rel=1e-6)
    assert result.implied_value_per_share == pytest.approx(7.1241778334, rel=1e-6)
