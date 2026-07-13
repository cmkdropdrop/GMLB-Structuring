"""Focused tests for the projector's Full-Withdrawal action boundary."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import numpy as np
import pytest

from agile_engine import (
    ESGConfig,
    ExpenseAssumptions,
    IndexLinkedLifetimeIncomeProduct,
    Measure,
    MortalityTable,
    PolicySpec,
    ProjectionConfig,
    SurrenderActionValueContext,
    SurrenderDecisionContext,
    YieldCurve,
    project,
    simulate,
)
from agile_engine.optimal_behaviour_lsmc import no_voluntary_action_behaviour
from agile_engine.projection import CASHFLOW_KEYS


class _ActionObserver:
    def __init__(self, *, anniversary_only: bool):
        self.anniversary_only = anniversary_only
        self.contexts: dict[int, SurrenderActionValueContext] = {}

    def observe_surrender_decision(
        self, *, context: SurrenderActionValueContext,
    ) -> None:
        assert isinstance(context, SurrenderActionValueContext)
        self.contexts[context.step] = context


class _TargetExercisePolicy:
    def __init__(self, target_step: int | None, *, anniversary_only: bool):
        self.target_step = target_step
        self.anniversary_only = anniversary_only
        self.contexts: dict[int, SurrenderDecisionContext] = {}

    def surrender_mask(
        self, *, context: SurrenderDecisionContext,
    ) -> np.ndarray:
        # The richer observer context must never leak into the PH policy.
        assert type(context) is SurrenderDecisionContext
        self.contexts[context.step] = context
        if context.step == self.target_step:
            return context.full_withdrawal_eligible.copy()
        return np.zeros(context.n_paths, dtype=bool)


def _inputs(*, horizon: float = 3.0, n_paths: int = 4):
    curve = YieldCurve.flat(0.04)
    scenarios = simulate(
        "black_scholes",
        ESGConfig(curve=curve),
        horizon,
        n_paths,
        measure=Measure.RISK_NEUTRAL,
        seed=421,
    )
    expenses = ExpenseAssumptions(
        acquisition_pct_of_premium=0.0,
        maintenance_per_policy=120.0,
        maintenance_pct_of_iv=0.012,
        expense_inflation=0.0,
        commission_pct_of_premium=0.0,
    )
    return dict(
        product=IndexLinkedLifetimeIncomeProduct(),
        policy=PolicySpec(age=65.0, income_start_year=1.0),
        scenarios=scenarios,
        behaviour=no_voluntary_action_behaviour(),
        mortality=MortalityTable.gompertz_makeham().stressed(0.0),
        expenses=expenses,
        config=ProjectionConfig(
            dva_enabled=True,
            crediting_margin_enabled=True,
            hedge_vol_spread=0.005,
            record_paths=True,
        ),
    )


def _assert_cashflow_sum(actual, left, right) -> None:
    for key in CASHFLOW_KEYS:
        np.testing.assert_allclose(
            actual[key], left[key] + right[key], rtol=0.0, atol=1.0e-10,
            err_msg=f"action-boundary cashflow {key!r} does not reconcile",
        )


def test_action_value_context_is_deeply_read_only_and_never_sent_to_policy():
    observer = _ActionObserver(anniversary_only=True)
    policy = _TargetExercisePolicy(None, anniversary_only=True)

    project(
        **_inputs(),
        surrender_policy=policy,
        surrender_decision_observer=observer,
    )
    action_context = observer.contexts[24]
    decision_context = policy.contexts[24]

    assert action_context.decision_context is decision_context
    assert {item.name for item in fields(SurrenderActionValueContext)} == {
        "decision_context",
        "post_cap_common_cashflows",
        "full_withdrawal_post_action_cashflows",
    }
    assert not hasattr(action_context, "scenarios")
    assert not hasattr(action_context, "discount")
    assert not hasattr(action_context, "future_cashflows")
    with pytest.raises(FrozenInstanceError):
        action_context.decision_context = decision_context
    with pytest.raises(TypeError):
        action_context.post_cap_common_cashflows["income_paid"] = np.zeros(4)
    with pytest.raises(ValueError):
        action_context.post_cap_common_cashflows["income_paid"][0] = 1.0
    with pytest.raises(ValueError):
        action_context.full_withdrawal_post_action_cashflows[
            "surrender_benefits"
        ][0] = 1.0
    with pytest.raises(ValueError):
        decision_context.account_value[0] = 1.0


def test_non_anniversary_full_withdrawal_has_exact_lapse_fees_and_ledger():
    observer = _ActionObserver(anniversary_only=False)
    policy = _TargetExercisePolicy(13, anniversary_only=False)
    result = project(
        **_inputs(),
        surrender_policy=policy,
        surrender_decision_observer=observer,
    )
    context = observer.contexts[13]
    full = context.full_withdrawal_post_action_cashflows

    assert np.all(context.decision_context.full_withdrawal_eligible)
    assert np.all(full["fees_product"] > 0.0)
    assert np.all(full["fees_lip"] > 0.0)
    assert np.all(full["surrender_benefits"] > 0.0)
    assert np.all(full["expenses"] > 0.0)
    for key in CASHFLOW_KEYS:
        np.testing.assert_allclose(
            result.post_surrender_cashflows[key][:, 13],
            full[key],
            rtol=0.0,
            atol=1.0e-10,
        )
    _assert_cashflow_sum(
        {key: result.cashflows[key][:, 13] for key in CASHFLOW_KEYS},
        context.post_cap_common_cashflows,
        full,
    )


def test_anniversary_common_and_realised_post_action_ledgers_reconcile():
    inputs = _inputs()
    continue_observer = _ActionObserver(anniversary_only=True)
    continue_policy = _TargetExercisePolicy(None, anniversary_only=True)
    continued = project(
        **inputs,
        surrender_policy=continue_policy,
        surrender_decision_observer=continue_observer,
    )
    full_observer = _ActionObserver(anniversary_only=True)
    full_policy = _TargetExercisePolicy(24, anniversary_only=True)
    withdrawn = project(
        **inputs,
        surrender_policy=full_policy,
        surrender_decision_observer=full_observer,
    )

    continue_context = continue_observer.contexts[24]
    full_context = full_observer.contexts[24]
    for key in CASHFLOW_KEYS:
        np.testing.assert_allclose(
            continue_context.post_cap_common_cashflows[key],
            full_context.post_cap_common_cashflows[key],
            rtol=0.0,
            atol=1.0e-10,
        )
        np.testing.assert_allclose(
            withdrawn.post_surrender_cashflows[key][:, 24],
            full_context.full_withdrawal_post_action_cashflows[key],
            rtol=0.0,
            atol=1.0e-10,
        )

    _assert_cashflow_sum(
        {key: continued.post_cap_cashflows[key][:, 24] for key in CASHFLOW_KEYS},
        continue_context.post_cap_common_cashflows,
        {
            key: continued.post_surrender_cashflows[key][:, 24]
            for key in CASHFLOW_KEYS
        },
    )
    _assert_cashflow_sum(
        {key: withdrawn.post_cap_cashflows[key][:, 24] for key in CASHFLOW_KEYS},
        full_context.post_cap_common_cashflows,
        full_context.full_withdrawal_post_action_cashflows,
    )
    assert np.all(
        full_context.full_withdrawal_post_action_cashflows["expenses"]
        < continued.post_surrender_cashflows["expenses"][:, 24]
    )
    assert np.all(withdrawn.lapse_events[:, 24] > 0.0)
    assert np.all(continued.lapse_events[:, 24] == 0.0)
