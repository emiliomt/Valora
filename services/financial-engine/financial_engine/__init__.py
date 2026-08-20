"""Deterministic financial calculation engine.

This package contains ONLY pure, side-effect-free Python functions and
dataclasses. It has no dependency on the database, the web framework, or any
LLM. Per PRD section 21: "Keep calculation logic in pure Python functions
with extensive unit tests; do not put financial logic in React components or
LLM prompts."

Given the same inputs, every function here returns the same outputs
(PRD 7.7 acceptance criteria).
"""

from financial_engine.schemas import (
    Assumptions,
    DCFInputs,
    DCFResult,
    ForecastYear,
    HistoricalFinancials,
    ModelCheckResult,
    NetDebtBridge,
    ScenarioAssumptions,
)

__all__ = [
    "Assumptions",
    "DCFInputs",
    "DCFResult",
    "ForecastYear",
    "HistoricalFinancials",
    "ModelCheckResult",
    "NetDebtBridge",
    "ScenarioAssumptions",
]
