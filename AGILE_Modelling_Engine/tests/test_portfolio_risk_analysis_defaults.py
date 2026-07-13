"""Static contracts for the portfolio-risk runner's default scope."""

from pathlib import Path

from portfolio_simulations import run_portfolio_risk_analysis as risk_runner

from portfolio_simulations.run_portfolio_risk_analysis import (
    DEFAULT_BEHAVIOUR_MODELS,
    DEFAULT_RISK_SCOPE,
    DEFAULT_STRESS_SCENARIOS,
    ScenarioJob,
    STRESS_DEFINITIONS,
    _dynamic_command,
    _execute_scenario_job,
    _lsmc_command,
    parse_args,
)


def test_default_risk_scope_is_lapse_interest_and_longevity_only():
    args = parse_args([])

    assert DEFAULT_RISK_SCOPE == ("lapse", "interest_rate", "longevity")
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
    lsmc = _lsmc_command(args, 0.06, Path("lsmc"))

    assert DEFAULT_BEHAVIOUR_MODELS == ("dynamic_functions", "lsmc")
    assert dynamic[dynamic.index("--income-election-mode") + 1] == "dynamic"
    assert dynamic[dynamic.index("--post-income-behaviour") + 1] == "dynamic"
    assert "--no-dynamic-benchmark" in lsmc


def test_scenario_job_runs_dynamic_then_factor_benchmarks_then_lsmc(
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
        dynamic_benchmark_commands=(("v00",), ("v01",), ("v10",)),
        lsmc_command=("lsmc",),
        reuse=False,
    )

    _execute_scenario_job(job, blas_threads=1)

    assert [command for command, _output, _threads in calls] == [
        ("dynamic",),
        ("v00",),
        ("v01",),
        ("v10",),
        ("lsmc",),
    ]
