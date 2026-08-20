import math

import pytest

from financial_engine.dcf import compute_dcf
from financial_engine.forecast import build_forecast
from financial_engine.schemas import DCFInputs, ForecastYear, HistoricalFinancials, ScenarioAssumptions
from financial_engine.sensitivity import revenue_growth_vs_margin_grid, wacc_vs_terminal_growth_grid


def test_wacc_vs_terminal_growth_grid_shape_and_monotonicity():
    base_inputs = DCFInputs(
        ufcf_by_year={2025: 100.0, 2026: 110.0},
        wacc=0.10,
        terminal_growth_rate=0.03,
        valuation_date_fiscal_year=2024,
        cash=0.0,
        debt=0.0,
    )
    wacc_values = [0.08, 0.10, 0.12]
    g_values = [0.02, 0.03]
    grid = wacc_vs_terminal_growth_grid(base_inputs, wacc_values, g_values)

    assert len(grid.grid) == 3
    assert all(len(row) == 2 for row in grid.grid)

    # Higher WACC -> lower enterprise value, holding g fixed.
    col0 = [row[0] for row in grid.grid]
    assert col0[0] > col0[1] > col0[2]

    # Original base_inputs must not be mutated.
    assert base_inputs.wacc == 0.10
    assert base_inputs.terminal_growth_rate == 0.03


def test_wacc_vs_terminal_growth_grid_invalid_cell_is_nan():
    base_inputs = DCFInputs(
        ufcf_by_year={2025: 100.0},
        wacc=0.10,
        terminal_growth_rate=0.03,
        valuation_date_fiscal_year=2024,
        cash=0.0,
        debt=0.0,
    )
    grid = wacc_vs_terminal_growth_grid(base_inputs, [0.05], [0.05])
    assert math.isnan(grid.grid[0][0])


def _hist():
    return [
        HistoricalFinancials(
            fiscal_year=2024,
            revenue=1000.0,
            cogs=400.0,
            operating_expenses=300.0,
            d_and_a=50.0,
            capex=60.0,
            net_working_capital=100.0,
            tax_rate=0.25,
        )
    ]


def _scenario():
    return ScenarioAssumptions(
        scenario="base",
        years=[
            ForecastYear(
                fiscal_year=2025,
                revenue_growth_rate=0.10,
                gross_margin=0.60,
                opex_pct_of_revenue=0.30,
                d_and_a_pct_of_revenue=0.05,
                capex_pct_of_revenue=0.06,
                nwc_pct_of_revenue=0.10,
                tax_rate=0.25,
            )
        ],
    )


def test_revenue_growth_vs_margin_grid_higher_growth_higher_ev():
    hist = _hist()
    scenario = _scenario()
    forecast = build_forecast(hist, scenario)
    static_inputs = DCFInputs(
        ufcf_by_year=forecast.ufcf_by_year(),
        wacc=0.10,
        terminal_growth_rate=0.03,
        valuation_date_fiscal_year=2024,
        cash=0.0,
        debt=0.0,
    )
    grid = revenue_growth_vs_margin_grid(
        hist, scenario, static_inputs, revenue_growth_deltas=[-0.02, 0.0, 0.02], gross_margin_deltas=[0.0]
    )
    values = [row[0] for row in grid.grid]
    assert values[0] < values[1] < values[2]
