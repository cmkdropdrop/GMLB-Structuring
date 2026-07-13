"""Exact tests for the finite-horizon Stackelberg reference solver."""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

import numpy as np
import pytest

from agile_engine.stackelberg_control import (
    PolicyholderAction,
    TabularStackelbergProblem,
    solve_tabular_stackelberg,
)


CONTINUE = int(PolicyholderAction.CONTINUE)
FULL_WITHDRAWAL = int(PolicyholderAction.FULL_WITHDRAWAL)


def _three_year_problem() -> TabularStackelbergProblem:
    """A small deterministic tree with two states and two annual caps.

    Every node has only four action pairs, so the complete game contains
    ``3 * 2 * 2 * 2 = 24`` directly enumerable leader/follower alternatives.
    Withdrawal is terminal; Continue moves to state zero under the low cap and
    state one under the high cap until the final year.
    """

    policyholder_reward = np.array(
        [
            [
                [[1.0, 6.0], [0.0, 8.0]],
                [[0.0, 9.0], [1.0, 7.0]],
            ],
            [
                [[1.0, 5.0], [0.0, 6.0]],
                [[0.0, 7.0], [2.0, 6.0]],
            ],
            [
                [[5.0, 4.0], [3.0, 6.0]],
                [[2.0, 5.0], [7.0, 6.0]],
            ],
        ],
        dtype=float,
    )
    insurer_reward = np.array(
        [
            [
                [[3.0, 0.0], [0.0, 9.0]],
                [[0.0, 4.0], [2.0, 0.0]],
            ],
            [
                [[1.0, 0.0], [0.0, 5.0]],
                [[0.0, 6.0], [1.0, 0.0]],
            ],
            [
                [[2.0, 0.0], [0.0, 1.0]],
                [[0.0, 4.0], [3.0, 0.0]],
            ],
        ],
        dtype=float,
    )
    next_state = np.full((3, 2, 2, 2), -1, dtype=np.int64)
    for time in (0, 1):
        for state in (0, 1):
            next_state[time, state, 0, CONTINUE] = 0
            next_state[time, state, 1, CONTINUE] = 1

    return TabularStackelbergProblem(
        policyholder_reward=policyholder_reward,
        insurer_reward=insurer_reward,
        next_state=next_state,
        action_values=np.array([0.01, 0.20]),
    )


def _enumerate_exactly(
    problem: TabularStackelbergProblem,
    admissible: tuple[int, ...] | None = None,
):
    """Independent scalar enumeration of every deterministic subgame."""

    allowed = (
        tuple(range(problem.n_leader_actions))
        if admissible is None
        else tuple(sorted(admissible))
    )

    @lru_cache(maxsize=None)
    def node(time: int, state: int):
        if time == problem.horizon:
            return 0.0, 0.0, -1, tuple(
                -1 for _ in range(problem.n_leader_actions)
            )

        responses = [-1] * problem.n_leader_actions
        policyholder_after_response: dict[int, float] = {}
        insurer_after_response: dict[int, float] = {}
        for leader_action in allowed:
            policyholder_totals: list[float] = []
            insurer_totals: list[float] = []
            for follower_action in (CONTINUE, FULL_WITHDRAWAL):
                transition = int(
                    problem.next_state[
                        time, state, leader_action, follower_action
                    ]
                )
                if transition < 0:
                    next_policyholder = 0.0
                    next_insurer = 0.0
                else:
                    next_policyholder, next_insurer, _cap, _responses = node(
                        time + 1, transition
                    )
                policyholder_totals.append(
                    float(
                        problem.policyholder_reward[
                            time, state, leader_action, follower_action
                        ]
                    )
                    + next_policyholder
                )
                insurer_totals.append(
                    float(
                        problem.insurer_reward[
                            time, state, leader_action, follower_action
                        ]
                    )
                    + next_insurer
                )

            response = (
                FULL_WITHDRAWAL
                if policyholder_totals[FULL_WITHDRAWAL]
                > policyholder_totals[CONTINUE]
                + problem.policyholder_tie_tolerance
                else CONTINUE
            )
            responses[leader_action] = response
            policyholder_after_response[leader_action] = policyholder_totals[
                response
            ]
            insurer_after_response[leader_action] = insurer_totals[response]

        selected_cap = allowed[0]
        for candidate in allowed[1:]:
            candidate_value = insurer_after_response[candidate]
            selected_value = insurer_after_response[selected_cap]
            if candidate_value > selected_value + problem.insurer_tie_tolerance:
                selected_cap = candidate
            elif (
                abs(candidate_value - selected_value)
                <= problem.insurer_tie_tolerance
                and problem.action_values[candidate]
                < problem.action_values[selected_cap]
            ):
                selected_cap = candidate

        return (
            policyholder_after_response[selected_cap],
            insurer_after_response[selected_cap],
            selected_cap,
            tuple(responses),
        )

    policyholder_value = np.zeros((problem.horizon, problem.n_states))
    insurer_value = np.zeros_like(policyholder_value)
    leader_policy = np.full(
        (problem.horizon, problem.n_states), -1, dtype=np.int64
    )
    follower_policy = np.full(
        (
            problem.horizon,
            problem.n_states,
            problem.n_leader_actions,
        ),
        -1,
        dtype=np.int64,
    )
    for time in range(problem.horizon):
        for state in range(problem.n_states):
            ph, insurer, leader, responses = node(time, state)
            policyholder_value[time, state] = ph
            insurer_value[time, state] = insurer
            leader_policy[time, state] = leader
            follower_policy[time, state, :] = responses
    return policyholder_value, insurer_value, leader_policy, follower_policy


def test_three_year_backward_induction_matches_complete_enumeration():
    problem = _three_year_problem()
    solution = solve_tabular_stackelberg(problem)
    enumerated = _enumerate_exactly(problem)

    expected_leader = np.array(
        [
            [1, 1],
            [1, 0],
            [0, 0],
        ],
        dtype=np.int64,
    )
    expected_response_by_cap = np.tile(
        np.array([[CONTINUE, FULL_WITHDRAWAL],
                  [FULL_WITHDRAWAL, CONTINUE]], dtype=np.int64)[None, :, :],
        (3, 1, 1),
    )
    expected_policyholder_value = np.array(
        [
            [8.0, 8.0],
            [6.0, 7.0],
            [5.0, 5.0],
        ]
    )
    expected_insurer_value = np.array(
        [
            [9.0, 8.0],
            [5.0, 6.0],
            [2.0, 4.0],
        ]
    )

    np.testing.assert_array_equal(solution.leader_action_index, expected_leader)
    np.testing.assert_array_equal(
        solution.policyholder_action_index,
        expected_response_by_cap,
    )
    np.testing.assert_allclose(
        solution.policyholder_value,
        expected_policyholder_value,
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        solution.insurer_value,
        expected_insurer_value,
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(solution.policyholder_value, enumerated[0])
    np.testing.assert_allclose(solution.insurer_value, enumerated[1])
    np.testing.assert_array_equal(solution.leader_action_index, enumerated[2])
    np.testing.assert_array_equal(
        solution.policyholder_action_index,
        enumerated[3],
    )


def test_fixed_cap_is_the_singleton_subclass_of_the_same_problem():
    problem = _three_year_problem()
    solution = solve_tabular_stackelberg(
        problem,
        admissible_leader_action_indices=(1,),
    )
    enumerated = _enumerate_exactly(problem, admissible=(1,))

    np.testing.assert_array_equal(solution.leader_action_index, 1)
    np.testing.assert_array_equal(
        solution.policyholder_action_index[:, :, 0],
        -1,
    )
    np.testing.assert_array_equal(
        solution.policyholder_action_index[:, :, 1],
        np.array(
            [
                [CONTINUE, CONTINUE],
                [CONTINUE, CONTINUE],
                [FULL_WITHDRAWAL, CONTINUE],
            ]
        ),
    )
    np.testing.assert_allclose(
        solution.policyholder_value,
        np.array([[9.0, 10.0], [7.0, 9.0], [6.0, 7.0]]),
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        solution.insurer_value,
        np.array([[4.0, 6.0], [3.0, 4.0], [1.0, 3.0]]),
        rtol=0.0,
        atol=0.0,
    )
    assert solution.admissible_leader_action_indices == (1,)
    np.testing.assert_allclose(solution.policyholder_value, enumerated[0])
    np.testing.assert_allclose(solution.insurer_value, enumerated[1])
    np.testing.assert_array_equal(solution.leader_action_index, enumerated[2])
    np.testing.assert_array_equal(
        solution.policyholder_action_index,
        enumerated[3],
    )


def test_policyholder_tie_continues_and_leader_tie_uses_lowest_cap():
    problem = TabularStackelbergProblem(
        policyholder_reward=np.array([[[[5.0, 5.0], [7.0, 7.0]]]]),
        # The very large insurer withdrawal rewards are deliberately
        # irrelevant: the follower chooses its own tied Continue action.
        insurer_reward=np.array([[[[10.0, -1_000.0], [10.0, 1_000.0]]]]),
        next_state=np.full((1, 1, 2, 2), -1, dtype=np.int64),
        action_values=np.array([0.01, 0.20]),
    )

    solution = solve_tabular_stackelberg(
        problem,
        admissible_leader_action_indices=(1, 0),
    )

    np.testing.assert_array_equal(
        solution.policyholder_action_index[0, 0],
        [CONTINUE, CONTINUE],
    )
    assert solution.leader_action_index[0, 0] == 0
    assert solution.policyholder_value[0, 0] == pytest.approx(5.0)
    assert solution.insurer_value[0, 0] == pytest.approx(10.0)


def test_insurer_reward_cannot_select_the_policyholder_action():
    policyholder_reward = np.array(
        [[[[10.0, 0.0], [0.0, 10.0]]]],
        dtype=float,
    )
    transitions = np.full((1, 1, 2, 2), -1, dtype=np.int64)
    prefer_high_cap = TabularStackelbergProblem(
        policyholder_reward=policyholder_reward,
        insurer_reward=np.array(
            [[[[0.0, 1_000.0], [0.0, 1_000.0]]]],
            dtype=float,
        ),
        next_state=transitions,
        action_values=np.array([0.01, 0.20]),
    )
    prefer_low_cap = replace(
        prefer_high_cap,
        insurer_reward=np.array(
            [[[[1_000.0, 0.0], [1_000.0, 0.0]]]],
            dtype=float,
        ),
    )

    high_solution = solve_tabular_stackelberg(prefer_high_cap)
    low_solution = solve_tabular_stackelberg(prefer_low_cap)
    expected_best_response = np.array([CONTINUE, FULL_WITHDRAWAL])

    np.testing.assert_array_equal(
        high_solution.policyholder_action_index[0, 0],
        expected_best_response,
    )
    np.testing.assert_array_equal(
        low_solution.policyholder_action_index[0, 0],
        expected_best_response,
    )
    # Insurer rewards can change the leader decision, but never the follower's
    # cap-conditional argmax.
    assert high_solution.leader_action_index[0, 0] == 1
    assert low_solution.leader_action_index[0, 0] == 0


def _reachable_continuation_problem() -> TabularStackelbergProblem:
    policyholder_reward = np.zeros((2, 2, 1, 2), dtype=float)
    policyholder_reward[0, :, 0, :] = [0.0, 5.0]
    policyholder_reward[1, 0, 0, :] = [4.0, 0.0]
    policyholder_reward[1, 1, 0, :] = [8.0, 0.0]
    next_state = np.full((2, 2, 1, 2), -1, dtype=np.int64)
    next_state[0, :, 0, CONTINUE] = 0
    return TabularStackelbergProblem(
        policyholder_reward=policyholder_reward,
        insurer_reward=np.zeros_like(policyholder_reward),
        next_state=next_state,
        action_values=np.array([0.06]),
    )


def test_later_state_changes_reach_earlier_follower_only_through_transition():
    base_problem = _reachable_continuation_problem()
    base = solve_tabular_stackelberg(base_problem)

    unreachable_reward = np.array(base_problem.policyholder_reward, copy=True)
    unreachable_reward[1, 1, 0, CONTINUE] = 800.0
    unreachable = solve_tabular_stackelberg(
        replace(base_problem, policyholder_reward=unreachable_reward)
    )

    redirected_transition = np.array(base_problem.next_state, copy=True)
    redirected_transition[0, 0, 0, CONTINUE] = 1
    redirected = solve_tabular_stackelberg(
        replace(base_problem, next_state=redirected_transition)
    )

    assert base.policyholder_action_index[0, 0, 0] == FULL_WITHDRAWAL
    assert unreachable.policyholder_action_index[0, 0, 0] == FULL_WITHDRAWAL
    assert redirected.policyholder_action_index[0, 0, 0] == CONTINUE
    assert base.policyholder_q[0, 0, 0, CONTINUE] == pytest.approx(4.0)
    assert unreachable.policyholder_q[0, 0, 0, CONTINUE] == pytest.approx(4.0)
    assert redirected.policyholder_q[0, 0, 0, CONTINUE] == pytest.approx(8.0)
    assert base.policyholder_q[0, 0, 0, FULL_WITHDRAWAL] == pytest.approx(5.0)
    assert redirected.policyholder_q[
        0, 0, 0, FULL_WITHDRAWAL
    ] == pytest.approx(5.0)


def test_later_insurer_reward_changes_only_insurer_continuation_under_fixed_cap():
    problem = _reachable_continuation_problem()
    redirected_transition = np.array(problem.next_state, copy=True)
    redirected_transition[0, 0, 0, CONTINUE] = 1
    redirected = replace(problem, next_state=redirected_transition)

    changed_insurer_reward = np.array(redirected.insurer_reward, copy=True)
    changed_insurer_reward[1, 1, 0, CONTINUE] = 500.0
    changed = replace(redirected, insurer_reward=changed_insurer_reward)

    baseline_solution = solve_tabular_stackelberg(
        redirected,
        admissible_leader_action_indices=(0,),
    )
    changed_solution = solve_tabular_stackelberg(
        changed,
        admissible_leader_action_indices=(0,),
    )

    np.testing.assert_array_equal(
        changed_solution.policyholder_action_index,
        baseline_solution.policyholder_action_index,
    )
    np.testing.assert_allclose(
        changed_solution.policyholder_value,
        baseline_solution.policyholder_value,
        rtol=0.0,
        atol=0.0,
    )
    assert baseline_solution.insurer_value[0, 0] == pytest.approx(0.0)
    assert changed_solution.insurer_value[0, 0] == pytest.approx(500.0)


def _leader_continuation_problem(state_one_reward: float):
    policyholder_reward = np.zeros((2, 2, 2, 2), dtype=float)
    policyholder_reward[..., CONTINUE] = 10.0
    insurer_reward = np.zeros_like(policyholder_reward)
    insurer_reward[1, 0, :, CONTINUE] = 2.0
    insurer_reward[1, 1, :, CONTINUE] = state_one_reward
    next_state = np.full((2, 2, 2, 2), -1, dtype=np.int64)
    next_state[0, :, 0, CONTINUE] = 0
    next_state[0, :, 1, CONTINUE] = 1
    return TabularStackelbergProblem(
        policyholder_reward=policyholder_reward,
        insurer_reward=insurer_reward,
        next_state=next_state,
        action_values=np.array([0.01, 0.20]),
    )


def test_later_insurer_reward_reaches_leader_only_through_insurer_continuation():
    low_future_state = solve_tabular_stackelberg(
        _leader_continuation_problem(state_one_reward=1.0)
    )
    high_future_state = solve_tabular_stackelberg(
        _leader_continuation_problem(state_one_reward=3.0)
    )

    assert low_future_state.leader_action_index[0, 0] == 0
    assert high_future_state.leader_action_index[0, 0] == 1
    np.testing.assert_array_equal(
        low_future_state.policyholder_action_index,
        CONTINUE,
    )
    np.testing.assert_array_equal(
        high_future_state.policyholder_action_index,
        CONTINUE,
    )
    assert low_future_state.insurer_q_after_best_response[0, 0, 0] \
        == pytest.approx(2.0)
    assert low_future_state.insurer_q_after_best_response[0, 0, 1] \
        == pytest.approx(1.0)
    assert high_future_state.insurer_q_after_best_response[0, 0, 0] \
        == pytest.approx(2.0)
    assert high_future_state.insurer_q_after_best_response[0, 0, 1] \
        == pytest.approx(3.0)

