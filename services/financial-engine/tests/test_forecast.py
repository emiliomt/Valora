import pytest

from financial_engine.forecast import build_forecast
from financial_engine.schemas import ForecastYear, HistoricalFinancials, ScenarioAssumptions


def _hist(fiscal_year=2024, revenue=1000.0, nwc=100.0):
    return HistoricalFinancials(
        fiscal_year=fiscal_year,
        revenue=revenue,
        cogs=400.0,
        operating_expenses=300.0,
        d_and_a=50.0,
        capex=60.0,
        net_working_capital=nwc,
        tax_rate=0.25,
    )


def _year(fiscal_year, growth=0.10, margin=0.60, opex=0.30, da=0.05, capex=0.06, nwc=0.10, tax=0.25):
    return ForecastYear(
        fiscal_year=fiscal_year,
        revenue_growth_rate=growth,
        gross_margin=margin,
        opex_pct_of_revenue=opex,
        d_and_a_pct_of_revenue=da,
        capex_pct_of_revenue=capex,
        nwc_pct_of_revenue=nwc,
        tax_rate=tax,
    )


def test_single_year_forecast_matches_hand_calculation():
    hist = [_hist()]
    scenario = ScenarioAssumptions(scenario="base", years=[_year(2025)])
    result = build_forecast(hist, scenario)

    line = result.income_statement[0]
    assert line.revenue == pytest.approx(1100.0)
    assert line.gross_profit == pytest.approx(660.0)
    assert line.cogs == pytest.approx(440.0)
    assert line.operating_expenses == pytest.approx(330.0)
    assert line.ebitda == pytest.approx(330.0)
    assert line.d_and_a == pytest.approx(55.0)
    assert line.ebit == pytest.approx(275.0)
    assert line.taxes == pytest.approx(68.75)
    assert line.nopat == pytest.approx(206.25)

    cf = result.cash_flow[0]
    assert cf.capex == pytest.approx(66.0)
    expected_nwc = 1100.0 * 0.10
    assert cf.change_in_nwc == pytest.approx(expected_nwc - 100.0)
    expected_ufcf = 206.25 + 55.0 - 66.0 - (expected_nwc - 100.0)
    assert cf.ufcf == pytest.approx(expected_ufcf)


def test_multi_year_forecast_compounds_revenue():
    hist = [_hist()]
    scenario = ScenarioAssumptions(scenario="base", years=[_year(2025), _year(2026), _year(2027)])
    result = build_forecast(hist, scenario)
    revs = [line.revenue for line in result.income_statement]
    assert revs[0] == pytest.approx(1100.0)
    assert revs[1] == pytest.approx(1100.0 * 1.10)
    assert revs[2] == pytest.approx(1100.0 * 1.10 * 1.10)


def test_taxes_floored_at_zero_ebit():
    hist = [_hist()]
    # Force a negative EBIT: opex + d&a exceed gross profit.
    scenario = ScenarioAssumptions(
        scenario="bear",
        years=[_year(2025, margin=0.30, opex=0.50, da=0.10)],
    )
    result = build_forecast(hist, scenario)
    line = result.income_statement[0]
    assert line.ebit < 0
    assert line.taxes == 0.0
    assert line.nopat == pytest.approx(line.ebit)


def test_rejects_forecast_year_not_after_historicals():
    hist = [_hist(fiscal_year=2025)]
    scenario = ScenarioAssumptions(scenario="base", years=[_year(2024)])
    with pytest.raises(ValueError):
        build_forecast(hist, scenario)


def test_rejects_empty_historicals():
    scenario = ScenarioAssumptions(scenario="base", years=[_year(2025)])
    with pytest.raises(ValueError):
        build_forecast([], scenario)


def test_scenario_rejects_duplicate_fiscal_years():
    with pytest.raises(ValueError):
        ScenarioAssumptions(scenario="base", years=[_year(2025), _year(2025)])


def test_scenario_rejects_empty_years():
    with pytest.raises(ValueError):
        ScenarioAssumptions(scenario="base", years=[])


def test_forecast_uses_last_historical_year_as_anchor_regardless_of_input_order():
    hist_unordered = [_hist(fiscal_year=2024, revenue=1000.0), _hist(fiscal_year=2023, revenue=900.0)]
    scenario = ScenarioAssumptions(scenario="base", years=[_year(2025)])
    result = build_forecast(hist_unordered, scenario)
    assert result.income_statement[0].revenue == pytest.approx(1100.0)
