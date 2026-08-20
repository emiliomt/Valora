# Model Logic

Authoritative reference for every financial formula, accounting definition, unit, and edge case
implemented in `services/financial-engine`. PRD §21: "Maintain a `docs/model-logic.md` document
explaining all financial formulas, accounting definitions, units, and edge cases." If this
document and the code ever disagree, the code's unit tests (`services/financial-engine/tests`)
are the tiebreaker — file a fix so they agree again.

All calculation logic lives in `services/financial-engine`, as pure, side-effect-free Python
functions with no database, web framework, or LLM dependency (PRD §21). The API layer
(`apps/api/app/services/engine_bridge.py`) only maps database rows into these functions' input
shapes and back — it never re-implements a formula.

## 1. Units, currency, and sign conventions

- Every `HistoricalFinancials` and `ForecastYear` value is in the deal's reporting currency and
  unit scale (actuals / thousands / millions), consistent across the whole set — mixing currencies
  or unit scales within one deal is a blocking model check (`check_currency_and_unit_consistency`).
- Revenue, COGS, operating expenses, D&A, and capex are all **positive** numbers. The engine
  applies signs internally (e.g. `COGS` is subtracted from `Revenue`, `Capex` is subtracted in the
  UFCF build).
- Net working capital (`net_working_capital` / `nwc_pct_of_revenue`) can be **negative** — this is
  normal and expected for businesses with float or deferred revenue (subscription/SaaS businesses
  in particular; see the SaaS golden test case in §6).

## 2. Forecast build (`financial_engine.forecast.build_forecast`)

Driver-based, one `ForecastYear` per forecast fiscal year, anchored off the **last historical
fiscal year** supplied (`HistoricalFinancials`, sorted ascending, last element = anchor):

```
Revenue_t         = Revenue_(t-1) * (1 + revenue_growth_rate_t)
Gross Profit_t    = Revenue_t * gross_margin_t
COGS_t            = Revenue_t - Gross Profit_t
Opex_t            = Revenue_t * opex_pct_of_revenue_t
EBITDA_t          = Gross Profit_t - Opex_t
D&A_t             = Revenue_t * d_and_a_pct_of_revenue_t
EBIT_t            = EBITDA_t - D&A_t
Taxes_t           = max(EBIT_t, 0) * tax_rate_t
NOPAT_t           = EBIT_t - Taxes_t          (== EBIT_t * (1 - tax_rate_t) when EBIT_t >= 0)
Capex_t           = Revenue_t * capex_pct_of_revenue_t
NWC_t             = Revenue_t * nwc_pct_of_revenue_t
Change in NWC_t   = NWC_t - NWC_(t-1)
UFCF_t            = NOPAT_t + D&A_t - Capex_t - Change in NWC_t
```

**Edge case — negative EBIT:** taxes are floored at `EBIT >= 0` (no tax benefit / NOL modeling in
the MVP driver model). A loss-making forecast year has `Taxes_t = 0` and `NOPAT_t = EBIT_t`
(negative). This is standard unlevered-DCF convention; it does not model deferred tax assets.

**Edge case — first forecast year:** must have a `fiscal_year` strictly after the last historical
fiscal year, or `build_forecast` raises `ValueError`. Historical years may be passed out of order;
the anchor is always `max(fiscal_year)`.

**Edge case — empty inputs:** an empty `historicals` list or an empty `ScenarioAssumptions.years`
both raise `ValueError` rather than silently returning zeros.

## 3. Unlevered free cash flow DCF (`financial_engine.dcf.compute_dcf`)

```
Discount Factor_t   = 1 / (1 + WACC)^t                       (t = 1..n, n = number of forecast years)
PV(UFCF_t)          = UFCF_t * Discount Factor_t
Terminal-Year UFCF   = UFCF_n * (1 + terminal growth rate)
Terminal Value       = Terminal-Year UFCF / (WACC - terminal growth rate)
PV(Terminal Value)   = Terminal Value * Discount Factor_n      (i.e. discounted at the SAME factor as year n)
Enterprise Value     = sum(PV(UFCF_t) for t=1..n) + PV(Terminal Value)
Equity Value          = Enterprise Value + Cash - Debt - Lease Liabilities
                         - Preferred Claims + Other Non-Operating Assets
Value per Share       = Equity Value / Diluted Shares Outstanding   (None if share count unknown)
TV % of EV            = PV(Terminal Value) / Enterprise Value
```

**Edge case — WACC vs. terminal growth:** `DCFInputs.__post_init__` (and `Assumptions`) raise
`ValueError` if `WACC <= terminal_growth_rate` — this is enforced at construction time, not just
as a warning, per PRD §7.6/§12 ("The system prevents terminal growth from being equal to or
greater than WACC"). The API layer surfaces this as an HTTP 400 on assumption-set save.

**Edge case — empty UFCF schedule:** `DCFInputs` requires at least one forecast-year UFCF value.

**Discount timing convention:** the valuation date is fiscal year "0"; the first forecast year is
discounted at `t=1`. `valuation_date_fiscal_year` is carried on `DCFInputs` for traceability but
the discount exponent is derived from the *position* of each year in the sorted UFCF schedule, not
by subtracting fiscal years — so a schedule with a gap year is still discounted by consecutive
integer periods (1, 2, 3, …), matching how the forecast engine always produces consecutive
fiscal years.

## 4. Net debt bridge (`financial_engine.net_debt.build_net_debt_bridge`)

Built from a single `HistoricalFinancials` snapshot (the latest actual, point-in-time balance
sheet) so every component shares one balance-sheet date, per PRD §12 ("Net debt bridge must use a
consistent point-in-time balance date"):

```
Net Debt = Debt + Lease Liabilities + Preferred Claims - Cash - Other Non-Operating Assets
```

`NetDebtBridge` exposes the four raw components plus the derived `net_debt` property; the DCF
consumes the raw components directly (see §3's Equity Value formula) rather than the netted figure,
so each line stays individually visible in the export and API response.

## 5. Sensitivities (`financial_engine.sensitivity`)

- **WACC × terminal growth** (`wacc_vs_terminal_growth_grid`): re-runs `compute_dcf` at every
  `(wacc, terminal_growth_rate)` pair in the grid, holding UFCF fixed. A cell where
  `wacc <= terminal_growth_rate` is invalid and rendered as `NaN` rather than raising, so the rest
  of the grid still renders.
- **Revenue growth × gross margin** (`revenue_growth_vs_margin_grid`): applies an *additive delta*
  to every forecast year's `revenue_growth_rate` / `gross_margin` in the base scenario, re-runs
  the full forecast (not just the DCF), then re-runs the DCF. This is the more expensive grid
  because it re-derives UFCF at every cell, not just the discounting.
- Both grid functions are pure: the `DCFInputs` / `ScenarioAssumptions` passed in are never
  mutated (verified by `test_sensitivity.py`), using `dataclasses.replace` to build each cell's
  inputs.

## 6. Golden test cases (PRD §17)

`services/financial-engine/tests/test_golden_cases.py` pins three fixed companies end-to-end
(forecast → UFCF → DCF), each with hand-checkable first-year figures plus a locked enterprise
value / equity value / value-per-share triplet regenerated directly from the engine (not
estimated by hand) so a future refactor can't silently change results without a test failing:

1. **SaaS** — high growth (35%→18%), high gross margin (80-83%), negative NWC (deferred revenue).
2. **Consumer/e-commerce** — moderate growth (15%→9%), inventory-driven positive NWC, thinner
   margins.
3. **Industrial/hardware** — low growth (8%→5%), capex- and debt-heavy, lowest margins of the
   three.

## 7. Model checks (`financial_engine.checks`)

| check_id | Severity | What it verifies |
|---|---|---|
| `balance_sheet_balances` | error | `abs(Assets - (Liabilities+Equity)) / Assets <= 0.5%` (PRD §12 default tolerance) |
| `gross_profit_reconciles` | error | `Revenue - COGS == Gross Profit` |
| `wacc_gt_terminal_growth` | error | `WACC > terminal growth rate` |
| `terminal_value_concentration` | warning | `PV(Terminal Value) / EV <= 75%` (configurable) |
| `no_missing_historical_periods` | error | historical fiscal years are contiguous (no gaps) |
| `currency_and_unit_consistency` | error | exactly one currency and one unit scale observed |

`ModelCheckReport.has_blocking_failures` is `True` if any **error**-severity check fails.
`apps/api` blocks `ModelVersion` approval while `has_blocking_failures` is true (PRD §7.4/§7.16 —
"No valuation can be marked approved when material unresolved mappings or failed balance checks
exist"); this MVP does not yet implement the explicit-override escape hatch PRD §7.4 describes, so
the block is currently hard rather than override-able.

## 8. Reconciliation thresholds (PRD §12)

```
Model reconciliation:      < 0.5% variance
Balance-sheet check:       < 0.5% of total assets
Export (app vs. XLSX) comparison: < 0.1% variance
```

The Excel exporter (`apps/api/app/services/xlsx_export.py`) keeps the DCF sheet's discount
factors, PV rollups, terminal value, and enterprise value as **live Excel formulas** referencing
the same WACC/terminal-growth cells and the UFCF computed on the Revenue Build sheet — not just
pasted-in numbers — specifically so the workbook's own recalculation reproduces the app's
`enterprise_value` within the 0.1% export-comparison tolerance.
