"""Focused safety tests for the dynamic-Behaviour cap-control study."""

from dataclasses import replace

import numpy as np

from agile_engine import ProjectionConfig
from portfolio_simulations.optimize_crediting_rate_dynamic_behaviour import (
    ACTION_CAPS,
    CONTROL_STATE_FEATURE_NAMES,
    _adaptive_policy_passes_validation,
    _constant_first_year_policy,
    _projection_configs_by_sample,
    _screened_policy_actions,
)


def _constant_policy(*, values, standard_errors, deployable):
    raw = np.zeros((8, len(CONTROL_STATE_FEATURE_NAMES)))
    outputs = np.zeros((len(ACTION_CAPS), 10))
    outputs[:, 0] = np.asarray(values, dtype=float)
    policy = _constant_first_year_policy(
        year=0,
        raw_state=raw,
        action_values=outputs,
        action_standard_errors=np.asarray(standard_errors, dtype=float),
        feature_names=CONTROL_STATE_FEATURE_NAMES,
    )
    return replace(
        policy,
        action_deployable_mask=np.asarray(deployable, dtype=bool),
    )


def test_projection_rng_namespaces_are_distinct_but_reproducible():
    first = _projection_configs_by_sample(ProjectionConfig())
    second = _projection_configs_by_sample(ProjectionConfig())

    assert first == second
    assert len({item.take_up_seed for item in first.values()}) == 4
    assert len({item.mortality_seed for item in first.values()}) == 4


def test_action_mask_excludes_only_the_unreliable_high_q_cap():
    fallback = 3
    unreliable = 7
    stable_alternative = 5
    values = np.zeros(len(ACTION_CAPS))
    values[unreliable] = 100.0
    values[stable_alternative] = 20.0
    deployable = np.ones(len(ACTION_CAPS), dtype=bool)
    deployable[unreliable] = False
    policy = _constant_policy(
        values=values,
        standard_errors=np.zeros(len(ACTION_CAPS)),
        deployable=deployable,
    )

    chosen, diagnostics = _screened_policy_actions(
        policy=policy,
        raw_state=np.zeros((4, len(CONTROL_STATE_FEATURE_NAMES))),
        feature_names=CONTROL_STATE_FEATURE_NAMES,
        fallback_action=fallback,
        advantage_screen_multiplier=1.96,
    )

    np.testing.assert_array_equal(chosen, np.full(4, stable_alternative))
    assert diagnostics["masked_action_count"] == 1
    assert diagnostics["adaptive_action_count"] == 4


def test_local_advantage_screen_and_unsafe_fallback_fit_retain_fixed_cap():
    fallback = 3
    alternative = 5
    values = np.zeros(len(ACTION_CAPS))
    values[alternative] = 1.0
    standard_errors = np.ones(len(ACTION_CAPS))
    deployable = np.ones(len(ACTION_CAPS), dtype=bool)
    policy = _constant_policy(
        values=values,
        standard_errors=standard_errors,
        deployable=deployable,
    )

    screened, diagnostics = _screened_policy_actions(
        policy=policy,
        raw_state=np.zeros((3, len(CONTROL_STATE_FEATURE_NAMES))),
        feature_names=CONTROL_STATE_FEATURE_NAMES,
        fallback_action=fallback,
        advantage_screen_multiplier=1.96,
    )
    np.testing.assert_array_equal(screened, np.full(3, fallback))
    assert diagnostics["advantage_screen_fallback_count"] == 3

    unsafe_fallback = replace(
        policy,
        action_deployable_mask=np.asarray([
            action != fallback for action in range(len(ACTION_CAPS))
        ]),
    )
    retained, diagnostics = _screened_policy_actions(
        policy=unsafe_fallback,
        raw_state=np.zeros((3, len(CONTROL_STATE_FEATURE_NAMES))),
        feature_names=CONTROL_STATE_FEATURE_NAMES,
        fallback_action=fallback,
        advantage_screen_multiplier=0.0,
    )
    np.testing.assert_array_equal(retained, np.full(3, fallback))
    assert diagnostics["fit_mask_fallback_count"] == 3


def test_positive_paired_validation_can_accept_a_masked_candidate():
    assert _adaptive_policy_passes_validation(
        masked_candidate_executable=True,
        policyholder_validation_passed=True,
        causal_rollout_valid=True,
        csm_delta_aud=196.01,
        paired_standard_error_aud=100.0,
    )
    assert not _adaptive_policy_passes_validation(
        masked_candidate_executable=True,
        policyholder_validation_passed=True,
        causal_rollout_valid=True,
        csm_delta_aud=196.0,
        paired_standard_error_aud=100.0,
    )
