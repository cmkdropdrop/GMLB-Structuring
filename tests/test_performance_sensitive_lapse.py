"""Integration tests for credited-performance-sensitive Income lapses."""

from dataclasses import replace

import numpy as np

from policy_engine import (
    ESGConfig,
    Index,
    IndexLinkedLifetimeIncomeProduct,
    Measure,
    MortalityTable,
    PolicySpec,
    ProjectionConfig,
    ReferenceFundSpec,
    ScenarioSet,
    YieldCurve,
    load_dynamic_behaviour_assumptions,
)
from policy_engine.projection import project


def _good_market_scenarios(*, horizon_years: int = 3) -> ScenarioSet:
    """Deterministic good market where the 30/70 fund return is below 20%."""
    n_steps = horizon_years * 12
    times = np.arange(n_steps + 1, dtype=float) / 12.0
    curve = YieldCurve.flat(0.04)
    config = ESGConfig(curve=curve)
    monthly_equity_growth = 1.30 ** (1.0 / 12.0)
    equity = monthly_equity_growth ** np.arange(n_steps + 1, dtype=float)
    levels = np.broadcast_to(equity, (3, n_steps + 1)).copy()
    discount = np.broadcast_to(
        np.asarray(curve.df(times), dtype=float), (3, n_steps + 1)
    ).copy()
    short_rate = np.full_like(discount, 0.04)
    return ScenarioSet(
        config=config,
        measure=Measure.RISK_NEUTRAL,
        dt=1.0 / 12.0,
        times=times,
        index_levels={
            Index.AUS_EQUITY: levels.copy(),
            Index.GLOBAL_EQUITY: levels.copy(),
        },
        short_rate=short_rate,
        discount=discount,
        model_name="black_scholes",
        seed=17,
    )


def _production_behaviour():
    loaded = load_dynamic_behaviour_assumptions().behaviour
    return replace(loaded, take_up=replace(loaded.take_up, mode="deterministic"))


def _project_with_cap(
    cap: float,
    *,
    hedge_gain: bool = False,
    horizon_years: int = 3,
):
    product = IndexLinkedLifetimeIncomeProduct(
        reference_fund=ReferenceFundSpec(scenario_maximum_return=cap)
    )
    return project(
        product,
        PolicySpec(age=65.0, income_start_year=1.0),
        _good_market_scenarios(horizon_years=horizon_years),
        _production_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(
            dva_enabled=False,
            crediting_margin_enabled=hedge_gain,
            record_paths=True,
        ),
    )


def test_low_cap_after_good_return_increases_income_lapse_but_not_growth_lapse():
    low = _project_with_cap(0.0025)
    high = _project_with_cap(0.20)

    first_anniversary = 12
    # Growth surrender is prohibited and a newly elected Income contract
    # cannot surrender on the same anniversary timestamp.
    np.testing.assert_array_equal(
        low.lapse_events[:, :first_anniversary + 1], 0.0
    )
    np.testing.assert_array_equal(
        high.lapse_events[:, :first_anniversary + 1], 0.0
    )
    assert np.sum(low.lapse_events[:, first_anniversary + 1:]) > np.sum(
        high.lapse_events[:, first_anniversary + 1:]
    )
    assert low.ordinary_lapse_events is not None
    assert low.performance_lapse_events is not None
    np.testing.assert_allclose(
        low.lapse_events,
        low.ordinary_lapse_events + low.performance_lapse_events,
        rtol=0.0,
        atol=1.0e-14,
    )
    assert np.sum(low.performance_lapse_events) > 0.0


def test_growth_product_gate_overrides_shared_performance_hazard_for_all_years():
    behaviour = load_dynamic_behaviour_assumptions().behaviour
    behaviour = replace(
        behaviour,
        take_up=replace(
            behaviour.take_up,
            mode="hazard",
            hazard=(0.0,),
            force_by_year=None,
        ),
    )
    # The generic statistical function is deliberately reusable and can
    # produce a performance cause at a zero ordinary baseline.  The product's
    # stronger contractual Growth prohibition must still win in projection.
    assert behaviour.dynamic.growth_probability(
        0.0,
        0.0,
        100_000.0,
        1.0,
        performance_shortfall=0.10,
    ) > 0.0

    result = project(
        IndexLinkedLifetimeIncomeProduct(
            reference_fund=ReferenceFundSpec(scenario_maximum_return=0.0025)
        ),
        PolicySpec(age=65.0, income_start_year=1.0),
        _good_market_scenarios(horizon_years=3),
        behaviour,
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(dva_enabled=False, record_paths=True),
    )
    np.testing.assert_array_equal(result.lapse_events, 0.0)
    assert result.phase_paths is not None
    np.testing.assert_array_equal(result.phase_paths[:, :-1], 0)
    np.testing.assert_array_equal(result.phase_paths[:, -1], 2)


def test_hedge_gain_toggle_does_not_change_lapses_or_inforce():
    without_hedge_gain = _project_with_cap(0.0025, hedge_gain=False)
    with_hedge_gain = _project_with_cap(0.0025, hedge_gain=True)

    np.testing.assert_array_equal(
        with_hedge_gain.lapse_events, without_hedge_gain.lapse_events
    )
    np.testing.assert_array_equal(
        with_hedge_gain.inforce, without_hedge_gain.inforce
    )


def test_zero_surrender_value_cannot_forfeit_positive_income_guarantee():
    result = _project_with_cap(0.0025, horizon_years=20)
    assert result.iv_paths is not None
    assert result.phase_paths is not None
    exhausted_income = (
        (result.phase_paths == 1) & (result.iv_paths <= 1.0e-7)
    )
    assert np.any(exhausted_income)
    np.testing.assert_array_equal(result.lapse_events[exhausted_income], 0.0)
