"""Compact output-layout and Windows path-length contracts."""

from pathlib import Path

import pytest

from portfolio_simulations._run_layout import (
    behaviour_benchmark_directories,
)
from portfolio_simulations.run_portfolio_risk_analysis import (
    ScenarioJob,
    _expected_job_artifact_paths,
    _validate_output_path_lengths,
)


def _job(root: Path) -> ScenarioJob:
    return ScenarioJob(
        sequence=1,
        stress_id="interest_down",
        rate=0.06,
        dynamic_output=root / "dynamic_behaviour",
        lsmc_output=root / "lsmc_fitted_lower_bound",
        dynamic_command=(),
        dynamic_benchmark_commands=(),
        lsmc_command=(),
        reuse=False,
    )


def test_behaviour_benchmark_directories_use_compact_factor_ids():
    root = Path("scenario")

    assert behaviour_benchmark_directories(root) == {
        "deterministic_election_continue": root / "bench" / "v00",
        "deterministic_election_post_behaviour": root / "bench" / "v01",
        "variable_election_continue": root / "bench" / "v10",
    }


def test_path_preflight_includes_reconciliation_and_optional_plot_paths():
    job = _job(Path("scenario"))

    without_plots = _expected_job_artifact_paths(job, include_plots=False)
    with_plots = _expected_job_artifact_paths(job, include_plots=True)

    assert all(
        path.name == "portfolio_aggregation_reconciliation.csv"
        for path in without_plots
    )
    assert len(with_plots) > len(without_plots)
    assert any(
        path.name == "03_model_point_profitability_heatmaps.png"
        for path in with_plots
    )


def test_path_preflight_rejects_overlong_output_before_child_runs():
    job = _job(Path("x" * 240))

    with pytest.raises(ValueError, match="shorter --output path"):
        _validate_output_path_lengths(
            [job],
            include_plots=True,
            max_path_chars=259,
        )
