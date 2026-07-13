"""Contracts for the repository Monte-Carlo analysis input CSV."""

from portfolio_simulations._mc_analysis_inputs import (
    DEFAULT_MC_ANALYSIS_INPUT_PATH,
    load_mc_analysis_inputs,
    require_mc_samples,
)


def test_repository_mc_inputs_define_evaluation_training_and_validation():
    inputs = load_mc_analysis_inputs()

    evaluation = require_mc_samples(inputs, "evaluation", 1)[0]
    training = require_mc_samples(inputs, "lsmc_training", 3)
    validation = require_mc_samples(inputs, "lsmc_validation", 1)[0]

    assert DEFAULT_MC_ANALYSIS_INPUT_PATH.is_file()
    assert (
        evaluation.n_paths,
        evaluation.market_seed,
        evaluation.take_up_seed,
        evaluation.mortality_seed,
    ) == (2_000, 2026, 97, 197)
    assert [sample.seed_set for sample in training] == [1, 2, 3]
    assert {sample.n_paths for sample in training} == {4_000}
    assert [sample.market_seed for sample in training] == [
        12026,
        32026,
        42026,
    ]
    assert (
        validation.n_paths,
        validation.market_seed,
        validation.take_up_seed,
        validation.mortality_seed,
    ) == (2_000, 22026, 20097, 20197)


def test_script_selects_training_seed_count_from_available_csv_sets():
    inputs = load_mc_analysis_inputs()

    streamlined = require_mc_samples(inputs, "lsmc_training", 1)
    replicated = require_mc_samples(inputs, "lsmc_training", 3)

    assert len(streamlined) == 1
    assert len(replicated) == 3
    assert streamlined[0] == replicated[0]
