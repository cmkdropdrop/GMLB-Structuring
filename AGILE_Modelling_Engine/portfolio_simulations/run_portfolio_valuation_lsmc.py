"""Run the generic portfolio valuation with LSMC-optimal Income surrender.

The market, product, mortality, cost, model-point and aggregation mechanics are
the same as in ``run_portfolio_valuation.py``.  The model-point Income Election
remains deterministic.  CSV-based Income lapse and Excess Withdrawal are
replaced by an independently trained annual-grid LSMC lower-bound policy that
maximises the risk-neutral value of policyholder cashflows over Continue versus
Full Withdrawal.  The frozen policy is evaluated out of sample by the
unchanged monthly projection engine.  A paired dynamic-behaviour benchmark is
produced on the same evaluation scenarios by default.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence


ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from agile_engine import (  # noqa: E402
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DEFAULT_MODEL_PARAMETERS_PATH,
    DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
    FeeSpec,
    IndexLinkedLifetimeIncomeProduct,
    MortalityTable,
    ProjectionConfig,
    ReferenceFundSpec,
    ValuationSettings,
    __version__ as ENGINE_VERSION,
    load_cost_assumptions,
    load_dynamic_behaviour_assumptions,
    load_market_assumptions,
    load_policyholder_model_points,
    value_policyholder_portfolio,
)
from agile_engine.esg import Measure  # noqa: E402
from agile_engine.optimal_behaviour_lsmc import (  # noqa: E402
    OptimalBehaviourLSMCFit,
    OptimalBehaviourLSMCSettings,
    fit_optimal_surrender_policy,
    no_voluntary_action_behaviour,
)
from agile_engine.portfolio_stresses import (  # noqa: E402
    PORTFOLIO_STRESS_CHOICES,
    apply_portfolio_input_stress,
    get_portfolio_stress,
    portfolio_scenario_transform,
)
from agile_engine.pricing import build_scenarios, resolve_horizon  # noqa: E402
from agile_engine.product import PolicySpec, SpouseDeathElection  # noqa: E402

from run_portfolio_valuation import (  # noqa: E402
    _as_float,
    _build_aggregation_reconciliation,
    _configure_logging,
    _create_plots,
    _make_progress_callback,
    _write_csv,
)


DEFAULT_OUTPUT_DIRECTORY = (
    Path(__file__).resolve().parent / "output" / "portfolio_valuation_lsmc"
)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-points", type=Path,
                        default=DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH)
    parser.add_argument("--cost-assumptions", type=Path,
                        default=DEFAULT_COST_ASSUMPTIONS_PATH)
    parser.add_argument("--cost-assumption-set", default=None)
    parser.add_argument("--dynamic-behaviour", type=Path,
                        default=DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
                        help="used only for the dynamic benchmark and provenance")
    parser.add_argument("--behaviour-assumption-set", default=None)
    parser.add_argument("--zero-curve", type=Path,
                        default=DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH)
    parser.add_argument("--model-parameters", type=Path,
                        default=DEFAULT_MODEL_PARAMETERS_PATH)
    parser.add_argument("--n-paths", type=int, default=2_000,
                        help="independent out-of-sample evaluation paths")
    parser.add_argument("--seed", type=int, default=2026,
                        help="out-of-sample evaluation seed")
    parser.add_argument("--n-train", type=int, default=4_000,
                        help="independent LSMC training paths")
    parser.add_argument("--train-seed", type=int, default=12026)
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument(
        "--stress-scenario",
        choices=PORTFOLIO_STRESS_CHOICES,
        default="base",
        help="shared stress applied to LSMC training and all evaluations",
    )
    parser.add_argument("--lsmc-folds", type=int, default=5)
    parser.add_argument("--lsmc-ridge", type=float, default=1.0e-6)
    parser.add_argument(
        "--exercise-buffer-rmse-multiplier",
        type=float,
        default=0.25,
        help="optional conservative Full-Withdrawal advantage screen",
    )
    parser.add_argument("--crediting-cap-rate", type=float, default=None)
    parser.add_argument("--portfolio-contract-count", type=float, default=None)
    parser.add_argument("--profitability-materiality-bp", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--no-dynamic-benchmark", action="store_true")
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    parser.add_argument("--log-file", type=Path, default=None)
    args = parser.parse_args(argv)

    for name in ("n_paths", "n_train", "heston_substeps"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.lsmc_folds < 2:
        parser.error("--lsmc-folds must be at least two")
    if args.seed < 0 or args.train_seed < 0:
        parser.error("seeds must be non-negative")
    if args.seed == args.train_seed:
        parser.error("--seed and --train-seed must differ for out-of-sample LSMC")
    if not math.isfinite(args.lsmc_ridge) or args.lsmc_ridge < 0.0:
        parser.error("--lsmc-ridge must be finite and non-negative")
    if (
        not math.isfinite(args.exercise_buffer_rmse_multiplier)
        or args.exercise_buffer_rmse_multiplier < 0.0
    ):
        parser.error("--exercise-buffer-rmse-multiplier must be non-negative")
    if args.crediting_cap_rate is not None and (
        not math.isfinite(args.crediting_cap_rate)
        or not 0.0 <= args.crediting_cap_rate <= 1.0
    ):
        parser.error("--crediting-cap-rate must be between zero and one")
    if args.portfolio_contract_count is not None and (
        not math.isfinite(args.portfolio_contract_count)
        or args.portfolio_contract_count <= 0.0
    ):
        parser.error("--portfolio-contract-count must be positive and finite")
    if (
        not math.isfinite(args.profitability_materiality_bp)
        or args.profitability_materiality_bp < 0.0
    ):
        parser.error("--profitability-materiality-bp must be non-negative")
    return args


def _policy_signature(policy: PolicySpec) -> tuple[object, ...]:
    return (
        float(policy.age),
        policy.sex.value,
        float(policy.initial_investment),
        int(round(policy.income_start_year)),
        policy.income_type.value,
        bool(policy.spouse),
        None if policy.spouse_age is None else float(policy.spouse_age),
        None if policy.spouse_sex is None else policy.spouse_sex.value,
        policy.spouse_death_election.value,
        float(policy.commencement_year),
    )


def _comparison_rows(
    dynamic: Mapping[str, object],
    lsmc: Mapping[str, object],
    *,
    benchmark_column: str = "dynamic_behaviour",
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    preferred = [
        key for key in lsmc
        if key.startswith("normalised_average_")
        or key.startswith("portfolio_total_")
        or key in {
            "new_business_margin_before_risk_margin",
            "premium_weighted_identity_gap",
        }
    ]
    for key in sorted(preferred):
        left = _as_float(dynamic.get(key))
        right = _as_float(lsmc.get(key))
        if left is None or right is None:
            continue
        delta = right - left
        delta_column = (
            "lsmc_minus_dynamic"
            if benchmark_column == "dynamic_behaviour"
            else f"lsmc_minus_{benchmark_column}"
        )
        rows.append({
            "metric": key,
            benchmark_column: left,
            "lsmc_optimal_behaviour": right,
            delta_column: delta,
            "relative_delta": (
                delta / left if not math.isclose(left, 0.0, abs_tol=1.0e-16)
                else None
            ),
        })
    return rows


def _model_point_comparison_rows(
    dynamic_rows: list[dict[str, object]],
    lsmc_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    dynamic_by_id = {str(row["model_point_id"]): row for row in dynamic_rows}
    output: list[dict[str, object]] = []
    for row in lsmc_rows:
        model_point_id = str(row["model_point_id"])
        baseline = dynamic_by_id[model_point_id]
        for metric in sorted(
            key for key in row
            if key.startswith("per_contract_")
        ):
            left = _as_float(baseline.get(metric))
            right = _as_float(row.get(metric))
            if left is None or right is None:
                continue
            output.append({
                "model_point_id": model_point_id,
                "metric": metric,
                "dynamic_behaviour": left,
                "lsmc_optimal_behaviour": right,
                "lsmc_minus_dynamic": right - left,
            })
    return output


def _write_comparison_report(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    wanted = (
        "normalised_average_pv_policyholder_benefits_aud",
        "normalised_average_pv_future_fees_aud",
        "normalised_average_pv_guarantee_claims_aud",
        "normalised_average_bel_total_aud",
        "normalised_average_insurer_net_present_value_before_risk_margin_aud",
        "new_business_margin_before_risk_margin",
    )
    by_metric = {str(row["metric"]): row for row in rows}
    lines = [
        "# Vergleich Dynamic Behaviour vs. LSMC Optimal Behaviour",
        "",
        "Positive Deltas bedeuten `LSMC - Dynamic`. Geldwerte sind AUD je ",
        "normalisiertem repräsentativem Vertrag, sofern keine absolute ",
        "Bestandsgröße vorgegeben wurde.",
        "",
        "| Kennzahl | Dynamic | LSMC | Delta |",
        "|---|---:|---:|---:|",
    ]
    for metric in wanted:
        row = by_metric.get(metric)
        if row is None:
            continue
        lines.append(
            f"| {metric} | {float(row['dynamic_behaviour']):,.6f} | "
            f"{float(row['lsmc_optimal_behaviour']):,.6f} | "
            f"{float(row['lsmc_minus_dynamic']):,.6f} |"
        )
    lines.extend([
        "",
        "Der LSMC-Lauf behält den deterministischen Income-Start des "
        "Modellpunkts bei. Optimiert wird die jährliche Entscheidung Continue "
        "gegen Full Withdrawal; Growth-Aktionen bleiben verboten.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    logger, log_path = _configure_logging(output, args.log_file, args.log_level)
    started = time.perf_counter()

    try:
        logger.info("[1/7] LSMC-Portfoliolauf gestartet | Output: %s", output)
        stress = get_portfolio_stress(args.stress_scenario)
        stress_audit = stress.audit_dict(
            applied_to_training=True,
            applied_to_evaluation=True,
        )
        logger.info(
            "Stress-Szenario | %s | %s | Training und Evaluation",
            stress.stress_id,
            stress.label,
        )
        market = load_market_assumptions(args.zero_curve, args.model_parameters)
        generic_base_product = IndexLinkedLifetimeIncomeProduct(
            reference_fund=ReferenceFundSpec(
                scenario_maximum_return=args.crediting_cap_rate),
            fees=FeeSpec(lip_waived_in_income_phase_if_aps=False),
            dividend_yield={
                index: parameters.dividend_yield
                for index, parameters in market.esg.equity.items()
            },
        )
        portfolio_projection = ProjectionConfig(record_paths=False, heston_cos=False)
        costs = load_cost_assumptions(
            args.cost_assumptions,
            assumption_set_id=args.cost_assumption_set,
            value_basis="base",
            product=generic_base_product,
            projection=portfolio_projection,
        )
        behaviour_assumptions = None
        dynamic_behaviour = None
        if not args.no_dynamic_benchmark:
            behaviour_assumptions = load_dynamic_behaviour_assumptions(
                args.dynamic_behaviour,
                assumption_set_id=args.behaviour_assumption_set,
                value_basis="base",
            )
            dynamic_behaviour = replace(
                behaviour_assumptions.behaviour,
                take_up=replace(
                    behaviour_assumptions.behaviour.take_up,
                    mode="deterministic",
                ),
            )
        lsmc_behaviour = no_voluntary_action_behaviour(dynamic_behaviour)
        model_points = load_policyholder_model_points(
            args.model_points,
            expected_market_parameter_set_id=market.parameter_set_id,
            expected_yield_curve_id=market.curve_id,
        )
        mortality = MortalityTable.gompertz_makeham()
        stressed_esg, mortality, stressed_expenses = apply_portfolio_input_stress(
            stress,
            market.esg,
            mortality,
            costs.expenses,
        )
        scenario_transform = portfolio_scenario_transform(stress)
        evaluation_settings = ValuationSettings(
            model="heston_hull_white",
            n_paths=args.n_paths,
            seed=args.seed,
            heston_substeps=args.heston_substeps,
            horizon_years=None,
            projection=costs.projection,
            real_world_model="hull_white_bs",
        )
        horizon_basis = replace(evaluation_settings, horizon_years=None)
        common_horizon = max(
            resolve_horizon(horizon_basis, point.policy)
            for point in model_points.model_points
        )
        training_projection = replace(
            costs.projection, record_paths=True, heston_cos=False)
        training_settings = ValuationSettings(
            model="heston_hull_white",
            n_paths=args.n_train,
            seed=args.train_seed,
            heston_substeps=args.heston_substeps,
            horizon_years=common_horizon,
            projection=training_projection,
            real_world_model="hull_white_bs",
        )
        logger.info(
            "[2/7] Unabhängige LSMC-Trainingspfade erzeugen | paths=%d | "
            "seed=%d | horizon=%.1f",
            args.n_train, args.train_seed, common_horizon,
        )
        training_scenarios = build_scenarios(
            stressed_esg,
            training_settings,
            measure=Measure.RISK_NEUTRAL,
            horizon_years=common_horizon,
        )
        if scenario_transform is not None:
            training_scenarios = scenario_transform(training_scenarios)
        lsmc_settings = OptimalBehaviourLSMCSettings(
            ridge=args.lsmc_ridge,
            n_folds=args.lsmc_folds,
            exercise_buffer_rmse_multiplier=args.exercise_buffer_rmse_multiplier,
        )

        policy_labels: dict[tuple[object, ...], list[str]] = {}
        for point in model_points.model_points:
            policy_labels.setdefault(_policy_signature(point.policy), []).append(
                point.model_point_id)
            if point.policy.spouse:
                fallback = replace(
                    point.policy,
                    spouse=False,
                    spouse_age=None,
                    spouse_sex=None,
                    spouse_death_election=SpouseDeathElection.CONTINUE_INCOME,
                )
                policy_labels.setdefault(_policy_signature(fallback), []).append(
                    f"{point.model_point_id}:single_fallback")

        fits: dict[tuple[object, ...], OptimalBehaviourLSMCFit] = {}

        def surrender_policy_factory(policy_object: object):
            if not isinstance(policy_object, PolicySpec):
                raise TypeError("LSMC policy factory requires PolicySpec.")
            key = _policy_signature(policy_object)
            if key not in fits:
                labels = ",".join(policy_labels.get(key, ["unlabelled"]))
                logger.info(
                    "LSMC-Fit | %s | age=%.0f | premium=%.0f | spouse=%s",
                    labels, policy_object.age, policy_object.initial_investment,
                    policy_object.spouse,
                )
                fits[key] = fit_optimal_surrender_policy(
                    costs.product,
                    policy_object,
                    training_scenarios,
                    mortality,
                    expenses=stressed_expenses,
                    projection_config=training_projection,
                    settings=lsmc_settings,
                )
            return fits[key].policy

        dynamic_result = None
        if not args.no_dynamic_benchmark:
            if dynamic_behaviour is None:
                raise ValueError("Dynamic benchmark behaviour was not loaded.")
            logger.info(
                "[3/7] Dynamic-Behaviour-Benchmark auf Evaluationspfaden | "
                "paths=%d | seed=%d",
                args.n_paths, args.seed,
            )
            dynamic_result = value_policyholder_portfolio(
                costs.product,
                model_points,
                stressed_esg,
                mortality,
                dynamic_behaviour,
                stressed_expenses,
                settings=evaluation_settings,
                portfolio_contract_count=args.portfolio_contract_count,
                profitability_materiality_bp=args.profitability_materiality_bp,
                progress_callback=_make_progress_callback(logger),
                scenario_transform=scenario_transform,
            )
        else:
            logger.info("[3/7] Dynamic-Behaviour-Benchmark deaktiviert")

        logger.info(
            "[4/7] Zulässigen Continue-Benchmark und LSMC-Policy out of sample "
            "im Monatsprojektor bewerten"
        )
        continue_result = value_policyholder_portfolio(
            costs.product,
            model_points,
            stressed_esg,
            mortality,
            lsmc_behaviour,
            stressed_expenses,
            settings=evaluation_settings,
            portfolio_contract_count=args.portfolio_contract_count,
            profitability_materiality_bp=args.profitability_materiality_bp,
            progress_callback=_make_progress_callback(logger),
            scenario_transform=scenario_transform,
        )
        lsmc_result = value_policyholder_portfolio(
            costs.product,
            model_points,
            stressed_esg,
            mortality,
            lsmc_behaviour,
            stressed_expenses,
            settings=evaluation_settings,
            portfolio_contract_count=args.portfolio_contract_count,
            profitability_materiality_bp=args.profitability_materiality_bp,
            progress_callback=_make_progress_callback(logger),
            surrender_policy_factory=surrender_policy_factory,
            scenario_transform=scenario_transform,
        )
        if dynamic_result is not None and (
            dynamic_result.scenario_fingerprint != lsmc_result.scenario_fingerprint
        ):
            raise ValueError(
                "Dynamic and LSMC evaluations do not share the same scenario set."
            )
        if continue_result.scenario_fingerprint != lsmc_result.scenario_fingerprint:
            raise ValueError(
                "Continue and LSMC evaluations do not share the same scenario set."
            )
        if training_scenarios.content_fingerprint == lsmc_result.scenario_fingerprint:
            raise ValueError("Training and evaluation scenario sets must be independent.")

        logger.info("[5/7] Vollständige Ergebnisse und Vergleiche schreiben")
        lsmc_summary = lsmc_result.summary_dict()
        lsmc_summary.update({
            "valuation_as_of_date": market.curve_metadata["as_of_date"],
            "valuation_currency": market.curve_metadata["currency"],
            "market_parameter_set_id": market.parameter_set_id,
            "yield_curve_id": market.curve_id,
            "cost_assumption_set_id": costs.assumption_set_id,
            "behaviour_assumption_set_id": None,
            "lsmc_training_paths": args.n_train,
            "lsmc_training_seed": args.train_seed,
            "lsmc_training_scenario_fingerprint": (
                training_scenarios.content_fingerprint),
            "lsmc_action_set": "continue|full_withdrawal",
            "lsmc_income_election": "deterministic_model_point_date",
            "lsmc_decision_grid": "annual_policy_anniversary_lower_bound",
            "stress_scenario_id": stress.stress_id,
        })
        lsmc_rows = lsmc_result.model_point_rows()
        summary_path = output / "portfolio_summary.csv"
        model_point_path = output / "model_point_results.csv"
        reconciliation_path = output / "portfolio_aggregation_reconciliation.csv"
        _write_csv(summary_path, [lsmc_summary])
        _write_csv(model_point_path, lsmc_rows)
        _write_csv(
            reconciliation_path,
            _build_aggregation_reconciliation(lsmc_summary, lsmc_rows),
        )

        dynamic_outputs: dict[str, str] = {}
        comparison_rows: list[dict[str, object]] = []
        model_point_comparison_rows: list[dict[str, object]] = []
        continue_dir = output / "continue_benchmark"
        continue_summary = continue_result.summary_dict()
        continue_summary["stress_scenario_id"] = stress.stress_id
        continue_rows = continue_result.model_point_rows()
        continue_summary_path = continue_dir / "portfolio_summary.csv"
        continue_model_point_path = continue_dir / "model_point_results.csv"
        continue_recon_path = (
            continue_dir / "portfolio_aggregation_reconciliation.csv")
        _write_csv(continue_summary_path, [continue_summary])
        _write_csv(continue_model_point_path, continue_rows)
        _write_csv(
            continue_recon_path,
            _build_aggregation_reconciliation(continue_summary, continue_rows),
        )
        continue_comparison_rows = _comparison_rows(
            continue_summary,
            lsmc_summary,
            benchmark_column="continue_benchmark",
        )
        _write_csv(
            output / "lsmc_vs_continue_summary.csv",
            continue_comparison_rows,
        )
        objective_key = "normalised_average_pv_policyholder_benefits_aud"
        continue_objective = float(continue_summary[objective_key])
        lsmc_objective = float(lsmc_summary[objective_key])
        out_of_sample_dominates_continue = lsmc_objective >= continue_objective
        if not out_of_sample_dominates_continue:
            logger.warning(
                "Die eingefrorene LSMC-Policy unterschreitet out of sample den "
                "Continue-Benchmark um AUD %.6f je repräsentativem Vertrag; "
                "der Lauf bleibt zur Diagnose unverändert und wählt nicht auf "
                "den Evaluationspfaden nach.",
                continue_objective - lsmc_objective,
            )
        if dynamic_result is not None:
            dynamic_dir = output / "dynamic_benchmark"
            dynamic_summary = dynamic_result.summary_dict()
            dynamic_summary.update({
                "valuation_as_of_date": market.curve_metadata["as_of_date"],
                "valuation_currency": market.curve_metadata["currency"],
                "market_parameter_set_id": market.parameter_set_id,
                "yield_curve_id": market.curve_id,
                "cost_assumption_set_id": costs.assumption_set_id,
                "behaviour_assumption_set_id": behaviour_assumptions.assumption_set_id,
                "stress_scenario_id": stress.stress_id,
            })
            dynamic_rows = dynamic_result.model_point_rows()
            dynamic_summary_path = dynamic_dir / "portfolio_summary.csv"
            dynamic_model_point_path = dynamic_dir / "model_point_results.csv"
            dynamic_recon_path = (
                dynamic_dir / "portfolio_aggregation_reconciliation.csv")
            _write_csv(dynamic_summary_path, [dynamic_summary])
            _write_csv(dynamic_model_point_path, dynamic_rows)
            _write_csv(
                dynamic_recon_path,
                _build_aggregation_reconciliation(dynamic_summary, dynamic_rows),
            )
            dynamic_outputs = {
                "portfolio_summary_csv": str(dynamic_summary_path),
                "model_point_results_csv": str(dynamic_model_point_path),
                "aggregation_reconciliation_csv": str(dynamic_recon_path),
            }
            comparison_rows = _comparison_rows(dynamic_summary, lsmc_summary)
            model_point_comparison_rows = _model_point_comparison_rows(
                dynamic_rows, lsmc_rows)
            _write_csv(output / "comparison_summary.csv", comparison_rows)
            _write_csv(
                output / "model_point_comparison.csv",
                model_point_comparison_rows,
            )
            _write_comparison_report(
                output / "comparison_report.md", comparison_rows)

        diagnostic_rows: list[dict[str, object]] = []
        action_rows: list[dict[str, object]] = []
        for key, fit in fits.items():
            labels = "|".join(policy_labels.get(key, ["unlabelled"]))
            for diagnostic in fit.diagnostics:
                diagnostic_rows.append({
                    "policy_labels": labels,
                    "training_scenario_fingerprint": (
                        fit.training_scenario_fingerprint),
                    "training_policyholder_value_aud": (
                        fit.training_policyholder_value_aud),
                    "training_no_action_policyholder_value_aud": (
                        fit.training_no_action_policyholder_value_aud),
                    "training_candidate_policyholder_value_aud": (
                        fit.training_candidate_policyholder_value_aud),
                    "training_optionality_uplift_aud": (
                        fit.training_optionality_uplift_aud),
                    "training_fallback_used": fit.training_fallback_used,
                    **diagnostic.as_dict(),
                })
            policy_action_rows = 0
            for step, stats in sorted(fit.policy.evaluation_statistics.items()):
                eligible = stats["eligible_path_count"]
                action_rows.append({
                    "policy_labels": labels,
                    "policy_year": step // 12,
                    "decision_step": step,
                    **stats,
                    "evaluation_exercise_rate": (
                        stats["exercise_path_count"] / eligible
                        if eligible else 0.0
                    ),
                    "training_fallback_used": fit.training_fallback_used,
                })
                policy_action_rows += 1
            if policy_action_rows == 0:
                action_rows.append({
                    "policy_labels": labels,
                    "policy_year": None,
                    "decision_step": None,
                    "eligible_path_count": 0,
                    "exercise_path_count": 0,
                    "evaluation_exercise_rate": 0.0,
                    "training_fallback_used": fit.training_fallback_used,
                })
        _write_csv(output / "lsmc_regression_diagnostics.csv", diagnostic_rows)
        _write_csv(output / "lsmc_action_summary.csv", action_rows)

        figure_paths: dict[str, str] = {}
        matplotlib_version: Optional[str] = None
        if args.no_plots:
            logger.info("[6/7] Grafiken deaktiviert")
        else:
            logger.info("[6/7] LSMC-Portfolio-Grafiken erstellen")
            figure_paths, matplotlib_version = _create_plots(
                lsmc_summary,
                lsmc_rows,
                output / "figures",
                absolute=bool(lsmc_summary.get(
                    "absolute_portfolio_values_available")),
                include_fair_fee_plot=False,
                logger=logger,
            )

        logger.info("[7/7] Run-Manifest schreiben")
        manifest_path = output / "run_manifest.json"
        manifest = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "runtime_seconds": time.perf_counter() - started,
            "engine_version": ENGINE_VERSION,
            "stress_scenario": stress_audit,
            "method": {
                "product": "generic_index_linked_lifetime_income_case_study",
                "valuation_measure": "risk_neutral",
                "market_model": "heston_hull_white",
                "simulation": "plain_monte_carlo",
                "lsmc_used": True,
                "lsmc_objective": "maximise_policyholder_cashflow_pv",
                "lsmc_action_set": ["continue", "full_withdrawal"],
                "income_election": "deterministic_effective_model_point_date",
                "decision_frequency": "annual_policy_anniversary",
                "policy_characterisation": (
                    "conservative_lower_bound_on_annual_exercise_grid"),
                "partial_withdrawal_reduction": (
                    "dominated_convex_combination_of_continue_and_full_withdrawal"
                ),
                "growth_surrender_allowed": False,
                "growth_withdrawal_allowed": False,
                "out_of_sample_monthly_projector_rollout": True,
                "dynamic_behaviour_used_for_lsmc": False,
                "dynamic_behaviour_used_for_benchmark": (
                    dynamic_result is not None),
            },
            "lsmc_settings": {
                "n_train": args.n_train,
                "train_seed": args.train_seed,
                "training_scenario_fingerprint": (
                    training_scenarios.content_fingerprint),
                "n_folds": args.lsmc_folds,
                "ridge": args.lsmc_ridge,
                "exercise_buffer_rmse_multiplier": (
                    args.exercise_buffer_rmse_multiplier),
                "maximum_condition_number": (
                    lsmc_settings.maximum_condition_number),
                "fallback_to_no_action_if_training_underperforms": (
                    lsmc_settings.fallback_to_no_action_if_training_underperforms),
                "unique_policy_fits": len(fits),
                "training_fallback_policy_count": sum(
                    fit.training_fallback_used for fit in fits.values()),
                "out_of_sample_policyholder_value_dominates_continue": (
                    out_of_sample_dominates_continue),
                "out_of_sample_policyholder_value_minus_continue_aud": (
                    lsmc_objective - continue_objective),
            },
            "evaluation_settings": {
                "n_paths": args.n_paths,
                "seed": args.seed,
                "heston_substeps": args.heston_substeps,
                "scenario_horizon_years": lsmc_result.scenario_horizon_years,
                "scenario_fingerprint": lsmc_result.scenario_fingerprint,
                "dynamic_benchmark_same_scenarios": (
                    None if dynamic_result is None else True),
                "continue_benchmark_same_scenarios": True,
            },
            "sources": {
                "model_points": model_points.source_metadata(),
                "market": market.source_metadata(),
                "costs": costs.source_metadata(),
                "dynamic_behaviour_benchmark_only": (
                    None
                    if behaviour_assumptions is None
                    else behaviour_assumptions.source_metadata()),
            },
            "model_limitations": [
                "Research valuation gross of reinsurance.",
                "Mortality is illustrative and not an approved production basis.",
                "Income Election remains the deterministic model-point product input.",
                "Optimal behaviour is an annual LSMC lower-bound policy on an "
                "independent evaluation sample.",
                "The annual exercise grid is coarser than the monthly Full-"
                "Withdrawal event grid in the cashflow projector.",
                "Partial withdrawal is removed from the optimal action grid "
                "because proportional AV and Locked-Income reduction makes it a "
                "convex combination of Continue and Full Withdrawal for this "
                "generic non-APS design.",
                "The five-year government-bond sleeve, monthly 50/50 rebalancing, "
                "absence of bond term premium and other fixed proxy assumptions "
                "remain unchanged from the dynamic benchmark.",
            ],
            "outputs": {
                "portfolio_summary_csv": str(summary_path),
                "model_point_results_csv": str(model_point_path),
                "aggregation_reconciliation_csv": str(reconciliation_path),
                "comparison_summary_csv": (
                    str(output / "comparison_summary.csv")
                    if comparison_rows else None),
                "model_point_comparison_csv": (
                    str(output / "model_point_comparison.csv")
                    if model_point_comparison_rows else None),
                "lsmc_regression_diagnostics_csv": str(
                    output / "lsmc_regression_diagnostics.csv"),
                "lsmc_action_summary_csv": str(
                    output / "lsmc_action_summary.csv"),
                "lsmc_vs_continue_summary_csv": str(
                    output / "lsmc_vs_continue_summary.csv"),
                "continue_benchmark": {
                    "portfolio_summary_csv": str(continue_summary_path),
                    "model_point_results_csv": str(continue_model_point_path),
                    "aggregation_reconciliation_csv": str(continue_recon_path),
                },
                "dynamic_benchmark": dynamic_outputs,
                "figures": figure_paths,
                "log": str(log_path),
            },
            "reporting": {"matplotlib_version": matplotlib_version},
            "summary": lsmc_summary,
        }
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True,
                      allow_nan=False, default=str)
            handle.write("\n")

        logger.info(
            "LSMC-Lauf abgeschlossen | fits=%d | runtime=%.1fs | summary=%s",
            len(fits), time.perf_counter() - started, summary_path,
        )
        return 0
    except Exception:
        logger.exception("LSMC-Portfoliolauf fehlgeschlagen")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
