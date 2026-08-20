import pytest

from financial_engine.checks import (
    check_balance_sheet,
    check_currency_and_unit_consistency,
    check_gross_profit_reconciliation,
    check_no_missing_periods,
    check_terminal_value_concentration,
    check_wacc_greater_than_terminal_growth,
    run_full_check_suite,
)
from financial_engine.dcf import compute_dcf
from financial_engine.schemas import DCFInputs, HistoricalFinancials


def _hist(year):
    return HistoricalFinancials(
        fiscal_year=year,
        revenue=1000.0,
        cogs=400.0,
        operating_expenses=300.0,
        d_and_a=50.0,
        capex=60.0,
        net_working_capital=100.0,
        tax_rate=0.25,
    )


def test_balance_sheet_check_passes_within_tolerance():
    result = check_balance_sheet(1000.0, 1004.0)  # 0.4% variance
    assert result.passed


def test_balance_sheet_check_fails_outside_tolerance():
    result = check_balance_sheet(1000.0, 1100.0)  # 10% variance
    assert not result.passed
    assert result.severity == "error"


def test_gross_profit_reconciliation():
    ok = check_gross_profit_reconciliation(revenue=1000.0, cogs=400.0, gross_profit=600.0)
    assert ok.passed
    bad = check_gross_profit_reconciliation(revenue=1000.0, cogs=400.0, gross_profit=550.0)
    assert not bad.passed


def test_wacc_gt_terminal_growth_check():
    assert check_wacc_greater_than_terminal_growth(0.10, 0.03).passed
    assert not check_wacc_greater_than_terminal_growth(0.03, 0.03).passed


def test_terminal_value_concentration_flags_high_concentration():
    inputs = DCFInputs(
        ufcf_by_year={2025: 100.0},
        wacc=0.101,
        terminal_growth_rate=0.10,  # near WACC -> huge TV
        valuation_date_fiscal_year=2024,
        cash=0.0,
        debt=0.0,
    )
    result = compute_dcf(inputs)
    check = check_terminal_value_concentration(result, threshold_pct=0.75)
    assert not check.passed
    assert check.severity == "warning"


def test_no_missing_periods_detects_gap():
    ok = check_no_missing_periods([_hist(2022), _hist(2023), _hist(2024)])
    assert ok.passed
    gap = check_no_missing_periods([_hist(2022), _hist(2024)])
    assert not gap.passed


def test_currency_consistency():
    ok = check_currency_and_unit_consistency({"USD"}, {"millions"})
    assert ok.passed
    bad = check_currency_and_unit_consistency({"USD", "EUR"}, {"millions"})
    assert not bad.passed


def test_full_check_suite_blocking_failure_flagged():
    inputs = DCFInputs(
        ufcf_by_year={2025: 100.0},
        wacc=0.10,
        terminal_growth_rate=0.03,
        valuation_date_fiscal_year=2024,
        cash=0.0,
        debt=0.0,
    )
    dcf_result = compute_dcf(inputs)
    report = run_full_check_suite(
        historicals=[_hist(2022), _hist(2024)],  # gap
        dcf_result=dcf_result,
        currencies={"USD"},
        unit_scales={"millions"},
    )
    assert report.has_blocking_failures
    assert any(c.check_id == "no_missing_historical_periods" for c in report.failures)


def test_full_check_suite_all_pass():
    inputs = DCFInputs(
        ufcf_by_year={2025: 100.0},
        wacc=0.10,
        terminal_growth_rate=0.03,
        valuation_date_fiscal_year=2024,
        cash=0.0,
        debt=0.0,
    )
    dcf_result = compute_dcf(inputs)
    report = run_full_check_suite(
        historicals=[_hist(2022), _hist(2023), _hist(2024)],
        dcf_result=dcf_result,
        currencies={"USD"},
        unit_scales={"millions"},
    )
    assert not report.has_blocking_failures
