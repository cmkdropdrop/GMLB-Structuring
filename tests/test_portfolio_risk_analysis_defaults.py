"""Static contracts for the portfolio-risk runner's default scope."""

import csv
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

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
    STRESS_DELTA_METRICS,
    _build_stress_loss_rows,
    _cache_market_stress_id,
    _cache_precompute_jobs,
    _csm_components,
    _create_timestamped_run_directory,
    _dynamic_benchmark_commands,
    _dynamic_command,
    _execute_scenario_job,
    _estimate_horizon_months,
    _lsmc_command,
    _lsmc_deployment_plot_label,
    _lsmc_diagnostic_metrics,
    _normalised_action_tokens,
    _run_cache_precompute_jobs,
    _validate_dynamic_cache_metadata,
    _validate_lsmc_cache_metadata,
    parse_args,
)


def test_lsmc_plot_label_identifies_direct_single_sample_v11():
    rows = [{"lsmc_deployed_policy": "V11"} for _ in range(2)]

    assert _lsmc_deployment_plot_label(rows) == (
        "Direct single-sample customer LSMC (direct V11)"
    )


def _lsmc_diagnostic_fixture(
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    action_rows = [
        {
            "training_seed_index": 1,
            "primary_training_seed": True,
            "action_type": "income_election",
            "eligible_path_count": 100,
            "action_path_count": 50,
            "forced_path_count": 0,
        },
        {
            "training_seed_index": 1,
            "primary_training_seed": True,
            "action_type": "full_withdrawal",
            "eligible_path_count": 80,
            "action_path_count": 0,
            "forced_path_count": 0,
        },
    ]
    diagnostic_rows = [
        {
            "action_type": "income_election",
            "oof_r_squared": 0.1,
            "oof_rmse_aud": 100.0,
            "condition_number": 10.0,
            "regression_accepted_for_action": True,
        },
        {
            "action_type": "full_withdrawal",
            "oof_r_squared": 0.2,
            "oof_rmse_aud": 80.0,
            "condition_number": 8.0,
            "regression_accepted_for_action": True,
        },
    ]
    manifest = {
        "lsmc_settings": {
            "training_seed_count": 1,
            "allow_partial_withdrawal": False,
            "unique_policy_fits": 1,
            "training_fallback_policy_count": 0,
        },
    }
    return action_rows, diagnostic_rows, manifest


def test_lsmc_diagnostics_cover_both_direct_actions_without_fallback():
    action_rows, diagnostic_rows, manifest = _lsmc_diagnostic_fixture()

    metrics = _lsmc_diagnostic_metrics(
        action_rows,
        diagnostic_rows,
        manifest,
    )

    assert metrics["surrender_regression_count"] == 1
    assert metrics["surrender_regression_accepted_count"] == 1
    assert metrics["full_withdrawal_eligible_path_count"] == 80
    assert metrics["training_fallback_policy_count"] == 0


def test_lsmc_diagnostics_require_all_direct_actions():
    action_rows, diagnostic_rows, manifest = _lsmc_diagnostic_fixture()
    diagnostic_rows = diagnostic_rows[:1]

    with pytest.raises(
        ValueError,
        match="diagnostics do not cover every enabled optimal action",
    ):
        _lsmc_diagnostic_metrics(action_rows, diagnostic_rows, manifest)


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


def test_default_uses_single_model_point_fast_proxy():
    with DEFAULT_MODEL_POINTS_PATH.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert [row["model_point_id"] for row in rows] == ["ALT4-01"]
    assert sum(float(row["contract_weight"]) for row in rows) == pytest.approx(
        1.0
    )
    assert sum(
        float(row["premium_volume_weight"]) for row in rows
    ) == pytest.approx(1.0)


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


def test_mc_conditional_rejects_unsold_cap_leg_before_execution():
    with pytest.raises(SystemExit):
        parse_args(["--hedge-cap-leg-mode", "not_sold"])


def test_unsold_cap_leg_requires_explicit_moment_matched_proxy():
    args = parse_args([
        "--hedge-pricing-method",
        "moment_matched_bs",
        "--hedge-cap-leg-mode",
        "not_sold",
    ])
    assert args.hedge_cap_leg_mode == "not_sold"
    assert args.require_market_cache is True
    assert args.require_hedge_cache is False


def test_removed_reuse_existing_option_is_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--reuse-existing"])


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
    assert "--training-seed-count" not in lsmc
    assert "--n-paths" not in lsmc
    assert "--n-validation" not in lsmc
    assert lsmc[lsmc.index("--lsmc-income-action-set") + 1] == (
        "continue_full"
    )
    assert lsmc[lsmc.index("--model-points") + 1] == str(
        DEFAULT_MODEL_POINTS_PATH.resolve()
    )
    assert "--train-seed-2" not in lsmc
    assert "--train-seed-3" not in lsmc
    assert dynamic[dynamic.index("--n-paths") + 1] == str(args.n_train)
    assert dynamic[dynamic.index("--seed") + 1] == str(args.train_seed)
    assert lsmc[lsmc.index("--n-train") + 1] == str(args.n_train)
    assert lsmc[lsmc.index("--train-seed") + 1] == str(args.train_seed)


def test_alternate_model_parameters_propagate_to_all_cache_and_valuation_calls(
    tmp_path,
):
    alternate_parameters = (
        risk_runner.DEFAULT_MARKET_DATA_DIRECTORY
        / "model_parameters_constant_equity_vol_low_rate_vol_sensitivity.csv"
    ).resolve()
    args = parse_args([
        "--model-parameters",
        str(alternate_parameters),
    ])

    dynamic = _dynamic_command(args, 0.06, tmp_path / "dynamic")
    lsmc = _lsmc_command(args, 0.06, tmp_path / "lsmc")
    precompute_jobs = _cache_precompute_jobs(
        args,
        (_scenario_job(1, "base", 0.06),),
        horizon_years=53.0,
        output=tmp_path,
    )

    for command in (
        dynamic,
        lsmc,
        *(list(job.command) for job in precompute_jobs),
    ):
        assert command[command.index("--model-parameters") + 1] == str(
            alternate_parameters
        )


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
            _scenario_job(5, "interest_down", 0.06),
        ),
        horizon_years=53.0,
        output=tmp_path,
    )

    assert _cache_market_stress_id("longevity") == "base"
    assert _cache_market_stress_id("expense") == "base"
    assert _cache_market_stress_id("interest_up") == "interest_up"
    assert len(jobs) == 3
    assert [(job.market_stress, job.sample_role) for job in jobs] == [
        ("base", "training_and_valuation"),
        ("interest_up", "training_and_valuation"),
        ("interest_down", "training_and_valuation"),
    ]
    for job in jobs:
        command = list(job.command)
        assert command[1] == str(Q_CACHE_PRECOMPUTE_RUNNER)
        assert command[command.index("--horizon-years") + 1] == "53"
        expected_cap = "0.06" if job.market_stress == "interest_down" else "0.04"
        assert command[command.index("--cap-grid") + 1] == expected_cap
        assert "--market-only" not in command


def test_multiple_training_seed_mode_is_rejected():
    with pytest.raises(SystemExit):
        parse_args(["--training-seed-count", "3"])


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

    assert len(jobs) == 1
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


def test_horizon_estimator_uses_shared_policy_engine_resolver(monkeypatch):
    policies = [object(), object()]
    monkeypatch.setattr(
        risk_runner,
        "load_policyholder_model_points",
        lambda _path: SimpleNamespace(
            model_points=[
                SimpleNamespace(policy=policy) for policy in policies
            ]
        ),
    )
    calls = []

    def resolve(settings, policy):
        calls.append((settings, policy))
        return 12.0 if policy is policies[0] else 14.5

    monkeypatch.setattr(risk_runner, "resolve_horizon", resolve)

    months, source = _estimate_horizon_months(Path("model_points.csv"))

    assert months == 174
    assert source.startswith("policy_engine.resolve_horizon:")
    assert [policy for _settings, policy in calls] == policies
    assert all(settings.horizon_years is None for settings, _policy in calls)


def test_canonical_csm_components_reconcile_to_legacy_npv():
    components = _csm_components(
        {
            "pv_future_fees_aud": 100.0,
            "pv_crediting_margin_aud": 30.0,
            "pv_mva_retained_aud": 4.0,
            "pv_aps_retained_aud": 1.0,
            "pv_guarantee_claims_aud": 20.0,
            "pv_expenses_aud": 10.0,
            "pv_hedge_costs_aud": 5.0,
            "insurer_net_present_value_before_risk_margin_aud": 100.0,
        },
        label="test",
    )

    assert components == {
        "csm_aud": 100.0,
        "csm_pv_fee_income_aud": 100.0,
        "csm_pv_other_income_aud": 35.0,
        "csm_pv_claims_aud": 20.0,
        "csm_pv_costs_aud": 15.0,
        "csm_reconciliation_gap_aud": 0.0,
    }


def test_stress_output_uses_canonical_csm_loss_and_deployed_policy_fields():
    def scenario(stress_id, dynamic_csm, lsmc_csm, fingerprint):
        row = {
            "stress_scenario_id": stress_id,
            "crediting_cap_rate": 0.06,
            "crediting_cap_rate_percent": 6.0,
            "premium_aud": 1_000.0,
            "scenario_fingerprint": fingerprint,
            "lsmc_deployed_policy": "V11",
            "lsmc_policy_selection_mode": "direct_single_sample_expected_pv",
            "lsmc_policyholder_objective_discount_basis": (
                "time_zero_australian_zero_curve_deterministic_v1"
            ),
            "lsmc_oos_validation_used": False,
            "lsmc_oos_evaluation_used": False,
            "lsmc_time0_customer_optionality_uplift_aud": 12.0,
            "lsmc_regression_accepted_share": 0.9,
            "lsmc_training_fallback_policy_share": 0.0,
            "dynamic_scenario_directory": "dynamic",
            "lsmc_scenario_directory": "lsmc",
        }
        for method, csm in (("dynamic", dynamic_csm), ("lsmc", lsmc_csm)):
            for metric in STRESS_DELTA_METRICS:
                row[f"{method}_{metric}"] = 0.0
            row[f"{method}_csm_aud"] = csm
        return row

    rows = _build_stress_loss_rows(
        [scenario("base", 100.0, 90.0, "base")],
        [scenario("longevity", 80.0, 60.0, "stress")],
        0.06,
    )

    assert len(rows) == 1
    result = rows[0]
    assert result["dynamic_signed_csm_stress_loss_aud"] == 20.0
    assert result["lsmc_signed_csm_stress_loss_aud"] == 30.0
    assert result[
        "lsmc_minus_dynamic_signed_csm_stress_loss_aud"
    ] == 10.0
    assert result["lsmc_deployed_policy"] == "V11"
    assert result["lsmc_oos_validation_used"] is False
    assert result["lsmc_signed_stress_loss_aud"] == (
        result["lsmc_signed_csm_stress_loss_aud"]
    )


def _dynamic_cache_fixture(args):
    fingerprint = "evaluation-fingerprint"
    manifest = {
        "method": {
            "hedge_pricing_method": "mc_conditional",
            "market_cache_key": "market-evaluation",
            "scenario_fingerprint": fingerprint,
            "hedge_cache_key": "hedge-evaluation",
            "hedge_price_surface_fingerprint": "surface-evaluation",
            "hedge_training_scenario_fingerprint": fingerprint,
            "hedge_cap_grid": [0.06],
        },
        "portfolio": {"scenario_fingerprint": fingerprint},
        "valuation_settings": {
            "hedge_pricing_method": "mc_conditional",
            "require_market_cache": True,
            "require_hedge_cache": True,
            "market_cache_root": str(args.market_cache_root),
            "hedge_cache_root": str(args.hedge_cache_root),
        },
    }
    summary = {
        "hedge_pricing_method": "mc_conditional",
        "market_cache_key": "market-evaluation",
        "scenario_fingerprint": fingerprint,
        "hedge_cache_key": "hedge-evaluation",
        "hedge_price_surface_fingerprint": "surface-evaluation",
        "hedge_training_scenario_fingerprint": fingerprint,
    }
    return manifest, summary, fingerprint


def test_dynamic_cache_metadata_rejects_tampered_cache_key(tmp_path):
    args = parse_args([
        "--market-cache-root",
        str(tmp_path / "market"),
        "--hedge-cache-root",
        str(tmp_path / "hedge"),
    ])
    manifest, summary, fingerprint = _dynamic_cache_fixture(args)
    manifest["method"]["market_cache_key"] = "wrong-market"

    with pytest.raises(ValueError, match="different market caches"):
        _validate_dynamic_cache_metadata(
            manifest,
            summary,
            args,
            rate=0.06,
            evaluation_fingerprint=fingerprint,
        )


def test_lsmc_cache_metadata_rejects_path_incongruent_hedge(tmp_path):
    args = parse_args([
        "--market-cache-root",
        str(tmp_path / "market"),
        "--hedge-cache-root",
        str(tmp_path / "hedge"),
    ])
    fingerprint = "single-sample-fingerprint"
    manifest = {
        "method": {
            "hedge_pricing_method": "mc_conditional",
            "scenario_fingerprint": fingerprint,
            "market_cache_key": "market-single",
            "hedge_cache_key": "hedge-single",
            "hedge_price_surface_fingerprint": "surface-single",
        },
    }
    summary = {
        "hedge_pricing_method": "mc_conditional",
        "scenario_fingerprint": fingerprint,
        "market_cache_key": "market-single",
        "hedge_cache_key": "hedge-single",
        "hedge_price_surface_fingerprint": "surface-single",
        "hedge_training_scenario_fingerprint": "wrong-fingerprint",
    }

    with pytest.raises(ValueError, match="not path-congruent"):
        _validate_lsmc_cache_metadata(
            manifest,
            summary,
            args,
            rate=0.06,
            scenario_fingerprint=fingerprint,
        )


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
    )

    _execute_scenario_job(job, blas_threads=1)

    assert [command for command, _output, _threads in calls] == [
        ("dynamic",),
        ("lsmc",),
    ]
