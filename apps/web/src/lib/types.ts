// Mirrors apps/api/app/schemas.py. Kept as plain TS types (PRD 21: "Define
// Pydantic and Zod schemas before implementing API endpoints and UI forms") —
// Zod schemas for the two write-heavy forms (deal create, assumptions) live
// alongside their components.

export interface Workspace {
  id: string;
  name: string;
}

export interface Deal {
  id: string;
  workspace_id: string;
  company_name: string;
  ticker: string | null;
  exchange: string | null;
  investment_type: string;
  industry: string;
  subsector: string | null;
  country: string | null;
  currency: string | null;
  unit_scale: string;
  valuation_date: string | null;
  fiscal_year_end: string | null;
  forecast_years: number;
  investment_thesis: string | null;
  status: string;
  ready_for_valuation: boolean;
}

export interface SourceDocument {
  id: string;
  deal_id: string;
  filename: string;
  mime_type: string;
  document_type: string;
  processing_status: string;
  processing_error: string | null;
}

export interface FinancialLineItem {
  id: string;
  period_id: string;
  statement_type: string;
  reported_label: string;
  normalized_key: string | null;
  value: number;
  currency: string;
  unit_scale: string;
  mapping_status: string;
  confidence_score: number | null;
}

export interface FinancialPeriod {
  id: string;
  fiscal_year: number;
  period_type: string;
  is_historical: boolean;
  line_items: FinancialLineItem[];
}

export interface ImportResult {
  document_id: string;
  periods_created: number;
  line_items_created: number;
  unresolved_mappings: number;
  warnings: string[];
}

export interface ModelCheck {
  check_id: string;
  passed: boolean;
  message: string;
  severity: "error" | "warning";
}

export interface ModelChecksReport {
  checks: ModelCheck[];
  has_blocking_failures: boolean;
}

export type AssumptionOrigin = "user" | "management_guidance" | "third_party" | "ai_suggested" | "calculated";

export interface Assumption {
  id: string;
  key: string;
  label: string;
  fiscal_year: number;
  value: number;
  unit: string;
  origin: AssumptionOrigin;
  rationale: string | null;
  is_locked: boolean;
}

export interface AssumptionSet {
  id: string;
  scenario: string;
  name: string;
  status: string;
  wacc: number;
  terminal_growth_rate: number;
  assumptions: Assumption[];
}

export interface ModelVersion {
  id: string;
  deal_id: string;
  name: string;
  status: string;
  scenario_default: string;
  approved_at: string | null;
}

export interface ForecastYearRow {
  fiscal_year: number;
  revenue: number;
  cogs: number;
  gross_profit: number;
  operating_expenses: number;
  ebitda: number;
  d_and_a: number;
  ebit: number;
  taxes: number;
  nopat: number;
  capex: number;
  change_in_nwc: number;
  ufcf: number;
}

export interface DiscountedYear {
  fiscal_year: number;
  period: number;
  ufcf: number;
  discount_factor: number;
  present_value: number;
}

export interface DCFResult {
  scenario: string;
  discounted_years: DiscountedYear[];
  terminal_year_ufcf: number;
  terminal_value_undiscounted: number;
  pv_terminal_value: number;
  pv_explicit_period: number;
  enterprise_value: number;
  equity_value: number;
  implied_value_per_share: number | null;
  terminal_value_pct_of_ev: number;
  wacc: number;
  terminal_growth_rate: number;
}

export interface ScenarioResult {
  scenario: string;
  forecast: ForecastYearRow[];
  dcf: DCFResult;
  model_checks: ModelChecksReport;
}

export interface ValuationRunOut {
  scenarios: Record<string, ScenarioResult>;
}

export interface SensitivityGrid {
  row_label: string;
  column_label: string;
  row_values: number[];
  column_values: number[];
  grid: (number | null)[][];
  metric: string;
}

export const ASSUMPTION_KEYS = [
  "revenue_growth_rate",
  "gross_margin",
  "opex_pct_of_revenue",
  "d_and_a_pct_of_revenue",
  "capex_pct_of_revenue",
  "nwc_pct_of_revenue",
  "tax_rate",
] as const;

export const ASSUMPTION_LABELS: Record<(typeof ASSUMPTION_KEYS)[number], string> = {
  revenue_growth_rate: "Revenue growth",
  gross_margin: "Gross margin",
  opex_pct_of_revenue: "Opex % of revenue",
  d_and_a_pct_of_revenue: "D&A % of revenue",
  capex_pct_of_revenue: "Capex % of revenue",
  nwc_pct_of_revenue: "NWC % of revenue",
  tax_rate: "Tax rate",
};

export const SCENARIOS = ["base", "bull", "bear"] as const;
export type Scenario = (typeof SCENARIOS)[number];
