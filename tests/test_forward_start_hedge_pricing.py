"""Targeted tests for cached annual forward-start call-spread prices."""

from dataclasses import replace

import numpy as np
import pytest

from policy_engine import (
    BehaviourModel,
    IndexLinkedLifetimeIncomeProduct,
    MortalityTable,
    PolicySpec,
    ProjectionConfig,
    ReferenceFundSpec,
    ScenarioSet,
)
from policy_engine.forward_start_hedge_pricing import (
    HEDGE_FEATURE_NAMES,
    HedgePriceCacheNotFoundError,
    HedgePriceCacheSpec,
    annual_call_spread_payoffs,
    build_annual_pricing_features,
    build_hedge_price_surface,
    cross_fitted_conditional_prices,
    direct_discounted_mc_pv,
    load_hedge_price_surface,
    save_hedge_price_surface,
)
from policy_engine.product import Index
from policy_engine.projection import project
from test_scenario_cache import synthetic_scenarios


def hedge_spec(
    scenarios: ScenarioSet,
    *,
    equity_allocation: float = 0.30,
    cap_grid=(0.0, 0.06, 0.10),
) -> HedgePriceCacheSpec:
    return HedgePriceCacheSpec(
        market_cache_key="1" * 64,
        scenario_fingerprint=scenarios.content_fingerprint,
        n_paths=scenarios.n_paths,
        horizon_years=float(scenarios.times[-1]),
        equity_index=Index.GLOBAL_EQUITY,
        equity_allocation=equity_allocation,
        allocation_input_sha256="2" * 64,
        cap_grid=cap_grid,
        training_scenario_fingerprint=scenarios.content_fingerprint,
        cross_fit_folds=3,
        cross_fit_seed=11,
        ridge=1.0e-6,
    )


def _path_slice(scenarios: ScenarioSet, start: int, stop: int) -> ScenarioSet:
    variance = {
        index: values[start:stop] for index, values in scenarios.variance.items()
    }
    return ScenarioSet.from_storage(
        config=scenarios.config,
        measure=scenarios.measure,
        dt=scenarios.dt,
        times=scenarios.times,
        index_levels={
            index: values[start:stop]
            for index, values in scenarios.index_levels.items()
        },
        short_rate=scenarios.short_rate[start:stop],
        discount=scenarios.discount[start:stop],
        variance=variance,
        stochastic_rates=scenarios.stochastic_rates,
        model_name=scenarios.model_name,
        seed=scenarios.seed,
        substeps=scenarios.substeps,
    )


def _repeat_paths(scenarios: ScenarioSet, repeats: int) -> ScenarioSet:
    repeated = lambda value: np.concatenate([np.asarray(value)] * repeats, axis=0)
    return ScenarioSet.from_storage(
        config=scenarios.config,
        measure=scenarios.measure,
        dt=scenarios.dt,
        times=scenarios.times,
        index_levels={
            index: repeated(values)
            for index, values in scenarios.index_levels.items()
        },
        short_rate=repeated(scenarios.short_rate),
        discount=repeated(scenarios.discount),
        variance={
            index: repeated(values) for index, values in scenarios.variance.items()
        },
        stochastic_rates=scenarios.stochastic_rates,
        model_name=scenarios.model_name,
        seed=scenarios.seed,
        substeps=scenarios.substeps,
    )


def _time_prefix(scenarios: ScenarioSet, stop_step: int) -> ScenarioSet:
    stop = stop_step + 1
    return ScenarioSet.from_storage(
        config=scenarios.config,
        measure=scenarios.measure,
        dt=scenarios.dt,
        times=scenarios.times[:stop],
        index_levels={
            index: values[:, :stop]
            for index, values in scenarios.index_levels.items()
        },
        short_rate=scenarios.short_rate[:, :stop],
        discount=scenarios.discount[:, :stop],
        variance={
            index: values[:, :stop]
            for index, values in scenarios.variance.items()
        },
        stochastic_rates=scenarios.stochastic_rates,
        model_name=scenarios.model_name,
        seed=scenarios.seed,
        substeps=scenarios.substeps,
    )


def test_call_spread_payoff_is_call_one_minus_call_one_plus_cap():
    returns = np.asarray([[-0.20, 0.03, 0.20]])
    caps = np.asarray([0.0, 0.05, 0.10])
    payoff = annual_call_spread_payoffs(returns, caps)
    expected = np.minimum(np.maximum(returns[:, :, None], 0.0), caps)
    np.testing.assert_allclose(payoff, expected)
    np.testing.assert_allclose(payoff[:, :, 0], 0.0)


def test_direct_mc_pv_and_conditional_tower_reconcile_for_constant_payoff():
    n_paths, n_years = 30, 2
    features = np.zeros((n_paths, n_years, len(HEDGE_FEATURE_NAMES)))
    features[:, :, 1] = 0.02
    features[:, :, 4] = np.arange(1, n_years + 1)
    caps = np.asarray([0.0, 0.06])
    discount_ratio = np.full((n_paths, n_years), 0.98)
    payoff = np.zeros((n_paths, n_years, 2))
    payoff[:, :, 1] = 0.04
    target = discount_ratio[:, :, None] * payoff
    start_discount = np.asarray([[1.0, 0.98]] * n_paths)
    prices, _ = cross_fitted_conditional_prices(
        features=features,
        discounted_payoff_target=target,
        start_date_discount=start_discount,
        cap_grid=caps,
        one_year_zero_bond_price=discount_ratio,
        folds=3,
        fold_seed=7,
    )
    notional = np.ones((n_paths, n_years))
    direct = direct_discounted_mc_pv(
        start_discount * discount_ratio, notional, payoff
    )
    tower = direct_discounted_mc_pv(start_discount, notional, prices)
    np.testing.assert_allclose(tower, direct, rtol=0.0, atol=1.0e-12)


def test_prices_are_nonnegative_monotone_bounded_and_zero_at_cap_zero():
    scenarios = synthetic_scenarios(n_paths=18)
    surface = build_hedge_price_surface(scenarios, hedge_spec(scenarios))
    prices = surface.annual_fair_price_per_unit
    assert np.all(prices >= 0.0)
    assert np.all(prices[:, :, 0] == 0.0)
    assert np.all(np.diff(prices, axis=2) >= -1.0e-12)
    upper = np.column_stack([
        scenarios.zero_bond_price(int(step), 1.0)
        for step in surface.annual_start_steps
    ])[:, :, None] * surface.cap_grid[None, None, :]
    assert np.all(prices <= upper + 1.0e-12)


def test_features_use_only_anniversary_observable_market_state():
    scenarios = synthetic_scenarios(n_paths=12)
    starts = np.asarray([0, 12], dtype=np.int64)
    before = build_annual_pricing_features(scenarios, starts)
    changed_levels = {
        index: np.array(values, copy=True)
        for index, values in scenarios.index_levels.items()
    }
    changed_levels[Index.GLOBAL_EQUITY][:, 1:12] *= 4.0
    changed = ScenarioSet(
        config=scenarios.config,
        measure=scenarios.measure,
        dt=scenarios.dt,
        times=scenarios.times,
        index_levels=changed_levels,
        short_rate=scenarios.short_rate,
        discount=scenarios.discount,
        variance=scenarios.variance,
        stochastic_rates=scenarios.stochastic_rates,
        model_name=scenarios.model_name,
        seed=scenarios.seed,
        substeps=scenarios.substeps,
    )
    after = build_annual_pricing_features(changed, starts)
    np.testing.assert_array_equal(before, after)


def test_cross_fit_prediction_does_not_train_on_its_own_target():
    rng = np.random.default_rng(23)
    features = rng.normal(size=(30, 1, len(HEDGE_FEATURE_NAMES)))
    caps = np.asarray([0.05, 0.10])
    target = rng.uniform(0.0, 0.04, size=(30, 1, 2))
    target[:, :, 1] = np.maximum(target[:, :, 1], target[:, :, 0])
    kwargs = dict(
        features=features,
        start_date_discount=np.ones((30, 1)),
        cap_grid=caps,
        one_year_zero_bond_price=np.ones((30, 1)),
        folds=3,
        fold_seed=17,
    )
    base, models = cross_fitted_conditional_prices(
        discounted_payoff_target=target, **kwargs
    )
    changed = target.copy()
    changed[0, 0, :] = caps
    other, other_models = cross_fitted_conditional_prices(
        discounted_payoff_target=changed, **kwargs
    )
    np.testing.assert_allclose(other[0], base[0], rtol=0.0, atol=1.0e-12)
    assert models["fold_ids"][0] == other_models["fold_ids"][0]


def test_hedge_cache_invalidates_on_allocation_or_cap_grid_only(tmp_path):
    scenarios = synthetic_scenarios(n_paths=18)
    base = hedge_spec(scenarios)
    changed_allocation = replace(base, equity_allocation=0.45)
    changed_caps = replace(base, cap_grid=(0.0, 0.04, 0.06, 0.10))
    assert base.market_cache_key == changed_allocation.market_cache_key
    assert base.market_cache_key == changed_caps.market_cache_key
    assert len({base.cache_key, changed_allocation.cache_key, changed_caps.cache_key}) == 3

    surface = build_hedge_price_surface(scenarios, base)
    save_hedge_price_surface(tmp_path, surface)
    loaded = load_hedge_price_surface(tmp_path, base, scenarios, mmap_mode="r")
    assert isinstance(loaded.annual_fair_price_per_unit, np.memmap)
    assert loaded.price_surface_fingerprint == surface.price_surface_fingerprint
    with pytest.raises(HedgePriceCacheNotFoundError):
        load_hedge_price_surface(tmp_path, changed_caps, scenarios)


def test_surface_path_mapping_remains_exact_after_slice_repeat_and_prefix():
    scenarios = synthetic_scenarios(n_paths=18)
    surface = build_hedge_price_surface(scenarios, hedge_spec(scenarios))

    sliced_scenarios = _path_slice(scenarios, 3, 11)
    sliced = surface.slice_paths(3, 11, sliced_scenarios)
    sliced.validate_against(sliced_scenarios)
    assert sliced.hedge_cache_key == surface.hedge_cache_key
    np.testing.assert_array_equal(
        sliced.annual_fair_price_per_unit,
        surface.annual_fair_price_per_unit[3:11],
    )

    repeated_scenarios = _repeat_paths(scenarios, 2)
    repeated = surface.repeat_paths(2, repeated_scenarios)
    repeated.validate_against(repeated_scenarios)
    assert repeated.hedge_cache_key == surface.hedge_cache_key
    np.testing.assert_array_equal(
        repeated.annual_fair_price_per_unit[:scenarios.n_paths],
        surface.annual_fair_price_per_unit,
    )

    prefix_scenarios = _time_prefix(scenarios, 12)
    prefix = surface.horizon_prefix(12, prefix_scenarios)
    prefix.validate_against(prefix_scenarios)
    assert prefix.hedge_cache_key == surface.hedge_cache_key
    assert prefix.annual_fair_price_per_unit.shape[1] == 1


def test_mc_cost_markup_management_fee_and_bs_proxy_remain_separate():
    scenarios = synthetic_scenarios(n_paths=18)
    surface = build_hedge_price_surface(scenarios, hedge_spec(scenarios))
    scenarios.bind_hedge_price_surface(surface)
    product = IndexLinkedLifetimeIncomeProduct(
        reference_fund=ReferenceFundSpec(equity_weight=0.30)
    )
    policy = PolicySpec(age=80.0, income_start_year=1.0)
    result = project(
        product,
        policy,
        scenarios,
        BehaviourModel.static_only(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(
            record_paths=False,
            max_age=82.0,
            hedge_pricing_method="mc_conditional",
        ),
    )
    fair = result.cashflows["hedge_option_fair_value_costs"][:, 0]
    markup = result.cashflows["hedge_option_markup_costs"][:, 0]
    management = result.cashflows["hedge_management_fee_costs"][:, 0]
    bs_proxy = result.cashflows["hedge_option_fair_value_bs_proxy"][:, 0]
    np.testing.assert_allclose(markup, 0.005 * fair)
    assert np.all(management > 0.0)
    assert np.all(bs_proxy >= 0.0)
    assert not np.allclose(management, markup)


def test_explicit_moment_matched_bs_fallback_needs_no_hedge_cache():
    scenarios = synthetic_scenarios(n_paths=12)
    result = project(
        IndexLinkedLifetimeIncomeProduct(
            reference_fund=ReferenceFundSpec(equity_weight=0.30)
        ),
        PolicySpec(age=80.0, income_start_year=1.0),
        scenarios,
        BehaviourModel.static_only(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(
            record_paths=False,
            max_age=82.0,
            hedge_pricing_method="moment_matched_bs",
        ),
    )
    np.testing.assert_allclose(
        result.cashflows["hedge_option_fair_value_costs"],
        result.cashflows["hedge_option_fair_value_bs_proxy"],
    )
