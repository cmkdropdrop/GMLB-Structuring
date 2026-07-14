"""Evaluate lifetime-income valuation exposures across crediting-cap scenarios.

For every requested scenario Maximum Return, this orchestrator calls both
``run_portfolio_valuation.py`` (statistical/dynamic policyholder behaviour) and
``run_portfolio_valuation_lsmc.py`` (annual fitted Income Election followed by
annual Continue/Full-Withdrawal decisions on one common Q sample).
Only the complete policies are retained for the risk comparison: Dynamic
Election plus Dynamic post-Election Behaviour, and the directly fitted LSMC
V11 policy.  There is no separate validation/evaluation sample, deployment
gate or fixed-policy fallback. Counterfactual
V00/V01/V10 Dynamic runs and Behaviour-effect decompositions are deliberately
omitted.

The default compares 4%, 6%, 12% and 15% Caps on the base market scenario with
the complete Dynamic and directly fitted LSMC policies for the one-point proxy, but
without counterfactual Behaviour arms or
shock-and-revalue stresses.  Aggregate risk-analysis plots are produced by
default; the more numerous child-scenario plots remain opt-in.  This makes
Lapse/Behaviour the default risk scope.  Interest up,
interest down and Longevity remain the preselected one-factor stress set when
stress analysis is explicitly enabled.  Other research stresses remain
available only when explicitly selected.  The portfolio runners deliberately
retain expected present values and model-point scalars, not pathwise loss
distributions.  Consequently this script does not label model-point dispersion
as VaR/CTE and does not claim to calculate economic capital, Risk Margin or an
APRA/LAGIC stress aggregation.

Every invocation writes all aggregate results and its Dynamic/LSMC child-run
artifacts below a new UTC timestamp subdirectory of the configured output root.
Existing run directories are never overwritten.

Risk-analysis children are operative Q-valuations and therefore always require
an exact market cache.  With the default ``mc_conditional`` hedge method they
also always require the exact hedge-price cache.  Before valuation starts, this
orchestrator invokes the dedicated precompute runner for every exact required
sample, market variant and Cap.  That runner validates existing entries and is
the only component allowed to create missing cache data.

Independent cap/stress scenario pairs are scheduled together in one parallel
queue.  The reduced default uses one worker with one BLAS/OpenMP thread per
child.  Larger explicitly requested grids can opt into a higher fixed worker
count or the deliberately conservative automatic mode, which gates CPU
concurrency by a path/horizon-based LSMC memory estimate.  Dynamic and LSMC
remain serial within each pair to bound peak memory.
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
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence

if __package__:
    from ._mc_analysis_inputs import (
        load_mc_analysis_inputs,
        require_mc_samples,
    )
    from ._run_layout import behaviour_benchmark_directories
    from ._run_logging import format_run_log_line, log_to_console
else:
    from _mc_analysis_inputs import (
        load_mc_analysis_inputs,
        require_mc_samples,
    )
    from _run_layout import behaviour_benchmark_directories
    from _run_logging import format_run_log_line, log_to_console


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
ENGINE_ROOT = SCRIPT_DIRECTORY.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from policy_engine.repository_paths import (  # noqa: E402
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH as DEFAULT_ZERO_CURVE_PATH,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DEFAULT_FAST_POLICYHOLDER_MODEL_POINTS_PATH as DEFAULT_MODEL_POINTS_PATH,
    DEFAULT_MODEL_PARAMETERS_PATH,
    MARKET_DATA_DIRECTORY as DEFAULT_MARKET_DATA_DIRECTORY,
    PROJECT_ROOT as REPOSITORY_ROOT,
    Q_HEDGE_PRICE_CACHE_ROOT as DEFAULT_HEDGE_CACHE_ROOT,
    Q_MARKET_PATH_CACHE_ROOT as DEFAULT_MARKET_CACHE_ROOT,
    run_output_directory,
)
from policy_engine.model_points import load_policyholder_model_points  # noqa: E402
from policy_engine.pricing import ValuationSettings, resolve_horizon  # noqa: E402
from policy_engine.projection import ProjectionConfig  # noqa: E402

DYNAMIC_PORTFOLIO_RUNNER = SCRIPT_DIRECTORY / "run_portfolio_valuation.py"
LSMC_PORTFOLIO_RUNNER = SCRIPT_DIRECTORY / "run_portfolio_valuation_lsmc.py"
Q_CACHE_PRECOMPUTE_RUNNER = (
    SCRIPT_DIRECTORY / "precompute_q_market_and_hedge_cache.py"
)
DEFAULT_OUTPUT_DIRECTORY = run_output_directory("portfolio_risk_analysis")
RUN_DIRECTORY_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%S.%fZ"
DEFAULT_CREDITING_CAP_RATES = (0.04, 0.06, 0.12, 0.15)
DEFAULT_BASELINE_RATE = 0.06
CONTRACTUAL_MINIMUM_CREDITING_CAP_RATE = 0.0025
MINIMUM_LSMC_TRAINING_PATHS = 60
AUTO_WORKER_MEMORY_FRACTION = 0.65
DEFAULT_MAX_WORKERS = 1
AUTO_WORKER_MAXIMUM = 16
AUTO_WORKER_FIXED_BYTES = 1_342_177_280  # 1.25 GiB process/projection overhead
# Includes the added Election, phase-exposure and cause-specific Behaviour
# diagnostics retained by the enhanced training/evaluation projections.
AUTO_WORKER_BYTES_PER_PATH_MONTH = 768
AUTO_WORKER_SAFETY_MULTIPLIER = 1.25
AUTO_WORKER_MINIMUM_MEMORY_RESERVE_BYTES = 2 * 1024 ** 3
DEFAULT_HORIZON_MONTHS_FALLBACK = 70 * 12
MARKET_CACHE_STRESS_IDS = frozenset({
    "interest_up",
    "interest_down",
    "equity_level_down",
    "equity_volatility_up",
})
CHILD_HEARTBEAT_SECONDS = 30.0
WINDOWS_LEGACY_MAX_PATH_CHARS = 259
RECONCILIATION_FILE_NAME = "portfolio_aggregation_reconciliation.csv"
LONGEST_SCENARIO_PLOT_RELATIVE_PATH = (
    Path("figures") / "03_model_point_profitability_heatmaps.png"
)

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
    "pv_money_market_income_aud",
    "pv_hedge_gain_aud",
    "pv_hedge_option_fair_value_costs_aud",
    "pv_hedge_option_markup_costs_aud",
    "pv_hedge_management_fee_costs_aud",
    "pv_hedge_execution_costs_aud",
    "pv_hedge_cost_reconciliation_gap_aud",
    "pv_crediting_margin_reconciliation_gap_aud",
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

CSM_SOURCE_METRICS = (
    "pv_future_fees_aud",
    "pv_crediting_margin_aud",
    "pv_mva_retained_aud",
    "pv_aps_retained_aud",
    "pv_guarantee_claims_aud",
    "pv_expenses_aud",
    "pv_hedge_costs_aud",
    "insurer_net_present_value_before_risk_margin_aud",
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

MODEL_POINT_COMPARISON_METRICS = (
    "premium_aud",
    "pv_policyholder_benefits_aud",
    "pv_future_fees_aud",
    "pv_guarantee_claims_aud",
    "pv_expenses_aud",
    "pv_hedge_costs_aud",
    "pv_crediting_margin_aud",
    "pv_money_market_income_aud",
    "pv_hedge_gain_aud",
    "pv_hedge_option_fair_value_costs_aud",
    "pv_hedge_option_markup_costs_aud",
    "pv_hedge_management_fee_costs_aud",
    "pv_hedge_execution_costs_aud",
    "pv_mva_retained_aud",
    "pv_aps_retained_aud",
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
# Lapse risk is present in every base Cap run through the V11 Dynamic/LSMC
# Behaviour comparison.  It is deliberately not represented
# as a statistical lapse-rate shock because the LSMC method replaces those
# rates with its joint action policy.  The reduced default runs no explicit
# shock grid, so its effective risk scope is Lapse/Behaviour only.  If stress
# analysis is enabled, the preselected set adds the two interest-rate
# directions and Longevity.
DEFAULT_RISK_SCOPE = ("lapse",)
DEFAULT_STRESS_SCENARIOS = ("interest_up", "interest_down", "longevity")
DEFAULT_BEHAVIOUR_MODELS = ("dynamic_functions", "lsmc")


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
    mc_inputs = load_mc_analysis_inputs()
    training_input = require_mc_samples(mc_inputs, "lsmc_training", 1)[0]
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
    # Retain the old evaluation arguments as parseable compatibility aliases.
    # They are normalised to the sole training/valuation sample below and are
    # never used to create an additional cache or OOS rollout.
    parser.add_argument("--n-paths", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--take-up-seed", type=int, default=None,
                        help=argparse.SUPPRESS)
    parser.add_argument("--mortality-seed", type=int, default=None,
                        help=argparse.SUPPRESS)
    parser.add_argument(
        "--n-train", type=int, default=training_input.n_paths,
        help="paths in the sole LSMC fit/valuation Q sample",
    )
    parser.add_argument(
        "--train-seed", type=int, default=training_input.market_seed
    )
    parser.add_argument(
        "--train-take-up-seed",
        type=int,
        default=training_input.take_up_seed,
    )
    parser.add_argument(
        "--train-mortality-seed",
        type=int,
        default=training_input.mortality_seed,
    )
    parser.add_argument(
        "--train-seed-2", type=int, default=None, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--train-take-up-seed-2",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--train-mortality-seed-2",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--train-seed-3", type=int, default=None, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--train-take-up-seed-3",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--train-mortality-seed-3",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--training-seed-count",
        type=int,
        choices=(1,),
        default=1,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--n-validation", type=int, default=None, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--validation-seed", type=int, default=None, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--validation-take-up-seed",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--validation-mortality-seed",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument(
        "--market-cache-root", type=Path, default=DEFAULT_MARKET_CACHE_ROOT
    )
    parser.add_argument(
        "--hedge-cache-root", type=Path, default=DEFAULT_HEDGE_CACHE_ROOT
    )
    parser.add_argument(
        "--hedge-pricing-method",
        choices=("mc_conditional", "moment_matched_bs"),
        default="mc_conditional",
    )
    parser.add_argument(
        "--require-market-cache",
        action="store_true",
        help=(
            "compatibility flag; operative risk runs always require the exact "
            "Q-market cache"
        ),
    )
    parser.add_argument(
        "--require-hedge-cache",
        action="store_true",
        help=(
            "require an exact hedge-price cache; implied automatically by "
            "mc_conditional"
        ),
    )
    parser.add_argument(
        "--hedge-cap-leg-mode",
        choices=("sold", "not_sold"),
        default="sold",
        help=(
            "sold is the standard capped hedge; not_sold retains the uncapped "
            "option payoff above the customer crediting cap"
        ),
    )
    parser.add_argument("--lsmc-folds", type=int, default=5)
    parser.add_argument(
        "--lsmc-income-action-set",
        choices=("continue_full",),
        default="continue_full",
        help=(
            "fixed ordered annual LSMC action set: CONTINUE_FOR_ONE_YEAR or "
            "FULL_WITHDRAWAL_NOW"
        ),
    )
    parser.add_argument(
        "--lsmc-ridge",
        type=float,
        choices=(0.0, 1.0e-8, 1.0e-6, 1.0e-4, 1.0e-2),
        default=1.0e-6,
    )
    parser.add_argument(
        "--exercise-buffer-rmse-multiplier",
        type=float,
        default=0.0,
    )
    parser.add_argument("--portfolio-contract-count", type=float, default=None)
    parser.add_argument("--profitability-materiality-bp", type=float, default=1.0)
    parser.add_argument(
        "--model-points",
        type=Path,
        default=DEFAULT_MODEL_POINTS_PATH,
        help=(
            "policyholder model-point CSV; customer-LSMC risk runs default "
            "to the one-point fast proxy"
        ),
    )
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
            "run for every cap and both policyholder-behaviour methods when "
            "--stress-analysis is enabled. The preselected set is interest "
            "up/down and Longevity; Lapse risk is always covered by the "
            "full-policy Dynamic-V11 versus deployed-LSMC comparison"
        ),
    )
    stress_toggle = parser.add_mutually_exclusive_group()
    stress_toggle.add_argument(
        "--stress-analysis",
        dest="no_stress_analysis",
        action="store_false",
        help=(
            "enable the selected shock-and-revalue grid in addition to the "
            "base Cap and Lapse-Behaviour analysis"
        ),
    )
    stress_toggle.add_argument(
        "--no-stress-analysis",
        dest="no_stress_analysis",
        action="store_true",
        help=(
            "skip the selected shock-and-revalue grid; the Cap and Lapse-"
            "Behaviour exposure analysis is still produced"
        ),
    )
    parser.set_defaults(no_stress_analysis=True)
    parser.add_argument(
        "--max-workers",
        type=_parse_max_workers,
        default=DEFAULT_MAX_WORKERS,
        metavar="AUTO_OR_N",
        help=(
            "parallel independent cap/stress scenario pairs in one combined "
            "queue. The reduced default is one single-threaded valuation "
            "child; 'auto' instead uses a conservative CPU/RAM estimate"
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
    plot_toggle = parser.add_mutually_exclusive_group()
    plot_toggle.add_argument(
        "--plots",
        dest="no_plots",
        action="store_false",
        help="create the aggregate risk-analysis figures (default)",
    )
    plot_toggle.add_argument(
        "--no-plots",
        dest="no_plots",
        action="store_true",
        help="write CSV/report/manifest outputs without analysis figures",
    )
    parser.set_defaults(no_plots=False)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help=(
            "base output directory; every invocation creates a new UTC "
            "timestamp subdirectory"
        ),
    )
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    args = parser.parse_args(argv)
    args.stress_scenarios = list(dict.fromkeys(args.stress_scenarios))
    # One common sample drives the Swing-policy fit, its direct expected-PV
    # rollout and the Dynamic CRN comparator.  Normalising legacy attributes
    # here keeps helper APIs stable without retaining any OOS semantics.
    args.n_paths = args.n_train
    args.seed = args.train_seed
    args.take_up_seed = args.train_take_up_seed
    args.mortality_seed = args.train_mortality_seed
    args.n_validation = args.n_train
    args.validation_seed = args.train_seed
    args.validation_take_up_seed = args.train_take_up_seed
    args.validation_mortality_seed = args.train_mortality_seed
    args.train_seed_2 = args.train_seed
    args.train_take_up_seed_2 = args.train_take_up_seed
    args.train_mortality_seed_2 = args.train_mortality_seed
    args.train_seed_3 = args.train_seed
    args.train_take_up_seed_3 = args.train_take_up_seed
    args.train_mortality_seed_3 = args.train_mortality_seed
    # This orchestrator is an operative market-consistent valuation reader.
    # It must never let a child silently simulate replacement Q paths.  The
    # conditional-MC method likewise has no proxy price fallback.
    args.require_market_cache = True
    args.require_hedge_cache = args.hedge_pricing_method == "mc_conditional"
    if (
        args.hedge_pricing_method == "mc_conditional"
        and args.hedge_cap_leg_mode == "not_sold"
    ):
        parser.error(
            "--hedge-pricing-method=mc_conditional cannot be combined with "
            "--hedge-cap-leg-mode=not_sold because the conditional hedge cache "
            "contains sold-call-spread prices only; choose moment_matched_bs "
            "explicitly for the uncapped retained-payoff proxy"
        )

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
    seed_names = ("train_seed", "train_take_up_seed", "train_mortality_seed")
    if any(getattr(args, name) < 0 for name in seed_names):
        parser.error("seeds must be non-negative")
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


def _model_point_ids(path: Path) -> tuple[str, ...]:
    """Read model-point identifiers for an explicit run-scope log entry."""
    resolved = path.expanduser().resolve()
    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        identifiers = tuple(
            str(row.get("model_point_id", "")).strip()
            for row in csv.DictReader(handle)
        )
    if not identifiers or any(not identifier for identifier in identifiers):
        raise ValueError(
            f"Model-point input must contain non-empty model_point_id values: "
            f"{resolved}"
        )
    return identifiers


def _create_timestamped_run_directory(
    output_root: Path,
    created_at: Optional[datetime] = None,
) -> tuple[Path, Path, str, str]:
    """Create one immutable UTC-timestamped directory for this invocation."""
    created = datetime.now(timezone.utc) if created_at is None else created_at
    if created.tzinfo is None:
        raise ValueError("Run creation timestamp must be timezone-aware.")
    created_utc = created.astimezone(timezone.utc)
    run_id = created_utc.strftime(RUN_DIRECTORY_TIMESTAMP_FORMAT)
    root = output_root.expanduser().resolve()
    output = root / run_id
    if output.parent != root:
        raise RuntimeError("Unsafe timestamped risk-analysis output path.")
    output.mkdir(parents=True, exist_ok=False)
    return root, output, run_id, created_utc.isoformat()


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
    _optional_argument(command, "--market-cache-root", args.market_cache_root)
    _optional_argument(command, "--hedge-cache-root", args.hedge_cache_root)
    command.extend(("--hedge-pricing-method", args.hedge_pricing_method))
    if args.require_market_cache:
        command.append("--require-market-cache")
    if args.require_hedge_cache:
        command.append("--require-hedge-cache")


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
        "--n-paths", str(args.n_train),
        "--seed", str(args.train_seed),
        "--take-up-seed", str(args.train_take_up_seed),
        "--mortality-seed", str(args.train_mortality_seed),
        "--heston-substeps", str(args.heston_substeps),
        "--hedge-cap-leg-mode", args.hedge_cap_leg_mode,
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
    return behaviour_benchmark_directories(dynamic_output.parent)


def _lsmc_benchmark_directories(lsmc_output: Path) -> dict[str, Path]:
    return behaviour_benchmark_directories(lsmc_output)


def _dynamic_benchmark_commands(
    args: argparse.Namespace,
    rate: float,
    dynamic_output: Path,
    *,
    stress_scenario: str,
) -> tuple[tuple[str, ...], ...]:
    # The risk runner intentionally retains only the complete Dynamic V11 arm.
    # V00/V01/V10 remain research counterfactuals in lower-level runners, not
    # part of this default portfolio comparison.
    del args, rate, dynamic_output, stress_scenario
    return ()


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
        "--n-train", str(args.n_train),
        "--train-seed", str(args.train_seed),
        "--train-take-up-seed", str(args.train_take_up_seed),
        "--train-mortality-seed", str(args.train_mortality_seed),
        "--heston-substeps", str(args.heston_substeps),
        "--hedge-cap-leg-mode", args.hedge_cap_leg_mode,
        "--lsmc-folds", str(args.lsmc_folds),
        "--lsmc-income-action-set", args.lsmc_income_action_set,
        "--lsmc-ridge", str(args.lsmc_ridge),
        "--exercise-buffer-rmse-multiplier",
        str(args.exercise_buffer_rmse_multiplier),
        "--profitability-materiality-bp",
        str(args.profitability_materiality_bp),
        # The full Dynamic-functions valuation is a separate required command
        # in the same ScenarioJob.  Suppress only the duplicate Dynamic run
        # embedded in the standalone LSMC runner.
        "--no-dynamic-benchmark",
        # The risk analysis reports only direct V11.  V10 remains a purely
        # descriptive same-sample comparator and can never replace V11.
        "--no-factorial-benchmarks",
        "--log-level", args.log_level,
        "--output", str(output),
    ]
    if not args.scenario_plots:
        command.append("--no-plots")
    _append_shared_inputs(command, args)
    return command


def _cache_market_stress_id(stress_id: str) -> str:
    """Map non-market stresses to their unchanged base-market cache."""
    return stress_id if stress_id in MARKET_CACHE_STRESS_IDS else "base"


def _required_cache_samples(
    args: argparse.Namespace,
) -> tuple[tuple[str, int, int], ...]:
    """Return the sole exact Q sample consumed by Dynamic and LSMC."""
    return ((
        "training_and_valuation",
        int(args.n_train),
        int(args.train_seed),
    ),)


def _cache_precompute_command(
    args: argparse.Namespace,
    *,
    horizon_years: float,
    market_stress: str,
    cap_rate: float,
    n_paths: int,
    seed: int,
) -> list[str]:
    """Build one exact invocation of the sole authorised cache writer."""
    command = [
        str(args.python_executable),
        str(Q_CACHE_PRECOMPUTE_RUNNER),
        "--market-cache-root",
        str(args.market_cache_root.expanduser().resolve()),
        "--hedge-cache-root",
        str(args.hedge_cache_root.expanduser().resolve()),
        "--horizon-years", f"{horizon_years:.12g}",
        "--n-paths", str(n_paths),
        "--seed", str(seed),
        "--heston-substeps", str(args.heston_substeps),
        "--market-stress", market_stress,
    ]
    _optional_argument(command, "--zero-curve", args.zero_curve)
    _optional_argument(command, "--model-parameters", args.model_parameters)
    if args.require_hedge_cache:
        command.extend(("--cap-grid", f"{cap_rate:.12g}"))
    else:
        command.append("--market-only")
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

    @property
    def label(self) -> str:
        return f"{self.stress_id} / cap {100.0 * self.rate:.2f}%"


@dataclass(frozen=True)
class CachePrecomputeJob:
    """One exact cache validation/creation request run before valuation."""

    sequence: int
    market_stress: str
    sample_role: str
    n_paths: int
    seed: int
    cap_rate: float
    output: Path
    command: tuple[str, ...]

    @property
    def label(self) -> str:
        cap = (
            f" / cap {100.0 * self.cap_rate:.2f}%"
            if "--market-only" not in self.command
            else ""
        )
        return (
            f"{self.market_stress} / {self.sample_role} "
            f"({self.n_paths} paths, seed {self.seed}){cap}"
        )


def _cache_precompute_jobs(
    args: argparse.Namespace,
    scenario_jobs: Sequence[ScenarioJob],
    *,
    horizon_years: float,
    output: Path,
) -> tuple[CachePrecomputeJob, ...]:
    """Deduplicate exact market/sample/Cap inputs for the scenario grid."""
    cells: list[tuple[str, float]] = []
    seen_cells: set[tuple[str, Optional[float]]] = set()
    for scenario_job in sorted(scenario_jobs, key=lambda job: job.sequence):
        market_stress = _cache_market_stress_id(scenario_job.stress_id)
        cap_rate = _rate_key(scenario_job.rate)
        deduplication_key = (
            market_stress,
            cap_rate if args.require_hedge_cache else None,
        )
        if deduplication_key not in seen_cells:
            seen_cells.add(deduplication_key)
            cells.append((market_stress, cap_rate))

    jobs: list[CachePrecomputeJob] = []
    for market_stress, cap_rate in cells:
        for sample_role, n_paths, seed in _required_cache_samples(args):
            sequence = len(jobs) + 1
            cache_scope = (
                _rate_directory_name(cap_rate)
                if args.require_hedge_cache
                else "market_only"
            )
            job_output = (
                output
                / "cache_precompute"
                / (
                    f"{sequence:04d}_{market_stress}_{sample_role}_"
                    f"{cache_scope}"
                )
            )
            command = _cache_precompute_command(
                args,
                horizon_years=horizon_years,
                market_stress=market_stress,
                cap_rate=cap_rate,
                n_paths=n_paths,
                seed=seed,
            )
            jobs.append(CachePrecomputeJob(
                sequence=sequence,
                market_stress=market_stress,
                sample_role=sample_role,
                n_paths=n_paths,
                seed=seed,
                cap_rate=cap_rate,
                output=job_output,
                command=tuple(command),
            ))
    return tuple(jobs)


def _expected_job_artifact_paths(
    job: ScenarioJob,
    *,
    include_plots: bool,
) -> tuple[Path, ...]:
    """Return the longest relevant files expected below one job layout."""
    dynamic_benchmark_directories = tuple(
        _dynamic_benchmark_directories(job.dynamic_output).values()
        if job.dynamic_benchmark_commands
        else ()
    )
    lsmc_benchmark_directories = (
        _lsmc_benchmark_directories(job.lsmc_output)[
            "variable_election_continue"
        ],
    )
    reconciliation_directories = (
        job.dynamic_output,
        *dynamic_benchmark_directories,
        job.lsmc_output,
        *lsmc_benchmark_directories,
    )
    paths = [
        directory / RECONCILIATION_FILE_NAME
        for directory in reconciliation_directories
    ]
    if include_plots:
        paths.extend(
            directory / LONGEST_SCENARIO_PLOT_RELATIVE_PATH
            for directory in (
                job.dynamic_output,
                *dynamic_benchmark_directories,
                job.lsmc_output,
            )
        )
    return tuple(paths)


def _validate_output_path_lengths(
    jobs: Sequence[ScenarioJob],
    *,
    include_plots: bool,
    max_path_chars: int,
) -> None:
    """Fail before valuation work if an expected artifact path is too long."""
    paths = tuple(
        path
        for job in jobs
        for path in _expected_job_artifact_paths(
            job,
            include_plots=include_plots,
        )
    )
    if not paths:
        return
    longest = max(paths, key=lambda path: len(str(path)))
    longest_length = len(str(longest))
    if longest_length > max_path_chars:
        raise ValueError(
            "Risk-run output path exceeds the supported Windows MAX_PATH "
            f"limit ({longest_length} > {max_path_chars} characters): "
            f"{longest}. Choose a shorter --output path, for example C:\\risk."
        )


def _validate_windows_output_path_lengths(
    jobs: Sequence[ScenarioJob],
    *,
    include_plots: bool,
) -> None:
    if os.name == "nt":
        _validate_output_path_lengths(
            jobs,
            include_plots=include_plots,
            max_path_chars=WINDOWS_LEGACY_MAX_PATH_CHARS,
        )


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
    """Resolve the portfolio horizon through the engine's canonical resolver."""
    path = model_points_path.expanduser().resolve()
    try:
        model_points = load_policyholder_model_points(path)
        horizon_basis = ValuationSettings(
            horizon_years=None,
            projection=ProjectionConfig(record_paths=False, heston_cos=False),
        )
        horizon_years = max(
            resolve_horizon(horizon_basis, point.policy)
            for point in model_points.model_points
        )
        horizon_months = int(round(12.0 * horizon_years))
        if horizon_months <= 0 or not math.isclose(
            horizon_months / 12.0,
            horizon_years,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError(
                "Canonical portfolio horizon is not a positive monthly duration."
            )
    except (OSError, TypeError, ValueError):
        return (
            DEFAULT_HORIZON_MONTHS_FALLBACK,
            f"fallback_after_unreadable_model_points:{path}",
        )
    return horizon_months, f"policy_engine.resolve_horizon:{path}"


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
    pending_count = len(jobs)
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
        configured_workers_exceed_safe_auto=exceeds_auto,
        single_worker_estimate_exceeds_budget=estimate_exceeds_budget,
    )


def _format_gib(value: Optional[int]) -> str:
    if value is None:
        return "unknown"
    return f"{value / 1024 ** 3:.2f} GiB"


def _format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(float(seconds))))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {seconds_part:02d}s"
    if minutes:
        return f"{minutes:d}m {seconds_part:02d}s"
    return f"{seconds_part:d}s"


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
    """Execute one child, persist its output and emit periodic heartbeats."""
    output.mkdir(parents=True, exist_ok=True)
    completion_manifest = output / "run_manifest.json"
    try:
        completion_manifest.unlink()
    except FileNotFoundError:
        pass
    log_path = output / "orchestrator_console.log"
    environment = _child_environment(blas_threads, output)
    runner_name = (
        Path(str(command[1])).stem
        if len(command) > 1
        else Path(str(command[0])).stem
    )
    started = time.perf_counter()
    process: Optional[subprocess.Popen[str]] = None
    with log_path.open("w", encoding="utf-8", newline="") as log_handle:
        log_handle.write(format_run_log_line(
            "Command: " + subprocess.list2cmdline(list(command))
        ))
        log_handle.write("\n")
        log_handle.write(format_run_log_line(
            f"BLAS/OpenMP threads: {blas_threads}"
        ))
        log_handle.write("\n\n")
        log_handle.flush()
        try:
            process = subprocess.Popen(
                list(command),
                cwd=str(ENGINE_ROOT),
                env=environment,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            while True:
                try:
                    return_code = process.wait(
                        timeout=CHILD_HEARTBEAT_SECONDS
                    )
                    break
                except subprocess.TimeoutExpired:
                    log_to_console(
                        f"ACTIVE | {runner_name} | elapsed "
                        f"{_format_duration(time.perf_counter() - started)} | "
                        f"Details: {log_path}"
                    )
        except OSError as exc:
            raise RuntimeError(
                f"Could not start valuation command; see {log_path}"
            ) from exc
        except BaseException:
            if process is not None and process.poll() is None:
                process.terminate()
            raise
    if return_code != 0:
        raise RuntimeError(
            f"{runner_name} failed with exit code {return_code}; "
            f"see {log_path}"
        )


def _run_cache_precompute_jobs(
    jobs: Sequence[CachePrecomputeJob],
    *,
    blas_threads: int,
) -> None:
    """Validate or create all exact cache entries before any valuation child."""
    if not jobs:
        log_to_console(
            "CACHE PREPARATION | No new valuation runs; no cache validation "
            "required."
        )
        return
    phase_started = time.perf_counter()
    log_to_console(
        f"CACHE PREPARATION START | {len(jobs)} exact precompute calls | "
        "validating existing entries and creating missing entries."
    )
    for index, job in enumerate(jobs, start=1):
        job_started = time.perf_counter()
        log_to_console(
            f"CACHE {index}/{len(jobs)} START | {job.label}"
        )
        _run_logged_command(
            job.command,
            job.output,
            blas_threads=blas_threads,
        )
        log_to_console(
            f"CACHE {index}/{len(jobs)} COMPLETE | {job.label} | elapsed "
            f"{_format_duration(time.perf_counter() - job_started)}"
        )
    log_to_console(
        f"CACHE PREPARATION COMPLETE | {len(jobs)} calls | elapsed "
        f"{_format_duration(time.perf_counter() - phase_started)}"
    )


def _execute_scenario_job(job: ScenarioJob, blas_threads: int) -> None:
    """Run Dynamic V11 and the validated LSMC deployment in one worker."""
    job_started = time.perf_counter()
    dynamic_started = time.perf_counter()
    log_to_console(
        f"START 1/2 | {job.label} | Dynamic V11 | "
        f"Output: {job.dynamic_output}"
    )
    _run_logged_command(
        job.dynamic_command,
        job.dynamic_output,
        blas_threads=blas_threads,
    )
    log_to_console(
        f"COMPLETE 1/2 | {job.label} | Dynamic V11 | elapsed "
        f"{_format_duration(time.perf_counter() - dynamic_started)}"
    )
    if job.dynamic_benchmark_commands:
        raise ValueError("V11-only jobs must not contain Dynamic benchmarks.")
    lsmc_started = time.perf_counter()
    log_to_console(
        f"START 2/2 | {job.label} | LSMC V11 candidate: training, validation, "
        f"evaluation | Output: {job.lsmc_output}"
    )
    _run_logged_command(
        job.lsmc_command,
        job.lsmc_output,
        blas_threads=blas_threads,
    )
    log_to_console(
        f"COMPLETE 2/2 | {job.label} | LSMC deployment | elapsed "
        f"{_format_duration(time.perf_counter() - lsmc_started)}"
    )
    log_to_console(
        f"SCENARIO COMPLETE | {job.label} | total elapsed "
        f"{_format_duration(time.perf_counter() - job_started)}"
    )


def _run_pending_jobs(
    jobs: Sequence[ScenarioJob],
    worker_plan: WorkerPlan,
    *,
    phase_label: str,
) -> None:
    pending = sorted(jobs, key=lambda job: job.sequence)
    if not pending:
        log_to_console(f"{phase_label}: no scenario pair to run.")
        return
    effective_workers = min(worker_plan.selected_workers, len(pending))
    log_to_console(
        f"{phase_label}: {len(pending)} scenario pairs to run, "
        f"{effective_workers} worker(s)."
    )
    if effective_workers == 1:
        failures: list[str] = []
        phase_started = time.perf_counter()
        for index, job in enumerate(pending, start=1):
            log_to_console(
                f"SCENARIO {index}/{len(pending)} START | {job.label}"
            )
            try:
                _execute_scenario_job(job, worker_plan.blas_threads_per_child)
            except Exception as exc:
                failures.append(f"{job.label}: {exc}")
                log_to_console(
                    f"[{phase_label} {index}/{len(pending)}] FAILED {job.label}",
                    level="ERROR",
                )
            else:
                log_to_console(
                    f"PROGRESS {index}/{len(pending)} | {job.label} completed "
                    "successfully"
                )
        if failures:
            raise RuntimeError(
                "One or more scenario cells failed; no aggregate report was "
                "created:\n" + "\n".join(failures)
            )
        log_to_console(
            f"VALUATION GRID COMPLETE | {len(pending)} scenarios | elapsed "
            f"{_format_duration(time.perf_counter() - phase_started)}"
        )
        return

    phase_started = time.perf_counter()
    executor = ThreadPoolExecutor(
        max_workers=effective_workers,
        thread_name_prefix="portfolio-scenario",
    )
    futures: dict[Future[None], ScenarioJob] = {}
    completed_count = 0
    failures: list[str] = []
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
            try:
                future.result()
            except Exception as exc:
                failures.append(f"{job.label}: {exc}")
                log_to_console(
                    f"[{phase_label}] FAILED {job.label}", level="ERROR"
                )
            else:
                completed_count += 1
                log_to_console(
                    f"[{phase_label} {completed_count}/{len(pending)}] "
                    f"Completed {job.label}"
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=False)
    if failures:
        raise RuntimeError(
            "One or more scenario cells failed; no aggregate report was "
            "created:\n" + "\n".join(failures)
        )
    log_to_console(
        f"VALUATION GRID COMPLETE | {len(pending)} scenarios | elapsed "
        f"{_format_duration(time.perf_counter() - phase_started)}"
    )


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
        canonical: _first_float(
            summary,
            (
                *aliases,
                *(f"normalised_average_{alias}" for alias in aliases),
            ),
            label=f"{label} {canonical}",
        )
        for canonical, aliases in BEHAVIOUR_SCALAR_METRICS.items()
    }
    for key, value in summary.items():
        key_text = str(key)
        canonical_key = (
            key_text.removeprefix("normalised_average_")
            if key_text.startswith("normalised_average_")
            else key_text
        )
        if any(
            pattern.match(canonical_key)
            for pattern in BEHAVIOUR_POLICY_YEAR_PATTERNS
        ):
            parsed = _as_float(value, f"{label} {key_text}")
            if canonical_key in metrics:
                _require_close(
                    float(metrics[canonical_key]),
                    parsed,
                    f"{label} direct/prefixed {canonical_key}",
                )
            metrics[canonical_key] = parsed
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


def _csm_components(
    metrics: Mapping[str, object],
    *,
    label: str,
) -> dict[str, float]:
    """Return the canonical simplified CSM and reconcile it to legacy NPV."""
    fee_income = _as_float(
        metrics.get("pv_future_fees_aud"), f"{label} pv_future_fees_aud"
    )
    other_income = sum(
        _as_float(metrics.get(field), f"{label} {field}")
        for field in (
            "pv_crediting_margin_aud",
            "pv_mva_retained_aud",
            "pv_aps_retained_aud",
        )
    )
    claims = _as_float(
        metrics.get("pv_guarantee_claims_aud"),
        f"{label} pv_guarantee_claims_aud",
    )
    costs = sum(
        _as_float(metrics.get(field), f"{label} {field}")
        for field in ("pv_expenses_aud", "pv_hedge_costs_aud")
    )
    csm = fee_income + other_income - claims - costs
    legacy_npv = _as_float(
        metrics.get("insurer_net_present_value_before_risk_margin_aud"),
        f"{label} insurer_net_present_value_before_risk_margin_aud",
    )
    reconciliation_gap = csm - legacy_npv
    _require_close(csm, legacy_npv, f"{label} CSM/legacy insurer-NPV reconciliation")
    return {
        "csm_aud": csm,
        "csm_pv_fee_income_aud": fee_income,
        "csm_pv_other_income_aud": other_income,
        "csm_pv_claims_aud": claims,
        "csm_pv_costs_aud": costs,
        "csm_reconciliation_gap_aud": reconciliation_gap,
    }


def _prefixed_csm_components(
    row: Mapping[str, object],
    prefix: str,
    *,
    label: str,
) -> dict[str, float]:
    source = {
        metric: row.get(f"{prefix}{metric}") for metric in CSM_SOURCE_METRICS
    }
    return _csm_components(source, label=label)


def _validate_model_point_csm_aggregation(
    summary: Mapping[str, object],
    model_point_rows: Sequence[Mapping[str, object]],
    portfolio_metrics: Mapping[str, object],
    *,
    label: str,
) -> None:
    contribution_prefix = (
        "portfolio_contribution_"
        if _as_bool(summary.get("absolute_portfolio_values_available"))
        else "normalised_contribution_"
    )
    aggregated = sum(
        _prefixed_csm_components(
            row,
            contribution_prefix,
            label=f"{label} model-point contribution",
        )["csm_aud"]
        for row in model_point_rows
    )
    _require_close(
        aggregated,
        float(portfolio_metrics["csm_aud"]),
        f"{label} model-point/portfolio CSM aggregation",
    )


def _portfolio_metrics(
    summary: Mapping[str, object],
    *,
    label: str = "portfolio summary",
) -> dict[str, object]:
    metrics: dict[str, object] = {
        metric: _monetary(summary, metric) for metric in MONETARY_METRICS
    }
    metrics.update(_csm_components(metrics, label=label))
    metrics.update(_extract_behaviour_metrics(summary, label=label))
    premium = float(metrics["premium_aud"])
    claims = float(metrics["pv_guarantee_claims_aud"])
    future_fees = float(metrics["pv_future_fees_aud"])
    expenses = float(metrics["pv_expenses_aud"])
    hedge_costs = float(metrics["pv_hedge_costs_aud"])
    money_market_income = float(metrics["pv_money_market_income_aud"])
    hedge_gain = float(metrics["pv_hedge_gain_aud"])
    hedge_components = (
        float(metrics["pv_hedge_option_fair_value_costs_aud"])
        + float(metrics["pv_hedge_option_markup_costs_aud"])
        + float(metrics["pv_hedge_management_fee_costs_aud"])
        + float(metrics["pv_hedge_execution_costs_aud"])
    )
    crediting_margin_components = money_market_income + hedge_gain
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
        "money_market_income_to_premium": _safe_ratio(
            money_market_income, premium),
        "hedge_gain_to_premium": _safe_ratio(hedge_gain, premium),
        "expenses_to_premium": _safe_ratio(expenses, premium),
        "hedge_costs_to_premium": _safe_ratio(hedge_costs, premium),
        "csm_to_premium": _safe_ratio(float(metrics["csm_aud"]), premium),
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
        hedge_costs,
        hedge_components,
        f"{label} hedge-cost component reconciliation",
    )
    _require_close(
        float(metrics["pv_hedge_cost_reconciliation_gap_aud"]),
        hedge_costs - hedge_components,
        f"{label} reported hedge-cost reconciliation gap",
    )
    _require_close(
        float(metrics["pv_crediting_margin_aud"]),
        crediting_margin_components,
        f"{label} backing-income/hedge-gain reconciliation",
    )
    _require_close(
        float(metrics["pv_crediting_margin_reconciliation_gap_aud"]),
        float(metrics["pv_crediting_margin_aud"])
        - crediting_margin_components,
        f"{label} reported crediting-margin reconciliation gap",
    )
    _require_close(
        float(metrics["pv_guarantee_claims_aud"]),
        float(metrics["pv_post_election_guarantee_claims_aud"]),
        f"{label} post-Election Guarantee-Claim PV",
    )
    _require_close(
        _as_float(
            summary.get("new_business_margin_before_risk_margin"),
            "new_business_margin_before_risk_margin",
        ),
        float(metrics["csm_aud"]) / premium,
        f"{label} CSM-to-premium/new-business-margin reconciliation",
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
    csms = [
        _prefixed_csm_components(
            row,
            "per_contract_",
            label="model-point per-contract CSM",
        )["csm_aud"]
        for row in rows
    ]
    premiums = [
        _as_float(row.get("per_contract_premium_aud"), "per_contract_premium_aud")
        for row in rows
    ]
    margins = [csm / premium for csm, premium in zip(csms, premiums)]
    for row, csm_margin in zip(rows, margins):
        _require_close(
            _as_float(
                row.get("per_contract_new_business_margin_before_risk_margin"),
                "per_contract_new_business_margin_before_risk_margin",
            ),
            csm_margin,
            "model-point CSM-to-premium/new-business-margin reconciliation",
        )
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
        weight for weight, csm in zip(weights, csms) if csm < 0.0
    )
    weighted_margin_mean = sum(
        weight * margin for weight, margin in zip(weights, margins)
    )
    weighted_margin_variance = sum(
        weight * (margin - weighted_margin_mean) ** 2
        for weight, margin in zip(weights, margins)
    )
    weighted_p10 = _weighted_quantile(margins, weights, 0.10)
    weighted_tail_mean = _weighted_lower_tail_mean(margins, weights, 0.10)
    weighted_standard_deviation = math.sqrt(max(weighted_margin_variance, 0.0))
    return {
        "model_point_count": len(rows),
        "negative_value_contract_share": negative_value_share,
        "strict_negative_csm_contract_share": strict_negative_share,
        "strict_negative_npv_contract_share": strict_negative_share,
        "model_point_csm_to_premium_contract_weighted_mean": weighted_margin_mean,
        "model_point_csm_to_premium_weighted_p10": weighted_p10,
        "model_point_csm_to_premium_weighted_lower_tail_mean_10pct": (
            weighted_tail_mean
        ),
        "model_point_csm_to_premium_weighted_standard_deviation": (
            weighted_standard_deviation
        ),
        # Backward-compatible NBM aliases; the numerator is canonical CSM.
        "model_point_nbm_contract_weighted_mean": weighted_margin_mean,
        "model_point_nbm_weighted_p10": weighted_p10,
        "model_point_nbm_weighted_lower_tail_mean_10pct": weighted_tail_mean,
        "model_point_nbm_weighted_standard_deviation": weighted_standard_deviation,
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
    settings = manifest.get("lsmc_settings")
    if not isinstance(settings, Mapping):
        raise ValueError("LSMC manifest has no lsmc_settings object.")
    training_seed_count = int(_as_float(
        settings.get("training_seed_count", 1), "training_seed_count"
    ))
    if training_seed_count != 1:
        raise ValueError("Direct customer LSMC must use exactly one sample.")
    expected_seed_indices = set(range(1, training_seed_count + 1))
    if _as_bool(settings.get("allow_partial_withdrawal")):
        raise ValueError(
            "The risk analysis supports only the ordered Continue/Full-Withdrawal "
            "LSMC policy."
        )
    action_seed_indices: set[int] = set()
    for row in action_rows:
        seed_index = int(_as_float(
            row.get("training_seed_index"),
            "action training_seed_index",
        ))
        if seed_index not in expected_seed_indices:
            raise ValueError("LSMC action summary has an unknown training seed.")
        action_seed_indices.add(seed_index)
        if _as_bool(row.get("primary_training_seed")) is not (seed_index == 1):
            raise ValueError(
                "LSMC action summary has an inconsistent primary flag."
            )
    if action_seed_indices != expected_seed_indices:
        raise ValueError("LSMC action summary does not cover all active seeds.")
    action_rows = [
        row for row in action_rows
        if _as_bool(row.get("primary_training_seed"))
    ]
    if any(
        not str(row.get("action_type", "")).strip()
        and _as_float(row.get("eligible_path_count", 0.0), "eligible_path_count")
        > 0.0
        for row in action_rows
    ):
        raise ValueError(
            "LSMC action summary must distinguish Election and annual "
            "Continue/Full-Withdrawal action types."
        )
    action_rows = [
        row for row in action_rows
        if str(row.get("action_type", "")).strip()
    ]
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
                    "action_path_count",
                    "selected_action_path_count",
                    "exercise_path_count",
                    "start_income_path_count"
                    if action_type == "income_election"
                    else f"{action_type}_path_count",
                ),
                label=f"{action_type} selected path count",
            ))
            eligible += int(_as_float(
                row.get("eligible_path_count"),
                f"{action_type} eligible_path_count",
            ))
            forced_field = (
                "forced_action_path_count"
                if row.get("forced_action_path_count") not in (None, "")
                else "forced_path_count"
            )
            if row.get(forced_field) not in (None, ""):
                forced += int(_as_float(
                    row.get(forced_field),
                    f"{action_type} {forced_field}",
                ))
        return selected, eligible, forced

    election_count, election_eligible, forced_election_count = action_totals(
        "income_election"
    )
    continue_count, continue_eligible, _ = action_totals("continue")
    surrender_count, surrender_eligible, _ = action_totals("full_withdrawal")
    if election_eligible <= 0:
        raise ValueError("LSMC action summary has no eligible Election decisions.")
    # Every enabled optimal action must have fit evidence.  There is no
    # validation fallback that can excuse a structurally invalid V11 fit.
    r_squared = [
        _as_float(row.get("oof_r_squared"), "oof_r_squared")
        for row in diagnostic_rows
        if row.get("oof_r_squared") not in (None, "")
    ]
    rmse = [
        _as_float(row.get("oof_rmse_aud"), "oof_rmse_aud")
        for row in diagnostic_rows
        if row.get("oof_rmse_aud") not in (None, "")
    ]
    condition_numbers = [
        _as_float(row.get("condition_number"), "condition_number")
        for row in diagnostic_rows
        if row.get("condition_number") not in (None, "")
    ]
    accepted = sum(
        _as_bool(row.get(
            "regression_accepted_for_action",
            row.get("regression_accepted_for_exercise"),
        ))
        for row in diagnostic_rows
    )
    diagnostic_groups = {
        action_type: [
            row for row in diagnostic_rows
            if str(row.get("action_type")).strip().lower() == action_type
        ]
        for action_type in (
            "income_election",
            "full_withdrawal",
        )
    }

    missing_diagnostics = {
        action_type
        for action_type, rows in diagnostic_groups.items()
        if not rows
    }
    if missing_diagnostics:
        raise ValueError(
            "LSMC diagnostics do not cover every enabled optimal action."
        )
    unique_fits = int(_as_float(
        settings.get("unique_policy_fits"), "unique_policy_fits"))
    fallback_fits = int(_as_float(
        settings.get("training_fallback_policy_count", 0),
        "training fallback policy count",
    ))
    if fallback_fits:
        raise ValueError("Direct V11 customer LSMC must not deploy a fit fallback.")
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
        "continue_action_path_count": continue_count,
        "continue_eligible_path_count": continue_eligible,
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
        "numerical_regression_diagnostic_count": len(r_squared),
        "oof_r_squared_q25": (
            _quantile(r_squared, 0.25) if r_squared else 0.0
        ),
        "oof_r_squared_median": (
            statistics.median(r_squared) if r_squared else 0.0
        ),
        "oof_rmse_aud_median": statistics.median(rmse) if rmse else 0.0,
        "condition_number_median": (
            statistics.median(condition_numbers)
            if condition_numbers else 0.0
        ),
        "condition_number_max": (
            max(condition_numbers) if condition_numbers else 0.0
        ),
    }
    for action_type, rows in diagnostic_groups.items():
        prefix = {
            "income_election": "election",
            "full_withdrawal": "surrender",
        }[action_type]
        group_r_squared = [
            _as_float(row.get("oof_r_squared"), "oof_r_squared")
            for row in rows
            if row.get("oof_r_squared") not in (None, "")
        ]
        group_rmse = [
            _as_float(row.get("oof_rmse_aud"), "oof_rmse_aud")
            for row in rows
            if row.get("oof_rmse_aud") not in (None, "")
        ]
        group_accepted = sum(
            _as_bool(row.get(
                "regression_accepted_for_action",
                row.get("regression_accepted_for_exercise"),
            ))
            for row in rows
        )
        output.update({
            f"{prefix}_regression_count": len(rows),
            f"{prefix}_regression_accepted_count": group_accepted,
            f"{prefix}_regression_accepted_share": (
                group_accepted / len(rows) if rows else 0.0
            ),
            f"{prefix}_numerical_diagnostic_count": len(group_r_squared),
            f"{prefix}_oof_r_squared_median": (
                statistics.median(group_r_squared)
                if group_r_squared else 0.0
            ),
            f"{prefix}_oof_rmse_aud_median": (
                statistics.median(group_rmse) if group_rmse else 0.0
            ),
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
            f"{label} records an explicit portfolio contract count although the "
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
) -> list[dict[str, object]]:
    dynamic = {str(row["model_point_id"]): row for row in dynamic_rows}
    output: list[dict[str, object]] = []
    for right in lsmc_rows:
        model_point_id = str(right["model_point_id"])
        left = dynamic[model_point_id]
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
            row[f"dynamic_per_contract_{metric}"] = left_value
            row[f"lsmc_per_contract_{metric}"] = right_value
            row[f"lsmc_minus_dynamic_per_contract_{metric}"] = (
                right_value - left_value)
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
        for value_prefix in (
            "per_contract_",
            "normalised_contribution_",
            "portfolio_contribution_",
        ):
            if not all(
                f"{value_prefix}{metric}" in left
                and f"{value_prefix}{metric}" in right
                for metric in CSM_SOURCE_METRICS
            ):
                continue
            dynamic_csm = _prefixed_csm_components(
                left,
                value_prefix,
                label=f"Dynamic model point {model_point_id} {value_prefix}CSM",
            )
            lsmc_csm = _prefixed_csm_components(
                right,
                value_prefix,
                label=f"LSMC model point {model_point_id} {value_prefix}CSM",
            )
            for field in dynamic_csm:
                row[f"dynamic_{value_prefix}{field}"] = dynamic_csm[field]
                row[f"lsmc_{value_prefix}{field}"] = lsmc_csm[field]
                row[f"lsmc_minus_dynamic_{value_prefix}{field}"] = (
                    lsmc_csm[field] - dynamic_csm[field]
                )
        dynamic_csm = float(row["dynamic_per_contract_csm_aud"])
        lsmc_csm = float(row["lsmc_per_contract_csm_aud"])
        csm_gap = dynamic_csm - lsmc_csm
        row["behaviour_model_csm_gap_per_contract_aud"] = csm_gap
        # Backward-compatible alias for downstream readers of older runs.
        row["behaviour_model_gap_to_insurer_per_contract_aud"] = csm_gap
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


def _manifest_hedge_cap_leg_mode(manifest: Mapping[str, object]) -> str:
    """Return one internally consistent hedge mode from a runner manifest."""
    values: list[str] = []
    for section_name in (
        "method",
        "valuation_settings",
        "lsmc_settings",
        "evaluation_settings",
    ):
        section = manifest.get(section_name)
        if isinstance(section, Mapping) and section.get("hedge_cap_leg_mode") not in (
            None,
            "",
        ):
            values.append(str(section["hedge_cap_leg_mode"]))
    if not values:
        raise ValueError("Runner manifest has no hedge_cap_leg_mode metadata.")
    if len(set(values)) != 1:
        raise ValueError("Runner manifest contains inconsistent hedge-cap-leg modes.")
    if values[0] not in {"sold", "not_sold"}:
        raise ValueError(f"Unknown runner hedge-cap-leg mode {values[0]!r}.")
    return values[0]


def _required_manifest_text(value: object, label: str) -> str:
    text = str(value).strip()
    if text in {"", "None"}:
        raise ValueError(f"{label} is missing from the runner manifest.")
    return text


def _none_like(value: object) -> bool:
    return value is None or str(value).strip() in {"", "None"}


def _manifest_hedge_pricing_method(
    manifest: Mapping[str, object],
    summary: Mapping[str, object],
    *,
    label: str,
) -> str:
    values: list[str] = []
    for section_name in (
        "method",
        "valuation_settings",
        "lsmc_settings",
        "evaluation_settings",
    ):
        section = manifest.get(section_name)
        if isinstance(section, Mapping) and section.get("hedge_pricing_method") not in (
            None,
            "",
        ):
            values.append(str(section["hedge_pricing_method"]).strip())
    if summary.get("hedge_pricing_method") not in (None, ""):
        values.append(str(summary["hedge_pricing_method"]).strip())
    if not values or len(set(values)) != 1:
        raise ValueError(f"{label} has missing or inconsistent hedge-pricing metadata.")
    return values[0]


def _validate_manifest_cache_controls(
    manifest: Mapping[str, object],
    args: argparse.Namespace,
    *,
    label: str,
    require_presence: bool,
) -> tuple[bool, bool]:
    sections = tuple(
        section
        for section_name in (
            "method",
            "valuation_settings",
            "lsmc_settings",
            "evaluation_settings",
            "validation_settings",
        )
        for section in (manifest.get(section_name),)
        if isinstance(section, Mapping)
    )
    expected = {
        "require_market_cache": bool(args.require_market_cache),
        "require_hedge_cache": bool(args.require_hedge_cache),
    }
    present: dict[str, list[bool]] = {field: [] for field in expected}
    for section in sections:
        for field in expected:
            if field in section:
                present[field].append(_as_bool(section[field]))
    for field, expected_value in expected.items():
        if require_presence and not present[field]:
            raise ValueError(f"{label} manifest has no {field} audit flag.")
        if any(value is not expected_value for value in present[field]):
            raise ValueError(f"{label} manifest has an inconsistent {field} flag.")

    root_expectations = {
        "market_cache_root": args.market_cache_root,
        "hedge_cache_root": args.hedge_cache_root,
    }
    for field, expected_path in root_expectations.items():
        actual_paths = [
            section[field]
            for section in sections
            if section.get(field) not in (None, "")
        ]
        if require_presence and not actual_paths:
            raise ValueError(f"{label} manifest has no {field} audit path.")
        for actual in actual_paths:
            if Path(str(actual)).expanduser().resolve() != (
                expected_path.expanduser().resolve()
            ):
                raise ValueError(f"{label} manifest changed {field}.")
    return bool(present["require_market_cache"]), bool(
        present["require_hedge_cache"]
    )


def _validate_dynamic_cache_metadata(
    manifest: Mapping[str, object],
    summary: Mapping[str, object],
    args: argparse.Namespace,
    *,
    rate: float,
    evaluation_fingerprint: str,
) -> dict[str, object]:
    method = manifest.get("method")
    portfolio = manifest.get("portfolio")
    if not isinstance(method, Mapping) or not isinstance(portfolio, Mapping):
        raise ValueError("Dynamic manifest has incomplete cache metadata.")
    pricing_method = _manifest_hedge_pricing_method(
        manifest, summary, label="Dynamic"
    )
    if pricing_method != args.hedge_pricing_method:
        raise ValueError("Dynamic hedge-pricing method differs from the request.")
    market_flag_present, hedge_flag_present = _validate_manifest_cache_controls(
        manifest,
        args,
        label="Dynamic",
        require_presence=True,
    )
    market_key = _required_manifest_text(
        summary.get("market_cache_key"), "Dynamic summary market_cache_key"
    )
    if _required_manifest_text(
        method.get("market_cache_key"), "Dynamic method market_cache_key"
    ) != market_key:
        raise ValueError("Dynamic summary and manifest use different market caches.")
    manifest_fingerprints = {
        _required_manifest_text(
            method.get("scenario_fingerprint"),
            "Dynamic method scenario_fingerprint",
        ),
        _required_manifest_text(
            portfolio.get("scenario_fingerprint"),
            "Dynamic portfolio scenario_fingerprint",
        ),
        _required_manifest_text(
            summary.get("scenario_fingerprint"),
            "Dynamic summary scenario_fingerprint",
        ),
        evaluation_fingerprint,
    }
    if len(manifest_fingerprints) != 1:
        raise ValueError("Dynamic cache and scenario fingerprints are inconsistent.")

    hedge_key: Optional[str] = None
    price_surface_fingerprint: Optional[str] = None
    if args.require_hedge_cache:
        hedge_key = _required_manifest_text(
            summary.get("hedge_cache_key"), "Dynamic summary hedge_cache_key"
        )
        if _required_manifest_text(
            method.get("hedge_cache_key"), "Dynamic method hedge_cache_key"
        ) != hedge_key:
            raise ValueError("Dynamic summary and manifest use different hedge caches.")
        price_surface_fingerprint = _required_manifest_text(
            summary.get("hedge_price_surface_fingerprint"),
            "Dynamic summary hedge_price_surface_fingerprint",
        )
        if _required_manifest_text(
            method.get("hedge_price_surface_fingerprint"),
            "Dynamic method hedge_price_surface_fingerprint",
        ) != price_surface_fingerprint:
            raise ValueError("Dynamic hedge-price surface fingerprints differ.")
        for container, container_label in ((summary, "summary"), (method, "method")):
            if _required_manifest_text(
                container.get("hedge_training_scenario_fingerprint"),
                f"Dynamic {container_label} hedge training fingerprint",
            ) != evaluation_fingerprint:
                raise ValueError(
                    "Dynamic hedge-price cache is not congruent with evaluation paths."
                )
        cap_grid = method.get("hedge_cap_grid")
        if not isinstance(cap_grid, list) or len(cap_grid) != 1:
            raise ValueError("Dynamic hedge cache does not evidence one exact cap.")
        _require_close(
            _as_float(cap_grid[0], "Dynamic hedge cap grid"),
            rate,
            "Dynamic hedge-cache cap",
        )
    else:
        for field in (
            "hedge_cache_key",
            "hedge_price_surface_fingerprint",
            "hedge_training_scenario_fingerprint",
        ):
            if not _none_like(summary.get(field)) or not _none_like(method.get(field)):
                raise ValueError(
                    f"Moment-matched Dynamic valuation unexpectedly records {field}."
                )

    return {
        "market_cache_key": market_key,
        "hedge_cache_key": hedge_key,
        "hedge_price_surface_fingerprint": price_surface_fingerprint,
        "pricing_method": pricing_method,
        "require_market_cache_flag_present": market_flag_present,
        "require_hedge_cache_flag_present": hedge_flag_present,
    }


def _validate_lsmc_cache_metadata(
    manifest: Mapping[str, object],
    summary: Mapping[str, object],
    args: argparse.Namespace,
    *,
    rate: float,
    scenario_fingerprint: str,
) -> dict[str, object]:
    """Validate the one cache-congruent sample used for fit and valuation."""
    method = manifest.get("method")
    if not isinstance(method, Mapping):
        raise ValueError("LSMC manifest has no cache-aware method metadata.")
    pricing_method = _manifest_hedge_pricing_method(manifest, summary, label="LSMC")
    if pricing_method != args.hedge_pricing_method:
        raise ValueError("LSMC hedge-pricing method differs from the request.")
    market_flag_present, hedge_flag_present = _validate_manifest_cache_controls(
        manifest,
        args,
        label="LSMC",
        require_presence=False,
    )
    if _required_manifest_text(
        method.get("scenario_fingerprint"),
        "LSMC method scenario_fingerprint",
    ) != scenario_fingerprint or _required_manifest_text(
        summary.get("scenario_fingerprint"),
        "LSMC summary scenario_fingerprint",
    ) != scenario_fingerprint:
        raise ValueError("LSMC fit and valuation do not use the common Q sample.")

    market_key = _required_manifest_text(
        method.get("market_cache_key"), "LSMC method market_cache_key"
    )
    if market_key != _required_manifest_text(
        summary.get("market_cache_key"), "LSMC summary market_cache_key"
    ):
        raise ValueError("LSMC summary and manifest market-cache keys differ.")

    hedge_key: Optional[str] = None
    surface_fingerprint: Optional[str] = None
    if args.require_hedge_cache:
        hedge_key = _required_manifest_text(
            method.get("hedge_cache_key"), "LSMC method hedge_cache_key"
        )
        if hedge_key != _required_manifest_text(
            summary.get("hedge_cache_key"), "LSMC summary hedge_cache_key"
        ):
            raise ValueError("LSMC summary and manifest hedge-cache keys differ.")
        surface_fingerprint = _required_manifest_text(
            method.get("hedge_price_surface_fingerprint"),
            "LSMC method hedge-price surface fingerprint",
        )
        if surface_fingerprint != _required_manifest_text(
            summary.get("hedge_price_surface_fingerprint"),
            "LSMC summary hedge-price surface fingerprint",
        ):
            raise ValueError("LSMC hedge-price surface fingerprints differ.")
        if _required_manifest_text(
            summary.get("hedge_training_scenario_fingerprint"),
            "LSMC summary hedge training fingerprint",
        ) != scenario_fingerprint:
            raise ValueError("LSMC hedge cache is not path-congruent.")
    else:
        optional_values = (
            method.get("hedge_cache_key"),
            method.get("hedge_price_surface_fingerprint"),
            summary.get("hedge_cache_key"),
            summary.get("hedge_price_surface_fingerprint"),
            summary.get("hedge_training_scenario_fingerprint"),
        )
        if any(not _none_like(value) for value in optional_values):
            raise ValueError(
                "Moment-matched LSMC valuation unexpectedly records a hedge cache."
            )

    return {
        "market_cache_key": market_key,
        "hedge_cache_key": hedge_key,
        "hedge_price_surface_fingerprint": surface_fingerprint,
        "pricing_method": pricing_method,
        "require_market_cache_flag_present": market_flag_present,
        "require_hedge_cache_flag_present": hedge_flag_present,
    }


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
    tokens = {
        token
        for token in re.split(r"[^a-z0-9_]+", str(value).strip().lower())
        if token
    }
    action_aliases = {
        "wait_for_one_year": "wait",
        "start_income_now": "start_income",
        "continue_for_one_year": "continue",
        "normal_income_for_one_year": "continue",
        "normal_income": "continue",
        "full_withdrawal_now": "full_withdrawal",
        "full_surrender_now": "full_withdrawal",
        "full_surrender": "full_withdrawal",
    }
    tokens.update(
        action_aliases[token]
        for token in tuple(tokens)
        if token in action_aliases
    )
    return tokens


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


_LSMC_VALIDATION_COMPONENTS = {
    "election_only",
    "income_action_only",
    "combined_policy",
}


def _expected_lsmc_training_seed_triplets(
    args: argparse.Namespace,
) -> tuple[dict[str, object], ...]:
    available = (
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
    return available[:args.training_seed_count]


def _validate_lsmc_gate_set(
    gates: object,
    *,
    label: str,
    require_all_valid: bool = True,
) -> None:
    if not isinstance(gates, list) or len(gates) != 3:
        raise ValueError(f"{label} must contain exactly three validation gates.")
    if any(
        not isinstance(gate, Mapping)
        for gate in gates
    ):
        raise ValueError(f"{label} contains a malformed validation gate.")
    components = {
        str(gate.get("component", "")).strip()
        for gate in gates
        if isinstance(gate, Mapping)
    }
    if components != _LSMC_VALIDATION_COMPONENTS:
        raise ValueError(
            f"{label} must contain Election-, Income-action- and Combined gates."
        )
    if require_all_valid and any(
        not _as_bool(gate.get("valid"))
        for gate in gates
        if isinstance(gate, Mapping)
    ):
        raise ValueError(f"{label} contains an invalid validation gate.")


def _validate_lsmc_seed_evidence(
    directory: Path,
    manifest: Mapping[str, object],
    validation_manifest: Mapping[str, object],
    *,
    expected_args: argparse.Namespace,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[bool, ...]]:
    """Validate every active fit's acceptance and evaluation evidence."""

    lsmc_settings = manifest.get("lsmc_settings")
    validation_settings = manifest.get("validation_settings")
    evaluation_settings = manifest.get("evaluation_settings")
    if not all(
        isinstance(item, Mapping)
        for item in (lsmc_settings, validation_settings, evaluation_settings)
    ):
        raise ValueError("LSMC seed settings are incomplete.")
    assert isinstance(lsmc_settings, Mapping)
    assert isinstance(validation_settings, Mapping)
    assert isinstance(evaluation_settings, Mapping)

    expected_triplets = _expected_lsmc_training_seed_triplets(expected_args)
    expected_seed_count = len(expected_triplets)
    triplets = lsmc_settings.get("training_seed_triplets")
    if not isinstance(triplets, list) or len(triplets) != expected_seed_count:
        raise ValueError("LSMC manifest has the wrong active seed-triplet count.")
    for index, (actual, expected) in enumerate(
        zip(triplets, expected_triplets), start=1
    ):
        if not isinstance(actual, Mapping):
            raise ValueError(f"LSMC training seed triplet {index} is malformed.")
        for field in ("seed_index", "market_seed", "take_up_seed", "mortality_seed"):
            if int(_as_float(actual.get(field), field)) != int(expected[field]):
                raise ValueError(
                    f"LSMC training seed triplet {index} changed {field}."
                )
        if _as_bool(actual.get("primary")) is not bool(expected["primary"]):
            raise ValueError(
                f"LSMC training seed triplet {index} has the wrong primary flag."
            )

    training_fingerprints_raw = lsmc_settings.get(
        "training_scenario_fingerprints"
    )
    if not isinstance(training_fingerprints_raw, list) or len(
        training_fingerprints_raw
    ) != expected_seed_count:
        raise ValueError(
            "LSMC manifest has the wrong training-fingerprint count."
        )
    training_fingerprints = tuple(
        str(value).strip() for value in training_fingerprints_raw
    )
    validation_fingerprint = str(
        validation_settings.get("scenario_fingerprint", "")
    ).strip()
    evaluation_fingerprint = str(
        evaluation_settings.get("scenario_fingerprint", "")
    ).strip()
    all_fingerprints = {
        *training_fingerprints,
        validation_fingerprint,
        evaluation_fingerprint,
    }
    if "" in all_fingerprints \
            or len(set(training_fingerprints)) != expected_seed_count \
            or len(all_fingerprints) != expected_seed_count + 2:
        raise ValueError(
            "All active training, validation and evaluation fingerprints must differ."
        )
    if str(lsmc_settings.get("training_scenario_fingerprint", "")).strip() \
            != training_fingerprints[0]:
        raise ValueError(
            "The backward-compatible training fingerprint is not primary seed 1."
        )
    if int(_as_float(
        lsmc_settings.get("training_seed_count"), "training_seed_count"
    )) != expected_seed_count or int(_as_float(
        lsmc_settings.get("primary_training_seed_index"),
        "primary_training_seed_index",
    )) != 1:
        raise ValueError("LSMC primary training seed 1 is not predeclared.")
    if lsmc_settings.get("evaluation_used_for_training_seed_selection") is not False:
        raise ValueError("LSMC training-seed selection used final evaluation data.")
    selection_rule = str(
        lsmc_settings.get("primary_seed_selection_rule", "")
    ).lower()
    if "predeclared" not in selection_rule or "not_evaluation" not in selection_rule:
        raise ValueError("LSMC primary seed-selection rule is not predeclared.")

    gates_by_seed = validation_settings.get("gates_by_training_seed")
    expected_gate_keys = {
        f"training_seed_{index}"
        for index in range(1, expected_seed_count + 1)
    }
    if not isinstance(gates_by_seed, Mapping) \
            or set(gates_by_seed) != expected_gate_keys:
        raise ValueError("LSMC manifest has no complete gates-by-seed mapping.")
    candidate_fit_valid_by_seed = validation_settings.get(
        "candidate_fit_valid_by_training_seed"
    )
    deployed_policy_by_seed = validation_settings.get(
        "deployed_policy_by_training_seed"
    )
    fallback_reason_by_seed = validation_settings.get(
        "validation_fallback_reason_by_training_seed"
    )
    if not all(isinstance(item, Mapping) for item in (
        candidate_fit_valid_by_seed,
        deployed_policy_by_seed,
        fallback_reason_by_seed,
    )):
        raise ValueError("LSMC manifest has incomplete deployment evidence.")
    assert isinstance(candidate_fit_valid_by_seed, Mapping)
    assert isinstance(deployed_policy_by_seed, Mapping)
    assert isinstance(fallback_reason_by_seed, Mapping)
    expected_deployed_by_seed: dict[int, str] = {}
    candidate_accepted_by_seed: dict[int, bool] = {}
    for index in range(1, expected_seed_count + 1):
        seed_key = f"training_seed_{index}"
        gates = gates_by_seed[seed_key]
        _validate_lsmc_gate_set(
            gates,
            label=f"LSMC manifest training seed {index}",
            require_all_valid=False,
        )
        assert isinstance(gates, list)
        all_gates_valid = all(
            _as_bool(gate.get("valid"))
            for gate in gates
            if isinstance(gate, Mapping)
        )
        candidate_fit_valid = _as_bool(
            candidate_fit_valid_by_seed.get(seed_key)
        )
        candidate_accepted = candidate_fit_valid and all_gates_valid
        combined_gate = next(
            gate
            for gate in gates
            if isinstance(gate, Mapping)
            and gate.get("component") == "combined_policy"
        )
        expected_deployed = (
            "V11"
            if candidate_accepted
            else str(combined_gate.get("benchmark_name", "")).strip()
        )
        actual_deployed = str(
            deployed_policy_by_seed.get(seed_key, "")
        ).strip()
        fallback_reason = str(
            fallback_reason_by_seed.get(seed_key, "")
        ).strip()
        if not expected_deployed or actual_deployed != expected_deployed:
            raise ValueError(
                f"LSMC training seed {index} deployed an unvalidated policy."
            )
        if candidate_accepted and fallback_reason:
            raise ValueError(
                f"LSMC training seed {index} records a spurious fallback."
            )
        if not candidate_accepted and not fallback_reason:
            raise ValueError(
                f"LSMC training seed {index} has no fallback reason."
            )
        expected_deployed_by_seed[index] = expected_deployed
        candidate_accepted_by_seed[index] = candidate_accepted
    if not _as_bool(validation_settings.get(
        "every_seed_passes_or_deploys_validated_fallback"
    )) or not _as_bool(validation_settings.get("deployment_valid")):
        raise ValueError(
            "Not every LSMC seed deploys V11 or its validated fixed fallback."
        )
    if _as_bool(validation_settings.get("candidate_valid")) is not all(
        candidate_accepted_by_seed.values()
    ):
        raise ValueError("LSMC manifest changed aggregate candidate validity.")

    if not isinstance(validation_manifest, Mapping) or not _as_bool(
        validation_manifest.get("valid")
    ) or not _as_bool(validation_manifest.get("deployment_valid")):
        raise ValueError("Independent LSMC validation manifest is invalid.")
    if _as_bool(validation_manifest.get("candidate_valid")) is not all(
        candidate_accepted_by_seed.values()
    ):
        raise ValueError(
            "Independent LSMC validation changed aggregate candidate validity."
        )
    if int(_as_float(
        validation_manifest.get("training_seed_count"),
        "validation training_seed_count",
    )) != expected_seed_count:
        raise ValueError("Validation manifest has the wrong active seed count.")
    if validation_manifest.get("seed_selection_using_evaluation") is not False:
        raise ValueError("Validation manifest permits evaluation-based selection.")
    if int(_as_float(
        validation_manifest.get("primary_training_seed_index"),
        "validation primary_training_seed_index",
    )) != 1:
        raise ValueError("Validation manifest does not predeclare seed 1.")
    validation_candidate_fit = validation_manifest.get(
        "candidate_fit_valid_by_training_seed"
    )
    validation_deployed = validation_manifest.get(
        "deployed_policy_by_training_seed"
    )
    validation_fallbacks = validation_manifest.get(
        "validation_fallback_reason_by_training_seed"
    )
    if not all(isinstance(item, Mapping) for item in (
        validation_candidate_fit,
        validation_deployed,
        validation_fallbacks,
    )):
        raise ValueError(
            "Validation manifest has incomplete deployment selections."
        )
    assert isinstance(validation_candidate_fit, Mapping)
    assert isinstance(validation_deployed, Mapping)
    assert isinstance(validation_fallbacks, Mapping)
    for index in range(1, expected_seed_count + 1):
        numeric_key = str(index)
        if _as_bool(validation_candidate_fit.get(numeric_key)) is not (
            _as_bool(candidate_fit_valid_by_seed.get(
                f"training_seed_{index}"
            ))
        ) or str(validation_deployed.get(numeric_key, "")).strip() != (
            expected_deployed_by_seed[index]
        ):
            raise ValueError(
                f"Validation manifest changed deployment for seed {index}."
            )
        expected_fallback = str(fallback_reason_by_seed.get(
            f"training_seed_{index}", ""
        )).strip()
        if str(validation_fallbacks.get(numeric_key, "")).strip() != (
            expected_fallback
        ):
            raise ValueError(
                f"Validation manifest changed fallback reason for seed {index}."
            )
    top_level_gates = validation_manifest.get("gates")
    if not isinstance(top_level_gates, list) \
            or len(top_level_gates) != 3 * expected_seed_count:
        raise ValueError("Validation manifest has the wrong gate count.")
    top_level_groups: dict[int, list[Mapping[str, object]]] = {
        index: [] for index in range(1, expected_seed_count + 1)
    }
    for gate in top_level_gates:
        if not isinstance(gate, Mapping):
            raise ValueError("Validation manifest contains a malformed top-level gate.")
        seed_index = int(_as_float(
            gate.get("training_seed_index"), "gate training_seed_index"
        ))
        if seed_index not in top_level_groups:
            raise ValueError("Validation gate refers to an unknown training seed.")
        top_level_groups[seed_index].append(gate)
    for index, gates in top_level_groups.items():
        _validate_lsmc_gate_set(
            gates,
            label=f"Validation manifest top-level seed {index}",
            require_all_valid=False,
        )
        expected = expected_triplets[index - 1]
        for gate in gates:
            if str(gate.get("training_scenario_fingerprint", "")).strip() != (
                training_fingerprints[index - 1]
            ):
                raise ValueError("Top-level validation gate changed its sample.")
            for field, expected_field in (
                ("training_market_seed", "market_seed"),
                ("training_take_up_seed", "take_up_seed"),
                ("training_mortality_seed", "mortality_seed"),
            ):
                if int(_as_float(gate.get(field), field)) != int(
                    expected[expected_field]
                ):
                    raise ValueError(
                        f"Top-level validation gate {index} changed {field}."
                    )

    training_runs = validation_manifest.get("training_runs")
    if not isinstance(training_runs, list) \
            or len(training_runs) != expected_seed_count:
        raise ValueError("Validation manifest has the wrong training-run count.")
    for index, (run, expected, fingerprint) in enumerate(
        zip(training_runs, expected_triplets, training_fingerprints), start=1
    ):
        if not isinstance(run, Mapping) or not _as_bool(run.get("valid")) \
                or not _as_bool(run.get("deployment_valid")):
            raise ValueError(f"Validation training run {index} is invalid.")
        if _as_bool(run.get("candidate_valid")) is not (
            candidate_accepted_by_seed[index]
        ):
            raise ValueError(
                f"Validation training run {index} changed candidate validity."
            )
        for field in ("seed_index", "market_seed", "take_up_seed", "mortality_seed"):
            if int(_as_float(run.get(field), field)) != int(expected[field]):
                raise ValueError(
                    f"Validation training run {index} changed {field}."
                )
        if _as_bool(run.get("primary")) is not bool(expected["primary"]):
            raise ValueError(
                f"Validation training run {index} has the wrong primary flag."
            )
        if str(run.get("training_scenario_fingerprint", "")).strip() != fingerprint:
            raise ValueError(
                f"Validation training run {index} changed its fingerprint."
            )
        _validate_lsmc_gate_set(
            run.get("gates"),
            label=f"Validation training run {index}",
            require_all_valid=False,
        )

    final_evaluations = evaluation_settings.get("multi_seed_final_evaluation")
    evaluation_fingerprints = evaluation_settings.get(
        "multi_seed_evaluation_scenario_fingerprints"
    )
    if not isinstance(final_evaluations, list) \
            or len(final_evaluations) != expected_seed_count:
        raise ValueError("LSMC manifest has the wrong final-evaluation count.")
    if not isinstance(evaluation_fingerprints, list) or len(
        evaluation_fingerprints
    ) != expected_seed_count or any(
        str(value).strip() != evaluation_fingerprint
        for value in evaluation_fingerprints
    ):
        raise ValueError("The active LSMC fits do not share one final evaluation.")
    if evaluation_settings.get("training_seed_selected_using_evaluation") is not False:
        raise ValueError("Final evaluation was used to select a training seed.")
    for index, (row, expected, fingerprint) in enumerate(
        zip(final_evaluations, expected_triplets, training_fingerprints), start=1
    ):
        if not isinstance(row, Mapping):
            raise ValueError(f"Final evaluation row {index} is malformed.")
        if int(_as_float(
            row.get("training_seed_index"), "evaluation training_seed_index"
        )) != index:
            raise ValueError("Final evaluation training-seed order changed.")
        if _as_bool(row.get("primary_training_seed")) is not bool(
            expected["primary"]
        ):
            raise ValueError("Final evaluation primary-seed flag is inconsistent.")
        if str(row.get("training_scenario_fingerprint", "")).strip() != fingerprint:
            raise ValueError("Final evaluation changed a training fingerprint.")
        for field, expected_field in (
            ("training_market_seed", "market_seed"),
            ("training_take_up_seed", "take_up_seed"),
            ("training_mortality_seed", "mortality_seed"),
        ):
            if int(_as_float(row.get(field), field)) != int(
                expected[expected_field]
            ):
                raise ValueError(f"Final evaluation row {index} changed {field}.")
        if str(row.get("evaluation_scenario_fingerprint", "")).strip() \
                != evaluation_fingerprint:
            raise ValueError("Final evaluations do not use one common sample.")
        if row.get("evaluation_used_for_seed_selection") is not False:
            raise ValueError("Final evaluation row permits seed selection.")
        if not _as_bool(row.get("deployment_valid")) or str(
            row.get("deployed_policy", "")
        ).strip() != expected_deployed_by_seed[index]:
            raise ValueError("Final evaluation did not use the validated policy.")
        if _as_bool(row.get("selected_for_primary_outputs")) is not (index == 1):
            raise ValueError("Only predeclared training seed 1 may drive outputs.")

    report_rows = _read_csv(
        directory / "lsmc_multi_seed_validation_evaluation.csv"
    )
    if len(report_rows) != expected_seed_count:
        raise ValueError("Seed-evidence CSV has the wrong row count.")
    for index, (row, expected, fingerprint) in enumerate(
        zip(report_rows, expected_triplets, training_fingerprints), start=1
    ):
        if int(_as_float(
            row.get("training_seed_index"), "CSV training_seed_index"
        )) != index:
            raise ValueError("Multi-seed CSV training-seed order changed.")
        if _as_bool(row.get("primary_training_seed")) is not bool(
            expected["primary"]
        ):
            raise ValueError("Multi-seed CSV primary-seed flag is inconsistent.")
        for field, expected_field in (
            ("training_market_seed", "market_seed"),
            ("training_take_up_seed", "take_up_seed"),
            ("training_mortality_seed", "mortality_seed"),
        ):
            if int(_as_float(row.get(field), field)) != int(expected[expected_field]):
                raise ValueError(f"Multi-seed CSV row {index} changed {field}.")
        if str(row.get("training_scenario_fingerprint", "")).strip() != fingerprint:
            raise ValueError("Multi-seed CSV changed a training fingerprint.")
        if str(row.get("validation_scenario_fingerprint", "")).strip() \
                != validation_fingerprint or str(
                    row.get("evaluation_scenario_fingerprint", "")
                ).strip() != evaluation_fingerprint:
            raise ValueError("Multi-seed CSV changed validation/evaluation samples.")
        if not _as_bool(row.get("deployment_valid")) or str(
            row.get("deployed_policy", "")
        ).strip() != expected_deployed_by_seed[index]:
            raise ValueError(
                "Multi-seed CSV did not evaluate the validated deployment."
            )
        if _as_bool(row.get("selected_for_primary_outputs")) is not (index == 1):
            raise ValueError("Multi-seed CSV did not preselect seed 1.")
        if _as_bool(row.get("evaluation_used_for_seed_selection")):
            raise ValueError("Multi-seed CSV evidences evaluation-based selection.")
        csv_selection_rule = str(row.get("selection_rule", "")).lower()
        if "predeclared" not in csv_selection_rule or "not_evaluation" not in (
            csv_selection_rule
        ):
            raise ValueError("Multi-seed CSV has no predeclared selection rule.")
        csv_candidate_accepted = _as_bool(
            row.get("candidate_fit_valid")
        ) and all(
            _as_bool(row.get(f"validation_{component}_valid"))
            for component in _LSMC_VALIDATION_COMPONENTS
        )
        if csv_candidate_accepted is not candidate_accepted_by_seed[index]:
            raise ValueError(
                f"Multi-seed CSV row {index} changed candidate acceptance."
            )
    deployed_policies = tuple(
        expected_deployed_by_seed[index]
        for index in range(1, expected_seed_count + 1)
    )
    candidate_acceptance = tuple(
        candidate_accepted_by_seed[index]
        for index in range(1, expected_seed_count + 1)
    )
    return training_fingerprints, deployed_policies, candidate_acceptance


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
    forced_rule = str(
        method.get("forced_income_start")
        or method.get("forced_income_election")
        or ""
    ).lower()
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
    if (
        expected_election_mode in {"dynamic", "optimal"}
        and (
            "wait" not in actions
            or not {"start_income", "start_income_now"}.intersection(actions)
        )
    ):
        raise ValueError(
            f"{label} does not expose WAIT | START_INCOME in Growth."
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
        if not {
            "continue",
            "full_withdrawal",
            }.issubset(actions):
            raise ValueError(
                f"{label} does not expose annual CONTINUE | "
                "FULL_WITHDRAWAL in Income."
            )

    joint = str(
        method.get("joint_life_behaviour")
        or method.get("joint_life_election_treatment")
        or ""
    ).lower()
    if expected_election_mode in {"dynamic", "optimal"} and not any(
        marker in joint for marker in ("pathwise", "separate", "cohort")
    ):
        raise ValueError(
            f"{label} does not document separate pathwise Joint-Life status."
        )
    if expected_election_mode == "optimal":
        return _manifest_fit_basis_fingerprint(manifest)
    return None


def _validate_direct_single_sample_policy(
    manifest: Mapping[str, object],
) -> dict[str, object]:
    """Require direct V11 selection under the time-zero customer objective."""
    method = manifest.get("method")
    if not isinstance(method, Mapping):
        raise ValueError("LSMC manifest has no method object.")
    selection_mode = str(method.get("policy_selection_mode", "")).strip()
    sample_semantics = str(method.get("sample_semantics", "")).strip()
    if selection_mode != "direct_single_sample_expected_pv" or (
        sample_semantics != "single_sample_time0_swing"
    ):
        raise ValueError(
            "LSMC manifest does not identify direct single-sample expected-PV "
            "policy selection."
        )
    discount_basis = str(
        method.get("policyholder_objective_discount_basis", "")
    ).strip()
    if discount_basis != "time_zero_australian_zero_curve_deterministic_v1":
        raise ValueError(
            "LSMC customer objective is not discounted with the time-zero "
            "Australian zero curve."
        )
    for field in ("oos_validation_used", "oos_evaluation_used"):
        if field not in method or _as_bool(method[field]):
            raise ValueError(f"LSMC direct policy must record {field}=false.")
    deployed_policy = str(
        method.get("primary_lsmc_deployed_policy", "")
    ).strip()
    if deployed_policy != "V11":
        raise ValueError("Direct customer LSMC must deploy V11 without fallback.")
    if _as_bool(method.get("fixed_policy_substitution_allowed")) or _as_bool(
        method.get("noninferiority_gates_used")
    ):
        raise ValueError("Direct customer LSMC must not use gates or fallback.")
    settings = manifest.get("lsmc_settings")
    if not isinstance(settings, Mapping) or not _as_bool(
        settings.get("all_v11_candidates_structurally_valid")
    ):
        raise ValueError("Direct V11 fit is not structurally valid.")
    return {
        "policy_selection_mode": selection_mode,
        "sample_semantics": sample_semantics,
        "policyholder_objective_discount_basis": discount_basis,
        "oos_validation_used": False,
        "oos_evaluation_used": False,
        "deployed_policy": deployed_policy,
    }


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
    dynamic_benchmark_directories: dict[str, Path] = {}
    dynamic_benchmark_summaries: dict[str, dict[str, str]] = {}
    dynamic_benchmark_rows: dict[str, list[dict[str, str]]] = {}
    dynamic_benchmark_manifests: dict[str, dict[str, object]] = {}
    lsmc_summary = _read_single_csv_row(lsmc_output / "portfolio_summary.csv")
    lsmc_rows = _read_csv(lsmc_output / "model_point_results.csv")
    lsmc_manifest = _read_json(lsmc_output / "run_manifest.json")
    all_lsmc_benchmark_directories = _lsmc_benchmark_directories(lsmc_output)
    lsmc_benchmark_directories = {
        "variable_election_continue": all_lsmc_benchmark_directories[
            "variable_election_continue"
        ]
    }
    election_continue_directory = lsmc_benchmark_directories[
        "variable_election_continue"
    ]
    continue_summary = _read_single_csv_row(
        election_continue_directory / "portfolio_summary.csv"
    )
    continue_rows = _read_csv(
        election_continue_directory / "model_point_results.csv"
    )
    lsmc_benchmark_summaries: dict[str, dict[str, str]] = {
        "variable_election_continue": continue_summary,
    }
    lsmc_benchmark_rows: dict[str, list[dict[str, str]]] = {
        "variable_election_continue": continue_rows,
    }
    runner_manifests = (
        ("Dynamic full policy", dynamic_manifest),
        *(
            (f"Dynamic benchmark {benchmark_id}", manifest)
            for benchmark_id, manifest in dynamic_benchmark_manifests.items()
        ),
        ("LSMC full policy", lsmc_manifest),
    )
    for label, manifest in runner_manifests:
        if _manifest_hedge_cap_leg_mode(manifest) != args.hedge_cap_leg_mode:
            raise ValueError(
                f"{label} hedge-cap-leg mode differs from the requested "
                f"{args.hedge_cap_leg_mode!r}."
            )
    runner_summaries = (
        ("Dynamic full policy", dynamic_summary),
        *(
            (f"Dynamic benchmark {benchmark_id}", summary)
            for benchmark_id, summary in dynamic_benchmark_summaries.items()
        ),
        ("LSMC full policy", lsmc_summary),
        *(
            (f"LSMC benchmark {benchmark_id}", summary)
            for benchmark_id, summary in lsmc_benchmark_summaries.items()
        ),
    )
    for label, summary in runner_summaries:
        if str(summary.get("hedge_cap_leg_mode")) != args.hedge_cap_leg_mode:
            raise ValueError(
                f"{label} summary has a different hedge-cap-leg mode."
            )
        if args.hedge_cap_leg_mode == "sold":
            _require_close(
                _monetary(summary, "pv_hedge_gain_aud"),
                0.0,
                f"{label} sold cap-leg Above-Cap hedge gain",
            )

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
        if not _as_bool(
            valuation_settings.get("force_pathwise_joint_life")
        ):
            raise ValueError(
                f"{label} does not use the common pathwise Joint-Life basis."
            )
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
    lsmc_fit_basis_fingerprint = _manifest_fit_basis_fingerprint(lsmc_manifest)
    direct_policy = _validate_direct_single_sample_policy(lsmc_manifest)
    lsmc_method = lsmc_manifest.get("method")
    if not isinstance(lsmc_method, Mapping):
        raise ValueError("LSMC manifest has no method object.")
    lsmc_training_settings = lsmc_manifest.get("lsmc_settings")
    lsmc_evaluation_settings = lsmc_manifest.get("evaluation_settings")
    if not isinstance(lsmc_training_settings, Mapping) or not isinstance(
        lsmc_evaluation_settings, Mapping
    ):
        raise ValueError(
            "LSMC manifest has incomplete fit/rollout settings."
        )
    action_set = lsmc_method.get("lsmc_action_set")
    if not isinstance(action_set, Mapping):
        raise ValueError("LSMC manifest has no phase-specific Swing action set.")
    growth_actions = _normalised_action_tokens(action_set.get("growth"))
    income_actions = _normalised_action_tokens(action_set.get("income"))
    if not {"wait", "start_income"}.issubset(growth_actions) or not {
        "continue", "full_withdrawal"
    }.issubset(income_actions):
        raise ValueError(
            "LSMC manifest does not expose WAIT/START in Growth and "
            "NORMAL/FULL in Income."
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
        *(
            (f"LSMC benchmark {benchmark_id}", summary)
            for benchmark_id, summary in lsmc_benchmark_summaries.items()
        ),
    ):
        summary_stress = summary.get("stress_scenario_id")
        if summary_stress is not None and str(summary_stress) != expected_stress:
            raise ValueError(
                f"{label} summary stress scenario differs from its manifest."
            )
    evaluation_fingerprints = {
        str(summary.get("scenario_fingerprint", "")).strip()
        for summary in (
            dynamic_summary,
            lsmc_summary,
            *dynamic_benchmark_summaries.values(),
            *lsmc_benchmark_summaries.values(),
        )
    }
    if "" in evaluation_fingerprints or len(evaluation_fingerprints) != 1:
        raise ValueError(
            "Dynamic/LSMC factor arms do not evidence one common evaluation "
            "scenario fingerprint."
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
            raise ValueError(f"Child output has no {label} source path.")
        if Path(str(actual)).expanduser().resolve() != requested.expanduser().resolve():
            raise ValueError(f"Child output has a different {label} source path.")

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
                "Child output has a different dynamic-behaviour directory."
            )

    _validate_reconciliation(
        dynamic_output / "portfolio_aggregation_reconciliation.csv", "Dynamic")
    _validate_reconciliation(
        lsmc_output / "portfolio_aggregation_reconciliation.csv", "LSMC")
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
    for benchmark_id in dynamic_benchmark_summaries:
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
        continue_summary, args=args, rate=rate, expect_lsmc=True,
        label="Variable-Election Continue benchmark")
    for benchmark_id, summary in dynamic_benchmark_summaries.items():
        _validate_summary_settings(
            summary,
            args=args,
            rate=rate,
            expect_lsmc=False,
            label=f"Dynamic benchmark {benchmark_id}",
        )
    expected_lsmc_by_benchmark = {
        "deterministic_election_continue": False,
        "deterministic_election_post_behaviour": True,
        "variable_election_continue": True,
    }
    for benchmark_id, summary in lsmc_benchmark_summaries.items():
        _validate_summary_settings(
            summary,
            args=args,
            rate=rate,
            expect_lsmc=expected_lsmc_by_benchmark[benchmark_id],
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
    direct_policy = _validate_direct_single_sample_policy(lsmc_manifest)
    if _as_bool(lsmc_method.get("dynamic_behaviour_used_for_benchmark")):
        raise ValueError(
            "LSMC scenario unexpectedly contains a duplicate Dynamic benchmark."
        )
    if str(evaluation_settings.get("sample_role", "")).strip() != (
        "same_q_sample_actuarial_rollout"
    ):
        raise ValueError("LSMC rollout is not labelled as a same-Q-sample rollout.")
    scenario_fingerprint = _required_manifest_text(
        dynamic_portfolio.get("scenario_fingerprint"),
        "Dynamic portfolio scenario_fingerprint",
    )
    lsmc_fingerprints = {
        _required_manifest_text(
            lsmc_method.get("scenario_fingerprint"),
            "LSMC method scenario_fingerprint",
        ),
        _required_manifest_text(
            evaluation_settings.get("scenario_fingerprint"),
            "LSMC rollout scenario_fingerprint",
        ),
        _required_manifest_text(
            lsmc_settings.get("scenario_fingerprint"),
            "LSMC fit scenario_fingerprint",
        ),
    }
    if lsmc_fingerprints != {scenario_fingerprint}:
        raise ValueError(
            "Dynamic, LSMC fit and LSMC rollout do not use one common Q sample."
        )
    for benchmark_id, benchmark_manifest in dynamic_benchmark_manifests.items():
        benchmark_portfolio = benchmark_manifest.get("portfolio")
        if not isinstance(benchmark_portfolio, Mapping):
            raise ValueError(
                f"Dynamic benchmark {benchmark_id} has no portfolio metadata."
            )
        if str(
            benchmark_portfolio.get("scenario_fingerprint")
        ) != scenario_fingerprint:
            raise ValueError(
                f"Dynamic benchmark {benchmark_id} changed evaluation paths."
            )
    dynamic_cache_metadata = _validate_dynamic_cache_metadata(
        dynamic_manifest,
        dynamic_summary,
        args,
        rate=rate,
        evaluation_fingerprint=scenario_fingerprint,
    )
    lsmc_cache_metadata = _validate_lsmc_cache_metadata(
        lsmc_manifest,
        lsmc_summary,
        args,
        rate=rate,
        scenario_fingerprint=scenario_fingerprint,
    )
    if dynamic_cache_metadata["market_cache_key"] != (
        lsmc_cache_metadata["market_cache_key"]
    ):
        raise ValueError("Dynamic and LSMC loaded different market caches.")
    if dynamic_cache_metadata["hedge_cache_key"] != (
        lsmc_cache_metadata["hedge_cache_key"]
    ):
        raise ValueError("Dynamic and LSMC loaded different hedge caches.")
    if dynamic_cache_metadata["hedge_price_surface_fingerprint"] != (
        lsmc_cache_metadata["hedge_price_surface_fingerprint"]
    ):
        raise ValueError(
            "Dynamic and LSMC loaded different hedge-price surfaces."
        )
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
    for container, field, expected, label in (
        (evaluation_settings, "take_up_seed", args.train_take_up_seed,
         "LSMC same-sample take-up seed"),
        (evaluation_settings, "mortality_seed", args.train_mortality_seed,
         "LSMC same-sample mortality seed"),
        (lsmc_settings, "train_take_up_seed", args.train_take_up_seed,
         "LSMC training take-up seed"),
        (lsmc_settings, "train_mortality_seed", args.train_mortality_seed,
         "LSMC training mortality seed"),
    ):
        _require_close(
            _as_float(container.get(field), field),
            float(expected),
            label,
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
        _as_float(evaluation_settings.get("n_paths"), "rollout n_paths"),
        float(args.n_train),
        "LSMC same-sample rollout paths",
    )
    _require_close(
        _as_float(evaluation_settings.get("seed"), "rollout seed"),
        float(args.train_seed),
        "LSMC same-sample rollout seed",
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
    ) != scenario_fingerprint:
        raise ValueError("LSMC summary and manifest sample fingerprints differ.")
    _require_close(
        _as_float(lsmc_settings.get("n_folds"), "n_folds"),
        float(args.lsmc_folds),
        "LSMC n_folds",
    )
    if _as_bool(lsmc_method.get("partial_withdrawal_in_optimal_policy")):
        raise ValueError("LSMC Partial Withdrawal must be disabled.")
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
        raise ValueError("Child output has a different cost assumption set.")
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
        raise ValueError("Child output has a different behaviour assumption set.")

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
    _validate_model_point_csm_aggregation(
        dynamic_summary,
        dynamic_rows,
        dynamic_metrics,
        label="Dynamic",
    )
    _validate_model_point_csm_aggregation(
        lsmc_summary,
        lsmc_rows,
        lsmc_metrics,
        label="LSMC",
    )
    _validate_model_point_csm_aggregation(
        continue_summary,
        continue_rows,
        continue_metrics,
        label="LSMC variable-Election Continue benchmark",
    )
    for benchmark_id, metrics in dynamic_benchmark_metrics.items():
        _validate_model_point_csm_aggregation(
            dynamic_benchmark_summaries[benchmark_id],
            dynamic_benchmark_rows[benchmark_id],
            metrics,
            label=f"Dynamic benchmark {benchmark_id}",
        )
    for benchmark_id, metrics in lsmc_benchmark_metrics.items():
        _validate_model_point_csm_aggregation(
            lsmc_benchmark_summaries[benchmark_id],
            lsmc_benchmark_rows[benchmark_id],
            metrics,
            label=f"LSMC benchmark {benchmark_id}",
        )
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
    diagnostic_seed_indices: set[int] = set()
    for diagnostic in diagnostic_rows:
        seed_index = int(_as_float(
            diagnostic.get("training_seed_index"),
            "diagnostic training_seed_index",
        ))
        if seed_index != 1:
            raise ValueError("LSMC regression diagnostic has an unknown seed.")
        diagnostic_seed_indices.add(seed_index)
        if str(diagnostic.get("training_scenario_fingerprint")) != (
            scenario_fingerprint
        ):
            raise ValueError(
                "LSMC regression diagnostics changed a training fingerprint."
            )
        if _as_bool(diagnostic.get("primary_training_seed")) is not (
            seed_index == 1
        ):
            raise ValueError(
                "LSMC regression diagnostic has an inconsistent primary flag."
            )
    if diagnostic_seed_indices != {1}:
        raise ValueError("LSMC diagnostics do not cover the sole fit sample.")
    lsmc_diagnostics = _lsmc_diagnostic_metrics(
        action_rows,
        diagnostic_rows,
        lsmc_manifest,
    )

    row: dict[str, object] = {
        "stress_scenario_id": expected_stress,
        "crediting_cap_rate": rate,
        "crediting_cap_rate_percent": 100.0 * rate,
        "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
        "below_contractual_minimum_crediting_cap": (
            rate < CONTRACTUAL_MINIMUM_CREDITING_CAP_RATE),
        "valuation_basis": dynamic_basis,
        "valuation_currency": dynamic_summary.get("valuation_currency"),
        "premium_aud": dynamic_metrics["premium_aud"],
        "scenario_fingerprint": scenario_fingerprint,
        "hedge_pricing_method": args.hedge_pricing_method,
        "market_cache_key": dynamic_cache_metadata["market_cache_key"],
        "hedge_cache_key": dynamic_cache_metadata["hedge_cache_key"],
        "hedge_price_surface_fingerprint": (
            dynamic_cache_metadata["hedge_price_surface_fingerprint"]
        ),
        "dynamic_manifest_require_market_cache_flag_present": (
            dynamic_cache_metadata["require_market_cache_flag_present"]
        ),
        "dynamic_manifest_require_hedge_cache_flag_present": (
            dynamic_cache_metadata["require_hedge_cache_flag_present"]
        ),
        "lsmc_manifest_require_market_cache_flag_present": (
            lsmc_cache_metadata["require_market_cache_flag_present"]
        ),
        "lsmc_manifest_require_hedge_cache_flag_present": (
            lsmc_cache_metadata["require_hedge_cache_flag_present"]
        ),
        "sample_role": "training_and_valuation",
        "sample_n_paths": args.n_train,
        "sample_market_seed": args.train_seed,
        "sample_take_up_seed": args.train_take_up_seed,
        "sample_mortality_seed": args.train_mortality_seed,
        "lsmc_income_action_set": args.lsmc_income_action_set,
        "lsmc_policy_selection_mode": direct_policy["policy_selection_mode"],
        "lsmc_sample_semantics": direct_policy["sample_semantics"],
        "lsmc_policyholder_objective_discount_basis": direct_policy[
            "policyholder_objective_discount_basis"
        ],
        "lsmc_oos_validation_used": False,
        "lsmc_oos_evaluation_used": False,
        "lsmc_deployed_policy": direct_policy["deployed_policy"],
        "lsmc_fixed_policy_fallback_used": False,
        "lsmc_time0_customer_expected_pv_aud": _as_float(
            lsmc_summary.get("lsmc_time0_customer_expected_pv_aud"),
            "LSMC time-zero customer expected PV",
        ),
        "lsmc_time0_customer_no_action_pv_aud": _as_float(
            lsmc_summary.get("lsmc_time0_customer_no_action_pv_aud"),
            "LSMC time-zero customer no-action PV",
        ),
        "lsmc_time0_customer_optionality_uplift_aud": _as_float(
            lsmc_summary.get("lsmc_time0_customer_optionality_uplift_aud"),
            "LSMC time-zero customer optionality uplift",
        ),
        "lsmc_fit_basis_fingerprint": lsmc_fit_basis_fingerprint,
        "source_metadata_fingerprint": source_metadata_fingerprint,
        "engine_version": dynamic_engine_version,
        "dynamic_scenario_directory": str(dynamic_output),
        "lsmc_scenario_directory": str(lsmc_output),
    }
    for method, metrics in (
        ("dynamic", dynamic_metrics),
        ("lsmc", lsmc_metrics),
    ):
        row.update({f"{method}_{key}": value for key, value in metrics.items()})
    row.update({
        f"dynamic_{key}": value for key, value in dynamic_mp_risk.items()
    })
    row.update({f"lsmc_{key}": value for key, value in lsmc_mp_risk.items()})
    row.update({
        f"lsmc_{key}": value for key, value in lsmc_diagnostics.items()
    })

    comparable_metrics = (
        *MONETARY_METRICS,
        "csm_aud",
        "csm_pv_fee_income_aud",
        "csm_pv_other_income_aud",
        "csm_pv_claims_aud",
        "csm_pv_costs_aud",
        "csm_reconciliation_gap_aud",
        "csm_to_premium",
        "new_business_margin_before_risk_margin",
        "guarantee_claims_to_premium",
        "guarantee_value_to_premium",
        "bel_nonunit_to_premium",
        "bel_total_to_premium",
        "future_fees_to_premium",
        "crediting_margin_to_premium",
        "money_market_income_to_premium",
        "hedge_gain_to_premium",
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

    premium = float(row["premium_aud"])
    behaviour_risk = float(dynamic_metrics["csm_aud"]) - float(
        lsmc_metrics["csm_aud"]
    )
    row.update({
        # Positive means the fitted LSMC scenario is adverse to the insurer.
        "behaviour_model_csm_gap_aud": behaviour_risk,
        "behaviour_model_csm_gap_to_premium": _safe_ratio(
            behaviour_risk, premium),
        # Backward-compatible aliases; the canonical measure is CSM.
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
    })
    return row, _paired_model_point_rows(
        rate, dynamic_rows, lsmc_rows)


CORE_BASELINE_FIELDS = (
    "dynamic_pv_guarantee_claims_aud",
    "lsmc_pv_guarantee_claims_aud",
    "dynamic_guarantee_value_aud",
    "lsmc_guarantee_value_aud",
    "dynamic_pv_future_fees_aud",
    "lsmc_pv_future_fees_aud",
    "dynamic_pv_money_market_income_aud",
    "lsmc_pv_money_market_income_aud",
    "dynamic_pv_hedge_gain_aud",
    "lsmc_pv_hedge_gain_aud",
    "dynamic_pv_hedge_costs_aud",
    "lsmc_pv_hedge_costs_aud",
    "dynamic_pv_hedge_option_fair_value_costs_aud",
    "lsmc_pv_hedge_option_fair_value_costs_aud",
    "dynamic_pv_hedge_option_markup_costs_aud",
    "lsmc_pv_hedge_option_markup_costs_aud",
    "dynamic_pv_hedge_management_fee_costs_aud",
    "lsmc_pv_hedge_management_fee_costs_aud",
    "dynamic_pv_hedge_execution_costs_aud",
    "lsmc_pv_hedge_execution_costs_aud",
    "dynamic_bel_total_aud",
    "lsmc_bel_total_aud",
    "dynamic_csm_aud",
    "lsmc_csm_aud",
    "dynamic_csm_pv_fee_income_aud",
    "lsmc_csm_pv_fee_income_aud",
    "dynamic_csm_pv_other_income_aud",
    "lsmc_csm_pv_other_income_aud",
    "dynamic_csm_pv_claims_aud",
    "lsmc_csm_pv_claims_aud",
    "dynamic_csm_pv_costs_aud",
    "lsmc_csm_pv_costs_aud",
    "dynamic_csm_reconciliation_gap_aud",
    "lsmc_csm_reconciliation_gap_aud",
    "dynamic_insurer_net_present_value_before_risk_margin_aud",
    "lsmc_insurer_net_present_value_before_risk_margin_aud",
    "dynamic_new_business_margin_before_risk_margin",
    "lsmc_new_business_margin_before_risk_margin",
    "dynamic_negative_value_contract_share",
    "lsmc_negative_value_contract_share",
    "behaviour_model_csm_gap_aud",
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
    ("pv_money_market_income_aud", "AUD", "lower_is_adverse"),
    ("pv_hedge_gain_aud", "AUD", "lower_is_adverse"),
    ("pv_growth_fees_aud", "AUD", "diagnostic"),
    ("pv_growth_crediting_margin_aud", "AUD", "diagnostic"),
    ("pv_post_election_guarantee_claims_aud", "AUD", "higher_is_adverse"),
    ("pv_expenses_aud", "AUD", "higher_is_adverse"),
    ("pv_hedge_costs_aud", "AUD", "higher_is_adverse"),
    ("pv_hedge_option_fair_value_costs_aud", "AUD", "higher_is_adverse"),
    ("pv_hedge_option_markup_costs_aud", "AUD", "higher_is_adverse"),
    ("pv_hedge_management_fee_costs_aud", "AUD", "higher_is_adverse"),
    ("pv_hedge_execution_costs_aud", "AUD", "higher_is_adverse"),
    ("bel_nonunit_aud", "AUD", "higher_is_adverse"),
    ("bel_total_aud", "AUD", "higher_is_adverse"),
    ("csm_aud", "AUD", "lower_is_adverse"),
    ("csm_pv_fee_income_aud", "AUD", "lower_is_adverse"),
    ("csm_pv_other_income_aud", "AUD", "lower_is_adverse"),
    ("csm_pv_claims_aud", "AUD", "higher_is_adverse"),
    ("csm_pv_costs_aud", "AUD", "higher_is_adverse"),
    ("csm_reconciliation_gap_aud", "AUD", "diagnostic"),
    ("csm_to_premium", "ratio", "lower_is_adverse"),
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
    ("money_market_income_to_premium", "ratio", "lower_is_adverse"),
    ("hedge_gain_to_premium", "ratio", "lower_is_adverse"),
    ("claims_to_future_fees", "ratio", "higher_is_adverse"),
    ("fee_coverage_ratio", "ratio", "lower_is_adverse"),
    ("income_start_year_mean", "years", "diagnostic"),
    ("income_start_year_median", "years", "diagnostic"),
    ("income_start_year_p10", "years", "diagnostic"),
    ("income_start_year_p90", "years", "diagnostic"),
    ("income_election_share", "ratio", "diagnostic"),
    ("forced_income_election_share", "ratio", "diagnostic"),
    ("mean_growth_duration", "years", "diagnostic"),
    ("growth_phase_exposure", "ratio", "diagnostic"),
    ("income_phase_exposure", "ratio", "diagnostic"),
    ("ordinary_income_lapse_rate", "ratio", "diagnostic"),
    ("performance_income_lapse_rate", "ratio", "diagnostic"),
    ("total_income_lapse_rate", "ratio", "diagnostic"),
)

MODEL_POINT_SENSITIVITY_METRICS = (
    ("negative_value_contract_share", "ratio", "higher_is_adverse"),
    (
        "model_point_csm_to_premium_weighted_p10",
        "ratio",
        "lower_is_adverse",
    ),
    (
        "model_point_csm_to_premium_weighted_lower_tail_mean_10pct",
        "ratio",
        "lower_is_adverse",
    ),
    ("guarantee_claims_hhi", "index", "diagnostic"),
    ("top_5_guarantee_claim_share", "ratio", "diagnostic"),
    ("joint_life_guarantee_claim_share", "ratio", "diagnostic"),
)

BEHAVIOUR_SENSITIVITY_METRICS = (
    (
        "behaviour_model_csm_gap_aud",
        "AUD",
        "higher_is_adverse",
    ),
    (
        "behaviour_model_csm_gap_to_premium",
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
        "lsmc_unweighted_income_election_action_rate",
        "ratio",
        "diagnostic",
    ),
    (
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
    for method in ("dynamic", "lsmc"):
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
        ("hedge_pricing_method", "hedge-pricing method"),
        ("market_cache_key", "market cache"),
        ("scenario_fingerprint", "common fit/valuation scenario set"),
        ("sample_role", "sample role"),
        ("sample_n_paths", "sample path count"),
        ("sample_market_seed", "sample market seed"),
        ("sample_take_up_seed", "sample take-up seed"),
        ("sample_mortality_seed", "sample mortality seed"),
        ("lsmc_policy_selection_mode", "LSMC selection mode"),
        (
            "lsmc_policyholder_objective_discount_basis",
            "LSMC customer discount basis",
        ),
        ("lsmc_deployed_policy", "direct LSMC policy"),
        ("source_metadata_fingerprint", "source inputs"),
        ("engine_version", "engine version"),
    )
    for field, description in checks:
        if len({str(row[field]) for row in rows}) != 1:
            raise ValueError(f"{label} does not share one {description}.")
    if any(
        not _as_bool(row["dynamic_manifest_require_market_cache_flag_present"])
        for row in rows
    ):
        raise ValueError(f"{label} lacks Dynamic market-cache requirement evidence.")
    pricing_method = str(rows[0]["hedge_pricing_method"])
    if pricing_method == "mc_conditional":
        hedge_keys = {
            _required_manifest_text(
                row["hedge_cache_key"],
                f"{label} hedge-cache key",
            )
            for row in rows
        }
        surface_fingerprints = {
            _required_manifest_text(
                row["hedge_price_surface_fingerprint"],
                f"{label} hedge-price surface fingerprint",
            )
            for row in rows
        }
        if len(hedge_keys) != len(rows) or len(surface_fingerprints) != len(rows):
            raise ValueError(
                f"{label} reused a hedge cache across distinct crediting caps."
            )
        if any(
            not _as_bool(row[
                "dynamic_manifest_require_hedge_cache_flag_present"
            ])
            for row in rows
        ):
            raise ValueError(f"{label} lacks Dynamic hedge-cache requirement evidence.")
    elif pricing_method == "moment_matched_bs":
        if any(
            not _none_like(row["hedge_cache_key"])
            or not _none_like(row["hedge_price_surface_fingerprint"])
            for row in rows
        ):
            raise ValueError(f"{label} mixes moment matching with hedge-cache data.")
    else:
        raise ValueError(f"{label} has unknown hedge-pricing method {pricing_method!r}.")
    fit_fingerprints = {
        str(row["lsmc_fit_basis_fingerprint"]) for row in rows
    }
    if len(fit_fingerprints) != len(rows):
        raise ValueError(
            f"{label} reused an LSMC fit basis across different caps; every "
            "cap/stress combination must be refitted."
        )
    for row in rows:
        if (
            str(row["sample_role"]) != "training_and_valuation"
            or str(row["lsmc_deployed_policy"]) != "V11"
            or _as_bool(row["lsmc_oos_validation_used"])
            or _as_bool(row["lsmc_oos_evaluation_used"])
            or _as_bool(row["lsmc_fixed_policy_fallback_used"])
        ):
            raise ValueError(
                f"{label} violates direct single-sample V11 semantics."
            )


STRESS_DELTA_METRICS = (
    "csm_aud",
    "csm_pv_fee_income_aud",
    "csm_pv_other_income_aud",
    "csm_pv_claims_aud",
    "csm_pv_costs_aud",
    "csm_reconciliation_gap_aud",
    "bel_nonunit_aud",
    "pv_guarantee_claims_aud",
    "pv_future_fees_aud",
    "pv_policyholder_benefits_aud",
    "pv_expenses_aud",
    "pv_hedge_costs_aud",
    "pv_money_market_income_aud",
    "pv_hedge_gain_aud",
    "pv_hedge_option_fair_value_costs_aud",
    "pv_hedge_option_markup_costs_aud",
    "pv_hedge_management_fee_costs_aud",
    "pv_hedge_execution_costs_aud",
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
            "base_scenario_fingerprint": base["scenario_fingerprint"],
            "stress_scenario_fingerprint": stressed["scenario_fingerprint"],
            "lsmc_deployed_policy": stressed["lsmc_deployed_policy"],
            "lsmc_policy_selection_mode": stressed[
                "lsmc_policy_selection_mode"
            ],
            "lsmc_policyholder_objective_discount_basis": stressed[
                "lsmc_policyholder_objective_discount_basis"
            ],
            "lsmc_oos_validation_used": stressed["lsmc_oos_validation_used"],
            "lsmc_oos_evaluation_used": stressed["lsmc_oos_evaluation_used"],
            "lsmc_time0_customer_optionality_uplift_aud": stressed[
                "lsmc_time0_customer_optionality_uplift_aud"
            ],
            "lsmc_regression_accepted_share": stressed[
                "lsmc_regression_accepted_share"],
            "lsmc_training_fallback_policy_share": stressed[
                "lsmc_training_fallback_policy_share"],
            "dynamic_stress_scenario_directory": stressed[
                "dynamic_scenario_directory"],
            "lsmc_stress_scenario_directory": stressed[
                "lsmc_scenario_directory"],
        }
        for method in ("dynamic", "lsmc"):
            csm_field = f"{method}_csm_aud"
            base_csm = float(base[csm_field])
            stress_csm = float(stressed[csm_field])
            signed_loss = base_csm - stress_csm
            row[f"{method}_base_csm_aud"] = base_csm
            row[f"{method}_stress_csm_aud"] = stress_csm
            row[f"{method}_signed_csm_stress_loss_aud"] = signed_loss
            row[f"{method}_adverse_csm_stress_loss_aud"] = max(
                0.0, signed_loss
            )
            row[f"{method}_signed_csm_stress_loss_bp_of_premium"] = (
                10_000.0 * signed_loss / premium
            )
            row[f"{method}_adverse_csm_stress_loss_bp_of_premium"] = (
                10_000.0 * max(0.0, signed_loss) / premium
            )
            # Backward-compatible aliases; CSM is now the canonical measure.
            row[f"{method}_base_insurer_npv_aud"] = base_csm
            row[f"{method}_stress_insurer_npv_aud"] = stress_csm
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
        dynamic_loss = float(row["dynamic_signed_csm_stress_loss_aud"])
        lsmc_loss = float(row["lsmc_signed_csm_stress_loss_aud"])
        row["lsmc_minus_dynamic_signed_csm_stress_loss_aud"] = (
            lsmc_loss - dynamic_loss
        )
        row[
            "lsmc_minus_dynamic_signed_csm_stress_loss_bp_of_premium"
        ] = 10_000.0 * (lsmc_loss - dynamic_loss) / premium
        # Backward-compatible aliases.
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
        for method in ("dynamic", "lsmc"):
            field = f"{method}_signed_csm_stress_loss_aud"
            values = [float(row[field]) for row in group]
            baseline_value = values[baseline_index]
            for index, row in enumerate(group):
                change, lower, upper, scheme = _finite_difference_per_100bp(
                    rates, values, index)
                csm_change = values[index] - baseline_value
                row[
                    f"{method}_signed_csm_stress_loss_change_vs_baseline_cap_aud"
                ] = csm_change
                row[f"{method}_signed_stress_loss_change_vs_baseline_cap_aud"] = (
                    csm_change
                )
                row[f"{method}_stress_loss_cap_finite_difference_scheme"] = scheme
                row[f"{method}_stress_loss_cap_fd_lower_rate"] = lower
                row[f"{method}_stress_loss_cap_fd_upper_rate"] = upper
                row[f"{method}_stress_loss_change_per_100bp_cap_aud"] = change
                row[f"{method}_csm_stress_loss_cap_finite_difference_scheme"] = (
                    scheme
                )
                row[f"{method}_csm_stress_loss_cap_fd_lower_rate"] = lower
                row[f"{method}_csm_stress_loss_cap_fd_upper_rate"] = upper
                row[f"{method}_csm_stress_loss_change_per_100bp_cap_aud"] = (
                    change
                )
                csm_change_bp = (
                    None
                    if change is None
                    else 10_000.0 * change / float(row["premium_aud"])
                )
                row[
                    f"{method}_stress_loss_change_per_100bp_cap_bp_of_premium"
                ] = csm_change_bp
                row[
                    f"{method}_csm_stress_loss_change_per_100bp_cap_bp_of_premium"
                ] = csm_change_bp
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


def _lsmc_deployment_plot_label(rows: list[dict[str, object]]) -> str:
    """Describe the directly fitted single-sample Swing policy."""
    base = "Direct single-sample customer LSMC"
    if not rows:
        return base
    deployed_policies = {
        str(row.get("lsmc_deployed_policy", "unknown"))
        for row in rows
    }
    if deployed_policies == {"V11"}:
        return f"{base} (direct V11)"
    return f"{base} ({', '.join(sorted(deployed_policies))})"


def _create_plots(
    rows: list[dict[str, object]],
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
        "lsmc": _lsmc_deployment_plot_label(rows),
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
        (axes[1, 0], "csm_to_premium", 100.0,
         "Simplified CSM / Premium", "%"),
        (axes[1, 1], "fee_coverage_ratio", 1.0,
         "Future Fees / Claims and Costs", "ratio"),
        (axes[1, 2], "hedge_costs_to_premium", 100.0,
         "Total Hedge Costs / Premium", "%"),
    )
    for axis, field, scale, title, ylabel in panels:
        plot_method_lines(
            axis, field, scale=scale,
            zero_line=field in {
                "guarantee_value_to_premium",
                "bel_nonunit_to_premium",
                "csm_to_premium",
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

    fig, axes = plt.subplots(2, 4, figsize=(18.0, 9.0), sharex=True)
    behaviour_panels = (
        (axes[0, 0], "income_start_year_mean", 1.0,
         "Mean Income start year", "policy year"),
        (axes[0, 1], "income_start_year_median", 1.0,
         "Median Income start year", "policy year"),
        (axes[0, 2], "income_election_share", 100.0,
         "Income-Election share", "%"),
        (axes[0, 3], "forced_income_election_share", 100.0,
         "Forced Election share", "%"),
        (axes[1, 0], "mean_growth_duration", 1.0,
         "Mean Growth duration", "years"),
        (axes[1, 1], "ordinary_income_lapse_rate", 100.0,
         "Ordinary Income lapse rate", "%"),
        (axes[1, 2], "performance_income_lapse_rate", 100.0,
         "Performance Income lapse rate", "%"),
        (axes[1, 3], "total_income_lapse_rate", 100.0,
         "Total Income lapse / Full Withdrawal rate", "%"),
    )
    for axis, field, scale, title, ylabel in behaviour_panels:
        plot_method_lines(axis, field, scale=scale)
        axis.set_title(title, loc="left")
        axis.set_ylabel(ylabel)
    axes[0, 0].legend()
    for axis in axes[1, :]:
        axis.set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
    fig.suptitle(
        "Income-Election timing and post-Election behaviour by crediting cap"
    )
    behaviour_path = output / "02_income_election_behaviour_by_crediting_cap.png"
    finish(fig, behaviour_path)
    figure_paths["income_election_behaviour"] = str(behaviour_path)

    fig, axes = plt.subplots(2, 3, figsize=(15.0, 9.0), sharex=True)
    phase_value_panels = (
        (axes[0, 0], "pv_policyholder_benefits_pre_election_aud",
         "Policyholder benefits before Election"),
        (axes[0, 1], "pv_policyholder_benefits_post_election_aud",
         "Policyholder benefits after Election"),
        (axes[0, 2], "pv_growth_fees_aud", "Growth-phase fees"),
        (axes[1, 0], "pv_growth_crediting_margin_aud",
         "Growth-phase crediting margin"),
        (axes[1, 1], "pv_post_election_guarantee_claims_aud",
         "Post-Election guarantee claims"),
    )
    for axis, field, title in phase_value_panels:
        plot_method_lines(axis, field, zero_line="margin" in field)
        axis.set_title(title, loc="left")
        axis.set_ylabel("AUD")
        axis.yaxis.set_major_formatter(FuncFormatter(_aud_axis))
    phase_axis = axes[1, 2]
    for method in ("dynamic", "lsmc"):
        for phase, linestyle in (("growth", "-"), ("income", "--")):
            phase_axis.plot(
                caps,
                [
                    100.0 * float(row[f"{method}_{phase}_phase_exposure"])
                    for row in rows
                ],
                marker="o",
                linewidth=2.0,
                linestyle=linestyle,
                color=colours[method],
                label=f"{labels[method]} / {phase.title()}",
            )
    phase_axis.axvline(baseline_percent, color="#9ca3af", linestyle="--")
    phase_axis.set_title("Growth/Income phase exposure", loc="left")
    phase_axis.set_ylabel("% of projection horizon")
    phase_axis.grid(alpha=0.25)
    phase_axis.legend(fontsize=8)
    axes[0, 0].legend()
    for axis in axes[1, :]:
        axis.set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
    fig.suptitle("Phase-specific valuation exposures by crediting cap")
    phase_path = output / "03_phase_value_exposures_by_crediting_cap.png"
    finish(fig, phase_path)
    figure_paths["phase_value_exposures"] = str(phase_path)

    policy_years = sorted({
        int(match.group(1))
        for row in rows
        for key in row
        for match in [re.match(
            r"^(?:dynamic|lsmc)_(?:income_election_share|growth_phase_share)_policy_year_(\d+)$",
            str(key),
        )]
        if match is not None
    })
    if policy_years:
        fig, axes = plt.subplots(
            2, 2, figsize=(15.0, 9.5), sharex=True, sharey="col"
        )
        for method_index, method in enumerate(("dynamic", "lsmc")):
            for bucket_index, (bucket, title) in enumerate((
                ("income_election_share", "Income Elections by policy year"),
                ("growth_phase_share", "Growth-phase exposure by policy year"),
            )):
                axis = axes[method_index, bucket_index]
                for row in rows:
                    cap = float(row["crediting_cap_rate_percent"])
                    linewidth = (
                        2.8 if _rate_key(cap / 100.0) == _rate_key(baseline_rate)
                        else 1.6
                    )
                    axis.plot(
                        policy_years,
                        [
                            100.0 * float(row.get(
                                f"{method}_{bucket}_policy_year_{year}",
                                math.nan,
                            ))
                            for year in policy_years
                        ],
                        marker="o",
                        linewidth=linewidth,
                        label=f"{cap:.2f}% cap",
                    )
                axis.set_title(f"{labels[method]} — {title}", loc="left")
                axis.set_xlabel("policy year")
                axis.set_ylabel("%")
                axis.grid(alpha=0.25)
            axes[method_index, 0].legend(fontsize=8, ncol=2)
        fig.suptitle("Policy-year Behaviour profile across crediting caps")
        policy_year_path = output / "04_policy_year_behaviour_profile.png"
        finish(fig, policy_year_path)
        figure_paths["policy_year_behaviour_profile"] = str(policy_year_path)

    fig, axes = plt.subplots(2, 3, figsize=(15.5, 9.0), sharex=True)
    profitability_panels = (
        (
            axes[0, 0], "csm_aud",
            "Simplified contractual service margin (CSM)", True,
        ),
        (axes[0, 1], "pv_future_fees_aud", "Future fee income", False),
        (axes[1, 0], "pv_guarantee_claims_aud", "Guarantee claims", False),
        (
            axes[1, 1], "pv_hedge_costs_aud",
            "Total call-spread / hedge costs", False,
        ),
    )
    for axis, field, title, zero_line in profitability_panels:
        plot_method_lines(axis, field, zero_line=zero_line)
        axis.set_title(title, loc="left")
        axis.set_ylabel("AUD")
        axis.yaxis.set_major_formatter(FuncFormatter(_aud_axis))

    other_income_axis = axes[0, 2]
    for method in ("dynamic", "lsmc"):
        other_income_axis.plot(
            caps,
            [
                float(row[f"{method}_csm_pv_other_income_aud"])
                for row in rows
            ],
            marker="o",
            linewidth=2.0,
            color=colours[method],
            label=labels[method],
        )
    other_income_axis.axvline(
        baseline_percent, color="#9ca3af", linestyle="--"
    )
    other_income_axis.set_title(
        "CSM other income (backing, hedge gain, MVA/APS)", loc="left"
    )
    other_income_axis.set_ylabel("AUD")
    other_income_axis.yaxis.set_major_formatter(FuncFormatter(_aud_axis))
    other_income_axis.grid(alpha=0.25)

    gap_axis = axes[1, 2]
    behaviour_gaps = [
        float(row["dynamic_csm_aud"]) - float(row["lsmc_csm_aud"])
        for row in rows
    ]
    gap_axis.bar(caps, behaviour_gaps, width=0.55, color="#bb3e03")
    gap_axis.axhline(0.0, color="#1f2937", linewidth=0.8)
    gap_axis.axvline(baseline_percent, color="#9ca3af", linestyle="--")
    gap_axis.set_title(
        "CSM behaviour-model gap (Dynamic minus LSMC)", loc="left"
    )
    gap_axis.set_ylabel("AUD; positive = LSMC more adverse")
    gap_axis.yaxis.set_major_formatter(FuncFormatter(_aud_axis))
    gap_axis.grid(axis="y", alpha=0.25)

    axes[0, 0].legend()
    for axis in axes[1, :]:
        axis.set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
    fig.suptitle(
        "Simplified CSM and reconciled value drivers by crediting cap"
    )
    profitability_path = (
        output / "05_csm_and_value_drivers_by_crediting_cap.png"
    )
    finish(fig, profitability_path)
    figure_paths["csm_and_value_drivers"] = str(profitability_path)

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.0), sharex=True)
    model_point_panels = (
        (
            axes[0, 0], "negative_value_contract_share", 100.0,
            "Contract share in negative-value segments", "%",
        ),
        (
            axes[0, 1],
            "model_point_csm_to_premium_weighted_lower_tail_mean_10pct", 100.0,
            "Lowest 10% contract-weighted segment CSM / premium", "%",
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
            zero_line="csm" in field,
        )
        axis.set_title(title, loc="left")
        axis.set_ylabel(ylabel)
    axes[0, 0].legend()
    for axis in axes[1, :]:
        axis.set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
    fig.suptitle(
        "Model-point heterogeneity and concentration (not a pathwise VaR/CTE)"
    )
    model_point_path = output / "07_model_point_risk_by_crediting_cap.png"
    finish(fig, model_point_path)
    figure_paths["model_point_risk"] = str(model_point_path)

    fig, axes = plt.subplots(2, 4, figsize=(18.0, 9.0), sharex=True)
    quality_panels = (
        (
            axes[0, 0], "lsmc_election_regression_accepted_share", 100.0,
            "Accepted Election regressions", "%",
        ),
        (
            axes[0, 1], "lsmc_surrender_regression_accepted_share", 100.0,
            "Accepted Full-Withdrawal regressions", "%",
        ),
        (
            axes[0, 2], "lsmc_election_oof_r_squared_median", 1.0,
            "Election median out-of-fold R-squared", "R-squared",
        ),
        (
            axes[0, 3], "lsmc_surrender_oof_r_squared_median", 1.0,
            "Withdrawal median out-of-fold R-squared", "R-squared",
        ),
        (
            axes[1, 0], "lsmc_unweighted_income_election_action_rate", 100.0,
            "Unweighted Election action rate", "%",
        ),
        (
            axes[1, 1], "lsmc_unweighted_full_withdrawal_action_rate", 100.0,
            "Unweighted Full-Withdrawal action rate", "%",
        ),
        (
            axes[1, 2], "lsmc_training_fallback_policy_share", 100.0,
            "Training fallback policy share", "%",
        ),
        (
            axes[1, 3], "lsmc_condition_number_max", 1.0,
            "Maximum regression condition number", "condition number",
        ),
    )
    for axis, field, scale, title, ylabel in quality_panels:
        axis.plot(
            caps,
            [
                math.nan
                if row.get(field) is None
                else scale * float(row[field])
                for row in rows
            ],
            marker="o",
            linewidth=2.0,
            color="#bb3e03",
        )
        axis.axvline(baseline_percent, color="#9ca3af", linestyle="--")
        axis.set_title(title, loc="left")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)
    if all(
        row.get("lsmc_condition_number_max") is not None
        and float(row["lsmc_condition_number_max"]) > 0.0
        for row in rows
    ):
        axes[1, 3].set_yscale("log")
    for axis in axes[1, :]:
        axis.set_xlabel("Scenario Maximum Return / Crediting Cap (%)")
    fig.suptitle("LSMC model-risk diagnostics by crediting cap")
    quality_path = output / "08_lsmc_model_risk_diagnostics.png"
    finish(fig, quality_path)
    figure_paths["lsmc_model_risk_diagnostics"] = str(quality_path)

    if stress_rows:
        stress_method_labels = {
            **labels,
            "lsmc": _lsmc_deployment_plot_label(stress_rows),
        }
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
                            f"{method}_signed_csm_stress_loss_bp_of_premium"
                        ])
                        for row in group
                    ],
                    marker="o",
                    linewidth=2.0,
                    color=colours[method],
                    label=stress_method_labels[method],
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
        stress_path = output / "09_stress_loss_by_crediting_cap.png"
        finish(fig, stress_path)
        figure_paths["stress_loss_by_crediting_cap"] = str(stress_path)

        cap_labels = [f"{cap:.2f}%" for cap in caps]
        stress_labels = [
            str(STRESS_DEFINITIONS[stress_id]["label"])
            for stress_id in selected_stresses
        ]
        fields = (
            ("dynamic_signed_csm_stress_loss_bp_of_premium", "Dynamic"),
            (
                "lsmc_signed_csm_stress_loss_bp_of_premium",
                "Deployed LSMC policy",
            ),
            (
                "lsmc_minus_dynamic_signed_csm_stress_loss_bp_of_premium",
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
                label="signed CSM stress loss (bp premium)",
                shrink=0.85,
            )
        fig.suptitle("Risk-driver / crediting-cap stress-loss heatmap")
        heatmap_path = output / "10_stress_loss_heatmap.png"
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
        "absolute portfolio values"
        if basis == "absolute_portfolio"
        else "normalised weighted average values per representative contract"
    )
    lines = [
        "# GMLB/GMWB Portfolio Risk, Cap and Behaviour Analysis",
        "",
        (
            "The analysis compares a path-dependent statistical Dynamic policy "
            "with the directly fitted LSMC V11 policy on the same Q sample. "
            "There is no separate OOS test. Income Election remains "
            "annual under both approaches. Voluntary Income actions are decided "
            "monthly under the Dynamic policy, but only on crediting anniversaries "
            "under the LSMC policy. Both approaches model Income Election "
            "endogenously; after Election, Income lapse and Full Withdrawal are "
            "treated separately from the Growth phase. The input labelled "
            "Crediting Rate is technically the Scenario Maximum Return, or "
            "Crediting Cap, on the complete CSV-configured reference-fund return: "
            "`min(max(R_fund, 0), Cap)`. Only 6% is the contractual basis; other "
            "values are non-contractual design sensitivities. All other product "
            "parameters remain fixed, and the variants are not repriced to be "
            "budget-neutral."
        ),
        (
            "A symmetric one-factor shock-and-revalue grid is also evaluated for "
            "Dynamic and LSMC; the LSMC policy is refitted and valued on the same "
            "exact Q sample for each stress-and-cap combination."
            if stress_rows
            else "The explicit shock-and-revalue grid was skipped by option."
        ),
        "",
        f"Valuation basis: **{monetary_description}**. All runs use "
        "Heston-Hull-White under Q and common random numbers.",
        (
            "Hedge prices come from the exact path-congruent Conditional-MC "
            "hedge-price cache."
            if baseline["hedge_pricing_method"] == "mc_conditional"
            else "Hedge prices use the explicitly selected moment-matched "
            "Black-Scholes fallback as a proxy; no Conditional-MC hedge-price "
            "valuation is available."
        ),
        (
            "Income-Election distributions and phase exposures are aggregated "
            "using model-point/contract weight, Q-path probability and pathwise "
            "in-force/survival weight. The separately reported LSMC action rates, "
            "by contrast, are unweighted fit diagnostics across eligible decision "
            "points."
        ),
        "",
        "## Execution",
        "",
        (
            f"For {worker_plan.pending_job_count} scenario pairs, "
            f"{worker_plan.selected_workers} workers were selected (conservative "
            f"automatic value: {worker_plan.safe_auto_workers}). "
            + (
                "Base and stress cases share a single worker queue; "
                if stress_rows
                else "the queue contains base cases only; "
            )
            + "Dynamic and LSMC run sequentially within each scenario pair."
        ),
        (
            "RAM planning estimates a peak of "
            f"{_format_gib(worker_plan.estimated_worker_bytes)} per worker for a "
            f"projection horizon of {worker_plan.estimated_horizon_months} months; "
            f"{_format_gib(worker_plan.available_memory_bytes)} was available at "
            f"planning time. Each child uses "
            f"{worker_plan.blas_threads_per_child} BLAS/OpenMP thread(s). The RAM "
            "estimate is a conservative planning heuristic, not a hard memory "
            "guarantee."
        ),
        *(
            [
                "",
                (
                    "> **Execution warning:** The configured worker count exceeds "
                    "the conservative automatic value and may exceed available "
                    "memory."
                ),
            ]
            if worker_plan.configured_workers_exceed_safe_auto
            else []
        ),
        "",
        "## Core Results by Crediting Cap",
        "",
        (
            "| Cap | Guarantee Claims Dynamic | Guarantee Claims LSMC | "
            "CSM Dynamic | CSM LSMC | Direct LSMC policy | "
            "Behaviour-Model Gap | Time-zero customer optionality uplift |"
        ),
        "|---:|---:|---:|---:|---:|:---|---:|:---:|",
    ]
    for row in rows:
        lines.append(
            f"| {float(row['crediting_cap_rate_percent']):.2f}% | "
            f"{_format_money(float(row['dynamic_pv_guarantee_claims_aud']))} | "
            f"{_format_money(float(row['lsmc_pv_guarantee_claims_aud']))} | "
            f"{_format_money(float(row['dynamic_csm_aud']))} | "
            f"{_format_money(float(row['lsmc_csm_aud']))} | "
            f"{row['lsmc_deployed_policy']} | "
            f"{_format_money(float(row['behaviour_model_csm_gap_aud']))} | "
            f"{_format_money(float(row['lsmc_time0_customer_optionality_uplift_aud']))} |"
        )

    lines.extend([
        "",
        "## CSM Components and Reconciliation",
        "",
        (
            "`CSM = PV(Fee Income) + PV(Other Income) − PV(Claims) − PV(Costs)`. "
            "Other Income includes Crediting Margin (Money Market plus Hedge Gain) "
            "and retained MVA/APS amounts; Costs include Expenses and call-spread/"
            "hedge costs."
        ),
        "",
        (
            "| Cap / Ansatz | Fee Income | Other Income | Claims | Costs | CSM | "
            "Reconciliation Gap |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        for method, method_label in (("dynamic", "Dynamic"), ("lsmc", "LSMC")):
            lines.append(
                f"| {float(row['crediting_cap_rate_percent']):.2f}% / {method_label} | "
                f"{_format_money(float(row[f'{method}_csm_pv_fee_income_aud']))} | "
                f"{_format_money(float(row[f'{method}_csm_pv_other_income_aud']))} | "
                f"{_format_money(float(row[f'{method}_csm_pv_claims_aud']))} | "
                f"{_format_money(float(row[f'{method}_csm_pv_costs_aud']))} | "
                f"{_format_money(float(row[f'{method}_csm_aud']))} | "
                f"{_format_money(float(row[f'{method}_csm_reconciliation_gap_aud']))} |"
            )

    lines.extend([
        "",
        "## Insurer Backing and Hedge Costs",
        "",
        (
            "The administrative balance earns only the stochastic AUD overnight "
            "return; the customer liability remains separate from reference-fund "
            "backing. Hedge cap-leg mode: `"
            f"{baseline['hedge_cap_leg_mode']}`."
        ),
        "",
        (
            "| Cap / Ansatz | Money-Market | Hedge Gain | Fair Option | "
            "Purchase Markup | Management Fee | Legacy Execution | Total Hedge |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        for method, method_label in (("dynamic", "Dynamic"), ("lsmc", "LSMC")):
            lines.append(
                f"| {float(row['crediting_cap_rate_percent']):.2f}% / {method_label} | "
                f"{_format_money(float(row[f'{method}_pv_money_market_income_aud']))} | "
                f"{_format_money(float(row[f'{method}_pv_hedge_gain_aud']))} | "
                f"{_format_money(float(row[f'{method}_pv_hedge_option_fair_value_costs_aud']))} | "
                f"{_format_money(float(row[f'{method}_pv_hedge_option_markup_costs_aud']))} | "
                f"{_format_money(float(row[f'{method}_pv_hedge_management_fee_costs_aud']))} | "
                f"{_format_money(float(row[f'{method}_pv_hedge_execution_costs_aud']))} | "
                f"{_format_money(float(row[f'{method}_pv_hedge_costs_aud']))} |"
            )

    lines.extend([
        "",
        "## Income-Election and Phase Profile",
        "",
        (
            "| Cap / Ansatz | Start mean | median | p10 | p90 | Election | "
            "Forced share | Growth duration | Growth exposure | "
            "Income exposure | Total Income lapse |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        for method, method_label in (("dynamic", "Dynamic"), ("lsmc", "LSMC")):
            lines.append(
                f"| {float(row['crediting_cap_rate_percent']):.2f}% / {method_label} | "
                f"{float(row[f'{method}_income_start_year_mean']):.3f} | "
                f"{float(row[f'{method}_income_start_year_median']):.3f} | "
                f"{float(row[f'{method}_income_start_year_p10']):.3f} | "
                f"{float(row[f'{method}_income_start_year_p90']):.3f} | "
                f"{100.0 * float(row[f'{method}_income_election_share']):.3f}% | "
                f"{100.0 * float(row[f'{method}_forced_income_election_share']):.3f}% | "
                f"{float(row[f'{method}_mean_growth_duration']):.3f} | "
                f"{100.0 * float(row[f'{method}_growth_phase_exposure']):.3f}% | "
                f"{100.0 * float(row[f'{method}_income_phase_exposure']):.3f}% | "
                f"{100.0 * float(row[f'{method}_total_income_lapse_rate']):.3f}% |"
            )

    lines.extend([
        "",
        "### LSMC Action and Regression Diagnostics",
        "",
        (
            "| Cap | Election action (unweighted) | Full Withdrawal action "
            "(unweighted) | Election regressions accepted | "
            "Full regressions accepted |"
        ),
        "|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        lines.append(
            f"| {float(row['crediting_cap_rate_percent']):.2f}% | "
            f"{100.0 * float(row['lsmc_unweighted_income_election_action_rate']):.3f}% | "
            f"{100.0 * float(row['lsmc_unweighted_full_withdrawal_action_rate']):.3f}% | "
            f"{100.0 * float(row['lsmc_election_regression_accepted_share']):.3f}% | "
            f"{100.0 * float(row['lsmc_surrender_regression_accepted_share']):.3f}% |"
        )

    below_minimum_caps = [
        float(row["crediting_cap_rate_percent"])
        for row in rows
        if bool(row["below_contractual_minimum_crediting_cap"])
    ]
    if below_minimum_caps:
        lines.extend([
            "",
            (
                "> **Contract-boundary warning:** Caps below the contractual "
                "minimum of 0.25% were evaluated as purely technical "
                "sensitivities: "
                + ", ".join(f"{cap:.4f}%" for cap in below_minimum_caps)
                + "."
            ),
        ])

    lines.extend([
        "",
        f"## Risk Profile at the {100.0 * baseline_rate:.2f}% Base Cap",
        "",
        "| Metric | Dynamic | LSMC |",
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
            "| CSM / Premium | "
            f"{100.0 * float(baseline['dynamic_csm_to_premium']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_csm_to_premium']):.3f}% |"
        ),
        (
            "| Contract share in segments classified as negative | "
            f"{100.0 * float(baseline['dynamic_negative_value_contract_share']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_negative_value_contract_share']):.3f}% |"
        ),
        (
            "| Mean CSM/Premium in the lowest 10% contract/segment tail | "
            f"{100.0 * float(baseline['dynamic_model_point_csm_to_premium_weighted_lower_tail_mean_10pct']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_model_point_csm_to_premium_weighted_lower_tail_mean_10pct']):.3f}% |"
        ),
        "",
        (
            "The lower segment tail measures heterogeneity across representative "
            "contracts. It is neither a pathwise loss distribution nor VaR/CTE."
        ),
        (
            "The negative classification uses the configured materiality of "
            f"{float(baseline['dynamic_profitability_materiality_bp']):.3f} bp. "
            "HHI and top-five shares depend on model-point segmentation and are "
            "not measures of systematic-risk diversification."
        ),
        (
            "Metric identities should not be read as independent risks: canonical "
            "CSM agrees with legacy Insurer NPV before Risk Margin and equals "
            "− Non-unit BEL; Net Guarantee Value = Guarantee Claims − LIP Fees. "
            "The Fee Coverage metric is "
            "`Future Fees / (Guarantee Claims + Expenses + Total Hedge Costs)` "
            "and deliberately excludes Crediting Margin and MVA/APS retention."
        ),
    ])

    lines.extend([
        "",
        "## Phase Values and Income Lapse at the Base Cap",
        "",
        "| Metric | Dynamic | LSMC |",
        "|---|---:|---:|",
        (
            "| PV Policyholder Benefits before Election | "
            f"{_format_money(float(baseline['dynamic_pv_policyholder_benefits_pre_election_aud']))} | "
            f"{_format_money(float(baseline['lsmc_pv_policyholder_benefits_pre_election_aud']))} |"
        ),
        (
            "| PV Policyholder Benefits after Election | "
            f"{_format_money(float(baseline['dynamic_pv_policyholder_benefits_post_election_aud']))} | "
            f"{_format_money(float(baseline['lsmc_pv_policyholder_benefits_post_election_aud']))} |"
        ),
        (
            "| PV Growth-Phase Fees | "
            f"{_format_money(float(baseline['dynamic_pv_growth_fees_aud']))} | "
            f"{_format_money(float(baseline['lsmc_pv_growth_fees_aud']))} |"
        ),
        (
            "| PV Growth-Phase Crediting Margin | "
            f"{_format_money(float(baseline['dynamic_pv_growth_crediting_margin_aud']))} | "
            f"{_format_money(float(baseline['lsmc_pv_growth_crediting_margin_aud']))} |"
        ),
        (
            "| PV Post-Election Guarantee Claims | "
            f"{_format_money(float(baseline['dynamic_pv_post_election_guarantee_claims_aud']))} | "
            f"{_format_money(float(baseline['lsmc_pv_post_election_guarantee_claims_aud']))} |"
        ),
        (
            "| Ordinary Income-Lapse-Rate | "
            f"{100.0 * float(baseline['dynamic_ordinary_income_lapse_rate']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_ordinary_income_lapse_rate']):.3f}% |"
        ),
        (
            "| Performance Income-Lapse-Rate | "
            f"{100.0 * float(baseline['dynamic_performance_income_lapse_rate']):.3f}% | "
            f"{100.0 * float(baseline['lsmc_performance_income_lapse_rate']):.3f}% |"
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
            f"## One-Factor Stress Losses at the {100.0 * baseline_rate:.2f}% Base Cap",
            "",
            (
                "`Signed Stress Loss = CSM_base − CSM_stress`; positive values "
                "are adverse. The table reports basis points of premium. "
                "`LSMC − Dynamic` measures the behaviour-model amplification of "
                "each fully reoptimised stress."
            ),
            "",
            "| One-factor stress | Dynamic signed | LSMC signed | LSMC adverse | "
            "LSMC − Dynamic | Direct LSMC policy | Time-zero optionality uplift |",
            "|---|---:|---:|---:|---:|:---|---:|",
        ])
        for stress in baseline_stresses:
            lines.append(
                f"| {stress['stress_label']} | "
                f"{float(stress['dynamic_signed_csm_stress_loss_bp_of_premium']):.3f} bp | "
                f"{float(stress['lsmc_signed_csm_stress_loss_bp_of_premium']):.3f} bp | "
                f"{float(stress['lsmc_adverse_csm_stress_loss_bp_of_premium']):.3f} bp | "
                f"{float(stress['lsmc_minus_dynamic_signed_csm_stress_loss_bp_of_premium']):.3f} bp | "
                f"{stress['lsmc_deployed_policy']} | "
                f"{_format_money(float(stress['lsmc_time0_customer_optionality_uplift_aud']))} |"
            )
        lines.extend([
            "",
            (
                "Each selected one-factor stress is shown separately; neither the "
                "maximum is selected automatically nor is a correlation aggregation "
                "to a regulatory capital amount performed. The complete effect of "
                "the cap on each stress loss is available in the stress CSV."
            ),
        ])

    lines.extend([
        "",
        "## Cap Secant on the Scenario Grid at the Base Point",
        "",
        (
            "The change per +100 bp is not an infinitesimal sensitivity. It is "
            "calculated across the adjacent cap scenarios reported in the table; "
            "because of cap non-linearity and LSMC refitting, it may differ from a "
            "symmetric bump at the base point."
        ),
        "",
        "| Method | Metric | Secant interval | Change per +100 bp |",
        "|---|---|---:|---:|",
    ])
    wanted = {
        ("dynamic", "pv_guarantee_claims_aud"),
        ("lsmc", "pv_guarantee_claims_aud"),
        ("dynamic", "csm_aud"),
        ("lsmc", "csm_aud"),
        ("behaviour_difference", "behaviour_model_csm_gap_aud"),
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
        "## Interpreting the Behaviour Comparison",
        "",
        (
            "`Behaviour-Model Gap = Dynamic CSM − LSMC CSM`. A positive value "
            "means that the fitted LSMC approach is more adverse for the insurer. "
            "The LSMC policy maximises the time-zero-curve-discounted expected "
            "present value of customer cashflows under Q; it optimises neither "
            "insurer profit nor risk capital."
        ),
        "",
        (
            "The delta compares two complete behaviour approaches: path-dependent "
            "statistical Income Election plus monthly post-Election lapse/withdrawal "
            "assumptions on one side, and a jointly fitted LSMC policy on the other. "
            "In the Growth phase, LSMC chooses between WAIT and "
            "START_NORMAL_INCOME; in the Income phase, it chooses between receiving "
            "NORMAL_INCOME and FULL_SURRENDER on crediting anniversaries. It "
            "should therefore not be read as "
            "the isolated effect of a single rate."
        ),
        "",
        (
            "Income-Election decisions occur on policy anniversaries. Dynamic "
            "voluntary Income actions occur monthly, whereas LSMC chooses only on "
            "crediting anniversaries. Surviving contracts that have not "
            "yet elected start no later than the first policy anniversary after age "
            "100 is reached. Joint-Life contracts use pathwise separate Primary and "
            "Spouse life states."
        ),
        "",
        (
            "Only the complete Dynamic V11 policy and the directly fitted LSMC "
            "V11 policy are reported; no validation gate or fixed-policy fallback "
            "is used. "
            "V00/V01/V10 and the decomposition into Election, post-Election and "
            "interaction effects are omitted. Raw Election and Full-Withdrawal "
            "action rates are unweighted across model-point/path/decision events "
            "and are not portfolio-weighted take-up or surrender rates."
        ),
        "",
        "## Model Limitations",
        "",
        (
            "- The runners retain expected Q present values and model-point "
            "scalars, but not pathwise portfolio losses. Therefore, neither "
            "VaR/TVaR/CTE nor Cashflow-at-Risk is calculated."
        ),
        (
            "- The selected one-factor shocks are individual research stresses. "
            "They are neither calibrated best-estimate forecasts nor an APRA/"
            "LAGIC or Solvency II capital aggregation."
            if stress_rows
            else "- One-factor shock-and-revalue stresses were skipped in this run."
        ),
        (
            "- The equity-level stress scales the simulated equity indices by 39% "
            "from month one. The t=0 account of duration-zero new business is not "
            "shocked like a unit-linked spot holding."
            if any(
                row["stress_scenario_id"] == "equity_level_down"
                for row in stress_rows
            )
            else "- No equity-level stress result is available."
        ),
        (
            "- Lapse risk is assessed through the complete Dynamic V11 policy and "
            "the actually deployed LSMC policy. A symmetric statistical lapse/"
            "take-up/withdrawal shock is not applied to LSMC because its phase-"
            "specific joint action set replaces those statistical functions."
        ),
        (
            "- Common random numbers reduce comparison noise but do not replace "
            "Monte Carlo standard errors or repetitions across seeds. The same "
            "sample is intentionally used for fit and reported customer value; "
            "there is no OOS performance claim."
        ),
        (
            "- The LSMC policy is fitted on one Q sample with annual "
            "WAIT/START_NORMAL_INCOME in Growth and annual "
            "NORMAL_INCOME/FULL_SURRENDER in Income; Partial Withdrawal is "
            "excluded from the optimal action set."
        ),
        (
            "- The valuation is before Risk Margin and gross of reinsurance. "
            "Mortality is illustrative and not calibrated for production use."
        ),
        (
            "- The five-year government-bond proxy, monthly rebalancing, missing "
            "bond term premium and other fixed proxy assumptions remain unchanged."
        ),
    ])
    if figure_paths:
        lines.extend(["", "## Figures", ""])
        lines.extend(
            f"- `{Path(figure).name}`" for figure in figure_paths.values()
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    run_started = time.perf_counter()
    model_points_path = args.model_points.expanduser().resolve()
    model_point_ids = _model_point_ids(model_points_path)
    if len(model_point_ids) != 1:
        raise ValueError(
            "Customer-LSMC risk analyses require exactly one model point; "
            f"received {len(model_point_ids)} from {model_points_path}."
        )
    output_root, output, run_id, run_created_at_utc = (
        _create_timestamped_run_directory(args.output)
    )
    log_to_console(f"RUN START | ID {run_id} | Output: {output}")
    rates = sorted({
        _rate_key(rate)
        for rate in (*args.crediting_rates, args.baseline_rate)
    })
    rate_directories = {_rate_directory_name(rate) for rate in rates}
    if len(rate_directories) != len(rates):
        raise ValueError("Crediting-cap rates map to non-unique scenario paths.")
    log_to_console(
        "CAPS | "
        + ", ".join(f"{100.0 * rate:.2f}%" for rate in rates)
        + f" | comparison basis {100.0 * args.baseline_rate:.2f}%"
    )
    log_to_console(
        "BEHAVIOUR | Per scenario, retain Dynamic V11 and direct single-sample "
        "LSMC V11; no OOS gate, fixed fallback or V00/V01/V10 decomposition."
    )
    log_to_console(
        f"MODEL POINTS | {len(model_point_ids)} used | "
        f"IDs: {', '.join(model_point_ids)} | input: {model_points_path}"
    )
    log_to_console(
        "COMPUTATION SCOPE | "
        f"one shared sample with {args.n_train} paths and market seed "
        f"{args.train_seed} for Dynamic comparison, LSMC fit and LSMC rollout."
    )

    all_jobs: list[ScenarioJob] = []
    base_jobs: list[ScenarioJob] = []
    stress_jobs_by_id: dict[str, list[ScenarioJob]] = {
        stress_id: [] for stress_id in args.stress_scenarios
    }
    commands: list[dict[str, object]] = []
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
        job = ScenarioJob(
            sequence=sequence,
            stress_id="base",
            rate=rate,
            dynamic_output=dynamic_output,
            lsmc_output=lsmc_output,
            dynamic_command=tuple(dynamic_command),
            dynamic_benchmark_commands=dynamic_benchmark_commands,
            lsmc_command=tuple(lsmc_command),
        )
        base_jobs.append(job)
        all_jobs.append(job)
        commands.append({
            "job_sequence": sequence,
            "stress_scenario_id": "base",
            "crediting_cap_rate": rate,
            "execution_mode": "executed_in_immutable_run_directory",
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
                job = ScenarioJob(
                    sequence=sequence,
                    stress_id=stress_id,
                    rate=rate,
                    dynamic_output=dynamic_output,
                    lsmc_output=lsmc_output,
                    dynamic_command=tuple(dynamic_command),
                    dynamic_benchmark_commands=dynamic_benchmark_commands,
                    lsmc_command=tuple(lsmc_command),
                )
                stress_jobs_by_id[stress_id].append(job)
                all_jobs.append(job)
                commands.append({
                    "job_sequence": sequence,
                    "stress_scenario_id": stress_id,
                    "crediting_cap_rate": rate,
                    "execution_mode": "executed_in_immutable_run_directory",
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

    _validate_windows_output_path_lengths(
        all_jobs,
        include_plots=args.scenario_plots,
    )
    worker_plan = _resolve_worker_plan(args, all_jobs)
    cache_precompute_jobs = _cache_precompute_jobs(
        args,
        all_jobs,
        horizon_years=worker_plan.estimated_horizon_months / 12.0,
        output=output,
    )
    if (
        cache_precompute_jobs
        and worker_plan.horizon_estimation_source.startswith("fallback_")
    ):
        raise ValueError(
            "The exact lifetime horizon required for cache precomputation "
            "could not be resolved from the model-point input: "
            f"{worker_plan.horizon_estimation_source}"
        )
    cache_precompute_commands = [
        {
            "sequence": job.sequence,
            "market_stress": job.market_stress,
            "sample_role": job.sample_role,
            "n_paths": job.n_paths,
            "seed": job.seed,
            "horizon_years": worker_plan.estimated_horizon_months / 12.0,
            "crediting_cap_rate": (
                None if "--market-only" in job.command else job.cap_rate
            ),
            "command": list(job.command),
            "orchestrator_log": str(
                job.output / "orchestrator_console.log"
            ),
        }
        for job in cache_precompute_jobs
    ]
    base_pending_count = len(base_jobs)
    stress_pending_count = sum(
        len(stress_jobs_by_id[stress_id]) for stress_id in args.stress_scenarios
    )
    parallel_execution_used = (
        worker_plan.selected_workers > 1
        and worker_plan.pending_job_count > 1
    )
    log_to_console(
        "Worker plan: "
        f"{worker_plan.selected_workers} selected "
        f"(safe auto {worker_plan.safe_auto_workers}, "
        f"{worker_plan.logical_cpu_count} logical CPUs, "
        f"available RAM {_format_gib(worker_plan.available_memory_bytes)}, "
        f"estimated peak {_format_gib(worker_plan.estimated_worker_bytes)} "
        "per worker)."
    )
    log_to_console(
        "RUN-PLAN | "
        f"{len(all_jobs)} cap/stress scenarios, "
        f"{2 * worker_plan.pending_job_count} new V11 child runs, "
        f"{len(cache_precompute_jobs)} cache-precompute calls, "
        f"stresses {'enabled' if not args.no_stress_analysis else 'disabled'}, "
        f"plots {'enabled' if not args.no_plots else 'disabled'}, "
        f"heartbeat every {int(CHILD_HEARTBEAT_SECONDS)} seconds."
    )
    if (
        worker_plan.available_memory_bytes is None
        and worker_plan.pending_job_count > 0
        and args.max_workers is None
    ):
        log_to_console(
            "Available RAM could not be detected; automatic mode "
            "uses one worker.",
            level="WARNING",
        )
    if (
        worker_plan.single_worker_estimate_exceeds_budget
        and worker_plan.pending_job_count > 0
        and args.max_workers is None
    ):
        log_to_console(
            "No worker fits inside the conservative automatic RAM "
            "budget. The script retains the serial one-worker fallback; close "
            "other applications or reduce path counts if memory is tight.",
            level="WARNING",
        )
    if worker_plan.configured_workers_exceed_safe_auto:
        log_to_console(
            "Configured --max-workers exceeds the conservative "
            "automatic worker count and may exhaust RAM. Use --max-workers "
            "auto to enable RAM-gated scheduling.",
            level="WARNING",
        )

    # The sole authorised writer first validates or creates every exact cache
    # input.  Valuation children start only after this phase succeeds.
    _run_cache_precompute_jobs(
        cache_precompute_jobs,
        blas_threads=args.blas_threads,
    )

    # Base and opt-in stress scenarios are independent.  A single queue also
    # keeps explicitly requested multi-cell grids efficient when callers raise
    # the worker count above the reduced serial default.
    _run_pending_jobs(all_jobs, worker_plan, phase_label="valuation grid")
    log_to_console(
        "VALIDATION START | Checking runner manifests, input fingerprints, "
        "aggregation reconciliations and LSMC gates."
    )
    validated_results_by_sequence: dict[
        int,
        tuple[dict[str, object], list[dict[str, object]]],
    ] = {}
    cell_validation_failures: list[str] = []
    for validation_index, job in enumerate(all_jobs, start=1):
        log_to_console(
            f"VALIDATION {validation_index}/{len(all_jobs)} START | "
            f"{job.label}"
        )
        try:
            validated_results_by_sequence[job.sequence] = _load_scenario_result(
                args,
                job.rate,
                job.dynamic_output,
                job.lsmc_output,
                expected_stress=job.stress_id,
            )
        except (OSError, ValueError, TypeError, KeyError, csv.Error) as exc:
            cell_validation_failures.append(
                f"{job.label}: {type(exc).__name__}: "
                + " ".join(str(exc).split())
            )
        else:
            log_to_console(
                f"VALIDATION {validation_index}/{len(all_jobs)} OK | "
                f"{job.label}"
            )
    if cell_validation_failures:
        raise RuntimeError(
            "One or more scenario cells failed validation; no aggregate "
            "report was created:\n" + "\n".join(cell_validation_failures)
        )
    log_to_console("VALIDATION COMPLETE | All scenarios are consistent.")

    rows: list[dict[str, object]] = []
    model_point_rows: list[dict[str, object]] = []
    for index, job in enumerate(base_jobs, start=1):
        log_to_console(
            f"COLLECT BASE RESULT {index}/{len(base_jobs)} | {job.label}"
        )
        scenario_row, scenario_model_points = validated_results_by_sequence[
            job.sequence
        ]
        rows.append(scenario_row)
        model_point_rows.extend(scenario_model_points)

    _validate_scenario_grid(rows, label="base crediting-cap grid")
    bases = {str(row["valuation_basis"]) for row in rows}
    scenario_fingerprints = {
        str(row["scenario_fingerprint"]) for row in rows
    }
    market_cache_keys = {
        str(row["market_cache_key"]) for row in rows
    }
    hedge_cache_keys_by_rate = {
        _rate_key(float(row["crediting_cap_rate"])): row["hedge_cache_key"]
        for row in rows
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
                log_to_console(
                    f"COLLECT STRESS RESULT {index}/{len(stress_group_jobs)} | "
                    f"{job.label}"
                )
                stress_row, _stress_model_points = (
                    validated_results_by_sequence[job.sequence]
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
            stress_scenario_fingerprints = {
                str(row["scenario_fingerprint"])
                for row in stress_group
            }
            stress_market_cache_keys = {
                str(row["market_cache_key"])
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
                if stress_scenario_fingerprints == scenario_fingerprints:
                    raise ValueError(
                        f"Market stress {stress_id!r} did not change scenarios."
                    )
                if stress_market_cache_keys == market_cache_keys:
                    raise ValueError(
                        f"Market stress {stress_id!r} reused the base market cache."
                    )
            elif stress_scenario_fingerprints != scenario_fingerprints:
                raise ValueError(
                    f"Non-market stress {stress_id!r} unexpectedly changed scenarios."
                )
            elif stress_market_cache_keys != market_cache_keys:
                raise ValueError(
                    f"Non-market stress {stress_id!r} changed the market cache."
                )
            if args.require_hedge_cache:
                for stress_row in stress_group:
                    rate_key = _rate_key(float(stress_row["crediting_cap_rate"]))
                    base_hedge_key = hedge_cache_keys_by_rate[rate_key]
                    stress_hedge_key = stress_row["hedge_cache_key"]
                    if stress_id in market_path_stresses:
                        if stress_hedge_key == base_hedge_key:
                            raise ValueError(
                                f"Market stress {stress_id!r} reused the base "
                                "hedge-price cache."
                            )
                    elif stress_hedge_key != base_hedge_key:
                        raise ValueError(
                            f"Non-market stress {stress_id!r} changed the "
                            "hedge-price cache."
                        )

    all_fit_rows = [*rows, *stressed_scenario_rows]
    all_fit_fingerprints = {
        str(row["lsmc_fit_basis_fingerprint"]) for row in all_fit_rows
    }
    if len(all_fit_fingerprints) != len(all_fit_rows):
        raise ValueError(
            "An LSMC Joint-Policy fit basis was reused across distinct "
            "cap/stress cells. Every cell must be refitted independently."
        )

    log_to_console(
        "AGGREGATION START | V11 comparison, cap sensitivities, model-point "
        "concentration and optional stress losses."
    )
    _add_baseline_deltas(rows, args.baseline_rate)
    sensitivity_rows = _build_sensitivity_rows(rows, args.baseline_rate)
    stress_loss_rows = _build_stress_loss_rows(
        rows,
        stressed_scenario_rows,
        args.baseline_rate,
    )
    risk_csv = output / "portfolio_risk_by_crediting_cap.csv"
    sensitivity_csv = output / "crediting_cap_risk_sensitivities.csv"
    model_point_csv = output / "model_point_behaviour_model_gap.csv"
    stress_csv = output / "portfolio_stress_losses_by_crediting_cap.csv"
    report_path = output / "portfolio_risk_report.md"
    manifest_path = output / "analysis_manifest.json"
    log_to_console(f"OUTPUT START | Writing result files to {output}.")
    _write_csv(risk_csv, rows)
    _write_csv(sensitivity_csv, sensitivity_rows)
    _write_csv(model_point_csv, model_point_rows)
    if stress_loss_rows:
        _write_csv(stress_csv, stress_loss_rows)

    figure_paths: dict[str, str] = {}
    matplotlib_version: Optional[str] = None
    if not args.no_plots:
        figure_paths, matplotlib_version = _create_plots(
            rows,
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

    effective_risk_scope = ["lapse"]
    if not args.no_stress_analysis:
        for stress_id in args.stress_scenarios:
            risk_category = str(STRESS_DEFINITIONS[stress_id]["risk_category"])
            if risk_category not in effective_risk_scope:
                effective_risk_scope.append(risk_category)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "run_created_at_utc": run_created_at_utc,
        "output_root": str(output_root),
        "run_directory": str(output),
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
            "hedge_pricing_method": args.hedge_pricing_method,
            "hedge_pricing_interpretation": (
                "exact_path_congruent_conditional_mc_hedge_price_cache"
                if args.hedge_pricing_method == "mc_conditional"
                else "explicit_moment_matched_black_scholes_fallback_proxy"
            ),
            "dynamic_behaviour": (
                "path_dependent_statistical_income_election_then_dynamic_"
                "post_election_lapse_and_withdrawal"
            ),
            "lsmc_behaviour": (
                "direct_single_sample_time0_expected_pv_swing_policy"
            ),
            "policy_selection_mode": "direct_single_sample_expected_pv",
            "sample_semantics": "single_sample_time0_swing",
            "policyholder_objective_discount_basis": (
                "time_zero_australian_zero_curve_deterministic_v1"
            ),
            "oos_validation_used": False,
            "oos_evaluation_used": False,
            "income_election_action_set": ["WAIT", "START_NORMAL_INCOME"],
            "post_income_action_set": ["NORMAL_INCOME", "FULL_SURRENDER"],
            "behaviour_decision_grid": {
                "dynamic": {
                    "income_election": "policy_anniversaries",
                    "income_actions": "monthly",
                },
                "lsmc": {
                    "income_election": "crediting_anniversaries",
                    "income_actions": "crediting_anniversaries",
                },
            },
            "minimum_income_start": "contractual_minimum_start_rule",
            "forced_income_start": (
                "first_policy_anniversary_after_primary_attains_age_100"
            ),
            "joint_life_behaviour": (
                "pathwise_separate_primary_and_spouse_life_status"
            ),
            "insurer_backing_asset": (
                "administrative_crediting_frame_in_stochastic_aud_"
                "overnight_money_market_account"
            ),
            "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
            "hedge_cap_leg_interpretation": (
                "short_cap_call_sold"
                if args.hedge_cap_leg_mode == "sold"
                else "cap_call_not_sold_and_excess_payoff_retained"
            ),
            "money_market_accrual": (
                "pathwise_integrated_short_rate_daily_roll_equivalent_on_"
                "monthly_cashflow_grid"
            ),
            "customer_liability_uses_performance_fund_as_backing": False,
            "behaviour_arms_retained": {
                "dynamic_v11": (
                    "dynamic Election; dynamic post-Election behaviour"
                ),
                "lsmc_deployed_policy": (
                    "direct V11 fit; no validation gate or fixed fallback"
                ),
            },
            "lsmc_direct_policy_by_cell": {
                (
                    f"{row['stress_scenario_id']}|"
                    f"{float(row['crediting_cap_rate_percent']):.8f}%"
                ): row["lsmc_deployed_policy"]
                for row in all_fit_rows
            },
            "counterfactual_v00_v01_v10_dynamic_runs": False,
            "behaviour_effect_decomposition_calculated": False,
            "lsmc_policy_refitted_for_every_crediting_cap": True,
            "lsmc_policy_refitted_for_every_stress_and_crediting_cap": (
                not args.no_stress_analysis),
            "common_random_numbers_across_methods_and_caps": True,
            "scenario_pairs_executed_in_parallel": parallel_execution_used,
            "base_and_stress_jobs_share_one_execution_queue": (
                not args.no_stress_analysis
            ),
            "runner_pair_execution_order": "dynamic_then_lsmc",
            "behaviour_models_compared": list(DEFAULT_BEHAVIOUR_MODELS),
            "separate_dynamic_full_policy_run_required": True,
            "lsmc_internal_dynamic_benchmark_disabled_to_avoid_duplicate": True,
            "lsmc_internal_v10_continue_descriptive_comparator_retained": True,
            "lsmc_v00_v01_factorial_outputs_disabled": True,
            "parallel_schedule_changes_random_seeds": False,
            "one_factor_shock_and_revalue": not args.no_stress_analysis,
            "default_risk_scope": list(DEFAULT_RISK_SCOPE),
            "effective_risk_scope": effective_risk_scope,
            "lapse_risk_assessment": (
                "full_policy_dynamic_v11_vs_direct_single_sample_lsmc_v11"
            ),
            "stress_losses_are_not_regulatory_capital_aggregation": True,
            "portfolio_tail_distribution_calculated": False,
        },
        "settings": {
            "sample_role": "training_and_valuation",
            "n_paths": args.n_train,
            "market_seed": args.train_seed,
            "take_up_seed": args.train_take_up_seed,
            "mortality_seed": args.train_mortality_seed,
            "heston_substeps": args.heston_substeps,
            "hedge_pricing_method": args.hedge_pricing_method,
            "market_cache_root": str(
                args.market_cache_root.expanduser().resolve()
            ),
            "hedge_cache_root": str(
                args.hedge_cache_root.expanduser().resolve()
            ),
            "require_market_cache": args.require_market_cache,
            "require_hedge_cache": args.require_hedge_cache,
            "cache_precompute_call_count": len(cache_precompute_jobs),
            "cache_horizon_years": (
                worker_plan.estimated_horizon_months / 12.0
            ),
            "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
            "lsmc_folds": args.lsmc_folds,
            "lsmc_income_action_set": args.lsmc_income_action_set,
            "lsmc_ridge": args.lsmc_ridge,
            "exercise_buffer_rmse_multiplier": (
                args.exercise_buffer_rmse_multiplier),
            "portfolio_contract_count": args.portfolio_contract_count,
            "model_points": {
                "source_path": str(model_points_path),
                "count": len(model_point_ids),
                "ids": list(model_point_ids),
            },
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
            "q_cache_precompute_runner": str(Q_CACHE_PRECOMPUTE_RUNNER),
            "q_cache_precompute_commands": cache_precompute_commands,
            "common_fit_and_valuation_scenario_fingerprint": next(
                iter(scenario_fingerprints)),
            "common_source_metadata_fingerprint": next(
                iter(source_fingerprints)),
            "common_engine_version": next(iter(engine_versions)),
            "one_common_sample_per_cell": True,
            "oos_validation_used": False,
            "oos_evaluation_used": False,
            "validation_gate_used": False,
            "fixed_policy_fallback_used": False,
            "all_cells_deploy_direct_v11": all(
                str(row["lsmc_deployed_policy"]) == "V11"
                for row in all_fit_rows
            ),
            "aggregation_reconciliations_checked": True,
            "csm_component_reconciliation_checked": True,
            "csm_model_point_to_portfolio_aggregation_checked": True,
            "model_point_alignment_checked": True,
            "source_identifiers_checked": True,
            "child_hedge_pricing_method_checked": True,
            "child_common_sample_fingerprints_checked": True,
            "child_market_cache_keys_checked_where_emitted": True,
            "child_hedge_cache_keys_and_surface_fingerprints_checked": (
                args.require_hedge_cache
            ),
            "dynamic_child_cache_requirement_flags_and_roots_checked": True,
            "lsmc_child_cache_requirement_flags_and_roots_checked": (
                "where_emitted_by_child_schema"
            ),
            "stress_application_checked_in_runner_manifests": (
                not args.no_stress_analysis),
            "joint_policy_fit_basis_unique_per_cap_stress_cell": True,
            "lsmc_fit_basis_fingerprints_by_cell": {
                (
                    f"{row['stress_scenario_id']}|"
                    f"{float(row['crediting_cap_rate_percent']):.8f}%"
                ): row["lsmc_fit_basis_fingerprint"]
                for row in all_fit_rows
            },
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
                "csm",
                "csm_fee_income",
                "csm_other_income",
                "csm_claims",
                "csm_costs",
                "csm_reconciliation_gap",
                "future_fees",
                "crediting_margin",
                "money_market_income",
                "retained_excess_performance_hedge_gain",
                "expenses",
                "fair_option_package_cost",
                "option_purchase_markup_cost",
                "hedge_reference_management_fee_cost",
                "legacy_hedge_execution_proxy",
                "legacy_insurer_npv_before_risk_margin_reconciled_to_csm",
                "new_business_margin_before_risk_margin",
            ],
            "policyholder_behaviour": [
                "behaviour_model_csm_gap_dynamic_minus_lsmc",
                "lsmc_guarantee_claim_difference",
                "income_start_year_mean_median_p10_p90",
                "income_election_and_forced_election_share",
                "mean_growth_duration_and_phase_exposures",
                "ordinary_performance_and_total_income_lapse_rates",
                "unweighted_lsmc_income_election_action_rate",
                "unweighted_lsmc_full_withdrawal_action_rate",
                "lsmc_time0_customer_expected_pv",
                "lsmc_time0_customer_optionality_uplift",
                "policy_year_income_election_and_growth_phase_buckets",
            ],
            "model_point_concentration": [
                "negative_value_contract_share",
                "contract_weighted_lower_10pct_model_point_csm_to_premium",
                "guarantee_claim_hhi",
                "top_5_guarantee_claim_share",
                "joint_life_guarantee_claim_share",
            ],
            "shock_and_revalue": (
                []
                if args.no_stress_analysis
                else [
                    "signed_csm_stress_loss",
                    "adverse_csm_stress_loss",
                    "stress_delta_nonunit_bel",
                    "stress_delta_guarantee_claims",
                    "stress_delta_future_fees",
                    "stress_delta_policyholder_benefits",
                    "lsmc_minus_dynamic_stress_loss_amplification",
                    "csm_stress_loss_change_per_100bp_crediting_cap",
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
            (
                "Conditional-MC hedge prices are loaded from exact path-congruent caches."
                if args.hedge_pricing_method == "mc_conditional"
                else "Hedge prices use the explicitly selected moment-matched Black-Scholes fallback proxy, not Conditional MC."
            ),
            "No pathwise portfolio loss distribution; no VaR, TVaR or CTE.",
            "One common Q sample is used for LSMC fit and reported customer value; there is no OOS validation claim or repeated-seed confidence interval.",
            (
                "One-factor research stresses are not an APRA/LAGIC or Solvency-II capital aggregation."
                if stress_loss_rows
                else "The explicit shock-and-revalue grid was skipped for this run."
            ),
            "Lapse risk is assessed through complete Dynamic V11 versus direct single-sample LSMC V11; no validation gate, fixed-policy fallback, V00/V01/V10 effect decomposition or symmetric statistical lapse/take-up/withdrawal shock is reported.",
            "No catastrophe, FX, credit-spread or correlation stress.",
            "Results are before Risk Margin and gross of reinsurance.",
            "Mortality is illustrative and not an approved production basis.",
            (
                "LSMC uses one ordered annual decision with WAIT/START_INCOME "
                "in Growth and CONTINUE_FOR_ONE_YEAR/FULL_WITHDRAWAL_NOW in "
                "Income; Partial Withdrawal is excluded from the optimal "
                "action set."
            ),
            "Income is forced no later than the first policy anniversary after primary age 100 for an eligible surviving contract.",
            "The LSMC Election and enabled Income-action diagnostics are "
            "unweighted fit diagnostics, not portfolio-weighted take-up or "
            "surrender rates.",
            "Non-6% caps are non-contractual design sensitivities.",
            "Caps below 0.25% are technical sensitivities outside the contractual minimum.",
            "Crediting-cap variants hold all other terms fixed and are not budget-neutral repricings.",
            "Five-year government-bond sleeve, monthly rebalancing, no bond term premium and other fixed proxy assumptions remain in force.",
        ],
        "outputs": {
            "portfolio_risk_by_crediting_cap_csv": str(risk_csv),
            "crediting_cap_risk_sensitivities_csv": str(sensitivity_csv),
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
            "behaviour_metric_weighting": (
                "model_point_contract_weight_x_q_path_probability_x_"
                "pathwise_in_force_survival_weight"
            ),
            "lsmc_action_diagnostic_weighting": (
                "unweighted_eligible_model_point_path_decision_events"
            ),
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

    log_to_console(f"Risk comparison CSV: {risk_csv}")
    log_to_console(f"Sensitivity CSV: {sensitivity_csv}")
    log_to_console(f"Model-point comparison CSV: {model_point_csv}")
    if stress_loss_rows:
        log_to_console(f"Stress-loss CSV: {stress_csv}")
    log_to_console(f"Report: {report_path}")
    log_to_console(f"Manifest: {manifest_path}")
    log_to_console(
        f"RUN COMPLETE | ID {run_id} | total elapsed "
        f"{_format_duration(time.perf_counter() - run_started)} | "
        f"Output: {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
