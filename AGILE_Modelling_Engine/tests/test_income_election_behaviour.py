"""Focused contractual tests for state-dependent Income Election.

These tests intentionally use the production monthly projector: Election is a
state transition, not an immediate benefit, and later Full Withdrawal remains
subject to the Income-phase event gate.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from agile_engine import (
    ESGConfig,
    IndexLinkedLifetimeIncomeProduct,
    MortalityTable,
    PolicySpec,
    ProjectionConfig,
    YieldCurve,
    load_dynamic_behaviour_assumptions,
)
from agile_engine.esg import Measure, simulate
from agile_engine.optimal_behaviour_lsmc import no_voluntary_action_behaviour
from agile_engine.product import Phase
from agile_engine.projection import IncomeElectionDecisionContext, project


class _StartAtEveryEligibleAnniversary:
    anniversary_only = True

    def __init__(self) -> None:
        self.contexts: dict[int, IncomeElectionDecisionContext] = {}

    def start_income_mask(self, *, context: IncomeElectionDecisionContext):
        self.contexts[context.step] = context
        return context.voluntary_election_eligible.copy()


class _AlwaysWait:
    anniversary_only = True

    def start_income_mask(self, *, context: IncomeElectionDecisionContext):
        return np.zeros(context.n_paths, dtype=bool)


class _StartThenTryToSurrender(_StartAtEveryEligibleAnniversary):
    def surrender_mask(self, *, context):
        return np.ones(context.n_paths, dtype=bool)


def _scenarios(*, horizon: float, n_paths: int = 16, seed: int = 41):
    config = ESGConfig(curve=YieldCurve.flat(0.04))
    return simulate(
        "black_scholes",
        config,
        horizon,
        n_paths,
        measure=Measure.RISK_NEUTRAL,
        seed=seed,
    )


def test_start_now_locks_income_and_first_payment_is_one_month_later():
    scenarios = _scenarios(horizon=2.0)
    product = IndexLinkedLifetimeIncomeProduct()
    policy = PolicySpec(age=65, income_start_year=2)
    election_policy = _StartAtEveryEligibleAnniversary()
    result = project(
        product,
        policy,
        scenarios,
        no_voluntary_action_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(record_paths=True, max_age=67.0),
        income_election_policy=election_policy,
    )

    context = election_policy.contexts[12]
    assert np.all(result.phase_paths[:, 11] == Phase.GROWTH.value)
    assert np.all(result.phase_paths[:, 12] == Phase.INCOME.value)
    np.testing.assert_allclose(
        result.income_paths[:, 12],
        context.prospective_locked_annual_income,
    )
    assert np.all(result.cashflows["income_paid"][:, 12] == 0.0)
    assert np.any(result.cashflows["income_paid"][:, 13] > 0.0)


def test_income_election_cannot_create_same_timestamp_full_withdrawal():
    scenarios = _scenarios(horizon=2.0)
    combined = _StartThenTryToSurrender()
    result = project(
        IndexLinkedLifetimeIncomeProduct(),
        PolicySpec(age=65, income_start_year=2),
        scenarios,
        no_voluntary_action_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(record_paths=True, max_age=67.0),
        income_election_policy=combined,
        surrender_policy=combined,
    )

    assert np.any(result.income_election_events[:, 12] > 0.0)
    assert np.all(result.lapse_events[:, 12] == 0.0)


def test_phase_cashflow_ledgers_reconcile_to_canonical_cashflows():
    scenarios = _scenarios(horizon=3.0)
    combined = _StartThenTryToSurrender()
    result = project(
        IndexLinkedLifetimeIncomeProduct(),
        PolicySpec(age=65, income_start_year=2),
        scenarios,
        no_voluntary_action_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(record_paths=False, max_age=68.0),
        income_election_policy=combined,
        surrender_policy=combined,
    )

    pv = result.pv_by_component()
    phase_pv = result.pv_phase_by_component()
    canonical_benefits = sum(
        pv[key]
        for key in (
            "income_paid",
            "death_benefits",
            "surrender_benefits",
            "partial_withdrawals",
            "terminal_closeout",
        )
    )
    assert (
        phase_pv["policyholder_benefits_pre_election"]
        + phase_pv["policyholder_benefits_post_election"]
    ) == pytest.approx(canonical_benefits)
    assert phase_pv["post_election_guarantee_claims"] == pytest.approx(
        pv["guarantee_claims"]
    )
    assert np.isfinite(phase_pv["growth_fees"])
    assert np.isfinite(phase_pv["growth_crediting_margin"])


def test_contractual_forced_start_overrides_wait_policy_at_age_100_gate():
    scenarios = _scenarios(horizon=22.0, n_paths=8)
    result = project(
        IndexLinkedLifetimeIncomeProduct(),
        PolicySpec(age=80, income_start_year=5),
        scenarios,
        no_voluntary_action_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(record_paths=True, max_age=103.0),
        income_election_policy=_AlwaysWait(),
    )

    forced_step = 21 * 12
    assert np.all(result.income_election_events[:, :forced_step] == 0.0)
    assert np.any(result.forced_income_election_events[:, forced_step] > 0.0)
    assert np.all(
        result.income_election_events[:, forced_step]
        == result.forced_income_election_events[:, forced_step]
    )


def test_dynamic_take_up_does_not_use_model_point_start_as_realised_date():
    scenarios = _scenarios(horizon=2.0, n_paths=32)
    loaded = load_dynamic_behaviour_assumptions().behaviour
    policy = PolicySpec(age=65, income_start_year=1)
    config = ProjectionConfig(record_paths=True, max_age=67.0, take_up_seed=9)

    dynamic = project(
        IndexLinkedLifetimeIncomeProduct(),
        policy,
        scenarios,
        loaded,
        MortalityTable.gompertz_makeham(),
        config=config,
    )
    deterministic = project(
        IndexLinkedLifetimeIncomeProduct(),
        policy,
        scenarios,
        replace(loaded, take_up=replace(loaded.take_up, mode="deterministic")),
        MortalityTable.gompertz_makeham(),
        config=config,
    )

    # The loaded statistical basis has a structural-zero Year-1 band.  The
    # explicit deterministic benchmark nevertheless starts on the model-point
    # date, proving that the two modes no longer share a silent override.
    assert np.all(dynamic.income_election_events[:, 12] == 0.0)
    assert np.any(deterministic.income_election_events[:, 12] > 0.0)


def test_election_context_is_read_only_and_contains_no_future_surface():
    scenarios = _scenarios(horizon=2.0)
    policy_hook = _StartAtEveryEligibleAnniversary()
    project(
        IndexLinkedLifetimeIncomeProduct(),
        PolicySpec(age=65, income_start_year=2),
        scenarios,
        no_voluntary_action_behaviour(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(record_paths=False, max_age=67.0),
        income_election_policy=policy_hook,
    )
    context = policy_hook.contexts[12]

    assert not hasattr(context, "scenarios")
    assert not hasattr(context, "future_discount")
    assert not hasattr(context, "hedge_pnl")
    assert not context.account_value.flags.writeable
    assert not context.previous_reference_return.flags.writeable


def test_joint_life_election_uses_separate_spouse_status_rates():
    q_primary = np.full(116, 1.0e-6)
    q_spouse = np.full(116, 0.50)
    q_primary[-1] = 1.0
    q_spouse[-1] = 1.0
    mortality = MortalityTable(
        qx_male=q_primary,
        qx_female=q_spouse,
        improvement_rate=0.0,
    )
    scenarios = _scenarios(horizon=2.0, n_paths=128, seed=73)
    policy_hook = _StartAtEveryEligibleAnniversary()
    project(
        IndexLinkedLifetimeIncomeProduct(),
        PolicySpec(
            age=65,
            income_start_year=2,
            spouse=True,
            spouse_age=65,
            spouse_sex="F",
        ),
        scenarios,
        no_voluntary_action_behaviour(),
        mortality,
        config=ProjectionConfig(
            record_paths=False,
            max_age=67.0,
            mortality_seed=811,
        ),
        income_election_policy=policy_hook,
    )
    rates = policy_hook.contexts[12].prospective_income_rate

    # Paths with a surviving Spouse receive the joint rate; paths whose Spouse
    # died during Growth receive the Single-Life fallback.  A nonlinear
    # Behaviour function is never applied to their average.
    assert np.unique(rates).size == 2
