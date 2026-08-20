"""Pydantic request/response schemas (PRD 21: "Define Pydantic and Zod schemas
before implementing API endpoints and UI forms")."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth / users / workspaces
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    email: EmailStr
    name: str = ""
    password: str = Field(min_length=8)


class UserOut(OrmBase):
    id: uuid.UUID
    email: str
    name: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be blank")
        return stripped


class WorkspaceOut(OrmBase):
    id: uuid.UUID
    name: str


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------


class DealCreate(BaseModel):
    workspace_id: uuid.UUID
    company_name: str = Field(min_length=1, max_length=255)
    ticker: str | None = None
    exchange: str | None = None
    investment_type: str = "Public Equity"
    industry: str = "general"
    subsector: str | None = None
    country: str | None = None
    currency: str | None = None
    unit_scale: str = "actuals"
    valuation_date: dt.date | None = None
    fiscal_year_end: str | None = None
    forecast_years: int = 5
    investment_thesis: str | None = None

    @field_validator("company_name")
    @classmethod
    def strip_company_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("company_name cannot be blank")
        return stripped


class DealUpdate(BaseModel):
    company_name: str | None = None
    ticker: str | None = None
    exchange: str | None = None
    investment_type: str | None = None
    industry: str | None = None
    subsector: str | None = None
    country: str | None = None
    currency: str | None = None
    unit_scale: str | None = None
    valuation_date: dt.date | None = None
    fiscal_year_end: str | None = None
    forecast_years: int | None = None
    investment_thesis: str | None = None
    status: str | None = None


class DealOut(OrmBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    company_name: str
    ticker: str | None
    exchange: str | None
    investment_type: str
    industry: str
    subsector: str | None
    country: str | None
    currency: str | None
    unit_scale: str
    valuation_date: dt.date | None
    fiscal_year_end: str | None
    forecast_years: int
    investment_thesis: str | None
    status: str
    ready_for_valuation: bool = False


# ---------------------------------------------------------------------------
# Source documents
# ---------------------------------------------------------------------------


class SourceDocumentOut(OrmBase):
    id: uuid.UUID
    deal_id: uuid.UUID
    filename: str
    mime_type: str
    document_type: str
    processing_status: str
    processing_error: str | None


# ---------------------------------------------------------------------------
# Financials
# ---------------------------------------------------------------------------


class FinancialLineItemOut(OrmBase):
    id: uuid.UUID
    period_id: uuid.UUID
    statement_type: str
    reported_label: str
    normalized_key: str | None
    value: float
    currency: str
    unit_scale: str
    mapping_status: str
    confidence_score: float | None


class FinancialLineItemUpdate(BaseModel):
    normalized_key: str | None = None
    mapping_status: str | None = None
    value: float | None = None


class FinancialPeriodOut(OrmBase):
    id: uuid.UUID
    fiscal_year: int
    period_type: str
    is_historical: bool
    line_items: list[FinancialLineItemOut] = []


class ImportResult(BaseModel):
    document_id: uuid.UUID
    periods_created: int
    line_items_created: int
    unresolved_mappings: int
    warnings: list[str] = []


class ModelCheckOut(BaseModel):
    check_id: str
    passed: bool
    message: str
    severity: str


class ModelChecksReport(BaseModel):
    checks: list[ModelCheckOut]
    has_blocking_failures: bool


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------


class AssumptionIn(BaseModel):
    key: str
    label: str = ""
    fiscal_year: int
    value: float
    unit: str = "pct"
    origin: str = "user"
    rationale: str | None = None
    is_locked: bool = False


class AssumptionOut(OrmBase):
    id: uuid.UUID
    key: str
    label: str
    fiscal_year: int
    value: float
    unit: str
    origin: str
    rationale: str | None
    is_locked: bool


class AssumptionSetUpsert(BaseModel):
    scenario: str
    name: str = ""
    wacc: float = 0.10
    terminal_growth_rate: float = 0.025
    assumptions: list[AssumptionIn] = []


class AssumptionSetOut(OrmBase):
    id: uuid.UUID
    scenario: str
    name: str
    status: str
    wacc: float
    terminal_growth_rate: float
    assumptions: list[AssumptionOut] = []


# ---------------------------------------------------------------------------
# Model versions / valuation
# ---------------------------------------------------------------------------


class ModelVersionCreate(BaseModel):
    name: str
    scenario_default: str = "base"


class ModelVersionOut(OrmBase):
    id: uuid.UUID
    deal_id: uuid.UUID
    name: str
    status: str
    scenario_default: str
    approved_at: dt.datetime | None


class ForecastYearOut(BaseModel):
    fiscal_year: int
    revenue: float
    cogs: float
    gross_profit: float
    operating_expenses: float
    ebitda: float
    d_and_a: float
    ebit: float
    taxes: float
    nopat: float
    capex: float
    change_in_nwc: float
    ufcf: float


class DiscountedYearOut(BaseModel):
    fiscal_year: int
    period: int
    ufcf: float
    discount_factor: float
    present_value: float


class DCFOut(BaseModel):
    scenario: str
    discounted_years: list[DiscountedYearOut]
    terminal_year_ufcf: float
    terminal_value_undiscounted: float
    pv_terminal_value: float
    pv_explicit_period: float
    enterprise_value: float
    equity_value: float
    implied_value_per_share: float | None
    terminal_value_pct_of_ev: float
    wacc: float
    terminal_growth_rate: float


class ScenarioResultOut(BaseModel):
    scenario: str
    forecast: list[ForecastYearOut]
    dcf: DCFOut
    model_checks: ModelChecksReport


class ValuationRunOut(BaseModel):
    scenarios: dict[str, ScenarioResultOut]


class SensitivityGridOut(BaseModel):
    row_label: str
    column_label: str
    row_values: list[float]
    column_values: list[float]
    grid: list[list[float | None]]
    metric: str
