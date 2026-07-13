"""Contract tests for the unified optimal Income-action policy hook.

The tests deliberately exercise the production monthly projector.  The hook
must remain an optional research control: a CONTINUE-only policy is identical
to the no-voluntary-action baseline, while Partial and Full Withdrawals use the
same contractual MVA, residual-Account-Value and Locked-Income mechanics as the
rest of the engine.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace

import numpy as np
import pytest

from agile_engine import (
    ESGConfig,
    HullWhiteParams,
    IncomeActionDecision,
    IncomeActionDecisionContext,
    IncomeTransitionPanelCollector,
    IncomeActionType,
    IndexLinkedLifetimeIncomeProduct,
    MVASpec,
    Measure,
    MortalityTable,
    PolicySpec,
    ProjectionConfig,
    Sex,
    YieldCurve,
    advance_income_month,
    apply_income_action,
    project,
    simulate,
)
from agile_engine.optimal_behaviour_lsmc import (
    FEATURE_NAMES,
    OptimalBehaviourLSMCSettings,
    fit_surrender_continuation_regression,
    no_voluntary_action_behaviour,
)
from agile_engine.product import Phase


class _ContinueIncomePolicy:
    """Capture every safe context and choose no voluntary Income action."""

    def __init__(self) -> None:
        self.contexts: dict[int, IncomeActionDecisionContext] = {}

    def choose_income_action(
        self, *, context: IncomeActionDecisionContext,
    ) -> IncomeActionDecision:
        assert type(context) is IncomeActionDecisionContext
        self.contexts[context.step] = context
        return IncomeActionDecision(
            action_type=np.full(
                context.n_paths, IncomeActionType.CONTINUE.value, dtype=object,
            ),
            partial_fraction_of_max=np.zeros(context.n_paths),
        )


class _GrossPartialAtStep(_ContinueIncomePolicy):
    """Request one common gross Partial Withdrawal on eligible paths."""

    def __init__(self, step: int, gross_amount: float) -> None:
        super().__init__()
        self.target_step = int(step)
        self.gross_amount = float(gross_amount)

    def choose_income_action(
        self, *, context: IncomeActionDecisionContext,
    ) -> IncomeActionDecision:
        self.contexts[context.step] = context
        action = np.full(
            context.n_paths, IncomeActionType.CONTINUE.value, dtype=object,
        )
        fraction = np.zeros(context.n_paths)
        selected = (
            (context.step == self.target_step)
            & context.partial_withdrawal_eligible
            & (context.max_partial_gross_amount >= self.gross_amount)
        )
        action[selected] = IncomeActionType.PARTIAL_WITHDRAWAL.value
        fraction[selected] = np.divide(
            self.gross_amount,
            context.max_partial_gross_amount[selected],
        )
        return IncomeActionDecision(action, fraction)


class _MaximumPartialAtStep(_ContinueIncomePolicy):
    """Deduct the maximum gross amount while preserving AUD 2,000."""

    def __init__(self, step: int) -> None:
        super().__init__()
        self.target_step = int(step)

    def choose_income_action(
        self, *, context: IncomeActionDecisionContext,
    ) -> IncomeActionDecision:
        self.contexts[context.step] = context
        selected = (
            (context.step == self.target_step)
            & context.partial_withdrawal_eligible
        )
        action = np.full(
            context.n_paths, IncomeActionType.CONTINUE.value, dtype=object,
        )
        action[selected] = IncomeActionType.PARTIAL_WITHDRAWAL.value
        return IncomeActionDecision(action, selected.astype(float))


class _FractionPartialAtStep(_ContinueIncomePolicy):
    """Withdraw one fixed fraction of the maximum at one monthly boundary."""

    def __init__(self, step: int, fraction: float) -> None:
        super().__init__()
        self.target_step = int(step)
        self.fraction = float(fraction)

    def choose_income_action(
        self, *, context: IncomeActionDecisionContext,
    ) -> IncomeActionDecision:
        self.contexts[context.step] = context
        selected = (
            (context.step == self.target_step)
            & context.partial_withdrawal_eligible
        )
        action = np.full(
            context.n_paths, IncomeActionType.CONTINUE.value, dtype=object,
        )
        fraction = np.zeros(context.n_paths)
        action[selected] = IncomeActionType.PARTIAL_WITHDRAWAL.value
        fraction[selected] = self.fraction
        return IncomeActionDecision(action, fraction)


class _FullWhenEligible(_ContinueIncomePolicy):
    """Choose Full Withdrawal only where the projector advertises it."""

    def choose_income_action(
        self, *, context: IncomeActionDecisionContext,
    ) -> IncomeActionDecision:
        self.contexts[context.step] = context
        action = np.full(
            context.n_paths, IncomeActionType.CONTINUE.value, dtype=object,
        )
        action[context.full_withdrawal_eligible] = (
            IncomeActionType.FULL_WITHDRAWAL.value
        )
        return IncomeActionDecision(action, np.zeros(context.n_paths))


class _BadPathCountPolicy:
    def choose_income_action(
        self, *, context: IncomeActionDecisionContext,
    ) -> IncomeActionDecision:
        return IncomeActionDecision(["continue"], np.zeros(1))


class _FullAtStep(_ContinueIncomePolicy):
    def __init__(self, step: int) -> None:
        super().__init__()
        self.target_step = int(step)

    def choose_income_action(
        self, *, context: IncomeActionDecisionContext,
    ) -> IncomeActionDecision:
        self.contexts[context.step] = context
        action = np.full(
            context.n_paths, IncomeActionType.CONTINUE.value, dtype=object,
        )
        if context.step == self.target_step:
            action[:] = IncomeActionType.FULL_WITHDRAWAL.value
        return IncomeActionDecision(action, np.zeros(context.n_paths))


def _inputs(
    *,
    horizon: float = 3.0,
    n_paths: int = 4,
    income_start_year: float = 1.0,
    product: IndexLinkedLifetimeIncomeProduct | None = None,
) -> dict[str, object]:
    # Deterministic rates make the explicitly loaded MVA exactly observable;
    # equity paths remain stochastic and therefore exercise the pathwise API.
    esg = ESGConfig(
        curve=YieldCurve.flat(0.04),
        hull_white=HullWhiteParams(sigma_r=0.0),
    )
    scenarios = simulate(
        "black_scholes",
        esg,
        horizon,
        n_paths,
        measure=Measure.RISK_NEUTRAL,
        seed=811,
    )
    return {
        "product": product or IndexLinkedLifetimeIncomeProduct(),
        "policy": PolicySpec(age=65.0, income_start_year=income_start_year),
        "scenarios": scenarios,
        "behaviour": no_voluntary_action_behaviour(),
        # Remove mortality weights so the action cashflow identities can be
        # checked in gross AUD path by path.
        "mortality": MortalityTable.gompertz_makeham().stressed(0.0),
        "config": ProjectionConfig(
            record_paths=True,
            max_age=65.0 + horizon,
        ),
    }


def _assert_same_optional_array(left: object, right: object) -> None:
    if left is None or right is None:
        assert left is right
    else:
        np.testing.assert_array_equal(left, right)


def test_income_action_decision_is_strictly_exclusive_and_read_only():
    supplied_action = np.asarray([
        IncomeActionType.CONTINUE,
        IncomeActionType.PARTIAL_WITHDRAWAL,
        IncomeActionType.FULL_WITHDRAWAL,
    ], dtype=object)
    supplied_fraction = np.asarray([0.0, 0.25, 0.0])
    decision = IncomeActionDecision(supplied_action, supplied_fraction)

    assert decision.n_paths == 3
    assert not decision.action_type.flags.writeable
    assert not decision.partial_fraction_of_max.flags.writeable
    supplied_action[:] = IncomeActionType.FULL_WITHDRAWAL
    supplied_fraction[:] = 1.0
    np.testing.assert_array_equal(
        decision.action_type,
        np.asarray(["continue", "partial_withdrawal", "full_withdrawal"]),
    )
    np.testing.assert_array_equal(
        decision.partial_fraction_of_max, np.asarray([0.0, 0.25, 0.0]),
    )
    with pytest.raises(FrozenInstanceError):
        decision.partial_fraction_of_max = np.zeros(3)
    with pytest.raises(ValueError):
        decision.action_type[0] = "full_withdrawal"

    with pytest.raises(ValueError, match="share one scenario-path shape"):
        IncomeActionDecision(["continue", "continue"], np.zeros(1))
    with pytest.raises(ValueError, match="unknown action"):
        IncomeActionDecision(["not_an_action"], np.zeros(1))
    with pytest.raises(ValueError, match="strictly positive"):
        IncomeActionDecision(["partial_withdrawal"], np.zeros(1))
    with pytest.raises(ValueError, match="require a zero partial fraction"):
        IncomeActionDecision(["full_withdrawal"], np.ones(1))


def test_income_action_context_is_shape_strict_read_only_and_adapted():
    hook = _ContinueIncomePolicy()
    project(**_inputs(horizon=2.0), income_action_policy=hook)
    context = hook.contexts[13]

    assert context.n_paths == 4
    assert context.duration_years > 1.0
    assert not hasattr(context, "scenarios")
    assert not hasattr(context, "future_discount")
    assert not hasattr(context, "future_cashflows")
    assert not hasattr(context, "hedge_pnl")
    assert not hasattr(context, "backing_assets")
    for item in fields(IncomeActionDecisionContext):
        value = getattr(context, item.name)
        if isinstance(value, np.ndarray):
            assert value.shape == (context.n_paths,)
            assert not value.flags.writeable
    with pytest.raises(FrozenInstanceError):
        context.duration_years = 2.0
    with pytest.raises(ValueError):
        context.account_value[0] = 1.0
    with pytest.raises(ValueError, match="share one path shape"):
        replace(context, short_rate=np.zeros(context.n_paths + 1))

    with pytest.raises(ValueError, match="one action per scenario path"):
        project(
            **_inputs(horizon=2.0),
            income_action_policy=_BadPathCountPolicy(),
        )


def test_continue_hook_is_identical_to_no_voluntary_action_baseline():
    inputs = _inputs(horizon=3.0)
    baseline = project(**inputs)
    continued = project(**inputs, income_action_policy=_ContinueIncomePolicy())

    assert baseline.cashflows.keys() == continued.cashflows.keys()
    for key in baseline.cashflows:
        np.testing.assert_array_equal(
            baseline.cashflows[key], continued.cashflows[key]
        )
    for name in (
        "inforce",
        "lapse_events",
        "iv_paths",
        "income_paths",
        "phase_paths",
        "ordinary_lapse_events",
        "performance_lapse_events",
        "ordinary_lapse_probabilities",
        "performance_lapse_probabilities",
        "total_lapse_probabilities",
        "income_election_events",
    ):
        _assert_same_optional_array(
            getattr(baseline, name), getattr(continued, name)
        )


def test_partial_minimum_and_mva_are_applied_to_gross_amount():
    product = IndexLinkedLifetimeIncomeProduct(
        mva=MVASpec(cost_loading=0.10),
    )
    inputs = _inputs(horizon=2.0, product=product)
    below_minimum_hook = _GrossPartialAtStep(step=13, gross_amount=99.0)
    below_minimum = project(
        **inputs, income_action_policy=below_minimum_hook
    )
    exact_minimum_hook = _GrossPartialAtStep(step=13, gross_amount=100.0)
    exact_minimum = project(
        **inputs, income_action_policy=exact_minimum_hook
    )

    assert np.all(below_minimum_hook.contexts[13].partial_withdrawal_eligible)
    assert np.all(below_minimum.cashflows["partial_withdrawals"][:, 13] == 0.0)
    assert np.all(below_minimum.cashflows["mva_retained"][:, 13] == 0.0)

    context = exact_minimum_hook.contexts[13]
    np.testing.assert_allclose(context.mva_factor, 0.10, atol=1.0e-12)
    np.testing.assert_allclose(
        exact_minimum.cashflows["partial_withdrawals"][:, 13],
        90.0,
        atol=1.0e-10,
    )
    np.testing.assert_allclose(
        exact_minimum.cashflows["mva_retained"][:, 13],
        10.0,
        atol=1.0e-10,
    )
    np.testing.assert_allclose(
        exact_minimum.cashflows["partial_withdrawals"][:, 13]
        + exact_minimum.cashflows["mva_retained"][:, 13],
        100.0,
        atol=1.0e-10,
    )


def test_maximum_partial_preserves_aud_2000_and_reduces_locked_income():
    product = IndexLinkedLifetimeIncomeProduct(
        mva=MVASpec(cost_loading=0.10),
    )
    hook = _MaximumPartialAtStep(step=13)
    result = project(
        **_inputs(horizon=2.0, product=product),
        income_action_policy=hook,
    )
    context = hook.contexts[13]
    gross = context.max_partial_gross_amount
    expected_income = context.locked_annual_income * (
        1.0 - gross / context.account_value
    )

    assert np.all(gross >= product.withdrawals.min_withdrawal)
    np.testing.assert_allclose(
        result.account_value_paths[:, 13],
        product.withdrawals.min_residual_value,
        atol=1.0e-8,
    )
    np.testing.assert_allclose(
        result.income_paths[:, 13], expected_income, rtol=1.0e-12, atol=1.0e-8,
    )
    np.testing.assert_allclose(
        result.cashflows["partial_withdrawals"][:, 13]
        + result.cashflows["mva_retained"][:, 13],
        gross,
        rtol=1.0e-12,
        atol=1.0e-8,
    )
    assert np.all(result.lapse_events[:, 13] == 0.0)


def test_mva_signal_ends_at_the_ten_year_contractual_boundary():
    product = IndexLinkedLifetimeIncomeProduct(
        mva=MVASpec(cost_loading=0.10),
    )
    hook = _ContinueIncomePolicy()
    project(
        **_inputs(horizon=10.25, n_paths=2, product=product),
        income_action_policy=hook,
    )

    np.testing.assert_allclose(hook.contexts[119].mva_factor, 0.10)
    np.testing.assert_allclose(hook.contexts[120].mva_factor, 0.0)


def test_partial_is_allowed_but_full_is_gated_in_election_month():
    partial_hook = _GrossPartialAtStep(step=12, gross_amount=100.0)
    partial = project(
        **_inputs(horizon=2.0), income_action_policy=partial_hook
    )
    election_context = partial_hook.contexts[12]

    assert np.all(election_context.just_elected)
    assert np.all(election_context.partial_withdrawal_eligible)
    assert not np.any(election_context.full_withdrawal_eligible)
    assert np.all(partial.lapse_events[:, 12] == 0.0)
    np.testing.assert_allclose(
        partial.cashflows["partial_withdrawals"][:, 12]
        + partial.cashflows["mva_retained"][:, 12],
        100.0,
        atol=1.0e-10,
    )

    full_hook = _FullWhenEligible()
    full = project(**_inputs(horizon=2.0), income_action_policy=full_hook)
    assert np.all(full_hook.contexts[12].just_elected)
    assert not np.any(full_hook.contexts[12].full_withdrawal_eligible)
    assert np.all(full.lapse_events[:, 12] == 0.0)
    assert np.all(full_hook.contexts[13].full_withdrawal_eligible)
    assert np.all(full.lapse_events[:, 13] > 0.0)
    assert np.all(full.cashflows["surrender_benefits"][:, 13] > 0.0)
    assert np.all(full.cashflows["partial_withdrawals"] == 0.0)

    with pytest.raises(ValueError, match="ineligible path"):
        project(
            **_inputs(horizon=2.0),
            income_action_policy=_FullAtStep(12),
        )


def test_income_action_hook_conflicts_with_legacy_surrender_hook():
    with pytest.raises(ValueError, match="mutually exclusive"):
        project(
            **_inputs(horizon=2.0),
            income_action_policy=_ContinueIncomePolicy(),
            surrender_policy=object(),
        )


def test_income_hook_is_not_called_in_growth_or_at_terminal():
    hook = _ContinueIncomePolicy()
    inputs = _inputs(horizon=2.0, income_start_year=2.0)
    result = project(**inputs, income_action_policy=hook)
    terminal_step = result.scenarios.n_steps

    assert terminal_step not in hook.contexts
    assert not any(
        np.all(context.phase != Phase.INCOME.value)
        for context in hook.contexts.values()
    )
    assert np.all(result.cashflows["partial_withdrawals"][:, :12] == 0.0)
    assert np.all(result.lapse_events[:, :12] == 0.0)


def test_truncated_svd_stabilises_an_exactly_collinear_public_regression():
    n_observations = 512
    driver = np.linspace(-1.0, 1.0, n_observations)
    features = np.column_stack([
        (index + 1.0) * driver for index in range(len(FEATURE_NAMES))
    ])
    target = 75_000.0 + 10_000.0 * driver
    settings = OptimalBehaviourLSMCSettings(
        ridge=0.0,
        relative_svd_cutoff=1.0e-8,
        maximum_condition_number=1.0e8,
    )

    regression = fit_surrender_continuation_regression(
        features,
        target,
        premium=100_000.0,
        settings=settings,
    )
    prediction = regression.predict_features(features)

    assert regression.effective_rank == 2  # intercept plus one SVD component
    assert regression.matrix_rank == regression.coefficients.size
    assert regression.condition_number <= settings.maximum_condition_number
    assert np.all(np.isfinite(regression.coefficients))
    np.testing.assert_allclose(prediction, target, rtol=0.0, atol=1.0e-7)


def _collected_continue_projection(
    inputs: dict[str, object],
) -> tuple[object, IncomeTransitionPanelCollector]:
    collector = IncomeTransitionPanelCollector()
    result = project(
        **inputs,
        income_action_policy=_ContinueIncomePolicy(),
        income_transition_observer=collector,
    )
    return result, collector


def test_transition_state_accepts_uncapped_crediting_sentinel():
    inputs = _inputs(horizon=2.0)
    _, collector = _collected_continue_projection(inputs)
    state = collector.states_by_step[13]
    scenario_slice = collector.slices_by_step[13]

    uncapped_state = replace(
        state, announced_cap=np.full(state.n_paths, np.inf)
    )
    uncapped_slice = replace(
        scenario_slice,
        next_announced_cap=np.full(scenario_slice.n_paths, np.inf),
    )

    assert np.all(np.isposinf(uncapped_state.announced_cap))
    assert np.all(np.isposinf(uncapped_slice.next_announced_cap))


@pytest.mark.parametrize("fraction", [0.25, 0.50, 0.75, 1.00])
def test_array_kernel_partial_fractions_match_full_monthly_projector(fraction):
    product = IndexLinkedLifetimeIncomeProduct(
        mva=MVASpec(cost_loading=0.10),
    )
    inputs = _inputs(horizon=2.0, product=product)
    _, collector = _collected_continue_projection(inputs)
    state = collector.states_by_step[13]
    scenario_slice = collector.slices_by_step[13]
    action = np.full(
        state.n_paths, IncomeActionType.PARTIAL_WITHDRAWAL.value, dtype=object,
    )
    decision = IncomeActionDecision(
        action, np.full(state.n_paths, fraction),
    )
    action_transition = apply_income_action(
        state, decision, product, scenario_slice
    )
    month_transition = advance_income_month(
        action_transition.post_action_state,
        product,
        inputs["policy"],
        scenario_slice,
    )

    projected = project(
        **inputs,
        income_action_policy=_FractionPartialAtStep(13, fraction),
    )
    idx = state.path_index
    np.testing.assert_allclose(
        projected.cashflows["partial_withdrawals"][idx, 13],
        action_transition.partial_withdrawal_cashflow,
        rtol=1.0e-12,
        atol=1.0e-9,
    )
    np.testing.assert_allclose(
        projected.cashflows["mva_retained"][idx, 13],
        action_transition.mva_retained_cashflow,
        rtol=1.0e-12,
        atol=1.0e-9,
    )
    np.testing.assert_allclose(
        projected.account_value_paths[idx, 14],
        month_transition.next_state.account_value,
        rtol=1.0e-12,
        atol=1.0e-8,
    )
    np.testing.assert_allclose(
        projected.income_paths[idx, 14],
        month_transition.next_state.locked_annual_income,
        rtol=1.0e-12,
        atol=1.0e-8,
    )
    np.testing.assert_allclose(
        projected.cashflows["income_paid"][idx, 14],
        month_transition.income_cashflow,
        rtol=1.0e-12,
        atol=1.0e-9,
    )


def test_array_kernel_full_matches_fee_mva_and_termination_in_projector():
    product = IndexLinkedLifetimeIncomeProduct(
        mva=MVASpec(cost_loading=0.10),
    )
    inputs = _inputs(horizon=2.0, product=product)
    _, collector = _collected_continue_projection(inputs)
    state = collector.states_by_step[13]
    scenario_slice = collector.slices_by_step[13]
    decision = IncomeActionDecision(
        np.full(
            state.n_paths, IncomeActionType.FULL_WITHDRAWAL.value, dtype=object,
        ),
        np.zeros(state.n_paths),
    )
    action_transition = apply_income_action(
        state, decision, product, scenario_slice
    )
    month_transition = advance_income_month(
        action_transition.post_action_state,
        product,
        inputs["policy"],
        scenario_slice,
    )
    projected = project(
        **inputs,
        income_action_policy=_FullAtStep(13),
    )
    idx = state.path_index

    np.testing.assert_allclose(
        projected.cashflows["surrender_benefits"][idx, 13],
        action_transition.surrender_benefit_cashflow,
        rtol=1.0e-12,
        atol=1.0e-8,
    )
    np.testing.assert_allclose(
        projected.cashflows["fees_product"][idx, 13],
        action_transition.fees_product_cashflow,
        rtol=1.0e-12,
        atol=1.0e-9,
    )
    np.testing.assert_allclose(
        projected.cashflows["fees_lip"][idx, 13],
        action_transition.fees_lip_cashflow,
        rtol=1.0e-12,
        atol=1.0e-9,
    )
    np.testing.assert_allclose(
        projected.cashflows["mva_retained"][idx, 13],
        action_transition.mva_retained_cashflow,
        rtol=1.0e-12,
        atol=1.0e-8,
    )
    assert np.all(projected.inforce[idx, 13] == 0.0)
    assert np.all(projected.account_value_paths[idx, 13] == 0.0)
    assert np.all(projected.income_paths[idx, 13] == 0.0)
    assert np.all(projected.phase_paths[idx, 13] == Phase.TERMINATED.value)
    assert np.all(month_transition.next_state.inforce_weight == 0.0)
    assert np.all(month_transition.mandatory_policyholder_cashflow == 0.0)


@pytest.mark.parametrize(
    ("horizon", "terminal_next"),
    [(3.0, False), (2.0, True)],
)
def test_array_kernel_continue_matches_anniversary_and_terminal_boundaries(
    horizon, terminal_next,
):
    inputs = _inputs(horizon=horizon)
    projected, collector = _collected_continue_projection(inputs)
    state = collector.states_by_step[23]
    scenario_slice = collector.slices_by_step[23]
    assert scenario_slice.is_anniversary
    assert scenario_slice.terminal_next is terminal_next
    decision = IncomeActionDecision(
        np.full(state.n_paths, IncomeActionType.CONTINUE.value, dtype=object),
        np.zeros(state.n_paths),
    )
    action_transition = apply_income_action(
        state, decision, inputs["product"], scenario_slice
    )
    month_transition = advance_income_month(
        action_transition.post_action_state,
        inputs["product"],
        inputs["policy"],
        scenario_slice,
    )
    idx = state.path_index
    np.testing.assert_allclose(
        projected.account_value_paths[idx, 24],
        month_transition.next_state.account_value,
        rtol=1.0e-12,
        atol=1.0e-8,
    )
    np.testing.assert_allclose(
        projected.cashflows["income_paid"][idx, 24],
        month_transition.income_cashflow,
        rtol=1.0e-12,
        atol=1.0e-9,
    )
    np.testing.assert_allclose(
        projected.cashflows["fees_product"][idx, 24],
        month_transition.fees_product_cashflow,
        rtol=1.0e-12,
        atol=1.0e-9,
    )
    np.testing.assert_allclose(
        projected.cashflows["fees_lip"][idx, 24],
        month_transition.fees_lip_cashflow,
        rtol=1.0e-12,
        atol=1.0e-9,
    )
    np.testing.assert_allclose(
        projected.cashflows["terminal_closeout"][idx, 24],
        month_transition.terminal_closeout_cashflow,
        rtol=1.0e-12,
        atol=1.0e-9,
    )
    assert not np.any(
        month_transition.next_context.partial_withdrawal_eligible
    ) if terminal_next else np.all(
        month_transition.next_context.phase == Phase.INCOME.value
    )


def test_transition_collector_and_kernel_preserve_joint_life_state():
    inputs = _inputs(horizon=2.0, n_paths=8)
    inputs["policy"] = PolicySpec(
        age=65.0,
        spouse=True,
        spouse_age=63.0,
        spouse_sex=Sex.FEMALE,
        income_start_year=1.0,
    )
    inputs["config"] = replace(
        inputs["config"], force_pathwise_joint_life=True
    )
    projected, collector = _collected_continue_projection(inputs)
    state = collector.states_by_step[13]
    scenario_slice = collector.slices_by_step[13]
    assert np.all(state.primary_alive)
    assert np.all(state.spouse_alive)
    assert np.all(state.joint_income_cover)
    decision = IncomeActionDecision(
        np.full(state.n_paths, IncomeActionType.CONTINUE.value, dtype=object),
        np.zeros(state.n_paths),
    )
    action_transition = apply_income_action(
        state, decision, inputs["product"], scenario_slice
    )
    month_transition = advance_income_month(
        action_transition.post_action_state,
        inputs["product"],
        inputs["policy"],
        scenario_slice,
    )
    idx = state.path_index
    np.testing.assert_array_equal(
        month_transition.next_state.primary_alive,
        scenario_slice.next_primary_alive,
    )
    np.testing.assert_array_equal(
        month_transition.next_state.spouse_alive,
        scenario_slice.next_spouse_alive,
    )
    np.testing.assert_allclose(
        projected.account_value_paths[idx, 14],
        month_transition.next_state.account_value,
        rtol=1.0e-12,
        atol=1.0e-8,
    )
