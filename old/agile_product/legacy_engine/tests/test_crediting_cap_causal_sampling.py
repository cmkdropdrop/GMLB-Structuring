"""Focused sampling and causality tests for crediting-cap deployment."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from agile_engine import ESGConfig, Index, Measure, ScenarioSet, YieldCurve
from portfolio_simulations import optimize_crediting_rate_lsmc as optimizer


class _FitSetStub:
    def __init__(self, cap: float, scenario_fingerprint: str) -> None:
        self.cap = float(cap)
        self.scenario_fingerprint = scenario_fingerprint
        self.cap_schedule_fingerprint = f"constant-cap::{cap:.4f}"
        self.fallback_count = 0
        self.validation_fallback_signatures: set[tuple[object, ...]] = set()

    def factory(self, _policy: object) -> object:
        return SimpleNamespace(cap=self.cap)


def test_fixed_lsmc_fits_only_training_and_selects_without_final_paths(
    monkeypatch,
):
    """Final evaluation outcomes cannot train or select the fixed benchmark."""
    training = _deterministic_scenarios(future_level=1.0, n_paths=3)
    evaluation = _deterministic_scenarios(future_level=1.5, n_paths=6)
    assert training.content_fingerprint != evaluation.content_fingerprint
    cases = (
        ("fixed_cap_1pct", 0.01, "one percent"),
        ("fixed_cap_2pct", 0.02, "two percent"),
    )
    monkeypatch.setattr(optimizer, "_benchmark_cases", lambda: cases)

    fit_calls: list[tuple[object, np.ndarray]] = []

    def fake_fit(**kwargs):
        scenario_sample = kwargs["scenarios"]
        cap_matrix = np.asarray(kwargs["cap_matrix"], dtype=float)
        fit_calls.append((scenario_sample, cap_matrix.copy()))
        assert scenario_sample is training
        assert cap_matrix.shape == (training.n_paths, 2)
        cap = float(cap_matrix[0, 0])
        np.testing.assert_array_equal(cap_matrix, np.full_like(cap_matrix, cap))
        return _FitSetStub(cap, scenario_sample.content_fingerprint)

    monkeypatch.setattr(
        optimizer, "_fit_cap_aware_policyholder_policies", fake_fit
    )

    # Cap 1% wins by one unit on the selection paths but is made arbitrarily
    # bad on the untouched final paths.  If final outcomes leaked into model
    # selection, cap 2% would necessarily win.
    path_values = {
        0.01: np.array([10.0, 10.0, -1.0e12, -1.0e12, -1.0e12, -1.0e12]),
        0.02: np.array([9.0, 9.0, 1.0e12, 1.0e12, 1.0e12, 1.0e12]),
    }
    projection_calls: list[tuple[object, np.ndarray, float | None]] = []

    def fake_aggregate(**kwargs):
        scenario_sample = kwargs["scenarios"]
        cap_matrix = np.asarray(kwargs["cap_matrix"], dtype=float)
        cap = float(cap_matrix[0, 0])
        factory = kwargs.get("surrender_policy_factory")
        factory_owner = None if factory is None else getattr(factory, "__self__")
        fitted_cap = None if factory_owner is None else factory_owner.cap
        projection_calls.append((scenario_sample, cap_matrix.copy(), fitted_cap))
        assert scenario_sample is evaluation
        assert cap_matrix.shape == (evaluation.n_paths, 2)
        if fitted_cap is not None:
            assert np.isclose(fitted_cap, cap)
            csm = path_values[cap]
            # The selection paths establish non-negative customer optionality;
            # deliberately hostile final-path values must not trigger fallback.
            policyholder = np.array(
                [1.0, 1.0, -1.0e12, -1.0e12, -1.0e12, -1.0e12]
            )
        else:
            csm = np.zeros(evaluation.n_paths)
            policyholder = np.zeros(evaluation.n_paths)
        return SimpleNamespace(
            new_business_csm_proxy=csm[:, None],
            policyholder_benefits_by_signature={
                ("test-policy",): policyholder[:, None]
            },
            inforce_exposure=np.ones((evaluation.n_paths, 2)),
        )

    monkeypatch.setattr(optimizer, "_aggregate_portfolio_paths", fake_aggregate)
    monkeypatch.setattr(
        optimizer,
        "_summed_csm_components",
        lambda projected, _path_slice: {
            "stub": np.asarray(projected.new_business_csm_proxy[:, 0])
        },
    )

    def fake_benchmark_row(**kwargs):
        return {
            "case": kwargs["label"],
            "cap": kwargs["cap"],
            "is_best_fixed_cap_admissible_grid": kwargs["is_best_fixed"],
            "reported_final_mean": float(np.mean(kwargs["csm_paths"])),
        }

    monkeypatch.setattr(optimizer, "_csm_benchmark_row", fake_benchmark_row)
    monkeypatch.setattr(
        optimizer, "_policyholder_exercise_rows", lambda **_kwargs: []
    )

    (
        rows,
        final_values,
        selection_values,
        best_label,
        metadata,
        fit_sets,
        exercise_rows,
        validation_rows,
    ) = optimizer._evaluate_fixed_lsmc_benchmarks(
        training_scenarios=training,
        evaluation_scenarios=evaluation,
        n_years=2,
        product=object(),
        model_points=object(),
        mortality=object(),
        expenses=object(),
        projection_config=object(),
        portfolio_scale=1.0,
        model_point_log_interval=1,
        selection_path_count=2,
        follower_settings=object(),
    )

    assert len(fit_calls) == len(cases)
    assert all(sample is training for sample, _caps in fit_calls)
    assert len(projection_calls) == 2 * len(cases)
    assert all(sample is evaluation for sample, _caps, _fit_cap in projection_calls)
    assert sum(fitted_cap is not None for _, _, fitted_cap in projection_calls) == len(
        cases
    )
    assert set(fit_sets) == {case[0] for case in cases}
    assert all(not fit.validation_fallback_signatures for fit in fit_sets.values())

    assert best_label == "fixed_cap_1pct"
    assert np.mean(final_values["fixed_cap_2pct"]) > np.mean(
        final_values["fixed_cap_1pct"]
    )
    np.testing.assert_array_equal(
        selection_values["fixed_cap_1pct"], path_values[0.01][:2]
    )
    np.testing.assert_array_equal(
        final_values["fixed_cap_1pct"], path_values[0.01][2:]
    )
    assert metadata["best_fixed_selection_csm_aud"] == 10.0
    best_rows = [row for row in rows if row["is_best_fixed_cap_admissible_grid"]]
    assert [row["case"] for row in best_rows] == [best_label]
    assert exercise_rows == []
    assert len(validation_rows) == len(cases)
    assert all(not row["continue_fallback_required"] for row in validation_rows)
    assert all(not row["continue_fallback_deployed"] for row in validation_rows)
    validation_fingerprint = optimizer._slice_scenarios(
        evaluation, 0, 2
    ).content_fingerprint
    assert validation_fingerprint != evaluation.content_fingerprint
    assert all(
        row["sample_fingerprint"] == validation_fingerprint
        and row["sample_path_count"] == 2
        for row in validation_rows
    )


def _deterministic_scenarios(
    *, future_level: float, n_paths: int = 2
) -> ScenarioSet:
    n_steps = 36
    times = np.arange(n_steps + 1, dtype=float) / 12.0
    common = np.ones((n_paths, n_steps + 1), dtype=float)
    global_equity = common.copy()
    global_equity[:, 13:] = future_level
    short_rate = np.full_like(common, 0.04)
    discount = np.broadcast_to(np.exp(-0.04 * times), common.shape).copy()
    return ScenarioSet(
        config=ESGConfig(curve=YieldCurve.flat(0.04)),
        measure=Measure.RISK_NEUTRAL,
        dt=1.0 / 12.0,
        times=times,
        index_levels={
            Index.AUS_EQUITY: common,
            Index.GLOBAL_EQUITY: global_equity,
        },
        short_rate=short_rate,
        discount=discount,
        model_name="black_scholes",
        seed=17,
    )


def test_projected_state_rollout_freezes_actions_from_time_prefixes(monkeypatch):
    """Changing market paths after year one only affects later cap decisions."""
    n_paths, n_years = 2, 3
    inputs = optimizer.ControlStateInputs(
        market_features=np.zeros((n_paths, n_years + 1, 5), dtype=float),
        annual_reference_fund_return=np.zeros((n_paths, n_years), dtype=float),
    )
    feature_names = (
        *optimizer.CONTROL_STATE_FEATURE_NAMES,
        *optimizer.PORTFOLIO_CONTROL_STATE_FEATURE_NAMES,
    )
    fallback_cap = 0.01
    alternative_cap = 0.20
    fallback_action = int(np.flatnonzero(
        np.isclose(optimizer.ACTION_CAPS, fallback_cap)
    )[0])
    alternative_action = int(np.flatnonzero(
        np.isclose(optimizer.ACTION_CAPS, alternative_cap)
    )[0])
    policies = [
        SimpleNamespace(
            year=year,
            numerically_stable=True,
            action_caps=optimizer.ACTION_CAPS,
            action_value_standard_error=np.zeros(len(optimizer.ACTION_CAPS)),
        )
        for year in range(n_years)
    ]

    aggregate_calls: list[SimpleNamespace] = []

    def fake_aggregate(**kwargs):
        call = SimpleNamespace(
            scenarios=kwargs["scenarios"],
            cap_matrix=np.asarray(kwargs["cap_matrix"], dtype=float).copy(),
        )
        aggregate_calls.append(call)
        return call

    monkeypatch.setattr(optimizer, "_aggregate_portfolio_paths", fake_aggregate)

    def fake_portfolio_extension(projected):
        decision_step = (
            0 if projected.scenarios.n_steps < 12 else projected.scenarios.n_steps
        )
        marker = np.asarray(
            projected.scenarios.index_levels[Index.GLOBAL_EQUITY][
                :, decision_step
            ],
            dtype=float,
        )
        rich = np.broadcast_to(
            marker[:, None, None],
            (
                marker.size,
                projected.cap_matrix.shape[1] + 1,
                len(optimizer.PORTFOLIO_CONTROL_STATE_FEATURE_NAMES),
            ),
        ).copy()
        return rich, optimizer.PORTFOLIO_CONTROL_STATE_FEATURE_NAMES

    monkeypatch.setattr(
        optimizer, "_portfolio_state_extension", fake_portfolio_extension
    )

    def fake_policy_values(_policy, raw_state, _feature_names):
        state = np.asarray(raw_state, dtype=float)
        values = np.full(
            (state.shape[0], len(optimizer.ACTION_CAPS), 1), -1.0, dtype=float
        )
        values[:, fallback_action, 0] = 0.0
        first_rich_feature = state[
            :, len(optimizer.CONTROL_STATE_FEATURE_NAMES)
        ]
        values[:, alternative_action, 0] = np.where(
            first_rich_feature > 2.0, 1.0, -1.0
        )
        return values

    monkeypatch.setattr(optimizer, "_policy_action_values", fake_policy_values)

    def run(scenarios: ScenarioSet):
        call_start = len(aggregate_calls)
        caps, projected, metadata = (
            optimizer._rollout_cap_policy_with_projected_states(
                inputs=inputs,
                policy_years=policies,
                feature_names=feature_names,
                fallback_cap=fallback_cap,
                scenarios=scenarios,
                product=object(),
                model_points=object(),
                behaviour=object(),
                mortality=object(),
                expenses=object(),
                projection_config=object(),
                model_point_log_interval=1,
                surrender_policy_factory=None,
            )
        )
        return caps, projected, metadata, aggregate_calls[call_start:]

    baseline_caps, _baseline_projection, baseline_meta, baseline_calls = run(
        _deterministic_scenarios(future_level=1.0)
    )
    changed_caps, _changed_projection, changed_meta, changed_calls = run(
        _deterministic_scenarios(future_level=3.0)
    )

    assert [call.scenarios.n_steps for call in baseline_calls] == [1, 12, 24, 36]
    assert [call.scenarios.n_steps for call in changed_calls] == [1, 12, 24, 36]
    assert baseline_calls[0].scenarios.content_fingerprint == (
        changed_calls[0].scenarios.content_fingerprint
    )
    assert baseline_calls[1].scenarios.content_fingerprint == (
        changed_calls[1].scenarios.content_fingerprint
    )
    assert baseline_calls[2].scenarios.content_fingerprint != (
        changed_calls[2].scenarios.content_fingerprint
    )

    np.testing.assert_array_equal(
        baseline_caps, np.full((n_paths, n_years), fallback_cap)
    )
    np.testing.assert_array_equal(changed_caps[:, :2], baseline_caps[:, :2])
    np.testing.assert_array_equal(
        changed_caps[:, 2], np.full(n_paths, alternative_cap)
    )
    # At the year-two prefix call the year-two action is not frozen yet.  It
    # appears only in the final projection after observing the year-two state.
    np.testing.assert_array_equal(
        changed_calls[2].cap_matrix[:, 2], np.full(n_paths, fallback_cap)
    )
    np.testing.assert_array_equal(
        changed_calls[3].cap_matrix[:, 2], np.full(n_paths, alternative_cap)
    )
    assert baseline_meta["method"] == "exact_causal_prefix_rollout"
    assert changed_meta["evaluation_sample_used_for_fallback"] is False
