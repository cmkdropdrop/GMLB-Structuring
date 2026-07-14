"""Focused safety tests for the alternative dynamic-Behaviour cap study."""

import json
from dataclasses import replace

import numpy as np
import pytest

from policy_engine import ProjectionConfig
from policy_engine.crediting_capital import (
    PairedBootstrapRatioDelta,
    PolicyCSMPathArrays,
    score_lsmc_value_vectors,
)
from portfolio_simulations.optimize_crediting_rate_dynamic_behaviour_alt import (
    ACTION_CAPS,
    CONTROL_STATE_FEATURE_NAMES,
    SLIM_DIRECT_Q_BASIS_DIMENSION,
    BackwardResult,
    PortfolioPathData,
    ManagementObjectiveSpec,
    _adaptive_policy_passes_ratio_validation,
    _adaptive_policy_passes_validation,
    _backward_induction,
    _constant_first_year_policy,
    _csm_mll_evaluation_from_paths,
    _direct_transition_target,
    _decision_year_activity_exposure,
    _fit_direct_q_chain,
    _grid_continuation_lookup,
    _lower_cap_argmax,
    _masked_lower_cap_argmax,
    _mll_metrics_from_payload,
    _management_payload_and_activity_exposure,
    _objective_from_payload,
    _time_zero_policy_class_weights,
    parse_args,
    _pathwise_outer_fold_ids,
    _policy_action_values,
    _policy_payload,
    _projection_configs_by_sample,
    _screened_policy_component_values,
    _screened_policy_actions,
    _select_best_fixed_label,
    _shell_neutral_argv_display,
    _slim_direct_q_design,
    _fit_time_zero_chain,
    _clip_management_predictions,
    _load_benchmark_cache,
    _store_benchmark_cache,
    _validate_benchmark_cache_arrays,
    _validated_activity_exposure,
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


def _portfolio_path_data(*, fees, raw_states, exposure=None):
    fees = np.asarray(fees, dtype=float)
    states = np.asarray(raw_states, dtype=float)
    zeros = np.zeros_like(fees)
    if exposure is None:
        exposure = np.ones_like(fees)
    feature_names = (
        "log_reference_fund_level",
        "short_rate",
        "heston_variance_global",
        "account_value_per_initial_premium",
    )
    return PortfolioPathData(
        guarantee_claims=zeros.copy(),
        other_insurer_funded_benefits=zeros.copy(),
        fees_product=fees,
        fees_lip=zeros.copy(),
        crediting_margin=zeros.copy(),
        money_market_income=zeros.copy(),
        hedge_gain=zeros.copy(),
        mva_retained=zeros.copy(),
        aps_retained=zeros.copy(),
        expenses=zeros.copy(),
        hedge_costs=zeros.copy(),
        income_paid=zeros.copy(),
        death_benefits=zeros.copy(),
        surrender_benefits=zeros.copy(),
        partial_withdrawals=zeros.copy(),
        terminal_closeout=zeros.copy(),
        lapse_events=zeros.copy(),
        inforce_exposure=np.asarray(exposure, dtype=float),
        raw_states=states,
        state_feature_names=feature_names,
        pre_action_states=None,
        pre_action_state_feature_names=(),
        representative_initial_premium=100.0,
    )


def _synthetic_direct_q_data(paths_per_action: int = 12):
    rng = np.random.default_rng(812_377)
    n_actions = len(ACTION_CAPS)
    observed = np.repeat(np.arange(n_actions, dtype=np.int64), paths_per_action)
    n_paths = observed.size
    action_indices = np.column_stack((observed, np.roll(observed, 3)))
    feature_names = (
        "log_reference_fund_level",
        "short_rate",
        "heston_variance_global",
        "account_value_per_initial_premium",
    )
    raw_states = np.zeros((n_paths, 3, len(feature_names)))
    for year in range(3):
        raw_states[:, year, 0] = rng.normal(0.02 * year, 0.16, n_paths)
        raw_states[:, year, 1] = rng.normal(0.025, 0.012, n_paths)
        raw_states[:, year, 2] = rng.uniform(0.01, 0.09, n_paths)
        raw_states[:, year, 3] = rng.uniform(0.35, 1.65, n_paths)
    fees = np.column_stack((
        2.0 + 8.0 * ACTION_CAPS[action_indices[:, 0]]
        + 0.4 * raw_states[:, 0, 3] + rng.normal(0.0, 0.03, n_paths),
        1.0 + 5.0 * ACTION_CAPS[action_indices[:, 1]]
        + 0.2 * raw_states[:, 1, 3] + rng.normal(0.0, 0.03, n_paths),
    ))
    data = _portfolio_path_data(fees=fees, raw_states=raw_states)
    return data, action_indices


def test_projection_rng_namespaces_are_distinct_but_reproducible():
    first = _projection_configs_by_sample(ProjectionConfig())
    second = _projection_configs_by_sample(ProjectionConfig())

    assert first == second
    assert len({item.take_up_seed for item in first.values()}) == 4
    assert len({item.mortality_seed for item in first.values()}) == 4


def test_cache_remediation_argv_display_is_shell_neutral_and_lossless():
    argv = [
        "C:/Program Files/Python/python.exe",
        "C:/repo with spaces/precompute.py",
        "--cap-grid",
        "0.0025,0.01",
        "apostrophe's-value",
    ]

    display = _shell_neutral_argv_display(argv)

    assert json.loads(display) == argv
    assert not display.lstrip().startswith("&")


def test_activity_exposure_clips_only_numerical_negative_noise():
    values = np.array([[1.0, -1.0e-14], [0.5, 0.0]])

    cleaned = _validated_activity_exposure(
        values, expected_shape=(2, 2), label="test"
    )

    np.testing.assert_array_equal(cleaned, [[1.0, 0.0], [0.5, 0.0]])
    with np.testing.assert_raises_regex(ValueError, "materially negative"):
        _validated_activity_exposure(
            np.array([[1.0, -1.0e-6]]),
            expected_shape=(1, 2),
            label="test",
        )


def test_decision_year_activity_exposure_drops_only_terminal_boundary():
    boundary_values = np.array([
        [1.0, 0.8, 0.4, 0.1],
        [1.0, 0.7, 0.2, 0.0],
    ])

    aligned = _decision_year_activity_exposure(
        boundary_values,
        n_paths=2,
        n_years=3,
        label="test",
    )

    np.testing.assert_array_equal(aligned, boundary_values[:, :3])
    with np.testing.assert_raises_regex(ValueError, "has shape"):
        _decision_year_activity_exposure(
            np.ones((2, 5)),
            n_paths=2,
            n_years=3,
            label="test",
        )


def test_capital_aware_benchmark_cache_round_trips_complete_mll_ledger(tmp_path):
    paths = PolicyCSMPathArrays(
        base_csm_paths=np.array([10.0, 12.0, 11.0]),
        mortality_stressed_csm_paths=np.array([9.0, 10.0, 9.0]),
        longevity_stressed_csm_paths=np.array([8.0, 9.0, 8.0]),
        lapse_up_stressed_csm_paths=np.array([7.0, 8.0, 7.0]),
        lapse_down_stressed_csm_paths=np.array([10.0, 11.0, 10.0]),
        model_point_base_csm_paths=np.array([
            [6.0, 4.0], [7.0, 5.0], [6.5, 4.5]
        ]),
    )
    objective = ManagementObjectiveSpec(
        kind="csm_to_mll",
        model_point_count=2,
        capital_materiality=1.0e-9,
        mass_lapse_fraction=0.4,
    )
    evaluation = _csm_mll_evaluation_from_paths(
        paths, model_point_ids=("mp1", "mp2"), objective_spec=objective
    )
    component_names = (
        "fees_product", "fees_lip", "crediting_margin",
        "money_market_income", "hedge_gain", "mva_retained",
        "aps_retained", "guarantee_claims",
        "other_insurer_funded_benefits", "expenses", "hedge_costs",
        "income_paid", "death_benefits", "surrender_benefits",
        "partial_withdrawals", "terminal_closeout", "lapse_events",
    )
    components = {name: np.zeros(2) for name in component_names}
    cache_path = tmp_path / "benchmark.npz"

    _store_benchmark_cache(
        cache_path,
        np.asarray(paths.base_csm_paths),
        np.array([13.0, 14.0]),
        components,
        evaluation,
    )
    selection, final, loaded_components, loaded_paths, loaded_ids = (
        _load_benchmark_cache(cache_path)
    )

    _validate_benchmark_cache_arrays(
        selection_csm=selection,
        evaluation_csm=final,
        components=loaded_components,
        selection_path_count=3,
        evaluation_path_count=2,
        selection_mll_paths=loaded_paths,
        model_point_ids=loaded_ids,
    )
    rebuilt = _csm_mll_evaluation_from_paths(
        loaded_paths,
        model_point_ids=loaded_ids,
        objective_spec=objective,
    )
    assert loaded_ids == ("mp1", "mp2")
    assert rebuilt.result.csm_to_mll_ratio \
        == evaluation.result.csm_to_mll_ratio


def test_grid_interpolation_is_pathwise_linear_and_clamps_boundaries():
    grid = np.array([0.0, 1.0, 3.0])
    node_values = np.zeros((4, 3, 9))
    node_values[:, :, 0] = np.array([0.0, 2.0, 10.0])
    query = np.array([-1.0, 0.25, 2.0, 4.0])

    interpolated, delta = _grid_continuation_lookup(
        node_values, grid, query
    )

    np.testing.assert_allclose(interpolated[:, 0], [0.0, 0.5, 6.0, 10.0])
    np.testing.assert_allclose(delta[:, 0], [2.0, 2.0, 8.0, 8.0])


def test_direct_transition_target_uses_each_realised_next_inventory():
    grid = np.array([0.0, 1.0, 2.0])
    next_values = np.zeros((2, 3, 9))
    next_values[:, :, 0] = np.array([0.0, 1.0, 4.0])
    immediate = np.zeros((2, 9))

    direct = _direct_transition_target(
        immediate,
        next_node_values=next_values,
        inventory_grid=grid,
        realised_next_inventory=np.array([0.5, 1.5]),
    )
    at_mean_transition = _direct_transition_target(
        immediate,
        next_node_values=next_values,
        inventory_grid=grid,
        realised_next_inventory=np.ones(2),
    )

    np.testing.assert_allclose(direct[:, 0], [0.5, 2.5])
    np.testing.assert_allclose(at_mean_transition[:, 0], [1.0, 1.0])
    assert np.mean(direct[:, 0]) != np.mean(at_mean_transition[:, 0])


def test_two_year_screened_target_matches_frozen_direct_rollout_rule():
    fallback = 0
    alternative = 5
    component_values = np.zeros(len(ACTION_CAPS))
    component_values[fallback] = 2.0
    component_values[alternative] = 10.0
    policy = _constant_policy(
        values=component_values,
        standard_errors=np.full(len(ACTION_CAPS), 4.0),
        deployable=np.ones(len(ACTION_CAPS), dtype=bool),
    )
    coefficients = policy.coefficients.copy()
    # Component zero is fee income, so its derived CSM agrees with the constant
    # Q value used by the rollout screen.
    coefficients[:, 0, 1] = component_values
    policy = replace(policy, coefficients=coefficients)
    raw_next_state = np.zeros((4, len(CONTROL_STATE_FEATURE_NAMES)))

    screened_components, chosen = _screened_policy_component_values(
        policy=policy,
        raw_state=raw_next_state,
        feature_names=CONTROL_STATE_FEATURE_NAMES,
        fallback_action=fallback,
        advantage_screen_multiplier=1.96,
    )
    all_values = _policy_action_values(
        policy, raw_next_state, CONTROL_STATE_FEATURE_NAMES
    )
    rows = np.arange(raw_next_state.shape[0])
    immediate = np.zeros((raw_next_state.shape[0], 9))
    immediate[:, 0] = np.arange(1.0, 5.0)
    node_values = np.repeat(screened_components[:, None, :], 3, axis=1)
    bellman_target = _direct_transition_target(
        immediate,
        next_node_values=node_values,
        inventory_grid=np.array([0.0, 1.0, 2.0]),
        realised_next_inventory=np.array([0.0, 0.4, 1.3, 2.0]),
    )
    direct_rollout_value = immediate + all_values[rows, chosen, 1:]

    np.testing.assert_array_equal(chosen, np.full(4, fallback))
    np.testing.assert_allclose(bellman_target, direct_rollout_value)


def test_complete_path_outer_fold_is_held_out_from_every_recursive_fit():
    data, actions = _synthetic_direct_q_data()
    fold_ids = _pathwise_outer_fold_ids(actions, folds=3, seed=91)
    held_out = fold_ids == 0
    training = ~held_out
    first = _fit_direct_q_chain(
        data=data,
        action_indices=actions,
        fit_mask=training,
        folds=3,
        ridge=1.0e-6,
        inventory_nodes=5,
        inventory_quantile_clip=0.0,
        minimum_training_count=SLIM_DIRECT_Q_BASIS_DIMENSION,
    )

    changed_fees = data.fees_product.copy()
    changed_fees[held_out, :] += 1.0e8
    changed = replace(data, fees_product=changed_fees)
    second = _fit_direct_q_chain(
        data=changed,
        action_indices=actions,
        fit_mask=training,
        folds=3,
        ridge=1.0e-6,
        inventory_nodes=5,
        inventory_quantile_clip=0.0,
        minimum_training_count=SLIM_DIRECT_Q_BASIS_DIMENSION,
    )

    assert set(np.unique(fold_ids)) == {0, 1, 2}
    for year in (0, 1):
        np.testing.assert_allclose(
            first.policies[year].coefficients,
            second.policies[year].coefficients,
            rtol=0.0,
            atol=0.0,
        )
        np.testing.assert_allclose(
            first.grid_values[year].node_coefficients,
            second.grid_values[year].node_coefficients,
            rtol=0.0,
            atol=0.0,
        )


def test_fit_and_deployment_share_basis_and_therefore_argmax():
    data, actions = _synthetic_direct_q_data()
    chain = _fit_direct_q_chain(
        data=data,
        action_indices=actions,
        fit_mask=np.ones(actions.shape[0], dtype=bool),
        folds=2,
        ridge=1.0e-6,
        inventory_nodes=5,
        inventory_quantile_clip=0.0,
        minimum_training_count=SLIM_DIRECT_Q_BASIS_DIMENSION,
    )
    policy = chain.policies[1]
    raw = data.raw_states[:80, 1, :]
    design, _, _ = _slim_direct_q_design(
        raw,
        data.state_feature_names,
        policy.raw_mean,
        policy.raw_scale,
    )
    unbounded = np.einsum("pb,abo->pao", design, policy.coefficients)
    lower = np.asarray(policy.value_lower_bounds)
    upper = np.asarray(policy.value_upper_bounds)
    bounded = np.minimum(np.maximum(unbounded, lower[None, :, :]), upper[None, :, :])
    bounded[:, :, 0] = (
        bounded[:, :, 1] + bounded[:, :, 2] + bounded[:, :, 3]
        + bounded[:, :, 4] + bounded[:, :, 5] - bounded[:, :, 6]
        - bounded[:, :, 7] - bounded[:, :, 8] - bounded[:, :, 9]
    )
    deployed = _policy_action_values(policy, raw, data.state_feature_names)
    mask = np.asarray(policy.action_deployable_mask, dtype=bool)

    assert policy.compact_q_basis
    assert policy.coefficients.shape[1] == SLIM_DIRECT_Q_BASIS_DIMENSION
    np.testing.assert_array_equal(
        _masked_lower_cap_argmax(bounded[:, :, 0], mask, axis=1),
        _masked_lower_cap_argmax(deployed[:, :, 0], mask, axis=1),
    )


def test_backward_diagnostics_are_complete_path_outer_fold_oos():
    data, actions = _synthetic_direct_q_data(paths_per_action=60)
    result = _backward_induction(
        data,
        actions,
        folds=2,
        ridge=1.0e-6,
        seed=71,
        inventory_nodes=5,
        inventory_quantile_clip=0.0,
    )

    assert result.first_year_cap in ACTION_CAPS
    assert all(policy.compact_q_basis for policy in result.policy_years)
    assert all(row["outer_fold_pure"] for row in result.regression_rows)
    assert all(row["outer_fold_count"] == 2 for row in result.regression_rows)
    assert all(
        row["direct_realised_transition_target"]
        and row["fit_feature_basis"] == row["deployment_feature_basis"]
        for row in result.regression_rows
    )
    assert sum(
        row["holdout_path_count"] for row in result.first_year_action_rows
    ) == actions.shape[0]


def test_deterministic_time_zero_action_is_fold_seed_invariant_and_not_r2_masked():
    paths_per_action = 64
    observed = np.repeat(
        np.arange(len(ACTION_CAPS), dtype=np.int64), paths_per_action
    )
    actions = observed[:, None]
    n_paths = observed.size
    raw_states = np.zeros((n_paths, 2, 4))
    raw_states[:, :, 1] = 0.025
    raw_states[:, :, 2] = 0.04
    raw_states[:, :, 3] = 1.0
    noise = 0.05 * np.sin(np.arange(n_paths, dtype=float) * 1.61803398875)
    fees = (1_000.0 * ACTION_CAPS[observed] + noise)[:, None]
    data = _portfolio_path_data(fees=fees, raw_states=raw_states)

    results = [
        _backward_induction(
            data,
            actions,
            folds=2,
            ridge=1.0e-6,
            seed=seed,
            inventory_nodes=3,
            inventory_quantile_clip=0.0,
        )
        for seed in (71, 999)
    ]

    assert [result.first_year_cap for result in results] == [
        ACTION_CAPS[-1], ACTION_CAPS[-1]
    ]
    masks = [
        [row["deployable_for_frozen_policy"] for row in result.regression_rows]
        for result in results
    ]
    assert masks[0] == masks[1] == [True] * len(ACTION_CAPS)
    assert all(
        "outer_oof_r_squared_below_threshold"
        not in row["action_fit_mask_reasons"]
        for result in results
        for row in result.regression_rows
    )


def test_year_specific_reachable_inventory_support_avoids_false_node_mask():
    data, actions = _synthetic_direct_q_data(paths_per_action=12)
    raw_states = data.raw_states.copy()
    within_action = np.tile(
        np.linspace(0.0, 1.0, 12), len(ACTION_CAPS)
    )
    raw_states[:, 0, 3] = 0.90 + 0.20 * within_action
    raw_states[:, 1, 3] = 0.04 + 0.04 * within_action
    raw_states[:, 2, 3] = 0.03 + 0.03 * within_action
    data = replace(data, raw_states=raw_states)

    chain = _fit_direct_q_chain(
        data=data,
        action_indices=actions,
        fit_mask=np.ones(actions.shape[0], dtype=bool),
        folds=2,
        ridge=1.0e-6,
        inventory_nodes=5,
        inventory_quantile_clip=0.0,
        minimum_training_count=SLIM_DIRECT_Q_BASIS_DIMENSION,
    )

    assert chain.grids[0][0] >= 0.90
    assert chain.grids[1][-1] <= 0.08
    assert chain.grids[1][-1] < chain.grids[0][0]
    assert np.all(chain.policies[1].action_deployable_mask)
    assert all(
        "clip" not in reason
        for reasons in chain.action_mask_reasons[1]
        for reason in reasons
    )


def test_lower_cap_argmax_identity_is_stable_under_numeric_ties():
    values = np.array([[1.0, 1.0 + 5.0e-11, 0.0], [0.0, 2.0, 2.0]])
    np.testing.assert_array_equal(_lower_cap_argmax(values, axis=1), [0, 1])


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


def test_validation_gate_accepts_significant_uplift_and_rejects_fallback_cases():
    assert _adaptive_policy_passes_validation(
        masked_candidate_executable=True,
        policyholder_validation_passed=True,
        causal_rollout_valid=True,
        csm_delta_aud=196.01,
        paired_standard_error_aud=100.0,
    )
    for override in (
        {"masked_candidate_executable": False},
        {"policyholder_validation_passed": False},
        {"causal_rollout_valid": False},
        {"csm_delta_aud": 196.0},
    ):
        arguments = {
            "masked_candidate_executable": True,
            "policyholder_validation_passed": True,
            "causal_rollout_valid": True,
            "csm_delta_aud": 196.01,
            "paired_standard_error_aud": 100.0,
        }
        arguments.update(override)
        assert not _adaptive_policy_passes_validation(**arguments)


def test_ratio_parser_uses_one_full_sample_and_one_model_point_default():
    args = parse_args(["--n-paths", "882", "--seed", "17"])

    assert args.optimisation_objective == "csm_to_mll"
    assert args.n_paths == 882
    assert args.seed == 17
    assert args.model_points.name == "model_points_policyholders_1_point_proxy.csv"
    for removed in (
        "benchmark_paths", "fixed_selection_seed", "validation_seed",
        "evaluation_seed", "ratio_bootstrap_replicates",
    ):
        assert not hasattr(args, removed)
    with pytest.raises(SystemExit):
        parse_args(["--fixed-selection-seed", "18"])


def test_time_zero_policy_class_grid_is_predeclared_and_additive():
    grid = _time_zero_policy_class_weights()

    assert len(grid) == 21
    assert len({name for name, _ in grid}) == 21
    assert grid[0][0] == "base_csm"
    np.testing.assert_array_equal(
        grid[0][1],
        np.array([1.0] * 5 + [-1.0] * 4 + [0.0] * 5),
    )
    longevity_half = dict(grid)[
        "base_stress_mix_alpha_0.50::longevity_stressed_csm"
    ]
    np.testing.assert_array_equal(
        longevity_half[:9],
        0.5 * np.array([1.0] * 5 + [-1.0] * 4),
    )
    assert longevity_half[10] == 0.5
    assert np.count_nonzero(longevity_half[9:]) == 1


def test_single_model_point_payload_is_recomputed_after_clipping():
    spec = ManagementObjectiveSpec(
        kind="csm_to_mll",
        model_point_count=1,
        capital_materiality=0.01,
        mass_lapse_fraction=0.40,
    )
    payload = np.array([
        100.0, 5.0, 0.0, 0.0, 0.0,
        20.0, 0.0, 0.0, 0.0,
        70.0, 75.0, 80.0, 78.0,
        999.0,
    ])
    with_objective = np.concatenate(([0.0], payload))
    lower = np.full(15, -200.0)
    upper = np.full(15, 200.0)

    bounded, _ = _clip_management_predictions(
        with_objective, lower, upper, spec
    )
    implied_csm = (
        np.sum(bounded[1:6]) - np.sum(bounded[6:10])
    )

    assert bounded[-1] == implied_csm
    score = score_lsmc_value_vectors(
        bounded[1:], capital_materiality=0.01
    )
    assert score.mass_lapse_loss == 0.40 * max(implied_csm, 0.0)


def test_full_sample_time_zero_chain_never_calls_outer_fold(monkeypatch):
    from portfolio_simulations import (
        optimize_crediting_rate_dynamic_behaviour_alt as optimizer,
    )

    data, actions = _synthetic_direct_q_data(paths_per_action=60)
    states = data.raw_states.copy()
    states[:, 0, :] = np.array([0.0, 0.025, 0.04, 1.0])
    data = replace(data, raw_states=states)
    base_csm = data.new_business_csm_proxy
    data = replace(data, model_point_csm=base_csm[None, ...])
    stressed = {
        stress_id: replace(
            data,
            fees_product=data.fees_product - shift,
            model_point_csm=None,
        )
        for stress_id, shift in zip(
            ("mortality", "longevity", "lapse_up", "lapse_down"),
            (0.2, 0.4, 0.3, 0.1),
        )
    }
    spec = ManagementObjectiveSpec(
        kind="csm_to_mll", model_point_count=1,
        capital_materiality=0.01, mass_lapse_fraction=0.40,
    )
    payload, exposure, active = _management_payload_and_activity_exposure(
        data, stressed, spec
    )
    monkeypatch.setattr(
        optimizer,
        "_evaluate_outer_fold_direct_q_chains",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("outer-fold code must not run")
        ),
    )

    estimate = _fit_time_zero_chain(
        data=data,
        actions=actions,
        immediate_payload=payload,
        activity_exposure=exposure,
        objective_spec=spec,
        ridge=1.0e-6,
        inventory_nodes=5,
        inventory_quantile_clip=0.0,
        linear_weights=None,
    )
    fixed_anchor = _fit_time_zero_chain(
        data=data,
        actions=actions,
        immediate_payload=payload,
        activity_exposure=exposure,
        objective_spec=spec,
        ridge=1.0e-6,
        inventory_nodes=5,
        inventory_quantile_clip=0.0,
        linear_weights=_time_zero_policy_class_weights()[0][1],
        forced_action=0,
    )

    assert active == (0, 1)
    assert payload.shape[-1] == 14
    assert estimate.first_year_action_payloads.shape == (len(ACTION_CAPS), 14)
    assert np.all(np.isfinite(estimate.first_year_action_scores))
    assert fixed_anchor.chosen_action == 0
    assert all(
        policy.action_deployable_mask.tolist()
        == [True] + [False] * (len(ACTION_CAPS) - 1)
        for policy in fixed_anchor.chain.policies.values()
    )


def test_optimizer_mll_score_matches_central_vector_arithmetic():
    payload = np.array([
        100.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
        80.0, 90.0, 95.0, 85.0,
        60.0, 40.0,
    ])
    spec = ManagementObjectiveSpec(
        kind="csm_to_mll",
        model_point_count=2,
        capital_materiality=0.01,
        mass_lapse_fraction=0.40,
    )

    csm, capital, ratio = _mll_metrics_from_payload(payload, spec)
    central = score_lsmc_value_vectors(
        payload,
        capital_materiality=0.01,
    )

    assert csm == central.csm
    assert capital == central.mll_capital
    assert ratio == central.csm_to_mll_ratio


def test_ratio_objective_can_prefer_lower_csm_with_better_risk_profile():
    spec = ManagementObjectiveSpec(
        kind="csm_to_mll",
        model_point_count=1,
        capital_materiality=0.01,
        mass_lapse_fraction=0.40,
    )
    high_csm_high_risk = np.array([
        120.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
        40.0, 50.0, 60.0, 60.0,
        120.0,
    ])
    lower_csm_low_risk = np.array([
        100.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
        90.0, 92.0, 94.0, 94.0,
        20.0,
    ])

    assert _objective_from_payload(lower_csm_low_risk, spec) > (
        _objective_from_payload(high_csm_high_risk, spec)
    )


def test_ratio_is_formed_after_value_vector_aggregation():
    spec = ManagementObjectiveSpec(
        kind="csm_to_mll",
        model_point_count=1,
        capital_materiality=0.01,
        mass_lapse_fraction=0.40,
    )
    paths = np.array([
        [100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
         70.0, 85.0, 90.0, 90.0, 100.0],
        [50.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
         45.0, 45.0, 45.0, 45.0, 5.0],
    ])

    ratio_of_mean_vector = float(_objective_from_payload(
        np.mean(paths, axis=0), spec
    ))
    mean_of_path_ratios = float(np.mean(
        _objective_from_payload(paths, spec)
    ))

    assert not np.isclose(ratio_of_mean_vector, mean_of_path_ratios)


def test_ratio_validation_gate_uses_bootstrap_interval_and_operational_flags():
    passing = PairedBootstrapRatioDelta(
        estimate=0.20,
        standard_error=0.05,
        ci_lower=0.01,
        ci_upper=0.31,
        confidence_level=0.95,
        n_resamples=100,
        seed=7,
    )
    failing = replace(passing, ci_lower=-0.01)

    assert _adaptive_policy_passes_ratio_validation(
        masked_candidate_executable=True,
        policyholder_validation_passed=True,
        causal_rollout_valid=True,
        bootstrap=passing,
    )
    assert not _adaptive_policy_passes_ratio_validation(
        masked_candidate_executable=True,
        policyholder_validation_passed=True,
        causal_rollout_valid=True,
        bootstrap=failing,
    )
    assert not _adaptive_policy_passes_ratio_validation(
        masked_candidate_executable=False,
        policyholder_validation_passed=True,
        causal_rollout_valid=True,
        bootstrap=passing,
    )


def test_fixed_grid_selection_uses_ratio_instead_of_higher_csm():
    labels = ("fixed_cap_low", "fixed_cap_high")
    csm_paths = {
        "fixed_cap_low": np.array([90.0, 90.0]),
        "fixed_cap_high": np.array([120.0, 120.0]),
    }
    ratios = {"fixed_cap_low": 2.1, "fixed_cap_high": 1.7}

    assert _select_best_fixed_label(
        labels,
        selection_csm_paths=csm_paths,
        selection_csm_to_mll=ratios,
        objective_kind="csm_to_mll",
    ) == "fixed_cap_low"
    assert _select_best_fixed_label(
        labels,
        selection_csm_paths=csm_paths,
        selection_csm_to_mll=None,
        objective_kind="csm",
    ) == "fixed_cap_high"


def test_ratio_policy_json_serializes_payload_coefficients_and_bounds_only():
    raw = np.zeros((8, len(CONTROL_STATE_FEATURE_NAMES)))
    base = _constant_first_year_policy(
        year=0,
        raw_state=raw,
        action_values=np.zeros((len(ACTION_CAPS), 10)),
        action_standard_errors=np.zeros(len(ACTION_CAPS)),
        feature_names=CONTROL_STATE_FEATURE_NAMES,
    )
    spec = ManagementObjectiveSpec(
        kind="csm_to_mll",
        model_point_count=1,
        capital_materiality=0.01,
        mass_lapse_fraction=0.40,
    )
    output_count = spec.payload_width + 1
    coefficients = np.zeros((*base.coefficients.shape[:2], output_count))
    lower = np.full((len(ACTION_CAPS), output_count), -10.0)
    upper = np.full((len(ACTION_CAPS), output_count), 10.0)
    policy = replace(
        base,
        coefficients=coefficients,
        value_lower_bounds=lower,
        value_upper_bounds=upper,
        objective_spec=spec,
    )
    result = BackwardResult(
        first_year_cap=float(ACTION_CAPS[0]),
        pv_new_business_csm_proxy=1.0,
        pv_guarantee_claims=0.0,
        pv_other_insurer_funded_benefits=0.0,
        pv_fees_product=1.0,
        pv_fees_lip=0.0,
        pv_crediting_margin=0.0,
        pv_mva_retained=0.0,
        pv_aps_retained=0.0,
        pv_expenses=0.0,
        pv_hedge_costs=0.0,
        standard_error_new_business_csm_proxy=0.0,
        first_year_action_rows=[],
        policy_year_rows=[],
        regression_rows=[],
        policy_years=[policy],
        reconciliation_gap=0.0,
        economically_active_policy_years=(1,),
        inactive_market_tail_year_count=0,
        management_objective="csm_to_mll",
        management_objective_value=2.0,
        mll_capital_proxy=0.5,
        csm_to_mll_ratio=2.0,
    )
    bootstrap = PairedBootstrapRatioDelta(
        estimate=0.1,
        standard_error=0.02,
        ci_lower=0.01,
        ci_upper=0.2,
        confidence_level=0.95,
        n_resamples=100,
        seed=5,
    )

    payload = _policy_payload(
        result,
        CONTROL_STATE_FEATURE_NAMES,
        {},
        fixed_fallback_cap=float(ACTION_CAPS[0]),
        deployed_first_year_cap=float(ACTION_CAPS[0]),
        adaptive_policy_selected=True,
        validation_delta_aud=1.0,
        validation_paired_standard_error_aud=0.2,
        validation_ratio_bootstrap=bootstrap,
        model_point_ids=("mp-1",),
    )
    year = payload["years"][0]

    assert len(payload["coefficient_output_layout"]) == spec.payload_width
    assert np.asarray(year["coefficients_by_action_basis_output"]).shape[-1] == (
        spec.payload_width
    )
    assert np.asarray(year["value_lower_bounds_by_action_output"]).shape[-1] == (
        spec.payload_width
    )
    assert year["management_objective_recomputed_from_payload"]
