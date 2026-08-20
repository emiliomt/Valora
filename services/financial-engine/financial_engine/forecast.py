"""Driver-based five-year (configurable) forecast engine.

Formulas (see docs/model-logic.md for the authoritative writeup):

    Revenue_t        = Revenue_(t-1) * (1 + revenue_growth_rate_t)
    Gross Profit_t    = Revenue_t * gross_margin_t
    COGS_t            = Revenue_t - Gross Profit_t
    Opex_t            = Revenue_t * opex_pct_of_revenue_t
    EBITDA_t          = Gross Profit_t - Opex_t
    D&A_t             = Revenue_t * d_and_a_pct_of_revenue_t
    EBIT_t            = EBITDA_t - D&A_t
    Taxes_t           = max(EBIT_t, 0) * tax_rate_t
    NOPAT_t           = EBIT_t - Taxes_t   (== EBIT_t * (1 - tax_rate_t) when EBIT_t >= 0)
    Capex_t           = Revenue_t * capex_pct_of_revenue_t
    NWC_t             = Revenue_t * nwc_pct_of_revenue_t
    Change in NWC_t   = NWC_t - NWC_(t-1)
    UFCF_t            = NOPAT_t + D&A_t - Capex_t - Change in NWC_t

Taxes are floored at EBIT >= 0 (no tax benefit modeled on operating losses in
the MVP driver model) — this mirrors standard unlevered DCF convention and is
called out explicitly in docs/model-logic.md.
"""

from __future__ import annotations

from financial_engine.schemas import (
    CashFlowLine,
    ForecastResult,
    HistoricalFinancials,
    IncomeStatementLine,
    ScenarioAssumptions,
)


def build_forecast(
    historicals: list[HistoricalFinancials],
    scenario: ScenarioAssumptions,
) -> ForecastResult:
    """Build a full forecast income statement + UFCF schedule for one scenario.

    `historicals` must be sorted ascending by fiscal_year and contain at
    least one year (the anchor year the first forecast year grows off of).
    """
    if not historicals:
        raise ValueError("build_forecast requires at least one historical year")

    sorted_hist = sorted(historicals, key=lambda h: h.fiscal_year)
    sorted_years = sorted(scenario.years, key=lambda y: y.fiscal_year)

    last_hist = sorted_hist[-1]
    first_forecast_year = sorted_years[0].fiscal_year
    if first_forecast_year <= last_hist.fiscal_year:
        raise ValueError(
            "First forecast fiscal_year must be after the last historical fiscal_year "
            f"(last historical={last_hist.fiscal_year}, first forecast={first_forecast_year})"
        )

    income_statement: list[IncomeStatementLine] = []
    cash_flow: list[CashFlowLine] = []

    prior_revenue = last_hist.revenue
    prior_nwc = last_hist.net_working_capital

    for year in sorted_years:
        revenue = prior_revenue * (1.0 + year.revenue_growth_rate)
        gross_profit = revenue * year.gross_margin
        cogs = revenue - gross_profit
        opex = revenue * year.opex_pct_of_revenue
        ebitda = gross_profit - opex
        d_and_a = revenue * year.d_and_a_pct_of_revenue
        ebit = ebitda - d_and_a
        taxes = max(ebit, 0.0) * year.tax_rate
        nopat = ebit - taxes

        capex = revenue * year.capex_pct_of_revenue
        nwc = revenue * year.nwc_pct_of_revenue
        change_in_nwc = nwc - prior_nwc
        ufcf = nopat + d_and_a - capex - change_in_nwc

        income_statement.append(
            IncomeStatementLine(
                fiscal_year=year.fiscal_year,
                revenue=revenue,
                cogs=cogs,
                gross_profit=gross_profit,
                operating_expenses=opex,
                ebitda=ebitda,
                d_and_a=d_and_a,
                ebit=ebit,
                taxes=taxes,
                nopat=nopat,
            )
        )
        cash_flow.append(
            CashFlowLine(
                fiscal_year=year.fiscal_year,
                nopat=nopat,
                d_and_a=d_and_a,
                capex=capex,
                change_in_nwc=change_in_nwc,
                ufcf=ufcf,
            )
        )

        prior_revenue = revenue
        prior_nwc = nwc

    return ForecastResult(scenario=scenario.scenario, income_statement=income_statement, cash_flow=cash_flow)
