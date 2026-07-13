"""Unit tests for the LSMC cap-behaviour scenario orchestrator."""

from __future__ import annotations

import pytest

from portfolio_simulations.run_lsmc_cap_behaviour_scenarios import (
    _add_baseline_deltas,
    _parse_rate,
    _rate_directory_name,
    parse_args,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    (("0.04", 0.04), ("6%", 0.06), ("12", 0.12), ("20", 0.20)),
)
def test_rate_parser(text, expected):
    assert _parse_rate(text) == pytest.approx(expected)


def test_default_scenarios_use_separate_train_and_evaluation_samples():
    args = parse_args([])
    assert args.cap_rates == [0.04, 0.06, 0.12, 0.20]
    assert args.n_train == 4000
    assert args.n_paths == 2000
    assert args.train_seed != args.seed
    assert args.exercise_buffer_rmse_multiplier == pytest.approx(0.25)


def test_rate_directory_is_stable():
    assert _rate_directory_name(0.04) == "cap_4pct"
    assert _rate_directory_name(0.125) == "cap_12p5pct"


def test_baseline_deltas_are_added_without_averaging_policies():
    rows = []
    for rate, ph, npv in ((0.04, 90.0, 12.0), (0.06, 100.0, 10.0),
                           (0.12, 120.0, 7.0)):
        rows.append({
            "cap_rate": rate,
            "continue_policyholder_benefits_aud": ph - (rate * 10),
            "lsmc_policyholder_benefits_aud": ph,
            "lsmc_future_fees_aud": ph / 10,
            "lsmc_guarantee_claims_aud": ph / 5,
            "lsmc_crediting_margin_aud": 1.0,
            "lsmc_bel_total_aud": ph + 20,
            "lsmc_insurer_npv_aud": npv,
            "lsmc_new_business_margin": npv / 100,
            "lsmc_exercise_rate": 0.0,
            "lsmc_minus_continue_policyholder_benefits_aud": rate * 10,
            "dynamic_policyholder_benefits_aud": ph - 5,
            "dynamic_insurer_npv_aud": npv + 2,
        })
    _add_baseline_deltas(rows, 0.06)
    assert rows[0]["delta_vs_6pct_lsmc_policyholder_benefits_aud"] == -10.0
    assert rows[1]["delta_vs_6pct_lsmc_policyholder_benefits_aud"] == 0.0
    assert rows[2]["delta_vs_6pct_lsmc_insurer_npv_aud"] == -3.0
    assert rows[2]["mechanical_continue_change_vs_baseline_aud"] == pytest.approx(
        19.4)
    assert rows[2]["behaviour_interaction_vs_baseline_aud"] == pytest.approx(
        0.6)
    assert rows[2]["total_lsmc_change_vs_baseline_aud"] == 20.0
    assert rows[2]["cap_effect_decomposition_gap_aud"] == pytest.approx(0.0)
