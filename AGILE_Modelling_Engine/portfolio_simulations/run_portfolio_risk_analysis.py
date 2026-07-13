"""Analyse GMLB/GMWB valuation exposures across crediting-cap scenarios.

For every requested scenario Maximum Return, this orchestrator calls both
``run_portfolio_valuation.py`` (statistical/dynamic policyholder behaviour) and
``run_portfolio_valuation_lsmc.py`` (fitted annual LSMC lower-bound Income
surrender policy evaluated out of sample).
The LSMC runner's no-voluntary-action Continue benchmark is retained to split
the cap effect into the Continue-benchmark change and the change in each
behaviour method's value gap versus Continue.

The analysis includes symmetric one-factor shock-and-revalue runs for market,
biometric and expense risks.  The portfolio runners deliberately retain
expected present values and model-point scalars, not pathwise loss
distributions.  Consequently this script does not label model-point dispersion
as VaR/CTE and does not claim to calculate economic capital, Risk Margin or an
APRA/LAGIC stress aggregation.

Independent cap/stress scenario pairs are scheduled together in one parallel
queue.  The default uses up to 16 workers with one BLAS/OpenMP thread per child
so that outer scenario parallelism is not defeated by nested thread
oversubscription.  The optional automatic mode remains deliberately
conservative and gates CPU concurrency by a path/horizon-based LSMC memory
estimate; Dynamic and LSMC remain serial within each pair to bound peak memory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
ENGINE_ROOT = SCRIPT_DIRECTORY.parent
REPOSITORY_ROOT = ENGINE_ROOT.parent
DEFAULT_MARKET_DATA_DIRECTORY = ENGINE_ROOT / "input_market_data"
DEFAULT_ZERO_CURVE_PATH = (
    DEFAULT_MARKET_DATA_DIRECTORY / "australian_zero_curve.csv")
DEFAULT_MODEL_PARAMETERS_PATH = DEFAULT_MARKET_DATA_DIRECTORY / "model_parameters.csv"
DEFAULT_MODEL_POINTS_PATH = (
    REPOSITORY_ROOT
    / "input_model_points_policyholders"
    / "model_points_policyholders.csv"
)
DEFAULT_COST_ASSUMPTIONS_PATH = (
    REPOSITORY_ROOT / "input_cost_assumptions" / "cost_assumptions.csv")
DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY = REPOSITORY_ROOT / "input_dynamic_behaviour"
DYNAMIC_PORTFOLIO_RUNNER = SCRIPT_DIRECTORY / "run_portfolio_valuation.py"
LSMC_PORTFOLIO_RUNNER = SCRIPT_DIRECTORY / "run_portfolio_valuation_lsmc.py"
DEFAULT_OUTPUT_DIRECTORY = SCRIPT_DIRECTORY / "output" / "portfolio_risk_analysis"
DEFAULT_CREDITING_CAP_RATES = (0.04, 0.06, 0.12, 0.20)
DEFAULT_BASELINE_RATE = 0.06
CONTRACTUAL_MINIMUM_CREDITING_CAP_RATE = 0.0025
MINIMUM_LSMC_TRAINING_PATHS = 60
AUTO_WORKER_MEMORY_FRACTION = 0.65
DEFAULT_MAX_WORKERS = 16
AUTO_WORKER_MAXIMUM = 16
AUTO_WORKER_FIXED_BYTES = 1_342_177_280  # 1.25 GiB process/projection overhead
AUTO_WORKER_BYTES_PER_PATH_MONTH = 640
AUTO_WORKER_SAFETY_MULTIPLIER = 1.25
AUTO_WORKER_MINIMUM_MEMORY_RESERVE_BYTES = 2 * 1024 ** 3
DEFAULT_HORIZON_MONTHS_FALLBACK = 70 * 12
DEFAULT_PROJECTION_MAX_AGE = 115.0

MONETARY_METRICS = (
    "premium_aud",
    "pv_policyholder_benefits_aud",
    "pv_terminal_closeout_aud",
    "pv_future_fees_aud",
    "pv_product_fees_aud",
    "pv_lifetime_income_premiums_aud",
    "pv_guarantee_claims_aud",
    "pv_expenses_aud",
    "pv_hedge_costs_aud",
    "pv_crediting_margin_aud",
    "pv_mva_retained_aud",
    "pv_aps_retained_aud",
    "bel_nonunit_aud",
    "bel_total_aud",
    "market_consistent_bel_total_aud",
    "guarantee_value_aud",
    "insurer_net_present_value_before_risk_margin_aud",
    "pv_policyholder_benefits_pre_election_aud",
    "pv_policyholder_benefits_post_election_aud",
    "pv_growth_fees_aud",
    "pv_growth_crediting_margin_aud",
    "pv_post_election_guarantee_claims_aud",
)

# These fields are non-additive portfolio diagnostics.  They must be produced
# by the valuation runners from path/model-point event mass and must never be
# reconstructed by averaging model-point quantiles in this orchestrator.
BEHAVIOUR_SCALAR_METRICS: dict[str, tuple[str, ...]] = {
    "income_start_year_mean": (
        "income_start_year_mean",
        "expected_income_start_year",
    ),
    "income_start_year_median": (
        "income_start_year_median",
        "median_income_start_year",
    ),
    "income_start_year_p10": (
        "income_start_year_p10",
        "p10_income_start_year",
        "income_start_year_q10",
    ),
    "income_start_year_p90": (
        "income_start_year_p90",
        "p90_income_start_year",
        "income_start_year_q90",
    ),
    "income_election_share": (
        "income_election_share",
        "cumulative_income_election_share",
    ),
    "forced_income_election_share": (
        "forced_income_election_share",
        "forced_income_start_share",
    ),
    "mean_growth_duration": (
        "mean_growth_duration",
        "mean_growth_duration_years",
        "average_growth_duration_years",
    ),
    "growth_phase_exposure": (
        "growth_phase_exposure",
        "growth_phase_share",
    ),
    "income_phase_exposure": (
        "income_phase_exposure",
        "income_phase_share",
    ),
    "ordinary_income_lapse_rate": (
        "ordinary_income_lapse_rate",
        "income_lapse_ordinary_rate",
    ),
    "performance_income_lapse_rate": (
        "performance_income_lapse_rate",
        "income_lapse_performance_rate",
    ),
    "total_income_lapse_rate": (
        "total_income_lapse_rate",
        "income_lapse_total_rate",
        "income_phase_lapse_rate",
        "income_phase_full_withdrawal_rate",
    ),
}

BEHAVIOUR_POLICY_YEAR_PATTERNS = (
    re.compile(r"^income_election_share_policy_year_(\d+)$"),
    re.compile(r"^growth_phase_share_policy_year_(\d+)$"),
    re.compile(r"^income_phase_share_policy_year_(\d+)$"),
)

BENCHMARK_IDS = (
    "deterministic_election_continue",
    "deterministic_election_post_behaviour",
    "variable_election_continue",
)

BENCHMARK_DIRECTORY_ALIASES: dict[str, tuple[str, ...]] = {
    "deterministic_election_continue": (
        "deterministic_election_continue",
        "deterministic_election_no_voluntary_exit",
    ),
    "deterministic_election_post_behaviour": (
        "deterministic_election_post_behaviour",
        "deterministic_election_post_election_behaviour",
    ),
    "variable_election_continue": (
        "variable_election_continue",
        "dynamic_election_continue",
        "optimal_election_continue",
    ),
}

MODEL_POINT_COMPARISON_METRICS = (
    "premium_aud",
    "pv_policyholder_benefits_aud",
    "pv_future_fees_aud",
    "pv_guarantee_claims_aud",
    "pv_expenses_aud",
    "pv_hedge_costs_aud",
    "pv_crediting_margin_aud",
    "bel_total_aud",
    "guarantee_value_aud",
    "insurer_net_present_value_before_risk_margin_aud",
    "new_business_margin_before_risk_margin",
    "pv_policyholder_benefits_pre_election_aud",
    "pv_policyholder_benefits_post_election_aud",
    "pv_growth_fees_aud",
    "pv_growth_crediting_margin_aud",
    "pv_post_election_guarantee_claims_aud",
)

DECOMPOSITION_METRICS = (
    "pv_policyholder_benefits_aud",
    "pv_policyholder_benefits_pre_election_aud",
    "pv_policyholder_benefits_post_election_aud",
    "pv_guarantee_claims_aud",
    "pv_future_fees_aud",
    "pv_growth_fees_aud",
    "pv_crediting_margin_aud",
    "pv_growth_crediting_margin_aud",
    "insurer_net_present_value_before_risk_margin_aud",
)

# Research shock-and-revalue definitions reuse the engine's CapitalStresses
# conventions.  They are kept as separate one-factor scenarios and are not an
# APRA/LAGIC or Solvency-II aggregation.
STRESS_DEFINITIONS: dict[str, dict[str, object]] = {
    "interest_up": {
        "risk_category": "interest_rate",
        "label": "Interest-rate up",
        "description": (
            "Tenor-dependent relative upward zero-curve stress with the "
            "CapitalStresses minimum +100 bp shift."
        ),
    },
    "interest_down": {
        "risk_category": "interest_rate",
        "label": "Interest-rate down",
        "description": (
            "Tenor-dependent relative downward zero-curve stress from "
            "CapitalStresses."
        ),
    },
    "equity_level_down": {
        "risk_category": "equity_level",
        "label": "Equity level -39%",
        "description": (
            "CapitalStresses type-1 equity shock applied to both simulated "
            "equity indices from month one; the indexed account is not shocked "
            "as a unit-linked spot holding at time zero."
        ),
    },
    "equity_volatility_up": {
        "risk_category": "equity_volatility",
        "label": "Equity volatility +25%",
        "description": (
            "Relative +25% stress to Black-Scholes sigma and Heston initial/"
            "long-run volatility levels."
        ),
    },
    "longevity": {
        "risk_category": "longevity",
        "label": "Longevity: qx -20%",
        "description": "Multiplicative 0.80 stress to all mortality rates.",
    },
    "mortality": {
        "risk_category": "mortality",
        "label": "Mortality: qx +15%",
        "description": "Multiplicative 1.15 stress to all mortality rates.",
    },
    "expense": {
        "risk_category": "expense",
        "label": "Expense level/inflation up",
        "description": (
            "Maintenance expense level +10% and expense inflation +100 bp."
        ),
    },
}
DEFAULT_STRESS_SCENARIOS = tuple(STRESS_DEFINITIONS)


def _parse_rate(text: str) -> float:
    """Parse decimals or percentages; bare percentage points require value >= 1."""
    raw = str(text).strip()
    is_percent = raw.endswith("%")
    if is_percent:
        raw = raw[:-1].strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid crediting-cap rate: {text!r}"
        ) from exc
    if is_percent or value >= 1.0:
        value /= 100.0
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(
            "crediting-cap rates must be between 0% and 100%"
        )
    return value


def _parse_max_workers(text: str) -> Optional[int]:
    """Parse an explicit positive worker count or the automatic default."""
    raw = str(text).strip().lower()
    if raw == "auto":
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--max-workers must be 'auto' or a positive integer"
        ) from exc
    if value <= 0:
        raise argparse.ArgumentTypeError(
            "--max-workers must be 'auto' or a positive integer"
        )
    return value


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--crediting-rates",
        nargs="+",
        type=_parse_rate,
        default=list(DEFAULT_CREDITING_CAP_RATES),
        metavar="RATE",
        help=(
            "scenario Maximum Returns; accepts 0.06, 6%% or 6. Values below "
            "1 without %% are decimals, so 0.25%% must be 0.25%% or 0.0025"
        ),
    )
    parser.add_argument(
        "--baseline-rate",
        type=_parse_rate,
        default=DEFAULT_BASELINE_RATE,
        help="comparison baseline; automatically added to the scenario set",
    )
    parser.add_argument("--n-paths", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--take-up-seed", type=int, default=97)
    parser.add_argument("--mortality-seed", type=int, default=197)
    parser.add_argument("--n-train", type=int, default=4_000)
    parser.add_argument("--train-seed", type=int, default=12026)
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument("--lsmc-folds", type=int, default=5)
    parser.add_argument("--lsmc-ridge", type=float, default=1.0e-6)
    parser.add_argument(
        "--exercise-buffer-rmse-multiplier",
        type=float,
        default=0.25,
    )
    parser.add_argument("--portfolio-contract-count", type=float, default=None)
    parser.add_argument("--profitability-materiality-bp", type=float, default=1.0)
    parser.add_argument("--model-points", type=Path, default=None)
    parser.add_argument("--cost-assumptions", type=Path, default=None)
    parser.add_argument("--cost-assumption-set", default=None)
    parser.add_argument("--dynamic-behaviour", type=Path, default=None)
    parser.add_argument("--behaviour-assumption-set", default=None)
    parser.add_argument("--zero-curve", type=Path, default=None)
    parser.add_argument("--model-parameters", type=Path, default=None)
    parser.add_argument(
        "--scenario-plots",
        action="store_true",
        help="also create each valuation runner's standard plots",
    )
    parser.add_argument(
        "--stress-scenarios",
        nargs="+",
        choices=tuple(STRESS_DEFINITIONS),
        default=list(DEFAULT_STRESS_SCENARIOS),
        metavar="STRESS",
        help=(
            "one-factor shock-and-revalue scenarios; each selected stress is "
            "run for every cap and both policyholder-behaviour methods"
        ),
    )
    parser.add_argument(
        "--no-stress-analysis",
        action="store_true",
        help=(
            "skip the market, biometric and expense shock-and-revalue grid; "
            "the cap/behaviour exposure analysis is still produced"
        ),
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help=(
            "reuse complete scenario outputs after validating cap, settings, "
            "basis, model points, reconciliations and scenario fingerprints"
        ),
    )
    parser.add_argument(
        "--max-workers",
        type=_parse_max_workers,
        default=DEFAULT_MAX_WORKERS,
        metavar="AUTO_OR_N",
        help=(
            "parallel independent cap/stress scenario pairs in one combined "
            "queue. The configured default keeps up to 16 single-threaded "
            "valuation children busy; 'auto' instead uses a conservative "
            "CPU/RAM estimate"
        ),
    )
    parser.add_argument(
        "--blas-threads",
        type=int,
        default=1,
        help=(
            "BLAS/OpenMP threads per valuation child process; one prevents "
            "CPU oversubscription when scenario workers run in parallel"
        ),
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="write CSV/report/manifest outputs without analysis figures",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="WARNING",
    )
    args = parser.parse_args(argv)
    args.stress_scenarios = list(dict.fromkeys(args.stress_scenarios))

    resolved_python = shutil.which(str(args.python_executable))
    if resolved_python is None:
        parser.error(
            f"--python-executable cannot be resolved: {args.python_executable!r}"
        )
    args.python_executable = str(Path(resolved_python).resolve())

    for name in ("n_paths", "n_train", "heston_substeps"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.n_train < MINIMUM_LSMC_TRAINING_PATHS:
        parser.error(
            f"--n-train must be at least {MINIMUM_LSMC_TRAINING_PATHS} so "
            "the current LSMC feature set can produce regression diagnostics"
        )
    if args.lsmc_folds < 2:
        parser.error("--lsmc-folds must be at least two")
    if args.blas_threads <= 0:
        parser.error("--blas-threads must be positive")
    if any(
        seed < 0
        for seed in (
            args.seed,
            args.train_seed,
            args.take_up_seed,
            args.mortality_seed,
        )
    ):
        parser.error("seeds must be non-negative")
    if args.seed == args.train_seed:
        parser.error("--seed and --train-seed must be different")
    for name in ("lsmc_ridge", "exercise_buffer_rmse_multiplier"):
        value = float(getattr(args, name))
        if not math.isfinite(value) or value < 0.0:
            parser.error(f"--{name.replace('_', '-')} must be non-negative")
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
    for name in ("zero_curve", "model_parameters"):
        path = getattr(args, name)
        if path is not None and path.expanduser().resolve().parent != (
            DEFAULT_MARKET_DATA_DIRECTORY.resolve()
        ):
            parser.error(
                f"--{name.replace('_', '-')} must be sourced from "
                f"{DEFAULT_MARKET_DATA_DIRECTORY}"
            )
    return args


def _rate_key(rate: float) -> float:
    return round(float(rate), 12)


def _rate_directory_name(rate: float) -> str:
    percentage = f"{100.0 * rate:.10f}".rstrip("0").rstrip(".")
    return f"crediting_cap_{percentage.replace('.', 'p')}pct"


def _optional_argument(command: list[str], flag: str, value: object) -> None:
    if value is not None:
        if isinstance(value, Path):
            value = value.expanduser().resolve()
        command.extend((flag, str(value)))


def _append_shared_inputs(command: list[str], args: argparse.Namespace) -> None:
    _optional_argument(command, "--portfolio-contract-count",
                       args.portfolio_contract_count)
    _optional_argument(command, "--model-points", args.model_points)
    _optional_argument(command, "--cost-assumptions", args.cost_assumptions)
    _optional_argument(command, "--cost-assumption-set", args.cost_assumption_set)
    _optional_argument(command, "--dynamic-behaviour", args.dynamic_behaviour)
    _optional_argument(
        command, "--behaviour-assumption-set", args.behaviour_assumption_set)
    _optional_argument(command, "--zero-curve", args.zero_curve)
    _optional_argument(command, "--model-parameters", args.model_parameters)


def _dynamic_command(
    args: argparse.Namespace,
    rate: float,
    output: Path,
    *,
    stress_scenario: str = "base",
    income_election_mode: str = "dynamic",
    post_income_behaviour: str = "dynamic",
) -> list[str]:
    command = [
        str(args.python_executable),
        str(DYNAMIC_PORTFOLIO_RUNNER),
        "--crediting-cap-rate", f"{rate:.12g}",
        "--stress-scenario", stress_scenario,
        "--income-election-mode", income_election_mode,
        "--post-income-behaviour", post_income_behaviour,
        "--n-paths", str(args.n_paths),
        "--seed", str(args.seed),
        "--take-up-seed", str(args.take_up_seed),
        "--mortality-seed", str(args.mortality_seed),
        "--heston-substeps", str(args.heston_substeps),
        "--profitability-materiality-bp",
        str(args.profitability_materiality_bp),
        "--log-level", args.log_level,
        "--output", str(output),
    ]
    if not args.scenario_plots:
        command.append("--no-plots")
    _append_shared_inputs(command, args)
    return command


def _dynamic_benchmark_directories(dynamic_output: Path) -> dict[str, Path]:
    root = dynamic_output.parent / "dynamic_benchmarks"
    return {
        "deterministic_election_continue": (
            root / "deterministic_election_continue"
        ),
        "deterministic_election_post_behaviour": (
            root / "deterministic_election_post_behaviour"
        ),
        "variable_election_continue": root / "dynamic_election_continue",
    }


def _lsmc_benchmark_directories(lsmc_output: Path) -> dict[str, Path]:
    root = lsmc_output / "benchmarks"
    return {
        "deterministic_election_continue": (
            root / "deterministic_election_continue"
        ),
        "deterministic_election_post_behaviour": (
            root / "deterministic_election_post_behaviour"
        ),
        # The established Continue directory is retained as a compatibility
        # output name, but its new semantics must be optimal Election followed
        # by CONTINUE and are validated through the parent manifest.
        "variable_election_continue": lsmc_output / "continue_benchmark",
    }


def _dynamic_benchmark_commands(
    args: argparse.Namespace,
    rate: float,
    dynamic_output: Path,
    *,
    stress_scenario: str,
) -> tuple[tuple[str, ...], ...]:
    directories = _dynamic_benchmark_directories(dynamic_output)
    specifications = (
        ("deterministic_election_continue", "deterministic", "continue"),
        (
            "deterministic_election_post_behaviour",
            "deterministic",
            "dynamic",
        ),
        ("variable_election_continue", "dynamic", "continue"),
    )
    return tuple(
        tuple(_dynamic_command(
            args,
            rate,
            directories[benchmark_id],
            stress_scenario=stress_scenario,
            income_election_mode=election_mode,
            post_income_behaviour=post_behaviour,
        ))
        for benchmark_id, election_mode, post_behaviour in specifications
    )


def _lsmc_command(
    args: argparse.Namespace,
    rate: float,
    output: Path,
    *,
    stress_scenario: str = "base",
) -> list[str]:
    command = [
        str(args.python_executable),
        str(LSMC_PORTFOLIO_RUNNER),
        "--crediting-cap-rate", f"{rate:.12g}",
        "--stress-scenario", stress_scenario,
        "--n-paths", str(args.n_paths),
        "--seed", str(args.seed),
        "--n-train", str(args.n_train),
        "--train-seed", str(args.train_seed),
        "--heston-substeps", str(args.heston_substeps),
        "--lsmc-folds", str(args.lsmc_folds),
        "--lsmc-ridge", str(args.lsmc_ridge),
        "--exercise-buffer-rmse-multiplier",
        str(args.exercise_buffer_rmse_multiplier),
        "--profitability-materiality-bp",
        str(args.profitability_materiality_bp),
        "--no-dynamic-benchmark",
        "--log-level", args.log_level,
        "--output", str(output),
    ]
    if not args.scenario_plots:
        command.append("--no-plots")
    _append_shared_inputs(command, args)
    return command


@dataclass(frozen=True)
class ScenarioJob:
    """One independent scenario pair with isolated output directories."""

    sequence: int
    stress_id: str
    rate: float
    dynamic_output: Path
    lsmc_output: Path
    dynamic_command: tuple[str, ...]
    dynamic_benchmark_commands: tuple[tuple[str, ...], ...]
    lsmc_command: tuple[str, ...]
    reuse: bool

    @property
    def label(self) -> str:
        return f"{self.stress_id} / cap {100.0 * self.rate:.2f}%"


@dataclass(frozen=True)
class WorkerPlan:
    """Auditable concurrency decision for valuation child processes."""

    requested_workers: object
    selected_workers: int
    safe_auto_workers: int
    logical_cpu_count: int
    cpu_worker_limit: int
    available_memory_bytes: Optional[int]
    memory_detection_method: str
    memory_budget_bytes: Optional[int]
    memory_worker_limit: Optional[int]
    estimated_worker_bytes: int
    estimated_horizon_months: int
    horizon_estimation_source: str
    blas_threads_per_child: int
    total_job_count: int
    pending_job_count: int
    reused_job_count: int
    configured_workers_exceed_safe_auto: bool
    single_worker_estimate_exceeds_budget: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "requested_workers": self.requested_workers,
            "selected_workers": self.selected_workers,
            "safe_auto_workers": self.safe_auto_workers,
            "logical_cpu_count": self.logical_cpu_count,
            "cpu_worker_limit": self.cpu_worker_limit,
            "automatic_worker_ceiling": AUTO_WORKER_MAXIMUM,
            "available_memory_bytes_at_planning": self.available_memory_bytes,
            "memory_detection_method": self.memory_detection_method,
            "memory_budget_bytes": self.memory_budget_bytes,
            "memory_budget_fraction_of_available": AUTO_WORKER_MEMORY_FRACTION,
            "minimum_memory_reserve_bytes": (
                AUTO_WORKER_MINIMUM_MEMORY_RESERVE_BYTES
            ),
            "memory_worker_limit": self.memory_worker_limit,
            "estimated_peak_bytes_per_worker": self.estimated_worker_bytes,
            "memory_estimate_fixed_bytes": AUTO_WORKER_FIXED_BYTES,
            "memory_estimate_bytes_per_path_month": (
                AUTO_WORKER_BYTES_PER_PATH_MONTH
            ),
            "memory_estimate_safety_multiplier": (
                AUTO_WORKER_SAFETY_MULTIPLIER
            ),
            "estimated_horizon_months": self.estimated_horizon_months,
            "horizon_estimation_source": self.horizon_estimation_source,
            "blas_threads_per_child": self.blas_threads_per_child,
            "total_scenario_pair_jobs": self.total_job_count,
            "pending_scenario_pair_jobs": self.pending_job_count,
            "reused_scenario_pair_jobs": self.reused_job_count,
            "configured_workers_exceed_safe_auto": (
                self.configured_workers_exceed_safe_auto
            ),
            "single_worker_estimate_exceeds_memory_budget": (
                self.single_worker_estimate_exceeds_budget
            ),
            "serial_fallback_used_despite_memory_estimate": (
                self.single_worker_estimate_exceeds_budget
                and self.pending_job_count > 0
                and self.selected_workers == 1
            ),
            "estimation_is_conservative_not_a_hard_memory_guarantee": True,
        }


def _logical_cpu_count() -> int:
    """Return CPUs available to this process, respecting affinity if possible."""
    process_counter = getattr(os, "process_cpu_count", None)
    if callable(process_counter):
        try:
            count = process_counter()
            if count is not None and int(count) > 0:
                return int(count)
        except (OSError, TypeError, ValueError):
            pass
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            get_current_process = kernel32.GetCurrentProcess
            get_current_process.restype = ctypes.c_void_p
            get_process_affinity_mask = kernel32.GetProcessAffinityMask
            get_process_affinity_mask.argtypes = (
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_size_t),
                ctypes.POINTER(ctypes.c_size_t),
            )
            get_process_affinity_mask.restype = ctypes.c_int
            process_mask = ctypes.c_size_t()
            system_mask = ctypes.c_size_t()
            if get_process_affinity_mask(
                get_current_process(),
                ctypes.byref(process_mask),
                ctypes.byref(system_mask),
            ):
                affinity_count = int(process_mask.value).bit_count()
                if affinity_count > 0:
                    return affinity_count
        except (AttributeError, OSError, TypeError, ValueError):
            pass
    affinity_getter = getattr(os, "sched_getaffinity", None)
    if callable(affinity_getter):
        try:
            affinity_count = len(affinity_getter(0))
            if affinity_count > 0:
                return affinity_count
        except (OSError, TypeError, ValueError):
            pass
    return max(1, int(os.cpu_count() or 1))


def _available_memory_bytes() -> tuple[Optional[int], str]:
    """Detect currently available physical memory without new dependencies."""
    if os.name == "nt":
        try:
            import ctypes

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(status)
            ):
                available = int(status.ullAvailPhys)
                if available > 0:
                    return available, "windows_global_memory_status_ex"
        except (AttributeError, OSError, TypeError, ValueError):
            pass

    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        try:
            for line in meminfo.read_text(encoding="ascii").splitlines():
                if line.startswith("MemAvailable:"):
                    available = int(line.split()[1]) * 1024
                    if available > 0:
                        return available, "proc_meminfo_mem_available"
        except (IndexError, OSError, UnicodeError, ValueError):
            pass

    try:
        available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        available = available_pages * page_size
        if available > 0:
            return available, "posix_sysconf_available_pages"
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    return None, "unavailable"


def _estimate_horizon_months(
    model_points_path: Path,
) -> tuple[int, str]:
    """Estimate the longest default projection from covered-life ages."""
    path = model_points_path.expanduser().resolve()
    minimum_age: Optional[float] = None
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                for field in ("primary_age", "secondary_age"):
                    raw = str(row.get(field, "")).strip()
                    if not raw:
                        continue
                    age = float(raw)
                    if math.isfinite(age) and 0.0 < age < DEFAULT_PROJECTION_MAX_AGE:
                        minimum_age = (
                            age
                            if minimum_age is None
                            else min(minimum_age, age)
                        )
    except (OSError, TypeError, ValueError, csv.Error):
        return (
            DEFAULT_HORIZON_MONTHS_FALLBACK,
            f"fallback_after_unreadable_model_points:{path}",
        )
    if minimum_age is None:
        return (
            DEFAULT_HORIZON_MONTHS_FALLBACK,
            f"fallback_no_valid_covered_life_ages:{path}",
        )
    remaining_years = max(
        1,
        int(math.ceil(DEFAULT_PROJECTION_MAX_AGE - minimum_age)),
    )
    return 12 * remaining_years, f"covered_life_ages:{path}"


def _estimate_worker_memory_bytes(
    args: argparse.Namespace,
    horizon_months: int,
) -> int:
    """Conservative peak proxy for one LSMC valuation child process."""
    path_month_cells = (
        (int(args.n_train) + int(args.n_paths)) * (horizon_months + 1)
    )
    estimate = (
        AUTO_WORKER_FIXED_BYTES
        + AUTO_WORKER_BYTES_PER_PATH_MONTH * path_month_cells
    )
    if args.scenario_plots:
        estimate += 256 * 1024 ** 2
    return int(math.ceil(AUTO_WORKER_SAFETY_MULTIPLIER * estimate))


def _resolve_worker_plan(
    args: argparse.Namespace,
    jobs: Sequence[ScenarioJob],
) -> WorkerPlan:
    pending_count = sum(not job.reuse for job in jobs)
    logical_cpus = _logical_cpu_count()
    # Leave roughly half the logical CPUs to the OS/hyperthreads and account
    # for any explicit BLAS fan-out within every valuation child.
    cpu_limit = min(
        AUTO_WORKER_MAXIMUM,
        max(1, (logical_cpus // 2) // int(args.blas_threads)),
    )
    model_points_path = (
        args.model_points
        if args.model_points is not None
        else DEFAULT_MODEL_POINTS_PATH
    )
    horizon_months, horizon_source = _estimate_horizon_months(
        Path(model_points_path)
    )
    estimated_worker_bytes = _estimate_worker_memory_bytes(
        args,
        horizon_months,
    )
    available_memory, memory_method = _available_memory_bytes()
    memory_budget: Optional[int]
    memory_limit: Optional[int]
    estimate_exceeds_budget = False
    if available_memory is None:
        memory_budget = None
        memory_limit = None
        safe_auto_workers = 1
    else:
        memory_budget = max(
            0,
            min(
                int(available_memory * AUTO_WORKER_MEMORY_FRACTION),
                available_memory - AUTO_WORKER_MINIMUM_MEMORY_RESERVE_BYTES,
            ),
        )
        estimate_exceeds_budget = estimated_worker_bytes > memory_budget
        memory_limit = memory_budget // estimated_worker_bytes
        # Keep the historical one-process capability available even if the
        # deliberately conservative estimate finds no RAM-safe concurrency.
        safe_auto_workers = min(cpu_limit, max(1, memory_limit))
    if pending_count:
        safe_auto_workers = min(safe_auto_workers, pending_count)
    else:
        safe_auto_workers = 1

    requested = args.max_workers
    if requested is None:
        selected_workers = safe_auto_workers
        requested_for_audit: object = "auto"
        exceeds_auto = False
    else:
        requested_count = int(requested)
        selected_workers = (
            min(requested_count, pending_count) if pending_count else 1
        )
        requested_for_audit = requested_count
        exceeds_auto = selected_workers > safe_auto_workers

    return WorkerPlan(
        requested_workers=requested_for_audit,
        selected_workers=max(1, selected_workers),
        safe_auto_workers=max(1, safe_auto_workers),
        logical_cpu_count=logical_cpus,
        cpu_worker_limit=cpu_limit,
        available_memory_bytes=available_memory,
        memory_detection_method=memory_method,
        memory_budget_bytes=memory_budget,
        memory_worker_limit=memory_limit,
        estimated_worker_bytes=estimated_worker_bytes,
        estimated_horizon_months=horizon_months,
        horizon_estimation_source=horizon_source,
        blas_threads_per_child=int(args.blas_threads),
        total_job_count=len(jobs),
        pending_job_count=pending_count,
        reused_job_count=len(jobs) - pending_count,
        configured_workers_exceed_safe_auto=exceeds_auto,
        single_worker_estimate_exceeds_budget=estimate_exceeds_budget,
    )


def _format_gib(value: Optional[int]) -> str:
    if value is None:
        return "unknown"
    return f"{value / 1024 ** 3:.2f} GiB"


def _child_environment(blas_threads: int, output: Path) -> dict[str, str]:
    """Build an isolated, non-oversubscribed child-process environment."""
    environment = os.environ.copy()
    thread_count = str(blas_threads)
    for variable in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "BLIS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "NUMBA_NUM_THREADS",
        "RAYON_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        environment[variable] = thread_count
    environment["OMP_DYNAMIC"] = "FALSE"
    environment["MKL_DYNAMIC"] = "FALSE"
    environment["PYTHONUNBUFFERED"] = "1"
    environment["MPLBACKEND"] = "Agg"
    mpl_config = output / ".matplotlib"
    mpl_config.mkdir(parents=True, exist_ok=True)
    environment["MPLCONFIGDIR"] = str(mpl_config)
    return environment


def _run_logged_command(
    command: Sequence[str],
    output: Path,
    *,
    blas_threads: int,
) -> None:
    """Execute one child with an invalidated completion marker and own log."""
    output.mkdir(parents=True, exist_ok=True)
    completion_manifest = output / "run_manifest.json"
    try:
        completion_manifest.unlink()
    except FileNotFoundError:
        pass
    log_path = output / "orchestrator_console.log"
    environment = _child_environment(blas_threads, output)
    with log_path.open("w", encoding="utf-8", newline="") as log_handle:
        log_handle.write("Command: ")
        log_handle.write(subprocess.list2cmdline(list(command)))
        log_handle.write("\n")
        log_handle.write(f"BLAS/OpenMP threads: {blas_threads}\n\n")
        log_handle.flush()
        try:
            completed = subprocess.run(
                list(command),
                check=False,
                cwd=str(ENGINE_ROOT),
                env=environment,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as exc:
            raise RuntimeError(
                f"Could not start valuation command; see {log_path}"
            ) from exc
    if completed.returncode != 0:
        raise RuntimeError(
            "Valuation command failed with exit code "
            f"{completed.returncode}; see {log_path}"
        )


def _execute_scenario_job(job: ScenarioJob, blas_threads: int) -> None:
    """Run all Dynamic variants then LSMC within one memory-budgeted worker."""
    _run_logged_command(
        job.dynamic_command,
        job.dynamic_output,
        blas_threads=blas_threads,
    )
    benchmark_directories = tuple(
        _dynamic_benchmark_directories(job.dynamic_output).values()
    )
    if len(benchmark_directories) != len(job.dynamic_benchmark_commands):
        raise ValueError("Dynamic benchmark command/output counts differ.")
    for command, benchmark_output in zip(
        job.dynamic_benchmark_commands,
        benchmark_directories,
    ):
        _run_logged_command(
            command,
            benchmark_output,
            blas_threads=blas_threads,
        )
    _run_logged_command(
        job.lsmc_command,
        job.lsmc_output,
        blas_threads=blas_threads,
    )


def _run_pending_jobs(
    jobs: Sequence[ScenarioJob],
    worker_plan: WorkerPlan,
    *,
    phase_label: str,
) -> None:
    pending = sorted(
        (job for job in jobs if not job.reuse),
        key=lambda job: job.sequence,
    )
    reused_count = len(jobs) - len(pending)
    if not pending:
        print(
            f"{phase_label}: all {reused_count} scenario pairs reused; "
            "no child process started.",
            flush=True,
        )
        return
    effective_workers = min(worker_plan.selected_workers, len(pending))
    print(
        f"{phase_label}: {len(pending)} scenario pairs to run, "
        f"{reused_count} reused, {effective_workers} worker(s).",
        flush=True,
    )
    if effective_workers == 1:
        for index, job in enumerate(pending, start=1):
            print(
                f"[{phase_label} {index}/{len(pending)}] Run {job.label}",
                flush=True,
            )
            _execute_scenario_job(job, worker_plan.blas_threads_per_child)
        return

    executor = ThreadPoolExecutor(
        max_workers=effective_workers,
        thread_name_prefix="portfolio-scenario",
    )
    futures: dict[Future[None], ScenarioJob] = {}
    completed_count = 0
    failed = False
    try:
        for job in pending:
            future = executor.submit(
                _execute_scenario_job,
                job,
                worker_plan.blas_threads_per_child,
            )
            futures[future] = job
        for future in as_completed(futures):
            job = futures[future]
            future.result()
            completed_count += 1
            print(
                f"[{phase_label} {completed_count}/{len(pending)}] "
                f"Completed {job.label}",
                flush=True,
            )
    except BaseException:
        failed = True
        for future in futures:
            future.cancel()
        raise
    finally:
        executor.shutdown(wait=True, cancel_futures=failed)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_single_csv_row(path: Path) -> dict[str, str]:
    rows = _read_csv(path)
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one row in {path}, found {len(rows)}")
    return rows[0]


def _sole_assumption_set(paths: Sequence[Path], label: str) -> str:
    sets: Optional[set[str]] = None
    for path in paths:
        current = {
            str(row.get("assumption_set_id", "")).strip()
            for row in _read_csv(path)
        }
        if "" in current or not current:
            raise ValueError(f"{label} has missing assumption_set_id values.")
        if sets is None:
            sets = current
        elif sets != current:
            raise ValueError(f"{label} files contain different assumption sets.")
    available = sorted(sets or ())
    if len(available) != 1:
        raise ValueError(
            f"{label} requires an explicit assumption set; available: "
            + ", ".join(available)
        )
    return available[0]


def _read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_source_file_hash(
    source_path: object,
    expected_sha256: object,
    label: str,
) -> None:
    path = Path(str(source_path)).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{label} source file no longer exists: {path}")
    expected = str(expected_sha256)
    if not expected or expected == "None":
        raise ValueError(f"{label} manifest has no source SHA256.")
    actual = _file_sha256(path)
    if actual.lower() != expected.lower():
        raise ValueError(
            f"{label} source changed since the cached valuation: "
            f"manifest={expected}, current={actual}"
        )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty CSV: {path}")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _as_float(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Missing or invalid numeric field {field}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Non-finite numeric field {field}")
    return number


def _first_float(
    row: Mapping[str, object],
    fields: Sequence[str],
    *,
    label: str,
) -> float:
    """Read one required numeric field while allowing harmless schema aliases."""
    for field in fields:
        if row.get(field) not in (None, ""):
            return _as_float(row.get(field), field)
    raise ValueError(
        f"{label} is missing; expected one of {', '.join(fields)}."
    )


def _extract_behaviour_metrics(
    summary: Mapping[str, object],
    *,
    label: str,
) -> dict[str, float]:
    """Extract runner-aggregated Behaviour metrics without averaging tails."""
    metrics = {
        canonical: _first_float(summary, aliases, label=f"{label} {canonical}")
        for canonical, aliases in BEHAVIOUR_SCALAR_METRICS.items()
    }
    for key, value in summary.items():
        key_text = str(key)
        if any(pattern.match(key_text) for pattern in BEHAVIOUR_POLICY_YEAR_PATTERNS):
            metrics[key_text] = _as_float(value, f"{label} {key_text}")
    if not any(key.startswith("income_election_share_policy_year_") for key in metrics):
        raise ValueError(
            f"{label} has no policy-year Income-Election distribution fields."
        )
    if not any(key.startswith("growth_phase_share_policy_year_") for key in metrics):
        raise ValueError(
            f"{label} has no policy-year Growth-phase exposure fields."
        )
    return metrics


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _safe_ratio(numerator: float, denominator: float) -> Optional[float]:
    if math.isclose(denominator, 0.0, rel_tol=0.0, abs_tol=1.0e-14):
        return None
    return numerator / denominator


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1.0e-10, abs_tol=1.0e-8)


def _require_close(left: float, right: float, label: str) -> None:
    if not _close(left, right):
        raise ValueError(f"{label} mismatch: {left} != {right}")


def _validate_reconciliation(path: Path, label: str) -> None:
    rows = _read_csv(path)
    if not rows:
        raise ValueError(f"Empty aggregation reconciliation for {label}: {path}")
    failures = [
        str(row.get("metric", "<unknown>"))
        for row in rows
        if not _as_bool(row.get("within_numerical_tolerance"))
    ]
    if failures:
        raise ValueError(
            f"Aggregation reconciliation failed for {label}: "
            + ", ".join(failures)
        )


def _validate_live_aggregation(
    summary: Mapping[str, object],
    model_point_rows: list[dict[str, str]],
    label: str,
) -> None:
    """Recompute key aggregation identities from the current CSV contents."""
    if not model_point_rows:
        raise ValueError(f"Empty model-point results for {label}.")
    bases = [("normalised_average_", "normalised_contribution_")]
    if _as_bool(summary.get("absolute_portfolio_values_available")):
        bases.append(("portfolio_total_", "portfolio_contribution_"))
    for summary_prefix, contribution_prefix in bases:
        for metric in MONETARY_METRICS:
            summary_field = f"{summary_prefix}{metric}"
            contribution_field = f"{contribution_prefix}{metric}"
            expected = _as_float(summary.get(summary_field), summary_field)
            actual = sum(
                _as_float(row.get(contribution_field), contribution_field)
                for row in model_point_rows
            )
            if not _close(expected, actual):
                raise ValueError(
                    f"Live aggregation failed for {label} {summary_field}: "
                    f"summary={expected}, model-point sum={actual}"
                )


def _valuation_prefix(summary: Mapping[str, object]) -> tuple[str, str]:
    if _as_bool(summary.get("absolute_portfolio_values_available")):
        return "portfolio_total_", "absolute_portfolio"
    return "normalised_average_", "normalised_average_contract"


def _monetary(summary: Mapping[str, object], metric: str) -> float:
    prefix, _ = _valuation_prefix(summary)
    field = f"{prefix}{metric}"
    return _as_float(summary.get(field), field)


def _portfolio_metrics(
    summary: Mapping[str, object],
    *,
    label: str = "portfolio summary",
) -> dict[str, object]:
    metrics: dict[str, object] = {
        metric: _monetary(summary, metric) for metric in MONETARY_METRICS
    }
    metrics.update(_extract_behaviour_metrics(summary, label=label))
    premium = float(metrics["premium_aud"])
    claims = float(metrics["pv_guarantee_claims_aud"])
    future_fees = float(metrics["pv_future_fees_aud"])
    expenses = float(metrics["pv_expenses_aud"])
    hedge_costs = float(metrics["pv_hedge_costs_aud"])
    claim_and_cost_outgo = claims + expenses + hedge_costs
    metrics.update({
        "new_business_margin_before_risk_margin": _as_float(
            summary.get("new_business_margin_before_risk_margin"),
            "new_business_margin_before_risk_margin",
        ),
        "profitability_materiality_bp": _as_float(
            summary.get("profitability_materiality_bp"),
            "profitability_materiality_bp",
        ),
        "guarantee_claims_to_premium": _safe_ratio(claims, premium),
        "guarantee_value_to_premium": _safe_ratio(
            float(metrics["guarantee_value_aud"]), premium),
        "bel_nonunit_to_premium": _safe_ratio(
            float(metrics["bel_nonunit_aud"]), premium),
        "bel_total_to_premium": _safe_ratio(
            float(metrics["bel_total_aud"]), premium),
        "future_fees_to_premium": _safe_ratio(future_fees, premium),
        "crediting_margin_to_premium": _safe_ratio(
            float(metrics["pv_crediting_margin_aud"]), premium),
        "expenses_to_premium": _safe_ratio(expenses, premium),
        "hedge_costs_to_premium": _safe_ratio(hedge_costs, premium),
        "claims_to_future_fees": _safe_ratio(claims, future_fees),
        "fee_coverage_ratio": _safe_ratio(future_fees, claim_and_cost_outgo),
        "profitability_classification": summary.get(
            "profitability_classification"),
    })
    _require_close(
        float(metrics["pv_policyholder_benefits_aud"]),
        float(metrics["pv_policyholder_benefits_pre_election_aud"])
        + float(metrics["pv_policyholder_benefits_post_election_aud"]),
        f"{label} pre/post-Election Policyholder-benefit PV",
    )
    _require_close(
        float(metrics["pv_guarantee_claims_aud"]),
        float(metrics["pv_post_election_guarantee_claims_aud"]),
        f"{label} post-Election Guarantee-Claim PV",
    )
    return metrics


def _weighted_quantile(
    values: Sequence[float],
    weights: Sequence[float],
    probability: float,
) -> float:
    if not values or len(values) != len(weights):
        raise ValueError("Weighted quantile requires aligned non-empty inputs.")
    ordered = sorted(zip(values, weights), key=lambda item: item[0])
    total = sum(weight for _, weight in ordered)
    if total <= 0.0:
        raise ValueError("Weighted quantile requires positive total weight.")
    threshold = min(max(probability, 0.0), 1.0) * total
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= threshold:
            return float(value)
    return float(ordered[-1][0])


def _weighted_lower_tail_mean(
    values: Sequence[float],
    weights: Sequence[float],
    tail_probability: float,
) -> float:
    if not 0.0 < tail_probability <= 1.0:
        raise ValueError("tail_probability must be in (0, 1].")
    ordered = sorted(zip(values, weights), key=lambda item: item[0])
    total = sum(weight for _, weight in ordered)
    target = tail_probability * total
    if target <= 0.0:
        raise ValueError("Weighted tail mean requires positive total weight.")
    remaining = target
    weighted_sum = 0.0
    for value, weight in ordered:
        used = min(max(weight, 0.0), remaining)
        weighted_sum += value * used
        remaining -= used
        if remaining <= 1.0e-15:
            break
    return weighted_sum / target


def _model_point_risk_metrics(
    rows: list[dict[str, str]],
) -> dict[str, object]:
    if not rows:
        raise ValueError("Model-point risk analysis requires non-empty rows.")
    weights = [
        _as_float(row.get("normalised_contract_share"),
                  "normalised_contract_share")
        for row in rows
    ]
    weight_total = sum(weights)
    if not _close(weight_total, 1.0):
        raise ValueError(
            f"Model-point normalised contract shares sum to {weight_total}, not one."
        )
    weights = [weight / weight_total for weight in weights]
    claims = [
        _as_float(
            row.get("per_contract_pv_guarantee_claims_aud"),
            "per_contract_pv_guarantee_claims_aud",
        )
        for row in rows
    ]
    margins = [
        _as_float(
            row.get("per_contract_new_business_margin_before_risk_margin"),
            "per_contract_new_business_margin_before_risk_margin",
        )
        for row in rows
    ]
    npvs = [
        _as_float(
            row.get(
                "per_contract_insurer_net_present_value_before_risk_margin_aud"),
            "per_contract_insurer_net_present_value_before_risk_margin_aud",
        )
        for row in rows
    ]
    claim_contributions = [
        max(claim, 0.0) * weight for claim, weight in zip(claims, weights)
    ]
    total_claim_contribution = sum(claim_contributions)
    if total_claim_contribution > 0.0:
        claim_shares = [
            contribution / total_claim_contribution
            for contribution in claim_contributions
        ]
        hhi = sum(share * share for share in claim_shares)
        top_five = sum(sorted(claim_shares, reverse=True)[:5])
        joint_share = sum(
            share
            for share, row in zip(claim_shares, rows)
            if _as_bool(row.get("spouse"))
        )
        claim_weighted_age = sum(
            share * _as_float(row.get("primary_age"), "primary_age")
            for share, row in zip(claim_shares, rows)
        )
    else:
        hhi = 0.0
        top_five = 0.0
        joint_share = 0.0
        claim_weighted_age = None

    classifications = [
        str(row.get("per_contract_profitability_classification")
            or row.get("profitability_classification") or "")
        for row in rows
    ]
    negative_value_share = sum(
        weight
        for weight, classification in zip(weights, classifications)
        if classification == "negative_value"
    )
    strict_negative_share = sum(
        weight for weight, npv in zip(weights, npvs) if npv < 0.0
    )
    weighted_margin_mean = sum(
        weight * margin for weight, margin in zip(weights, margins)
    )
    weighted_margin_variance = sum(
        weight * (margin - weighted_margin_mean) ** 2
        for weight, margin in zip(weights, margins)
    )
    return {
        "model_point_count": len(rows),
        "negative_value_contract_share": negative_value_share,
        "strict_negative_npv_contract_share": strict_negative_share,
        "model_point_nbm_contract_weighted_mean": weighted_margin_mean,
        "model_point_nbm_weighted_p10": _weighted_quantile(
            margins, weights, 0.10),
        "model_point_nbm_weighted_lower_tail_mean_10pct": (
            _weighted_lower_tail_mean(margins, weights, 0.10)
        ),
        "model_point_nbm_weighted_standard_deviation": math.sqrt(
            max(weighted_margin_variance, 0.0)),
        "guarantee_claims_hhi": hhi,
        "top_5_guarantee_claim_share": top_five,
        "joint_life_guarantee_claim_share": joint_share,
        "guarantee_claim_weighted_primary_age": claim_weighted_age,
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("Quantile requires at least one value.")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = min(max(probability, 0.0), 1.0) * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _lsmc_diagnostic_metrics(
    action_rows: list[dict[str, str]],
    diagnostic_rows: list[dict[str, str]],
    manifest: Mapping[str, object],
) -> dict[str, object]:
    if not action_rows or not diagnostic_rows:
        raise ValueError("LSMC action and regression diagnostics must be non-empty.")
    if any(not str(row.get("action_type", "")).strip() for row in action_rows):
        raise ValueError(
            "LSMC action summary must distinguish income_election and "
            "full_withdrawal action types."
        )
    if any(
        not str(row.get("action_type", "")).strip()
        for row in diagnostic_rows
    ):
        raise ValueError(
            "LSMC regression diagnostics must identify their action type."
        )

    def action_totals(action_type: str) -> tuple[int, int, int]:
        selected = 0
        eligible = 0
        forced = 0
        for row in action_rows:
            if str(row.get("action_type")).strip().lower() != action_type:
                continue
            selected += int(_first_float(
                row,
                (
                    "selected_action_path_count",
                    "exercise_path_count",
                    "start_income_path_count"
                    if action_type == "income_election"
                    else "full_withdrawal_path_count",
                ),
                label=f"{action_type} selected path count",
            ))
            eligible += int(_as_float(
                row.get("eligible_path_count"),
                f"{action_type} eligible_path_count",
            ))
            if row.get("forced_action_path_count") not in (None, ""):
                forced += int(_as_float(
                    row.get("forced_action_path_count"),
                    f"{action_type} forced_action_path_count",
                ))
        return selected, eligible, forced

    election_count, election_eligible, forced_election_count = action_totals(
        "income_election"
    )
    surrender_count, surrender_eligible, _ = action_totals("full_withdrawal")
    if election_eligible <= 0:
        raise ValueError("LSMC action summary has no eligible Election decisions.")
    r_squared = [
        _as_float(row.get("oof_r_squared"), "oof_r_squared")
        for row in diagnostic_rows
    ]
    rmse = [
        _as_float(row.get("oof_rmse_aud"), "oof_rmse_aud")
        for row in diagnostic_rows
    ]
    condition_numbers = [
        _as_float(row.get("condition_number"), "condition_number")
        for row in diagnostic_rows
    ]
    accepted = sum(
        _as_bool(row.get("regression_accepted_for_exercise"))
        for row in diagnostic_rows
    )
    diagnostic_groups = {
        action_type: [
            row for row in diagnostic_rows
            if str(row.get("action_type")).strip().lower() == action_type
        ]
        for action_type in ("income_election", "full_withdrawal")
    }
    if any(not rows for rows in diagnostic_groups.values()):
        raise ValueError(
            "LSMC diagnostics must cover both Election and Full Withdrawal."
        )
    settings = manifest.get("lsmc_settings")
    if not isinstance(settings, Mapping):
        raise ValueError("LSMC manifest has no lsmc_settings object.")
    unique_fits = int(_as_float(
        settings.get("unique_policy_fits"), "unique_policy_fits"))
    fallback_fits = int(_first_float(
        settings,
        (
            "training_fallback_policy_count",
            "training_fallback_fit_count",
        ),
        label="training fallback policy count",
    ))
    output: dict[str, object] = {
        # These remain unweighted fit diagnostics.  Portfolio-weighted realised
        # rates come from the valuation summary fields above.
        "unweighted_income_election_action_rate": (
            election_count / election_eligible
        ),
        "unweighted_full_withdrawal_action_rate": (
            surrender_count / surrender_eligible
            if surrender_eligible else 0.0
        ),
        "income_election_action_path_count": election_count,
        "income_election_eligible_path_count": election_eligible,
        "forced_income_election_action_path_count": forced_election_count,
        "full_withdrawal_action_path_count": surrender_count,
        "full_withdrawal_eligible_path_count": surrender_eligible,
        "unique_policy_fit_count": unique_fits,
        "training_fallback_policy_count": fallback_fits,
        "training_fallback_policy_share": (
            fallback_fits / unique_fits if unique_fits else 0.0
        ),
        "regression_count": len(diagnostic_rows),
        "regression_accepted_count": accepted,
        "regression_accepted_share": accepted / len(diagnostic_rows),
        "oof_r_squared_q25": _quantile(r_squared, 0.25),
        "oof_r_squared_median": statistics.median(r_squared),
        "oof_rmse_aud_median": statistics.median(rmse),
        "condition_number_median": statistics.median(condition_numbers),
        "condition_number_max": max(condition_numbers),
        "out_of_sample_policyholder_value_dominates_continue": _as_bool(
            settings.get("out_of_sample_policyholder_value_dominates_continue")
        ),
    }
    for action_type, rows in diagnostic_groups.items():
        prefix = (
            "election" if action_type == "income_election" else "surrender"
        )
        group_r_squared = [
            _as_float(row.get("oof_r_squared"), "oof_r_squared")
            for row in rows
        ]
        group_rmse = [
            _as_float(row.get("oof_rmse_aud"), "oof_rmse_aud")
            for row in rows
        ]
        group_accepted = sum(
            _as_bool(row.get("regression_accepted_for_exercise"))
            for row in rows
        )
        output.update({
            f"{prefix}_regression_count": len(rows),
            f"{prefix}_regression_accepted_count": group_accepted,
            f"{prefix}_regression_accepted_share": (
                group_accepted / len(rows)
            ),
            f"{prefix}_oof_r_squared_median": statistics.median(
                group_r_squared
            ),
            f"{prefix}_oof_rmse_aud_median": statistics.median(group_rmse),
        })
    return output


def _validate_summary_settings(
    summary: Mapping[str, object],
    *,
    args: argparse.Namespace,
    rate: float,
    expect_lsmc: bool,
    label: str,
) -> None:
    _require_close(
        _as_float(summary.get("crediting_cap_rate"), "crediting_cap_rate"),
        rate,
        f"{label} crediting cap",
    )
    _require_close(
        _as_float(summary.get("n_paths"), "n_paths"),
        float(args.n_paths),
        f"{label} n_paths",
    )
    _require_close(
        _as_float(summary.get("seed"), "seed"),
        float(args.seed),
        f"{label} seed",
    )
    _require_close(
        _as_float(summary.get("heston_substeps"), "heston_substeps"),
        float(args.heston_substeps),
        f"{label} heston_substeps",
    )
    _require_close(
        _as_float(
            summary.get("profitability_materiality_bp"),
            "profitability_materiality_bp",
        ),
        float(args.profitability_materiality_bp),
        f"{label} profitability materiality",
    )
    if args.portfolio_contract_count is not None:
        _require_close(
            _as_float(
                summary.get("portfolio_contract_count"),
                "portfolio_contract_count",
            ),
            float(args.portfolio_contract_count),
            f"{label} portfolio contract count",
        )
    elif (
        not _as_bool(summary.get("source_exposure_counts_available"))
        and summary.get("portfolio_contract_count") not in (None, "")
    ):
        raise ValueError(
            f"{label} reused an explicit portfolio contract count although the "
            "current analysis did not request one."
        )
    if _as_bool(summary.get("lsmc_used")) != expect_lsmc:
        raise ValueError(f"Unexpected lsmc_used flag for {label}.")
    if str(summary.get("valuation_measure")) != "risk_neutral":
        raise ValueError(f"{label} is not a risk-neutral valuation.")
    if str(summary.get("valuation_model")) != "heston_hull_white":
        raise ValueError(f"{label} does not use Heston-Hull-White.")


def _validate_model_point_alignment(
    dynamic_rows: list[dict[str, str]],
    lsmc_rows: list[dict[str, str]],
) -> None:
    dynamic = {str(row.get("model_point_id")): row for row in dynamic_rows}
    lsmc = {str(row.get("model_point_id")): row for row in lsmc_rows}
    if not dynamic or len(dynamic) != len(dynamic_rows):
        raise ValueError("Dynamic model-point IDs are empty or not unique.")
    if not lsmc or len(lsmc) != len(lsmc_rows):
        raise ValueError("LSMC model-point IDs are empty or not unique.")
    if set(dynamic) != set(lsmc):
        missing_lsmc = sorted(set(dynamic) - set(lsmc))
        missing_dynamic = sorted(set(lsmc) - set(dynamic))
        raise ValueError(
            "Dynamic/LSMC model-point IDs differ; "
            f"missing in LSMC={missing_lsmc}, missing in Dynamic={missing_dynamic}"
        )
    for model_point_id, left in dynamic.items():
        right = lsmc[model_point_id]
        for field in (
            "normalised_contract_share",
            "per_contract_premium_aud",
            "primary_age",
        ):
            _require_close(
                _as_float(left.get(field), f"Dynamic {field}"),
                _as_float(right.get(field), f"LSMC {field}"),
                f"model point {model_point_id} {field}",
            )
        # ``income_start_year`` is now only the deterministic benchmark input,
        # not a realised Dynamic/LSMC start.  It remains an immutable source
        # attribute and is compared under that explicit name.
        _require_close(
            _as_float(left.get("income_start_year"), "Dynamic benchmark input"),
            _as_float(right.get("income_start_year"), "Comparator benchmark input"),
            f"model point {model_point_id} deterministic benchmark start input",
        )
        for field in ("primary_sex", "spouse", "income_type"):
            if str(left.get(field)) != str(right.get(field)):
                raise ValueError(
                    f"model point {model_point_id} {field} mismatch: "
                    f"{left.get(field)!r} != {right.get(field)!r}"
                )


def _paired_model_point_rows(
    rate: float,
    dynamic_rows: list[dict[str, str]],
    lsmc_rows: list[dict[str, str]],
    continue_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    dynamic = {str(row["model_point_id"]): row for row in dynamic_rows}
    continuing = {str(row["model_point_id"]): row for row in continue_rows}
    output: list[dict[str, object]] = []
    for right in lsmc_rows:
        model_point_id = str(right["model_point_id"])
        left = dynamic[model_point_id]
        continue_row = continuing[model_point_id]
        row: dict[str, object] = {
            "crediting_cap_rate": rate,
            "crediting_cap_rate_percent": 100.0 * rate,
            "model_point_id": model_point_id,
            "normalised_contract_share": _as_float(
                left.get("normalised_contract_share"),
                "normalised_contract_share",
            ),
            "primary_age": _as_float(left.get("primary_age"), "primary_age"),
            "primary_sex": left.get("primary_sex"),
            "spouse": _as_bool(left.get("spouse")),
            "model_point_income_start_year_deterministic_benchmark": _as_float(
                left.get("income_start_year"), "income_start_year"),
            "income_type": left.get("income_type"),
            "dynamic_behaviour_treatment": left.get("behaviour_treatment"),
            "lsmc_behaviour_treatment": right.get("behaviour_treatment"),
            "dynamic_profitability_classification": left.get(
                "per_contract_profitability_classification"),
            "lsmc_profitability_classification": right.get(
                "per_contract_profitability_classification"),
        }
        for canonical, aliases in BEHAVIOUR_SCALAR_METRICS.items():
            dynamic_candidates = tuple(
                f"per_contract_{alias}" for alias in aliases
            )
            lsmc_candidates = tuple(
                f"per_contract_{alias}" for alias in aliases
            )
            dynamic_value = _first_float(
                left,
                dynamic_candidates,
                label=f"Dynamic model point {model_point_id} {canonical}",
            )
            lsmc_value = _first_float(
                right,
                lsmc_candidates,
                label=f"LSMC model point {model_point_id} {canonical}",
            )
            row[f"dynamic_{canonical}"] = dynamic_value
            row[f"lsmc_{canonical}"] = lsmc_value
            row[f"lsmc_minus_dynamic_{canonical}"] = (
                lsmc_value - dynamic_value
            )
        for metric in MODEL_POINT_COMPARISON_METRICS:
            field = f"per_contract_{metric}"
            left_value = _as_float(left.get(field), f"Dynamic {field}")
            right_value = _as_float(right.get(field), f"LSMC {field}")
            continue_value = _as_float(
                continue_row.get(field), f"Continue {field}")
            row[f"dynamic_per_contract_{metric}"] = left_value
            row[f"lsmc_per_contract_{metric}"] = right_value
            row[f"continue_per_contract_{metric}"] = continue_value
            row[f"lsmc_minus_dynamic_per_contract_{metric}"] = (
                right_value - left_value)
            row[f"lsmc_minus_continue_per_contract_{metric}"] = (
                right_value - continue_value)
            for contribution_prefix in (
                "normalised_contribution_",
                "portfolio_contribution_",
            ):
                contribution_field = f"{contribution_prefix}{metric}"
                if contribution_field in left and contribution_field in right:
                    left_contribution = _as_float(
                        left.get(contribution_field),
                        f"Dynamic {contribution_field}",
                    )
                    right_contribution = _as_float(
                        right.get(contribution_field),
                        f"LSMC {contribution_field}",
                    )
                    row[f"dynamic_{contribution_field}"] = left_contribution
                    row[f"lsmc_{contribution_field}"] = right_contribution
                    row[f"lsmc_minus_dynamic_{contribution_field}"] = (
                        right_contribution - left_contribution)
        dynamic_npv = float(row[
            "dynamic_per_contract_insurer_net_present_value_before_risk_margin_aud"
        ])
        lsmc_npv = float(row[
            "lsmc_per_contract_insurer_net_present_value_before_risk_margin_aud"
        ])
        row["behaviour_model_gap_to_insurer_per_contract_aud"] = (
            dynamic_npv - lsmc_npv)
        output.append(row)
    return output


def _manifest_stress_id(manifest: Mapping[str, object]) -> str:
    stress = manifest.get("stress_scenario")
    if stress is None:
        # Backward-compatible base outputs created before the common stress
        # hook are still reusable after all other provenance checks pass.
        return "base"
    if not isinstance(stress, Mapping):
        raise ValueError("Runner manifest stress_scenario must be an object.")
    stress_id = str(stress.get("stress_id", "")).strip()
    if not stress_id:
        raise ValueError("Runner manifest stress_scenario has no stress_id.")
    return stress_id


def _normalised_action_tokens(value: object) -> set[str]:
    if isinstance(value, Mapping):
        tokens: set[str] = set()
        for phase, actions in value.items():
            tokens.add(str(phase).strip().lower())
            tokens.update(_normalised_action_tokens(actions))
        return tokens
    if isinstance(value, (list, tuple, set)):
        tokens = set()
        for item in value:
            tokens.update(_normalised_action_tokens(item))
        return tokens
    return {
        token
        for token in re.split(r"[^a-z0-9_]+", str(value).strip().lower())
        if token
    }


def _manifest_fit_basis_fingerprint(
    manifest: Mapping[str, object],
) -> str:
    settings = manifest.get("lsmc_settings")
    if not isinstance(settings, Mapping):
        raise ValueError("LSMC manifest has no lsmc_settings object.")
    value = settings.get("fit_basis_fingerprint")
    if value in (None, ""):
        value = settings.get("policy_fit_basis_fingerprint")
    if value in (None, ""):
        value = settings.get("fit_basis_fingerprints")
    if value in (None, "", {}, []):
        raise ValueError(
            "LSMC manifest has no cap/stress-specific fit-basis fingerprint."
        )
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _validate_behaviour_manifest(
    manifest: Mapping[str, object],
    *,
    label: str,
    expected_election_mode: str,
    expected_post_income_mode: str,
) -> Optional[str]:
    """Reject cached Fixed-Election/surrender-only results for new main runs."""
    method = manifest.get("method")
    if not isinstance(method, Mapping):
        raise ValueError(f"{label} manifest has no method object.")
    election_value = (
        method.get("income_election_mode")
        or method.get("income_election")
        or method.get("income_take_up")
    )
    election_text = str(election_value).strip().lower()
    if expected_election_mode == "dynamic":
        valid_election = "dynamic" in election_text
    elif expected_election_mode == "deterministic":
        valid_election = "deterministic" in election_text
    else:
        valid_election = (
            "optimal" in election_text or "lsmc" in election_text
        ) and "deterministic" not in election_text
    if not valid_election:
        raise ValueError(
            f"{label} Income-Election mode {election_value!r} does not match "
            f"{expected_election_mode!r}."
        )

    decision_grid = str(
        method.get("income_election_decision_grid")
        or method.get("decision_frequency")
        or ""
    ).lower()
    if "annivers" not in decision_grid:
        raise ValueError(f"{label} does not document Anniversary-only Election.")
    forced_rule = str(method.get("forced_income_start") or "").lower()
    if "100" not in forced_rule or "annivers" not in forced_rule:
        raise ValueError(
            f"{label} does not document the forced start after age 100."
        )

    action_value = (
        method.get("action_set_by_phase")
        or {
            "growth": method.get("income_election_action_set"),
            "income": method.get("post_income_action_set")
            or method.get("lsmc_action_set"),
        }
    )
    actions = _normalised_action_tokens(action_value)
    if expected_election_mode in {"dynamic", "optimal"} and not {
        "wait",
        "start_income_now",
    }.issubset(actions):
        raise ValueError(
            f"{label} does not expose WAIT | START_INCOME_NOW in Growth."
        )
    if expected_post_income_mode == "continue":
        if "continue" not in actions:
            raise ValueError(f"{label} Continue benchmark has no CONTINUE action.")
    elif expected_post_income_mode == "dynamic":
        if not any("withdraw" in action or "lapse" in action for action in actions):
            raise ValueError(
                f"{label} does not document dynamic post-Election exit."
            )
    else:
        if not {"continue", "full_withdrawal"}.issubset(actions):
            raise ValueError(
                f"{label} does not expose CONTINUE | FULL_WITHDRAWAL in Income."
            )

    joint = str(method.get("joint_life_behaviour") or "").lower()
    if expected_election_mode in {"dynamic", "optimal"} and not any(
        marker in joint for marker in ("pathwise", "separate", "cohort")
    ):
        raise ValueError(
            f"{label} does not document separate pathwise Joint-Life status."
        )
    if expected_election_mode == "optimal":
        return _manifest_fit_basis_fingerprint(manifest)
    return None


def _scenario_outputs_complete(
    dynamic_output: Path,
    lsmc_output: Path,
    *,
    require_plots: bool,
    expected_stress: str = "base",
) -> bool:
    dynamic_benchmark_directories = _dynamic_benchmark_directories(
        dynamic_output
    )
    required = (
        dynamic_output / "portfolio_summary.csv",
        dynamic_output / "model_point_results.csv",
        dynamic_output / "portfolio_aggregation_reconciliation.csv",
        dynamic_output / "run_manifest.json",
        lsmc_output / "portfolio_summary.csv",
        lsmc_output / "model_point_results.csv",
        lsmc_output / "portfolio_aggregation_reconciliation.csv",
        lsmc_output / "run_manifest.json",
        lsmc_output / "lsmc_action_summary.csv",
        lsmc_output / "lsmc_regression_diagnostics.csv",
        lsmc_output / "continue_benchmark" / "portfolio_summary.csv",
        lsmc_output / "continue_benchmark" / "model_point_results.csv",
        lsmc_output / "continue_benchmark"
        / "portfolio_aggregation_reconciliation.csv",
        *(
            path / file_name
            for path in dynamic_benchmark_directories.values()
            for file_name in (
                "portfolio_summary.csv",
                "model_point_results.csv",
                "portfolio_aggregation_reconciliation.csv",
                "run_manifest.json",
            )
        ),
    )
    if not all(path.is_file() for path in required):
        return False
    manifests: dict[Path, Mapping[str, object]] = {}
    try:
        for scenario_output in (
            dynamic_output,
            *dynamic_benchmark_directories.values(),
            lsmc_output,
        ):
            manifest = _read_json(scenario_output / "run_manifest.json")
            if _manifest_stress_id(manifest) != expected_stress:
                return False
            manifests[scenario_output] = manifest
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    if require_plots:
        for scenario_output in (dynamic_output, lsmc_output):
            manifest = manifests[scenario_output]
            if scenario_output == dynamic_output:
                reporting = manifest.get("reporting")
                if (
                    not isinstance(reporting, Mapping)
                    or reporting.get("plots_requested") is not True
                ):
                    return False
            outputs = manifest.get("outputs")
            figures = outputs.get("figures") if isinstance(outputs, Mapping) else None
            if not isinstance(figures, Mapping) or not figures:
                return False
            if any(
                not Path(str(figure_path)).is_file()
                for figure_path in figures.values()
            ):
                return False
    return True


def _load_scenario_result(
    args: argparse.Namespace,
    rate: float,
    dynamic_output: Path,
    lsmc_output: Path,
    *,
    expected_stress: str = "base",
) -> tuple[dict[str, object], list[dict[str, object]]]:
    dynamic_summary = _read_single_csv_row(
        dynamic_output / "portfolio_summary.csv")
    dynamic_rows = _read_csv(dynamic_output / "model_point_results.csv")
    dynamic_manifest = _read_json(dynamic_output / "run_manifest.json")
    dynamic_benchmark_directories = _dynamic_benchmark_directories(
        dynamic_output
    )
    dynamic_benchmark_summaries = {
        benchmark_id: _read_single_csv_row(
            directory / "portfolio_summary.csv"
        )
        for benchmark_id, directory in dynamic_benchmark_directories.items()
    }
    dynamic_benchmark_rows = {
        benchmark_id: _read_csv(directory / "model_point_results.csv")
        for benchmark_id, directory in dynamic_benchmark_directories.items()
    }
    dynamic_benchmark_manifests = {
        benchmark_id: _read_json(directory / "run_manifest.json")
        for benchmark_id, directory in dynamic_benchmark_directories.items()
    }
    lsmc_summary = _read_single_csv_row(lsmc_output / "portfolio_summary.csv")
    lsmc_rows = _read_csv(lsmc_output / "model_point_results.csv")
    lsmc_manifest = _read_json(lsmc_output / "run_manifest.json")
    continue_summary = _read_single_csv_row(
        lsmc_output / "continue_benchmark" / "portfolio_summary.csv")
    continue_rows = _read_csv(
        lsmc_output / "continue_benchmark" / "model_point_results.csv")
    lsmc_benchmark_directories = _lsmc_benchmark_directories(lsmc_output)
    lsmc_benchmark_summaries: dict[str, dict[str, str]] = {
        "variable_election_continue": continue_summary,
    }
    lsmc_benchmark_rows: dict[str, list[dict[str, str]]] = {
        "variable_election_continue": continue_rows,
    }
    for benchmark_id in (
        "deterministic_election_continue",
        "deterministic_election_post_behaviour",
    ):
        directory = lsmc_benchmark_directories[benchmark_id]
        summary_path = directory / "portfolio_summary.csv"
        rows_path = directory / "model_point_results.csv"
        reconciliation_path = (
            directory / "portfolio_aggregation_reconciliation.csv"
        )
        if all(path.is_file() for path in (
            summary_path,
            rows_path,
            reconciliation_path,
        )):
            lsmc_benchmark_summaries[benchmark_id] = _read_single_csv_row(
                summary_path
            )
            lsmc_benchmark_rows[benchmark_id] = _read_csv(rows_path)

    _validate_behaviour_manifest(
        dynamic_manifest,
        label="Dynamic full policy",
        expected_election_mode="dynamic",
        expected_post_income_mode="dynamic",
    )
    dynamic_benchmark_modes = {
        "deterministic_election_continue": ("deterministic", "continue"),
        "deterministic_election_post_behaviour": (
            "deterministic",
            "dynamic",
        ),
        "variable_election_continue": ("dynamic", "continue"),
    }
    for benchmark_id, manifest in dynamic_benchmark_manifests.items():
        election_mode, post_mode = dynamic_benchmark_modes[benchmark_id]
        _validate_behaviour_manifest(
            manifest,
            label=f"Dynamic benchmark {benchmark_id}",
            expected_election_mode=election_mode,
            expected_post_income_mode=post_mode,
        )
    for label, manifest in (
        ("Dynamic full policy", dynamic_manifest),
        *(
            (f"Dynamic benchmark {benchmark_id}", manifest)
            for benchmark_id, manifest in dynamic_benchmark_manifests.items()
        ),
    ):
        valuation_settings = manifest.get("valuation_settings")
        if not isinstance(valuation_settings, Mapping):
            raise ValueError(f"{label} has no valuation_settings metadata.")
        _require_close(
            _as_float(valuation_settings.get("take_up_seed"), "take_up_seed"),
            float(args.take_up_seed),
            f"{label} take-up seed",
        )
        _require_close(
            _as_float(
                valuation_settings.get("mortality_seed"),
                "mortality_seed",
            ),
            float(args.mortality_seed),
            f"{label} mortality seed",
        )
    lsmc_fit_basis_fingerprint = _validate_behaviour_manifest(
        lsmc_manifest,
        label="LSMC full policy",
        expected_election_mode="optimal",
        expected_post_income_mode="optimal",
    )
    lsmc_method = lsmc_manifest.get("method")
    if not isinstance(lsmc_method, Mapping):
        raise ValueError("LSMC manifest has no method object.")
    benchmark_metadata = lsmc_method.get("behaviour_benchmarks")
    if not isinstance(benchmark_metadata, Mapping):
        benchmark_metadata = lsmc_manifest.get("behaviour_benchmarks")
    if not isinstance(benchmark_metadata, Mapping) or not all(
        benchmark_id in benchmark_metadata
        for benchmark_id in lsmc_benchmark_summaries
    ):
        raise ValueError(
            "LSMC manifest does not identify the semantics of every retained "
            "Behaviour benchmark."
        )

    dynamic_stress_id = _manifest_stress_id(dynamic_manifest)
    lsmc_stress_id = _manifest_stress_id(lsmc_manifest)
    if dynamic_stress_id != expected_stress or lsmc_stress_id != expected_stress:
        raise ValueError(
            "Runner stress scenario does not match the requested analysis "
            f"scenario {expected_stress!r}."
        )
    if any(
        _manifest_stress_id(manifest) != expected_stress
        for manifest in dynamic_benchmark_manifests.values()
    ):
        raise ValueError(
            "A Dynamic factorial benchmark uses a different stress scenario."
        )
    for label, summary in (
        ("Dynamic", dynamic_summary),
        ("LSMC", lsmc_summary),
        ("Continue", continue_summary),
        *(
            (f"Dynamic benchmark {benchmark_id}", summary)
            for benchmark_id, summary in dynamic_benchmark_summaries.items()
        ),
    ):
        summary_stress = summary.get("stress_scenario_id")
        if summary_stress is not None and str(summary_stress) != expected_stress:
            raise ValueError(
                f"{label} summary stress scenario differs from its manifest."
            )
    if expected_stress != "base":
        for label, manifest, training_expected in (
            ("Dynamic", dynamic_manifest, False),
            ("LSMC", lsmc_manifest, True),
        ):
            stress_metadata = manifest.get("stress_scenario")
            if not isinstance(stress_metadata, Mapping):
                raise ValueError(f"{label} manifest has no stress metadata.")
            if stress_metadata.get("applied_to_evaluation") is not True:
                raise ValueError(f"{label} stress was not applied to evaluation.")
            if bool(stress_metadata.get("applied_to_training")) != training_expected:
                raise ValueError(
                    f"{label} stress training-application flag is inconsistent."
                )

    dynamic_sources = dynamic_manifest.get("sources")
    lsmc_sources = lsmc_manifest.get("sources")
    if not isinstance(dynamic_sources, Mapping) or not isinstance(
        lsmc_sources, Mapping
    ):
        raise ValueError("Runner manifests must contain source metadata.")
    for benchmark_id, benchmark_manifest in dynamic_benchmark_manifests.items():
        benchmark_sources = benchmark_manifest.get("sources")
        if not isinstance(benchmark_sources, Mapping):
            raise ValueError(
                f"Dynamic benchmark {benchmark_id} has no source metadata."
            )
        for source_name in ("model_points", "market", "costs"):
            if json.dumps(
                dynamic_sources.get(source_name),
                sort_keys=True,
                default=str,
            ) != json.dumps(
                benchmark_sources.get(source_name),
                sort_keys=True,
                default=str,
            ):
                raise ValueError(
                    f"Dynamic benchmark {benchmark_id} changed {source_name}."
                )
    for source_name in ("model_points", "market", "costs"):
        if json.dumps(
            dynamic_sources.get(source_name), sort_keys=True, default=str
        ) != json.dumps(
            lsmc_sources.get(source_name), sort_keys=True, default=str
        ):
            raise ValueError(
                f"Dynamic/LSMC {source_name} source metadata differ."
            )
    source_metadata_fingerprint = hashlib.sha256(
        json.dumps(
            dynamic_sources,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    dynamic_engine_version = str(dynamic_manifest.get("engine_version"))
    lsmc_engine_version = str(lsmc_manifest.get("engine_version"))
    if (
        dynamic_engine_version in {"", "None"}
        or dynamic_engine_version != lsmc_engine_version
    ):
        raise ValueError("Dynamic and LSMC runner engine versions differ.")

    def require_requested_path(actual: object, requested: Optional[Path],
                               label: str) -> None:
        if requested is None:
            return
        if actual in (None, ""):
            raise ValueError(f"Reused output has no {label} source path.")
        if Path(str(actual)).expanduser().resolve() != requested.expanduser().resolve():
            raise ValueError(f"Reused output has a different {label} source path.")

    model_point_source = dynamic_sources.get("model_points")
    cost_source = dynamic_sources.get("costs")
    market_source = dynamic_sources.get("market")
    if not isinstance(model_point_source, Mapping) or not isinstance(
        cost_source, Mapping
    ) or not isinstance(market_source, Mapping):
        raise ValueError("Incomplete source metadata in Dynamic manifest.")
    market_paths = market_source.get("source_paths")
    market_hashes = market_source.get("source_sha256")
    behaviour_source = dynamic_sources.get("dynamic_behaviour")
    if (
        not isinstance(market_paths, Mapping)
        or not isinstance(market_hashes, Mapping)
        or not isinstance(behaviour_source, Mapping)
        or not isinstance(behaviour_source.get("source_paths"), Mapping)
        or not isinstance(behaviour_source.get("source_sha256"), Mapping)
    ):
        raise ValueError("Dynamic manifest has incomplete source paths or hashes.")
    _validate_source_file_hash(
        model_point_source.get("source_path"),
        model_point_source.get("source_sha256"),
        "model-point",
    )
    _validate_source_file_hash(
        cost_source.get("source_path"),
        cost_source.get("source_sha256"),
        "cost-assumption",
    )
    for source_name in ("curve", "model_parameters"):
        _validate_source_file_hash(
            market_paths.get(source_name),
            market_hashes.get(source_name),
            f"market {source_name}",
        )
    behaviour_paths = behaviour_source["source_paths"]
    behaviour_hashes = behaviour_source["source_sha256"]
    for source_name in ("baselines", "coefficients"):
        _validate_source_file_hash(
            behaviour_paths.get(source_name),
            behaviour_hashes.get(source_name),
            f"dynamic behaviour {source_name}",
        )
    require_requested_path(
        model_point_source.get("source_path"),
        args.model_points or DEFAULT_MODEL_POINTS_PATH,
        "model-point",
    )
    require_requested_path(
        cost_source.get("source_path"),
        args.cost_assumptions or DEFAULT_COST_ASSUMPTIONS_PATH,
        "cost-assumption",
    )
    require_requested_path(
        market_paths.get("curve"),
        args.zero_curve or DEFAULT_ZERO_CURVE_PATH,
        "zero-curve",
    )
    require_requested_path(
        market_paths.get("model_parameters"),
        args.model_parameters or DEFAULT_MODEL_PARAMETERS_PATH,
        "model-parameter",
    )
    requested_directory = (
        args.dynamic_behaviour or DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY
    ).expanduser().resolve()
    for source_path in behaviour_paths.values():
        if Path(str(source_path)).expanduser().resolve().parent != requested_directory:
            raise ValueError(
                "Reused output has a different dynamic-behaviour directory."
            )

    _validate_reconciliation(
        dynamic_output / "portfolio_aggregation_reconciliation.csv", "Dynamic")
    _validate_reconciliation(
        lsmc_output / "portfolio_aggregation_reconciliation.csv", "LSMC")
    _validate_reconciliation(
        lsmc_output / "continue_benchmark"
        / "portfolio_aggregation_reconciliation.csv",
        "Continue",
    )
    for benchmark_id, directory in dynamic_benchmark_directories.items():
        _validate_reconciliation(
            directory / "portfolio_aggregation_reconciliation.csv",
            f"Dynamic benchmark {benchmark_id}",
        )
    for benchmark_id, directory in lsmc_benchmark_directories.items():
        if benchmark_id not in lsmc_benchmark_summaries:
            continue
        _validate_reconciliation(
            directory / "portfolio_aggregation_reconciliation.csv",
            f"LSMC benchmark {benchmark_id}",
        )
    _validate_live_aggregation(dynamic_summary, dynamic_rows, "Dynamic")
    _validate_live_aggregation(lsmc_summary, lsmc_rows, "LSMC")
    _validate_live_aggregation(continue_summary, continue_rows, "Continue")
    for benchmark_id in BENCHMARK_IDS:
        _validate_live_aggregation(
            dynamic_benchmark_summaries[benchmark_id],
            dynamic_benchmark_rows[benchmark_id],
            f"Dynamic benchmark {benchmark_id}",
        )
    for benchmark_id, summary in lsmc_benchmark_summaries.items():
        _validate_live_aggregation(
            summary,
            lsmc_benchmark_rows[benchmark_id],
            f"LSMC benchmark {benchmark_id}",
        )
    _validate_summary_settings(
        dynamic_summary, args=args, rate=rate, expect_lsmc=False,
        label="Dynamic")
    _validate_summary_settings(
        lsmc_summary, args=args, rate=rate, expect_lsmc=True, label="LSMC")
    _validate_summary_settings(
        continue_summary, args=args, rate=rate, expect_lsmc=False,
        label="Continue")
    for benchmark_id, summary in dynamic_benchmark_summaries.items():
        _validate_summary_settings(
            summary,
            args=args,
            rate=rate,
            expect_lsmc=False,
            label=f"Dynamic benchmark {benchmark_id}",
        )
    for benchmark_id, summary in lsmc_benchmark_summaries.items():
        # Restricted LSMC benchmarks can themselves contain a fitted policy;
        # the valuation basis/settings checks are independent of that flag.
        _validate_summary_settings(
            summary,
            args=args,
            rate=rate,
            expect_lsmc=_as_bool(summary.get("lsmc_used")),
            label=f"LSMC benchmark {benchmark_id}",
        )

    dynamic_prefix, dynamic_basis = _valuation_prefix(dynamic_summary)
    lsmc_prefix, lsmc_basis = _valuation_prefix(lsmc_summary)
    continue_prefix, continue_basis = _valuation_prefix(continue_summary)
    dynamic_benchmark_bases = {
        _valuation_prefix(summary)[1]
        for summary in dynamic_benchmark_summaries.values()
    }
    lsmc_benchmark_bases = {
        _valuation_prefix(summary)[1]
        for summary in lsmc_benchmark_summaries.values()
    }
    if len({
        dynamic_basis,
        lsmc_basis,
        continue_basis,
        *dynamic_benchmark_bases,
        *lsmc_benchmark_bases,
    }) != 1:
        raise ValueError(
            "Behaviour variants returned different valuation bases."
        )
    dynamic_benchmark_prefixes = {
        _valuation_prefix(summary)[0]
        for summary in dynamic_benchmark_summaries.values()
    }
    lsmc_benchmark_prefixes = {
        _valuation_prefix(summary)[0]
        for summary in lsmc_benchmark_summaries.values()
    }
    if len({
        dynamic_prefix,
        lsmc_prefix,
        continue_prefix,
        *dynamic_benchmark_prefixes,
        *lsmc_benchmark_prefixes,
    }) != 1:
        raise ValueError("Inconsistent monetary prefixes across behaviour methods.")

    _validate_model_point_alignment(dynamic_rows, lsmc_rows)
    _validate_model_point_alignment(dynamic_rows, continue_rows)
    for benchmark_rows in dynamic_benchmark_rows.values():
        _validate_model_point_alignment(dynamic_rows, benchmark_rows)
    for benchmark_rows in lsmc_benchmark_rows.values():
        _validate_model_point_alignment(dynamic_rows, benchmark_rows)
    for field in (
        "valuation_as_of_date",
        "valuation_currency",
        "market_parameter_set_id",
        "yield_curve_id",
        "cost_assumption_set_id",
    ):
        if str(dynamic_summary.get(field)) != str(lsmc_summary.get(field)):
            raise ValueError(
                f"Dynamic/LSMC source field {field} mismatch: "
                f"{dynamic_summary.get(field)!r} != {lsmc_summary.get(field)!r}"
            )
    _require_close(
        _as_float(dynamic_summary.get("scenario_horizon_years"),
                  "Dynamic scenario_horizon_years"),
        _as_float(lsmc_summary.get("scenario_horizon_years"),
                  "LSMC scenario_horizon_years"),
        "Dynamic/LSMC scenario horizon",
    )

    dynamic_portfolio = dynamic_manifest.get("portfolio")
    lsmc_method = lsmc_manifest.get("method")
    evaluation_settings = lsmc_manifest.get("evaluation_settings")
    lsmc_settings = lsmc_manifest.get("lsmc_settings")
    if not isinstance(dynamic_portfolio, Mapping):
        raise ValueError("Dynamic manifest has no portfolio object.")
    if not isinstance(lsmc_method, Mapping):
        raise ValueError("LSMC manifest has no method object.")
    if not isinstance(evaluation_settings, Mapping):
        raise ValueError("LSMC manifest has no evaluation_settings object.")
    if not isinstance(lsmc_settings, Mapping):
        raise ValueError("LSMC manifest has no lsmc_settings object.")
    if _as_bool(lsmc_method.get("dynamic_behaviour_used_for_benchmark")):
        raise ValueError(
            "LSMC scenario unexpectedly contains a duplicate Dynamic benchmark."
        )
    if not _as_bool(
        evaluation_settings.get("continue_benchmark_same_scenarios")
    ):
        raise ValueError("Continue and LSMC are not confirmed on the same scenarios.")
    evaluation_fingerprint = str(dynamic_portfolio.get("scenario_fingerprint"))
    lsmc_evaluation_fingerprint = str(
        evaluation_settings.get("scenario_fingerprint"))
    if evaluation_fingerprint != lsmc_evaluation_fingerprint:
        raise ValueError(
            "Dynamic and LSMC evaluations do not use the same scenario set."
        )
    for benchmark_id, benchmark_manifest in dynamic_benchmark_manifests.items():
        benchmark_portfolio = benchmark_manifest.get("portfolio")
        if not isinstance(benchmark_portfolio, Mapping):
            raise ValueError(
                f"Dynamic benchmark {benchmark_id} has no portfolio metadata."
            )
        if str(
            benchmark_portfolio.get("scenario_fingerprint")
        ) != evaluation_fingerprint:
            raise ValueError(
                f"Dynamic benchmark {benchmark_id} changed evaluation paths."
            )
    training_fingerprint = str(
        lsmc_settings.get("training_scenario_fingerprint"))
    if training_fingerprint == evaluation_fingerprint:
        raise ValueError("LSMC training and evaluation scenarios must differ.")
    _require_close(
        _as_float(lsmc_settings.get("n_train"), "n_train"),
        float(args.n_train),
        "LSMC n_train",
    )
    _require_close(
        _as_float(lsmc_settings.get("train_seed"), "train_seed"),
        float(args.train_seed),
        "LSMC train_seed",
    )
    _require_close(
        _as_float(
            lsmc_summary.get("lsmc_training_paths"),
            "lsmc_training_paths",
        ),
        float(args.n_train),
        "LSMC summary training paths",
    )
    _require_close(
        _as_float(
            lsmc_summary.get("lsmc_training_seed"),
            "lsmc_training_seed",
        ),
        float(args.train_seed),
        "LSMC summary training seed",
    )
    if str(
        lsmc_summary.get("lsmc_training_scenario_fingerprint")
    ) != training_fingerprint:
        raise ValueError("LSMC summary and manifest training fingerprints differ.")
    _require_close(
        _as_float(lsmc_settings.get("n_folds"), "n_folds"),
        float(args.lsmc_folds),
        "LSMC n_folds",
    )
    _require_close(
        _as_float(lsmc_settings.get("ridge"), "ridge"),
        float(args.lsmc_ridge),
        "LSMC ridge",
    )
    _require_close(
        _as_float(
            lsmc_settings.get("exercise_buffer_rmse_multiplier"),
            "exercise_buffer_rmse_multiplier",
        ),
        float(args.exercise_buffer_rmse_multiplier),
        "LSMC exercise buffer",
    )
    expected_cost_set = (
        str(args.cost_assumption_set)
        if args.cost_assumption_set is not None
        else _sole_assumption_set(
            [Path(str(cost_source["source_path"]))],
            "cost assumptions",
        )
    )
    if str(dynamic_summary.get("cost_assumption_set_id")) != expected_cost_set:
        raise ValueError("Reused output has a different cost assumption set.")
    expected_behaviour_set = (
        str(args.behaviour_assumption_set)
        if args.behaviour_assumption_set is not None
        else _sole_assumption_set(
            [Path(str(path)) for path in behaviour_paths.values()],
            "dynamic behaviour assumptions",
        )
    )
    if str(
        dynamic_summary.get("behaviour_assumption_set_id")
    ) != expected_behaviour_set:
        raise ValueError("Reused output has a different behaviour assumption set.")

    manifest_summary = lsmc_manifest.get("summary")
    if not isinstance(manifest_summary, Mapping):
        raise ValueError("LSMC manifest has no embedded summary object.")
    for metric in MONETARY_METRICS:
        _require_close(
            _monetary(lsmc_summary, metric),
            _monetary(manifest_summary, metric),
            f"LSMC CSV/manifest {metric}",
        )

    dynamic_metrics = _portfolio_metrics(dynamic_summary, label="Dynamic")
    lsmc_metrics = _portfolio_metrics(lsmc_summary, label="LSMC")
    continue_metrics = _portfolio_metrics(
        continue_summary,
        label="LSMC variable-Election Continue benchmark",
    )
    dynamic_benchmark_metrics = {
        benchmark_id: _portfolio_metrics(
            summary,
            label=f"Dynamic benchmark {benchmark_id}",
        )
        for benchmark_id, summary in dynamic_benchmark_summaries.items()
    }
    lsmc_benchmark_metrics = {
        benchmark_id: _portfolio_metrics(
            summary,
            label=f"LSMC benchmark {benchmark_id}",
        )
        for benchmark_id, summary in lsmc_benchmark_summaries.items()
    }
    for label, metrics in (
        ("LSMC", lsmc_metrics),
        ("Continue", continue_metrics),
        *(
            (f"Dynamic benchmark {benchmark_id}", metrics)
            for benchmark_id, metrics in dynamic_benchmark_metrics.items()
        ),
        *(
            (f"LSMC benchmark {benchmark_id}", metrics)
            for benchmark_id, metrics in lsmc_benchmark_metrics.items()
        ),
    ):
        _require_close(
            float(dynamic_metrics["premium_aud"]),
            float(metrics["premium_aud"]),
            f"Dynamic/{label} premium",
        )

    dynamic_mp_risk = _model_point_risk_metrics(dynamic_rows)
    lsmc_mp_risk = _model_point_risk_metrics(lsmc_rows)
    action_rows = _read_csv(lsmc_output / "lsmc_action_summary.csv")
    diagnostic_rows = _read_csv(
        lsmc_output / "lsmc_regression_diagnostics.csv")
    if any(
        str(diagnostic.get("training_scenario_fingerprint"))
        != training_fingerprint
        for diagnostic in diagnostic_rows
    ):
        raise ValueError(
            "LSMC regression diagnostics use a different training fingerprint."
        )
    lsmc_diagnostics = _lsmc_diagnostic_metrics(
        action_rows,
        diagnostic_rows,
        lsmc_manifest,
    )

    row: dict[str, object] = {
        "stress_scenario_id": expected_stress,
        "crediting_cap_rate": rate,
        "crediting_cap_rate_percent": 100.0 * rate,
        "below_contractual_minimum_crediting_cap": (
            rate < CONTRACTUAL_MINIMUM_CREDITING_CAP_RATE),
        "valuation_basis": dynamic_basis,
        "valuation_currency": dynamic_summary.get("valuation_currency"),
        "premium_aud": dynamic_metrics["premium_aud"],
        "evaluation_scenario_fingerprint": evaluation_fingerprint,
        "training_scenario_fingerprint": training_fingerprint,
        "lsmc_fit_basis_fingerprint": lsmc_fit_basis_fingerprint,
        "source_metadata_fingerprint": source_metadata_fingerprint,
        "engine_version": dynamic_engine_version,
        "dynamic_scenario_directory": str(dynamic_output),
        "lsmc_scenario_directory": str(lsmc_output),
    }
    for method, metrics in (
        ("dynamic", dynamic_metrics),
        ("lsmc", lsmc_metrics),
        ("continue", continue_metrics),
    ):
        row.update({f"{method}_{key}": value for key, value in metrics.items()})
    for benchmark_id, metrics in dynamic_benchmark_metrics.items():
        row.update({
            f"dynamic_benchmark_{benchmark_id}_{key}": value
            for key, value in metrics.items()
        })
    for benchmark_id, metrics in lsmc_benchmark_metrics.items():
        row.update({
            f"lsmc_benchmark_{benchmark_id}_{key}": value
            for key, value in metrics.items()
        })
    row.update({
        f"dynamic_{key}": value for key, value in dynamic_mp_risk.items()
    })
    row.update({f"lsmc_{key}": value for key, value in lsmc_mp_risk.items()})
    row.update({
        f"lsmc_{key}": value for key, value in lsmc_diagnostics.items()
    })

    comparable_metrics = (
        *MONETARY_METRICS,
        "new_business_margin_before_risk_margin",
        "guarantee_claims_to_premium",
        "guarantee_value_to_premium",
        "bel_nonunit_to_premium",
        "bel_total_to_premium",
        "future_fees_to_premium",
        "crediting_margin_to_premium",
        "expenses_to_premium",
        "hedge_costs_to_premium",
        "claims_to_future_fees",
        "fee_coverage_ratio",
    )
    for metric in comparable_metrics:
        dynamic_value = dynamic_metrics.get(metric)
        lsmc_value = lsmc_metrics.get(metric)
        if dynamic_value is not None and lsmc_value is not None:
            row[f"lsmc_minus_dynamic_{metric}"] = (
                float(lsmc_value) - float(dynamic_value))
        continue_value = continue_metrics.get(metric)
        if continue_value is not None and lsmc_value is not None:
            row[f"lsmc_minus_continue_{metric}"] = (
                float(lsmc_value) - float(continue_value))

    premium = float(row["premium_aud"])
    behaviour_risk = (
        float(dynamic_metrics[
            "insurer_net_present_value_before_risk_margin_aud"])
        - float(lsmc_metrics[
            "insurer_net_present_value_before_risk_margin_aud"])
    )
    row.update({
        # Positive means the fitted LSMC scenario is adverse to the insurer.
        "behaviour_model_gap_to_insurer_aud": behaviour_risk,
        "behaviour_model_gap_to_premium": _safe_ratio(
            behaviour_risk, premium),
        "lsmc_guarantee_claim_difference_vs_dynamic_to_premium": _safe_ratio(
            float(lsmc_metrics["pv_guarantee_claims_aud"])
            - float(dynamic_metrics["pv_guarantee_claims_aud"]),
            premium,
        ),
        "lsmc_policyholder_benefit_difference_vs_dynamic_to_premium": _safe_ratio(
            float(lsmc_metrics["pv_policyholder_benefits_aud"])
            - float(dynamic_metrics["pv_policyholder_benefits_aud"]),
            premium,
        ),
        "lsmc_policyholder_value_difference_vs_continue_aud": (
            float(lsmc_metrics["pv_policyholder_benefits_aud"])
            - float(continue_metrics["pv_policyholder_benefits_aud"])
        ),
        "lsmc_policyholder_value_difference_vs_continue_to_premium": _safe_ratio(
            float(lsmc_metrics["pv_policyholder_benefits_aud"])
            - float(continue_metrics["pv_policyholder_benefits_aud"]),
            premium,
        ),
    })
    return row, _paired_model_point_rows(
        rate, dynamic_rows, lsmc_rows, continue_rows)


def _validated_reuse_result(
    args: argparse.Namespace,
    rate: float,
    dynamic_output: Path,
    lsmc_output: Path,
    *,
    expected_stress: str = "base",
) -> tuple[
    bool,
    Optional[tuple[dict[str, object], list[dict[str, object]]]],
    str,
]:
    """Validate a reuse candidate fully before excluding it from scheduling."""
    if not args.reuse_existing:
        return False, None, "not_requested"
    if not _scenario_outputs_complete(
        dynamic_output,
        lsmc_output,
        require_plots=args.scenario_plots,
        expected_stress=expected_stress,
    ):
        return False, None, "rejected_incomplete_or_stress_mismatch"
    try:
        result = _load_scenario_result(
            args,
            rate,
            dynamic_output,
            lsmc_output,
            expected_stress=expected_stress,
        )
    except (OSError, ValueError, TypeError, KeyError, csv.Error) as exc:
        reason = " ".join(str(exc).split())
        return (
            False,
            None,
            f"rejected_{type(exc).__name__}:{reason}",
        )
    return True, result, "validated"


CORE_BASELINE_FIELDS = (
    "dynamic_pv_guarantee_claims_aud",
    "lsmc_pv_guarantee_claims_aud",
    "continue_pv_guarantee_claims_aud",
    "dynamic_guarantee_value_aud",
    "lsmc_guarantee_value_aud",
    "dynamic_pv_future_fees_aud",
    "lsmc_pv_future_fees_aud",
    "dynamic_bel_total_aud",
    "lsmc_bel_total_aud",
    "dynamic_insurer_net_present_value_before_risk_margin_aud",
    "lsmc_insurer_net_present_value_before_risk_margin_aud",
    "dynamic_new_business_margin_before_risk_margin",
    "lsmc_new_business_margin_before_risk_margin",
    "dynamic_negative_value_contract_share",
    "lsmc_negative_value_contract_share",
    "behaviour_model_gap_to_insurer_aud",
    "lsmc_policyholder_value_difference_vs_continue_aud",
    "lsmc_unweighted_income_election_action_rate",
    "lsmc_unweighted_full_withdrawal_action_rate",
    "dynamic_income_start_year_mean",
    "lsmc_income_start_year_mean",
    "dynamic_income_start_year_median",
    "lsmc_income_start_year_median",
    "dynamic_income_election_share",
    "lsmc_income_election_share",
    "dynamic_forced_income_election_share",
    "lsmc_forced_income_election_share",
    "dynamic_mean_growth_duration",
    "lsmc_mean_growth_duration",
    "dynamic_total_income_lapse_rate",
    "lsmc_total_income_lapse_rate",
)


def _add_baseline_deltas(
    rows: list[dict[str, object]],
    baseline_rate: float,
) -> None:
    baseline = next(
        row for row in rows
        if _rate_key(float(row["crediting_cap_rate"]))
        == _rate_key(baseline_rate)
    )
    for row in rows:
        row["baseline_crediting_cap_rate"] = baseline_rate
        for field in CORE_BASELINE_FIELDS:
            row[f"delta_vs_baseline_{field}"] = (
                float(row[field]) - float(baseline[field])
            )


METHOD_SENSITIVITY_METRICS = (
    ("pv_policyholder_benefits_aud", "AUD", "diagnostic"),
    ("pv_policyholder_benefits_pre_election_aud", "AUD", "diagnostic"),
    ("pv_policyholder_benefits_post_election_aud", "AUD", "diagnostic"),
    ("pv_guarantee_claims_aud", "AUD", "higher_is_adverse"),
    ("guarantee_value_aud", "AUD", "higher_is_adverse"),
    ("pv_future_fees_aud", "AUD", "lower_is_adverse"),
    ("pv_crediting_margin_aud", "AUD", "lower_is_adverse"),
    ("pv_growth_fees_aud", "AUD", "diagnostic"),
    ("pv_growth_crediting_margin_aud", "AUD", "diagnostic"),
    ("pv_post_election_guarantee_claims_aud", "AUD", "higher_is_adverse"),
    ("pv_expenses_aud", "AUD", "higher_is_adverse"),
    ("pv_hedge_costs_aud", "AUD", "higher_is_adverse"),
    ("bel_nonunit_aud", "AUD", "higher_is_adverse"),
    ("bel_total_aud", "AUD", "higher_is_adverse"),
    (
        "insurer_net_present_value_before_risk_margin_aud",
        "AUD",
        "lower_is_adverse",
    ),
    (
        "new_business_margin_before_risk_margin",
        "ratio",
        "lower_is_adverse",
    ),
    ("guarantee_claims_to_premium", "ratio", "higher_is_adverse"),
    ("guarantee_value_to_premium", "ratio", "higher_is_adverse"),
    ("bel_total_to_premium", "ratio", "higher_is_adverse"),
    ("expenses_to_premium", "ratio", "higher_is_adverse"),
    ("hedge_costs_to_premium", "ratio", "higher_is_adverse"),
    ("claims_to_future_fees", "ratio", "higher_is_adverse"),
    ("fee_coverage_ratio", "ratio", "lower_is_adverse"),
    ("income_start_year_mean", "years", "diagnostic"),
    ("income_start_year_median", "years", "diagnostic"),
    ("income_start_year_p10", "years", "diagnostic"),
    ("income_start_year_p90", "years", "diagnostic"),
    ("income_election_share", "ratio", "diagnostic"),
    ("forced_income_election_share", "ratio", "diagnostic"),
    ("mean_growth_duration", "years", "diagnostic"),
    ("growth_phase_exposure", "exposure_years", "diagnostic"),
    ("income_phase_exposure", "exposure_years", "diagnostic"),
    ("ordinary_income_lapse_rate", "ratio", "diagnostic"),
    ("performance_income_lapse_rate", "ratio", "diagnostic"),
    ("total_income_lapse_rate", "ratio", "diagnostic"),
)

MODEL_POINT_SENSITIVITY_METRICS = (
    ("negative_value_contract_share", "ratio", "higher_is_adverse"),
    (
        "model_point_nbm_weighted_p10",
        "ratio",
        "lower_is_adverse",
    ),
    (
        "model_point_nbm_weighted_lower_tail_mean_10pct",
        "ratio",
        "lower_is_adverse",
    ),
    ("guarantee_claims_hhi", "index", "diagnostic"),
    ("top_5_guarantee_claim_share", "ratio", "diagnostic"),
    ("joint_life_guarantee_claim_share", "ratio", "diagnostic"),
)

BEHAVIOUR_SENSITIVITY_METRICS = (
    (
        "behaviour_model_gap_to_insurer_aud",
        "AUD",
        "higher_is_adverse",
    ),
    (
        "behaviour_model_gap_to_premium",
        "ratio",
        "higher_is_adverse",
    ),
    (
        "lsmc_guarantee_claim_difference_vs_dynamic_to_premium",
        "ratio",
        "higher_is_adverse",
    ),
    (
        "lsmc_policyholder_benefit_difference_vs_dynamic_to_premium",
        "ratio",
        "diagnostic",
    ),
    (
        "lsmc_policyholder_value_difference_vs_continue_aud",
        "AUD",
        "diagnostic",
    ),
    (
        "lsmc_unweighted_income_election_action_rate",
        "lsmc_unweighted_full_withdrawal_action_rate",
        "ratio",
        "diagnostic",
    ),
)


def _finite_difference_per_100bp(
    rates: Sequence[float],
    values: Sequence[Optional[float]],
    index: int,
) -> tuple[Optional[float], Optional[float], Optional[float], str]:
    if len(rates) < 2:
        return None, None, None, "not_available_single_scenario"
    if index == 0:
        left, right = 0, 1
        scheme = "forward_secant"
    elif index == len(rates) - 1:
        left, right = len(rates) - 2, len(rates) - 1
        scheme = "backward_secant"
    else:
        left, right = index - 1, index + 1
        scheme = "bracketing_secant"
    rate_difference = rates[right] - rates[left]
    if (
        math.isclose(rate_difference, 0.0, abs_tol=1.0e-15)
        or values[left] is None
        or values[right] is None
    ):
        return None, rates[left], rates[right], scheme
    change = (
        (float(values[right]) - float(values[left]))
        / rate_difference
        * 0.01
    )
    return change, rates[left], rates[right], scheme


def _build_sensitivity_rows(
    rows: list[dict[str, object]],
    baseline_rate: float,
) -> list[dict[str, object]]:
    rates = [float(row["crediting_cap_rate"]) for row in rows]
    baseline_index = next(
        index for index, rate in enumerate(rates)
        if _rate_key(rate) == _rate_key(baseline_rate)
    )
    series: list[tuple[str, str, str, str]] = []
    for method in ("dynamic", "lsmc", "continue"):
        series.extend(
            (method, metric, unit, direction)
            for metric, unit, direction in METHOD_SENSITIVITY_METRICS
        )
    for method in ("dynamic", "lsmc"):
        series.extend(
            (method, metric, unit, direction)
            for metric, unit, direction in MODEL_POINT_SENSITIVITY_METRICS
        )
    series.extend(
        ("behaviour_difference", metric, unit, direction)
        for metric, unit, direction in BEHAVIOUR_SENSITIVITY_METRICS
    )

    output: list[dict[str, object]] = []
    for method, metric, unit, direction in series:
        field = metric if method == "behaviour_difference" else f"{method}_{metric}"
        values = [
            None if row.get(field) is None else float(row[field])
            for row in rows
        ]
        baseline_value = values[baseline_index]
        for index, (row, value) in enumerate(zip(rows, values)):
            change, lower_rate, upper_rate, scheme = (
                _finite_difference_per_100bp(rates, values, index)
            )
            adverse_multiplier = (
                1.0 if direction == "higher_is_adverse"
                else -1.0 if direction == "lower_is_adverse"
                else None
            )
            premium = float(row["premium_aud"])
            output.append({
                "crediting_cap_rate": row["crediting_cap_rate"],
                "crediting_cap_rate_percent": row["crediting_cap_rate_percent"],
                "method": method,
                "risk_metric": metric,
                "source_field": field,
                "unit": unit,
                "adverse_direction": direction,
                "value": value,
                "baseline_rate": baseline_rate,
                "baseline_value": baseline_value,
                "delta_vs_baseline": (
                    None
                    if value is None or baseline_value is None
                    else value - baseline_value
                ),
                "finite_difference_scheme": scheme,
                "finite_difference_lower_cap_rate": lower_rate,
                "finite_difference_upper_cap_rate": upper_rate,
                "finite_difference_span_bp": (
                    None
                    if lower_rate is None or upper_rate is None
                    else 10_000.0 * (upper_rate - lower_rate)
                ),
                "finite_difference_change_per_100bp": change,
                "finite_difference_change_per_100bp_percentage_points": (
                    None if change is None or unit != "ratio"
                    else 100.0 * change
                ),
                "finite_difference_change_per_100bp_as_percent_of_premium": (
                    None if change is None or unit != "AUD"
                    else 100.0 * change / premium
                ),
                "adverse_finite_difference_change_per_100bp": (
                    None
                    if change is None or adverse_multiplier is None
                    else adverse_multiplier * change
                ),
                "finite_difference_change_as_fraction_of_current_value": (
                    None
                    if change is None or value is None
                    or math.isclose(value, 0.0, abs_tol=1.0e-14)
                    else change / abs(value)
                ),
            })
    return output


def _build_decomposition_rows(
    rows: list[dict[str, object]],
    baseline_rate: float,
) -> list[dict[str, object]]:
    baseline = next(
        row for row in rows
        if _rate_key(float(row["crediting_cap_rate"]))
        == _rate_key(baseline_rate)
    )
    output: list[dict[str, object]] = []
    for row in rows:
        for metric in DECOMPOSITION_METRICS:
            continue_value = float(row[f"continue_{metric}"])
            lsmc_value = float(row[f"lsmc_{metric}"])
            dynamic_value = float(row[f"dynamic_{metric}"])
            baseline_continue = float(baseline[f"continue_{metric}"])
            baseline_lsmc = float(baseline[f"lsmc_{metric}"])
            baseline_dynamic = float(baseline[f"dynamic_{metric}"])
            mechanical = continue_value - baseline_continue
            lsmc_interaction = (
                (lsmc_value - continue_value)
                - (baseline_lsmc - baseline_continue)
            )
            dynamic_interaction = (
                (dynamic_value - continue_value)
                - (baseline_dynamic - baseline_continue)
            )
            lsmc_total = lsmc_value - baseline_lsmc
            dynamic_total = dynamic_value - baseline_dynamic
            output.append({
                "crediting_cap_rate": row["crediting_cap_rate"],
                "crediting_cap_rate_percent": row["crediting_cap_rate_percent"],
                "baseline_rate": baseline_rate,
                "metric": metric,
                "unit": "AUD",
                "continue_benchmark_change_vs_baseline": mechanical,
                "change_in_lsmc_minus_continue_gap_vs_baseline": lsmc_interaction,
                "lsmc_total_change_vs_baseline": lsmc_total,
                "lsmc_decomposition_gap": (
                    lsmc_total - mechanical - lsmc_interaction),
                "change_in_dynamic_minus_continue_gap_vs_baseline": (
                    dynamic_interaction),
                "dynamic_total_change_vs_baseline": dynamic_total,
                "dynamic_decomposition_gap": (
                    dynamic_total - mechanical - dynamic_interaction),
            })
    return output


def _validate_scenario_grid(
    rows: Sequence[Mapping[str, object]],
    *,
    label: str,
) -> None:
    if not rows:
        raise ValueError(f"{label} produced no scenario results.")
    bases = {str(row["valuation_basis"]) for row in rows}
    if len(bases) != 1:
        raise ValueError(f"{label} returned different valuation bases: {bases}")
    premium = float(rows[0]["premium_aud"])
    for row in rows[1:]:
        _require_close(
            float(row["premium_aud"]), premium, f"premium within {label}")
    checks = (
        ("evaluation_scenario_fingerprint", "evaluation scenario set"),
        ("training_scenario_fingerprint", "LSMC training scenario set"),
        ("source_metadata_fingerprint", "source inputs"),
        ("engine_version", "engine version"),
    )
    for field, description in checks:
        if len({str(row[field]) for row in rows}) != 1:
            raise ValueError(f"{label} does not share one {description}.")
    fit_fingerprints = {
        str(row["lsmc_fit_basis_fingerprint"]) for row in rows
    }
    if len(fit_fingerprints) != len(rows):
        raise ValueError(
            f"{label} reused an LSMC fit basis across different caps; every "
            "cap/stress combination must be refitted."
        )
    if {
        str(row["evaluation_scenario_fingerprint"]) for row in rows
    } == {
        str(row["training_scenario_fingerprint"]) for row in rows
    }:
        raise ValueError(f"{label} LSMC training and evaluation must differ.")


STRESS_DELTA_METRICS = (
    "bel_nonunit_aud",
    "pv_guarantee_claims_aud",
    "pv_future_fees_aud",
    "pv_policyholder_benefits_aud",
    "pv_expenses_aud",
    "pv_hedge_costs_aud",
    "guarantee_value_aud",
)


def _build_stress_loss_rows(
    base_rows: Sequence[Mapping[str, object]],
    stressed_rows: Sequence[Mapping[str, object]],
    baseline_rate: float,
) -> list[dict[str, object]]:
    base_by_rate = {
        _rate_key(float(row["crediting_cap_rate"])): row for row in base_rows
    }
    output: list[dict[str, object]] = []
    for stressed in stressed_rows:
        stress_id = str(stressed["stress_scenario_id"])
        definition = STRESS_DEFINITIONS[stress_id]
        rate_key = _rate_key(float(stressed["crediting_cap_rate"]))
        if rate_key not in base_by_rate:
            raise ValueError(
                f"Stress {stress_id!r} has no matching base cap scenario."
            )
        base = base_by_rate[rate_key]
        _require_close(
            float(stressed["premium_aud"]),
            float(base["premium_aud"]),
            f"premium for stress {stress_id}",
        )
        premium = float(base["premium_aud"])
        row: dict[str, object] = {
            "stress_scenario_id": stress_id,
            "risk_category": definition["risk_category"],
            "stress_label": definition["label"],
            "stress_description": definition["description"],
            "crediting_cap_rate": stressed["crediting_cap_rate"],
            "crediting_cap_rate_percent": stressed[
                "crediting_cap_rate_percent"],
            "baseline_crediting_cap_rate": baseline_rate,
            "premium_aud": premium,
            "base_evaluation_scenario_fingerprint": base[
                "evaluation_scenario_fingerprint"],
            "stress_evaluation_scenario_fingerprint": stressed[
                "evaluation_scenario_fingerprint"],
            "stress_training_scenario_fingerprint": stressed[
                "training_scenario_fingerprint"],
            "lsmc_out_of_sample_policyholder_value_dominates_continue": stressed[
                "lsmc_out_of_sample_policyholder_value_dominates_continue"],
            "lsmc_regression_accepted_share": stressed[
                "lsmc_regression_accepted_share"],
            "lsmc_training_fallback_policy_share": stressed[
                "lsmc_training_fallback_policy_share"],
            "dynamic_stress_scenario_directory": stressed[
                "dynamic_scenario_directory"],
            "lsmc_stress_scenario_directory": stressed[
                "lsmc_scenario_directory"],
        }
        for method in ("dynamic", "lsmc", "continue"):
            npv_field = (
                f"{method}_insurer_net_present_value_before_risk_margin_aud"
            )
            base_npv = float(base[npv_field])
            stress_npv = float(stressed[npv_field])
            signed_loss = base_npv - stress_npv
            row[f"{method}_base_insurer_npv_aud"] = base_npv
            row[f"{method}_stress_insurer_npv_aud"] = stress_npv
            row[f"{method}_signed_stress_loss_aud"] = signed_loss
            row[f"{method}_adverse_stress_loss_aud"] = max(0.0, signed_loss)
            row[f"{method}_signed_stress_loss_bp_of_premium"] = (
                10_000.0 * signed_loss / premium)
            row[f"{method}_adverse_stress_loss_bp_of_premium"] = (
                10_000.0 * max(0.0, signed_loss) / premium)
            for metric in STRESS_DELTA_METRICS:
                row[f"{method}_stress_delta_{metric}"] = (
                    float(stressed[f"{method}_{metric}"])
                    - float(base[f"{method}_{metric}"])
                )
        dynamic_loss = float(row["dynamic_signed_stress_loss_aud"])
        lsmc_loss = float(row["lsmc_signed_stress_loss_aud"])
        row["lsmc_minus_dynamic_signed_stress_loss_aud"] = (
            lsmc_loss - dynamic_loss)
        row["lsmc_minus_dynamic_signed_stress_loss_bp_of_premium"] = (
            10_000.0 * (lsmc_loss - dynamic_loss) / premium)
        output.append(row)

    stress_order = {name: index for index, name in enumerate(STRESS_DEFINITIONS)}
    output.sort(key=lambda row: (
        stress_order[str(row["stress_scenario_id"])],
        float(row["crediting_cap_rate"]),
    ))
    for stress_id in STRESS_DEFINITIONS:
        group = [
            row for row in output if row["stress_scenario_id"] == stress_id
        ]
        if not group:
            continue
        rates = [float(row["crediting_cap_rate"]) for row in group]
        baseline_index = next(
            index for index, rate in enumerate(rates)
            if _rate_key(rate) == _rate_key(baseline_rate)
        )
        for method in ("dynamic", "lsmc", "continue"):
            field = f"{method}_signed_stress_loss_aud"
            values = [float(row[field]) for row in group]
            baseline_value = values[baseline_index]
            for index, row in enumerate(group):
                change, lower, upper, scheme = _finite_difference_per_100bp(
                    rates, values, index)
                row[f"{method}_signed_stress_loss_change_vs_baseline_cap_aud"] = (
                    values[index] - baseline_value)
                row[f"{method}_stress_loss_cap_finite_difference_scheme"] = scheme
                row[f"{method}_stress_loss_cap_fd_lower_rate"] = lower
                row[f"{method}_stress_loss_cap_fd_upper_rate"] = upper
                row[f"{method}_stress_loss_change_per_100bp_cap_aud"] = change
                row[
                    f"{method}_stress_loss_change_per_100bp_cap_bp_of_premium"
                ] = (
                    None
                    if change is None
                    else 10_000.0 * change / float(row["premium_aud"])
                )
    return output


def _aud_axis(value: float, _position: object = None) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}bn"
    if absolute >= 1_000_000:
        return f"{value / 1_000_000:.1f}m"
    if absolute >= 1_000:
        return f"{value / 1_000:.0f}k"
    return f"{value:.0f}"


def _create_plots(
    rows: list[dict[str, object]],
    decomposition_rows: list[dict[str, object]],
    stress_rows: list[dict[str, object]],
    output: Path,
    baseline_rate: float,
) -> tuple[dict[str, str], Optional[str]]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter
    except ImportError as exc:
        raise RuntimeError(
            "Plots are enabled, but matplotlib is not available. Install "
            "matplotlib or rerun explicitly with --no-plots."
        ) from exc

    output.mkdir(parents=True, exist_ok=True)
    caps = [float(row["crediting_cap_rate_percent"]) for row in rows]
    baseline_percent = 100.0 * baseline_rate
    colours = {"dynamic": "#5b6573", "lsmc": "#005f73"}
    labels = {
        "dynamic": "Dynamic assumptions",
        "lsmc": "Fitted annual LSMC lower bound",
    }
    figure_paths: dict[str, str] = {}

    def finish(fig: object, path: Path) -> None:
        fig.tight_layout()
        fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)

    def plot_method_lines(
        axis: object,
        field: str,
        *,
        scale: float = 1.0,
        zero_line: bool = False,
    ) -> None:
        for method in ("dynamic", "lsmc"):
            values = [
                math.nan
                if row.get(f"{method}_{field}") is None
                else scale * float(row[f"{method}_{field}"])
                for row in rows
            ]
            axis.plot(
                caps,
                values,
                marker="o",
                linewidth=2.0,
                color=colours[method],
                label=labels[method],
            )
        if zero_line:
            axis.axhline(0.0, color="#1f2937", linewidth=0.8)
        axis.axvline(baseline_percent, color="#9ca3af", linestyle="--")
        axis.grid(alpha=0.25)

    fig, axes = plt.subplots(2, 3, figsize=(15.0, 9.0), sharex=True)
    panels = (
        (axes[0, 0], "guarantee_claims_to_premium", 100.0,
         "Guarantee Claims / Premium", "%"),
        (axes[0, 1], "guarantee_value_to_premium", 100.0,
         "Net Guarantee Value / Premium", "%"),
        (axes[0, 2], "bel_nonunit_to_premium", 100.0,
         "Non-unit BEL / Premium", "%"),
        (axes[1, 0], "new_business_margin_before_risk_margin", 100.0,
         "New Business Margin before RM", "%"),
        (axes[1, 1], "fee_coverage_ratio", 1.0,
         "Future Fees / Claims and Costs", "ratio"),
        (axes[1, 2], "hedge_costs_to_premium", 100.0,
         "Hedge-cost Proxy / Premium", "%"),
    )
    for axis, field, scale, title, ylabel in panels:
        plot_method_lines(
            axis, field, scale=scale,
            zero_line=field in {
                "guarantee_value_to_premium",
                "bel_nonunit_to_premium",
                "new_business_margin_before_risk_margin",
            },
        )
        axis.set_title(title, loc="left")
        axis.set_ylabel(ylabel)
    axes[0, 0].legend()
    for axis in axes[1, :]:
        axis.set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
    fig.suptitle(
        "Generic index-linked lifetime-income valuation exposures by crediting cap"
    )
    exposure_path = output / "01_valuation_exposure_risks_by_crediting_cap.png"
    finish(fig, exposure_path)
    figure_paths["valuation_exposure_risks"] = str(exposure_path)

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.0), sharex=True)
    behaviour_panels = (
        (
            axes[0, 0], "behaviour_model_gap_to_premium",
            "Insurer behaviour-model gap: Dynamic NPV - LSMC NPV", 100.0,
        ),
        (
            axes[0, 1],
            "lsmc_guarantee_claim_difference_vs_dynamic_to_premium",
            "LSMC Guarantee-Claim Difference vs Dynamic", 100.0,
        ),
        (
            axes[1, 0],
            "lsmc_policyholder_benefit_difference_vs_dynamic_to_premium",
            "LSMC Policyholder-Benefit Difference vs Dynamic", 100.0,
        ),
        (
            axes[1, 1], "lsmc_unweighted_decision_event_exercise_rate",
            "LSMC unweighted decision-event exercise rate", 100.0,
        ),
    )
    for axis, field, title, scale in behaviour_panels:
        axis.plot(
            caps,
            [scale * float(row[field]) for row in rows],
            marker="o",
            linewidth=2.0,
            color="#9b2226" if "risk" in field or "claim" in field else "#0a9396",
        )
        axis.axhline(0.0, color="#1f2937", linewidth=0.8)
        axis.axvline(baseline_percent, color="#9ca3af", linestyle="--")
        axis.set_title(title, loc="left")
        axis.set_ylabel("% of Premium" if "exercise" not in field else "%")
        axis.grid(alpha=0.25)
    for axis in axes[1, :]:
        axis.set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
    fig.suptitle(
        "Behaviour-model scenario gap: fitted annual LSMC versus Dynamic"
    )
    behaviour_path = output / "02_behaviour_model_gap_by_crediting_cap.png"
    finish(fig, behaviour_path)
    figure_paths["behaviour_model_gap"] = str(behaviour_path)

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.0), sharex=True)
    model_point_panels = (
        (
            axes[0, 0], "negative_value_contract_share", 100.0,
            "Contract share in negative-value segments", "%",
        ),
        (
            axes[0, 1],
            "model_point_nbm_weighted_lower_tail_mean_10pct", 100.0,
            "Lowest 10% contract-weighted segment NBM mean", "%",
        ),
        (
            axes[1, 0], "guarantee_claims_hhi", 1.0,
            "Segment-dependent guarantee-claim HHI", "index",
        ),
        (
            axes[1, 1], "joint_life_guarantee_claim_share", 100.0,
            "Joint-life share of guarantee claims", "%",
        ),
    )
    for axis, field, scale, title, ylabel in model_point_panels:
        plot_method_lines(
            axis, field, scale=scale,
            zero_line="nbm" in field,
        )
        axis.set_title(title, loc="left")
        axis.set_ylabel(ylabel)
    axes[0, 0].legend()
    for axis in axes[1, :]:
        axis.set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
    fig.suptitle(
        "Model-point heterogeneity and concentration (not a pathwise VaR/CTE)"
    )
    model_point_path = output / "03_model_point_risk_by_crediting_cap.png"
    finish(fig, model_point_path)
    figure_paths["model_point_risk"] = str(model_point_path)

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.0), sharex=True)
    quality_panels = (
        (
            axes[0, 0], "lsmc_regression_accepted_share", 100.0,
            "Accepted LSMC regressions", "%",
        ),
        (
            axes[0, 1], "lsmc_oof_r_squared_median", 1.0,
            "Median out-of-fold R-squared", "R-squared",
        ),
        (
            axes[1, 0], "lsmc_training_fallback_policy_share", 100.0,
            "Training fallback policy share", "%",
        ),
        (
            axes[1, 1], "lsmc_condition_number_max", 1.0,
            "Maximum regression condition number", "condition number",
        ),
    )
    for axis, field, scale, title, ylabel in quality_panels:
        axis.plot(
            caps,
            [scale * float(row[field]) for row in rows],
            marker="o",
            linewidth=2.0,
            color="#bb3e03",
        )
        axis.axvline(baseline_percent, color="#9ca3af", linestyle="--")
        axis.set_title(title, loc="left")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)
    if all(float(row["lsmc_condition_number_max"]) > 0.0 for row in rows):
        axes[1, 1].set_yscale("log")
    for axis in axes[1, :]:
        axis.set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
    fig.suptitle("LSMC model-risk diagnostics by crediting cap")
    quality_path = output / "04_lsmc_model_risk_diagnostics.png"
    finish(fig, quality_path)
    figure_paths["lsmc_model_risk_diagnostics"] = str(quality_path)

    selected_decomposition = {
        metric: [row for row in decomposition_rows if row["metric"] == metric]
        for metric in (
            "pv_policyholder_benefits_aud",
            "insurer_net_present_value_before_risk_margin_aud",
        )
    }
    fig, axes = plt.subplots(2, 1, figsize=(12.0, 9.0), sharex=True)
    bar_width = min(1.1, max(0.25, 0.18 * (max(caps) - min(caps) or 1.0)))
    for axis, (metric, metric_rows) in zip(axes, selected_decomposition.items()):
        mechanical = [
            float(row["continue_benchmark_change_vs_baseline"])
            for row in metric_rows
        ]
        interaction = [
            float(row["change_in_lsmc_minus_continue_gap_vs_baseline"])
            for row in metric_rows
        ]
        total = [
            float(row["lsmc_total_change_vs_baseline"])
            for row in metric_rows
        ]
        axis.bar(
            caps, mechanical, width=bar_width, color="#94d2bd",
            label="Continue-benchmark component",
        )
        axis.bar(
            caps, interaction, width=bar_width, bottom=mechanical,
            color="#ee9b00", label="Change in LSMC-minus-Continue gap",
        )
        axis.plot(
            caps, total, marker="D", linestyle="none", color="#9b2226",
            label="Total LSMC change",
        )
        axis.axhline(0.0, color="#1f2937", linewidth=0.8)
        axis.axvline(baseline_percent, color="#9ca3af", linestyle="--")
        axis.yaxis.set_major_formatter(FuncFormatter(_aud_axis))
        axis.grid(axis="y", alpha=0.25)
        axis.set_ylabel("AUD")
        axis.set_title(
            "PV Policyholder Benefits"
            if metric == "pv_policyholder_benefits_aud"
            else "Insurer NPV before Risk Margin",
            loc="left",
        )
    axes[0].legend(ncol=3, fontsize=9)
    axes[1].set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
    fig.suptitle(
        f"Crediting-cap effect relative to {baseline_percent:.2f}% baseline"
    )
    decomposition_path = output / "05_crediting_cap_effect_decomposition.png"
    finish(fig, decomposition_path)
    figure_paths["crediting_cap_effect_decomposition"] = str(decomposition_path)

    if stress_rows:
        selected_stresses = [
            stress_id for stress_id in STRESS_DEFINITIONS
            if any(row["stress_scenario_id"] == stress_id for row in stress_rows)
        ]
        fig, axes = plt.subplots(4, 2, figsize=(14.5, 15.5), sharex=True)
        flat_axes = list(axes.flat)
        for axis, stress_id in zip(flat_axes, selected_stresses):
            group = [
                row for row in stress_rows
                if row["stress_scenario_id"] == stress_id
            ]
            group_caps = [
                float(row["crediting_cap_rate_percent"]) for row in group
            ]
            for method in ("dynamic", "lsmc"):
                axis.plot(
                    group_caps,
                    [
                        float(row[
                            f"{method}_signed_stress_loss_bp_of_premium"
                        ])
                        for row in group
                    ],
                    marker="o",
                    linewidth=2.0,
                    color=colours[method],
                    label=labels[method],
                )
            axis.axhline(0.0, color="#1f2937", linewidth=0.8)
            axis.axvline(baseline_percent, color="#9ca3af", linestyle="--")
            axis.set_title(str(STRESS_DEFINITIONS[stress_id]["label"]), loc="left")
            axis.set_ylabel("signed loss (bp premium)")
            axis.grid(alpha=0.25)
        for axis in flat_axes[len(selected_stresses):]:
            axis.set_visible(False)
        if selected_stresses:
            flat_axes[0].legend()
        for axis in axes[-1, :]:
            if axis.get_visible():
                axis.set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
        fig.suptitle(
            "One-factor shock-and-revalue loss by crediting cap and behaviour method"
        )
        stress_path = output / "06_stress_loss_by_crediting_cap.png"
        finish(fig, stress_path)
        figure_paths["stress_loss_by_crediting_cap"] = str(stress_path)

        cap_labels = [f"{cap:.2f}%" for cap in caps]
        stress_labels = [
            str(STRESS_DEFINITIONS[stress_id]["label"])
            for stress_id in selected_stresses
        ]
        fields = (
            ("dynamic_signed_stress_loss_bp_of_premium", "Dynamic"),
            ("lsmc_signed_stress_loss_bp_of_premium", "LSMC fitted lower bound"),
            (
                "lsmc_minus_dynamic_signed_stress_loss_bp_of_premium",
                "LSMC minus Dynamic loss",
            ),
        )
        matrices: list[list[list[float]]] = []
        for field, _title in fields:
            matrices.append([
                [
                    float(next(
                        row[field] for row in stress_rows
                        if row["stress_scenario_id"] == stress_id
                        and _rate_key(float(row["crediting_cap_rate"]))
                        == _rate_key(float(base_row["crediting_cap_rate"]))
                    ))
                    for base_row in rows
                ]
                for stress_id in selected_stresses
            ])
        max_abs = max(
            (abs(value) for matrix in matrices for line in matrix for value in line),
            default=1.0,
        ) or 1.0
        fig, heat_axes = plt.subplots(1, 3, figsize=(18.0, 7.5), sharey=True)
        heat_image = None
        for axis, matrix, (_field, title) in zip(heat_axes, matrices, fields):
            heat_image = axis.imshow(
                matrix,
                aspect="auto",
                cmap="RdBu_r",
                vmin=-max_abs,
                vmax=max_abs,
            )
            axis.set_xticks(range(len(cap_labels)), labels=cap_labels, rotation=45)
            axis.set_yticks(range(len(stress_labels)), labels=stress_labels)
            axis.set_title(title, loc="left")
            axis.set_xlabel("Crediting Cap")
        if heat_image is not None:
            fig.colorbar(
                heat_image,
                ax=list(heat_axes),
                label="signed insurer stress loss (bp premium)",
                shrink=0.85,
            )
        fig.suptitle("Risk-driver / crediting-cap stress-loss heatmap")
        heatmap_path = output / "07_stress_loss_heatmap.png"
        finish(fig, heatmap_path)
        figure_paths["stress_loss_heatmap"] = str(heatmap_path)

    return figure_paths, str(matplotlib.__version__)


def _format_money(value: float) -> str:
    return f"{value:,.2f}"


def _write_report(
    path: Path,
    rows: list[dict[str, object]],
    sensitivity_rows: list[dict[str, object]],
    stress_rows: list[dict[str, object]],
    baseline_rate: float,
    figure_paths: Mapping[str, str],
    worker_plan: WorkerPlan,
) -> None:
    baseline = next(
        row for row in rows
        if _rate_key(float(row["crediting_cap_rate"]))
        == _rate_key(baseline_rate)
    )
    basis = str(baseline["valuation_basis"])
    monetary_description = (
        "absolute Portfoliowerte"
        if basis == "absolute_portfolio"
        else "normalisierte gewichtete Durchschnittswerte je repräsentativem Vertrag"
    )
    lines = [
        "# GMLB/GMWB-Portfolio-Risiko-, Cap- und Behaviour-Analyse",
        "",
        (
            "Die Analyse vergleicht Dynamic Behaviour mit einer jährlich "
            "entscheidenden, out-of-sample bewerteten LSMC-Policy. Die als "
            "Crediting Rate bezeichnete Eingabe ist technisch der Scenario "
            "Maximum Return beziehungsweise Crediting Cap auf dem vollständigen "
            "50/50-Referenzfondsreturn: `min(max(R_fund, 0), Cap)`. Nur 6 % "
            "sind die vertragliche Basis; andere Werte sind nichtvertragliche "
            "Design-Sensitivitäten. Alle übrigen Produktparameter bleiben fix; "
            "die Varianten werden nicht budgetneutral neu bepreist."
        ),
        (
            "Zusätzlich wird ein symmetrisches Einfaktor-Shock-and-Revalue-Gitter "
            "für Dynamic und LSMC gerechnet; die LSMC-Policy wird je Kombination "
            "aus Stress und Cap auf unabhängigen Trainingspfaden neu angepasst."
            if stress_rows
            else "Das explizite Shock-and-Revalue-Gitter wurde per Option ausgelassen."
        ),
        "",
        f"Bewertungsbasis: **{monetary_description}**. Alle Läufe verwenden "
        "Heston-Hull-White unter Q und Common Random Numbers.",
        "",
        "## Ausführung",
        "",
        (
            (
                f"Für {worker_plan.pending_job_count} neu zu rechnende "
                f"Szenariopaare wurden {worker_plan.selected_workers} Worker "
                f"gewählt (konservativer Auto-Wert: "
                f"{worker_plan.safe_auto_workers}); "
                f"{worker_plan.reused_job_count} Szenariopaare wurden "
                "wiederverwendet. "
                + (
                    "Basis- und Stressfälle teilen sich eine gemeinsame "
                    "Worker-Queue; "
                    if stress_rows
                    else "Die Queue enthält ausschließlich Basisfälle; "
                )
                + "Dynamic und LSMC laufen innerhalb eines Szenariopaars "
                "nacheinander."
            )
            if worker_plan.pending_job_count
            else (
                f"Alle {worker_plan.reused_job_count} Szenariopaare wurden "
                "wiederverwendet; es wurde kein Valuation-Child gestartet."
            )
        ),
        (
            "Die RAM-Planung schätzt den Peak je Worker auf "
            f"{_format_gib(worker_plan.estimated_worker_bytes)} bei einem "
            f"Projektionshorizont von "
            f"{worker_plan.estimated_horizon_months} Monaten; verfügbar waren "
            f"zum Planungszeitpunkt "
            f"{_format_gib(worker_plan.available_memory_bytes)}. Pro Child "
            f"gelten {worker_plan.blas_threads_per_child} BLAS/OpenMP-Thread(s). "
            "Die RAM-Schätzung ist eine konservative Planungsheuristik, keine "
            "harte Speichergarantie."
        ),
        *(
            [
                "",
                (
                    "> **Ausführungswarnung:** Die konfigurierte Workerzahl "
                    "liegt über dem konservativen Auto-Wert und kann den "
                    "verfügbaren Arbeitsspeicher überschreiten."
                ),
            ]
            if worker_plan.configured_workers_exceed_safe_auto
            else []
        ),
        "",
        "## Kernergebnisse nach Crediting Cap",
        "",
        (
            "| Cap | Guarantee Claims Dynamic | Guarantee Claims LSMC | "
            "Insurer NPV Dynamic | Insurer NPV LSMC | Behaviour-Model Gap | "
            "LSMC Exercise-Diagnostik | OOS PH ≥ Continue |"
        ),
        "|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for row in rows:
        lines.append(
            f"| {float(row['crediting_cap_rate_percent']):.2f}% | "
            f"{_format_money(float(row['dynamic_pv_guarantee_claims_aud']))} | "
            f"{_format_money(float(row['lsmc_pv_guarantee_claims_aud']))} | "
            f"{_format_money(float(row['dynamic_insurer_net_present_value_before_risk_margin_aud']))} | "
            f"{_format_money(float(row['lsmc_insurer_net_present_value_before_risk_margin_aud']))} | "
            f"{_format_money(float(row['behaviour_model_gap_to_insurer_aud']))} | "
            f"{100.0 * float(row['lsmc_unweighted_decision_event_exercise_rate']):.3f}% | "
            f"{'ja' if row['lsmc_out_of_sample_policyholder_value_dominates_continue'] else 'NEIN'} |"
        )

    failed_oos_caps = [
        float(row["crediting_cap_rate_percent"])
        for row in rows
        if not bool(row[
            "lsmc_out_of_sample_policyholder_value_dominates_continue"
        ])
    ]
    if failed_oos_caps:
        lines.extend([
            "",
            (
                "> **LSMC-Validierungswarnung:** Die eingefrorene Policy "
                "unterschreitet out of sample den Continue-Benchmark bei: "
                + ", ".join(f"{cap:.2f}%" for cap in failed_oos_caps)
                + ". Diese Szenarien sind Fit-Diagnostik und dürfen nicht als "
                "optimales Verhalten interpretiert werden."
            ),
        ])
    below_minimum_caps = [
        float(row["crediting_cap_rate_percent"])
        for row in rows
        if bool(row["below_contractual_minimum_crediting_cap"])
    ]
    if below_minimum_caps:
        lines.extend([
            "",
            (
                "> **Vertragsgrenzen-Warnung:** Caps unter dem vertraglichen "
                "Minimum von 0.25% wurden als rein technische Sensitivität "
                "gerechnet: "
                + ", ".join(f"{cap:.4f}%" for cap in below_minimum_caps)
                + "."
            ),
        ])

    lines.extend([
        "",
        f"## Risikoprofil bei {100.0 * baseline_rate:.2f}% Basis-Cap",
        "",
        "| Kennzahl | Dynamic | LSMC |",
        "|---|---:|---:|",
        (
            "| Guarantee Claims / Premium | "
            f"{100.0 * float(baseline['dynamic_guarantee_claims_to_premium']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_guarantee_claims_to_premium']):.3f}% |"
        ),
        (
            "| Net Guarantee Value / Premium | "
            f"{100.0 * float(baseline['dynamic_guarantee_value_to_premium']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_guarantee_value_to_premium']):.3f}% |"
        ),
        (
            "| Non-unit BEL / Premium | "
            f"{100.0 * float(baseline['dynamic_bel_nonunit_to_premium']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_bel_nonunit_to_premium']):.3f}% |"
        ),
        (
            "| New Business Margin vor Risk Margin | "
            f"{100.0 * float(baseline['dynamic_new_business_margin_before_risk_margin']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_new_business_margin_before_risk_margin']):.3f}% |"
        ),
        (
            "| Vertragsanteil in negativ klassifizierten Segmenten | "
            f"{100.0 * float(baseline['dynamic_negative_value_contract_share']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_negative_value_contract_share']):.3f}% |"
        ),
        (
            "| NBM-Mittel im unteren 10%-Vertrags-/Segment-Tail | "
            f"{100.0 * float(baseline['dynamic_model_point_nbm_weighted_lower_tail_mean_10pct']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_model_point_nbm_weighted_lower_tail_mean_10pct']):.3f}% |"
        ),
        "",
        (
            "Der untere Segment-Tail misst Heterogenität über repräsentative "
            "Verträge. Er ist keine pfadweise Verlustverteilung und kein VaR/CTE."
        ),
        (
            "Die Negativklassifikation verwendet die konfigurierte "
            f"Materialität von {float(baseline['dynamic_profitability_materiality_bp']):.3f} bp. "
            "HHI und Top-5-Anteile hängen von der Modellpunktsegmentierung ab "
            "und sind keine Diversifikationsmessung systematischer Risiken."
        ),
        (
            "Kennzahlidentitäten sind nicht als unabhängige Risiken zu lesen: "
            "Insurer NPV vor Risk Margin = − Non-unit BEL; Net Guarantee Value "
            "= Guarantee Claims − LIP Fees. Die Fee-Coverage-Kennzahl ist "
            "`Future Fees / (Guarantee Claims + Expenses + Hedge-cost Proxy)` "
            "und lässt Crediting Margin sowie MVA-/APS-Retention bewusst außen vor."
        ),
    ])

    if stress_rows:
        baseline_stresses = [
            row for row in stress_rows
            if _rate_key(float(row["crediting_cap_rate"]))
            == _rate_key(baseline_rate)
        ]
        lines.extend([
            "",
            f"## Einfaktor-Stressverluste bei {100.0 * baseline_rate:.2f}% Basis-Cap",
            "",
            (
                "`Signed Stress Loss = Insurer NPV_base − Insurer NPV_stress`; "
                "positive Werte sind advers. Die Tabelle zeigt Basispunkte der "
                "Prämie. `LSMC − Dynamic` misst die Behaviour-Modell-Amplifikation "
                "des jeweiligen voll reoptimierten Stresses."
            ),
            "",
            "| Einfaktorstress | Dynamic signed | LSMC signed | LSMC adverse | LSMC − Dynamic | OOS PH ≥ Continue |",
            "|---|---:|---:|---:|---:|:---:|",
        ])
        for stress in baseline_stresses:
            lines.append(
                f"| {stress['stress_label']} | "
                f"{float(stress['dynamic_signed_stress_loss_bp_of_premium']):.3f} bp | "
                f"{float(stress['lsmc_signed_stress_loss_bp_of_premium']):.3f} bp | "
                f"{float(stress['lsmc_adverse_stress_loss_bp_of_premium']):.3f} bp | "
                f"{float(stress['lsmc_minus_dynamic_signed_stress_loss_bp_of_premium']):.3f} bp | "
                f"{'ja' if stress['lsmc_out_of_sample_policyholder_value_dominates_continue'] else 'NEIN'} |"
            )
        failed_stress_oos = [
            row for row in stress_rows
            if not bool(row[
                "lsmc_out_of_sample_policyholder_value_dominates_continue"
            ])
        ]
        lines.extend([
            "",
            (
                "Zins-Up und Zins-Down werden separat gezeigt; es wird weder das "
                "Maximum automatisch ausgewählt noch eine Korrelationsaggregation "
                "zu einem regulatorischen Kapitalbetrag vorgenommen. Der Einfluss "
                "des Caps auf jeden Stressverlust steht vollständig in der Stress-CSV."
            ),
        ])
        if failed_stress_oos:
            lines.extend([
                "",
                (
                    "> **LSMC-Stressvalidierungswarnung:** Die eingefrorene "
                    "Stress-Policy unterschreitet den Continue-Benchmark bei "
                    + ", ".join(
                        f"{row['stress_scenario_id']} / "
                        f"{float(row['crediting_cap_rate_percent']):.2f}%"
                        for row in failed_stress_oos
                    )
                    + ". Diese Stresswerte dürfen nicht als optimale "
                    "Policyholder-Ausübung interpretiert werden."
                ),
            ])

    lines.extend([
        "",
        "## Cap-Sekante auf dem Szenariogitter an der Basis",
        "",
        (
            "Die Änderung je +100 bp ist keine infinitesimale Sensitivität. "
            "Sie wird über die in der Tabelle ausgewiesenen benachbarten "
            "Cap-Szenarien berechnet; wegen Cap-Nichtlinearität und LSMC-Refit "
            "kann sie von einem symmetrischen Bump am Basispunkt abweichen."
        ),
        "",
        "| Ansatz | Kennzahl | Sekantenintervall | Änderung je +100 bp |",
        "|---|---|---:|---:|",
    ])
    wanted = {
        ("dynamic", "pv_guarantee_claims_aud"),
        ("lsmc", "pv_guarantee_claims_aud"),
        ("dynamic", "insurer_net_present_value_before_risk_margin_aud"),
        ("lsmc", "insurer_net_present_value_before_risk_margin_aud"),
        ("behaviour_difference", "behaviour_model_gap_to_insurer_aud"),
    }
    for sensitivity in sensitivity_rows:
        if (
            _rate_key(float(sensitivity["crediting_cap_rate"]))
            != _rate_key(baseline_rate)
            or (str(sensitivity["method"]), str(sensitivity["risk_metric"]))
            not in wanted
        ):
            continue
        change = sensitivity["finite_difference_change_per_100bp"]
        lower = sensitivity["finite_difference_lower_cap_rate"]
        upper = sensitivity["finite_difference_upper_cap_rate"]
        interval = (
            "n/a"
            if lower is None or upper is None
            else f"{100.0 * float(lower):.2f}%–{100.0 * float(upper):.2f}%"
        )
        lines.append(
            f"| {sensitivity['method']} | {sensitivity['risk_metric']} | "
            f"{interval} | "
            f"{_format_money(float(change)) if change is not None else 'n/a'} |"
        )

    lines.extend([
        "",
        "## Interpretation des Behaviour-Vergleichs",
        "",
        (
            "`Behaviour-Model Gap = Dynamic Insurer NPV − LSMC Insurer NPV`. Ein "
            "positiver Wert bedeutet, dass der angepasste LSMC-Ansatz für den "
            "Versicherer adverser ist. Die LSMC-Policy maximiert den "
            "Policyholder-Cashflow-Barwert unter Q; sie optimiert weder "
            "Versichererprofit noch Risikokapital."
        ),
        "",
        (
            "Das Delta ist ein Vergleich zweier vollständiger Behaviour-Ansätze: "
            "monatliche statistische Lapse-/Withdrawal-Annahmen einerseits und "
            "jährliches Continue/Full Withdrawal andererseits. Es ist deshalb "
            "nicht als isolierter Effekt einer einzelnen Lapse-Rate zu lesen."
        ),
        "",
        (
            "Der Continue-Benchmark zerlegt den Cap-Effekt algebraisch in die "
            "Änderung unter Continue und die Änderung des jeweiligen Wert-Gaps "
            "gegen Continue. Letztere umfasst Refit, Zustands-/Payoff-Änderungen "
            "und Trainingsrauschen; sie ist kein isolierter kausaler "
            "Reoptimierungseffekt. Die rohe "
            "LSMC Exercise-Rate ist über Modellpunkt-/Pfad-/Entscheidungsereignisse "
            "ungewichtet und keine Portfolio-Surrender-Rate."
        ),
        "",
        "## Modellgrenzen",
        "",
        (
            "- Die Runner behalten erwartete Q-Barwerte und Modellpunkt-Skalare, "
            "aber keine pfadweisen Portfolioverluste. Daher werden weder VaR/TVaR/"
            "CTE noch Cashflow-at-Risk berechnet."
        ),
        (
            "- Die ausgewiesenen Markt-, biometrischen und Expense-Schocks sind "
            "einzelne Research-Stresse. Sie sind weder kalibrierte Best-Estimate-"
            "Prognosen noch eine APRA/LAGIC- oder Solvency-II-Kapitalaggregation."
            if stress_rows
            else "- Markt-, biometrische und Expense-Stresse wurden in diesem Lauf ausgelassen."
        ),
        (
            "- Der Equity-Level-Stress skaliert die simulierten Equity-Indizes ab "
            "Monat eins um 39%. Das t=0-Konto des Duration-zero-Neugeschäfts wird "
            "nicht wie ein Unit-Linked-Spotbestand geschockt."
            if stress_rows
            else "- Es liegt kein Equity-Level-Stressergebnis vor."
        ),
        (
            "- Statistische Lapse-/Take-up-/Withdrawal-Stresse werden nicht als "
            "symmetrische LSMC-Sensitivität ausgegeben: beim LSMC ersetzt das "
            "Continue/Full-Withdrawal-Action-Set die statistische Income-Lapse-Rate."
        ),
        (
            "- Common Random Numbers reduzieren Vergleichsrauschen, ersetzen "
            "aber keine Monte-Carlo-Standardfehler oder Wiederholungen über "
            "Evaluations- und Trainings-Seeds. Kleine Deltas sind ohne solche "
            "Konfidenzanalysen nicht als statistisch signifikant zu werten."
        ),
        (
            "- Die LSMC-Policy ist ein konservativer Lower Bound auf einem "
            "jährlichen Exercise-Grid mit Continue/Full Withdrawal; Partial "
            "Withdrawal und Growth-Phase-Aktionen sind nicht Teil des Action Sets. "
            "Der Lower Bound gilt für den Policyholder-Wert und ist kein "
            "konservativer Upper Bound für Versichererkosten."
        ),
        (
            "- Die Bewertung ist vor Risk Margin und brutto Rückversicherung. "
            "Mortality ist illustrativ, nicht produktiv kalibriert."
        ),
        (
            "- Fünfjähriger Government-Bond-Proxy, monatliches Rebalancing, "
            "fehlende Bond Term Premium und weitere feste Proxy-Annahmen bleiben "
            "unverändert."
        ),
    ])
    if figure_paths:
        lines.extend(["", "## Grafiken", ""])
        lines.extend(
            f"- `{Path(figure).name}`" for figure in figure_paths.values()
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    rates = sorted({
        _rate_key(rate)
        for rate in (*args.crediting_rates, args.baseline_rate)
    })
    rate_directories = {_rate_directory_name(rate) for rate in rates}
    if len(rate_directories) != len(rates):
        raise ValueError("Crediting-cap rates map to non-unique scenario paths.")
    print(
        "Portfolio valuation-exposure analysis caps: "
        + ", ".join(f"{100.0 * rate:.2f}%" for rate in rates),
        flush=True,
    )

    all_jobs: list[ScenarioJob] = []
    base_jobs: list[ScenarioJob] = []
    stress_jobs_by_id: dict[str, list[ScenarioJob]] = {
        stress_id: [] for stress_id in args.stress_scenarios
    }
    commands: list[dict[str, object]] = []
    validated_base_reuse_results: dict[
        int,
        tuple[dict[str, object], list[dict[str, object]]],
    ] = {}
    validated_stress_reuse_rows: dict[int, dict[str, object]] = {}
    sequence = 0
    for rate in rates:
        sequence += 1
        scenario_root = output / "scenarios" / _rate_directory_name(rate)
        dynamic_output = scenario_root / "dynamic_behaviour"
        lsmc_output = scenario_root / "lsmc_fitted_lower_bound"
        dynamic_command = _dynamic_command(args, rate, dynamic_output)
        dynamic_benchmark_commands = _dynamic_benchmark_commands(
            args,
            rate,
            dynamic_output,
            stress_scenario="base",
        )
        lsmc_command = _lsmc_command(args, rate, lsmc_output)
        reuse, reuse_result, reuse_validation = _validated_reuse_result(
            args,
            rate,
            dynamic_output,
            lsmc_output,
        )
        if reuse_result is not None:
            validated_base_reuse_results[sequence] = reuse_result
        job = ScenarioJob(
            sequence=sequence,
            stress_id="base",
            rate=rate,
            dynamic_output=dynamic_output,
            lsmc_output=lsmc_output,
            dynamic_command=tuple(dynamic_command),
            dynamic_benchmark_commands=dynamic_benchmark_commands,
            lsmc_command=tuple(lsmc_command),
            reuse=reuse,
        )
        base_jobs.append(job)
        all_jobs.append(job)
        commands.append({
            "job_sequence": sequence,
            "stress_scenario_id": "base",
            "crediting_cap_rate": rate,
            "execution_mode": "reused" if reuse else "executed",
            "reuse_validation": reuse_validation,
            "dynamic_command": dynamic_command,
            "dynamic_benchmark_commands": [
                list(command) for command in dynamic_benchmark_commands
            ],
            "lsmc_command": lsmc_command,
            "dynamic_orchestrator_log": str(
                dynamic_output / "orchestrator_console.log"
            ),
            "lsmc_orchestrator_log": str(
                lsmc_output / "orchestrator_console.log"
            ),
        })

    if not args.no_stress_analysis:
        for stress_id in args.stress_scenarios:
            for rate in rates:
                sequence += 1
                scenario_root = (
                    output
                    / "stress_scenarios"
                    / stress_id
                    / _rate_directory_name(rate)
                )
                dynamic_output = scenario_root / "dynamic_behaviour"
                lsmc_output = scenario_root / "lsmc_fitted_lower_bound"
                dynamic_command = _dynamic_command(
                    args,
                    rate,
                    dynamic_output,
                    stress_scenario=stress_id,
                )
                dynamic_benchmark_commands = _dynamic_benchmark_commands(
                    args,
                    rate,
                    dynamic_output,
                    stress_scenario=stress_id,
                )
                lsmc_command = _lsmc_command(
                    args,
                    rate,
                    lsmc_output,
                    stress_scenario=stress_id,
                )
                reuse, reuse_result, reuse_validation = _validated_reuse_result(
                    args,
                    rate,
                    dynamic_output,
                    lsmc_output,
                    expected_stress=stress_id,
                )
                if reuse_result is not None:
                    validated_stress_reuse_rows[sequence] = reuse_result[0]
                job = ScenarioJob(
                    sequence=sequence,
                    stress_id=stress_id,
                    rate=rate,
                    dynamic_output=dynamic_output,
                    lsmc_output=lsmc_output,
                    dynamic_command=tuple(dynamic_command),
                    dynamic_benchmark_commands=dynamic_benchmark_commands,
                    lsmc_command=tuple(lsmc_command),
                    reuse=reuse,
                )
                stress_jobs_by_id[stress_id].append(job)
                all_jobs.append(job)
                commands.append({
                    "job_sequence": sequence,
                    "stress_scenario_id": stress_id,
                    "crediting_cap_rate": rate,
                    "execution_mode": "reused" if reuse else "executed",
                    "reuse_validation": reuse_validation,
                    "dynamic_command": dynamic_command,
                    "dynamic_benchmark_commands": [
                        list(command) for command in dynamic_benchmark_commands
                    ],
                    "lsmc_command": lsmc_command,
                    "dynamic_orchestrator_log": str(
                        dynamic_output / "orchestrator_console.log"
                    ),
                    "lsmc_orchestrator_log": str(
                        lsmc_output / "orchestrator_console.log"
                    ),
                })

    worker_plan = _resolve_worker_plan(args, all_jobs)
    base_pending_count = sum(not job.reuse for job in base_jobs)
    stress_pending_count = sum(
        not job.reuse
        for stress_id in args.stress_scenarios
        for job in stress_jobs_by_id[stress_id]
    )
    parallel_execution_used = (
        worker_plan.selected_workers > 1
        and worker_plan.pending_job_count > 1
    )
    print(
        "Worker plan: "
        f"{worker_plan.selected_workers} selected "
        f"(safe auto {worker_plan.safe_auto_workers}, "
        f"{worker_plan.logical_cpu_count} logical CPUs, "
        f"available RAM {_format_gib(worker_plan.available_memory_bytes)}, "
        f"estimated peak {_format_gib(worker_plan.estimated_worker_bytes)} "
        "per worker).",
        flush=True,
    )
    if (
        worker_plan.available_memory_bytes is None
        and worker_plan.pending_job_count > 0
        and args.max_workers is None
    ):
        print(
            "WARNING: available RAM could not be detected; automatic mode "
            "uses one worker.",
            flush=True,
        )
    if (
        worker_plan.single_worker_estimate_exceeds_budget
        and worker_plan.pending_job_count > 0
        and args.max_workers is None
    ):
        print(
            "WARNING: no worker fits inside the conservative automatic RAM "
            "budget. The script retains the serial one-worker fallback; close "
            "other applications or reduce path counts if memory is tight.",
            flush=True,
        )
    if worker_plan.configured_workers_exceed_safe_auto:
        print(
            "WARNING: configured --max-workers exceeds the conservative "
            "automatic worker count and may exhaust RAM. Use --max-workers "
            "auto to enable RAM-gated scheduling.",
            flush=True,
        )

    # Base and stress scenarios are independent.  A single queue avoids the
    # former four-job base barrier leaving most of a 16-worker pool idle before
    # the larger stress grid starts.
    _run_pending_jobs(all_jobs, worker_plan, phase_label="valuation grid")
    rows: list[dict[str, object]] = []
    model_point_rows: list[dict[str, object]] = []
    for index, job in enumerate(base_jobs, start=1):
        print(
            f"[base validation {index}/{len(base_jobs)}] {job.label}",
            flush=True,
        )
        if job.sequence in validated_base_reuse_results:
            scenario_row, scenario_model_points = (
                validated_base_reuse_results[job.sequence]
            )
        else:
            scenario_row, scenario_model_points = _load_scenario_result(
                args,
                job.rate,
                job.dynamic_output,
                job.lsmc_output,
            )
        rows.append(scenario_row)
        model_point_rows.extend(scenario_model_points)

    _validate_scenario_grid(rows, label="base crediting-cap grid")
    bases = {str(row["valuation_basis"]) for row in rows}
    evaluation_fingerprints = {
        str(row["evaluation_scenario_fingerprint"]) for row in rows
    }
    training_fingerprints = {
        str(row["training_scenario_fingerprint"]) for row in rows
    }
    source_fingerprints = {
        str(row["source_metadata_fingerprint"]) for row in rows
    }
    engine_versions = {str(row["engine_version"]) for row in rows}

    stressed_scenario_rows: list[dict[str, object]] = []
    if not args.no_stress_analysis:
        market_path_stresses = {
            "interest_up",
            "interest_down",
            "equity_level_down",
            "equity_volatility_up",
        }
        for stress_id in args.stress_scenarios:
            stress_group: list[dict[str, object]] = []
            stress_group_jobs = stress_jobs_by_id[stress_id]
            for index, job in enumerate(stress_group_jobs, start=1):
                print(
                    f"[stress validation {index}/{len(stress_group_jobs)}] "
                    f"{job.label}",
                    flush=True,
                )
                if job.sequence in validated_stress_reuse_rows:
                    stress_row = validated_stress_reuse_rows[job.sequence]
                else:
                    stress_row, _stress_model_points = _load_scenario_result(
                        args,
                        job.rate,
                        job.dynamic_output,
                        job.lsmc_output,
                        expected_stress=stress_id,
                    )
                stress_group.append(stress_row)
                stressed_scenario_rows.append(stress_row)

            _validate_scenario_grid(
                stress_group,
                label=f"stress grid {stress_id}",
            )
            base_by_rate = {
                _rate_key(float(row["crediting_cap_rate"])): row
                for row in rows
            }
            for stress_row in stress_group:
                base_row = base_by_rate[
                    _rate_key(float(stress_row["crediting_cap_rate"]))
                ]
                if str(
                    stress_row["lsmc_fit_basis_fingerprint"]
                ) == str(base_row["lsmc_fit_basis_fingerprint"]):
                    raise ValueError(
                        f"LSMC fit basis was reused between base and "
                        f"{stress_id!r} for cap "
                        f"{float(stress_row['crediting_cap_rate_percent']):.2f}%."
                    )
            stress_evaluation_fingerprints = {
                str(row["evaluation_scenario_fingerprint"])
                for row in stress_group
            }
            stress_source_fingerprints = {
                str(row["source_metadata_fingerprint"])
                for row in stress_group
            }
            if stress_source_fingerprints != source_fingerprints:
                raise ValueError(
                    f"Source inputs changed between base and stress {stress_id!r}."
                )
            stress_engine_versions = {
                str(row["engine_version"]) for row in stress_group
            }
            if stress_engine_versions != engine_versions:
                raise ValueError(
                    f"Engine version changed between base and stress {stress_id!r}."
                )
            if stress_id in market_path_stresses:
                if stress_evaluation_fingerprints == evaluation_fingerprints:
                    raise ValueError(
                        f"Market stress {stress_id!r} did not change scenarios."
                    )
            elif stress_evaluation_fingerprints != evaluation_fingerprints:
                raise ValueError(
                    f"Non-market stress {stress_id!r} unexpectedly changed scenarios."
                )

    _add_baseline_deltas(rows, args.baseline_rate)
    sensitivity_rows = _build_sensitivity_rows(rows, args.baseline_rate)
    decomposition_rows = _build_decomposition_rows(rows, args.baseline_rate)
    stress_loss_rows = _build_stress_loss_rows(
        rows,
        stressed_scenario_rows,
        args.baseline_rate,
    )
    for row in decomposition_rows:
        mechanical = float(row["continue_benchmark_change_vs_baseline"])
        lsmc_interaction = float(
            row["change_in_lsmc_minus_continue_gap_vs_baseline"])
        dynamic_interaction = float(
            row["change_in_dynamic_minus_continue_gap_vs_baseline"])
        if not _close(
            float(row["lsmc_total_change_vs_baseline"]),
            mechanical + lsmc_interaction,
        ):
            raise ValueError("LSMC cap-effect decomposition does not reconcile.")
        if not _close(
            float(row["dynamic_total_change_vs_baseline"]),
            mechanical + dynamic_interaction,
        ):
            raise ValueError("Dynamic cap-effect decomposition does not reconcile.")

    risk_csv = output / "portfolio_risk_by_crediting_cap.csv"
    sensitivity_csv = output / "crediting_cap_risk_sensitivities.csv"
    decomposition_csv = output / "crediting_cap_effect_decomposition.csv"
    model_point_csv = output / "model_point_behaviour_model_gap.csv"
    stress_csv = output / "portfolio_stress_losses_by_crediting_cap.csv"
    report_path = output / "portfolio_risk_report.md"
    manifest_path = output / "analysis_manifest.json"
    _write_csv(risk_csv, rows)
    _write_csv(sensitivity_csv, sensitivity_rows)
    _write_csv(decomposition_csv, decomposition_rows)
    _write_csv(model_point_csv, model_point_rows)
    if stress_loss_rows:
        _write_csv(stress_csv, stress_loss_rows)

    figure_paths: dict[str, str] = {}
    matplotlib_version: Optional[str] = None
    if not args.no_plots:
        figure_paths, matplotlib_version = _create_plots(
            rows,
            decomposition_rows,
            stress_loss_rows,
            output / "figures",
            args.baseline_rate,
        )
    _write_report(
        report_path,
        rows,
        sensitivity_rows,
        stress_loss_rows,
        args.baseline_rate,
        figure_paths,
        worker_plan,
    )

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "gmlb_gmwb_shock_cap_and_behaviour_portfolio_risk_analysis",
        "contractual_base_crediting_cap_rate": DEFAULT_BASELINE_RATE,
        "contractual_minimum_crediting_cap_rate": (
            CONTRACTUAL_MINIMUM_CREDITING_CAP_RATE),
        "comparison_baseline_rate": args.baseline_rate,
        "scenario_crediting_cap_rates": rates,
        "valuation_basis": next(iter(bases)),
        "method": {
            "valuation_measure": "risk_neutral",
            "market_model": "heston_hull_white",
            "dynamic_behaviour": (
                "statistical_dynamic_lapse_and_withdrawal_with_deterministic_"
                "model_point_income_election"
            ),
            "lsmc_behaviour": (
                "annual_out_of_sample_lower_bound_continue_or_full_withdrawal"
            ),
            "continue_benchmark_used_for_cap_decomposition": True,
            "lsmc_policy_refitted_for_every_crediting_cap": True,
            "lsmc_policy_refitted_for_every_stress_and_crediting_cap": (
                not args.no_stress_analysis),
            "common_random_numbers_across_methods_and_caps": True,
            "scenario_pairs_executed_in_parallel": parallel_execution_used,
            "base_and_stress_jobs_share_one_execution_queue": (
                not args.no_stress_analysis
            ),
            "runner_pair_execution_order": "dynamic_then_lsmc",
            "parallel_schedule_changes_random_seeds": False,
            "one_factor_shock_and_revalue": not args.no_stress_analysis,
            "stress_losses_are_not_regulatory_capital_aggregation": True,
            "portfolio_tail_distribution_calculated": False,
        },
        "settings": {
            "n_paths": args.n_paths,
            "seed": args.seed,
            "n_train": args.n_train,
            "train_seed": args.train_seed,
            "heston_substeps": args.heston_substeps,
            "lsmc_folds": args.lsmc_folds,
            "lsmc_ridge": args.lsmc_ridge,
            "exercise_buffer_rmse_multiplier": (
                args.exercise_buffer_rmse_multiplier),
            "portfolio_contract_count": args.portfolio_contract_count,
            "profitability_materiality_bp": args.profitability_materiality_bp,
            "stress_analysis_requested": not args.no_stress_analysis,
            "stress_scenarios": (
                [] if args.no_stress_analysis else args.stress_scenarios),
            "parallel_execution": worker_plan.as_dict(),
            "pending_jobs_by_scenario_type": {
                "base": base_pending_count,
                "stress": stress_pending_count,
            },
            "pending_jobs_by_execution_phase": {
                "combined_valuation_grid": worker_plan.pending_job_count,
            },
            "effective_workers_by_execution_phase": {
                "combined_valuation_grid": min(
                    worker_plan.selected_workers,
                    worker_plan.pending_job_count,
                ),
            },
        },
        "runner_validation": {
            "dynamic_runner": str(DYNAMIC_PORTFOLIO_RUNNER),
            "lsmc_runner": str(LSMC_PORTFOLIO_RUNNER),
            "common_evaluation_scenario_fingerprint": next(
                iter(evaluation_fingerprints)),
            "common_training_scenario_fingerprint": next(
                iter(training_fingerprints)),
            "common_source_metadata_fingerprint": next(
                iter(source_fingerprints)),
            "common_engine_version": next(iter(engine_versions)),
            "training_and_evaluation_are_distinct": True,
            "aggregation_reconciliations_checked": True,
            "model_point_alignment_checked": True,
            "source_identifiers_checked": True,
            "stress_application_checked_in_runner_manifests": (
                not args.no_stress_analysis),
            "commands": commands,
        },
        "risk_indicators": {
            "guarantee_and_market_exposure": [
                "pv_guarantee_claims",
                "guarantee_value",
                "bel_nonunit",
                "bel_total",
            ],
            "fee_cost_and_profitability": [
                "future_fees",
                "crediting_margin",
                "expenses",
                "hedge_cost_proxy",
                "insurer_npv_before_risk_margin",
                "new_business_margin_before_risk_margin",
            ],
            "policyholder_behaviour": [
                "behaviour_model_npv_gap_dynamic_minus_lsmc",
                "lsmc_guarantee_claim_difference",
                "lsmc_policyholder_value_difference_vs_continue",
                "unweighted_lsmc_decision_event_exercise_rate",
            ],
            "model_point_concentration": [
                "negative_value_contract_share",
                "contract_weighted_lower_10pct_model_point_margin",
                "guarantee_claim_hhi",
                "top_5_guarantee_claim_share",
                "joint_life_guarantee_claim_share",
            ],
            "shock_and_revalue": (
                []
                if args.no_stress_analysis
                else [
                    "signed_insurer_stress_loss",
                    "adverse_insurer_stress_loss",
                    "stress_delta_nonunit_bel",
                    "stress_delta_guarantee_claims",
                    "stress_delta_future_fees",
                    "stress_delta_policyholder_benefits",
                    "lsmc_minus_dynamic_stress_loss_amplification",
                    "stress_loss_change_per_100bp_crediting_cap",
                ]
            ),
        },
        "stress_definitions": {
            stress_id: STRESS_DEFINITIONS[stress_id]
            for stress_id in (
                [] if args.no_stress_analysis else args.stress_scenarios)
        },
        "model_limitations": [
            "Expected risk-neutral present values, not a Real-World forecast.",
            "No pathwise portfolio loss distribution; no VaR, TVaR or CTE.",
            "No Monte Carlo standard errors or repeated-seed confidence intervals; common random numbers reduce but do not remove simulation and LSMC training uncertainty.",
            (
                "One-factor research stresses are not an APRA/LAGIC or Solvency-II capital aggregation."
                if stress_loss_rows
                else "The explicit shock-and-revalue grid was skipped for this run."
            ),
            "No symmetric statistical lapse/take-up/withdrawal stress because LSMC replaces the statistical Income-lapse function with its action set.",
            "No catastrophe, FX, credit-spread or correlation stress.",
            "Results are before Risk Margin and gross of reinsurance.",
            "Mortality is illustrative and not an approved production basis.",
            "LSMC is an annual-grid lower-bound Continue/Full-Withdrawal policy.",
            "The LSMC exercise diagnostic is not a portfolio-weighted surrender rate.",
            "Non-6% caps are non-contractual design sensitivities.",
            "Caps below 0.25% are technical sensitivities outside the contractual minimum.",
            "Crediting-cap variants hold all other terms fixed and are not budget-neutral repricings.",
            "Five-year government-bond sleeve, monthly rebalancing, no bond term premium and other fixed proxy assumptions remain in force.",
        ],
        "outputs": {
            "portfolio_risk_by_crediting_cap_csv": str(risk_csv),
            "crediting_cap_risk_sensitivities_csv": str(sensitivity_csv),
            "crediting_cap_effect_decomposition_csv": str(decomposition_csv),
            "model_point_behaviour_model_gap_csv": str(model_point_csv),
            "portfolio_stress_losses_by_crediting_cap_csv": (
                str(stress_csv) if stress_loss_rows else None),
            "report": str(report_path),
            "figures": figure_paths,
            "scenario_root": str(output / "scenarios"),
            "stress_scenario_root": (
                str(output / "stress_scenarios")
                if stress_loss_rows else None),
        },
        "reporting": {
            "plots_requested": not args.no_plots,
            "matplotlib_version": matplotlib_version,
        },
        "results": rows,
        "stress_results": stress_loss_rows,
    }
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(
            manifest,
            handle,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            default=str,
        )
        handle.write("\n")

    print(f"Risk comparison CSV: {risk_csv}")
    print(f"Sensitivity CSV: {sensitivity_csv}")
    print(f"Model-point comparison CSV: {model_point_csv}")
    if stress_loss_rows:
        print(f"Stress-loss CSV: {stress_csv}")
    print(f"Report: {report_path}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
