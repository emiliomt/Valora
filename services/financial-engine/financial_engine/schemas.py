"""Pure-Python data structures used by the deterministic engine.

These are deliberately independent of Pydantic/SQLAlchemy so this package has
zero framework dependencies (PRD 8.1 financial-engine is plain Pandas/NumPy-
style Python). The API layer maps its own Pydantic/ORM models to/from these
dataclasses at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AssumptionOrigin(str, Enum):
    USER = "user"
    MANAGEMENT_GUIDANCE = "management_guidance"
    THIRD_PARTY = "third_party"
    AI_SUGGESTED = "ai_suggested"
    CALCULATED = "calculated"


@dataclass(frozen=True)
class HistoricalFinancials:
    """One historical fiscal year of normalized financials.

    All values are in the deal's reporting currency and unit scale. Revenue,
    cogs, opex, capex, and taxes are expressed as positive numbers; the
    engine applies sign conventions internally.
    """

    fiscal_year: int
    revenue: float
    cogs: float
    operating_expenses: float
    d_and_a: float
    capex: float
    net_working_capital: float
    tax_rate: float
    cash: float = 0.0
    debt: float = 0.0
    lease_liabilities: float = 0.0
    preferred_claims: float = 0.0
    other_non_operating_assets: float = 0.0
    diluted_shares_outstanding: float | None = None


@dataclass(frozen=True)
class ForecastYear:
    """Assumptions driving a single forecast fiscal year.

    `revenue_growth_rate` is applied to the prior year's revenue (historical
    final year, or the prior forecast year).
    """

    fiscal_year: int
    revenue_growth_rate: float
    gross_margin: float
    opex_pct_of_revenue: float
    d_and_a_pct_of_revenue: float
    capex_pct_of_revenue: float
    nwc_pct_of_revenue: float
    tax_rate: float


@dataclass(frozen=True)
class ScenarioAssumptions:
    """A full scenario: base/bull/bear, one ForecastYear per forecast year."""

    scenario: str  # "base" | "bull" | "bear" | custom name
    years: list[ForecastYear]

    def __post_init__(self) -> None:
        if not self.years:
            raise ValueError("ScenarioAssumptions requires at least one forecast year")
        fys = [y.fiscal_year for y in self.years]
        if len(fys) != len(set(fys)):
            raise ValueError("Duplicate fiscal_year in ScenarioAssumptions.years")


@dataclass(frozen=True)
class Assumptions:
    """DCF-level assumptions independent of the operating driver forecast."""

    wacc: float
    terminal_growth_rate: float
    valuation_date_fiscal_year: int
    diluted_shares_outstanding: float | None = None

    def __post_init__(self) -> None:
        if self.wacc <= self.terminal_growth_rate:
            raise ValueError(
                "WACC must be greater than terminal growth rate "
                f"(wacc={self.wacc}, terminal_growth_rate={self.terminal_growth_rate})"
            )


@dataclass(frozen=True)
class IncomeStatementLine:
    fiscal_year: int
    revenue: float
    cogs: float
    gross_profit: float
    operating_expenses: float
    ebitda: float
    d_and_a: float
    ebit: float
    taxes: float
    nopat: float  # EBIT * (1 - tax rate)


@dataclass(frozen=True)
class CashFlowLine:
    fiscal_year: int
    nopat: float
    d_and_a: float
    capex: float
    change_in_nwc: float
    ufcf: float


@dataclass(frozen=True)
class ForecastResult:
    scenario: str
    income_statement: list[IncomeStatementLine]
    cash_flow: list[CashFlowLine]

    def ufcf_by_year(self) -> dict[int, float]:
        return {line.fiscal_year: line.ufcf for line in self.cash_flow}


@dataclass(frozen=True)
class DCFInputs:
    ufcf_by_year: dict[int, float]  # fiscal_year -> UFCF, explicit forecast period only
    wacc: float
    terminal_growth_rate: float
    valuation_date_fiscal_year: int  # year 0; first forecast year discounts as year 1
    cash: float
    debt: float
    lease_liabilities: float = 0.0
    preferred_claims: float = 0.0
    other_non_operating_assets: float = 0.0
    diluted_shares_outstanding: float | None = None

    def __post_init__(self) -> None:
        if self.wacc <= self.terminal_growth_rate:
            raise ValueError("WACC must be greater than terminal growth rate")
        if not self.ufcf_by_year:
            raise ValueError("DCFInputs requires at least one forecast-year UFCF")


@dataclass(frozen=True)
class DiscountedYear:
    fiscal_year: int
    period: int  # discount period, 1-indexed from valuation date
    ufcf: float
    discount_factor: float
    present_value: float


@dataclass(frozen=True)
class DCFResult:
    scenario: str
    discounted_years: list[DiscountedYear]
    terminal_year_ufcf: float
    terminal_value_undiscounted: float
    terminal_value_discount_factor: float
    pv_terminal_value: float
    pv_explicit_period: float
    enterprise_value: float
    equity_value: float
    implied_value_per_share: float | None
    terminal_value_pct_of_ev: float
    wacc: float
    terminal_growth_rate: float


@dataclass(frozen=True)
class NetDebtBridge:
    cash: float
    debt: float
    lease_liabilities: float
    preferred_claims: float
    other_non_operating_assets: float

    @property
    def net_debt(self) -> float:
        return self.debt + self.lease_liabilities + self.preferred_claims - self.cash - self.other_non_operating_assets


@dataclass(frozen=True)
class ModelCheckResult:
    check_id: str
    passed: bool
    message: str
    severity: str = "error"  # "error" | "warning"


@dataclass(frozen=True)
class ModelCheckReport:
    checks: list[ModelCheckResult] = field(default_factory=list)

    @property
    def has_blocking_failures(self) -> bool:
        return any(not c.passed and c.severity == "error" for c in self.checks)

    @property
    def warnings(self) -> list[ModelCheckResult]:
        return [c for c in self.checks if not c.passed and c.severity == "warning"]

    @property
    def failures(self) -> list[ModelCheckResult]:
        return [c for c in self.checks if not c.passed]
