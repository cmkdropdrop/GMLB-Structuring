"""Optimise annual Reference-Fund caps under dynamic Policyholder behaviour.

This is a standalone counterfactual management-action study.  Policyholders
follow the repository's statistical dynamic Behaviour model throughout the
monthly projection; no Policyholder value-function regression or optimal-
surrender LSMC is fitted or applied.  The insurer's annual cap is optimised
with a gas-storage-style Least-Squares Monte Carlo: the customer account value
per initial premium is treated as the endogenous inventory ("storage level")
on a discretised grid, the cap is the injection control that decides how much
Reference-Fund return is credited into the fund, and dynamic Income and
withdrawals draw the fund down.

The market paths are simulated once without contractual crediting under
risk-neutral Heston-Hull-White.  Exploratory cap paths then drive the existing
generic monthly contract projector.  A backward pass on the account-value
inventory grid (Boogert & de Jong, 2008; Carmona & Ludkovski, 2010) estimates,
for every anniversary, admissible cap and grid node,

    E[PV(Fee Income) + PV(Other Income) - PV(Claims) - PV(Costs)
      + continuation value at the resulting account value
      | information at the cap-setting time].

The continuation value is fitted by a separate regression per grid node on the
slim exogenous basis ``{1, ATM one-year call, Reference-Fund level, overnight
rate}`` and interpolated across nodes.  Reward and account-value transition
regressions add standardised account value and its square to those four
columns.  The inter-node delta V(A_{k+1}) - V(A_k) is the discrete marginal
value of account value (the storage shadow price) that determines the optimal
cap.  The signed objective is the repository's market-consistent insurer net
value before Risk Margin and is used here as an approximate New Business CSM
proxy.  The optimisation selects, at each account-value node, the cap with the
largest proxy value after the projector has applied dynamic Income lapse and
withdrawal behaviour.  Income Election is also left in the loaded dynamic
Behaviour mode, subject to the existing contractual eligibility and
forced-start gates.

The admissible action grid is ``{0.25%, 1%, 2%, ..., 20%}``, matching the
documented Guaranteed Minimum Cap while replacing the case study's fixed 6%
Maximum Return for this counterfactual.  Fixed-cap checks distinguish zero
crediting from uncapped positive-return crediting.

Important timing convention
---------------------------
The management action is selected after old-cap crediting, fee posting,
mortality and Income Election and before the new DVA/hedge restart.  The
optimisation uses a strictly pre-action market plus rich portfolio-exposure
state; the newly announced cap is then observable to a same-Anniversary Full
Withdrawal.  Collected Product/LIP Fees,
Crediting and retained margins, Guarantee Claims, operating expenses and
full option/hedge costs enter the CSM proxy with their insurer cashflow signs.
The standard insurer hedge is fixed to the complete bull call spread: the
upper cap call is sold, so the insurer retains no Reference-Fund performance
above the customer cap.  The crediting margin still includes the insurer's
pathwise money-market backing income.
Ordinary lapse, performance-sensitive lapse, Income Election and voluntary
withdrawals are therefore driven only by the versioned assumptions under
``input_dynamic_behaviour``.  The current announced cap has no separate direct
coefficient in that Behaviour model; it affects behaviour through the
projected Account Value, guarantee moneyness and realised performance history.

When explicitly run, the script writes CSV/JSON results, a DEBUG ``run.log``
and headless Matplotlib diagnostics below ``plots/`` while reporting concise
progress to the console.  Merely importing it has no side effects.
"""

# Algorithmic change: 2026-07-13 (Europe/Zurich).
# The insurer-cap backward induction (_backward_induction) was rewritten from a
# flat cross-fitted control-randomisation Fitted-Q into a gas-storage-style
# Least-Squares Monte Carlo (Boogert & de Jong, 2008; Carmona & Ludkovski,
# 2010).  The customer account value per initial premium is now an explicit
# endogenous inventory discretised onto an adaptive grid (the "Gitter"); the
# continuation value is fitted per grid node on the exogenous state and
# interpolated across nodes, and the inter-node delta V(A_{k+1}) - V(A_k) -- the
# discrete marginal value of account value / storage shadow price -- drives the
# optimal cap.  For a counterfactual cap the one-step insurer reward and the
# account-value transition are empirical ridge regressions evaluated at the
# forced grid node (crediting with fees, mortality, income and withdrawals is
# not closed-form).  The recursion still emits, per active policy year, a
# deployable per-cap RegressionPolicyYear Q-function so the unchanged causal
# monthly-projection rollout, plots and JSON payload keep working.  The previous
# outer-fold-pure single-continuation chain is replaced by the inventory-grid
# value function; per-cap out-of-fold diagnostics are still reported.
#
# Basis change: 2026-07-13 (Europe/Zurich).
# The gas-storage regressions now use the parsimonious economic basis
# {1, ATM one-year call, Reference-Fund level, overnight rate}, augmented by
# standardised account value and its square for reward and transition.  The
# deployable Q-functions remain on the full 25-column rollout basis: the slim
# per-cap component Q-values are projected onto that full basis after each
# Bellman step, preserving the existing RegressionPolicyYear interface.

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Iterator, Mapping, Optional, Sequence

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
    HedgeCapLegMode,
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
    load_equity_allocation,
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
from agile_engine.product import Phase, PolicySpec  # noqa: E402
from agile_engine.optimal_behaviour_lsmc import (  # noqa: E402
    FEATURE_NAMES as POLICYHOLDER_FEATURE_NAMES,
    OptimalBehaviourLSMCSettings,
    OptimalSurrenderPolicy,
    build_surrender_regression_features,
    build_surrender_regression_features_from_arrays,
    fit_optimal_surrender_policy,
    fit_surrender_continuation_regression,
    fit_surrender_continuation_policy,
    no_voluntary_action_behaviour,
)


Array = NDArray[np.float64]
IntArray = NDArray[np.int64]
STEPS_PER_YEAR = 12

ACTION_CAPS = np.concatenate((np.array([0.0025]), np.arange(0.01, 0.201, 0.01)))
OTHER_INSURER_FUNDED_BENEFIT_KEYS: tuple[str, ...] = ()
CONTROL_STATE_FEATURE_NAMES = (
    "zero_rate_5y",
    "heston_variance_global",
    "log_discount_to_time0",
    "trailing_reference_fund_return",
    "log_reference_fund_level",
    "log_credited_index_proxy",
    "previous_cap",
    "average_historical_cap",
    "average_excess_return_above_cap_proxy",
    "trailing_performance_shortfall",
)
PORTFOLIO_CONTROL_STATE_FEATURE_NAMES = (
    "short_rate",
    "inforce_exposure",
    "growth_exposure",
    "income_exposure",
    "account_value_per_initial_premium",
    "surrender_value_per_initial_premium",
    "locked_income_per_initial_premium",
    "guarantee_pv_per_initial_premium",
    "guarantee_moneyness_exposure",
    "exhausted_income_exposure",
)
INSURER_COMPONENT_NAMES = (
    "fees_product",
    "fees_lip",
    "crediting_margin",
    "mva_retained",
    "aps_retained",
    "guarantee_claims",
    "other_insurer_funded_benefits",
    "expenses",
    "hedge_costs",
)
NONNEGATIVE_INSURER_COMPONENT_INDICES = (1, 2, 4, 5, 6, 7, 8, 9)
FOLLOWER_PRE_CAP_FEATURE_NAMES = (
    *POLICYHOLDER_FEATURE_NAMES,
    "previous_cap",
)
DEFAULT_OUTPUT_DIRECTORY = (
    Path(__file__).resolve().parent / "output" / "crediting_cap_dynamic_behaviour"
)
DEFAULT_BENCHMARK_CACHE_DIRECTORY = (
    Path(__file__).resolve().parent / "output" / "benchmark_projection_cache"
)
LOGGER = logging.getLogger("crediting_cap_dynamic_behaviour")


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
    equity_weight: float = 0.30
    bond_tenor_years: float = 5.0
    rebalance_frequency_months: int = 1
    specification_vintage: str = "counterfactual-dynamic-behaviour-control-grid"

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
class SignatureDecisionYearPaths:
    """Projector primitives for one follower decision and one signature.

    Customer quantities are stored per surviving contract.  Insurer component
    deltas and next-state exposure contributions already include the branch
    probability and ``contract_weight`` exactly once.  Compact ``float32``
    snapshots keep the full lifetime training problem memory-bounded; every
    regression promotes its working slice back to ``float64``.
    """

    policy_year: int
    decision_step: int
    pre_cap_core: Array
    after_cap_core: Array
    phase: NDArray[np.int8]
    just_elected: NDArray[np.bool_]
    full_withdrawal_eligible: NDArray[np.bool_]
    decision_discount_inforce: Array
    next_decision_discount_inforce: Array
    continue_policyholder_interval_pv: Array
    full_withdrawal_value: Array
    insurer_full_minus_continue_components: Array
    next_portfolio_exposure_contribution: Array


@dataclass
class SignatureControlPaths:
    """All fitted-control primitives for one economic PolicySpec signature."""

    signature: tuple[object, ...]
    policy: PolicySpec
    decision_years: dict[int, SignatureDecisionYearPaths]


@dataclass
class PortfolioPathData:
    """Discounted insurer-margin paths used by the backward induction."""

    guarantee_claims: Array
    other_insurer_funded_benefits: Array
    fees_product: Array
    fees_lip: Array
    crediting_margin: Array
    money_market_income: Array
    hedge_gain: Array
    mva_retained: Array
    aps_retained: Array
    expenses: Array
    hedge_costs: Array
    income_paid: Array
    death_benefits: Array
    surrender_benefits: Array
    partial_withdrawals: Array
    terminal_closeout: Array
    lapse_events: Array
    inforce_exposure: Array | None
    raw_states: Array | None
    state_feature_names: tuple[str, ...]
    pre_action_states: Array | None
    pre_action_state_feature_names: tuple[str, ...]
    representative_initial_premium: float
    signature_control_paths: dict[
        tuple[object, ...], SignatureControlPaths
    ] = field(default_factory=dict)
    policyholder_benefits_by_signature: dict[
        tuple[object, ...], Array
    ] = field(default_factory=dict)

    @property
    def new_business_csm_proxy(self) -> Array:
        """User-defined CSM = fee income + other income - claims - costs."""
        return (
            self.fees_product
            + self.fees_lip
            + self.money_market_income
            + self.hedge_gain
            + self.mva_retained
            + self.aps_retained
            - self.guarantee_claims
            - self.other_insurer_funded_benefits
            - self.expenses
            - self.hedge_costs
        )

    @property
    def policyholder_benefits(self) -> Array:
        """All customer cashflows, excluding the sunk issue premium."""
        return (
            self.income_paid
            + self.death_benefits
            + self.surrender_benefits
            + self.partial_withdrawals
            + self.terminal_closeout
        )


class _CapDecisionStateCollector:
    """Collect immutable pre-cap contexts from one projection branch."""

    def __init__(self) -> None:
        self.contexts: dict[int, object] = {}

    def observe_cap_decision(self, *, context: object) -> None:
        policy_year = int(getattr(context, "policy_year"))
        if policy_year in self.contexts:
            raise RuntimeError(
                f"Duplicate cap-decision context for policy year {policy_year}."
            )
        self.contexts[policy_year] = context


class _StackelbergPrimitiveCollector:
    """Record safe customer states and separate insurer action primitives."""

    anniversary_only = True

    def __init__(self) -> None:
        self.surrender_contexts: dict[int, object] = {}
        self.action_value_contexts: dict[int, object] = {}

    def surrender_mask(self, *, context: object) -> NDArray[np.bool_]:
        year = int(getattr(context, "policy_year"))
        if year in self.surrender_contexts:
            raise RuntimeError(
                f"Duplicate surrender context for policy year {year}."
            )
        self.surrender_contexts[year] = context
        return np.zeros(int(getattr(context, "n_paths")), dtype=bool)

    def observe_surrender_decision(self, *, context: object) -> None:
        decision = getattr(context, "decision_context")
        year = int(getattr(decision, "policy_year"))
        if year in self.action_value_contexts:
            raise RuntimeError(
                f"Duplicate surrender action-value context for year {year}."
            )
        self.action_value_contexts[year] = context


@dataclass(frozen=True)
class RegressionPolicyYear:
    year: int
    raw_mean: Array
    raw_scale: Array
    coefficients: Array
    action_caps: Array
    action_value_standard_error: Array
    value_lower_bounds: Array | None = None
    value_upper_bounds: Array | None = None
    numerically_stable: bool = True
    action_deployable_mask: NDArray[np.bool_] | None = None


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
    numerically_stable: bool = True
    numerical_fallback_reasons: tuple[str, ...] = ()
    follower_regression_rows: list[dict[str, object]] = field(
        default_factory=list
    )
    follower_fit_set: object | None = None


def _policy_signature(policy: PolicySpec) -> tuple[object, ...]:
    """Canonical cache key for one separately optimised customer contract.

    Joint-Life and Single-Life fallback contracts deliberately produce
    different keys.  Product fields that change net premium, APS eligibility
    or the customer cashflow state are included so a fitted best response is
    never silently reused for an economically different contract.
    """
    return (
        float(policy.age),
        policy.sex.value,
        float(policy.initial_investment),
        float(policy.upfront_adviser_fee_pct),
        float(policy.bonus_interest_pct),
        int(round(policy.income_start_year)),
        policy.income_type.value,
        bool(policy.spouse),
        None if policy.spouse_age is None else float(policy.spouse_age),
        None if policy.spouse_sex is None else policy.spouse_sex.value,
        policy.spouse_death_election.value,
        bool(policy.age_pension_plus),
        policy.funding_source.value,
        policy.condition_of_release_year,
        policy.aps_life_expectancy,
        float(policy.commencement_year),
    )


_FOLLOWER_CORE_NAMES = (
    "account_value",
    "surrender_value",
    "locked_annual_income",
    "guarantee_pv",
    "guarantee_log_moneyness",
    "short_rate",
    "zero_rate_5y",
    "heston_variance",
    "cap_history_value",
    "previous_reference_return",
    "previous_credited_return",
    "performance_gap",
    "inforce_weight",
)


def _compact_follower_core(
    context: object,
    *,
    premium: float,
    cap_attribute: str,
) -> Array:
    """Copy the minimum customer state needed to rebuild the public basis."""
    if not np.isfinite(premium) or premium <= 0.0:
        raise ValueError("Follower feature premium must be positive and finite.")
    core = np.column_stack((
        np.maximum(np.asarray(getattr(context, "account_value")), 0.0) / premium,
        np.maximum(np.asarray(getattr(context, "surrender_value")), 0.0) / premium,
        np.maximum(
            np.asarray(getattr(context, "locked_annual_income")), 0.0
        ) / premium,
        np.maximum(np.asarray(getattr(context, "guarantee_pv")), 0.0) / premium,
        np.asarray(getattr(context, "guarantee_log_moneyness"), dtype=float),
        np.asarray(getattr(context, "short_rate"), dtype=float),
        np.asarray(getattr(context, "zero_rate_5y"), dtype=float),
        np.maximum(
            np.asarray(getattr(context, "heston_variance"), dtype=float), 0.0
        ),
        np.asarray(getattr(context, cap_attribute), dtype=float),
        np.asarray(getattr(context, "previous_reference_return"), dtype=float),
        np.asarray(getattr(context, "previous_credited_return"), dtype=float),
        np.maximum(
            np.asarray(getattr(context, "performance_gap"), dtype=float), 0.0
        ),
        np.maximum(
            np.asarray(getattr(context, "inforce_weight"), dtype=float), 0.0
        ),
    ))
    if core.shape[1] != len(_FOLLOWER_CORE_NAMES):
        raise RuntimeError("Compact follower state layout is inconsistent.")
    if not np.all(np.isfinite(core)):
        raise ValueError("Compact follower state contains non-finite values.")
    return np.asarray(core, dtype=np.float32)


def _follower_features_from_core(
    core: Array,
    *,
    announced_cap: Array | float,
    duration_years: float,
    include_previous_cap: bool,
) -> Array:
    """Rebuild the adapted customer basis for a candidate announced cap."""
    values = np.asarray(core, dtype=float)
    if values.ndim != 2 or values.shape[1] != len(_FOLLOWER_CORE_NAMES):
        raise ValueError("Follower core matrix has an invalid shape.")
    cap = np.asarray(announced_cap, dtype=float)
    if cap.ndim == 0:
        cap = np.full(values.shape[0], float(cap))
    if cap.shape != (values.shape[0],):
        raise ValueError("Candidate cap must have one value per follower path.")
    previous_cap = values[:, 8]
    raw = build_surrender_regression_features_from_arrays(
        account_value=values[:, 0],
        surrender_value=values[:, 1],
        locked_annual_income=values[:, 2],
        guarantee_pv=values[:, 3],
        guarantee_log_moneyness=values[:, 4],
        short_rate=values[:, 5],
        zero_rate_5y=values[:, 6],
        heston_variance=values[:, 7],
        duration_years=float(duration_years),
        announced_cap=cap,
        previous_reference_return=values[:, 9],
        previous_credited_return=values[:, 10],
        performance_gap=values[:, 11],
        # Compact monetary values were already divided by premium.
        premium=1.0,
    )
    if include_previous_cap:
        raw = np.column_stack((raw, previous_cap))
        expected = len(FOLLOWER_PRE_CAP_FEATURE_NAMES)
    else:
        expected = len(POLICYHOLDER_FEATURE_NAMES)
    if raw.shape[1] != expected or not np.all(np.isfinite(raw)):
        raise RuntimeError("Follower regression feature construction failed.")
    return raw


@dataclass
class PolicyholderFitSet:
    """Cap-aware follower policies fitted separately by PolicySpec signature."""

    fits: dict[tuple[object, ...], object]
    scenario_fingerprint: str
    cap_schedule_fingerprint: str
    validation_fallback_signatures: set[tuple[object, ...]] = field(
        default_factory=set
    )

    def factory(self, policy: PolicySpec) -> object:
        key = _policy_signature(policy)
        if key not in self.fits:
            raise KeyError("No cap-consistent LSMC fit exists for PolicySpec.")
        policy = self.fits[key].policy
        if key in self.validation_fallback_signatures:
            return type(policy)(regressions={}, settings=policy.settings)
        return policy

    def training_factory(self, policy: PolicySpec) -> object:
        """Return the complete-path out-of-fold policy for leader targets."""
        key = _policy_signature(policy)
        if key not in self.fits:
            raise KeyError("No cap-consistent LSMC fit exists for PolicySpec.")
        return self.fits[key].cross_fitted_training_policy

    @property
    def fallback_count(self) -> int:
        training = {
            signature
            for signature, fit in self.fits.items()
            if bool(fit.training_fallback_used)
            or any(
                not bool(diagnostic.regression_accepted_for_exercise)
                for diagnostic in fit.diagnostics
            )
        }
        return len(training | self.validation_fallback_signatures)

    @property
    def fallback_step_count(self) -> int:
        count = 0
        for signature, fit in self.fits.items():
            rejected = {
                int(diagnostic.decision_step)
                for diagnostic in fit.diagnostics
                if not bool(diagnostic.regression_accepted_for_exercise)
            }
            if bool(fit.training_fallback_used):
                # The training PV gate replaces the entire fitted policy by
                # Continue, including individually stable decision steps.
                rejected.update(
                    int(diagnostic.decision_step)
                    for diagnostic in fit.diagnostics
                )
            if signature in self.validation_fallback_signatures:
                rejected.update(int(step) for step in fit.policy.regressions)
                rejected.update(
                    int(diagnostic.decision_step)
                    for diagnostic in fit.diagnostics
                )
            count += len(rejected)
        return count

    @property
    def signature_count(self) -> int:
        return len(self.fits)


@dataclass(frozen=True)
class _FollowerDeploymentRegression:
    """One frozen customer-continuation regression for forward rollout."""

    premium: float
    active_feature_indices: IntArray
    centre: Array
    scale: Array
    coefficients: Array
    condition_number: float
    matrix_rank: int
    oof_rmse_aud: float
    stable: bool

    def predict(self, context: object) -> Array:
        raw = build_surrender_regression_features(context, self.premium)
        active = self.active_feature_indices
        design = np.column_stack((
            np.ones(raw.shape[0]),
            (raw[:, active] - self.centre) / self.scale,
        ))
        prediction = design @ self.coefficients * self.premium
        return np.maximum(np.asarray(prediction, dtype=float), 0.0)


@dataclass
class CoupledOptimalSurrenderPolicy:
    """Frozen follower best response from the coupled two-value recursion."""

    regressions: Mapping[int, _FollowerDeploymentRegression]
    settings: OptimalBehaviourLSMCSettings
    evaluation_statistics: dict[int, dict[str, int]] = field(
        default_factory=dict
    )
    anniversary_only: bool = field(default=True, init=False, repr=False)

    def surrender_mask(self, *, context: object) -> NDArray[np.bool_]:
        step = int(getattr(context, "step"))
        n_paths = int(getattr(context, "n_paths"))
        regression = self.regressions.get(step)
        if (
            regression is None
            or not bool(getattr(context, "is_anniversary"))
            or not regression.stable
        ):
            return np.zeros(n_paths, dtype=bool)
        eligible = (
            np.asarray(getattr(context, "full_withdrawal_eligible"), dtype=bool)
            & (np.asarray(getattr(context, "phase")) == Phase.INCOME.value)
            & (
                np.asarray(getattr(context, "inforce_weight"), dtype=float)
                > self.settings.minimum_inforce_weight
            )
        )
        continuation = regression.predict(context)
        buffer = (
            self.settings.exercise_tolerance_aud
            + self.settings.exercise_buffer_rmse_multiplier
            * regression.oof_rmse_aud
        )
        exercise = eligible & (
            np.asarray(getattr(context, "surrender_value"), dtype=float)
            > continuation + buffer
        )
        stats = self.evaluation_statistics.setdefault(
            step, {"eligible_path_count": 0, "exercise_path_count": 0}
        )
        stats["eligible_path_count"] += int(np.count_nonzero(eligible))
        stats["exercise_path_count"] += int(np.count_nonzero(exercise))
        return exercise


@dataclass
class CoupledPolicyholderFitSet:
    """Signature-separated follower policies produced inside leader recursion."""

    policies: dict[tuple[object, ...], object]
    scenario_fingerprint: str
    cap_schedule_fingerprint: str
    fallback_signatures: set[tuple[object, ...]] = field(default_factory=set)
    fallback_steps_by_signature: dict[
        tuple[object, ...], tuple[int, ...]
    ] = field(default_factory=dict)

    def factory(self, policy: PolicySpec) -> object:
        key = _policy_signature(policy)
        if key not in self.policies:
            raise KeyError("No coupled follower policy exists for PolicySpec.")
        if key in self.fallback_signatures:
            return CoupledOptimalSurrenderPolicy(
                regressions={},
                settings=getattr(self.policies[key], "settings"),
            )
        return self.policies[key]

    @property
    def fallback_count(self) -> int:
        return len(
            self.fallback_signatures
            | {
                signature
                for signature, steps in self.fallback_steps_by_signature.items()
                if steps
            }
        )

    @property
    def fallback_step_count(self) -> int:
        return sum(len(steps) for steps in self.fallback_steps_by_signature.values())

    @property
    def signature_count(self) -> int:
        return len(self.policies)


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


def _lower_cap_argmax(values: Array, axis: int = -1) -> IntArray:
    """Return the smallest cap index within a numerical maximum tie.

    The action grid is strictly increasing.  Treating values within a small
    relative floating-point tolerance as tied makes the contractual lower-cap
    tie-break explicit instead of depending on incidental BLAS rounding.
    """
    array = np.asarray(values, dtype=float)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("Cap action values must be finite and non-empty.")
    maxima = np.max(array, axis=axis, keepdims=True)
    tolerance = 1.0e-10 * np.maximum(1.0, np.abs(maxima))
    tied = array >= maxima - tolerance
    return np.asarray(np.argmax(tied, axis=axis), dtype=np.int64)


def _masked_lower_cap_argmax(
    values: Array,
    deployable_mask: NDArray[np.bool_],
    axis: int = -1,
) -> IntArray:
    """Apply the lower-cap argmax to finite deployable action columns only."""
    array = np.asarray(values, dtype=float)
    if array.ndim == 0:
        raise ValueError("Masked cap action values must have an action axis.")
    action_axis = axis if axis >= 0 else array.ndim + axis
    if action_axis < 0 or action_axis >= array.ndim:
        raise ValueError("Masked cap action axis is invalid.")
    mask = np.asarray(deployable_mask, dtype=bool)
    if mask.shape != (array.shape[action_axis],):
        raise ValueError("Deployable-action mask has the wrong shape.")
    deployable_indices = np.flatnonzero(mask)
    if deployable_indices.size == 0:
        raise ValueError("At least one deployable cap action is required.")
    finite_values = np.take(array, deployable_indices, axis=action_axis)
    local_choice = _lower_cap_argmax(finite_values, axis=action_axis)
    return np.asarray(deployable_indices[local_choice], dtype=np.int64)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
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
        "--behaviour-value-basis",
        choices=("low", "base", "high"),
        default="base",
        help=(
            "dynamic Behaviour proxy sensitivity basis; base uses the central "
            "performance-shortfall response"
        ),
    )
    parser.add_argument(
        "--performance-gap-behaviour",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "include the trailing reference-fund versus credited-return gap in "
            "dynamic lapse hazards (default: enabled)"
        ),
    )
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
        "--benchmark-paths", type=int, default=None,
        help=(
            "paths in each independent fixed-cap selection, adaptive-policy "
            "validation and final evaluation sample; defaults to 10%% of "
            "--n-paths.  This is the dominant runtime lever (fixed-cap "
            "benchmarks and the causal rollouts scale ~linearly with it); pass "
            "an explicit value to override the 10%% rule"
        ),
    )
    parser.add_argument(
        "--benchmark-batch-size", type=int, default=4,
        help=(
            "retained for CLI compatibility; dynamic-Behaviour fixed-cap cases "
            "are projected separately to preserve common Behaviour draws"
        ),
    )
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument("--cross-fit-folds", type=int, default=5)
    parser.add_argument(
        "--ridge", type=float, default=1.0e-4,
        help=(
            "dimensionless ridge multiplier for the regression normal matrix; "
            "pass 0 for ordinary least squares (OLS, the classic gas-storage "
            "regression).  The internal Bellman regressions use the slim "
            "economic 4/6-column basis; deployable policies are projected "
            "onto the full rollout basis"
        ),
    )
    parser.add_argument(
        "--persistent-exploration-fraction", type=float, default=0.5,
        help=(
            "fraction of paths assigned a constant exploratory cap history "
            "to cover low/high endogenous credited-index states"
        ),
    )
    parser.add_argument(
        "--portfolio-contract-count", type=float, default=None,
        help="optional absolute contract count; otherwise PVs are normalised",
    )
    parser.add_argument(
        "--inventory-nodes", type=int, default=25,
        help=(
            "number of account-value inventory grid nodes (the gas-storage "
            "Gitter) used by the backward induction"
        ),
    )
    parser.add_argument(
        "--inventory-quantile-clip", type=float, default=0.005,
        help=(
            "lower/upper quantile clip when placing the account-value grid "
            "nodes on the pooled in-force fund distribution"
        ),
    )
    parser.add_argument(
        "--benchmark-cache-dir", type=Path,
        default=DEFAULT_BENCHMARK_CACHE_DIRECTORY,
        help=(
            "directory holding cached fixed-cap benchmark projections; the "
            "fixed-cap benchmarks depend only on the market scenarios, cap and "
            "assumptions (not on the fitted LSMC policy), so an identical "
            "repeat configuration reuses them instead of re-projecting"
        ),
    )
    parser.add_argument(
        "--no-benchmark-cache", action="store_true",
        help="disable the fixed-cap benchmark projection cache",
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
        help=(
            "base output directory; each run is written to a new UTC timestamp "
            "subdirectory"
        ),
    )
    args = parser.parse_args(argv)
    # Kept as an internal provenance field so shared reporting helpers can use
    # one stable schema.  It is intentionally not user-configurable here.
    args.policyholder_behaviour = "dynamic"

    if args.n_paths <= 0:
        parser.error("--n-paths must be positive")
    if args.benchmark_paths is None:
        # Default: the benchmark (fixed-cap selection, adaptive validation and
        # final evaluation) paths are 10% of the capital-market training paths.
        args.benchmark_paths = max(30, int(round(0.1 * args.n_paths)))
    if args.benchmark_paths <= 0:
        parser.error("--benchmark-paths must be positive")
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
        parser.error("--ridge must be finite and non-negative (0 = OLS)")
    if not 0.0 <= args.persistent_exploration_fraction < 1.0:
        parser.error("--persistent-exploration-fraction must be in [0, 1)")
    if args.inventory_nodes < 3:
        parser.error("--inventory-nodes must be at least three")
    if not 0.0 <= args.inventory_quantile_clip < 0.5:
        parser.error("--inventory-quantile-clip must be in [0, 0.5)")
    if (args.portfolio_contract_count is not None
            and (not np.isfinite(args.portfolio_contract_count)
                 or args.portfolio_contract_count <= 0.0)):
        parser.error("--portfolio-contract-count must be positive and finite")
    _, _, insurer_basis_names = _basis_specification(
        (*CONTROL_STATE_FEATURE_NAMES, *PORTFOLIO_CONTROL_STATE_FEATURE_NAMES)
    )
    minimum_per_action_fit = max(30, 3 * len(insurer_basis_names))
    minimum_per_action_total = math.ceil(
        minimum_per_action_fit
        * args.cross_fit_folds
        / (args.cross_fit_folds - 2)
        * 1.10
    )
    min_paths = len(ACTION_CAPS) * minimum_per_action_total
    if args.n_paths < min_paths:
        parser.error(
            f"--n-paths must be at least {min_paths} for stable action/fold coverage"
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


def _vector_intra_year_value_factor(
    x0: float | Array,
    protection: Protection,
    cap: float | Array,
    tau: float,
    rate: float | Array,
    dividend_yield: float,
    sigma: float | Array,
    buffer: float = 0.10,
) -> float | Array:
    """Array-cap equivalent of the engine's DVA replication factor."""
    zcb = np.exp(-np.asarray(rate, dtype=float) * max(float(tau), 0.0))
    package = _vector_crediting_package_value(
        x0,
        protection,
        cap,
        tau,
        rate,
        dividend_yield,
        sigma,
        buffer,
    )
    result = zcb + np.asarray(package)
    scalar = all(np.ndim(value) == 0 for value in (x0, cap, rate, sigma))
    return float(result) if scalar else np.asarray(result, dtype=float)


def _vector_hedge_option_package_value(
    x0: float | Array,
    cap: float | Array,
    tau: float,
    rate: float | Array,
    dividend_yield: float,
    sigma: float | Array,
    cap_leg_mode: HedgeCapLegMode | str = HedgeCapLegMode.SOLD,
) -> float | Array:
    """Array-cap equivalent of the insurer's option-hedge package."""
    try:
        mode = HedgeCapLegMode(cap_leg_mode)
    except (TypeError, ValueError) as exc:
        raise ValueError("Unknown hedge cap-leg mode.") from exc

    spot, caps, rates, vols = np.broadcast_arrays(
        np.asarray(x0, dtype=float),
        np.asarray(cap, dtype=float),
        np.asarray(rate, dtype=float),
        np.asarray(sigma, dtype=float),
    )
    tau = float(tau)
    dividend_yield = float(dividend_yield)
    if not np.all(np.isfinite(spot)) or np.any(spot < 0.0):
        raise ValueError("x0 must be finite and non-negative.")
    if np.any(np.isnan(caps)) or np.any(caps < 0.0):
        raise ValueError("cap must be non-negative and not NaN.")
    if not np.all(np.isfinite(rates)):
        raise ValueError("r must be finite.")
    if not np.all(np.isfinite(vols)) or np.any(vols < 0.0):
        raise ValueError("sigma must be finite and non-negative.")
    if not np.isfinite(tau) or tau < 0.0:
        raise ValueError("tau must be finite and non-negative.")
    if not np.isfinite(dividend_yield):
        raise ValueError("q must be finite.")

    long_call = np.asarray(_vector_bs_call(
        spot, 1.0, tau, rates, dividend_yield, vols,
    ))
    if mode == HedgeCapLegMode.SOLD:
        result = long_call - np.asarray(_vector_bs_call(
            spot, 1.0 + caps, tau, rates, dividend_yield, vols,
        ))
    else:
        result = long_call
    scalar = all(np.ndim(value) == 0 for value in (x0, cap, rate, sigma))
    return float(result) if scalar else np.asarray(result, dtype=float)


def _vector_retained_excess_return(
    index_return: float | Array,
    cap: float | Array,
    cap_leg_mode: HedgeCapLegMode | str = HedgeCapLegMode.SOLD,
) -> float | Array:
    """Array-cap equivalent of the insurer's retained excess payoff."""
    try:
        mode = HedgeCapLegMode(cap_leg_mode)
    except (TypeError, ValueError) as exc:
        raise ValueError("Unknown hedge cap-leg mode.") from exc

    returns, caps = np.broadcast_arrays(
        np.asarray(index_return, dtype=float), np.asarray(cap, dtype=float)
    )
    if not np.all(np.isfinite(returns)):
        raise ValueError("index_return must be finite.")
    if np.any(np.isnan(caps)) or np.any(caps < 0.0):
        raise ValueError("cap must be non-negative and not NaN.")
    result = (
        np.zeros_like(returns)
        if mode == HedgeCapLegMode.SOLD
        else np.maximum(returns - caps, 0.0)
    )
    scalar = np.ndim(index_return) == 0 and np.ndim(cap) == 0
    return float(result) if scalar else np.asarray(result, dtype=float)


@contextmanager
def _pathwise_cap_adapter() -> Iterator[None]:
    """Temporarily vectorise projector calls reached by pathwise cap controls.

    The adapter is process-local and restored in ``finally``.  It vectorises
    customer and insurer option functions so that the direct monthly
    projection retains DVA and includes pathwise cap-dependent hedge costs and
    retained hedge gains.
    """
    original_return = projection_module.credited_return
    original_package = projection_module.crediting_package_value
    original_intra_year = projection_module.intra_year_value_factor
    original_hedge_package = projection_module.hedge_option_package_value
    original_retained_excess = projection_module.retained_excess_return
    projection_module.credited_return = _vector_credited_return
    projection_module.crediting_package_value = _vector_crediting_package_value
    projection_module.intra_year_value_factor = _vector_intra_year_value_factor
    projection_module.hedge_option_package_value = (
        _vector_hedge_option_package_value
    )
    projection_module.retained_excess_return = _vector_retained_excess_return
    try:
        yield
    finally:
        projection_module.credited_return = original_return
        projection_module.crediting_package_value = original_package
        projection_module.intra_year_value_factor = original_intra_year
        projection_module.hedge_option_package_value = original_hedge_package
        projection_module.retained_excess_return = original_retained_excess


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


def _array_fingerprint(values: Array) -> str:
    """Stable provenance fingerprint for one complete path/control sample."""
    array = np.ascontiguousarray(np.asarray(values, dtype=np.float64))
    digest = hashlib.sha256()
    digest.update(str(array.shape).encode("ascii"))
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(array.view(np.uint8))
    return digest.hexdigest()


_PROJECTION_SAMPLE_SEED_OFFSETS = MappingProxyType({
    "training": 100_003,
    "fixed_cap_selection": 200_003,
    "validation": 300_007,
    "evaluation": 400_009,
})


def _projection_configs_by_sample(
    base: ProjectionConfig,
) -> dict[str, ProjectionConfig]:
    """Create reproducible, disjoint projector-RNG namespaces by sample role.

    Common random numbers are deliberately retained *within* a sample role:
    every policy compared on validation, for example, receives identical
    Income-Election and pathwise-mortality draws.  Across training, fixed-cap
    selection, validation and final evaluation those draws must be independent.
    """
    configs = {
        role: replace(
            base,
            take_up_seed=int(base.take_up_seed) + offset,
            mortality_seed=int(base.mortality_seed) + offset,
        )
        for role, offset in _PROJECTION_SAMPLE_SEED_OFFSETS.items()
    }
    if len({item.take_up_seed for item in configs.values()}) != len(configs):
        raise RuntimeError("Take-up RNG sample namespaces are not distinct.")
    if len({item.mortality_seed for item in configs.values()}) != len(configs):
        raise RuntimeError("Mortality RNG sample namespaces are not distinct.")
    return configs


def _fit_cap_aware_policyholder_policies(
    *,
    cap_matrix: Array,
    scenarios: ScenarioSet,
    product: IndexLinkedLifetimeIncomeProduct,
    model_points: PolicyholderModelPointSet,
    mortality: MortalityTable,
    expenses: ExpenseAssumptions,
    projection_config: ProjectionConfig,
    settings: OptimalBehaviourLSMCSettings,
    progress_label: str,
) -> PolicyholderFitSet:
    """Fit one follower policy per economic PolicySpec signature.

    The complete pathwise cap schedule is part of the training sample.  Caps
    enter the observable follower state in ``optimal_behaviour_lsmc``; a fit
    is therefore never trained under one reference cap and reused as if it
    were cap invariant.  Joint and Single-Life fallback branches are fitted
    before any spouse-survival or portfolio weighting is applied.
    """
    caps = np.asarray(cap_matrix, dtype=float)
    if caps.ndim != 2 or caps.shape[0] != scenarios.n_paths:
        raise ValueError("Follower cap matrix must match the training paths.")
    if np.any(np.isnan(caps)) or np.any(caps < 0.0):
        raise ValueError("Follower cap schedules must be non-negative and not NaN.")
    controlled = _controlled_product(product, caps)
    no_actions = no_voluntary_action_behaviour()
    policies: dict[tuple[object, ...], PolicySpec] = {}
    for point in model_points.model_points:
        for branch in _projection_branches(
            point, product, mortality, no_actions
        ):
            policies.setdefault(_policy_signature(branch.policy), branch.policy)
    fits: dict[tuple[object, ...], object] = {}
    LOGGER.info(
        "%s | %d separate PolicySpec signatures | paths=%d",
        progress_label,
        len(policies),
        scenarios.n_paths,
    )
    follower_projection = replace(
        projection_config,
        record_paths=True,
        heston_cos=False,
    )
    with _pathwise_cap_adapter():
        for number, (signature, policy) in enumerate(policies.items(), start=1):
            LOGGER.info(
                "%s | follower fit %d/%d | age=%.0f | premium=%.0f | spouse=%s",
                progress_label,
                number,
                len(policies),
                policy.age,
                policy.initial_investment,
                policy.spouse,
            )
            fits[signature] = fit_optimal_surrender_policy(
                controlled,
                policy,
                scenarios,
                mortality,
                expenses=expenses,
                projection_config=follower_projection,
                settings=settings,
            )
    return PolicyholderFitSet(
        fits=fits,
        scenario_fingerprint=scenarios.content_fingerprint,
        cap_schedule_fingerprint=_array_fingerprint(caps),
    )


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
    """Describe the effective dynamic treatment used by this runner."""
    dynamic_active = (
        behaviour.use_dynamic
        or behaviour.use_dynamic_take_up
        or behaviour.use_dynamic_withdrawals
    )
    if point.policy.spouse:
        return (
            "pathwise_joint_life_state_dependent"
            if dynamic_active
            else "pathwise_joint_life_static_base"
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
    """Use the projector's pathwise Joint-Life dynamic-behaviour treatment."""
    if not point.policy.spouse:
        return (ProjectionBranch(
            policy=point.policy,
            probability=1.0,
            behaviour=behaviour,
            label="single",
        ),)
    # ``project`` maintains the primary/spouse life-state cohorts internally
    # whenever dynamic Behaviour or non-deterministic Take-up is active.  A
    # deterministic spouse-survival split would suppress that state dependence.
    return (ProjectionBranch(
        policy=point.policy,
        probability=1.0,
        behaviour=behaviour,
        label="pathwise_joint_life_state_dependent",
    ),)


def _model_point_treatment_rows(
    model_points: PolicyholderModelPointSet,
    product: IndexLinkedLifetimeIncomeProduct,
    mortality: MortalityTable,
    behaviour: BehaviourModel,
    source_behaviour: BehaviourModel,
) -> list[dict[str, object]]:
    """Audit dynamic Election and pathwise Behaviour treatment by model point."""
    rows: list[dict[str, object]] = []
    for point in model_points.model_points:
        policy = point.policy
        scheduled = int(round(float(policy.income_start_year)))
        years_to_automatic_age = max(
            float(product.automatic_income_start_age) - float(policy.age),
            0.0,
        )
        automatic_start_anniversary = max(
            int(np.floor(years_to_automatic_age + 1.0e-12)) + 1,
            int(product.min_years_before_income),
            1,
        )
        dynamic_active = (
            behaviour.use_dynamic
            or behaviour.use_dynamic_take_up
            or behaviour.use_dynamic_withdrawals
        )
        rows.append({
            "model_point_id": point.model_point_id,
            "contract_weight": float(point.contract_weight),
            "scheduled_income_start_year": scheduled,
            "scheduled_income_start_year_used_for_dynamic_take_up": False,
            "effective_income_start_year": None,
            "effective_start_overrides_scheduled_start": None,
            "effective_start_override_reason": "not_applicable_dynamic_take_up",
            "product_min_years_before_income": int(
                product.min_years_before_income
            ),
            "product_automatic_income_start_age": float(
                product.automatic_income_start_age
            ),
            "automatic_start_anniversary": automatic_start_anniversary,
            "source_income_take_up_mode": source_behaviour.take_up.mode,
            "effective_income_take_up_mode": behaviour.take_up.mode,
            "dynamic_take_up_coefficients_applied": bool(
                behaviour.use_dynamic_take_up
            ),
            "take_up_override_reason": None,
            "spouse": bool(policy.spouse),
            "spouse_death_election": (
                policy.spouse_death_election.value if policy.spouse else None
            ),
            "spouse_survival_to_effective_income_election": None,
            "behaviour_treatment": _model_point_behaviour_treatment(
                point, behaviour
            ),
            "joint_branch_behaviour_regime": (
                ("dynamic" if dynamic_active else "static")
                if policy.spouse else None
            ),
            "single_fallback_behaviour_regime": None,
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
    cohorts = tuple(sorted(cohort_set))
    # Dynamic Take-up makes the realised Income start path-dependent; a
    # deterministic model-point start cohort would misstate the control state.
    effective_income_starts: tuple[int, ...] = ()
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
            out[:, year] += np.sum(
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


def _annual_discounted_control_paths(
    cashflow: Array,
    post_cap_cashflow: Array,
    discount: Array,
    n_years: int,
) -> Array:
    """Assign split Anniversary cashflows to the economically correct cap.

    The canonical ledger timestamps all Anniversary events in one column.
    Old-cap crediting, fee posting, mortality and Election belong to the year
    ending there; hedge restart, customer actions and later same-timestamp
    events belong to the cap announced at that boundary.  The projector's
    auxiliary ``post_cap_cashflow`` ledger identifies exactly the latter
    portion, so no contractual event order is changed or inferred here.
    """
    values = np.asarray(cashflow, dtype=float)
    post = np.asarray(post_cap_cashflow, dtype=float)
    disc = np.asarray(discount, dtype=float)
    if values.shape != post.shape or values.shape != disc.shape:
        raise ValueError("Control-year cashflow ledgers must have equal shapes.")
    out = _annual_discounted_paths(
        values,
        disc,
        n_years,
        include_time_zero_in_first_year=True,
    )
    # The final grid anniversary has no subsequent control year.  Internal
    # boundaries alone are shifted from the old-cap reward to the new one.
    for new_year in range(1, n_years):
        step = new_year * STEPS_PER_YEAR
        if step >= values.shape[1]:
            break
        shifted = post[:, step] * disc[:, step]
        out[:, new_year - 1] -= shifted
        out[:, new_year] += shifted
    total = np.sum(values * disc, axis=1)
    gap = total - np.sum(out, axis=1)
    tolerance = 1.0e-10 * max(1.0, float(np.max(np.abs(total))))
    if np.any(np.abs(gap) > tolerance):
        raise RuntimeError("Control-year cashflow allocation failed to reconcile.")
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
    surrender_policy_factory: Optional[Callable[[PolicySpec], object]] = None,
    collect_stackelberg_primitives: bool = False,
    collect_policyholder_by_signature: bool = False,
    collect_pre_action_states: bool = False,
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
        "%s | %d model points | %d market paths | %d policy years | "
        "full_states=%s | pre_action_states=%s",
        progress_label,
        point_count,
        scenarios.n_paths,
        n_years,
        collect_states,
        collect_pre_action_states,
    )
    guarantee_claims = np.zeros((scenarios.n_paths, n_years))
    other_insurer_funded_benefits = np.zeros_like(guarantee_claims)
    fees_product = np.zeros_like(guarantee_claims)
    fees_lip = np.zeros_like(guarantee_claims)
    crediting_margin = np.zeros_like(guarantee_claims)
    money_market_income = np.zeros_like(guarantee_claims)
    hedge_gain = np.zeros_like(guarantee_claims)
    mva_retained = np.zeros_like(guarantee_claims)
    aps_retained = np.zeros_like(guarantee_claims)
    projected_expenses = np.zeros_like(guarantee_claims)
    hedge_costs = np.zeros_like(guarantee_claims)
    income_paid = np.zeros_like(guarantee_claims)
    death_benefits = np.zeros_like(guarantee_claims)
    surrender_benefits = np.zeros_like(guarantee_claims)
    partial_withdrawals = np.zeros_like(guarantee_claims)
    terminal_closeout = np.zeros_like(guarantee_claims)
    lapse_events = np.zeros_like(guarantee_claims)
    signature_control_paths: dict[
        tuple[object, ...], SignatureControlPaths
    ] = {}
    policyholder_benefits_by_signature: dict[
        tuple[object, ...], Array
    ] = {}
    if collect_stackelberg_primitives and surrender_policy_factory is not None:
        raise ValueError(
            "Stackelberg primitive collection requires the no-action recorder; "
            "an external surrender policy cannot be supplied simultaneously."
        )

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
    pre_action_feature_names: tuple[str, ...] = ()
    pre_action_feature_index: dict[str, int] = {}
    pre_action_states: Array | None = None
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
    if (
        collect_states
        or collect_pre_action_states
        or collect_stackelberg_primitives
    ):
        pre_action_feature_names = PORTFOLIO_CONTROL_STATE_FEATURE_NAMES
        pre_action_feature_index = {
            name: position
            for position, name in enumerate(pre_action_feature_names)
        }
        pre_action_states = np.zeros(
            (
                scenarios.n_paths,
                n_years + 1,
                len(pre_action_feature_names),
            ),
            dtype=float,
        )
        for year in range(n_years + 1):
            step = min(year * STEPS_PER_YEAR, scenarios.n_steps)
            pre_action_states[
                :, year, pre_action_feature_index["short_rate"]
            ] = scenarios.short_rate[:, step]
    if collect_states:
        if raw_states is None:
            raise RuntimeError("Full state storage was not initialised.")
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
                cap_state_collector = (
                    _CapDecisionStateCollector()
                    if (
                        collect_states
                        or collect_pre_action_states
                        or collect_stackelberg_primitives
                    )
                    else None
                )
                primitive_collector = (
                    _StackelbergPrimitiveCollector()
                    if collect_stackelberg_primitives else None
                )
                result = projection_module.project(
                    controlled,
                    policy,
                    scenarios,
                    branch.behaviour,
                    mortality,
                    expenses=expenses,
                    config=config,
                    surrender_policy=(
                        primitive_collector
                        if primitive_collector is not None
                        else None
                        if surrender_policy_factory is None
                        else surrender_policy_factory(policy)
                    ),
                    cap_decision_observer=cap_state_collector,
                    surrender_decision_observer=primitive_collector,
                )
                branch_weight = float(point.contract_weight * branch_probability)
                n_columns = len(result.times)
                discount = scenarios.discount[:, :n_columns]
                if result.post_cap_cashflows is None \
                        or result.post_cap_lapse_events is None:
                    raise RuntimeError(
                        "Projection result lacks the Anniversary cap boundary ledger."
                    )
                if result.post_surrender_cashflows is None:
                    raise RuntimeError(
                        "Projection result lacks the customer action-boundary ledger."
                    )

                def annual_control_cashflow(key: str) -> Array:
                    return _annual_discounted_control_paths(
                        result.cashflows[key],
                        result.post_cap_cashflows[key],
                        discount,
                        n_years,
                    )

                guarantee_claims += (
                    branch_weight * annual_control_cashflow("guarantee_claims")
                )
                for key in OTHER_INSURER_FUNDED_BENEFIT_KEYS:
                    other_insurer_funded_benefits += (
                        branch_weight * annual_control_cashflow(key)
                    )
                fees_product += branch_weight * annual_control_cashflow(
                    "fees_product"
                )
                fees_lip += branch_weight * annual_control_cashflow(
                    "fees_lip"
                )
                annual_crediting_margin = annual_control_cashflow(
                    "crediting_margin"
                )
                crediting_margin += branch_weight * annual_crediting_margin
                money_market_income += branch_weight * annual_control_cashflow(
                    "money_market_income"
                )
                hedge_gain += branch_weight * annual_control_cashflow(
                    "hedge_gain"
                )
                mva_retained += branch_weight * annual_control_cashflow(
                    "mva_retained"
                )
                aps_retained += branch_weight * annual_control_cashflow(
                    "aps_retained"
                )
                projected_expenses += branch_weight * annual_control_cashflow(
                    "expenses"
                )
                hedge_costs += branch_weight * annual_control_cashflow(
                    "hedge_costs"
                )
                income_paid += branch_weight * annual_control_cashflow(
                    "income_paid"
                )
                death_benefits += branch_weight * annual_control_cashflow(
                    "death_benefits"
                )
                surrender_benefits += branch_weight * annual_control_cashflow(
                    "surrender_benefits"
                )
                partial_withdrawals += branch_weight * annual_control_cashflow(
                    "partial_withdrawals"
                )
                terminal_closeout += branch_weight * annual_control_cashflow(
                    "terminal_closeout"
                )
                lapse_events += branch_weight * _annual_discounted_control_paths(
                    result.lapse_events,
                    result.post_cap_lapse_events,
                    np.ones_like(discount),
                    n_years,
                )

                signature = _policy_signature(policy)
                if collect_policyholder_by_signature:
                    signature_benefits = sum(
                        annual_control_cashflow(key)
                        for key in (
                            "income_paid",
                            "death_benefits",
                            "surrender_benefits",
                            "partial_withdrawals",
                            "terminal_closeout",
                        )
                    )
                    policyholder_benefits_by_signature.setdefault(
                        signature, np.zeros_like(signature_benefits)
                    )
                    policyholder_benefits_by_signature[signature] += (
                        branch_weight * signature_benefits
                    )

                if collect_stackelberg_primitives:
                    if primitive_collector is None or cap_state_collector is None:
                        raise RuntimeError("Stackelberg primitive collectors are missing.")
                    ph_cashflow = sum(
                        result.cashflows[key]
                        for key in (
                            "income_paid",
                            "death_benefits",
                            "surrender_benefits",
                            "partial_withdrawals",
                            "terminal_closeout",
                        )
                    )
                    ph_post_action = sum(
                        result.post_surrender_cashflows[key]
                        for key in (
                            "income_paid",
                            "death_benefits",
                            "surrender_benefits",
                            "partial_withdrawals",
                            "terminal_closeout",
                        )
                    )
                    ph_intervals = _annual_discounted_control_paths(
                        ph_cashflow,
                        ph_post_action,
                        discount,
                        n_years,
                    )
                    continue_components = np.stack((
                        annual_control_cashflow("fees_product"),
                        annual_control_cashflow("fees_lip"),
                        annual_control_cashflow("crediting_margin"),
                        annual_control_cashflow("mva_retained"),
                        annual_control_cashflow("aps_retained"),
                        annual_control_cashflow("guarantee_claims"),
                        np.zeros_like(annual_crediting_margin),
                        annual_control_cashflow("expenses"),
                        annual_control_cashflow("hedge_costs"),
                    ), axis=2)
                    full_components = np.array(continue_components, copy=True)
                    for year, action_context in (
                        primitive_collector.action_value_contexts.items()
                    ):
                        if year < 0 or year >= n_years:
                            continue
                        step = int(getattr(action_context, "step"))
                        common = getattr(
                            action_context, "post_cap_common_cashflows"
                        )
                        full = getattr(
                            action_context,
                            "full_withdrawal_post_action_cashflows",
                        )

                        def full_value(key: str) -> Array:
                            return (
                                np.asarray(common[key], dtype=float)
                                + np.asarray(full[key], dtype=float)
                            ) * discount[:, step]

                        full_components[:, year, :] = np.column_stack((
                            full_value("fees_product"),
                            full_value("fees_lip"),
                            full_value("crediting_margin"),
                            full_value("mva_retained"),
                            full_value("aps_retained"),
                            full_value("guarantee_claims"),
                            np.zeros(scenarios.n_paths),
                            full_value("expenses"),
                            full_value("hedge_costs"),
                        ))

                    first_decision_year = (
                        policy.effective_income_start_year(product) + 1
                    )
                    existing = signature_control_paths.get(signature)
                    if existing is None:
                        existing = SignatureControlPaths(
                            signature=signature,
                            policy=policy,
                            decision_years={},
                        )
                        signature_control_paths[signature] = existing
                    for year in range(first_decision_year, n_years):
                        action_context = (
                            primitive_collector.action_value_contexts.get(year)
                        )
                        cap_context = cap_state_collector.contexts.get(year)
                        if action_context is None or cap_context is None:
                            continue
                        decision_context = getattr(
                            action_context, "decision_context"
                        )
                        next_context = (
                            primitive_collector.surrender_contexts.get(year + 1)
                        )
                        current_step = int(getattr(decision_context, "step"))
                        current_scale = (
                            discount[:, current_step]
                            * np.asarray(
                                getattr(decision_context, "inforce_weight"),
                                dtype=float,
                            )
                        )
                        if next_context is None:
                            next_scale = np.zeros(scenarios.n_paths)
                        else:
                            next_step = int(getattr(next_context, "step"))
                            next_scale = (
                                discount[:, next_step]
                                * np.asarray(
                                    getattr(next_context, "inforce_weight"),
                                    dtype=float,
                                )
                            )
                        exposure_context = cap_state_collector.contexts.get(
                            year + 1
                        )
                        next_exposure = np.zeros((scenarios.n_paths, 9))
                        if exposure_context is not None:
                            exposure_phase = np.asarray(
                                getattr(exposure_context, "phase"), dtype=np.int8
                            )
                            exposure_inforce = np.asarray(
                                getattr(exposure_context, "inforce_weight"),
                                dtype=float,
                            )
                            account_value = np.maximum(np.asarray(
                                getattr(exposure_context, "account_value")
                            ), 0.0)
                            surrender_value = np.maximum(np.asarray(
                                getattr(exposure_context, "surrender_value")
                            ), 0.0)
                            locked_income = np.maximum(np.asarray(
                                getattr(exposure_context, "locked_annual_income")
                            ), 0.0)
                            guarantee_pv = np.maximum(np.asarray(
                                getattr(exposure_context, "guarantee_pv")
                            ), 0.0)
                            guarantee_mny = np.clip(np.asarray(
                                getattr(exposure_context, "guarantee_moneyness")
                            ), 0.0, 20.0)
                            next_exposure = np.column_stack((
                                exposure_inforce,
                                exposure_inforce
                                * (exposure_phase == Phase.GROWTH.value),
                                exposure_inforce
                                * (exposure_phase == Phase.INCOME.value),
                                exposure_inforce * account_value
                                / representative_premium,
                                exposure_inforce * surrender_value
                                / representative_premium,
                                exposure_inforce * locked_income
                                / representative_premium,
                                exposure_inforce * guarantee_pv
                                / representative_premium,
                                exposure_inforce * guarantee_mny,
                                exposure_inforce
                                * (exposure_phase == Phase.INCOME.value)
                                * (
                                    account_value
                                    <= 1.0e-10 * policy.initial_investment
                                ),
                            ))
                        delta = branch_weight * (
                            full_components[:, year, :]
                            - continue_components[:, year, :]
                        )
                        contribution = branch_weight * next_exposure
                        record = existing.decision_years.get(year)
                        if record is None:
                            existing.decision_years[year] = (
                                SignatureDecisionYearPaths(
                                    policy_year=year,
                                    decision_step=current_step,
                                    pre_cap_core=_compact_follower_core(
                                        cap_context,
                                        premium=float(policy.net_initial_investment),
                                        cap_attribute="previous_cap",
                                    ),
                                    after_cap_core=_compact_follower_core(
                                        decision_context,
                                        premium=float(policy.net_initial_investment),
                                        cap_attribute="announced_cap",
                                    ),
                                    phase=np.asarray(
                                        getattr(decision_context, "phase"),
                                        dtype=np.int8,
                                    ).copy(),
                                    just_elected=np.asarray(
                                        getattr(decision_context, "just_elected"),
                                        dtype=bool,
                                    ).copy(),
                                    full_withdrawal_eligible=np.asarray(
                                        getattr(
                                            decision_context,
                                            "full_withdrawal_eligible",
                                        ),
                                        dtype=bool,
                                    ).copy(),
                                    decision_discount_inforce=np.asarray(
                                        current_scale, dtype=np.float32
                                    ),
                                    next_decision_discount_inforce=np.asarray(
                                        next_scale, dtype=np.float32
                                    ),
                                    continue_policyholder_interval_pv=np.asarray(
                                        ph_intervals[:, year], dtype=np.float32
                                    ),
                                    full_withdrawal_value=np.asarray(
                                        getattr(
                                            decision_context,
                                            "surrender_value",
                                        ),
                                        dtype=np.float32,
                                    ),
                                    insurer_full_minus_continue_components=(
                                        np.asarray(delta, dtype=np.float32)
                                    ),
                                    next_portfolio_exposure_contribution=(
                                        np.asarray(contribution, dtype=np.float32)
                                    ),
                                )
                            )
                        else:
                            record.insurer_full_minus_continue_components += (
                                np.asarray(delta, dtype=np.float32)
                            )
                            record.next_portfolio_exposure_contribution += (
                                np.asarray(contribution, dtype=np.float32)
                            )

                if pre_action_states is not None:
                    if cap_state_collector is None:
                        raise RuntimeError("Pre-action state collector is missing.")
                    for year, context in cap_state_collector.contexts.items():
                        if year < 0 or year > n_years:
                            continue
                        phase_at_decision = np.asarray(context.phase, dtype=np.int8)
                        inforce_at_decision = np.asarray(
                            context.inforce_weight, dtype=float
                        )
                        exposure = branch_weight * inforce_at_decision
                        growth_exposure = exposure * (
                            phase_at_decision == Phase.GROWTH.value
                        )
                        income_exposure = exposure * (
                            phase_at_decision == Phase.INCOME.value
                        )
                        account_value = np.maximum(
                            np.asarray(context.account_value, dtype=float), 0.0
                        )
                        surrender_value = np.maximum(
                            np.asarray(context.surrender_value, dtype=float), 0.0
                        )
                        locked_income = np.maximum(
                            np.asarray(context.locked_annual_income, dtype=float),
                            0.0,
                        )
                        guarantee_pv = np.maximum(
                            np.asarray(context.guarantee_pv, dtype=float), 0.0
                        )
                        guarantee_moneyness = np.clip(
                            np.asarray(context.guarantee_moneyness, dtype=float),
                            0.0,
                            20.0,
                        )
                        values = {
                            "inforce_exposure": exposure,
                            "growth_exposure": growth_exposure,
                            "income_exposure": income_exposure,
                            "account_value_per_initial_premium": (
                                exposure * account_value
                            ),
                            "surrender_value_per_initial_premium": (
                                exposure * surrender_value
                            ),
                            "locked_income_per_initial_premium": (
                                exposure * locked_income
                            ),
                            "guarantee_pv_per_initial_premium": (
                                exposure * guarantee_pv
                            ),
                            "guarantee_moneyness_exposure": (
                                exposure * guarantee_moneyness
                            ),
                            "exhausted_income_exposure": (
                                income_exposure
                                * (
                                    account_value
                                    <= 1.0e-10 * policy.initial_investment
                                )
                            ),
                        }
                        for name, value in values.items():
                            pre_action_states[
                                :, year, pre_action_feature_index[name]
                            ] += value

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

    inforce_exposure: Array | None = None
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
    if pre_action_states is not None:
        pre_action_monetary_columns = [
            pre_action_feature_index[name]
            for name in (
                "account_value_per_initial_premium",
                "surrender_value_per_initial_premium",
                "locked_income_per_initial_premium",
                "guarantee_pv_per_initial_premium",
            )
        ]
        pre_action_states[:, :, pre_action_monetary_columns] /= (
            representative_premium
        )
        if not np.all(np.isfinite(pre_action_states)):
            raise RuntimeError("Pre-action portfolio states contain non-finite values.")
        inforce_exposure = np.array(
            pre_action_states[
                :, :, pre_action_feature_index["inforce_exposure"]
            ],
            copy=True,
        )

    if not np.allclose(
        crediting_margin,
        money_market_income + hedge_gain,
        rtol=1.0e-12,
        atol=1.0e-8,
    ):
        raise RuntimeError(
            "Crediting margin does not reconcile to money-market income plus "
            "retained hedge gain."
        )
    if projection_config.hedge_cap_leg_mode == HedgeCapLegMode.SOLD \
            and not np.allclose(hedge_gain, 0.0, rtol=0.0, atol=1.0e-10):
        raise RuntimeError(
            "The standard sold cap leg must not retain Reference-Fund "
            "performance above the customer cap."
        )

    return PortfolioPathData(
        guarantee_claims=guarantee_claims,
        other_insurer_funded_benefits=other_insurer_funded_benefits,
        fees_product=fees_product,
        fees_lip=fees_lip,
        crediting_margin=crediting_margin,
        money_market_income=money_market_income,
        hedge_gain=hedge_gain,
        mva_retained=mva_retained,
        aps_retained=aps_retained,
        expenses=projected_expenses,
        hedge_costs=hedge_costs,
        income_paid=income_paid,
        death_benefits=death_benefits,
        surrender_benefits=surrender_benefits,
        partial_withdrawals=partial_withdrawals,
        terminal_closeout=terminal_closeout,
        lapse_events=lapse_events,
        inforce_exposure=inforce_exposure,
        raw_states=raw_states,
        state_feature_names=feature_names,
        pre_action_states=pre_action_states,
        pre_action_state_feature_names=pre_action_feature_names,
        representative_initial_premium=representative_premium,
        signature_control_paths=signature_control_paths,
        policyholder_benefits_by_signature=policyholder_benefits_by_signature,
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


def _slice_scenarios(
    scenarios: ScenarioSet,
    start: int,
    stop: int,
) -> ScenarioSet:
    """Return a path slice without changing the simulated market history."""
    if start < 0 or stop <= start or stop > scenarios.n_paths:
        raise ValueError("Invalid ScenarioSet path slice.")

    def sliced(array: Array) -> Array:
        return np.asarray(array)[start:stop]

    variance = None
    if scenarios.variance is not None:
        variance = {
            index: sliced(values)
            for index, values in scenarios.variance.items()
        }
    return ScenarioSet(
        config=scenarios.config,
        measure=scenarios.measure,
        dt=scenarios.dt,
        times=scenarios.times,
        index_levels={
            index: sliced(values)
            for index, values in scenarios.index_levels.items()
        },
        short_rate=sliced(scenarios.short_rate),
        discount=sliced(scenarios.discount),
        variance=variance,
        stochastic_rates=scenarios.stochastic_rates,
        model_name=scenarios.model_name,
        seed=scenarios.seed,
        substeps=scenarios.substeps,
        _copy_inputs=False,
    )


def _truncate_scenarios(
    scenarios: ScenarioSet,
    stop_step: int,
) -> ScenarioSet:
    """Return a time-prefix view for causal annual policy deployment."""
    if stop_step < 1 or stop_step > scenarios.n_steps:
        raise ValueError("Invalid ScenarioSet time-prefix endpoint.")
    stop = int(stop_step) + 1

    def truncated(array: Array) -> Array:
        return np.asarray(array)[:, :stop]

    variance = None
    if scenarios.variance is not None:
        variance = {
            index: truncated(values)
            for index, values in scenarios.variance.items()
        }
    return ScenarioSet(
        config=scenarios.config,
        measure=scenarios.measure,
        dt=scenarios.dt,
        times=np.asarray(scenarios.times)[:stop],
        index_levels={
            index: truncated(values)
            for index, values in scenarios.index_levels.items()
        },
        short_rate=truncated(scenarios.short_rate),
        discount=truncated(scenarios.discount),
        variance=variance,
        stochastic_rates=scenarios.stochastic_rates,
        model_name=scenarios.model_name,
        seed=scenarios.seed,
        substeps=scenarios.substeps,
        _copy_inputs=False,
    )


@dataclass(frozen=True)
class ControlStateInputs:
    """Pre-action market history used by the implementable cap policy."""

    market_features: Array
    annual_reference_fund_return: Array

    @property
    def n_paths(self) -> int:
        return int(self.market_features.shape[0])

    @property
    def n_years(self) -> int:
        return int(self.annual_reference_fund_return.shape[1])


def _control_state_inputs(
    scenarios: ScenarioSet,
    product: IndexLinkedLifetimeIncomeProduct,
    n_years: int,
) -> ControlStateInputs:
    """Build market variables observable at each annual decision time.

    The return in control year ``y`` is stored separately and is only used to
    update the state for ``y + 1``.  It therefore cannot leak into the cap
    decision at the start of year ``y``.
    """
    if n_years <= 0:
        raise ValueError("Control-state horizon is inconsistent with scenarios.")
    # The final market interval can be a partial policy year when a covered
    # life has a fractional issue age.  There is still one action at the start
    # of that final interval; its terminal state is observed at the last ESG
    # step rather than beyond the simulated horizon.
    annual_steps = np.minimum(
        np.arange(n_years + 1, dtype=int) * STEPS_PER_YEAR,
        int(scenarios.n_steps),
    )
    if np.any(np.diff(annual_steps) <= 0):
        raise ValueError("Control-state horizon is inconsistent with scenarios.")
    reference = scenarios.monthly_rebalanced_reference_fund_index(
        equity_index=product.reference_fund.equity_index,
        equity_weight=product.reference_fund.equity_weight,
        bond_tenor=product.reference_fund.bond_tenor_years,
    )
    annual_reference = reference[:, annual_steps]
    annual_return = (
        annual_reference[:, 1:]
        / np.maximum(annual_reference[:, :-1], 1.0e-300)
        - 1.0
    )
    features = np.zeros((scenarios.n_paths, n_years + 1, 5), dtype=float)
    for year, step in enumerate(annual_steps):
        features[:, year, 0] = scenarios.zero_rate(int(step), 5.0)
    if scenarios.variance is None:
        variance = np.full(
            (scenarios.n_paths, n_years + 1),
            scenarios.config.equity[Index.GLOBAL_EQUITY].sigma ** 2,
        )
    else:
        variance = scenarios.variance[Index.GLOBAL_EQUITY][:, annual_steps]
    features[:, :, 1] = variance
    features[:, :, 2] = np.log(
        np.maximum(scenarios.discount[:, annual_steps], 1.0e-300)
    )
    features[:, 1:, 3] = annual_return
    features[:, :, 4] = np.log(
        np.maximum(
            annual_reference / np.maximum(annual_reference[:, :1], 1.0e-300),
            1.0e-300,
        )
    )
    if not np.all(np.isfinite(features)) or not np.all(np.isfinite(annual_return)):
        raise RuntimeError("Control-state market inputs contain non-finite values.")
    return ControlStateInputs(features, annual_return)


def _control_state_paths(
    inputs: ControlStateInputs,
    cap_matrix: Array,
) -> Array:
    """Create compact, strictly pre-action states from realised history.

    The credited-index and excess-return variables are transparent state
    proxies, not additional calibrated product or Behaviour parameters.  They
    summarise the endogenous cap history while keeping a learned policy
    directly executable before the monthly product projection is run.
    """
    caps = np.asarray(cap_matrix, dtype=float)
    expected_shape = (inputs.n_paths, inputs.n_years)
    if caps.shape != expected_shape:
        raise ValueError(
            f"cap_matrix must have shape {expected_shape}, got {caps.shape}."
        )
    if not np.all(np.isfinite(caps)) or np.any(caps < 0.0):
        raise ValueError("Control-state caps must be finite and non-negative.")

    states = np.zeros(
        (inputs.n_paths, inputs.n_years + 1, len(CONTROL_STATE_FEATURE_NAMES)),
        dtype=float,
    )
    states[:, :, :5] = inputs.market_features
    log_credited = np.zeros(inputs.n_paths)
    cumulative_cap = np.zeros(inputs.n_paths)
    cumulative_excess = np.zeros(inputs.n_paths)
    previous_cap = np.zeros(inputs.n_paths)
    trailing_performance_shortfall = np.zeros(inputs.n_paths)
    for year in range(inputs.n_years + 1):
        states[:, year, 5] = log_credited
        states[:, year, 6] = previous_cap
        if year:
            states[:, year, 7] = cumulative_cap / year
            states[:, year, 8] = cumulative_excess / year
        states[:, year, 9] = trailing_performance_shortfall
        if year == inputs.n_years:
            break
        cap = caps[:, year]
        positive_return = np.maximum(
            inputs.annual_reference_fund_return[:, year], 0.0
        )
        credited = np.minimum(positive_return, cap)
        excess = np.maximum(positive_return - cap, 0.0)
        trailing_performance_shortfall = np.maximum(
            np.log1p(inputs.annual_reference_fund_return[:, year])
            - np.log1p(credited),
            0.0,
        )
        log_credited += np.log1p(credited)
        cumulative_cap += cap
        cumulative_excess += excess
        previous_cap = cap
    if not np.all(np.isfinite(states)):
        raise RuntimeError("Control states contain non-finite values.")
    return states


def _portfolio_state_extension(
    data: PortfolioPathData,
) -> tuple[Array, tuple[str, ...]]:
    """Return exact pre-cap portfolio states for leader decisions.

    Market/cap history is supplied by :func:`_control_state_paths`.  This
    extension comes from the projector's read-only decision observer after
    the old-cap events and before the current cap starts.  It therefore keeps
    customer exposure, surrender value and guarantee value without letting
    the current leader action leak into its own regressors.
    """
    if data.pre_action_states is None:
        raise ValueError("Pre-action portfolio state collection is required.")
    by_name = {
        name: position
        for position, name in enumerate(data.pre_action_state_feature_names)
    }
    missing = [
        name for name in PORTFOLIO_CONTROL_STATE_FEATURE_NAMES
        if name not in by_name
    ]
    if missing:
        raise ValueError(
            "Rich portfolio state is missing required features: "
            + ", ".join(missing)
        )
    positions = [by_name[name] for name in PORTFOLIO_CONTROL_STATE_FEATURE_NAMES]
    names = tuple(
        data.pre_action_state_feature_names[position] for position in positions
    )
    if not names:
        raise ValueError("No portfolio exposure features remain after state merge.")
    values = np.asarray(data.pre_action_states[:, :, positions], dtype=float)
    if not np.all(np.isfinite(values)):
        raise RuntimeError("Rich portfolio control states contain non-finite values.")
    return values, names


def _merge_control_and_portfolio_states(
    *,
    inputs: ControlStateInputs,
    cap_matrix: Array,
    data: PortfolioPathData,
) -> tuple[Array, tuple[str, ...], Array]:
    portfolio_values, portfolio_names = _portfolio_state_extension(data)
    compact = _control_state_paths(inputs, cap_matrix)
    if compact.shape[:2] != portfolio_values.shape[:2]:
        raise ValueError("Market and portfolio state grids do not align.")
    merged = np.concatenate((compact, portfolio_values), axis=2)
    names = (*CONTROL_STATE_FEATURE_NAMES, *portfolio_names)
    if len(set(names)) != len(names):
        raise RuntimeError("Merged control-state feature names are not unique.")
    return merged, names, portfolio_values


def _basis_specification(
    feature_names: Sequence[str],
) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...], tuple[str, ...]]:
    index = {name: pos for pos, name in enumerate(feature_names)}
    nonlinear_names = (
        "account_value_per_initial_premium",
        "guarantee_moneyness_exposure",
    )
    nonlinear = tuple(index[name] for name in nonlinear_names if name in index)
    interaction_names = (
        ("zero_rate_5y", "log_credited_index_proxy"),
        ("guarantee_moneyness_exposure", "previous_cap"),
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
    if ridge <= 0.0:
        # Ordinary least squares (the classic gas-storage regression): an SVD
        # solve that returns the minimum-norm coefficients if the design is
        # rank-deficient.  No shrinkage, so the fit is less biased but more
        # variable than the ridge path below.
        return np.linalg.lstsq(design, targets, rcond=None)[0]
    gram = design.T @ design
    penalty_scale = float(np.trace(gram) / max(gram.shape[0], 1))
    penalty = np.eye(gram.shape[0]) * ridge * max(penalty_scale, 1.0)
    penalty[0, 0] = 0.0
    rhs = design.T @ targets
    try:
        return np.linalg.solve(gram + penalty, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(gram + penalty, rhs, rcond=None)[0]


def _condition_number(design: Array, ridge: float) -> float:
    """Condition number of the actual ridge-regularised normal matrix."""
    try:
        gram = design.T @ design
        penalty_scale = float(np.trace(gram) / max(gram.shape[0], 1))
        penalty = np.eye(gram.shape[0]) * ridge * max(penalty_scale, 1.0)
        penalty[0, 0] = 0.0
        return float(np.linalg.cond(gram + penalty))
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
            # Three observations per regularised basis coefficient, followed
            # by the explicit condition-number gate below, is sufficiently
            # conservative without discarding balanced late-year action cells.
            minimum = max(30, 3 * len(basis_names))
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
            "raw_design_effective_rank": int(np.linalg.matrix_rank(
                full_design[selected]
            )),
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
            "regularized_normal_matrix_condition_number": _condition_number(
                full_design[selected], ridge
            ),
            # Backward-compatible CSV alias; this is the regularised matrix,
            # not the singular raw design used by the invalid predecessor run.
            "design_condition_number": _condition_number(
                full_design[selected], ridge
            ),
        })

    policy = RegressionPolicyYear(
        year=year,
        raw_mean=full_mean,
        raw_scale=full_scale,
        coefficients=coefficients,
        action_caps=ACTION_CAPS.copy(),
        action_value_standard_error=np.asarray([
            float(row["out_of_fold_rmse_new_business_csm_proxy"])
            / np.sqrt(max(int(row["observed_path_count"]), 1))
            for row in diagnostics
        ]),
    )
    # ``basis_names`` is deterministic from the public feature-name list and
    # is stored once in the policy JSON by the caller.
    return predictions, policy, diagnostics


def _csm_from_component_values(components: Array) -> Array:
    """Derive CSM from the nine separately fitted economic components."""
    values = np.asarray(components, dtype=float)
    if values.shape[-1] != len(INSURER_COMPONENT_NAMES):
        raise ValueError("Insurer component tensor has an invalid final axis.")
    return (
        values[..., 0]
        + values[..., 1]
        + values[..., 2]
        + values[..., 3]
        + values[..., 4]
        - values[..., 5]
        - values[..., 6]
        - values[..., 7]
        - values[..., 8]
    )


def _with_derived_csm(components: Array) -> Array:
    values = np.asarray(components, dtype=float)
    return np.concatenate(
        (_csm_from_component_values(values)[..., None], values), axis=-1
    )


def _component_regression_coefficients(component_beta: Array) -> Array:
    beta = np.asarray(component_beta, dtype=float)
    if beta.shape[-1] != len(INSURER_COMPONENT_NAMES):
        raise ValueError("Component coefficients have an invalid output axis.")
    return np.concatenate(
        (_csm_from_component_values(beta)[..., None], beta), axis=-1
    )


def _component_prediction_bounds(targets: Array) -> tuple[Array, Array]:
    """Finite economic envelope used only as a numerical safety rail."""
    values = np.asarray(targets, dtype=float)
    if values.ndim != 2 or values.shape[1] != 10:
        raise ValueError("Leader targets must contain CSM plus nine components.")
    component = values[:, 1:]
    spread = np.std(component, axis=0, ddof=0)
    floor = np.min(component, axis=0) - 5.0 * spread
    ceiling = np.max(component, axis=0) + 5.0 * spread
    for output in NONNEGATIVE_INSURER_COMPONENT_INDICES:
        floor[output - 1] = 0.0
    padding = 1.0e-10 * np.maximum(1.0, np.max(np.abs(component), axis=0))
    ceiling = np.maximum(ceiling + padding, floor + padding)
    lower = _with_derived_csm(floor[None, :])[0]
    upper = _with_derived_csm(ceiling[None, :])[0]
    # CSM is recomputed after component clipping.  Persist its exact finite
    # envelope implied by the nine component boxes for reproducible rollout.
    lower[0] = (
        np.sum(floor[:5]) - np.sum(ceiling[5:])
    )
    upper[0] = (
        np.sum(ceiling[:5]) - np.sum(floor[5:])
    )
    return lower, upper


def _clip_component_predictions(
    values: Array,
    lower: Array,
    upper: Array,
) -> tuple[Array, float]:
    predicted = np.asarray(values, dtype=float)
    bounded = predicted.copy()
    before = bounded[..., 1:].copy()
    bounded[..., 1:] = np.minimum(
        np.maximum(bounded[..., 1:], lower[1:]), upper[1:]
    )
    clipped_fraction = float(np.mean(np.abs(bounded[..., 1:] - before) > 0.0))
    bounded[..., 0] = _csm_from_component_values(bounded[..., 1:])
    return bounded, clipped_fraction


@dataclass
class _CoupledLeaderYearFit:
    deployment: RegressionPolicyYear
    fold_means: Array
    fold_scales: Array
    fold_coefficients: Array
    fold_lower_bounds: Array
    fold_upper_bounds: Array
    stable: bool
    instability_reasons: tuple[str, ...]


def _fit_coupled_leader_year(
    *,
    year: int,
    raw_state: Array,
    targets: Array,
    observed_actions: IntArray,
    fold_ids: IntArray,
    n_folds: int,
    ridge: float,
    feature_names: Sequence[str],
) -> tuple[Array, _CoupledLeaderYearFit, list[dict[str, object]]]:
    """Fit insurer components after the already-computed follower response."""
    n_paths = raw_state.shape[0]
    nonlinear, interactions, basis_names = _basis_specification(feature_names)
    n_basis = len(basis_names)
    n_actions = len(ACTION_CAPS)
    oof = np.full((n_paths, n_actions, 10), np.nan)
    fold_means = np.zeros((n_folds, raw_state.shape[1]))
    fold_scales = np.ones_like(fold_means)
    fold_coefficients = np.zeros((n_folds, n_actions, n_basis, 10))
    fold_lower = np.zeros((n_folds, n_actions, 10))
    fold_upper = np.zeros_like(fold_lower)
    reasons: set[str] = set()
    fold_clip_fractions: dict[tuple[int, int], float] = {}

    for fold in range(n_folds):
        test = fold_ids == fold
        train = ~test
        mean, scale = _raw_scaling(raw_state[train])
        fold_means[fold] = mean
        fold_scales[fold] = scale
        test_design = _design_matrix(
            raw_state[test], mean, scale, nonlinear, interactions
        )
        for action in range(n_actions):
            selected = train & (observed_actions == action)
            minimum = max(30, 3 * n_basis)
            count = int(np.count_nonzero(selected))
            if count < minimum:
                reasons.add(
                    f"year_{year + 1}_cap_{ACTION_CAPS[action]:.6f}_"
                    f"fold_{fold}_support_{count}_below_{minimum}"
                )
                if count == 0:
                    # Exploration validation should prevent this.  Keep a
                    # finite placeholder so the global fixed-cap fallback can
                    # be selected on validation rather than emitting NaNs.
                    component_mean = np.zeros(len(INSURER_COMPONENT_NAMES))
                    beta_components = np.zeros((n_basis, len(component_mean)))
                    beta_components[0] = component_mean
                    bounds_source = np.zeros((1, 10))
                else:
                    component_mean = np.mean(targets[selected, 1:], axis=0)
                    beta_components = np.zeros((n_basis, len(component_mean)))
                    beta_components[0] = component_mean
                    bounds_source = targets[selected]
            else:
                train_design = _design_matrix(
                    raw_state[selected], mean, scale, nonlinear, interactions
                )
                beta_components = _ridge_fit_multioutput(
                    train_design, targets[selected, 1:], ridge
                )
                condition = _condition_number(train_design, ridge)
                if not np.isfinite(condition) or condition > 1.0e10:
                    reasons.add(
                        f"year_{year + 1}_cap_{ACTION_CAPS[action]:.6f}_"
                        f"fold_{fold}_condition_{condition:.6g}"
                    )
                bounds_source = targets[selected]
            beta = _component_regression_coefficients(beta_components)
            lower, upper = _component_prediction_bounds(bounds_source)
            raw_prediction = test_design @ beta
            bounded, clip_fraction = _clip_component_predictions(
                raw_prediction, lower, upper
            )
            if clip_fraction > 0.01:
                reasons.add(
                    f"year_{year + 1}_cap_{ACTION_CAPS[action]:.6f}_"
                    f"fold_{fold}_clip_fraction_{clip_fraction:.6g}"
                )
            oof[test, action] = bounded
            fold_coefficients[fold, action] = beta
            fold_lower[fold, action] = lower
            fold_upper[fold, action] = upper
            fold_clip_fractions[(fold, action)] = clip_fraction

    if not np.all(np.isfinite(oof)):
        reasons.add(f"year_{year + 1}_nonfinite_oof_prediction")
        oof = np.nan_to_num(oof, nan=-1.0e100, posinf=1.0e100, neginf=-1.0e100)

    full_mean, full_scale = _raw_scaling(raw_state)
    full_design = _design_matrix(
        raw_state, full_mean, full_scale, nonlinear, interactions
    )
    coefficients = np.zeros((n_actions, n_basis, 10))
    lower_bounds = np.zeros((n_actions, 10))
    upper_bounds = np.zeros_like(lower_bounds)
    diagnostics: list[dict[str, object]] = []
    action_se = np.zeros(n_actions)
    for action, cap in enumerate(ACTION_CAPS):
        selected = observed_actions == action
        count = int(np.count_nonzero(selected))
        if count < n_basis:
            reasons.add(
                f"year_{year + 1}_cap_{cap:.6f}_full_support_{count}_below_{n_basis}"
            )
            component_beta = np.zeros((n_basis, len(INSURER_COMPONENT_NAMES)))
            if count:
                component_beta[0] = np.mean(targets[selected, 1:], axis=0)
                bounds_source = targets[selected]
            else:
                bounds_source = np.zeros((1, 10))
        else:
            component_beta = _ridge_fit_multioutput(
                full_design[selected], targets[selected, 1:], ridge
            )
            bounds_source = targets[selected]
        beta = _component_regression_coefficients(component_beta)
        coefficients[action] = beta
        lower, upper = _component_prediction_bounds(bounds_source)
        lower_bounds[action] = lower
        upper_bounds[action] = upper
        fitted_raw = full_design[selected] @ beta
        fitted, in_sample_clip = _clip_component_predictions(
            fitted_raw, lower, upper
        )
        observed_oof = oof[selected, action]
        residual = targets[selected, 0] - observed_oof[:, 0]
        rmse = float(np.sqrt(np.mean(residual * residual))) if count else float("inf")
        target_scale = max(
            float(np.std(targets[selected, 0])) if count else 0.0,
            float(np.mean(np.abs(targets[selected, 0]))) if count else 0.0,
            1.0,
        )
        if not np.isfinite(rmse) or rmse > 10.0 * target_scale:
            reasons.add(
                f"year_{year + 1}_cap_{cap:.6f}_oof_rmse_ratio_"
                f"{rmse / target_scale:.6g}"
            )
        action_se[action] = rmse / np.sqrt(max(count, 1))
        target_variance = float(np.var(targets[selected, 0])) if count else 0.0
        oof_r2 = (
            1.0 - rmse * rmse / target_variance
            if target_variance > 1.0e-20 else 1.0
        )
        condition = _condition_number(full_design[selected], ridge) if count else float("inf")
        diagnostics.append({
            "policy_year": year + 1,
            "cap": float(cap),
            "observed_path_count": count,
            "basis_dimension": n_basis,
            "ridge_multiplier": float(ridge),
            "out_of_fold_rmse_new_business_csm_proxy": rmse,
            "out_of_fold_r_squared_new_business_csm_proxy": float(oof_r2),
            "in_sample_component_clip_fraction": in_sample_clip,
            "maximum_fold_component_clip_fraction": max(
                fold_clip_fractions[(fold, action)] for fold in range(n_folds)
            ),
            "regularized_normal_matrix_condition_number": condition,
            "design_condition_number": condition,
            "csm_derived_from_components": True,
        })

    stable = not reasons
    deployment = RegressionPolicyYear(
        year=year,
        raw_mean=full_mean,
        raw_scale=full_scale,
        coefficients=coefficients,
        action_caps=ACTION_CAPS.copy(),
        action_value_standard_error=action_se,
        value_lower_bounds=lower_bounds,
        value_upper_bounds=upper_bounds,
        numerically_stable=stable,
    )
    return oof, _CoupledLeaderYearFit(
        deployment=deployment,
        fold_means=fold_means,
        fold_scales=fold_scales,
        fold_coefficients=fold_coefficients,
        fold_lower_bounds=fold_lower,
        fold_upper_bounds=fold_upper,
        stable=stable,
        instability_reasons=tuple(sorted(reasons)),
    ), diagnostics


def _cross_fitted_leader_action_values(
    fit: _CoupledLeaderYearFit,
    raw_state: Array,
    fold_ids: IntArray,
    feature_names: Sequence[str],
) -> Array:
    """Evaluate a future leader rule without reusing a path's own fold."""
    nonlinear, interactions, _ = _basis_specification(feature_names)
    raw = np.asarray(raw_state, dtype=float)
    out = np.zeros((raw.shape[0], len(ACTION_CAPS), 10))
    for fold in range(fit.fold_coefficients.shape[0]):
        selected = fold_ids == fold
        if not np.any(selected):
            continue
        design = _design_matrix(
            raw[selected],
            fit.fold_means[fold],
            fit.fold_scales[fold],
            nonlinear,
            interactions,
        )
        values = np.einsum(
            "pb,abo->pao", design, fit.fold_coefficients[fold]
        )
        for action in range(len(ACTION_CAPS)):
            values[:, action], _ = _clip_component_predictions(
                values[:, action],
                fit.fold_lower_bounds[fold, action],
                fit.fold_upper_bounds[fold, action],
            )
        out[selected] = values
    if not np.all(np.isfinite(out)):
        raise RuntimeError("Cross-fitted future leader values are non-finite.")
    return out


@dataclass
class _CoupledFollowerYearFit:
    candidate_values: Array
    deployment_regression: _FollowerDeploymentRegression
    stable: bool
    instability_reasons: tuple[str, ...]
    diagnostic: dict[str, object]


def _follower_linear_design(
    raw: Array,
    centre: Array,
    scale: Array,
    active: IntArray,
) -> Array:
    values = np.asarray(raw, dtype=float)
    return np.column_stack((
        np.ones(values.shape[0]),
        (values[:, active] - centre) / scale,
    ))


def _fit_coupled_follower_year(
    *,
    signature: tuple[object, ...],
    policy: PolicySpec,
    record: SignatureDecisionYearPaths,
    actual_caps: Array,
    continuation_target: Array,
    fold_ids: IntArray,
    settings: OptimalBehaviourLSMCSettings,
) -> _CoupledFollowerYearFit:
    """Cross-fit customer Continue/FULL values without insurer objectives."""
    premium = float(policy.net_initial_investment)
    raw_actual = _follower_features_from_core(
        record.pre_cap_core,
        announced_cap=actual_caps,
        duration_years=float(record.policy_year),
        include_previous_cap=True,
    )
    after_actual = _follower_features_from_core(
        record.after_cap_core,
        announced_cap=np.asarray(record.after_cap_core, dtype=float)[:, 8],
        duration_years=float(record.policy_year),
        include_previous_cap=False,
    )
    phase = np.asarray(record.phase, dtype=np.int8)
    inforce = np.asarray(record.pre_cap_core, dtype=float)[:, 12]
    fit_eligible = (
        (phase == Phase.INCOME.value)
        & (inforce > settings.minimum_inforce_weight)
    )
    target = np.column_stack((
        np.maximum(np.asarray(continuation_target, dtype=float), 0.0),
        np.maximum(np.asarray(record.full_withdrawal_value, dtype=float), 0.0),
    ))
    n_paths = raw_actual.shape[0]
    n_folds = settings.n_folds
    predictions = np.zeros((n_paths, len(ACTION_CAPS), 2))
    reasons: set[str] = set()
    fold_rmses: list[float] = []
    raw_scale_all = np.std(raw_actual[fit_eligible], axis=0) \
        if np.any(fit_eligible) else np.zeros(raw_actual.shape[1])
    active_columns = np.flatnonzero(raw_scale_all > 1.0e-10).astype(np.int64)
    basis_dimension = int(active_columns.size + 1)
    minimum = max(60, 2 * basis_dimension)

    for fold in range(n_folds):
        test = fold_ids == fold
        train = (fold_ids != fold) & fit_eligible
        count = int(np.count_nonzero(train))
        if count < minimum or active_columns.size == 0:
            reasons.add(
                f"year_{record.policy_year}_fold_{fold}_support_"
                f"{count}_below_{minimum}"
            )
            mean_target = (
                np.mean(target[train], axis=0) if count else np.zeros(2)
            )
            predictions[test, :, :] = mean_target
            continue
        centre = np.mean(raw_actual[train][:, active_columns], axis=0)
        scale = np.std(raw_actual[train][:, active_columns], axis=0)
        scale = np.where(scale > 1.0e-10, scale, 1.0)
        design = _follower_linear_design(
            raw_actual[train], centre, scale, active_columns
        )
        beta = _ridge_fit_multioutput(
            design, target[train] / premium, settings.ridge
        )
        condition = _condition_number(design, settings.ridge)
        if not np.isfinite(condition) or condition > settings.maximum_condition_number:
            reasons.add(
                f"year_{record.policy_year}_fold_{fold}_condition_{condition:.6g}"
            )
        for action, cap in enumerate(ACTION_CAPS):
            candidate_raw = _follower_features_from_core(
                np.asarray(record.pre_cap_core)[test],
                announced_cap=float(cap),
                duration_years=float(record.policy_year),
                include_previous_cap=True,
            )
            candidate_design = _follower_linear_design(
                candidate_raw, centre, scale, active_columns
            )
            predictions[test, action] = np.maximum(
                candidate_design @ beta * premium, 0.0
            )
        eligible_test = test & fit_eligible
        if np.any(eligible_test):
            actual_index = np.argmin(
                np.abs(
                    actual_caps[eligible_test, None]
                    - ACTION_CAPS[None, :]
                ),
                axis=1,
            )
            observed_prediction = predictions[eligible_test, actual_index]
            fold_rmses.append(float(np.sqrt(np.mean(
                (
                    observed_prediction[:, 0]
                    - target[eligible_test, 0]
                ) ** 2
            ))))

    if not np.all(np.isfinite(predictions)):
        reasons.add(f"year_{record.policy_year}_nonfinite_policyholder_prediction")
        predictions = np.nan_to_num(predictions, nan=0.0, posinf=0.0, neginf=0.0)

    # A broad training-support envelope prevents a continuous-cap regression
    # from manufacturing astronomical optionality between observed grid cells.
    if np.any(fit_eligible):
        ceiling = np.max(target[fit_eligible], axis=0) + 5.0 * np.std(
            target[fit_eligible], axis=0
        )
    else:
        ceiling = np.zeros(2)
    ceiling = np.maximum(ceiling, 0.0)
    before = predictions.copy()
    predictions = np.minimum(predictions, ceiling[None, None, :])
    clip_fraction = float(np.mean(np.abs(before - predictions) > 0.0))
    # Clipping itself is the safety control.  A few extrapolated candidate
    # rows are expected when the same path is evaluated at every cap; reject
    # the entire follower regression only when clipping is pervasive.
    if clip_fraction > 0.20:
        reasons.add(
            f"year_{record.policy_year}_candidate_clip_fraction_{clip_fraction:.6g}"
        )

    # Deployment uses the exact after-cap customer state.  Its target is the
    # same coupled Continue value used above; only the information basis moves
    # from pre-cap-plus-candidate to the realised safe decision context.
    deployment_scale = np.std(after_actual[fit_eligible], axis=0) \
        if np.any(fit_eligible) else np.zeros(after_actual.shape[1])
    deployment_active = np.flatnonzero(
        deployment_scale > 1.0e-10
    ).astype(np.int64)
    deployment_count = int(np.count_nonzero(fit_eligible))
    if deployment_count < max(60, 2 * (deployment_active.size + 1)):
        reasons.add(
            f"year_{record.policy_year}_deployment_support_{deployment_count}"
        )
    if deployment_active.size and deployment_count:
        centre = np.mean(after_actual[fit_eligible][:, deployment_active], axis=0)
        scale = np.std(after_actual[fit_eligible][:, deployment_active], axis=0)
        scale = np.where(scale > 1.0e-10, scale, 1.0)
        design = _follower_linear_design(
            after_actual[fit_eligible], centre, scale, deployment_active
        )
        beta = _ridge_fit_multioutput(
            design,
            target[fit_eligible, :1] / premium,
            settings.ridge,
        )[:, 0]
        condition = _condition_number(design, settings.ridge)
        rank = int(np.linalg.matrix_rank(design))
    else:
        centre = np.zeros(0)
        scale = np.ones(0)
        beta = np.asarray([
            float(np.mean(target[fit_eligible, 0]) / premium)
            if deployment_count else 0.0
        ])
        condition = 1.0
        rank = 1
    rmse = float(np.mean(fold_rmses)) if fold_rmses else float("inf")
    stable = (
        not reasons
        and np.isfinite(condition)
        and condition <= settings.maximum_condition_number
        and rank == beta.size
    )
    regression = _FollowerDeploymentRegression(
        premium=premium,
        active_feature_indices=deployment_active,
        centre=np.asarray(centre, dtype=float),
        scale=np.asarray(scale, dtype=float),
        coefficients=np.asarray(beta, dtype=float),
        condition_number=float(condition),
        matrix_rank=rank,
        oof_rmse_aud=rmse,
        stable=stable,
    )
    signature_text = json.dumps(signature, default=str, separators=(",", ":"))
    diagnostic = {
        "policy_signature": signature_text,
        "policy_signature_fingerprint": hashlib.sha256(
            signature_text.encode("utf-8")
        ).hexdigest(),
        "policy_year": record.policy_year,
        "decision_step": record.decision_step,
        "observations": deployment_count,
        "folds_used": n_folds,
        "feature_count": basis_dimension,
        "matrix_rank": rank,
        "condition_number": float(condition),
        "oof_rmse_aud": rmse,
        "candidate_prediction_clip_fraction": clip_fraction,
        "regression_accepted_for_exercise": stable,
        "fallback_reason": "|".join(sorted(reasons)) if reasons else "",
        "two_value_recursion": True,
    }
    return _CoupledFollowerYearFit(
        candidate_values=predictions,
        deployment_regression=regression,
        stable=stable,
        instability_reasons=tuple(sorted(reasons)),
        diagnostic=diagnostic,
    )


def _constant_first_year_policy(
    year: int,
    raw_state: Array,
    action_values: Array,
    action_standard_errors: Array,
    feature_names: Sequence[str],
    numerically_stable: bool = True,
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
        action_value_standard_error=np.asarray(
            action_standard_errors, dtype=float
        ).copy(),
        numerically_stable=bool(numerically_stable),
        action_deployable_mask=np.ones(len(ACTION_CAPS), dtype=bool),
    )


def _policy_action_values(
    policy: RegressionPolicyYear,
    raw_state: Array,
    feature_names: Sequence[str],
) -> Array:
    """Evaluate all fitted cap actions for one pre-action state matrix."""
    nonlinear, interactions, _ = _basis_specification(feature_names)
    design = _design_matrix(
        np.asarray(raw_state, dtype=float),
        policy.raw_mean,
        policy.raw_scale,
        nonlinear,
        interactions,
    )
    if design.shape[1] != policy.coefficients.shape[1]:
        raise ValueError("Fitted policy basis is incompatible with control states.")
    values = np.einsum("pb,abo->pao", design, policy.coefficients)
    if (
        policy.value_lower_bounds is not None
        or policy.value_upper_bounds is not None
    ):
        if policy.value_lower_bounds is None or policy.value_upper_bounds is None:
            raise ValueError("Fitted value bounds must be supplied as a pair.")
        lower = np.asarray(policy.value_lower_bounds, dtype=float)
        upper = np.asarray(policy.value_upper_bounds, dtype=float)
        expected = (len(policy.action_caps), values.shape[2])
        if lower.shape != expected or upper.shape != expected:
            raise ValueError("Fitted value bounds are shape-inconsistent.")
        values = np.minimum(np.maximum(values, lower[None, :, :]),
                            upper[None, :, :])
        if values.shape[2] == 10:
            values[:, :, 0] = (
                values[:, :, 1]
                + values[:, :, 2]
                + values[:, :, 3]
                + values[:, :, 4]
                + values[:, :, 5]
                - values[:, :, 6]
                - values[:, :, 7]
                - values[:, :, 8]
                - values[:, :, 9]
            )
    if not np.all(np.isfinite(values)):
        raise RuntimeError("Fitted cap-policy values contain non-finite entries.")
    return values


def _screened_policy_actions(
    *,
    policy: RegressionPolicyYear,
    raw_state: Array,
    feature_names: Sequence[str],
    fallback_action: int,
    advantage_screen_multiplier: float,
) -> tuple[IntArray, dict[str, int]]:
    """Choose deployable actions with a conservative local fixed-cap screen.

    Regression standard errors are diagnostics rather than state-conditional
    confidence intervals.  They are used only as a conservative screen here;
    the complete frozen rule is accepted or rejected later on an independent,
    paired monthly-projection validation sample.
    """
    if not np.isfinite(advantage_screen_multiplier) \
            or advantage_screen_multiplier < 0.0:
        raise ValueError(
            "advantage_screen_multiplier must be finite and non-negative."
        )
    values = _policy_action_values(policy, raw_state, feature_names)[:, :, 0]
    n_rows, n_actions = values.shape
    if not 0 <= fallback_action < n_actions:
        raise ValueError("fallback_action is outside the fitted action grid.")
    if policy.action_deployable_mask is None:
        deployable = np.ones(n_actions, dtype=bool)
    else:
        deployable = np.asarray(policy.action_deployable_mask, dtype=bool)
        if deployable.shape != (n_actions,):
            raise ValueError("Fitted action-deployability mask is inconsistent.")

    # The physical fixed-cap fallback remains executable even when its Q fit is
    # unreliable.  In that case the regression cannot support a local
    # comparison, so every state conservatively keeps the fixed cap.
    if not deployable[fallback_action] or not np.any(deployable):
        return (
            np.full(n_rows, fallback_action, dtype=np.int64),
            {
                "fit_mask_fallback_count": n_rows,
                "advantage_screen_fallback_count": 0,
                "adaptive_action_count": 0,
                "masked_action_count": int(np.count_nonzero(~deployable)),
            },
        )

    best = np.asarray(
        _masked_lower_cap_argmax(values, deployable, axis=1), dtype=np.int64
    )
    rows = np.arange(n_rows)
    advantage = values[rows, best] - values[:, fallback_action]
    standard_errors = np.asarray(
        policy.action_value_standard_error, dtype=float
    )
    if standard_errors.shape != (n_actions,):
        raise ValueError("Fitted action standard errors are inconsistent.")
    uncertainty = advantage_screen_multiplier * np.hypot(
        standard_errors[best], standard_errors[fallback_action]
    )
    candidate = best != fallback_action
    passes = candidate & np.isfinite(advantage) & np.isfinite(uncertainty) \
        & (advantage > uncertainty)
    chosen = np.where(passes, best, fallback_action).astype(np.int64)
    return chosen, {
        "fit_mask_fallback_count": 0,
        "advantage_screen_fallback_count": int(np.count_nonzero(
            candidate & ~passes
        )),
        "adaptive_action_count": int(np.count_nonzero(passes)),
        "masked_action_count": int(np.count_nonzero(~deployable)),
    }


def _rollout_cap_policy(
    inputs: ControlStateInputs,
    policy_years: Sequence[RegressionPolicyYear],
    feature_names: Sequence[str],
    fallback_cap: float,
    advantage_screen_multiplier: float = 1.96,
    portfolio_state_paths: Optional[Array] = None,
) -> Array:
    """Generate an implementable pathwise cap schedule without look-ahead.

    Only market and cap/crediting history through the start of the current year
    enter the action.  The resulting complete cap matrix can therefore be fed
    once into the unchanged monthly product projector on independent paths.
    """
    names = tuple(feature_names)
    if names[:len(CONTROL_STATE_FEATURE_NAMES)] != CONTROL_STATE_FEATURE_NAMES:
        raise ValueError(
            "Rollout state must start with the documented adapted market/cap state."
        )
    extra_feature_count = len(names) - len(CONTROL_STATE_FEATURE_NAMES)
    if extra_feature_count:
        if portfolio_state_paths is None:
            raise ValueError(
                "Rich fitted policy requires observable portfolio state paths."
            )
        rich = np.asarray(portfolio_state_paths, dtype=float)
        expected = (inputs.n_paths, inputs.n_years + 1, extra_feature_count)
        if rich.shape != expected or not np.all(np.isfinite(rich)):
            raise ValueError(
                f"portfolio_state_paths must be finite with shape {expected}."
            )
    elif portfolio_state_paths is not None:
        raise ValueError("Compact fitted policy cannot accept extra portfolio states.")
    by_year = {policy.year: policy for policy in policy_years}
    if 0 not in by_year:
        raise ValueError("The fitted policy has no first-year decision.")
    fallback_action = int(np.argmin(np.abs(ACTION_CAPS - fallback_cap)))
    if not np.isclose(ACTION_CAPS[fallback_action], fallback_cap):
        raise ValueError("fallback_cap must be on the admissible action grid.")
    if not np.isfinite(advantage_screen_multiplier) \
            or advantage_screen_multiplier < 0.0:
        raise ValueError(
            "advantage_screen_multiplier must be finite and non-negative."
        )
    caps = np.full(
        (inputs.n_paths, inputs.n_years), fallback_cap, dtype=float
    )
    for year in range(inputs.n_years):
        policy = by_year.get(year)
        if policy is None:
            # No customer exposure remains in the omitted market tail.
            continue
        states = _control_state_paths(inputs, caps)
        if extra_feature_count:
            states = np.concatenate((states, rich), axis=2)
        chosen, _ = _screened_policy_actions(
            policy=policy,
            raw_state=states[:, year, :],
            feature_names=feature_names,
            fallback_action=fallback_action,
            advantage_screen_multiplier=advantage_screen_multiplier,
        )
        caps[:, year] = policy.action_caps[chosen]
    return caps


def _rollout_cap_policy_with_projected_states(
    *,
    inputs: ControlStateInputs,
    policy_years: Sequence[RegressionPolicyYear],
    feature_names: Sequence[str],
    fallback_cap: float,
    scenarios: ScenarioSet,
    product: IndexLinkedLifetimeIncomeProduct,
    model_points: PolicyholderModelPointSet,
    behaviour: BehaviourModel,
    mortality: MortalityTable,
    expenses: ExpenseAssumptions,
    projection_config: ProjectionConfig,
    model_point_log_interval: int,
    surrender_policy_factory: Optional[Callable[[PolicySpec], object]],
    advantage_screen_multiplier: float = 1.96,
    collect_policyholder_by_signature: bool = False,
) -> tuple[Array, PortfolioPathData, dict[str, object]]:
    """Roll out the rich-state policy causally, one frozen prefix at a time.

    The state at the start of year ``y`` depends only on caps ``0..y-1``.
    Therefore a time-prefix portfolio projection with an arbitrary suffix is
    sufficient to freeze cap ``y`` exactly.  This removes the former
    full-horizon fixed-point convergence selector and ensures that validation
    and evaluation execute the same precommitted policy without either sample
    being allowed to choose a fallback.
    """
    caps = np.full((scenarios.n_paths, inputs.n_years), fallback_cap, dtype=float)
    by_year = {policy.year: policy for policy in policy_years}
    fallback_action = int(np.argmin(np.abs(ACTION_CAPS - fallback_cap)))
    if not np.isclose(ACTION_CAPS[fallback_action], fallback_cap):
        raise ValueError("fallback_cap must be on the admissible action grid.")
    expected_names = tuple(feature_names)[len(CONTROL_STATE_FEATURE_NAMES):]
    frozen_action_counts: list[int] = []
    fit_mask_fallback_counts: list[int] = []
    advantage_screen_fallback_counts: list[int] = []
    masked_action_counts: list[int] = []
    prefix_projection_count = 0

    for year in range(inputs.n_years):
        policy = by_year.get(year)
        if policy is None:
            frozen_action_counts.append(0)
            fit_mask_fallback_counts.append(0)
            advantage_screen_fallback_counts.append(0)
            masked_action_counts.append(0)
            continue
        stop_step = max(1, min(year * STEPS_PER_YEAR, scenarios.n_steps))
        prefix_scenarios = _truncate_scenarios(scenarios, stop_step)
        prefix_projected = _aggregate_portfolio_paths(
            scenarios=prefix_scenarios,
            cap_matrix=caps,
            product=product,
            model_points=model_points,
            behaviour=behaviour,
            mortality=mortality,
            expenses=expenses,
            projection_config=projection_config,
            collect_states=False,
            progress_label=f"Causal rich-state rollout year {year + 1}",
            model_point_log_interval=model_point_log_interval,
            surrender_policy_factory=surrender_policy_factory,
            collect_pre_action_states=True,
        )
        prefix_projection_count += 1
        rich, rich_names = _portfolio_state_extension(prefix_projected)
        if rich_names != expected_names:
            raise RuntimeError("Evaluation portfolio state layout differs from training.")
        compact = _control_state_paths(inputs, caps)
        raw = np.concatenate((compact[:, year, :], rich[:, year, :]), axis=1)
        if year == 0:
            selected, screen = _screened_policy_actions(
                policy=policy,
                raw_state=np.mean(raw, axis=0, keepdims=True),
                feature_names=feature_names,
                fallback_action=fallback_action,
                advantage_screen_multiplier=advantage_screen_multiplier,
            )
            chosen = int(selected[0])
            caps[:, year] = policy.action_caps[chosen]
            frozen_action_counts.append(
                inputs.n_paths * int(chosen != fallback_action)
            )
        else:
            chosen, screen = _screened_policy_actions(
                policy=policy,
                raw_state=raw,
                feature_names=feature_names,
                fallback_action=fallback_action,
                advantage_screen_multiplier=advantage_screen_multiplier,
            )
            caps[:, year] = policy.action_caps[chosen]
            frozen_action_counts.append(int(np.count_nonzero(
                chosen != fallback_action
            )))
        multiplier = inputs.n_paths if year == 0 else 1
        fit_mask_fallback_counts.append(
            multiplier * int(screen["fit_mask_fallback_count"])
        )
        advantage_screen_fallback_counts.append(
            multiplier * int(screen["advantage_screen_fallback_count"])
        )
        masked_action_counts.append(int(screen["masked_action_count"]))

    projected = _aggregate_portfolio_paths(
        scenarios=scenarios,
        cap_matrix=caps,
        product=product,
        model_points=model_points,
        behaviour=behaviour,
        mortality=mortality,
        expenses=expenses,
        projection_config=projection_config,
        collect_states=True,
        progress_label="Causal rich-state rollout final projection",
        model_point_log_interval=model_point_log_interval,
        surrender_policy_factory=surrender_policy_factory,
        collect_policyholder_by_signature=collect_policyholder_by_signature,
    )
    # Audit the central causal invariant against the final full-horizon
    # projection.  This catches horizon-dependent projector RNG or state
    # collection immediately instead of silently valuing a different policy.
    final_rich, final_names = _portfolio_state_extension(projected)
    if final_names != expected_names:
        raise RuntimeError("Final portfolio state layout differs from training.")
    final_compact = _control_state_paths(inputs, caps)
    state_action_mismatch_counts: list[int] = []
    for year in range(inputs.n_years):
        policy = by_year.get(year)
        if policy is None:
            state_action_mismatch_counts.append(0)
            continue
        final_raw = np.concatenate(
            (final_compact[:, year, :], final_rich[:, year, :]), axis=1
        )
        if year == 0:
            audited, _ = _screened_policy_actions(
                policy=policy,
                raw_state=np.mean(final_raw, axis=0, keepdims=True),
                feature_names=feature_names,
                fallback_action=fallback_action,
                advantage_screen_multiplier=advantage_screen_multiplier,
            )
            audited_caps = np.full(inputs.n_paths, policy.action_caps[audited[0]])
        else:
            audited, _ = _screened_policy_actions(
                policy=policy,
                raw_state=final_raw,
                feature_names=feature_names,
                fallback_action=fallback_action,
                advantage_screen_multiplier=advantage_screen_multiplier,
            )
            audited_caps = policy.action_caps[audited]
        state_action_mismatch_counts.append(int(np.count_nonzero(
            ~np.isclose(audited_caps, caps[:, year], rtol=0.0, atol=1.0e-15)
        )))
    mismatch_count = int(sum(state_action_mismatch_counts))
    if mismatch_count:
        raise RuntimeError(
            "Causal prefix rollout does not reproduce the policy actions on "
            f"the final state paths ({mismatch_count} path-year mismatches)."
        )
    return caps, projected, {
        "converged": mismatch_count == 0,
        "causal_prefix_projection_count": prefix_projection_count,
        "changed_action_counts": frozen_action_counts,
        "fit_mask_fallback_counts": fit_mask_fallback_counts,
        "advantage_screen_fallback_counts": advantage_screen_fallback_counts,
        "masked_action_counts": masked_action_counts,
        "state_action_mismatch_counts": state_action_mismatch_counts,
        "local_action_advantage_screen_multiplier": (
            advantage_screen_multiplier
        ),
        "method": "audited_exact_causal_prefix_rollout",
        "evaluation_sample_used_for_fallback": False,
    }


def _direct_policy_year_rows(
    cap_matrix: Array,
    inforce_exposure: Array,
    active_policy_years: Sequence[int],
) -> list[dict[str, object]]:
    """Summarise cap choices from the independent direct policy rollout."""
    caps = np.asarray(cap_matrix, dtype=float)
    exposure = np.asarray(inforce_exposure, dtype=float)
    rows: list[dict[str, object]] = []
    for policy_year in active_policy_years:
        year = int(policy_year) - 1
        selected = caps[:, year]
        quantiles = np.quantile(selected, (0.10, 0.50, 0.90))
        mean_cap = float(np.mean(selected))
        mean_inforce = float(np.mean(exposure[:, year]))
        for action, cap in enumerate(ACTION_CAPS):
            rows.append({
                "policy_year": int(policy_year),
                "cap": float(cap),
                "selected_fraction": float(np.mean(np.isclose(selected, cap))),
                "mean_selected_cap": mean_cap,
                "p10_selected_cap": float(quantiles[0]),
                "median_selected_cap": float(quantiles[1]),
                "p90_selected_cap": float(quantiles[2]),
                "economically_active": True,
                "mean_inforce_exposure": mean_inforce,
                "source": "independent_direct_policy_rollout",
                "action_index": action,
            })
    return rows


def _policyholder_exercise_rows(
    *,
    label: str,
    cap_matrix: Array,
    projected: PortfolioPathData,
    active_policy_years: Sequence[int],
    path_slice: slice = slice(None),
    cap_values: Sequence[float] = ACTION_CAPS,
) -> list[dict[str, object]]:
    """Portfolio-weighted Full-Withdrawal exposure by year and chosen cap."""
    caps = np.asarray(cap_matrix, dtype=float)[path_slice]
    events = np.asarray(projected.lapse_events, dtype=float)[path_slice]
    if caps.shape != events.shape:
        raise ValueError("Cap and annual exercise matrices must align.")
    if projected.pre_action_states is None:
        raise ValueError("Exercise reporting requires pre-action exposures.")
    state_index = {
        name: position
        for position, name in enumerate(
            projected.pre_action_state_feature_names
        )
    }
    income_exposure = projected.pre_action_states[
        path_slice, :-1, state_index["income_exposure"]
    ]
    rows: list[dict[str, object]] = []
    for policy_year in active_policy_years:
        year = int(policy_year) - 1
        for cap in cap_values:
            selected = (
                np.isposinf(caps[:, year])
                if np.isposinf(cap)
                else np.isclose(caps[:, year], cap)
            )
            count = int(np.count_nonzero(selected))
            selected_exit_mass = float(np.sum(events[selected, year]))
            selected_income_exposure = float(np.sum(
                income_exposure[selected, year]
            ))
            rows.append({
                "policy": label,
                "policy_year": int(policy_year),
                "cap": float(cap),
                "cap_percent": 100.0 * float(cap),
                "selected_market_path_count": count,
                "selected_market_path_fraction": float(np.mean(selected)),
                "mean_full_withdrawal_probability_on_selected_paths": (
                    float(np.mean(events[selected, year])) if count else 0.0
                ),
                "mean_full_withdrawal_probability_all_paths": float(
                    np.mean(np.where(selected, events[:, year], 0.0))
                ),
                "full_withdrawal_exercise_rate_over_income_exposure": (
                    selected_exit_mass / selected_income_exposure
                    if selected_income_exposure > 0.0 else 0.0
                ),
                "selected_full_withdrawal_exit_mass": selected_exit_mass,
                "selected_pre_action_income_exposure": (
                    selected_income_exposure
                ),
                "weighting": (
                    "contract_weight and spouse-branch probability applied "
                    "once inside the pathwise portfolio projection"
                ),
            })
    return rows


def _policyholder_regression_rows(
    fit_sets: Mapping[str, PolicyholderFitSet],
) -> list[dict[str, object]]:
    """Flatten follower-value diagnostics without mixing insurer regressions."""
    rows: list[dict[str, object]] = []
    for fit_label, fit_set in fit_sets.items():
        for signature, fit in fit_set.fits.items():
            signature_text = json.dumps(signature, default=str, separators=(",", ":"))
            signature_fingerprint = hashlib.sha256(
                signature_text.encode("utf-8")
            ).hexdigest()
            diagnostics = tuple(fit.diagnostics)
            if not diagnostics:
                rows.append({
                    "fit_label": fit_label,
                    "policy_signature_fingerprint": signature_fingerprint,
                    "policy_signature": signature_text,
                    "policy_year": None,
                    "decision_step": None,
                    "observations": fit.training_path_count,
                    "folds_used": None,
                    "feature_count": None,
                    "matrix_rank": None,
                    "condition_number": None,
                    "oof_rmse_aud": None,
                    "oof_r_squared": None,
                    "mean_immediate_value_aud": None,
                    "mean_continuation_target_aud": None,
                    "training_exercise_rate": 0.0,
                    "regression_accepted_for_exercise": False,
                    "training_policyholder_value_aud": (
                        fit.training_policyholder_value_aud
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
                    "training_scenario_fingerprint": (
                        fit.training_scenario_fingerprint
                    ),
                    "training_cap_schedule_fingerprint": (
                        fit_set.cap_schedule_fingerprint
                    ),
                })
                continue
            for diagnostic in diagnostics:
                row = diagnostic.as_dict()
                row.update({
                    "fit_label": fit_label,
                    "policy_signature_fingerprint": signature_fingerprint,
                    "policy_signature": signature_text,
                    "training_policyholder_value_aud": (
                        fit.training_policyholder_value_aud
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
                    "training_scenario_fingerprint": (
                        fit.training_scenario_fingerprint
                    ),
                    "training_cap_schedule_fingerprint": (
                        fit_set.cap_schedule_fingerprint
                    ),
                })
                rows.append(row)
    return rows


def _counterfactual_next_leader_state(
    *,
    inputs: ControlStateInputs,
    current_state: Array,
    year: int,
    current_cap: Array,
    next_portfolio_state: Array,
) -> Array:
    """Advance only observable market/cap history plus supplied exposures."""
    state = np.asarray(current_state, dtype=float)
    cap = np.asarray(current_cap, dtype=float)
    portfolio = np.asarray(next_portfolio_state, dtype=float)
    if state.shape[0] != inputs.n_paths or cap.shape != (inputs.n_paths,):
        raise ValueError("Counterfactual leader transition has invalid path shape.")
    if portfolio.shape != (
        inputs.n_paths, len(PORTFOLIO_CONTROL_STATE_FEATURE_NAMES)
    ):
        raise ValueError("Counterfactual portfolio state has an invalid shape.")
    if year < 0 or year >= inputs.n_years:
        raise ValueError("Counterfactual leader transition year is invalid.")
    compact = np.zeros((inputs.n_paths, len(CONTROL_STATE_FEATURE_NAMES)))
    compact[:, :5] = inputs.market_features[:, year + 1, :]
    reference_return = inputs.annual_reference_fund_return[:, year]
    positive_return = np.maximum(reference_return, 0.0)
    credited = np.minimum(positive_return, cap)
    excess = np.maximum(positive_return - cap, 0.0)
    compact[:, 5] = state[:, 5] + np.log1p(credited)
    compact[:, 6] = cap
    compact[:, 7] = (state[:, 7] * year + cap) / (year + 1)
    compact[:, 8] = (state[:, 8] * year + excess) / (year + 1)
    compact[:, 9] = np.maximum(
        np.log1p(reference_return) - np.log1p(credited), 0.0
    )
    out = np.concatenate((compact, portfolio), axis=1)
    if not np.all(np.isfinite(out)):
        raise RuntimeError("Counterfactual next leader state is non-finite.")
    return out


def _portfolio_continue_component_tensor(data: PortfolioPathData) -> Array:
    components = np.stack((
        data.fees_product,
        data.fees_lip,
        data.crediting_margin,
        data.mva_retained,
        data.aps_retained,
        data.guarantee_claims,
        data.other_insurer_funded_benefits,
        data.expenses,
        data.hedge_costs,
    ), axis=2)
    return _with_derived_csm(components)


def _coupled_backward_induction_rowwise_crossfit_legacy(
    data: PortfolioPathData,
    action_indices: IntArray,
    *,
    control_inputs: ControlStateInputs,
    portfolio_state_extension: Array,
    folds: int,
    ridge: float,
    seed: int,
    follower_settings: OptimalBehaviourLSMCSettings,
    scenario_fingerprint: str,
    cap_schedule_fingerprint: str,
) -> BackwardResult:
    """Joint two-value fitted Stackelberg recursion.

    At every year the customer continuation value is fitted first for every
    PolicySpec signature.  The corresponding CONTINUE/FULL response changes
    the insurer reward and the next aggregate exposure state.  Only then is
    the insurer action value fitted and the cap selected.  Future customer
    targets evaluate the already-fitted future leader rule, never the
    exploratory control law.

    A Policyholder is treated as non-atomic with respect to the portfolio
    state: a single customer's deviation does not move the future common cap,
    while the population best-response mass does.  The response/exposure map
    is iterated vectorially; a cycle falls back to Continue for that year.
    """
    if data.raw_states is None or data.inforce_exposure is None:
        raise ValueError("Coupled backward induction requires rich state paths.")
    if not data.signature_control_paths:
        raise ValueError("Coupled backward induction lacks signature primitives.")
    n_paths, n_years = data.new_business_csm_proxy.shape
    if action_indices.shape != (n_paths, n_years):
        raise ValueError("Coupled action indices are shape-inconsistent.")
    if portfolio_state_extension.shape != (
        n_paths,
        n_years + 1,
        len(PORTFOLIO_CONTROL_STATE_FEATURE_NAMES),
    ):
        raise ValueError("Coupled portfolio-state extension is shape-inconsistent.")
    feature_names = data.state_feature_names
    if tuple(feature_names) != (
        *CONTROL_STATE_FEATURE_NAMES,
        *PORTFOLIO_CONTROL_STATE_FEATURE_NAMES,
    ):
        raise ValueError("Coupled recursion requires the documented 20-state layout.")

    rng = np.random.default_rng(seed)
    fold_ids = np.empty(n_paths, dtype=np.int64)
    for action in range(len(ACTION_CAPS)):
        rows = np.flatnonzero(action_indices[:, 0] == action)
        assigned = np.resize(np.arange(folds, dtype=np.int64), len(rows))
        fold_ids[rows] = rng.permutation(assigned)
    if set(np.unique(fold_ids)) != set(range(folds)):
        raise RuntimeError("Complete-path cross-fitting did not populate every fold.")

    continue_components = _portfolio_continue_component_tensor(data)
    future_leader: _CoupledLeaderYearFit | None = None
    future_follower_values: dict[tuple[object, ...], Array] = {}
    follower_deployment_targets: dict[
        tuple[object, ...], dict[int, Array]
    ] = {signature: {} for signature in data.signature_control_paths}
    follower_rows: list[dict[str, object]] = []
    leader_rows: list[dict[str, object]] = []
    policy_year_rows: list[dict[str, object]] = []
    first_year_action_rows: list[dict[str, object]] = []
    policy_years: list[RegressionPolicyYear] = []
    active_years: list[int] = []
    numerical_reasons: set[str] = set()
    first_cap = float("nan")
    first_outputs = np.zeros(10)
    first_se = float("nan")

    LOGGER.info(
        "Coupled backward induction | years=%d | actions=%d | paths=%d | "
        "signatures=%d | folds=%d",
        n_years,
        len(ACTION_CAPS),
        n_paths,
        len(data.signature_control_paths),
        folds,
    )
    rows_index = np.arange(n_paths)
    for year in range(n_years - 1, -1, -1):
        exposure = np.asarray(data.inforce_exposure[:, year], dtype=float)
        economically_active = bool(np.any(exposure > 0.0))
        if not economically_active:
            continue
        active_years.append(year + 1)
        if year == n_years - 1 or year == 0 or (year + 1) % 5 == 0:
            LOGGER.info(
                "Coupled backward induction | processing policy year %d/%d",
                year + 1,
                n_years,
            )

        records = {
            signature: paths.decision_years[year]
            for signature, paths in data.signature_control_paths.items()
            if year in paths.decision_years
        }
        responses = {
            signature: np.zeros(n_paths, dtype=bool)
            for signature in records
        }
        final_fits: dict[tuple[object, ...], _CoupledFollowerYearFit] = {}
        final_targets: dict[tuple[object, ...], Array] = {}
        response_converged = True
        previous_future_action: Array | None = None
        maximum_response_iterations = 4 if records else 1

        for response_iteration in range(maximum_response_iterations):
            next_portfolio = np.array(
                portfolio_state_extension[:, year + 1, :], copy=True
            )
            for signature, response in responses.items():
                contribution = np.asarray(
                    records[signature].next_portfolio_exposure_contribution,
                    dtype=float,
                )
                next_portfolio[:, 1:] -= response[:, None] * contribution
            next_portfolio[:, 1:] = np.maximum(next_portfolio[:, 1:], 0.0)
            next_state = _counterfactual_next_leader_state(
                inputs=control_inputs,
                current_state=data.raw_states[:, year, :],
                year=year,
                current_cap=ACTION_CAPS[action_indices[:, year]],
                next_portfolio_state=next_portfolio,
            )
            if future_leader is None:
                future_action = np.zeros(n_paths, dtype=np.int64)
            else:
                future_values = _cross_fitted_leader_action_values(
                    future_leader, next_state, fold_ids, feature_names
                )
                future_action = _lower_cap_argmax(
                    future_values[:, :, 0], axis=1
                )

            new_responses: dict[tuple[object, ...], Array] = {}
            current_follower_values: dict[tuple[object, ...], Array] = {}
            iteration_fits: dict[
                tuple[object, ...], _CoupledFollowerYearFit
            ] = {}
            iteration_targets: dict[tuple[object, ...], Array] = {}
            for signature, record in records.items():
                next_u_grid = future_follower_values.get(signature)
                if next_u_grid is None:
                    future_u = np.zeros(n_paths)
                else:
                    future_u = next_u_grid[rows_index, future_action]
                numerator = (
                    np.asarray(
                        record.continue_policyholder_interval_pv, dtype=float
                    )
                    + np.asarray(
                        record.next_decision_discount_inforce, dtype=float
                    ) * future_u
                )
                denominator = np.asarray(
                    record.decision_discount_inforce, dtype=float
                )
                continuation_target = np.divide(
                    numerator,
                    np.maximum(denominator, 1.0e-300),
                    out=np.zeros_like(numerator),
                    where=denominator > 1.0e-300,
                )
                paths = data.signature_control_paths[signature]
                fit = _fit_coupled_follower_year(
                    signature=signature,
                    policy=paths.policy,
                    record=record,
                    actual_caps=ACTION_CAPS[action_indices[:, year]],
                    continuation_target=continuation_target,
                    fold_ids=fold_ids,
                    settings=follower_settings,
                )
                candidate = fit.candidate_values
                structural_eligible = (
                    (np.asarray(record.phase) == Phase.INCOME.value)[:, None]
                    & (~np.asarray(record.just_elected, dtype=bool))[:, None]
                    & (
                        np.asarray(record.pre_cap_core, dtype=float)[:, 12]
                        > follower_settings.minimum_inforce_weight
                    )[:, None]
                )
                buffer = (
                    follower_settings.exercise_tolerance_aud
                    + follower_settings.exercise_buffer_rmse_multiplier
                    * fit.deployment_regression.oof_rmse_aud
                )
                response_grid = structural_eligible & (
                    candidate[:, :, 1] > candidate[:, :, 0] + buffer
                )
                if not fit.stable:
                    response_grid[:] = False
                response_observed = response_grid[
                    rows_index, action_indices[:, year]
                ]
                # On the actually observed cap the monthly projector's exact
                # gate is authoritative, including Election and zero-SV rules.
                response_observed &= np.asarray(
                    record.full_withdrawal_eligible, dtype=bool
                )
                new_responses[signature] = response_observed
                current_follower_values[signature] = np.where(
                    response_grid,
                    candidate[:, :, 1],
                    candidate[:, :, 0],
                )
                iteration_fits[signature] = fit
                iteration_targets[signature] = continuation_target

            same_response = all(
                np.array_equal(new_responses[key], responses[key])
                for key in responses
            )
            same_future_action = (
                previous_future_action is not None
                and np.array_equal(future_action, previous_future_action)
            )
            responses = new_responses
            final_fits = iteration_fits
            final_targets = iteration_targets
            if same_response and (future_leader is None or same_future_action):
                future_follower_candidate = current_follower_values
                break
            previous_future_action = future_action.copy()
            future_follower_candidate = current_follower_values
        else:
            response_converged = False

        if records and not response_converged:
            reason = f"policy_year_{year + 1}_follower_exposure_fixed_point"
            numerical_reasons.add(reason)
            LOGGER.warning(
                "Coupled follower/exposure map did not converge in year %d; "
                "using the conservative Continue response for that year.",
                year + 1,
            )
            # Re-evaluate the value functions on the state transition induced
            # by the deployed all-Continue population.  Reusing the final
            # oscillating iterate here would hand the preceding year a value
            # from a response state that is never deployed.
            continue_next_portfolio = np.array(
                portfolio_state_extension[:, year + 1, :], copy=True
            )
            continue_next_state = _counterfactual_next_leader_state(
                inputs=control_inputs,
                current_state=data.raw_states[:, year, :],
                year=year,
                current_cap=ACTION_CAPS[action_indices[:, year]],
                next_portfolio_state=continue_next_portfolio,
            )
            if future_leader is None:
                continue_future_action = np.zeros(n_paths, dtype=np.int64)
            else:
                continue_future_values = _cross_fitted_leader_action_values(
                    future_leader,
                    continue_next_state,
                    fold_ids,
                    feature_names,
                )
                continue_future_action = _lower_cap_argmax(
                    continue_future_values[:, :, 0], axis=1
                )
            fallback_fits: dict[
                tuple[object, ...], _CoupledFollowerYearFit
            ] = {}
            fallback_targets: dict[tuple[object, ...], Array] = {}
            fallback_values: dict[tuple[object, ...], Array] = {}
            for signature, record in records.items():
                next_u_grid = future_follower_values.get(signature)
                future_u = (
                    np.zeros(n_paths)
                    if next_u_grid is None
                    else next_u_grid[rows_index, continue_future_action]
                )
                numerator = (
                    np.asarray(
                        record.continue_policyholder_interval_pv,
                        dtype=float,
                    )
                    + np.asarray(
                        record.next_decision_discount_inforce,
                        dtype=float,
                    ) * future_u
                )
                denominator = np.asarray(
                    record.decision_discount_inforce, dtype=float
                )
                continuation_target = np.divide(
                    numerator,
                    np.maximum(denominator, 1.0e-300),
                    out=np.zeros_like(numerator),
                    where=denominator > 1.0e-300,
                )
                fit = _fit_coupled_follower_year(
                    signature=signature,
                    policy=data.signature_control_paths[signature].policy,
                    record=record,
                    actual_caps=ACTION_CAPS[action_indices[:, year]],
                    continuation_target=continuation_target,
                    fold_ids=fold_ids,
                    settings=follower_settings,
                )
                responses[signature] = np.zeros(n_paths, dtype=bool)
                fallback_fits[signature] = fit
                fallback_targets[signature] = continuation_target
                fallback_values[signature] = fit.candidate_values[:, :, 0]
            final_fits = fallback_fits
            final_targets = fallback_targets
            future_follower_candidate = fallback_values

        # Freeze only stable final customer regressions.  An omitted year is
        # operationally Continue in the context-aware forward policy.
        for signature, fit in final_fits.items():
            diagnostic = dict(fit.diagnostic)
            diagnostic["response_fixed_point_converged"] = response_converged
            observed_response = responses[signature]
            diagnostic["training_exercise_rate"] = float(
                np.mean(observed_response)
            )
            follower_rows.append(diagnostic)
            if fit.stable and response_converged:
                step = records[signature].decision_step
                follower_deployment_targets[signature][step] = np.asarray(
                    final_targets[signature], dtype=float
                ).copy()
            elif fit.instability_reasons:
                signature_key = hashlib.sha256(
                    json.dumps(
                        signature, default=str, separators=(",", ":")
                    ).encode("utf-8")
                ).hexdigest()
                for reason in fit.instability_reasons:
                    numerical_reasons.add(
                        f"policyholder::{signature_key}::{reason}"
                    )
        future_follower_values = dict(future_follower_candidate)

        next_portfolio = np.array(
            portfolio_state_extension[:, year + 1, :], copy=True
        )
        immediate = np.array(continue_components[:, year, :], copy=True)
        for signature, response in responses.items():
            record = records[signature]
            delta = np.asarray(
                record.insurer_full_minus_continue_components, dtype=float
            )
            immediate[:, 1:] += response[:, None] * delta
            contribution = np.asarray(
                record.next_portfolio_exposure_contribution, dtype=float
            )
            next_portfolio[:, 1:] -= response[:, None] * contribution
        next_portfolio[:, 1:] = np.maximum(next_portfolio[:, 1:], 0.0)
        immediate[:, 0] = _csm_from_component_values(immediate[:, 1:])
        next_state = _counterfactual_next_leader_state(
            inputs=control_inputs,
            current_state=data.raw_states[:, year, :],
            year=year,
            current_cap=ACTION_CAPS[action_indices[:, year]],
            next_portfolio_state=next_portfolio,
        )
        if future_leader is None:
            future_selected = np.zeros_like(immediate)
        else:
            future_values = _cross_fitted_leader_action_values(
                future_leader, next_state, fold_ids, feature_names
            )
            future_action = _lower_cap_argmax(
                future_values[:, :, 0], axis=1
            )
            future_selected = future_values[rows_index, future_action]
        targets = immediate + future_selected
        targets[:, 0] = _csm_from_component_values(targets[:, 1:])

        oof, leader_fit, diagnostics = _fit_coupled_leader_year(
            year=year,
            raw_state=data.raw_states[:, year, :],
            targets=targets,
            observed_actions=action_indices[:, year],
            fold_ids=fold_ids,
            n_folds=folds,
            ridge=ridge,
            feature_names=feature_names,
        )
        leader_rows.extend(diagnostics)
        numerical_reasons.update(
            f"insurer::{reason}" for reason in leader_fit.instability_reasons
        )
        if year == 0:
            action_values = np.mean(oof, axis=0)
            action_se = np.asarray([
                _standard_error(oof[:, action, 0])
                for action in range(len(ACTION_CAPS))
            ])
            chosen = int(_lower_cap_argmax(action_values[:, 0]))
            first_cap = float(ACTION_CAPS[chosen])
            first_outputs = action_values[chosen]
            first_se = float(action_se[chosen])
            constant = _constant_first_year_policy(
                year=0,
                raw_state=data.raw_states[:, 0, :],
                action_values=action_values,
                action_standard_errors=action_se,
                feature_names=feature_names,
                numerically_stable=leader_fit.stable,
            )
            policy_years.append(constant)
            for action, cap in enumerate(ACTION_CAPS):
                first_year_action_rows.append({
                    "cap": float(cap),
                    "cap_percent": 100.0 * float(cap),
                    "selection_estimated_q_new_business_csm_proxy": float(
                        action_values[action, 0]
                    ),
                    "selection_standard_error_new_business_csm_proxy": float(
                        action_se[action]
                    ),
                    "holdout_estimated_q_new_business_csm_proxy": float(
                        action_values[action, 0]
                    ),
                    "holdout_estimated_q_fees_product": float(
                        action_values[action, 1]
                    ),
                    "holdout_estimated_q_fees_lip": float(
                        action_values[action, 2]
                    ),
                    "holdout_estimated_q_crediting_margin": float(
                        action_values[action, 3]
                    ),
                    "holdout_estimated_q_mva_retained": float(
                        action_values[action, 4]
                    ),
                    "holdout_estimated_q_aps_retained": float(
                        action_values[action, 5]
                    ),
                    "holdout_estimated_q_guarantee_claims": float(
                        action_values[action, 6]
                    ),
                    "holdout_estimated_q_other_insurer_funded_benefits": float(
                        action_values[action, 7]
                    ),
                    "holdout_estimated_q_expenses": float(
                        action_values[action, 8]
                    ),
                    "holdout_estimated_q_hedge_costs": float(
                        action_values[action, 9]
                    ),
                    "holdout_standard_error_new_business_csm_proxy": float(
                        action_se[action]
                    ),
                    "selection_path_count": n_paths,
                    "holdout_path_count": n_paths,
                    "observed_control_action_path_count": int(np.sum(
                        action_indices[:, 0] == action
                    )),
                    "selection_value_semantics": (
                        "complete-path out-of-fold fitted action-value mean"
                    ),
                    "holdout_value_semantics": (
                        "legacy output column; identical complete-path OOF "
                        "fitted action-value mean, not final evaluation CSM"
                    ),
                    "economically_active": True,
                    "is_optimal_first_year_cap": action == chosen,
                    "two_value_stackelberg_recursion": True,
                })
            policy_year_rows.append({
                "policy_year": 1,
                "cap": first_cap,
                "selected_fraction": 1.0,
                "mean_selected_cap": first_cap,
                "p10_selected_cap": first_cap,
                "median_selected_cap": first_cap,
                "p90_selected_cap": first_cap,
                "economically_active": True,
                "mean_inforce_exposure": float(np.mean(exposure)),
                "follower_response_fixed_point_converged": response_converged,
            })
        else:
            chosen = _lower_cap_argmax(oof[:, :, 0], axis=1)
            selected_caps = ACTION_CAPS[chosen]
            mean_cap = float(np.mean(selected_caps))
            quantiles = np.quantile(selected_caps, (0.10, 0.50, 0.90))
            for action, cap in enumerate(ACTION_CAPS):
                fraction = float(np.mean(chosen == action))
                diagnostics[action]["selected_fraction_cross_fitted"] = fraction
                policy_year_rows.append({
                    "policy_year": year + 1,
                    "cap": float(cap),
                    "selected_fraction": fraction,
                    "mean_selected_cap": mean_cap,
                    "p10_selected_cap": float(quantiles[0]),
                    "median_selected_cap": float(quantiles[1]),
                    "p90_selected_cap": float(quantiles[2]),
                    "economically_active": True,
                    "mean_inforce_exposure": float(np.mean(exposure)),
                    "follower_response_fixed_point_converged": (
                        response_converged
                    ),
                })
            policy_years.append(leader_fit.deployment)
        future_leader = leader_fit

    policy_years.sort(key=lambda item: item.year)
    active_years.sort()
    if not active_years or active_years[0] != 1:
        raise RuntimeError("The coupled portfolio has no active first policy year.")
    expected = list(range(1, active_years[-1] + 1))
    if active_years != expected:
        raise RuntimeError("Coupled economic policy horizon is not contiguous.")
    policies: dict[tuple[object, ...], object] = {}
    signature_fallbacks: set[tuple[object, ...]] = set()
    signature_fallback_steps: dict[
        tuple[object, ...], tuple[int, ...]
    ] = {}
    for signature, paths in data.signature_control_paths.items():
        targets_by_step = follower_deployment_targets[signature]
        features_by_step: dict[int, Array] = {}
        fold_paths_by_step: dict[int, IntArray] = {}
        for year, record in paths.decision_years.items():
            step = record.decision_step
            if step not in targets_by_step:
                continue
            eligible = (
                (np.asarray(record.phase) == Phase.INCOME.value)
                & (
                    np.asarray(record.pre_cap_core, dtype=float)[:, 12]
                    > follower_settings.minimum_inforce_weight
                )
            )
            features_by_step[step] = _follower_features_from_core(
                record.after_cap_core,
                announced_cap=np.asarray(record.after_cap_core, dtype=float)[:, 8],
                duration_years=float(year),
                include_previous_cap=False,
            )[eligible]
            targets_by_step[step] = np.asarray(
                targets_by_step[step], dtype=float
            )[eligible]
            fold_paths_by_step[step] = fold_ids[eligible].copy()
        continuation_fit = fit_surrender_continuation_policy(
            features_by_step,
            targets_by_step,
            premium=float(paths.policy.net_initial_investment),
            settings=follower_settings,
            fold_ids_by_step=fold_paths_by_step,
        )
        policies[signature] = continuation_fit.policy
        active_year_indices = {policy_year - 1 for policy_year in active_years}
        expected_steps = {
            record.decision_step
            for year, record in paths.decision_years.items()
            if year in active_year_indices
        }
        deployed_steps = set(continuation_fit.policy.regressions)
        signature_fallback_steps[signature] = tuple(sorted(
            expected_steps - deployed_steps
        ))
        if features_by_step and len(continuation_fit.fallback_steps) == len(
            features_by_step
        ):
            signature_fallbacks.add(signature)
        signature_text = json.dumps(
            signature, default=str, separators=(",", ":")
        )
        signature_fingerprint = hashlib.sha256(
            signature_text.encode("utf-8")
        ).hexdigest()
        for diagnostic in continuation_fit.diagnostics:
            row = diagnostic.as_dict()
            row.update({
                "policy_signature": signature_text,
                "policy_signature_fingerprint": signature_fingerprint,
                "value_function": "coupled_after_cap_deployment_continuation",
                "two_value_recursion": True,
            })
            follower_rows.append(row)
    fit_set = CoupledPolicyholderFitSet(
        policies=policies,
        scenario_fingerprint=scenario_fingerprint,
        cap_schedule_fingerprint=cap_schedule_fingerprint,
        fallback_signatures=signature_fallbacks,
        fallback_steps_by_signature=signature_fallback_steps,
    )
    component_csm = _csm_from_component_values(first_outputs[1:][None, :])[0]
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
        standard_error_new_business_csm_proxy=first_se,
        first_year_action_rows=first_year_action_rows,
        policy_year_rows=sorted(
            policy_year_rows,
            key=lambda row: (int(row["policy_year"]), float(row["cap"])),
        ),
        regression_rows=sorted(
            leader_rows,
            key=lambda row: (int(row["policy_year"]), float(row["cap"])),
        ),
        policy_years=policy_years,
        reconciliation_gap=float(first_outputs[0] - component_csm),
        economically_active_policy_years=tuple(active_years),
        inactive_market_tail_year_count=n_years - len(active_years),
        numerically_stable=not any(
            reason.startswith("insurer::") for reason in numerical_reasons
        ),
        numerical_fallback_reasons=tuple(sorted(numerical_reasons)),
        follower_regression_rows=follower_rows,
        follower_fit_set=fit_set,
    )


@dataclass
class _OuterFollowerFit:
    """One outer-chain customer Q fit evaluated on every path and cap."""

    candidate_values: Array
    after_cap_continuation: Array
    after_cap_regression: object | None
    eligible: NDArray[np.bool_]
    stable: bool
    instability_reasons: tuple[str, ...]
    condition_number: float
    matrix_rank: int
    feature_count: int
    training_rmse_aud: float
    candidate_clip_fraction: float


@dataclass
class _FollowerChainYearSolution:
    responses: dict[tuple[object, ...], NDArray[np.bool_]]
    fits: dict[tuple[object, ...], _OuterFollowerFit]
    continuation_targets: dict[tuple[object, ...], Array]
    policyholder_values: dict[tuple[object, ...], Array]
    next_state: Array
    future_action: IntArray
    converged: bool


@dataclass
class _OuterLeaderFit:
    policy: RegressionPolicyYear
    predictions: Array
    instability_reasons: tuple[str, ...]
    action_deployable_mask: NDArray[np.bool_]
    action_instability_reasons: tuple[tuple[str, ...], ...]
    conditions: Array
    clip_fractions: Array
    counterfactual_clip_fractions: Array
    observed_counts: IntArray


def _fit_outer_follower_model(
    *,
    policy: PolicySpec,
    record: SignatureDecisionYearPaths,
    actual_caps: Array,
    continuation_target: Array,
    train_mask: NDArray[np.bool_],
    settings: OptimalBehaviourLSMCSettings,
    buffer_rmse_override: float | None = None,
) -> _OuterFollowerFit:
    """Fit the canonical customer basis on one explicit outer training set.

    The pre-cap models supply candidate-cap Q values.  The after-cap model is
    the exact same canonical regression object stored in the forward
    :class:`OptimalSurrenderPolicy`; its observed-cap response therefore needs
    no later refit.  FULL value remains a separate customer target because the
    new cap can affect the same-timestamp DVA restart and surrender value.
    """
    n_paths = actual_caps.size
    premium = float(policy.net_initial_investment)
    pre_actual = _follower_features_from_core(
        record.pre_cap_core,
        announced_cap=actual_caps,
        duration_years=float(record.policy_year),
        include_previous_cap=False,
    )
    after_actual = _follower_features_from_core(
        record.after_cap_core,
        announced_cap=np.asarray(record.after_cap_core, dtype=float)[:, 8],
        duration_years=float(record.policy_year),
        include_previous_cap=False,
    )
    continuation = np.maximum(
        np.asarray(continuation_target, dtype=float), 0.0
    )
    full_value = np.maximum(
        np.asarray(record.full_withdrawal_value, dtype=float), 0.0
    )
    inforce = np.asarray(record.after_cap_core, dtype=float)[:, 12]
    eligible = (
        (np.asarray(record.phase) == Phase.INCOME.value)
        & (inforce > settings.minimum_inforce_weight)
    )
    selected = np.asarray(train_mask, dtype=bool) & eligible
    feature_count = len(POLICYHOLDER_FEATURE_NAMES) + 1
    minimum = 2 * feature_count
    reasons: set[str] = set()
    count = int(np.count_nonzero(selected))
    if count < minimum:
        reasons.add(
            f"support_{count}_below_{minimum}"
        )
        mean_continue = float(np.mean(continuation[selected])) if count else 0.0
        mean_full = float(np.mean(full_value[selected])) if count else 0.0
        candidate = np.zeros((n_paths, len(ACTION_CAPS), 2))
        candidate[:, :, 0] = mean_continue
        candidate[:, :, 1] = mean_full
        after_prediction = np.full(n_paths, mean_continue)
        return _OuterFollowerFit(
            candidate_values=candidate,
            after_cap_continuation=after_prediction,
            after_cap_regression=None,
            eligible=eligible,
            stable=False,
            instability_reasons=tuple(sorted(reasons)),
            condition_number=float("inf"),
            matrix_rank=0,
            feature_count=feature_count,
            training_rmse_aud=float("inf"),
            candidate_clip_fraction=0.0,
        )

    try:
        pre_continue_regression = fit_surrender_continuation_regression(
            pre_actual[selected],
            continuation[selected],
            premium=premium,
            settings=settings,
        )
        pre_full_regression = fit_surrender_continuation_regression(
            pre_actual[selected],
            full_value[selected],
            premium=premium,
            settings=settings,
        )
        after_regression = fit_surrender_continuation_regression(
            after_actual[selected],
            continuation[selected],
            premium=premium,
            settings=settings,
        )
    except (ValueError, np.linalg.LinAlgError) as exc:
        reasons.add(f"fit_failed:{exc}")
        mean_continue = float(np.mean(continuation[selected]))
        mean_full = float(np.mean(full_value[selected]))
        candidate = np.zeros((n_paths, len(ACTION_CAPS), 2))
        candidate[:, :, 0] = mean_continue
        candidate[:, :, 1] = mean_full
        return _OuterFollowerFit(
            candidate_values=candidate,
            after_cap_continuation=np.full(n_paths, mean_continue),
            after_cap_regression=None,
            eligible=eligible,
            stable=False,
            instability_reasons=tuple(sorted(reasons)),
            condition_number=float("inf"),
            matrix_rank=0,
            feature_count=feature_count,
            training_rmse_aud=float("inf"),
            candidate_clip_fraction=0.0,
        )

    regressions = (
        pre_continue_regression,
        pre_full_regression,
        after_regression,
    )
    condition = max(float(item.condition_number) for item in regressions)
    minimum_rank = min(int(item.matrix_rank) for item in regressions)
    if any(item.matrix_rank != item.coefficients.size for item in regressions):
        reasons.add("rank_deficient")
    if not np.isfinite(condition) or condition > settings.maximum_condition_number:
        reasons.add(f"condition_{condition:.6g}")

    candidate = np.zeros((n_paths, len(ACTION_CAPS), 2))
    for action, cap in enumerate(ACTION_CAPS):
        candidate_features = _follower_features_from_core(
            record.pre_cap_core,
            announced_cap=float(cap),
            duration_years=float(record.policy_year),
            include_previous_cap=False,
        )
        candidate[:, action, 0] = (
            pre_continue_regression.predict_features(candidate_features)
        )
        candidate[:, action, 1] = (
            pre_full_regression.predict_features(candidate_features)
        )
    after_prediction = after_regression.predict_features(after_actual)
    training_prediction = after_prediction[selected]
    training_rmse = float(np.sqrt(np.mean(
        (training_prediction - continuation[selected]) ** 2
    )))
    effective_rmse = (
        training_rmse
        if buffer_rmse_override is None
        else float(buffer_rmse_override)
    )
    after_regression = replace(
        after_regression, oof_rmse_aud=effective_rmse
    )

    target_matrix = np.column_stack((
        continuation[selected], full_value[selected]
    ))
    ceiling = np.maximum(
        np.max(target_matrix, axis=0)
        + 5.0 * np.std(target_matrix, axis=0),
        0.0,
    )
    before = candidate.copy()
    candidate = np.minimum(candidate, ceiling[None, None, :])
    # Do not clip the observed after-cap prediction.  This exact regression
    # object is persisted in ``OptimalSurrenderPolicy`` and its forward
    # prediction must therefore be bit-for-bit the value used to determine
    # the training response.  Candidate-cap Q values are internal control-
    # randomisation approximations and may still be bounded defensively.
    clip_fraction = float(np.mean(np.abs(before - candidate) > 0.0))
    if clip_fraction > 0.20:
        reasons.add(f"candidate_clip_fraction_{clip_fraction:.6g}")
    if not np.all(np.isfinite(candidate)) \
            or not np.all(np.isfinite(after_prediction)):
        reasons.add("nonfinite_prediction")
        candidate = np.nan_to_num(candidate, nan=0.0, posinf=0.0, neginf=0.0)
        after_prediction = np.nan_to_num(
            after_prediction, nan=0.0, posinf=0.0, neginf=0.0
        )
    return _OuterFollowerFit(
        candidate_values=candidate,
        after_cap_continuation=after_prediction,
        after_cap_regression=after_regression,
        eligible=eligible,
        stable=not reasons,
        instability_reasons=tuple(sorted(reasons)),
        condition_number=condition,
        matrix_rank=minimum_rank,
        feature_count=feature_count,
        training_rmse_aud=training_rmse,
        candidate_clip_fraction=clip_fraction,
    )


def _leader_values_for_outer_chain(
    fit: _CoupledLeaderYearFit,
    raw_state: Array,
    chain: int,
    feature_names: Sequence[str],
) -> Array:
    """Evaluate one future outer-fold chain on all supplied states."""
    if chain == fit.fold_coefficients.shape[0]:
        return _policy_action_values(fit.deployment, raw_state, feature_names)
    nonlinear, interactions, _ = _basis_specification(feature_names)
    design = _design_matrix(
        np.asarray(raw_state, dtype=float),
        fit.fold_means[chain],
        fit.fold_scales[chain],
        nonlinear,
        interactions,
    )
    values = np.einsum(
        "pb,abo->pao", design, fit.fold_coefficients[chain]
    )
    for action in range(len(ACTION_CAPS)):
        values[:, action], _ = _clip_component_predictions(
            values[:, action],
            fit.fold_lower_bounds[chain, action],
            fit.fold_upper_bounds[chain, action],
        )
    if not np.all(np.isfinite(values)):
        raise RuntimeError("Outer-chain leader values are non-finite.")
    return values


def _solve_follower_outer_chain_year(
    *,
    records: Mapping[tuple[object, ...], SignatureDecisionYearPaths],
    data: PortfolioPathData,
    year: int,
    chain: int,
    train_mask: NDArray[np.bool_],
    fold_ids: IntArray,
    action_indices: IntArray,
    control_inputs: ControlStateInputs,
    portfolio_state_extension: Array,
    future_leader: _CoupledLeaderYearFit | None,
    future_follower_values: Mapping[tuple[object, ...], Array],
    follower_settings: OptimalBehaviourLSMCSettings,
    feature_names: Sequence[str],
    buffer_rmse_by_signature: Mapping[tuple[object, ...], float] | None = None,
    force_continue_signatures: frozenset[tuple[object, ...]] = frozenset(),
) -> _FollowerChainYearSolution:
    """Solve one fold-pure follower/exposure fixed point for one year."""
    n_paths = action_indices.shape[0]
    rows = np.arange(n_paths)
    responses = {
        signature: np.zeros(n_paths, dtype=bool)
        for signature in records
    }
    previous_future_action: Array | None = None
    maximum_iterations = 4 if records else 1

    def evaluate(
        current_responses: Mapping[
            tuple[object, ...], NDArray[np.bool_]
        ],
    ) -> tuple[
        Array,
        IntArray,
        dict[tuple[object, ...], _OuterFollowerFit],
        dict[tuple[object, ...], Array],
        dict[tuple[object, ...], NDArray[np.bool_]],
        dict[tuple[object, ...], Array],
    ]:
        next_portfolio = np.array(
            portfolio_state_extension[:, year + 1, :], copy=True
        )
        for signature, response in current_responses.items():
            contribution = np.asarray(
                records[signature].next_portfolio_exposure_contribution,
                dtype=float,
            )
            next_portfolio[:, 1:] -= response[:, None] * contribution
        next_portfolio[:, 1:] = np.maximum(next_portfolio[:, 1:], 0.0)
        next_state = _counterfactual_next_leader_state(
            inputs=control_inputs,
            current_state=data.raw_states[:, year, :],
            year=year,
            current_cap=ACTION_CAPS[action_indices[:, year]],
            next_portfolio_state=next_portfolio,
        )
        if future_leader is None:
            future_action = np.zeros(n_paths, dtype=np.int64)
        else:
            future_values = _leader_values_for_outer_chain(
                future_leader, next_state, chain, feature_names
            )
            future_action = _lower_cap_argmax(
                future_values[:, :, 0], axis=1
            )

        fits: dict[tuple[object, ...], _OuterFollowerFit] = {}
        targets: dict[tuple[object, ...], Array] = {}
        new_responses: dict[
            tuple[object, ...], NDArray[np.bool_]
        ] = {}
        values: dict[tuple[object, ...], Array] = {}
        actual_caps = ACTION_CAPS[action_indices[:, year]]
        for signature, record in records.items():
            future_grid = future_follower_values.get(signature)
            if future_grid is None:
                future_u = np.zeros(n_paths)
            else:
                future_u = future_grid[
                    chain, rows, future_action
                ]
            numerator = (
                np.asarray(
                    record.continue_policyholder_interval_pv, dtype=float
                )
                + np.asarray(
                    record.next_decision_discount_inforce, dtype=float
                ) * future_u
            )
            denominator = np.asarray(
                record.decision_discount_inforce, dtype=float
            )
            target = np.divide(
                numerator,
                np.maximum(denominator, 1.0e-300),
                out=np.zeros_like(numerator),
                where=denominator > 1.0e-300,
            )
            fit = _fit_outer_follower_model(
                policy=data.signature_control_paths[signature].policy,
                record=record,
                actual_caps=actual_caps,
                continuation_target=target,
                train_mask=train_mask,
                settings=follower_settings,
                buffer_rmse_override=(
                    None
                    if buffer_rmse_by_signature is None
                    else buffer_rmse_by_signature.get(signature)
                ),
            )
            buffer = (
                follower_settings.exercise_tolerance_aud
                + follower_settings.exercise_buffer_rmse_multiplier
                * (
                    fit.training_rmse_aud
                    if fit.after_cap_regression is None
                    else fit.after_cap_regression.oof_rmse_aud
                )
            )
            exact_response = (
                fit.eligible
                & (~np.asarray(record.just_elected, dtype=bool))
                & np.asarray(record.full_withdrawal_eligible, dtype=bool)
                & (
                    np.asarray(record.full_withdrawal_value, dtype=float)
                    > fit.after_cap_continuation + buffer
                )
            )
            forced_continue = signature in force_continue_signatures
            if not fit.stable or forced_continue:
                exact_response[:] = False

            candidate = fit.candidate_values
            structural = (
                fit.eligible[:, None]
                & (~np.asarray(record.just_elected, dtype=bool))[:, None]
                & (candidate[:, :, 1] > 0.0)
            )
            candidate_response = structural & (
                candidate[:, :, 1] > candidate[:, :, 0] + buffer
            )
            if not fit.stable or forced_continue:
                candidate_response[:] = False
            candidate_value = np.where(
                candidate_response,
                candidate[:, :, 1],
                candidate[:, :, 0],
            )
            # The observed cap has an exact post-DVA state and contractual
            # eligibility; use it instead of its pre-cap Q approximation.
            observed_action = action_indices[:, year]
            candidate_value[rows, observed_action] = np.where(
                exact_response,
                np.asarray(record.full_withdrawal_value, dtype=float),
                fit.after_cap_continuation,
            )
            fits[signature] = fit
            targets[signature] = target
            new_responses[signature] = exact_response
            values[signature] = candidate_value
        return (
            next_state,
            future_action,
            fits,
            targets,
            new_responses,
            values,
        )

    last: tuple[Array, IntArray, dict, dict, dict, dict] | None = None
    converged = True
    for _iteration in range(maximum_iterations):
        last = evaluate(responses)
        (
            _next_state,
            future_action,
            _fits,
            _targets,
            new_responses,
            _values,
        ) = last
        same_response = all(
            np.array_equal(new_responses[key], responses[key])
            for key in responses
        )
        same_future_action = (
            previous_future_action is not None
            and np.array_equal(future_action, previous_future_action)
        )
        responses = new_responses
        if same_response and (
            not records or future_leader is None or same_future_action
        ):
            break
        previous_future_action = future_action.copy()
    else:
        converged = False

    if not converged and records:
        responses = {
            signature: np.zeros(n_paths, dtype=bool)
            for signature in records
        }
        last = evaluate(responses)
        next_state, future_action, fits, targets, _ignored, values = last
        for signature, fit in fits.items():
            values[signature] = fit.candidate_values[:, :, 0].copy()
            values[signature][
                rows, action_indices[:, year]
            ] = fit.after_cap_continuation
    else:
        if last is None:
            raise RuntimeError("Follower outer-chain iteration produced no state.")
        next_state, future_action, fits, targets, responses, values = last
    return _FollowerChainYearSolution(
        responses=responses,
        fits=fits,
        continuation_targets=targets,
        policyholder_values=values,
        next_state=next_state,
        future_action=future_action,
        converged=converged,
    )


def _insurer_targets_for_outer_chain(
    *,
    data: PortfolioPathData,
    year: int,
    solution: _FollowerChainYearSolution,
    continue_components: Array,
    future_leader: _CoupledLeaderYearFit | None,
    chain: int,
    feature_names: Sequence[str],
) -> Array:
    immediate = np.array(continue_components[:, year, :], copy=True)
    for signature, response in solution.responses.items():
        delta = np.asarray(
            data.signature_control_paths[
                signature
            ].decision_years[year].insurer_full_minus_continue_components,
            dtype=float,
        )
        immediate[:, 1:] += response[:, None] * delta
    immediate[:, 0] = _csm_from_component_values(immediate[:, 1:])
    if future_leader is None:
        future_selected = np.zeros_like(immediate)
    else:
        future_values = _leader_values_for_outer_chain(
            future_leader, solution.next_state, chain, feature_names
        )
        action = _lower_cap_argmax(future_values[:, :, 0], axis=1)
        future_selected = future_values[np.arange(future_values.shape[0]), action]
    target = immediate + future_selected
    target[:, 0] = _csm_from_component_values(target[:, 1:])
    return target


def _fit_outer_leader_model(
    *,
    year: int,
    raw_state: Array,
    targets: Array,
    observed_actions: IntArray,
    train_mask: NDArray[np.bool_],
    ridge: float,
    feature_names: Sequence[str],
) -> _OuterLeaderFit:
    """Fit one leader chain on an explicit outer training mask."""
    nonlinear, interactions, basis_names = _basis_specification(feature_names)
    n_basis = len(basis_names)
    n_actions = len(ACTION_CAPS)
    mean, scale = _raw_scaling(raw_state[train_mask])
    design_all = _design_matrix(
        raw_state, mean, scale, nonlinear, interactions
    )
    coefficients = np.zeros((n_actions, n_basis, 10))
    lower_bounds = np.zeros((n_actions, 10))
    upper_bounds = np.zeros_like(lower_bounds)
    predictions = np.zeros((raw_state.shape[0], n_actions, 10))
    standard_errors = np.zeros(n_actions)
    conditions = np.zeros(n_actions)
    clip_fractions = np.zeros(n_actions)
    counterfactual_clip_fractions = np.zeros(n_actions)
    counts = np.zeros(n_actions, dtype=np.int64)
    reasons: set[str] = set()
    action_blocking_reasons: list[set[str]] = [
        set() for _ in range(n_actions)
    ]
    minimum = max(30, 3 * n_basis)
    for action, cap in enumerate(ACTION_CAPS):
        blocking = action_blocking_reasons[action]
        selected = train_mask & (observed_actions == action)
        count = int(np.count_nonzero(selected))
        counts[action] = count
        if count < minimum:
            reason = (
                f"year_{year + 1}_cap_{cap:.6f}_support_"
                f"{count}_below_{minimum}"
            )
            reasons.add(reason)
            blocking.add(reason)
            component_beta = np.zeros((n_basis, len(INSURER_COMPONENT_NAMES)))
            if count:
                component_beta[0] = np.mean(targets[selected, 1:], axis=0)
                bounds_source = targets[selected]
            else:
                bounds_source = np.zeros((1, 10))
            condition = float("inf")
        else:
            component_beta = _ridge_fit_multioutput(
                design_all[selected], targets[selected, 1:], ridge
            )
            bounds_source = targets[selected]
            condition = _condition_number(design_all[selected], ridge)
            if not np.isfinite(condition) or condition > 1.0e10:
                reason = (
                    f"year_{year + 1}_cap_{cap:.6f}_condition_"
                    f"{condition:.6g}"
                )
                reasons.add(reason)
                blocking.add(reason)
        beta = _component_regression_coefficients(component_beta)
        lower, upper = _component_prediction_bounds(bounds_source)
        raw_prediction = design_all @ beta
        bounded, counterfactual_clip_fraction = _clip_component_predictions(
            raw_prediction, lower, upper
        )
        if count:
            in_support_clip_fraction = float(np.mean(
                np.abs(
                    bounded[selected, 1:] - raw_prediction[selected, 1:]
                ) > 0.0
            ))
        else:
            in_support_clip_fraction = 0.0
        if in_support_clip_fraction > 0.01:
            reason = (
                f"year_{year + 1}_cap_{cap:.6f}_in_support_clip_fraction_"
                f"{in_support_clip_fraction:.6g}"
            )
            reasons.add(reason)
            # Bounding is itself the numerical safety rail.  Moderate
            # in-support clipping is retained as a warning; only pervasive
            # in-support clipping makes this particular cap undeployable.
            if in_support_clip_fraction > 0.20:
                blocking.add(reason)
        coefficients[action] = beta
        lower_bounds[action] = lower
        upper_bounds[action] = upper
        predictions[:, action] = bounded
        conditions[action] = condition
        clip_fractions[action] = in_support_clip_fraction
        counterfactual_clip_fractions[action] = (
            counterfactual_clip_fraction
        )
        if count:
            residual = targets[selected, 0] - bounded[selected, 0]
            rmse = float(np.sqrt(np.mean(residual * residual)))
            scale_target = max(
                float(np.std(targets[selected, 0])),
                float(np.mean(np.abs(targets[selected, 0]))),
                1.0,
            )
            if not np.isfinite(rmse) or rmse > 10.0 * scale_target:
                reason = (
                    f"year_{year + 1}_cap_{cap:.6f}_rmse_ratio_"
                    f"{rmse / scale_target:.6g}"
                )
                reasons.add(reason)
                blocking.add(reason)
            standard_errors[action] = (
                rmse / np.sqrt(count)
                if np.isfinite(rmse)
                else float(np.finfo(np.float64).max)
            )
        else:
            standard_errors[action] = float(np.finfo(np.float64).max)
    policy = RegressionPolicyYear(
        year=year,
        raw_mean=mean,
        raw_scale=scale,
        coefficients=coefficients,
        action_caps=ACTION_CAPS.copy(),
        action_value_standard_error=standard_errors,
        value_lower_bounds=lower_bounds,
        value_upper_bounds=upper_bounds,
        numerically_stable=not reasons,
        action_deployable_mask=np.asarray(
            [not item for item in action_blocking_reasons], dtype=bool
        ),
    )
    return _OuterLeaderFit(
        policy=policy,
        predictions=predictions,
        instability_reasons=tuple(sorted(reasons)),
        action_deployable_mask=np.asarray(
            [not item for item in action_blocking_reasons], dtype=bool
        ),
        action_instability_reasons=tuple(
            tuple(sorted(item)) for item in action_blocking_reasons
        ),
        conditions=conditions,
        clip_fractions=clip_fractions,
        counterfactual_clip_fractions=counterfactual_clip_fractions,
        observed_counts=counts,
    )


def _coupled_backward_induction(
    data: PortfolioPathData,
    action_indices: IntArray,
    *,
    control_inputs: ControlStateInputs,
    portfolio_state_extension: Array,
    folds: int,
    ridge: float,
    seed: int,
    follower_settings: OptimalBehaviourLSMCSettings,
    scenario_fingerprint: str,
    cap_schedule_fingerprint: str,
) -> BackwardResult:
    """Outer-fold-pure two-value Stackelberg Fitted-Q recursion.

    Each complete-path outer fold owns an independent future Leader/Follower
    policy chain trained without that fold.  A separate full-sample chain
    supplies the persisted deployment models.  Thus current held-out values
    cannot leak indirectly through a future-year regression target, and the
    exact after-cap follower regression used in insurer rewards is the same
    frozen object used by the monthly forward projector.
    """
    if data.raw_states is None or data.inforce_exposure is None:
        raise ValueError("Coupled backward induction requires rich state paths.")
    if not data.signature_control_paths:
        raise ValueError("Coupled backward induction lacks signature primitives.")
    n_paths, n_years = data.new_business_csm_proxy.shape
    if action_indices.shape != (n_paths, n_years):
        raise ValueError("Coupled action indices are shape-inconsistent.")
    if portfolio_state_extension.shape != (
        n_paths,
        n_years + 1,
        len(PORTFOLIO_CONTROL_STATE_FEATURE_NAMES),
    ):
        raise ValueError("Coupled portfolio-state extension is inconsistent.")
    feature_names = data.state_feature_names
    if tuple(feature_names) != (
        *CONTROL_STATE_FEATURE_NAMES,
        *PORTFOLIO_CONTROL_STATE_FEATURE_NAMES,
    ):
        raise ValueError("Coupled recursion requires the documented state layout.")

    rng = np.random.default_rng(seed)
    fold_ids = np.empty(n_paths, dtype=np.int64)
    for action in range(len(ACTION_CAPS)):
        action_rows = np.flatnonzero(action_indices[:, 0] == action)
        assigned = np.resize(np.arange(folds, dtype=np.int64), len(action_rows))
        fold_ids[action_rows] = rng.permutation(assigned)
    if set(np.unique(fold_ids)) != set(range(folds)):
        raise RuntimeError("Complete-path outer folds are incomplete.")

    continue_components = _portfolio_continue_component_tensor(data)
    future_leader: _CoupledLeaderYearFit | None = None
    future_follower_values: dict[tuple[object, ...], Array] = {}
    deployment_regressions: dict[
        tuple[object, ...], dict[int, object]
    ] = {signature: {} for signature in data.signature_control_paths}
    follower_rows: list[dict[str, object]] = []
    leader_rows: list[dict[str, object]] = []
    policy_year_rows: list[dict[str, object]] = []
    first_year_action_rows: list[dict[str, object]] = []
    policy_years: list[RegressionPolicyYear] = []
    active_years: list[int] = []
    numerical_reasons: set[str] = set()
    first_cap = float("nan")
    first_outputs = np.zeros(10)
    first_se = float("nan")

    LOGGER.info(
        "Outer-fold-pure coupled backward induction | years=%d | actions=%d | "
        "paths=%d | signatures=%d | folds=%d plus deployment chain",
        n_years,
        len(ACTION_CAPS),
        n_paths,
        len(data.signature_control_paths),
        folds,
    )
    for year in range(n_years - 1, -1, -1):
        exposure = np.asarray(data.inforce_exposure[:, year], dtype=float)
        if not np.any(exposure > 0.0):
            residual = max(
                float(np.max(np.abs(
                    np.asarray(getattr(data, name))[:, year]
                )))
                for name in (
                    "fees_product",
                    "fees_lip",
                    "crediting_margin",
                    "mva_retained",
                    "aps_retained",
                    "guarantee_claims",
                    "other_insurer_funded_benefits",
                    "expenses",
                    "hedge_costs",
                )
            )
            materiality = 1.0e-8 * data.representative_initial_premium
            has_follower_continuation = any(
                np.any(np.abs(np.asarray(values, dtype=float)) > materiality)
                for values in future_follower_values.values()
            )
            if (
                residual > materiality
                or future_leader is not None
                or has_follower_continuation
            ):
                raise RuntimeError(
                    "Inactive policy year has a material reward or a later "
                    "active continuation; refusing to discard it."
                )
            continue
        active_years.append(year + 1)
        if year == n_years - 1 or year == 0 or (year + 1) % 5 == 0:
            LOGGER.info(
                "Outer-fold coupled recursion | policy year %d/%d",
                year + 1,
                n_years,
            )
        records = {
            signature: paths.decision_years[year]
            for signature, paths in data.signature_control_paths.items()
            if year in paths.decision_years
        }

        fold_solutions: list[_FollowerChainYearSolution] = []
        fold_targets: list[Array] = []
        fold_leader_fits: list[_OuterLeaderFit] = []
        for fold in range(folds):
            train_mask = fold_ids != fold
            solution = _solve_follower_outer_chain_year(
                records=records,
                data=data,
                year=year,
                chain=fold,
                train_mask=train_mask,
                fold_ids=fold_ids,
                action_indices=action_indices,
                control_inputs=control_inputs,
                portfolio_state_extension=portfolio_state_extension,
                future_leader=future_leader,
                future_follower_values=future_follower_values,
                follower_settings=follower_settings,
                feature_names=feature_names,
            )
            target = _insurer_targets_for_outer_chain(
                data=data,
                year=year,
                solution=solution,
                continue_components=continue_components,
                future_leader=future_leader,
                chain=fold,
                feature_names=feature_names,
            )
            leader_fit = _fit_outer_leader_model(
                year=year,
                raw_state=data.raw_states[:, year, :],
                targets=target,
                observed_actions=action_indices[:, year],
                train_mask=train_mask,
                ridge=ridge,
                feature_names=feature_names,
            )
            fold_solutions.append(solution)
            fold_targets.append(target)
            fold_leader_fits.append(leader_fit)

        oof_rmse_by_signature: dict[tuple[object, ...], float] = {}
        for signature in records:
            residual_parts: list[Array] = []
            for fold, solution in enumerate(fold_solutions):
                fit = solution.fits[signature]
                held_out = (fold_ids == fold) & fit.eligible
                if np.any(held_out):
                    residual_parts.append(
                        fit.after_cap_continuation[held_out]
                        - solution.continuation_targets[signature][held_out]
                    )
            oof_rmse_by_signature[signature] = (
                float(np.sqrt(np.mean(np.concatenate(residual_parts) ** 2)))
                if residual_parts else float("inf")
            )

        # A missing finite OOF error estimate makes the full-sample exercise
        # buffer unusable, so that deployment signature is conservatively
        # frozen to Continue before its insurer target is built.  An unstable
        # individual outer fit already returns Continue in its own fold-pure
        # chain; it does not invalidate a separately stable full-sample fit.
        crossfit_forced_continue = frozenset(
            signature
            for signature in records
            if not np.isfinite(oof_rmse_by_signature[signature])
        )

        deployment_chain = folds
        full_solution = _solve_follower_outer_chain_year(
            records=records,
            data=data,
            year=year,
            chain=deployment_chain,
            train_mask=np.ones(n_paths, dtype=bool),
            fold_ids=fold_ids,
            action_indices=action_indices,
            control_inputs=control_inputs,
            portfolio_state_extension=portfolio_state_extension,
            future_leader=future_leader,
            future_follower_values=future_follower_values,
            follower_settings=follower_settings,
            feature_names=feature_names,
            buffer_rmse_by_signature=oof_rmse_by_signature,
            force_continue_signatures=crossfit_forced_continue,
        )
        full_target = _insurer_targets_for_outer_chain(
            data=data,
            year=year,
            solution=full_solution,
            continue_components=continue_components,
            future_leader=future_leader,
            chain=deployment_chain,
            feature_names=feature_names,
        )
        full_leader_fit = _fit_outer_leader_model(
            year=year,
            raw_state=data.raw_states[:, year, :],
            targets=full_target,
            observed_actions=action_indices[:, year],
            train_mask=np.ones(n_paths, dtype=bool),
            ridge=ridge,
            feature_names=feature_names,
        )

        fold_coefficients = np.stack([
            item.policy.coefficients for item in fold_leader_fits
        ])
        fold_lower = np.stack([
            item.policy.value_lower_bounds for item in fold_leader_fits
        ])
        fold_upper = np.stack([
            item.policy.value_upper_bounds for item in fold_leader_fits
        ])
        leader_instability = {
            f"outer_fold_{fold}::{reason}"
            for fold, item in enumerate(fold_leader_fits)
            for reason in item.instability_reasons
        }
        leader_instability.update(
            f"deployment::{reason}"
            for reason in full_leader_fit.instability_reasons
        )
        leader_fit = _CoupledLeaderYearFit(
            deployment=full_leader_fit.policy,
            fold_means=np.stack([
                item.policy.raw_mean for item in fold_leader_fits
            ]),
            fold_scales=np.stack([
                item.policy.raw_scale for item in fold_leader_fits
            ]),
            fold_coefficients=fold_coefficients,
            fold_lower_bounds=fold_lower,
            fold_upper_bounds=fold_upper,
            stable=not leader_instability,
            instability_reasons=tuple(sorted(leader_instability)),
        )
        numerical_reasons.update(
            f"insurer::{reason}" for reason in leader_instability
        )

        oof = np.zeros((n_paths, len(ACTION_CAPS), 10))
        for fold, item in enumerate(fold_leader_fits):
            held_out = fold_ids == fold
            oof[held_out] = item.predictions[held_out]
        if not np.all(np.isfinite(oof)):
            raise RuntimeError("Outer-fold insurer OOF values are non-finite.")

        for action, cap in enumerate(ACTION_CAPS):
            observed = action_indices[:, year] == action
            residual_parts = []
            target_parts = []
            for fold in range(folds):
                selected = observed & (fold_ids == fold)
                if np.any(selected):
                    residual_parts.append(
                        fold_targets[fold][selected, 0]
                        - oof[selected, action, 0]
                    )
                    target_parts.append(fold_targets[fold][selected, 0])
            residual = np.concatenate(residual_parts)
            observed_target = np.concatenate(target_parts)
            rmse = float(np.sqrt(np.mean(residual * residual)))
            variance = float(np.var(observed_target))
            leader_rows.append({
                "policy_year": year + 1,
                "cap": float(cap),
                "observed_path_count": int(observed_target.size),
                "basis_dimension": int(
                    full_leader_fit.policy.coefficients.shape[1]
                ),
                "ridge_multiplier": float(ridge),
                "out_of_fold_rmse_new_business_csm_proxy": rmse,
                "out_of_fold_r_squared_new_business_csm_proxy": (
                    1.0 - rmse * rmse / variance
                    if variance > 1.0e-20 else 1.0
                ),
                "in_sample_component_clip_fraction": float(
                    full_leader_fit.clip_fractions[action]
                ),
                "maximum_fold_component_clip_fraction": float(max(
                    item.clip_fractions[action]
                    for item in fold_leader_fits
                )),
                "regularized_normal_matrix_condition_number": float(
                    full_leader_fit.conditions[action]
                ),
                "design_condition_number": float(
                    full_leader_fit.conditions[action]
                ),
                "csm_derived_from_components": True,
                "outer_fold_pure": True,
            })

        current_follower_values: dict[tuple[object, ...], Array] = {}
        for signature, record in records.items():
            chain_values = [
                solution.policyholder_values[signature]
                for solution in fold_solutions
            ]
            chain_values.append(full_solution.policyholder_values[signature])
            current_follower_values[signature] = np.stack(chain_values)
            full_fit = full_solution.fits[signature]
            deployment_stable = (
                full_fit.stable
                and full_solution.converged
                and np.isfinite(oof_rmse_by_signature[signature])
                and signature not in crossfit_forced_continue
            )
            signature_text = json.dumps(
                signature, default=str, separators=(",", ":")
            )
            reasons = {
                reason
                for solution in fold_solutions
                for reason in solution.fits[signature].instability_reasons
            }
            reasons.update(full_fit.instability_reasons)
            if signature in crossfit_forced_continue:
                reasons.add("missing_finite_oof_rmse_forced_continue")
            if not all(solution.converged for solution in fold_solutions) \
                    or not full_solution.converged:
                reasons.add("follower_exposure_fixed_point")
            follower_rows.append({
                "fit_label": "coupled_control_randomisation",
                "policy_signature": signature_text,
                "policy_signature_fingerprint": hashlib.sha256(
                    signature_text.encode("utf-8")
                ).hexdigest(),
                "policy_year": year + 1,
                "decision_step": record.decision_step,
                "observations": int(np.count_nonzero(full_fit.eligible)),
                "folds_used": folds,
                "feature_count": full_fit.feature_count,
                "matrix_rank": full_fit.matrix_rank,
                "condition_number": full_fit.condition_number,
                "oof_rmse_aud": oof_rmse_by_signature[signature],
                "candidate_prediction_clip_fraction": (
                    full_fit.candidate_clip_fraction
                ),
                "training_exercise_rate": float(np.mean(
                    full_solution.responses[signature]
                )),
                "regression_accepted_for_exercise": deployment_stable,
                "outer_crossfit_stable": all(
                    solution.converged
                    and solution.fits[signature].stable
                    for solution in fold_solutions
                ),
                "deployment_regression_stable": deployment_stable,
                "fallback_reason": "|".join(sorted(reasons)),
                "value_function": (
                    "outer_fold_pure_policyholder_continuation_and_full_q"
                ),
                "two_value_recursion": True,
                "outer_fold_pure": True,
                "response_fixed_point_converged": (
                    full_solution.converged
                ),
            })
            if deployment_stable and full_fit.after_cap_regression is not None:
                deployment_regressions[signature][record.decision_step] = (
                    full_fit.after_cap_regression
                )
            else:
                signature_key = hashlib.sha256(
                    signature_text.encode("utf-8")
                ).hexdigest()
                for reason in reasons or {"unstable_follower_regression"}:
                    numerical_reasons.add(
                        f"policyholder::{signature_key}::{reason}"
                    )
        future_follower_values = current_follower_values

        if year == 0:
            action_values = np.mean(oof, axis=0)
            action_se = np.asarray([
                _standard_error(oof[:, action, 0])
                for action in range(len(ACTION_CAPS))
            ])
            chosen = int(_lower_cap_argmax(action_values[:, 0]))
            first_cap = float(ACTION_CAPS[chosen])
            first_outputs = action_values[chosen]
            first_se = float(action_se[chosen])
            constant = _constant_first_year_policy(
                year=0,
                raw_state=data.raw_states[:, 0, :],
                action_values=action_values,
                action_standard_errors=action_se,
                feature_names=feature_names,
                numerically_stable=leader_fit.stable,
            )
            policy_years.append(constant)
            for action, cap in enumerate(ACTION_CAPS):
                values = action_values[action]
                first_year_action_rows.append({
                    "cap": float(cap),
                    "cap_percent": 100.0 * float(cap),
                    "selection_estimated_q_new_business_csm_proxy": float(
                        values[0]
                    ),
                    "selection_standard_error_new_business_csm_proxy": float(
                        action_se[action]
                    ),
                    "holdout_estimated_q_new_business_csm_proxy": float(values[0]),
                    "holdout_estimated_q_fees_product": float(values[1]),
                    "holdout_estimated_q_fees_lip": float(values[2]),
                    "holdout_estimated_q_crediting_margin": float(values[3]),
                    "holdout_estimated_q_mva_retained": float(values[4]),
                    "holdout_estimated_q_aps_retained": float(values[5]),
                    "holdout_estimated_q_guarantee_claims": float(values[6]),
                    "holdout_estimated_q_other_insurer_funded_benefits": float(
                        values[7]
                    ),
                    "holdout_estimated_q_expenses": float(values[8]),
                    "holdout_estimated_q_hedge_costs": float(values[9]),
                    "holdout_standard_error_new_business_csm_proxy": float(
                        action_se[action]
                    ),
                    "selection_path_count": n_paths,
                    "holdout_path_count": n_paths,
                    "observed_control_action_path_count": int(np.sum(
                        action_indices[:, 0] == action
                    )),
                    "economically_active": True,
                    "is_optimal_first_year_cap": action == chosen,
                    "two_value_stackelberg_recursion": True,
                    "outer_fold_pure": True,
                    "selection_value_semantics": (
                        "complete-path outer-fold-pure OOF action-value mean"
                    ),
                    "holdout_value_semantics": (
                        "legacy output alias of the outer-fold-pure OOF mean"
                    ),
                })
            policy_year_rows.append({
                "policy_year": 1,
                "cap": first_cap,
                "selected_fraction": 1.0,
                "mean_selected_cap": first_cap,
                "p10_selected_cap": first_cap,
                "median_selected_cap": first_cap,
                "p90_selected_cap": first_cap,
                "economically_active": True,
                "mean_inforce_exposure": float(np.mean(exposure)),
                "outer_fold_pure": True,
            })
        else:
            chosen = _lower_cap_argmax(oof[:, :, 0], axis=1)
            selected_caps = ACTION_CAPS[chosen]
            quantiles = np.quantile(selected_caps, (0.10, 0.50, 0.90))
            for action, cap in enumerate(ACTION_CAPS):
                fraction = float(np.mean(chosen == action))
                policy_year_rows.append({
                    "policy_year": year + 1,
                    "cap": float(cap),
                    "selected_fraction": fraction,
                    "mean_selected_cap": float(np.mean(selected_caps)),
                    "p10_selected_cap": float(quantiles[0]),
                    "median_selected_cap": float(quantiles[1]),
                    "p90_selected_cap": float(quantiles[2]),
                    "economically_active": True,
                    "mean_inforce_exposure": float(np.mean(exposure)),
                    "outer_fold_pure": True,
                })
            policy_years.append(full_leader_fit.policy)
        future_leader = leader_fit

    policy_years.sort(key=lambda item: item.year)
    active_years.sort()
    if not active_years or active_years[0] != 1:
        raise RuntimeError("The coupled portfolio has no active first policy year.")
    if active_years != list(range(1, active_years[-1] + 1)):
        raise RuntimeError("Coupled economic policy horizon is not contiguous.")

    policies: dict[tuple[object, ...], object] = {}
    fallback_steps_by_signature: dict[
        tuple[object, ...], tuple[int, ...]
    ] = {}
    full_fallback_signatures: set[tuple[object, ...]] = set()
    active_year_indices = {item - 1 for item in active_years}
    for signature, paths in data.signature_control_paths.items():
        regressions = dict(sorted(deployment_regressions[signature].items()))
        policies[signature] = OptimalSurrenderPolicy(
            regressions=MappingProxyType(regressions),
            settings=follower_settings,
        )
        expected_steps = {
            record.decision_step
            for year, record in paths.decision_years.items()
            if year in active_year_indices
        }
        fallback_steps = tuple(sorted(expected_steps - set(regressions)))
        fallback_steps_by_signature[signature] = fallback_steps
        if expected_steps and len(fallback_steps) == len(expected_steps):
            full_fallback_signatures.add(signature)
    fit_set = CoupledPolicyholderFitSet(
        policies=policies,
        scenario_fingerprint=scenario_fingerprint,
        cap_schedule_fingerprint=cap_schedule_fingerprint,
        fallback_signatures=full_fallback_signatures,
        fallback_steps_by_signature=fallback_steps_by_signature,
    )
    component_csm = _csm_from_component_values(first_outputs[1:][None, :])[0]
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
        standard_error_new_business_csm_proxy=first_se,
        first_year_action_rows=first_year_action_rows,
        policy_year_rows=sorted(
            policy_year_rows,
            key=lambda row: (int(row["policy_year"]), float(row["cap"])),
        ),
        regression_rows=sorted(
            leader_rows,
            key=lambda row: (int(row["policy_year"]), float(row["cap"])),
        ),
        policy_years=policy_years,
        reconciliation_gap=float(first_outputs[0] - component_csm),
        economically_active_policy_years=tuple(active_years),
        inactive_market_tail_year_count=n_years - len(active_years),
        numerically_stable=not any(
            reason.startswith("insurer::") for reason in numerical_reasons
        ),
        numerical_fallback_reasons=tuple(sorted(numerical_reasons)),
        follower_regression_rows=follower_rows,
        follower_fit_set=fit_set,
    )


# ============================================================================
# Gas-storage-style account-value inventory grid (Gitter) helpers
# ============================================================================
#
# The insurer cap recursion below values the annual crediting cap with the
# regression-Monte-Carlo method used to value gas storage contracts
# (Boogert & de Jong, 2008; Carmona & Ludkovski, 2010).  The customer account
# value per initial premium is the endogenous inventory ("storage level").
# It is discretised onto an adaptive grid; the cap is the injection control
# governing how much reference-fund return is credited into the fund (the
# injected volume), while dynamic income and withdrawals draw it down.  The
# continuation value is fitted per grid node on the exogenous state and looked
# up at the resulting account value by interpolation, whose inter-node delta
# V(A_{k+1}) - V(A_k) is the discrete marginal value of account value (the
# storage shadow price) that drives the optimal cap.

ACCOUNT_VALUE_INVENTORY_FEATURE = "account_value_per_initial_premium"


def _inventory_feature_index(feature_names: Sequence[str]) -> int:
    """Return the column of the endogenous account-value inventory state."""
    names = tuple(feature_names)
    if ACCOUNT_VALUE_INVENTORY_FEATURE not in names:
        raise ValueError(
            "Gas-storage backward induction requires the "
            f"'{ACCOUNT_VALUE_INVENTORY_FEATURE}' inventory state feature."
        )
    return names.index(ACCOUNT_VALUE_INVENTORY_FEATURE)


def _exogenous_feature_layout(
    feature_names: Sequence[str], inventory_index: int
) -> tuple[tuple[str, ...], IntArray]:
    """Split off the exogenous state the per-node value function regresses on.

    In the storage analogy the account value is the single controllable
    inventory dimension carried by the grid-node index; every other state
    variable is the exogenous ("price") factor on which the continuation value
    is regressed, separately per node (Boogert & de Jong, 2008).
    """
    columns = [i for i in range(len(feature_names)) if i != inventory_index]
    exogenous_names = tuple(feature_names[i] for i in columns)
    return exogenous_names, np.asarray(columns, dtype=np.int64)


def _account_value_grid(
    account_value: Array,
    n_nodes: int,
    quantile_clip: float,
) -> Array:
    """Build the strictly increasing account-value inventory grid (Gitter).

    Nodes are placed on empirical quantiles of the pooled in-force account
    value, so the grid concentrates where the fund density is highest (adaptive
    spacing).  The observed extremes and the unit initial account value are
    always bracketed so a transitioned level never falls outside the
    interpolation range by design.
    """
    if n_nodes < 3:
        raise ValueError("The account-value grid needs at least three nodes.")
    if not 0.0 <= quantile_clip < 0.5:
        raise ValueError("quantile_clip must lie in [0, 0.5).")
    pooled = np.asarray(account_value, dtype=float)
    pooled = pooled[np.isfinite(pooled)]
    if pooled.size == 0:
        raise RuntimeError("No active account-value observations for the grid.")
    probabilities = np.linspace(quantile_clip, 1.0 - quantile_clip, n_nodes)
    nodes = np.quantile(pooled, probabilities)
    nodes = np.concatenate((
        nodes, [float(np.min(pooled)), float(np.max(pooled)), 1.0]
    ))
    nodes = np.unique(np.round(nodes, 12))
    span = max(float(nodes[-1] - nodes[0]), 1.0e-6)
    minimum_gap = 1.0e-4 * span
    cleaned = [float(nodes[0])]
    for value in nodes[1:]:
        if value - cleaned[-1] >= minimum_gap:
            cleaned.append(float(value))
    if len(cleaned) < 3:
        cleaned = list(np.linspace(nodes[0], nodes[-1] + minimum_gap, 3))
    return np.asarray(cleaned, dtype=float)


def _grid_continuation_lookup(
    node_values: Array,
    grid: Array,
    query: Array,
) -> tuple[Array, Array]:
    """Piecewise-linear interpolation of a per-node value function.

    ``node_values`` holds, for every path, the continuation value already
    evaluated at each grid node (shape ``(n_paths, n_nodes, n_outputs)``).  For
    a transitioned account value ``query`` per path we locate the bracketing
    nodes and interpolate using the **delta between the two neighbouring
    states**, ``node_values[:, k + 1] - node_values[:, k]`` (Boogert & de Jong,
    2008, Eqs. 26-28).  That inter-node delta is the discrete marginal value of
    account value -- the storage shadow price -- and is what turns the
    continuation surface into an optimal-control signal.  Queries outside the
    grid clamp to the boundary nodes.  The signed inter-node delta actually
    used is returned alongside the interpolated value for diagnostics.
    """
    grid = np.asarray(grid, dtype=float)
    n_nodes = grid.shape[0]
    clamped = np.clip(np.asarray(query, dtype=float), grid[0], grid[-1])
    lower_index = np.searchsorted(grid, clamped, side="right") - 1
    lower_index = np.clip(lower_index, 0, n_nodes - 2)
    upper_index = lower_index + 1
    lower_edge = grid[lower_index]
    upper_edge = grid[upper_index]
    weight = (clamped - lower_edge) / np.maximum(upper_edge - lower_edge, 1.0e-300)
    lower_values = np.take_along_axis(
        node_values, lower_index[:, None, None], axis=1
    )[:, 0, :]
    upper_values = np.take_along_axis(
        node_values, upper_index[:, None, None], axis=1
    )[:, 0, :]
    inter_state_delta = upper_values - lower_values
    interpolated = lower_values + weight[:, None] * inter_state_delta
    return interpolated, inter_state_delta


def _force_inventory(raw_state: Array, inventory_index: int, level: float) -> Array:
    """Return a copy of the state with the account-value column set to ``level``.

    Evaluating the reward and transition regressions at a forced grid node is
    the storage-method device that maps a continuous, control-affected account
    value onto the discrete inventory levels of the grid; the squared and
    interacted basis terms in the design matrix update consistently.
    """
    forced = np.array(raw_state, dtype=float, copy=True)
    forced[:, inventory_index] = level
    return forced


@dataclass(frozen=True)
class _GridYearValue:
    """Per-node continuation value function fitted at one decision time."""

    exogenous_mean: Array
    exogenous_scale: Array
    node_coefficients: Array  # (n_nodes, basis_z, 9) component value functions


def _fit_grid_continuation(
    exogenous_state: Array,
    node_targets: Array,
    exogenous_names: Sequence[str],
    ridge: float,
) -> _GridYearValue:
    """Regress the optimal value at each grid node on the exogenous state.

    One ridge regression is fitted per inventory node (Boogert & de Jong,
    2008): the account-value dependence is carried by the node index while the
    exogenous market/portfolio factors enter through the basis.  Boogert & de
    Jong found a joint price-inventory basis numerically unsatisfactory and
    recommend exactly this separate-regression-per-level scheme.
    """
    nonlinear, interactions, _ = _basis_specification(exogenous_names)
    mean, scale = _raw_scaling(exogenous_state)
    design = _design_matrix(exogenous_state, mean, scale, nonlinear, interactions)
    n_nodes = node_targets.shape[1]
    n_components = node_targets.shape[2]
    coefficients = np.zeros((n_nodes, design.shape[1], n_components), dtype=float)
    for node in range(n_nodes):
        coefficients[node] = _ridge_fit_multioutput(
            design, node_targets[:, node, :], ridge
        )
    return _GridYearValue(mean, scale, coefficients)


def _evaluate_grid_continuation(
    value: _GridYearValue,
    exogenous_state: Array,
    exogenous_names: Sequence[str],
) -> Array:
    """Evaluate every node's continuation value for one exogenous state matrix."""
    nonlinear, interactions, _ = _basis_specification(exogenous_names)
    design = _design_matrix(
        exogenous_state, value.exogenous_mean, value.exogenous_scale,
        nonlinear, interactions,
    )
    # (n_paths, basis) x (n_nodes, basis, 9) -> (n_paths, n_nodes, 9)
    return np.einsum("pb,kbo->pko", design, value.node_coefficients)


def _kfold_oof_csm_diagnostics(
    design: Array, target_csm: Array, folds: int, ridge: float, seed: int
) -> tuple[float, float]:
    """Return (out-of-fold RMSE, out-of-fold R^2) for one cap's CSM value."""
    n = design.shape[0]
    variance = float(np.var(target_csm))
    if n < 2 * folds:
        beta = _ridge_fit_multioutput(design, target_csm[:, None], ridge)[:, 0]
        residual = target_csm - design @ beta
        rmse = float(np.sqrt(np.mean(residual ** 2)))
        return rmse, (1.0 - rmse * rmse / variance if variance > 1.0e-20 else 1.0)
    rng = np.random.default_rng(seed)
    fold_of = rng.permutation(np.resize(np.arange(folds), n))
    prediction = np.empty(n, dtype=float)
    for fold in range(folds):
        test = fold_of == fold
        train = ~test
        beta = _ridge_fit_multioutput(design[train], target_csm[train, None], ridge)
        prediction[test] = design[test] @ beta[:, 0]
    residual = target_csm - prediction
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    return rmse, (1.0 - rmse * rmse / variance if variance > 1.0e-20 else 1.0)


# ============================================================================
# Rewritten backward induction -- gas-storage inventory grid + inter-node delta
# ============================================================================

def _backward_induction(
    data: PortfolioPathData,
    action_indices: IntArray,
    *,
    folds: int,
    ridge: float,
    seed: int,
    inventory_nodes: int = 25,
    inventory_quantile_clip: float = 0.005,
) -> BackwardResult:
    """Gas-storage-style account-value grid backward induction for the cap.

    This recursion mirrors the regression-Monte-Carlo method used to value gas
    storage contracts (Boogert & de Jong, 2008, *Gas Storage Valuation Using a
    Monte Carlo Method*; Carmona & Ludkovski, 2010, *Valuation of energy
    storage: an optimal switching approach*).  The customer account value per
    initial premium is the endogenous inventory (the "storage level"),
    discretised onto an adaptive grid ``A_0 < ... < A_K`` (the ``Gitter``).  The
    annual crediting cap is the injection control: it governs how much
    reference-fund return is credited into the fund (the injected volume), while
    dynamic income and withdrawals draw the fund down.

    The value function is carried **on the account-value grid**: after year
    ``y + 1`` it is stored as one ridge regression on the exogenous
    market/portfolio state per grid node (Boogert & de Jong: a separate
    regression per storage level).  At year ``y`` and each grid node the optimal
    cap maximises the one-step insurer reward plus the continuation value looked
    up at the *resulting* account value; the account-value transition per cap is
    an empirical ridge regression (crediting with fees, mortality, dynamic
    income and withdrawals is not closed-form, unlike the analytic gas
    ``v -> v + dv`` transition), and the continuation is the grid value function
    **interpolated** at that resulting level.  The interpolation uses the delta
    between neighbouring nodes ``V(A_{k+1}) - V(A_k)`` -- the discrete marginal
    value of account value (the storage shadow price ``dV/dA``) -- which is what
    makes the continuation sensitive to where the fund lands and therefore what
    drives the optimal cap.  Piecewise-linear interpolation with boundary
    clamping keeps the continuation bounded, so the backward recursion is a
    contraction and stays numerically stable over the full lifetime horizon.

    To avoid a look-ahead / Jensen bias, the continuation entering the per-cap
    maximisation is the **conditional expectation given the current-year state**,
    ``E[V_{k+1}(node, X_{k+1}) | X_k]``, estimated by regressing the realised
    next-year node values onto the current exogenous state (the regress-later
    device).  Thus the cap is chosen from current-state-measurable continuations
    only, not from the realised next-year market state.  The reported first-year
    value uses the direct realised-action estimator (a Monte Carlo average with
    no maximisation, hence unbiased) with the realised grid continuation.

    For downstream deployment the recursion emits, per active policy year, a
    :class:`RegressionPolicyYear` whose per-cap Q-function
    ``design(x) @ coefficients[a]`` reproduces the grid-optimal value at each
    path's own account value, so the unchanged causal monthly-projection
    rollout, plots and JSON payload continue to work.  Per-cap out-of-fold
    diagnostics are reported.
    """
    if data.raw_states is None:
        raise ValueError("Backward induction requires recorded state paths.")
    if data.inforce_exposure is None:
        raise ValueError("Backward induction requires in-force exposure paths.")
    n_paths, n_years = data.new_business_csm_proxy.shape
    if action_indices.shape != (n_paths, n_years):
        raise ValueError("Action indices and projected rewards are inconsistent.")
    feature_names = tuple(data.state_feature_names)
    raw_states = np.asarray(data.raw_states, dtype=float)
    if raw_states.shape[0] != n_paths or raw_states.shape[1] < n_years + 1:
        raise ValueError("Recorded state paths are shape-inconsistent.")
    exposure = np.asarray(data.inforce_exposure, dtype=float)
    inventory_index = _inventory_feature_index(feature_names)
    exogenous_names, exogenous_columns = _exogenous_feature_layout(
        feature_names, inventory_index
    )
    account_value = raw_states[:, :, inventory_index]  # (n_paths, n_years + 1)
    exogenous_nonlinear, exogenous_interactions, _ = _basis_specification(
        exogenous_names
    )

    nonlinear_full, interactions_full, basis_names_full = _basis_specification(
        feature_names
    )
    minimum_training_count = max(30, 3 * len(basis_names_full))
    n_actions = len(ACTION_CAPS)

    # Component reward tensor: index 0 is CSM, 1..9 the auditable components.
    immediate = _portfolio_continue_component_tensor(data)  # (n_paths, n_years, 10)

    active_year_indices = [
        year for year in range(n_years) if np.any(exposure[:, year] > 0.0)
    ]
    if not active_year_indices:
        raise RuntimeError(
            "The control-randomisation portfolio has no active policy year."
        )
    last_active = active_year_indices[-1]
    active_set = set(active_year_indices)

    LOGGER.info(
        "Gas-storage account-value grid backward induction | %d years | "
        "%d caps | %d paths | %d requested inventory nodes",
        n_years, n_actions, n_paths, inventory_nodes,
    )

    # Inventory grid pooled over all active decision times where the fund is in
    # force, so node density follows the realised account-value distribution.
    pooled_av = np.concatenate([
        account_value[exposure[:, year] > 0.0, year]
        for year in active_year_indices
    ])
    grid = _account_value_grid(pooled_av, inventory_nodes, inventory_quantile_clip)
    n_nodes = grid.shape[0]
    LOGGER.info(
        "Account-value inventory grid | %d nodes | span [%.4f, %.4f] per premium",
        n_nodes, float(grid[0]), float(grid[-1]),
    )

    year_values: dict[int, _GridYearValue] = {}
    policy_years: list[RegressionPolicyYear] = []
    regression_rows: list[dict[str, object]] = []
    policy_year_rows: list[dict[str, object]] = []
    first_year_action_rows: list[dict[str, object]] = []
    numerical_reasons: set[str] = set()
    first_cap = float("nan")
    first_outputs = np.zeros(10)
    first_se = float("nan")

    for year in range(n_years - 1, -1, -1):
        year_exposure = exposure[:, year]
        if not np.any(year_exposure > 0.0):
            residual_magnitude = max(
                float(np.max(np.abs(immediate[:, year, :]))),
                max(
                    (float(np.max(np.abs(v.node_coefficients)))
                     for v in year_values.values()),
                    default=0.0,
                ),
            )
            materiality = 1.0e-8 * data.representative_initial_premium
            if residual_magnitude > materiality:
                raise RuntimeError(
                    "Policy year %d has zero in-force exposure but residual "
                    "objective magnitude %.6g. Refusing to discard a material "
                    "continuation value." % (year + 1, residual_magnitude)
                )
            LOGGER.debug(
                "Gas-storage backward induction | policy year %d inactive.",
                year + 1,
            )
            continue

        if year == last_active or year == 0 or (year + 1) % 5 == 0:
            LOGGER.info(
                "Gas-storage backward induction | policy year %d/%d",
                year + 1, n_years,
            )

        raw_year = raw_states[:, year, :]
        exogenous_year = raw_year[:, exogenous_columns]
        observed = action_indices[:, year]
        mean_full, scale_full = _raw_scaling(raw_year)
        design_own = _design_matrix(
            raw_year, mean_full, scale_full, nonlinear_full, interactions_full
        )
        has_continuation = (year + 1) in active_set

        # Grid value function at the realised next-year exogenous state: this is
        # the direct sample used by the unbiased year-0 estimator and the basis
        # for the conditional expectation used by the year>0 Bellman maximum.
        if has_continuation:
            node_next_realised = _evaluate_grid_continuation(
                year_values[year + 1],
                raw_states[:, year + 1, exogenous_columns],
                exogenous_names,
            )  # (n_paths, n_nodes, 9)
        else:
            node_next_realised = np.zeros((n_paths, n_nodes, 9))

        # One reward (9 components) and one account-value transition regression
        # per cap, on the paths that explored that cap this year.
        reward_beta = np.zeros((n_actions, design_own.shape[1], 9))
        transition_beta = np.zeros((n_actions, design_own.shape[1]))
        deployable = np.ones(n_actions, dtype=bool)
        action_counts = np.zeros(n_actions, dtype=np.int64)
        for action in range(n_actions):
            selected = observed == action
            count = int(np.count_nonzero(selected))
            action_counts[action] = count
            if count < minimum_training_count:
                deployable[action] = False
                numerical_reasons.add(
                    f"policy_year_{year + 1}::cap_{ACTION_CAPS[action]:.6f}"
                    f"_support_{count}_below_{minimum_training_count}"
                )
                if count == 0:
                    raise ValueError(
                        "Too few training paths for policy year "
                        f"{year + 1}, cap {ACTION_CAPS[action]:.4%}: {count}. "
                        "Increase --n-paths."
                    )
            design_sel = design_own[selected]
            reward_beta[action] = _ridge_fit_multioutput(
                design_sel, immediate[selected, year, 1:], ridge
            )
            if has_continuation:
                transition_beta[action] = _ridge_fit_multioutput(
                    design_sel,
                    account_value[selected, year + 1][:, None],
                    ridge,
                )[:, 0]

        if year == 0:
            # Common initial state: report the optimal first cap and its value
            # from the direct realised-action estimator (a Monte Carlo average,
            # so unbiased) with the realised grid continuation, matching the
            # first-year row schema exactly.
            realised_value = immediate[:, 0, 1:].copy()
            if has_continuation:
                realised_continuation, _ = _grid_continuation_lookup(
                    node_next_realised, grid, account_value[:, 1]
                )
                realised_value = realised_value + realised_continuation
            realised_csm = _csm_from_component_values(realised_value)
            action_values = np.zeros((n_actions, 10))
            action_standard_errors = np.zeros(n_actions)
            for action in range(n_actions):
                sel = observed == action
                if not np.any(sel):
                    raise RuntimeError(
                        f"First-year coverage missing for cap {ACTION_CAPS[action]}."
                    )
                mean_components = np.mean(realised_value[sel], axis=0)
                action_values[action] = _with_derived_csm(mean_components[None, :])[0]
                action_standard_errors[action] = _standard_error(realised_csm[sel])
            chosen_action = int(_lower_cap_argmax(action_values[:, 0]))
            first_cap = float(ACTION_CAPS[chosen_action])
            first_outputs = action_values[chosen_action]
            first_se = float(action_standard_errors[chosen_action])
            LOGGER.info(
                "First-year gas-storage Bellman diagnostic | cap %.2f%% | "
                "Q-CSM %.2f | SE %.2f",
                100.0 * first_cap, first_outputs[0], first_se,
            )
            for action, cap in enumerate(ACTION_CAPS):
                values = action_values[action]
                first_year_action_rows.append({
                    "cap": float(cap),
                    "cap_percent": 100.0 * float(cap),
                    "selection_estimated_q_new_business_csm_proxy": float(values[0]),
                    "selection_standard_error_new_business_csm_proxy": float(
                        action_standard_errors[action]
                    ),
                    "holdout_estimated_q_new_business_csm_proxy": float(values[0]),
                    "holdout_estimated_q_fees_product": float(values[1]),
                    "holdout_estimated_q_fees_lip": float(values[2]),
                    "holdout_estimated_q_crediting_margin": float(values[3]),
                    "holdout_estimated_q_mva_retained": float(values[4]),
                    "holdout_estimated_q_aps_retained": float(values[5]),
                    "holdout_estimated_q_guarantee_claims": float(values[6]),
                    "holdout_estimated_q_other_insurer_funded_benefits": float(
                        values[7]
                    ),
                    "holdout_estimated_q_expenses": float(values[8]),
                    "holdout_estimated_q_hedge_costs": float(values[9]),
                    "holdout_standard_error_new_business_csm_proxy": float(
                        action_standard_errors[action]
                    ),
                    "selection_path_count": int(action_counts[action]),
                    "holdout_path_count": int(action_counts[action]),
                    "observed_control_action_path_count": int(action_counts[action]),
                    "selection_value_semantics": (
                        "direct realised-action target with gas-storage grid "
                        "continuation"
                    ),
                    "holdout_value_semantics": (
                        "alias of the direct realised-action target; deployment is "
                        "decided on the independent validation sample"
                    ),
                    "economically_active": True,
                    "is_optimal_first_year_cap": action == chosen_action,
                    "outer_fold_pure": False,
                    "csm_derived_from_components": True,
                })
            first_policy = _constant_first_year_policy(
                year=0,
                raw_state=raw_states[:, 0, :],
                action_values=action_values,
                action_standard_errors=action_standard_errors,
                feature_names=feature_names,
                numerically_stable=True,
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
                "mean_inforce_exposure": float(np.mean(year_exposure)),
                "outer_fold_pure": False,
            })
            continue

        # Conditional expectation of the node values given the current-year
        # state (regress-later): removes the look-ahead / Jensen bias while
        # keeping the bounded grid interpolation that makes the recursion stable.
        if has_continuation:
            mean_exogenous, scale_exogenous = _raw_scaling(exogenous_year)
            design_exogenous = _design_matrix(
                exogenous_year, mean_exogenous, scale_exogenous,
                exogenous_nonlinear, exogenous_interactions,
            )
            conditional_beta = _ridge_fit_multioutput(
                design_exogenous,
                node_next_realised.reshape(n_paths, n_nodes * 9),
                ridge,
            )
            node_next = (design_exogenous @ conditional_beta).reshape(
                n_paths, n_nodes, 9
            )
        else:
            node_next = np.zeros((n_paths, n_nodes, 9))

        # Value iteration across the inventory grid: at each forced node the
        # optimal cap maximises reward + interpolated (bounded) continuation.
        node_value_target = np.zeros((n_paths, n_nodes, 9))
        for node, level in enumerate(grid):
            forced = _force_inventory(raw_year, inventory_index, float(level))
            design_node = _design_matrix(
                forced, mean_full, scale_full, nonlinear_full, interactions_full
            )
            reward_node = np.einsum("pb,abo->pao", design_node, reward_beta)
            if has_continuation:
                next_level = np.einsum("pb,ab->pa", design_node, transition_beta)
                continuation_node = np.empty((n_paths, n_actions, 9))
                for action in range(n_actions):
                    continuation_node[:, action, :], _ = _grid_continuation_lookup(
                        node_next, grid, next_level[:, action]
                    )
            else:
                continuation_node = np.zeros((n_paths, n_actions, 9))
            q_node = reward_node + continuation_node
            csm_node = _csm_from_component_values(q_node)  # (n_paths, n_actions)
            if not np.all(np.isfinite(csm_node)):
                raise RuntimeError(
                    f"Non-finite node Q values at policy year {year + 1}."
                )
            best = (
                _masked_lower_cap_argmax(csm_node, deployable, axis=1)
                if np.any(deployable) else np.zeros(n_paths, dtype=np.int64)
            )
            node_value_target[:, node, :] = np.take_along_axis(
                q_node, best[:, None, None], axis=1
            )[:, 0, :]
        year_values[year] = _fit_grid_continuation(
            exogenous_year, node_value_target, exogenous_names, ridge
        )
        node_csm_curve = _csm_from_component_values(np.mean(node_value_target, axis=0))
        marginal_value = np.diff(node_csm_curve) / np.maximum(np.diff(grid), 1.0e-12)
        LOGGER.debug(
            "Policy year %d | inventory marginal value dV/dA in [%.3f, %.3f] | "
            "mean %.3f (per unit account value)",
            year + 1, float(np.min(marginal_value)),
            float(np.max(marginal_value)), float(np.mean(marginal_value)),
        )

        # Deployable per-cap Q-function at each path's own account value.
        reward_own = np.einsum("pb,abo->pao", design_own, reward_beta)
        if has_continuation:
            next_level_own = np.einsum("pb,ab->pa", design_own, transition_beta)
            continuation_own = np.empty((n_paths, n_actions, 9))
            for action in range(n_actions):
                continuation_own[:, action, :], _ = _grid_continuation_lookup(
                    node_next, grid, next_level_own[:, action]
                )
        else:
            continuation_own = np.zeros((n_paths, n_actions, 9))
        q_own = reward_own + continuation_own  # (n_paths, n_actions, 9)
        csm_own = _csm_from_component_values(q_own)  # (n_paths, n_actions)

        # Project the (interpolation-nonlinear) per-cap Q onto the deployment
        # basis; CSM (output 0) follows by linearity of the component rows.
        q_flat = q_own.reshape(n_paths, n_actions * 9)
        beta_flat = _ridge_fit_multioutput(design_own, q_flat, ridge)
        deploy_component_beta = np.transpose(
            beta_flat.reshape(design_own.shape[1], n_actions, 9), (1, 0, 2)
        )  # (n_actions, basis, 9)
        deploy_coefficients = _component_regression_coefficients(deploy_component_beta)
        if not np.all(np.isfinite(deploy_coefficients)):
            raise RuntimeError(
                f"Non-finite deployment coefficients at policy year {year + 1}."
            )

        action_standard_errors = np.zeros(n_actions)
        chosen = (
            _masked_lower_cap_argmax(csm_own, deployable, axis=1)
            if np.any(deployable) else np.zeros(n_paths, dtype=np.int64)
        )
        selected_caps = ACTION_CAPS[chosen]
        mean_cap = float(np.mean(selected_caps))
        quantiles = np.quantile(selected_caps, (0.10, 0.50, 0.90))
        mean_inforce = float(np.mean(year_exposure))
        for action, cap in enumerate(ACTION_CAPS):
            sel = observed == action
            design_sel = design_own[sel]
            target_csm = csm_own[sel, action]
            fitted_csm = design_sel @ deploy_coefficients[action, :, 0]
            residual = target_csm - fitted_csm
            rmse = float(np.sqrt(np.mean(residual ** 2))) if residual.size else 0.0
            action_standard_errors[action] = rmse / np.sqrt(max(residual.size, 1))
            oof_rmse, oof_r2 = _kfold_oof_csm_diagnostics(
                design_sel, target_csm, folds, ridge, seed + action + 101 * year
            )
            condition = _condition_number(design_sel, ridge)
            regression_rows.append({
                "policy_year": year + 1,
                "cap": float(cap),
                "observed_path_count": int(action_counts[action]),
                "basis_dimension": int(design_own.shape[1]),
                "ridge_multiplier": float(ridge),
                "out_of_fold_rmse_new_business_csm_proxy": float(oof_rmse),
                "out_of_fold_r_squared_new_business_csm_proxy": float(oof_r2),
                "in_sample_component_clip_fraction": 0.0,
                "maximum_fold_component_clip_fraction": 0.0,
                "counterfactual_component_clip_fraction": 0.0,
                "maximum_fold_counterfactual_component_clip_fraction": 0.0,
                "action_mask_in_support_clip_threshold": 0.20,
                "regularized_normal_matrix_condition_number": float(condition),
                "design_condition_number": float(condition),
                "deployable_for_frozen_policy": bool(deployable[action]),
                "action_fit_mask_reasons": "" if deployable[action] else (
                    f"support_{action_counts[action]}_below_{minimum_training_count}"
                ),
                "csm_derived_from_components": True,
                "outer_fold_pure": False,
                "selected_fraction_cross_fitted": float(np.mean(chosen == action)),
                "economically_active": True,
            })
            policy_year_rows.append({
                "policy_year": year + 1,
                "cap": float(cap),
                "selected_fraction": float(np.mean(chosen == action)),
                "mean_selected_cap": mean_cap,
                "p10_selected_cap": float(quantiles[0]),
                "median_selected_cap": float(quantiles[1]),
                "p90_selected_cap": float(quantiles[2]),
                "economically_active": True,
                "mean_inforce_exposure": mean_inforce,
                "outer_fold_pure": False,
            })

        policy_years.append(RegressionPolicyYear(
            year=year,
            raw_mean=mean_full,
            raw_scale=scale_full,
            coefficients=deploy_coefficients,
            action_caps=ACTION_CAPS.copy(),
            action_value_standard_error=action_standard_errors,
            numerically_stable=bool(np.all(deployable)),
            action_deployable_mask=deployable,
        ))

    policy_years.sort(key=lambda item: item.year)
    active_policy_years = sorted(year + 1 for year in active_year_indices)
    if not active_policy_years or active_policy_years[0] != 1:
        raise RuntimeError(
            "The control-randomisation portfolio has no active first policy year."
        )
    if active_policy_years != list(range(1, active_policy_years[-1] + 1)):
        raise RuntimeError(
            "In-force exposure becomes positive after an inactive policy year; "
            "the economic policy horizon is not contiguous."
        )
    component_csm = _csm_from_component_values(first_outputs[1:][None, :])[0]
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
        numerically_stable=not numerical_reasons,
        numerical_fallback_reasons=tuple(sorted(numerical_reasons)),
    )


def _benchmark_cases() -> list[tuple[str, float, str]]:
    # Thinned comparator grid: the 0.25% guaranteed-minimum cap, every third
    # per-cent cap from 1% to 19% and the uncapped extreme.  The zero-crediting
    # case was dropped as a benchmark.
    cases: list[tuple[str, float, str]] = [
        (
            "fixed_cap_0.25pct",
            0.0025,
            "same 0.25% cap in every crediting year",
        ),
    ]
    cases.extend(
        (
            f"fixed_cap_{percent}pct",
            percent / 100.0,
            f"same {percent}% cap in every crediting year",
        )
        for percent in range(1, 21, 3)
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
        "money_market_income",
        "hedge_gain",
        "mva_retained",
        "aps_retained",
        "guarantee_claims",
        "other_insurer_funded_benefits",
        "expenses",
        "hedge_costs",
        "income_paid",
        "death_benefits",
        "surrender_benefits",
        "partial_withdrawals",
        "terminal_closeout",
        "lapse_events",
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

    def component(name: str) -> Array:
        return np.asarray(
            components.get(name, np.zeros_like(csm_paths)), dtype=float
        )

    def mean_pv(name: str) -> float:
        return portfolio_scale * float(np.mean(component(name)))

    fee_income = components["fees_product"] + components["fees_lip"]
    other_income = (
        components["money_market_income"]
        + components["hedge_gain"]
        + components["mva_retained"]
        + components["aps_retained"]
    )
    claims = (
        components["guarantee_claims"]
        + components["other_insurer_funded_benefits"]
    )
    costs = components["expenses"] + components["hedge_costs"]
    reconstructed_csm = fee_income + other_income - claims - costs
    reconciliation = csm_paths - reconstructed_csm
    crediting_margin_reconciliation = (
        components["crediting_margin"]
        - components["money_market_income"]
        - components["hedge_gain"]
    )
    lapse_events = np.asarray(
        components.get("lapse_events", np.zeros_like(csm_paths)),
        dtype=float,
    )
    policyholder_benefits = (
        component("income_paid")
        + component("death_benefits")
        + component("surrender_benefits")
        + component("partial_withdrawals")
        + component("terminal_closeout")
    )
    return {
        "case": label,
        "cap": cap,
        "cap_percent": None if cap is None else 100.0 * cap,
        "definition": definition,
        "pv_product_fees_aud": mean_pv("fees_product"),
        "pv_lip_fees_aud": mean_pv("fees_lip"),
        "pv_fee_income_aud": portfolio_scale * float(np.mean(fee_income)),
        "pv_future_fees_aud": portfolio_scale * float(np.mean(fee_income)),
        "pv_crediting_margin_aud": mean_pv("crediting_margin"),
        "pv_money_market_income_aud": mean_pv("money_market_income"),
        "pv_hedge_gain_aud": mean_pv("hedge_gain"),
        "pv_mva_retained_aud": mean_pv("mva_retained"),
        "pv_aps_retained_aud": mean_pv("aps_retained"),
        "pv_other_income_aud": portfolio_scale * float(np.mean(other_income)),
        "pv_other_insurer_margins_aud": portfolio_scale * float(
            np.mean(other_income)
        ),
        "pv_total_insurer_inflows_aud": portfolio_scale * float(np.mean(
            fee_income + other_income
        )),
        "pv_guarantee_claims_aud": mean_pv("guarantee_claims"),
        "pv_other_insurer_funded_benefits_aud": mean_pv(
            "other_insurer_funded_benefits"
        ),
        "pv_claims_aud": portfolio_scale * float(np.mean(claims)),
        "pv_total_insurer_funded_benefits_aud": portfolio_scale * float(
            np.mean(claims)
        ),
        "pv_expenses_aud": mean_pv("expenses"),
        "pv_hedge_costs_aud": mean_pv("hedge_costs"),
        "pv_costs_aud": portfolio_scale * float(np.mean(costs)),
        "pv_total_costs_aud": portfolio_scale * float(np.mean(costs)),
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
        "crediting_margin_reconciliation_gap_aud": (
            portfolio_scale * float(np.mean(crediting_margin_reconciliation))
        ),
        "crediting_margin_reconciliation_max_absolute_aud": (
            portfolio_scale * float(
                np.max(np.abs(crediting_margin_reconciliation))
            )
        ),
        "pv_terminal_closeout_excluded_aud": mean_pv("terminal_closeout"),
        "pv_policyholder_benefits_aud": portfolio_scale * float(
            np.mean(policyholder_benefits)
        ),
        "pv_policyholder_income_aud": mean_pv("income_paid"),
        "pv_policyholder_death_benefits_aud": mean_pv("death_benefits"),
        "pv_policyholder_surrender_benefits_aud": mean_pv(
            "surrender_benefits"
        ),
        "pv_policyholder_partial_withdrawals_aud": mean_pv(
            "partial_withdrawals"
        ),
        "expected_cumulative_full_surrender_probability": float(
            np.mean(lapse_events)
        ),
        "expected_cumulative_full_surrenders_scaled_contract_count": (
            portfolio_scale * float(np.mean(lapse_events))
        ),
        "new_business_csm_difference_vs_best_fixed_admissible_aud": float(
            np.mean(difference)
        ),
        "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud": (
            _standard_error(difference)
        ),
        "is_best_fixed_cap_admissible_grid": is_best_fixed,
        "n_common_random_number_paths": int(csm_paths.size),
    }


def _projection_input_fingerprint(args: argparse.Namespace) -> str:
    """Content hash of every non-market projection input.

    The fixed-cap benchmark projections are a deterministic function of the
    market scenarios (captured by their content fingerprint and the projector
    seeds), the cap and these assumption inputs.  Hashing the input file bytes
    makes the benchmark cache key change whenever any assumption changes, so a
    stale cached result can never be reused.
    """
    digest = hashlib.sha256()
    digest.update(ENGINE_VERSION.encode("utf-8"))
    for path in (
        args.model_points, args.cost_assumptions,
        args.zero_curve, args.model_parameters,
    ):
        digest.update(b"|file|")
        digest.update(str(path).encode("utf-8"))
        digest.update(Path(path).read_bytes())
    behaviour_directory = Path(args.dynamic_behaviour)
    for path in sorted(
        item for item in behaviour_directory.rglob("*") if item.is_file()
    ):
        digest.update(b"|behaviour|")
        digest.update(
            str(path.relative_to(behaviour_directory)).encode("utf-8")
        )
        digest.update(path.read_bytes())
    for value in (
        args.cost_assumption_set, args.behaviour_assumption_set,
        args.behaviour_value_basis, args.performance_gap_behaviour,
    ):
        digest.update(f"|{value}".encode("utf-8"))
    return digest.hexdigest()


def _benchmark_cache_path(
    cache_dir: Path,
    projection_fingerprint: str,
    *,
    selection_scenarios: ScenarioSet,
    evaluation_scenarios: ScenarioSet,
    selection_projection_config: ProjectionConfig,
    evaluation_projection_config: ProjectionConfig,
    cap: float,
    n_years: int,
) -> Path:
    """Deterministic cache path for one fixed-cap benchmark case."""
    def sample_fingerprint(
        scenarios: ScenarioSet, config: ProjectionConfig
    ) -> str:
        return hashlib.sha256((
            scenarios.content_fingerprint
            + f"|take_up={config.take_up_seed}"
            + f"|mortality={config.mortality_seed}"
        ).encode("ascii")).hexdigest()

    key = hashlib.sha256((
        f"{projection_fingerprint}"
        f"|sel={sample_fingerprint(selection_scenarios, selection_projection_config)}"
        f"|evl={sample_fingerprint(evaluation_scenarios, evaluation_projection_config)}"
        f"|cap={cap!r}|n_years={int(n_years)}"
    ).encode("ascii")).hexdigest()
    return cache_dir / f"benchmark_{key}.npz"


def _store_benchmark_cache(
    path: Path,
    selection_csm: Array,
    evaluation_csm: Array,
    evaluation_components: Mapping[str, Array],
) -> None:
    arrays = {
        "selection_csm": np.asarray(selection_csm, dtype=float),
        "evaluation_csm": np.asarray(evaluation_csm, dtype=float),
    }
    for name, values in evaluation_components.items():
        arrays[f"component__{name}"] = np.asarray(values, dtype=float)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "wb") as handle:
        np.savez(handle, **arrays)
    temporary.replace(path)


def _load_benchmark_cache(
    path: Path,
) -> tuple[Array, Array, dict[str, Array]]:
    with np.load(path) as data:
        selection_csm = np.asarray(data["selection_csm"], dtype=float)
        evaluation_csm = np.asarray(data["evaluation_csm"], dtype=float)
        components = {
            name[len("component__"):]: np.asarray(data[name], dtype=float)
            for name in data.files
            if name.startswith("component__")
        }
    return selection_csm, evaluation_csm, components


def _evaluate_fixed_benchmarks(
    *,
    selection_scenarios: ScenarioSet,
    evaluation_scenarios: ScenarioSet,
    n_years: int,
    product: IndexLinkedLifetimeIncomeProduct,
    model_points: PolicyholderModelPointSet,
    behaviour: BehaviourModel,
    mortality: MortalityTable,
    expenses: ExpenseAssumptions,
    selection_projection_config: ProjectionConfig,
    evaluation_projection_config: ProjectionConfig,
    portfolio_scale: float,
    model_point_log_interval: int,
    cache_dir: Optional[Path] = None,
    projection_fingerprint: str = "",
) -> tuple[
    list[dict[str, object]],
    dict[str, Array],
    dict[str, Array],
    str,
    dict[str, object],
]:
    """Select fixed cap on one sample and report it on an independent sample."""
    cases = _benchmark_cases()
    if selection_scenarios.n_paths <= 0 or evaluation_scenarios.n_paths <= 0:
        raise ValueError("Fixed-cap sample roles must both contain paths.")
    evaluation_path_values: dict[str, Array] = {}
    selection_path_values: dict[str, Array] = {}
    evaluation_component_paths: dict[str, dict[str, Array]] = {}
    # Dynamic Take-up and pathwise Joint-Life mortality use seeded projector
    # draws.  Project cases separately so every cap sees the same draws; simply
    # stacking repeated market paths would generate different Behaviour draws
    # for each stacked block and would not be a true CRN comparison.
    LOGGER.info(
        "Fixed-cap benchmarks | %d cases | selection paths=%d | "
        "evaluation paths=%d",
        len(cases), selection_scenarios.n_paths, evaluation_scenarios.n_paths,
    )

    for case_number, (label, cap, _) in enumerate(cases, start=1):
        case_started = time.perf_counter()
        LOGGER.info(
            "Benchmark case %d/%d | %s", case_number, len(cases), label
        )
        cache_path = (
            _benchmark_cache_path(
                cache_dir, projection_fingerprint,
                selection_scenarios=selection_scenarios,
                evaluation_scenarios=evaluation_scenarios,
                selection_projection_config=selection_projection_config,
                evaluation_projection_config=evaluation_projection_config,
                cap=cap, n_years=n_years,
            )
            if cache_dir is not None else None
        )
        if cache_path is not None and cache_path.exists():
            try:
                (
                    selection_path_values[label],
                    evaluation_path_values[label],
                    evaluation_component_paths[label],
                ) = _load_benchmark_cache(cache_path)
                LOGGER.info(
                    "Benchmark case %d/%d complete | reused cached projection",
                    case_number, len(cases),
                )
                continue
            except Exception as error:  # noqa: BLE001 - cache must never be fatal
                LOGGER.warning(
                    "Benchmark cache read failed for %s (%s); recomputing.",
                    label, error,
                )
        selection_projected = _aggregate_portfolio_paths(
            scenarios=selection_scenarios,
            cap_matrix=np.full(
                (selection_scenarios.n_paths, n_years), cap, dtype=float
            ),
            product=product,
            model_points=model_points,
            behaviour=behaviour,
            mortality=mortality,
            expenses=expenses,
            projection_config=selection_projection_config,
            collect_states=False,
            progress_label=(
                f"Fixed-cap selection {case_number}/{len(cases)}"
            ),
            model_point_log_interval=model_point_log_interval,
        )
        evaluation_projected = _aggregate_portfolio_paths(
            scenarios=evaluation_scenarios,
            cap_matrix=np.full(
                (evaluation_scenarios.n_paths, n_years), cap, dtype=float
            ),
            product=product,
            model_points=model_points,
            behaviour=behaviour,
            mortality=mortality,
            expenses=expenses,
            projection_config=evaluation_projection_config,
            collect_states=False,
            progress_label=(
                f"Fixed-cap evaluation {case_number}/{len(cases)}"
            ),
            model_point_log_interval=model_point_log_interval,
        )
        selection_path_values[label] = np.sum(
            selection_projected.new_business_csm_proxy, axis=1
        )
        evaluation_path_values[label] = np.sum(
            evaluation_projected.new_business_csm_proxy, axis=1
        )
        evaluation_component_paths[label] = _summed_csm_components(
            evaluation_projected, slice(None)
        )
        if cache_path is not None:
            try:
                _store_benchmark_cache(
                    cache_path,
                    selection_path_values[label],
                    evaluation_path_values[label],
                    evaluation_component_paths[label],
                )
            except Exception as error:  # noqa: BLE001 - cache must never be fatal
                LOGGER.warning(
                    "Benchmark cache write failed for %s (%s).", label, error
                )
        LOGGER.info(
            "Benchmark case %d/%d complete | elapsed %.1fs",
            case_number, len(cases), time.perf_counter() - case_started,
        )

    fixed_labels = [
        label
        for label, cap, _ in cases
        if label.startswith("fixed_cap_")
        and np.any(np.isclose(cap, ACTION_CAPS))
    ]
    best_label = max(
        fixed_labels,
        key=lambda label: float(np.mean(selection_path_values[label])),
    )
    best_paths = evaluation_path_values[best_label]
    selection_means = {
        label: portfolio_scale * float(np.mean(selection_path_values[label]))
        for label in fixed_labels
    }
    LOGGER.info(
        "Best fixed admissible benchmark selected independently | %s | "
        "selection CSM %.2f | evaluation CSM %.2f",
        best_label,
        selection_means[best_label],
        portfolio_scale * float(np.mean(best_paths)),
    )
    rows: list[dict[str, object]] = []
    for label, cap, definition in cases:
        csm_paths = evaluation_path_values[label]
        components = evaluation_component_paths[label]
        row = _csm_benchmark_row(
            label=label,
            cap=None if np.isposinf(cap) else float(cap),
            definition=definition,
            components=components,
            csm_paths=csm_paths,
            best_fixed_paths=best_paths,
            portfolio_scale=portfolio_scale,
            is_best_fixed=label == best_label,
        )
        row["fixed_cap_selection_sample_csm_aud"] = (
            selection_means.get(label)
        )
        row["n_fixed_cap_selection_paths"] = selection_scenarios.n_paths
        row["n_final_evaluation_paths"] = evaluation_scenarios.n_paths
        row["sample_role"] = "final_evaluation"
        rows.append(row)
        LOGGER.debug(
            "Benchmark result | %s | fee income=%.2f | other income=%.2f | "
            "claims=%.2f | expenses=%.2f | hedge costs=%.2f | "
            "CSM proxy=%.2f | SE=%.2f | terminal closeout excluded=%.2f",
            label,
            row["pv_fee_income_aud"],
            row["pv_other_income_aud"],
            row["pv_claims_aud"],
            row["pv_expenses_aud"],
            row["pv_hedge_costs_aud"],
            row["estimated_new_business_csm_proxy_aud"],
            row["standard_error_new_business_csm_proxy_aud"],
            row["pv_terminal_closeout_excluded_aud"],
        )
    selection_metadata = {
        "selection_path_count": selection_scenarios.n_paths,
        "evaluation_path_count": evaluation_scenarios.n_paths,
        "best_fixed_selection_csm_aud": selection_means[best_label],
        "selection_market_scenario_fingerprint": (
            selection_scenarios.content_fingerprint
        ),
        "evaluation_market_scenario_fingerprint": (
            evaluation_scenarios.content_fingerprint
        ),
        "selection_take_up_seed": selection_projection_config.take_up_seed,
        "selection_mortality_seed": selection_projection_config.mortality_seed,
        "evaluation_take_up_seed": evaluation_projection_config.take_up_seed,
        "evaluation_mortality_seed": evaluation_projection_config.mortality_seed,
        "common_random_numbers_within_each_sample": True,
    }
    return (
        rows,
        evaluation_path_values,
        selection_path_values,
        best_label,
        selection_metadata,
    )


def _policyholder_signature_validation(
    *,
    candidate: PortfolioPathData,
    comparator: PortfolioPathData,
    path_slice: slice,
    policy_label: str,
    cap: float | None,
    portfolio_scale: float,
    sample_fingerprint: str,
) -> tuple[list[dict[str, object]], set[tuple[object, ...]]]:
    """Paired Policyholder-value gate, kept separate by PolicySpec signature."""
    candidate_keys = set(candidate.policyholder_benefits_by_signature)
    comparator_keys = set(comparator.policyholder_benefits_by_signature)
    if candidate_keys != comparator_keys or not candidate_keys:
        raise RuntimeError(
            "Signature-separated Policyholder validation ledgers are missing "
            "or inconsistent."
        )
    rows: list[dict[str, object]] = []
    failed: set[tuple[object, ...]] = set()
    for signature in sorted(candidate_keys, key=repr):
        candidate_paths = np.sum(
            candidate.policyholder_benefits_by_signature[signature], axis=1
        )[path_slice]
        comparator_paths = np.sum(
            comparator.policyholder_benefits_by_signature[signature], axis=1
        )[path_slice]
        delta = portfolio_scale * (candidate_paths - comparator_paths)
        mean, standard_error = _paired_mean_and_standard_error(delta)
        lower = mean - 1.96 * standard_error
        rejected = bool(lower < -1.0e-10)
        if rejected:
            failed.add(signature)
        signature_text = json.dumps(
            signature, default=str, separators=(",", ":")
        )
        rows.append({
            "policy": policy_label,
            "cap": cap,
            "cap_percent": None if cap is None else 100.0 * cap,
            "policy_signature": signature_text,
            "policy_signature_fingerprint": hashlib.sha256(
                signature_text.encode("utf-8")
            ).hexdigest(),
            "sample": "validation",
            "sample_fingerprint": sample_fingerprint,
            "sample_path_count": int(delta.size),
            "policyholder_pv_difference_vs_continue_aud": mean,
            "paired_standard_error_aud": standard_error,
            "confidence_95pct_lower_aud": lower,
            "confidence_95pct_upper_aud": mean + 1.96 * standard_error,
            "continue_fallback_required": rejected,
            "selection_rule": (
                "fallback if the paired 95% lower confidence bound is negative"
            ),
        })
    return rows, failed


def _evaluate_fixed_lsmc_benchmarks(
    *,
    training_scenarios: ScenarioSet,
    evaluation_scenarios: ScenarioSet,
    n_years: int,
    product: IndexLinkedLifetimeIncomeProduct,
    model_points: PolicyholderModelPointSet,
    mortality: MortalityTable,
    expenses: ExpenseAssumptions,
    projection_config: ProjectionConfig,
    portfolio_scale: float,
    model_point_log_interval: int,
    selection_path_count: int,
    follower_settings: OptimalBehaviourLSMCSettings,
) -> tuple[
    list[dict[str, object]],
    dict[str, Array],
    dict[str, Array],
    str,
    dict[str, float],
    dict[str, PolicyholderFitSet],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Fresh, cap-consistent follower fit for every fixed/sanity cap.

    Training/cross-fitting uses ``training_scenarios`` only.  The first slice
    of ``evaluation_scenarios`` is reserved for signature-level follower
    validation and fixed-cap selection; the second slice is the untouched
    final sample.  All caps share common random numbers within each split.
    """
    if not 0 < selection_path_count < evaluation_scenarios.n_paths:
        raise ValueError("Fixed-LSMC selection must leave final evaluation paths.")
    no_actions = no_voluntary_action_behaviour()
    rows_by_label: dict[str, dict[str, object]] = {}
    all_paths: dict[str, Array] = {}
    all_components: dict[str, dict[str, Array]] = {}
    fit_sets: dict[str, PolicyholderFitSet] = {}
    exercise_rows: list[dict[str, object]] = []
    validation_rows: list[dict[str, object]] = []
    cases = _benchmark_cases()
    selection = slice(0, selection_path_count)
    final = slice(selection_path_count, None)
    validation_fingerprint = _slice_scenarios(
        evaluation_scenarios, 0, selection_path_count
    ).content_fingerprint
    LOGGER.info(
        "Fixed-cap follower LSMC | %d separately trained fixed/sanity caps",
        len(cases),
    )
    for number, (label, cap, definition) in enumerate(cases, start=1):
        LOGGER.info(
            "Fixed-cap follower LSMC %d/%d | cap=%.2f%%",
            number,
            len(cases),
            100.0 * cap,
        )
        train_caps = np.full(
            (training_scenarios.n_paths, n_years), cap, dtype=float
        )
        fit_set = _fit_cap_aware_policyholder_policies(
            cap_matrix=train_caps,
            scenarios=training_scenarios,
            product=product,
            model_points=model_points,
            mortality=mortality,
            expenses=expenses,
            projection_config=projection_config,
            settings=follower_settings,
            progress_label=f"Fixed follower {100.0 * cap:g}%",
        )
        fit_sets[label] = fit_set
        evaluation_caps = np.full(
            (evaluation_scenarios.n_paths, n_years), cap, dtype=float
        )
        projected = _aggregate_portfolio_paths(
            scenarios=evaluation_scenarios,
            cap_matrix=evaluation_caps,
            product=product,
            model_points=model_points,
            behaviour=no_actions,
            mortality=mortality,
            expenses=expenses,
            projection_config=projection_config,
            collect_states=True,
            progress_label=f"Fixed follower evaluation {100.0 * cap:g}%",
            model_point_log_interval=model_point_log_interval,
            surrender_policy_factory=fit_set.factory,
            collect_policyholder_by_signature=True,
        )
        continue_projected = _aggregate_portfolio_paths(
            scenarios=evaluation_scenarios,
            cap_matrix=evaluation_caps,
            product=product,
            model_points=model_points,
            behaviour=no_actions,
            mortality=mortality,
            expenses=expenses,
            projection_config=projection_config,
            collect_states=False,
            progress_label=(
                f"Fixed follower Continue validation {100.0 * cap:g}%"
            ),
            model_point_log_interval=model_point_log_interval,
            collect_policyholder_by_signature=True,
        )
        cap_validation_rows, failed_signatures = (
            _policyholder_signature_validation(
                candidate=projected,
                comparator=continue_projected,
                path_slice=selection,
                policy_label=f"fixed_lsmc::{label}",
                cap=float(cap),
                portfolio_scale=portfolio_scale,
                sample_fingerprint=validation_fingerprint,
            )
        )
        fit_set.validation_fallback_signatures.update(failed_signatures)
        if failed_signatures:
            LOGGER.warning(
                "Fixed-cap follower validation | cap=%s | %d signature(s) "
                "replaced by Continue before final evaluation",
                "uncapped" if np.isposinf(cap) else f"{100.0 * cap:g}%",
                len(failed_signatures),
            )
            projected = _aggregate_portfolio_paths(
                scenarios=evaluation_scenarios,
                cap_matrix=evaluation_caps,
                product=product,
                model_points=model_points,
                behaviour=no_actions,
                mortality=mortality,
                expenses=expenses,
                projection_config=projection_config,
                collect_states=True,
                progress_label=(
                    f"Validated fixed follower evaluation {100.0 * cap:g}%"
                ),
                model_point_log_interval=model_point_log_interval,
                surrender_policy_factory=fit_set.factory,
                collect_policyholder_by_signature=True,
            )
        deployed_by_signature = projected.policyholder_benefits_by_signature
        continue_by_signature = (
            continue_projected.policyholder_benefits_by_signature
        )
        by_fingerprint = {
            row["policy_signature_fingerprint"]: row
            for row in cap_validation_rows
        }
        for signature in sorted(deployed_by_signature, key=repr):
            signature_text = json.dumps(
                signature, default=str, separators=(",", ":")
            )
            fingerprint = hashlib.sha256(
                signature_text.encode("utf-8")
            ).hexdigest()
            post_delta = portfolio_scale * (
                np.sum(deployed_by_signature[signature], axis=1)[selection]
                - np.sum(continue_by_signature[signature], axis=1)[selection]
            )
            post_mean, post_se = _paired_mean_and_standard_error(post_delta)
            fitted = getattr(fit_set, "fits", {}).get(signature)
            training_fallback_steps = (
                set()
                if fitted is None
                else {
                    int(diagnostic.decision_step)
                    for diagnostic in fitted.diagnostics
                    if (
                        bool(fitted.training_fallback_used)
                        or not bool(
                            diagnostic.regression_accepted_for_exercise
                        )
                    )
                }
            )
            fallback_deployed = bool(
                signature in failed_signatures or training_fallback_steps
            )
            deployed_fallback_steps = set(training_fallback_steps)
            if signature in failed_signatures and fitted is not None:
                deployed_fallback_steps.update(
                    int(diagnostic.decision_step)
                    for diagnostic in fitted.diagnostics
                )
            by_fingerprint[fingerprint].update({
                "deployed_policyholder_pv_difference_vs_continue_aud": (
                    post_mean
                ),
                "deployed_paired_standard_error_aud": post_se,
                "deployed_confidence_95pct_lower_aud": (
                    post_mean - 1.96 * post_se
                ),
                "continue_fallback_deployed": (
                    fallback_deployed
                ),
                "training_continue_fallback_deployed": bool(
                    training_fallback_steps
                ),
                "continue_fallback_decision_step_count": (
                    len(deployed_fallback_steps)
                ),
            })
        validation_rows.extend(cap_validation_rows)
        components = _summed_csm_components(projected, slice(None))
        csm_paths = np.sum(projected.new_business_csm_proxy, axis=1)
        all_paths[label] = csm_paths
        all_components[label] = components
        rows_by_label[label] = {
            "case": label,
            "cap": float(cap),
            "definition": definition,
        }
        if projected.inforce_exposure is None:
            raise RuntimeError("Fixed-cap exercise reporting lacks exposure paths.")
        active_years = tuple(
            int(year + 1)
            for year in np.flatnonzero(
                np.any(projected.inforce_exposure > 0.0, axis=0)
            )
        )
        exercise_rows.extend(_policyholder_exercise_rows(
            label=f"fixed_lsmc::{label}",
            cap_matrix=evaluation_caps,
            projected=projected,
            active_policy_years=active_years,
            path_slice=final,
            cap_values=(float(cap),),
        ))

    admissible_labels = [
        label
        for label, cap, _ in cases
        if np.any(np.isclose(cap, ACTION_CAPS))
    ]
    admissible_selection_means = np.asarray([
        float(np.mean(all_paths[label][selection]))
        for label in admissible_labels
    ])
    best_label = admissible_labels[
        int(_lower_cap_argmax(admissible_selection_means))
    ]
    best_final_paths = all_paths[best_label][final]
    result_rows: list[dict[str, object]] = []
    for label, cap, definition in cases:
        components = {
            name: values[final]
            for name, values in all_components[label].items()
        }
        row = _csm_benchmark_row(
            label=label,
            cap=float(cap),
            definition=definition + "; cap-consistent follower LSMC",
            components=components,
            csm_paths=all_paths[label][final],
            best_fixed_paths=best_final_paths,
            portfolio_scale=portfolio_scale,
            is_best_fixed=label == best_label,
        )
        row.update({
            "fixed_cap_base_case": label,
            "policyholder_behaviour": "lsmc",
            "fixed_cap_selection_sample_csm_aud": (
                portfolio_scale * float(np.mean(all_paths[label][selection]))
            ),
            "n_fixed_cap_selection_paths": selection_path_count,
            "n_final_evaluation_paths": (
                evaluation_scenarios.n_paths - selection_path_count
            ),
            "policyholder_training_scenario_fingerprint": (
                training_scenarios.content_fingerprint
            ),
            "policyholder_training_cap_schedule_fingerprint": (
                fit_sets[label].cap_schedule_fingerprint
            ),
            "policyholder_training_fallback_signature_count": (
                fit_sets[label].fallback_count
            ),
        })
        result_rows.append(row)
    evaluation_values = {
        label: paths[final] for label, paths in all_paths.items()
    }
    selection_values = {
        label: paths[selection] for label, paths in all_paths.items()
    }
    metadata = {
        "selection_path_count": float(selection_path_count),
        "evaluation_path_count": float(
            evaluation_scenarios.n_paths - selection_path_count
        ),
        "best_fixed_selection_csm_aud": portfolio_scale * float(
            np.mean(all_paths[best_label][selection])
        ),
    }
    return (
        result_rows,
        evaluation_values,
        selection_values,
        best_label,
        metadata,
        fit_sets,
        exercise_rows,
        validation_rows,
    )


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


def _evaluate_pathwise_policy_benchmark(
    *,
    label: str,
    definition: str,
    cap_matrix: Array,
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
    surrender_policy_factory: Optional[Callable[[PolicySpec], object]] = None,
) -> tuple[dict[str, object], Array, PortfolioPathData]:
    """Directly project a frozen pathwise feedback-policy schedule."""
    caps = np.asarray(cap_matrix, dtype=float)
    if caps.ndim != 2 or caps.shape[0] != scenarios.n_paths:
        raise ValueError("Pathwise policy caps must match evaluation scenarios.")
    if not np.all(np.isfinite(caps)) or np.any(caps < ACTION_CAPS[0] - 1.0e-15):
        raise ValueError("Pathwise policy contains an inadmissible cap.")
    projected = _aggregate_portfolio_paths(
        scenarios=scenarios,
        cap_matrix=caps,
        product=product,
        model_points=model_points,
        behaviour=behaviour,
        mortality=mortality,
        expenses=expenses,
        projection_config=projection_config,
        collect_states=True,
        progress_label=label,
        model_point_log_interval=model_point_log_interval,
        surrender_policy_factory=surrender_policy_factory,
    )
    components = _summed_csm_components(projected, slice(None))
    csm_paths = np.sum(projected.new_business_csm_proxy, axis=1)
    row = _csm_benchmark_row(
        label=label,
        cap=None,
        definition=definition,
        components=components,
        csm_paths=csm_paths,
        best_fixed_paths=np.asarray(comparison_paths, dtype=float),
        portfolio_scale=portfolio_scale,
        is_best_fixed=False,
    )
    row["policy_value_source"] = "independent_direct_monthly_projector_rollout"
    return row, csm_paths, projected


def _projected_policy_benchmark_row(
    *,
    label: str,
    definition: str,
    projected: PortfolioPathData,
    comparison_paths: Array,
    portfolio_scale: float,
) -> tuple[dict[str, object], Array]:
    """Report an already completed direct monthly-projector rollout."""
    components = _summed_csm_components(projected, slice(None))
    csm_paths = np.sum(projected.new_business_csm_proxy, axis=1)
    row = _csm_benchmark_row(
        label=label,
        cap=None,
        definition=definition,
        components=components,
        csm_paths=csm_paths,
        best_fixed_paths=np.asarray(comparison_paths, dtype=float),
        portfolio_scale=portfolio_scale,
        is_best_fixed=False,
    )
    row["policy_value_source"] = "independent_direct_monthly_projector_rollout"
    return row, csm_paths


def _paired_mean_and_standard_error(values: Array, scale: float = 1.0) -> tuple[float, float]:
    sample = scale * np.asarray(values, dtype=float)
    return float(np.mean(sample)), _standard_error(sample)


def _adaptive_policy_passes_validation(
    *,
    masked_candidate_executable: bool,
    policyholder_validation_passed: bool,
    causal_rollout_valid: bool,
    csm_delta_aud: float,
    paired_standard_error_aud: float,
    confidence_multiplier: float = 1.96,
) -> bool:
    """Pure validation-sample deployment rule; evaluation is not an input."""
    values = np.asarray(
        (csm_delta_aud, paired_standard_error_aud, confidence_multiplier),
        dtype=float,
    )
    if not np.all(np.isfinite(values)) or paired_standard_error_aud < 0.0:
        return False
    return bool(
        masked_candidate_executable
        and policyholder_validation_passed
        and causal_rollout_valid
        and csm_delta_aud
        > confidence_multiplier * paired_standard_error_aud
    )


def _surrender_policy_payload(policy: object) -> dict[str, object]:
    """Serialize the frozen context-only follower policy used in rollout."""
    settings = getattr(policy, "settings")
    regressions = getattr(policy, "regressions")
    return {
        "settings": {
            key: value
            for key, value in vars(settings).items()
        },
        "feature_names": list(POLICYHOLDER_FEATURE_NAMES),
        "regressions_by_decision_step": [
            {
                "decision_step": int(step),
                "premium": float(regression.premium),
                "active_feature_indices": (
                    regression.active_feature_indices.tolist()
                ),
                "orthogonal_components": (
                    regression.orthogonal_components.tolist()
                ),
                "centre": regression.centre.tolist(),
                "scale": regression.scale.tolist(),
                "coefficients": regression.coefficients.tolist(),
                "condition_number": float(regression.condition_number),
                "matrix_rank": int(regression.matrix_rank),
                "oof_rmse_aud": float(regression.oof_rmse_aud),
            }
            for step, regression in sorted(regressions.items())
        ],
    }


def _policyholder_fit_set_payload(fit_set: object) -> dict[str, object]:
    """Persist every signature-specific frozen follower regression."""
    if isinstance(fit_set, CoupledPolicyholderFitSet):
        policies = fit_set.policies
        validation_fallbacks = set(fit_set.fallback_signatures)
        fallback_steps = dict(fit_set.fallback_steps_by_signature)
        source = "coupled_two_value_backward_induction"
    elif isinstance(fit_set, PolicyholderFitSet):
        policies = {
            signature: fit.policy
            for signature, fit in fit_set.fits.items()
        }
        validation_fallbacks = set(
            fit_set.validation_fallback_signatures
        )
        fallback_steps = {
            signature: tuple(sorted(
                {
                    int(diagnostic.decision_step)
                    for diagnostic in fit.diagnostics
                    if not bool(
                        diagnostic.regression_accepted_for_exercise
                    )
                }
                | (
                    {
                        int(diagnostic.decision_step)
                        for diagnostic in fit.diagnostics
                    }
                    if bool(fit.training_fallback_used)
                    else set()
                )
            ))
            for signature, fit in fit_set.fits.items()
        }
        for signature in validation_fallbacks:
            fit = fit_set.fits[signature]
            fallback_steps[signature] = tuple(sorted(
                set(fallback_steps.get(signature, ()))
                | {int(step) for step in fit.policy.regressions}
                | {
                    int(diagnostic.decision_step)
                    for diagnostic in fit.diagnostics
                }
            ))
        source = "fresh_fixed_cap_policyholder_lsmc"
    else:
        raise TypeError("Unsupported Policyholder fit-set type.")
    signatures: list[dict[str, object]] = []
    for signature in sorted(policies, key=repr):
        signature_text = json.dumps(
            signature, default=str, separators=(",", ":")
        )
        trained_policy = policies[signature]
        deployed_fallback_steps = tuple(fallback_steps.get(signature, ()))
        trained_steps = set(getattr(trained_policy, "regressions"))
        fallback_step_set = set(deployed_fallback_steps)
        expected_steps = trained_steps | fallback_step_set
        accepted_steps = (
            set()
            if signature in validation_fallbacks
            else trained_steps - fallback_step_set
        )
        whole_signature_fallback = bool(expected_steps) and not accepted_steps
        # Deployment replaces a failed signature with Continue.  Persist that
        # switch explicitly while retaining the trained regression for audit.
        signatures.append({
            "policy_signature": signature_text,
            "policy_signature_fingerprint": hashlib.sha256(
                signature_text.encode("utf-8")
            ).hexdigest(),
            "continue_fallback_deployed": bool(deployed_fallback_steps),
            "whole_signature_continue_fallback_deployed": (
                whole_signature_fallback
            ),
            "continue_fallback_decision_steps": list(
                deployed_fallback_steps
            ),
            "trained_policy": _surrender_policy_payload(trained_policy),
            "deployed_regression_count": (
                len(accepted_steps)
            ),
        })
    return {
        "source": source,
        "training_scenario_fingerprint": fit_set.scenario_fingerprint,
        "training_cap_schedule_fingerprint": (
            fit_set.cap_schedule_fingerprint
        ),
        "signature_count": fit_set.signature_count,
        "fallback_signature_count": fit_set.fallback_count,
        "signatures": signatures,
    }


def _policy_payload(
    result: BackwardResult,
    feature_names: Sequence[str],
    projection_semantics: Mapping[str, object],
    *,
    fixed_fallback_cap: float,
    deployed_first_year_cap: float,
    adaptive_policy_selected: bool,
    validation_delta_aud: float,
    validation_paired_standard_error_aud: float,
    advantage_screen_multiplier: float = 1.96,
) -> dict[str, object]:
    nonlinear, interactions, basis_names = _basis_specification(feature_names)
    deployed_rule = (
        "Apply the year-specific fitted-Q coefficients, exclude locally "
        "masked actions, and deviate from the fixed cap only when the fitted "
        "Q advantage exceeds the documented conservative uncertainty screen."
        if adaptive_policy_selected
        else "Ignore the fitted-Q coefficients for deployment and apply the "
        "fixed fallback cap in every policy year."
    )
    return {
        "engine_version": ENGINE_VERSION,
        "method": "outer_fold_pure_control_randomisation_fitted_q",
        "optimization_direction": "maximize",
        "numerically_stable": bool(result.numerically_stable),
        "numerically_stable_semantics": (
            "all raw year/action fits pass every diagnostic; false does not "
            "disable the masked candidate"
        ),
        "masked_candidate_executable": True,
        "numerical_fallback_reasons": list(
            result.numerical_fallback_reasons
        ),
        "projection_semantics": dict(projection_semantics),
        "objective_outputs": [
            "new_business_csm_proxy",
            "product_fees",
            "lip_fees",
            "crediting_margin",
            "money_market_income",
            "hedge_gain",
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
        "deployment": {
            "policy_type": (
                "adaptive_fitted_q"
                if adaptive_policy_selected
                else "fixed_cap_fallback"
            ),
            "adaptive_policy_selected": bool(adaptive_policy_selected),
            "fitted_coefficients_authoritative_for_deployment": bool(
                adaptive_policy_selected
            ),
            "fixed_fallback_cap_decimal": float(fixed_fallback_cap),
            "fixed_fallback_cap_percent": 100.0 * float(fixed_fallback_cap),
            "deployed_first_year_cap_decimal": float(deployed_first_year_cap),
            "deployed_first_year_cap_percent": (
                100.0 * float(deployed_first_year_cap)
            ),
            "adaptive_validation_delta_vs_fixed_aud": float(
                validation_delta_aud
            ),
            "adaptive_validation_paired_standard_error_aud": float(
                validation_paired_standard_error_aud
            ),
            "adaptive_validation_rule": (
                "Select the adaptive candidate only when its paired direct-"
                "projection validation delta exceeds 1.96 standard errors."
            ),
            "local_action_advantage_screen_applied": True,
            "local_action_advantage_screen_multiplier": float(
                advantage_screen_multiplier
            ),
            "advantage_screen_is_confidence_interval": False,
            "deployed_rule": deployed_rule,
        },
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
                "action_value_standard_error": (
                    item.action_value_standard_error.tolist()
                ),
                "value_lower_bounds_by_action_output": (
                    None
                    if item.value_lower_bounds is None
                    else item.value_lower_bounds.tolist()
                ),
                "value_upper_bounds_by_action_output": (
                    None
                    if item.value_upper_bounds is None
                    else item.value_upper_bounds.tolist()
                ),
                "numerically_stable": bool(item.numerically_stable),
                "action_deployable_mask": (
                    np.ones(len(item.action_caps), dtype=bool).tolist()
                    if item.action_deployable_mask is None
                    else np.asarray(
                        item.action_deployable_mask, dtype=bool
                    ).tolist()
                ),
            }
            for item in result.policy_years
        ],
        "application_rule": deployed_rule,
        "fitted_candidate_rule": (
            "At each economically active anniversary form only the listed "
            "pre-action state, apply that year's scaling and basis, predict "
            "all deployable action values, and use the fixed comparator unless "
            "the best alternative clears the local uncertainty screen. The "
            "complete masked adaptive rule is selected or rejected only on the "
            "separate paired validation sample. No policy is fitted after all covered "
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


def _plot_flexibility_value(
    *,
    pyplot,
    ticker,
    benchmark_rows: Sequence[Mapping[str, object]],
    directory: Path,
    plot_format: str,
    dpi: int,
) -> list[Path]:
    """Plain-language comparison based only on direct evaluation cashflows."""
    # The zero-crediting comparator is optional; it is only drawn when present.
    no_credit = next(
        (row for row in benchmark_rows
         if row["case"] == "no_crediting_cap_0pct"),
        None,
    )
    best_fixed = next(
        row for row in benchmark_rows
        if row["is_best_fixed_cap_admissible_grid"]
    )
    requested_fixed = next(
        row for row in benchmark_rows
        if row.get("is_best_fixed_cap_requested_1_to_20_grid", False)
    )
    flexible = next(
        row for row in benchmark_rows
        if row["case"] == "flexible_dynamic_behaviour_policy"
    )
    entries: list[tuple[Mapping[str, object], str, str]] = []
    if no_credit is not None:
        entries.append((no_credit, "Keine Gutschrift\n(0 %)", "#8A94A3"))
    entries.append((
        requested_fixed,
        "Bester fixer Cap\n"
        f"nur 1–20 % ({float(requested_fixed['cap_percent']):g} %)",
        "#5B8DB8",
    ))
    entries.append((
        best_fixed,
        f"Bester fixer Cap\n({float(best_fixed['cap_percent']):g} %)",
        "#2F6B9A",
    ))
    entries.append((flexible, "Flexibler jährlicher\nKandidat", "#168A45"))
    rows = tuple(entry[0] for entry in entries)
    labels = tuple(entry[1] for entry in entries)
    bar_colours = tuple(entry[2] for entry in entries)
    values = np.asarray([
        float(row["estimated_new_business_csm_proxy_aud"]) for row in rows
    ])
    errors = 1.96 * np.asarray([
        float(row["standard_error_new_business_csm_proxy_aud"]) for row in rows
    ])
    delta = float(
        flexible["new_business_csm_difference_vs_best_fixed_admissible_aud"]
    )
    delta_se = float(
        flexible[
            "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud"
        ]
    )
    lower = delta - 1.96 * delta_se
    upper = delta + 1.96 * delta_se

    figure, (top, bottom) = pyplot.subplots(
        2, 1, figsize=(10.5, 8.2),
        gridspec_kw={"height_ratios": (2.2, 1.0)},
    )
    positions = np.arange(len(rows))
    bars = top.bar(
        positions, values, yerr=errors, capsize=5, color=bar_colours, alpha=0.9
    )
    top.axhline(0.0, color="black", linewidth=0.8)
    top.set_xticks(positions, labels)
    top.set_ylabel("New-Business-CSM-Proxy (AUD; höher ist besser)")
    top.set_title("Direkter Vergleich mit denselben finalen Zufallsziehungen")
    top.yaxis.set_major_formatter(ticker.FuncFormatter(_aud_formatter))
    top.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, values):
        vertical = 4 if value >= 0.0 else -14
        alignment = "bottom" if value >= 0.0 else "top"
        top.annotate(
            f"AUD {_aud_formatter(value, None)}",
            (bar.get_x() + bar.get_width() / 2.0, value),
            xytext=(0, vertical), textcoords="offset points",
            ha="center", va=alignment, fontsize=9,
        )

    bottom.errorbar(
        [0.0], [delta], yerr=[1.96 * delta_se], fmt="o", markersize=8,
        capsize=7, linewidth=2.0, color="#168A45",
    )
    bottom.axhline(0.0, color="black", linewidth=1.0)
    bottom.set_xlim(-0.75, 0.75)
    bottom.set_xticks([0.0], ["Flexibel minus bester fixer Cap"])
    bottom.set_ylabel("Gepaarter Δ CSM (AUD)")
    bottom.yaxis.set_major_formatter(ticker.FuncFormatter(_aud_formatter))
    bottom.grid(axis="y", alpha=0.25)
    if np.isclose(delta_se, 0.0) and np.isclose(delta, 0.0):
        # Avoid a degenerate +/-0 y-axis if every local screen retains the
        # fixed comparator and the candidate therefore coincides with it.
        vertical_span = max(1_000.0, 0.04 * float(np.max(np.abs(values))))
        bottom.set_ylim(-vertical_span, vertical_span)
        evidence = "Kandidat entspricht auf allen Pfaden dem fixen Cap"
    else:
        evidence = (
            "95%-Intervall vollständig über null"
            if lower > 0.0
            else "kein positiver Flexibilitätswert nachgewiesen"
        )
    bottom.set_title(
        f"Reiner Flexibilitätswert ggü. fairem fixer Vergleich: "
        f"AUD {_aud_formatter(delta, None)} "
        f"[{_aud_formatter(lower, None)}, {_aud_formatter(upper, None)}]; {evidence}",
        fontsize=10,
    )
    exercise_rate = float(flexible.get(
        "policyholder_full_withdrawal_exercise_rate_over_income_exposure",
        0.0,
    ))
    deployment_note = (
        "Validierung abgelehnt; deployed wird der fixe Fallback"
        if not flexible.get("adaptive_policy_selected", False)
        else "Validierung bestanden; Kandidat wird deployed"
    )
    boundary_note = (
        "; erster Cap am Rand des Aktionsgitters"
        if flexible.get("candidate_first_year_cap_on_action_grid_boundary", False)
        else ""
    )
    figure.text(
        0.01, 0.01,
        "Alle Balken stammen aus direkten Monatsprojektionen. Der flexible CSM "
        "ist kein regressierter Bellman-Wert; das Δ-Intervall nutzt gepaarte "
        "Markt-, Take-up- und Mortalitätsziehungen. Ein Vorsprung gegenüber dem "
        "1–20-%-Check kann allein aus dem zusätzlich zulässigen 0,25-%-Cap stammen "
        "und ist dann kein Flexibilitätswert.",
        fontsize=8,
    )
    figure.text(
        0.01,
        0.04,
        f"Policyholder exercise rate / Income exposure: "
        f"{100.0 * exercise_rate:.2f}%; deployment: {deployment_note}"
        f"{boundary_note}.",
        fontsize=8,
    )
    figure.tight_layout(rect=(0.0, 0.075, 1.0, 1.0))
    return _save_figure(
        figure=figure, pyplot=pyplot, directory=directory,
        stem="00_flexibility_value", plot_format=plot_format, dpi=dpi,
    )


def _plot_first_year_choice(
    *,
    pyplot,
    ticker,
    rows: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
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
    deployed_cap = float(summary["optimal_first_year_cap_percent"])
    single_oof_series = any(
        bool(row.get("two_value_stackelberg_recursion", False))
        or bool(row.get("outer_fold_pure", False))
        for row in ordered
    )
    outer_fold_pure = any(
        bool(row.get("outer_fold_pure", False)) for row in ordered
    )

    figure, axis = pyplot.subplots(figsize=(10.5, 6.2))
    axis.errorbar(
        caps, selection, yerr=1.96 * selection_se,
        marker="o", markersize=4, linewidth=1.5, capsize=2,
        label=(
            "Complete-path outer-fold-pure OOF Q"
            if outer_fold_pure
            else "Complete-path OOF coupled Q"
            if single_oof_series
            else "Selection folds: estimated Q"
        ),
    )
    if not single_oof_series:
        axis.errorbar(
            caps, holdout, yerr=1.96 * holdout_se,
            marker="s", markersize=3.5, linewidth=1.2, capsize=2,
            linestyle="--", label="Held-out fold: estimated Q",
        )
    axis.axvline(
        chosen_cap, color="black", linewidth=1.2, linestyle=":",
        label=f"Unconstrained Bellman choice: {chosen_cap:g}%",
    )
    axis.axvline(
        deployed_cap, color="#168A45", linewidth=1.5, linestyle="--",
        label=f"Validated deployed cap: {deployed_cap:g}%",
    )
    axis.axhline(0.0, color="grey", linewidth=0.8)
    axis.set_xlabel("First-year cap (%)")
    axis.set_ylabel("Approximate New Business CSM (AUD; higher is better)")
    axis.set_title("First-year Fitted-Q diagnostic and validated deployed cap")
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
    directory: Path,
    plot_format: str,
    dpi: int,
) -> list[Path]:
    numeric = sorted(
        (
            row for row in benchmark_rows
            if row["cap_percent"] is not None
            and np.isfinite(float(row["cap_percent"]))
        ),
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
            "new_business_csm_difference_vs_best_fixed_admissible_aud"
        ]) for row in numeric
    ])
    paired_se = np.asarray([
        float(row[
            "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud"
        ]) for row in numeric
    ])
    best = next(
        row for row in numeric if row["is_best_fixed_cap_admissible_grid"]
    )
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
        label=f"Best fixed admissible cap: {best_cap:g}%",
    )
    special_styles = {
        "uncapped_positive_credit": ("No upper cap", "tab:green", "--"),
        "flexible_dynamic_behaviour_policy": (
            "Adaptive annual-cap candidate (direct rollout)", "tab:purple", "-."
        ),
    }
    for case, (label, colour, style) in special_styles.items():
        matching = [row for row in benchmark_rows if row["case"] == case]
        if matching:
            top.axhline(
                float(matching[0]["estimated_new_business_csm_proxy_aud"]),
                color=colour, linestyle=style, linewidth=1.2, label=label,
            )
    top.set_ylabel("Approximate New Business CSM (AUD)")
    top.set_title("Direct fixed-cap checks and flexible-policy rollout")
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
        "Paired intervals use common market, Take-up and mortality draws; "
        "positive Δ CSM is better.",
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
        (
            row for row in benchmark_rows
            if row["cap_percent"] is not None
            and np.isfinite(float(row["cap_percent"]))
        ),
        key=lambda row: float(row["cap_percent"]),
    )
    caps = np.asarray([float(row["cap_percent"]) for row in numeric])
    product_fees = np.asarray([
        float(row["pv_product_fees_aud"]) for row in numeric
    ])
    lip_fees = np.asarray([
        float(row["pv_lip_fees_aud"]) for row in numeric
    ])
    other_income = np.asarray([
        float(row["pv_other_income_aud"]) for row in numeric
    ])
    claims = -np.asarray([
        float(row["pv_claims_aud"]) for row in numeric
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
    axis.plot(caps, other_income, marker="D", label="+ Other income")
    axis.plot(caps, claims, marker="o", label="− Claims")
    axis.plot(caps, expenses, marker="P", label="− Operating expenses")
    axis.plot(caps, hedge_costs, marker="X", label="− Option/hedge costs")
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


def _plot_lapse_behaviour_by_cap(
    *,
    pyplot,
    benchmark_rows: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
    directory: Path,
    plot_format: str,
    dpi: int,
) -> list[Path]:
    """Show the directly projected full-surrender response to fixed caps."""
    rows = sorted(
        (
            row for row in benchmark_rows
            if str(row["case"]).startswith("fixed_cap_")
            and row.get("cap_percent") is not None
            and 0.25 <= float(row["cap_percent"]) <= 20.0
        ),
        key=lambda row: float(row["cap_percent"]),
    )
    caps = np.asarray([float(row["cap_percent"]) for row in rows])
    lapse = 100.0 * np.asarray([
        float(row["expected_cumulative_full_surrender_probability"])
        for row in rows
    ])
    figure, axis = pyplot.subplots(figsize=(10.5, 5.6))
    axis.plot(caps, lapse, marker="o", linewidth=2.0, color="#A44A3F")
    best_cap = float(summary["best_fixed_cap_admissible_percent"])
    axis.axvline(
        best_cap, color="#2F6B9A", linestyle="--", linewidth=1.5,
        label=f"Bester fixer Cap: {best_cap:g} %",
    )
    axis.set_xlabel("Jährlich fixer Cap (%)")
    axis.set_ylabel("Erwartete kumulierte Full-Surrender-Wahrscheinlichkeit (%)")
    axis.set_title(
        "Direkt projizierte Behaviour-Reaktion auf den Crediting-Cap\n"
        f"Performance-Gap={summary['performance_gap_behaviour_enabled']}, "
        f"Basis={summary['behaviour_value_basis']}"
    )
    axis.grid(alpha=0.25)
    axis.legend(loc="best")
    figure.text(
        0.01, 0.01,
        "Growth Surrender ist produktseitig verboten. Die Kurve misst daher "
        "Full Surrender in den modellierten Income-Zweigen; Joint-Life-"
        "Continue-Income bleibt bis zur Kohortenerweiterung statisch.",
        fontsize=8,
    )
    figure.tight_layout(rect=(0.0, 0.055, 1.0, 1.0))
    return _save_figure(
        figure=figure, pyplot=pyplot, directory=directory,
        stem="06_lapse_behaviour_by_cap", plot_format=plot_format, dpi=dpi,
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
        "Adaptive-candidate cap choices in the independent direct rollout; "
        "grey tail has zero exposure"
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
        "00_flexibility_value",
        "01_first_year_cap_choice",
        "02_fixed_cap_sanity_checks",
        "03_fixed_cap_pv_decomposition",
        "04_dynamic_cap_policy",
        "05_regression_diagnostics",
        "06_lapse_behaviour_by_cap",
    )
    for stem in stems:
        for extension in ("png", "svg"):
            stale = plot_directory / f"{stem}.{extension}"
            if stale.is_file():
                stale.unlink()
                LOGGER.debug("Removed stale plot from previous run | %s", stale)
    paths: list[Path] = []
    paths.extend(_plot_flexibility_value(
        pyplot=pyplot, ticker=ticker, benchmark_rows=benchmark_rows,
        directory=plot_directory, plot_format=plot_format, dpi=dpi,
    ))
    paths.extend(_plot_first_year_choice(
        pyplot=pyplot, ticker=ticker, rows=first_year_rows,
        summary=summary,
        directory=plot_directory, plot_format=plot_format, dpi=dpi,
    ))
    paths.extend(_plot_fixed_cap_checks(
        pyplot=pyplot, ticker=ticker, benchmark_rows=benchmark_rows,
        directory=plot_directory,
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
    paths.extend(_plot_lapse_behaviour_by_cap(
        pyplot=pyplot,
        benchmark_rows=benchmark_rows,
        summary=summary,
        directory=plot_directory,
        plot_format=plot_format,
        dpi=dpi,
    ))
    return paths, str(matplotlib.__version__)


def main() -> None:
    args = parse_args()
    run_started = time.perf_counter()
    run_created = datetime.now(timezone.utc)
    run_created_utc = run_created.isoformat()
    run_id = run_created.strftime("%Y%m%dT%H%M%S.%fZ")
    script_path = Path(__file__).resolve()
    script_sha256 = hashlib.sha256(script_path.read_bytes()).hexdigest()
    output_root = args.output.expanduser().resolve()
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    log_path = _configure_logging(output, args.log_level)
    LOGGER.info(
        "Crediting-cap dynamic-Behaviour run started | output root=%s | "
        "run directory=%s",
        output_root,
        output,
    )
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
    # Mark the new timestamped run before the first fallible stage.  If this
    # process stops unexpectedly, consumers see an explicit non-completed
    # status and the current run id in that run's own directory.
    running_summary = {
        "status": "running",
        "run_id": run_id,
        "created_utc": run_created_utc,
        "script": str(script_path),
        "script_sha256": script_sha256,
        "run_log_file": str(log_path.relative_to(output)),
        "message": (
            "Run in progress or interrupted; use results only when status is "
            "completed. See run.log for the last completed stage."
        ),
    }
    with (output / "optimization_summary.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(running_summary, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with _logged_stage("Validate headless Matplotlib plotting backend"):
        plotting_backend = _load_plotting_backend()

    with _logged_stage("Load market assumptions"):
        market = load_market_assumptions(args.zero_curve, args.model_parameters)
    LOGGER.debug("Market inputs | %s", market.source_metadata())
    with _logged_stage("Load equity allocation"):
        equity_allocation = load_equity_allocation()
    LOGGER.info(
        "Equity allocation | id=%s | equity=%.2f%% | bonds=%.2f%% | %s",
        equity_allocation.allocation_id,
        100.0 * equity_allocation.equity_weight,
        100.0 * equity_allocation.bond_weight,
        equity_allocation.source_path,
    )
    generic_product = IndexLinkedLifetimeIncomeProduct(
        reference_fund=ReferenceFundSpec(
            equity_weight=equity_allocation.equity_weight,
        ),
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
            value_basis=args.behaviour_value_basis,
        )
    # This dedicated runner deliberately preserves the complete loaded dynamic
    # Behaviour model, including state-dependent Income Election.
    dynamic_behaviour = loaded_behaviour.behaviour
    if not args.performance_gap_behaviour:
        dynamic_behaviour = replace(
            dynamic_behaviour,
            dynamic=replace(
                dynamic_behaviour.dynamic,
                performance=replace(
                    dynamic_behaviour.dynamic.performance,
                    excess_hazard_cap=0.0,
                ),
            ),
        )
    behaviour = dynamic_behaviour
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
    joint_life_count = sum(bool(row["spouse"]) for row in treatment_rows)
    joint_continue_income_count = sum(
        point.policy.spouse
        and point.policy.spouse_death_election
        == SpouseDeathElection.CONTINUE_INCOME
        for point in model_points.model_points
    )
    joint_lump_sum_count = joint_life_count - joint_continue_income_count
    dynamic_behaviour_active = (
        behaviour.use_dynamic
        or behaviour.use_dynamic_take_up
        or behaviour.use_dynamic_withdrawals
    )
    base_branch_behaviour = (
        "dynamic_state_dependent" if dynamic_behaviour_active else "static_base"
    )
    behaviour_treatment_by_branch = {
        "single_life": base_branch_behaviour,
        "joint_life": (
            "pathwise_joint_life_state_dependent"
            if joint_life_count else "not_applicable"
        ),
    }
    joint_life_behaviour_treatment = (
        "pathwise_joint_life_state_dependent"
        if joint_life_count else "not_applicable"
    )
    projection_semantics: dict[str, object] = {
        "engine_version": ENGINE_VERSION,
        "policyholder_behaviour_mode": args.policyholder_behaviour,
        "statistical_lapse_applied_alongside_lsmc": False,
        "policyholder_lsmc_replaces_statistical_voluntary_actions": False,
        "policyholder_lsmc_used": False,
        "dynamic_income_election_used": bool(behaviour.use_dynamic_take_up),
        "leader_state_timing": (
            "after old-cap credit, fee posting, mortality and Election; before "
            "new-cap DVA/hedge restart"
        ),
        "announced_cap_observable_to_same_anniversary_surrender": True,
        "source_behaviour_regime": loaded_behaviour.behaviour.regime,
        "base_behaviour_regime": behaviour.regime,
        "dynamic_lapse_or_withdrawal_active_on_base_behaviour": (
            dynamic_behaviour_active
        ),
        "behaviour_value_basis": args.behaviour_value_basis,
        "performance_gap_behaviour_enabled": bool(
            args.performance_gap_behaviour
        ),
        "performance_lapse_model": "competing_risk_excess_hazard",
        "performance_lapse_retention_gamma": float(
            behaviour.dynamic.performance.retention_gamma
        ),
        "performance_lapse_retention_floor": float(
            behaviour.dynamic.performance.retention_floor
        ),
        "performance_lapse_shortfall_deadband": float(
            behaviour.dynamic.performance.shortfall_deadband
        ),
        "performance_shortfall_max_log_return": float(
            behaviour.dynamic.performance.shortfall_max
        ),
        "performance_lapse_excess_hazard_cap": float(
            behaviour.dynamic.performance.excess_hazard_cap
        ),
        "performance_lapse_excess_hazard_scale": float(
            behaviour.dynamic.performance.excess_hazard_scale
        ),
        "performance_lapse_annual_probability_cap": float(
            behaviour.dynamic.performance.annual_probability_cap
        ),
        "performance_gap_definition": (
            "positive part of trailing annual log(reference-fund gross return) "
            "minus log(customer credited gross return), observed after annual "
            "crediting; customer fund only, no backing-asset or hedge P&L input"
        ),
        "growth_surrender_treatment": (
            "contractually prohibited; performance-gap coefficient cannot "
            "create Growth-phase lapses"
        ),
        "behaviour_treatment_by_branch": behaviour_treatment_by_branch,
        "source_income_take_up_mode": loaded_behaviour.behaviour.take_up.mode,
        "effective_income_take_up_mode": behaviour.take_up.mode,
        "dynamic_take_up_coefficients_applied": bool(
            behaviour.use_dynamic_take_up
        ),
        "take_up_override_reason": None,
        "income_take_up_source": (
            "dynamic_behaviour_hazard_with_contractual_minimum_wait_and_"
            "automatic_age_backstop"
        ),
        "effective_income_start_override_model_point_count": None,
        "product_min_years_before_income": int(
            costs.product.min_years_before_income
        ),
        "product_automatic_income_start_age": float(
            costs.product.automatic_income_start_age
        ),
        "distinct_effective_income_start_years": [],
        "effective_income_start_state_cohorts_added": False,
        "effective_income_start_state_cohorts": (
            "not applicable; Income Election is path-dependent under dynamic Take-up"
        ),
        "joint_life_model_point_count": joint_life_count,
        "joint_continue_income_model_point_count": joint_continue_income_count,
        "joint_lump_sum_model_point_count": joint_lump_sum_count,
        "joint_life_election_treatment": (
            "pathwise_primary_and_spouse_life_state"
            if joint_life_count else "not_applicable_single_life_portfolio"
        ),
        "joint_life_dependence": (
            "independent_lives" if joint_life_count else "not_applicable"
        ),
        "joint_life_behaviour_treatment": joint_life_behaviour_treatment,
        "joint_life_four_state_account_cohorts": (
            True if joint_life_count else None
        ),
        "income_lapse_after_account_value_exhaustion": (
            "full surrender is ineligible once the customer surrender value "
            "is exhausted; a positive lifetime-income guarantee cannot be "
            "forfeited for zero consideration"
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
        "csm_definition": (
            "PV(Fee Income) + PV(Other Income) - PV(Claims) - PV(Costs)"
        ),
        "new_business_csm_proxy_scope": (
            "Fee Income = Product Fees + LIP Fees; Other Income = pathwise "
            "Money-Market Income + retained Hedge Gain + MVA/APS retained; "
            "Claims = Guarantee Claims + other insurer-funded benefits; "
            "Costs = acquisition/maintenance/other operating expenses + full "
            "option/hedge costs"
        ),
        "other_insurer_funded_benefit_cashflow_keys": list(
            OTHER_INSURER_FUNDED_BENEFIT_KEYS
        ),
        "account_value_funded_policyholder_benefits_in_csm_proxy": False,
        "crediting_margin_in_csm_proxy": True,
        "money_market_income_in_csm_proxy": True,
        "hedge_cap_leg_mode": HedgeCapLegMode.SOLD.value,
        "retained_above_cap_hedge_gain_in_csm_proxy": False,
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
        crediting_margin_enabled=True,
        hedge_cap_leg_mode=HedgeCapLegMode.SOLD,
        record_paths=True,
        heston_cos=False,
        force_pathwise_joint_life=True,
    )
    projection_configs = _projection_configs_by_sample(projection_config)
    training_projection_config = projection_configs["training"]
    fixed_selection_projection_config = projection_configs[
        "fixed_cap_selection"
    ]
    validation_projection_config = projection_configs["validation"]
    evaluation_projection_config = projection_configs["evaluation"]
    projection_random_seeds_by_sample = {
        role: {
            "take_up_seed": config.take_up_seed,
            "mortality_seed": config.mortality_seed,
        }
        for role, config in projection_configs.items()
    }
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
        "dynamic covariates active=%s | contractual minimum wait and "
        "automatic-age-%.1f backstop",
        loaded_behaviour.behaviour.take_up.mode,
        behaviour.take_up.mode,
        behaviour.use_dynamic_take_up,
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
        "Behaviour feedback | dynamic statistical Income Election, lapse and "
        "withdrawals are applied directly by the monthly projector; no "
        "Policyholder LSMC is fitted. Leader state is the exact pre-cap "
        "aggregate portfolio exposure plus adapted market/cap history."
    )
    LOGGER.info(
        "Performance-gap lapse proxy | enabled=%s | basis=%s | competing-risk "
        "hazard cap=%.4f | scale=%.4f | deadband=%.4f | clip=%.2f | "
        "Growth surrender prohibited",
        args.performance_gap_behaviour,
        args.behaviour_value_basis,
        behaviour.dynamic.performance.excess_hazard_cap,
        behaviour.dynamic.performance.excess_hazard_scale,
        behaviour.dynamic.performance.shortfall_deadband,
        behaviour.dynamic.performance.shortfall_max,
    )
    LOGGER.info(
        "Mortality | Policy-Year annual q_x reconciled to monthly decrements | "
        "hard terminal age=%d | market path target age=120",
        MORTALITY_TERMINAL_AGE,
    )
    LOGGER.info(
        "Objective | MAX CSM = PV(Fee Income) + PV(Other Income) - "
        "PV(Claims) - PV(Costs) | Other Income includes Money-Market backing "
        "and zero retained above-cap gain | DVA=%s | hedge vol spread=%.6f | "
        "hedge cap leg=%s (no retained above-cap performance)",
        projection_config.dva_enabled,
        projection_config.hedge_vol_spread,
        projection_config.hedge_cap_leg_mode.value,
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
            projection_config=training_projection_config,
            collect_states=True,
            progress_label="Control-randomisation training projection",
            model_point_log_interval=args.model_point_log_interval,
            surrender_policy_factory=None,
            collect_stackelberg_primitives=False,
        )
    with _logged_stage("Merge adapted market history and rich portfolio states"):
        training_control_inputs = _control_state_inputs(
            training_scenarios, costs.product, n_years
        )
        (
            training_data.raw_states,
            training_data.state_feature_names,
            training_portfolio_state_extension,
        ) = _merge_control_and_portfolio_states(
            inputs=training_control_inputs,
            cap_matrix=exploratory_caps,
            data=training_data,
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
    with _logged_stage("Run gas-storage account-value grid backward induction"):
        backward = _backward_induction(
            training_data,
            action_indices,
            folds=args.cross_fit_folds,
            ridge=args.ridge,
            seed=args.seed + 130_363,
            inventory_nodes=args.inventory_nodes,
            inventory_quantile_clip=args.inventory_quantile_clip,
        )
    LOGGER.info(
        "Backward diagnostic | first-year cap=%.2f%% | outer-fold OOF Bellman value=%.2f | "
        "fee income=%.2f | other income=%.2f | claims=%.2f | "
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
    unstable = (~np.isfinite(condition_values)) | (condition_values > 1.0e10)
    if np.any(unstable):
        LOGGER.warning(
            "Regression health diagnostic: %d/%d "
            "regularised year-action matrices exceed 1e10 or are non-finite "
            "(maximum=%s). Affected actions are masked locally; the complete "
            "masked candidate is decided only by paired validation.",
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
            3 * args.benchmark_paths,
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
    # Fixed-cap selection, adaptive validation and final evaluation own
    # disjoint market blocks and disjoint projector-RNG namespaces.  Policies
    # compared within one role intentionally retain common random numbers.
    fixed_selection_scenarios = _slice_scenarios(
        benchmark_scenarios, 0, args.benchmark_paths
    )
    evaluation_scenarios = _slice_scenarios(
        benchmark_scenarios,
        args.benchmark_paths,
        2 * args.benchmark_paths,
    )
    validation_scenarios = _slice_scenarios(
        benchmark_scenarios,
        2 * args.benchmark_paths,
        3 * args.benchmark_paths,
    )
    market_sample_fingerprints = {
        "training": training_scenarios.content_fingerprint,
        "fixed_cap_selection": fixed_selection_scenarios.content_fingerprint,
        "validation": validation_scenarios.content_fingerprint,
        "evaluation": evaluation_scenarios.content_fingerprint,
    }
    if len(set(market_sample_fingerprints.values())) != 4:
        raise RuntimeError(
            "Training, fixed-cap selection, adaptive validation and final "
            "evaluation ScenarioSets must be pairwise disjoint."
        )
    LOGGER.info(
        "Disjoint samples | training=%s | fixed selection=%s | "
        "adaptive validation=%s | evaluation=%s",
        market_sample_fingerprints["training"],
        market_sample_fingerprints["fixed_cap_selection"],
        market_sample_fingerprints["validation"],
        market_sample_fingerprints["evaluation"],
    )

    full_stochastic_sample_fingerprints = {
        role: hashlib.sha256(
            (
                market_sample_fingerprints[role]
                + f"|take_up={projection_configs[role].take_up_seed}"
                + f"|mortality={projection_configs[role].mortality_seed}"
            ).encode("ascii")
        ).hexdigest()
        for role in projection_configs
    }
    if len(set(full_stochastic_sample_fingerprints.values())) != 4:
        raise RuntimeError("Full stochastic sample namespaces must be distinct.")

    with _logged_stage("Evaluate existing dynamic-Behaviour fixed-cap benchmarks"):
        dynamic_results = _evaluate_fixed_benchmarks(
            selection_scenarios=fixed_selection_scenarios,
            evaluation_scenarios=evaluation_scenarios,
            n_years=n_years,
            product=costs.product,
            model_points=model_points,
            behaviour=dynamic_behaviour,
            mortality=mortality,
            expenses=costs.expenses,
            selection_projection_config=fixed_selection_projection_config,
            evaluation_projection_config=evaluation_projection_config,
            portfolio_scale=portfolio_scale,
            model_point_log_interval=args.model_point_log_interval,
            cache_dir=(
                None if args.no_benchmark_cache else args.benchmark_cache_dir
            ),
            projection_fingerprint=_projection_input_fingerprint(args),
        )

    fixed_policyholder_exercise_rows: list[dict[str, object]] = []
    policyholder_validation_rows: list[dict[str, object]] = []
    (
        benchmark_rows,
        benchmark_path_values,
        _fixed_selection_path_values,
        best_fixed_label,
        fixed_selection_metadata,
    ) = dynamic_results
    for row in benchmark_rows:
        row["policyholder_behaviour"] = "dynamic"

    behaviour_benchmark_rows: list[dict[str, object]] = []
    for source in dynamic_results[0]:
        row = dict(source)
        row["fixed_cap_base_case"] = source["case"]
        row["case"] = f"{source['case']}__dynamic"
        row["policyholder_behaviour"] = "dynamic"
        behaviour_benchmark_rows.append(row)

    best_fixed_row = next(
        row for row in benchmark_rows
        if row["is_best_fixed_cap_admissible_grid"]
    )
    best_fixed_cap = float(best_fixed_row["cap"])
    fixed_1_to_20_rows = [
        row for row in benchmark_rows
        if str(row["case"]).startswith("fixed_cap_")
        and row["cap_percent"] is not None
        and 1.0 <= float(row["cap_percent"]) <= 20.0
    ]
    requested_grid_values = np.asarray([
        float(row["fixed_cap_selection_sample_csm_aud"])
        for row in fixed_1_to_20_rows
    ])
    best_fixed_1_to_20_row = fixed_1_to_20_rows[
        int(_lower_cap_argmax(requested_grid_values))
    ]
    for row in benchmark_rows:
        row["is_best_fixed_cap_requested_1_to_20_grid"] = (
            row is best_fixed_1_to_20_row
        )
    if np.isclose(best_fixed_cap, ACTION_CAPS[0]) \
            or np.isclose(best_fixed_cap, ACTION_CAPS[-1]):
        LOGGER.warning(
            "Best fixed admissible cap lies on its grid boundary: %.2f%%.",
            100.0 * best_fixed_cap,
        )

    with _logged_stage("Project paired validation fixed-cap fallback"):
        validation_best_fixed_caps = np.full(
            (validation_scenarios.n_paths, n_years),
            best_fixed_cap,
            dtype=float,
        )
        validation_best_fixed_projected = _aggregate_portfolio_paths(
            scenarios=validation_scenarios,
            cap_matrix=validation_best_fixed_caps,
            product=costs.product,
            model_points=model_points,
            behaviour=behaviour,
            mortality=mortality,
            expenses=costs.expenses,
            projection_config=validation_projection_config,
            collect_states=False,
            progress_label="Paired validation fixed-cap fallback",
            model_point_log_interval=args.model_point_log_interval,
        )
        validation_best_fixed_paths = np.sum(
            validation_best_fixed_projected.new_business_csm_proxy,
            axis=1,
        )

    policyholder_validation_fallback_used = False
    policyholder_validation_failed_signature_count = 0
    policyholder_validation_uplift_aud: float | None = None
    policyholder_validation_uplift_se_aud: float | None = None
    with _logged_stage("Validate adaptive policy against fixed fallback"):
        validation_control_inputs = _control_state_inputs(
            validation_scenarios, costs.product, n_years
        )
        (
            validation_cap_matrix,
            validation_projected,
            validation_rollout_metadata,
        ) = _rollout_cap_policy_with_projected_states(
            inputs=validation_control_inputs,
            policy_years=backward.policy_years,
            feature_names=training_data.state_feature_names,
            fallback_cap=best_fixed_cap,
            scenarios=validation_scenarios,
            product=costs.product,
            model_points=model_points,
            behaviour=behaviour,
            mortality=mortality,
            expenses=costs.expenses,
            projection_config=validation_projection_config,
            model_point_log_interval=args.model_point_log_interval,
            surrender_policy_factory=None,
            collect_policyholder_by_signature=False,
        )
        validation_row, _ = _projected_policy_benchmark_row(
            label="adaptive_policy_validation",
            definition=(
                "validation-only adaptive cap policy under dynamic statistical "
                "Policyholder behaviour and exact pre-cap portfolio state"
            ),
            projected=validation_projected,
            comparison_paths=validation_best_fixed_paths,
            portfolio_scale=portfolio_scale,
        )

    validation_delta = float(validation_row[
        "new_business_csm_difference_vs_best_fixed_admissible_aud"
    ])
    validation_delta_se = float(validation_row[
        "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud"
    ])
    validation_adaptive_policy_selected = _adaptive_policy_passes_validation(
        masked_candidate_executable=True,
        policyholder_validation_passed=True,
        causal_rollout_valid=bool(validation_rollout_metadata["converged"]),
        csm_delta_aud=validation_delta,
        paired_standard_error_aud=validation_delta_se,
    )
    adaptive_policy_selected = validation_adaptive_policy_selected
    LOGGER.info(
        "Adaptive-policy validation | delta vs fixed fallback=%.2f | paired "
        "SE=%.2f | causal rollout valid=%s | all raw fits stable=%s | "
        "selected=%s",
        validation_delta,
        validation_delta_se,
        validation_rollout_metadata["converged"],
        backward.numerically_stable,
        validation_adaptive_policy_selected,
    )

    deployed_policyholder_continue_fallback_used = False
    deployed_policyholder_fallback_signature_count = 0
    deployed_policyholder_fallback_step_count = 0
    # Frozen before the final sample: evaluation measures the adaptive
    # candidate whether or not validation approved it for deployment.  It can
    # never change selection or choose a new fallback.
    evaluation_rollout_fallback_used = False
    with _logged_stage("Evaluate frozen adaptive candidate on independent paths"):
        evaluation_control_inputs = _control_state_inputs(
            evaluation_scenarios, costs.product, n_years
        )
        (
            adaptive_candidate_cap_matrix,
            adaptive_candidate_projected,
            evaluation_rollout_metadata,
        ) = _rollout_cap_policy_with_projected_states(
            inputs=evaluation_control_inputs,
            policy_years=backward.policy_years,
            feature_names=training_data.state_feature_names,
            fallback_cap=best_fixed_cap,
            scenarios=evaluation_scenarios,
            product=costs.product,
            model_points=model_points,
            behaviour=behaviour,
            mortality=mortality,
            expenses=costs.expenses,
            projection_config=evaluation_projection_config,
            model_point_log_interval=args.model_point_log_interval,
            surrender_policy_factory=None,
        )
        if not evaluation_rollout_metadata["converged"]:
            raise RuntimeError(
                "Frozen adaptive candidate could not be executed on the final "
                "sample. Evaluation is not allowed to select a fallback."
            )

    evaluation_best_fixed_paths = benchmark_path_values[best_fixed_label]
    with _logged_stage("Report paired adaptive-candidate flexibility value"):
        flexible_row, flexible_csm_paths = _projected_policy_benchmark_row(
            label="flexible_dynamic_behaviour_policy",
            definition=(
                "frozen adaptive annual-cap research candidate under dynamic "
                "statistical Policyholder behaviour; evaluated regardless of "
                "the separate validation deployment decision"
            ),
            projected=adaptive_candidate_projected,
            portfolio_scale=portfolio_scale,
            comparison_paths=evaluation_best_fixed_paths,
        )
    flexible_row.update({
        "policy_role": "adaptive_research_candidate",
        "sample_role": "final_evaluation",
        "adaptive_policy_selected": adaptive_policy_selected,
        "validation_adaptive_policy_selected": (
            validation_adaptive_policy_selected
        ),
        "policyholder_behaviour": args.policyholder_behaviour,
        "policyholder_continue_fallback_used": False,
        "adaptive_candidate_policyholder_validation_rejected": (
            policyholder_validation_fallback_used
        ),
        "evaluation_rollout_fallback_used": evaluation_rollout_fallback_used,
        "validation_csm_difference_vs_fixed_aud": validation_delta,
        "validation_paired_standard_error_aud": validation_delta_se,
    })

    if adaptive_policy_selected:
        deployed_cap_matrix = adaptive_candidate_cap_matrix
        deployed_projected = adaptive_candidate_projected
        deployed_rollout_metadata = dict(evaluation_rollout_metadata)
        deployed_rollout_metadata["deployment_source"] = (
            "validation_approved_adaptive_candidate"
        )
    else:
        with _logged_stage("Project validated fixed-cap deployment fallback"):
            deployed_cap_matrix = np.full(
                (evaluation_scenarios.n_paths, n_years),
                best_fixed_cap,
                dtype=float,
            )
            deployed_projected = _aggregate_portfolio_paths(
                scenarios=evaluation_scenarios,
                cap_matrix=deployed_cap_matrix,
                product=costs.product,
                model_points=model_points,
                behaviour=behaviour,
                mortality=mortality,
                expenses=costs.expenses,
                projection_config=evaluation_projection_config,
                collect_states=True,
                progress_label="Deployed fixed-cap fallback",
                model_point_log_interval=args.model_point_log_interval,
                surrender_policy_factory=None,
            )
            reproduced_fixed_paths = np.sum(
                deployed_projected.new_business_csm_proxy, axis=1
            )
            if not np.allclose(
                reproduced_fixed_paths,
                evaluation_best_fixed_paths,
                rtol=1.0e-12,
                atol=1.0e-8,
            ):
                raise RuntimeError(
                    "Final fixed-cap deployment does not reproduce the CRN "
                    "fixed-cap evaluation benchmark."
                )
            deployed_rollout_metadata = {
                "converged": True,
                "causal_prefix_projection_count": 0,
                "changed_action_counts": [],
                "method": "fixed_cap_direct_projection",
                "evaluation_sample_used_for_fallback": False,
                "fixed_cap_fallback": True,
                "deployment_source": "validation_rejected_adaptive_candidate",
            }

    with _logged_stage("Report validated deployed policy"):
        deployed_row, _deployed_csm_paths = _projected_policy_benchmark_row(
            label="validated_deployed_dynamic_behaviour_policy",
            definition=(
                "validation-approved adaptive rule or preselected best fixed "
                "cap fallback; final evaluation never changes this choice"
            ),
            projected=deployed_projected,
            portfolio_scale=portfolio_scale,
            comparison_paths=evaluation_best_fixed_paths,
        )
    deployed_row.update({
        "policy_role": "validated_deployed_policy",
        "sample_role": "final_evaluation",
        "adaptive_policy_selected": adaptive_policy_selected,
        "validation_adaptive_policy_selected": (
            validation_adaptive_policy_selected
        ),
        "policyholder_behaviour": args.policyholder_behaviour,
        "policyholder_continue_fallback_used": (
            deployed_policyholder_continue_fallback_used
        ),
        "deployed_policyholder_fallback_signature_count": (
            deployed_policyholder_fallback_signature_count
        ),
        "deployed_policyholder_fallback_step_count": (
            deployed_policyholder_fallback_step_count
        ),
        "evaluation_rollout_fallback_used": evaluation_rollout_fallback_used,
        "validation_csm_difference_vs_fixed_aud": validation_delta,
        "validation_paired_standard_error_aud": validation_delta_se,
    })
    benchmark_rows.extend((flexible_row, deployed_row))

    candidate_first_year_caps = np.unique(adaptive_candidate_cap_matrix[:, 0])
    if candidate_first_year_caps.size != 1:
        raise RuntimeError(
            "The candidate time-zero decision must be identical on all paths."
        )
    candidate_first_year_cap = float(candidate_first_year_caps[0])
    deployed_first_year_caps = np.unique(deployed_cap_matrix[:, 0])
    if deployed_first_year_caps.size != 1:
        raise RuntimeError(
            "The deployed time-zero decision must be identical on all paths."
        )
    selected_first_year_cap = float(deployed_first_year_caps[0])
    if adaptive_candidate_projected.inforce_exposure is None:
        raise RuntimeError("Adaptive candidate did not record in-force exposure.")
    if deployed_projected.inforce_exposure is None:
        raise RuntimeError("Deployed policy did not record in-force exposure.")
    candidate_policy_rows = _direct_policy_year_rows(
        adaptive_candidate_cap_matrix,
        adaptive_candidate_projected.inforce_exposure,
        backward.economically_active_policy_years,
    )
    for row in candidate_policy_rows:
        row["policy_role"] = "adaptive_research_candidate"
    deployed_policy_rows = _direct_policy_year_rows(
        deployed_cap_matrix,
        deployed_projected.inforce_exposure,
        backward.economically_active_policy_years,
    )
    for row in deployed_policy_rows:
        row["policy_role"] = "validated_deployed_policy"
    direct_policy_rows = candidate_policy_rows
    candidate_policyholder_exercise_rows = _policyholder_exercise_rows(
        label="adaptive_research_candidate",
        cap_matrix=adaptive_candidate_cap_matrix,
        projected=adaptive_candidate_projected,
        active_policy_years=backward.economically_active_policy_years,
    )
    deployed_policyholder_exercise_rows = _policyholder_exercise_rows(
        label="validated_deployed_policy",
        cap_matrix=deployed_cap_matrix,
        projected=deployed_projected,
        active_policy_years=backward.economically_active_policy_years,
    )
    policyholder_exercise_rows = [
        *fixed_policyholder_exercise_rows,
        *candidate_policyholder_exercise_rows,
        *deployed_policyholder_exercise_rows,
    ]
    candidate_exercise_mass = sum(
        float(row["selected_full_withdrawal_exit_mass"])
        for row in candidate_policyholder_exercise_rows
    )
    candidate_income_exposure = sum(
        float(row["selected_pre_action_income_exposure"])
        for row in candidate_policyholder_exercise_rows
    )
    deployed_exercise_mass = sum(
        float(row["selected_full_withdrawal_exit_mass"])
        for row in deployed_policyholder_exercise_rows
    )
    deployed_income_exposure = sum(
        float(row["selected_pre_action_income_exposure"])
        for row in deployed_policyholder_exercise_rows
    )
    flexible_row[
        "policyholder_full_withdrawal_exercise_rate_over_income_exposure"
    ] = (
        candidate_exercise_mass / candidate_income_exposure
        if candidate_income_exposure > 0.0 else 0.0
    )
    deployed_row[
        "policyholder_full_withdrawal_exercise_rate_over_income_exposure"
    ] = (
        deployed_exercise_mass / deployed_income_exposure
        if deployed_income_exposure > 0.0 else 0.0
    )
    flexible_row["candidate_first_year_cap_on_action_grid_boundary"] = bool(
        np.isclose(candidate_first_year_cap, ACTION_CAPS[0])
        or np.isclose(candidate_first_year_cap, ACTION_CAPS[-1])
    )
    deployed_row["deployed_first_year_cap_on_action_grid_boundary"] = bool(
        np.isclose(selected_first_year_cap, ACTION_CAPS[0])
        or np.isclose(selected_first_year_cap, ACTION_CAPS[-1])
    )
    policyholder_regression_rows = [{
        "fit_label": "not_applicable",
        "policyholder_behaviour": "dynamic",
        "reason": (
            "Policyholder outcomes use the configured statistical dynamic "
            "Behaviour model; no Policyholder LSMC regression is fitted."
        ),
    }]
    policyholder_validation_rows = [{
        "policy": "not_applicable",
        "policyholder_behaviour": "dynamic",
        "reason": (
            "There is no fitted Policyholder policy to validate; the adaptive "
            "insurer cap policy is validated directly against the best fixed cap."
        ),
    }]

    direct_nonnegative_fields = (
        "pv_guarantee_claims_aud",
        "pv_other_insurer_funded_benefits_aud",
        "pv_expenses_aud",
        "pv_hedge_costs_aud",
    )
    direct_reconciliation_scale = (
        portfolio_scale * training_data.representative_initial_premium
    )
    for row in benchmark_rows:
        for field in direct_nonnegative_fields:
            if float(row[field]) < -1.0e-8:
                raise RuntimeError(
                    f"Direct projection produced negative {field} for {row['case']}."
                )
        if abs(float(row[
            "new_business_csm_component_reconciliation_gap_aud"
        ])) > 1.0e-8 * max(1.0, direct_reconciliation_scale):
            raise RuntimeError(
                f"CSM component reconciliation failed for {row['case']}."
            )

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
        "Adaptive research candidate | first-year cap %.2f%% | CSM=%.2f | "
        "MC SE=%.2f | paired flexibility value vs best fixed=%.2f",
        100.0 * candidate_first_year_cap,
        flexible_row["estimated_new_business_csm_proxy_aud"],
        flexible_row["standard_error_new_business_csm_proxy_aud"],
        flexible_row[
            "new_business_csm_difference_vs_best_fixed_admissible_aud"
        ],
    )
    LOGGER.info(
        "Validated deployed policy | adaptive=%s | first-year cap %.2f%% | "
        "CSM=%.2f | paired delta vs best fixed=%.2f",
        adaptive_policy_selected,
        100.0 * selected_first_year_cap,
        deployed_row["estimated_new_business_csm_proxy_aud"],
        deployed_row[
            "new_business_csm_difference_vs_best_fixed_admissible_aud"
        ],
    )
    adaptive_candidate_row = flexible_row
    adaptive_candidate_csm = float(
        adaptive_candidate_row["estimated_new_business_csm_proxy_aud"]
    )
    adaptive_candidate_se = float(
        adaptive_candidate_row["standard_error_new_business_csm_proxy_aud"]
    )
    flexibility_delta = float(adaptive_candidate_row[
        "new_business_csm_difference_vs_best_fixed_admissible_aud"
    ])
    flexibility_delta_se = float(adaptive_candidate_row[
        "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud"
    ])
    flexibility_fee_income_change = float(
        adaptive_candidate_row["pv_fee_income_aud"]
        - best_fixed_row["pv_fee_income_aud"]
    )
    flexibility_other_income_change = float(
        adaptive_candidate_row["pv_other_income_aud"]
        - best_fixed_row["pv_other_income_aud"]
    )
    flexibility_claims_change = float(
        adaptive_candidate_row["pv_claims_aud"]
        - best_fixed_row["pv_claims_aud"]
    )
    flexibility_costs_change = float(
        adaptive_candidate_row["pv_costs_aud"]
        - best_fixed_row["pv_costs_aud"]
    )
    flexibility_hedge_cost_change = float(
        adaptive_candidate_row["pv_hedge_costs_aud"]
        - best_fixed_row["pv_hedge_costs_aud"]
    )
    flexibility_decomposition_sum = (
        flexibility_fee_income_change
        + flexibility_other_income_change
        - flexibility_claims_change
        - flexibility_costs_change
    )
    flexibility_decomposition_gap = (
        flexibility_delta - flexibility_decomposition_sum
    )
    if abs(flexibility_decomposition_gap) > 1.0e-8 * max(
        1.0, abs(flexibility_delta), abs(flexibility_decomposition_sum)
    ):
        raise RuntimeError(
            "Flexibility-value component decomposition does not reconcile."
        )
    adaptive_candidate_row.update({
        "change_in_pv_fee_income_vs_best_fixed_aud": (
            flexibility_fee_income_change
        ),
        "change_in_pv_other_income_vs_best_fixed_aud": (
            flexibility_other_income_change
        ),
        "change_in_pv_claims_vs_best_fixed_aud": flexibility_claims_change,
        "change_in_pv_costs_vs_best_fixed_aud": flexibility_costs_change,
        "change_in_pv_hedge_costs_vs_best_fixed_aud": (
            flexibility_hedge_cost_change
        ),
        "flexibility_value_component_reconciliation_gap_aud": (
            flexibility_decomposition_gap
        ),
    })
    # Legacy ``estimated_optimal_*`` outputs describe what would actually be
    # deployed.  The research question is answered by the separate primary
    # adaptive-candidate-minus-best-fixed fields below.
    flexible_row = deployed_row
    optimal_csm = float(deployed_row["estimated_new_business_csm_proxy_aud"])
    optimal_se = float(
        deployed_row["standard_error_new_business_csm_proxy_aud"]
    )
    best_fixed_csm = float(
        best_fixed_row["estimated_new_business_csm_proxy_aud"]
    )
    best_fixed_se = float(
        best_fixed_row["standard_error_new_business_csm_proxy_aud"]
    )
    fitted_action_masks = [
        (
            np.ones(len(policy.action_caps), dtype=bool)
            if policy.action_deployable_mask is None
            else np.asarray(policy.action_deployable_mask, dtype=bool)
        )
        for policy in backward.policy_years
    ]
    masked_action_fit_count = int(sum(
        np.count_nonzero(~mask) for mask in fitted_action_masks
    ))
    best_fixed_action = int(np.argmin(np.abs(ACTION_CAPS - best_fixed_cap)))
    policy_years_with_only_fixed_local_fallback = int(sum(
        (not np.any(mask)) or (not mask[best_fixed_action])
        for mask in fitted_action_masks
    ))
    scaled_initial_premium = portfolio_scale * (
        training_data.representative_initial_premium
    )

    summary = {
        "status": "completed",
        "run_id": run_id,
        "created_utc": run_created_utc,
        "engine_version": ENGINE_VERSION,
        "valuation_label": (
            "market-consistent approximate New Business CSM cap-management "
            "study under fixed proxy product and behaviour assumptions"
        ),
        "method": (
            "outer-fold-pure control-randomisation insurer Fitted-Q with "
            "statistical dynamic Policyholder Income Election, lapse and "
            "withdrawal feedback"
        ),
        "estimate_type": (
            "frozen masked Fitted-Q candidate evaluated against the independently "
            "selected best fixed cap by paired direct monthly projections; "
            "deployment is decided on a separate validation sample"
        ),
        "csm_measurement_label": (
            "approximate market-consistent New Business CSM proxy; aligned "
            "with insurer net value before Risk Margin, not reported IFRS 17 CSM"
        ),
        "optimality_scope": (
            "adaptive research candidate within the documented observable pre-"
            "action state class, plus a separately validated deployed policy; "
            "not a proof of the global control optimum"
        ),
        "primary_research_question": (
            "incremental insurer CSM value of annual crediting-cap flexibility "
            "relative to the best constant admissible cap"
        ),
        "primary_output_sample_role": "final_evaluation",
        "primary_output_common_random_numbers": True,
        "evaluation_used_for_policy_selection": False,
        "primary_paired_csm_delta_adaptive_minus_best_fixed_aud": (
            flexibility_delta
        ),
        "primary_paired_csm_delta_standard_error_aud": flexibility_delta_se,
        "primary_paired_csm_delta_interval_95pct_lower_aud": (
            flexibility_delta - 1.96 * flexibility_delta_se
        ),
        "primary_paired_csm_delta_interval_95pct_upper_aud": (
            flexibility_delta + 1.96 * flexibility_delta_se
        ),
        "primary_flexibility_value_decomposition_aud": {
            "change_in_fee_income": flexibility_fee_income_change,
            "change_in_other_income": flexibility_other_income_change,
            "change_in_claims": flexibility_claims_change,
            "change_in_costs": flexibility_costs_change,
            "change_in_hedge_costs_included_in_costs": (
                flexibility_hedge_cost_change
            ),
            "signed_csm_contribution_from_fee_income": (
                flexibility_fee_income_change
            ),
            "signed_csm_contribution_from_other_income": (
                flexibility_other_income_change
            ),
            "signed_csm_contribution_from_claims": (
                -flexibility_claims_change
            ),
            "signed_csm_contribution_from_costs": (
                -flexibility_costs_change
            ),
            "reconciliation_gap": flexibility_decomposition_gap,
        },
        "adaptive_candidate_new_business_csm_proxy_aud": (
            adaptive_candidate_csm
        ),
        "adaptive_candidate_new_business_csm_proxy_standard_error_aud": (
            adaptive_candidate_se
        ),
        "adaptive_candidate_first_year_cap": candidate_first_year_cap,
        "adaptive_candidate_first_year_cap_percent": (
            100.0 * candidate_first_year_cap
        ),
        "validated_deployed_new_business_csm_proxy_aud": optimal_csm,
        "validated_deployed_new_business_csm_proxy_standard_error_aud": (
            optimal_se
        ),
        "validated_deployed_minus_best_fixed_csm_aud": float(deployed_row[
            "new_business_csm_difference_vs_best_fixed_admissible_aud"
        ]),
        "validated_deployed_first_year_cap": selected_first_year_cap,
        "validated_deployed_first_year_cap_percent": (
            100.0 * selected_first_year_cap
        ),
        "objective_direction": "maximize",
        "objective": (
            "maximise PV(Fee Income) + PV(Other Income) - PV(Claims) - "
            "PV(Costs), where Other Income includes pathwise Money-Market "
            "Income and Costs include the complete option spread cost"
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
        "optimal_first_year_cap": selected_first_year_cap,
        "optimal_first_year_cap_percent": 100.0 * selected_first_year_cap,
        "unconstrained_bellman_first_year_cap_diagnostic": (
            backward.first_year_cap
        ),
        "estimated_optimal_new_business_csm_proxy_aud": optimal_csm,
        "estimated_optimal_recognised_csm_proxy_aud": max(optimal_csm, 0.0),
        "estimated_optimal_loss_component_proxy_aud": max(-optimal_csm, 0.0),
        "estimated_optimal_new_business_csm_proxy_to_initial_premium": (
            optimal_csm / scaled_initial_premium
        ),
        "estimated_optimal_pv_guarantee_claims_aud": (
            flexible_row["pv_guarantee_claims_aud"]
        ),
        "estimated_optimal_pv_other_insurer_funded_benefits_aud": (
            flexible_row["pv_other_insurer_funded_benefits_aud"]
        ),
        "estimated_optimal_pv_product_fees_aud": (
            flexible_row["pv_product_fees_aud"]
        ),
        "estimated_optimal_pv_lip_fees_aud": (
            flexible_row["pv_lip_fees_aud"]
        ),
        "estimated_optimal_pv_future_fees_aud": flexible_row[
            "pv_future_fees_aud"
        ],
        "estimated_optimal_pv_fee_income_aud": flexible_row[
            "pv_fee_income_aud"
        ],
        "estimated_optimal_pv_crediting_margin_aud": (
            flexible_row["pv_crediting_margin_aud"]
        ),
        "estimated_optimal_pv_money_market_income_aud": flexible_row[
            "pv_money_market_income_aud"
        ],
        "estimated_optimal_pv_hedge_gain_aud": flexible_row[
            "pv_hedge_gain_aud"
        ],
        "estimated_optimal_pv_mva_retained_aud": (
            flexible_row["pv_mva_retained_aud"]
        ),
        "estimated_optimal_pv_aps_retained_aud": (
            flexible_row["pv_aps_retained_aud"]
        ),
        "estimated_optimal_pv_other_insurer_margins_aud": flexible_row[
            "pv_other_insurer_margins_aud"
        ],
        "estimated_optimal_pv_other_income_aud": flexible_row[
            "pv_other_income_aud"
        ],
        "estimated_optimal_pv_total_insurer_inflows_aud": flexible_row[
            "pv_total_insurer_inflows_aud"
        ],
        "estimated_optimal_pv_total_insurer_funded_benefits_aud": (
            flexible_row["pv_total_insurer_funded_benefits_aud"]
        ),
        "estimated_optimal_pv_claims_aud": flexible_row["pv_claims_aud"],
        "estimated_optimal_pv_expenses_aud": (
            flexible_row["pv_expenses_aud"]
        ),
        "estimated_optimal_pv_hedge_costs_aud": (
            flexible_row["pv_hedge_costs_aud"]
        ),
        "estimated_optimal_pv_total_costs_aud": flexible_row[
            "pv_total_costs_aud"
        ],
        "estimated_optimal_pv_costs_aud": flexible_row["pv_costs_aud"],
        "estimated_optimal_policyholder_pv_aud": flexible_row[
            "pv_policyholder_benefits_aud"
        ],
        "estimated_optimal_policyholder_income_pv_aud": flexible_row[
            "pv_policyholder_income_aud"
        ],
        "estimated_optimal_policyholder_death_benefit_pv_aud": flexible_row[
            "pv_policyholder_death_benefits_aud"
        ],
        "estimated_optimal_policyholder_surrender_benefit_pv_aud": flexible_row[
            "pv_policyholder_surrender_benefits_aud"
        ],
        "deployed_policyholder_exercise_rate_over_income_exposure": flexible_row[
            "policyholder_full_withdrawal_exercise_rate_over_income_exposure"
        ],
        "estimated_optimal_new_business_csm_proxy_standard_error_aud": (
            optimal_se
        ),
        "estimated_optimal_cumulative_full_surrender_probability": (
            flexible_row[
                "expected_cumulative_full_surrender_probability"
            ]
        ),
        "optimal_csm_evaluation_sample": (
            "independent direct rollout sample, disjoint from training, fixed-"
            "cap selection and adaptive-policy validation"
        ),
        "adaptive_candidate_csm_evaluation_sample": (
            "same independent final sample as the best-fixed comparator, with "
            "paired market, Income-Election and mortality draws; never used "
            "for selection"
        ),
        "direct_rollout_csm_mc_interval_95pct_lower_aud": (
            optimal_csm - 1.96 * optimal_se
        ),
        "direct_rollout_csm_mc_interval_95pct_upper_aud": (
            optimal_csm + 1.96 * optimal_se
        ),
        "direct_rollout_mc_interval_scope": (
            "path dispersion of realised monthly-projector cashflows conditional "
            "on the frozen fitted policy"
        ),
        "new_business_csm_component_reconciliation_gap_aud": (
            flexible_row[
                "new_business_csm_component_reconciliation_gap_aud"
            ]
        ),
        "crediting_margin_reconciliation_gap_aud": flexible_row[
            "crediting_margin_reconciliation_gap_aud"
        ],
        "crediting_margin_reconciliation_max_absolute_aud": flexible_row[
            "crediting_margin_reconciliation_max_absolute_aud"
        ],
        "best_fixed_cap_admissible_case": best_fixed_row["case"],
        "best_fixed_cap_admissible_percent": best_fixed_row["cap_percent"],
        "best_fixed_cap_requested_1_to_20_case": (
            best_fixed_1_to_20_row["case"]
        ),
        "best_fixed_cap_requested_1_to_20_percent": (
            best_fixed_1_to_20_row["cap_percent"]
        ),
        "best_fixed_cap_requested_1_to_20_csm_aud": (
            best_fixed_1_to_20_row[
                "estimated_new_business_csm_proxy_aud"
            ]
        ),
        "flexible_minus_best_fixed_requested_1_to_20_csm_aud": (
            optimal_csm
            - float(best_fixed_1_to_20_row[
                "estimated_new_business_csm_proxy_aud"
            ])
        ),
        "adaptive_candidate_minus_best_fixed_requested_1_to_20_csm_aud": (
            adaptive_candidate_csm
            - float(best_fixed_1_to_20_row[
                "estimated_new_business_csm_proxy_aud"
            ])
        ),
        "flexible_policy_fixed_fallback_cap_percent": 100.0 * best_fixed_cap,
        "fitted_policy_local_action_advantage_screen_applied": True,
        "fitted_policy_local_action_advantage_screen_multiplier": 1.96,
        "adaptive_policy_validation_confidence_multiplier": 1.96,
        "adaptive_policy_selected_on_validation_sample": (
            validation_adaptive_policy_selected
        ),
        "adaptive_policy_actually_deployed": adaptive_policy_selected,
        "adaptive_policy_evaluation_operational_fallback_used": (
            evaluation_rollout_fallback_used
        ),
        "adaptive_policy_validation_state_rollout": validation_rollout_metadata,
        "adaptive_candidate_evaluation_state_rollout": (
            evaluation_rollout_metadata
        ),
        "validated_deployed_evaluation_state_rollout": (
            deployed_rollout_metadata
        ),
        "adaptive_policy_validation_csm_difference_vs_fixed_aud": (
            validation_delta
        ),
        "adaptive_policy_validation_paired_standard_error_aud": (
            validation_delta_se
        ),
        "adaptive_policy_validation_selection_rule": (
            "deploy adaptive rule only if validation delta exceeds 1.96 paired SE; "
            "otherwise deploy the admissible fixed fallback"
        ),
        "flexible_policy_deviation_rule": (
            "mask unreliable action regressions locally and deviate from the "
            "best fixed cap only when the fitted Q advantage exceeds 1.96 times "
            "the combined action standard errors; deploy this complete candidate "
            "only if its paired validation delta also clears 1.96 standard errors"
        ),
        "best_fixed_cap_new_business_csm_proxy_aud": best_fixed_csm,
        "best_fixed_cap_new_business_csm_proxy_standard_error_aud": (
            best_fixed_se
        ),
        "best_fixed_cap_cumulative_full_surrender_probability": (
            best_fixed_row[
                "expected_cumulative_full_surrender_probability"
            ]
        ),
        "estimated_optimal_minus_best_fixed_new_business_csm_proxy_aud": (
            flexible_row[
                "new_business_csm_difference_vs_best_fixed_admissible_aud"
            ]
        ),
        "adaptive_candidate_minus_best_fixed_new_business_csm_proxy_aud": (
            flexibility_delta
        ),
        "paired_standard_error_adaptive_candidate_minus_best_fixed_csm_aud": (
            flexibility_delta_se
        ),
        "paired_standard_error_optimal_minus_best_fixed_csm_aud": flexible_row[
            "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud"
        ],
        "paired_optimal_minus_best_fixed_csm_interval_95pct_lower_aud": (
            float(flexible_row[
                "new_business_csm_difference_vs_best_fixed_admissible_aud"
            ])
            - 1.96 * float(flexible_row[
                "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud"
            ])
        ),
        "paired_optimal_minus_best_fixed_csm_interval_95pct_upper_aud": (
            float(flexible_row[
                "new_business_csm_difference_vs_best_fixed_admissible_aud"
            ])
            + 1.96 * float(flexible_row[
                "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud"
            ])
        ),
        "bellman_value_diagnostic_only_aud": (
            portfolio_scale * backward.pv_new_business_csm_proxy
        ),
        "bellman_value_diagnostic_standard_error_aud": (
            portfolio_scale * backward.standard_error_new_business_csm_proxy
        ),
        "insurer_regressions_numerically_stable": (
            backward.numerically_stable
        ),
        "all_raw_insurer_fits_stable": backward.numerically_stable,
        "masked_adaptive_candidate_executable": True,
        "masked_action_fit_count": masked_action_fit_count,
        "policy_years_with_only_fixed_local_fallback": (
            policy_years_with_only_fixed_local_fallback
        ),
        "insurer_numerical_fallback_reasons": list(
            backward.numerical_fallback_reasons
        ),
        "action_caps": ACTION_CAPS.tolist(),
        "cap_grid_convention": "0.25%, followed by integer 1% caps through 20%",
        "cap_floor_override": None,
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
        "policyholder_behaviour_mode": args.policyholder_behaviour,
        "policyholder_behaviour_basis": (
            "versioned statistical dynamic Behaviour proxy using Income Take-up, "
            "ordinary/performance lapse and partial/excess withdrawal functions; "
            "not a Policyholder value maximisation"
        ),
        "policyholder_validation_continue_fallback_used": (
            policyholder_validation_fallback_used
        ),
        "deployed_policyholder_continue_fallback_used": (
            deployed_policyholder_continue_fallback_used
        ),
        "deployed_policyholder_fallback_signature_count": (
            deployed_policyholder_fallback_signature_count
        ),
        "deployed_policyholder_fallback_step_count": (
            deployed_policyholder_fallback_step_count
        ),
        "policyholder_validation_failed_signature_count": (
            policyholder_validation_failed_signature_count
        ),
        "policyholder_validation_pv_uplift_vs_continue_aud": (
            policyholder_validation_uplift_aud
        ),
        "policyholder_validation_paired_standard_error_aud": (
            policyholder_validation_uplift_se_aud
        ),
        "policyholder_lsmc_training_signature_count": 0,
        "policyholder_lsmc_training_signature_fallback_count": 0,
        "policyholder_lsmc_training_cap_schedule_fingerprint": None,
        "market_scenario_fingerprints": market_sample_fingerprints,
        "full_stochastic_sample_fingerprints": (
            full_stochastic_sample_fingerprints
        ),
        "projection_random_seeds_by_sample": (
            projection_random_seeds_by_sample
        ),
        "common_random_numbers_within_sample": {
            "fixed_cap_selection": "all fixed-cap candidates",
            "validation": "adaptive candidate versus selected best fixed cap",
            "evaluation": (
                "adaptive candidate, validated deployment and all fixed-cap "
                "sanity cases"
            ),
        },
        "n_control_randomisation_paths": args.n_paths,
        "n_fixed_cap_selection_paths_per_case": args.benchmark_paths,
        "n_adaptive_policy_validation_paths": args.benchmark_paths,
        "n_final_evaluation_paths_per_case": args.benchmark_paths,
        "fixed_cap_selection_metadata": fixed_selection_metadata,
        "cross_fit_folds": args.cross_fit_folds,
        "ridge_multiplier": args.ridge,
        "dva_enabled": bool(projection_config.dva_enabled),
        "hedge_gain_enabled": False,
        "retained_above_cap_hedge_gain_enabled": False,
        "money_market_backing_income_enabled": True,
        "hedge_cap_leg_mode": projection_config.hedge_cap_leg_mode.value,
        "crediting_margin_in_objective": True,
        "mva_and_aps_retained_in_objective": True,
        "hedge_costs_in_objective": True,
        "expenses_in_objective": True,
        "other_insurer_funded_benefit_cashflow_keys": list(
            OTHER_INSURER_FUNDED_BENEFIT_KEYS
        ),
        "base_policy_behaviour_regime": behaviour.regime,
        "behaviour_value_basis": args.behaviour_value_basis,
        "performance_gap_behaviour_enabled": bool(
            args.performance_gap_behaviour
        ),
        "performance_lapse_model": "competing_risk_excess_hazard",
        "performance_lapse_retention_gamma": float(
            behaviour.dynamic.performance.retention_gamma
        ),
        "performance_lapse_retention_floor": float(
            behaviour.dynamic.performance.retention_floor
        ),
        "performance_lapse_shortfall_deadband": float(
            behaviour.dynamic.performance.shortfall_deadband
        ),
        "performance_shortfall_max_log_return": float(
            behaviour.dynamic.performance.shortfall_max
        ),
        "performance_lapse_excess_hazard_cap": float(
            behaviour.dynamic.performance.excess_hazard_cap
        ),
        "performance_lapse_excess_hazard_scale": float(
            behaviour.dynamic.performance.excess_hazard_scale
        ),
        "performance_lapse_annual_probability_cap": float(
            behaviour.dynamic.performance.annual_probability_cap
        ),
        "behaviour_treatment_by_branch": behaviour_treatment_by_branch,
        "source_income_take_up_mode": loaded_behaviour.behaviour.take_up.mode,
        "income_take_up_mode": behaviour.take_up.mode,
        "effective_income_start_override_model_point_count": None,
        "joint_life_behaviour_treatment": joint_life_behaviour_treatment,
        "mortality_application": (
            "single-life expected decrements and pathwise primary/spouse life "
            "states for Joint-Life contracts; both use annual q_x converted "
            "to twelve reconciled monthly probabilities"
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
        fixed_fallback_cap=best_fixed_cap,
        deployed_first_year_cap=selected_first_year_cap,
        adaptive_policy_selected=adaptive_policy_selected,
        validation_delta_aud=validation_delta,
        validation_paired_standard_error_aud=validation_delta_se,
    )
    policy_payload["flexibility_value_evaluation"] = {
        "sample_role": "final_evaluation",
        "used_for_policy_selection": False,
        "common_random_numbers": True,
        "adaptive_candidate_csm_aud": adaptive_candidate_csm,
        "best_fixed_csm_aud": best_fixed_csm,
        "paired_delta_adaptive_minus_best_fixed_aud": flexibility_delta,
        "paired_delta_standard_error_aud": flexibility_delta_se,
        "paired_delta_interval_95pct_aud": [
            flexibility_delta - 1.96 * flexibility_delta_se,
            flexibility_delta + 1.96 * flexibility_delta_se,
        ],
        "paired_delta_decomposition_aud": {
            "change_in_fee_income": flexibility_fee_income_change,
            "change_in_other_income": flexibility_other_income_change,
            "minus_change_in_claims": -flexibility_claims_change,
            "minus_change_in_costs": -flexibility_costs_change,
            "change_in_hedge_costs_included_in_costs": (
                flexibility_hedge_cost_change
            ),
            "reconciliation_gap": flexibility_decomposition_gap,
        },
    }
    policy_payload["dynamic_behaviour_control"] = {
        "controller": "insurer annual cap Fitted-Q policy",
        "policyholder_response": (
            "statistical dynamic Behaviour applied inside the monthly projector; "
            "no separate Policyholder value function or LSMC exercise policy"
        ),
        "policyholder_behaviour_mode": args.policyholder_behaviour,
        "policyholder_lsmc_used": False,
        "policyholder_training_scenario_fingerprint": None,
        "policyholder_training_cap_schedule_fingerprint": None,
        "policyholder_signature_count": 0,
        "policyholder_training_fallback_signature_count": 0,
        "policyholder_validation_continue_fallback_used": (
            policyholder_validation_fallback_used
        ),
        "deployed_policyholder_continue_fallback_used": (
            deployed_policyholder_continue_fallback_used
        ),
        "deployed_policyholder_fallback_signature_count": (
            deployed_policyholder_fallback_signature_count
        ),
        "deployed_policyholder_fallback_step_count": (
            deployed_policyholder_fallback_step_count
        ),
        "policyholder_validation_failed_signature_count": (
            policyholder_validation_failed_signature_count
        ),
        "policyholder_validation_pv_uplift_vs_continue_aud": (
            policyholder_validation_uplift_aud
        ),
        "policyholder_validation_paired_standard_error_aud": (
            policyholder_validation_uplift_se_aud
        ),
        "market_scenario_fingerprints": market_sample_fingerprints,
        "full_stochastic_sample_fingerprints": (
            full_stochastic_sample_fingerprints
        ),
        "projection_random_seeds_by_sample": (
            projection_random_seeds_by_sample
        ),
        "dynamic_behaviour_assumptions": loaded_behaviour.source_metadata(),
    }
    manifest = {
        "output_schema_version": "crediting-cap-dynamic-behaviour-1.3",
        "run_id": run_id,
        "created_utc": run_created_utc,
        "engine_version": ENGINE_VERSION,
        "script": str(script_path),
        "script_sha256": script_sha256,
        "summary_file": "optimization_summary.json",
        "output_inventory": {
            "summary": "optimization_summary.json",
            "policy": "dynamic_cap_policy.json",
            "manifest": "run_manifest.json",
            "csv_tables": [
                "first_year_action_values.csv",
                "optimal_policy_by_year.csv",
                "adaptive_candidate_policy_by_year.csv",
                "validated_deployed_policy_by_year.csv",
                "cross_fitted_policy_diagnostics_by_year.csv",
                "regression_diagnostics.csv",
                "policyholder_regression_diagnostics.csv",
                "policyholder_validation_diagnostics.csv",
                "policyholder_exercise_by_year_and_cap.csv",
                "fixed_cap_sanity_checks.csv",
                "fixed_cap_behaviour_benchmarks.csv",
                "model_point_projection_treatments.csv",
            ],
            "log": "run.log",
            "plots": "populated in graphics.files after successful plotting",
        },
        "engine_market_inputs": market.source_metadata(),
        "cost_assumptions": costs.source_metadata(),
        "equity_allocation": equity_allocation.source_metadata(),
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
        "training_scenario_fingerprint": market_sample_fingerprints["training"],
        "fixed_cap_selection_scenario_fingerprint": (
            market_sample_fingerprints["fixed_cap_selection"]
        ),
        "validation_scenario_fingerprint": (
            market_sample_fingerprints["validation"]
        ),
        "evaluation_scenario_fingerprint": (
            market_sample_fingerprints["evaluation"]
        ),
        "benchmark_parent_scenario_fingerprint": (
            benchmark_scenarios.content_fingerprint
        ),
        "market_scenario_samples_are_pairwise_distinct": True,
        "full_stochastic_samples_are_pairwise_distinct": True,
        "projection_random_seeds_by_sample": (
            projection_random_seeds_by_sample
        ),
        "market_training_seed": args.seed,
        "market_benchmark_parent_seed": args.seed + 1,
        "heston_substeps": args.heston_substeps,
        "exploration": exploration_metadata,
        "objective_scope": {
            "measurement": (
                "approximate market-consistent New Business CSM proxy aligned "
                "with insurer net value before Risk Margin; not IFRS 17 CSM"
            ),
            "definition": (
                "PV(Fee Income) + PV(Other Income) - PV(Claims) - PV(Costs)"
            ),
            "optimization_direction": "maximize",
            "fee_income": ["fees_product", "fees_lip"],
            "other_income": [
                "money_market_income",
                "hedge_gain",
                "mva_retained",
                "aps_retained",
            ],
            "crediting_margin_composition": (
                "pathwise money-market backing income; no retained above-cap "
                "Reference-Fund performance under the standard sold cap leg"
            ),
            "hedge_cap_leg_mode": projection_config.hedge_cap_leg_mode.value,
            "claims": [
                "guarantee_claims",
                *OTHER_INSURER_FUNDED_BENEFIT_KEYS,
            ],
            "costs": ["expenses", "hedge_costs"],
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
            "adaptive_candidate_flexibility_value": (
                "paired independent direct monthly-projector rollout against "
                "the selected best fixed cap, regardless of deployment gate"
            ),
            "validated_deployed_value": (
                "independent direct rollout of the validation-approved adaptive "
                "candidate or the preselected fixed fallback"
            ),
            "bellman_value": (
                "diagnostic only; never reported or plotted as realised CSM"
            ),
        },
        "nonanticipativity": {
            "decision_state_time": "start of each crediting year",
            "future_reference_fund_return_in_state": False,
            "future_discount_factor_in_state": False,
            "control_state_features": list(CONTROL_STATE_FEATURE_NAMES),
            "portfolio_control_state_features": list(
                PORTFOLIO_CONTROL_STATE_FEATURE_NAMES
            ),
            "control_state_history_rule": (
                "state at year y uses market observations, fund returns and caps "
                "only through year y-1"
            ),
            "fold_unit": "complete market/control path",
            "recursive_cross_fit_rule": (
                "each outer fold owns a complete future-value chain fitted "
                "without that fold; a separate full-sample chain supplies "
                "deployment coefficients"
            ),
            "first_cap_bellman_diagnostic": (
                "direct randomised action-cell means with fold-pure future "
                "continuation targets across all outer folds"
            ),
            "realised_csm_evaluation_sample": (
                "independent final ScenarioSet; no control-fit fold"
            ),
            "evaluation_fold_used_in_any_regression_fit": False,
            "dva_enabled_in_product_projection": bool(
                projection_config.dva_enabled
            ),
            "pre_action_state_independent_of_current_cap": True,
        },
        "limitations": [
            "The leader state contains exact pre-cap aggregate Account Value, "
            "Surrender Value, locked Income, guarantee PV/moneyness and phase "
            "exposures plus market and crediting history. It remains an aggregate "
            "Markov compression rather than the complete model-point distribution, "
            "so a useful adaptive rule can still be missed.",
            "Policyholder behaviour is an exogenous statistical response model, "
            "not an individually optimal or equilibrium best response. Every "
            "reported insurer value is checked in an independent direct rollout.",
            "The monthly product rollout retains DVA, fee subledger, mortality, "
            "expenses, crediting margin and hedge-cost logic. No new calibrated "
            "Behaviour or market parameter is introduced.",
            "The dynamic Behaviour model has no direct announced-cap coefficient. "
            "Caps affect behaviour through projected Account Value, guarantee "
            "moneyness and realised reference-versus-credited performance history.",
            "Joint-Life contracts use the projector's pathwise primary/spouse "
            "life-state treatment so the dynamic response is not replaced by a "
            "static spouse-survival-weighted fallback.",
            "Income Election follows the loaded dynamic annual Take-up hazard, "
            "subject to contractual eligibility, the product minimum waiting "
            f"period of {float(costs.product.min_years_before_income):g} year(s) "
            f"and the automatic-start age {costs.product.automatic_income_start_age:g}.",
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
            "The admissible action and fixed-comparison grid is exactly 0.25%, then "
            "integer caps from 1% through 20%. Zero crediting and no upper cap are "
            "non-contractual sanity checks only.",
            "The local Q-advantage screen uses residual RMSE/sqrt(n) as a "
            "conservative stability diagnostic, not as a state-conditional "
            "confidence interval. Only the paired direct validation and final "
            "evaluation support policy-level statistical statements.",
            "The best fixed admissible cap is selected on its own sample. The "
            "adaptive-versus-fixed deployment gate uses a second, disjoint sample, "
            "and the frozen adaptive candidate is always reported on a third final "
            "sample even if validation rejects deployment. Flexible-minus-fixed "
            "differences are paired on common final-evaluation market, Income-"
            "Election and mortality draws.",
        ],
    }

    scaled_first_year_rows = _scaled_first_year_rows(
        backward.first_year_action_rows, portfolio_scale
    )
    csv_outputs = (
        (output / "first_year_action_values.csv", scaled_first_year_rows),
        (output / "optimal_policy_by_year.csv", deployed_policy_rows),
        (
            output / "adaptive_candidate_policy_by_year.csv",
            candidate_policy_rows,
        ),
        (
            output / "validated_deployed_policy_by_year.csv",
            deployed_policy_rows,
        ),
        (
            output / "cross_fitted_policy_diagnostics_by_year.csv",
            backward.policy_year_rows,
        ),
        (output / "regression_diagnostics.csv", backward.regression_rows),
        (
            output / "policyholder_regression_diagnostics.csv",
            policyholder_regression_rows,
        ),
        (
            output / "policyholder_validation_diagnostics.csv",
            policyholder_validation_rows,
        ),
        (
            output / "policyholder_exercise_by_year_and_cap.csv",
            policyholder_exercise_rows,
        ),
        (output / "fixed_cap_sanity_checks.csv", benchmark_rows),
        (
            output / "fixed_cap_behaviour_benchmarks.csv",
            behaviour_benchmark_rows,
        ),
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
        (output / "dynamic_cap_policy.json", policy_payload),
        (output / "run_manifest.json", manifest),
    )
    with _logged_stage("Checkpoint numerical JSON results before plotting"):
        for path, payload in preliminary_json_outputs:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(
                    payload, handle, indent=2, ensure_ascii=False,
                    default=_json_default, allow_nan=False,
                )
                handle.write("\n")
            LOGGER.debug("Checkpoint JSON written | %s", path)

    with _logged_stage("Generate result graphics"):
        plot_paths, matplotlib_version = _generate_plots(
            plotting_backend=plotting_backend,
            output=output,
            first_year_rows=scaled_first_year_rows,
            policy_rows=direct_policy_rows,
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
                    default=_json_default, allow_nan=False,
                )
                handle.write("\n")
            LOGGER.debug("JSON written | %s", path)

    total_elapsed = time.perf_counter() - run_started
    LOGGER.info(
        "RUN COMPLETE | elapsed %.1fs | first-year cap %.2f%% | "
        "direct flexible CSM %.2f | best fixed cap %.2f%% / CSM %.2f",
        total_elapsed,
        100.0 * selected_first_year_cap,
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
