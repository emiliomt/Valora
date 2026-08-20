"""Net debt bridge (PRD 7.7 "Net debt bridge uses consistent debt and cash definitions")."""

from __future__ import annotations

from financial_engine.schemas import HistoricalFinancials, NetDebtBridge


def build_net_debt_bridge(latest_actual: HistoricalFinancials) -> NetDebtBridge:
    """Build the net debt bridge from the latest actual (point-in-time) balance sheet.

    All components must come from the same balance-sheet date to stay internally
    consistent (PRD 12 DCF validation rule).
    """
    return NetDebtBridge(
        cash=latest_actual.cash,
        debt=latest_actual.debt,
        lease_liabilities=latest_actual.lease_liabilities,
        preferred_claims=latest_actual.preferred_claims,
        other_non_operating_assets=latest_actual.other_non_operating_assets,
    )
