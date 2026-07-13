"""Active tests for the generic-product optimal-behaviour LSMC layer."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace

import numpy as np
import pytest

import agile_engine.optimal_behaviour_lsmc as optimal_behaviour_module
from agile_engine import (ESGConfig, IndexLinkedLifetimeIncomeProduct,
                          CreditingCapDecisionContext, MortalityTable,
                          PolicySpec, ProjectionConfig, ReferenceFundSpec,
                          SurrenderDecisionContext, YieldCurve,
                          ValuationSettings,
                          credited_return,
                          load_dynamic_behaviour_assumptions,
                          value_contract)
from agile_engine.esg import Measure, simulate
from agile_engine.optimal_behaviour_lsmc import (
    ELECTION_FEATURE_NAMES,
    FEATURE_NAMES,
    OptimalBehaviourLSMCSettings,
    build_income_election_regression_features,
    build_surrender_regression_features,
    build_surrender_regression_features_from_arrays,
    fit_optimal_behaviour_policy,
    fit_optimal_surrender_policy,
    fit_surrender_continuation_policy,
    no_voluntary_action_behaviour,
)
from agile_engine.product import Protection
from agile_engine.projection import project


class _NeverSurrender:
    def surrender_mask(self, *, account_value, **_kwargs):
        return np.zeros_like(account_value, dtype=bool)


class _TaggedNeverSurrender(_NeverSurrender):
    def __init__(self, tag: str) -> None:
        self.provenance_fingerprint = tag


class _BadShapePolicy:
    def surrender_mask(self, **_kwargs):
        return np.zeros(1, dtype=bool)


class _ContextCapturePolicy:
    anniversary_only = True

    def __init__(self, *, exercise=False):
        self.contexts = {}
        self.exercise = exercise

    def surrender_mask(self, *, context):
        assert isinstance(context, SurrenderDecisionContext)
        self.contexts[context.step] = context
        if self.exercise:
            return context.full_withdrawal_eligible.copy()
        return np.zeros(context.n_paths, dtype=bool)


class _CapContextCapture:
    def __init__(self):
        self.contexts = {}

    def observe_cap_decision(self, *, context):
        assert isinstance(context, CreditingCapDecisionContext)
        self.contexts[context.step] = context


class _AlwaysSurrenderContextPolicy:
    def __init__(self):
        self.contexts = {}

    def surrender_mask(self, *, context):
        self.contexts[context.step] = context
        return np.ones(context.n_paths, dtype=bool)


class _ZeroValueSurrenderContextPolicy:
    def __init__(self):
        self.contexts = {}
        self.attempts = {}

    def surrender_mask(self, *, context):
        self.contexts[context.step] = context
        attempt = (
            (context.surrender_value <= 1.0e-8)
            & (context.guarantee_pv > 1.0e-8)
        )
        self.attempts[context.step] = attempt
        return attempt


class _ScheduledReferenceFund(ReferenceFundSpec):
    def cap(self, policy_year):
        schedule = (0.01, 0.02, 0.15, 0.07)
        return schedule[min(int(policy_year), len(schedule) - 1)]


class _ChangedNewAndFutureCapsReferenceFund(ReferenceFundSpec):
    def cap(self, policy_year):
        schedule = (0.01, 0.15, 0.18, 0.20)
        return schedule[min(int(policy_year), len(schedule) - 1)]


class _FastIncomeRates:
    def lifetime_income_rate(self, *_args, **_kwargs):
        return 2.0


def _setup(n_paths=96, seed=11, horizon=8.0):
    curve = YieldCurve.flat(0.04)
    esg = ESGConfig(curve=curve)
    scenarios = simulate(
        "black_scholes", esg, horizon, n_paths,
        measure=Measure.RISK_NEUTRAL, seed=seed,
    )
    return esg, scenarios


def _synthetic_surrender_context(
    n_paths=128,
    *,
    step=24,
    seed=987,
):
    rng = np.random.default_rng(seed)
    surrender_value = rng.uniform(45_000.0, 105_000.0, n_paths)
    guarantee_pv = rng.uniform(70_000.0, 180_000.0, n_paths)
    guarantee_moneyness = guarantee_pv / surrender_value
    announced_cap = rng.choice(
        np.asarray([0.0025, 0.01, 0.03, 0.08, 0.15, 0.20]),
        size=n_paths,
    )
    reference_return = rng.normal(0.04, 0.12, n_paths)
    credited_return = np.minimum(np.maximum(reference_return, 0.0), announced_cap)
    performance_gap = np.maximum(
        np.log1p(np.maximum(reference_return, -0.95))
        - np.log1p(credited_return),
        0.0,
    )
    short_rate = rng.normal(0.04, 0.01, n_paths)
    return SurrenderDecisionContext(
        step=step,
        time=step / 12.0,
        is_anniversary=True,
        policy_year=step // 12,
        duration_years=step / 12.0,
        phase=np.full(n_paths, 1, dtype=np.int8),
        account_value=rng.uniform(50_000.0, 125_000.0, n_paths),
        surrender_value=surrender_value,
        locked_annual_income=rng.uniform(3_000.0, 9_000.0, n_paths),
        guarantee_pv=guarantee_pv,
        guarantee_moneyness=guarantee_moneyness,
        guarantee_log_moneyness=np.log(guarantee_moneyness),
        short_rate=short_rate,
        zero_rate_5y=short_rate + rng.normal(0.005, 0.004, n_paths),
        heston_variance=rng.uniform(0.015, 0.09, n_paths),
        announced_cap=announced_cap,
        previous_reference_return=reference_return,
        previous_credited_return=credited_return,
        performance_gap=performance_gap,
        inforce_weight=rng.uniform(0.65, 1.0, n_paths),
        just_elected=np.zeros(n_paths, dtype=bool),
        full_withdrawal_eligible=np.ones(n_paths, dtype=bool),
    )


def test_never_surrender_hook_is_cashflow_identical_to_no_hook():
    _, scenarios = _setup()
    product = IndexLinkedLifetimeIncomeProduct()
    policy = PolicySpec(age=65, income_start_year=2)
    mortality = MortalityTable.gompertz_makeham()
    behaviour = no_voluntary_action_behaviour()
    config = ProjectionConfig(record_paths=False, max_age=73.0)

    plain = project(product, policy, scenarios, behaviour, mortality,
                    config=config)
    hooked = project(product, policy, scenarios, behaviour, mortality,
                     config=config, surrender_policy=_NeverSurrender())

    assert plain.cashflows.keys() == hooked.cashflows.keys()
    for key in plain.cashflows:
        np.testing.assert_array_equal(plain.cashflows[key], hooked.cashflows[key])
    np.testing.assert_array_equal(plain.inforce, hooked.inforce)


def test_external_decision_policy_changes_valuation_provenance():
    esg, scenarios = _setup(n_paths=16, seed=27, horizon=2.0)
    product = IndexLinkedLifetimeIncomeProduct()
    policy = PolicySpec(age=65, income_start_year=1)
    settings = ValuationSettings(
        model="black_scholes",
        n_paths=16,
        seed=27,
        horizon_years=2.0,
        projection=ProjectionConfig(record_paths=False, max_age=67.0),
    )
    first = value_contract(
        product,
        policy,
        esg,
        MortalityTable.gompertz_makeham(),
        no_voluntary_action_behaviour(),
        settings=settings,
        scenarios=scenarios,
        surrender_policy=_TaggedNeverSurrender("fit-A"),
    )
    second = value_contract(
        product,
        policy,
        esg,
        MortalityTable.gompertz_makeham(),
        no_voluntary_action_behaviour(),
        settings=settings,
        scenarios=scenarios,
        surrender_policy=_TaggedNeverSurrender("fit-B"),
    )

    assert first.provenance != second.provenance
    assert first.pv == second.pv


def test_never_surrender_hook_fully_replaces_dynamic_statistical_lapses():
    _, scenarios = _setup(n_paths=16, seed=19, horizon=4.0)
    product = IndexLinkedLifetimeIncomeProduct()
    policy = PolicySpec(age=65, income_start_year=1)
    mortality = MortalityTable.gompertz_makeham()
    dynamic_behaviour = load_dynamic_behaviour_assumptions().behaviour
    config = ProjectionConfig(record_paths=False, max_age=69.0)

    statistical = project(
        product,
        policy,
        scenarios,
        dynamic_behaviour,
        mortality,
        config=config,
    )
    externally_controlled = project(
        product,
        policy,
        scenarios,
        dynamic_behaviour,
        mortality,
        config=config,
        surrender_policy=_NeverSurrender(),
    )

    assert np.any(statistical.lapse_events > 0.0)
    assert np.all(externally_controlled.lapse_events == 0.0)
    assert np.all(externally_controlled.ordinary_lapse_events == 0.0)
    assert np.all(externally_controlled.performance_lapse_events == 0.0)
    assert np.all(
        externally_controlled.cashflows["surrender_benefits"] == 0.0
    )


def test_surrender_hook_requires_one_decision_per_path():
    _, scenarios = _setup(n_paths=48)
    with pytest.raises(ValueError, match="one boolean per scenario path"):
        project(
            IndexLinkedLifetimeIncomeProduct(),
            PolicySpec(age=65, income_start_year=2),
            scenarios,
            no_voluntary_action_behaviour(),
            MortalityTable.gompertz_makeham(),
            config=ProjectionConfig(record_paths=False, max_age=73.0),
            surrender_policy=_BadShapePolicy(),
        )


def test_lsmc_fit_is_finite_out_of_sample_and_respects_growth_gate():
    esg, training = _setup(n_paths=96, seed=101)
    _, evaluation = _setup(n_paths=96, seed=202)
    product = IndexLinkedLifetimeIncomeProduct()
    policy = PolicySpec(age=65, income_start_year=2)
    mortality = MortalityTable.gompertz_makeham()
    config = ProjectionConfig(record_paths=True, max_age=73.0)
    fit = fit_optimal_surrender_policy(
        product,
        policy,
        training,
        mortality,
        projection_config=config,
        settings=OptimalBehaviourLSMCSettings(n_folds=3, fold_seed=7),
    )

    assert fit.training_scenario_fingerprint == training.content_fingerprint
    assert fit.training_path_count == 96
    assert (
        fit.training_policyholder_value_aud
        >= fit.training_no_action_policyholder_value_aud
    )
    assert fit.training_fallback_used == (
        fit.training_candidate_policyholder_value_aud
        < fit.training_no_action_policyholder_value_aud
    )
    if fit.training_fallback_used:
        assert not fit.policy.regressions
    assert fit.diagnostics
    for diagnostic in fit.diagnostics:
        if diagnostic.regression_accepted_for_exercise:
            assert diagnostic.oof_rmse_aud is not None
            assert diagnostic.condition_number is not None
            assert np.isfinite(diagnostic.oof_rmse_aud)
            assert np.isfinite(diagnostic.condition_number)
            assert diagnostic.matrix_rank == diagnostic.feature_count
            assert (
                diagnostic.condition_number
                <= fit.policy.settings.maximum_condition_number
            )
            assert diagnostic.fallback_reason is None
        else:
            assert diagnostic.fallback_reason

    rollout = project(
        product,
        policy,
        evaluation,
        no_voluntary_action_behaviour(),
        mortality,
        config=config,
        surrender_policy=fit.policy,
    )
    assert evaluation.content_fingerprint != training.content_fingerprint
    assert np.isfinite(list(rollout.pv_by_component().values())).all()
    # Election is at month 24 and the product forbids every Growth surrender.
    assert np.all(rollout.cashflows["surrender_benefits"][:, :24] == 0.0)
    assert np.all(rollout.cashflows["partial_withdrawals"] == 0.0)
    for step, stats in fit.policy.evaluation_statistics.items():
        assert step % 12 == 0
        assert step >= 36
        assert 0 <= stats["exercise_path_count"] <= stats["eligible_path_count"]


def test_legacy_lsmc_failed_cross_fits_fall_back_to_continue(monkeypatch):
    _, training = _setup(n_paths=96, seed=811, horizon=8.0)
    attempts = 0

    def fail_cross_fit(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise ValueError("Insufficient observations in an LSMC cross-fit fold.")

    monkeypatch.setattr(
        optimal_behaviour_module,
        "_cross_fitted_regression",
        fail_cross_fit,
    )
    fit = fit_optimal_surrender_policy(
        IndexLinkedLifetimeIncomeProduct(),
        PolicySpec(age=65, income_start_year=2),
        training,
        MortalityTable.gompertz_makeham(),
        projection_config=ProjectionConfig(record_paths=True, max_age=73.0),
        settings=OptimalBehaviourLSMCSettings(n_folds=3, fold_seed=7),
    )

    assert attempts > 0
    assert not fit.policy.regressions
    assert not fit.cross_fitted_training_policy.regressions_by_step
    assert fit.diagnostics
    assert all(
        not diagnostic.regression_accepted_for_exercise
        for diagnostic in fit.diagnostics
    )
    assert all(
        diagnostic.fallback_reason is not None
        and diagnostic.fallback_reason.startswith("cross_fit_failed:")
        for diagnostic in fit.diagnostics
    )
    assert np.isfinite(fit.training_candidate_policyholder_value_aud)
    assert fit.training_candidate_policyholder_value_aud == pytest.approx(
        fit.training_no_action_policyholder_value_aud,
        rel=2.0e-13,
        abs=1.0e-8,
    )


def test_combined_lsmc_fits_election_and_surrender_and_rolls_out_from_issue():
    _, training = _setup(n_paths=192, seed=1101, horizon=4.0)
    _, evaluation = _setup(n_paths=192, seed=2202, horizon=4.0)
    product = IndexLinkedLifetimeIncomeProduct(
        automatic_income_start_age=67.0
    )
    policy = PolicySpec(age=65, income_start_year=1)
    mortality = MortalityTable.gompertz_makeham()
    config = ProjectionConfig(
        record_paths=False,
        max_age=69.0,
        mortality_seed=3311,
    )
    fit = fit_optimal_behaviour_policy(
        product,
        policy,
        training,
        mortality,
        projection_config=config,
        settings=OptimalBehaviourLSMCSettings(
            n_folds=3,
            fold_seed=17,
        ),
        fit_basis_inputs={"crediting_cap_rate": 0.06, "stress": "base"},
    )

    assert fit.training_scenario_fingerprint == training.content_fingerprint
    assert fit.fit_basis_fingerprint != fit.training_scenario_fingerprint
    assert {diagnostic.action_type for diagnostic in fit.diagnostics} == {
        "income_election",
        "full_withdrawal",
    }
    assert all(
        diagnostic.phase in {"growth", "income"}
        for diagnostic in fit.diagnostics
    )
    assert all(
        diagnostic.folds_used in {0, 3}
        for diagnostic in fit.diagnostics
        if diagnostic.action_type == "income_election"
    )
    assert fit.policy.provenance_fingerprint
    assert fit.policy.surrender_policy.provenance_fingerprint

    rollout = project(
        product,
        policy,
        evaluation,
        no_voluntary_action_behaviour(),
        mortality,
        config=replace(config, mortality_seed=4422),
        income_election_policy=fit.policy,
        surrender_policy=fit.policy,
    )
    assert evaluation.content_fingerprint != training.content_fingerprint
    assert np.all(rollout.income_election_events[:, :12] == 0.0)
    assert np.all(
        np.sum(rollout.income_election_events[:, :37], axis=1) > 0.0
    )
    assert not np.any(
        (rollout.income_election_events > 0.0)
        & (rollout.lapse_events > 0.0)
    )
    assert np.isfinite(list(rollout.pv_by_component().values())).all()


def test_combined_fit_identity_changes_for_each_cap_and_stress_basis():
    _, training = _setup(n_paths=96, seed=5101, horizon=3.0)
    product = IndexLinkedLifetimeIncomeProduct(
        automatic_income_start_age=67.0
    )
    higher_cap_product = replace(
        product,
        reference_fund=replace(
            product.reference_fund,
            scenario_maximum_return=0.12,
        ),
    )
    policy = PolicySpec(age=65, income_start_year=1)
    mortality = MortalityTable.gompertz_makeham()
    config = ProjectionConfig(record_paths=False, max_age=68.0)
    settings = OptimalBehaviourLSMCSettings(n_folds=3, fold_seed=29)

    base = fit_optimal_behaviour_policy(
        product,
        policy,
        training,
        mortality,
        projection_config=config,
        settings=settings,
        fit_basis_inputs={"crediting_cap_rate": 0.06, "stress": "base"},
    )
    cap = fit_optimal_behaviour_policy(
        higher_cap_product,
        policy,
        training,
        mortality,
        projection_config=config,
        settings=settings,
        fit_basis_inputs={"crediting_cap_rate": 0.12, "stress": "base"},
    )
    stress = fit_optimal_behaviour_policy(
        product,
        policy,
        training,
        mortality,
        projection_config=config,
        settings=settings,
        fit_basis_inputs={"crediting_cap_rate": 0.06, "stress": "longevity"},
    )

    assert len({
        base.fit_basis_fingerprint,
        cap.fit_basis_fingerprint,
        stress.fit_basis_fingerprint,
    }) == 3


def test_income_election_features_use_only_the_decision_context():
    _, scenarios = _setup(n_paths=16, seed=3303, horizon=3.0)

    class _ElectionCapture:
        anniversary_only = True

        def __init__(self):
            self.context = None

        def start_income_mask(self, *, context):
            self.context = context
            return np.zeros(context.n_paths, dtype=bool)

    capture = _ElectionCapture()
    policy = PolicySpec(age=65, income_start_year=2)
    project(
        IndexLinkedLifetimeIncomeProduct(),
        policy,
        scenarios,
        no_voluntary_action_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(record_paths=False, max_age=68.0),
        income_election_policy=capture,
    )
    assert capture.context is not None
    features = build_income_election_regression_features(
        capture.context,
        policy.net_initial_investment,
        policy.age,
    )
    assert features.shape == (scenarios.n_paths, len(ELECTION_FEATURE_NAMES))
    assert np.isfinite(features).all()
    assert not hasattr(capture.context, "scenarios")
    assert not hasattr(capture.context, "future_discount")


def test_context_exposes_only_observable_read_only_state_and_rich_features():
    _, scenarios = _setup(n_paths=16, seed=303, horizon=4.0)
    product = IndexLinkedLifetimeIncomeProduct(
        reference_fund=_ScheduledReferenceFund())
    policy = PolicySpec(age=65, income_start_year=1)
    capture = _ContextCapturePolicy()
    project(
        product,
        policy,
        scenarios,
        no_voluntary_action_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(record_paths=False, max_age=69.0),
        surrender_policy=capture,
    )

    context = capture.contexts[24]
    assert context.step == 24
    assert context.policy_year == 2
    assert context.duration_years == pytest.approx(2.0)
    assert not hasattr(context, "scenarios")
    assert not hasattr(context, "discount")
    assert not hasattr(context, "future_returns")
    assert not hasattr(context, "hedge_costs")
    assert not context.account_value.flags.writeable
    assert not context.full_withdrawal_eligible.flags.writeable
    with pytest.raises(FrozenInstanceError):
        context.step = 1
    with pytest.raises(ValueError):
        context.account_value[0] = 0.0

    features = build_surrender_regression_features(
        context, policy.net_initial_investment)
    assert features.shape == (scenarios.n_paths, len(FEATURE_NAMES))
    assert np.isfinite(features).all()


def test_array_native_feature_builder_exactly_matches_context_builder():
    context = _synthetic_surrender_context()
    premium = 100_000.0

    from_context = build_surrender_regression_features(context, premium)
    from_arrays = build_surrender_regression_features_from_arrays(
        account_value=context.account_value,
        surrender_value=context.surrender_value,
        locked_annual_income=context.locked_annual_income,
        guarantee_pv=context.guarantee_pv,
        guarantee_log_moneyness=context.guarantee_log_moneyness,
        short_rate=context.short_rate,
        zero_rate_5y=context.zero_rate_5y,
        heston_variance=context.heston_variance,
        duration_years=context.duration_years,
        announced_cap=context.announced_cap,
        previous_reference_return=context.previous_reference_return,
        previous_credited_return=context.previous_credited_return,
        performance_gap=context.performance_gap,
        premium=premium,
    )

    np.testing.assert_array_equal(from_arrays, from_context)
    assert from_arrays.shape == (context.n_paths, len(FEATURE_NAMES))


def test_public_continuation_fitter_returns_context_policy_and_pathwise_oof_fit():
    context = _synthetic_surrender_context()
    premium = 100_000.0
    features = build_surrender_regression_features(context, premium)
    continuation = np.zeros(context.n_paths)
    # Two synthetic rows can represent replicas of one complete path; replicas
    # deliberately retain the same path ID and therefore the same OOF fold.
    complete_path_ids = np.repeat(
        np.arange(context.n_paths // 2, dtype=np.int64), 2
    )

    fit = fit_surrender_continuation_policy(
        {context.step: features},
        {context.step: continuation},
        premium=premium,
        settings=OptimalBehaviourLSMCSettings(
            n_folds=3,
            fold_seed=17,
            exercise_buffer_rmse_multiplier=0.0,
        ),
        fold_ids_by_step={context.step: complete_path_ids},
    )

    assert fit.fallback_steps == ()
    assert context.step in fit.policy.regressions
    assert context.step in fit.oof_continuation_by_step
    np.testing.assert_array_equal(
        fit.fold_ids_by_step[context.step], complete_path_ids
    )
    assert not fit.fold_ids_by_step[context.step].flags.writeable
    assert not fit.oof_continuation_by_step[context.step].flags.writeable
    np.testing.assert_allclose(
        fit.oof_continuation_by_step[context.step], 0.0, atol=1.0e-10
    )
    assert fit.diagnostics[0].regression_accepted_for_exercise
    # Zero continuation and a strictly positive exit value imply exercise on
    # every contractually eligible Income path.
    np.testing.assert_array_equal(
        fit.policy.surrender_mask(context=context),
        context.full_withdrawal_eligible,
    )


def test_public_continuation_fitter_falls_back_to_continue_when_too_small():
    context = _synthetic_surrender_context(n_paths=32)
    features = build_surrender_regression_features(context, 100_000.0)
    fit = fit_surrender_continuation_policy(
        {context.step: features},
        {context.step: np.zeros(context.n_paths)},
        premium=100_000.0,
        settings=OptimalBehaviourLSMCSettings(n_folds=3),
    )

    assert fit.fallback_steps == (context.step,)
    assert context.step not in fit.policy.regressions
    assert context.step not in fit.oof_continuation_by_step
    assert fit.diagnostics[0].fallback_reason.startswith(
        "too_few_observations"
    )
    assert not np.any(fit.policy.surrender_mask(context=context))


def test_public_continuation_fitter_handles_an_imbalanced_boundary_fold():
    context = _synthetic_surrender_context(n_paths=60)
    features = build_surrender_regression_features(context, 100_000.0)
    # Modulo two gives 31 rows in fold 0 and 29 in fold 1.  Although the
    # overall 60-row threshold is met, fold 0 leaves only 29 training rows for
    # 29 raw features plus the intercept.
    complete_path_ids = np.concatenate((
        np.arange(59, dtype=np.int64),
        np.array([60], dtype=np.int64),
    ))

    fit = fit_surrender_continuation_policy(
        {context.step: features},
        {context.step: np.zeros(context.n_paths)},
        premium=100_000.0,
        settings=OptimalBehaviourLSMCSettings(n_folds=2),
        fold_ids_by_step={context.step: complete_path_ids},
    )

    assert fit.fallback_steps == (context.step,)
    assert context.step not in fit.policy.regressions
    assert context.step not in fit.oof_continuation_by_step
    diagnostic = fit.diagnostics[0]
    assert diagnostic.observations == 60
    assert diagnostic.folds_used == 0
    assert diagnostic.fallback_reason is not None
    assert diagnostic.fallback_reason.startswith("cross_fit_failed:")
    assert "Insufficient observations" in diagnostic.fallback_reason
    assert not np.any(fit.policy.surrender_mask(context=context))


def test_public_continuation_fitter_falls_back_to_continue_when_unstable():
    context = _synthetic_surrender_context()
    features = build_surrender_regression_features(context, 100_000.0)
    fit = fit_surrender_continuation_policy(
        {context.step: features},
        {context.step: np.zeros(context.n_paths)},
        premium=100_000.0,
        settings=OptimalBehaviourLSMCSettings(
            ridge=1.0,
            n_folds=3,
            maximum_condition_number=1.000001,
        ),
    )

    assert fit.fallback_steps == (context.step,)
    assert context.step not in fit.policy.regressions
    assert fit.diagnostics[0].fallback_reason in {
        "condition_number_exceeds_limit",
        "unstable_cross_fit_fold",
    }
    assert not np.any(fit.policy.surrender_mask(context=context))


def test_anniversary_context_separates_old_crediting_cap_from_new_announced_cap():
    _, scenarios = _setup(n_paths=24, seed=404, horizon=4.0)
    product = IndexLinkedLifetimeIncomeProduct(
        reference_fund=_ScheduledReferenceFund())
    capture = _ContextCapturePolicy()
    project(
        product,
        PolicySpec(age=65, income_start_year=1),
        scenarios,
        no_voluntary_action_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(record_paths=False, max_age=69.0),
        surrender_policy=capture,
    )

    # At t=2 the year-1 cap (2%) has just credited the completed year, while
    # the year-2 cap (15%) is already announced before Full Withdrawal.
    context = capture.contexts[24]
    np.testing.assert_allclose(context.announced_cap, 0.15)
    expected_credit = credited_return(
        context.previous_reference_return,
        Protection.TOTAL,
        0.02,
    )
    np.testing.assert_allclose(context.previous_credited_return, expected_credit)
    expected_gap = np.maximum(
        np.log1p(context.previous_reference_return)
        - np.log1p(context.previous_credited_return),
        0.0,
    )
    np.testing.assert_allclose(context.performance_gap, expected_gap)
    assert not np.any(context.just_elected)


def test_cap_context_precedes_new_cap_and_ignores_future_caps_and_returns():
    _, scenarios = _setup(n_paths=12, seed=405, horizon=4.0)
    future_levels = {
        index: values.copy()
        for index, values in scenarios.index_levels.items()
    }
    future_multiplier = np.linspace(1.05, 1.80, scenarios.n_steps - 12)
    for values in future_levels.values():
        values[:, 13:] *= future_multiplier[None, :]
    changed_future = replace(
        scenarios,
        index_levels=future_levels,
        seed=scenarios.seed + 1,
    )
    policy = PolicySpec(age=65, income_start_year=1)
    mortality = MortalityTable.gompertz_makeham()
    config = ProjectionConfig(record_paths=False, max_age=69.0)
    base_cap_capture = _CapContextCapture()
    changed_cap_capture = _CapContextCapture()
    base_surrender_capture = _ContextCapturePolicy()
    changed_surrender_capture = _ContextCapturePolicy()

    project(
        IndexLinkedLifetimeIncomeProduct(
            reference_fund=_ScheduledReferenceFund()),
        policy,
        scenarios,
        no_voluntary_action_behaviour(),
        mortality,
        config=config,
        surrender_policy=base_surrender_capture,
        cap_decision_observer=base_cap_capture,
    )
    project(
        IndexLinkedLifetimeIncomeProduct(
            reference_fund=_ChangedNewAndFutureCapsReferenceFund()),
        policy,
        changed_future,
        no_voluntary_action_behaviour(),
        mortality,
        config=config,
        surrender_policy=changed_surrender_capture,
        cap_decision_observer=changed_cap_capture,
    )

    # At t=1 the completed crediting year used the common 1% old cap.  The
    # newly announced cap and every market return after t=1 are outside the
    # leader's information set at this decision timestamp.
    base_context = base_cap_capture.contexts[12]
    changed_context = changed_cap_capture.contexts[12]
    for context_field in fields(CreditingCapDecisionContext):
        left = getattr(base_context, context_field.name)
        right = getattr(changed_context, context_field.name)
        if isinstance(left, np.ndarray):
            np.testing.assert_array_equal(left, right)
        else:
            assert left == right
    np.testing.assert_allclose(base_context.previous_cap, 0.01)

    # The policyholder observes that new cap later at the same Anniversary,
    # after the pre-action leader context has been recorded.
    np.testing.assert_allclose(
        base_surrender_capture.contexts[12].announced_cap,
        0.02,
    )
    np.testing.assert_allclose(
        changed_surrender_capture.contexts[12].announced_cap,
        0.15,
    )
    assert not np.allclose(
        base_cap_capture.contexts[24].account_value,
        changed_cap_capture.contexts[24].account_value,
    )


def test_external_context_hook_cannot_surrender_in_growth_or_on_election_date():
    _, scenarios = _setup(n_paths=20, seed=505, horizon=4.0)
    hook = _AlwaysSurrenderContextPolicy()
    result = project(
        IndexLinkedLifetimeIncomeProduct(),
        PolicySpec(age=65, income_start_year=2),
        scenarios,
        no_voluntary_action_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(record_paths=False, max_age=69.0),
        surrender_policy=hook,
    )

    assert np.all(result.lapse_events[:, :25] == 0.0)
    assert np.all(hook.contexts[12].phase == 0)
    assert not np.any(hook.contexts[12].full_withdrawal_eligible)
    assert np.all(hook.contexts[24].just_elected)
    assert not np.any(hook.contexts[24].full_withdrawal_eligible)
    assert np.any(hook.contexts[25].full_withdrawal_eligible)
    assert np.any(result.lapse_events[:, 25] > 0.0)


def test_external_hook_cannot_exchange_positive_income_guarantee_for_zero_value():
    _, scenarios = _setup(n_paths=12, seed=606, horizon=3.0)
    hook = _ZeroValueSurrenderContextPolicy()
    result = project(
        IndexLinkedLifetimeIncomeProduct(income_rates=_FastIncomeRates()),
        PolicySpec(age=65, income_start_year=1),
        scenarios,
        no_voluntary_action_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(record_paths=False, max_age=68.0),
        surrender_policy=hook,
    )

    attempted = [
        (step, mask)
        for step, mask in hook.attempts.items()
        if np.any(mask)
    ]
    assert attempted
    for step, mask in attempted:
        context = hook.contexts[step]
        assert not np.any(context.full_withdrawal_eligible[mask])
        assert np.all(result.lapse_events[mask, step] == 0.0)
        assert np.all(result.cashflows["surrender_benefits"][mask, step] == 0.0)


def test_crediting_margin_toggle_does_not_change_context_or_best_response():
    _, scenarios = _setup(n_paths=20, seed=707, horizon=4.0)
    product = IndexLinkedLifetimeIncomeProduct()
    policy = PolicySpec(age=65, income_start_year=1)
    mortality = MortalityTable.gompertz_makeham()
    enabled_hook = _ContextCapturePolicy(exercise=True)
    disabled_hook = _ContextCapturePolicy(exercise=True)
    enabled = project(
        product,
        policy,
        scenarios,
        no_voluntary_action_behaviour(),
        mortality,
        config=ProjectionConfig(
            record_paths=False, max_age=69.0, crediting_margin_enabled=True),
        surrender_policy=enabled_hook,
    )
    disabled = project(
        product,
        policy,
        scenarios,
        no_voluntary_action_behaviour(),
        mortality,
        config=ProjectionConfig(
            record_paths=False, max_age=69.0, crediting_margin_enabled=False),
        surrender_policy=disabled_hook,
    )

    assert enabled_hook.contexts.keys() == disabled_hook.contexts.keys()
    for step in enabled_hook.contexts:
        left = build_surrender_regression_features(
            enabled_hook.contexts[step], policy.net_initial_investment)
        right = build_surrender_regression_features(
            disabled_hook.contexts[step], policy.net_initial_investment)
        np.testing.assert_array_equal(left, right)
    np.testing.assert_array_equal(enabled.lapse_events, disabled.lapse_events)
    for key in (
        "income_paid", "death_benefits", "surrender_benefits",
        "partial_withdrawals", "terminal_closeout",
    ):
        np.testing.assert_array_equal(enabled.cashflows[key], disabled.cashflows[key])
    assert np.any(enabled.cashflows["crediting_margin"] != 0.0)
    assert np.all(disabled.cashflows["crediting_margin"] == 0.0)


def test_lsmc_settings_reject_bad_controls():
    with pytest.raises(ValueError, match="at least two"):
        OptimalBehaviourLSMCSettings(n_folds=1)
    with pytest.raises(ValueError, match="finite and non-negative"):
        OptimalBehaviourLSMCSettings(ridge=-1.0)
