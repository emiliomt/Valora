"""Unlevered DCF valuation.

Formulas (PRD 7.7 / 7.8, see docs/model-logic.md):

    Discount factor_t = 1 / (1 + WACC) ** t          (t = 1..n, n = years since valuation date)
    PV(UFCF_t)         = UFCF_t * Discount factor_t
    Terminal Value      = UFCF_(n+1) / (WACC - g)      where UFCF_(n+1) = UFCF_n * (1 + g)
    PV(Terminal Value)  = Terminal Value * Discount factor_n
    Enterprise Value    = sum(PV(UFCF_t)) + PV(Terminal Value)
    Equity Value        = Enterprise Value + Cash - Debt - Lease Liabilities
                           - Preferred Claims + Other Non-Operating Assets
    Value per Share     = Equity Value / Diluted Shares Outstanding
"""

from __future__ import annotations

from financial_engine.schemas import DCFInputs, DCFResult, DiscountedYear


def compute_dcf(inputs: DCFInputs, scenario: str = "base") -> DCFResult:
    years_sorted = sorted(inputs.ufcf_by_year.items(), key=lambda kv: kv[0])
    n = len(years_sorted)

    discounted_years: list[DiscountedYear] = []
    pv_explicit_period = 0.0
    for idx, (fiscal_year, ufcf) in enumerate(years_sorted, start=1):
        discount_factor = 1.0 / ((1.0 + inputs.wacc) ** idx)
        pv = ufcf * discount_factor
        pv_explicit_period += pv
        discounted_years.append(
            DiscountedYear(
                fiscal_year=fiscal_year,
                period=idx,
                ufcf=ufcf,
                discount_factor=discount_factor,
                present_value=pv,
            )
        )

    terminal_year_ufcf = years_sorted[-1][1] * (1.0 + inputs.terminal_growth_rate)
    terminal_value_undiscounted = terminal_year_ufcf / (inputs.wacc - inputs.terminal_growth_rate)
    terminal_discount_factor = 1.0 / ((1.0 + inputs.wacc) ** n)
    pv_terminal_value = terminal_value_undiscounted * terminal_discount_factor

    enterprise_value = pv_explicit_period + pv_terminal_value

    equity_value = (
        enterprise_value
        + inputs.cash
        - inputs.debt
        - inputs.lease_liabilities
        - inputs.preferred_claims
        + inputs.other_non_operating_assets
    )

    implied_value_per_share = (
        equity_value / inputs.diluted_shares_outstanding
        if inputs.diluted_shares_outstanding
        else None
    )

    terminal_value_pct_of_ev = (
        pv_terminal_value / enterprise_value if enterprise_value != 0 else 0.0
    )

    return DCFResult(
        scenario=scenario,
        discounted_years=discounted_years,
        terminal_year_ufcf=terminal_year_ufcf,
        terminal_value_undiscounted=terminal_value_undiscounted,
        terminal_value_discount_factor=terminal_discount_factor,
        pv_terminal_value=pv_terminal_value,
        pv_explicit_period=pv_explicit_period,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        implied_value_per_share=implied_value_per_share,
        terminal_value_pct_of_ev=terminal_value_pct_of_ev,
        wacc=inputs.wacc,
        terminal_growth_rate=inputs.terminal_growth_rate,
    )
