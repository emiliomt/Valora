"""Sensitivity grids (PRD 7.8).

All sensitivity functions are pure: given the same UFCF schedule and axis
values, they return the same grid. They never mutate the DCFInputs passed in.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from financial_engine.dcf import compute_dcf
from financial_engine.forecast import build_forecast
from financial_engine.schemas import (
    DCFInputs,
    HistoricalFinancials,
    ScenarioAssumptions,
)


@dataclass(frozen=True)
class SensitivityGrid:
    row_label: str
    column_label: str
    row_values: list[float]
    column_values: list[float]
    # grid[row_index][col_index] = enterprise value (or equity value)
    grid: list[list[float]]
    metric: str = "enterprise_value"


def wacc_vs_terminal_growth_grid(
    base_inputs: DCFInputs,
    wacc_values: list[float],
    terminal_growth_values: list[float],
    metric: str = "enterprise_value",
) -> SensitivityGrid:
    """2-D sensitivity of EV (or equity value) to WACC (rows) x terminal growth (cols)."""
    grid: list[list[float]] = []
    for wacc in wacc_values:
        row: list[float] = []
        for g in terminal_growth_values:
            if wacc <= g:
                row.append(float("nan"))
                continue
            inputs = replace(base_inputs, wacc=wacc, terminal_growth_rate=g)
            result = compute_dcf(inputs)
            row.append(result.enterprise_value if metric == "enterprise_value" else result.equity_value)
        grid.append(row)
    return SensitivityGrid(
        row_label="WACC",
        column_label="Terminal Growth Rate",
        row_values=wacc_values,
        column_values=terminal_growth_values,
        grid=grid,
        metric=metric,
    )


def revenue_growth_vs_margin_grid(
    historicals: list[HistoricalFinancials],
    base_scenario: ScenarioAssumptions,
    dcf_static_inputs: DCFInputs,
    revenue_growth_deltas: list[float],
    gross_margin_deltas: list[float],
    metric: str = "enterprise_value",
) -> SensitivityGrid:
    """2-D sensitivity of EV to a uniform shift in revenue growth (rows) x gross margin (cols).

    Deltas are applied additively to every forecast year's revenue_growth_rate /
    gross_margin in the base scenario, then the full forecast + DCF is re-run.
    `dcf_static_inputs.ufcf_by_year` is ignored/overwritten per cell; wacc,
    terminal_growth_rate, and balance-sheet items are held constant.
    """
    grid: list[list[float]] = []
    for dg in revenue_growth_deltas:
        row: list[float] = []
        for dm in gross_margin_deltas:
            shifted_years = [
                replace(
                    y,
                    revenue_growth_rate=y.revenue_growth_rate + dg,
                    gross_margin=y.gross_margin + dm,
                )
                for y in base_scenario.years
            ]
            shifted_scenario = ScenarioAssumptions(scenario=base_scenario.scenario, years=shifted_years)
            forecast = build_forecast(historicals, shifted_scenario)
            inputs = replace(dcf_static_inputs, ufcf_by_year=forecast.ufcf_by_year())
            result = compute_dcf(inputs)
            row.append(result.enterprise_value if metric == "enterprise_value" else result.equity_value)
        grid.append(row)
    return SensitivityGrid(
        row_label="Revenue Growth Δ",
        column_label="Gross Margin Δ",
        row_values=revenue_growth_deltas,
        column_values=gross_margin_deltas,
        grid=grid,
        metric=metric,
    )
