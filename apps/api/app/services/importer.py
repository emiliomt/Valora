"""CSV/XLSX historical-financials import (PRD 7.3/7.4).

Expected input format (a simple, documented tabular schema — not an attempt
to parse arbitrary filing layouts; that's the PDF/DOCX extraction pipeline,
which is out of scope for this vertical slice per docs/prd.md
"Implementation status"):

    fiscal_year | statement_type      | label              | value | currency | unit_scale
    2024        | income_statement    | Total revenue      | 1000000 | USD    | actuals
    2024        | income_statement    | Cost of revenue    | 400000  | USD    | actuals
    ...

`statement_type` must be one of income_statement | balance_sheet | cash_flow.
currency/unit_scale are optional and default to the deal's settings.
"""

from __future__ import annotations

import io

import pandas as pd

REQUIRED_COLUMNS = {"fiscal_year", "statement_type", "label", "value"}
VALID_STATEMENT_TYPES = {"income_statement", "balance_sheet", "cash_flow"}


class ImportValidationError(ValueError):
    pass


def parse_financials_file(filename: str, content: bytes) -> pd.DataFrame:
    """Parse a CSV or XLSX file into a normalized DataFrame with the required
    columns, or raise ImportValidationError with a clear message.

    PRD 7.3 acceptance criteria: "Unsupported files return a clear error and
    do not corrupt the deal."
    """
    lower = filename.lower()
    try:
        if lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif lower.endswith(".xlsx") or lower.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise ImportValidationError(
                f"Unsupported file type for '{filename}'. Only .csv and .xlsx are supported for structured "
                "financial import."
            )
    except ImportValidationError:
        raise
    except Exception as exc:  # pragma: no cover - defensive, exact exception varies by bad input
        raise ImportValidationError(f"Could not parse '{filename}': {exc}") from exc

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ImportValidationError(
            f"Missing required column(s) {sorted(missing)}. Required columns: {sorted(REQUIRED_COLUMNS)}."
        )

    if "currency" not in df.columns:
        df["currency"] = None
    if "unit_scale" not in df.columns:
        df["unit_scale"] = None

    df = df.dropna(subset=["fiscal_year", "statement_type", "label", "value"])
    if df.empty:
        raise ImportValidationError("No usable rows found after dropping rows missing required fields.")

    bad_statements = set(df["statement_type"].astype(str).str.strip().str.lower()) - VALID_STATEMENT_TYPES
    if bad_statements:
        raise ImportValidationError(
            f"Invalid statement_type value(s) {sorted(bad_statements)}. Must be one of {sorted(VALID_STATEMENT_TYPES)}."
        )

    df["fiscal_year"] = df["fiscal_year"].astype(int)
    df["statement_type"] = df["statement_type"].astype(str).str.strip().str.lower()
    df["label"] = df["label"].astype(str).str.strip()
    df["value"] = df["value"].astype(float)

    return df
