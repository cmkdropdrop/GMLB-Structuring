"""Static CLI contracts for streamlined and replicated LSMC runs."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from agile_engine.projection import IncomeActionType
from portfolio_simulations.run_portfolio_valuation_lsmc import (
    _FixedIncomeActionPolicy,
    parse_args,
)


def test_lsmc_runner_defaults_to_one_seed_and_continue_full_only():
    args = parse_args([])

    assert args.training_seed_count == 1
    assert args.lsmc_income_action_set == "continue_full"
    assert len({args.train_seed, args.validation_seed, args.seed}) == 3


def test_fixed_full_withdrawal_benchmark_preserves_complete_action_values():
    policy = _FixedIncomeActionPolicy("full_first")
    context = SimpleNamespace(
        n_paths=3,
        full_withdrawal_eligible=np.asarray([False, True, True]),
    )

    decision = policy.choose_income_action(context=context)

    np.testing.assert_array_equal(
        decision.action_type,
        np.asarray([
            IncomeActionType.CONTINUE.value,
            IncomeActionType.FULL_WITHDRAWAL.value,
            IncomeActionType.FULL_WITHDRAWAL.value,
        ]),
    )


@pytest.mark.parametrize(
    ("option", "collision"),
    (
        ("--train-seed-2", "12026"),
        ("--train-seed-2", "22026"),
        ("--train-seed-3", "2026"),
        ("--train-take-up-seed-2", "10097"),
        ("--train-take-up-seed-3", "20097"),
        ("--train-mortality-seed-3", "10197"),
        ("--train-mortality-seed-2", "197"),
    ),
)
def test_lsmc_runner_rejects_training_seed_collisions(option, collision):
    with pytest.raises(SystemExit):
        parse_args([option, collision])


def test_lsmc_runner_accepts_explicit_second_and_third_seed_triplets():
    args = parse_args([
        "--train-seed-2", "51001",
        "--train-take-up-seed-2", "51002",
        "--train-mortality-seed-2", "51003",
        "--train-seed-3", "52001",
        "--train-take-up-seed-3", "52002",
        "--train-mortality-seed-3", "52003",
    ])

    assert (
        args.train_seed_2,
        args.train_take_up_seed_2,
        args.train_mortality_seed_2,
    ) == (51001, 51002, 51003)
    assert (
        args.train_seed_3,
        args.train_take_up_seed_3,
        args.train_mortality_seed_3,
    ) == (52001, 52002, 52003)
    assert args.training_seed_count == 3
    assert args.lsmc_income_action_set == "continue_full"


def test_lsmc_runner_rejects_deprecated_partial_action_set():
    with pytest.raises(SystemExit):
        parse_args([
            "--lsmc-income-action-set", "continue_partial_full",
        ])


def test_lsmc_runner_accepts_explicit_streamlined_mode_with_legacy_seed_values():
    args = parse_args([
        "--train-seed-2", "51001",
        "--training-seed-count", "1",
        "--lsmc-income-action-set", "continue_full",
    ])

    assert args.training_seed_count == 1
    assert args.lsmc_income_action_set == "continue_full"
