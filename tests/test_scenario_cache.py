"""Targeted tests for the strict reusable Q market-path cache."""

from dataclasses import replace

import numpy as np
import pytest

from policy_engine import ESGConfig, Measure, ScenarioSet, YieldCurve
from policy_engine._provenance import assumption_fingerprint
from policy_engine.product import Index
from policy_engine.scenario_cache import (
    ScenarioCacheNotFoundError,
    ScenarioCacheSpec,
    load_scenario_set,
    save_scenario_set,
)


def synthetic_scenarios(n_paths: int = 12, years: int = 2) -> ScenarioSet:
    config = ESGConfig(curve=YieldCurve.flat(0.03))
    times = np.arange(years * 12 + 1, dtype=float) / 12.0
    path = np.arange(n_paths, dtype=float)[:, None]
    month = np.arange(times.size, dtype=float)[None, :]
    short_rate = 0.02 + 0.0002 * path + 0.00005 * month
    discount = np.exp(-short_rate * times[None, :])
    global_level = np.exp(
        (0.035 + 0.001 * path) * times[None, :]
        + 0.01 * np.sin(month / 3.0 + path)
        - 0.01 * np.sin(path)
    )
    aus_level = np.exp(
        (0.03 + 0.0008 * path) * times[None, :]
        + 0.008 * np.sin(month / 4.0 + path)
        - 0.008 * np.sin(path)
    )
    variance_global = np.broadcast_to(
        0.0225 + 0.0001 * path, (n_paths, times.size)
    ).copy()
    variance_aus = np.broadcast_to(
        0.0256 + 0.0001 * path, (n_paths, times.size)
    ).copy()
    return ScenarioSet(
        config=config,
        measure=Measure.RISK_NEUTRAL,
        dt=1.0 / 12.0,
        times=times,
        index_levels={
            Index.GLOBAL_EQUITY: global_level,
            Index.AUS_EQUITY: aus_level,
        },
        short_rate=short_rate,
        discount=discount,
        variance={
            Index.GLOBAL_EQUITY: variance_global,
            Index.AUS_EQUITY: variance_aus,
        },
        stochastic_rates=True,
        model_name="heston_hull_white",
        seed=17,
        substeps=3,
    )


def cache_spec(scenarios: ScenarioSet) -> ScenarioCacheSpec:
    return ScenarioCacheSpec.from_inputs(
        scenarios.config,
        australian_curve_sha256="a" * 64,
        model_parameters_sha256="b" * 64,
        horizon_years=float(scenarios.times[-1]),
        n_paths=scenarios.n_paths,
        seed=scenarios.seed,
        heston_substeps=int(scenarios.substeps),
    )


def test_scenario_cache_roundtrip_preserves_arrays_and_fingerprint(tmp_path):
    scenarios = synthetic_scenarios()
    spec = cache_spec(scenarios)
    save_scenario_set(tmp_path, spec, scenarios)
    loaded = load_scenario_set(tmp_path, spec, scenarios.config, mmap_mode=None)

    assert loaded.content_fingerprint == scenarios.content_fingerprint
    assert loaded.market_cache_key == spec.cache_key
    assert loaded.market_variant == spec.market_variant
    np.testing.assert_array_equal(loaded.times, scenarios.times)
    np.testing.assert_array_equal(loaded.short_rate, scenarios.short_rate)
    np.testing.assert_array_equal(loaded.discount, scenarios.discount)
    for index in Index:
        np.testing.assert_array_equal(
            loaded.index_levels[index], scenarios.index_levels[index]
        )
        np.testing.assert_array_equal(
            loaded.variance[index], scenarios.variance[index]
        )
    assert not loaded.short_rate.flags.writeable


def test_scenario_cache_supports_memory_mapped_loading(tmp_path):
    scenarios = synthetic_scenarios()
    spec = cache_spec(scenarios)
    save_scenario_set(tmp_path, spec, scenarios)
    loaded = load_scenario_set(tmp_path, spec, scenarios.config, mmap_mode="r")

    assert isinstance(loaded.short_rate, np.memmap)
    assert isinstance(loaded.index_levels[Index.GLOBAL_EQUITY], np.memmap)
    assert loaded.short_rate.mode == "r"


@pytest.mark.parametrize(
    "changed",
    (
        {"seed": 18},
        {"horizon_years": 1.0},
        {"model_parameters_sha256": "c" * 64},
        {"australian_curve_sha256": "d" * 64},
        {"market_variant": "equity_level_down"},
    ),
)
def test_exact_cache_lookup_rejects_seed_horizon_inputs_or_stress_change(
    tmp_path, changed,
):
    scenarios = synthetic_scenarios()
    spec = cache_spec(scenarios)
    save_scenario_set(tmp_path, spec, scenarios)
    other = replace(spec, **changed)

    with pytest.raises(ScenarioCacheNotFoundError, match="Exact market cache"):
        load_scenario_set(tmp_path, other, scenarios.config)


def test_esg_fingerprint_is_part_of_market_cache_key():
    scenarios = synthetic_scenarios()
    base = cache_spec(scenarios)
    bumped = scenarios.config.bump_equity_vol(0.10)
    changed = replace(
        base, esg_config_fingerprint=assumption_fingerprint(bumped)
    )
    assert changed.cache_key != base.cache_key
