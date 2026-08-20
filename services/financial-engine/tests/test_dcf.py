import pytest

from financial_engine.dcf import compute_dcf
from financial_engine.schemas import DCFInputs


def test_dcf_hand_calculation_two_year():
    inputs = DCFInputs(
        ufcf_by_year={2025: 100.0, 2026: 110.0},
        wacc=0.10,
        terminal_growth_rate=0.03,
        valuation_date_fiscal_year=2024,
        cash=50.0,
        debt=200.0,
        diluted_shares_outstanding=100.0,
    )
    result = compute_dcf(inputs)

    pv1 = 100.0 / 1.10
    pv2 = 110.0 / (1.10**2)
    assert result.pv_explicit_period == pytest.approx(pv1 + pv2)

    terminal_year_ufcf = 110.0 * 1.03
    tv = terminal_year_ufcf / (0.10 - 0.03)
    pv_tv = tv / (1.10**2)
    assert result.terminal_value_undiscounted == pytest.approx(tv)
    assert result.pv_terminal_value == pytest.approx(pv_tv)

    expected_ev = pv1 + pv2 + pv_tv
    assert result.enterprise_value == pytest.approx(expected_ev)

    expected_equity = expected_ev + 50.0 - 200.0
    assert result.equity_value == pytest.approx(expected_equity)
    assert result.implied_value_per_share == pytest.approx(expected_equity / 100.0)


def test_dcf_deterministic_same_inputs_same_outputs():
    inputs = DCFInputs(
        ufcf_by_year={2025: 100.0, 2026: 110.0, 2027: 121.0},
        wacc=0.09,
        terminal_growth_rate=0.025,
        valuation_date_fiscal_year=2024,
        cash=10.0,
        debt=40.0,
    )
    r1 = compute_dcf(inputs)
    r2 = compute_dcf(inputs)
    assert r1 == r2


def test_dcf_rejects_wacc_leq_terminal_growth():
    with pytest.raises(ValueError):
        DCFInputs(
            ufcf_by_year={2025: 100.0},
            wacc=0.05,
            terminal_growth_rate=0.05,
            valuation_date_fiscal_year=2024,
            cash=0.0,
            debt=0.0,
        )


def test_dcf_rejects_empty_ufcf():
    with pytest.raises(ValueError):
        DCFInputs(
            ufcf_by_year={},
            wacc=0.10,
            terminal_growth_rate=0.03,
            valuation_date_fiscal_year=2024,
            cash=0.0,
            debt=0.0,
        )


def test_implied_value_per_share_none_without_share_count():
    inputs = DCFInputs(
        ufcf_by_year={2025: 100.0},
        wacc=0.10,
        terminal_growth_rate=0.03,
        valuation_date_fiscal_year=2024,
        cash=0.0,
        debt=0.0,
    )
    result = compute_dcf(inputs)
    assert result.implied_value_per_share is None


def test_terminal_value_pct_of_ev_between_zero_and_one_for_typical_inputs():
    inputs = DCFInputs(
        ufcf_by_year={y: 100.0 * (1.08 ** (y - 2024)) for y in range(2025, 2030)},
        wacc=0.11,
        terminal_growth_rate=0.03,
        valuation_date_fiscal_year=2024,
        cash=0.0,
        debt=0.0,
    )
    result = compute_dcf(inputs)
    assert 0.0 < result.terminal_value_pct_of_ev < 1.0


def test_full_net_debt_bridge_components_flow_into_equity_value():
    inputs = DCFInputs(
        ufcf_by_year={2025: 100.0},
        wacc=0.10,
        terminal_growth_rate=0.03,
        valuation_date_fiscal_year=2024,
        cash=100.0,
        debt=50.0,
        lease_liabilities=20.0,
        preferred_claims=10.0,
        other_non_operating_assets=5.0,
    )
    result = compute_dcf(inputs)
    expected_equity = result.enterprise_value + 100.0 - 50.0 - 20.0 - 10.0 + 5.0
    assert result.equity_value == pytest.approx(expected_equity)
