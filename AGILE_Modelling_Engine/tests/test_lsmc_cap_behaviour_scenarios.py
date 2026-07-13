"""Unit tests for the LSMC cap-behaviour scenario orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from portfolio_simulations.run_lsmc_cap_behaviour_scenarios import (
    HEDGE_MONETARY_FIELDS,
    _add_baseline_deltas,
    _hedge_summary_metrics,
    _manifest_hedge_cap_leg_mode,
    _parse_rate,
    _rate_directory_name,
    _required_scenario_outputs,
    _scenario_command,
    _validate_hedge_summary,
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
    assert args.hedge_cap_leg_mode == "sold"


def test_hedge_cap_leg_mode_is_forwarded_to_lsmc_runner():
    args = parse_args(["--hedge-cap-leg-mode", "not_sold"])
    command = _scenario_command(args, 0.06, "base", Path("scenario-output"))
    mode_index = command.index("--hedge-cap-leg-mode")
    assert command[mode_index + 1] == "not_sold"


def test_manifest_hedge_cap_leg_mode_must_be_present_and_consistent():
    manifest = {
        "method": {"hedge_cap_leg_mode": "sold"},
        "lsmc_settings": {"hedge_cap_leg_mode": "sold"},
        "evaluation_settings": {"hedge_cap_leg_mode": "sold"},
    }
    assert _manifest_hedge_cap_leg_mode(manifest) == "sold"

    manifest["evaluation_settings"]["hedge_cap_leg_mode"] = "not_sold"
    with pytest.raises(ValueError, match="inconsistent"):
        _manifest_hedge_cap_leg_mode(manifest)

    manifest["evaluation_settings"]["hedge_cap_leg_mode"] = "sold"
    manifest["lsmc_settings"]["hedge_cap_leg_mode"] = "not_sold"
    with pytest.raises(ValueError, match="inconsistent"):
        _manifest_hedge_cap_leg_mode(manifest)


@pytest.mark.parametrize(
    ("absolute", "source_prefix"),
    ((False, "normalised_average_"), (True, "portfolio_total_")),
)
def test_all_hedge_metrics_are_extracted_for_every_summary_basis(
    absolute,
    source_prefix,
):
    summary = {"absolute_portfolio_values_available": absolute}
    expected = {}
    for index, metric in enumerate(HEDGE_MONETARY_FIELDS, start=1):
        value = float(index)
        summary[f"{source_prefix}{metric}"] = value
        expected[f"benchmark_{metric}"] = value
    assert _hedge_summary_metrics(summary, "benchmark") == expected


def test_hedge_summary_reconciles_costs_and_forbids_gain_when_cap_leg_is_sold():
    values = {
        "pv_money_market_income_aud": 10.0,
        "pv_hedge_gain_aud": 0.0,
        "pv_hedge_option_fair_value_costs_aud": 3.0,
        "pv_hedge_option_markup_costs_aud": 0.1,
        "pv_hedge_management_fee_costs_aud": 0.2,
        "pv_hedge_execution_costs_aud": 0.3,
        "pv_hedge_costs_aud": 3.6,
    }
    summary = {
        "absolute_portfolio_values_available": False,
        **{f"normalised_average_{key}": value for key, value in values.items()},
    }
    _validate_hedge_summary(summary, "benchmark", "sold")

    summary["normalised_average_pv_hedge_costs_aud"] = 3.7
    with pytest.raises(ValueError, match="do not reconcile"):
        _validate_hedge_summary(summary, "benchmark", "sold")

    summary["normalised_average_pv_hedge_costs_aud"] = 3.6
    summary["normalised_average_pv_hedge_gain_aud"] = 1.0
    with pytest.raises(ValueError, match="cap leg is sold"):
        _validate_hedge_summary(summary, "benchmark", "sold")
    _validate_hedge_summary(summary, "benchmark", "not_sold")


def test_rate_directory_is_stable():
    assert _rate_directory_name(0.04) == "cap_4pct"
    assert _rate_directory_name(0.125) == "cap_12p5pct"


def test_required_outputs_use_compact_factor_benchmark_directories():
    scenario = Path("scenario-output")

    required = _required_scenario_outputs(
        scenario,
        include_dynamic=False,
    )

    assert scenario / "bench" / "v00" / "portfolio_summary.csv" in required
    assert scenario / "bench" / "v01" / "portfolio_summary.csv" in required
    assert scenario / "bench" / "v10" / "portfolio_summary.csv" in required
    assert not any("continue_benchmark" in str(path) for path in required)


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
