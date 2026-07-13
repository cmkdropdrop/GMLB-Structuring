"""Static contracts for the portfolio-risk runner's default scope."""

from datetime import datetime, timezone
from pathlib import Path

from portfolio_simulations import run_portfolio_risk_analysis as risk_runner

from portfolio_simulations.run_portfolio_risk_analysis import (
    DEFAULT_BEHAVIOUR_MODELS,
    DEFAULT_CREDITING_CAP_RATES,
    DEFAULT_MAX_WORKERS,
    DEFAULT_RISK_SCOPE,
    DEFAULT_STRESS_SCENARIOS,
    ScenarioJob,
    STRESS_DEFINITIONS,
    _create_timestamped_run_directory,
    _dynamic_benchmark_commands,
    _dynamic_command,
    _execute_scenario_job,
    _lsmc_command,
    parse_args,
)


def test_reduced_default_is_one_base_cap_behaviour_analysis_only():
    args = parse_args([])

    assert DEFAULT_CREDITING_CAP_RATES == (0.06,)
    assert args.crediting_rates == [0.06]
    assert args.baseline_rate == 0.06
    assert DEFAULT_MAX_WORKERS == 1
    assert args.max_workers == 1
    assert args.no_stress_analysis is True
    assert args.no_plots is True
    assert args.scenario_plots is False
    assert DEFAULT_RISK_SCOPE == ("lapse",)
    assert DEFAULT_STRESS_SCENARIOS == (
        "interest_up",
        "interest_down",
        "longevity",
    )
    assert tuple(args.stress_scenarios) == DEFAULT_STRESS_SCENARIOS
    assert args.hedge_cap_leg_mode == "sold"
    assert {
        STRESS_DEFINITIONS[stress_id]["risk_category"]
        for stress_id in DEFAULT_STRESS_SCENARIOS
    } == {"interest_rate", "longevity"}


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
    assert dynamic_benchmarks == ()
    assert "--no-dynamic-benchmark" in lsmc
    assert "--no-factorial-benchmarks" in lsmc
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
