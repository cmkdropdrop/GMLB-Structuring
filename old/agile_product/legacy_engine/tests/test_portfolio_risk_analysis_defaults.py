"""Static contracts for the portfolio-risk runner's default scope."""

import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from portfolio_simulations import run_portfolio_risk_analysis as risk_runner

from portfolio_simulations.run_portfolio_risk_analysis import (
    DEFAULT_BEHAVIOUR_MODELS,
    DEFAULT_CREDITING_CAP_RATES,
    DEFAULT_MAX_WORKERS,
    DEFAULT_MODEL_POINTS_PATH,
    DEFAULT_RISK_SCOPE,
    DEFAULT_STRESS_SCENARIOS,
    Q_CACHE_PRECOMPUTE_RUNNER,
    CachePrecomputeJob,
    ScenarioJob,
    STRESS_DEFINITIONS,
    _cache_market_stress_id,
    _cache_precompute_jobs,
    _create_timestamped_run_directory,
    _dynamic_benchmark_commands,
    _dynamic_command,
    _execute_scenario_job,
    _validate_lsmc_gate_set,
    _lsmc_command,
    _normalised_action_tokens,
    _run_cache_precompute_jobs,
    parse_args,
)


def test_lsmc_gate_structure_can_be_checked_when_candidate_falls_back():
    gates = [
        {"component": "election_only", "valid": False},
        {"component": "income_action_only", "valid": True},
        {"component": "combined_policy", "valid": True},
    ]

    with pytest.raises(ValueError, match="invalid validation gate"):
        _validate_lsmc_gate_set(gates, label="candidate")

    _validate_lsmc_gate_set(
        gates,
        label="candidate with fixed fallback",
        require_all_valid=False,
    )


def test_annual_lsmc_action_names_expose_canonical_manifest_actions():
    tokens = _normalised_action_tokens({
        "growth": ["wait_for_one_year", "start_income_now"],
        "income": ["continue_for_one_year", "full_withdrawal_now"],
    })

    assert {"wait", "start_income", "continue", "full_withdrawal"}.issubset(
        tokens
    )


def test_default_is_four_base_cap_v11_behaviour_analysis_only():
    args = parse_args([])

    assert DEFAULT_CREDITING_CAP_RATES == (0.04, 0.06, 0.12, 0.15)
    assert args.crediting_rates == [0.04, 0.06, 0.12, 0.15]
    assert args.baseline_rate == 0.06
    assert DEFAULT_MAX_WORKERS == 1
    assert args.max_workers == 1
    assert args.no_stress_analysis is True
    assert args.no_plots is False
    assert args.scenario_plots is False
    assert args.log_level == "INFO"
    assert args.model_points == DEFAULT_MODEL_POINTS_PATH
    assert DEFAULT_RISK_SCOPE == ("lapse",)
    assert DEFAULT_STRESS_SCENARIOS == (
        "interest_up",
        "interest_down",
        "longevity",
    )
    assert tuple(args.stress_scenarios) == DEFAULT_STRESS_SCENARIOS
    assert args.hedge_cap_leg_mode == "sold"
    assert args.require_market_cache is True
    assert args.require_hedge_cache is True
    assert {
        STRESS_DEFINITIONS[stress_id]["risk_category"]
        for stress_id in DEFAULT_STRESS_SCENARIOS
    } == {"interest_rate", "longevity"}


def test_default_uses_only_first_model_point_of_four_point_proxy():
    with DEFAULT_MODEL_POINTS_PATH.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert [row["model_point_id"] for row in rows] == ["ALT4-01"]
    assert [float(row["contract_weight"]) for row in rows] == [1.0]
    assert [float(row["premium_volume_weight"]) for row in rows] == [1.0]


def test_full_stress_and_plot_outputs_are_explicit_opt_ins():
    args = parse_args(["--stress-analysis", "--plots"])

    assert args.no_stress_analysis is False
    assert args.no_plots is False


def test_each_invocation_gets_a_new_utc_timestamp_directory(tmp_path):
    first_created = datetime(2026, 7, 13, 10, 11, 12, 123456, tzinfo=timezone.utc)
    second_created = datetime(2026, 7, 13, 10, 11, 12, 123457, tzinfo=timezone.utc)

    root_1, output_1, run_id_1, created_utc_1 = (
        _create_timestamped_run_directory(tmp_path, first_created)
    )
    root_2, output_2, run_id_2, created_utc_2 = (
        _create_timestamped_run_directory(tmp_path, second_created)
    )

    assert root_1 == root_2 == tmp_path.resolve()
    assert run_id_1 == "20260713T101112.123456Z"
    assert run_id_2 == "20260713T101112.123457Z"
    assert created_utc_1 == first_created.isoformat()
    assert created_utc_2 == second_created.isoformat()
    assert output_1 == root_1 / run_id_1
    assert output_2 == root_2 / run_id_2
    assert output_1.is_dir()
    assert output_2.is_dir()
    assert output_1 != output_2


def test_non_default_research_stresses_remain_explicitly_available():
    assert {
        "equity_level_down",
        "equity_volatility_up",
        "mortality",
        "expense",
    }.issubset(STRESS_DEFINITIONS)
    assert not set(DEFAULT_STRESS_SCENARIOS).intersection({
        "equity_level_down",
        "equity_volatility_up",
        "mortality",
        "expense",
    })

    args = parse_args([
        "--stress-scenarios",
        "equity_level_down",
        "expense",
    ])
    assert args.stress_scenarios == ["equity_level_down", "expense"]


def test_unsold_cap_leg_is_explicit_opt_in():
    args = parse_args(["--hedge-cap-leg-mode", "not_sold"])
    assert args.hedge_cap_leg_mode == "not_sold"


def test_default_commands_require_dynamic_functions_and_lsmc():
    args = parse_args([])
    dynamic = _dynamic_command(args, 0.06, Path("dynamic"))
    dynamic_benchmarks = _dynamic_benchmark_commands(
        args,
        0.06,
        Path("dynamic"),
        stress_scenario="base",
    )
    lsmc = _lsmc_command(args, 0.06, Path("lsmc"))

    assert DEFAULT_BEHAVIOUR_MODELS == ("dynamic_functions", "lsmc")
    assert dynamic[dynamic.index("--income-election-mode") + 1] == "dynamic"
    assert dynamic[dynamic.index("--post-income-behaviour") + 1] == "dynamic"
    assert dynamic[dynamic.index("--model-points") + 1] == str(
        DEFAULT_MODEL_POINTS_PATH.resolve()
    )
    assert dynamic_benchmarks == ()
    assert "--no-dynamic-benchmark" in lsmc
    assert "--no-factorial-benchmarks" in lsmc
    assert "--require-market-cache" in dynamic
    assert "--require-hedge-cache" in dynamic
    assert "--require-market-cache" in lsmc
    assert "--require-hedge-cache" in lsmc
    assert args.training_seed_count == 1
    assert args.lsmc_income_action_set == "continue_full"
    assert lsmc[lsmc.index("--training-seed-count") + 1] == "1"
    assert lsmc[lsmc.index("--lsmc-income-action-set") + 1] == (
        "continue_full"
    )
    assert lsmc[lsmc.index("--model-points") + 1] == str(
        DEFAULT_MODEL_POINTS_PATH.resolve()
    )
    assert lsmc[lsmc.index("--train-seed-2") + 1] == str(args.train_seed_2)
    assert lsmc[lsmc.index("--train-seed-3") + 1] == str(args.train_seed_3)
    assert len({
        args.train_seed,
        args.train_seed_2,
        args.train_seed_3,
        args.validation_seed,
        args.seed,
    }) == 5
    assert len({
        args.train_take_up_seed,
        args.train_take_up_seed_2,
        args.train_take_up_seed_3,
        args.validation_take_up_seed,
        args.take_up_seed,
    }) == 5
    assert len({
        args.train_mortality_seed,
        args.train_mortality_seed_2,
        args.train_mortality_seed_3,
        args.validation_mortality_seed,
        args.mortality_seed,
    }) == 5


def test_moment_matched_risk_run_still_requires_market_but_not_hedge_cache():
    args = parse_args(["--hedge-pricing-method", "moment_matched_bs"])
    dynamic = _dynamic_command(args, 0.06, Path("dynamic"))
    lsmc = _lsmc_command(args, 0.06, Path("lsmc"))

    assert args.require_market_cache is True
    assert args.require_hedge_cache is False
    assert "--require-market-cache" in dynamic
    assert "--require-market-cache" in lsmc
    assert "--require-hedge-cache" not in dynamic
    assert "--require-hedge-cache" not in lsmc


def _scenario_job(
    sequence: int,
    stress_id: str,
    rate: float,
    *,
    reuse: bool = False,
) -> ScenarioJob:
    return ScenarioJob(
        sequence=sequence,
        stress_id=stress_id,
        rate=rate,
        dynamic_output=Path("scenario") / "dynamic",
        lsmc_output=Path("scenario") / "lsmc",
        dynamic_command=("dynamic",),
        dynamic_benchmark_commands=(),
        lsmc_command=("lsmc",),
        reuse=reuse,
    )


def test_cache_precompute_matrix_deduplicates_non_market_stresses(tmp_path):
    args = parse_args([])
    jobs = _cache_precompute_jobs(
        args,
        (
            _scenario_job(1, "base", 0.04),
            _scenario_job(2, "longevity", 0.04),
            _scenario_job(3, "expense", 0.04),
            _scenario_job(4, "interest_up", 0.04),
            _scenario_job(5, "interest_down", 0.06, reuse=True),
        ),
        horizon_years=53.0,
        output=tmp_path,
    )

    assert _cache_market_stress_id("longevity") == "base"
    assert _cache_market_stress_id("expense") == "base"
    assert _cache_market_stress_id("interest_up") == "interest_up"
    assert len(jobs) == 6
    assert [(job.market_stress, job.sample_role) for job in jobs] == [
        ("base", "evaluation"),
        ("base", "training_1"),
        ("base", "validation"),
        ("interest_up", "evaluation"),
        ("interest_up", "training_1"),
        ("interest_up", "validation"),
    ]
    for job in jobs:
        command = list(job.command)
        assert command[1] == str(Q_CACHE_PRECOMPUTE_RUNNER)
        assert command[command.index("--horizon-years") + 1] == "53"
        assert command[command.index("--cap-grid") + 1] == "0.04"
        assert "--market-only" not in command


def test_three_training_seeds_are_all_precomputed(tmp_path):
    args = parse_args(["--training-seed-count", "3"])
    jobs = _cache_precompute_jobs(
        args,
        (_scenario_job(1, "base", 0.06),),
        horizon_years=53.0,
        output=tmp_path,
    )

    assert [job.sample_role for job in jobs] == [
        "evaluation",
        "training_1",
        "training_2",
        "training_3",
        "validation",
    ]
    assert [job.seed for job in jobs] == [
        args.seed,
        args.train_seed,
        args.train_seed_2,
        args.train_seed_3,
        args.validation_seed,
    ]


def test_moment_matched_precompute_creates_market_cache_only(tmp_path):
    args = parse_args(["--hedge-pricing-method", "moment_matched_bs"])
    jobs = _cache_precompute_jobs(
        args,
        (
            _scenario_job(1, "base", 0.04),
            _scenario_job(2, "base", 0.06),
        ),
        horizon_years=53.0,
        output=tmp_path,
    )

    assert len(jobs) == 3
    assert all("--market-only" in job.command for job in jobs)
    assert all("--cap-grid" not in job.command for job in jobs)


def test_cache_precompute_jobs_run_serially(monkeypatch):
    calls = []

    def record(command, output, *, blas_threads):
        calls.append((command, output, blas_threads))

    monkeypatch.setattr(risk_runner, "_run_logged_command", record)
    jobs = (
        CachePrecomputeJob(
            sequence=1,
            market_stress="base",
            sample_role="evaluation",
            n_paths=10,
            seed=1,
            cap_rate=0.06,
            output=Path("cache") / "evaluation",
            command=("python", "precompute", "--cap-grid", "0.06"),
        ),
        CachePrecomputeJob(
            sequence=2,
            market_stress="base",
            sample_role="training_1",
            n_paths=20,
            seed=2,
            cap_rate=0.06,
            output=Path("cache") / "training",
            command=("python", "precompute", "--cap-grid", "0.06"),
        ),
    )

    _run_cache_precompute_jobs(jobs, blas_threads=1)

    assert [output for _command, output, _threads in calls] == [
        Path("cache") / "evaluation",
        Path("cache") / "training",
    ]


def test_risk_runner_rejects_deprecated_partial_lsmc_action_set():
    with pytest.raises(SystemExit):
        parse_args([
            "--lsmc-income-action-set", "continue_partial_full"
        ])


def test_scenario_job_runs_only_full_dynamic_v11_then_full_lsmc_v11(
    monkeypatch,
):
    calls = []

    def record(command, output, *, blas_threads):
        calls.append((command, output, blas_threads))

    monkeypatch.setattr(risk_runner, "_run_logged_command", record)
    job = ScenarioJob(
        sequence=1,
        stress_id="base",
        rate=0.06,
        dynamic_output=Path("scenario") / "dynamic",
        lsmc_output=Path("scenario") / "lsmc",
        dynamic_command=("dynamic",),
        dynamic_benchmark_commands=(),
        lsmc_command=("lsmc",),
        reuse=False,
    )

    _execute_scenario_job(job, blas_threads=1)

    assert [command for command, _output, _threads in calls] == [
        ("dynamic",),
        ("lsmc",),
    ]
