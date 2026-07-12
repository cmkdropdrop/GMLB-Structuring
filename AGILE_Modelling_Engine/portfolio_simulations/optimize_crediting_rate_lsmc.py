"""Optimise annual Reference-Fund caps by control-randomisation LSMC.

This is a standalone counterfactual management-action study.  It deliberately
does not use the archived American-option-style ``agile_engine.lsmc`` module.
Instead, it treats the annual cap as a repeated discrete control, in the same
way that regression Monte Carlo for gas storage treats injection/withdrawal as
a control that changes the future inventory state.

The market paths are simulated once without contractual crediting under
risk-neutral Heston-Hull-White.  Exploratory cap paths then drive the existing
generic monthly contract projector.  A cross-fitted Fitted-Q backward pass
estimates, for every anniversary and admissible cap,

    E[PV(collected fees + other insurer margins
         - insurer-funded benefits - insurer costs)
      + optimal continuation value | information at the cap-setting time].

The signed quantity is the repository's market-consistent insurer net value
before Risk Margin and is used here as an approximate New Business CSM proxy.
The optimisation selects the cap with the largest proxy value.

The action grid is the explicit research convention requested for this study:
``{0.20%, 1%, 2%, ..., 20%}``.  It overrides the active case study's 0.25%
guaranteed minimum and fixed 6% Maximum Return; no existing product or engine
file is changed.  Fixed-cap checks distinguish zero crediting from uncapped
positive-return crediting.

Important timing convention
---------------------------
The management action is selected immediately after the anniversary state is
known and applies to the following crediting year.  The optimisation therefore
uses the administrative annual-crediting view with DVA disabled.  This makes
every regression state strictly pre-action.  Collected Product/LIP Fees,
Crediting and retained margins, Guarantee Claims, operating expenses and
hedge-execution costs enter the CSM proxy with their insurer cashflow signs.
Dynamic income-phase lapse and withdrawal assumptions are
re-evaluated after cap-dependent Account-Value changes for Single-Life,
Lump-Sum-Spouse and Single-Life fallback branches.  Consistent with the active
Engine, a Continue-Income Joint-Life branch uses state-independent CSV base
rates until separate p11/p10/p01 Account-Value cohorts are implemented.

When explicitly run, the script writes CSV/JSON results, a DEBUG ``run.log``
and headless Matplotlib diagnostics below ``plots/`` while reporting concise
progress to the console.  Merely importing it has no side effects.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.special import ndtr


ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

import agile_engine.projection as projection_module  # noqa: E402
from agile_engine import (  # noqa: E402
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DEFAULT_MODEL_PARAMETERS_PATH,
    DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
    ExpenseAssumptions,
    FeeSpec,
    Index,
    IndexLinkedLifetimeIncomeProduct,
    Measure,
    MortalityTable,
    ProjectionConfig,
    Protection,
    ReferenceFundSpec,
    ScenarioSet,
    SpouseDeathElection,
    __version__ as ENGINE_VERSION,
    load_cost_assumptions,
    load_dynamic_behaviour_assumptions,
    load_market_assumptions,
    load_policyholder_model_points,
    simulate,
)
from agile_engine.behavior import BehaviourModel  # noqa: E402
from agile_engine.model_points import (  # noqa: E402
    PolicyholderModelPoint,
    PolicyholderModelPointSet,
)
from agile_engine.mortality import MAX_AGE as MORTALITY_TERMINAL_AGE  # noqa: E402
from agile_engine.product import PolicySpec  # noqa: E402


Array = NDArray[np.float64]
IntArray = NDArray[np.int64]
STEPS_PER_YEAR = 12

ACTION_CAPS = np.concatenate((np.array([0.002]), np.arange(0.01, 0.201, 0.01)))
OTHER_INSURER_FUNDED_BENEFIT_KEYS: tuple[str, ...] = ()
DEFAULT_OUTPUT_DIRECTORY = (
    Path(__file__).resolve().parent / "output" / "crediting_cap_lsmc"
)
LOGGER = logging.getLogger("crediting_cap_lsmc")


def _configure_logging(output: Path, level_name: str) -> Path:
    """Log concise progress to the console and a detailed persistent run log."""
    level = getattr(logging, level_name.upper())
    log_path = output / "run.log"
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.propagate = False
    for handler in tuple(LOGGER.handlers):
        LOGGER.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    LOGGER.addHandler(console)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)
    return log_path


@contextmanager
def _logged_stage(label: str) -> Iterator[None]:
    started = time.perf_counter()
    LOGGER.info("START | %s", label)
    try:
        yield
    except Exception:
        LOGGER.exception("FAILED | %s | elapsed %.1fs", label,
                         time.perf_counter() - started)
        raise
    LOGGER.info("DONE  | %s | elapsed %.1fs", label,
                time.perf_counter() - started)


@dataclass(frozen=True)
class PathwiseReferenceFundSpec:
    """Duck-typed ReferenceFundSpec with one cap per path and policy year.

    ``ReferenceFundSpec`` intentionally enforces the active product's fixed 6%
    cap.  This local adapter is used only by this counterfactual script and
    leaves the product class and all repository inputs untouched.
    """

    cap_matrix: Array
    equity_index: Index = Index.GLOBAL_EQUITY
    equity_weight: float = 0.50
    bond_tenor_years: float = 5.0
    rebalance_frequency_months: int = 1
    specification_vintage: str = "counterfactual-lsmc-control-grid"

    def __post_init__(self) -> None:
        caps = np.asarray(self.cap_matrix, dtype=float)
        if caps.ndim != 2 or caps.shape[0] <= 0 or caps.shape[1] <= 0:
            raise ValueError("cap_matrix must have shape (positive paths, years).")
        if np.any(np.isnan(caps)) or np.any(caps < 0.0):
            raise ValueError("Pathwise caps must be non-negative and not NaN.")
        # Positive infinity is the explicit uncapped benchmark.
        snapshot = np.array(caps, dtype=float, copy=True)
        snapshot.flags.writeable = False
        object.__setattr__(self, "cap_matrix", snapshot)

    def cap(self, policy_year: int) -> Array:
        if isinstance(policy_year, bool) or int(policy_year) != policy_year \
                or policy_year < 0:
            raise ValueError("policy_year must be a non-negative integer.")
        column = min(int(policy_year), self.cap_matrix.shape[1] - 1)
        return self.cap_matrix[:, column]


@dataclass(frozen=True)
class ProjectionBranch:
    """One mortality-conditioned policy branch and its effective behaviour."""

    policy: PolicySpec
    probability: float
    behaviour: BehaviourModel
    label: str


@dataclass
class PortfolioPathData:
    """Discounted insurer-margin paths used by the backward induction."""

    guarantee_claims: Array
    other_insurer_funded_benefits: Array
    fees_product: Array
    fees_lip: Array
    crediting_margin: Array
    mva_retained: Array
    aps_retained: Array
    expenses: Array
    hedge_costs: Array
    terminal_closeout: Array
    raw_states: Array | None
    state_feature_names: tuple[str, ...]
    representative_initial_premium: float

    @property
    def new_business_csm_proxy(self) -> Array:
        return (
            self.fees_product
            + self.fees_lip
            + self.crediting_margin
            + self.mva_retained
            + self.aps_retained
            - self.guarantee_claims
            - self.other_insurer_funded_benefits
            - self.expenses
            - self.hedge_costs
        )


@dataclass(frozen=True)
class RegressionPolicyYear:
    year: int
    raw_mean: Array
    raw_scale: Array
    coefficients: Array
    action_caps: Array


@dataclass
class BackwardResult:
    first_year_cap: float
    pv_new_business_csm_proxy: float
    pv_guarantee_claims: float
    pv_other_insurer_funded_benefits: float
    pv_fees_product: float
    pv_fees_lip: float
    pv_crediting_margin: float
    pv_mva_retained: float
    pv_aps_retained: float
    pv_expenses: float
    pv_hedge_costs: float
    standard_error_new_business_csm_proxy: float
    first_year_action_rows: list[dict[str, object]]
    policy_year_rows: list[dict[str, object]]
    regression_rows: list[dict[str, object]]
    policy_years: list[RegressionPolicyYear]
    reconciliation_gap: float
    economically_active_policy_years: tuple[int, ...]
    inactive_market_tail_year_count: int


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "value"):
        return getattr(value, "value")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serialisable")


def _standard_error(values: Array) -> float:
    values = np.asarray(values, dtype=float)
    if values.size <= 1:
        return 0.0
    return float(np.std(values, ddof=1) / np.sqrt(values.size))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-points", type=Path,
        default=DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
        help="policyholder model-point CSV",
    )
    parser.add_argument(
        "--cost-assumptions", type=Path,
        default=DEFAULT_COST_ASSUMPTIONS_PATH,
        help="repository cost_assumptions.csv",
    )
    parser.add_argument("--cost-assumption-set", default=None)
    parser.add_argument(
        "--dynamic-behaviour", type=Path,
        default=DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
        help="repository dynamic-behaviour directory",
    )
    parser.add_argument("--behaviour-assumption-set", default=None)
    parser.add_argument(
        "--zero-curve", type=Path,
        default=DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    )
    parser.add_argument(
        "--model-parameters", type=Path,
        default=DEFAULT_MODEL_PARAMETERS_PATH,
    )
    parser.add_argument(
        "--n-paths", type=int, default=4_200,
        help="control-randomisation paths (default gives 200 paths/action/year)",
    )
    parser.add_argument(
        "--benchmark-paths", type=int, default=500,
        help="common-random-number paths per fixed-cap benchmark",
    )
    parser.add_argument(
        "--benchmark-batch-size", type=int, default=4,
        help="number of fixed-cap cases projected together",
    )
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument("--cross-fit-folds", type=int, default=5)
    parser.add_argument(
        "--ridge", type=float, default=1.0e-4,
        help="dimensionless ridge multiplier for the regression normal matrix",
    )
    parser.add_argument(
        "--persistent-exploration-fraction", type=float, default=0.0,
        help="fraction of paths assigned a constant exploratory cap history",
    )
    parser.add_argument(
        "--portfolio-contract-count", type=float, default=None,
        help="optional absolute contract count; otherwise PVs are normalised",
    )
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING"), default="INFO",
        help="console logging level; run.log always records DEBUG details",
    )
    parser.add_argument(
        "--model-point-log-interval", type=int, default=8,
        help="log portfolio-projection progress after this many model points",
    )
    parser.add_argument(
        "--plot-format", choices=("png", "svg", "both"), default="png",
        help="graphics format written below the output plots directory",
    )
    parser.add_argument(
        "--plot-dpi", type=int, default=160,
        help="raster resolution for PNG graphics",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_DIRECTORY,
        help="output directory",
    )
    args = parser.parse_args()

    if args.n_paths <= 0 or args.benchmark_paths <= 0:
        parser.error("--n-paths and --benchmark-paths must be positive")
    if args.benchmark_batch_size <= 0:
        parser.error("--benchmark-batch-size must be positive")
    if args.model_point_log_interval <= 0:
        parser.error("--model-point-log-interval must be positive")
    if args.plot_dpi < 72:
        parser.error("--plot-dpi must be at least 72")
    if args.seed < 0 or args.heston_substeps <= 0:
        parser.error("seed must be non-negative and Heston substeps positive")
    if args.cross_fit_folds < 3:
        parser.error("--cross-fit-folds must be at least three")
    if not np.isfinite(args.ridge) or args.ridge < 0.0:
        parser.error("--ridge must be finite and non-negative")
    if not 0.0 <= args.persistent_exploration_fraction < 1.0:
        parser.error("--persistent-exploration-fraction must be in [0, 1)")
    if (args.portfolio_contract_count is not None
            and (not np.isfinite(args.portfolio_contract_count)
                 or args.portfolio_contract_count <= 0.0)):
        parser.error("--portfolio-contract-count must be positive and finite")
    min_paths = len(ACTION_CAPS) * args.cross_fit_folds * 20
    if args.n_paths < min_paths:
        parser.error(
            f"--n-paths must be at least {min_paths} for action/fold coverage"
        )
    return args


def _vector_credited_return(
    index_return: float | Array,
    protection: Protection,
    cap: float | Array,
    buffer: float = 0.10,
) -> float | Array:
    """Array-cap equivalent of ``agile_engine.crediting.credited_return``."""
    protection = Protection(protection)
    returns, caps = np.broadcast_arrays(
        np.asarray(index_return, dtype=float), np.asarray(cap, dtype=float)
    )
    if not np.all(np.isfinite(returns)):
        raise ValueError("index_return must be finite.")
    if np.any(np.isnan(caps)) or np.any(caps < 0.0):
        raise ValueError("cap must be non-negative and not NaN.")
    if not np.isfinite(buffer) or not 0.0 <= buffer < 1.0:
        raise ValueError("buffer must be finite and in [0, 1).")
    if protection == Protection.TOTAL:
        out = np.minimum(np.maximum(returns, 0.0), caps)
    else:
        out = np.where(
            returns >= 0.0,
            np.minimum(returns, caps),
            np.minimum(0.0, returns + buffer),
        )
    return float(out) if np.ndim(index_return) == 0 and np.ndim(cap) == 0 else out


def _vector_bs_call(
    x0: float | Array,
    strike: float | Array,
    tau: float,
    rate: float | Array,
    dividend_yield: float,
    sigma: float | Array,
) -> float | Array:
    """Black-Scholes call supporting one pathwise strike per cap control."""
    spot, strike_array, rate_array, sigma_array = np.broadcast_arrays(
        np.asarray(x0, dtype=float),
        np.asarray(strike, dtype=float),
        np.asarray(rate, dtype=float),
        np.asarray(sigma, dtype=float),
    )
    if np.any(np.isnan(strike_array)) or np.any(strike_array <= 0.0):
        raise ValueError("Option strikes must be positive and not NaN.")
    if tau <= 0.0:
        result = np.maximum(spot - strike_array, 0.0)
    else:
        vol = np.maximum(sigma_array, 1.0e-8) * np.sqrt(float(tau))
        forward = spot * np.exp((rate_array - dividend_yield) * tau)
        finite = np.isfinite(strike_array)
        safe_strike = np.where(finite, strike_array, 1.0)
        d1 = np.log(np.maximum(forward, 1.0e-300) / safe_strike) / vol \
            + 0.5 * vol
        d2 = d1 - vol
        result = np.exp(-rate_array * tau) * (
            forward * ndtr(d1) - safe_strike * ndtr(d2)
        )
        result = np.where(finite, result, 0.0)
    scalar = all(np.ndim(value) == 0 for value in (x0, strike, rate, sigma))
    return float(result) if scalar else np.asarray(result, dtype=float)


def _vector_crediting_package_value(
    x0: float | Array,
    protection: Protection,
    cap: float | Array,
    tau: float,
    rate: float | Array,
    dividend_yield: float,
    sigma: float | Array,
    buffer: float = 0.10,
) -> float | Array:
    """Vector-cap package value used by margin and hedge-cost cashflows."""
    protection = Protection(protection)
    caps = np.asarray(cap, dtype=float)
    if np.any(np.isnan(caps)) or np.any(caps < 0.0):
        raise ValueError("cap must be non-negative and not NaN.")
    if not np.isfinite(buffer) or not 0.0 <= buffer < 1.0:
        raise ValueError("buffer must be finite and in [0, 1).")
    call_at_one = _vector_bs_call(
        x0, 1.0, tau, rate, dividend_yield, sigma
    )
    call_at_cap = _vector_bs_call(
        x0, 1.0 + caps, tau, rate, dividend_yield, sigma
    )
    call_spread = np.asarray(call_at_one) - np.asarray(call_at_cap)
    if protection == Protection.TOTAL:
        result = call_spread
    else:
        strike = 1.0 - buffer
        call_at_buffer = np.asarray(_vector_bs_call(
            x0, strike, tau, rate, dividend_yield, sigma
        ))
        spot = np.asarray(x0, dtype=float)
        rate_array = np.asarray(rate, dtype=float)
        put_at_buffer = (
            call_at_buffer
            - spot * np.exp(-dividend_yield * tau)
            + strike * np.exp(-rate_array * tau)
        )
        result = call_spread - put_at_buffer
    scalar = all(np.ndim(value) == 0 for value in (x0, cap, rate, sigma))
    return float(result) if scalar else np.asarray(result, dtype=float)


@contextmanager
def _pathwise_cap_adapter() -> Iterator[None]:
    """Temporarily vectorise projector calls reached by pathwise cap controls.

    The adapter is process-local and restored in ``finally``. DVA remains
    disabled, while the package pricer is vectorised so the CSM proxy can
    include cap-dependent Crediting Margin and hedge-execution cost.
    """
    original_return = projection_module.credited_return
    original_package = projection_module.crediting_package_value
    projection_module.credited_return = _vector_credited_return
    projection_module.crediting_package_value = _vector_crediting_package_value
    try:
        yield
    finally:
        projection_module.credited_return = original_return
        projection_module.crediting_package_value = original_package


def _controlled_product(
    product: IndexLinkedLifetimeIncomeProduct,
    cap_matrix: Array,
) -> IndexLinkedLifetimeIncomeProduct:
    base: ReferenceFundSpec = product.reference_fund
    reference = PathwiseReferenceFundSpec(
        cap_matrix=cap_matrix,
        equity_index=base.equity_index,
        equity_weight=base.equity_weight,
        bond_tenor_years=base.bond_tenor_years,
        rebalance_frequency_months=base.rebalance_frequency_months,
    )
    return replace(product, reference_fund=reference)  # type: ignore[arg-type]


def _youngest_covered_age(model_points: PolicyholderModelPointSet) -> float:
    ages: list[float] = []
    for point in model_points.model_points:
        ages.append(float(point.policy.age))
        if point.policy.spouse and point.policy.spouse_age is not None:
            ages.append(float(point.policy.spouse_age))
    return min(ages)


def _projection_horizon_years(
    model_points: PolicyholderModelPointSet,
    terminal_age: float = 120.0,
) -> float:
    raw = terminal_age - _youngest_covered_age(model_points)
    if raw <= 0.0:
        raise ValueError("The terminal age must exceed the youngest covered age.")
    # Preserve the monthly ESG grid if a future model-point file uses a
    # fractional age.
    return float(np.ceil(raw * STEPS_PER_YEAR - 1e-12) / STEPS_PER_YEAR)


def _spouse_survival_to_election(
    point: PolicyholderModelPoint,
    product: IndexLinkedLifetimeIncomeProduct,
    mortality: MortalityTable,
) -> float:
    """Match the engine's effective Election and reconciled mortality basis."""
    policy = point.policy
    if not policy.spouse or policy.spouse_age is None:
        return 0.0
    steps = policy.effective_income_start_year(product) * STEPS_PER_YEAR
    issue_offset = policy.commencement_year - mortality.base_year
    spouse_sex = policy.spouse_sex or policy.sex
    q_monthly = mortality.monthly_q_curve(
        policy.spouse_age,
        spouse_sex,
        steps,
        years_from_base=issue_offset,
        projection_duration_start=0.0,
    )
    survival = float(np.prod(1.0 - q_monthly))
    return float(np.clip(survival, 0.0, 1.0))


def _model_point_behaviour_treatment(
    point: PolicyholderModelPoint,
    behaviour: BehaviourModel,
) -> str:
    """Describe the effective branch treatment used by the active Engine."""
    dynamic_active = behaviour.use_dynamic or behaviour.use_dynamic_withdrawals
    if (
        point.policy.spouse
        and point.policy.spouse_death_election
        == SpouseDeathElection.CONTINUE_INCOME
    ):
        return (
            "joint_branch_static_base_single_fallback_dynamic"
            if dynamic_active
            else "joint_and_single_branches_static_base"
        )
    if point.policy.spouse:
        return (
            "spouse_lump_sum_joint_and_fallback_dynamic"
            if dynamic_active
            else "spouse_lump_sum_joint_and_fallback_static_base"
        )
    if dynamic_active:
        return "dynamic_state_dependent"
    return "static_base"


def _projection_branches(
    point: PolicyholderModelPoint,
    product: IndexLinkedLifetimeIncomeProduct,
    mortality: MortalityTable,
    behaviour: BehaviourModel,
) -> tuple[ProjectionBranch, ...]:
    """Match the portfolio wrapper's Election split and Behaviour treatment."""
    if not point.policy.spouse:
        return (ProjectionBranch(
            policy=point.policy,
            probability=1.0,
            behaviour=behaviour,
            label="single",
        ),)
    if behaviour.take_up.mode != "deterministic":
        raise ValueError(
            "Joint-Life LSMC model points require deterministic model-point "
            "Income Election for the spouse-survival fallback split."
        )
    joint_behaviour = behaviour
    if (
        point.policy.spouse_death_election
        == SpouseDeathElection.CONTINUE_INCOME
        and (behaviour.use_dynamic or behaviour.use_dynamic_withdrawals)
    ):
        joint_behaviour = replace(behaviour, regime="static")
    spouse_survival = _spouse_survival_to_election(point, product, mortality)
    fallback = replace(
        point.policy,
        spouse=False,
        spouse_age=None,
        spouse_sex=None,
        spouse_death_election=SpouseDeathElection.CONTINUE_INCOME,
    )
    return (
        ProjectionBranch(
            policy=point.policy,
            probability=spouse_survival,
            behaviour=joint_behaviour,
            label=(
                "joint_dynamic_state_dependent"
                if joint_behaviour.use_dynamic
                or joint_behaviour.use_dynamic_withdrawals
                else "joint_static_base"
            ),
        ),
        ProjectionBranch(
            policy=fallback,
            probability=1.0 - spouse_survival,
            behaviour=behaviour,
            label=(
                "single_fallback_dynamic"
                if behaviour.use_dynamic or behaviour.use_dynamic_withdrawals
                else "single_fallback_static_base"
            ),
        ),
    )


def _model_point_treatment_rows(
    model_points: PolicyholderModelPointSet,
    product: IndexLinkedLifetimeIncomeProduct,
    mortality: MortalityTable,
    behaviour: BehaviourModel,
    source_behaviour: BehaviourModel,
) -> list[dict[str, object]]:
    """Audit the effective Election, mortality split and Behaviour overlay."""
    rows: list[dict[str, object]] = []
    for point in model_points.model_points:
        policy = point.policy
        scheduled = int(round(float(policy.income_start_year)))
        effective = policy.effective_income_start_year(product)
        minimum_adjusted_start = max(
            scheduled, int(product.min_years_before_income)
        )
        years_to_automatic_age = max(
            float(product.automatic_income_start_age) - float(policy.age),
            0.0,
        )
        automatic_start_anniversary = max(
            int(np.floor(years_to_automatic_age + 1.0e-12)) + 1,
            int(product.min_years_before_income),
            1,
        )
        if effective == scheduled:
            override_reason = "none"
        elif (
            effective == automatic_start_anniversary
            and automatic_start_anniversary < minimum_adjusted_start
        ):
            override_reason = "automatic_age_backstop"
        elif scheduled < product.min_years_before_income:
            override_reason = "minimum_wait"
        else:
            override_reason = "combined_product_constraints"
        dynamic_active = behaviour.use_dynamic or behaviour.use_dynamic_withdrawals
        joint_static = bool(
            policy.spouse
            and policy.spouse_death_election
            == SpouseDeathElection.CONTINUE_INCOME
            and dynamic_active
        )
        rows.append({
            "model_point_id": point.model_point_id,
            "contract_weight": float(point.contract_weight),
            "scheduled_income_start_year": scheduled,
            "effective_income_start_year": effective,
            "effective_start_overrides_scheduled_start": effective != scheduled,
            "effective_start_override_reason": override_reason,
            "product_min_years_before_income": int(
                product.min_years_before_income
            ),
            "product_automatic_income_start_age": float(
                product.automatic_income_start_age
            ),
            "automatic_start_anniversary": automatic_start_anniversary,
            "source_income_take_up_mode": source_behaviour.take_up.mode,
            "effective_income_take_up_mode": behaviour.take_up.mode,
            "dynamic_take_up_coefficients_applied": False,
            "take_up_override_reason": (
                "deterministic effective model-point Election; Joint-Life "
                "fallback compatibility where applicable"
            ),
            "spouse": bool(policy.spouse),
            "spouse_death_election": (
                policy.spouse_death_election.value if policy.spouse else None
            ),
            "spouse_survival_to_effective_income_election": (
                _spouse_survival_to_election(point, product, mortality)
                if policy.spouse else None
            ),
            "behaviour_treatment": _model_point_behaviour_treatment(
                point, behaviour
            ),
            "joint_branch_behaviour_regime": (
                (
                    "static"
                    if joint_static or not dynamic_active
                    else "dynamic"
                )
                if policy.spouse else None
            ),
            "single_fallback_behaviour_regime": (
                ("dynamic" if dynamic_active else "static")
                if policy.spouse else None
            ),
        })
    return rows


def _bucket_label(value: float) -> str:
    text = f"{value:g}"
    return text.replace("-", "minus_").replace(".", "_")


def _state_layout(
    model_points: PolicyholderModelPointSet,
    product: IndexLinkedLifetimeIncomeProduct,
) -> tuple[
    tuple[str, ...],
    dict[str, int],
    tuple[float, ...],
    tuple[float, ...],
    tuple[tuple[float, str, bool], ...],
    tuple[int, ...],
]:
    ages = tuple(sorted({float(p.policy.age) for p in model_points.model_points}))
    premiums = tuple(sorted({float(p.policy.initial_investment)
                             for p in model_points.model_points}))
    cohort_set = {
        (float(p.policy.age), p.policy.sex.value, bool(p.policy.spouse))
        for p in model_points.model_points
    }
    cohort_set.update(
        (float(p.policy.age), p.policy.sex.value, False)
        for p in model_points.model_points if p.policy.spouse
    )
    cohorts = tuple(sorted(cohort_set))
    effective_income_starts = tuple(sorted({
        point.policy.effective_income_start_year(product)
        for point in model_points.model_points
    }))
    names = [
        "short_rate",
        "zero_rate_5y",
        "heston_variance_global",
        "log_discount_to_time0",
        "trailing_reference_fund_return",
        "inforce_exposure",
        "growth_exposure",
        "income_exposure",
        "account_value_per_initial_premium",
        "locked_income_per_initial_premium",
        "income_pv_proxy_over_account_value",
        "exhausted_income_exposure",
    ]
    for age in ages:
        label = _bucket_label(age)
        names.extend((
            f"inforce_primary_age_{label}",
            f"account_value_primary_age_{label}_per_initial_premium",
        ))
    for premium in premiums:
        label = _bucket_label(premium)
        names.extend((
            f"inforce_premium_{label}",
            f"account_value_premium_{label}_per_initial_premium",
        ))
    for age, sex, spouse in cohorts:
        cohort = (
            f"age_{_bucket_label(age)}_sex_{sex}_"
            f"{'joint' if spouse else 'single'}"
        )
        names.extend((
            f"inforce_cohort_{cohort}",
            f"account_value_cohort_{cohort}_per_initial_premium",
            f"locked_income_cohort_{cohort}_per_initial_premium",
        ))
    # A single common Election anniversary is already represented by the
    # portfolio phase features.  Add explicit cohorts only when scheduled
    # starts or product constraints produce heterogeneous effective dates.
    if len(effective_income_starts) > 1:
        for start_year in effective_income_starts:
            names.extend((
                f"inforce_effective_income_start_year_{start_year}",
                f"account_value_effective_income_start_year_{start_year}_"
                "per_initial_premium",
                f"locked_income_effective_income_start_year_{start_year}_"
                "per_initial_premium",
            ))
    index = {name: pos for pos, name in enumerate(names)}
    return (
        tuple(names), index, ages, premiums, cohorts,
        effective_income_starts,
    )


def _annual_discounted_paths(
    cashflow: Array,
    discount: Array,
    n_years: int,
    *,
    include_time_zero_in_first_year: bool = False,
) -> Array:
    """Aggregate grid cashflows in ``(year, year+1]`` in time-zero units."""
    n_paths, n_columns = cashflow.shape
    out = np.zeros((n_paths, n_years))
    if include_time_zero_in_first_year and n_years:
        out[:, 0] = cashflow[:, 0] * discount[:, 0]
    last_step = n_columns - 1
    for year in range(n_years):
        lo = year * STEPS_PER_YEAR + 1
        hi = min((year + 1) * STEPS_PER_YEAR, last_step)
        if lo <= hi:
            out[:, year] = np.sum(
                cashflow[:, lo:hi + 1] * discount[:, lo:hi + 1], axis=1
            )
    return out


def _annual_start_discounted_paths(
    cashflow: Array,
    discount: Array,
    n_years: int,
) -> Array:
    """Assign anniversary-start cashflows to the cap chosen at that time."""
    n_paths, n_columns = cashflow.shape
    out = np.zeros((n_paths, n_years))
    for year in range(n_years):
        step = year * STEPS_PER_YEAR
        if step >= n_columns:
            break
        out[:, year] = cashflow[:, step] * discount[:, step]
    total_discounted = np.sum(cashflow * discount, axis=1)
    unassigned = total_discounted - np.sum(out, axis=1)
    tolerance = 1.0e-10 * max(
        1.0, float(np.max(np.abs(total_discounted)))
    )
    if np.any(np.abs(unassigned) > tolerance):
        raise RuntimeError(
            "Hedge-cost cashflows were found away from control-year starts; "
            "the action-timing aggregation would omit a material amount."
        )
    return out


def _aggregate_portfolio_paths(
    *,
    scenarios: ScenarioSet,
    cap_matrix: Array,
    product: IndexLinkedLifetimeIncomeProduct,
    model_points: PolicyholderModelPointSet,
    behaviour: BehaviourModel,
    mortality: MortalityTable,
    expenses: ExpenseAssumptions,
    projection_config: ProjectionConfig,
    collect_states: bool,
    progress_label: str,
    model_point_log_interval: int,
) -> PortfolioPathData:
    """Project all model points under one pathwise cap schedule.

    Aggregation follows the repository portfolio rule: ``contract_weight`` is
    applied exactly once and ``premium_volume_weight`` is never a valuation
    weight.  Joint-Life points use the same spouse-survival-conditioned joint/
    Single-Life fallback mix and branch-specific Behaviour basis as the active
    Engine 2.2 portfolio wrapper.
    """
    caps = np.asarray(cap_matrix, dtype=float)
    if caps.shape[0] != scenarios.n_paths:
        raise ValueError("cap_matrix path count must match the scenario set.")
    n_years = caps.shape[1]
    point_count = len(model_points.model_points)
    LOGGER.info(
        "%s | %d model points | %d market paths | %d policy years | states=%s",
        progress_label, point_count, scenarios.n_paths, n_years, collect_states,
    )
    guarantee_claims = np.zeros((scenarios.n_paths, n_years))
    other_insurer_funded_benefits = np.zeros_like(guarantee_claims)
    fees_product = np.zeros_like(guarantee_claims)
    fees_lip = np.zeros_like(guarantee_claims)
    crediting_margin = np.zeros_like(guarantee_claims)
    mva_retained = np.zeros_like(guarantee_claims)
    aps_retained = np.zeros_like(guarantee_claims)
    projected_expenses = np.zeros_like(guarantee_claims)
    hedge_costs = np.zeros_like(guarantee_claims)
    terminal_closeout = np.zeros_like(guarantee_claims)

    representative_premium = float(sum(
        point.contract_weight * point.policy.initial_investment
        for point in model_points.model_points
    ))
    if representative_premium <= 0.0:
        raise ValueError("The contract-weighted representative premium is not positive.")

    feature_names: tuple[str, ...] = ()
    feature_index: dict[str, int] = {}
    ages: tuple[float, ...] = ()
    premiums: tuple[float, ...] = ()
    cohorts: tuple[tuple[float, str, bool], ...] = ()
    effective_income_starts: tuple[int, ...] = ()
    raw_states: Array | None = None
    if collect_states:
        (
            feature_names,
            feature_index,
            ages,
            premiums,
            cohorts,
            effective_income_starts,
        ) = _state_layout(model_points, product)
        raw_states = np.zeros(
            (scenarios.n_paths, n_years + 1, len(feature_names)), dtype=float
        )
        fund = scenarios.monthly_rebalanced_reference_fund_index(
            equity_index=product.reference_fund.equity_index,
            equity_weight=product.reference_fund.equity_weight,
            bond_tenor=product.reference_fund.bond_tenor_years,
        )
        for year in range(n_years + 1):
            step = min(year * STEPS_PER_YEAR, scenarios.n_steps)
            previous = max(step - STEPS_PER_YEAR, 0)
            trailing = np.where(
                step > 0,
                fund[:, step] / np.maximum(fund[:, previous], 1.0e-300) - 1.0,
                0.0,
            )
            raw_states[:, year, feature_index["short_rate"]] = (
                scenarios.short_rate[:, step]
            )
            raw_states[:, year, feature_index["zero_rate_5y"]] = (
                scenarios.zero_rate(step, 5.0)
            )
            if scenarios.variance is None:
                variance = np.full(
                    scenarios.n_paths,
                    scenarios.config.equity[Index.GLOBAL_EQUITY].sigma ** 2,
                )
            else:
                variance = scenarios.variance[Index.GLOBAL_EQUITY][:, step]
            raw_states[:, year, feature_index["heston_variance_global"]] = variance
            raw_states[:, year, feature_index["log_discount_to_time0"]] = np.log(
                np.maximum(scenarios.discount[:, step], 1.0e-300)
            )
            raw_states[:, year, feature_index[
                "trailing_reference_fund_return"
            ]] = trailing

    controlled = _controlled_product(product, caps)
    config = replace(projection_config, record_paths=collect_states)
    with _pathwise_cap_adapter():
        for point_number, point in enumerate(model_points.model_points, start=1):
            branch_count = 0
            for branch in _projection_branches(
                point, product, mortality, behaviour
            ):
                policy = branch.policy
                branch_probability = branch.probability
                if branch_probability <= 0.0:
                    continue
                branch_count += 1
                LOGGER.debug(
                    "%s | model point %s (%d/%d) | branch=%s | "
                    "behaviour=%s | weight=%.8f",
                    progress_label,
                    point.model_point_id,
                    point_number,
                    point_count,
                    branch.label,
                    branch.behaviour.regime,
                    point.contract_weight * branch_probability,
                )
                result = projection_module.project(
                    controlled,
                    policy,
                    scenarios,
                    branch.behaviour,
                    mortality,
                    expenses=expenses,
                    config=config,
                )
                branch_weight = float(point.contract_weight * branch_probability)
                n_columns = len(result.times)
                discount = scenarios.discount[:, :n_columns]
                guarantee_claims += branch_weight * _annual_discounted_paths(
                    result.cashflows["guarantee_claims"], discount, n_years
                )
                for key in OTHER_INSURER_FUNDED_BENEFIT_KEYS:
                    other_insurer_funded_benefits += (
                        branch_weight * _annual_discounted_paths(
                            result.cashflows[key], discount, n_years
                        )
                    )
                fees_product += branch_weight * _annual_discounted_paths(
                    result.cashflows["fees_product"], discount, n_years
                )
                fees_lip += branch_weight * _annual_discounted_paths(
                    result.cashflows["fees_lip"], discount, n_years
                )
                crediting_margin += branch_weight * _annual_discounted_paths(
                    result.cashflows["crediting_margin"], discount, n_years
                )
                mva_retained += branch_weight * _annual_discounted_paths(
                    result.cashflows["mva_retained"], discount, n_years
                )
                aps_retained += branch_weight * _annual_discounted_paths(
                    result.cashflows["aps_retained"], discount, n_years
                )
                projected_expenses += branch_weight * _annual_discounted_paths(
                    result.cashflows["expenses"],
                    discount,
                    n_years,
                    include_time_zero_in_first_year=True,
                )
                hedge_costs += branch_weight * _annual_start_discounted_paths(
                    result.cashflows["hedge_costs"], discount, n_years
                )
                terminal_closeout += branch_weight * _annual_discounted_paths(
                    result.cashflows["terminal_closeout"], discount, n_years
                )

                if raw_states is None:
                    continue
                if (result.iv_paths is None or result.income_paths is None
                        or result.phase_paths is None):
                    raise RuntimeError("State collection requires recorded projection paths.")
                age_label = _bucket_label(float(point.policy.age))
                premium_label = _bucket_label(float(point.policy.initial_investment))
                effective_income_start = (
                    point.policy.effective_income_start_year(product)
                )
                cohort_label = (
                    f"age_{_bucket_label(float(policy.age))}_sex_{policy.sex.value}_"
                    f"{'joint' if policy.spouse else 'single'}"
                )
                for year in range(n_years + 1):
                    step = year * STEPS_PER_YEAR
                    if step >= n_columns:
                        continue
                    inforce = result.inforce[:, step]
                    account_value = np.maximum(result.iv_paths[:, step], 0.0)
                    income = np.maximum(result.income_paths[:, step], 0.0)
                    phase = result.phase_paths[:, step]
                    exposure = branch_weight * inforce
                    growth = exposure * (phase == 0)
                    income_phase = exposure * (phase == 1)
                    weighted_av = exposure * account_value
                    weighted_income = exposure * income

                    raw_states[:, year, feature_index["inforce_exposure"]] += exposure
                    raw_states[:, year, feature_index["growth_exposure"]] += growth
                    raw_states[:, year, feature_index["income_exposure"]] += income_phase
                    raw_states[:, year, feature_index[
                        "account_value_per_initial_premium"
                    ]] += weighted_av
                    raw_states[:, year, feature_index[
                        "locked_income_per_initial_premium"
                    ]] += weighted_income
                    exhausted = income_phase * (
                        account_value <= 1.0e-10 * point.policy.initial_investment
                    )
                    raw_states[:, year, feature_index[
                        "exhausted_income_exposure"
                    ]] += exhausted
                    raw_states[:, year, feature_index[
                        f"inforce_primary_age_{age_label}"
                    ]] += exposure
                    raw_states[:, year, feature_index[
                        f"account_value_primary_age_{age_label}_per_initial_premium"
                    ]] += weighted_av
                    raw_states[:, year, feature_index[
                        f"inforce_premium_{premium_label}"
                    ]] += exposure
                    raw_states[:, year, feature_index[
                        f"account_value_premium_{premium_label}_per_initial_premium"
                    ]] += weighted_av
                    raw_states[:, year, feature_index[
                        f"inforce_cohort_{cohort_label}"
                    ]] += exposure
                    raw_states[:, year, feature_index[
                        f"account_value_cohort_{cohort_label}_per_initial_premium"
                    ]] += weighted_av
                    raw_states[:, year, feature_index[
                        f"locked_income_cohort_{cohort_label}_per_initial_premium"
                    ]] += weighted_income
                    if len(effective_income_starts) > 1:
                        raw_states[:, year, feature_index[
                            "inforce_effective_income_start_year_"
                            f"{effective_income_start}"
                        ]] += exposure
                        raw_states[:, year, feature_index[
                            "account_value_effective_income_start_year_"
                            f"{effective_income_start}_per_initial_premium"
                        ]] += weighted_av
                        raw_states[:, year, feature_index[
                            "locked_income_effective_income_start_year_"
                            f"{effective_income_start}_per_initial_premium"
                        ]] += weighted_income
            if (point_number == 1 or point_number == point_count
                    or point_number % model_point_log_interval == 0):
                LOGGER.info(
                    "%s | model-point progress %d/%d (%.0f%%) | last=%s | branches=%d",
                    progress_label,
                    point_number,
                    point_count,
                    100.0 * point_number / point_count,
                    point.model_point_id,
                    branch_count,
                )

    if raw_states is not None:
        monetary_columns = [
            feature_index["account_value_per_initial_premium"],
            feature_index["locked_income_per_initial_premium"],
        ]
        monetary_columns.extend(
            feature_index[
                f"account_value_primary_age_{_bucket_label(age)}_per_initial_premium"
            ] for age in ages
        )
        monetary_columns.extend(
            feature_index[
                f"account_value_premium_{_bucket_label(premium)}_per_initial_premium"
            ] for premium in premiums
        )
        for age, sex, spouse in cohorts:
            cohort = (
                f"age_{_bucket_label(age)}_sex_{sex}_"
                f"{'joint' if spouse else 'single'}"
            )
            monetary_columns.extend((
                feature_index[
                    f"account_value_cohort_{cohort}_per_initial_premium"
                ],
                feature_index[
                    f"locked_income_cohort_{cohort}_per_initial_premium"
                ],
            ))
        if len(effective_income_starts) > 1:
            for start_year in effective_income_starts:
                monetary_columns.extend((
                    feature_index[
                        "account_value_effective_income_start_year_"
                        f"{start_year}_per_initial_premium"
                    ],
                    feature_index[
                        "locked_income_effective_income_start_year_"
                        f"{start_year}_per_initial_premium"
                    ],
                ))
        raw_states[:, :, monetary_columns] /= representative_premium
        av = raw_states[:, :, feature_index["account_value_per_initial_premium"]]
        income = raw_states[:, :, feature_index["locked_income_per_initial_premium"]]
        # Ten times annual income is a transparent duration proxy.  The rate
        # and mortality state are represented separately; no new calibrated
        # annuity or behaviour parameter is introduced.
        raw_states[:, :, feature_index["income_pv_proxy_over_account_value"]] = (
            np.divide(
                10.0 * income,
                np.maximum(av, 1.0e-12),
                out=np.zeros_like(income),
                where=av > 1.0e-12,
            )
        )
        np.clip(
            raw_states[:, :, feature_index["income_pv_proxy_over_account_value"]],
            0.0,
            20.0,
            out=raw_states[:, :, feature_index[
                "income_pv_proxy_over_account_value"
            ]],
        )

    return PortfolioPathData(
        guarantee_claims=guarantee_claims,
        other_insurer_funded_benefits=other_insurer_funded_benefits,
        fees_product=fees_product,
        fees_lip=fees_lip,
        crediting_margin=crediting_margin,
        mva_retained=mva_retained,
        aps_retained=aps_retained,
        expenses=projected_expenses,
        hedge_costs=hedge_costs,
        terminal_closeout=terminal_closeout,
        raw_states=raw_states,
        state_feature_names=feature_names,
        representative_initial_premium=representative_premium,
    )


def _exploration_schedule(
    n_paths: int,
    n_years: int,
    seed: int,
    persistent_fraction: float,
) -> tuple[IntArray, Array, dict[str, object]]:
    """Balanced independent controls plus persistent fixed-cap trajectories."""
    rng = np.random.default_rng(seed)
    n_actions = len(ACTION_CAPS)
    actions = np.empty((n_paths, n_years), dtype=np.int64)
    base = np.resize(np.arange(n_actions, dtype=np.int64), n_paths)
    for year in range(n_years):
        actions[:, year] = rng.permutation(base)

    n_persistent = int(math.floor(n_paths * persistent_fraction))
    if n_persistent > 0:
        persistent_rows = rng.permutation(n_paths)[:n_persistent]
        fixed_actions = np.resize(
            np.arange(n_actions, dtype=np.int64), n_persistent
        )
        fixed_actions = rng.permutation(fixed_actions)
        actions[persistent_rows, :] = fixed_actions[:, None]
    caps = ACTION_CAPS[actions]
    diagnostics = {
        "design": "balanced_independent_plus_persistent_fixed_histories",
        "persistent_path_count": n_persistent,
        "persistent_fraction_realised": n_persistent / n_paths,
        "minimum_action_count_in_any_year": int(min(
            np.bincount(actions[:, year], minlength=n_actions).min()
            for year in range(n_years)
        )),
    }
    return actions, caps, diagnostics


def _repeat_scenarios(scenarios: ScenarioSet, repeats: int) -> ScenarioSet:
    if repeats <= 0:
        raise ValueError("repeats must be positive.")

    def repeated(array: Array) -> Array:
        return np.concatenate([np.asarray(array)] * repeats, axis=0)

    variance = None
    if scenarios.variance is not None:
        variance = {
            index: repeated(values)
            for index, values in scenarios.variance.items()
        }
    return ScenarioSet(
        config=scenarios.config,
        measure=scenarios.measure,
        dt=scenarios.dt,
        times=scenarios.times,
        index_levels={
            index: repeated(values)
            for index, values in scenarios.index_levels.items()
        },
        short_rate=repeated(scenarios.short_rate),
        discount=repeated(scenarios.discount),
        variance=variance,
        stochastic_rates=scenarios.stochastic_rates,
        model_name=scenarios.model_name,
        seed=scenarios.seed,
        substeps=scenarios.substeps,
        _copy_inputs=False,
    )


def _basis_specification(
    feature_names: Sequence[str],
) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...], tuple[str, ...]]:
    index = {name: pos for pos, name in enumerate(feature_names)}
    nonlinear_names = (
        "short_rate",
        "zero_rate_5y",
        "heston_variance_global",
        "log_discount_to_time0",
        "trailing_reference_fund_return",
        "inforce_exposure",
        "growth_exposure",
        "income_exposure",
        "account_value_per_initial_premium",
        "locked_income_per_initial_premium",
        "income_pv_proxy_over_account_value",
        "exhausted_income_exposure",
    )
    nonlinear = tuple(index[name] for name in nonlinear_names if name in index)
    interaction_names = (
        ("short_rate", "account_value_per_initial_premium"),
        ("zero_rate_5y", "income_pv_proxy_over_account_value"),
        ("heston_variance_global", "account_value_per_initial_premium"),
        ("income_exposure", "income_pv_proxy_over_account_value"),
        ("inforce_exposure", "account_value_per_initial_premium"),
    )
    interactions = tuple(
        (index[left], index[right])
        for left, right in interaction_names
        if left in index and right in index
    )
    basis_names = ["intercept", *feature_names]
    basis_names.extend(f"square:{feature_names[pos]}" for pos in nonlinear)
    basis_names.extend(
        f"interaction:{feature_names[left]}*{feature_names[right]}"
        for left, right in interactions
    )
    return nonlinear, interactions, tuple(basis_names)


def _raw_scaling(raw: Array) -> tuple[Array, Array]:
    mean = np.mean(raw, axis=0)
    scale = np.std(raw, axis=0, ddof=0)
    scale = np.where(scale > 1.0e-10, scale, 1.0)
    return mean, scale


def _design_matrix(
    raw: Array,
    mean: Array,
    scale: Array,
    nonlinear: Sequence[int],
    interactions: Sequence[tuple[int, int]],
) -> Array:
    standardised = np.clip((raw - mean) / scale, -6.0, 6.0)
    columns = [np.ones(raw.shape[0]), *[standardised[:, pos]
                                       for pos in range(raw.shape[1])]]
    columns.extend(standardised[:, pos] ** 2 for pos in nonlinear)
    columns.extend(
        standardised[:, left] * standardised[:, right]
        for left, right in interactions
    )
    return np.column_stack(columns)


def _ridge_fit_multioutput(design: Array, targets: Array, ridge: float) -> Array:
    if design.ndim != 2 or targets.ndim != 2 or design.shape[0] != targets.shape[0]:
        raise ValueError("Regression design and targets are shape-inconsistent.")
    gram = design.T @ design
    penalty_scale = float(np.trace(gram) / max(gram.shape[0], 1))
    penalty = np.eye(gram.shape[0]) * ridge * max(penalty_scale, 1.0)
    penalty[0, 0] = 0.0
    rhs = design.T @ targets
    try:
        return np.linalg.solve(gram + penalty, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(gram + penalty, rhs, rcond=None)[0]


def _condition_number(design: Array) -> float:
    try:
        return float(np.linalg.cond(design))
    except np.linalg.LinAlgError:
        return float("inf")


def _cross_fitted_action_values(
    *,
    year: int,
    raw_state: Array,
    targets: Array,
    observed_actions: IntArray,
    fold_ids: IntArray,
    n_folds: int,
    ridge: float,
    feature_names: Sequence[str],
) -> tuple[Array, RegressionPolicyYear, list[dict[str, object]]]:
    """Predict all cap alternatives with complete-path cross-fitting."""
    n_paths = raw_state.shape[0]
    n_actions = len(ACTION_CAPS)
    n_outputs = targets.shape[1]
    nonlinear, interactions, basis_names = _basis_specification(feature_names)
    predictions = np.full((n_paths, n_actions, n_outputs), np.nan)

    selection_pool = fold_ids != 0
    for fold in range(n_folds):
        test = fold_ids == fold
        # Fold zero is an evaluation sample and is excluded from every fit,
        # including fits that generate continuation targets for other folds.
        train = selection_pool if fold == 0 else (
            selection_pool & (fold_ids != fold)
        )
        mean, scale = _raw_scaling(raw_state[train])
        test_design = _design_matrix(
            raw_state[test], mean, scale, nonlinear, interactions
        )
        for action in range(n_actions):
            selected = train & (observed_actions == action)
            minimum = max(10, len(basis_names) // 2)
            if int(np.sum(selected)) < minimum:
                raise ValueError(
                    f"Too few training paths for year {year + 1}, action "
                    f"{ACTION_CAPS[action]:.4%}, fold {fold}: "
                    f"{int(np.sum(selected))} < {minimum}. Increase --n-paths."
                )
            train_design = _design_matrix(
                raw_state[selected], mean, scale, nonlinear, interactions
            )
            beta = _ridge_fit_multioutput(
                train_design, targets[selected], ridge
            )
            predictions[test, action, :] = test_design @ beta

    if not np.all(np.isfinite(predictions)):
        raise RuntimeError("Cross-fitted action values contain non-finite entries.")

    full_mean, full_scale = _raw_scaling(raw_state[selection_pool])
    full_design = _design_matrix(
        raw_state, full_mean, full_scale, nonlinear, interactions
    )
    coefficients = np.zeros(
        (n_actions, full_design.shape[1], n_outputs), dtype=float
    )
    diagnostics: list[dict[str, object]] = []
    for action, cap in enumerate(ACTION_CAPS):
        selected = selection_pool & (observed_actions == action)
        beta = _ridge_fit_multioutput(
            full_design[selected], targets[selected], ridge
        )
        coefficients[action] = beta
        fitted = full_design[selected] @ beta
        residual = targets[selected, 0] - fitted[:, 0]
        target_variance = float(np.var(targets[selected, 0]))
        residual_variance = float(np.mean(residual ** 2))
        oof_residual = (
            targets[selected, 0] - predictions[selected, action, 0]
        )
        oof_residual_variance = float(np.mean(oof_residual ** 2))
        r_squared = (
            1.0 - residual_variance / target_variance
            if target_variance > 1.0e-20 else 1.0
        )
        oof_r_squared = (
            1.0 - oof_residual_variance / target_variance
            if target_variance > 1.0e-20 else 1.0
        )
        diagnostics.append({
            "policy_year": year + 1,
            "cap": float(cap),
            "observed_path_count": int(np.sum(selected)),
            "basis_dimension": int(full_design.shape[1]),
            "ridge_multiplier": float(ridge),
            "in_sample_rmse_new_business_csm_proxy": float(
                np.sqrt(residual_variance)
            ),
            "in_sample_r_squared_new_business_csm_proxy": float(r_squared),
            "out_of_fold_rmse_new_business_csm_proxy": float(
                np.sqrt(oof_residual_variance)
            ),
            "out_of_fold_r_squared_new_business_csm_proxy": float(
                oof_r_squared
            ),
            "design_condition_number": _condition_number(full_design[selected]),
        })

    policy = RegressionPolicyYear(
        year=year,
        raw_mean=full_mean,
        raw_scale=full_scale,
        coefficients=coefficients,
        action_caps=ACTION_CAPS.copy(),
    )
    # ``basis_names`` is deterministic from the public feature-name list and
    # is stored once in the policy JSON by the caller.
    return predictions, policy, diagnostics


def _constant_first_year_policy(
    year: int,
    raw_state: Array,
    action_values: Array,
    feature_names: Sequence[str],
) -> RegressionPolicyYear:
    nonlinear, interactions, _ = _basis_specification(feature_names)
    mean, scale = _raw_scaling(raw_state)
    dimension = _design_matrix(
        raw_state[:1], mean, scale, nonlinear, interactions
    ).shape[1]
    coefficients = np.zeros(
        (len(ACTION_CAPS), dimension, action_values.shape[1]), dtype=float
    )
    coefficients[:, 0, :] = action_values
    return RegressionPolicyYear(
        year=year,
        raw_mean=mean,
        raw_scale=scale,
        coefficients=coefficients,
        action_caps=ACTION_CAPS.copy(),
    )


def _backward_induction(
    data: PortfolioPathData,
    action_indices: IntArray,
    *,
    folds: int,
    ridge: float,
    seed: int,
) -> BackwardResult:
    """Cross-fitted Fitted-Q recursion for a repeated discrete control."""
    if data.raw_states is None:
        raise ValueError("Backward induction requires recorded state paths.")
    n_paths, n_years = data.new_business_csm_proxy.shape
    if action_indices.shape != (n_paths, n_years):
        raise ValueError("Action indices and projected rewards are inconsistent.")
    LOGGER.info(
        "Backward induction | %d years | %d actions | %d paths | %d folds",
        n_years, len(ACTION_CAPS), n_paths, folds,
    )
    rng = np.random.default_rng(seed)
    # Stratify complete-path folds by the first action so the cap-selection
    # sample and held-out first-year CSM sample both contain every cap.
    fold_ids = np.empty(n_paths, dtype=np.int64)
    for action in range(len(ACTION_CAPS)):
        rows = np.flatnonzero(action_indices[:, 0] == action)
        assigned = np.resize(np.arange(folds, dtype=np.int64), len(rows))
        fold_ids[rows] = rng.permutation(assigned)

    # Columns: CSM proxy, Product Fees, LIP Fees, Crediting Margin,
    # MVA retained, APS retained, Guarantee Claims, other insurer-funded
    # benefits, operating expenses and hedge-execution costs.
    continuation = np.zeros((n_paths, 10), dtype=float)
    policy_years: list[RegressionPolicyYear] = []
    regression_rows: list[dict[str, object]] = []
    policy_year_rows: list[dict[str, object]] = []
    first_year_action_rows: list[dict[str, object]] = []
    active_policy_years: list[int] = []
    inforce_index = data.state_feature_names.index("inforce_exposure")

    first_cap = float("nan")
    first_outputs = np.zeros(10)
    first_se = float("nan")

    for year in range(n_years - 1, -1, -1):
        if (year == n_years - 1 or year == 0 or (year + 1) % 5 == 0):
            LOGGER.info(
                "Backward induction | processing policy year %d/%d",
                year + 1, n_years,
            )
        year_exposure = data.raw_states[:, year, inforce_index]
        if not np.any(year_exposure > 0.0):
            residual_magnitude = max(
                float(np.max(np.abs(data.new_business_csm_proxy[:, year]))),
                float(np.max(np.abs(data.guarantee_claims[:, year]))),
                float(np.max(np.abs(
                    data.other_insurer_funded_benefits[:, year]
                ))),
                float(np.max(np.abs(data.fees_product[:, year]))),
                float(np.max(np.abs(data.fees_lip[:, year]))),
                float(np.max(np.abs(data.crediting_margin[:, year]))),
                float(np.max(np.abs(data.mva_retained[:, year]))),
                float(np.max(np.abs(data.aps_retained[:, year]))),
                float(np.max(np.abs(data.expenses[:, year]))),
                float(np.max(np.abs(data.hedge_costs[:, year]))),
                float(np.max(np.abs(continuation))),
            )
            materiality = 1.0e-10 * data.representative_initial_premium
            if residual_magnitude > materiality:
                raise RuntimeError(
                    "Policy year %d has zero in-force exposure but residual "
                    "objective magnitude %.6g. Refusing to discard a material "
                    "continuation value." % (year + 1, residual_magnitude)
                )
            continuation.fill(0.0)
            LOGGER.debug(
                "Backward induction | policy year %d economically inactive; "
                "no cap regression fitted.",
                year + 1,
            )
            continue
        active_policy_years.append(year + 1)
        targets = np.column_stack((
            data.new_business_csm_proxy[:, year] + continuation[:, 0],
            data.fees_product[:, year] + continuation[:, 1],
            data.fees_lip[:, year] + continuation[:, 2],
            data.crediting_margin[:, year] + continuation[:, 3],
            data.mva_retained[:, year] + continuation[:, 4],
            data.aps_retained[:, year] + continuation[:, 5],
            data.guarantee_claims[:, year] + continuation[:, 6],
            data.other_insurer_funded_benefits[:, year] + continuation[:, 7],
            data.expenses[:, year] + continuation[:, 8],
            data.hedge_costs[:, year] + continuation[:, 9],
        ))
        observed = action_indices[:, year]

        if year == 0:
            # Fold zero is never used to select the first cap.  Its paths get
            # continuation estimates from regressions trained without fold
            # zero and provide an honest holdout CSM after the cap is frozen.
            selection_paths = fold_ids != 0
            holdout_paths = fold_ids == 0
            selection_values = np.zeros((len(ACTION_CAPS), 10), dtype=float)
            holdout_values = np.zeros((len(ACTION_CAPS), 10), dtype=float)
            selection_standard_errors = np.zeros(len(ACTION_CAPS), dtype=float)
            holdout_standard_errors = np.zeros(len(ACTION_CAPS), dtype=float)
            for action, cap in enumerate(ACTION_CAPS):
                selection = selection_paths & (observed == action)
                holdout = holdout_paths & (observed == action)
                if not selection.any() or not holdout.any():
                    raise RuntimeError(
                        f"First-year selection/holdout coverage is missing for cap {cap}."
                    )
                selection_values[action] = np.mean(targets[selection], axis=0)
                holdout_values[action] = np.mean(targets[holdout], axis=0)
                selection_standard_errors[action] = _standard_error(
                    targets[selection, 0]
                )
                holdout_standard_errors[action] = _standard_error(
                    targets[holdout, 0]
                )
            chosen_action = int(np.argmax(selection_values[:, 0]))
            first_cap = float(ACTION_CAPS[chosen_action])
            first_outputs = holdout_values[chosen_action]
            first_se = holdout_standard_errors[chosen_action]
            LOGGER.info(
                "First-year decision (unscaled representative contract) | "
                "cap %.2f%% | selection Q-CSM %.2f | holdout CSM %.2f | "
                "holdout SE %.2f",
                100.0 * first_cap,
                selection_values[chosen_action, 0],
                first_outputs[0],
                first_se,
            )
            for action, cap in enumerate(ACTION_CAPS):
                first_year_action_rows.append({
                    "cap": float(cap),
                    "cap_percent": 100.0 * float(cap),
                    "selection_estimated_q_new_business_csm_proxy": float(
                        selection_values[action, 0]
                    ),
                    "selection_standard_error_new_business_csm_proxy": float(
                        selection_standard_errors[action]
                    ),
                    "holdout_estimated_q_new_business_csm_proxy": float(
                        holdout_values[action, 0]
                    ),
                    "holdout_estimated_q_fees_product": float(
                        holdout_values[action, 1]
                    ),
                    "holdout_estimated_q_fees_lip": float(
                        holdout_values[action, 2]
                    ),
                    "holdout_estimated_q_crediting_margin": float(
                        holdout_values[action, 3]
                    ),
                    "holdout_estimated_q_mva_retained": float(
                        holdout_values[action, 4]
                    ),
                    "holdout_estimated_q_aps_retained": float(
                        holdout_values[action, 5]
                    ),
                    "holdout_estimated_q_guarantee_claims": float(
                        holdout_values[action, 6]
                    ),
                    "holdout_estimated_q_other_insurer_funded_benefits": float(
                        holdout_values[action, 7]
                    ),
                    "holdout_estimated_q_expenses": float(
                        holdout_values[action, 8]
                    ),
                    "holdout_estimated_q_hedge_costs": float(
                        holdout_values[action, 9]
                    ),
                    "holdout_standard_error_new_business_csm_proxy": float(
                        holdout_standard_errors[action]
                    ),
                    "selection_path_count": int(np.sum(
                        selection_paths & (observed == action)
                    )),
                    "holdout_path_count": int(np.sum(
                        holdout_paths & (observed == action)
                    )),
                    "economically_active": True,
                    "is_optimal_first_year_cap": action == chosen_action,
                })
            first_policy = _constant_first_year_policy(
                year,
                data.raw_states[selection_paths, year, :],
                selection_values,
                data.state_feature_names,
            )
            policy_years.append(first_policy)
            policy_year_rows.append({
                "policy_year": 1,
                "cap": first_cap,
                "selected_fraction": 1.0,
                "mean_selected_cap": first_cap,
                "p10_selected_cap": first_cap,
                "median_selected_cap": first_cap,
                "p90_selected_cap": first_cap,
                "economically_active": True,
                "mean_inforce_exposure": float(np.mean(
                    data.raw_states[:, year, inforce_index]
                )),
            })
            continue

        predictions, fitted_policy, diagnostics = _cross_fitted_action_values(
            year=year,
            raw_state=data.raw_states[:, year, :],
            targets=targets,
            observed_actions=observed,
            fold_ids=fold_ids,
            n_folds=folds,
            ridge=ridge,
            feature_names=data.state_feature_names,
        )
        chosen = np.argmax(predictions[:, :, 0], axis=1)
        rows = np.arange(n_paths)
        continuation = predictions[rows, chosen, :]
        selected_caps = ACTION_CAPS[chosen]
        LOGGER.debug(
            "Backward induction | year %d | mean selected cap %.3f%% | "
            "maximum Q-CSM %.2f (unscaled representative contract)",
            year + 1,
            100.0 * float(np.mean(selected_caps)),
            float(np.mean(continuation[:, 0])),
        )
        mean_cap = float(np.mean(selected_caps))
        quantiles = np.quantile(selected_caps, (0.10, 0.50, 0.90))
        mean_inforce = float(np.mean(data.raw_states[:, year, inforce_index]))
        for action, cap in enumerate(ACTION_CAPS):
            fraction = float(np.mean(chosen == action))
            diagnostics[action]["selected_fraction_cross_fitted"] = fraction
            diagnostics[action]["economically_active"] = True
            policy_year_rows.append({
                "policy_year": year + 1,
                "cap": float(cap),
                "selected_fraction": fraction,
                "mean_selected_cap": mean_cap,
                "p10_selected_cap": float(quantiles[0]),
                "median_selected_cap": float(quantiles[1]),
                "p90_selected_cap": float(quantiles[2]),
                "economically_active": True,
                "mean_inforce_exposure": mean_inforce,
            })
        regression_rows.extend(diagnostics)
        policy_years.append(fitted_policy)

    policy_years.sort(key=lambda item: item.year)
    active_policy_years.sort()
    if not active_policy_years or active_policy_years[0] != 1:
        raise RuntimeError("The LSMC portfolio has no active first policy year.")
    expected_active_years = list(range(1, active_policy_years[-1] + 1))
    if active_policy_years != expected_active_years:
        raise RuntimeError(
            "In-force exposure becomes positive after an inactive policy year; "
            "the economic policy horizon is not contiguous."
        )
    component_csm = (
        first_outputs[1]
        + first_outputs[2]
        + first_outputs[3]
        + first_outputs[4]
        + first_outputs[5]
        - first_outputs[6]
        - first_outputs[7]
        - first_outputs[8]
        - first_outputs[9]
    )
    return BackwardResult(
        first_year_cap=first_cap,
        pv_new_business_csm_proxy=float(first_outputs[0]),
        pv_fees_product=float(first_outputs[1]),
        pv_fees_lip=float(first_outputs[2]),
        pv_crediting_margin=float(first_outputs[3]),
        pv_mva_retained=float(first_outputs[4]),
        pv_aps_retained=float(first_outputs[5]),
        pv_guarantee_claims=float(first_outputs[6]),
        pv_other_insurer_funded_benefits=float(first_outputs[7]),
        pv_expenses=float(first_outputs[8]),
        pv_hedge_costs=float(first_outputs[9]),
        standard_error_new_business_csm_proxy=float(first_se),
        first_year_action_rows=first_year_action_rows,
        policy_year_rows=sorted(
            policy_year_rows,
            key=lambda row: (int(row["policy_year"]), float(row["cap"])),
        ),
        regression_rows=sorted(
            regression_rows,
            key=lambda row: (int(row["policy_year"]), float(row["cap"])),
        ),
        policy_years=policy_years,
        reconciliation_gap=float(first_outputs[0] - component_csm),
        economically_active_policy_years=tuple(active_policy_years),
        inactive_market_tail_year_count=n_years - len(active_policy_years),
    )


def _benchmark_cases() -> list[tuple[str, float, str]]:
    cases: list[tuple[str, float, str]] = [
        (
            "no_crediting_cap_0pct",
            0.0,
            "credited return is identically zero",
        ),
        (
            "fixed_cap_0.2pct",
            0.002,
            "same 0.20% cap in every crediting year",
        ),
    ]
    cases.extend(
        (
            f"fixed_cap_{percent}pct",
            percent / 100.0,
            f"same {percent}% cap in every crediting year",
        )
        for percent in range(1, 21)
    )
    cases.append((
        "uncapped_positive_credit",
        float("inf"),
        "credited return is max(reference-fund return, 0) with no upper cap",
    ))
    return cases


def _summed_csm_components(
    projected: PortfolioPathData,
    rows: slice,
) -> dict[str, Array]:
    """Collapse annual discounted components to one PV per market path."""
    names = (
        "fees_product",
        "fees_lip",
        "crediting_margin",
        "mva_retained",
        "aps_retained",
        "guarantee_claims",
        "other_insurer_funded_benefits",
        "expenses",
        "hedge_costs",
        "terminal_closeout",
    )
    return {
        name: np.sum(np.asarray(getattr(projected, name))[rows], axis=1)
        for name in names
    }


def _csm_benchmark_row(
    *,
    label: str,
    cap: float | None,
    definition: str,
    components: Mapping[str, Array],
    csm_paths: Array,
    best_fixed_paths: Array,
    portfolio_scale: float,
    is_best_fixed: bool,
) -> dict[str, object]:
    """Create one auditable fixed/special-policy CSM result row."""
    difference = portfolio_scale * (csm_paths - best_fixed_paths)

    def mean_pv(name: str) -> float:
        return portfolio_scale * float(np.mean(components[name]))

    future_fees = components["fees_product"] + components["fees_lip"]
    other_margins = (
        components["crediting_margin"]
        + components["mva_retained"]
        + components["aps_retained"]
    )
    total_benefits = (
        components["guarantee_claims"]
        + components["other_insurer_funded_benefits"]
    )
    total_costs = components["expenses"] + components["hedge_costs"]
    reconstructed_csm = future_fees + other_margins - total_benefits - total_costs
    reconciliation = csm_paths - reconstructed_csm
    return {
        "case": label,
        "cap": cap,
        "cap_percent": None if cap is None else 100.0 * cap,
        "definition": definition,
        "pv_product_fees_aud": mean_pv("fees_product"),
        "pv_lip_fees_aud": mean_pv("fees_lip"),
        "pv_future_fees_aud": portfolio_scale * float(np.mean(future_fees)),
        "pv_crediting_margin_aud": mean_pv("crediting_margin"),
        "pv_mva_retained_aud": mean_pv("mva_retained"),
        "pv_aps_retained_aud": mean_pv("aps_retained"),
        "pv_other_insurer_margins_aud": portfolio_scale * float(
            np.mean(other_margins)
        ),
        "pv_total_insurer_inflows_aud": portfolio_scale * float(np.mean(
            future_fees + other_margins
        )),
        "pv_guarantee_claims_aud": mean_pv("guarantee_claims"),
        "pv_other_insurer_funded_benefits_aud": mean_pv(
            "other_insurer_funded_benefits"
        ),
        "pv_total_insurer_funded_benefits_aud": portfolio_scale * float(
            np.mean(total_benefits)
        ),
        "pv_expenses_aud": mean_pv("expenses"),
        "pv_hedge_costs_aud": mean_pv("hedge_costs"),
        "pv_total_costs_aud": portfolio_scale * float(np.mean(total_costs)),
        "estimated_new_business_csm_proxy_aud": portfolio_scale * float(
            np.mean(csm_paths)
        ),
        "standard_error_new_business_csm_proxy_aud": (
            portfolio_scale * _standard_error(csm_paths)
        ),
        "new_business_csm_component_reconciliation_gap_aud": (
            portfolio_scale * float(np.mean(reconciliation))
        ),
        "new_business_csm_component_reconciliation_max_absolute_aud": (
            portfolio_scale * float(np.max(np.abs(reconciliation)))
        ),
        "pv_terminal_closeout_excluded_aud": mean_pv("terminal_closeout"),
        "new_business_csm_difference_vs_best_fixed_1_to_20_aud": float(
            np.mean(difference)
        ),
        "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud": (
            _standard_error(difference)
        ),
        "is_best_fixed_cap_1_to_20": is_best_fixed,
        "n_common_random_number_paths": int(csm_paths.size),
    }


def _evaluate_fixed_benchmarks(
    *,
    base_scenarios: ScenarioSet,
    n_years: int,
    batch_size: int,
    product: IndexLinkedLifetimeIncomeProduct,
    model_points: PolicyholderModelPointSet,
    behaviour: BehaviourModel,
    mortality: MortalityTable,
    expenses: ExpenseAssumptions,
    projection_config: ProjectionConfig,
    portfolio_scale: float,
    model_point_log_interval: int,
) -> tuple[list[dict[str, object]], dict[str, Array]]:
    """Direct fixed-policy projections with paired common market paths."""
    cases = _benchmark_cases()
    path_values: dict[str, Array] = {}
    component_paths: dict[str, dict[str, Array]] = {}
    batch_count = int(np.ceil(len(cases) / batch_size))
    LOGGER.info(
        "Fixed-cap benchmarks | %d cases | %d batches | %d CRN paths/case",
        len(cases), batch_count, base_scenarios.n_paths,
    )

    for batch_number, start in enumerate(
        range(0, len(cases), batch_size), start=1
    ):
        batch = cases[start:start + batch_size]
        labels = ", ".join(label for label, _, _ in batch)
        batch_started = time.perf_counter()
        LOGGER.info(
            "Benchmark batch %d/%d | %s", batch_number, batch_count, labels
        )
        repeated = _repeat_scenarios(base_scenarios, len(batch))
        cap_matrix = np.vstack([
            np.full((base_scenarios.n_paths, n_years), cap, dtype=float)
            for _, cap, _ in batch
        ])
        projected = _aggregate_portfolio_paths(
            scenarios=repeated,
            cap_matrix=cap_matrix,
            product=product,
            model_points=model_points,
            behaviour=behaviour,
            mortality=mortality,
            expenses=expenses,
            projection_config=projection_config,
            collect_states=False,
            progress_label=f"Benchmark batch {batch_number}/{batch_count}",
            model_point_log_interval=model_point_log_interval,
        )
        for position, (label, _, _) in enumerate(batch):
            lo = position * base_scenarios.n_paths
            hi = (position + 1) * base_scenarios.n_paths
            components = _summed_csm_components(projected, slice(lo, hi))
            csm_paths = np.sum(
                projected.new_business_csm_proxy[lo:hi], axis=1
            )
            path_values[label] = csm_paths
            component_paths[label] = components
        LOGGER.info(
            "Benchmark batch %d/%d complete | elapsed %.1fs",
            batch_number, batch_count, time.perf_counter() - batch_started,
        )

    fixed_labels = [f"fixed_cap_{percent}pct" for percent in range(1, 21)]
    best_label = max(
        fixed_labels,
        key=lambda label: float(np.mean(path_values[label])),
    )
    best_paths = path_values[best_label]
    LOGGER.info(
        "Best fixed 1%%-20%% benchmark | %s | New Business CSM proxy %.2f",
        best_label, portfolio_scale * float(np.mean(best_paths)),
    )
    rows: list[dict[str, object]] = []
    for label, cap, definition in cases:
        csm_paths = path_values[label]
        row = _csm_benchmark_row(
            label=label,
            cap=None if np.isposinf(cap) else float(cap),
            definition=definition,
            components=component_paths[label],
            csm_paths=csm_paths,
            best_fixed_paths=best_paths,
            portfolio_scale=portfolio_scale,
            is_best_fixed=label == best_label,
        )
        rows.append(row)
        LOGGER.debug(
            "Benchmark result | %s | future fees=%.2f | other margins=%.2f | "
            "benefits=%.2f | expenses=%.2f | hedge costs=%.2f | "
            "CSM proxy=%.2f | SE=%.2f | terminal closeout excluded=%.2f",
            label,
            row["pv_future_fees_aud"],
            row["pv_other_insurer_margins_aud"],
            row["pv_total_insurer_funded_benefits_aud"],
            row["pv_expenses_aud"],
            row["pv_hedge_costs_aud"],
            row["estimated_new_business_csm_proxy_aud"],
            row["standard_error_new_business_csm_proxy_aud"],
            row["pv_terminal_closeout_excluded_aud"],
        )
    return rows, path_values


def _evaluate_explicit_schedule_benchmark(
    *,
    label: str,
    definition: str,
    cap_schedule: Array,
    scenarios: ScenarioSet,
    product: IndexLinkedLifetimeIncomeProduct,
    model_points: PolicyholderModelPointSet,
    behaviour: BehaviourModel,
    mortality: MortalityTable,
    expenses: ExpenseAssumptions,
    projection_config: ProjectionConfig,
    portfolio_scale: float,
    comparison_paths: Array,
    model_point_log_interval: int,
) -> tuple[dict[str, object], Array]:
    schedule = np.asarray(cap_schedule, dtype=float)
    if schedule.ndim != 1 or schedule.size <= 0:
        raise ValueError("cap_schedule must be a non-empty one-dimensional array.")
    if np.any(np.isnan(schedule)) or np.any(schedule < 0.0):
        raise ValueError("cap_schedule must be non-negative and not NaN.")
    comparison = np.asarray(comparison_paths, dtype=float)
    if comparison.shape != (scenarios.n_paths,) or not np.all(np.isfinite(comparison)):
        raise ValueError("comparison_paths must be finite and match scenario paths.")
    cap_matrix = np.broadcast_to(
        schedule, (scenarios.n_paths, schedule.size)
    ).copy()
    projected = _aggregate_portfolio_paths(
        scenarios=scenarios,
        cap_matrix=cap_matrix,
        product=product,
        model_points=model_points,
        behaviour=behaviour,
        mortality=mortality,
        expenses=expenses,
        projection_config=projection_config,
        collect_states=False,
        progress_label=label,
        model_point_log_interval=model_point_log_interval,
    )
    components = _summed_csm_components(projected, slice(None))
    csm_paths = np.sum(projected.new_business_csm_proxy, axis=1)
    row = _csm_benchmark_row(
        label=label,
        cap=None,
        definition=definition,
        components=components,
        csm_paths=csm_paths,
        best_fixed_paths=comparison,
        portfolio_scale=portfolio_scale,
        is_best_fixed=False,
    )
    return row, csm_paths


def _policy_payload(
    result: BackwardResult,
    feature_names: Sequence[str],
    projection_semantics: Mapping[str, object],
) -> dict[str, object]:
    nonlinear, interactions, basis_names = _basis_specification(feature_names)
    return {
        "engine_version": ENGINE_VERSION,
        "method": "cross_fitted_control_randomisation_fitted_q",
        "optimization_direction": "maximize",
        "projection_semantics": dict(projection_semantics),
        "objective_outputs": [
            "new_business_csm_proxy",
            "product_fees",
            "lip_fees",
            "crediting_margin",
            "mva_retained",
            "aps_retained",
            "guarantee_claims",
            "other_insurer_funded_benefits",
            "expenses",
            "hedge_costs",
        ],
        "other_insurer_funded_benefit_cashflow_keys": list(
            OTHER_INSURER_FUNDED_BENEFIT_KEYS
        ),
        "excluded_objective_cashflows": [
            "income_paid",
            "death_benefits",
            "surrender_benefits",
            "partial_withdrawals",
            "terminal_closeout",
        ],
        "action_caps": ACTION_CAPS.tolist(),
        "raw_state_features": list(feature_names),
        "economically_active_policy_years": list(
            result.economically_active_policy_years
        ),
        "inactive_market_tail_year_count": (
            result.inactive_market_tail_year_count
        ),
        "basis": {
            "names": list(basis_names),
            "standardisation": "per policy year; clipped to [-6, 6]",
            "squared_raw_feature_indices": list(nonlinear),
            "interaction_raw_feature_indices": [list(pair) for pair in interactions],
        },
        "years": [
            {
                "policy_year": item.year + 1,
                "economically_active": True,
                "raw_mean": item.raw_mean.tolist(),
                "raw_scale": item.raw_scale.tolist(),
                "coefficients_by_action_basis_output": item.coefficients.tolist(),
            }
            for item in result.policy_years
        ],
        "application_rule": (
            "At each economically active anniversary form only the listed "
            "pre-action state, apply that year's scaling and basis, predict "
            "all action values, and select the cap with the largest approximate "
            "New Business CSM prediction. No policy is fitted after all covered "
            "lives have zero in-force exposure."
        ),
    }


def _scaled_first_year_rows(
    rows: Sequence[Mapping[str, object]],
    scale: float,
) -> list[dict[str, object]]:
    monetary = (
        "selection_estimated_q_new_business_csm_proxy",
        "selection_standard_error_new_business_csm_proxy",
        "holdout_estimated_q_new_business_csm_proxy",
        "holdout_estimated_q_fees_product",
        "holdout_estimated_q_fees_lip",
        "holdout_estimated_q_crediting_margin",
        "holdout_estimated_q_mva_retained",
        "holdout_estimated_q_aps_retained",
        "holdout_estimated_q_guarantee_claims",
        "holdout_estimated_q_other_insurer_funded_benefits",
        "holdout_estimated_q_expenses",
        "holdout_estimated_q_hedge_costs",
        "holdout_standard_error_new_business_csm_proxy",
    )
    output: list[dict[str, object]] = []
    for source in rows:
        row = dict(source)
        for key in monetary:
            row[f"{key}_aud"] = scale * float(row.pop(key))
        output.append(row)
    return output


def _load_plotting_backend():
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        from matplotlib import ticker
    except ImportError as exc:
        raise RuntimeError(
            "Matplotlib is required for the requested graphics. Install the "
            "repository dependencies, for example: pip install -e ."
        ) from exc
    return matplotlib, plt, ticker


def _aud_formatter(value: float, _position: object) -> str:
    absolute = abs(value)
    if absolute >= 1.0e6:
        return f"{value / 1.0e6:.1f}m"
    if absolute >= 1.0e3:
        return f"{value / 1.0e3:.0f}k"
    return f"{value:.0f}"


def _save_figure(
    *,
    figure,
    pyplot,
    directory: Path,
    stem: str,
    plot_format: str,
    dpi: int,
) -> list[Path]:
    formats = ("png", "svg") if plot_format == "both" else (plot_format,)
    paths: list[Path] = []
    for extension in formats:
        path = directory / f"{stem}.{extension}"
        save_kwargs: dict[str, object] = {"bbox_inches": "tight"}
        if extension == "png":
            save_kwargs["dpi"] = dpi
        figure.savefig(path, **save_kwargs)
        paths.append(path)
        LOGGER.info("Plot written | %s", path)
    pyplot.close(figure)
    return paths


def _plot_first_year_choice(
    *,
    pyplot,
    ticker,
    rows: Sequence[Mapping[str, object]],
    directory: Path,
    plot_format: str,
    dpi: int,
) -> list[Path]:
    ordered = sorted(rows, key=lambda row: float(row["cap_percent"]))
    caps = np.asarray([float(row["cap_percent"]) for row in ordered])
    selection = np.asarray([
        float(row["selection_estimated_q_new_business_csm_proxy_aud"])
        for row in ordered
    ])
    selection_se = np.asarray([
        float(row["selection_standard_error_new_business_csm_proxy_aud"])
        for row in ordered
    ])
    holdout = np.asarray([
        float(row["holdout_estimated_q_new_business_csm_proxy_aud"])
        for row in ordered
    ])
    holdout_se = np.asarray([
        float(row["holdout_standard_error_new_business_csm_proxy_aud"])
        for row in ordered
    ])
    chosen = next(row for row in ordered if row["is_optimal_first_year_cap"])
    chosen_cap = float(chosen["cap_percent"])

    figure, axis = pyplot.subplots(figsize=(10.5, 6.2))
    axis.errorbar(
        caps, selection, yerr=1.96 * selection_se,
        marker="o", markersize=4, linewidth=1.5, capsize=2,
        label="Selection folds: estimated Q",
    )
    axis.errorbar(
        caps, holdout, yerr=1.96 * holdout_se,
        marker="s", markersize=3.5, linewidth=1.2, capsize=2,
        linestyle="--", label="Held-out fold: estimated Q",
    )
    axis.axvline(
        chosen_cap, color="black", linewidth=1.2, linestyle=":",
        label=f"Chosen first-year cap: {chosen_cap:g}%",
    )
    axis.axhline(0.0, color="grey", linewidth=0.8)
    axis.set_xlabel("First-year cap (%)")
    axis.set_ylabel("Approximate New Business CSM (AUD; higher is better)")
    axis.set_title("First-year cap decision: CSM-maximising Fitted-Q values")
    axis.yaxis.set_major_formatter(ticker.FuncFormatter(_aud_formatter))
    axis.grid(alpha=0.25)
    axis.legend(loc="best")
    figure.text(
        0.01, 0.01,
        "Error bars show ±1.96 × conditional Monte-Carlo SE. They exclude "
        "regression and model-selection uncertainty.",
        fontsize=8,
    )
    figure.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    return _save_figure(
        figure=figure, pyplot=pyplot, directory=directory,
        stem="01_first_year_cap_choice", plot_format=plot_format, dpi=dpi,
    )


def _plot_fixed_cap_checks(
    *,
    pyplot,
    ticker,
    benchmark_rows: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
    directory: Path,
    plot_format: str,
    dpi: int,
) -> list[Path]:
    numeric = sorted(
        (row for row in benchmark_rows if row["cap_percent"] is not None),
        key=lambda row: float(row["cap_percent"]),
    )
    caps = np.asarray([float(row["cap_percent"]) for row in numeric])
    csm = np.asarray([
        float(row["estimated_new_business_csm_proxy_aud"]) for row in numeric
    ])
    se = np.asarray([
        float(row["standard_error_new_business_csm_proxy_aud"])
        for row in numeric
    ])
    difference = np.asarray([
        float(row[
            "new_business_csm_difference_vs_best_fixed_1_to_20_aud"
        ]) for row in numeric
    ])
    paired_se = np.asarray([
        float(row[
            "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud"
        ]) for row in numeric
    ])
    best = next(row for row in numeric if row["is_best_fixed_cap_1_to_20"])
    best_cap = float(best["cap_percent"])

    figure, (top, bottom) = pyplot.subplots(
        2, 1, figsize=(10.5, 8.2), sharex=True,
        gridspec_kw={"height_ratios": (2.0, 1.0)},
    )
    top.errorbar(
        caps, csm, yerr=1.96 * se, marker="o", linewidth=1.5,
        markersize=4, capsize=2, label="Direct fixed-cap projection",
    )
    top.axvline(
        best_cap, color="black", linestyle=":", linewidth=1.2,
        label=f"Best fixed 1%-20% cap: {best_cap:g}%",
    )
    special_styles = {
        "uncapped_positive_credit": ("No upper cap", "tab:green", "--"),
        "lsmc_first_year_then_best_fixed_continuation": (
            "LSMC year 1, then best fixed", "tab:purple", "-."
        ),
    }
    for case, (label, colour, style) in special_styles.items():
        matching = [row for row in benchmark_rows if row["case"] == case]
        if matching:
            top.axhline(
                float(matching[0]["estimated_new_business_csm_proxy_aud"]),
                color=colour, linestyle=style, linewidth=1.2, label=label,
            )
    top.axhline(
        float(summary["estimated_optimal_new_business_csm_proxy_aud"]),
        color="tab:red", linestyle=":", linewidth=1.4,
        label="Held-out Bellman estimate (not direct rollout)",
    )
    top.set_ylabel("Approximate New Business CSM (AUD)")
    top.set_title("CSM-maximising fixed-cap and special-policy checks")
    top.yaxis.set_major_formatter(ticker.FuncFormatter(_aud_formatter))
    top.grid(alpha=0.25)
    top.legend(loc="best", fontsize=8)

    bottom.errorbar(
        caps, difference, yerr=1.96 * paired_se,
        marker="o", linewidth=1.2, markersize=3.5, capsize=2,
        color="tab:blue",
    )
    bottom.axhline(0.0, color="black", linewidth=0.9)
    bottom.set_xlabel("Constant annual cap (%)")
    bottom.set_ylabel("Paired Δ CSM\ncase − best fixed (AUD)")
    bottom.yaxis.set_major_formatter(ticker.FuncFormatter(_aud_formatter))
    bottom.grid(alpha=0.25)
    figure.text(
        0.01, 0.01,
        "0% means zero crediting. 'No upper cap' means max(fund return, 0). "
        "Paired intervals use common market paths; positive Δ CSM is better.",
        fontsize=8,
    )
    figure.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    return _save_figure(
        figure=figure, pyplot=pyplot, directory=directory,
        stem="02_fixed_cap_sanity_checks", plot_format=plot_format, dpi=dpi,
    )


def _plot_fixed_cap_decomposition(
    *,
    pyplot,
    ticker,
    benchmark_rows: Sequence[Mapping[str, object]],
    directory: Path,
    plot_format: str,
    dpi: int,
) -> list[Path]:
    numeric = sorted(
        (row for row in benchmark_rows if row["cap_percent"] is not None),
        key=lambda row: float(row["cap_percent"]),
    )
    caps = np.asarray([float(row["cap_percent"]) for row in numeric])
    product_fees = np.asarray([
        float(row["pv_product_fees_aud"]) for row in numeric
    ])
    lip_fees = np.asarray([
        float(row["pv_lip_fees_aud"]) for row in numeric
    ])
    other_margins = np.asarray([
        float(row["pv_other_insurer_margins_aud"]) for row in numeric
    ])
    claims = -np.asarray([
        float(row["pv_guarantee_claims_aud"]) for row in numeric
    ])
    other_benefits = -np.asarray([
        float(row["pv_other_insurer_funded_benefits_aud"])
        for row in numeric
    ])
    expenses = -np.asarray([
        float(row["pv_expenses_aud"]) for row in numeric
    ])
    hedge_costs = -np.asarray([
        float(row["pv_hedge_costs_aud"]) for row in numeric
    ])
    csm = np.asarray([
        float(row["estimated_new_business_csm_proxy_aud"]) for row in numeric
    ])
    se = np.asarray([
        float(row["standard_error_new_business_csm_proxy_aud"])
        for row in numeric
    ])

    figure, axis = pyplot.subplots(figsize=(11.5, 7.0))
    axis.plot(caps, product_fees, marker="s", label="+ Product fees")
    axis.plot(caps, lip_fees, marker="^", label="+ LIP fees")
    axis.plot(caps, other_margins, marker="D", label="+ Other insurer margins")
    axis.plot(caps, claims, marker="o", label="− Guarantee claims")
    if np.any(np.abs(other_benefits) > 0.0):
        axis.plot(
            caps, other_benefits, marker="v",
            label="− Other insurer-funded benefits",
        )
    axis.plot(caps, expenses, marker="P", label="− Operating expenses")
    axis.plot(caps, hedge_costs, marker="X", label="− Hedge execution costs")
    axis.plot(
        caps, csm, color="black", linewidth=2.0,
        label="Approximate New Business CSM",
    )
    axis.fill_between(
        caps, csm - 1.96 * se, csm + 1.96 * se,
        color="black", alpha=0.10, label="CSM ±1.96 MC SE",
    )
    axis.axhline(0.0, color="grey", linewidth=0.8)
    axis.set_xlabel("Constant annual cap (%)")
    axis.set_ylabel("Present value contribution (AUD)")
    axis.set_title(
        "Fixed-cap New Business CSM proxy decomposition "
        "(terminal closeout excluded)"
    )
    axis.yaxis.set_major_formatter(ticker.FuncFormatter(_aud_formatter))
    axis.grid(alpha=0.25)
    axis.legend(loc="best", fontsize=8)
    figure.tight_layout()
    return _save_figure(
        figure=figure, pyplot=pyplot, directory=directory,
        stem="03_fixed_cap_pv_decomposition", plot_format=plot_format, dpi=dpi,
    )


def _plot_dynamic_policy(
    *,
    pyplot,
    policy_rows: Sequence[Mapping[str, object]],
    market_policy_year_count: int,
    directory: Path,
    plot_format: str,
    dpi: int,
) -> list[Path]:
    maximum_active_year = max(int(row["policy_year"]) for row in policy_rows)
    if market_policy_year_count < maximum_active_year:
        raise ValueError("Market policy horizon cannot precede the active horizon.")
    matrix = np.zeros((len(ACTION_CAPS), market_policy_year_count))
    if market_policy_year_count > maximum_active_year:
        matrix[:, maximum_active_year:] = np.nan
    yearly: dict[int, Mapping[str, object]] = {}
    for row in policy_rows:
        year = int(row["policy_year"])
        cap = float(row["cap"])
        action = int(np.argmin(np.abs(ACTION_CAPS - cap)))
        matrix[action, year - 1] = float(row["selected_fraction"])
        yearly.setdefault(year, row)
    years = np.asarray(sorted(yearly))
    mean = 100.0 * np.asarray([
        float(yearly[year]["mean_selected_cap"]) for year in years
    ])
    median = 100.0 * np.asarray([
        float(yearly[year]["median_selected_cap"]) for year in years
    ])
    p10 = 100.0 * np.asarray([
        float(yearly[year]["p10_selected_cap"]) for year in years
    ])
    p90 = 100.0 * np.asarray([
        float(yearly[year]["p90_selected_cap"]) for year in years
    ])
    inforce = np.asarray([
        float(yearly[year]["mean_inforce_exposure"]) for year in years
    ])

    figure, (heat, band, exposure_axis) = pyplot.subplots(
        3, 1, figsize=(12.0, 10.5), sharex=True,
        gridspec_kw={"height_ratios": (2.2, 1.2, 0.8)},
    )
    colormap = pyplot.get_cmap("Blues").copy()
    colormap.set_bad(color="#e6e6e6")
    image = heat.imshow(
        matrix, origin="lower", aspect="auto", interpolation="nearest",
        vmin=0.0, vmax=max(float(np.nanmax(matrix)), 1.0e-12), cmap=colormap,
        extent=(0.5, market_policy_year_count + 0.5,
                -0.5, len(ACTION_CAPS) - 0.5),
    )
    tick_positions = np.arange(0, len(ACTION_CAPS), 2)
    heat.set_yticks(tick_positions)
    heat.set_yticklabels([
        f"{100.0 * ACTION_CAPS[position]:g}%" for position in tick_positions
    ])
    heat.set_ylabel("Cap action")
    heat.set_title(
        "CSM-maximising cross-fitted cap choices; grey tail has zero exposure "
        "(not an independent rollout)"
    )
    figure.colorbar(image, ax=heat, label="Selected path fraction", pad=0.01)

    band.fill_between(years, p10, p90, alpha=0.22, label="p10–p90 state distribution")
    band.plot(years, mean, linewidth=1.5, label="Mean selected cap")
    band.plot(years, median, linewidth=1.2, linestyle="--", label="Median")
    band.set_ylabel("Selected cap (%)")
    band.grid(alpha=0.25)
    band.legend(loc="best")

    exposure_years = years
    exposure_values = inforce
    if market_policy_year_count > maximum_active_year:
        exposure_years = np.append(exposure_years, maximum_active_year + 1)
        exposure_values = np.append(exposure_values, 0.0)
        inactive_start = maximum_active_year + 0.5
        inactive_end = market_policy_year_count + 0.5
        for axis in (heat, band, exposure_axis):
            axis.axvspan(
                inactive_start, inactive_end,
                color="tab:grey", alpha=0.14, linewidth=0.0,
            )
    exposure_axis.plot(
        exposure_years, exposure_values, color="tab:grey", linewidth=1.5
    )
    exposure_axis.fill_between(
        exposure_years, 0.0, exposure_values,
        color="tab:grey", alpha=0.15,
    )
    exposure_axis.set_xlabel("Policy year")
    exposure_axis.set_ylabel("Mean in-force\nexposure")
    exposure_axis.set_ylim(bottom=0.0)
    exposure_axis.set_xlim(0.5, market_policy_year_count + 0.5)
    exposure_axis.grid(alpha=0.25)
    figure.tight_layout()
    return _save_figure(
        figure=figure, pyplot=pyplot, directory=directory,
        stem="04_dynamic_cap_policy", plot_format=plot_format, dpi=dpi,
    )


def _plot_regression_diagnostics(
    *,
    pyplot,
    rows: Sequence[Mapping[str, object]],
    directory: Path,
    plot_format: str,
    dpi: int,
) -> list[Path]:
    if not rows:
        LOGGER.warning("Regression diagnostic plot skipped: no regression rows.")
        return []
    years = sorted({int(row["policy_year"]) for row in rows})
    year_index = {year: position for position, year in enumerate(years)}
    shape = (len(ACTION_CAPS), len(years))
    r_squared = np.full(shape, np.nan)
    log_condition = np.full(shape, np.nan)
    coverage = np.full(shape, np.nan)
    for row in rows:
        action = int(np.argmin(np.abs(ACTION_CAPS - float(row["cap"]))))
        column = year_index[int(row["policy_year"])]
        r_squared[action, column] = float(
            row["out_of_fold_r_squared_new_business_csm_proxy"]
        )
        condition = max(float(row["design_condition_number"]), 1.0)
        log_condition[action, column] = min(np.log10(condition), 16.0)
        coverage[action, column] = (
            float(row["observed_path_count"]) / float(row["basis_dimension"])
        )

    figure, axes = pyplot.subplots(3, 1, figsize=(12.0, 11.0), sharex=True)
    specifications = (
        (np.clip(r_squared, -1.0, 1.0), "coolwarm", -1.0, 1.0,
         "Out-of-fold R² (clipped to [-1, 1])"),
        (log_condition, "viridis", None, None,
         "log10 design condition number (capped at 16)"),
        (coverage, "cividis", None, None,
         "Observed selection paths / basis dimension"),
    )
    for axis, (values, cmap, minimum, maximum, title) in zip(axes, specifications):
        image = axis.imshow(
            values, origin="lower", aspect="auto", interpolation="nearest",
            cmap=cmap, vmin=minimum, vmax=maximum,
            extent=(years[0] - 0.5, years[-1] + 0.5,
                    -0.5, len(ACTION_CAPS) - 0.5),
        )
        tick_positions = np.arange(0, len(ACTION_CAPS), 2)
        axis.set_yticks(tick_positions)
        axis.set_yticklabels([
            f"{100.0 * ACTION_CAPS[position]:g}%" for position in tick_positions
        ])
        axis.set_ylabel("Cap action")
        axis.set_title(title)
        figure.colorbar(image, ax=axis, pad=0.01)
    axes[-1].set_xlabel("Policy year (year 1 is a direct mean, not a regression)")
    figure.suptitle(
        "New Business CSM Fitted-Q diagnostics (active years only)",
        y=1.01,
    )
    figure.tight_layout()
    return _save_figure(
        figure=figure, pyplot=pyplot, directory=directory,
        stem="05_regression_diagnostics", plot_format=plot_format, dpi=dpi,
    )


def _generate_plots(
    *,
    plotting_backend,
    output: Path,
    first_year_rows: Sequence[Mapping[str, object]],
    policy_rows: Sequence[Mapping[str, object]],
    regression_rows: Sequence[Mapping[str, object]],
    benchmark_rows: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
    plot_format: str,
    dpi: int,
) -> tuple[list[Path], str]:
    matplotlib, pyplot, ticker = plotting_backend
    plot_directory = output / "plots"
    plot_directory.mkdir(parents=True, exist_ok=True)
    stems = (
        "01_first_year_cap_choice",
        "02_fixed_cap_sanity_checks",
        "03_fixed_cap_pv_decomposition",
        "04_dynamic_cap_policy",
        "05_regression_diagnostics",
    )
    for stem in stems:
        for extension in ("png", "svg"):
            stale = plot_directory / f"{stem}.{extension}"
            if stale.is_file():
                stale.unlink()
                LOGGER.debug("Removed stale plot from previous run | %s", stale)
    paths: list[Path] = []
    paths.extend(_plot_first_year_choice(
        pyplot=pyplot, ticker=ticker, rows=first_year_rows,
        directory=plot_directory, plot_format=plot_format, dpi=dpi,
    ))
    paths.extend(_plot_fixed_cap_checks(
        pyplot=pyplot, ticker=ticker, benchmark_rows=benchmark_rows,
        summary=summary, directory=plot_directory,
        plot_format=plot_format, dpi=dpi,
    ))
    paths.extend(_plot_fixed_cap_decomposition(
        pyplot=pyplot, ticker=ticker, benchmark_rows=benchmark_rows,
        directory=plot_directory, plot_format=plot_format, dpi=dpi,
    ))
    paths.extend(_plot_dynamic_policy(
        pyplot=pyplot, policy_rows=policy_rows,
        market_policy_year_count=(
            int(summary["last_economically_active_policy_year"])
            + int(summary["inactive_market_tail_year_count_omitted_from_policy"])
        ),
        directory=plot_directory, plot_format=plot_format, dpi=dpi,
    ))
    paths.extend(_plot_regression_diagnostics(
        pyplot=pyplot, rows=regression_rows,
        directory=plot_directory, plot_format=plot_format, dpi=dpi,
    ))
    return paths, str(matplotlib.__version__)


def main() -> None:
    args = parse_args()
    run_started = time.perf_counter()
    output = args.output.expanduser().resolve()
    preexisting_outputs = list(output.glob("*")) if output.is_dir() else []
    output.mkdir(parents=True, exist_ok=True)
    log_path = _configure_logging(output, args.log_level)
    LOGGER.info("Crediting-cap LSMC run started | output=%s", output)
    LOGGER.info(
        "Controls | training paths=%d | benchmark paths=%d | seed=%d | "
        "folds=%d | Heston substeps=%d | caps=%s",
        args.n_paths,
        args.benchmark_paths,
        args.seed,
        args.cross_fit_folds,
        args.heston_substeps,
        ",".join(f"{100.0 * cap:g}%" for cap in ACTION_CAPS),
    )
    if preexisting_outputs:
        LOGGER.warning(
            "Output directory already contains %d item(s); matching result "
            "files and plots will be overwritten.",
            len(preexisting_outputs),
        )
    with _logged_stage("Validate headless Matplotlib plotting backend"):
        plotting_backend = _load_plotting_backend()

    with _logged_stage("Load market assumptions"):
        market = load_market_assumptions(args.zero_curve, args.model_parameters)
    LOGGER.debug("Market inputs | %s", market.source_metadata())
    generic_product = IndexLinkedLifetimeIncomeProduct(
        reference_fund=ReferenceFundSpec(),
        fees=FeeSpec(lip_waived_in_income_phase_if_aps=False),
        dividend_yield={
            index: parameters.dividend_yield
            for index, parameters in market.esg.equity.items()
        },
    )
    cost_seed_projection = ProjectionConfig(record_paths=False, heston_cos=False)
    with _logged_stage("Load cost assumptions"):
        costs = load_cost_assumptions(
            args.cost_assumptions,
            assumption_set_id=args.cost_assumption_set,
            value_basis="base",
            product=generic_product,
            projection=cost_seed_projection,
        )
    with _logged_stage("Load dynamic behaviour assumptions"):
        loaded_behaviour = load_dynamic_behaviour_assumptions(
            args.dynamic_behaviour,
            assumption_set_id=args.behaviour_assumption_set,
            value_basis="base",
        )
    # Resolve Take-up deterministically from each model point's effective
    # Election anniversary.  Branch-specific dynamic/static treatment is
    # applied below exactly as in the active portfolio wrapper.
    behaviour = replace(
        loaded_behaviour.behaviour,
        take_up=replace(loaded_behaviour.behaviour.take_up, mode="deterministic"),
    )
    with _logged_stage("Load and validate policyholder model points"):
        model_points = load_policyholder_model_points(
            args.model_points,
            expected_market_parameter_set_id=market.parameter_set_id,
            expected_yield_curve_id=market.curve_id,
        )
    mortality = MortalityTable.gompertz_makeham()

    treatment_rows = _model_point_treatment_rows(
        model_points,
        costs.product,
        mortality,
        behaviour,
        loaded_behaviour.behaviour,
    )
    effective_start_override_count = sum(
        bool(row["effective_start_overrides_scheduled_start"])
        for row in treatment_rows
    )
    joint_life_count = sum(bool(row["spouse"]) for row in treatment_rows)
    joint_continue_income_count = sum(
        point.policy.spouse
        and point.policy.spouse_death_election
        == SpouseDeathElection.CONTINUE_INCOME
        for point in model_points.model_points
    )
    joint_lump_sum_count = joint_life_count - joint_continue_income_count
    dynamic_behaviour_active = (
        behaviour.use_dynamic or behaviour.use_dynamic_withdrawals
    )
    base_branch_behaviour = (
        "dynamic_state_dependent" if dynamic_behaviour_active else "static_base"
    )
    behaviour_treatment_by_branch = {
        "single_life": base_branch_behaviour,
        "continue_income_joint_conditional": (
            "static_base" if joint_continue_income_count else "not_applicable"
        ),
        "continue_income_single_fallback": (
            base_branch_behaviour
            if joint_continue_income_count else "not_applicable"
        ),
        "lump_sum_spouse_joint_and_single_fallback": (
            base_branch_behaviour if joint_lump_sum_count else "not_applicable"
        ),
    }
    joint_life_behaviour_treatment = (
        "mixed_by_spouse_election: Continue-Income joint static with base "
        "Single fallback; Lump-Sum joint and fallback use base Behaviour"
        if joint_continue_income_count and joint_lump_sum_count
        else "joint_branch_static_base_single_fallback_dynamic_for_continue_income"
        if joint_continue_income_count and dynamic_behaviour_active
        else "joint_and_single_branches_static_base_for_continue_income"
        if joint_continue_income_count
        else "dynamic_joint_and_fallback_for_lump_sum_spouse_option"
        if joint_life_count and dynamic_behaviour_active
        else "static_base_for_lump_sum_spouse_option"
        if joint_life_count
        else "not_applicable"
    )
    projection_semantics: dict[str, object] = {
        "engine_version": ENGINE_VERSION,
        "source_behaviour_regime": loaded_behaviour.behaviour.regime,
        "base_behaviour_regime": behaviour.regime,
        "dynamic_lapse_or_withdrawal_active_on_base_behaviour": (
            dynamic_behaviour_active
        ),
        "behaviour_treatment_by_branch": behaviour_treatment_by_branch,
        "source_income_take_up_mode": loaded_behaviour.behaviour.take_up.mode,
        "effective_income_take_up_mode": behaviour.take_up.mode,
        "dynamic_take_up_coefficients_applied": False,
        "take_up_override_reason": (
            "deterministic effective model-point Election convention; also "
            "required for Joint-Life spouse-survival fallback compatibility"
        ),
        "income_take_up_source": (
            "effective_model_point_income_start_year_with_minimum_wait_and_"
            "automatic_age_backstop"
        ),
        "effective_income_start_override_model_point_count": (
            effective_start_override_count
        ),
        "product_min_years_before_income": int(
            costs.product.min_years_before_income
        ),
        "product_automatic_income_start_age": float(
            costs.product.automatic_income_start_age
        ),
        "distinct_effective_income_start_years": sorted({
            int(row["effective_income_start_year"])
            for row in treatment_rows
        }),
        "effective_income_start_state_cohorts_added": len({
            int(row["effective_income_start_year"])
            for row in treatment_rows
        }) > 1,
        "effective_income_start_state_cohorts": (
            "included when more than one effective start year is present"
        ),
        "joint_life_model_point_count": joint_life_count,
        "joint_continue_income_model_point_count": joint_continue_income_count,
        "joint_lump_sum_model_point_count": joint_lump_sum_count,
        "joint_life_election_treatment": (
            "spouse_survival_weighted_joint_and_single_life_fallback"
            if joint_life_count else "not_applicable_single_life_portfolio"
        ),
        "joint_life_dependence": (
            "independent_lives" if joint_life_count else "not_applicable"
        ),
        "joint_life_behaviour_treatment": joint_life_behaviour_treatment,
        "joint_life_four_state_account_cohorts": (
            False if joint_life_count else None
        ),
        "income_lapse_after_account_value_exhaustion": (
            "remains active while a locked Income guarantee exists"
        ),
        "mortality_monthly_conversion": (
            "one annual q_x per Policy Year converted to twelve reconciled "
            "monthly conditional probabilities"
        ),
        "mortality_terminal_age_treatment": (
            "death probability one in the monthly interval whose end first "
            f"reaches age {MORTALITY_TERMINAL_AGE}; the terminal q_x sentinel "
            "is not interpolated below the terminal age"
        ),
        "mortality_terminal_age": float(MORTALITY_TERMINAL_AGE),
        "scalar_behaviour_schedule_validation": "strict_engine_loader",
        "new_business_csm_proxy_scope": (
            "Product Fees + LIP Fees + Crediting Margin + MVA/APS retained "
            "minus Guarantee Claims, other insurer-funded benefits, operating "
            "expenses and hedge-execution costs"
        ),
        "other_insurer_funded_benefit_cashflow_keys": list(
            OTHER_INSURER_FUNDED_BENEFIT_KEYS
        ),
        "account_value_funded_policyholder_benefits_in_csm_proxy": False,
        "crediting_margin_in_csm_proxy": True,
        "operating_expenses_in_csm_proxy": True,
        "hedge_costs_in_csm_proxy": True,
        "hedge_volatility_spread": float(costs.projection.hedge_vol_spread),
        "time_zero_acquisition_cost_assignment": "first control year",
        "anniversary_start_hedge_cost_assignment": "same control year",
        "terminal_closeout_in_objective": False,
        "terminal_closeout_validation": (
            "fail if material under the required full lifetime horizon"
        ),
    }

    horizon_years = _projection_horizon_years(model_points, terminal_age=120.0)
    n_years = int(np.ceil(horizon_years - 1.0e-12))
    portfolio_scale = (
        1.0 if args.portfolio_contract_count is None
        else float(args.portfolio_contract_count)
    )
    projection_config = replace(
        costs.projection,
        dva_enabled=False,
        crediting_margin_enabled=True,
        record_paths=True,
        max_age=120.0,
        heston_cos=False,
    )
    LOGGER.info(
        "Inputs ready | engine=%s | model points=%d | youngest covered age=%.1f | "
        "market horizon=%.2f years | policy years=%d | behaviour=%s | "
        "take-up=%s",
        ENGINE_VERSION,
        len(model_points.model_points),
        _youngest_covered_age(model_points),
        horizon_years,
        n_years,
        behaviour.regime,
        behaviour.take_up.mode,
    )
    LOGGER.info(
        "Income Election | source take-up=%s | effective take-up=%s | "
        "effective-start overrides=%d/%d | convention=model point/minimum "
        "wait/automatic-age-%.1f backstop",
        loaded_behaviour.behaviour.take_up.mode,
        behaviour.take_up.mode,
        effective_start_override_count,
        len(treatment_rows),
        float(costs.product.automatic_income_start_age),
    )
    LOGGER.info(
        "Joint-Life application | model points=%d | Continue-Income=%d | "
        "Lump-Sum=%d | %s",
        joint_life_count,
        joint_continue_income_count,
        joint_lump_sum_count,
        joint_life_behaviour_treatment,
    )
    LOGGER.debug(
        "Behaviour treatment by branch | %s", behaviour_treatment_by_branch
    )
    LOGGER.info(
        "Behaviour feedback | realised crediting and Account-Value moneyness "
        "affect dynamic Single-Life/Lump-Sum-Spouse/fallback branches; the "
        "Continue-Income Joint branch uses static CSV base rates and no direct "
        "announced-cap elasticity is added."
    )
    LOGGER.info(
        "Mortality | Policy-Year annual q_x reconciled to monthly decrements | "
        "hard terminal age=%d | market path target age=120",
        MORTALITY_TERMINAL_AGE,
    )
    LOGGER.info(
        "Objective | MAX New Business CSM proxy | +Product/LIP Fees "
        "+Crediting/MVA/APS margins -Guarantee/other insurer benefits "
        "-Expenses -Hedge costs | hedge vol spread=%.6f",
        projection_config.hedge_vol_spread,
    )
    LOGGER.info(
        "Cost timing | time-zero acquisition cost -> first control year | "
        "anniversary-start hedge cost -> cap chosen for that same year"
    )
    LOGGER.debug("Cost inputs | %s", costs.source_metadata())
    LOGGER.debug("Behaviour inputs | %s", loaded_behaviour.source_metadata())
    LOGGER.debug("Model-point inputs | %s", model_points.source_metadata())
    for treatment in treatment_rows:
        LOGGER.debug("Model-point treatment | %s", treatment)

    with _logged_stage("Simulate training Q Heston-Hull-White scenarios"):
        training_scenarios = simulate(
            "heston_hull_white",
            market.esg,
            horizon_years,
            args.n_paths,
            measure=Measure.RISK_NEUTRAL,
            seed=args.seed,
            substeps=args.heston_substeps,
        )
    LOGGER.debug(
        "Training scenarios | fingerprint=%s | paths=%d | steps=%d",
        training_scenarios.content_fingerprint,
        training_scenarios.n_paths,
        training_scenarios.n_steps,
    )
    with _logged_stage("Generate exploratory cap controls"):
        action_indices, exploratory_caps, exploration_metadata = (
            _exploration_schedule(
                args.n_paths,
                n_years,
                args.seed + 104_729,
                args.persistent_exploration_fraction,
            )
        )
    LOGGER.info(
        "Exploration ready | persistent paths=%d | minimum paths/action/year=%d",
        exploration_metadata["persistent_path_count"],
        exploration_metadata["minimum_action_count_in_any_year"],
    )
    with _logged_stage("Project control-randomisation training portfolio"):
        training_data = _aggregate_portfolio_paths(
            scenarios=training_scenarios,
            cap_matrix=exploratory_caps,
            product=costs.product,
            model_points=model_points,
            behaviour=behaviour,
            mortality=mortality,
            expenses=costs.expenses,
            projection_config=projection_config,
            collect_states=True,
            progress_label="Control-randomisation training projection",
            model_point_log_interval=args.model_point_log_interval,
        )
    LOGGER.debug(
        "Training arrays | CSM rewards=%s | states=%s | representative premium=%.2f",
        training_data.new_business_csm_proxy.shape,
        None if training_data.raw_states is None else training_data.raw_states.shape,
        training_data.representative_initial_premium,
    )
    training_closeout_paths = np.sum(training_data.terminal_closeout, axis=1)
    training_closeout_max_abs = float(np.max(np.abs(training_closeout_paths)))
    closeout_materiality = (
        1.0e-10 * training_data.representative_initial_premium
    )
    if training_closeout_max_abs > closeout_materiality:
        message = (
            "Material terminal_closeout detected on exploratory paths despite "
            "the required full lifetime horizon: mean=%.6g, maximum "
            "absolute=%.6g, materiality=%.6g"
            % (
                float(np.mean(training_closeout_paths)),
                training_closeout_max_abs,
                closeout_materiality,
            )
        )
        LOGGER.error(message)
        raise RuntimeError(message)
    else:
        LOGGER.info(
            "Terminal-closeout diagnostic | zero/immaterial as expected for "
            "the full lifetime horizon | maximum absolute=%.6g",
            training_closeout_max_abs,
        )
    with _logged_stage("Run cross-fitted Fitted-Q backward induction"):
        backward = _backward_induction(
            training_data,
            action_indices,
            folds=args.cross_fit_folds,
            ridge=args.ridge,
            seed=args.seed + 130_363,
        )
    LOGGER.info(
        "Backward result | first-year cap=%.2f%% | held-out Bellman CSM=%.2f | "
        "future fees=%.2f | other margins=%.2f | benefits=%.2f | "
        "expenses=%.2f | hedge costs=%.2f | MC SE=%.2f",
        100.0 * backward.first_year_cap,
        portfolio_scale * backward.pv_new_business_csm_proxy,
        portfolio_scale * (
            backward.pv_fees_product + backward.pv_fees_lip
        ),
        portfolio_scale * (
            backward.pv_crediting_margin
            + backward.pv_mva_retained
            + backward.pv_aps_retained
        ),
        portfolio_scale * (
            backward.pv_guarantee_claims
            + backward.pv_other_insurer_funded_benefits
        ),
        portfolio_scale * backward.pv_expenses,
        portfolio_scale * backward.pv_hedge_costs,
        portfolio_scale * backward.standard_error_new_business_csm_proxy,
    )
    LOGGER.info(
        "Economic cap-policy horizon | active policy years=1-%d | inactive "
        "market-tail years omitted=%d",
        backward.economically_active_policy_years[-1],
        backward.inactive_market_tail_year_count,
    )
    if np.isclose(backward.first_year_cap, ACTION_CAPS[0]) \
            or np.isclose(backward.first_year_cap, ACTION_CAPS[-1]):
        LOGGER.warning(
            "First-year optimum lies on the action-grid boundary: %.2f%%.",
            100.0 * backward.first_year_cap,
        )
    condition_values = np.asarray([
        float(row["design_condition_number"])
        for row in backward.regression_rows
    ])
    unstable = (~np.isfinite(condition_values)) | (condition_values > 1.0e12)
    if np.any(unstable):
        LOGGER.warning(
            "Regression conditioning diagnostic | %d/%d year-action fits exceed "
            "1e12 or are non-finite | maximum=%s",
            int(np.sum(unstable)),
            len(condition_values),
            str(np.max(condition_values)),
        )
    if backward.regression_rows:
        oof_r2 = np.asarray([
            float(row["out_of_fold_r_squared_new_business_csm_proxy"])
            for row in backward.regression_rows
        ])
        LOGGER.debug(
            "Regression diagnostics | OOF R2 median=%.4f | p10=%.4f | minimum=%.4f",
            float(np.median(oof_r2)),
            float(np.quantile(oof_r2, 0.10)),
            float(np.min(oof_r2)),
        )

    with _logged_stage("Simulate benchmark Q Heston-Hull-White scenarios"):
        benchmark_scenarios = simulate(
            "heston_hull_white",
            market.esg,
            horizon_years,
            args.benchmark_paths,
            measure=Measure.RISK_NEUTRAL,
            seed=args.seed + 1,
            substeps=args.heston_substeps,
        )
    LOGGER.debug(
        "Benchmark scenarios | fingerprint=%s | paths=%d | steps=%d",
        benchmark_scenarios.content_fingerprint,
        benchmark_scenarios.n_paths,
        benchmark_scenarios.n_steps,
    )
    with _logged_stage("Evaluate fixed-cap sanity checks"):
        benchmark_rows, benchmark_path_values = _evaluate_fixed_benchmarks(
            base_scenarios=benchmark_scenarios,
            n_years=n_years,
            batch_size=args.benchmark_batch_size,
            product=costs.product,
            model_points=model_points,
            behaviour=behaviour,
            mortality=mortality,
            expenses=costs.expenses,
            projection_config=projection_config,
            portfolio_scale=portfolio_scale,
            model_point_log_interval=args.model_point_log_interval,
        )

    best_fixed_row = next(
        row for row in benchmark_rows if row["is_best_fixed_cap_1_to_20"]
    )
    best_fixed_cap = float(best_fixed_row["cap"])
    fallback_schedule = np.full(n_years, best_fixed_cap)
    fallback_schedule[0] = backward.first_year_cap
    if np.isclose(best_fixed_cap, 0.01) or np.isclose(best_fixed_cap, 0.20):
        LOGGER.warning(
            "Best fixed 1%%-20%% cap lies on its comparison-grid boundary: %.0f%%.",
            100.0 * best_fixed_cap,
        )
    with _logged_stage("Evaluate direct first-year-cap fallback schedule"):
        fallback_row, _ = _evaluate_explicit_schedule_benchmark(
            label="lsmc_first_year_then_best_fixed_continuation",
            definition=(
                f"LSMC-selected first-year cap {backward.first_year_cap:.2%}; "
                f"thereafter fixed {best_fixed_cap:.0%} cap"
            ),
            cap_schedule=fallback_schedule,
            scenarios=benchmark_scenarios,
            product=costs.product,
            model_points=model_points,
            behaviour=behaviour,
            mortality=mortality,
            expenses=costs.expenses,
            projection_config=projection_config,
            portfolio_scale=portfolio_scale,
            comparison_paths=benchmark_path_values[str(best_fixed_row["case"])],
            model_point_log_interval=args.model_point_log_interval,
        )
    benchmark_rows.append(fallback_row)
    benchmark_closeout_max_abs = max(
        abs(float(row["pv_terminal_closeout_excluded_aud"]))
        for row in benchmark_rows
    )
    if benchmark_closeout_max_abs > portfolio_scale * closeout_materiality:
        message = (
            "Material terminal_closeout detected in benchmark outputs despite "
            "the required full lifetime horizon: maximum absolute mean "
            "PV=%.6g" % benchmark_closeout_max_abs
        )
        LOGGER.error(message)
        raise RuntimeError(message)
    LOGGER.info(
        "Benchmark terminal-closeout diagnostic | zero/immaterial | maximum "
        "absolute mean PV=%.6g",
        benchmark_closeout_max_abs,
    )
    LOGGER.info(
        "Direct fallback result | %s | New Business CSM proxy=%.2f | MC SE=%.2f",
        fallback_row["definition"],
        fallback_row["estimated_new_business_csm_proxy_aud"],
        fallback_row["standard_error_new_business_csm_proxy_aud"],
    )
    optimal_csm = portfolio_scale * backward.pv_new_business_csm_proxy
    optimal_se = (
        portfolio_scale * backward.standard_error_new_business_csm_proxy
    )
    best_fixed_csm = float(
        best_fixed_row["estimated_new_business_csm_proxy_aud"]
    )
    best_fixed_se = float(
        best_fixed_row["standard_error_new_business_csm_proxy_aud"]
    )
    scaled_initial_premium = portfolio_scale * (
        training_data.representative_initial_premium
    )

    summary = {
        "status": "completed",
        "engine_version": ENGINE_VERSION,
        "valuation_label": (
            "market-consistent approximate New Business CSM cap-management "
            "study under fixed proxy product and behaviour assumptions"
        ),
        "method": "gas-storage-style control-randomisation Fitted-Q LSMC",
        "estimate_type": (
            "first cap selected without fold zero; CSM proxy evaluated on held-out "
            "fold zero with complete-path cross-fitted continuation values"
        ),
        "csm_measurement_label": (
            "approximate market-consistent New Business CSM proxy; aligned "
            "with insurer net value before Risk Margin, not reported IFRS 17 CSM"
        ),
        "objective_direction": "maximize",
        "objective": (
            "maximise PV(collected Product and LIP Fees + Crediting Margin + "
            "MVA/APS retained) - PV(Guarantee Claims + other insurer-funded "
            "benefits + operating expenses + hedge-execution costs)"
        ),
        "terminal_closeout_in_objective": False,
        "training_exploration_terminal_closeout_mean_pv_aud": (
            portfolio_scale * float(np.mean(training_closeout_paths))
        ),
        "training_exploration_terminal_closeout_max_absolute_pv_aud": (
            portfolio_scale * training_closeout_max_abs
        ),
        "benchmark_terminal_closeout_max_absolute_mean_pv_aud": (
            benchmark_closeout_max_abs
        ),
        "optimal_first_year_cap": backward.first_year_cap,
        "optimal_first_year_cap_percent": 100.0 * backward.first_year_cap,
        "estimated_optimal_new_business_csm_proxy_aud": optimal_csm,
        "estimated_optimal_recognised_csm_proxy_aud": max(optimal_csm, 0.0),
        "estimated_optimal_loss_component_proxy_aud": max(-optimal_csm, 0.0),
        "estimated_optimal_new_business_csm_proxy_to_initial_premium": (
            optimal_csm / scaled_initial_premium
        ),
        "estimated_optimal_pv_guarantee_claims_aud": (
            portfolio_scale * backward.pv_guarantee_claims
        ),
        "estimated_optimal_pv_other_insurer_funded_benefits_aud": (
            portfolio_scale * backward.pv_other_insurer_funded_benefits
        ),
        "estimated_optimal_pv_product_fees_aud": (
            portfolio_scale * backward.pv_fees_product
        ),
        "estimated_optimal_pv_lip_fees_aud": (
            portfolio_scale * backward.pv_fees_lip
        ),
        "estimated_optimal_pv_future_fees_aud": portfolio_scale * (
            backward.pv_fees_product + backward.pv_fees_lip
        ),
        "estimated_optimal_pv_crediting_margin_aud": (
            portfolio_scale * backward.pv_crediting_margin
        ),
        "estimated_optimal_pv_mva_retained_aud": (
            portfolio_scale * backward.pv_mva_retained
        ),
        "estimated_optimal_pv_aps_retained_aud": (
            portfolio_scale * backward.pv_aps_retained
        ),
        "estimated_optimal_pv_other_insurer_margins_aud": portfolio_scale * (
            backward.pv_crediting_margin
            + backward.pv_mva_retained
            + backward.pv_aps_retained
        ),
        "estimated_optimal_pv_total_insurer_inflows_aud": portfolio_scale * (
            backward.pv_fees_product
            + backward.pv_fees_lip
            + backward.pv_crediting_margin
            + backward.pv_mva_retained
            + backward.pv_aps_retained
        ),
        "estimated_optimal_pv_total_insurer_funded_benefits_aud": (
            portfolio_scale * (
                backward.pv_guarantee_claims
                + backward.pv_other_insurer_funded_benefits
            )
        ),
        "estimated_optimal_pv_expenses_aud": (
            portfolio_scale * backward.pv_expenses
        ),
        "estimated_optimal_pv_hedge_costs_aud": (
            portfolio_scale * backward.pv_hedge_costs
        ),
        "estimated_optimal_pv_total_costs_aud": portfolio_scale * (
            backward.pv_expenses + backward.pv_hedge_costs
        ),
        "estimated_optimal_new_business_csm_proxy_standard_error_aud": (
            optimal_se
        ),
        "optimal_csm_evaluation_sample": "held-out cross-fit fold zero",
        "conditional_holdout_csm_mc_interval_95pct_lower_aud": (
            optimal_csm - 1.96 * optimal_se
        ),
        "conditional_holdout_csm_mc_interval_95pct_upper_aud": (
            optimal_csm + 1.96 * optimal_se
        ),
        "conditional_holdout_mc_interval_scope": (
            "path dispersion conditional on fitted continuation models; excludes "
            "regression, model-selection and repeated-sample uncertainty"
        ),
        "new_business_csm_component_reconciliation_gap_aud": (
            portfolio_scale * backward.reconciliation_gap
        ),
        "best_fixed_cap_1_to_20_case": best_fixed_row["case"],
        "best_fixed_cap_1_to_20_percent": best_fixed_row["cap_percent"],
        "best_fixed_cap_new_business_csm_proxy_aud": best_fixed_csm,
        "best_fixed_cap_new_business_csm_proxy_standard_error_aud": (
            best_fixed_se
        ),
        "direct_first_year_cap_then_best_fixed_new_business_csm_proxy_aud": (
            fallback_row["estimated_new_business_csm_proxy_aud"]
        ),
        "direct_first_year_cap_then_best_fixed_csm_standard_error_aud": fallback_row[
            "standard_error_new_business_csm_proxy_aud"
        ],
        "direct_first_year_cap_then_best_fixed_definition": fallback_row[
            "definition"
        ],
        "estimated_optimal_minus_best_fixed_new_business_csm_proxy_aud": (
            optimal_csm - best_fixed_csm
        ),
        "approximate_unpaired_csm_standard_error_of_difference_aud": float(
            np.sqrt(optimal_se ** 2 + best_fixed_se ** 2)
        ),
        "action_caps": ACTION_CAPS.tolist(),
        "cap_grid_convention": "0.20%, followed by integer 1% caps through 20%",
        "cap_floor_override": (
            "0.20% research constraint overrides the active product's fixed "
            "0.25% guaranteed minimum for this counterfactual only"
        ),
        "youngest_covered_age_at_issue": _youngest_covered_age(model_points),
        "market_scenario_horizon_years": horizon_years,
        "last_economically_active_policy_year": (
            backward.economically_active_policy_years[-1]
        ),
        "inactive_market_tail_year_count_omitted_from_policy": (
            backward.inactive_market_tail_year_count
        ),
        "terminal_age_target": 120.0,
        "mortality_terminal_age": float(MORTALITY_TERMINAL_AGE),
        "mortality_terminal_age_treatment": (
            "death probability is one in the monthly interval whose end first "
            f"reaches age {MORTALITY_TERMINAL_AGE}; the terminal q_x sentinel "
            "is not interpolated below that age; "
            "market paths continue to the requested age-120 horizon"
        ),
        "valuation_measure": Measure.RISK_NEUTRAL.value,
        "market_model": "heston_hull_white",
        "n_control_randomisation_paths": args.n_paths,
        "n_benchmark_paths_per_case": args.benchmark_paths,
        "cross_fit_folds": args.cross_fit_folds,
        "ridge_multiplier": args.ridge,
        "dva_enabled": False,
        "crediting_margin_in_objective": True,
        "mva_and_aps_retained_in_objective": True,
        "hedge_costs_in_objective": True,
        "expenses_in_objective": True,
        "other_insurer_funded_benefit_cashflow_keys": list(
            OTHER_INSURER_FUNDED_BENEFIT_KEYS
        ),
        "base_policy_behaviour_regime": behaviour.regime,
        "behaviour_treatment_by_branch": behaviour_treatment_by_branch,
        "source_income_take_up_mode": loaded_behaviour.behaviour.take_up.mode,
        "income_take_up_mode": behaviour.take_up.mode,
        "effective_income_start_override_model_point_count": (
            effective_start_override_count
        ),
        "joint_life_behaviour_treatment": joint_life_behaviour_treatment,
        "mortality_application": (
            "deterministic expected decrements from one annual q_x per Policy "
            "Year, converted to twelve reconciled monthly probabilities"
        ),
        "projection_semantics": projection_semantics,
        "aggregation_basis": (
            "absolute_portfolio_contract_count"
            if args.portfolio_contract_count is not None
            else "normalised_to_one_representative_contract"
        ),
        "portfolio_contract_count": args.portfolio_contract_count,
        "representative_initial_premium_aud": (
            training_data.representative_initial_premium
        ),
        "scaled_initial_premium_aud": scaled_initial_premium,
    }

    policy_payload = _policy_payload(
        backward,
        training_data.state_feature_names,
        projection_semantics,
    )
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "engine_version": ENGINE_VERSION,
        "script": str(Path(__file__).resolve()),
        "summary_file": "optimization_summary.json",
        "output_inventory": {
            "summary": "optimization_summary.json",
            "policy": "lsmc_policy.json",
            "manifest": "run_manifest.json",
            "csv_tables": [
                "first_year_action_values.csv",
                "optimal_policy_by_year.csv",
                "regression_diagnostics.csv",
                "fixed_cap_sanity_checks.csv",
                "model_point_projection_treatments.csv",
            ],
            "log": "run.log",
            "plots": "populated in graphics.files after successful plotting",
        },
        "engine_market_inputs": market.source_metadata(),
        "cost_assumptions": costs.source_metadata(),
        "dynamic_behaviour_assumptions": loaded_behaviour.source_metadata(),
        "model_points": model_points.source_metadata(),
        "model_point_projection_treatments_file": (
            "model_point_projection_treatments.csv"
        ),
        "portfolio_application": projection_semantics,
        "economic_policy_horizon": {
            "economically_active_policy_years": list(
                backward.economically_active_policy_years
            ),
            "inactive_market_tail_year_count": (
                backward.inactive_market_tail_year_count
            ),
            "inactive_year_policy_treatment": (
                "no cap regression fitted; omitted from policy coefficients and "
                "tables; shown as a grey zero-exposure tail in the policy plot"
            ),
        },
        "training_scenario_fingerprint": training_scenarios.content_fingerprint,
        "benchmark_scenario_fingerprint": benchmark_scenarios.content_fingerprint,
        "training_seed": args.seed,
        "benchmark_seed": args.seed + 1,
        "heston_substeps": args.heston_substeps,
        "exploration": exploration_metadata,
        "objective_scope": {
            "measurement": (
                "approximate market-consistent New Business CSM proxy aligned "
                "with insurer net value before Risk Margin; not IFRS 17 CSM"
            ),
            "optimization_direction": "maximize",
            "included_fee_inflows": ["fees_product", "fees_lip"],
            "included_other_insurer_margins": [
                "crediting_margin", "mva_retained", "aps_retained",
            ],
            "included_insurer_funded_benefits": [
                "guarantee_claims",
                *OTHER_INSURER_FUNDED_BENEFIT_KEYS,
            ],
            "included_costs": ["expenses", "hedge_costs"],
            "expense_timing": (
                "time-zero acquisition/commission expense is assigned to the "
                "first control year; maintenance expense follows payment time"
            ),
            "hedge_cost_timing": (
                "anniversary-start hedge cost is assigned to the cap chosen "
                "for that control year"
            ),
            "excluded": [
                "premium", "income_paid", "death_benefits",
                "surrender_benefits", "partial_withdrawals",
                "terminal_closeout", "capital", "risk_margin", "tax",
                "cost_of_capital",
            ],
            "account_value_funded_benefit_treatment": (
                "Income, death, surrender and withdrawal benefits funded from "
                "Policyholder Account Value are excluded from insurer outgo; "
                "only separately recorded insurer-funded top-ups are deducted"
            ),
            "terminal_closeout_diagnostic": (
                "reported separately and expected to be zero for the full "
                "lifetime horizon"
            ),
        },
        "policy_value_outputs": {
            "dynamic_feedback_value": (
                "held-out fitted-Bellman estimate; no independent full rollout"
            ),
            "directly_projected_admissible_control": (
                "LSMC first-year cap followed by the best fixed 1%-20% cap"
            ),
        },
        "nonanticipativity": {
            "decision_state_time": "start of each crediting year",
            "future_reference_fund_return_in_state": False,
            "future_discount_factor_in_state": False,
            "fold_unit": "complete market/control path",
            "first_cap_selection_folds": "all folds except fold zero",
            "first_cap_csm_evaluation_fold": "fold zero only",
            "evaluation_fold_used_in_any_regression_fit": False,
            "dva_disabled_for_pre_action_state": True,
        },
        "limitations": [
            "The optimal-policy CSM proxy is cross-fitted but is not a second, fully "
            "independent forward simulation of the learned state-feedback policy.",
            "The annual administrative Account-Value view disables intra-year DVA; "
            "cap effects on dynamic Behaviour branches enter through realised "
            "annual crediting. Crediting Margin and hedge cost use the engine's "
            "annual option-package proxy, not a full ALM replication.",
            f"The regression state compresses {len(model_points.model_points)} "
            "model points into portfolio, age, "
            "premium, age/sex/Single-vs-Joint and, when heterogeneous, effective-"
            "Income-start cohort buckets; its ten-times-"
            "income moneyness feature is a "
            "basis proxy, while actual dynamic-branch Behaviour probabilities use "
            "the engine's full pathwise moneyness calculation.",
            "The existing Behaviour model has no direct announced-cap covariate; "
            "for dynamic Single-Life, Lump-Sum-Spouse and fallback branches the cap "
            "affects lapse and withdrawals through subsequent realised crediting "
            "and Account-Value moneyness; no new elasticity is invented.",
            "The Continue-Income Joint-Life branch uses static CSV base lapse and "
            "withdrawal rates while its Single-Life fallback remains dynamic; full "
            "p11/p10/p01 Account-Value and fee cohorts are not implemented.",
            "The optimisation deliberately applies the deterministic effective "
            "model-point Election convention to the whole portfolio; Joint-Life "
            "fallback compatibility additionally requires it. The effective "
            "Election is the earlier of the valid model-point anniversary and the "
            "first Policy Anniversary strictly after automatic-start age "
            f"{costs.product.automatic_income_start_age:g} is reached, "
            f"subject to the {float(costs.product.min_years_before_income):g}-year product "
            "minimum waiting period.",
            "The New Business CSM measure is a signed market-consistent proxy aligned "
            "with insurer net value before Risk Margin. It is not reported IFRS 17 "
            "CSM and excludes Risk Adjustment, capital, tax and reinsurance.",
            "Account-Value-funded Income, death, surrender and withdrawal payments "
            "are investment-component cashflows and are not deducted again; only "
            "Guarantee Claims and separately named insurer-funded benefits are outgo.",
            "Dynamic Behaviour inputs remain uncalibrated proxy assumptions; scalar "
            "Behaviour schedules are subject to the Engine loader's strict validation.",
            "The mortality basis is the illustrative repository Gompertz-Makeham "
            "table. Annual q_x is anchored by Policy Year, reconciled to monthly "
            f"decrements, and death is forced in the interval ending at age "
            f"{MORTALITY_TERMINAL_AGE}.",
            "Market paths continue until the youngest covered life would reach age "
            "120, but years after all in-force exposure reaches zero are omitted "
            "from the fitted cap policy and regression diagnostics and are shown "
            "as an inactive grey tail in the policy plot.",
            "Joint-Life survival assumes independent lives and omits divorce, common "
            "mortality shocks and changing spouse eligibility.",
            "The 0.20% minimum is a requested counterfactual and is below the "
            "active case-study product's documented 0.25% guaranteed minimum.",
            "The best fixed 1%-to-20% benchmark is selected on the same finite "
            "benchmark sample used to report it and its reported maximum CSM proxy "
            "is therefore subject to a small upward winner's-curse bias; paired "
            "path differences are also reported.",
        ],
    }

    scaled_first_year_rows = _scaled_first_year_rows(
        backward.first_year_action_rows, portfolio_scale
    )
    csv_outputs = (
        (output / "first_year_action_values.csv", scaled_first_year_rows),
        (output / "optimal_policy_by_year.csv", backward.policy_year_rows),
        (output / "regression_diagnostics.csv", backward.regression_rows),
        (output / "fixed_cap_sanity_checks.csv", benchmark_rows),
        (output / "model_point_projection_treatments.csv", treatment_rows),
    )
    with _logged_stage("Write CSV result tables"):
        for path, rows in csv_outputs:
            _write_csv(path, rows)
            LOGGER.debug("CSV written | %s | rows=%d", path, len(rows))

    summary.update({
        "status": "numerical_results_complete_plots_pending",
        "run_log_file": str(log_path.relative_to(output)),
        "generated_plot_files": [],
    })
    manifest.update({
        "logging": {
            "console_level": args.log_level,
            "file_level": "DEBUG",
            "file": str(log_path.relative_to(output)),
            "model_point_log_interval": args.model_point_log_interval,
        },
        "graphics": {
            "status": "pending",
            "backend": "Agg",
            "format": args.plot_format,
            "png_dpi": args.plot_dpi,
            "files": [],
        },
    })
    preliminary_json_outputs = (
        (output / "optimization_summary.json", summary),
        (output / "lsmc_policy.json", policy_payload),
        (output / "run_manifest.json", manifest),
    )
    with _logged_stage("Checkpoint numerical JSON results before plotting"):
        for path, payload in preliminary_json_outputs:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(
                    payload, handle, indent=2, ensure_ascii=False,
                    default=_json_default,
                )
                handle.write("\n")
            LOGGER.debug("Checkpoint JSON written | %s", path)

    with _logged_stage("Generate result graphics"):
        plot_paths, matplotlib_version = _generate_plots(
            plotting_backend=plotting_backend,
            output=output,
            first_year_rows=scaled_first_year_rows,
            policy_rows=backward.policy_year_rows,
            regression_rows=backward.regression_rows,
            benchmark_rows=benchmark_rows,
            summary=summary,
            plot_format=args.plot_format,
            dpi=args.plot_dpi,
        )
    relative_plot_paths = [str(path.relative_to(output)) for path in plot_paths]
    summary.update({
        "status": "completed",
        "run_elapsed_seconds_at_result_finalization": (
            time.perf_counter() - run_started
        ),
        "generated_plot_files": relative_plot_paths,
    })
    manifest["run_elapsed_seconds_at_result_finalization"] = summary[
        "run_elapsed_seconds_at_result_finalization"
    ]
    manifest["graphics"] = {
        "status": "completed",
        "matplotlib_version": matplotlib_version,
        "backend": "Agg",
        "format": args.plot_format,
        "png_dpi": args.plot_dpi,
        "files": relative_plot_paths,
    }

    final_json_outputs = (
        (output / "optimization_summary.json", summary),
        (output / "run_manifest.json", manifest),
    )
    with _logged_stage("Finalize summary and manifest after plotting"):
        for path, payload in final_json_outputs:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(
                    payload, handle, indent=2, ensure_ascii=False,
                    default=_json_default,
                )
                handle.write("\n")
            LOGGER.debug("JSON written | %s", path)

    total_elapsed = time.perf_counter() - run_started
    LOGGER.info(
        "RUN COMPLETE | elapsed %.1fs | first-year cap %.2f%% | "
        "held-out Bellman CSM %.2f | best fixed cap %.0f%% / CSM %.2f",
        total_elapsed,
        100.0 * backward.first_year_cap,
        optimal_csm,
        100.0 * best_fixed_cap,
        best_fixed_csm,
    )
    LOGGER.info(
        "Outputs | %d CSV | %d JSON | %d plot files | log=%s | directory=%s",
        len(csv_outputs), len(preliminary_json_outputs), len(plot_paths),
        log_path, output,
    )


if __name__ == "__main__":
    main()
