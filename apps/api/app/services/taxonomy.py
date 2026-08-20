"""Standardized financial taxonomy and rule-based mapping (PRD 7.4).

`STANDARD_TAXONOMY` enumerates the normalized line-item keys the platform
understands, grouped by statement. `suggest_mapping` proposes a normalized
key for a reported (as-filed) label using keyword rules. This is intentionally
NOT an AI call: it's the deterministic first pass every reported label goes
through; only unmatched/ambiguous labels are left for the analyst (or, later,
an AI-assisted suggestion — PRD 7.4: "Suggest mapping using rules plus
AI-assisted classification") to resolve manually. Nothing here fabricates a
value; it only proposes a classification for a value the user already
supplied, and the mapping always starts as "proposed" pending user approval.
"""

from __future__ import annotations

STATEMENT_INCOME = "income_statement"
STATEMENT_BALANCE = "balance_sheet"
STATEMENT_CASH_FLOW = "cash_flow"

STANDARD_TAXONOMY: dict[str, list[str]] = {
    STATEMENT_INCOME: [
        "revenue",
        "cost_of_revenue",
        "gross_profit",
        "sales_and_marketing",
        "research_and_development",
        "general_and_administrative",
        "other_operating_expenses",
        "ebitda",
        "depreciation_and_amortization",
        "ebit",
        "net_interest_expense",
        "other_non_operating_items",
        "income_taxes",
        "net_income",
    ],
    STATEMENT_BALANCE: [
        "cash_and_equivalents",
        "accounts_receivable",
        "inventory",
        "other_current_assets",
        "ppe",
        "intangible_assets",
        "other_assets",
        "accounts_payable",
        "accrued_expenses",
        "deferred_revenue",
        "other_current_liabilities",
        "debt",
        "lease_liabilities",
        "other_liabilities",
        "equity",
    ],
    STATEMENT_CASH_FLOW: [
        "net_income",
        "d_and_a",
        "stock_based_compensation",
        "change_in_net_working_capital",
        "cash_flow_from_operations",
        "capex",
        "acquisitions_divestitures",
        "financing_cash_flows",
        "free_cash_flow",
    ],
}

# Ordered (most-specific-first) keyword rules. Each rule is (normalized_key,
# statement_type, [keyword substrings matched case-insensitively]).
_RULES: list[tuple[str, str, list[str]]] = [
    ("revenue", STATEMENT_INCOME, ["total revenue", "net revenue", "net sales", "total net sales", "revenue"]),
    ("cost_of_revenue", STATEMENT_INCOME, ["cost of revenue", "cost of goods sold", "cogs", "cost of sales"]),
    ("gross_profit", STATEMENT_INCOME, ["gross profit", "gross margin"]),
    ("sales_and_marketing", STATEMENT_INCOME, ["sales and marketing", "selling and marketing", "marketing expense"]),
    ("research_and_development", STATEMENT_INCOME, ["research and development", "r&d"]),
    ("general_and_administrative", STATEMENT_INCOME, ["general and administrative", "g&a", "sg&a"]),
    ("ebitda", STATEMENT_INCOME, ["ebitda"]),
    ("depreciation_and_amortization", STATEMENT_INCOME, ["depreciation and amortization", "depreciation & amortization", "d&a"]),
    ("ebit", STATEMENT_INCOME, ["ebit", "operating income"]),
    ("net_interest_expense", STATEMENT_INCOME, ["interest expense", "net interest"]),
    ("income_taxes", STATEMENT_INCOME, ["income tax", "provision for income taxes", "taxes"]),
    ("net_income", STATEMENT_INCOME, ["net income", "net earnings", "net loss"]),
    ("cash_and_equivalents", STATEMENT_BALANCE, ["cash and cash equivalents", "cash and equivalents", "cash"]),
    ("accounts_receivable", STATEMENT_BALANCE, ["accounts receivable", "receivables", "trade receivables"]),
    ("inventory", STATEMENT_BALANCE, ["inventory", "inventories"]),
    ("ppe", STATEMENT_BALANCE, ["property, plant", "property and equipment", "ppe", "fixed assets"]),
    ("intangible_assets", STATEMENT_BALANCE, ["intangible assets", "goodwill"]),
    ("accounts_payable", STATEMENT_BALANCE, ["accounts payable", "trade payables"]),
    ("accrued_expenses", STATEMENT_BALANCE, ["accrued expenses", "accrued liabilities"]),
    ("deferred_revenue", STATEMENT_BALANCE, ["deferred revenue", "unearned revenue"]),
    ("debt", STATEMENT_BALANCE, ["long-term debt", "short-term debt", "notes payable", "borrowings", "debt"]),
    ("lease_liabilities", STATEMENT_BALANCE, ["lease liabilit", "lease obligation"]),
    ("equity", STATEMENT_BALANCE, ["stockholders' equity", "shareholders' equity", "total equity"]),
    ("d_and_a", STATEMENT_CASH_FLOW, ["depreciation and amortization", "depreciation & amortization", "d&a"]),
    ("stock_based_compensation", STATEMENT_CASH_FLOW, ["stock-based compensation", "share-based compensation", "sbc"]),
    ("cash_flow_from_operations", STATEMENT_CASH_FLOW, ["cash flow from operations", "cash from operating activities", "operating activities"]),
    ("capex", STATEMENT_CASH_FLOW, ["capital expenditures", "purchases of property", "capex"]),
    ("free_cash_flow", STATEMENT_CASH_FLOW, ["free cash flow"]),
]


def suggest_mapping(reported_label: str, statement_hint: str | None = None) -> tuple[str | None, float]:
    """Return (normalized_key, confidence_score) for a reported label.

    confidence_score is a heuristic in [0, 1]: 0.9 for an exact/near-exact
    match, 0.6 for a substring keyword match, 0.0 (key=None) when unresolved.
    Statement_hint, if provided, is used to disambiguate keys that collide
    across statements (e.g. "net_income" appears on both IS and CF).
    """
    label_lower = reported_label.strip().lower()
    best: tuple[str, float] | None = None
    for key, statement_type, keywords in _RULES:
        if statement_hint and statement_type != statement_hint:
            continue
        for kw in keywords:
            if label_lower == kw:
                return key, 0.95
            if kw in label_lower:
                score = 0.6 + 0.1 * (len(kw) / max(len(label_lower), 1))
                if best is None or score > best[1]:
                    best = (key, min(score, 0.9))
    if best:
        return best
    return None, 0.0
