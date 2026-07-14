"""Focused integration tests for insurer hedge and backing cashflows."""

from dataclasses import replace

import numpy as np
import pytest

from policy_engine import (
    AgileProduct,
    BehaviourModel,
    ESGConfig,
    FeeSpec,
    HedgeCapLegMode,
    IncomeRateTable,
    Index,
    Measure,
    MortalityTable,
    PolicySpec,
    ProjectionConfig,
    ReferenceFundSpec,
    ScenarioSet,
    YieldCurve,
)
from policy_engine.behavior import DynamicLapseParams, LapseAssumptions
from policy_engine.projection import project


def _deterministic_scenarios(
    *,
    equity_annual_growth: float,
    horizon_years: int = 8,
    overnight_rate: float = 0.04,
) -> ScenarioSet:
    """Deterministic market with independently controlled equity and O/N rate."""
    n_steps = horizon_years * 12
    times = np.arange(n_steps + 1, dtype=float) / 12.0
    base = equity_annual_growth ** times
    levels = np.broadcast_to(base, (2, n_steps + 1)).copy()
    discount = np.broadcast_to(
        np.exp(-overnight_rate * times), levels.shape
    ).copy()
    return ScenarioSet(
        config=ESGConfig(curve=YieldCurve.flat(overnight_rate)),
        measure=Measure.RISK_NEUTRAL,
        dt=1.0 / 12.0,
        times=times,
        index_levels={
            Index.AUS_EQUITY: levels.copy(),
            Index.GLOBAL_EQUITY: levels.copy(),
        },
        short_rate=np.full_like(levels, overnight_rate),
        discount=discount,
        model_name="black_scholes",
        seed=41,
    )


def _no_lapse_behaviour() -> BehaviourModel:
    return BehaviourModel(
        regime="static",
        lapse=LapseAssumptions(growth_phase=(0.0,), income_phase=0.0),
        dynamic=DynamicLapseParams(enabled=False),
    )


def _projection(
    mode: HedgeCapLegMode,
    *,
    scenarios: ScenarioSet | None = None,
    dva_enabled: bool = False,
):
    product = AgileProduct(
        reference_fund=ReferenceFundSpec(scenario_maximum_return=0.03),
        fees=FeeSpec(product_fee=0.0, lifetime_income_premium=0.0),
        # Force Account-Value exhaustion within the compact deterministic test
        # horizon, so the claims-invariance assertion is non-vacuous.
        income_rates=replace(IncomeRateTable(), base_rate_shift=0.20),
    )
    return project(
        product,
        PolicySpec(age=65, income_start_year=1),
        scenarios or _deterministic_scenarios(equity_annual_growth=1.60),
        _no_lapse_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(
            dva_enabled=dva_enabled,
            hedge_vol_spread=0.0,
            option_fair_value_markup=0.005,
            hedge_reference_management_fee=0.003,
            hedge_cap_leg_mode=mode,
            record_paths=True,
        ),
    )


def test_hedge_ledgers_reconcile_to_backward_compatible_aggregates():
    result = _projection(HedgeCapLegMode.NOT_SOLD)
    cashflows = result.cashflows

    np.testing.assert_allclose(
        cashflows["crediting_margin"],
        cashflows["money_market_income"] + cashflows["hedge_gain"],
        rtol=0.0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        cashflows["hedge_option_markup_costs"][:, 0],
        0.005 * cashflows["hedge_option_fair_value_costs"][:, 0],
        rtol=0.0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        cashflows["hedge_management_fee_costs"][:, 0],
        np.full(
            cashflows["hedge_management_fee_costs"].shape[0],
            0.003 * PolicySpec(age=65, income_start_year=1).initial_investment,
        ),
        rtol=0.0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        cashflows["hedge_execution_costs"], 0.0, rtol=0.0, atol=0.0
    )
    np.testing.assert_allclose(
        cashflows["hedge_costs"],
        cashflows["hedge_option_fair_value_costs"]
        + cashflows["hedge_option_markup_costs"]
        + cashflows["hedge_management_fee_costs"]
        + cashflows["hedge_execution_costs"],
        rtol=0.0,
        atol=1e-12,
    )

    pv = result.pv_by_component()
    assert pv["crediting_margin"] == pytest.approx(
        pv["money_market_income"] + pv["hedge_gain"], abs=1e-9
    )
    assert pv["hedge_costs"] == pytest.approx(
        pv["hedge_option_fair_value_costs"]
        + pv["hedge_option_markup_costs"]
        + pv["hedge_management_fee_costs"]
        + pv["hedge_execution_costs"],
        abs=1e-9,
    )

    # This ledger closes the customer-contract identity but is deliberately
    # outside shareholder P&L and therefore cannot alter insurer net value.
    insurer_net = result.pv_insurer_net()
    cashflows["contract_financing_margin"] = (
        cashflows["contract_financing_margin"] + 1_000_000.0
    )
    assert result.pv_insurer_net() == pytest.approx(insurer_net, abs=1e-9)


def test_unsold_cap_leg_adds_cost_and_gain_without_changing_liabilities():
    sold = _projection(HedgeCapLegMode.SOLD)
    not_sold = _projection(HedgeCapLegMode.NOT_SOLD)

    assert np.sum(sold.cashflows["hedge_gain"]) == pytest.approx(0.0)
    assert np.sum(not_sold.cashflows["hedge_gain"]) > 0.0
    assert np.sum(not_sold.cashflows["hedge_option_fair_value_costs"]) \
        > np.sum(sold.cashflows["hedge_option_fair_value_costs"])

    assert sold.iv_paths is not None and not_sold.iv_paths is not None
    np.testing.assert_array_equal(not_sold.iv_paths, sold.iv_paths)
    np.testing.assert_array_equal(not_sold.income_paths, sold.income_paths)
    np.testing.assert_array_equal(not_sold.phase_paths, sold.phase_paths)

    customer_cashflows = (
        "income_paid",
        "guarantee_claims",
        "death_benefits",
        "surrender_benefits",
        "partial_withdrawals",
        "terminal_closeout",
    )
    for key in customer_cashflows:
        np.testing.assert_array_equal(
            not_sold.cashflows[key], sold.cashflows[key], err_msg=key
        )
    assert np.sum(sold.cashflows["guarantee_claims"]) > 0.0


def test_money_market_income_uses_discount_accumulation_not_fund_performance():
    strong = _deterministic_scenarios(equity_annual_growth=1.60)
    weak = _deterministic_scenarios(equity_annual_growth=0.60)
    result = _projection(HedgeCapLegMode.SOLD, scenarios=strong)
    weak_result = _projection(HedgeCapLegMode.SOLD, scenarios=weak)

    assert result.iv_paths is not None
    expected_first_year = (
        result.inforce[:, :12]
        * result.iv_paths[:, :12]
        * (strong.discount[:, :12] / strong.discount[:, 1:13] - 1.0)
    )
    np.testing.assert_allclose(
        result.cashflows["money_market_income"][:, 1:13],
        expected_first_year,
        rtol=0.0,
        atol=1e-10,
    )
    # Before the first annual customer credit, radically different Reference-
    # Fund performance cannot alter the income earned on the same MM backing.
    np.testing.assert_allclose(
        result.cashflows["money_market_income"][:, 1:13],
        weak_result.cashflows["money_market_income"][:, 1:13],
        rtol=0.0,
        atol=1e-10,
    )


def test_money_market_income_uses_administrative_frame_not_dva_value():
    scenarios = _deterministic_scenarios(equity_annual_growth=1.60)
    result = _projection(
        HedgeCapLegMode.SOLD, scenarios=scenarios, dva_enabled=True)

    assert result.iv_paths is not None
    overnight_return = (
        scenarios.discount[:, :12] / scenarios.discount[:, 1:13] - 1.0
    )
    expected_first_year = (
        result.inforce[:, :12]
        * PolicySpec(age=65, income_start_year=1).initial_investment
        * overnight_return
    )
    np.testing.assert_allclose(
        result.cashflows["money_market_income"][:, 1:13],
        expected_first_year,
        rtol=0.0,
        atol=1e-10,
    )

    dva_value_income = (
        result.inforce[:, :12]
        * result.iv_paths[:, :12]
        * overnight_return
    )
    assert np.max(
        np.abs(expected_first_year - dva_value_income)
    ) > 1e-6


@pytest.mark.parametrize(
    "kwargs",
    [
        {"option_fair_value_markup": -1e-12},
        {"option_fair_value_markup": np.inf},
        {"hedge_reference_management_fee": -1e-12},
        {"hedge_reference_management_fee": 1.0},
        {"hedge_cap_leg_mode": "unknown"},
    ],
)
def test_hedge_projection_config_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        ProjectionConfig(**kwargs)


def test_hedge_projection_config_normalises_valid_string_mode():
    config = ProjectionConfig(hedge_cap_leg_mode="not_sold")
    assert config.hedge_cap_leg_mode is HedgeCapLegMode.NOT_SOLD
