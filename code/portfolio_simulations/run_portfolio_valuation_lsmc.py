"""Run the generic portfolio valuation with combined LSMC behaviour.

The phase-aware LSMC policy is treated as a time-zero Swing-option exercise
rule.  It maximises the risk-neutral present value of Policyholder cashflows
over annual ``WAIT | START_INCOME_NOW`` decisions in Growth and annual
``CONTINUE | FULL_WITHDRAWAL_NOW`` decisions in Income.  The fit and every
reported rollout use the same exact cached Q-market sample; there is no
validation sample, non-inferiority gate, fixed-policy substitution or held-out
out-of-sample test.  A structurally invalid learned V11 policy fails the run.
The policy fit is mortality-free, while actuarial and CSM rollouts retain the
configured mortality basis.  Partial Withdrawals and under-year voluntary
actions are excluded.
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
from typing import Callable, Mapping, Optional, Sequence

import numpy as np

if __package__:
    from ._mc_analysis_inputs import (
        load_mc_analysis_inputs,
        require_mc_samples,
    )
    from ._run_layout import behaviour_benchmark_directories
else:
    from _mc_analysis_inputs import (
        load_mc_analysis_inputs,
        require_mc_samples,
    )
    from _run_layout import behaviour_benchmark_directories


ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from policy_engine import (  # noqa: E402
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DEFAULT_MODEL_PARAMETERS_PATH,
    DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
    FeeSpec,
    HedgeCapLegMode,
    IncomeActionDecision,
    IncomeActionType,
    IndexLinkedLifetimeIncomeProduct,
    MortalityTable,
    ProjectionConfig,
    ReferenceFundSpec,
    ValuationSettings,
    __version__ as ENGINE_VERSION,
    bind_cached_hedge_prices,
    load_cost_assumptions,
    load_dynamic_behaviour_assumptions,
    load_equity_allocation,
    load_market_assumptions,
    load_policyholder_model_points,
    value_contract,
    value_policyholder_portfolio,
)
from policy_engine.esg import Measure  # noqa: E402
from policy_engine.optimal_behaviour_lsmc import (  # noqa: E402
    POLICYHOLDER_LSMC_MORTALITY_BASIS,
    OptimalBehaviourLSMCSettings,
    OptimalBehaviourPolicy,
    OptimalBehaviourPolicyFit,
    OptimalSurrenderPolicy,
    fit_optimal_behaviour_policy,
    mortality_free_policyholder_basis,
    no_voluntary_action_behaviour,
)
from policy_engine.portfolio_stresses import (  # noqa: E402
    PORTFOLIO_NON_BEHAVIOUR_STRESS_CHOICES,
    apply_portfolio_input_stress,
    get_portfolio_stress,
    portfolio_scenario_transform,
)
from policy_engine.pricing import build_scenarios, resolve_horizon  # noqa: E402
from policy_engine.optimal_behaviour_validation import (  # noqa: E402
    OptimalBehaviourValidationResult,
    paired_noninferiority_gate,
    select_deployed_policy,
)
from policy_engine.product import PolicySpec  # noqa: E402
from policy_engine.repository_paths import (  # noqa: E402
    DEFAULT_FAST_POLICYHOLDER_MODEL_POINTS_PATH,
    Q_HEDGE_PRICE_CACHE_ROOT as DEFAULT_HEDGE_CACHE_ROOT,
    Q_MARKET_PATH_CACHE_ROOT as DEFAULT_MARKET_CACHE_ROOT,
    run_output_directory,
)

if __package__:
    from .run_portfolio_valuation import (  # noqa: E402
        _as_float,
        _build_aggregation_reconciliation,
        _configure_logging,
        _create_plots,
        _make_progress_callback,
        _validate_hedge_backing_summary,
        _write_csv,
    )
else:
    from run_portfolio_valuation import (  # noqa: E402
        _as_float,
        _build_aggregation_reconciliation,
        _configure_logging,
        _create_plots,
        _make_progress_callback,
        _validate_hedge_backing_summary,
        _write_csv,
    )


DEFAULT_OUTPUT_DIRECTORY = run_output_directory("portfolio_valuation_lsmc")
AVAILABLE_LSMC_TRAINING_SEED_SETS = 3


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    supplied_argv = list(sys.argv[1:] if argv is None else argv)
    mc_inputs = load_mc_analysis_inputs()
    training_inputs = require_mc_samples(
        mc_inputs,
        "lsmc_training",
        AVAILABLE_LSMC_TRAINING_SEED_SETS,
    )
    primary_training_input = training_inputs[0]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-points",
        type=Path,
        default=DEFAULT_FAST_POLICYHOLDER_MODEL_POINTS_PATH,
        help="Policyholder model points; defaults to the fast one-point proxy.",
    )
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
    parser.add_argument(
        "--n-paths", type=int, default=primary_training_input.n_paths,
        help="legacy alias; normalised to --n-train",
    )
    parser.add_argument(
        "--seed", type=int, default=primary_training_input.market_seed,
        help="legacy alias; normalised to --train-seed",
    )
    parser.add_argument(
        "--take-up-seed",
        type=int,
        default=primary_training_input.take_up_seed,
        help="legacy alias; normalised to --train-take-up-seed",
    )
    parser.add_argument(
        "--mortality-seed",
        type=int,
        default=primary_training_input.mortality_seed,
        help="legacy alias; normalised to --train-mortality-seed",
    )
    parser.add_argument("--n-train", type=int, default=training_inputs[0].n_paths,
                        help="independent LSMC training paths")
    parser.add_argument(
        "--train-seed", type=int, default=training_inputs[0].market_seed
    )
    parser.add_argument(
        "--train-take-up-seed",
        type=int,
        default=training_inputs[0].take_up_seed,
        help="independent Election seed recorded for the LSMC training basis",
    )
    parser.add_argument(
        "--train-mortality-seed",
        type=int,
        default=training_inputs[0].mortality_seed,
        help="independent pathwise Joint-Life mortality seed for LSMC training",
    )
    parser.add_argument(
        "--train-seed-2",
        type=int,
        default=training_inputs[1].market_seed,
        help="market seed for the second independently validated LSMC fit",
    )
    parser.add_argument(
        "--train-take-up-seed-2",
        type=int,
        default=training_inputs[1].take_up_seed,
        help="Election stream for the second independently validated LSMC fit",
    )
    parser.add_argument(
        "--train-mortality-seed-2",
        type=int,
        default=training_inputs[1].mortality_seed,
        help="mortality stream for the second independently validated LSMC fit",
    )
    parser.add_argument(
        "--train-seed-3",
        type=int,
        default=training_inputs[2].market_seed,
        help="market seed for the third independently validated LSMC fit",
    )
    parser.add_argument(
        "--train-take-up-seed-3",
        type=int,
        default=training_inputs[2].take_up_seed,
        help="Election stream for the third independently validated LSMC fit",
    )
    parser.add_argument(
        "--train-mortality-seed-3",
        type=int,
        default=training_inputs[2].mortality_seed,
        help="mortality stream for the third independently validated LSMC fit",
    )
    parser.add_argument(
        "--training-seed-count",
        type=int,
        choices=(1, 3),
        default=None,
        help=(
            "legacy compatibility flag; the single-sample method always uses 1"
        ),
    )
    parser.add_argument(
        "--n-validation",
        type=int,
        default=primary_training_input.n_paths,
        help="legacy alias; normalised to --n-train (no validation sample)",
    )
    parser.add_argument(
        "--validation-seed", type=int,
        default=primary_training_input.market_seed,
    )
    parser.add_argument(
        "--validation-take-up-seed",
        type=int,
        default=primary_training_input.take_up_seed,
    )
    parser.add_argument(
        "--validation-mortality-seed",
        type=int,
        default=primary_training_input.mortality_seed,
    )
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument(
        "--market-cache-root", type=Path, default=DEFAULT_MARKET_CACHE_ROOT,
    )
    parser.add_argument(
        "--hedge-cache-root", type=Path, default=DEFAULT_HEDGE_CACHE_ROOT,
    )
    parser.add_argument(
        "--hedge-pricing-method",
        choices=("mc_conditional", "moment_matched_bs"),
        default="mc_conditional",
    )
    parser.add_argument(
        "--require-market-cache", action="store_true", default=True,
        help="require every exact Q-market cache used by the LSMC workflow",
    )
    parser.add_argument(
        "--require-hedge-cache", action="store_true", default=True,
        help="require path-congruent hedge caches for mc_conditional pricing",
    )
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
        choices=PORTFOLIO_NON_BEHAVIOUR_STRESS_CHOICES,
        default="base",
        help=(
            "shared non-behaviour stress applied to LSMC training and all "
            "evaluations; statistical lapse-rate stresses are Dynamic-only"
        ),
    )
    parser.add_argument("--lsmc-folds", type=int, default=5)
    parser.add_argument(
        "--lsmc-income-action-set",
        choices=("continue_full", "continue_partial_full"),
        default=None,
        help=(
            "deprecated compatibility flag; the annual combined model accepts "
            "continue_full only"
        ),
    )
    parser.add_argument(
        "--lsmc-ridge",
        type=float,
        choices=(0.0, 1.0e-8, 1.0e-6, 1.0e-4, 1.0e-2),
        default=1.0e-6,
        help=(
            "legacy single-Ridge setting; v4 selection always uses the exact "
            "documented five-value grid"
        ),
    )
    parser.add_argument(
        "--exercise-buffer-rmse-multiplier",
        type=float,
        default=0.25,
        help="conservative buffer for every fitted action advantage",
    )
    parser.add_argument("--crediting-cap-rate", type=float, default=None)
    parser.add_argument("--portfolio-contract-count", type=float, default=None)
    parser.add_argument("--profitability-materiality-bp", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--no-dynamic-benchmark", action="store_true")
    parser.add_argument(
        "--no-factorial-benchmarks",
        action="store_true",
        help=(
            "skip the V00/V01 counterfactual valuation outputs; retain only "
            "V11 and the descriptive same-sample Election/Continue control"
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    parser.add_argument("--log-file", type=Path, default=None)
    args = parser.parse_args(argv)
    args.require_market_cache = True
    args.require_hedge_cache = args.hedge_pricing_method == "mc_conditional"
    legacy_sample_options = (
        "--n-paths",
        "--seed",
        "--take-up-seed",
        "--mortality-seed",
        "--n-validation",
        "--validation-seed",
        "--validation-take-up-seed",
        "--validation-mortality-seed",
        "--training-seed-count",
        "--train-seed-2",
        "--train-take-up-seed-2",
        "--train-mortality-seed-2",
        "--train-seed-3",
        "--train-take-up-seed-3",
        "--train-mortality-seed-3",
    )
    args.legacy_sample_options_ignored = tuple(
        option for option in legacy_sample_options if option in supplied_argv
    )
    # One sample defines the time-zero Swing-option problem.  Legacy sample
    # arguments remain parseable so existing orchestrators fail neither
    # mysteriously nor halfway through a run, but they cannot create an OOS or
    # validation sample.
    args.training_seed_count = 1
    args.n_paths = args.n_train
    args.seed = args.train_seed
    args.take_up_seed = args.train_take_up_seed
    args.mortality_seed = args.train_mortality_seed
    args.n_validation = args.n_train
    args.validation_seed = args.train_seed
    args.validation_take_up_seed = args.train_take_up_seed
    args.validation_mortality_seed = args.train_mortality_seed
    if args.lsmc_income_action_set is None:
        args.lsmc_income_action_set = "continue_full"
    if args.lsmc_income_action_set != "continue_full":
        parser.error(
            "--lsmc-income-action-set=continue_partial_full is no longer "
            "admissible for ordered annual optimal behaviour"
        )

    for name in ("n_train", "heston_substeps"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.lsmc_folds < 2:
        parser.error("--lsmc-folds must be at least two")
    if args.hedge_pricing_method == "mc_conditional" \
            and args.hedge_cap_leg_mode != HedgeCapLegMode.SOLD.value:
        parser.error(
            "mc_conditional supports the standard sold-cap call spread only"
        )
    seed_names = (
        "train_seed",
        "train_take_up_seed",
        "train_mortality_seed",
    )
    if any(getattr(args, name) < 0 for name in seed_names):
        parser.error("training seeds must be non-negative")
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
    """Identify every input that can change a combined-policy fit or anchor."""
    return (
        float(policy.age),
        policy.sex.value,
        policy.funding_source.value,
        float(policy.initial_investment),
        policy.income_type.value,
        bool(policy.spouse),
        (
            None
            if policy.income_start_year is None
            else float(policy.income_start_year)
        ),
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


def _fresh_policy(
    source: OptimalBehaviourPolicyFit | OptimalBehaviourPolicy,
) -> OptimalBehaviourPolicy:
    """Clone a frozen fit while isolating per-rollout action statistics."""
    fitted_policy = source.policy if isinstance(
        source, OptimalBehaviourPolicyFit
    ) else source
    surrender = fitted_policy.surrender_policy
    if isinstance(surrender, OptimalSurrenderPolicy):
        surrender = replace(surrender, evaluation_statistics={})
    return replace(
        fitted_policy,
        surrender_policy=surrender,
        evaluation_statistics={},
    )


def _election_control_policy(
    fit: OptimalBehaviourPolicyFit,
) -> OptimalBehaviourPolicy:
    """Return deployable V10, or its fixed V00 control if V10 is invalid."""
    candidate = fit.policy_variants["V10"]
    if candidate.valid:
        return candidate
    fallback = fit.policy_variants["V00"]
    if not fallback.valid:
        raise RuntimeError("Neither V10 nor its fixed V00 control is valid.")
    return fallback


class _ElectionOnlyPolicy:
    """Deploy the fitted Election rule while suppressing Income actions."""

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


class _FixedIncomeActionPolicy:
    """Pre-declared feasible Income policy used only for validation."""

    def __init__(self, mode: str, fraction: float = 0.0) -> None:
        if mode not in {"full_first", "partial_once", "partial_annual"}:
            raise ValueError(f"Unknown fixed Income benchmark mode: {mode}.")
        if mode.startswith("partial") and not 0.0 < fraction <= 1.0:
            raise ValueError("Fixed Partial benchmark fraction must be in (0, 1].")
        self.mode = mode
        self.fraction = float(fraction)
        self._acted: Optional[np.ndarray] = None
        self.provenance_fingerprint = f"validation:{mode}:{fraction:.6f}"

    def choose_income_action(self, *, context: object) -> IncomeActionDecision:
        n_paths = int(getattr(context, "n_paths"))
        if self._acted is None:
            self._acted = np.zeros(n_paths, dtype=bool)
        if self._acted.shape != (n_paths,):
            raise ValueError("Fixed validation policy cannot be reused across samples.")
        # Store the Enum values explicitly.  NumPy may otherwise coerce the
        # ``str``-Enum through the eight-character ``continue`` scalar and
        # truncate a later ``IncomeActionType.FULL_WITHDRAWAL`` assignment to
        # ``IncomeAc``.
        actions = np.full(
            n_paths, IncomeActionType.CONTINUE.value, dtype="<U18"
        )
        fractions = np.zeros(n_paths)
        if self.mode == "full_first":
            selected = (
                np.asarray(getattr(context, "full_withdrawal_eligible"), dtype=bool)
                & ~self._acted
            )
            actions[selected] = IncomeActionType.FULL_WITHDRAWAL.value
        else:
            selected = np.asarray(
                getattr(context, "partial_withdrawal_eligible"), dtype=bool
            )
            selected &= (
                np.asarray(
                    getattr(context, "max_partial_gross_amount"), dtype=float
                )
                * self.fraction
                >= 100.0 - 1.0e-10
            )
            if self.mode == "partial_once":
                selected &= ~self._acted
            else:
                selected &= int(getattr(context, "step")) % 12 == 0
            actions[selected] = IncomeActionType.PARTIAL_WITHDRAWAL.value
            fractions[selected] = self.fraction
        self._acted[selected] = True
        return IncomeActionDecision(
            action_type=actions,
            partial_fraction_of_max=fractions,
        )


class _FixedAnnualLapsePolicy:
    """Predeclared annual validation benchmark: lapse when first eligible."""

    anniversary_only = True

    def __init__(self) -> None:
        self._acted: Optional[np.ndarray] = None
        self.provenance_fingerprint = "validation:annual_full_first_eligible"

    def surrender_mask(self, *, context: object) -> np.ndarray:
        n_paths = int(getattr(context, "n_paths"))
        if self._acted is None:
            self._acted = np.zeros(n_paths, dtype=bool)
        if self._acted.shape != (n_paths,):
            raise ValueError("Fixed annual policy cannot be reused across samples.")
        selected = (
            bool(getattr(context, "is_anniversary"))
            & np.asarray(
                getattr(context, "full_withdrawal_eligible"), dtype=bool
            )
            & ~self._acted
        )
        self._acted[selected] = True
        return selected


_POLICYHOLDER_VALIDATION_CASHFLOWS = (
    "income_paid",
    "death_benefits",
    "surrender_benefits",
    "terminal_closeout",
)


def _validation_election_year(
    policy: PolicySpec,
    product: IndexLinkedLifetimeIncomeProduct,
    strategy: str,
) -> float:
    earliest = float(product.min_years_before_income)
    forced = max(earliest, float(math.floor(100.0 - policy.age) + 1))
    candidates = {
        "earliest": earliest,
        "year_5": max(earliest, 5.0),
        "year_10": max(earliest, 10.0),
        "model_point": float(policy.effective_income_start_year(product)),
        "forced": forced,
    }
    if strategy not in candidates:
        raise ValueError(f"Unknown validation Election strategy: {strategy}.")
    return candidates[strategy]


def _validation_election_strategy_signatures(
    policies: Sequence[PolicySpec],
    product: IndexLinkedLifetimeIncomeProduct,
) -> dict[str, tuple[float, ...]]:
    """Deduplicate fixed Election years while retaining canonical V00."""
    strategies: dict[str, tuple[float, ...]] = {}
    # ``model_point`` is the contractual V00 reference used again below.  It
    # must win if, for example, its year 5 Election duplicates ``year_5``.
    for strategy in (
        "model_point",
        "earliest",
        "year_5",
        "year_10",
        "forced",
    ):
        signature = tuple(
            _validation_election_year(policy, product, strategy)
            for policy in policies
        )
        if signature not in strategies.values():
            strategies[strategy] = signature
    if "model_point" not in strategies:
        raise RuntimeError(
            "Canonical model-point Election benchmark was not retained."
        )
    return strategies


def _validation_policyholder_path_values(
    *,
    product: IndexLinkedLifetimeIncomeProduct,
    model_points: object,
    esg_config: object,
    mortality: MortalityTable,
    behaviour: object,
    expenses: object,
    settings: ValuationSettings,
    scenarios: object,
    policy_transform: Optional[Callable[[PolicySpec], PolicySpec]] = None,
    hooks_factory: Optional[
        Callable[[PolicySpec], tuple[Optional[object], Optional[object], Optional[object]]]
    ] = None,
) -> tuple[np.ndarray, float]:
    """Aggregate pathwise PH values without collapsing the validation sample."""

    points = tuple(getattr(model_points, "model_points"))
    weight_sum = float(sum(point.contract_weight for point in points))
    if not math.isfinite(weight_sum) or weight_sum <= 0.0:
        raise ValueError("Validation model-point weights must be positive.")
    aggregate = np.zeros(int(settings.n_paths))
    aggregate_premium = 0.0
    for point in points:
        original_policy = point.policy
        valuation_policy = (
            original_policy
            if policy_transform is None
            else policy_transform(original_policy)
        )
        election_policy: Optional[object] = None
        income_action_policy: Optional[object] = None
        surrender_policy: Optional[object] = None
        if hooks_factory is not None:
            election_policy, income_action_policy, surrender_policy = (
                hooks_factory(original_policy)
            )
        valuation = value_contract(
            product,
            valuation_policy,
            esg_config,
            mortality,
            behaviour,
            expenses=expenses,
            settings=settings,
            scenarios=scenarios,
            income_election_policy=election_policy,
            income_action_policy=income_action_policy,
            surrender_policy=surrender_policy,
        )
        projection = valuation.projection
        if np.any(np.abs(np.asarray(
            projection.cashflows["partial_withdrawals"], dtype=float
        )) > 1.0e-10):
            raise RuntimeError(
                "Optimal-behaviour validation produced a Partial Withdrawal."
            )
        cashflows = sum(
            projection.cashflows[name]
            for name in _POLICYHOLDER_VALIDATION_CASHFLOWS
        )
        columns = cashflows.shape[1]
        path_values = np.sum(
            cashflows * scenarios.discount[:, :columns], axis=1
        )
        weight = float(point.contract_weight) / weight_sum
        aggregate += weight * np.asarray(path_values, dtype=float)
        aggregate_premium += weight * float(valuation.premium)
    if not np.all(np.isfinite(aggregate)):
        raise ValueError("Validation produced non-finite Policyholder values.")
    return aggregate, aggregate_premium


def _write_validation_manifest(
    path: Path,
    result: OptimalBehaviourValidationResult,
    *,
    settings: ValuationSettings,
) -> None:
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "valid": result.valid,
        "scenario_fingerprint": result.scenario_fingerprint,
        "n_paths": settings.n_paths,
        "seed": settings.seed,
        "take_up_seed": settings.projection.take_up_seed,
        "mortality_seed": settings.projection.mortality_seed,
        "policyholder_mortality_basis": POLICYHOLDER_LSMC_MORTALITY_BASIS,
        "death_termination_in_policyholder_validation": False,
        "only_voluntary_termination_action": "FULL_WITHDRAWAL_NOW",
        "gates": [gate.as_dict() for gate in result.gates],
        "benchmark_means_aud": dict(result.benchmark_means_aud),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _deduplicate_validation_benchmarks(
    benchmarks: Mapping[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Remove pathwise-identical benchmark variants without using means."""

    unique: dict[str, np.ndarray] = {}
    for name, values in benchmarks.items():
        candidate = np.asarray(values, dtype=float)
        if any(np.array_equal(candidate, existing) for existing in unique.values()):
            continue
        unique[str(name)] = candidate
    if not unique:
        raise ValueError("Validation benchmark library is empty after filtering.")
    return unique


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
        "# Dynamic Behaviour versus LSMC Optimal Behaviour",
        "",
        "Positive deltas mean `LSMC - Dynamic`. Monetary values are in AUD ",
        "per normalised representative contract unless an absolute portfolio ",
        "size was supplied.",
        "",
        "| Metric | Dynamic | LSMC | Delta |",
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
        "The primary LSMC run optimises WAIT_FOR_ONE_YEAR versus "
        "START_INCOME_NOW at eligible policy anniversaries, followed by annual "
        "CONTINUE_FOR_ONE_YEAR versus FULL_WITHDRAWAL_NOW decisions. The "
        "model-point date remains a separately reported deterministic "
        "validation benchmark only; Growth surrenders and Growth withdrawals "
        "remain contractually excluded.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    logger, log_path = _configure_logging(output, args.log_file, args.log_level)
    started = time.perf_counter()

    try:
        logger.info("[1/8] LSMC portfolio run started | Output: %s", output)
        stale_multi_seed_report = (
            output / "lsmc_multi_seed_validation_evaluation.csv"
        ).resolve()
        if stale_multi_seed_report.parent != output:
            raise RuntimeError("Unsafe stale multi-seed report path.")
        if stale_multi_seed_report.is_file():
            stale_multi_seed_report.unlink()
        # Remove completion markers and validation artifacts before any fit.
        # A failed rerun must never leave an older apparently complete report
        # beside the new invalid diagnostics.
        for artifact_name in (
            "run_manifest.json",
            "portfolio_summary.csv",
            "model_point_results.csv",
            "portfolio_aggregation_reconciliation.csv",
            "income_election_distribution.csv",
            "lsmc_regression_diagnostics.csv",
            "lsmc_action_summary.csv",
            "lsmc_vs_continue_summary.csv",
            "behaviour_decomposition.csv",
            "lsmc_validation_summary.csv",
            "lsmc_validation_manifest.json",
        ):
            stale_artifact = (output / artifact_name).resolve()
            if stale_artifact.parent != output:
                raise RuntimeError("Unsafe stale LSMC-output path.")
            if stale_artifact.is_file():
                stale_artifact.unlink()
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
            "Stress scenario | %s | %s | Training and evaluation",
            stress.stress_id,
            stress.label,
        )
        equity_allocation = load_equity_allocation()
        logger.info(
            "Equity allocation | id=%s | equity=%.2f%% | bonds=%.2f%% | %s",
            equity_allocation.allocation_id,
            100.0 * equity_allocation.equity_weight,
            100.0 * equity_allocation.bond_weight,
            equity_allocation.source_path,
        )
        market = load_market_assumptions(args.zero_curve, args.model_parameters)
        generic_base_product = IndexLinkedLifetimeIncomeProduct(
            reference_fund=ReferenceFundSpec(
                equity_weight=equity_allocation.equity_weight,
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
            hedge_pricing_method=args.hedge_pricing_method,
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
        cache_settings = {
            "market_cache_root": str(args.market_cache_root),
            "market_curve_sha256": market.source_sha256["curve"],
            "market_model_parameters_sha256": (
                market.source_sha256["model_parameters"]
            ),
            "market_variant": (
                stress.stress_id
                if stress.stress_id in {
                    "interest_up", "interest_down", "equity_level_down",
                    "equity_volatility_up",
                }
                else "base"
            ),
            "require_market_cache": args.require_market_cache,
            "hedge_cache_root": str(args.hedge_cache_root),
            "hedge_cap_grid": (
                float(costs.product.reference_fund.effective_maximum_return),
            ),
            "hedge_equity_allocation": equity_allocation.equity_weight,
            "hedge_equity_index": costs.product.reference_fund.equity_index,
            "hedge_allocation_input_sha256": equity_allocation.source_sha256,
            "require_hedge_cache": args.require_hedge_cache,
        }
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
                force_pathwise_joint_life=True,
            ),
            real_world_model="hull_white_bs",
            **cache_settings,
        )
        horizon_basis = replace(evaluation_settings, horizon_years=None)
        common_horizon = max(
            resolve_horizon(horizon_basis, point.policy)
            for point in model_points.model_points
        )
        available_training_seed_triplets = (
            {
                "seed_index": 1,
                "market_seed": args.train_seed,
                "take_up_seed": args.train_take_up_seed,
                "mortality_seed": args.train_mortality_seed,
                "primary": True,
            },
            {
                "seed_index": 2,
                "market_seed": args.train_seed_2,
                "take_up_seed": args.train_take_up_seed_2,
                "mortality_seed": args.train_mortality_seed_2,
                "primary": False,
            },
            {
                "seed_index": 3,
                "market_seed": args.train_seed_3,
                "take_up_seed": args.train_take_up_seed_3,
                "mortality_seed": args.train_mortality_seed_3,
                "primary": False,
            },
        )
        training_seed_triplets = available_training_seed_triplets[
            :args.training_seed_count
        ]
        training_projections: list[ProjectionConfig] = []
        training_scenarios_by_seed: list[object] = []
        logger.info(
            "[2/8] Build %d independent LSMC training sample(s) | "
            "paths per sample=%d | horizon=%.1f",
            args.training_seed_count,
            args.n_train,
            common_horizon,
        )
        for seed_triplet in training_seed_triplets:
            training_projection_i = replace(
                costs.projection,
                record_paths=True,
                heston_cos=False,
                take_up_seed=int(seed_triplet["take_up_seed"]),
                mortality_seed=int(seed_triplet["mortality_seed"]),
                force_pathwise_joint_life=True,
            )
            training_settings_i = ValuationSettings(
                model="heston_hull_white",
                n_paths=args.n_train,
                seed=int(seed_triplet["market_seed"]),
                heston_substeps=args.heston_substeps,
                horizon_years=common_horizon,
                projection=training_projection_i,
                real_world_model="hull_white_bs",
                **cache_settings,
            )
            logger.info(
                "LSMC training sample %d/%d | market=%d | take-up=%d | "
                "mortality=%d",
                seed_triplet["seed_index"],
                args.training_seed_count,
                seed_triplet["market_seed"],
                seed_triplet["take_up_seed"],
                seed_triplet["mortality_seed"],
            )
            training_scenarios_i = build_scenarios(
                stressed_esg,
                training_settings_i,
                measure=Measure.RISK_NEUTRAL,
                horizon_years=common_horizon,
            )
            training_transform_already_cached = (
                training_scenarios_i.market_cache_key is not None
                and cache_settings["market_variant"] != "base"
                and training_scenarios_i.market_variant
                == cache_settings["market_variant"]
            )
            if scenario_transform is not None and not training_transform_already_cached:
                training_scenarios_i = scenario_transform(training_scenarios_i)
            training_scenarios_i = bind_cached_hedge_prices(
                training_scenarios_i, training_settings_i
            )
            training_projections.append(training_projection_i)
            training_scenarios_by_seed.append(training_scenarios_i)
        training_projection = training_projections[0]
        training_scenarios = training_scenarios_by_seed[0]
        training_scenario_fingerprints = tuple(
            scenario.content_fingerprint
            for scenario in training_scenarios_by_seed
        )
        if len(set(training_scenario_fingerprints)) \
                != args.training_seed_count:
            raise RuntimeError(
                "The active LSMC training samples must have distinct fingerprints."
            )
        lsmc_settings = OptimalBehaviourLSMCSettings(
            ridge=args.lsmc_ridge,
            n_folds=args.lsmc_folds,
            exercise_buffer_rmse_multiplier=args.exercise_buffer_rmse_multiplier,
            allow_partial_withdrawal=False,
        )

        policy_labels: dict[tuple[object, ...], list[str]] = {}
        for point in model_points.model_points:
            policy_labels.setdefault(_policy_signature(point.policy), []).append(
                point.model_point_id)

        fits_by_seed: list[
            dict[tuple[object, ...], OptimalBehaviourPolicyFit]
        ] = [{} for _ in training_seed_triplets]
        # The primary seed remains the only fit driving the canonical
        # V00/V01/V10/V11 output files.  Seeds two and three are independent
        # robustness replications and are never candidates for selection.
        fits = fits_by_seed[0]

        def ensure_fit(
            policy_object: object,
            training_seed_index: int = 0,
        ) -> OptimalBehaviourPolicyFit:
            if not isinstance(policy_object, PolicySpec):
                raise TypeError("LSMC policy factory requires PolicySpec.")
            if not 0 <= training_seed_index < len(training_seed_triplets):
                raise ValueError("training_seed_index is outside the active seeds.")
            selected_fits = fits_by_seed[training_seed_index]
            key = _policy_signature(policy_object)
            if key not in selected_fits:
                labels = ",".join(policy_labels.get(key, ["unlabelled"]))
                seed_triplet = training_seed_triplets[training_seed_index]
                logger.info(
                    "LSMC fit seed=%d | %s | age=%.0f | premium=%.0f | "
                    "spouse=%s",
                    seed_triplet["seed_index"],
                    labels, policy_object.age, policy_object.initial_investment,
                    policy_object.spouse,
                )
                selected_fits[key] = fit_optimal_behaviour_policy(
                    costs.product,
                    policy_object,
                    training_scenarios_by_seed[training_seed_index],
                    mortality,
                    expenses=stressed_expenses,
                    projection_config=training_projections[training_seed_index],
                    settings=lsmc_settings,
                    fit_basis_inputs={
                        "stress_scenario": stress_audit,
                        "training_seed_index": int(
                            seed_triplet["seed_index"]
                        ),
                        "training_seed_triplet": {
                            "market_seed": int(seed_triplet["market_seed"]),
                            "take_up_seed": int(seed_triplet["take_up_seed"]),
                        },
                        "policyholder_mortality_basis": (
                            POLICYHOLDER_LSMC_MORTALITY_BASIS
                        ),
                        "crediting_cap_rate": (
                            costs.product.reference_fund.effective_maximum_return
                        ),
                    },
                )
            return selected_fits[key]

        deployed_policies: dict[
            tuple[object, ...], OptimalBehaviourPolicy
        ] = {}
        deployment_selection_by_seed = [
            "training_selected" for _ in range(args.training_seed_count)
        ]
        election_only_policies: dict[
            tuple[object, ...], _ElectionOnlyPolicy
        ] = {}
        deterministic_surrender_policies: dict[
            tuple[object, ...], object
        ] = {}

        def deployment_policy(
            policy_object: PolicySpec,
            training_seed_index: int,
        ) -> OptimalBehaviourPolicy:
            fit = ensure_fit(policy_object, training_seed_index)
            selected = deployment_selection_by_seed[training_seed_index]
            if selected == "training_selected":
                return fit.policy
            if selected in fit.policy_variants:
                return fit.policy_variants[selected]
            if selected.startswith("V00_"):
                return fit.policy_variants["V00"]
            if selected.startswith("V01_"):
                return fit.policy_variants["V01"]
            if selected.startswith("V10_"):
                return fit.policy_variants["V10"]
            if "|" in selected:
                election_name, income_name = selected.split("|", 1)
                base = fit.policy_variants["V00"]
                return replace(
                    base,
                    surrender_policy=(
                        _FixedAnnualLapsePolicy()
                        if income_name == "annual_full_first_eligible"
                        else base.surrender_policy
                    ),
                    fixed_election_step=int(round(
                        _validation_election_year(
                            policy_object, costs.product, election_name
                        ) * 12.0
                    )),
                )
            raise RuntimeError(
                f"Unknown validation deployment selection: {selected}."
            )

        def combined_policy_factory(policy_object: object) -> object:
            if not isinstance(policy_object, PolicySpec):
                raise TypeError("LSMC policy factory requires PolicySpec.")
            key = _policy_signature(policy_object)
            if key not in deployed_policies:
                deployed_policies[key] = _fresh_policy(
                    deployment_policy(policy_object, 0)
                )
            return deployed_policies[key]

        def election_only_policy_factory(policy_object: object) -> object:
            if not isinstance(policy_object, PolicySpec):
                raise TypeError("LSMC policy factory requires PolicySpec.")
            key = _policy_signature(policy_object)
            if key not in election_only_policies:
                election_only_policies[key] = _ElectionOnlyPolicy(
                    _fresh_policy(
                        _election_control_policy(ensure_fit(policy_object))
                    )
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
                    ensure_fit(policy_object).policy_variants["V01"]
                )
            return deterministic_surrender_policies[key]

        validation_projection = replace(
            costs.projection,
            record_paths=False,
            heston_cos=False,
            take_up_seed=args.validation_take_up_seed,
            # Customer-policy validation is conditional on survival.  The
            # configured mortality basis is restored for the final actuarial
            # valuation below.
            mortality_seed=0,
            force_pathwise_joint_life=True,
        )
        validation_mortality = mortality_free_policyholder_basis(mortality)
        validation_settings = ValuationSettings(
            model="heston_hull_white",
            n_paths=args.n_validation,
            seed=args.validation_seed,
            heston_substeps=args.heston_substeps,
            horizon_years=common_horizon,
            projection=validation_projection,
            real_world_model="hull_white_bs",
            **cache_settings,
        )
        logger.info(
            "[3/8] Validate the frozen LSMC policy on independent validation "
            "paths | paths=%d | seed=%d",
            args.n_validation,
            args.validation_seed,
        )
        validation_scenarios = build_scenarios(
            stressed_esg,
            validation_settings,
            measure=Measure.RISK_NEUTRAL,
            horizon_years=common_horizon,
        )
        validation_transform_already_cached = (
            validation_scenarios.market_cache_key is not None
            and cache_settings["market_variant"] != "base"
            and validation_scenarios.market_variant
            == cache_settings["market_variant"]
        )
        if scenario_transform is not None and not validation_transform_already_cached:
            validation_scenarios = scenario_transform(validation_scenarios)
        validation_scenarios = bind_cached_hedge_prices(
            validation_scenarios, validation_settings
        )
        if validation_scenarios.content_fingerprint in set(
            training_scenario_fingerprints
        ):
            raise ValueError(
                "All training and validation scenario sets must be independent."
            )

        def validation_combined_hooks(
            policy_object: PolicySpec,
            training_seed_index: int = 0,
        ) -> tuple[object, None, object]:
            fit = ensure_fit(policy_object, training_seed_index)
            candidate = fit.policy_variants["V11"]
            policy = _fresh_policy(candidate if candidate.valid else fit.policy)
            return policy, None, policy

        def validation_election_hooks(
            policy_object: PolicySpec,
            training_seed_index: int = 0,
        ) -> tuple[object, None, None]:
            fit = ensure_fit(policy_object, training_seed_index)
            candidate = fit.policy_variants["V10"]
            policy = _fresh_policy(
                candidate if candidate.valid else fit.policy_variants["V00"]
            )
            return policy, None, None

        def validation_income_hooks(
            policy_object: PolicySpec,
            training_seed_index: int = 0,
        ) -> tuple[None, None, object]:
            return (
                None,
                None,
                _fresh_policy(
                    ensure_fit(
                        policy_object, training_seed_index
                    ).policy_variants["V01"]
                ),
            )

        for training_seed_index in range(args.training_seed_count):
            for point in model_points.model_points:
                ensure_fit(point.policy, training_seed_index)
        invalid_fit_records = [
            (training_seed_index, key, fit)
            for training_seed_index, selected_fits in enumerate(fits_by_seed)
            for key, fit in selected_fits.items()
            if not fit.valid
        ]
        if invalid_fit_records:
            invalid_diagnostic_rows = [
                {
                    "training_seed_index": training_seed_index + 1,
                    "training_market_seed": training_seed_triplets[
                        training_seed_index
                    ]["market_seed"],
                    "policy_signature": repr(key),
                    "fit_basis_fingerprint": fit.fit_basis_fingerprint,
                    "fit_valid": fit.valid,
                    "fit_invalid_reasons": "|".join(fit.invalid_reasons),
                    **diagnostic.as_dict(),
                }
                for training_seed_index, key, fit in invalid_fit_records
                for diagnostic in fit.diagnostics
            ]
            if invalid_diagnostic_rows:
                _write_csv(
                    output / "lsmc_regression_diagnostics.csv",
                    invalid_diagnostic_rows,
                )
            invalid_rows = [
                {
                    "valid": False,
                    "status": "fit_invalid",
                    "training_seed_index": training_seed_index + 1,
                    "training_market_seed": training_seed_triplets[
                        training_seed_index
                    ]["market_seed"],
                    "policy_signature": repr(key),
                    "fit_basis_fingerprint": fit.fit_basis_fingerprint,
                    "invalid_reasons": "|".join(fit.invalid_reasons),
                }
                for training_seed_index, key, fit in invalid_fit_records
            ]
            _write_csv(output / "lsmc_validation_summary.csv", invalid_rows)
            invalid_payload = {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "valid": False,
                "status": "fit_invalid",
                "scenario_fingerprint": (
                    validation_scenarios.content_fingerprint
                ),
                "training_scenario_fingerprints": list(
                    training_scenario_fingerprints
                ),
                "training_seed_triplets": list(training_seed_triplets),
                "gates": [],
                "invalid_fits": invalid_rows,
            }
            with (output / "lsmc_validation_manifest.json").open(
                "w", encoding="utf-8"
            ) as handle:
                json.dump(
                    invalid_payload,
                    handle,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                handle.write("\n")
            raise RuntimeError(
                "One or more LSMC fits are invalid; see validation diagnostics."
            )

        validation_candidates_by_seed: list[dict[str, np.ndarray]] = []
        validation_premium: Optional[float] = None
        for training_seed_index in range(args.training_seed_count):
            election_candidate, election_premium = (
                _validation_policyholder_path_values(
                    product=costs.product,
                    model_points=model_points,
                    esg_config=stressed_esg,
                    mortality=validation_mortality,
                    behaviour=lsmc_behaviour,
                    expenses=stressed_expenses,
                    settings=validation_settings,
                    scenarios=validation_scenarios,
                    hooks_factory=(
                        lambda policy, selected=training_seed_index: (
                            validation_election_hooks(policy, selected)
                        )
                    ),
                )
            )
            income_candidate, income_premium = (
                _validation_policyholder_path_values(
                    product=costs.product,
                    model_points=model_points,
                    esg_config=stressed_esg,
                    mortality=validation_mortality,
                    behaviour=lsmc_behaviour,
                    expenses=stressed_expenses,
                    settings=validation_settings,
                    scenarios=validation_scenarios,
                    hooks_factory=(
                        lambda policy, selected=training_seed_index: (
                            validation_income_hooks(policy, selected)
                        )
                    ),
                )
            )
            combined_candidate, combined_premium = (
                _validation_policyholder_path_values(
                    product=costs.product,
                    model_points=model_points,
                    esg_config=stressed_esg,
                    mortality=validation_mortality,
                    behaviour=lsmc_behaviour,
                    expenses=stressed_expenses,
                    settings=validation_settings,
                    scenarios=validation_scenarios,
                    hooks_factory=(
                        lambda policy, selected=training_seed_index: (
                            validation_combined_hooks(policy, selected)
                        )
                    ),
                )
            )
            premiums = (election_premium, income_premium, combined_premium)
            if not all(math.isclose(
                election_premium, premium, rel_tol=0.0, abs_tol=1.0e-10
            ) for premium in premiums[1:]):
                raise RuntimeError(
                    "Validation premium changed between policy components."
                )
            if validation_premium is None:
                validation_premium = election_premium
            elif not math.isclose(
                validation_premium,
                election_premium,
                rel_tol=0.0,
                abs_tol=1.0e-10,
            ):
                raise RuntimeError(
                    "Validation premium changed between training seeds."
                )
            validation_candidates_by_seed.append({
                "election_only": election_candidate,
                "income_action_only": income_candidate,
                "combined_policy": combined_candidate,
            })
        if validation_premium is None:
            raise RuntimeError("No validation premium was produced.")

        election_strategies = _validation_election_strategy_signatures(
            tuple(point.policy for point in model_points.model_points),
            costs.product,
        )

        election_benchmarks: dict[str, np.ndarray] = {}
        for strategy in election_strategies:
            values, _ = _validation_policyholder_path_values(
                product=costs.product,
                model_points=model_points,
                esg_config=stressed_esg,
                mortality=validation_mortality,
                behaviour=lsmc_behaviour,
                expenses=stressed_expenses,
                settings=validation_settings,
                scenarios=validation_scenarios,
                policy_transform=lambda policy, selected=strategy: replace(
                    policy,
                    income_start_year=_validation_election_year(
                        policy,
                        costs.product,
                        selected,
                    ),
                ),
            )
            election_benchmarks[strategy] = values
        modelpoint_v00_paths = np.asarray(
            election_benchmarks["model_point"], dtype=float
        )
        election_benchmarks = _deduplicate_validation_benchmarks(
            election_benchmarks
        )

        income_benchmark_specs: tuple[
            tuple[str, Optional[str], float], ...
        ] = (
            ("continue_only", None, 0.0),
            ("annual_full_first_eligible", "annual_full_first", 0.0),
        )
        income_benchmarks: dict[str, np.ndarray] = {}
        for name, mode, fraction in income_benchmark_specs:
            hooks_factory = None
            if mode is not None:
                hooks_factory = (
                    lambda _policy: (
                        None,
                        None,
                        _FixedAnnualLapsePolicy(),
                    )
                )
            values, _ = _validation_policyholder_path_values(
                product=costs.product,
                model_points=model_points,
                esg_config=stressed_esg,
                mortality=validation_mortality,
                behaviour=lsmc_behaviour,
                expenses=stressed_expenses,
                settings=validation_settings,
                scenarios=validation_scenarios,
                hooks_factory=hooks_factory,
            )
            income_benchmarks[name] = values
        income_benchmarks = _deduplicate_validation_benchmarks(income_benchmarks)

        combined_benchmarks: dict[str, np.ndarray] = {}
        for election_name in election_strategies:
            for income_name, mode, fraction in income_benchmark_specs:
                hooks_factory = None
                if mode is not None:
                    hooks_factory = (
                        lambda _policy: (
                            None,
                            None,
                            _FixedAnnualLapsePolicy(),
                        )
                    )
                values, _ = _validation_policyholder_path_values(
                    product=costs.product,
                    model_points=model_points,
                    esg_config=stressed_esg,
                    mortality=validation_mortality,
                    behaviour=lsmc_behaviour,
                    expenses=stressed_expenses,
                    settings=validation_settings,
                    scenarios=validation_scenarios,
                    policy_transform=(
                        lambda policy, selected=election_name: replace(
                            policy,
                            income_start_year=_validation_election_year(
                                policy,
                                costs.product,
                                selected,
                            ),
                        )
                    ),
                    hooks_factory=hooks_factory,
                )
                combined_benchmarks[
                    f"{election_name}|{income_name}"
                ] = values
        combined_benchmarks = _deduplicate_validation_benchmarks(
            combined_benchmarks
        )

        benchmark_means = {
            **{
                f"election_only:{name}": float(np.mean(values))
                for name, values in election_benchmarks.items()
            },
            **{
                f"income_action_only:{name}": float(np.mean(values))
                for name, values in income_benchmarks.items()
            },
            **{
                f"combined_policy:{name}": float(np.mean(values))
                for name, values in combined_benchmarks.items()
            },
        }
        validation_results_by_seed: list[
            OptimalBehaviourValidationResult
        ] = []
        validation_summary_rows: list[dict[str, object]] = []
        for training_seed_index, candidates in enumerate(
            validation_candidates_by_seed
        ):
            factorial_benchmarks = {
                **combined_benchmarks,
                "V00_model_point_fixed_continue": modelpoint_v00_paths,
                "V01_model_point_fixed_annual_lapse": candidates[
                    "income_action_only"
                ],
                "V10_annual_election_continue": candidates["election_only"],
            }
            validation_gates_i = (
                paired_noninferiority_gate(
                    candidates["election_only"],
                    election_benchmarks,
                    premium_aud=validation_premium,
                    component="election_only",
                ),
                paired_noninferiority_gate(
                    candidates["income_action_only"],
                    income_benchmarks,
                    premium_aud=validation_premium,
                    component="income_action_only",
                ),
                paired_noninferiority_gate(
                    candidates["combined_policy"],
                    factorial_benchmarks,
                    premium_aud=validation_premium,
                    component="combined_policy",
                ),
            )
            result_i = OptimalBehaviourValidationResult(
                scenario_fingerprint=(
                    validation_scenarios.content_fingerprint
                ),
                gates=validation_gates_i,
                benchmark_means_aud=benchmark_means,
            )
            validation_results_by_seed.append(result_i)
            seed_triplet = training_seed_triplets[training_seed_index]
            validation_summary_rows.append({
                "training_seed_index": training_seed_index + 1,
                "primary_training_seed": bool(seed_triplet["primary"]),
                "training_market_seed": seed_triplet["market_seed"],
                "component": "factorial_paired_effects",
                "path_count": int(modelpoint_v00_paths.size),
                "V00_mean_aud": float(np.mean(modelpoint_v00_paths)),
                "V01_mean_aud": float(np.mean(
                    candidates["income_action_only"]
                )),
                "V10_mean_aud": float(np.mean(candidates["election_only"])),
                "V11_mean_aud": float(np.mean(candidates["combined_policy"])),
                "lapse_optionality_V01_minus_V00_aud": float(np.mean(
                    candidates["income_action_only"] - modelpoint_v00_paths
                )),
                "election_optionality_V10_minus_V00_aud": float(np.mean(
                    candidates["election_only"] - modelpoint_v00_paths
                )),
                "combined_optionality_V11_minus_V00_aud": float(np.mean(
                    candidates["combined_policy"] - modelpoint_v00_paths
                )),
            })
            for row in result_i.rows():
                validation_summary_rows.append({
                    "training_seed_index": training_seed_index + 1,
                    "primary_training_seed": bool(seed_triplet["primary"]),
                    "training_market_seed": seed_triplet["market_seed"],
                    "training_take_up_seed": seed_triplet["take_up_seed"],
                    "training_mortality_seed": seed_triplet["mortality_seed"],
                    "training_scenario_fingerprint": (
                        training_scenario_fingerprints[training_seed_index]
                    ),
                    **row,
                })
        validation_result = validation_results_by_seed[0]
        validation_gate_rows = [
            row
            for row in validation_summary_rows
            if row.get("component") in {
                "election_only",
                "income_action_only",
                "combined_policy",
            }
        ]
        validation_fallback_reasons: dict[int, str] = {}
        candidate_fit_valid_by_seed: dict[int, bool] = {}
        deployment_valid_by_seed: dict[int, bool] = {}
        for index, result in enumerate(validation_results_by_seed):
            candidate_fits_valid = all(
                bool(fit.policy_variants["V11"].valid)
                for fit in fits_by_seed[index].values()
            )
            candidate_fit_valid_by_seed[index] = candidate_fits_valid
            selection = select_deployed_policy(
                result,
                candidate_policy_name="V11",
                candidate_fit_valid=candidate_fits_valid,
            )
            deployment_selection_by_seed[index] = selection.selected_policy_name
            combined_gate = next(
                gate
                for gate in result.gates
                if gate.component == "combined_policy"
            )
            deployment_valid_by_seed[index] = bool(
                (
                    candidate_fits_valid
                    and result.valid
                    and selection.selected_policy_name == "V11"
                )
                or (
                    selection.selected_policy_name
                    == combined_gate.benchmark_name
                    and selection.fallback_reason is not None
                )
            )
            if selection.fallback_reason is not None:
                validation_fallback_reasons[index] = selection.fallback_reason
        if not all(deployment_valid_by_seed.values()):
            raise RuntimeError(
                "Validation did not produce a deployable candidate or fixed "
                "fallback for every active training seed."
            )
        all_candidate_policies_valid = all(
            candidate_fit_valid_by_seed[index]
            and validation_results_by_seed[index].valid
            for index in range(args.training_seed_count)
        )
        all_deployments_valid = all(deployment_valid_by_seed.values())
        validation_summary_path = output / "lsmc_validation_summary.csv"
        validation_manifest_path = output / "lsmc_validation_manifest.json"
        _write_csv(validation_summary_path, validation_summary_rows)
        multi_seed_validation_payload = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "valid": all_deployments_valid,
            "candidate_valid": all_candidate_policies_valid,
            "deployment_valid": all_deployments_valid,
            "scenario_fingerprint": validation_scenarios.content_fingerprint,
            "n_paths": validation_settings.n_paths,
            "seed": validation_settings.seed,
            "take_up_seed": validation_settings.projection.take_up_seed,
            "mortality_seed": validation_settings.projection.mortality_seed,
            "requested_mortality_seed_ignored": args.validation_mortality_seed,
            "policyholder_mortality_basis": (
                POLICYHOLDER_LSMC_MORTALITY_BASIS
            ),
            "death_termination_in_policyholder_validation": False,
            "only_voluntary_termination_action": "FULL_WITHDRAWAL_NOW",
            "actuarial_evaluation_uses_configured_mortality": True,
            "training_seed_count": args.training_seed_count,
            "seed_selection_using_evaluation": False,
            "primary_training_seed_index": 1,
            "candidate_policy": "V11",
            "candidate_fit_valid_by_training_seed": {
                str(index + 1): valid
                for index, valid in candidate_fit_valid_by_seed.items()
            },
            "deployed_policy_by_training_seed": {
                str(index + 1): selection
                for index, selection in enumerate(
                    deployment_selection_by_seed
                )
            },
            "validation_fallback_reason_by_training_seed": {
                str(index + 1): reason
                for index, reason in validation_fallback_reasons.items()
            },
            "gates": validation_gate_rows,
            "training_runs": [
                {
                    **dict(training_seed_triplets[index]),
                    "training_scenario_fingerprint": (
                        training_scenario_fingerprints[index]
                    ),
                    "valid": deployment_valid_by_seed[index],
                    "candidate_valid": (
                        candidate_fit_valid_by_seed[index] and result.valid
                    ),
                    "deployment_valid": deployment_valid_by_seed[index],
                    "gates": [gate.as_dict() for gate in result.gates],
                    "fit_basis_fingerprints": {
                        repr(key): fit.fit_basis_fingerprint
                        for key, fit in sorted(
                            fits_by_seed[index].items(),
                            key=lambda item: str(item[0]),
                        )
                    },
                    "selected_training_anchors": {
                        repr(key): {
                            "fixed_election_step": (
                                fit.selected_fixed_election_step
                            ),
                            "fixed_election_year": (
                                None
                                if fit.selected_fixed_election_step is None
                                else fit.selected_fixed_election_step / 12.0
                            ),
                            "income_action_mode": (
                                fit.selected_income_action_mode
                            ),
                        }
                        for key, fit in sorted(
                            fits_by_seed[index].items(),
                            key=lambda item: str(item[0]),
                        )
                    },
                }
                for index, result in enumerate(validation_results_by_seed)
            ],
            "benchmark_means_aud": benchmark_means,
        }
        with validation_manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(
                multi_seed_validation_payload,
                handle,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
        failed_seed_gates = [
            f"seed_{index + 1}:{gate.component}"
            for index, result in enumerate(validation_results_by_seed)
            for gate in result.gates
            if not gate.valid
        ]
        if failed_seed_gates:
            logger.warning(
                "LSMC validation gate(s) failed; the final rollout deploys "
                "the best predeclared fixed baseline where required: %s",
                ", ".join(failed_seed_gates),
            )

        dynamic_result = None
        if not args.no_dynamic_benchmark:
            if dynamic_behaviour is None:
                raise ValueError("Dynamic benchmark behaviour was not loaded.")
            logger.info(
                "[4/8] Dynamic Behaviour benchmark on evaluation paths | "
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
            logger.info("[4/8] Dynamic Behaviour benchmark disabled")

        logger.info(
            "[5/8] Evaluate %s out of sample in the monthly projector",
            (
                "deployed LSMC policy plus internal Election control run"
                if args.no_factorial_benchmarks
                else "deterministic and combined LSMC policies"
            ),
        )
        continue_result = None
        deterministic_surrender_result = None
        if not args.no_factorial_benchmarks:
            # V00: legacy deterministic model-point Election with no
            # voluntary exit.
            continue_result = value_policyholder_portfolio(
                costs.product,
                model_points,
                stressed_esg,
                mortality,
                lsmc_behaviour,
                stressed_expenses,
                settings=evaluation_settings,
                portfolio_contract_count=args.portfolio_contract_count,
                profitability_materiality_bp=(
                    args.profitability_materiality_bp
                ),
                progress_callback=_make_progress_callback(logger),
                scenario_transform=scenario_transform,
            )
            # V01: deterministic model-point Election plus fitted annual
            # CONTINUE_FOR_ONE_YEAR/FULL_WITHDRAWAL_NOW decisions.
            deterministic_surrender_result = value_policyholder_portfolio(
                costs.product,
                model_points,
                stressed_esg,
                mortality,
                lsmc_behaviour,
                stressed_expenses,
                settings=evaluation_settings,
                portfolio_contract_count=args.portfolio_contract_count,
                profitability_materiality_bp=(
                    args.profitability_materiality_bp
                ),
                progress_callback=_make_progress_callback(logger),
                surrender_policy_factory=(
                    deterministic_surrender_policy_factory
                ),
                scenario_transform=scenario_transform,
            )
        # Election control: deploy V10 when it is valid, otherwise V00, and
        # suppress Income exit only in this counterfactual rollout. No action
        # is reselected OOS.
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
        # Deploy frozen V11 or the fixed policy selected on validation paths.
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
        lsmc_results_by_seed = [lsmc_result]
        deployed_policies_by_seed: list[
            dict[tuple[object, ...], OptimalBehaviourPolicy]
        ] = [deployed_policies]
        for training_seed_index in range(1, args.training_seed_count):
            evaluation_policy_cache: dict[
                tuple[object, ...], OptimalBehaviourPolicy
            ] = {}

            def replicated_combined_policy_factory(
                policy_object: object,
                *,
                selected_seed_index: int = training_seed_index,
                selected_cache: dict[
                    tuple[object, ...], OptimalBehaviourPolicy
                ] = evaluation_policy_cache,
            ) -> object:
                if not isinstance(policy_object, PolicySpec):
                    raise TypeError("LSMC policy factory requires PolicySpec.")
                key = _policy_signature(policy_object)
                if key not in selected_cache:
                    selected_cache[key] = _fresh_policy(
                        deployment_policy(
                            policy_object, selected_seed_index
                        )
                    )
                return selected_cache[key]

            logger.info(
                "Final evaluation of frozen training seed %d/%d on identical "
                "evaluation paths",
                training_seed_index + 1,
                args.training_seed_count,
            )
            replicated_result = value_policyholder_portfolio(
                costs.product,
                model_points,
                stressed_esg,
                mortality,
                lsmc_behaviour,
                stressed_expenses,
                settings=evaluation_settings,
                portfolio_contract_count=args.portfolio_contract_count,
                profitability_materiality_bp=(
                    args.profitability_materiality_bp
                ),
                progress_callback=_make_progress_callback(logger),
                combined_policy_factory=replicated_combined_policy_factory,
                scenario_transform=scenario_transform,
            )
            lsmc_results_by_seed.append(replicated_result)
            deployed_policies_by_seed.append(evaluation_policy_cache)
        if len(lsmc_results_by_seed) != args.training_seed_count:
            raise RuntimeError(
                "Every active training seed requires one final LSMC evaluation."
            )
        evaluation_fingerprints = {
            "election_continue": election_continue_result.scenario_fingerprint,
            "combined_lsmc": lsmc_result.scenario_fingerprint,
        }
        evaluation_fingerprints.update({
            f"combined_lsmc_seed_{index + 1}": result.scenario_fingerprint
            for index, result in enumerate(lsmc_results_by_seed[1:], start=1)
        })
        if continue_result is not None:
            evaluation_fingerprints["continue"] = (
                continue_result.scenario_fingerprint
            )
        if deterministic_surrender_result is not None:
            evaluation_fingerprints["deterministic_surrender"] = (
                deterministic_surrender_result.scenario_fingerprint
            )
        if dynamic_result is not None:
            evaluation_fingerprints["dynamic"] = (
                dynamic_result.scenario_fingerprint
            )
        if len(set(evaluation_fingerprints.values())) != 1:
            raise ValueError(
                "All dynamic, deterministic and LSMC evaluations must share "
                "one common scenario set."
            )
        if lsmc_result.scenario_fingerprint in set(
            training_scenario_fingerprints
        ):
            raise ValueError(
                "All training and evaluation scenario sets must be independent."
            )
        if (
            validation_scenarios.content_fingerprint
            == lsmc_result.scenario_fingerprint
        ):
            raise ValueError(
                "Validation and evaluation scenario sets must be independent."
            )

        multi_seed_objective_key = (
            "normalised_average_pv_policyholder_benefits_aud"
        )
        continue_evaluation_result = (
            election_continue_result
            if continue_result is None
            else continue_result
        )
        continue_evaluation_summary = continue_evaluation_result.summary_dict()
        continue_evaluation_objective = float(
            continue_evaluation_summary[multi_seed_objective_key]
        )
        multi_seed_report_rows: list[dict[str, object]] = []
        for training_seed_index, replicated_result in enumerate(
            lsmc_results_by_seed
        ):
            seed_triplet = training_seed_triplets[training_seed_index]
            replicated_summary = replicated_result.summary_dict()
            replicated_objective = float(
                replicated_summary[multi_seed_objective_key]
            )
            selected_fits = fits_by_seed[training_seed_index]
            report_row: dict[str, object] = {
                "training_seed_index": training_seed_index + 1,
                "primary_training_seed": bool(seed_triplet["primary"]),
                "training_market_seed": seed_triplet["market_seed"],
                "training_take_up_seed": seed_triplet["take_up_seed"],
                "training_mortality_seed": seed_triplet["mortality_seed"],
                "training_scenario_fingerprint": (
                    training_scenario_fingerprints[training_seed_index]
                ),
                "fit_count": len(selected_fits),
                "all_fits_valid": all(
                    fit.valid for fit in selected_fits.values()
                ),
                "candidate_fit_valid": candidate_fit_valid_by_seed[
                    training_seed_index
                ],
                "fit_basis_fingerprints_json": json.dumps(
                    {
                        repr(key): fit.fit_basis_fingerprint
                        for key, fit in sorted(
                            selected_fits.items(),
                            key=lambda item: str(item[0]),
                        )
                    },
                    sort_keys=True,
                ),
                "validation_scenario_fingerprint": (
                    validation_scenarios.content_fingerprint
                ),
                "validation_valid": validation_results_by_seed[
                    training_seed_index
                ].valid,
                "deployed_policy": deployment_selection_by_seed[
                    training_seed_index
                ],
                "validation_fallback_used": (
                    training_seed_index in validation_fallback_reasons
                ),
                "validation_fallback_reason": (
                    validation_fallback_reasons.get(training_seed_index)
                ),
                "deployment_valid": deployment_valid_by_seed[
                    training_seed_index
                ],
                "evaluation_scenario_fingerprint": (
                    replicated_result.scenario_fingerprint
                ),
                "evaluation_policyholder_value_aud": replicated_objective,
                "evaluation_continue_value_aud": (
                    continue_evaluation_objective
                ),
                "evaluation_minus_continue_aud": (
                    replicated_objective - continue_evaluation_objective
                ),
                "selected_for_primary_outputs": bool(seed_triplet["primary"]),
                "selection_rule": "predeclared_seed_1_not_evaluation_based",
                "evaluation_used_for_seed_selection": False,
            }
            for gate in validation_results_by_seed[
                training_seed_index
            ].gates:
                prefix = f"validation_{gate.component}"
                report_row[f"{prefix}_valid"] = gate.valid
                report_row[f"{prefix}_benchmark"] = gate.benchmark_name
                report_row[f"{prefix}_lcb95_aud"] = (
                    gate.lower_confidence_bound_95_aud
                )
                report_row[f"{prefix}_margin_aud"] = (
                    gate.noninferiority_margin_aud
                )
                report_row[f"{prefix}_paired_mean_aud"] = (
                    gate.paired_difference_mean_aud
                )
            multi_seed_report_rows.append(report_row)
        if not all(bool(row["deployment_valid"])
                   for row in multi_seed_report_rows):
            raise RuntimeError(
                "Every training seed must deploy either valid V11 or its "
                "recorded fixed validation fallback."
            )
        multi_seed_report_path = (
            output / "lsmc_multi_seed_validation_evaluation.csv"
        )
        _write_csv(multi_seed_report_path, multi_seed_report_rows)

        logger.info("[6/8] Write results and comparisons")
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
            "lsmc_training_mortality_seed_used_for_policy_fit": False,
            "lsmc_policyholder_mortality_basis": (
                POLICYHOLDER_LSMC_MORTALITY_BASIS
            ),
            "lsmc_training_seed_count": args.training_seed_count,
            "lsmc_training_seed_triplets_json": json.dumps(
                list(training_seed_triplets), sort_keys=True
            ),
            "lsmc_training_scenario_fingerprints_json": json.dumps(
                list(training_scenario_fingerprints)
            ),
            "lsmc_validation_paths": args.n_validation,
            "lsmc_validation_seed": args.validation_seed,
            "lsmc_validation_take_up_seed": args.validation_take_up_seed,
            "lsmc_validation_mortality_seed": args.validation_mortality_seed,
            "lsmc_validation_mortality_seed_used": False,
            "lsmc_actuarial_evaluation_uses_configured_mortality": True,
            "lsmc_candidate_policy": "V11",
            "lsmc_deployed_policy": deployment_selection_by_seed[0],
            "lsmc_validation_fallback_used": (
                0 in validation_fallback_reasons
            ),
            "lsmc_validation_fallback_reason": (
                validation_fallback_reasons.get(0)
            ),
            "lsmc_validation_candidate_value_aud": next(
                gate.policy_mean_aud
                for gate in validation_result.gates
                if gate.component == "combined_policy"
            ),
            "lsmc_validation_selected_value_aud": (
                next(
                    gate.policy_mean_aud
                    for gate in validation_result.gates
                    if gate.component == "combined_policy"
                )
                if deployment_selection_by_seed[0] == "V11"
                else next(
                    gate.benchmark_mean_aud
                    for gate in validation_result.gates
                    if gate.component == "combined_policy"
                )
            ),
            "lsmc_evaluation_seed": args.seed,
            "lsmc_evaluation_take_up_seed": args.take_up_seed,
            "lsmc_evaluation_mortality_seed": args.mortality_seed,
            "lsmc_training_scenario_fingerprint": (
                training_scenarios.content_fingerprint),
            "lsmc_validation_scenario_fingerprint": (
                validation_scenarios.content_fingerprint
            ),
            "lsmc_validation_valid": all_deployments_valid,
            "lsmc_validation_candidate_valid": all_candidate_policies_valid,
            "lsmc_validation_all_active_seeds_valid": all_deployments_valid,
            "lsmc_validation_all_active_seed_candidates_valid": (
                all_candidate_policies_valid
            ),
            "lsmc_validation_all_active_seeds_deployed": (
                all_deployments_valid
            ),
            "lsmc_final_evaluation_all_active_seeds_reported": True,
            # Backward-compatible evidence for already-running three-seed
            # orchestrators that imported the pre-streamlining validator.
            "lsmc_validation_all_three_seeds_valid": (
                args.training_seed_count == 3
                and all(result.valid for result in validation_results_by_seed)
            ),
            "lsmc_final_evaluation_all_three_seeds_reported": (
                args.training_seed_count == 3
            ),
            "lsmc_primary_seed_selection_rule": (
                "predeclared_first_seed_not_evaluation_based"
            ),
            "lsmc_policy_iteration_converged": all(
                fit.policy_iteration_converged for fit in fits.values()
            ),
            "lsmc_policy_iteration_count_max": max(
                (fit.policy_iteration_count for fit in fits.values()),
                default=0,
            ),
            "lsmc_income_action_exposure_coverage_min": min(
                (fit.income_action_exposure_coverage for fit in fits.values()),
                default=1.0,
            ),
            "lsmc_final_action_agreement_min": min(
                (fit.final_action_agreement for fit in fits.values()),
                default=1.0,
            ),
            "lsmc_final_policy_value_change_abs_max_aud": max(
                (abs(fit.final_policy_value_change_aud) for fit in fits.values()),
                default=0.0,
            ),
            "scenario_fingerprint": lsmc_result.scenario_fingerprint,
            "lsmc_fit_basis_fingerprint_count": len(fits),
            "lsmc_fit_basis_fingerprint_count_all_training_seeds": sum(
                len(selected_fits) for selected_fits in fits_by_seed
            ),
            "lsmc_election_fallback_policy_count": sum(
                fit.election_fallback_used for fit in fits.values()
            ),
            "lsmc_surrender_fallback_policy_count": sum(
                fit.surrender_fallback_used for fit in fits.values()
            ),
            "lsmc_fixed_election_anchor_policy_count": sum(
                fit.selected_fixed_election_step is not None
                for fit in fits.values()
            ),
            "lsmc_action_set": (
                "growth:wait_for_one_year|start_income_now;"
                "income:continue_for_one_year|full_withdrawal_now"
            ),
            "lsmc_income_election": (
                "pathwise_optimal_bellman_policy_with_predeclared_"
                "fixed_strategy_training_anchor"
            ),
            "income_take_up_mode": "optimal_lsmc",
            "income_take_up_source": "frozen_combined_lsmc_policy",
            "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
            "lsmc_decision_grid": (
                "growth:crediting_anniversaries;income:crediting_anniversaries"
            ),
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
        continue_summary_path = None
        continue_model_point_path = None
        continue_recon_path = None
        deterministic_surrender_summary_path = None
        deterministic_surrender_model_point_path = None
        deterministic_surrender_recon_path = None
        continue_summary = None
        deterministic_surrender_summary = None
        if not args.no_factorial_benchmarks:
            if continue_result is None or deterministic_surrender_result is None:
                raise RuntimeError("Factorial benchmark results are missing.")
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
                _build_aggregation_reconciliation(
                    continue_summary, continue_rows
                ),
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
                    "annual_post_election_lapse_policy"
                ),
                "income_action_rule_refitted_under_deterministic_election": False,
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
                "annual_election_rule_from_combined_fit_with_lapse_"
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

        decomposition_path = None
        if (
            continue_summary is not None
            and deterministic_surrender_summary is not None
        ):
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
                "The frozen LSMC policy underperforms the Continue benchmark "
                "out of sample by AUD %.6f per representative contract; the "
                "run is retained unchanged for diagnostics and does not "
                "reselect on the evaluation paths.",
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
        for training_seed_index in range(1, args.training_seed_count):
            seed_triplet = training_seed_triplets[training_seed_index]
            for key, fit in fits_by_seed[training_seed_index].items():
                labels = "|".join(policy_labels.get(key, ["unlabelled"]))
                for diagnostic in fit.diagnostics:
                    diagnostic_rows.append({
                        "training_seed_index": training_seed_index + 1,
                        "primary_training_seed": False,
                        "training_market_seed": seed_triplet["market_seed"],
                        "training_take_up_seed": seed_triplet["take_up_seed"],
                        "training_mortality_seed": seed_triplet[
                            "mortality_seed"
                        ],
                        "policy_labels": labels,
                        "training_scenario_fingerprint": (
                            fit.training_scenario_fingerprint
                        ),
                        "fit_basis_fingerprint": fit.fit_basis_fingerprint,
                        "training_policyholder_value_aud": (
                            fit.training_policyholder_value_aud
                        ),
                        "training_wait_policyholder_value_aud": (
                            fit.training_wait_policyholder_value_aud
                        ),
                        "training_no_action_policyholder_value_aud": (
                            fit.training_no_action_policyholder_value_aud
                        ),
                        "training_candidate_policyholder_value_aud": (
                            fit.training_candidate_policyholder_value_aud
                        ),
                        "training_optionality_uplift_aud": (
                            fit.training_optionality_uplift_aud
                        ),
                        "training_fallback_used": fit.training_fallback_used,
                        "election_fallback_used": fit.election_fallback_used,
                        "surrender_fallback_used": fit.surrender_fallback_used,
                        "selected_fixed_election_step": (
                            fit.selected_fixed_election_step
                        ),
                        "selected_fixed_election_year": (
                            None
                            if fit.selected_fixed_election_step is None
                            else fit.selected_fixed_election_step / 12.0
                        ),
                        "selected_income_action_mode": (
                            fit.selected_income_action_mode
                        ),
                        "candidate_policy_name": "V11",
                        "training_selected_policy_name": (
                            fit.selected_policy_name
                        ),
                        "training_fallback_reason": (
                            fit.training_fallback_reason
                        ),
                        "fit_valid": fit.valid,
                        "fit_invalid_reasons": "|".join(fit.invalid_reasons),
                        "income_action_exposure_coverage": (
                            fit.income_action_exposure_coverage
                        ),
                        "policy_iteration_count": fit.policy_iteration_count,
                        "policy_iteration_converged": (
                            fit.policy_iteration_converged
                        ),
                        "final_action_agreement": fit.final_action_agreement,
                        "final_policy_value_change_aud": (
                            fit.final_policy_value_change_aud
                        ),
                        **diagnostic.as_dict(),
                    })
        for key, fit in fits.items():
            labels = "|".join(policy_labels.get(key, ["unlabelled"]))
            for diagnostic in fit.diagnostics:
                diagnostic_rows.append({
                    "training_seed_index": 1,
                    "primary_training_seed": True,
                    "training_market_seed": args.train_seed,
                    "training_take_up_seed": args.train_take_up_seed,
                    "training_mortality_seed": args.train_mortality_seed,
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
                    "selected_fixed_election_step": (
                        fit.selected_fixed_election_step
                    ),
                    "selected_fixed_election_year": (
                        None
                        if fit.selected_fixed_election_step is None
                        else fit.selected_fixed_election_step / 12.0
                    ),
                    "selected_income_action_mode": (
                        fit.selected_income_action_mode
                    ),
                    "candidate_policy_name": "V11",
                    "training_selected_policy_name": (
                        fit.selected_policy_name
                    ),
                    "training_fallback_reason": (
                        fit.training_fallback_reason
                    ),
                    "fit_valid": fit.valid,
                    "fit_invalid_reasons": "|".join(fit.invalid_reasons),
                    "income_action_exposure_coverage": (
                        fit.income_action_exposure_coverage
                    ),
                    "policy_iteration_count": fit.policy_iteration_count,
                    "policy_iteration_converged": (
                        fit.policy_iteration_converged
                    ),
                    "final_action_agreement": fit.final_action_agreement,
                    "final_policy_value_change_aud": (
                        fit.final_policy_value_change_aud
                    ),
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
                if action_type == "income_action":
                    partial_count = int(stats.get("partial_path_count", 0))
                    full_count = int(stats.get("full_path_count", 0))
                    continue_count = int(stats.get(
                        "continue_path_count",
                        max(int(eligible) - partial_count - full_count, 0),
                    ))
                    distributions = (
                        ("continue", continue_count),
                        ("partial_withdrawal", partial_count),
                        ("full_withdrawal", full_count),
                    )
                else:
                    distributions = (
                        (action_type, int(stats["action_path_count"])),
                    )
                for reported_action, selected_count in distributions:
                    action_rows.append({
                        "training_seed_index": 1,
                        "primary_training_seed": True,
                        "training_market_seed": args.train_seed,
                        "training_take_up_seed": args.train_take_up_seed,
                        "training_mortality_seed": args.train_mortality_seed,
                        "policy_labels": labels,
                        "action_type": reported_action,
                        "phase": (
                            "growth"
                            if reported_action == "income_election"
                            else "income"
                        ),
                        "policy_year": step // 12,
                        "decision_step": step,
                        **stats,
                        "action_path_count": selected_count,
                        "evaluation_action_rate": (
                            selected_count / eligible if eligible else 0.0
                        ),
                        "training_fallback_used": fit.training_fallback_used,
                        "election_fallback_used": fit.election_fallback_used,
                        "surrender_fallback_used": fit.surrender_fallback_used,
                    })
                    policy_action_rows += 1
            if policy_action_rows == 0:
                action_rows.append({
                    "training_seed_index": 1,
                    "primary_training_seed": True,
                    "training_market_seed": args.train_seed,
                    "training_take_up_seed": args.train_take_up_seed,
                    "training_mortality_seed": args.train_mortality_seed,
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
        # Robustness fits are evaluated on the same final paths, so their
        # annual Election/Lapse action distributions are reported as well;
        # only seed 1 remains the predeclared canonical output.
        for training_seed_index in range(1, args.training_seed_count):
            seed_triplet = training_seed_triplets[training_seed_index]
            selected_deployed = deployed_policies_by_seed[
                training_seed_index
            ]
            for key, fit in fits_by_seed[training_seed_index].items():
                labels = "|".join(policy_labels.get(key, ["unlabelled"]))
                deployed = selected_deployed.get(key)
                evaluation_statistics = (
                    {} if deployed is None else deployed.evaluation_statistics
                )
                policy_action_rows = 0
                for (action_type, step), stats in sorted(
                    evaluation_statistics.items()
                ):
                    eligible = stats["eligible_path_count"]
                    if action_type == "income_action":
                        partial_count = int(stats.get("partial_path_count", 0))
                        full_count = int(stats.get("full_path_count", 0))
                        continue_count = int(stats.get(
                            "continue_path_count",
                            max(
                                int(eligible) - partial_count - full_count,
                                0,
                            ),
                        ))
                        distributions = (
                            ("continue", continue_count),
                            ("partial_withdrawal", partial_count),
                            ("full_withdrawal", full_count),
                        )
                    else:
                        distributions = (
                            (action_type, int(stats["action_path_count"])),
                        )
                    for reported_action, selected_count in distributions:
                        action_rows.append({
                            "training_seed_index": training_seed_index + 1,
                            "primary_training_seed": False,
                            "training_market_seed": seed_triplet[
                                "market_seed"
                            ],
                            "training_take_up_seed": seed_triplet[
                                "take_up_seed"
                            ],
                            "training_mortality_seed": seed_triplet[
                                "mortality_seed"
                            ],
                            "policy_labels": labels,
                            "action_type": reported_action,
                            "phase": (
                                "growth"
                                if reported_action == "income_election"
                                else "income"
                            ),
                            "policy_year": step // 12,
                            "decision_step": step,
                            **stats,
                            "action_path_count": selected_count,
                            "evaluation_action_rate": (
                                selected_count / eligible if eligible else 0.0
                            ),
                            "training_fallback_used": (
                                fit.training_fallback_used
                            ),
                            "election_fallback_used": (
                                fit.election_fallback_used
                            ),
                            "surrender_fallback_used": (
                                fit.surrender_fallback_used
                            ),
                        })
                        policy_action_rows += 1
                if policy_action_rows == 0:
                    action_rows.append({
                        "training_seed_index": training_seed_index + 1,
                        "primary_training_seed": False,
                        "training_market_seed": seed_triplet["market_seed"],
                        "training_take_up_seed": seed_triplet[
                            "take_up_seed"
                        ],
                        "training_mortality_seed": seed_triplet[
                            "mortality_seed"
                        ],
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
            logger.info("[7/8] Plots disabled")
        else:
            logger.info("[7/8] Create LSMC portfolio plots")
            figure_paths, matplotlib_version = _create_plots(
                lsmc_summary,
                lsmc_rows,
                output / "figures",
                absolute=bool(lsmc_summary.get(
                    "absolute_portfolio_values_available")),
                include_fair_fee_plot=False,
                logger=logger,
            )

        fit_basis_fingerprints_by_seed = {
            f"training_seed_{training_seed_index + 1}": {
                (
                    f"fit_{index:04d}|labels="
                    f"{'|'.join(policy_labels.get(key, ['unlabelled']))}"
                    f"|policy_signature={key!r}"
                ): fit.fit_basis_fingerprint
                for index, (key, fit) in enumerate(
                    sorted(
                        selected_fits.items(), key=lambda item: str(item[0])
                    ),
                    start=1,
                )
            }
            for training_seed_index, selected_fits in enumerate(fits_by_seed)
        }
        fit_basis_fingerprints = fit_basis_fingerprints_by_seed[
            "training_seed_1"
        ]
        if len(fit_basis_fingerprints) != len(fits):
            raise RuntimeError(
                "LSMC fit-basis provenance keys are not unique."
            )
        if any(
            len(fit_basis_fingerprints_by_seed[f"training_seed_{index + 1}"])
            != len(fits_by_seed[index])
            for index in range(args.training_seed_count)
        ):
            raise RuntimeError(
                "Multi-seed LSMC fit-basis provenance keys are not unique."
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
        logger.info("[8/8] Write run manifest")
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
                "market_cache_keys": {
                    "training": [
                        (
                            scenario.hedge_price_surface.spec.market_cache_key
                            if scenario.hedge_price_surface is not None else None
                        )
                        for scenario in training_scenarios_by_seed
                    ],
                    "validation": (
                        validation_scenarios.hedge_price_surface.spec.market_cache_key
                        if validation_scenarios.hedge_price_surface is not None
                        else None
                    ),
                    "evaluation": lsmc_summary.get("market_cache_key"),
                },
                "scenario_fingerprints": {
                    "training": list(training_scenario_fingerprints),
                    "validation": validation_scenarios.content_fingerprint,
                    "evaluation": lsmc_result.scenario_fingerprint,
                },
                "hedge_cache_keys": {
                    "training": [
                        (
                            scenario.hedge_price_surface.hedge_cache_key
                            if scenario.hedge_price_surface is not None else None
                        )
                        for scenario in training_scenarios_by_seed
                    ],
                    "validation": (
                        validation_scenarios.hedge_price_surface.hedge_cache_key
                        if validation_scenarios.hedge_price_surface is not None
                        else None
                    ),
                    "evaluation": lsmc_summary.get("hedge_cache_key"),
                },
                "hedge_price_surface_fingerprints": {
                    "training": [
                        (
                            scenario.hedge_price_surface.price_surface_fingerprint
                            if scenario.hedge_price_surface is not None else None
                        )
                        for scenario in training_scenarios_by_seed
                    ],
                    "validation": (
                        validation_scenarios.hedge_price_surface.price_surface_fingerprint
                        if validation_scenarios.hedge_price_surface is not None
                        else None
                    ),
                    "evaluation": lsmc_summary.get(
                        "hedge_price_surface_fingerprint"
                    ),
                },
                "hedge_pricing_method": args.hedge_pricing_method,
                "hedge_training_scenario_fingerprints": [
                    (
                        scenario.hedge_price_surface.spec.training_scenario_fingerprint
                        if scenario.hedge_price_surface is not None else None
                    )
                    for scenario in training_scenarios_by_seed
                ],
                "hedge_cross_fit_folds": (
                    training_scenarios.hedge_price_surface.spec.cross_fit_folds
                    if training_scenarios.hedge_price_surface is not None
                    else None
                ),
                "hedge_cap_grid": list(cache_settings["hedge_cap_grid"]),
                "hedge_equity_allocation": equity_allocation.equity_weight,
                "dva_mark_method": "moment_matched_bs",
                "nested_mc_used": False,
                "lsmc_used": True,
                "lsmc_objective": "maximise_policyholder_cashflow_pv",
                "lsmc_candidate_policy": "V11",
                "primary_lsmc_deployed_policy": (
                    deployment_selection_by_seed[0]
                ),
                "lsmc_deployed_policy_by_training_seed": {
                    f"training_seed_{index + 1}": selection
                    for index, selection in enumerate(
                        deployment_selection_by_seed
                    )
                },
                "lsmc_action_set": {
                    "growth": ["wait_for_one_year", "start_income_now"],
                    "income": [
                        "continue_for_one_year", "full_withdrawal_now"
                    ],
                },
                "income_election": "pathwise_optimal_bellman_policy",
                "model_point_income_start_year_use": (
                    "deterministic_validation_benchmarks_only"
                ),
                "decision_frequency": {
                    "income_election": "crediting_anniversaries",
                    "income_lapse": "crediting_anniversaries",
                },
                "earliest_income_election": (
                    "product_min_years_before_income"
                ),
                "forced_income_election": (
                    "first_policy_anniversary_strictly_after_attained_age_100"
                ),
                "first_income_payment": "one_month_after_election",
                "same_step_election_and_full_withdrawal_allowed": False,
                "policy_characterisation": (
                    "cross_fitted_lower_bound_with_ordered_annual_election_"
                    "and_income_lapse"
                ),
                "partial_withdrawal_in_optimal_policy": False,
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
                "behaviour_benchmarks": (
                    {
                        "variable_election_continue": (
                            "V10_internal_validation_control"
                        ),
                        "combined_variable_election_post_behaviour": "V11",
                    }
                    if args.no_factorial_benchmarks
                    else {
                        "deterministic_election_continue": "V00",
                        "deterministic_election_post_behaviour": "V01",
                        "variable_election_continue": "V10",
                        "combined_variable_election_post_behaviour": "V11",
                    }
                ),
                "factorial_benchmark_outputs_enabled": (
                    not args.no_factorial_benchmarks
                ),
            },
            "lsmc_settings": {
                "n_train": args.n_train,
                "train_seed": args.train_seed,
                "train_take_up_seed": args.train_take_up_seed,
                "train_mortality_seed": args.train_mortality_seed,
                "training_seed_count": args.training_seed_count,
                "primary_training_seed_index": 1,
                "primary_seed_selection_rule": (
                    "predeclared_first_seed_not_evaluation_based"
                ),
                "evaluation_used_for_training_seed_selection": False,
                "training_seed_triplets": list(training_seed_triplets),
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
                "training_scenario_fingerprints": list(
                    training_scenario_fingerprints
                ),
                "fit_basis_fingerprints": fit_basis_fingerprints,
                "fit_basis_fingerprints_by_training_seed": (
                    fit_basis_fingerprints_by_seed
                ),
                "fit_basis_includes": [
                    "training_scenario_content",
                    "crediting_cap",
                    "stress_audit",
                    "product",
                    "policy_including_predeclared_benchmark_start",
                    "mortality",
                    "expenses",
                    "projection_config",
                    "lsmc_settings",
                ],
                "n_folds": args.lsmc_folds,
                "income_action_set": args.lsmc_income_action_set,
                "allow_partial_withdrawal": (
                    lsmc_settings.allow_partial_withdrawal
                ),
                "ridge": args.lsmc_ridge,
                "ridge_grid": list(lsmc_settings.ridge_grid),
                "ridge_selection": "oof_decision_loss_one_standard_error",
                "exercise_buffer_rmse_multiplier": (
                    args.exercise_buffer_rmse_multiplier),
                "relative_svd_cutoff": lsmc_settings.relative_svd_cutoff,
                "minimum_regression_observations": (
                    lsmc_settings.minimum_regression_observations
                ),
                "observations_per_coefficient": (
                    lsmc_settings.observations_per_coefficient
                ),
                "maximum_condition_number": (
                    lsmc_settings.maximum_condition_number),
                "fallback_to_no_action_if_training_underperforms": (
                    lsmc_settings.fallback_to_no_action_if_training_underperforms),
                "fallback_semantics": (
                    "training_only_paired_95pct_lower_bound_against_"
                    "predeclared_fixed_election_and_continue_strategies"
                ),
                "material_fit_failure_policy": (
                    "reject_v11_candidate_and_deploy_recorded_fixed_"
                    "validation_benchmark"
                ),
                "unique_policy_fits": len(fits),
                "unique_policy_fits_across_active_training_seeds": sum(
                    len(selected_fits) for selected_fits in fits_by_seed
                ),
                "all_fits_valid_across_active_training_seeds": all(
                    fit.valid
                    for selected_fits in fits_by_seed
                    for fit in selected_fits.values()
                ),
                "unique_policy_fits_across_three_training_seeds": (
                    sum(len(selected_fits) for selected_fits in fits_by_seed)
                    if args.training_seed_count == 3 else 0
                ),
                "all_fits_valid_across_three_training_seeds": (
                    args.training_seed_count == 3
                    and all(
                        fit.valid
                        for selected_fits in fits_by_seed
                        for fit in selected_fits.values()
                    )
                ),
                "primary_only_diagnostic_counts": True,
                "training_fallback_policy_count": sum(
                    fit.training_fallback_used for fit in fits.values()),
                "election_fallback_policy_count": sum(
                    fit.election_fallback_used for fit in fits.values()),
                "surrender_fallback_policy_count": sum(
                    fit.surrender_fallback_used for fit in fits.values()),
                "fixed_election_anchor_policy_count": sum(
                    fit.selected_fixed_election_step is not None
                    for fit in fits.values()
                ),
                "selected_training_anchors": {
                    repr(key): {
                        "fixed_election_step": fit.selected_fixed_election_step,
                        "fixed_election_year": (
                            None
                            if fit.selected_fixed_election_step is None
                            else fit.selected_fixed_election_step / 12.0
                        ),
                        "income_action_mode": fit.selected_income_action_mode,
                    }
                    for key, fit in sorted(
                        fits.items(), key=lambda item: str(item[0])
                    )
                },
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
                "annual_income_lapse_exposure_coverage_min": min(
                    (fit.income_action_exposure_coverage for fit in fits.values()),
                    default=1.0,
                ),
                "policy_iteration_converged_all": all(
                    fit.policy_iteration_converged for fit in fits.values()
                ),
                "policy_iteration_count_max": max(
                    (fit.policy_iteration_count for fit in fits.values()),
                    default=0,
                ),
                "final_action_agreement_min": min(
                    (fit.final_action_agreement for fit in fits.values()),
                    default=1.0,
                ),
                "final_policy_value_change_abs_max_aud": max(
                    (
                        abs(fit.final_policy_value_change_aud)
                        for fit in fits.values()
                    ),
                    default=0.0,
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
                "deterministic_election_benchmarks_same_scenarios": (
                    None if args.no_factorial_benchmarks else True
                ),
                "training_and_evaluation_market_seeds_distinct": (
                    args.train_seed != args.seed
                ),
                "all_training_and_evaluation_market_seeds_distinct": (
                    args.seed not in {
                        int(item["market_seed"])
                        for item in training_seed_triplets
                    }
                ),
                "training_and_evaluation_take_up_seeds_distinct": (
                    args.train_take_up_seed != args.take_up_seed
                ),
                "all_training_and_evaluation_take_up_seeds_distinct": (
                    args.take_up_seed not in {
                        int(item["take_up_seed"])
                        for item in training_seed_triplets
                    }
                ),
                "training_and_evaluation_mortality_seeds_distinct": (
                    args.train_mortality_seed != args.mortality_seed
                ),
                "all_training_and_evaluation_mortality_seeds_distinct": (
                    args.mortality_seed not in {
                        int(item["mortality_seed"])
                        for item in training_seed_triplets
                    }
                ),
                "all_active_frozen_training_policies_evaluated": True,
                "all_three_frozen_training_policies_evaluated": (
                    args.training_seed_count == 3
                ),
                "training_seed_selected_using_evaluation": False,
                "multi_seed_evaluation_scenario_fingerprints": [
                    result.scenario_fingerprint
                    for result in lsmc_results_by_seed
                ],
                "multi_seed_final_evaluation": [
                    {
                        "training_seed_index": row["training_seed_index"],
                        "primary_training_seed": row[
                            "primary_training_seed"
                        ],
                        "training_market_seed": row[
                            "training_market_seed"
                        ],
                        "training_take_up_seed": row[
                            "training_take_up_seed"
                        ],
                        "training_mortality_seed": row[
                            "training_mortality_seed"
                        ],
                        "training_scenario_fingerprint": row[
                            "training_scenario_fingerprint"
                        ],
                        "evaluation_scenario_fingerprint": row[
                            "evaluation_scenario_fingerprint"
                        ],
                        "evaluation_policyholder_value_aud": row[
                            "evaluation_policyholder_value_aud"
                        ],
                        "evaluation_continue_value_aud": row[
                            "evaluation_continue_value_aud"
                        ],
                        "evaluation_minus_continue_aud": row[
                            "evaluation_minus_continue_aud"
                        ],
                        "fit_count": row["fit_count"],
                        "all_fits_valid": row["all_fits_valid"],
                        "candidate_fit_valid": row[
                            "candidate_fit_valid"
                        ],
                        "validation_valid": row["validation_valid"],
                        "deployed_policy": row["deployed_policy"],
                        "validation_fallback_used": row[
                            "validation_fallback_used"
                        ],
                        "validation_fallback_reason": row[
                            "validation_fallback_reason"
                        ],
                        "deployment_valid": row["deployment_valid"],
                        "selected_for_primary_outputs": row[
                            "selected_for_primary_outputs"
                        ],
                        "selection_rule": row["selection_rule"],
                        "evaluation_used_for_seed_selection": row[
                            "evaluation_used_for_seed_selection"
                        ],
                    }
                    for row in multi_seed_report_rows
                ],
                "common_random_numbers_across_behaviour_rollouts": True,
            },
            "validation_settings": {
                "valid": all_deployments_valid,
                "candidate_valid": all_candidate_policies_valid,
                "deployment_valid": all_deployments_valid,
                "training_seed_count": args.training_seed_count,
                "n_paths": args.n_validation,
                "seed": args.validation_seed,
                "take_up_seed": args.validation_take_up_seed,
                "mortality_seed": args.validation_mortality_seed,
                "mortality_seed_used": False,
                "policyholder_mortality_basis": (
                    POLICYHOLDER_LSMC_MORTALITY_BASIS
                ),
                "death_termination_in_policyholder_validation": False,
                "only_voluntary_termination_action": (
                    "FULL_WITHDRAWAL_NOW"
                ),
                "actuarial_evaluation_uses_configured_mortality": True,
                "scenario_fingerprint": (
                    validation_scenarios.content_fingerprint
                ),
                "training_validation_evaluation_fingerprints_distinct": (
                    len({
                        *training_scenario_fingerprints,
                        validation_scenarios.content_fingerprint,
                        lsmc_result.scenario_fingerprint,
                    }) == args.training_seed_count + 2
                ),
                "common_random_numbers_across_policy_and_benchmarks": True,
                "confidence_level": 0.95,
                "noninferiority_margin_basis_points_of_premium": 1.0,
                "gates": validation_gate_rows,
                "primary_training_seed_gates": [
                    gate.as_dict() for gate in validation_result.gates
                ],
                "gates_by_training_seed": {
                    f"training_seed_{index + 1}": [
                        gate.as_dict() for gate in result.gates
                    ]
                    for index, result in enumerate(validation_results_by_seed)
                },
                "every_seed_passes_election_income_combined": (
                    all_candidate_policies_valid
                ),
                "every_seed_passes_or_deploys_validated_fallback": (
                    all_deployments_valid
                ),
                "candidate_fit_valid_by_training_seed": {
                    f"training_seed_{index + 1}": valid
                    for index, valid in candidate_fit_valid_by_seed.items()
                },
                "deployed_policy_by_training_seed": {
                    f"training_seed_{index + 1}": selection
                    for index, selection in enumerate(
                        deployment_selection_by_seed
                    )
                },
                "validation_fallback_reason_by_training_seed": {
                    f"training_seed_{index + 1}": reason
                    for index, reason in validation_fallback_reasons.items()
                },
            },
            "sources": {
                "model_points": model_points.source_metadata(),
                "market": market.source_metadata(),
                "costs": costs.source_metadata(),
                "equity_allocation": equity_allocation.source_metadata(),
                "dynamic_behaviour_benchmark_only": (
                    None
                    if behaviour_assumptions is None
                    else behaviour_assumptions.source_metadata()),
            },
            "model_limitations": [
                "Research valuation gross of reinsurance.",
                "Mortality is illustrative and not an approved production basis.",
                "Optimal behaviour is a cross-fitted LSMC lower-bound policy "
                "with annual Election and annual Income Lapse decisions.",
                "The optimal Income action set is restricted to "
                "CONTINUE_FOR_ONE_YEAR or FULL_WITHDRAWAL_NOW; Partial "
                "Withdrawal is excluded.",
                "The five-year government-bond sleeve, monthly rebalancing to "
                "the CSV-configured target allocation, "
                "absence of bond term premium and other fixed proxy assumptions "
                "remain unchanged from the dynamic benchmark.",
                "The intra-year DVA mark remains a moment-matched BS proxy; "
                "annual new-issue hedge fair values use the selected pricing "
                "method without nested Monte Carlo.",
                (
                    "The fitted-Election/Continue rollout is retained only as "
                    "an internal final-sample validation control; it is not a "
                    "reported Behaviour-effect decomposition."
                    if args.no_factorial_benchmarks
                    else "The fitted-Election/Continue decomposition rollout "
                    "suppresses all voluntary Income actions after fitting; "
                    "its Election rule is not separately re-optimised under a "
                    "Continue-only terminal policy."
                ),
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
                "lsmc_validation_summary_csv": str(validation_summary_path),
                "lsmc_validation_manifest_json": str(
                    validation_manifest_path
                ),
                "lsmc_multi_seed_validation_evaluation_csv": str(
                    multi_seed_report_path
                ),
                "lsmc_vs_continue_summary_csv": str(
                    output / "lsmc_vs_continue_summary.csv"),
                "continue_benchmark": {
                    "semantics": (
                        "election_rule_from_combined_fit_with_"
                        "income_actions_suppressed_in_evaluation"
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
                "deterministic_election_continue_benchmark": (
                    None
                    if continue_summary_path is None
                    else {
                        "portfolio_summary_csv": str(continue_summary_path),
                        "model_point_results_csv": str(
                            continue_model_point_path
                        ),
                        "aggregation_reconciliation_csv": str(
                            continue_recon_path
                        ),
                    }
                ),
                "deterministic_election_post_behaviour_benchmark": (
                    None
                    if deterministic_surrender_summary_path is None
                    else {
                        "portfolio_summary_csv": str(
                            deterministic_surrender_summary_path
                        ),
                        "model_point_results_csv": str(
                            deterministic_surrender_model_point_path
                        ),
                        "aggregation_reconciliation_csv": str(
                            deterministic_surrender_recon_path
                        ),
                    }
                ),
                "behaviour_decomposition_csv": (
                    None if decomposition_path is None else str(decomposition_path)
                ),
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
            "LSMC run completed | fits=%d from three training seeds | "
            "runtime=%.1fs | summary=%s",
            sum(len(selected_fits) for selected_fits in fits_by_seed),
            time.perf_counter() - started,
            summary_path,
        )
        return 0
    except Exception as exc:
        logger.exception("LSMC portfolio run failed")
        # A policy-hook or validation-construction error must not leave a
        # prior successful manifest in place or look like an unvalidated
        # completed run.  Fit-invalid and statistical-gate failures write
        # richer artifacts before raising; this is the fail-closed catch-all
        # for earlier unexpected validation errors.
        validation_manifest = output / "lsmc_validation_manifest.json"
        validation_summary = output / "lsmc_validation_summary.csv"
        if not validation_manifest.exists():
            failure_row = {
                "valid": False,
                "status": "validation_or_fit_exception",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            if not validation_summary.exists():
                _write_csv(validation_summary, [failure_row])
            with validation_manifest.open("w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "generated_at_utc": datetime.now(
                            timezone.utc
                        ).isoformat(),
                        **failure_row,
                        "gates": [],
                    },
                    handle,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                handle.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
