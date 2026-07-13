"""Static CLI contracts for the three-seed optimal-behaviour runner."""

from __future__ import annotations

import pytest

from portfolio_simulations.run_portfolio_valuation_lsmc import parse_args


def test_lsmc_runner_declares_exactly_three_distinct_training_seed_triplets():
    args = parse_args([])
    triplets = (
        (
            args.train_seed,
            args.train_take_up_seed,
            args.train_mortality_seed,
        ),
        (
            args.train_seed_2,
            args.train_take_up_seed_2,
            args.train_mortality_seed_2,
        ),
        (
            args.train_seed_3,
            args.train_take_up_seed_3,
            args.train_mortality_seed_3,
        ),
    )

    assert len(triplets) == 3
    assert len(set(triplets)) == 3
    assert len({item[0] for item in triplets} | {
        args.validation_seed, args.seed,
    }) == 5
    assert len({item[1] for item in triplets} | {
        args.validation_take_up_seed, args.take_up_seed,
    }) == 5
    assert len({item[2] for item in triplets} | {
        args.validation_mortality_seed, args.mortality_seed,
    }) == 5


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
