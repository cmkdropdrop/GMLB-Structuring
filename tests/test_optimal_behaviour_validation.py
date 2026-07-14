from __future__ import annotations

import numpy as np
import pytest

from policy_engine.optimal_behaviour_validation import (
    build_validation_result,
    paired_noninferiority_gate,
    select_deployed_policy,
)


def test_paired_gate_uses_best_benchmark_and_common_path_standard_error():
    policy = np.array([101.0, 103.0, 99.0, 105.0])
    benchmarks = {
        "weak": np.array([90.0, 90.0, 90.0, 90.0]),
        "best": np.array([100.0, 102.0, 98.0, 104.0]),
    }
    gate = paired_noninferiority_gate(
        policy,
        benchmarks,
        premium_aud=100_000.0,
        component="combined",
    )
    assert gate.benchmark_name == "best"
    assert gate.paired_difference_mean_aud == pytest.approx(1.0)
    assert gate.paired_standard_error_aud == pytest.approx(0.0)
    assert gate.noninferiority_margin_aud == pytest.approx(10.0)
    assert gate.valid


def test_paired_gate_rejects_material_underperformance():
    gate = paired_noninferiority_gate(
        np.full(8, 80.0),
        {"continue": np.full(8, 100.0)},
        premium_aud=100_000.0,
        component="income_action_only",
    )
    assert not gate.valid
    assert gate.lower_confidence_bound_95_aud == pytest.approx(-20.0)


def test_validation_result_requires_every_component_gate():
    good = paired_noninferiority_gate(
        np.full(4, 101.0),
        {"continue": np.full(4, 100.0)},
        premium_aud=10_000.0,
        component="election_only",
    )
    bad = paired_noninferiority_gate(
        np.full(4, 80.0),
        {"continue": np.full(4, 100.0)},
        premium_aud=10_000.0,
        component="combined",
    )
    result = build_validation_result(
        scenario_fingerprint="validation-sample",
        gates=(good, bad),
        benchmark_path_values_aud={"continue": np.full(4, 100.0)},
    )
    assert not result.valid
    assert len(result.rows()) == 2


def test_validation_rejects_mismatched_or_nonfinite_paths():
    with pytest.raises(ValueError, match="identical paths"):
        paired_noninferiority_gate(
            np.ones(4),
            {"continue": np.ones(3)},
            premium_aud=1_000.0,
            component="combined",
        )
    with pytest.raises(ValueError, match="finite"):
        paired_noninferiority_gate(
            np.array([1.0, np.nan]),
            {"continue": np.ones(2)},
            premium_aud=1_000.0,
            component="combined",
        )


def test_failed_combined_gate_selects_the_recorded_fixed_baseline():
    gate = paired_noninferiority_gate(
        np.full(8, 80.0),
        {"year_5|continue_only": np.full(8, 100.0)},
        premium_aud=100_000.0,
        component="combined_policy",
    )
    result = build_validation_result(
        scenario_fingerprint="validation-sample",
        gates=(gate,),
        benchmark_path_values_aud={
            "year_5|continue_only": np.full(8, 100.0)
        },
    )

    selection = select_deployed_policy(result)

    assert selection.candidate_policy_name == "V11"
    assert selection.selected_policy_name == "year_5|continue_only"
    assert selection.fallback_reason == "combined_noninferiority_gate_failed"
    assert not selection.candidate_valid


def test_failed_component_gate_rejects_v11_even_if_combined_gate_passes():
    bad_lapse = paired_noninferiority_gate(
        np.full(8, 80.0),
        {"continue_only": np.full(8, 100.0)},
        premium_aud=100_000.0,
        component="income_action_only",
    )
    good_combined = paired_noninferiority_gate(
        np.full(8, 101.0),
        {"year_5|continue_only": np.full(8, 100.0)},
        premium_aud=100_000.0,
        component="combined_policy",
    )
    result = build_validation_result(
        scenario_fingerprint="validation-sample",
        gates=(bad_lapse, good_combined),
        benchmark_path_values_aud={
            "year_5|continue_only": np.full(8, 100.0)
        },
    )

    selection = select_deployed_policy(result)

    assert selection.selected_policy_name == "year_5|continue_only"
    assert selection.fallback_reason == (
        "component_noninferiority_gate_failed:income_action_only"
    )
    assert not selection.candidate_valid
