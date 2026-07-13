"""Exact small-state tests for the production coupled backward recursion.

The fixture deliberately uses the full 21-cap grid and enough repeated
complete paths to satisfy the production support gates.  Its economic state is
one deterministic finite state, so the fitted regressions are saturated by an
intercept plus the announced-cap covariate and can be compared with the exact
tabular Stackelberg solver without Monte-Carlo noise.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from agile_engine.optimal_behaviour_lsmc import OptimalBehaviourLSMCSettings
from agile_engine.product import Phase, PolicySpec
from agile_engine.projection import SurrenderDecisionContext
from agile_engine.stackelberg_control import (
    PolicyholderAction,
    TabularStackelbergProblem,
    solve_tabular_stackelberg,
)
from portfolio_simulations.optimize_crediting_rate_lsmc import (
    ACTION_CAPS,
    CONTROL_STATE_FEATURE_NAMES,
    PORTFOLIO_CONTROL_STATE_FEATURE_NAMES,
    ControlStateInputs,
    PortfolioPathData,
    SignatureControlPaths,
    SignatureDecisionYearPaths,
    _backward_induction,
    _coupled_backward_induction,
    _policy_signature,
)


N_YEARS = 2
FOLDS = 3
PATHS_PER_ACTION = 240
PREMIUM = 100.0


@dataclass(frozen=True)
class _FiniteStateFixture:
    data: PortfolioPathData
    action_indices: np.ndarray
    control_inputs: ControlStateInputs
    portfolio_state_extension: np.ndarray
    policy: PolicySpec
    signature: tuple[object, ...]
    ph_continue: np.ndarray
    ph_withdraw: np.ndarray
    insurer_continue: np.ndarray
    insurer_withdraw: np.ndarray


def _customer_core(
    rng: np.random.Generator,
    actual_caps: np.ndarray,
    full_withdrawal_value: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return full-rank compact pre-/post-cap customer states."""
    n_paths = actual_caps.size
    pre = np.zeros((n_paths, 13), dtype=float)
    pre[:, 0] = rng.uniform(0.55, 1.20, n_paths)  # Account Value / premium
    pre[:, 1] = rng.uniform(0.35, 1.05, n_paths)  # pre-cap Surrender Value
    pre[:, 2] = rng.uniform(0.025, 0.10, n_paths)  # annual income
    pre[:, 3] = rng.uniform(0.60, 1.80, n_paths)  # guarantee PV
    pre[:, 4] = rng.uniform(-0.8, 1.2, n_paths)  # log moneyness
    # Keep both rate inputs constant.  Otherwise the canonical slope feature is
    # an exact linear combination of short and five-year rates, which would
    # intentionally trigger the deployment rank fallback in this exact-fit test.
    pre[:, 5] = 0.0
    pre[:, 6] = 0.0
    pre[:, 7] = rng.uniform(0.015, 0.10, n_paths)
    pre[:, 8] = rng.choice(ACTION_CAPS, n_paths)  # previous cap
    pre[:, 9] = rng.uniform(-0.20, 0.25, n_paths)
    pre[:, 10] = rng.uniform(0.0, 0.20, n_paths)
    pre[:, 11] = rng.uniform(0.0, 0.25, n_paths)
    pre[:, 12] = 1.0

    after = pre.copy()
    # Add harmless independent variation to the realised post-cap exit value.
    # The exact action payoff remains the separate full_withdrawal_value array.
    after[:, 1] = (
        full_withdrawal_value / PREMIUM
        + rng.uniform(-0.01, 0.01, n_paths)
    )
    after[:, 8] = actual_caps
    return pre.astype(np.float32), after.astype(np.float32)


def _finite_state_fixture(*, policyholder_actions_enabled: bool) -> _FiniteStateFixture:
    n_actions = len(ACTION_CAPS)
    observed_action = np.repeat(
        np.arange(n_actions, dtype=np.int64), PATHS_PER_ACTION
    )
    action_indices = np.column_stack((observed_action, observed_action))
    actual_caps = ACTION_CAPS[observed_action]
    n_paths = observed_action.size

    # Customer rewards are in decision-time dollars.  At the final decision,
    # withdrawal is optimal only above 5%.  The final leader therefore chooses
    # 20%; its customer value (25) makes Continue optimal at time zero.
    ph_continue = np.vstack((
        np.full(n_actions, 2.0),
        np.full(n_actions, 10.0),
    ))
    ph_withdraw = np.vstack((
        10.0 + 50.0 * ACTION_CAPS,
        5.0 + 100.0 * ACTION_CAPS,
    ))

    # Only the Product-Fee component is used, so the insurer CSM equals this
    # component exactly and no sign convention is hidden in the fixture.
    insurer_continue = np.vstack((
        40.0 - 100.0 * ACTION_CAPS,
        20.0 - 20.0 * ACTION_CAPS,
    ))
    insurer_withdraw = np.vstack((
        15.0 + 10.0 * ACTION_CAPS,
        30.0 + 10.0 * ACTION_CAPS,
    ))

    policy = PolicySpec(
        age=65.0,
        initial_investment=PREMIUM,
        income_start_year=1,
    )
    signature = _policy_signature(policy)
    rng = np.random.default_rng(712_367)
    records: dict[int, SignatureDecisionYearPaths] = {}
    for year in range(N_YEARS):
        observed_continue = ph_continue[year, observed_action]
        observed_withdraw = ph_withdraw[year, observed_action]
        pre_core, after_core = _customer_core(
            rng, actual_caps, observed_withdraw
        )
        insurer_delta = np.zeros((n_paths, 9), dtype=np.float32)
        insurer_delta[:, 0] = (
            insurer_withdraw[year, observed_action]
            - insurer_continue[year, observed_action]
        )
        records[year] = SignatureDecisionYearPaths(
            policy_year=year,
            decision_step=12 * (year + 1),
            pre_cap_core=pre_core,
            after_cap_core=after_core,
            phase=np.full(n_paths, Phase.INCOME.value, dtype=np.int8),
            just_elected=np.zeros(n_paths, dtype=bool),
            full_withdrawal_eligible=np.full(
                n_paths, policyholder_actions_enabled, dtype=bool
            ),
            decision_discount_inforce=np.ones(n_paths, dtype=np.float32),
            next_decision_discount_inforce=(
                np.ones(n_paths, dtype=np.float32)
                if year == 0 else np.zeros(n_paths, dtype=np.float32)
            ),
            continue_policyholder_interval_pv=np.asarray(
                observed_continue, dtype=np.float32
            ),
            full_withdrawal_value=np.asarray(
                observed_withdraw, dtype=np.float32
            ),
            insurer_full_minus_continue_components=insurer_delta,
            # The exact finite-state problem has one state.  Customer exits do
            # not create a second aggregate state in this fixture.
            next_portfolio_exposure_contribution=np.zeros(
                (n_paths, 9), dtype=np.float32
            ),
        )

    shape = (n_paths, N_YEARS)
    zeros = np.zeros(shape)
    fees_product = np.column_stack((
        insurer_continue[0, observed_action],
        insurer_continue[1, observed_action],
    ))
    state_names = (
        *CONTROL_STATE_FEATURE_NAMES,
        *PORTFOLIO_CONTROL_STATE_FEATURE_NAMES,
    )
    raw_states = np.zeros((n_paths, N_YEARS + 1, len(state_names)))
    portfolio_state = np.zeros((
        n_paths,
        N_YEARS + 1,
        len(PORTFOLIO_CONTROL_STATE_FEATURE_NAMES),
    ))
    data = PortfolioPathData(
        guarantee_claims=zeros.copy(),
        other_insurer_funded_benefits=zeros.copy(),
        fees_product=fees_product,
        fees_lip=zeros.copy(),
        crediting_margin=zeros.copy(),
        mva_retained=zeros.copy(),
        aps_retained=zeros.copy(),
        expenses=zeros.copy(),
        hedge_costs=zeros.copy(),
        income_paid=np.column_stack((
            ph_continue[0, observed_action],
            ph_continue[1, observed_action],
        )),
        death_benefits=zeros.copy(),
        surrender_benefits=zeros.copy(),
        partial_withdrawals=zeros.copy(),
        terminal_closeout=zeros.copy(),
        lapse_events=zeros.copy(),
        inforce_exposure=np.ones(shape),
        raw_states=raw_states,
        state_feature_names=state_names,
        pre_action_states=portfolio_state.copy(),
        pre_action_state_feature_names=PORTFOLIO_CONTROL_STATE_FEATURE_NAMES,
        representative_initial_premium=PREMIUM,
        signature_control_paths={
            signature: SignatureControlPaths(
                signature=signature,
                policy=policy,
                decision_years=records,
            )
        },
    )
    inputs = ControlStateInputs(
        market_features=np.zeros((n_paths, N_YEARS + 1, 5)),
        annual_reference_fund_return=np.zeros(shape),
    )
    return _FiniteStateFixture(
        data=data,
        action_indices=action_indices,
        control_inputs=inputs,
        portfolio_state_extension=portfolio_state,
        policy=policy,
        signature=signature,
        ph_continue=ph_continue,
        ph_withdraw=ph_withdraw,
        insurer_continue=insurer_continue,
        insurer_withdraw=insurer_withdraw,
    )


def _tabular_solution(fixture: _FiniteStateFixture):
    ph_reward = np.zeros((N_YEARS, 1, len(ACTION_CAPS), 2))
    insurer_reward = np.zeros_like(ph_reward)
    ph_reward[:, 0, :, PolicyholderAction.CONTINUE] = fixture.ph_continue
    ph_reward[:, 0, :, PolicyholderAction.FULL_WITHDRAWAL] = fixture.ph_withdraw
    insurer_reward[:, 0, :, PolicyholderAction.CONTINUE] = (
        fixture.insurer_continue
    )
    insurer_reward[:, 0, :, PolicyholderAction.FULL_WITHDRAWAL] = (
        fixture.insurer_withdraw
    )
    transition = np.full(ph_reward.shape, -1, dtype=np.int64)
    transition[0, 0, :, PolicyholderAction.CONTINUE] = 0
    return solve_tabular_stackelberg(TabularStackelbergProblem(
        policyholder_reward=ph_reward,
        insurer_reward=insurer_reward,
        next_state=transition,
        action_values=ACTION_CAPS,
    ))


def _coupled_result(fixture: _FiniteStateFixture):
    return _coupled_backward_induction(
        fixture.data,
        fixture.action_indices,
        control_inputs=fixture.control_inputs,
        portfolio_state_extension=fixture.portfolio_state_extension,
        folds=FOLDS,
        ridge=1.0e-6,
        seed=91,
        follower_settings=OptimalBehaviourLSMCSettings(
            ridge=1.0e-6,
            n_folds=FOLDS,
            fold_seed=91,
            exercise_tolerance_aud=1.0e-6,
            exercise_buffer_rmse_multiplier=0.0,
            maximum_condition_number=1.0e12,
        ),
        scenario_fingerprint="finite-state-training",
        cap_schedule_fingerprint="balanced-21-cap-grid",
    )


def _selected_later_cap(result, policy_year: int) -> float:
    rows = [
        row for row in result.policy_year_rows
        if int(row["policy_year"]) == policy_year
    ]
    assert rows
    return float(max(rows, key=lambda row: row["selected_fraction"])["cap"])


def _decision_context(
    *,
    year: int,
    cap: float,
    surrender_value: float,
    eligible: bool,
    n_paths: int = 8,
) -> SurrenderDecisionContext:
    return SurrenderDecisionContext(
        step=12 * (year + 1),
        time=float(year),
        is_anniversary=True,
        policy_year=year,
        duration_years=float(year),
        phase=np.full(n_paths, Phase.INCOME.value, dtype=np.int8),
        account_value=np.full(n_paths, 0.80 * PREMIUM),
        surrender_value=np.full(n_paths, surrender_value),
        locked_annual_income=np.full(n_paths, 0.05 * PREMIUM),
        guarantee_pv=np.full(n_paths, PREMIUM),
        guarantee_moneyness=np.ones(n_paths),
        guarantee_log_moneyness=np.zeros(n_paths),
        short_rate=np.zeros(n_paths),
        zero_rate_5y=np.zeros(n_paths),
        heston_variance=np.full(n_paths, 0.04),
        announced_cap=np.full(n_paths, cap),
        previous_reference_return=np.zeros(n_paths),
        previous_credited_return=np.zeros(n_paths),
        performance_gap=np.zeros(n_paths),
        inforce_weight=np.ones(n_paths),
        just_elected=np.zeros(n_paths, dtype=bool),
        full_withdrawal_eligible=np.full(n_paths, eligible, dtype=bool),
    )


def test_production_coupled_backward_matches_exact_two_year_stackelberg():
    fixture = _finite_state_fixture(policyholder_actions_enabled=True)
    exact = _tabular_solution(fixture)
    fitted = _coupled_result(fixture)

    first_action = exact.first_leader_action_index
    second_action = int(exact.leader_action_index[1, 0])
    assert fitted.first_year_cap == pytest.approx(ACTION_CAPS[first_action])
    observed_second_cap = _selected_later_cap(fitted, 2)
    assert observed_second_cap == pytest.approx(ACTION_CAPS[second_action]), {
        "numerical_fallback_reasons": fitted.numerical_fallback_reasons,
        "follower_regressions": fitted.follower_regression_rows,
    }
    assert fitted.pv_new_business_csm_proxy == pytest.approx(
        exact.insurer_value[0, 0], abs=2.0e-4
    )
    assert fitted.pv_fees_product == pytest.approx(
        exact.insurer_value[0, 0], abs=2.0e-4
    )

    policy = fitted.follower_fit_set.policies[fixture.signature]
    for year, action in enumerate((first_action, second_action)):
        cap = float(ACTION_CAPS[action])
        context = _decision_context(
            year=year,
            cap=cap,
            surrender_value=float(fixture.ph_withdraw[year, action]),
            eligible=True,
        )
        expected_action = int(exact.policyholder_action_index[
            year, 0, action
        ])
        actual = policy.surrender_mask(context=context)
        np.testing.assert_array_equal(
            actual,
            expected_action == int(PolicyholderAction.FULL_WITHDRAWAL),
        )
        continuation = policy.regressions[context.step].predict(context)
        expected_continue = exact.policyholder_q[
            year, 0, action, PolicyholderAction.CONTINUE
        ]
        np.testing.assert_allclose(
            continuation, expected_continue, rtol=0.0, atol=2.0e-3
        )


def test_disabled_policyholder_actions_reproduce_legacy_insurer_optimizer():
    fixture = _finite_state_fixture(policyholder_actions_enabled=False)
    coupled = _coupled_result(fixture)
    legacy = _backward_induction(
        fixture.data,
        fixture.action_indices,
        folds=FOLDS,
        ridge=1.0e-6,
        seed=91,
    )

    assert coupled.first_year_cap == pytest.approx(legacy.first_year_cap)
    assert _selected_later_cap(coupled, 2) == pytest.approx(
        _selected_later_cap(legacy, 2)
    )
    for field in (
        "pv_new_business_csm_proxy",
        "pv_fees_product",
        "pv_fees_lip",
        "pv_crediting_margin",
        "pv_mva_retained",
        "pv_aps_retained",
        "pv_guarantee_claims",
        "pv_other_insurer_funded_benefits",
        "pv_expenses",
        "pv_hedge_costs",
    ):
        assert getattr(coupled, field) == pytest.approx(
            getattr(legacy, field), abs=2.0e-4
        )

    policy = coupled.follower_fit_set.policies[fixture.signature]
    for year in range(N_YEARS):
        cap = (
            coupled.first_year_cap
            if year == 0 else _selected_later_cap(coupled, 2)
        )
        action = int(np.argmin(np.abs(ACTION_CAPS - cap)))
        context = _decision_context(
            year=year,
            cap=cap,
            surrender_value=float(fixture.ph_withdraw[year, action]),
            eligible=False,
        )
        assert not np.any(policy.surrender_mask(context=context))
