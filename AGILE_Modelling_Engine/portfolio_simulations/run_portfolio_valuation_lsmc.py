"""Run the generic portfolio valuation with combined LSMC behaviour.

The market, product, mortality, cost, model-point and aggregation mechanics are
the same as in ``run_portfolio_valuation.py``.  An independently trained,
phase-aware annual-grid LSMC lower-bound policy maximises the risk-neutral
value of Policyholder cashflows over ``WAIT | START_INCOME_NOW`` in Growth and
``CONTINUE | FULL_WITHDRAWAL`` in Income.  The frozen policy is evaluated from
contract inception on independent paths by the unchanged monthly cashflow
projector.  The model-point ``income_start_year`` is retained only for explicit
deterministic validation benchmarks.  A paired dynamic-behaviour benchmark is
produced on the same evaluation scenarios by default.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import shutil
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence

import numpy as np

if __package__:
    from ._run_layout import behaviour_benchmark_directories
else:
    from _run_layout import behaviour_benchmark_directories


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
    HedgeCapLegMode,
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
    OptimalBehaviourLSMCSettings,
    OptimalBehaviourPolicy,
    OptimalBehaviourPolicyFit,
    fit_optimal_behaviour_policy,
    no_voluntary_action_behaviour,
)
from agile_engine.portfolio_stresses import (  # noqa: E402
    PORTFOLIO_STRESS_CHOICES,
    apply_portfolio_input_stress,
    get_portfolio_stress,
    portfolio_scenario_transform,
)
from agile_engine.pricing import build_scenarios, resolve_horizon  # noqa: E402
from agile_engine.product import PolicySpec  # noqa: E402

from run_portfolio_valuation import (  # noqa: E402
    _as_float,
    _build_aggregation_reconciliation,
    _configure_logging,
    _create_plots,
    _make_progress_callback,
    _validate_hedge_backing_summary,
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
    parser.add_argument(
        "--take-up-seed",
        type=int,
        default=97,
        help="out-of-sample common-random-number seed for Election",
    )
    parser.add_argument(
        "--mortality-seed",
        type=int,
        default=197,
        help="out-of-sample pathwise Joint-Life mortality seed",
    )
    parser.add_argument("--n-train", type=int, default=4_000,
                        help="independent LSMC training paths")
    parser.add_argument("--train-seed", type=int, default=12026)
    parser.add_argument(
        "--train-take-up-seed",
        type=int,
        default=10097,
        help="independent Election seed recorded for the LSMC training basis",
    )
    parser.add_argument(
        "--train-mortality-seed",
        type=int,
        default=10197,
        help="independent pathwise Joint-Life mortality seed for LSMC training",
    )
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument(
        "--hedge-cap-leg-mode",
        choices=tuple(mode.value for mode in HedgeCapLegMode),
        default=HedgeCapLegMode.SOLD.value,
        help=(
            "sold uses the standard capped call spread; not_sold buys the "
            "uncapped call and retains the payoff above the customer cap"
        ),
    )
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
        help="conservative Election and Full-Withdrawal advantage screen",
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
    seed_names = (
        "seed",
        "take_up_seed",
        "mortality_seed",
        "train_seed",
        "train_take_up_seed",
        "train_mortality_seed",
    )
    if any(getattr(args, name) < 0 for name in seed_names):
        parser.error("all seeds must be non-negative")
    if args.seed == args.train_seed:
        parser.error("--seed and --train-seed must differ for out-of-sample LSMC")
    if args.take_up_seed == args.train_take_up_seed:
        parser.error(
            "--take-up-seed and --train-take-up-seed must differ"
        )
    if args.mortality_seed == args.train_mortality_seed:
        parser.error(
            "--mortality-seed and --train-mortality-seed must differ"
        )
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
    """Identify a combined-policy fit without the legacy benchmark start year."""
    return (
        float(policy.age),
        policy.sex.value,
        policy.funding_source.value,
        float(policy.initial_investment),
        policy.income_type.value,
        bool(policy.spouse),
        None if policy.spouse_age is None else float(policy.spouse_age),
        None if policy.spouse_sex is None else policy.spouse_sex.value,
        policy.spouse_death_election.value,
        float(policy.commencement_year),
        bool(policy.age_pension_plus),
        (
            None
            if policy.condition_of_release_year is None
            else float(policy.condition_of_release_year)
        ),
        (
            None
            if policy.aps_life_expectancy is None
            else float(policy.aps_life_expectancy)
        ),
        float(policy.upfront_adviser_fee_pct),
        float(policy.bonus_interest_pct),
    )


def _fresh_policy(fit: OptimalBehaviourPolicyFit) -> OptimalBehaviourPolicy:
    """Clone a frozen fit while isolating per-rollout action statistics."""
    surrender = replace(
        fit.policy.surrender_policy,
        evaluation_statistics={},
    )
    return replace(
        fit.policy,
        surrender_policy=surrender,
        evaluation_statistics={},
    )


class _ElectionOnlyPolicy:
    """Deploy the fitted Election rule while suppressing Income surrender."""

    anniversary_only = True

    def __init__(self, combined: OptimalBehaviourPolicy) -> None:
        self.combined = combined
        self.provenance_fingerprint = (
            f"election_only:{combined.provenance_fingerprint}"
        )

    def start_income_mask(self, *, context: object) -> np.ndarray:
        return self.combined.start_income_mask(context=context)

    @staticmethod
    def surrender_mask(*, context: object) -> np.ndarray:
        n_paths = int(getattr(context, "n_paths"))
        return np.zeros(n_paths, dtype=bool)


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


def _behaviour_decomposition_rows(
    deterministic_continue: Mapping[str, object],
    deterministic_surrender: Mapping[str, object],
    election_continue: Mapping[str, object],
    combined: Mapping[str, object],
) -> list[dict[str, object]]:
    """Return the exact 2x2 rollout decomposition for numeric summary metrics.

    ``election_continue`` deploys the Election rule learned by the common fit
    and suppresses surrender only during this diagnostic evaluation.  It is a
    frozen-policy counterfactual, not a second fit optimised under Continue.
    """
    preferred = [
        key for key in combined
        if key.startswith("normalised_average_")
        or key.startswith("portfolio_total_")
        or key in {
            "new_business_margin_before_risk_margin",
            "premium_weighted_identity_gap",
        }
    ]
    rows: list[dict[str, object]] = []
    for key in sorted(preferred):
        v00 = _as_float(deterministic_continue.get(key))
        v01 = _as_float(deterministic_surrender.get(key))
        v10 = _as_float(election_continue.get(key))
        v11 = _as_float(combined.get(key))
        if any(value is None for value in (v00, v01, v10, v11)):
            continue
        assert v00 is not None and v01 is not None
        assert v10 is not None and v11 is not None
        timing = v10 - v00
        post_election = v01 - v00
        interaction = v11 - v10 - v01 + v00
        rows.append({
            "metric": key,
            "deterministic_election_continue_v00": v00,
            "deterministic_election_fitted_surrender_v01": v01,
            "fitted_election_continue_v10": v10,
            "combined_policy_v11": v11,
            "income_election_timing_effect_v10_minus_v00": timing,
            "post_election_behaviour_effect_v01_minus_v00": post_election,
            "interaction_effect": interaction,
            "reconciled_combined_minus_baseline": (
                timing + post_election + interaction
            ),
            "direct_combined_minus_baseline": v11 - v00,
            "election_counterfactual_is_refit_under_continue": False,
        })
    return rows


def _income_election_distribution_rows(
    summary: Mapping[str, object],
) -> list[dict[str, object]]:
    """Flatten contract-weighted annual Election diagnostics from a summary."""
    root = "normalised_average_income_election_event_mass_policy_year_"
    years = sorted(
        int(key[len(root):])
        for key in summary
        if key.startswith(root)
    )
    rows: list[dict[str, object]] = []
    for year in years:
        suffix = f"policy_year_{year}"
        rows.append({
            "policy_year": year,
            "weighting_basis": "normalised_contract_weight_then_path_mean",
            "eligible_growth_exposure": summary.get(
                f"normalised_average_eligible_growth_exposure_{suffix}"
            ),
            "income_election_event_mass": summary.get(
                f"normalised_average_income_election_event_mass_{suffix}"
            ),
            "forced_income_election_event_mass": summary.get(
                f"normalised_average_forced_income_election_event_mass_{suffix}"
            ),
            "income_election_share": summary.get(
                f"normalised_average_income_election_share_{suffix}"
            ),
            "annual_take_up_probability": summary.get(
                f"normalised_average_annual_take_up_probability_{suffix}"
            ),
            "mean_growth_exposure": summary.get(
                f"normalised_average_mean_growth_exposure_{suffix}"
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
        "Der LSMC-Hauptlauf optimiert auf zulässigen Policy Anniversaries "
        "WAIT gegen START_INCOME_NOW und danach CONTINUE gegen FULL_WITHDRAWAL. "
        "Der Modellpunkttermin bleibt ausschließlich ein separat ausgewiesener "
        "deterministischer Validierungsbenchmark; Growth-Surrender und "
        "Growth-Withdrawals bleiben vertraglich ausgeschlossen.",
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
        if args.no_dynamic_benchmark:
            stale_dynamic = (output / "dynamic_benchmark").resolve()
            if stale_dynamic.parent != output:
                raise RuntimeError("Unsafe stale Dynamic-output path.")
            if stale_dynamic.is_dir():
                shutil.rmtree(stale_dynamic)
            for name in (
                "comparison_summary.csv",
                "model_point_comparison.csv",
                "comparison_report.md",
            ):
                stale_file = (output / name).resolve()
                if stale_file.parent != output:
                    raise RuntimeError("Unsafe stale comparison-output path.")
                if stale_file.is_file():
                    stale_file.unlink()
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
        portfolio_projection = ProjectionConfig(
            record_paths=False,
            heston_cos=False,
            take_up_seed=args.take_up_seed,
            mortality_seed=args.mortality_seed,
            force_pathwise_joint_life=True,
            hedge_cap_leg_mode=HedgeCapLegMode(args.hedge_cap_leg_mode),
        )
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
            dynamic_behaviour = behaviour_assumptions.behaviour
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
            projection=replace(
                costs.projection,
                record_paths=False,
                heston_cos=False,
                take_up_seed=args.take_up_seed,
                mortality_seed=args.mortality_seed,
            ),
            real_world_model="hull_white_bs",
        )
        horizon_basis = replace(evaluation_settings, horizon_years=None)
        common_horizon = max(
            resolve_horizon(horizon_basis, point.policy)
            for point in model_points.model_points
        )
        training_projection = replace(
            costs.projection,
            record_paths=True,
            heston_cos=False,
            take_up_seed=args.train_take_up_seed,
            mortality_seed=args.train_mortality_seed,
        )
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

        fits: dict[tuple[object, ...], OptimalBehaviourPolicyFit] = {}

        def ensure_fit(policy_object: object) -> OptimalBehaviourPolicyFit:
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
                fits[key] = fit_optimal_behaviour_policy(
                    costs.product,
                    policy_object,
                    training_scenarios,
                    mortality,
                    expenses=stressed_expenses,
                    projection_config=training_projection,
                    settings=lsmc_settings,
                    fit_basis_inputs={
                        "stress_scenario": stress_audit,
                        "crediting_cap_rate": (
                            costs.product.reference_fund.effective_maximum_return
                        ),
                    },
                )
            return fits[key]

        deployed_policies: dict[
            tuple[object, ...], OptimalBehaviourPolicy
        ] = {}
        election_only_policies: dict[
            tuple[object, ...], _ElectionOnlyPolicy
        ] = {}
        deterministic_surrender_policies: dict[tuple[object, ...], object] = {}

        def combined_policy_factory(policy_object: object) -> object:
            if not isinstance(policy_object, PolicySpec):
                raise TypeError("LSMC policy factory requires PolicySpec.")
            key = _policy_signature(policy_object)
            if key not in deployed_policies:
                deployed_policies[key] = _fresh_policy(ensure_fit(policy_object))
            return deployed_policies[key]

        def election_only_policy_factory(policy_object: object) -> object:
            if not isinstance(policy_object, PolicySpec):
                raise TypeError("LSMC policy factory requires PolicySpec.")
            key = _policy_signature(policy_object)
            if key not in election_only_policies:
                election_only_policies[key] = _ElectionOnlyPolicy(
                    _fresh_policy(ensure_fit(policy_object))
                )
            return election_only_policies[key]

        def deterministic_surrender_policy_factory(
            policy_object: object,
        ) -> object:
            if not isinstance(policy_object, PolicySpec):
                raise TypeError("LSMC policy factory requires PolicySpec.")
            key = _policy_signature(policy_object)
            if key not in deterministic_surrender_policies:
                deterministic_surrender_policies[key] = _fresh_policy(
                    ensure_fit(policy_object)
                ).surrender_policy
            return deterministic_surrender_policies[key]

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
            "[4/7] Deterministische und kombinierte LSMC-Policies out of sample "
            "im Monatsprojektor bewerten"
        )
        # V00: legacy deterministic model-point Election with no voluntary exit.
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
        # V01: legacy deterministic Election plus the fitted Income rule.
        deterministic_surrender_result = value_policyholder_portfolio(
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
            surrender_policy_factory=deterministic_surrender_policy_factory,
            scenario_transform=scenario_transform,
        )
        # V10: deploy the common fit's Election rule but suppress Income exit
        # only in this counterfactual rollout; no action is reselected OOS.
        election_continue_result = value_policyholder_portfolio(
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
            combined_policy_factory=election_only_policy_factory,
            scenario_transform=scenario_transform,
        )
        # V11: frozen common Bellman policy from contract inception.
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
            combined_policy_factory=combined_policy_factory,
            scenario_transform=scenario_transform,
        )
        evaluation_fingerprints = {
            "continue": continue_result.scenario_fingerprint,
            "deterministic_surrender": (
                deterministic_surrender_result.scenario_fingerprint
            ),
            "election_continue": election_continue_result.scenario_fingerprint,
            "combined_lsmc": lsmc_result.scenario_fingerprint,
        }
        if dynamic_result is not None:
            evaluation_fingerprints["dynamic"] = (
                dynamic_result.scenario_fingerprint
            )
        if len(set(evaluation_fingerprints.values())) != 1:
            raise ValueError(
                "All dynamic, deterministic and LSMC evaluations must share "
                "one common scenario set."
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
            "lsmc_training_take_up_seed": args.train_take_up_seed,
            "lsmc_training_mortality_seed": args.train_mortality_seed,
            "lsmc_evaluation_seed": args.seed,
            "lsmc_evaluation_take_up_seed": args.take_up_seed,
            "lsmc_evaluation_mortality_seed": args.mortality_seed,
            "lsmc_training_scenario_fingerprint": (
                training_scenarios.content_fingerprint),
            "scenario_fingerprint": lsmc_result.scenario_fingerprint,
            "lsmc_fit_basis_fingerprint_count": len(fits),
            "lsmc_election_fallback_policy_count": sum(
                fit.election_fallback_used for fit in fits.values()
            ),
            "lsmc_surrender_fallback_policy_count": sum(
                fit.surrender_fallback_used for fit in fits.values()
            ),
            "lsmc_action_set": (
                "growth:wait|start_income_now;"
                "income:continue|full_withdrawal"
            ),
            "lsmc_income_election": "pathwise_optimal_bellman_policy",
            "income_take_up_mode": "optimal_lsmc",
            "income_take_up_source": "frozen_combined_lsmc_policy",
            "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
            "lsmc_decision_grid": "contractual_policy_anniversaries",
            "lsmc_forced_election_rule": (
                "first_policy_anniversary_strictly_after_attained_age_100"
            ),
            "stress_scenario_id": stress.stress_id,
        })
        _validate_hedge_backing_summary(
            lsmc_summary, args.hedge_cap_leg_mode
        )
        lsmc_rows = lsmc_result.model_point_rows()
        summary_path = output / "portfolio_summary.csv"
        model_point_path = output / "model_point_results.csv"
        reconciliation_path = output / "portfolio_aggregation_reconciliation.csv"
        election_distribution_path = output / "income_election_distribution.csv"
        _write_csv(summary_path, [lsmc_summary])
        _write_csv(model_point_path, lsmc_rows)
        _write_csv(
            reconciliation_path,
            _build_aggregation_reconciliation(lsmc_summary, lsmc_rows),
        )
        _write_csv(
            election_distribution_path,
            _income_election_distribution_rows(lsmc_summary),
        )

        dynamic_outputs: dict[str, str] = {}
        comparison_rows: list[dict[str, object]] = []
        model_point_comparison_rows: list[dict[str, object]] = []
        benchmark_directories = behaviour_benchmark_directories(output)
        continue_dir = benchmark_directories[
            "deterministic_election_continue"
        ]
        continue_summary = continue_result.summary_dict()
        continue_summary.update({
            "stress_scenario_id": stress.stress_id,
            "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
            "scenario_fingerprint": continue_result.scenario_fingerprint,
        })
        _validate_hedge_backing_summary(
            continue_summary, args.hedge_cap_leg_mode
        )
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

        deterministic_surrender_dir = benchmark_directories[
            "deterministic_election_post_behaviour"
        ]
        deterministic_surrender_summary = (
            deterministic_surrender_result.summary_dict()
        )
        deterministic_surrender_summary.update({
            "stress_scenario_id": stress.stress_id,
            "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
            "scenario_fingerprint": (
                deterministic_surrender_result.scenario_fingerprint
            ),
            "benchmark_treatment": (
                "deterministic_model_point_election_with_fitted_"
                "post_election_full_withdrawal"
            ),
            "surrender_rule_refitted_under_deterministic_election": False,
        })
        _validate_hedge_backing_summary(
            deterministic_surrender_summary, args.hedge_cap_leg_mode
        )
        deterministic_surrender_rows = (
            deterministic_surrender_result.model_point_rows()
        )
        deterministic_surrender_summary_path = (
            deterministic_surrender_dir / "portfolio_summary.csv"
        )
        deterministic_surrender_model_point_path = (
            deterministic_surrender_dir / "model_point_results.csv"
        )
        deterministic_surrender_recon_path = (
            deterministic_surrender_dir
            / "portfolio_aggregation_reconciliation.csv"
        )
        _write_csv(
            deterministic_surrender_summary_path,
            [deterministic_surrender_summary],
        )
        _write_csv(
            deterministic_surrender_model_point_path,
            deterministic_surrender_rows,
        )
        _write_csv(
            deterministic_surrender_recon_path,
            _build_aggregation_reconciliation(
                deterministic_surrender_summary,
                deterministic_surrender_rows,
            ),
        )

        election_continue_dir = benchmark_directories[
            "variable_election_continue"
        ]
        election_continue_summary = election_continue_result.summary_dict()
        election_continue_summary.update({
            "stress_scenario_id": stress.stress_id,
            "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
            "scenario_fingerprint": (
                election_continue_result.scenario_fingerprint
            ),
            "benchmark_treatment": (
                "election_rule_from_combined_fit_with_full_withdrawal_"
                "suppressed_in_evaluation"
            ),
            "election_rule_refitted_under_continue": False,
        })
        _validate_hedge_backing_summary(
            election_continue_summary, args.hedge_cap_leg_mode
        )
        election_continue_rows = election_continue_result.model_point_rows()
        election_continue_summary_path = (
            election_continue_dir / "portfolio_summary.csv"
        )
        election_continue_model_point_path = (
            election_continue_dir / "model_point_results.csv"
        )
        election_continue_recon_path = (
            election_continue_dir / "portfolio_aggregation_reconciliation.csv"
        )
        _write_csv(
            election_continue_summary_path,
            [election_continue_summary],
        )
        _write_csv(
            election_continue_model_point_path,
            election_continue_rows,
        )
        _write_csv(
            election_continue_recon_path,
            _build_aggregation_reconciliation(
                election_continue_summary,
                election_continue_rows,
            ),
        )

        decomposition_rows = _behaviour_decomposition_rows(
            continue_summary,
            deterministic_surrender_summary,
            election_continue_summary,
            lsmc_summary,
        )
        decomposition_path = output / "lsmc_behaviour_decomposition.csv"
        _write_csv(decomposition_path, decomposition_rows)

        continue_comparison_rows = _comparison_rows(
            election_continue_summary,
            lsmc_summary,
            benchmark_column="fitted_election_continue_benchmark",
        )
        _write_csv(
            output / "lsmc_vs_continue_summary.csv",
            continue_comparison_rows,
        )
        objective_key = "normalised_average_pv_policyholder_benefits_aud"
        continue_objective = float(election_continue_summary[objective_key])
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
                "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
                "scenario_fingerprint": dynamic_result.scenario_fingerprint,
            })
            _validate_hedge_backing_summary(
                dynamic_summary, args.hedge_cap_leg_mode
            )
            dynamic_rows = dynamic_result.model_point_rows()
            dynamic_summary_path = dynamic_dir / "portfolio_summary.csv"
            dynamic_model_point_path = dynamic_dir / "model_point_results.csv"
            dynamic_recon_path = (
                dynamic_dir / "portfolio_aggregation_reconciliation.csv")
            dynamic_election_distribution_path = (
                dynamic_dir / "income_election_distribution.csv"
            )
            _write_csv(dynamic_summary_path, [dynamic_summary])
            _write_csv(dynamic_model_point_path, dynamic_rows)
            _write_csv(
                dynamic_recon_path,
                _build_aggregation_reconciliation(dynamic_summary, dynamic_rows),
            )
            _write_csv(
                dynamic_election_distribution_path,
                _income_election_distribution_rows(dynamic_summary),
            )
            dynamic_outputs = {
                "portfolio_summary_csv": str(dynamic_summary_path),
                "model_point_results_csv": str(dynamic_model_point_path),
                "aggregation_reconciliation_csv": str(dynamic_recon_path),
                "income_election_distribution_csv": str(
                    dynamic_election_distribution_path
                ),
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
                    "fit_basis_fingerprint": fit.fit_basis_fingerprint,
                    "training_policyholder_value_aud": (
                        fit.training_policyholder_value_aud),
                    "training_wait_policyholder_value_aud": (
                        fit.training_wait_policyholder_value_aud),
                    "training_no_action_policyholder_value_aud": (
                        fit.training_no_action_policyholder_value_aud),
                    "training_candidate_policyholder_value_aud": (
                        fit.training_candidate_policyholder_value_aud),
                    "training_optionality_uplift_aud": (
                        fit.training_optionality_uplift_aud),
                    "training_fallback_used": fit.training_fallback_used,
                    "election_fallback_used": fit.election_fallback_used,
                    "surrender_fallback_used": fit.surrender_fallback_used,
                    **diagnostic.as_dict(),
                })
            policy_action_rows = 0
            deployed = deployed_policies.get(key)
            evaluation_statistics = (
                {} if deployed is None else deployed.evaluation_statistics
            )
            for (action_type, step), stats in sorted(
                evaluation_statistics.items()
            ):
                eligible = stats["eligible_path_count"]
                action_rows.append({
                    "policy_labels": labels,
                    "action_type": action_type,
                    "phase": (
                        "growth"
                        if action_type == "income_election"
                        else "income"
                    ),
                    "policy_year": step // 12,
                    "decision_step": step,
                    **stats,
                    "evaluation_action_rate": (
                        stats["action_path_count"] / eligible
                        if eligible else 0.0
                    ),
                    "training_fallback_used": fit.training_fallback_used,
                    "election_fallback_used": fit.election_fallback_used,
                    "surrender_fallback_used": fit.surrender_fallback_used,
                })
                policy_action_rows += 1
            if policy_action_rows == 0:
                action_rows.append({
                    "policy_labels": labels,
                    "action_type": None,
                    "phase": None,
                    "policy_year": None,
                    "decision_step": None,
                    "eligible_path_count": 0,
                    "action_path_count": 0,
                    "forced_path_count": 0,
                    "evaluation_action_rate": 0.0,
                    "training_fallback_used": fit.training_fallback_used,
                    "election_fallback_used": fit.election_fallback_used,
                    "surrender_fallback_used": fit.surrender_fallback_used,
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

        fit_basis_fingerprints = {
            (
                f"fit_{index:04d}|labels="
                f"{'|'.join(policy_labels.get(key, ['unlabelled']))}"
                f"|policy_signature={key!r}"
            ): fit.fit_basis_fingerprint
            for index, (key, fit) in enumerate(
                sorted(fits.items(), key=lambda item: str(item[0])),
                start=1,
            )
        }
        if len(fit_basis_fingerprints) != len(fits):
            raise RuntimeError(
                "LSMC fit-basis provenance keys are not unique."
            )
        accepted_election_regression_count = sum(
            diagnostic.regression_accepted_for_action
            for fit in fits.values()
            for diagnostic in fit.diagnostics
            if diagnostic.action_type == "income_election"
        )
        accepted_surrender_regression_count = sum(
            diagnostic.regression_accepted_for_action
            for fit in fits.values()
            for diagnostic in fit.diagnostics
            if diagnostic.action_type == "full_withdrawal"
        )
        election_regression_fallback_count = sum(
            not diagnostic.regression_accepted_for_action
            for fit in fits.values()
            for diagnostic in fit.diagnostics
            if diagnostic.action_type == "income_election"
        )
        surrender_regression_fallback_count = sum(
            not diagnostic.regression_accepted_for_action
            for fit in fits.values()
            for diagnostic in fit.diagnostics
            if diagnostic.action_type == "full_withdrawal"
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
                "lsmc_action_set": {
                    "growth": ["wait", "start_income_now"],
                    "income": ["continue", "full_withdrawal"],
                },
                "income_election": "pathwise_optimal_bellman_policy",
                "model_point_income_start_year_use": (
                    "deterministic_validation_benchmarks_only"
                ),
                "decision_frequency": "contractual_policy_anniversaries",
                "earliest_income_election": (
                    "product_min_years_before_income"
                ),
                "forced_income_election": (
                    "first_policy_anniversary_strictly_after_attained_age_100"
                ),
                "first_income_payment": "one_month_after_election",
                "same_step_election_and_full_withdrawal_allowed": False,
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
                "joint_life_election_treatment": (
                    "pathwise_primary_and_spouse_life_status_cohorts"
                ),
                "insurer_backing_asset": (
                    "administrative_crediting_frame_in_stochastic_aud_"
                    "overnight_money_market_account"
                ),
                "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
                "hedge_cap_leg_interpretation": (
                    "short_cap_call_sold"
                    if args.hedge_cap_leg_mode == HedgeCapLegMode.SOLD.value
                    else "cap_call_not_sold_and_excess_payoff_retained"
                ),
                "money_market_accrual": (
                    "pathwise_integrated_short_rate_daily_roll_equivalent_on_"
                    "monthly_cashflow_grid"
                ),
                "customer_liability_uses_performance_fund_as_backing": False,
                "behaviour_benchmarks": {
                    "deterministic_election_continue": "V00",
                    "deterministic_election_post_behaviour": "V01",
                    "variable_election_continue": "V10",
                    "combined_variable_election_post_behaviour": "V11",
                },
            },
            "lsmc_settings": {
                "n_train": args.n_train,
                "train_seed": args.train_seed,
                "train_take_up_seed": args.train_take_up_seed,
                "train_mortality_seed": args.train_mortality_seed,
                "force_pathwise_joint_life": (
                    training_projection.force_pathwise_joint_life
                ),
                "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
                "train_take_up_seed_usage": (
                    "reserved_independent_projector_stream;lsmc_election_is_"
                    "deterministic_given_state_and_cross_fitted_regressions"
                ),
                "training_scenario_fingerprint": (
                    training_scenarios.content_fingerprint),
                "fit_basis_fingerprints": fit_basis_fingerprints,
                "fit_basis_includes": [
                    "training_scenario_content",
                    "crediting_cap",
                    "stress_audit",
                    "product",
                    "policy_with_legacy_benchmark_start_canonicalised",
                    "mortality",
                    "expenses",
                    "projection_config",
                    "lsmc_settings",
                ],
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
                "election_fallback_policy_count": sum(
                    fit.election_fallback_used for fit in fits.values()),
                "surrender_fallback_policy_count": sum(
                    fit.surrender_fallback_used for fit in fits.values()),
                "accepted_election_regression_count": (
                    accepted_election_regression_count
                ),
                "accepted_surrender_regression_count": (
                    accepted_surrender_regression_count
                ),
                "election_regression_fallback_count": (
                    election_regression_fallback_count
                ),
                "surrender_regression_fallback_count": (
                    surrender_regression_fallback_count
                ),
                "out_of_sample_policyholder_value_dominates_continue": (
                    out_of_sample_dominates_continue),
                "out_of_sample_policyholder_value_minus_continue_aud": (
                    lsmc_objective - continue_objective),
            },
            "evaluation_settings": {
                "n_paths": args.n_paths,
                "seed": args.seed,
                "take_up_seed": args.take_up_seed,
                "mortality_seed": args.mortality_seed,
                "force_pathwise_joint_life": (
                    evaluation_settings.projection.force_pathwise_joint_life
                ),
                "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
                "option_fair_value_markup": (
                    evaluation_settings.projection.option_fair_value_markup
                ),
                "hedge_reference_management_fee": (
                    evaluation_settings.projection.hedge_reference_management_fee
                ),
                "hedge_vol_spread": (
                    evaluation_settings.projection.hedge_vol_spread
                ),
                "crediting_margin_enabled": (
                    evaluation_settings.projection.crediting_margin_enabled
                ),
                "take_up_seed_usage": (
                    "dynamic_benchmark_crn;combined_lsmc_policy_is_"
                    "deterministic_given_state"
                    if dynamic_result is not None
                    else "not_consumed_without_dynamic_benchmark;combined_"
                    "lsmc_policy_is_deterministic_given_state"
                ),
                "heston_substeps": args.heston_substeps,
                "scenario_horizon_years": lsmc_result.scenario_horizon_years,
                "scenario_fingerprint": lsmc_result.scenario_fingerprint,
                "dynamic_benchmark_same_scenarios": (
                    None if dynamic_result is None else True),
                "continue_benchmark_same_scenarios": True,
                "deterministic_election_benchmarks_same_scenarios": True,
                "training_and_evaluation_market_seeds_distinct": (
                    args.train_seed != args.seed
                ),
                "training_and_evaluation_take_up_seeds_distinct": (
                    args.train_take_up_seed != args.take_up_seed
                ),
                "training_and_evaluation_mortality_seeds_distinct": (
                    args.train_mortality_seed != args.mortality_seed
                ),
                "common_random_numbers_across_behaviour_rollouts": True,
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
                "The fitted-Election/Continue decomposition rollout suppresses "
                "Income surrender after fitting; its Election rule is not "
                "separately re-optimised under a Continue-only terminal policy.",
                "The deterministic-Election/fitted-surrender decomposition "
                "rollout deploys the Income rule from the combined fit; it is "
                "not separately re-fitted under deterministic Election.",
            ],
            "outputs": {
                "portfolio_summary_csv": str(summary_path),
                "model_point_results_csv": str(model_point_path),
                "aggregation_reconciliation_csv": str(reconciliation_path),
                "income_election_distribution_csv": str(
                    election_distribution_path
                ),
                "comparison_summary_csv": (
                    str(output / "comparison_summary.csv")
                    if comparison_rows else None),
                "model_point_comparison_csv": (
                    str(output / "model_point_comparison.csv")
                    if model_point_comparison_rows else None),
                "comparison_report_markdown": (
                    str(output / "comparison_report.md")
                    if comparison_rows else None
                ),
                "lsmc_regression_diagnostics_csv": str(
                    output / "lsmc_regression_diagnostics.csv"),
                "lsmc_action_summary_csv": str(
                    output / "lsmc_action_summary.csv"),
                "lsmc_vs_continue_summary_csv": str(
                    output / "lsmc_vs_continue_summary.csv"),
                "continue_benchmark": {
                    "semantics": (
                        "election_rule_from_combined_fit_with_"
                        "full_withdrawal_suppressed_in_evaluation"
                    ),
                    "portfolio_summary_csv": str(
                        election_continue_summary_path
                    ),
                    "model_point_results_csv": str(
                        election_continue_model_point_path
                    ),
                    "aggregation_reconciliation_csv": str(
                        election_continue_recon_path
                    ),
                },
                "deterministic_election_continue_benchmark": {
                    "portfolio_summary_csv": str(continue_summary_path),
                    "model_point_results_csv": str(continue_model_point_path),
                    "aggregation_reconciliation_csv": str(continue_recon_path),
                },
                "deterministic_election_post_behaviour_benchmark": {
                    "portfolio_summary_csv": str(
                        deterministic_surrender_summary_path
                    ),
                    "model_point_results_csv": str(
                        deterministic_surrender_model_point_path
                    ),
                    "aggregation_reconciliation_csv": str(
                        deterministic_surrender_recon_path
                    ),
                },
                "behaviour_decomposition_csv": str(decomposition_path),
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
