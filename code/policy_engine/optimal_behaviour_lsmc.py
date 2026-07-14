"""Phase-aware LSMC behaviour for the generic lifetime-income product.

This module is intentionally separate from the archived legacy implementation
in :mod:`policy_engine.lsmc`.  Training cashflows and the direct same-sample
actuarial rollout both use the current monthly projector, including the configured
Reference-Fund target allocation, daily fee subledger, monthly income, MVA,
expenses, hedge costs and crediting margin.  The Policyholder recursion is
conditional on survival: its training projections contain no mortality
decrement or death benefit, so Full Withdrawal is the only voluntary
terminating action.  The fitted policy is subsequently deployed in the
actuarial valuation projector with the configured mortality basis unchanged.

The primary API solves an ordered two-regime stopping problem on annual
Crediting Anniversaries: ``WAIT_FOR_ONE_YEAR | START_INCOME_NOW`` in Growth,
followed by ``CONTINUE_FOR_ONE_YEAR | FULL_WITHDRAWAL_NOW`` in Income.  START
is evaluated as the exact projector state transition followed by the
already-solved annual Income policy; it is not treated as an immediate
payment.  Partial Withdrawals and voluntary actions between Anniversaries are
outside the combined optimal-behaviour model.  The historical monthly action
helpers remain import-compatible for isolated legacy research only.

Version six treats the customer problem as a time-zero Swing-style expected-PV
maximisation.  Customer cashflows are discounted with the deterministic
discount-factor schedule implied by the current Australian zero curve; future
simulated short-rate realisations never enter the customer objective.  The
learned rule is deployed directly, without an OOS acceptance gate or a
statistical lower-bound fallback.  Internal complete-path cross-fitting remains
part of the continuation-value estimator.  The compatibility-only monthly
helper retains its earlier analytic Partial optimiser but is unreachable from
the primary combined fit.
All regressions use training-fold standardisation, truncated SVD and a
spectral Ridge solve in the orthogonal score basis.  In particular, this module
never forms normal equations: doing so squares the design condition number and
was the source of mechanically late Elections in the original research implementation.
"""

# 2026-07-13 18:27 CEST — Performance and algorithm update:
# - Replaced one SVD/least-squares fit per Ridge candidate with one SVD per
#   training fold and closed-form spectral Ridge updates across the full grid.
# - Stored each fitted surface as an affine raw-feature form for faster rollout.
# - The compatibility-only Partial helper uses the exact argmax of its fitted
#   quadratic; the ordered annual primary fit never invokes that helper.
# - Replaced one full fixed-start projection per Election year with one
#   randomized pooled START-value fit plus one cross-fitted policy valuation.
# - No projector event ordering or contractual cashflow formula was changed.

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Mapping, Optional

import numpy as np
from numpy.typing import NDArray

from ._provenance import assumption_fingerprint
from .behavior import BehaviourModel, LapseAssumptions, WithdrawalBehaviour
from .esg import ScenarioSet, STEPS_PER_YEAR
from .mortality import MortalityTable
from .product import (ExpenseAssumptions, IndexLinkedLifetimeIncomeProduct,
                      Phase, PolicySpec)
from .projection import (IncomeActionDecision, IncomeActionDecisionContext,
                         IncomeActionState, IncomeActionType,
                         IncomeElectionDecisionContext,
                         IncomeTransitionPanelCollector,
                         ProjectionConfig, ProjectionResult,
                         SurrenderDecisionContext, advance_income_month,
                         apply_income_action,
                         build_income_action_decision_context, project)


Array = NDArray[np.float64]
POLICYHOLDER_LSMC_MORTALITY_BASIS = (
    "conditional_survival_no_mortality_full_surrender_only_v1"
)
POLICYHOLDER_LSMC_OBJECTIVE_DISCOUNT_BASIS = (
    "time_zero_australian_zero_curve_deterministic_v1"
)


class _MortalityFreeLSMCBasis(MortalityTable):
    """Projection basis with zero death decrements for Policyholder fitting.

    Keeping this as a :class:`MortalityTable` subtype lets the LSMC reuse the
    exact production projector without adding a second cashflow engine.  All
    inherited survival, life-expectancy and annuity-factor methods dispatch to
    this override, and therefore also become conditional-on-survival measures.
    The actuarial valuation never receives this private training-only basis.
    """

    def monthly_q_curve(self, *args: object, **kwargs: object) -> Array:
        # Let the canonical implementation validate ages, horizons and grid
        # alignment, then remove every decrement including the terminal-age
        # sentinel.  Contractual terminal closeout remains a horizon event,
        # not a competing Policyholder stopping action.
        validated = super().monthly_q_curve(*args, **kwargs)
        return np.zeros_like(validated, dtype=float)


def mortality_free_policyholder_basis(
    mortality: MortalityTable,
) -> _MortalityFreeLSMCBasis:
    """Return the zero-decrement basis used for the customer LSMC fit."""
    if not isinstance(mortality, MortalityTable):
        raise TypeError("mortality must be MortalityTable.")
    return _MortalityFreeLSMCBasis(
        qx_male=mortality.qx_male,
        qx_female=mortality.qx_female,
        base_year=mortality.base_year,
        improvement_rate=mortality.improvement_rate,
        improvement_taper_age=mortality.improvement_taper_age,
        improvement_end_age=mortality.improvement_end_age,
        stress_multiplier=mortality.stress_multiplier,
        q_add_first_year=mortality.q_add_first_year,
    )

# Economically compact v2 basis.  Ratios are measured against net premium and
# all features are observable at the decision timestamp.  Deliberately omitted
# are the former cubic terms and correlated value-level cross-products.
FEATURE_NAMES = (
    "log1p_account_value_ratio",
    "surrender_value_ratio",
    "annual_income_ratio",
    "guarantee_log_moneyness",
    "mva_haircut_ratio",
    "attained_age_scaled",
    "duration_years_scaled",
    "short_rate",
    "five_year_rate_slope",
    "sqrt_heston_variance",
    "primary_alive",
    "spouse_alive",
    "announced_cap",
    "previous_reference_return",
    "performance_gap",
    "account_value_sq",
    "surrender_value_sq",
    "annual_income_sq",
    "guarantee_moneyness_sq",
    "account_value_x_guarantee_moneyness",
    "annual_income_x_guarantee_moneyness",
    "surrender_value_x_guarantee_moneyness",
    "guarantee_moneyness_x_short_rate",
)

# The documented linear fallback contains only AV, Income, Moneyness, time
# and rates.  Product controls (including MVA) deliberately remain full-basis
# features and cannot leak into this fallback.
CORE_FEATURE_INDICES = np.asarray(
    (0, 1, 2, 3, 5, 6, 7, 8, 10, 11), dtype=np.int64
)
RIDGE_GRID_DEFAULT = (0.0, 1.0e-8, 1.0e-6, 1.0e-4, 1.0e-2)


@dataclass(frozen=True)
class OptimalBehaviourLSMCSettings:
    """Numerical settings for the backward LSMC fit."""

    ridge: float = 1.0e-6
    ridge_grid: tuple[float, ...] = RIDGE_GRID_DEFAULT
    n_folds: int = 5
    fold_seed: int = 9137
    exercise_tolerance_aud: float = 1.0e-8
    # A positive RMSE buffer would deliberately reject some positive fitted
    # advantages.  The productive Swing rule instead applies the fitted
    # expected-PV argmax, subject only to the numerical exercise tolerance.
    exercise_buffer_rmse_multiplier: float = 0.0
    minimum_inforce_weight: float = 1.0e-10
    relative_svd_cutoff: float = 1.0e-8
    maximum_condition_number: float = 1.0e8
    minimum_regression_observations: int = 100
    observations_per_coefficient: int = 10
    immaterial_exposure_fraction: float = 1.0e-6
    fallback_to_no_action_if_training_underperforms: bool = False
    # Deprecated compatibility control for the isolated monthly-action API.
    # The combined annual optimal-behaviour fit ignores it and never permits
    # or produces a Partial Withdrawal.
    allow_partial_withdrawal: bool = False

    def __post_init__(self) -> None:
        numeric = np.asarray([
            self.ridge,
            self.exercise_tolerance_aud,
            self.exercise_buffer_rmse_multiplier,
            self.minimum_inforce_weight,
            self.relative_svd_cutoff,
            self.maximum_condition_number,
            self.immaterial_exposure_fraction,
        ], dtype=float)
        if not np.all(np.isfinite(numeric)) or np.any(numeric < 0.0):
            raise ValueError("LSMC numeric controls must be finite and non-negative.")
        if self.maximum_condition_number <= 1.0:
            raise ValueError("maximum_condition_number must exceed one.")
        if not 0.0 < self.relative_svd_cutoff < 1.0:
            raise ValueError("relative_svd_cutoff must lie strictly between zero and one.")
        ridge_grid = tuple(float(value) for value in self.ridge_grid)
        if not ridge_grid or any(
            not np.isfinite(value) or value < 0.0 for value in ridge_grid
        ):
            raise ValueError("ridge_grid must contain finite non-negative values.")
        ridge_grid = tuple(sorted(set((*ridge_grid, float(self.ridge)))))
        object.__setattr__(self, "ridge_grid", ridge_grid)
        for name in (
            "minimum_regression_observations",
            "observations_per_coefficient",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) \
                    or int(value) < 2:
                raise ValueError(f"{name} must be an integer of at least two.")
        if isinstance(self.n_folds, bool) or not isinstance(
                self.n_folds, (int, np.integer)) or self.n_folds < 2:
            raise ValueError("n_folds must be an integer of at least two.")
        if isinstance(self.fold_seed, bool) or not isinstance(
                self.fold_seed, (int, np.integer)) or self.fold_seed < 0:
            raise ValueError("fold_seed must be a non-negative integer.")
        if not isinstance(
            self.fallback_to_no_action_if_training_underperforms,
            (bool, np.bool_),
        ):
            raise ValueError("fallback_to_no_action_if_training_underperforms must be boolean.")
        if not isinstance(self.allow_partial_withdrawal, (bool, np.bool_)):
            raise ValueError("allow_partial_withdrawal must be boolean.")


@dataclass(frozen=True)
class LSMCRegressionDiagnostic:
    policy_year: int
    decision_step: int
    observations: int
    folds_used: int
    feature_count: int
    matrix_rank: int
    condition_number: Optional[float]
    oof_rmse_aud: Optional[float]
    oof_r_squared: Optional[float]
    mean_immediate_value_aud: float
    mean_continuation_target_aud: float
    training_exercise_rate: float
    regression_accepted_for_exercise: bool
    fallback_reason: Optional[str] = None
    selected_ridge: Optional[float] = None
    effective_rank: int = 0
    basis_level: str = "full"
    oof_policy_uplift_aud: Optional[float] = None
    relevant_exposure_fraction: float = 0.0

    def as_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class SurrenderContinuationRegressionDiagnostic:
    """Stability audit for one externally supplied continuation target."""

    decision_step: int
    observations: int
    folds_used: int
    feature_count: int
    matrix_rank: int
    condition_number: Optional[float]
    oof_rmse_aud: Optional[float]
    oof_r_squared: Optional[float]
    mean_continuation_target_aud: float
    regression_accepted_for_exercise: bool
    fallback_reason: Optional[str]
    selected_ridge: Optional[float] = None
    effective_rank: int = 0
    basis_level: str = "full"
    oof_policy_uplift_aud: Optional[float] = None
    relevant_exposure_fraction: float = 0.0

    def as_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


def build_surrender_regression_features(
    context: SurrenderDecisionContext,
    premium: float,
) -> Array:
    """Build the reusable adapted feature matrix for one decision context.

    Only fields on :class:`SurrenderDecisionContext` are used.  Consequently
    the feature surface cannot access future market returns, future discount
    factors, later caps, hedge P&L or backing assets.
    """
    if not isinstance(context, SurrenderDecisionContext):
        raise TypeError("LSMC features require SurrenderDecisionContext.")
    return build_surrender_regression_features_from_arrays(
        account_value=context.account_value,
        surrender_value=context.surrender_value,
        locked_annual_income=context.locked_annual_income,
        guarantee_pv=context.guarantee_pv,
        guarantee_log_moneyness=context.guarantee_log_moneyness,
        short_rate=context.short_rate,
        zero_rate_5y=context.zero_rate_5y,
        heston_variance=context.heston_variance,
        duration_years=context.duration_years,
        announced_cap=context.announced_cap,
        previous_reference_return=context.previous_reference_return,
        previous_credited_return=context.previous_credited_return,
        performance_gap=context.performance_gap,
        premium=premium,
        mva_factor=context.mva_factor,
        attained_age=context.attained_age,
        primary_alive=context.primary_alive,
        spouse_alive=context.spouse_alive,
    )


def build_surrender_regression_features_from_arrays(
    *,
    account_value: object,
    surrender_value: object,
    locked_annual_income: object,
    guarantee_pv: object,
    guarantee_log_moneyness: object,
    short_rate: object,
    zero_rate_5y: object,
    heston_variance: object,
    duration_years: object,
    announced_cap: object,
    previous_reference_return: object,
    previous_credited_return: object,
    performance_gap: object,
    premium: object,
    mva_factor: object = 0.0,
    attained_age: object = 0.0,
    primary_alive: object = 1.0,
    spouse_alive: object = 0.0,
) -> Array:
    """Build the canonical compact v2 policyholder features from arrays.

    Each input may be a scalar or a one-dimensional observation array.  The
    inputs are broadcast to one common path/row axis and the result has shape
    ``(n_observations, len(FEATURE_NAMES))``.  This is the array-native entry
    point for fitted-control algorithms: they can retain compact annual state
    tensors instead of thousands of :class:`SurrenderDecisionContext` objects.

    The feature definition is deliberately identical to
    :func:`build_surrender_regression_features`.  No future return, discount,
    hedge result or backing-asset input is accepted by this API.
    """
    # Retain the historical keyword in this low-level signature so external
    # research callers do not break, but v2 intentionally excludes the
    # redundant credited-return level from its design matrix.
    del previous_credited_return
    values = {
        "account_value": account_value,
        "surrender_value": surrender_value,
        "locked_annual_income": locked_annual_income,
        "guarantee_pv": guarantee_pv,
        "guarantee_log_moneyness": guarantee_log_moneyness,
        "short_rate": short_rate,
        "zero_rate_5y": zero_rate_5y,
        "heston_variance": heston_variance,
        "duration_years": duration_years,
        "announced_cap": announced_cap,
        "previous_reference_return": previous_reference_return,
        "performance_gap": performance_gap,
        "premium": premium,
        "mva_factor": mva_factor,
        "attained_age": attained_age,
        "primary_alive": primary_alive,
        "spouse_alive": spouse_alive,
    }
    arrays: list[Array] = []
    for name, value in values.items():
        array = np.asarray(value, dtype=float)
        if array.ndim > 1:
            raise ValueError(
                f"Surrender feature input {name} must be scalar or one-dimensional."
            )
        arrays.append(array)
    try:
        broadcast = np.broadcast_arrays(*arrays)
    except ValueError as exc:
        raise ValueError(
            "Surrender feature inputs must broadcast to one observation axis."
        ) from exc

    data = {
        name: np.asarray(array, dtype=float).reshape(-1)
        for name, array in zip(values, broadcast)
    }
    if not np.all(np.isfinite(data["premium"])) \
            or np.any(data["premium"] <= 0.0):
        raise ValueError("LSMC feature premium must be positive and finite.")
    cap_input = data["announced_cap"]
    if np.any(np.isnan(cap_input)) or np.any(np.isneginf(cap_input)) \
            or np.any(cap_input < 0.0):
        raise ValueError(
            "Announced cap must be non-negative and finite or positive infinity."
        )
    for name, array in data.items():
        if name in ("premium", "announced_cap"):
            continue
        if not np.all(np.isfinite(array)):
            raise ValueError(f"Non-finite surrender feature input: {name}.")
    if np.any(data["duration_years"] < 0.0):
        raise ValueError("Surrender feature duration must be non-negative.")

    premium_array = data["premium"]
    x = np.maximum(data["account_value"], 0.0) / premium_array
    log_x = np.log1p(x)
    surrender = np.maximum(data["surrender_value"], 0.0) / premium_array
    y = np.maximum(data["locked_annual_income"], 0.0) / premium_array
    m = data["guarantee_log_moneyness"]
    # ``mva_factor`` is the Projector's current non-negative MVA bite as a
    # fraction of gross withdrawal/Account Value (zero means no haircut).
    mva_haircut = np.clip(data["mva_factor"], 0.0, 1.0)
    attained_age = data["attained_age"] / 100.0
    r = data["short_rate"]
    z5 = data["zero_rate_5y"]
    sqrt_v = np.sqrt(np.maximum(data["heston_variance"], 0.0))
    duration = data["duration_years"] / 100.0
    # ``+inf`` is the explicit uncapped benchmark.  Regression design matrices
    # must remain finite, so encode that special state as a documented 100%
    # annual cap sentinel, safely above the admissible 0.25%-20% control grid.
    cap = np.where(np.isposinf(cap_input), 1.0, cap_input)
    reference_return = data["previous_reference_return"]
    gap = np.maximum(data["performance_gap"], 0.0)

    out = np.column_stack((
        log_x,
        surrender,
        y,
        m,
        mva_haircut,
        attained_age,
        duration,
        r,
        z5 - r,
        sqrt_v,
        data["primary_alive"],
        data["spouse_alive"],
        cap,
        reference_return,
        gap,
        log_x * log_x,
        surrender * surrender,
        y * y,
        m * m,
        log_x * m,
        y * m,
        surrender * m,
        m * r,
    ))
    if out.shape[1] != len(FEATURE_NAMES):
        raise RuntimeError("LSMC feature names and feature matrix are inconsistent.")
    if not np.all(np.isfinite(out)):
        raise ValueError("Non-finite LSMC state feature encountered.")
    return np.asarray(out, dtype=float)


@dataclass(frozen=True)
class _ContinuationRegression:
    premium: float
    raw_feature_count: int
    active_feature_indices: NDArray[np.int64]
    orthogonal_components: Array
    centre: Array
    scale: Array
    coefficients: Array
    condition_number: float
    matrix_rank: int
    oof_rmse_aud: float
    selected_ridge: float = 0.0
    effective_rank: int = 0
    basis_level: str = "full"
    clip_non_negative: bool = True
    # Optional cached affine representation.  Defaults preserve evaluation of
    # regression objects persisted before the v3 performance upgrade.
    raw_intercept_aud: Optional[float] = None
    raw_coefficients_aud: Optional[Array] = None

    def raw_affine_form(self) -> tuple[float, Array]:
        """Return the exact AUD affine surface in original feature space."""
        cached_intercept = getattr(self, "raw_intercept_aud", None)
        cached_coefficients = getattr(self, "raw_coefficients_aud", None)
        if cached_intercept is not None and cached_coefficients is not None:
            coefficients = np.asarray(cached_coefficients, dtype=float)
            if coefficients.shape == (self.raw_feature_count,):
                return float(cached_intercept), coefficients

        raw_coefficients_normalised = np.zeros(self.raw_feature_count)
        if self.active_feature_indices.size:
            component_loadings = (
                self.orthogonal_components.T @ self.coefficients[1:]
            )
            raw_coefficients_normalised[self.active_feature_indices] = (
                component_loadings / self.scale
            )
        raw_intercept_normalised = float(self.coefficients[0]) - float(np.dot(
            raw_coefficients_normalised[self.active_feature_indices],
            self.centre,
        ))
        return (
            raw_intercept_normalised * self.premium,
            raw_coefficients_normalised * self.premium,
        )

    def predict_features(self, raw_features: Array) -> Array:
        """Evaluate a frozen level or paired-advantage regression."""
        raw = np.asarray(raw_features, dtype=float)
        if raw.ndim != 2 or raw.shape[1] != self.raw_feature_count:
            raise ValueError(
                f"Regression features must have shape (n, {self.raw_feature_count})."
            )
        if not np.all(np.isfinite(raw)):
            raise ValueError("Surrender features must be finite.")
        # The PCA/SVD representation is affine in the original feature space.
        # Store that affine form once at fit time so every policy rollout uses
        # one BLAS matrix-vector multiply instead of repeated standardisation,
        # projection and design-matrix allocation.
        raw_intercept, raw_coefficients = self.raw_affine_form()
        prediction = raw @ raw_coefficients + raw_intercept
        return np.maximum(prediction, 0.0) if self.clip_non_negative else prediction

    def predict(self, context: SurrenderDecisionContext) -> Array:
        raw = build_surrender_regression_features(context, self.premium)
        return self.predict_features(raw)


class _MaterialCrossFitCoverageError(RuntimeError):
    """A fitted training policy has no model for material rollout exposure."""


@dataclass
class OptimalSurrenderPolicy:
    """Frozen continuation regressions used by the monthly projector."""

    regressions: Mapping[int, _ContinuationRegression]
    settings: OptimalBehaviourLSMCSettings
    provenance_fingerprint: Optional[str] = None
    regressions_are_advantages: bool = False
    strict_missing_material_regression: bool = False
    terminal_step: Optional[int] = None
    evaluation_statistics: dict[int, dict[str, int]] = field(default_factory=dict)
    anniversary_only: bool = field(default=True, init=False, repr=False)

    def surrender_mask(
        self,
        *,
        context: SurrenderDecisionContext,
    ) -> NDArray[np.bool_]:
        """Return adapted out-of-sample Full-Withdrawal decisions.

        The strict context-only signature is intentional: realised future
        returns, future discounts, later caps and insurer hedge results are not
        available to this policy.
        """
        if not isinstance(context, SurrenderDecisionContext):
            raise TypeError("Optimal surrender requires SurrenderDecisionContext.")
        step = context.step
        n_paths = context.n_paths
        if not context.is_anniversary:
            return np.zeros(n_paths, dtype=bool)
        if self.terminal_step is not None and step >= self.terminal_step:
            return np.zeros(n_paths, dtype=bool)
        eligible = (
            context.full_withdrawal_eligible
            & (context.phase == Phase.INCOME.value)
            & (context.inforce_weight > self.settings.minimum_inforce_weight)
        )
        # A zero surrender payment cannot dominate a strictly positive locked
        # lifetime income for a covered survivor.  Exclude this contractual
        # dominance region deterministically instead of asking a noisy
        # regression to manufacture an exercise boundary there.
        covered_alive = np.asarray(context.primary_alive, dtype=bool) | np.asarray(
            context.spouse_alive, dtype=bool
        )
        dominated_zero_surrender = (
            context.surrender_value <= self.settings.exercise_tolerance_aud
        ) & (
            context.locked_annual_income > self.settings.exercise_tolerance_aud
        ) & covered_alive
        eligible &= ~dominated_zero_surrender
        if not np.any(eligible):
            return np.zeros(n_paths, dtype=bool)
        if step not in self.regressions:
            exposure = float(np.mean(np.where(
                eligible, context.inforce_weight, 0.0
            )))
            if self.strict_missing_material_regression \
                    and exposure > self.settings.immaterial_exposure_fraction:
                raise RuntimeError(
                    "Material Full-Withdrawal regression is missing at "
                    f"step {step} (exposure={exposure:.12g})."
                )
            return np.zeros(n_paths, dtype=bool)
        regression = self.regressions[step]
        stable = (
            regression.matrix_rank == regression.coefficients.size
            and regression.condition_number
            <= self.settings.maximum_condition_number
        )
        if not stable:
            return np.zeros(n_paths, dtype=bool)
        buffer = (
            self.settings.exercise_tolerance_aud
            + self.settings.exercise_buffer_rmse_multiplier
            * regression.oof_rmse_aud
        )
        prediction = regression.predict(context)
        exercise = (
            eligible & (prediction > buffer)
            if self.regressions_are_advantages
            else eligible & (context.surrender_value > prediction + buffer)
        )
        stats = self.evaluation_statistics.setdefault(
            int(step), {"eligible_path_count": 0, "exercise_path_count": 0})
        stats["eligible_path_count"] += int(np.count_nonzero(eligible))
        stats["exercise_path_count"] += int(np.count_nonzero(exercise))
        return exercise


@dataclass
class CrossFittedOptimalSurrenderPolicy:
    """Training-only policy whose decision for each path is out of fold."""

    regressions_by_step: Mapping[int, tuple[_ContinuationRegression, ...]]
    fold_ids_by_step: Mapping[int, NDArray[np.int64]]
    settings: OptimalBehaviourLSMCSettings
    regressions_are_advantages: bool = False
    strict_missing_material_regression: bool = False
    terminal_step: Optional[int] = None
    anniversary_only: bool = field(default=True, init=False, repr=False)

    def surrender_mask(
        self,
        *,
        context: SurrenderDecisionContext,
    ) -> NDArray[np.bool_]:
        if not isinstance(context, SurrenderDecisionContext):
            raise TypeError("Cross-fitted surrender requires decision context.")
        step = int(context.step)
        if not context.is_anniversary:
            return np.zeros(context.n_paths, dtype=bool)
        if self.terminal_step is not None and step >= self.terminal_step:
            return np.zeros(context.n_paths, dtype=bool)
        if step not in self.regressions_by_step:
            eligible = (
                context.full_withdrawal_eligible
                & (context.phase == Phase.INCOME.value)
                & (context.inforce_weight > self.settings.minimum_inforce_weight)
            )
            covered_alive = (
                np.asarray(context.primary_alive, dtype=bool)
                | np.asarray(context.spouse_alive, dtype=bool)
            )
            eligible &= ~(
                (
                    context.surrender_value
                    <= self.settings.exercise_tolerance_aud
                )
                & (
                    context.locked_annual_income
                    > self.settings.exercise_tolerance_aud
                )
                & covered_alive
            )
            exposure = float(np.mean(np.where(
                eligible, context.inforce_weight, 0.0
            )))
            if self.strict_missing_material_regression \
                    and exposure > self.settings.immaterial_exposure_fraction:
                raise _MaterialCrossFitCoverageError(
                    "Material cross-fitted Full regression is missing at "
                    f"step {step} (exposure={exposure:.12g})."
                )
            return np.zeros(context.n_paths, dtype=bool)
        fold_ids = np.asarray(self.fold_ids_by_step[step], dtype=np.int64)
        if fold_ids.shape != (context.n_paths,):
            raise ValueError(
                "Cross-fitted training policy can be used only on its original "
                "complete path sample."
            )
        eligible = (
            context.full_withdrawal_eligible
            & (context.phase == Phase.INCOME.value)
            & (context.inforce_weight > self.settings.minimum_inforce_weight)
        )
        covered_alive = (
            np.asarray(context.primary_alive, dtype=bool)
            | np.asarray(context.spouse_alive, dtype=bool)
        )
        eligible &= ~(
            (
                context.surrender_value
                <= self.settings.exercise_tolerance_aud
            )
            & (
                context.locked_annual_income
                > self.settings.exercise_tolerance_aud
            )
            & covered_alive
        )
        prediction = np.zeros(context.n_paths)
        stable = np.ones(context.n_paths, dtype=bool)
        buffer = np.full(
            context.n_paths, self.settings.exercise_tolerance_aud, dtype=float
        )
        regressions = self.regressions_by_step[step]
        for fold, regression in enumerate(regressions):
            selected = fold_ids == fold
            if not np.any(selected):
                continue
            fold_prediction = regression.predict(context)
            prediction[selected] = fold_prediction[selected]
            fold_stable = (
                regression.matrix_rank == regression.coefficients.size
                and regression.condition_number
                <= self.settings.maximum_condition_number
            )
            stable[selected] = fold_stable
            buffer[selected] += (
                self.settings.exercise_buffer_rmse_multiplier
                * regression.oof_rmse_aud
            )
        return (
            eligible & stable & (prediction > buffer)
            if self.regressions_are_advantages
            else eligible & stable & (context.surrender_value > prediction + buffer)
        )


@dataclass(frozen=True)
class SurrenderContinuationPolicyFit:
    """Frozen context policy fitted to externally constructed Bellman targets.

    ``oof_continuation_by_step`` contains only accepted regressions.  A step
    omitted from that mapping is also absent from ``policy.regressions`` and
    therefore follows the conservative Continue action.  ``fold_ids_by_step``
    records the complete-path grouping used for the out-of-fold predictions.
    """

    policy: OptimalSurrenderPolicy
    oof_continuation_by_step: Mapping[int, Array]
    fold_ids_by_step: Mapping[int, NDArray[np.int64]]
    diagnostics: tuple[SurrenderContinuationRegressionDiagnostic, ...]

    def __post_init__(self) -> None:
        oof: dict[int, Array] = {}
        for step, values in self.oof_continuation_by_step.items():
            snapshot = np.array(values, dtype=float, copy=True)
            snapshot.flags.writeable = False
            oof[int(step)] = snapshot
        folds: dict[int, NDArray[np.int64]] = {}
        for step, values in self.fold_ids_by_step.items():
            snapshot = np.array(values, dtype=np.int64, copy=True)
            snapshot.flags.writeable = False
            folds[int(step)] = snapshot
        object.__setattr__(self, "oof_continuation_by_step", MappingProxyType(oof))
        object.__setattr__(self, "fold_ids_by_step", MappingProxyType(folds))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    @property
    def fallback_steps(self) -> tuple[int, ...]:
        return tuple(
            diagnostic.decision_step
            for diagnostic in self.diagnostics
            if not diagnostic.regression_accepted_for_exercise
        )


@dataclass(frozen=True)
class OptimalBehaviourLSMCFit:
    policy: OptimalSurrenderPolicy
    cross_fitted_training_policy: CrossFittedOptimalSurrenderPolicy
    diagnostics: tuple[LSMCRegressionDiagnostic, ...]
    training_scenario_fingerprint: str
    training_path_count: int
    training_policyholder_value_aud: float
    training_no_action_policyholder_value_aud: float
    training_candidate_policyholder_value_aud: float
    training_fallback_used: bool

    @property
    def training_optionality_uplift_aud(self) -> float:
        return (
            self.training_policyholder_value_aud
            - self.training_no_action_policyholder_value_aud
        )


def no_voluntary_action_behaviour(
    source: Optional[BehaviourModel] = None,
) -> BehaviourModel:
    """Remove statistical actions from the projector's fallback behaviour.

    Without an external policy this is the legacy deterministic-Election / no
    voluntary-exit benchmark.  Combined LSMC rollouts pass an external policy
    whose Election and surrender hooks take precedence over these fallbacks.
    """
    base = source or BehaviourModel.static_only()
    return replace(
        base,
        regime="static",
        lapse=LapseAssumptions(growth_phase=(0.0,), income_phase=0.0),
        take_up=replace(base.take_up, mode="deterministic"),
        withdrawals=WithdrawalBehaviour(
            free_utilisation=0.0,
            excess_rate=0.0,
            frequency=base.withdrawals.frequency,
        ),
    )


@dataclass
class _SurrenderContextRecorder:
    """No-action hook recording exact annual projector decision states."""

    contexts: dict[int, SurrenderDecisionContext] = field(default_factory=dict)
    anniversary_only: bool = field(default=True, init=False, repr=False)

    def surrender_mask(
        self,
        *,
        context: SurrenderDecisionContext,
    ) -> NDArray[np.bool_]:
        self.contexts[int(context.step)] = context
        return np.zeros(context.n_paths, dtype=bool)


@dataclass(frozen=True)
class _PreparedRegressionDesign:
    """One SVD-prepared design reused across the complete Ridge grid."""

    raw_feature_count: int
    active_feature_indices: NDArray[np.int64]
    orthogonal_components: Array
    centre: Array
    scale: Array
    orthogonal_scores: Array
    singular_values: Array
    condition_number: float
    matrix_rank: int
    effective_rank: int
    basis_level: str


def _prepare_regression_design(
    raw_features: Array,
    *,
    relative_svd_cutoff: float,
    feature_indices: Optional[NDArray[np.int64]] = None,
    basis_level: str = "full",
) -> _PreparedRegressionDesign:
    """Standardise and orthogonalise a regression sample exactly once."""
    raw = np.asarray(raw_features, dtype=float)
    if raw.ndim != 2 or raw.shape[0] < 2 or not np.all(np.isfinite(raw)):
        raise ValueError("Regression features must contain finite observations.")
    if not 0.0 < relative_svd_cutoff < 1.0:
        raise ValueError("relative_svd_cutoff must lie in (0, 1).")

    selected = (
        np.arange(raw.shape[1], dtype=np.int64)
        if feature_indices is None
        else np.asarray(feature_indices, dtype=np.int64)
    )
    if selected.ndim != 1 or np.any(selected < 0) \
            or np.any(selected >= raw.shape[1]) \
            or np.unique(selected).size != selected.size:
        raise ValueError("Regression feature indices are invalid.")

    selected_centre = np.mean(raw[:, selected], axis=0)
    selected_scale = np.std(raw[:, selected], axis=0)
    varying = selected_scale > 1.0e-10
    active = selected[varying]
    centre = selected_centre[varying]
    scale = selected_scale[varying]
    if active.size:
        standardised = (raw[:, active] - centre) / scale
        # One correction makes the intercept numerically orthogonal to every
        # feature score.  It preserves the represented affine surface while
        # allowing all Ridge solutions to use the singular spectrum directly.
        centring_correction = np.mean(standardised, axis=0)
        centre = centre + centring_correction * scale
        standardised = standardised - centring_correction
        left, singular, right = np.linalg.svd(
            standardised, full_matrices=False
        )
        if singular.size and singular[0] > 0.0:
            keep = singular >= relative_svd_cutoff * float(singular[0])
            retained_singular = singular[keep]
            components = right[keep]
            scores = left[:, keep] * retained_singular
        else:
            retained_singular = np.zeros(0)
            components = np.zeros((0, active.size))
            scores = np.zeros((raw.shape[0], 0))
    else:
        retained_singular = np.zeros(0)
        components = np.zeros((0, 0))
        scores = np.zeros((raw.shape[0], 0))

    solve_singular = np.concatenate((
        np.asarray([np.sqrt(raw.shape[0])], dtype=float),
        np.asarray(retained_singular, dtype=float),
    ))
    positive = solve_singular > 0.0
    condition = (
        float(np.max(solve_singular[positive]) / np.min(solve_singular[positive]))
        if np.any(positive)
        else float("inf")
    )
    return _PreparedRegressionDesign(
        raw_feature_count=int(raw.shape[1]),
        active_feature_indices=np.asarray(active, dtype=np.int64),
        orthogonal_components=np.asarray(components, dtype=float),
        centre=np.asarray(centre, dtype=float),
        scale=np.asarray(scale, dtype=float),
        orthogonal_scores=np.asarray(scores, dtype=float),
        singular_values=np.asarray(retained_singular, dtype=float),
        condition_number=condition,
        matrix_rank=int(1 + retained_singular.size),
        effective_rank=int(1 + retained_singular.size),
        basis_level=str(basis_level),
    )


def _solve_prepared_regression(
    prepared: _PreparedRegressionDesign,
    target_aud: Array,
    premium: float,
    ridge: float,
    *,
    oof_rmse_aud: float = 0.0,
    clip_non_negative: bool = True,
) -> _ContinuationRegression:
    """Solve one Ridge value in the already orthogonalised design."""
    target_aud_array = np.asarray(target_aud, dtype=float)
    n_obs = prepared.orthogonal_scores.shape[0]
    if target_aud_array.shape != (n_obs,) or not np.all(
        np.isfinite(target_aud_array)
    ):
        raise ValueError("Regression targets must match the prepared sample.")
    if not np.isfinite(premium) or premium <= 0.0:
        raise ValueError("Regression premium must be positive and finite.")
    if not np.isfinite(ridge) or ridge < 0.0:
        raise ValueError("Ridge must be finite and non-negative.")

    target = target_aud_array / float(premium)
    intercept = float(np.mean(target))
    if prepared.singular_values.size:
        centred_target = target - intercept
        numerator = prepared.orthogonal_scores.T @ centred_target
        denominator = prepared.singular_values ** 2 + float(ridge)
        component_coefficients = np.divide(
            numerator,
            denominator,
            out=np.zeros_like(numerator),
            where=denominator > 0.0,
        )
    else:
        component_coefficients = np.zeros(0)
    coefficients = np.concatenate((
        np.asarray([intercept], dtype=float),
        np.asarray(component_coefficients, dtype=float),
    ))
    if not np.all(np.isfinite(coefficients)):
        raise ValueError("LSMC regression produced non-finite coefficients.")

    raw_coefficients_normalised = np.zeros(prepared.raw_feature_count)
    if prepared.active_feature_indices.size:
        active_component_loadings = (
            prepared.orthogonal_components.T @ component_coefficients
        )
        raw_coefficients_normalised[prepared.active_feature_indices] = (
            active_component_loadings / prepared.scale
        )
    raw_intercept_normalised = intercept - float(np.dot(
        raw_coefficients_normalised[prepared.active_feature_indices],
        prepared.centre,
    ))
    return _ContinuationRegression(
        premium=float(premium),
        raw_feature_count=prepared.raw_feature_count,
        active_feature_indices=prepared.active_feature_indices,
        orthogonal_components=prepared.orthogonal_components,
        centre=prepared.centre,
        scale=prepared.scale,
        coefficients=coefficients,
        raw_intercept_aud=float(raw_intercept_normalised * premium),
        raw_coefficients_aud=np.asarray(
            raw_coefficients_normalised * premium, dtype=float
        ),
        condition_number=prepared.condition_number,
        matrix_rank=prepared.matrix_rank,
        oof_rmse_aud=float(oof_rmse_aud),
        selected_ridge=float(ridge),
        effective_rank=prepared.effective_rank,
        basis_level=prepared.basis_level,
        clip_non_negative=bool(clip_non_negative),
    )


def _fit_regression(
    raw_features: Array,
    target_aud: Array,
    premium: float,
    ridge: float,
    *,
    oof_rmse_aud: float = 0.0,
    relative_svd_cutoff: float = 1.0e-8,
    feature_indices: Optional[NDArray[np.int64]] = None,
    basis_level: str = "full",
    clip_non_negative: bool = True,
) -> _ContinuationRegression:
    """Fit one model; callers with a Ridge grid should reuse its prepared SVD."""
    prepared = _prepare_regression_design(
        raw_features,
        relative_svd_cutoff=relative_svd_cutoff,
        feature_indices=feature_indices,
        basis_level=basis_level,
    )
    return _solve_prepared_regression(
        prepared,
        target_aud,
        premium,
        ridge,
        oof_rmse_aud=oof_rmse_aud,
        clip_non_negative=clip_non_negative,
    )


def _minimum_cross_fit_observations(
    settings: OptimalBehaviourLSMCSettings,
    coefficient_count: int,
) -> int:
    minimum_train = max(
        settings.minimum_regression_observations,
        settings.observations_per_coefficient * int(coefficient_count),
    )
    return int(np.floor(
        minimum_train * settings.n_folds / (settings.n_folds - 1)
    )) + 1


def fit_surrender_continuation_regression(
    raw_features: Array,
    continuation_target_aud: Array,
    *,
    premium: float,
    settings: OptimalBehaviourLSMCSettings = OptimalBehaviourLSMCSettings(),
    oof_rmse_aud: float = 0.0,
) -> _ContinuationRegression:
    """Fit one canonical frozen continuation regression without product logic.

    Coupled-control callers can use this low-level boundary to fit a model on
    an explicit outer-fold training mask and evaluate it through
    :meth:`_ContinuationRegression.predict_features`.  The feature basis and
    numerical representation are exactly the same as the forward
    :class:`OptimalSurrenderPolicy`; no insurer objective enters the fit.
    """
    if not isinstance(settings, OptimalBehaviourLSMCSettings):
        raise TypeError("settings must be OptimalBehaviourLSMCSettings.")
    raw = np.asarray(raw_features, dtype=float)
    target = np.asarray(continuation_target_aud, dtype=float)
    if raw.ndim != 2 or raw.shape[1] != len(FEATURE_NAMES):
        raise ValueError(
            f"Surrender features must have shape (n, {len(FEATURE_NAMES)})."
        )
    if target.shape != (raw.shape[0],):
        raise ValueError(
            f"Continuation target must have shape ({raw.shape[0]},)."
        )
    if raw.shape[0] < 2:
        raise ValueError("At least two continuation observations are required.")
    if not np.all(np.isfinite(raw)) or not np.all(np.isfinite(target)):
        raise ValueError("Continuation regression inputs must be finite.")
    premium_value = float(premium)
    if not np.isfinite(premium_value) or premium_value <= 0.0:
        raise ValueError("Continuation-regression premium must be positive and finite.")
    if not np.isfinite(oof_rmse_aud) or oof_rmse_aud < 0.0:
        raise ValueError("oof_rmse_aud must be finite and non-negative.")
    return _fit_regression(
        raw,
        target,
        premium_value,
        settings.ridge,
        oof_rmse_aud=float(oof_rmse_aud),
        relative_svd_cutoff=settings.relative_svd_cutoff,
    )


def _cross_fitted_regression(
    raw_features: Array,
    target_aud: Array,
    premium: float,
    settings: OptimalBehaviourLSMCSettings,
    fold_ids: NDArray[np.int64],
    *,
    advantage_target: bool = False,
    feature_indices: Optional[NDArray[np.int64]] = None,
    basis_level: str = "full",
    enforce_unique_path_minimum: bool = False,
) -> tuple[
    _ContinuationRegression,
    Array,
    int,
    tuple[_ContinuationRegression, ...],
]:
    raw = np.asarray(raw_features, dtype=float)
    target = np.asarray(target_aud, dtype=float)
    if raw.ndim != 2 or target.shape != (raw.shape[0],) \
            or not np.all(np.isfinite(raw)) or not np.all(np.isfinite(target)):
        raise ValueError("Cross-fit regression inputs are inconsistent or non-finite.")
    n_obs = raw.shape[0]
    selected = (
        np.arange(raw.shape[1], dtype=np.int64)
        if feature_indices is None
        else np.asarray(feature_indices, dtype=np.int64)
    )
    if selected.ndim != 1 or np.any(selected < 0) \
            or np.any(selected >= raw.shape[1]) \
            or np.unique(selected).size != selected.size:
        raise ValueError("Regression feature indices are invalid.")
    # A sparse but economically material far-tail Income boundary can have too
    # few surviving paths for the full or core state basis even in a large
    # simulation. The final member of the documented hierarchy is an
    # intercept-only advantage regression. It still uses complete-path
    # cross-fitting and the direct expected-advantage argmax, so it is an
    # estimator on a coarser information set rather than a behavioural
    # Continue/fixed-policy fallback.
    sparse_constant_advantage = bool(
        advantage_target
        and selected.size == 0
        and not enforce_unique_path_minimum
    )
    total_observation_floor = (
        max(2 * settings.n_folds, settings.observations_per_coefficient)
        if sparse_constant_advantage
        else settings.minimum_regression_observations
    )
    if n_obs <= total_observation_floor:
        raise ValueError(
            "LSMC requires more observations than the per-regression minimum; "
            f"got {n_obs}."
        )

    supplied_ids = np.asarray(fold_ids, dtype=np.int64)
    if supplied_ids.shape != (n_obs,) or np.any(supplied_ids < 0):
        raise ValueError("Cross-fit IDs must match all regression rows.")

    # Try the largest fold count first.  Each candidate training fold is SVD-
    # prepared once, and its *retained* coefficient count drives the sample
    # gate.  This preserves the original adaptive observation rule without
    # repeating the SVD for every Ridge value or every smaller fold count.
    folds_used: Optional[int] = None
    prepared_folds: list[tuple[
        NDArray[np.bool_], NDArray[np.bool_], _PreparedRegressionDesign
    ]] = []
    for folds in range(settings.n_folds, 1, -1):
        candidate_fold_ids = np.mod(supplied_ids, folds)
        candidate_prepared: list[tuple[
            NDArray[np.bool_], NDArray[np.bool_], _PreparedRegressionDesign
        ]] = []
        viable = True
        for fold in range(folds):
            test = candidate_fold_ids == fold
            train = ~test
            if not np.any(test):
                viable = False
                break
            prepared = _prepare_regression_design(
                raw[train],
                relative_svd_cutoff=settings.relative_svd_cutoff,
                feature_indices=feature_indices,
                basis_level=basis_level,
            )
            regression_observation_floor = (
                settings.observations_per_coefficient
                if sparse_constant_advantage
                else settings.minimum_regression_observations
            )
            minimum_train = max(
                regression_observation_floor,
                settings.observations_per_coefficient
                * prepared.effective_rank,
            )
            if np.count_nonzero(train) < minimum_train:
                viable = False
                break
            if enforce_unique_path_minimum and np.unique(
                supplied_ids[train]
            ).size < minimum_train:
                viable = False
                break
            candidate_prepared.append((train, test, prepared))
        if viable:
            folds_used = folds
            prepared_folds = candidate_prepared
            break
    if folds_used is None:
        raise ValueError(
            "No cross-fit partition leaves the required number of unique "
            "complete paths for its active coefficient count."
        )

    candidate_results: list[tuple[
        float, float, Array, Array, tuple[_ContinuationRegression, ...]
    ]] = []
    for ridge in settings.ridge_grid:
        candidate_oof = np.zeros(n_obs)
        candidate_fold_models: list[_ContinuationRegression] = []
        for train, test, prepared in prepared_folds:
            regression = _solve_prepared_regression(
                prepared,
                target[train],
                premium,
                ridge,
                clip_non_negative=not advantage_target,
            )
            candidate_fold_models.append(regression)
            candidate_oof[test] = regression.predict_features(raw[test])
        if advantage_target:
            # Regret in AUD: realised positive advantage lost by Continue plus
            # realised negative advantage incurred by exercising.  Ridge
            # selection uses the deployment buffer and the candidate OOF RMSE.
            candidate_rmse = float(np.sqrt(np.mean(
                (candidate_oof - target) ** 2
            )))
            candidate_buffer = (
                settings.exercise_tolerance_aud
                + settings.exercise_buffer_rmse_multiplier * candidate_rmse
            )
            action = candidate_oof > candidate_buffer
            losses = np.where(
                action, np.maximum(-target, 0.0), np.maximum(target, 0.0)
            )
        else:
            losses = (candidate_oof - target) ** 2
        candidate_results.append((
            float(np.mean(losses)),
            float(ridge),
            np.asarray(losses, dtype=float),
            candidate_oof,
            tuple(candidate_fold_models),
        ))

    best_mean = min(item[0] for item in candidate_results)
    best_losses = min(candidate_results, key=lambda item: item[0])[2]
    one_standard_error = (
        float(np.std(best_losses, ddof=1) / np.sqrt(n_obs))
        if n_obs > 1 else 0.0
    )
    eligible_candidates = [
        item for item in candidate_results
        if item[0] <= best_mean + one_standard_error + 1.0e-14
    ]
    _score, selected_ridge, _losses, oof, selected_fold_regressions = max(
        eligible_candidates, key=lambda item: item[1]
    )
    rmse = float(np.sqrt(np.mean((oof - target) ** 2)))
    full_prepared = _prepare_regression_design(
        raw,
        relative_svd_cutoff=settings.relative_svd_cutoff,
        feature_indices=feature_indices,
        basis_level=basis_level,
    )
    full = _solve_prepared_regression(
        full_prepared,
        target,
        premium,
        selected_ridge,
        oof_rmse_aud=rmse,
        clip_non_negative=not advantage_target,
    )
    fold_regressions = tuple(
        replace(regression, oof_rmse_aud=rmse)
        for regression in selected_fold_regressions
    )
    return full, oof, folds_used, fold_regressions


def _cross_fitted_advantage_regression(
    raw_features: Array,
    advantage_target_aud: Array,
    premium: float,
    settings: OptimalBehaviourLSMCSettings,
    fold_ids: NDArray[np.int64],
    *,
    core_feature_indices: NDArray[np.int64],
    enforce_unique_path_minimum: bool = False,
) -> tuple[
    _ContinuationRegression,
    Array,
    int,
    tuple[_ContinuationRegression, ...],
]:
    """Fit the documented full -> core -> constant advantage hierarchy."""
    attempts = (
        ("full", None),
        ("core", np.asarray(core_feature_indices, dtype=np.int64)),
        ("constant", np.zeros(0, dtype=np.int64)),
    )
    failures: list[str] = []
    for basis_level, indices in attempts:
        try:
            fit = _cross_fitted_regression(
                raw_features,
                advantage_target_aud,
                premium,
                settings,
                fold_ids,
                advantage_target=True,
                feature_indices=indices,
                basis_level=basis_level,
                enforce_unique_path_minimum=enforce_unique_path_minimum,
            )
            regression, _oof, _folds, fold_regressions = fit
            if _regression_is_stable(regression, settings) and all(
                _regression_is_stable(item, settings)
                for item in fold_regressions
            ):
                return fit
            failures.append(f"{basis_level}:unstable")
        except (ValueError, np.linalg.LinAlgError) as exc:
            failures.append(f"{basis_level}:{exc}")
    raise ValueError(";".join(failures))


def fit_surrender_continuation_policy(
    features_by_step: Mapping[int, Array],
    continuation_targets_aud_by_step: Mapping[int, Array],
    *,
    premium: float,
    settings: OptimalBehaviourLSMCSettings = OptimalBehaviourLSMCSettings(),
    fold_ids_by_step: Optional[Mapping[int, NDArray[np.int64]]] = None,
) -> SurrenderContinuationPolicyFit:
    """Fit a frozen context-aware policy to external continuation targets.

    This is the reusable regression boundary for a coupled control algorithm.
    The caller constructs one policyholder Bellman continuation target per
    complete market/control path and decision step; this function owns the
    common PCA/ridge fit, complete-path cross-fitting, stability gates and the
    conservative Continue fallback.

    ``features_by_step[step]`` must have shape
    ``(n_paths, len(FEATURE_NAMES))`` and the target
    at that step must have shape ``(n_paths,)``.  When ``fold_ids_by_step`` is
    supplied, repeated replicas of one complete path must carry the same
    non-negative integer identifier.  The identifier is reduced modulo the
    effective fold count, so it may be either a fold label or a stable path ID.
    If it is omitted, all steps must have the same path count and one shuffled
    path assignment is reused for every step.

    Too few observations, a failed cross-fit, rank deficiency or an excessive
    condition number does not create an exercise rule.  The affected step is
    omitted from the frozen policy, which makes
    :class:`OptimalSurrenderPolicy` return Continue there.
    """
    if not isinstance(settings, OptimalBehaviourLSMCSettings):
        raise TypeError("settings must be OptimalBehaviourLSMCSettings.")
    premium_value = np.asarray(premium, dtype=float)
    if premium_value.ndim != 0 or not np.isfinite(premium_value) \
            or float(premium_value) <= 0.0:
        raise ValueError("Continuation-regression premium must be positive and finite.")
    premium_float = float(premium_value)

    def normalised_keys(mapping: Mapping[int, object], name: str) -> set[int]:
        keys: set[int] = set()
        for key in mapping:
            if isinstance(key, (bool, np.bool_)) or int(key) != key or int(key) < 0:
                raise ValueError(f"{name} decision steps must be non-negative integers.")
            keys.add(int(key))
        return keys

    feature_steps = normalised_keys(features_by_step, "Feature")
    target_steps = normalised_keys(
        continuation_targets_aud_by_step, "Continuation-target"
    )
    if feature_steps != target_steps:
        raise ValueError(
            "Feature and continuation-target mappings must contain identical steps."
        )
    steps = tuple(sorted(feature_steps))

    features: dict[int, Array] = {}
    targets: dict[int, Array] = {}
    observation_counts: dict[int, int] = {}
    for step in steps:
        raw = np.asarray(features_by_step[step], dtype=float)
        target = np.asarray(
            continuation_targets_aud_by_step[step], dtype=float
        )
        if raw.ndim != 2 or raw.shape[1] != len(FEATURE_NAMES):
            raise ValueError(
                f"Step {step} features must have shape (n, {len(FEATURE_NAMES)})."
            )
        if target.shape != (raw.shape[0],):
            raise ValueError(
                f"Step {step} continuation target must have shape ({raw.shape[0]},)."
            )
        if not np.all(np.isfinite(raw)) or not np.all(np.isfinite(target)):
            raise ValueError(
                f"Step {step} features and continuation targets must be finite."
            )
        features[step] = raw
        targets[step] = target
        observation_counts[step] = int(raw.shape[0])

    path_ids: dict[int, NDArray[np.int64]] = {}
    if fold_ids_by_step is None:
        counts = set(observation_counts.values())
        if len(counts) > 1:
            raise ValueError(
                "Steps with different row counts require explicit complete-path "
                "fold IDs."
            )
        if counts:
            n_paths = counts.pop()
            base_ids = np.arange(n_paths, dtype=np.int64)
            np.random.default_rng(settings.fold_seed).shuffle(base_ids)
            path_ids = {step: base_ids.copy() for step in steps}
    else:
        fold_steps = normalised_keys(fold_ids_by_step, "Fold-ID")
        if fold_steps != feature_steps:
            raise ValueError(
                "Fold-ID and feature mappings must contain identical steps."
            )
        for step in steps:
            supplied = np.asarray(fold_ids_by_step[step])
            if supplied.shape != (observation_counts[step],):
                raise ValueError(
                    f"Step {step} fold IDs must have shape "
                    f"({observation_counts[step]},)."
                )
            if not np.issubdtype(supplied.dtype, np.integer):
                numeric = np.asarray(supplied, dtype=float)
                if not np.all(np.isfinite(numeric)) \
                        or not np.all(numeric == np.floor(numeric)):
                    raise ValueError("Complete-path fold IDs must be integers.")
            ids = np.asarray(supplied, dtype=np.int64)
            if np.any(ids < 0):
                raise ValueError("Complete-path fold IDs must be non-negative.")
            path_ids[step] = ids.copy()

    regressions: dict[int, _ContinuationRegression] = {}
    oof_by_step: dict[int, Array] = {}
    diagnostics: list[SurrenderContinuationRegressionDiagnostic] = []
    raw_feature_count = len(FEATURE_NAMES) + 1
    minimum_observations = _minimum_cross_fit_observations(
        settings, raw_feature_count
    )
    for step in steps:
        raw = features[step]
        target = targets[step]
        observations = raw.shape[0]
        mean_target = float(np.mean(target)) if observations else 0.0
        if observations < minimum_observations:
            diagnostics.append(SurrenderContinuationRegressionDiagnostic(
                decision_step=step,
                observations=observations,
                folds_used=0,
                feature_count=raw_feature_count,
                matrix_rank=0,
                condition_number=None,
                oof_rmse_aud=None,
                oof_r_squared=None,
                mean_continuation_target_aud=mean_target,
                regression_accepted_for_exercise=False,
                fallback_reason=(
                    f"too_few_observations:{observations}<{minimum_observations}"
                ),
            ))
            continue
        try:
            regression, oof, folds_used, fold_regressions = (
                _cross_fitted_regression(
                    raw,
                    target,
                    premium_float,
                    settings,
                    path_ids[step],
                )
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            diagnostics.append(SurrenderContinuationRegressionDiagnostic(
                decision_step=step,
                observations=observations,
                folds_used=0,
                feature_count=raw_feature_count,
                matrix_rank=0,
                condition_number=None,
                oof_rmse_aud=None,
                oof_r_squared=None,
                mean_continuation_target_aud=mean_target,
                regression_accepted_for_exercise=False,
                fallback_reason=f"cross_fit_failed:{exc}",
            ))
            continue

        full_rank = regression.matrix_rank == regression.coefficients.size
        full_condition = (
            np.isfinite(regression.condition_number)
            and regression.condition_number <= settings.maximum_condition_number
        )
        folds_stable = all(
            fold.matrix_rank == fold.coefficients.size
            and np.isfinite(fold.condition_number)
            and fold.condition_number <= settings.maximum_condition_number
            for fold in fold_regressions
        )
        accepted = bool(full_rank and full_condition and folds_stable)
        if not full_rank:
            fallback_reason = "rank_deficient"
        elif not full_condition:
            fallback_reason = "condition_number_exceeds_limit"
        elif not folds_stable:
            fallback_reason = "unstable_cross_fit_fold"
        else:
            fallback_reason = None
        residual = target - oof
        residual_ss = float(np.sum(residual ** 2))
        total_ss = float(np.sum((target - mean_target) ** 2))
        oof_r_squared = 1.0 - residual_ss / total_ss if total_ss > 0.0 else 1.0
        diagnostics.append(SurrenderContinuationRegressionDiagnostic(
            decision_step=step,
            observations=observations,
            folds_used=folds_used,
            feature_count=int(regression.coefficients.size),
            matrix_rank=regression.matrix_rank,
            condition_number=float(regression.condition_number),
            oof_rmse_aud=float(regression.oof_rmse_aud),
            oof_r_squared=float(oof_r_squared),
            mean_continuation_target_aud=mean_target,
            regression_accepted_for_exercise=accepted,
            fallback_reason=fallback_reason,
            selected_ridge=regression.selected_ridge,
            effective_rank=regression.effective_rank,
            basis_level=regression.basis_level,
            oof_policy_uplift_aud=None,
            relevant_exposure_fraction=1.0,
        ))
        if accepted:
            regressions[step] = regression
            oof_by_step[step] = oof

    policy = OptimalSurrenderPolicy(
        regressions=MappingProxyType(dict(sorted(regressions.items()))),
        settings=settings,
        provenance_fingerprint=assumption_fingerprint(
            "surrender_continuation_policy_v1",
            features,
            targets,
            path_ids,
            premium_float,
            settings,
        ),
    )
    return SurrenderContinuationPolicyFit(
        policy=policy,
        oof_continuation_by_step=oof_by_step,
        fold_ids_by_step=path_ids,
        diagnostics=tuple(diagnostics),
    )


def fit_optimal_surrender_policy(
    product: IndexLinkedLifetimeIncomeProduct,
    policy: PolicySpec,
    training_scenarios: ScenarioSet,
    mortality: MortalityTable,
    *,
    expenses: Optional[ExpenseAssumptions] = None,
    projection_config: ProjectionConfig = ProjectionConfig(record_paths=True),
    settings: OptimalBehaviourLSMCSettings = OptimalBehaviourLSMCSettings(),
) -> OptimalBehaviourLSMCFit:
    """Fit an annual, adapted LSMC Full-Withdrawal rule.

    Cross-fitted predictions drive the backward training recursion.  This
    compatibility API now shares the productive conditional-survival and
    time-zero-curve customer objective.
    """
    policy.validate_against(product)
    if policy.age_pension_plus:
        raise NotImplementedError("Generic optimal behaviour does not support APS.")
    if product.allows_growth_surrender or product.allows_growth_withdrawals:
        raise ValueError("The generic LSMC implementation requires Growth action gates.")
    config = replace(
        projection_config,
        record_paths=True,
        heston_cos=False,
        mortality_seed=0,
    )
    behaviour = no_voluntary_action_behaviour()
    training_mortality = mortality_free_policyholder_basis(mortality)
    context_recorder = _SurrenderContextRecorder()
    projection = project(
        product,
        policy,
        training_scenarios,
        behaviour,
        training_mortality,
        expenses=expenses,
        config=config,
        surrender_policy=context_recorder,
    )
    if projection.iv_paths is None or projection.income_paths is None \
            or projection.phase_paths is None:
        raise ValueError("LSMC training requires recorded projector state paths.")

    premium = float(policy.net_initial_investment)
    n_steps = len(projection.times) - 1
    # The contractual event order does not allow Full Withdrawal on the Income
    # Election timestamp itself.  On the annual LSMC grid, the first admissible
    # decision is therefore the following Policy Anniversary.
    first_decision = (
        policy.effective_income_start_year(product) + 1
    ) * STEPS_PER_YEAR
    decision_steps = list(range(first_decision, n_steps, STEPS_PER_YEAR))
    if not decision_steps:
        raise ValueError("Projection horizon contains no Income decision anniversary.")

    discounted_cashflow = _discounted_policyholder_cashflows(
        projection, training_scenarios
    )
    discount = _time_zero_curve_discount_factors(
        training_scenarios, n_steps + 1
    )
    no_action_path_value = np.sum(discounted_cashflow, axis=1)

    rng = np.random.default_rng(settings.fold_seed)
    base_fold_ids = np.arange(training_scenarios.n_paths, dtype=np.int64)
    rng.shuffle(base_fold_ids)
    regressions: dict[int, _ContinuationRegression] = {}
    cross_fitted_regressions: dict[
        int, tuple[_ContinuationRegression, ...]
    ] = {}
    cross_fitted_fold_ids: dict[int, NDArray[np.int64]] = {}
    diagnostics: list[LSMCRegressionDiagnostic] = []

    last_step = decision_steps[-1]
    future_value_0 = np.sum(discounted_cashflow[:, last_step + 1:], axis=1)
    for position in range(len(decision_steps) - 1, -1, -1):
        step = decision_steps[position]
        if step not in context_recorder.contexts:
            raise ValueError(
                f"Projector did not record surrender decision context at step {step}."
            )
        context = context_recorder.contexts[step]
        inforce = context.inforce_weight
        phase = context.phase
        scale_0 = discount[:, step] * inforce
        eligible = (
            (phase == Phase.INCOME.value)
            & (inforce > settings.minimum_inforce_weight)
            & (scale_0 > 1.0e-300)
        )
        eligible_index = np.flatnonzero(eligible)
        if eligible_index.size < _minimum_cross_fit_observations(
            settings, 1
        ):
            # At the hard terminal-age tail there is no material in-force
            # cohort left to fit.  Continuing to the terminal closeout is the
            # conservative admissible action.
            if position > 0:
                previous = decision_steps[position - 1]
                future_value_0 += np.sum(
                    discounted_cashflow[:, previous + 1:step + 1], axis=1)
            continue

        continuation_target = future_value_0[eligible] / scale_0[eligible]
        immediate_all = context.surrender_value
        immediate = immediate_all[eligible]
        advantage_target = immediate - continuation_target
        raw = build_surrender_regression_features(context, premium)[eligible]
        fold_ids = base_fold_ids[eligible_index]
        try:
            (
                regression,
                oof_continuation,
                folds_used,
                fold_regressions,
            ) = _cross_fitted_advantage_regression(
                raw,
                advantage_target,
                premium,
                settings,
                fold_ids,
                core_feature_indices=CORE_FEATURE_INDICES,
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            # A globally sufficient tail sample can still leave an
            # undersized training set in one fixed complete-path fold.  The
            # other LSMC fitters treat any failed cross-fit as a conservative
            # Continue decision.  Preserve the same semantics here and roll
            # the skipped interval into the preceding Bellman target.
            diagnostics.append(LSMCRegressionDiagnostic(
                policy_year=step // STEPS_PER_YEAR,
                decision_step=step,
                observations=int(eligible_index.size),
                folds_used=0,
                feature_count=len(FEATURE_NAMES) + 1,
                matrix_rank=0,
                condition_number=None,
                oof_rmse_aud=None,
                oof_r_squared=None,
                mean_immediate_value_aud=float(np.mean(
                    context.surrender_value[eligible]
                )),
                mean_continuation_target_aud=float(np.mean(
                    continuation_target
                )),
                training_exercise_rate=0.0,
                regression_accepted_for_exercise=False,
                fallback_reason=f"cross_fit_failed:{exc}",
            ))
            if position > 0:
                previous = decision_steps[position - 1]
                future_value_0 += np.sum(
                    discounted_cashflow[:, previous + 1:step + 1], axis=1)
            continue
        buffer = (
            settings.exercise_tolerance_aud
            + settings.exercise_buffer_rmse_multiplier
            * regression.oof_rmse_aud
        )
        exercise_eligible = (
            context.full_withdrawal_eligible[eligible]
            & (oof_continuation > buffer)
        )
        regression_stable = (
            regression.matrix_rank == regression.coefficients.size
            and regression.condition_number <= settings.maximum_condition_number
        )
        if regression.matrix_rank != regression.coefficients.size:
            fallback_reason = "rank_deficient"
        elif (
            not np.isfinite(regression.condition_number)
            or regression.condition_number > settings.maximum_condition_number
        ):
            fallback_reason = "condition_number_exceeds_limit"
        else:
            fallback_reason = None
        exercise_eligible &= regression_stable
        exercise = np.zeros(training_scenarios.n_paths, dtype=bool)
        exercise[eligible_index] = exercise_eligible
        future_value_0 = np.where(
            exercise,
            scale_0 * immediate_all,
            future_value_0,
        )
        residual = advantage_target - oof_continuation
        total_ss = float(np.sum(
            (advantage_target - np.mean(advantage_target)) ** 2))
        residual_ss = float(np.sum(residual ** 2))
        r_squared = 1.0 - residual_ss / total_ss if total_ss > 0.0 else 1.0
        regressions[step] = regression
        cross_fitted_regressions[step] = fold_regressions
        cross_fitted_fold_ids[step] = np.mod(
            base_fold_ids, folds_used
        ).astype(np.int64)
        diagnostics.append(LSMCRegressionDiagnostic(
            policy_year=step // STEPS_PER_YEAR,
            decision_step=step,
            observations=int(eligible_index.size),
            folds_used=folds_used,
            feature_count=int(regression.coefficients.size),
            matrix_rank=regression.matrix_rank,
            condition_number=regression.condition_number,
            oof_rmse_aud=regression.oof_rmse_aud,
            oof_r_squared=float(r_squared),
            mean_immediate_value_aud=float(np.mean(immediate)),
            mean_continuation_target_aud=float(np.mean(continuation_target)),
            training_exercise_rate=float(np.mean(exercise_eligible)),
            regression_accepted_for_exercise=regression_stable,
            fallback_reason=fallback_reason,
            selected_ridge=regression.selected_ridge,
            effective_rank=regression.effective_rank,
            basis_level=regression.basis_level,
            oof_policy_uplift_aud=float(np.mean(
                np.where(exercise_eligible, advantage_target, 0.0)
            )),
            relevant_exposure_fraction=float(np.mean(inforce[eligible])),
        ))
        if position > 0:
            previous = decision_steps[position - 1]
            future_value_0 += np.sum(
                discounted_cashflow[:, previous + 1:step + 1], axis=1)

    first_step = decision_steps[0]
    before_and_at_first = np.sum(
        discounted_cashflow[:, :first_step + 1], axis=1)
    policy_path_value = before_and_at_first + future_value_0
    candidate_value = float(np.mean(policy_path_value))
    no_action_value = float(np.mean(no_action_path_value))
    fallback_used = bool(
        settings.fallback_to_no_action_if_training_underperforms
        and candidate_value < no_action_value
    )
    selected_regressions = {} if fallback_used else dict(sorted(regressions.items()))
    selected_cross_fitted_regressions = (
        {} if fallback_used else dict(sorted(cross_fitted_regressions.items()))
    )
    selected_cross_fitted_fold_ids = (
        {} if fallback_used else dict(sorted(cross_fitted_fold_ids.items()))
    )
    selected_value = no_action_value if fallback_used else candidate_value
    legacy_policy_fingerprint = assumption_fingerprint(
        "fixed_election_surrender_lsmc_v1",
        training_scenarios.content_fingerprint,
        product,
        policy,
        mortality,
        expenses,
        projection_config,
        settings,
    )
    optimal_policy = OptimalSurrenderPolicy(
        regressions=selected_regressions,
        settings=settings,
        provenance_fingerprint=legacy_policy_fingerprint,
        regressions_are_advantages=True,
    )
    cross_fitted_training_policy = CrossFittedOptimalSurrenderPolicy(
        regressions_by_step=selected_cross_fitted_regressions,
        fold_ids_by_step=selected_cross_fitted_fold_ids,
        settings=settings,
        regressions_are_advantages=True,
    )
    return OptimalBehaviourLSMCFit(
        policy=optimal_policy,
        cross_fitted_training_policy=cross_fitted_training_policy,
        diagnostics=tuple(sorted(diagnostics, key=lambda item: item.decision_step)),
        training_scenario_fingerprint=training_scenarios.content_fingerprint,
        training_path_count=training_scenarios.n_paths,
        training_policyholder_value_aud=selected_value,
        training_no_action_policyholder_value_aud=no_action_value,
        training_candidate_policyholder_value_aud=candidate_value,
        training_fallback_used=fallback_used,
    )


ELECTION_FEATURE_NAMES = (
    "log1p_account_value_ratio",
    "prospective_annual_income_ratio",
    "guarantee_log_moneyness",
    "short_rate",
    "five_year_rate_slope",
    "sqrt_heston_variance",
    "duration_years_scaled",
    "attained_age_scaled",
    "time_to_forced_election_scaled",
    "mva_remaining_years_scaled",
    "mva_factor",
    "primary_alive",
    "spouse_alive",
    "previous_cap",
    "previous_reference_return",
    "performance_gap",
    "account_value_sq",
    "prospective_annual_income_sq",
    "guarantee_moneyness_sq",
    "account_value_x_guarantee_moneyness",
    "income_x_guarantee_moneyness",
    "guarantee_moneyness_x_short_rate",
)

ELECTION_CORE_FEATURE_INDICES = np.asarray(
    (0, 1, 2, 3, 4, 6, 7, 8), dtype=np.int64
)
START_VALUE_FEATURE_NAMES = (
    *ELECTION_FEATURE_NAMES,
    "duration_years_sq",
    "duration_x_log_account_value",
    "duration_x_guarantee_moneyness",
)
START_VALUE_CORE_FEATURE_INDICES = np.asarray(
    (*ELECTION_CORE_FEATURE_INDICES, len(ELECTION_FEATURE_NAMES)),
    dtype=np.int64,
)

INCOME_ACTION_FEATURE_NAMES = (
    *FEATURE_NAMES,
    "time_to_forced_election_scaled",
    "mva_remaining_years_scaled",
    "mva_factor",
)
PARTIAL_ACTION_FEATURE_NAMES = (
    *INCOME_ACTION_FEATURE_NAMES,
    "partial_fraction",
    "partial_fraction_sq",
    "partial_fraction_x_moneyness",
    "partial_fraction_x_mva_factor",
    "partial_fraction_x_income",
)
INCOME_ACTION_CORE_FEATURE_INDICES = np.asarray(
    (*CORE_FEATURE_INDICES,
     len(FEATURE_NAMES)),
    dtype=np.int64,
)
PARTIAL_ACTION_CORE_FEATURE_INDICES = np.asarray(
    (*INCOME_ACTION_CORE_FEATURE_INDICES,
     len(INCOME_ACTION_FEATURE_NAMES)),
    dtype=np.int64,
)


def build_income_action_regression_features(
    context: IncomeActionDecisionContext,
    premium: float,
) -> Array:
    """Build observable monthly Income-state features for the action policy."""
    if not isinstance(context, IncomeActionDecisionContext):
        raise TypeError("Income-action features require IncomeActionDecisionContext.")
    base = build_surrender_regression_features_from_arrays(
        account_value=context.account_value,
        surrender_value=context.surrender_value,
        locked_annual_income=context.locked_annual_income,
        guarantee_pv=context.guarantee_pv,
        guarantee_log_moneyness=context.guarantee_log_moneyness,
        short_rate=context.short_rate,
        zero_rate_5y=context.zero_rate_5y,
        heston_variance=context.heston_variance,
        duration_years=context.duration_years,
        announced_cap=context.announced_cap,
        previous_reference_return=context.previous_reference_return,
        previous_credited_return=context.previous_credited_return,
        performance_gap=context.performance_gap,
        premium=premium,
        mva_factor=context.mva_factor,
        attained_age=context.attained_age,
        primary_alive=context.primary_alive,
        spouse_alive=context.spouse_alive,
    )
    time_to_forced = np.asarray(
        context.time_to_forced_election, dtype=float
    ) / 100.0
    mva_remaining = np.full(
        context.n_paths, float(context.mva_remaining_years) / 100.0
    )
    mva_factor = np.asarray(context.mva_factor, dtype=float)
    if not np.all(np.isfinite(mva_factor)) or np.any(mva_factor < 0.0):
        raise ValueError("Income-action MVA factors are invalid.")
    out = np.column_stack((
        base,
        time_to_forced,
        mva_remaining,
        mva_factor,
    ))
    if out.shape != (context.n_paths, len(INCOME_ACTION_FEATURE_NAMES)):
        raise RuntimeError("Income-action feature matrix is inconsistent.")
    return np.asarray(out, dtype=float)


def build_partial_action_regression_features(
    base_features: Array,
    partial_fraction_of_max: object,
) -> Array:
    """Append an action amount to monthly state features without future data."""
    base = np.asarray(base_features, dtype=float)
    if base.ndim != 2 or base.shape[1] != len(INCOME_ACTION_FEATURE_NAMES):
        raise ValueError(
            "Base Income-action features have an inconsistent shape."
        )
    fraction = np.asarray(partial_fraction_of_max, dtype=float)
    if fraction.ndim == 0:
        fraction = np.full(base.shape[0], float(fraction))
    if fraction.shape != (base.shape[0],) or not np.all(np.isfinite(fraction)) \
            or np.any((fraction <= 0.0) | (fraction > 1.0)):
        raise ValueError("Partial fractions must be finite and lie in (0, 1].")
    moneyness = base[:, FEATURE_NAMES.index("guarantee_log_moneyness")]
    income = base[:, FEATURE_NAMES.index("annual_income_ratio")]
    mva = base[:, INCOME_ACTION_FEATURE_NAMES.index("mva_factor")]
    out = np.column_stack((
        base,
        fraction,
        fraction * fraction,
        fraction * moneyness,
        fraction * mva,
        fraction * income,
    ))
    if out.shape[1] != len(PARTIAL_ACTION_FEATURE_NAMES):
        raise RuntimeError("Partial-action feature matrix is inconsistent.")
    return np.asarray(out, dtype=float)


@dataclass(frozen=True)
class IncomeActionRegressionSet:
    """Frozen monthly action-advantage models for one projector step."""

    full_withdrawal_advantage: Optional[_ContinuationRegression] = None
    partial_withdrawal_advantage: Optional[_ContinuationRegression] = None


def _partial_candidate_fractions(context: IncomeActionDecisionContext) -> Array:
    maximum = np.asarray(context.max_partial_gross_amount, dtype=float)
    candidates = np.column_stack((
        np.divide(100.0, maximum, out=np.zeros_like(maximum), where=maximum > 0.0),
        np.full(context.n_paths, 0.25),
        np.full(context.n_paths, 0.50),
        np.full(context.n_paths, 0.75),
        np.ones(context.n_paths),
    ))
    candidates = np.clip(candidates, 0.0, 1.0)
    gross = candidates * maximum[:, None]
    valid = gross >= 100.0 - 1.0e-10
    # Deduplicate by the contractual gross amount, not by a nominal fraction.
    # The grid is ordered from AUD 100 through increasing proportional amounts.
    for column in range(1, candidates.shape[1]):
        duplicate = np.any(
            valid[:, :column]
            & np.isclose(
                gross[:, :column], gross[:, [column]], atol=1.0e-8, rtol=0.0
            ),
            axis=1,
        )
        candidates[duplicate, column] = 0.0
    return candidates


def _predict_best_partial_action(
    regression: _ContinuationRegression,
    context: IncomeActionDecisionContext,
    base_features: Array,
    settings: OptimalBehaviourLSMCSettings,
) -> tuple[Array, Array]:
    """Maximise the fitted quadratic Partial advantage analytically.

    The documented Partial basis is affine in state and quadratic in the
    withdrawal fraction.  Therefore a five-point prediction loop plus two
    midpoint refinements is unnecessary: the exact fitted optimum is one of
    the contractual lower bound, the upper bound, or the concave vertex.
    """
    if not _regression_is_stable(regression, settings):
        raise RuntimeError("Partial-withdrawal advantage regression is unstable.")
    if regression.clip_non_negative:
        raise RuntimeError("Partial advantage regressions must remain signed.")
    if regression.raw_feature_count != len(PARTIAL_ACTION_FEATURE_NAMES):
        raise ValueError("Partial regression has an inconsistent feature count.")
    base = np.asarray(base_features, dtype=float)
    if base.shape != (context.n_paths, len(INCOME_ACTION_FEATURE_NAMES)):
        raise ValueError("Partial base features have an inconsistent shape.")

    maximum = np.asarray(context.max_partial_gross_amount, dtype=float)
    eligible = (
        np.asarray(context.partial_withdrawal_eligible, dtype=bool)
        & (maximum >= 100.0 - 1.0e-10)
    )
    minimum_fraction = np.divide(
        100.0,
        maximum,
        out=np.ones_like(maximum),
        where=maximum > 0.0,
    )
    minimum_fraction = np.clip(minimum_fraction, 0.0, 1.0)

    raw_intercept, weights = regression.raw_affine_form()
    base_count = len(INCOME_ACTION_FEATURE_NAMES)
    fraction_index = base_count
    square_index = base_count + 1
    moneyness_index = FEATURE_NAMES.index("guarantee_log_moneyness")
    mva_index = INCOME_ACTION_FEATURE_NAMES.index("mva_factor")
    income_index = FEATURE_NAMES.index("annual_income_ratio")
    linear = (
        weights[fraction_index]
        + weights[base_count + 2] * base[:, moneyness_index]
        + weights[base_count + 3] * base[:, mva_index]
        + weights[base_count + 4] * base[:, income_index]
    )
    quadratic = float(weights[square_index])
    buffer = (
        settings.exercise_tolerance_aud
        + settings.exercise_buffer_rmse_multiplier * regression.oof_rmse_aud
    )
    state_constant = (
        raw_intercept
        + base @ weights[:base_count]
        - buffer
    )

    def score(fraction: Array) -> Array:
        return state_constant + linear * fraction + quadratic * fraction * fraction

    best_fraction = minimum_fraction.copy()
    best_score = np.where(eligible, score(best_fraction), -np.inf)

    def consider(fraction: Array, valid: NDArray[np.bool_]) -> None:
        nonlocal best_fraction, best_score
        candidate_score = score(fraction)
        improve = valid & (
            (candidate_score > best_score + settings.exercise_tolerance_aud)
            | (
                np.abs(candidate_score - best_score)
                <= settings.exercise_tolerance_aud
            ) & (fraction < best_fraction)
        )
        best_score = np.where(improve, candidate_score, best_score)
        best_fraction = np.where(improve, fraction, best_fraction)

    upper = np.ones(context.n_paths)
    consider(upper, eligible)
    if quadratic < -1.0e-14:
        vertex = np.clip(
            -linear / (2.0 * quadratic), minimum_fraction, 1.0
        )
        consider(vertex, eligible)

    best_fraction = np.where(eligible, best_fraction, 0.0)
    return best_score, best_fraction


@dataclass(frozen=True)
class OptimalBehaviourRegressionDiagnostic:
    """Action-typed numerical audit for one combined Bellman regression."""

    action_type: str
    phase: str
    policy_year: int
    decision_step: int
    observations: int
    folds_used: int
    feature_count: int
    matrix_rank: int
    condition_number: Optional[float]
    oof_rmse_aud: Optional[float]
    oof_r_squared: Optional[float]
    mean_wait_or_continue_value_aud: float
    mean_action_value_aud: float
    training_action_rate: float
    regression_accepted_for_action: bool
    fallback_reason: Optional[str]
    wait_regression_rank: Optional[int] = None
    wait_regression_condition_number: Optional[float] = None
    wait_regression_oof_rmse_aud: Optional[float] = None
    action_regression_rank: Optional[int] = None
    action_regression_condition_number: Optional[float] = None
    action_regression_oof_rmse_aud: Optional[float] = None
    selected_ridge: Optional[float] = None
    effective_rank: int = 0
    basis_level: str = "full"
    oof_policy_uplift_aud: Optional[float] = None
    relevant_exposure_fraction: float = 0.0

    def as_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


def build_income_election_regression_features(
    context: IncomeElectionDecisionContext,
    premium: float,
    issue_age: float,
    automatic_income_start_age: float = 100.0,
) -> Array:
    """Build adapted Growth-state features without accepting future inputs."""
    if not isinstance(context, IncomeElectionDecisionContext):
        raise TypeError(
            "Income-Election LSMC features require IncomeElectionDecisionContext."
        )
    premium_value = float(premium)
    issue_age_value = float(issue_age)
    automatic_age_value = float(automatic_income_start_age)
    if not np.isfinite(premium_value) or premium_value <= 0.0:
        raise ValueError("Income-Election feature premium must be positive and finite.")
    if not np.isfinite(issue_age_value) or issue_age_value < 0.0:
        raise ValueError("Income-Election issue age must be finite and non-negative.")
    if not np.isfinite(automatic_age_value) \
            or automatic_age_value < issue_age_value:
        raise ValueError("Automatic Income start age must not precede issue age.")

    x = np.maximum(context.account_value, 0.0) / premium_value
    log_x = np.log1p(x)
    y = np.maximum(
        context.prospective_locked_annual_income, 0.0
    ) / premium_value
    m = np.asarray(context.guarantee_log_moneyness, dtype=float)
    r = np.asarray(context.short_rate, dtype=float)
    z5 = np.asarray(context.zero_rate_5y, dtype=float)
    sqrt_v = np.sqrt(np.maximum(context.heston_variance, 0.0))
    duration = np.full(context.n_paths, context.duration_years / 100.0)
    attained_age = np.full(
        context.n_paths, (issue_age_value + context.duration_years) / 100.0
    )
    time_to_forced = np.full(
        context.n_paths,
        max(automatic_age_value - issue_age_value - context.duration_years, 0.0)
        / 100.0,
    )
    # Context values are the canonical projector state.  The locally derived
    # age/time arrays above remain a consistency fallback for older contexts.
    attained_age = np.asarray(
        getattr(context, "attained_age", attained_age * 100.0), dtype=float
    ) / 100.0
    time_to_forced = np.asarray(
        getattr(
            context,
            "time_to_forced_election",
            time_to_forced * 100.0,
        ),
        dtype=float,
    ) / 100.0
    mva_remaining = np.full(
        context.n_paths,
        float(getattr(context, "mva_remaining_years", 0.0)) / 100.0,
    )
    mva_factor = np.asarray(
        getattr(context, "mva_factor", np.ones(context.n_paths)), dtype=float
    )
    primary_alive = np.asarray(
        getattr(context, "primary_alive", np.ones(context.n_paths)), dtype=float
    )
    spouse_alive = np.asarray(
        getattr(context, "spouse_alive", np.zeros(context.n_paths)), dtype=float
    )
    previous_cap_input = np.asarray(context.previous_cap, dtype=float)
    if np.any(np.isnan(previous_cap_input)) or np.any(previous_cap_input < 0.0):
        raise ValueError("Previous cap must be non-negative and not NaN.")
    # Positive infinity is the explicit uncapped state.  The one-unit sentinel
    # remains safely above the supported design-control grid and keeps the
    # regression matrix finite.
    previous_cap = np.where(np.isposinf(previous_cap_input), 1.0,
                            previous_cap_input)
    previous_reference = np.asarray(
        context.previous_reference_return, dtype=float
    )
    gap = np.maximum(context.performance_gap, 0.0)

    out = np.column_stack((
        log_x,
        y,
        m,
        r,
        z5 - r,
        sqrt_v,
        duration,
        attained_age,
        time_to_forced,
        mva_remaining,
        mva_factor,
        primary_alive,
        spouse_alive,
        previous_cap,
        previous_reference,
        gap,
        log_x * log_x,
        y * y,
        m * m,
        log_x * m,
        y * m,
        m * r,
    ))
    if out.shape != (context.n_paths, len(ELECTION_FEATURE_NAMES)):
        raise RuntimeError("Income-Election feature matrix is inconsistent.")
    if not np.all(np.isfinite(out)):
        raise ValueError("Non-finite Income-Election LSMC feature encountered.")
    return np.asarray(out, dtype=float)


def _build_income_start_value_features(election_features: Array) -> Array:
    """Add a compact nonlinear time basis to the pooled START value model."""
    base = np.asarray(election_features, dtype=float)
    if base.ndim != 2 or base.shape[1] != len(ELECTION_FEATURE_NAMES):
        raise ValueError("START-value base features have an inconsistent shape.")
    duration = base[:, ELECTION_FEATURE_NAMES.index("duration_years_scaled")]
    log_account = base[:, ELECTION_FEATURE_NAMES.index(
        "log1p_account_value_ratio"
    )]
    moneyness = base[:, ELECTION_FEATURE_NAMES.index(
        "guarantee_log_moneyness"
    )]
    out = np.column_stack((
        base,
        duration * duration,
        duration * log_account,
        duration * moneyness,
    ))
    if out.shape[1] != len(START_VALUE_FEATURE_NAMES):
        raise RuntimeError("START-value feature matrix is inconsistent.")
    return np.asarray(out, dtype=float)


def _regression_is_stable(
    regression: _ContinuationRegression,
    settings: OptimalBehaviourLSMCSettings,
) -> bool:
    return bool(
        regression.matrix_rank == regression.coefficients.size
        and np.isfinite(regression.condition_number)
        and regression.condition_number <= settings.maximum_condition_number
    )


@dataclass(frozen=True)
class _ElectionRegressionPair:
    """Compatibility name for the v2 paired START-minus-WAIT model."""

    advantage: _ContinuationRegression

    @property
    def combined_oof_rmse_aud(self) -> float:
        return float(self.advantage.oof_rmse_aud)

    def stable(self, settings: OptimalBehaviourLSMCSettings) -> bool:
        return _regression_is_stable(self.advantage, settings)

    def predict(
        self,
        context: IncomeElectionDecisionContext,
        premium: float,
        issue_age: float,
        automatic_income_start_age: float = 100.0,
    ) -> Array:
        raw = build_income_election_regression_features(
            context, premium, issue_age, automatic_income_start_age
        )
        return self.advantage.predict_features(raw)


@dataclass
class OptimalBehaviourPolicy:
    """Frozen annual phase-aware Policyholder rule produced by the Swing fit."""

    election_regressions: Mapping[int, _ElectionRegressionPair]
    surrender_policy: OptimalSurrenderPolicy
    premium: float
    issue_age: float
    settings: OptimalBehaviourLSMCSettings
    automatic_income_start_age: float = 100.0
    fixed_election_step: Optional[int] = None
    income_action_regressions: Mapping[
        int, IncomeActionRegressionSet
    ] = field(default_factory=dict)
    valid: bool = True
    invalid_reasons: tuple[str, ...] = ()
    monthly_income_actions_required: bool = False
    provenance_fingerprint: Optional[str] = None
    evaluation_statistics: dict[
        tuple[str, int], dict[str, float | int]
    ] = field(default_factory=dict)
    anniversary_only: bool = field(default=True, init=False, repr=False)

    def start_income_mask(
        self,
        *,
        context: IncomeElectionDecisionContext,
    ) -> NDArray[np.bool_]:
        """Choose voluntary START; contractual forced START remains external."""
        if not isinstance(context, IncomeElectionDecisionContext):
            raise TypeError(
                "Optimal Income Election requires IncomeElectionDecisionContext."
            )
        if not self.valid:
            raise RuntimeError(
                "Invalid optimal-behaviour policy cannot be evaluated: "
                + ",".join(self.invalid_reasons)
            )
        step = int(context.step)
        voluntary_eligible = (
            context.voluntary_election_eligible
            & (context.phase == Phase.GROWTH.value)
            & (context.inforce_weight > self.settings.minimum_inforce_weight)
        )
        forced = np.asarray(context.forced_election, dtype=bool)
        voluntary_eligible &= ~forced
        action = np.zeros(context.n_paths, dtype=bool)
        regression = self.election_regressions.get(step)
        if self.fixed_election_step is not None:
            action = voluntary_eligible & (
                step >= int(self.fixed_election_step)
            )
        elif regression is not None and regression.stable(self.settings) \
                and np.any(voluntary_eligible):
            advantage = regression.predict(
                context,
                self.premium,
                self.issue_age,
                self.automatic_income_start_age,
            )
            buffer = (
                self.settings.exercise_tolerance_aud
                + self.settings.exercise_buffer_rmse_multiplier
                * regression.combined_oof_rmse_aud
            )
            action = voluntary_eligible & (
                advantage > buffer
            )
        elif regression is None and np.any(voluntary_eligible):
            exposure = float(np.mean(np.where(
                voluntary_eligible, context.inforce_weight, 0.0
            )))
            if exposure > self.settings.immaterial_exposure_fraction:
                raise RuntimeError(
                    "Material Income-Election advantage regression is missing "
                    f"at step {step} (exposure={exposure:.12g})."
                )
        elif regression is not None and not regression.stable(self.settings):
            raise RuntimeError(
                f"Income-Election advantage regression at step {step} is unstable."
            )
        stats = self.evaluation_statistics.setdefault(
            ("income_election", step),
            {
                "eligible_path_count": 0,
                "action_path_count": 0,
                "forced_path_count": 0,
            },
        )
        stats["eligible_path_count"] += int(
            np.count_nonzero(voluntary_eligible)
        )
        stats["action_path_count"] += int(np.count_nonzero(action))
        stats["forced_path_count"] += int(np.count_nonzero(forced))
        return action

    def choose_income_action(
        self,
        *,
        context: IncomeActionDecisionContext,
    ) -> IncomeActionDecision:
        """Compatibility hook for the deprecated monthly action API.

        Productive combined policies set ``monthly_income_actions_required``
        to false and are deployed through :meth:`surrender_mask` only.  In
        that mode this method deterministically returns CONTINUE and can never
        create a Partial Withdrawal or an under-year Full Withdrawal.
        """
        if not isinstance(context, IncomeActionDecisionContext):
            raise TypeError("Optimal Income action requires IncomeActionDecisionContext.")
        if not self.valid:
            raise RuntimeError(
                "Invalid optimal-behaviour policy cannot be evaluated: "
                + ",".join(self.invalid_reasons)
            )
        step = int(context.step)
        n_paths = context.n_paths
        in_income = (
            (context.phase == Phase.INCOME.value)
            & (context.inforce_weight > self.settings.minimum_inforce_weight)
        )
        models = self.income_action_regressions.get(step)
        if models is None and self.monthly_income_actions_required:
            action_eligible = (
                np.asarray(context.full_withdrawal_eligible, dtype=bool)
                | (
                    np.asarray(context.partial_withdrawal_eligible, dtype=bool)
                    & bool(self.settings.allow_partial_withdrawal)
                )
            )
            exposure = float(np.mean(np.where(
                in_income & action_eligible, context.inforce_weight, 0.0
            )))
            if exposure > self.settings.immaterial_exposure_fraction:
                raise RuntimeError(
                    "Material monthly Income action regression is missing at "
                    f"step {step} (exposure={exposure:.12g})."
                )
            return IncomeActionDecision(
                action_type=np.full(
                    n_paths, IncomeActionType.CONTINUE.value, dtype="<U32"
                ),
                partial_fraction_of_max=np.zeros(n_paths),
            )

        if models is not None and self.monthly_income_actions_required:
            missing_full_exposure = float(np.mean(np.where(
                in_income
                & np.asarray(context.full_withdrawal_eligible, dtype=bool),
                context.inforce_weight,
                0.0,
            )))
            missing_partial_exposure = float(np.mean(np.where(
                in_income
                & np.asarray(context.partial_withdrawal_eligible, dtype=bool),
                context.inforce_weight,
                0.0,
            ))) if self.settings.allow_partial_withdrawal else 0.0
            if models.full_withdrawal_advantage is None \
                    and missing_full_exposure \
                    > self.settings.immaterial_exposure_fraction:
                raise RuntimeError(
                    "Material Full-Withdrawal advantage regression is missing "
                    f"at step {step} (exposure={missing_full_exposure:.12g})."
                )
            if models.partial_withdrawal_advantage is None \
                    and missing_partial_exposure \
                    > self.settings.immaterial_exposure_fraction:
                raise RuntimeError(
                    "Material Partial-Withdrawal advantage regression is missing "
                    f"at step {step} (exposure={missing_partial_exposure:.12g})."
                )

        base_features = build_income_action_regression_features(
            context, self.premium
        )
        partial_score = np.full(n_paths, -np.inf)
        partial_fraction = np.zeros(n_paths)
        if self.settings.allow_partial_withdrawal \
                and models is not None \
                and models.partial_withdrawal_advantage is not None:
            partial_score, partial_fraction = _predict_best_partial_action(
                models.partial_withdrawal_advantage,
                context,
                base_features,
                self.settings,
            )
            partial_score = np.where(in_income, partial_score, -np.inf)

        full_regression = (
            None if models is None else models.full_withdrawal_advantage
        )
        full_score = np.full(n_paths, -np.inf)
        if full_regression is not None:
            if not _regression_is_stable(full_regression, self.settings):
                raise RuntimeError(
                    f"Full-Withdrawal regression at step {step} is unstable."
                )
            raw = (
                base_features
                if full_regression.raw_feature_count == len(INCOME_ACTION_FEATURE_NAMES)
                else base_features[:, :len(FEATURE_NAMES)]
            )
            prediction = full_regression.predict_features(raw)
            advantage = prediction
            buffer = (
                self.settings.exercise_tolerance_aud
                + self.settings.exercise_buffer_rmse_multiplier
                * full_regression.oof_rmse_aud
            )
            full_score = np.where(
                in_income & context.full_withdrawal_eligible,
                advantage - buffer,
                -np.inf,
            )

        action_type = np.full(
            n_paths, IncomeActionType.CONTINUE.value, dtype="<U32"
        )
        fraction = np.zeros(n_paths)
        take_partial = partial_score > 0.0
        action_type[take_partial] = IncomeActionType.PARTIAL_WITHDRAWAL.value
        fraction[take_partial] = partial_fraction[take_partial]
        # FULL has the lowest tie priority, hence strict improvement over both
        # Continue and the best Partial candidate is required.
        take_full = (
            (full_score > 0.0)
            & (full_score > partial_score + self.settings.exercise_tolerance_aud)
        )
        action_type[take_full] = IncomeActionType.FULL_WITHDRAWAL.value
        fraction[take_full] = 0.0

        stats = self.evaluation_statistics.setdefault(
            ("income_action", step),
            {
                "eligible_path_count": 0,
                "action_path_count": 0,
                "forced_path_count": 0,
                "continue_path_count": 0,
                "partial_path_count": 0,
                "full_path_count": 0,
                "partial_gross_amount_sum_aud": 0.0,
                "partial_gross_below_100_path_count": 0,
                "partial_gross_100_499_path_count": 0,
                "partial_gross_500_1999_path_count": 0,
                "partial_gross_2000_9999_path_count": 0,
                "partial_gross_ge_10000_path_count": 0,
            },
        )
        selected_partial = take_partial & ~take_full
        selected_continue = in_income & ~(selected_partial | take_full)
        gross = fraction * np.asarray(
            context.max_partial_gross_amount, dtype=float
        )
        stats["eligible_path_count"] += int(np.count_nonzero(in_income))
        stats["continue_path_count"] += int(np.count_nonzero(selected_continue))
        stats["partial_path_count"] += int(np.count_nonzero(selected_partial))
        stats["full_path_count"] += int(np.count_nonzero(take_full))
        stats["action_path_count"] += int(np.count_nonzero(take_partial | take_full))
        stats["partial_gross_amount_sum_aud"] += float(np.sum(
            np.where(selected_partial, gross, 0.0)
        ))
        for key, band in (
            ("partial_gross_below_100_path_count", gross < 100.0),
            ("partial_gross_100_499_path_count", (gross >= 100.0) & (gross < 500.0)),
            ("partial_gross_500_1999_path_count", (gross >= 500.0) & (gross < 2_000.0)),
            ("partial_gross_2000_9999_path_count", (gross >= 2_000.0) & (gross < 10_000.0)),
            ("partial_gross_ge_10000_path_count", gross >= 10_000.0),
        ):
            stats[key] += int(np.count_nonzero(selected_partial & band))
        return IncomeActionDecision(
            action_type=action_type,
            partial_fraction_of_max=fraction,
        )

    def surrender_mask(
        self,
        *,
        context: SurrenderDecisionContext,
    ) -> NDArray[np.bool_]:
        if not isinstance(context, SurrenderDecisionContext):
            raise TypeError("Optimal surrender requires SurrenderDecisionContext.")
        if not self.valid:
            raise RuntimeError(
                "Invalid optimal-behaviour policy cannot be evaluated: "
                + ",".join(self.invalid_reasons)
            )
        action = self.surrender_policy.surrender_mask(context=context)
        eligible = (
            context.full_withdrawal_eligible
            & (context.phase == Phase.INCOME.value)
            & (context.inforce_weight > self.settings.minimum_inforce_weight)
        )
        stats = self.evaluation_statistics.setdefault(
            ("full_withdrawal", int(context.step)),
            {
                "eligible_path_count": 0,
                "action_path_count": 0,
                "forced_path_count": 0,
            },
        )
        stats["eligible_path_count"] += int(np.count_nonzero(eligible))
        stats["action_path_count"] += int(np.count_nonzero(action))
        return action


@dataclass
class CrossFittedOptimalBehaviourPolicy:
    """Training-only annual policy; every complete path stays out of fold."""

    election_regressions_by_step: Mapping[
        int, tuple[_ElectionRegressionPair, ...]
    ]
    election_fold_ids_by_step: Mapping[int, NDArray[np.int64]]
    surrender_policy: CrossFittedOptimalSurrenderPolicy
    premium: float
    issue_age: float
    settings: OptimalBehaviourLSMCSettings
    automatic_income_start_age: float = 100.0
    fixed_election_step: Optional[int] = None
    income_action_regressions_by_step: Mapping[
        int, _CrossFittedIncomeActionRegressionSet
    ] = field(default_factory=dict)
    valid: bool = True
    invalid_reasons: tuple[str, ...] = ()
    monthly_income_actions_required: bool = False
    anniversary_only: bool = field(default=True, init=False, repr=False)

    def start_income_mask(
        self,
        *,
        context: IncomeElectionDecisionContext,
    ) -> NDArray[np.bool_]:
        if not isinstance(context, IncomeElectionDecisionContext):
            raise TypeError(
                "Cross-fitted Election requires IncomeElectionDecisionContext."
            )
        if not self.valid:
            raise RuntimeError(
                "Invalid cross-fitted optimal policy cannot be evaluated: "
                + ",".join(self.invalid_reasons)
            )
        step = int(context.step)
        if self.fixed_election_step is not None:
            eligible = (
                context.voluntary_election_eligible
                & ~np.asarray(context.forced_election, dtype=bool)
                & (context.phase == Phase.GROWTH.value)
                & (context.inforce_weight > self.settings.minimum_inforce_weight)
            )
            return eligible & (step >= int(self.fixed_election_step))
        pairs = self.election_regressions_by_step.get(step)
        if pairs is None:
            eligible = (
                context.voluntary_election_eligible
                & ~np.asarray(context.forced_election, dtype=bool)
                & (context.phase == Phase.GROWTH.value)
                & (context.inforce_weight > self.settings.minimum_inforce_weight)
            )
            exposure = float(np.mean(np.where(
                eligible, context.inforce_weight, 0.0
            )))
            if exposure > self.settings.immaterial_exposure_fraction:
                raise RuntimeError(
                    "Material cross-fitted Election regression is missing at "
                    f"step {step} (exposure={exposure:.12g})."
                )
            return np.zeros(context.n_paths, dtype=bool)
        fold_ids = np.asarray(
            self.election_fold_ids_by_step[step], dtype=np.int64
        )
        if fold_ids.shape != (context.n_paths,):
            raise ValueError(
                "Cross-fitted Election policy requires its original path sample."
            )
        raw = build_income_election_regression_features(
            context,
            self.premium,
            self.issue_age,
            self.automatic_income_start_age,
        )
        advantage = np.zeros(context.n_paths)
        stable = np.zeros(context.n_paths, dtype=bool)
        buffer = np.full(
            context.n_paths, self.settings.exercise_tolerance_aud
        )
        for fold, pair in enumerate(pairs):
            selected = fold_ids == fold
            if not np.any(selected):
                continue
            fold_prediction = pair.advantage.predict_features(raw)
            advantage[selected] = fold_prediction[selected]
            stable[selected] = pair.stable(self.settings)
            buffer[selected] += (
                self.settings.exercise_buffer_rmse_multiplier
                * pair.combined_oof_rmse_aud
            )
        eligible = (
            context.voluntary_election_eligible
            & ~np.asarray(context.forced_election, dtype=bool)
            & (context.phase == Phase.GROWTH.value)
            & (context.inforce_weight > self.settings.minimum_inforce_weight)
        )
        return eligible & stable & (advantage > buffer)

    def surrender_mask(
        self,
        *,
        context: SurrenderDecisionContext,
    ) -> NDArray[np.bool_]:
        if not self.valid:
            raise RuntimeError(
                "Invalid cross-fitted optimal policy cannot be evaluated: "
                + ",".join(self.invalid_reasons)
            )
        return self.surrender_policy.surrender_mask(context=context)

    def choose_income_action(
        self,
        *,
        context: IncomeActionDecisionContext,
    ) -> IncomeActionDecision:
        """Training-sample hook for unified monthly Partial/Full actions."""
        if not isinstance(context, IncomeActionDecisionContext):
            raise TypeError("Cross-fitted Income action requires decision context.")
        if not self.valid:
            raise RuntimeError(
                "Invalid cross-fitted optimal policy cannot be evaluated: "
                + ",".join(self.invalid_reasons)
            )
        step = int(context.step)
        models = self.income_action_regressions_by_step.get(step)
        if models is not None:
            in_income = (
                (context.phase == Phase.INCOME.value)
                & (
                    context.inforce_weight
                    > self.settings.minimum_inforce_weight
                )
            )
            full_exposure = float(np.mean(np.where(
                in_income & context.full_withdrawal_eligible,
                context.inforce_weight,
                0.0,
            )))
            partial_exposure = float(np.mean(np.where(
                in_income & context.partial_withdrawal_eligible,
                context.inforce_weight,
                0.0,
            ))) if self.settings.allow_partial_withdrawal else 0.0
            if not models.full_withdrawal_advantage \
                    and full_exposure \
                    > self.settings.immaterial_exposure_fraction:
                raise RuntimeError(
                    "Material cross-fitted Full advantage is missing at "
                    f"step {step} (exposure={full_exposure:.12g})."
                )
            if not models.partial_withdrawal_advantage \
                    and partial_exposure \
                    > self.settings.immaterial_exposure_fraction:
                raise RuntimeError(
                    "Material cross-fitted Partial advantage is missing at "
                    f"step {step} (exposure={partial_exposure:.12g})."
                )
            helper = _CrossFittedIncomeActionPolicy(
                regressions_by_step={step: models},
                premium=self.premium,
                settings=self.settings,
            )
            return helper._cross_fitted_decision(context, models)
        if self.monthly_income_actions_required:
            in_income = (
                (context.phase == Phase.INCOME.value)
                & (context.inforce_weight > self.settings.minimum_inforce_weight)
            )
            action_eligible = (
                np.asarray(context.full_withdrawal_eligible, dtype=bool)
                | (
                    np.asarray(context.partial_withdrawal_eligible, dtype=bool)
                    & bool(self.settings.allow_partial_withdrawal)
                )
            )
            exposure = float(np.mean(np.where(
                in_income & action_eligible, context.inforce_weight, 0.0
            )))
            if exposure > self.settings.immaterial_exposure_fraction:
                raise RuntimeError(
                    "Material cross-fitted monthly action regression is missing "
                    f"at step {step} (exposure={exposure:.12g})."
                )
        return IncomeActionDecision(
            action_type=np.full(
                context.n_paths, IncomeActionType.CONTINUE.value, dtype="<U32"
            ),
            partial_fraction_of_max=np.zeros(context.n_paths),
        )


@dataclass
class _AssignedElectionContextRecorder:
    assigned_start_steps: NDArray[np.int64]
    election_contexts: dict[int, IncomeElectionDecisionContext] = field(
        default_factory=dict
    )
    surrender_contexts: dict[int, SurrenderDecisionContext] = field(
        default_factory=dict
    )
    anniversary_only: bool = field(default=True, init=False, repr=False)

    def start_income_mask(
        self,
        *,
        context: IncomeElectionDecisionContext,
    ) -> NDArray[np.bool_]:
        assigned = np.asarray(self.assigned_start_steps, dtype=np.int64)
        if assigned.shape != (context.n_paths,):
            raise ValueError("Assigned Election steps must match the path sample.")
        self.election_contexts[int(context.step)] = context
        return context.voluntary_election_eligible & (
            int(context.step) >= assigned
        )

    def surrender_mask(
        self,
        *,
        context: SurrenderDecisionContext,
    ) -> NDArray[np.bool_]:
        self.surrender_contexts[int(context.step)] = context
        return np.zeros(context.n_paths, dtype=bool)


@dataclass(frozen=True)
class _CrossFittedIncomeActionRegressionSet:
    full_withdrawal_advantage: tuple[Optional[_ContinuationRegression], ...] = ()
    full_fold_ids: Optional[NDArray[np.int64]] = None
    partial_withdrawal_advantage: tuple[Optional[_ContinuationRegression], ...] = ()
    partial_fold_ids: Optional[NDArray[np.int64]] = None


@dataclass
class _CrossFittedIncomeActionPolicy:
    """Training-only policy with optional one-step action override."""

    regressions_by_step: Mapping[int, _CrossFittedIncomeActionRegressionSet]
    premium: float
    settings: OptimalBehaviourLSMCSettings
    override_step: Optional[int] = None
    override_action: IncomeActionType = IncomeActionType.CONTINUE
    override_partial_fraction: Optional[Array] = None
    contexts: dict[int, IncomeActionDecisionContext] = field(default_factory=dict)
    decisions: dict[int, IncomeActionDecision] = field(default_factory=dict)

    def _cross_fitted_decision(
        self,
        context: IncomeActionDecisionContext,
        models: _CrossFittedIncomeActionRegressionSet,
    ) -> IncomeActionDecision:
        base = build_income_action_regression_features(context, self.premium)
        in_income = (
            (context.phase == Phase.INCOME.value)
            & (context.inforce_weight > self.settings.minimum_inforce_weight)
        )
        full_score = np.full(context.n_paths, -np.inf)
        if models.full_withdrawal_advantage:
            if models.full_fold_ids is None:
                raise RuntimeError("Missing Full complete-path fold assignment.")
            fold_ids = np.asarray(models.full_fold_ids, dtype=np.int64)
            if fold_ids.shape != (context.n_paths,):
                raise ValueError("Full fold IDs do not match the training paths.")
            for fold, regression in enumerate(models.full_withdrawal_advantage):
                selected = fold_ids == fold
                if regression is None or not np.any(selected):
                    continue
                prediction = regression.predict_features(base)
                buffer = (
                    self.settings.exercise_tolerance_aud
                    + self.settings.exercise_buffer_rmse_multiplier
                    * regression.oof_rmse_aud
                )
                full_score[selected] = prediction[selected] - buffer
        partial_score = np.full(context.n_paths, -np.inf)
        partial_fraction = np.zeros(context.n_paths)
        if self.settings.allow_partial_withdrawal \
                and models.partial_withdrawal_advantage:
            if models.partial_fold_ids is None:
                raise RuntimeError("Missing Partial complete-path fold assignment.")
            fold_ids = np.asarray(models.partial_fold_ids, dtype=np.int64)
            if fold_ids.shape != (context.n_paths,):
                raise ValueError("Partial fold IDs do not match the training paths.")
            for fold, regression in enumerate(models.partial_withdrawal_advantage):
                selected = fold_ids == fold
                if regression is None or not np.any(selected):
                    continue
                fold_score, fold_fraction = _predict_best_partial_action(
                    regression, context, base, self.settings
                )
                partial_score[selected] = fold_score[selected]
                partial_fraction[selected] = fold_fraction[selected]

        take_partial = in_income & (partial_score > 0.0)
        take_full = (
            in_income
            & context.full_withdrawal_eligible
            & (full_score > 0.0)
            & (full_score > partial_score + self.settings.exercise_tolerance_aud)
        )
        action_type = np.full(
            context.n_paths, IncomeActionType.CONTINUE.value, dtype="<U32"
        )
        fraction = np.zeros(context.n_paths)
        action_type[take_partial] = IncomeActionType.PARTIAL_WITHDRAWAL.value
        fraction[take_partial] = partial_fraction[take_partial]
        action_type[take_full] = IncomeActionType.FULL_WITHDRAWAL.value
        fraction[take_full] = 0.0
        return IncomeActionDecision(
            action_type=action_type,
            partial_fraction_of_max=fraction,
        )

    def choose_income_action(
        self,
        *,
        context: IncomeActionDecisionContext,
    ) -> IncomeActionDecision:
        if not isinstance(context, IncomeActionDecisionContext):
            raise TypeError("Training Income action requires decision context.")
        step = int(context.step)
        self.contexts[step] = context
        if self.override_step is not None and step == int(self.override_step):
            action_type = np.full(
                context.n_paths, IncomeActionType.CONTINUE.value, dtype="<U32"
            )
            fraction = np.zeros(context.n_paths)
            if self.override_action is IncomeActionType.FULL_WITHDRAWAL:
                selected = np.asarray(
                    context.full_withdrawal_eligible, dtype=bool
                )
                action_type[selected] = IncomeActionType.FULL_WITHDRAWAL.value
            elif self.override_action is IncomeActionType.PARTIAL_WITHDRAWAL:
                supplied = np.asarray(
                    self.override_partial_fraction, dtype=float
                )
                if supplied.ndim == 0:
                    supplied = np.full(context.n_paths, float(supplied))
                if supplied.shape != (context.n_paths,):
                    raise ValueError("Partial override must match the path sample.")
                selected = (
                    context.partial_withdrawal_eligible
                    & (supplied > 0.0)
                    & (supplied <= 1.0)
                    & (
                        context.max_partial_gross_amount * supplied
                        >= 100.0 - 1.0e-10
                    )
                )
                action_type[selected] = IncomeActionType.PARTIAL_WITHDRAWAL.value
                fraction[selected] = supplied[selected]
            decision = IncomeActionDecision(
                action_type=action_type,
                partial_fraction_of_max=fraction,
            )
        else:
            models = self.regressions_by_step.get(step)
            decision = (
                IncomeActionDecision(
                    action_type=np.full(
                        context.n_paths,
                        IncomeActionType.CONTINUE.value,
                        dtype="<U32",
                    ),
                    partial_fraction_of_max=np.zeros(context.n_paths),
                )
                if models is None
                else self._cross_fitted_decision(context, models)
            )
        self.decisions[step] = decision
        return decision


@dataclass
class _FixedElectionContextRecorder:
    start_step: int
    election_contexts: dict[int, IncomeElectionDecisionContext] = field(
        default_factory=dict
    )
    anniversary_only: bool = field(default=True, init=False, repr=False)

    def start_income_mask(
        self,
        *,
        context: IncomeElectionDecisionContext,
    ) -> NDArray[np.bool_]:
        self.election_contexts[int(context.step)] = context
        return context.voluntary_election_eligible & (
            int(context.step) >= int(self.start_step)
        )


@dataclass(frozen=True)
class _SurrenderPhaseFit:
    policy: OptimalSurrenderPolicy
    cross_fitted_policy: CrossFittedOptimalSurrenderPolicy
    diagnostics: tuple[OptimalBehaviourRegressionDiagnostic, ...]
    training_policyholder_value_aud: float
    training_continue_value_aud: float
    training_candidate_value_aud: float
    fallback_used: bool


def _continue_only_surrender_phase_fallback(
    fit: _SurrenderPhaseFit,
    settings: OptimalBehaviourLSMCSettings,
) -> _SurrenderPhaseFit:
    """Replace an unusable annual lapse fit by the explicit Continue rule.

    The attempted candidate value and diagnostics remain available for audit,
    while neither the deployable nor cross-fitted fallback can exercise an
    absent Full-Withdrawal regression.
    """
    return replace(
        fit,
        policy=OptimalSurrenderPolicy(regressions={}, settings=settings),
        cross_fitted_policy=CrossFittedOptimalSurrenderPolicy(
            regressions_by_step={},
            fold_ids_by_step={},
            settings=settings,
        ),
        training_policyholder_value_aud=fit.training_continue_value_aud,
        fallback_used=True,
    )


@dataclass(frozen=True)
class OptimalBehaviourPolicyFit:
    policy: OptimalBehaviourPolicy
    cross_fitted_training_policy: CrossFittedOptimalBehaviourPolicy
    diagnostics: tuple[OptimalBehaviourRegressionDiagnostic, ...]
    training_scenario_fingerprint: str
    fit_basis_fingerprint: str
    training_path_count: int
    training_policyholder_value_aud: float
    training_wait_policyholder_value_aud: float
    training_no_action_policyholder_value_aud: float
    training_candidate_policyholder_value_aud: float
    election_fallback_used: bool
    surrender_fallback_used: bool
    selected_fixed_election_step: Optional[int]
    selected_income_action_mode: str
    valid: bool = True
    invalid_reasons: tuple[str, ...] = ()
    fit_version: str = "time_zero_curve_swing_lsmc_v6"
    policyholder_mortality_basis: str = POLICYHOLDER_LSMC_MORTALITY_BASIS
    policyholder_objective_discount_basis: str = (
        POLICYHOLDER_LSMC_OBJECTIVE_DISCOUNT_BASIS
    )
    income_action_exposure_coverage: float = 1.0
    policy_iteration_count: int = 0
    policy_iteration_converged: bool = True
    final_action_agreement: float = 1.0
    final_policy_value_change_aud: float = 0.0
    candidate_policy: Optional[OptimalBehaviourPolicy] = None
    policy_variants: Mapping[str, OptimalBehaviourPolicy] = field(
        default_factory=dict
    )
    selected_policy_name: str = "V11"
    training_fallback_reason: Optional[str] = None

    @property
    def training_optionality_uplift_aud(self) -> float:
        return (
            self.training_policyholder_value_aud
            - self.training_no_action_policyholder_value_aud
        )

    @property
    def training_fallback_used(self) -> bool:
        return self.election_fallback_used or self.surrender_fallback_used


_POLICYHOLDER_CASHFLOW_KEYS = (
    "income_paid",
    "surrender_benefits",
    "terminal_closeout",
)


def _time_zero_curve_discount_factors(
    scenarios: ScenarioSet,
    n_columns: Optional[int] = None,
) -> Array:
    """Return deterministic ``P(0,t)`` factors from today's zero curve.

    The customer Swing objective is an expectation formed at time zero.  It
    therefore uses the current curve at every cashflow date and never the
    realised integral of a simulated future short-rate path.  The market paths
    and their cache-fingerprinted stochastic discount factors remain untouched
    for insurer valuation, CSM and hedge pricing.
    """
    if not isinstance(scenarios, ScenarioSet):
        raise TypeError("scenarios must be a ScenarioSet.")
    columns = len(scenarios.times) if n_columns is None else int(n_columns)
    if columns <= 0 or columns > len(scenarios.times):
        raise ValueError("n_columns must select a non-empty scenario prefix.")
    factors = np.asarray(
        scenarios.config.curve.df(scenarios.times[:columns]), dtype=float
    )
    if factors.shape != (columns,) or not np.all(np.isfinite(factors)) \
            or np.any(factors <= 0.0):
        raise ValueError("Today's zero curve produced invalid discount factors.")
    return np.broadcast_to(factors, (scenarios.n_paths, columns))


def _assert_no_optimal_partial_withdrawals(
    projection: ProjectionResult,
    *,
    context: str,
) -> None:
    """Enforce the annual optimal-policy action set at every rollout boundary."""
    partial = np.asarray(projection.cashflows["partial_withdrawals"], dtype=float)
    if np.any(np.abs(partial) > 1.0e-10):
        raise RuntimeError(
            f"{context} produced Partial Withdrawals; the annual optimal "
            "behaviour action set permits only START and FULL_WITHDRAWAL."
        )


def _discounted_policyholder_cashflows(
    projection: ProjectionResult,
    scenarios: ScenarioSet,
) -> Array:
    n_columns = len(projection.times)
    for excluded in ("death_benefits", "partial_withdrawals"):
        values = np.asarray(projection.cashflows[excluded], dtype=float)
        if np.any(np.abs(values) > 1.0e-10):
            raise RuntimeError(
                "Time-zero customer LSMC requires zero "
                f"{excluded.replace('_', ' ')}."
            )
    cashflows = sum(
        projection.cashflows[name]
        for name in _POLICYHOLDER_CASHFLOW_KEYS
    )
    return np.asarray(
        cashflows * _time_zero_curve_discount_factors(
            scenarios, n_columns
        ),
        dtype=float,
    )


def _contractual_forced_election_step(
    product: IndexLinkedLifetimeIncomeProduct,
    policy: PolicySpec,
) -> int:
    years_to_automatic_age = max(
        float(product.automatic_income_start_age) - float(policy.age), 0.0
    )
    forced_year = max(
        int(np.floor(years_to_automatic_age + 1.0e-12)) + 1,
        int(product.min_years_before_income),
        1,
    )
    return forced_year * STEPS_PER_YEAR


def _oof_r_squared(target: Array, prediction: Array) -> float:
    mean_target = float(np.mean(target))
    residual_ss = float(np.sum((target - prediction) ** 2))
    total_ss = float(np.sum((target - mean_target) ** 2))
    return float(1.0 - residual_ss / total_ss) if total_ss > 0.0 else 1.0


@dataclass(frozen=True)
class IncomeActionAdvantagePolicyFit:
    """Reusable fit boundary for a monthly Bellman transition engine."""

    regressions_by_step: Mapping[int, IncomeActionRegressionSet]
    diagnostics: tuple[OptimalBehaviourRegressionDiagnostic, ...]
    fit_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "regressions_by_step",
            MappingProxyType(dict(sorted(self.regressions_by_step.items()))),
        )
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


def fit_income_action_advantage_policy(
    base_features_by_step: Mapping[int, Array],
    *,
    full_advantage_targets_aud_by_step: Mapping[int, Array],
    partial_fractions_by_step: Mapping[int, Array],
    partial_advantage_targets_aud_by_step: Mapping[int, Array],
    premium: float,
    settings: OptimalBehaviourLSMCSettings = OptimalBehaviourLSMCSettings(),
    fold_ids_by_step: Optional[Mapping[int, NDArray[np.int64]]] = None,
    partial_valid_by_step: Optional[Mapping[int, NDArray[np.bool_]]] = None,
) -> IncomeActionAdvantagePolicyFit:
    """Fit monthly FULL and action-conditioned PARTIAL advantages.

    This array-native API is the integration boundary for the monthly Bellman
    kernel.  Partial alternatives may have shape ``(n_paths, n_candidates)``;
    repeated alternatives inherit their complete-path fold ID, preventing
    action replicas from leaking across train and test folds.
    """
    if not isinstance(settings, OptimalBehaviourLSMCSettings):
        raise TypeError("settings must be OptimalBehaviourLSMCSettings.")
    premium_value = float(premium)
    if not np.isfinite(premium_value) or premium_value <= 0.0:
        raise ValueError("Income-action premium must be positive and finite.")
    steps = tuple(sorted(int(step) for step in base_features_by_step))
    if any(step < 0 for step in steps) or len(steps) != len(base_features_by_step):
        raise ValueError("Income-action decision steps must be unique and non-negative.")
    allowed_steps = set(steps)
    for name, mapping in (
        ("full", full_advantage_targets_aud_by_step),
        ("partial fractions", partial_fractions_by_step),
        ("partial targets", partial_advantage_targets_aud_by_step),
    ):
        if not set(map(int, mapping)).issubset(allowed_steps):
            raise ValueError(f"{name} contains a step without base features.")
    if set(map(int, partial_fractions_by_step)) != set(
        map(int, partial_advantage_targets_aud_by_step)
    ):
        raise ValueError("Partial fraction and target mappings must share steps.")

    rng = np.random.default_rng(settings.fold_seed)
    fitted: dict[int, IncomeActionRegressionSet] = {}
    diagnostics: list[OptimalBehaviourRegressionDiagnostic] = []
    fingerprint_inputs: dict[int, tuple[object, ...]] = {}
    for step in steps:
        base = np.asarray(base_features_by_step[step], dtype=float)
        if base.ndim != 2 or base.shape[1] != len(INCOME_ACTION_FEATURE_NAMES) \
                or not np.all(np.isfinite(base)):
            raise ValueError(
                f"Income-action features at step {step} have an invalid shape/value."
            )
        n_paths = base.shape[0]
        if fold_ids_by_step is None:
            path_ids = np.arange(n_paths, dtype=np.int64)
            rng.shuffle(path_ids)
        else:
            if step not in fold_ids_by_step:
                raise ValueError(f"Missing complete-path fold IDs at step {step}.")
            path_ids = np.asarray(fold_ids_by_step[step], dtype=np.int64)
            if path_ids.shape != (n_paths,) or np.any(path_ids < 0):
                raise ValueError(f"Invalid complete-path fold IDs at step {step}.")

        full_regression: Optional[_ContinuationRegression] = None
        partial_regression: Optional[_ContinuationRegression] = None
        full_target = full_advantage_targets_aud_by_step.get(step)
        if full_target is not None:
            target = np.asarray(full_target, dtype=float)
            if target.shape != (n_paths,) or not np.all(np.isfinite(target)):
                raise ValueError(f"Invalid Full advantage target at step {step}.")
            full_regression, full_oof, folds_used, _fold_models = (
                _cross_fitted_advantage_regression(
                    base,
                    target,
                    premium_value,
                    settings,
                    path_ids,
                    core_feature_indices=INCOME_ACTION_CORE_FEATURE_INDICES,
                    enforce_unique_path_minimum=True,
                )
            )
            buffer = (
                settings.exercise_tolerance_aud
                + settings.exercise_buffer_rmse_multiplier
                * full_regression.oof_rmse_aud
            )
            diagnostics.append(OptimalBehaviourRegressionDiagnostic(
                action_type="full_withdrawal",
                phase="income",
                policy_year=step // STEPS_PER_YEAR,
                decision_step=step,
                observations=n_paths,
                folds_used=folds_used,
                feature_count=int(full_regression.coefficients.size),
                matrix_rank=full_regression.matrix_rank,
                condition_number=full_regression.condition_number,
                oof_rmse_aud=full_regression.oof_rmse_aud,
                oof_r_squared=_oof_r_squared(target, full_oof),
                mean_wait_or_continue_value_aud=0.0,
                mean_action_value_aud=float(np.mean(target)),
                training_action_rate=float(np.mean(full_oof > buffer)),
                regression_accepted_for_action=True,
                fallback_reason=None,
                selected_ridge=full_regression.selected_ridge,
                effective_rank=full_regression.effective_rank,
                basis_level=full_regression.basis_level,
                oof_policy_uplift_aud=float(np.mean(np.where(
                    full_oof > buffer, target, 0.0
                ))),
                relevant_exposure_fraction=1.0,
            ))

        if step in partial_fractions_by_step:
            fractions = np.asarray(partial_fractions_by_step[step], dtype=float)
            targets = np.asarray(
                partial_advantage_targets_aud_by_step[step], dtype=float
            )
            if fractions.ndim != 2 or fractions.shape[0] != n_paths \
                    or targets.shape != fractions.shape:
                raise ValueError(f"Invalid Partial action panel at step {step}.")
            valid = (
                np.ones(fractions.shape, dtype=bool)
                if partial_valid_by_step is None or step not in partial_valid_by_step
                else np.asarray(partial_valid_by_step[step], dtype=bool)
            )
            if valid.shape != fractions.shape:
                raise ValueError(f"Invalid Partial validity mask at step {step}.")
            selected_fraction = fractions[valid]
            selected_target = targets[valid]
            if selected_fraction.size == 0 \
                    or not np.all(np.isfinite(selected_fraction)) \
                    or np.any((selected_fraction <= 0.0) | (selected_fraction > 1.0)) \
                    or not np.all(np.isfinite(selected_target)):
                raise ValueError(f"No finite admissible Partial targets at step {step}.")
            candidate_count = fractions.shape[1]
            repeated_base = np.repeat(base, candidate_count, axis=0)[valid.ravel()]
            repeated_ids = np.repeat(path_ids, candidate_count)[valid.ravel()]
            partial_raw = build_partial_action_regression_features(
                repeated_base, selected_fraction
            )
            partial_regression, partial_oof, folds_used, _fold_models = (
                _cross_fitted_advantage_regression(
                    partial_raw,
                    selected_target,
                    premium_value,
                    settings,
                    repeated_ids,
                    core_feature_indices=PARTIAL_ACTION_CORE_FEATURE_INDICES,
                    enforce_unique_path_minimum=True,
                )
            )
            buffer = (
                settings.exercise_tolerance_aud
                + settings.exercise_buffer_rmse_multiplier
                * partial_regression.oof_rmse_aud
            )
            diagnostics.append(OptimalBehaviourRegressionDiagnostic(
                action_type="partial_withdrawal",
                phase="income",
                policy_year=step // STEPS_PER_YEAR,
                decision_step=step,
                observations=int(selected_fraction.size),
                folds_used=folds_used,
                feature_count=int(partial_regression.coefficients.size),
                matrix_rank=partial_regression.matrix_rank,
                condition_number=partial_regression.condition_number,
                oof_rmse_aud=partial_regression.oof_rmse_aud,
                oof_r_squared=_oof_r_squared(selected_target, partial_oof),
                mean_wait_or_continue_value_aud=0.0,
                mean_action_value_aud=float(np.mean(selected_target)),
                training_action_rate=float(np.mean(partial_oof > buffer)),
                regression_accepted_for_action=True,
                fallback_reason=None,
                selected_ridge=partial_regression.selected_ridge,
                effective_rank=partial_regression.effective_rank,
                basis_level=partial_regression.basis_level,
                oof_policy_uplift_aud=float(np.mean(np.where(
                    partial_oof > buffer, selected_target, 0.0
                ))),
                relevant_exposure_fraction=1.0,
            ))

        if full_regression is None and partial_regression is None:
            raise ValueError(f"Step {step} has no Income action target.")
        fitted[step] = IncomeActionRegressionSet(
            full_withdrawal_advantage=full_regression,
            partial_withdrawal_advantage=partial_regression,
        )
        fingerprint_inputs[step] = (base, full_target, partial_fractions_by_step.get(step),
                                    partial_advantage_targets_aud_by_step.get(step), path_ids)

    return IncomeActionAdvantagePolicyFit(
        regressions_by_step=fitted,
        diagnostics=tuple(sorted(
            diagnostics, key=lambda item: (item.decision_step, item.action_type)
        )),
        fit_fingerprint=assumption_fingerprint(
            "monthly_income_action_advantage_lsmc_v2",
            fingerprint_inputs,
            premium_value,
            settings,
        ),
    )


def _fit_surrender_phase_from_projection(
    *,
    projection: ProjectionResult,
    contexts: Mapping[int, SurrenderDecisionContext],
    scenarios: ScenarioSet,
    premium: float,
    settings: OptimalBehaviourLSMCSettings,
    base_fold_ids: NDArray[np.int64],
) -> _SurrenderPhaseFit:
    """Fit the Income subproblem across a stratified Election-state sample."""
    discounted_cashflow = _discounted_policyholder_cashflows(
        projection, scenarios
    )
    objective_discount = _time_zero_curve_discount_factors(
        scenarios, discounted_cashflow.shape[1]
    )
    no_action_path_value = np.sum(discounted_cashflow, axis=1)
    n_steps = discounted_cashflow.shape[1] - 1
    decision_steps = sorted(
        int(step) for step in contexts if 0 < int(step) < n_steps
    )
    if not decision_steps:
        empty_policy = OptimalSurrenderPolicy(regressions={}, settings=settings)
        empty_cross = CrossFittedOptimalSurrenderPolicy(
            regressions_by_step={}, fold_ids_by_step={}, settings=settings
        )
        value = float(np.mean(no_action_path_value))
        return _SurrenderPhaseFit(
            policy=empty_policy,
            cross_fitted_policy=empty_cross,
            diagnostics=(),
            training_policyholder_value_aud=value,
            training_continue_value_aud=value,
            training_candidate_value_aud=value,
            fallback_used=False,
        )

    regressions: dict[int, _ContinuationRegression] = {}
    fold_regressions_by_step: dict[
        int, tuple[_ContinuationRegression, ...]
    ] = {}
    fold_ids_by_step: dict[int, NDArray[np.int64]] = {}
    diagnostics: list[OptimalBehaviourRegressionDiagnostic] = []
    minimum_observations = _minimum_cross_fit_observations(settings, 1)
    material_failures: list[str] = []
    training_panels: dict[int, tuple[Array, Array, NDArray[np.int64]]] = {}

    last_step = decision_steps[-1]
    future_value_0 = np.sum(
        discounted_cashflow[:, last_step + 1:], axis=1
    )
    for position in range(len(decision_steps) - 1, -1, -1):
        step = decision_steps[position]
        context = contexts[step]
        scale_0 = objective_discount[:, step] * context.inforce_weight
        eligible = (
            (context.phase == Phase.INCOME.value)
            & context.full_withdrawal_eligible
            & (context.inforce_weight > settings.minimum_inforce_weight)
            & (scale_0 > 1.0e-300)
        )
        dominated_zero_surrender = (
            eligible
            & (
                context.surrender_value
                <= settings.exercise_tolerance_aud
            )
            & (
                future_value_0
                >= -settings.exercise_tolerance_aud * scale_0
            )
        )
        # Do not train an exercise boundary where FULL pays zero and the
        # realised CONTINUE value is non-negative.  Those rows have the
        # deterministic CONTINUE action and remain in the carried value.
        eligible &= ~dominated_zero_surrender
        eligible_index = np.flatnonzero(eligible)
        observations = int(eligible_index.size)
        accepted = False
        fallback_reason: Optional[str] = None
        folds_used = 0
        continuation_target = np.zeros(0)
        immediate = np.zeros(0)
        oof_continuation = np.zeros(0)
        advantage_target = np.zeros(0)
        regression: Optional[_ContinuationRegression] = None
        fold_regressions: tuple[_ContinuationRegression, ...] = ()

        if observations:
            continuation_target = (
                future_value_0[eligible] / scale_0[eligible]
            )
            immediate = context.surrender_value[eligible]
            advantage_target = immediate - continuation_target
            raw = build_surrender_regression_features(
                context, premium
            )[eligible]
            local_ids = base_fold_ids[eligible_index]
            training_panels[step] = (raw, advantage_target, local_ids)
            try:
                (
                    regression,
                    oof_continuation,
                    folds_used,
                    fold_regressions,
                ) = _cross_fitted_advantage_regression(
                    raw,
                    advantage_target,
                    premium,
                    settings,
                    local_ids,
                    core_feature_indices=CORE_FEATURE_INDICES,
                )
                full_stable = _regression_is_stable(regression, settings)
                folds_stable = all(
                    _regression_is_stable(fold, settings)
                    for fold in fold_regressions
                )
                accepted = bool(full_stable and folds_stable)
                if not full_stable:
                    fallback_reason = "full_regression_unstable"
                elif not folds_stable:
                    fallback_reason = "cross_fit_fold_unstable"
            except (ValueError, np.linalg.LinAlgError) as exc:
                fallback_reason = f"cross_fit_failed:{exc}"
                neighbours = [
                    panel for other_step, panel in training_panels.items()
                    if other_step != step and abs(other_step - step) <= STEPS_PER_YEAR
                ]
                if neighbours:
                    pooled_raw = np.concatenate((raw, *(item[0] for item in neighbours)))
                    pooled_target = np.concatenate((
                        advantage_target, *(item[1] for item in neighbours)
                    ))
                    pooled_ids = np.concatenate((
                        local_ids, *(item[2] for item in neighbours)
                    ))
                    try:
                        (
                            regression,
                            pooled_oof,
                            folds_used,
                            fold_regressions,
                        ) = _cross_fitted_advantage_regression(
                            pooled_raw,
                            pooled_target,
                            premium,
                            settings,
                            pooled_ids,
                            core_feature_indices=CORE_FEATURE_INDICES,
                        )
                        regression = replace(
                            regression,
                            basis_level=f"pooled_12m/{regression.basis_level}",
                        )
                        fold_regressions = tuple(
                            replace(item, basis_level=regression.basis_level)
                            for item in fold_regressions
                        )
                        oof_continuation = pooled_oof[:observations]
                        accepted = True
                        fallback_reason = None
                    except (ValueError, np.linalg.LinAlgError) as pooled_exc:
                        fallback_reason += f";pooled_12m_failed:{pooled_exc}"
        else:
            fallback_reason = (
                f"too_few_observations:{observations}<{minimum_observations}"
            )

        exercise = np.zeros(scenarios.n_paths, dtype=bool)
        training_action_rate = 0.0
        if accepted and regression is not None:
            buffer = (
                settings.exercise_tolerance_aud
                + settings.exercise_buffer_rmse_multiplier
                * regression.oof_rmse_aud
            )
            exercise_eligible = oof_continuation > buffer
            exercise[eligible_index] = exercise_eligible
            training_action_rate = float(np.mean(exercise_eligible))
            regressions[step] = regression
            fold_regressions_by_step[step] = fold_regressions
            fold_ids_by_step[step] = np.mod(
                base_fold_ids, folds_used
            ).astype(np.int64)
        relevant_exposure = float(np.mean(np.where(
            eligible, context.inforce_weight, 0.0
        )))
        if not accepted and relevant_exposure > settings.immaterial_exposure_fraction:
            material_failures.append(
                f"step={step},exposure={relevant_exposure:.12g},reason={fallback_reason}"
            )
        elif not accepted:
            fallback_reason = "immaterial_no_fit"

        future_value_0 = np.where(
            exercise,
            scale_0 * context.surrender_value,
            future_value_0,
        )
        diagnostics.append(OptimalBehaviourRegressionDiagnostic(
            action_type="full_withdrawal",
            phase="income",
            policy_year=step // STEPS_PER_YEAR,
            decision_step=step,
            observations=observations,
            folds_used=folds_used,
            feature_count=(
                0 if regression is None else int(regression.coefficients.size)
            ),
            matrix_rank=0 if regression is None else regression.matrix_rank,
            condition_number=(
                None if regression is None else regression.condition_number
            ),
            oof_rmse_aud=(
                None if regression is None else regression.oof_rmse_aud
            ),
            oof_r_squared=(
                None
                if regression is None
                else _oof_r_squared(advantage_target, oof_continuation)
            ),
            mean_wait_or_continue_value_aud=(
                float(np.mean(continuation_target))
                if continuation_target.size else 0.0
            ),
            mean_action_value_aud=(
                float(np.mean(immediate)) if immediate.size else 0.0
            ),
            training_action_rate=training_action_rate,
            regression_accepted_for_action=accepted,
            fallback_reason=fallback_reason,
            wait_regression_rank=(
                None if regression is None else regression.matrix_rank
            ),
            wait_regression_condition_number=(
                None if regression is None else regression.condition_number
            ),
            wait_regression_oof_rmse_aud=(
                None if regression is None else regression.oof_rmse_aud
            ),
            selected_ridge=(
                None if regression is None else regression.selected_ridge
            ),
            effective_rank=(
                0 if regression is None else regression.effective_rank
            ),
            basis_level=(
                "none" if regression is None else regression.basis_level
            ),
            oof_policy_uplift_aud=(
                None if regression is None else float(np.mean(np.where(
                    oof_continuation > (
                        settings.exercise_tolerance_aud
                        + settings.exercise_buffer_rmse_multiplier
                        * regression.oof_rmse_aud
                    ),
                    advantage_target,
                    0.0,
                )))
            ),
            relevant_exposure_fraction=relevant_exposure,
        ))
        if position > 0:
            previous = decision_steps[position - 1]
            future_value_0 += np.sum(
                discounted_cashflow[:, previous + 1:step + 1], axis=1
            )

    if material_failures:
        raise ValueError(
            "Material Income advantage regressions unavailable: "
            + " | ".join(material_failures)
        )

    first_step = decision_steps[0]
    candidate_path_value = (
        np.sum(discounted_cashflow[:, :first_step + 1], axis=1)
        + future_value_0
    )
    candidate_value = float(np.mean(candidate_path_value))
    continue_value = float(np.mean(no_action_path_value))
    fallback_used = bool(
        settings.fallback_to_no_action_if_training_underperforms
        and candidate_value < continue_value
    )
    if fallback_used:
        regressions.clear()
        fold_regressions_by_step.clear()
        fold_ids_by_step.clear()
    selected_value = continue_value if fallback_used else candidate_value
    return _SurrenderPhaseFit(
        policy=OptimalSurrenderPolicy(
            regressions=MappingProxyType(dict(sorted(regressions.items()))),
            settings=settings,
            regressions_are_advantages=True,
            strict_missing_material_regression=not fallback_used,
            terminal_step=n_steps,
        ),
        cross_fitted_policy=CrossFittedOptimalSurrenderPolicy(
            regressions_by_step=MappingProxyType(dict(sorted(
                fold_regressions_by_step.items()
            ))),
            fold_ids_by_step=MappingProxyType(dict(sorted(
                fold_ids_by_step.items()
            ))),
            settings=settings,
            regressions_are_advantages=True,
            strict_missing_material_regression=not fallback_used,
            terminal_step=n_steps,
        ),
        diagnostics=tuple(sorted(
            diagnostics, key=lambda item: item.decision_step
        )),
        training_policyholder_value_aud=selected_value,
        training_continue_value_aud=continue_value,
        training_candidate_value_aud=candidate_value,
        fallback_used=fallback_used,
    )


def _fit_election_regression_pair(
    raw_features: Array,
    wait_target_aud: Array,
    start_target_aud: Array,
    *,
    premium: float,
    settings: OptimalBehaviourLSMCSettings,
    fold_ids: NDArray[np.int64],
) -> tuple[
    _ElectionRegressionPair,
    Array,
    int,
    tuple[_ElectionRegressionPair, ...],
]:
    advantage_target = np.asarray(start_target_aud) - np.asarray(wait_target_aud)
    (
        advantage_regression,
        advantage_oof,
        folds_used,
        fold_advantage_regressions,
    ) = _cross_fitted_advantage_regression(
        raw_features,
        advantage_target,
        premium,
        settings,
        fold_ids,
        core_feature_indices=ELECTION_CORE_FEATURE_INDICES,
        enforce_unique_path_minimum=True,
    )
    full_pair = _ElectionRegressionPair(advantage=advantage_regression)
    fold_pairs = tuple(
        _ElectionRegressionPair(advantage=advantage)
        for advantage in fold_advantage_regressions
    )
    return (
        full_pair,
        advantage_oof,
        folds_used,
        fold_pairs,
    )


def _project_fixed_election_branch(
    *,
    start_step: int,
    product: IndexLinkedLifetimeIncomeProduct,
    policy: PolicySpec,
    scenarios: ScenarioSet,
    behaviour: BehaviourModel,
    mortality: MortalityTable,
    expenses: Optional[ExpenseAssumptions],
    config: ProjectionConfig,
    surrender_policy: Optional[object] = None,
    income_action_policy: Optional[object] = None,
) -> tuple[ProjectionResult, _FixedElectionContextRecorder]:
    election_recorder = _FixedElectionContextRecorder(start_step=start_step)
    projection = project(
        product,
        policy,
        scenarios,
        behaviour,
        mortality,
        expenses=expenses,
        config=config,
        surrender_policy=surrender_policy,
        income_election_policy=election_recorder,
        income_action_policy=income_action_policy,
    )
    return projection, election_recorder


def _project_assigned_election_income_branch(
    *,
    assigned_start_steps: NDArray[np.int64],
    action_policy: _CrossFittedIncomeActionPolicy,
    product: IndexLinkedLifetimeIncomeProduct,
    policy: PolicySpec,
    scenarios: ScenarioSet,
    behaviour: BehaviourModel,
    mortality: MortalityTable,
    expenses: Optional[ExpenseAssumptions],
    config: ProjectionConfig,
    income_transition_observer: Optional[object] = None,
) -> tuple[ProjectionResult, _AssignedElectionContextRecorder]:
    election_policy = _AssignedElectionContextRecorder(
        assigned_start_steps=np.asarray(assigned_start_steps, dtype=np.int64)
    )
    projection = project(
        product,
        policy,
        scenarios,
        behaviour,
        mortality,
        expenses=expenses,
        config=config,
        income_election_policy=election_policy,
        income_action_policy=action_policy,
        income_transition_observer=income_transition_observer,
    )
    return projection, election_policy


def _project_assigned_election_annual_branch(
    *,
    assigned_start_steps: NDArray[np.int64],
    product: IndexLinkedLifetimeIncomeProduct,
    policy: PolicySpec,
    scenarios: ScenarioSet,
    behaviour: BehaviourModel,
    mortality: MortalityTable,
    expenses: Optional[ExpenseAssumptions],
    config: ProjectionConfig,
    surrender_policy: Optional[object] = None,
) -> tuple[ProjectionResult, _AssignedElectionContextRecorder]:
    """Project assigned STARTs with only annual Income FULL decisions.

    The recorder and the fitted policy both use the Projector's existing
    Anniversary surrender boundary.  Consequently the twelve monthly
    transitions between decision dates remain canonical product transitions;
    this LSMC layer does not recreate fees, mortality, Income or MVA logic.
    """
    election_policy = _AssignedElectionContextRecorder(
        assigned_start_steps=np.asarray(assigned_start_steps, dtype=np.int64)
    )
    projection = project(
        product,
        policy,
        scenarios,
        behaviour,
        mortality,
        expenses=expenses,
        config=config,
        income_election_policy=election_policy,
        surrender_policy=(
            election_policy if surrender_policy is None else surrender_policy
        ),
    )
    _assert_no_optimal_partial_withdrawals(
        projection,
        context="Assigned-start annual Income rollout",
    )
    return projection, election_policy


@dataclass(frozen=True)
class _MonthlyIncomeActionFit:
    regressions_by_step: Mapping[int, IncomeActionRegressionSet]
    cross_fitted_regressions_by_step: Mapping[
        int, _CrossFittedIncomeActionRegressionSet
    ]
    diagnostics: tuple[OptimalBehaviourRegressionDiagnostic, ...]
    training_policyholder_value_aud: float
    training_continue_value_aud: float
    training_candidate_value_aud: float
    covered_exposure_fraction: float
    policy_iteration_count: int
    policy_iteration_converged: bool
    final_action_agreement: float
    final_value_change_aud: float
    assigned_start_features: Array
    assigned_start_value_targets_aud: Array
    assigned_start_path_ids: NDArray[np.int64]
    fallback_used: bool
    valid: bool
    invalid_reasons: tuple[str, ...]


def _cross_fitted_state_value_regression(
    raw_features: Array,
    value_target_aud: Array,
    premium: float,
    settings: OptimalBehaviourLSMCSettings,
    fold_ids: NDArray[np.int64],
    *,
    core_feature_indices: NDArray[np.int64] = (
        INCOME_ACTION_CORE_FEATURE_INDICES
    ),
    enforce_unique_path_minimum: bool = False,
) -> tuple[
    _ContinuationRegression,
    Array,
    int,
    tuple[_ContinuationRegression, ...],
]:
    """Fit full -> linear core -> constant for an internal state value."""
    attempts = (
        ("full", None),
        ("core", np.asarray(core_feature_indices, dtype=np.int64)),
        ("constant", np.zeros(0, dtype=np.int64)),
    )
    failures: list[str] = []
    for basis_level, indices in attempts:
        try:
            fit = _cross_fitted_regression(
                raw_features,
                value_target_aud,
                premium,
                settings,
                fold_ids,
                advantage_target=False,
                feature_indices=indices,
                basis_level=basis_level,
                enforce_unique_path_minimum=enforce_unique_path_minimum,
            )
            regression, _oof, _folds, fold_regressions = fit
            if _regression_is_stable(regression, settings) and all(
                _regression_is_stable(item, settings)
                for item in fold_regressions
            ):
                return fit
            failures.append(f"{basis_level}:unstable")
        except (ValueError, np.linalg.LinAlgError) as exc:
            failures.append(f"{basis_level}:{exc}")
    raise ValueError(";".join(failures))



def _assigned_start_value_training_panel(
    *,
    projection: ProjectionResult,
    election_contexts: Mapping[int, IncomeElectionDecisionContext],
    assigned_start_steps: NDArray[np.int64],
    election_steps: tuple[int, ...],
    scenarios: ScenarioSet,
    premium: float,
    issue_age: float,
    automatic_income_start_age: float,
    settings: OptimalBehaviourLSMCSettings,
    complete_path_ids: NDArray[np.int64],
) -> tuple[Array, Array, NDArray[np.int64]]:
    """Build one randomized, pooled START-value sample across Election years."""
    if projection.phase_cashflows is None:
        raise RuntimeError(
            "Assigned-start value fitting requires phase cashflow ledgers."
        )
    assigned = np.asarray(assigned_start_steps, dtype=np.int64)
    path_ids = np.asarray(complete_path_ids, dtype=np.int64)
    if assigned.shape != (scenarios.n_paths,) \
            or path_ids.shape != (scenarios.n_paths,):
        raise ValueError("Assigned starts and complete-path IDs must match paths.")
    discounted = _discounted_policyholder_cashflows(projection, scenarios)
    objective_discount = _time_zero_curve_discount_factors(
        scenarios, discounted.shape[1]
    )
    post_election = projection.phase_cashflows[
        "policyholder_benefits_post_election"
    ]
    raw_panels: list[Array] = []
    target_panels: list[Array] = []
    id_panels: list[NDArray[np.int64]] = []
    for step in election_steps:
        context = election_contexts.get(step)
        if context is None:
            continue
        scale_0 = objective_discount[:, step] * context.inforce_weight
        eligible = (
            (assigned == step)
            & (context.phase == Phase.GROWTH.value)
            & (
                context.voluntary_election_eligible
                | np.asarray(context.forced_election, dtype=bool)
            )
            & (
                context.inforce_weight
                > settings.minimum_inforce_weight
            )
            & (scale_0 > 1.0e-300)
        )
        index = np.flatnonzero(eligible)
        if index.size == 0:
            continue
        current_post_election_0 = (
            post_election[index, step] * objective_discount[index, step]
        )
        future_0 = np.sum(discounted[index, step + 1:], axis=1)
        target_panels.append(
            (current_post_election_0 + future_0) / scale_0[index]
        )
        election_features = build_income_election_regression_features(
            context,
            premium,
            issue_age,
            automatic_income_start_age,
        )
        raw_panels.append(
            _build_income_start_value_features(election_features)[index]
        )
        id_panels.append(path_ids[index])
    if not raw_panels:
        raise ValueError("Assigned-start rollout produced no material START sample.")
    raw = np.concatenate(raw_panels, axis=0)
    target = np.concatenate(target_panels)
    ids = np.concatenate(id_panels).astype(np.int64, copy=False)
    if np.unique(ids).size != ids.size:
        raise ValueError(
            "Each complete path must enter the randomized START panel once."
        )
    return raw, target, ids


def _predict_fold_pure_regression(
    raw_features: Array,
    complete_path_ids: NDArray[np.int64],
    fold_regressions: tuple[_ContinuationRegression, ...],
) -> Array:
    """Evaluate each row with the model that excluded its complete path."""
    raw = np.asarray(raw_features, dtype=float)
    ids = np.asarray(complete_path_ids, dtype=np.int64)
    if raw.ndim != 2 or ids.shape != (raw.shape[0],):
        raise ValueError("Fold-pure prediction inputs are inconsistent.")
    if not fold_regressions:
        raise ValueError("Fold-pure prediction requires fitted fold models.")
    fold_ids = np.mod(ids, len(fold_regressions))
    prediction = np.zeros(raw.shape[0])
    for fold, regression in enumerate(fold_regressions):
        selected = fold_ids == fold
        if np.any(selected):
            prediction[selected] = regression.predict_features(raw[selected])
    return prediction


def _monthly_action_diagnostic(
    *,
    action_type: str,
    step: int,
    target: Array,
    oof: Array,
    regression: _ContinuationRegression,
    folds_used: int,
    settings: OptimalBehaviourLSMCSettings,
    exposure: float,
    iteration: int,
) -> OptimalBehaviourRegressionDiagnostic:
    buffer = (
        settings.exercise_tolerance_aud
        + settings.exercise_buffer_rmse_multiplier * regression.oof_rmse_aud
    )
    action = oof > buffer
    return OptimalBehaviourRegressionDiagnostic(
        action_type=action_type,
        phase="income",
        policy_year=step // STEPS_PER_YEAR,
        decision_step=step,
        observations=int(target.size),
        folds_used=folds_used,
        feature_count=int(regression.coefficients.size),
        matrix_rank=regression.matrix_rank,
        condition_number=regression.condition_number,
        oof_rmse_aud=regression.oof_rmse_aud,
        oof_r_squared=_oof_r_squared(target, oof),
        mean_wait_or_continue_value_aud=0.0,
        mean_action_value_aud=float(np.mean(target)),
        training_action_rate=float(np.mean(action)),
        regression_accepted_for_action=True,
        fallback_reason=None,
        action_regression_rank=regression.matrix_rank,
        action_regression_condition_number=regression.condition_number,
        action_regression_oof_rmse_aud=regression.oof_rmse_aud,
        selected_ridge=regression.selected_ridge,
        effective_rank=regression.effective_rank,
        basis_level=f"iteration_{iteration}/{regression.basis_level}",
        oof_policy_uplift_aud=float(np.mean(np.where(action, target, 0.0))),
        relevant_exposure_fraction=float(exposure),
    )


def _failed_monthly_action_diagnostic(
    *,
    action_type: str,
    step: int,
    observations: int,
    reason: str,
    exposure: float,
    iteration: int,
) -> OptimalBehaviourRegressionDiagnostic:
    return OptimalBehaviourRegressionDiagnostic(
        action_type=action_type,
        phase="income",
        policy_year=step // STEPS_PER_YEAR,
        decision_step=step,
        observations=int(observations),
        folds_used=0,
        feature_count=0,
        matrix_rank=0,
        condition_number=None,
        oof_rmse_aud=None,
        oof_r_squared=None,
        mean_wait_or_continue_value_aud=0.0,
        mean_action_value_aud=0.0,
        training_action_rate=0.0,
        regression_accepted_for_action=False,
        fallback_reason=reason,
        basis_level=f"iteration_{iteration}/none",
        relevant_exposure_fraction=float(exposure),
    )


def _conservative_continue_advantage_regression(
    *,
    raw_feature_count: int,
    premium: float,
) -> _ContinuationRegression:
    """Represent an explicit Continue rule where cross-fitting is impossible."""
    return _ContinuationRegression(
        premium=float(premium),
        raw_feature_count=int(raw_feature_count),
        active_feature_indices=np.zeros(0, dtype=np.int64),
        orthogonal_components=np.zeros((0, 0)),
        centre=np.zeros(0),
        scale=np.zeros(0),
        coefficients=np.zeros(1),
        condition_number=1.0,
        matrix_rank=1,
        oof_rmse_aud=0.0,
        selected_ridge=0.0,
        effective_rank=0,
        basis_level="conservative_continue_insufficient_sample",
        clip_non_negative=False,
        raw_intercept_aud=0.0,
        raw_coefficients_aud=np.zeros(int(raw_feature_count)),
    )


def _income_policy_rollout(
    *,
    regressions_by_step: Mapping[int, _CrossFittedIncomeActionRegressionSet],
    assigned_start_steps: NDArray[np.int64],
    product: IndexLinkedLifetimeIncomeProduct,
    policy: PolicySpec,
    scenarios: ScenarioSet,
    behaviour: BehaviourModel,
    mortality: MortalityTable,
    expenses: Optional[ExpenseAssumptions],
    config: ProjectionConfig,
    premium: float,
    settings: OptimalBehaviourLSMCSettings,
) -> tuple[
    float,
    _CrossFittedIncomeActionPolicy,
    ProjectionResult,
    IncomeTransitionPanelCollector,
    _AssignedElectionContextRecorder,
]:
    action_policy = _CrossFittedIncomeActionPolicy(
        regressions_by_step=regressions_by_step,
        premium=premium,
        settings=settings,
    )
    transition_collector = IncomeTransitionPanelCollector()
    projection, election_recorder = _project_assigned_election_income_branch(
        assigned_start_steps=assigned_start_steps,
        action_policy=action_policy,
        product=product,
        policy=policy,
        scenarios=scenarios,
        behaviour=behaviour,
        mortality=mortality,
        expenses=expenses,
        config=config,
        income_transition_observer=transition_collector,
    )
    path_value = np.sum(
        _discounted_policyholder_cashflows(projection, scenarios), axis=1
    )
    return (
        float(np.mean(path_value)),
        action_policy,
        projection,
        transition_collector,
        election_recorder,
    )


def _income_action_agreement(
    left: _CrossFittedIncomeActionPolicy,
    right: _CrossFittedIncomeActionPolicy,
    settings: OptimalBehaviourLSMCSettings,
) -> float:
    matches = 0
    relevant = 0
    for step in sorted(set(left.decisions) | set(right.decisions)):
        left_decision = left.decisions.get(step)
        right_decision = right.decisions.get(step)
        left_context = left.contexts.get(step)
        right_context = right.contexts.get(step)
        if left_decision is None or right_decision is None \
                or left_context is None or right_context is None:
            continue
        if left_context.n_paths != right_context.n_paths \
                or left_decision.n_paths != right_decision.n_paths \
                or left_decision.n_paths != left_context.n_paths:
            raise ValueError(
                "Policy-iteration agreement requires common scenario paths."
            )
        # Agreement is measured only where both on-policy rollouts reach the
        # same monthly boundary with positive Income exposure.
        eligible = (
            (left_context.phase == Phase.INCOME.value)
            & (right_context.phase == Phase.INCOME.value)
            & (
                left_context.inforce_weight
                > settings.minimum_inforce_weight
            )
            & (
                right_context.inforce_weight
                > settings.minimum_inforce_weight
            )
        )
        same = (
            left_decision.action_type == right_decision.action_type
        ) & np.isclose(
            left_decision.partial_fraction_of_max,
            right_decision.partial_fraction_of_max,
            atol=1.0e-10,
            rtol=0.0,
        )
        matches += int(np.count_nonzero(eligible & same))
        relevant += int(np.count_nonzero(eligible))
    return 1.0 if relevant == 0 else float(matches / relevant)


@dataclass(frozen=True)
class _OuterFoldIncomeBellmanChain:
    """One recursively fold-pure monthly Income Bellman chain."""

    regressions_by_step: Mapping[int, IncomeActionRegressionSet]
    diagnostics: tuple[OptimalBehaviourRegressionDiagnostic, ...]
    deployment_exposure: float
    covered_deployment_exposure: float
    material_failures: tuple[str, ...]


def _fit_monthly_income_action_phase(
    *,
    assigned_start_steps: NDArray[np.int64],
    product: IndexLinkedLifetimeIncomeProduct,
    policy: PolicySpec,
    scenarios: ScenarioSet,
    behaviour: BehaviourModel,
    mortality: MortalityTable,
    expenses: Optional[ExpenseAssumptions],
    config: ProjectionConfig,
    premium: float,
    settings: OptimalBehaviourLSMCSettings,
    base_fold_ids: NDArray[np.int64],
) -> _MonthlyIncomeActionFit:
    """Solve Income actions with complete outer-fold Bellman isolation.

    A deployment chain is fitted on all paths.  Independently, outer chain
    ``f`` excludes fold ``f`` from every action and state-value regression at
    every later month.  Consequently a held-out path cannot re-enter its own
    continuation target indirectly through a downstream fitted policy/value.
    """
    n_paths = scenarios.n_paths
    fold_source = np.asarray(base_fold_ids, dtype=np.int64)
    assigned = np.asarray(assigned_start_steps, dtype=np.int64)
    if fold_source.shape != (n_paths,) or np.unique(fold_source).size != n_paths:
        raise ValueError("Monthly Bellman folds require one stable ID per path.")
    if assigned.shape != (n_paths,):
        raise ValueError("Assigned Income starts must match the training paths.")
    outer_folds = int(settings.n_folds)
    outer_fold_ids = np.mod(fold_source, outer_folds).astype(np.int64)
    if any(not np.any(outer_fold_ids == fold) for fold in range(outer_folds)):
        raise ValueError("Every outer Bellman fold must contain a complete path.")

    (
        continue_value,
        prior_rollout_policy,
        continue_projection,
        continue_collector,
        continue_election_recorder,
    ) = _income_policy_rollout(
        regressions_by_step={},
        assigned_start_steps=assigned,
        product=product,
        policy=policy,
        scenarios=scenarios,
        behaviour=behaviour,
        mortality=mortality,
        expenses=expenses,
        config=config,
        premium=premium,
        settings=settings,
    )

    def solve_chain(
        collector: IncomeTransitionPanelCollector,
        *,
        excluded_fold: Optional[int],
        iteration: int,
        record_diagnostics: bool,
    ) -> _OuterFoldIncomeBellmanChain:
        """Fit one full downstream chain without the requested outer fold."""
        states_by_step = collector.states_by_step
        slices_by_step = collector.slices_by_step
        if set(states_by_step) != set(slices_by_step):
            raise RuntimeError("Income transition collector panels are inconsistent.")

        action_models: dict[int, IncomeActionRegressionSet] = {}
        value_models: dict[int, _ContinuationRegression] = {}
        diagnostics: list[OptimalBehaviourRegressionDiagnostic] = []
        failures: list[str] = []
        missing_continuations: set[tuple[int, int]] = set()
        total_deployment_exposure = 0.0
        covered_deployment_exposure = 0.0
        full_panels: dict[int, tuple[Array, Array, NDArray[np.int64]]] = {}
        partial_panels: dict[int, tuple[Array, Array, NDArray[np.int64]]] = {}
        value_panels: dict[int, tuple[Array, Array, NDArray[np.int64]]] = {}
        chain_name = (
            "deployment" if excluded_fold is None else f"outer_fold_{excluded_fold}"
        )

        def fit_panel_with_pooling(
            *,
            step: int,
            raw: Array,
            target: Array,
            path_ids: NDArray[np.int64],
            history: dict[int, tuple[Array, Array, NDArray[np.int64]]],
            advantage: bool,
            core_indices: NDArray[np.int64] = INCOME_ACTION_CORE_FEATURE_INDICES,
        ) -> tuple[_ContinuationRegression, Array, int]:
            raw_array = np.asarray(raw, dtype=float)
            target_array = np.asarray(target, dtype=float)
            ids = np.asarray(path_ids, dtype=np.int64)
            history[step] = (raw_array, target_array, ids)

            def fit_one(
                fit_raw: Array,
                fit_target: Array,
                fit_ids: NDArray[np.int64],
            ) -> tuple[_ContinuationRegression, Array, int]:
                # An outer fold has already removed one residue class from
                # ``fit_ids``.  Reusing those sparse IDs modulo the inner fold
                # count can therefore create an empty inner test fold.  Dense
                # IDs preserve complete-path grouping (including pooled rows)
                # while distributing only the paths that are actually present
                # across the nested cross-fit folds.
                _, dense_fit_ids = np.unique(
                    fit_ids, return_inverse=True
                )
                dense_fit_ids = dense_fit_ids.astype(np.int64, copy=False)
                if advantage:
                    regression, oof, folds_used, _fold_models = (
                        _cross_fitted_advantage_regression(
                            fit_raw,
                            fit_target,
                            premium,
                            settings,
                            dense_fit_ids,
                            core_feature_indices=core_indices,
                            enforce_unique_path_minimum=True,
                        )
                    )
                else:
                    regression, oof, folds_used, _fold_models = (
                        _cross_fitted_state_value_regression(
                            fit_raw,
                            fit_target,
                            premium,
                            settings,
                            dense_fit_ids,
                            enforce_unique_path_minimum=True,
                        )
                    )
                return regression, oof, folds_used

            local_error: Optional[Exception] = None
            try:
                return fit_one(raw_array, target_array, ids)
            except (ValueError, np.linalg.LinAlgError) as exc:
                local_error = exc

            neighbours = [
                panel
                for other_step, panel in history.items()
                if other_step != step
                and 0 < other_step - step <= STEPS_PER_YEAR
            ]
            if neighbours:
                pooled_raw = np.concatenate(
                    (raw_array, *(item[0] for item in neighbours))
                )
                pooled_target = np.concatenate(
                    (target_array, *(item[1] for item in neighbours))
                )
                pooled_ids = np.concatenate(
                    (ids, *(item[2] for item in neighbours))
                )
                try:
                    regression, pooled_oof, folds_used = fit_one(
                        pooled_raw, pooled_target, pooled_ids
                    )
                    regression = replace(
                        regression,
                        basis_level=f"pooled_12m/{regression.basis_level}",
                    )
                    return regression, pooled_oof[:target_array.size], folds_used
                except (ValueError, np.linalg.LinAlgError) as exc:
                    local_error = exc
            raise ValueError(
                str(local_error)
                if local_error is not None
                else "fit_failed_after_12m_pooling"
            )

        for step in sorted(states_by_step, reverse=True):
            state = states_by_step[step]
            scenario_slice = slices_by_step[step]
            context = build_income_action_decision_context(
                state, product, scenario_slice, terminal=False
            )
            path_index = np.asarray(state.path_index, dtype=np.int64)
            if path_index.shape != (context.n_paths,) \
                    or np.any(path_index < 0) or np.any(path_index >= n_paths):
                raise RuntimeError("Collected Income path indices are inconsistent.")
            path_ids = fold_source[path_index]
            state_outer_folds = outer_fold_ids[path_index]
            train_path = (
                np.ones(context.n_paths, dtype=bool)
                if excluded_fold is None
                else state_outer_folds != excluded_fold
            )
            deployment_path = (
                np.ones(context.n_paths, dtype=bool)
                if excluded_fold is None
                else state_outer_folds == excluded_fold
            )
            base_features = build_income_action_regression_features(
                context, premium
            )
            current_weight = np.asarray(state.inforce_weight, dtype=float)
            in_income = (
                (context.phase == Phase.INCOME.value)
                & (current_weight > settings.minimum_inforce_weight)
            )
            full_eligible = in_income & context.full_withdrawal_eligible
            partial_eligible = (
                in_income
                & context.partial_withdrawal_eligible
                & bool(settings.allow_partial_withdrawal)
            )
            train_full = full_eligible & train_path
            train_partial = partial_eligible & train_path
            deploy_full = full_eligible & deployment_path
            deploy_partial = partial_eligible & deployment_path
            full_deployment_exposure = float(np.sum(np.where(
                deploy_full, current_weight, 0.0
            )) / n_paths)
            partial_deployment_exposure = float(np.sum(np.where(
                deploy_partial, current_weight, 0.0
            )) / n_paths)
            total_deployment_exposure += (
                full_deployment_exposure + partial_deployment_exposure
            )

            def make_decision(
                action: IncomeActionType,
                selected: NDArray[np.bool_],
                fraction: Optional[Array] = None,
            ) -> IncomeActionDecision:
                selected_array = np.asarray(selected, dtype=bool)
                if selected_array.shape != (context.n_paths,):
                    raise ValueError("Bellman action mask has an invalid shape.")
                action_type = np.full(
                    context.n_paths,
                    IncomeActionType.CONTINUE.value,
                    dtype="<U18",
                )
                fractions = np.zeros(context.n_paths)
                if action is IncomeActionType.FULL_WITHDRAWAL:
                    action_type[selected_array] = action.value
                elif action is IncomeActionType.PARTIAL_WITHDRAWAL:
                    if fraction is None:
                        raise ValueError("Partial Bellman action requires a fraction.")
                    supplied = np.asarray(fraction, dtype=float)
                    if supplied.shape != (context.n_paths,):
                        raise ValueError(
                            "Partial Bellman fractions have an invalid shape."
                        )
                    action_type[selected_array] = action.value
                    fractions[selected_array] = supplied[selected_array]
                elif action is not IncomeActionType.CONTINUE:
                    raise ValueError("Unknown Bellman Income action.")
                return IncomeActionDecision(
                    action_type=action_type,
                    partial_fraction_of_max=fractions,
                )

            def action_q_value(decision: IncomeActionDecision) -> Array:
                action_transition = apply_income_action(
                    state,
                    decision,
                    product,
                    scenario_slice,
                    terminal=False,
                )
                month_transition = advance_income_month(
                    action_transition.post_action_state,
                    product,
                    policy,
                    scenario_slice,
                )
                next_state = month_transition.next_state
                objective_discount_ratio = float(
                    scenarios.config.curve.forward_df(
                        float(scenarios.times[step]),
                        float(scenarios.times[int(next_state.step)]),
                    )
                )
                next_active = (
                    (next_state.phase == Phase.INCOME.value)
                    & (
                        next_state.inforce_weight
                        > settings.minimum_inforce_weight
                    )
                )
                next_value = np.zeros(context.n_paths)
                if np.any(next_active):
                    value_model = value_models.get(int(next_state.step))
                    if value_model is None:
                        key = (int(step), int(next_state.step))
                        exposure = float(np.sum(np.where(
                            next_active, next_state.inforce_weight, 0.0
                        )) / n_paths)
                        if exposure > settings.immaterial_exposure_fraction \
                                and key not in missing_continuations:
                            missing_continuations.add(key)
                            failures.append(
                                f"{chain_name}:continuation@{step}->"
                                f"{next_state.step}:missing_state_value_model"
                            )
                    else:
                        next_raw = build_income_action_regression_features(
                            month_transition.next_context, premium
                        )
                        per_exposure = np.maximum(
                            value_model.predict_features(next_raw), 0.0
                        )
                        next_value = np.where(
                            next_active,
                            next_state.inforce_weight * per_exposure,
                            0.0,
                        )
                return np.asarray(
                    action_transition.policyholder_cashflow
                    + objective_discount_ratio
                    * (
                        month_transition.mandatory_policyholder_cashflow
                        + next_value
                    ),
                    dtype=float,
                )

            continue_q = action_q_value(make_decision(
                IncomeActionType.CONTINUE,
                np.zeros(context.n_paths, dtype=bool),
            ))
            full_q = continue_q.copy()
            full_regression: Optional[_ContinuationRegression] = None
            full_score = np.full(context.n_paths, -np.inf)
            if np.any(full_eligible):
                full_q = action_q_value(make_decision(
                    IncomeActionType.FULL_WITHDRAWAL, full_eligible
                ))
            minimum_full_paths = _minimum_cross_fit_observations(settings, 1)
            full_training_path_count = int(np.unique(
                path_ids[train_full]
            ).size)
            conservative_continue = bool(
                not settings.allow_partial_withdrawal
                and full_training_path_count < minimum_full_paths
            )
            if conservative_continue:
                # With Full Lapse as the only voluntary Income action, a
                # sample too small for honest complete-path cross-fitting has
                # one safe lower-bound decision: Continue.  Store that rule as
                # an explicit model so deployment does not confuse it with a
                # missing material regression.
                full_regression = _conservative_continue_advantage_regression(
                    raw_feature_count=base_features.shape[1],
                    premium=premium,
                )
                covered_deployment_exposure += full_deployment_exposure
                if record_diagnostics:
                    diagnostics.append(_failed_monthly_action_diagnostic(
                        action_type="full_withdrawal",
                        step=step,
                        observations=int(np.count_nonzero(train_full)),
                        reason=(
                            "insufficient_unique_paths_conservative_continue:"
                            f"{full_training_path_count}<"
                            f"{minimum_full_paths}"
                        ),
                        exposure=full_deployment_exposure,
                        iteration=iteration,
                    ))
            elif np.any(train_full):
                full_target = np.divide(
                    full_q[train_full] - continue_q[train_full],
                    current_weight[train_full],
                    out=np.zeros(np.count_nonzero(train_full)),
                    where=current_weight[train_full] > 0.0,
                )
                try:
                    full_regression, full_oof, full_folds_used = (
                        fit_panel_with_pooling(
                            step=step,
                            raw=base_features[train_full],
                            target=full_target,
                            path_ids=path_ids[train_full],
                            history=full_panels,
                            advantage=True,
                            core_indices=INCOME_ACTION_CORE_FEATURE_INDICES,
                        )
                    )
                    full_buffer = (
                        settings.exercise_tolerance_aud
                        + settings.exercise_buffer_rmse_multiplier
                        * full_regression.oof_rmse_aud
                    )
                    full_score[full_eligible] = (
                        full_regression.predict_features(base_features)[full_eligible]
                        - full_buffer
                    )
                    covered_deployment_exposure += full_deployment_exposure
                    if record_diagnostics:
                        diagnostics.append(_monthly_action_diagnostic(
                            action_type="full_withdrawal",
                            step=step,
                            target=full_target,
                            oof=full_oof,
                            regression=full_regression,
                            folds_used=full_folds_used,
                            settings=settings,
                            exposure=full_deployment_exposure,
                            iteration=iteration,
                        ))
                except (ValueError, np.linalg.LinAlgError) as exc:
                    reason = f"cross_fit_failed:{exc}"
                    training_exposure = float(np.sum(np.where(
                        train_full, current_weight, 0.0
                    )) / n_paths)
                    immaterial = max(
                        training_exposure, full_deployment_exposure
                    ) <= settings.immaterial_exposure_fraction
                    if not immaterial:
                        failures.append(f"{chain_name}:full@{step}:{reason}")
                    if record_diagnostics:
                        diagnostics.append(_failed_monthly_action_diagnostic(
                            action_type="full_withdrawal",
                            step=step,
                            observations=int(np.count_nonzero(train_full)),
                            reason="immaterial_no_fit" if immaterial else reason,
                            exposure=full_deployment_exposure,
                            iteration=iteration,
                        ))
            elif full_deployment_exposure > settings.immaterial_exposure_fraction:
                failures.append(
                    f"{chain_name}:full@{step}:no_outer_training_exposure"
                )

            partial_regression: Optional[_ContinuationRegression] = None
            partial_score = np.full(context.n_paths, -np.inf)
            partial_fraction = np.zeros(context.n_paths)
            if np.any(partial_eligible):
                coarse_fraction = _partial_candidate_fractions(context)
                candidate_fractions: list[Array] = [
                    coarse_fraction[:, column].copy()
                    for column in range(coarse_fraction.shape[1])
                ]
                candidate_targets: list[Array] = []
                candidate_valid: list[NDArray[np.bool_]] = []

                def evaluate_partial_candidate(
                    fraction: Array,
                    valid: NDArray[np.bool_],
                ) -> Array:
                    if not np.any(valid):
                        return np.zeros(context.n_paths)
                    candidate_q = action_q_value(make_decision(
                        IncomeActionType.PARTIAL_WITHDRAWAL,
                        valid,
                        fraction,
                    ))
                    return np.divide(
                        candidate_q - continue_q,
                        current_weight,
                        out=np.zeros(context.n_paths),
                        where=current_weight > 0.0,
                    )

                for fraction in candidate_fractions:
                    valid = (
                        partial_eligible
                        & (fraction > 0.0)
                        & (
                            context.max_partial_gross_amount * fraction
                            >= 100.0 - 1.0e-10
                        )
                    )
                    candidate_valid.append(valid)
                    candidate_targets.append(
                        evaluate_partial_candidate(fraction, valid)
                    )

                # The fitted Partial surface is quadratic in the action
                # fraction, so the five contractual anchor amounts identify
                # its shape.  The former two realised midpoint transitions
                # were redundant once deployment maximises that quadratic
                # analytically.
                fraction_matrix = coarse_fraction
                target_matrix = np.column_stack(candidate_targets)
                valid_matrix = np.column_stack(candidate_valid)
                training_valid = valid_matrix & train_path[:, None]
                selected_fraction = fraction_matrix[training_valid]
                selected_target = target_matrix[training_valid]
                candidate_count = fraction_matrix.shape[1]
                repeated_base = np.repeat(
                    base_features, candidate_count, axis=0
                )[training_valid.ravel()]
                repeated_ids = np.repeat(
                    path_ids, candidate_count
                )[training_valid.ravel()]
                if selected_fraction.size:
                    try:
                        partial_raw = build_partial_action_regression_features(
                            repeated_base, selected_fraction
                        )
                        (
                            partial_regression,
                            partial_oof,
                            partial_folds_used,
                        ) = fit_panel_with_pooling(
                            step=step,
                            raw=partial_raw,
                            target=selected_target,
                            path_ids=repeated_ids,
                            history=partial_panels,
                            advantage=True,
                            core_indices=PARTIAL_ACTION_CORE_FEATURE_INDICES,
                        )
                        partial_score, partial_fraction = (
                            _predict_best_partial_action(
                                partial_regression,
                                context,
                                base_features,
                                settings,
                            )
                        )
                        covered_deployment_exposure += (
                            partial_deployment_exposure
                        )
                        if record_diagnostics:
                            diagnostics.append(_monthly_action_diagnostic(
                                action_type="partial_withdrawal",
                                step=step,
                                target=selected_target,
                                oof=partial_oof,
                                regression=partial_regression,
                                folds_used=partial_folds_used,
                                settings=settings,
                                exposure=partial_deployment_exposure,
                                iteration=iteration,
                            ))
                    except (ValueError, np.linalg.LinAlgError) as exc:
                        reason = f"cross_fit_failed:{exc}"
                        training_exposure = float(np.sum(np.where(
                            train_partial, current_weight, 0.0
                        )) / n_paths)
                        immaterial = max(
                            training_exposure, partial_deployment_exposure
                        ) <= settings.immaterial_exposure_fraction
                        if not immaterial:
                            failures.append(
                                f"{chain_name}:partial@{step}:{reason}"
                            )
                        if record_diagnostics:
                            diagnostics.append(_failed_monthly_action_diagnostic(
                                action_type="partial_withdrawal",
                                step=step,
                                observations=int(selected_fraction.size),
                                reason=(
                                    "immaterial_no_fit" if immaterial else reason
                                ),
                                exposure=partial_deployment_exposure,
                                iteration=iteration,
                            ))
                elif (
                    partial_deployment_exposure
                    > settings.immaterial_exposure_fraction
                ):
                    failures.append(
                        f"{chain_name}:partial@{step}:"
                        "no_outer_training_candidates"
                    )

            action_models[step] = IncomeActionRegressionSet(
                full_withdrawal_advantage=full_regression,
                partial_withdrawal_advantage=partial_regression,
            )

            take_partial = in_income & (partial_score > 0.0)
            selected_q = continue_q.copy()
            if np.any(take_partial):
                partial_policy_q = action_q_value(make_decision(
                    IncomeActionType.PARTIAL_WITHDRAWAL,
                    take_partial,
                    partial_fraction,
                ))
                selected_q = np.where(
                    take_partial, partial_policy_q, selected_q
                )
            take_full = (
                full_eligible
                & (full_score > 0.0)
                & (
                    full_score
                    > partial_score + settings.exercise_tolerance_aud
                )
            )
            selected_q = np.where(take_full, full_q, selected_q)

            train_value = in_income & train_path
            if np.any(train_value):
                value_target = np.divide(
                    selected_q[train_value],
                    current_weight[train_value],
                    out=np.zeros(np.count_nonzero(train_value)),
                    where=current_weight[train_value] > 0.0,
                )
                try:
                    value_regression, _value_oof, _value_folds = (
                        fit_panel_with_pooling(
                            step=step,
                            raw=base_features[train_value],
                            target=value_target,
                            path_ids=path_ids[train_value],
                            history=value_panels,
                            advantage=False,
                        )
                    )
                    value_models[step] = value_regression
                except (ValueError, np.linalg.LinAlgError) as exc:
                    value_exposure = float(np.sum(np.where(
                        train_value | (in_income & deployment_path),
                        current_weight,
                        0.0,
                    )) / n_paths)
                    if value_exposure > settings.immaterial_exposure_fraction:
                        failures.append(
                            f"{chain_name}:state_value@{step}:"
                            f"cross_fit_failed:{exc}"
                        )

        return _OuterFoldIncomeBellmanChain(
            regressions_by_step=MappingProxyType(dict(sorted(action_models.items()))),
            diagnostics=tuple(diagnostics),
            deployment_exposure=float(total_deployment_exposure),
            covered_deployment_exposure=float(covered_deployment_exposure),
            material_failures=tuple(dict.fromkeys(failures)),
        )

    def assembled_cross_fitted_models(
        chains: tuple[_OuterFoldIncomeBellmanChain, ...],
    ) -> Mapping[int, _CrossFittedIncomeActionRegressionSet]:
        if len(chains) != outer_folds:
            raise RuntimeError("Outer-fold Income chains are incomplete.")
        steps = sorted(set().union(*(
            set(chain.regressions_by_step) for chain in chains
        )))
        assembled: dict[int, _CrossFittedIncomeActionRegressionSet] = {}
        for step in steps:
            per_fold = [
                chain.regressions_by_step.get(step, IncomeActionRegressionSet())
                for chain in chains
            ]
            full = tuple(
                item.full_withdrawal_advantage for item in per_fold
            )
            partial = tuple(
                item.partial_withdrawal_advantage for item in per_fold
            )
            assembled[step] = _CrossFittedIncomeActionRegressionSet(
                full_withdrawal_advantage=(
                    full if any(item is not None for item in full) else ()
                ),
                full_fold_ids=(
                    outer_fold_ids.copy()
                    if any(item is not None for item in full) else None
                ),
                partial_withdrawal_advantage=(
                    partial if any(item is not None for item in partial) else ()
                ),
                partial_fold_ids=(
                    outer_fold_ids.copy()
                    if any(item is not None for item in partial) else None
                ),
            )
        return MappingProxyType(dict(sorted(assembled.items())))

    def uniform_chain_models(
        chain: _OuterFoldIncomeBellmanChain,
    ) -> Mapping[int, _CrossFittedIncomeActionRegressionSet]:
        uniform: dict[int, _CrossFittedIncomeActionRegressionSet] = {}
        for step, item in chain.regressions_by_step.items():
            full = item.full_withdrawal_advantage
            partial = item.partial_withdrawal_advantage
            uniform[step] = _CrossFittedIncomeActionRegressionSet(
                full_withdrawal_advantage=(
                    tuple(full for _ in range(outer_folds))
                    if full is not None else ()
                ),
                full_fold_ids=(
                    outer_fold_ids.copy() if full is not None else None
                ),
                partial_withdrawal_advantage=(
                    tuple(partial for _ in range(outer_folds))
                    if partial is not None else ()
                ),
                partial_fold_ids=(
                    outer_fold_ids.copy() if partial is not None else None
                ),
            )
        return MappingProxyType(dict(sorted(uniform.items())))

    global_collector = continue_collector
    fold_collectors = tuple(continue_collector for _ in range(outer_folds))
    prior_value = continue_value
    final_frozen: Mapping[int, IncomeActionRegressionSet] = MappingProxyType({})
    final_cross: Mapping[
        int, _CrossFittedIncomeActionRegressionSet
    ] = MappingProxyType({})
    all_diagnostics: list[OptimalBehaviourRegressionDiagnostic] = []
    final_coverage = 1.0
    final_agreement = 1.0
    final_value_change = 0.0
    final_material_failures: tuple[str, ...] = ()
    final_assigned_projection: Optional[ProjectionResult] = None
    final_assigned_election_recorder: Optional[
        _AssignedElectionContextRecorder
    ] = None
    converged = False
    iteration_count = 0

    for iteration in range(1, 3):
        iteration_count = iteration
        global_chain = solve_chain(
            global_collector,
            excluded_fold=None,
            iteration=iteration,
            record_diagnostics=True,
        )
        fold_chains = tuple(
            solve_chain(
                fold_collectors[fold],
                excluded_fold=fold,
                iteration=iteration,
                record_diagnostics=False,
            )
            for fold in range(outer_folds)
        )
        cross = assembled_cross_fitted_models(fold_chains)
        cross_total = float(sum(
            chain.deployment_exposure for chain in fold_chains
        ))
        cross_covered = float(sum(
            chain.covered_deployment_exposure for chain in fold_chains
        ))
        cross_coverage = (
            1.0 if cross_total <= 0.0 else cross_covered / cross_total
        )
        global_coverage = (
            1.0
            if global_chain.deployment_exposure <= 0.0
            else global_chain.covered_deployment_exposure
            / global_chain.deployment_exposure
        )
        coverage = float(min(cross_coverage, global_coverage))
        material_failures = tuple(dict.fromkeys((
            *global_chain.material_failures,
            *(failure for chain in fold_chains
              for failure in chain.material_failures),
        )))

        (
            new_value,
            new_rollout_policy,
            new_projection,
            new_cross_collector,
            new_election_recorder,
        ) = _income_policy_rollout(
            regressions_by_step=cross,
            assigned_start_steps=assigned,
            product=product,
            policy=policy,
            scenarios=scenarios,
            behaviour=behaviour,
            mortality=mortality,
            expenses=expenses,
            config=config,
            premium=premium,
            settings=settings,
        )
        agreement = _income_action_agreement(
            prior_rollout_policy, new_rollout_policy, settings
        )
        value_change = abs(new_value - prior_value)
        converged = bool(
            agreement >= 0.99 and value_change <= 0.001 * premium
        )
        all_diagnostics.extend(global_chain.diagnostics)
        final_frozen = global_chain.regressions_by_step
        final_cross = cross
        final_coverage = coverage
        final_agreement = agreement
        final_value_change = value_change
        final_material_failures = material_failures
        final_assigned_projection = new_projection
        final_assigned_election_recorder = new_election_recorder
        prior_value = new_value
        prior_rollout_policy = new_rollout_policy
        if converged:
            break
        if iteration == 1:
            # The deployment re-fit may use the assembled OOF state sample.
            # Each outer re-fit instead receives a collector generated by its
            # own fold-excluding policy on every path.  Thus paths in fold f
            # cannot influence even the state distribution used by chain f.
            global_collector = new_cross_collector
            next_fold_collectors: list[IncomeTransitionPanelCollector] = []
            for chain in fold_chains:
                (
                    _chain_value,
                    _chain_policy,
                    _chain_projection,
                    chain_collector,
                    _chain_election_recorder,
                ) = _income_policy_rollout(
                    regressions_by_step=uniform_chain_models(chain),
                    assigned_start_steps=assigned,
                    product=product,
                    policy=policy,
                    scenarios=scenarios,
                    behaviour=behaviour,
                    mortality=mortality,
                    expenses=expenses,
                    config=config,
                    premium=premium,
                    settings=settings,
                )
                next_fold_collectors.append(chain_collector)
            fold_collectors = tuple(next_fold_collectors)

    if final_assigned_projection is None \
            or final_assigned_election_recorder is None:
        raise RuntimeError("Income policy iteration produced no assigned-start rollout.")

    candidate_value = prior_value
    fallback_used = bool(
        settings.fallback_to_no_action_if_training_underperforms
        and candidate_value < continue_value
    )
    selected_frozen = MappingProxyType({}) if fallback_used else final_frozen
    selected_cross = MappingProxyType({}) if fallback_used else final_cross
    selected_projection = (
        continue_projection if fallback_used else final_assigned_projection
    )
    selected_election_recorder = (
        continue_election_recorder
        if fallback_used else final_assigned_election_recorder
    )

    (
        assigned_start_features,
        assigned_start_value_targets,
        assigned_start_path_ids,
    ) = _assigned_start_value_training_panel(
        projection=selected_projection,
        election_contexts=selected_election_recorder.election_contexts,
        assigned_start_steps=assigned,
        election_steps=tuple(sorted(
            int(step) for step in np.unique(assigned)
        )),
        scenarios=scenarios,
        premium=premium,
        issue_age=float(policy.age),
        automatic_income_start_age=float(
            product.automatic_income_start_age
        ),
        settings=settings,
        complete_path_ids=fold_source,
    )

    invalid_reasons: list[str] = []
    if not fallback_used and final_coverage < 0.99:
        invalid_reasons.append(
            f"income_action_exposure_coverage:{final_coverage:.12g}<0.99"
        )
    if not fallback_used and final_material_failures:
        invalid_reasons.append(
            "material_income_action_fit_failure:"
            + "|".join(final_material_failures)
        )
    if not fallback_used and not converged:
        invalid_reasons.append("policy_iteration_not_converged")
    return _MonthlyIncomeActionFit(
        regressions_by_step=selected_frozen,
        cross_fitted_regressions_by_step=selected_cross,
        diagnostics=tuple(sorted(
            all_diagnostics,
            key=lambda item: (
                item.basis_level, item.decision_step, item.action_type
            ),
        )),
        training_policyholder_value_aud=(
            continue_value if fallback_used else candidate_value
        ),
        training_continue_value_aud=continue_value,
        training_candidate_value_aud=candidate_value,
        covered_exposure_fraction=(1.0 if fallback_used else final_coverage),
        policy_iteration_count=iteration_count,
        policy_iteration_converged=(True if fallback_used else converged),
        final_action_agreement=(1.0 if fallback_used else final_agreement),
        final_value_change_aud=(0.0 if fallback_used else final_value_change),
        assigned_start_features=assigned_start_features,
        assigned_start_value_targets_aud=assigned_start_value_targets,
        assigned_start_path_ids=assigned_start_path_ids,
        fallback_used=fallback_used,
        valid=not invalid_reasons,
        invalid_reasons=tuple(dict.fromkeys(invalid_reasons)),
    )


def _fit_monthly_optimal_behaviour_policy_legacy(
    product: IndexLinkedLifetimeIncomeProduct,
    policy: PolicySpec,
    training_scenarios: ScenarioSet,
    mortality: MortalityTable,
    *,
    expenses: Optional[ExpenseAssumptions] = None,
    projection_config: ProjectionConfig = ProjectionConfig(record_paths=False),
    settings: OptimalBehaviourLSMCSettings = OptimalBehaviourLSMCSettings(),
    fit_basis_inputs: Optional[Mapping[str, object]] = None,
) -> OptimalBehaviourPolicyFit:
    """Fit annual Election and unified monthly Partial/Full Income actions.

    The absorbing phase order permits the Income subproblem to be solved first.
    Its state sample is stratified over every admissible Election anniversary.
    One fold-stratified randomized START rollout is then used to fit a pooled,
    cross-fitted START value surface across all admissible Election years.
    Growth backward induction compares that fold-pure START value with WAIT
    followed by the already-fitted later combined policy.  This removes the
    former full monthly re-projection for every possible start year.
    """
    if not isinstance(settings, OptimalBehaviourLSMCSettings):
        raise TypeError("settings must be OptimalBehaviourLSMCSettings.")
    if tuple(settings.ridge_grid) != RIDGE_GRID_DEFAULT:
        raise ValueError(
            "Combined optimal-behaviour LSMC v3 requires the fixed Ridge grid "
            f"{RIDGE_GRID_DEFAULT}; got {tuple(settings.ridge_grid)}."
        )
    policy.validate_against(product)
    if policy.age_pension_plus:
        raise NotImplementedError("Generic optimal behaviour does not support APS.")
    if product.allows_growth_surrender or product.allows_growth_withdrawals:
        raise ValueError(
            "Combined LSMC requires the generic product's Growth action gates."
        )
    config = replace(projection_config, record_paths=False, heston_cos=False)
    behaviour = no_voluntary_action_behaviour()
    premium = float(policy.net_initial_investment)
    n_paths = training_scenarios.n_paths
    n_steps = training_scenarios.n_steps
    minimum_step = int(product.min_years_before_income) * STEPS_PER_YEAR
    forced_step = _contractual_forced_election_step(product, policy)
    if minimum_step <= 0 or minimum_step % STEPS_PER_YEAR:
        raise ValueError("Income-Election minimum must be a positive whole year.")
    if forced_step > n_steps:
        raise ValueError(
            "Training horizon must reach the contractual forced Election anniversary."
        )
    election_steps = tuple(range(
        minimum_step, forced_step + 1, STEPS_PER_YEAR
    ))
    if not election_steps or election_steps[-1] != forced_step:
        raise ValueError("Contractual Election grid is inconsistent.")

    rng = np.random.default_rng(settings.fold_seed)
    base_fold_ids = np.arange(n_paths, dtype=np.int64)
    rng.shuffle(base_fold_ids)
    # Stratify the synthetic Election starts *within* each cross-fit fold.
    # Reusing ``base_fold_ids`` modulo both the fold count and the number of
    # Election dates can make the two assignments identical whenever those
    # moduli share factors, leaving later regressions without observations in
    # one or more test folds.  The independent within-fold permutations below
    # keep every surviving Election stratum represented across folds.
    assigned_start_steps = np.empty(n_paths, dtype=np.int64)
    fold_labels = base_fold_ids % settings.n_folds
    for fold in range(settings.n_folds):
        fold_paths = np.flatnonzero(fold_labels == fold)
        rng.shuffle(fold_paths)
        assigned_start_steps[fold_paths] = np.asarray(
            [election_steps[index % len(election_steps)]
             for index in range(fold_paths.size)],
            dtype=np.int64,
        )
    income_action_fit = _fit_monthly_income_action_phase(
        assigned_start_steps=assigned_start_steps,
        product=product,
        policy=policy,
        scenarios=training_scenarios,
        behaviour=behaviour,
        mortality=mortality,
        expenses=expenses,
        config=config,
        premium=premium,
        settings=settings,
        base_fold_ids=base_fold_ids,
    )

    # Explicit no-voluntary-action benchmark: wait to the contractual force
    # date and then continue Income without Full Withdrawal.
    no_action_projection, _ = _project_fixed_election_branch(
        start_step=forced_step,
        product=product,
        policy=policy,
        scenarios=training_scenarios,
        behaviour=behaviour,
        mortality=mortality,
        expenses=expenses,
        config=config,
        surrender_policy=None,
    )
    no_action_value = float(np.mean(np.sum(
        _discounted_policyholder_cashflows(
            no_action_projection, training_scenarios
        ),
        axis=1,
    )))

    # One randomized assigned-start rollout already spans every admissible
    # Election year.  Fit a fold-pure pooled START value surface from that
    # rollout instead of re-running the complete monthly projector once for
    # every possible start year.
    start_value_raw = income_action_fit.assigned_start_features
    start_value_target = (
        income_action_fit.assigned_start_value_targets_aud
    )
    start_value_path_ids = income_action_fit.assigned_start_path_ids
    (
        _start_value_regression,
        _start_value_oof,
        _start_value_folds_used,
        start_value_fold_regressions,
    ) = _cross_fitted_state_value_regression(
        start_value_raw,
        start_value_target,
        premium,
        settings,
        start_value_path_ids,
        core_feature_indices=START_VALUE_CORE_FEATURE_INDICES,
        enforce_unique_path_minimum=True,
    )
    start_value_fold_regressions = tuple(
        replace(
            regression,
            basis_level=(
                "pooled_assigned_start/"
                f"{regression.basis_level}"
            ),
        )
        for regression in start_value_fold_regressions
    )

    # A single forced-Election branch supplies all WAIT cashflows and every
    # annual pre-Election context.  Its forced START value remains pathwise and
    # exact; voluntary START values use the fold-pure pooled surface above.
    cross_fitted_income_policy = _CrossFittedIncomeActionPolicy(
        regressions_by_step=(
            income_action_fit.cross_fitted_regressions_by_step
        ),
        premium=premium,
        settings=settings,
    )
    branch_projection, election_recorder = _project_fixed_election_branch(
        start_step=forced_step,
        product=product,
        policy=policy,
        scenarios=training_scenarios,
        behaviour=behaviour,
        mortality=mortality,
        expenses=expenses,
        config=config,
        income_action_policy=cross_fitted_income_policy,
    )
    growth_discounted_cashflow = _discounted_policyholder_cashflows(
        branch_projection, training_scenarios
    )
    objective_discount = _time_zero_curve_discount_factors(
        training_scenarios, len(branch_projection.times)
    )
    if branch_projection.phase_cashflows is None:
        raise RuntimeError(
            "Income-Election Bellman fit requires phase cashflow ledgers."
        )
    growth_pre_election_benefit_0 = (
        branch_projection.phase_cashflows[
            "policyholder_benefits_pre_election"
        ]
        * objective_discount[
            :, :branch_projection.phase_cashflows[
                "policyholder_benefits_pre_election"
            ].shape[1]
        ]
    )
    forced_post_election_current_0 = (
        branch_projection.phase_cashflows[
            "policyholder_benefits_post_election"
        ][:, forced_step]
        * objective_discount[:, forced_step]
    )
    forced_start_value_0 = (
        forced_post_election_current_0
        + np.sum(
            growth_discounted_cashflow[:, forced_step + 1:], axis=1
        )
    )
    growth_contexts = dict(election_recorder.election_contexts)
    wait_path_value_0 = np.sum(growth_discounted_cashflow, axis=1)

    election_regressions: dict[int, _ElectionRegressionPair] = {}
    election_fold_regressions: dict[
        int, tuple[_ElectionRegressionPair, ...]
    ] = {}
    election_fold_ids: dict[int, NDArray[np.int64]] = {}
    election_diagnostics: list[OptimalBehaviourRegressionDiagnostic] = []
    minimum_election_observations = _minimum_cross_fit_observations(
        settings, 1
    )
    material_election_failures: list[str] = []
    election_panels: dict[
        int,
        tuple[Array, Array, Array, NDArray[np.int64]],
    ] = {}

    future_value_0 = forced_start_value_0.copy()
    next_step = forced_step
    for step in reversed(election_steps[:-1]):
        future_value_0 += (
            np.sum(
                growth_discounted_cashflow[:, step + 1:next_step], axis=1
            )
            + growth_pre_election_benefit_0[:, next_step]
        )
        wait_realised_0 = future_value_0.copy()
        start_realised_0 = np.zeros(n_paths)
        context = growth_contexts.get(step)
        if context is None:
            raise ValueError(
                f"Projector did not expose Election context at step {step}."
            )
        scale_0 = objective_discount[:, step] * context.inforce_weight
        eligible = (
            context.voluntary_election_eligible
            & (context.phase == Phase.GROWTH.value)
            & (context.inforce_weight > settings.minimum_inforce_weight)
            & (scale_0 > 1.0e-300)
        )
        eligible_index = np.flatnonzero(eligible)
        observations = int(eligible_index.size)
        accepted = False
        fallback_reason: Optional[str] = None
        folds_used = 0
        wait_target = np.zeros(0)
        start_target = np.zeros(0)
        advantage_oof = np.zeros(0)
        pair: Optional[_ElectionRegressionPair] = None
        fold_pairs: tuple[_ElectionRegressionPair, ...] = ()
        if observations:
            wait_target = wait_realised_0[eligible] / scale_0[eligible]
            election_features = build_income_election_regression_features(
                context,
                premium,
                policy.age,
                product.automatic_income_start_age,
            )
            raw = election_features[eligible]
            start_raw = _build_income_start_value_features(
                election_features
            )[eligible]
            panel_ids = base_fold_ids[eligible_index]
            start_target = _predict_fold_pure_regression(
                start_raw,
                panel_ids,
                start_value_fold_regressions,
            )
            start_realised_0[eligible_index] = (
                scale_0[eligible_index] * start_target
            )
            election_panels[step] = (
                raw, wait_target, start_target, panel_ids
            )

        if observations < minimum_election_observations:
            fallback_reason = (
                f"too_few_observations:{observations}<"
                f"{minimum_election_observations}"
            )
        else:
            try:
                (
                    pair,
                    advantage_oof,
                    folds_used,
                    fold_pairs,
                ) = _fit_election_regression_pair(
                    raw,
                    wait_target,
                    start_target,
                    premium=premium,
                    settings=settings,
                    fold_ids=panel_ids,
                )
                full_stable = pair.stable(settings)
                folds_stable = all(
                    fold_pair.stable(settings) for fold_pair in fold_pairs
                )
                accepted = bool(full_stable and folds_stable)
                if not full_stable:
                    fallback_reason = "full_regression_unstable"
                elif not folds_stable:
                    fallback_reason = "cross_fit_fold_unstable"
            except (ValueError, np.linalg.LinAlgError) as exc:
                fallback_reason = f"cross_fit_failed:{exc}"

        # Fourth fallback level: pool complete-path panels from the nearest
        # already-solved Election years.  The current panel is first so its
        # OOF slice remains directly usable for this decision point.
        if not accepted and observations:
            neighbours = sorted(
                (
                    (other_step, panel)
                    for other_step, panel in election_panels.items()
                    if other_step != step
                ),
                key=lambda item: abs(item[0] - step),
            )[:2]
            if neighbours:
                pooled_raw = np.concatenate((
                    raw, *(panel[0] for _year, panel in neighbours)
                ))
                pooled_wait = np.concatenate((
                    wait_target, *(panel[1] for _year, panel in neighbours)
                ))
                pooled_start = np.concatenate((
                    start_target, *(panel[2] for _year, panel in neighbours)
                ))
                pooled_ids = np.concatenate((
                    panel_ids, *(panel[3] for _year, panel in neighbours)
                ))
                if np.unique(pooled_ids).size \
                        >= minimum_election_observations:
                    try:
                        (
                            pooled_pair,
                            pooled_oof,
                            folds_used,
                            pooled_fold_pairs,
                        ) = _fit_election_regression_pair(
                            pooled_raw,
                            pooled_wait,
                            pooled_start,
                            premium=premium,
                            settings=settings,
                            fold_ids=pooled_ids,
                        )
                        basis = (
                            "pooled_election_years/"
                            f"{pooled_pair.advantage.basis_level}"
                        )
                        pair = _ElectionRegressionPair(
                            advantage=replace(
                                pooled_pair.advantage,
                                basis_level=basis,
                            )
                        )
                        fold_pairs = tuple(
                            _ElectionRegressionPair(
                                advantage=replace(
                                    fold_pair.advantage,
                                    basis_level=basis,
                                )
                            )
                            for fold_pair in pooled_fold_pairs
                        )
                        advantage_oof = pooled_oof[:observations]
                        accepted = bool(
                            pair.stable(settings)
                            and all(
                                fold_pair.stable(settings)
                                for fold_pair in fold_pairs
                            )
                        )
                        fallback_reason = (
                            None
                            if accepted
                            else "pooled_election_regression_unstable"
                        )
                    except (ValueError, np.linalg.LinAlgError) as exc:
                        fallback_reason = (
                            "pooled_election_cross_fit_failed:"
                            f"{exc}"
                        )

        start_action = np.zeros(n_paths, dtype=bool)
        training_action_rate = 0.0
        if accepted and pair is not None:
            buffer = (
                settings.exercise_tolerance_aud
                + settings.exercise_buffer_rmse_multiplier
                * pair.combined_oof_rmse_aud
            )
            action_eligible = advantage_oof > buffer
            start_action[eligible_index] = action_eligible
            training_action_rate = float(np.mean(action_eligible))
            election_regressions[step] = pair
            election_fold_regressions[step] = fold_pairs
            election_fold_ids[step] = np.mod(
                base_fold_ids, folds_used
            ).astype(np.int64)

        relevant_exposure = float(np.mean(np.where(
            eligible, context.inforce_weight, 0.0
        )))
        if not accepted and relevant_exposure > settings.immaterial_exposure_fraction:
            material_election_failures.append(
                f"step={step},exposure={relevant_exposure:.12g},reason={fallback_reason}"
            )
        elif not accepted:
            fallback_reason = "immaterial_no_fit"

        future_value_0 = np.where(
            start_action, start_realised_0, wait_realised_0
        )
        election_diagnostics.append(OptimalBehaviourRegressionDiagnostic(
            action_type="income_election",
            phase="growth",
            policy_year=step // STEPS_PER_YEAR,
            decision_step=step,
            observations=observations,
            folds_used=folds_used,
            feature_count=(
                0
                if pair is None
                else int(pair.advantage.coefficients.size)
            ),
            matrix_rank=(
                0
                if pair is None
                else pair.advantage.matrix_rank
            ),
            condition_number=(
                None
                if pair is None
                else pair.advantage.condition_number
            ),
            oof_rmse_aud=(
                None if pair is None else pair.combined_oof_rmse_aud
            ),
            oof_r_squared=(
                None
                if pair is None
                else _oof_r_squared(
                    start_target - wait_target, advantage_oof
                )
            ),
            mean_wait_or_continue_value_aud=(
                float(np.mean(wait_target)) if wait_target.size else 0.0
            ),
            mean_action_value_aud=(
                float(np.mean(start_target)) if start_target.size else 0.0
            ),
            training_action_rate=training_action_rate,
            regression_accepted_for_action=accepted,
            fallback_reason=fallback_reason,
            wait_regression_rank=(
                None if pair is None else pair.advantage.matrix_rank
            ),
            wait_regression_condition_number=(
                None if pair is None else pair.advantage.condition_number
            ),
            wait_regression_oof_rmse_aud=(
                None if pair is None else pair.advantage.oof_rmse_aud
            ),
            action_regression_rank=(
                None if pair is None else pair.advantage.matrix_rank
            ),
            action_regression_condition_number=(
                None if pair is None else pair.advantage.condition_number
            ),
            action_regression_oof_rmse_aud=(
                None if pair is None else pair.advantage.oof_rmse_aud
            ),
            selected_ridge=(
                None if pair is None else pair.advantage.selected_ridge
            ),
            effective_rank=(
                0 if pair is None else pair.advantage.effective_rank
            ),
            basis_level=(
                "none" if pair is None else pair.advantage.basis_level
            ),
            oof_policy_uplift_aud=(
                None if pair is None else float(np.mean(np.where(
                    advantage_oof > (
                        settings.exercise_tolerance_aud
                        + settings.exercise_buffer_rmse_multiplier
                        * pair.advantage.oof_rmse_aud
                    ),
                    start_target - wait_target,
                    0.0,
                )))
            ),
            relevant_exposure_fraction=relevant_exposure,
        ))
        next_step = step

    first_step = election_steps[0]
    bellman_candidate_path_value = (
        np.sum(growth_discounted_cashflow[:, :first_step + 1], axis=1)
        + future_value_0
    )
    bellman_candidate_value = float(np.mean(bellman_candidate_path_value))
    wait_value = float(np.mean(wait_path_value_0))

    # The v3 combined policy deploys only the unified monthly Income-action
    # surface.  The explicit legacy Surrender object remains empty and is kept
    # solely for API compatibility with fixed-Election Stackelberg callers.
    surrender_policy = OptimalSurrenderPolicy(
        regressions={}, settings=settings
    )
    cross_surrender_policy = CrossFittedOptimalSurrenderPolicy(
        regressions_by_step={}, fold_ids_by_step={}, settings=settings
    )

    # The pooled START surface is used only to learn the boundary.  Value the
    # resulting complete cross-fitted policy once through the canonical
    # projector before applying either training lower-bound gate.  This keeps
    # the speed-up while removing regression-value bias from policy selection.
    candidate_path_value = bellman_candidate_path_value
    candidate_value = bellman_candidate_value
    if not material_election_failures and income_action_fit.valid:
        validation_policy = CrossFittedOptimalBehaviourPolicy(
            election_regressions_by_step=MappingProxyType(dict(sorted(
                election_fold_regressions.items()
            ))),
            election_fold_ids_by_step=MappingProxyType(dict(sorted(
                election_fold_ids.items()
            ))),
            surrender_policy=cross_surrender_policy,
            premium=premium,
            issue_age=float(policy.age),
            settings=settings,
            automatic_income_start_age=float(
                product.automatic_income_start_age
            ),
            income_action_regressions_by_step=(
                income_action_fit.cross_fitted_regressions_by_step
            ),
            monthly_income_actions_required=(
                not income_action_fit.fallback_used
            ),
            valid=True,
        )
        validation_projection = project(
            product,
            policy,
            training_scenarios,
            behaviour,
            mortality,
            expenses=expenses,
            config=config,
            income_election_policy=validation_policy,
            income_action_policy=validation_policy,
        )
        candidate_path_value = np.sum(
            _discounted_policyholder_cashflows(
                validation_projection, training_scenarios
            ),
            axis=1,
        )
        candidate_value = float(np.mean(candidate_path_value))

    # Validation compares the frozen policy with a pre-declared library of
    # fixed Election dates, not merely with WAIT until contractual force.  Use
    # the same library here, on training paths only, so the training fallback
    # and the independent validation gate have coherent lower bounds.  The
    # optional LSMC Income rule is retained at a fixed Election date only when
    # its paired 95% lower confidence bound exceeds the fixed candidate by one
    # basis point of premium.  The fully dynamic policy must clear the same
    # conservative threshold over the best fixed training anchor before it is
    # deployed.  The final evaluation sample is never used for either
    # selection.
    def paired_lower_confidence_bound(
        selected: Array,
        benchmark: Array,
    ) -> float:
        difference = np.asarray(selected, dtype=float) - np.asarray(
            benchmark, dtype=float
        )
        if difference.shape != (n_paths,):
            raise ValueError("Training lower-bound paths must match scenarios.")
        standard_error = float(
            np.std(difference, ddof=1) / np.sqrt(float(difference.size))
        )
        return float(np.mean(difference) - 1.96 * standard_error)

    def fixed_step(year: int) -> int:
        return min(
            forced_step,
            max(minimum_step, int(year) * STEPS_PER_YEAR),
        )

    fixed_election_steps = tuple(dict.fromkeys((
        minimum_step,
        fixed_step(5),
        fixed_step(10),
        fixed_step(policy.effective_income_start_year(product)),
        forced_step,
    )))
    no_action_path_value = np.sum(
        _discounted_policyholder_cashflows(
            no_action_projection, training_scenarios
        ),
        axis=1,
    )
    fixed_training_candidates: list[
        tuple[float, int, str, Array]
    ] = []
    training_selection_margin = premium / 10_000.0
    for anchor_step in fixed_election_steps:
        if anchor_step == forced_step:
            continue_projection = no_action_projection
        else:
            continue_projection, _ = _project_fixed_election_branch(
                start_step=anchor_step,
                product=product,
                policy=policy,
                scenarios=training_scenarios,
                behaviour=behaviour,
                mortality=mortality,
                expenses=expenses,
                config=config,
                income_action_policy=None,
            )
        continue_path_value = (
            no_action_path_value
            if anchor_step == forced_step
            else np.sum(
                _discounted_policyholder_cashflows(
                    continue_projection, training_scenarios
                ),
                axis=1,
            )
        )
        anchor_mode = "continue"
        anchor_path_value = continue_path_value
        if income_action_fit.valid and not income_action_fit.fallback_used:
            anchor_income_policy = _CrossFittedIncomeActionPolicy(
                regressions_by_step=(
                    income_action_fit.cross_fitted_regressions_by_step
                ),
                premium=premium,
                settings=settings,
            )
            income_projection, _ = _project_fixed_election_branch(
                start_step=anchor_step,
                product=product,
                policy=policy,
                scenarios=training_scenarios,
                behaviour=behaviour,
                mortality=mortality,
                expenses=expenses,
                config=config,
                income_action_policy=anchor_income_policy,
            )
            income_path_value = np.sum(
                _discounted_policyholder_cashflows(
                    income_projection, training_scenarios
                ),
                axis=1,
            )
            if paired_lower_confidence_bound(
                income_path_value, continue_path_value
            ) >= training_selection_margin:
                anchor_mode = "lsmc"
                anchor_path_value = income_path_value
        fixed_training_candidates.append((
            float(np.mean(anchor_path_value)),
            int(anchor_step),
            anchor_mode,
            np.asarray(anchor_path_value, dtype=float),
        ))

    (
        best_fixed_value,
        best_fixed_step,
        best_fixed_income_mode,
        best_fixed_path_value,
    ) = max(fixed_training_candidates, key=lambda item: item[0])
    selected_fixed_election_step: Optional[int] = None
    selected_income_action_mode = (
        "continue"
        if income_action_fit.fallback_used or not income_action_fit.valid
        else "lsmc"
    )
    selected_value = candidate_value
    dynamic_fit_complete = bool(
        not material_election_failures and income_action_fit.valid
    )
    if settings.fallback_to_no_action_if_training_underperforms and (
        not dynamic_fit_complete
        or paired_lower_confidence_bound(
            candidate_path_value, best_fixed_path_value
        ) < training_selection_margin
    ):
        selected_fixed_election_step = int(best_fixed_step)
        selected_income_action_mode = best_fixed_income_mode
        selected_value = float(best_fixed_value)

    election_fallback = selected_fixed_election_step is not None
    surrender_fallback = selected_income_action_mode == "continue"

    selected_election_regressions = (
        MappingProxyType({})
        if election_fallback
        else MappingProxyType(dict(sorted(election_regressions.items())))
    )
    selected_election_fold_regressions = (
        MappingProxyType({})
        if election_fallback
        else MappingProxyType(dict(sorted(
            election_fold_regressions.items()
        )))
    )
    selected_election_fold_ids = (
        MappingProxyType({})
        if election_fallback
        else MappingProxyType(dict(sorted(election_fold_ids.items())))
    )
    selected_income_regressions = (
        MappingProxyType({})
        if surrender_fallback
        else income_action_fit.regressions_by_step
    )
    selected_cross_income_regressions = (
        MappingProxyType({})
        if surrender_fallback
        else income_action_fit.cross_fitted_regressions_by_step
    )

    invalid_reason_list = list(income_action_fit.invalid_reasons)
    if material_election_failures:
        invalid_reason_list.append(
            "material_election_fit_failure:"
            + "|".join(material_election_failures)
        )
    invalid_reasons = tuple(dict.fromkeys(invalid_reason_list))
    optimal_policy = OptimalBehaviourPolicy(
        election_regressions=selected_election_regressions,
        surrender_policy=surrender_policy,
        premium=premium,
        issue_age=float(policy.age),
        settings=settings,
        automatic_income_start_age=float(product.automatic_income_start_age),
        fixed_election_step=selected_fixed_election_step,
        income_action_regressions=selected_income_regressions,
        monthly_income_actions_required=not surrender_fallback,
        valid=not invalid_reasons,
        invalid_reasons=invalid_reasons,
    )
    cross_fitted_policy = CrossFittedOptimalBehaviourPolicy(
        election_regressions_by_step=selected_election_fold_regressions,
        election_fold_ids_by_step=selected_election_fold_ids,
        surrender_policy=cross_surrender_policy,
        premium=premium,
        issue_age=float(policy.age),
        settings=settings,
        automatic_income_start_age=float(product.automatic_income_start_age),
        fixed_election_step=selected_fixed_election_step,
        income_action_regressions_by_step=selected_cross_income_regressions,
        monthly_income_actions_required=not surrender_fallback,
        valid=not invalid_reasons,
        invalid_reasons=invalid_reasons,
    )
    # ``income_start_year`` does not constrain the dynamic state transition,
    # but it is one member of the predeclared fixed training-anchor library.
    # It must therefore remain in the fit basis and cache identity.
    optimal_policy_basis = policy
    fit_basis_fingerprint = assumption_fingerprint(
        "combined_optimal_behaviour_lsmc_v3",
        training_scenarios.content_fingerprint,
        product,
        optimal_policy_basis,
        mortality,
        expenses,
        config,
        settings,
        fit_basis_inputs,
    )
    fitted_surrender_policy = replace(
        optimal_policy.surrender_policy,
        provenance_fingerprint=assumption_fingerprint(
            fit_basis_fingerprint,
            "legacy_empty_surrender_compatibility_policy",
        ),
    )
    optimal_policy = replace(
        optimal_policy,
        surrender_policy=fitted_surrender_policy,
        provenance_fingerprint=assumption_fingerprint(
            fit_basis_fingerprint,
            "combined_income_election_and_monthly_income_action_policy",
        ),
    )
    diagnostics = tuple(sorted(
        (*income_action_fit.diagnostics, *election_diagnostics),
        key=lambda item: (
            item.decision_step, item.action_type, item.basis_level
        ),
    ))
    return OptimalBehaviourPolicyFit(
        policy=optimal_policy,
        cross_fitted_training_policy=cross_fitted_policy,
        diagnostics=diagnostics,
        training_scenario_fingerprint=training_scenarios.content_fingerprint,
        fit_basis_fingerprint=fit_basis_fingerprint,
        training_path_count=n_paths,
        training_policyholder_value_aud=selected_value,
        training_wait_policyholder_value_aud=wait_value,
        training_no_action_policyholder_value_aud=no_action_value,
        training_candidate_policyholder_value_aud=candidate_value,
        election_fallback_used=election_fallback,
        surrender_fallback_used=surrender_fallback,
        selected_fixed_election_step=selected_fixed_election_step,
        selected_income_action_mode=selected_income_action_mode,
        valid=not invalid_reasons,
        invalid_reasons=invalid_reasons,
        income_action_exposure_coverage=(
            income_action_fit.covered_exposure_fraction
        ),
        policy_iteration_count=income_action_fit.policy_iteration_count,
        policy_iteration_converged=(
            income_action_fit.policy_iteration_converged
        ),
        final_action_agreement=income_action_fit.final_action_agreement,
        final_policy_value_change_aud=(
            income_action_fit.final_value_change_aud
        ),
    )


def fit_optimal_behaviour_policy(
    product: IndexLinkedLifetimeIncomeProduct,
    policy: PolicySpec,
    training_scenarios: ScenarioSet,
    mortality: MortalityTable,
    *,
    expenses: Optional[ExpenseAssumptions] = None,
    projection_config: ProjectionConfig = ProjectionConfig(record_paths=False),
    settings: OptimalBehaviourLSMCSettings = OptimalBehaviourLSMCSettings(),
    fit_basis_inputs: Optional[Mapping[str, object]] = None,
) -> OptimalBehaviourPolicyFit:
    """Fit the ordered annual Growth-then-Income stopping policy.

    This is analogous to a two-right swing recursion only at the Bellman level:
    compare value without action with immediate action value plus the value in
    the next regime.  The state dimension here is the irreversible contractual
    phase, not a count of interchangeable rights.  Income/Lapse is solved first;
    Growth/Election is solved second using that frozen downstream policy.
    """
    if not isinstance(settings, OptimalBehaviourLSMCSettings):
        raise TypeError("settings must be OptimalBehaviourLSMCSettings.")
    if tuple(settings.ridge_grid) != RIDGE_GRID_DEFAULT:
        raise ValueError(
            "Annual optimal-behaviour LSMC requires the fixed Ridge grid "
            f"{RIDGE_GRID_DEFAULT}; got {tuple(settings.ridge_grid)}."
        )
    if settings.exercise_buffer_rmse_multiplier != 0.0:
        raise ValueError(
            "Time-zero Swing LSMC requires a zero RMSE exercise buffer."
        )
    if settings.fallback_to_no_action_if_training_underperforms:
        raise ValueError(
            "Time-zero Swing LSMC does not permit a statistical policy "
            "fallback."
        )
    policy.validate_against(product)
    if policy.age_pension_plus:
        raise NotImplementedError("Generic optimal behaviour does not support APS.")
    if product.allows_growth_surrender or product.allows_growth_withdrawals:
        raise ValueError(
            "Annual optimal behaviour requires the generic product's Growth "
            "withdrawal and surrender gates."
        )

    # Policyholder optimisation is conditional on the covered life being
    # alive.  Mortality remains in the later actuarial rollout, but it must not
    # terminate or probability-weight LSMC training paths.  Normalising the
    # now-unused mortality seed also makes the fit invariant to an irrelevant
    # random stream.
    training_mortality = mortality_free_policyholder_basis(mortality)
    config = replace(
        projection_config,
        record_paths=False,
        heston_cos=False,
        mortality_seed=0,
    )
    behaviour = no_voluntary_action_behaviour()
    premium = float(policy.net_initial_investment)
    n_paths = training_scenarios.n_paths
    n_steps = training_scenarios.n_steps
    minimum_step = int(product.min_years_before_income) * STEPS_PER_YEAR
    forced_step = _contractual_forced_election_step(product, policy)
    if minimum_step <= 0 or minimum_step % STEPS_PER_YEAR:
        raise ValueError("Income-Election minimum must be a positive whole year.")
    if forced_step > n_steps:
        raise ValueError(
            "Training horizon must reach the contractual forced Election anniversary."
        )
    election_steps = tuple(range(
        minimum_step, forced_step + 1, STEPS_PER_YEAR
    ))
    if not election_steps or election_steps[-1] != forced_step:
        raise ValueError("Contractual Election grid is inconsistent.")

    rng = np.random.default_rng(settings.fold_seed)
    complete_path_ids = np.arange(n_paths, dtype=np.int64)
    rng.shuffle(complete_path_ids)
    fold_labels = complete_path_ids % settings.n_folds
    assigned_start_steps = np.empty(n_paths, dtype=np.int64)
    for fold in range(settings.n_folds):
        fold_paths = np.flatnonzero(fold_labels == fold)
        rng.shuffle(fold_paths)
        assigned_start_steps[fold_paths] = np.asarray([
            election_steps[index % len(election_steps)]
            for index in range(fold_paths.size)
        ], dtype=np.int64)

    # Stage 1: cover Income states from all material START dates, then solve
    # CONTINUE_FOR_ONE_YEAR versus FULL_WITHDRAWAL_NOW backwards.  The recorder
    # is anniversary-only, so no under-year state can become a regression row.
    assigned_continue_projection, assigned_recorder = (
        _project_assigned_election_annual_branch(
            assigned_start_steps=assigned_start_steps,
            product=product,
            policy=policy,
            scenarios=training_scenarios,
            behaviour=behaviour,
            mortality=training_mortality,
            expenses=expenses,
            config=config,
        )
    )
    income_fit_failure: Optional[str] = None
    income_fit = _fit_surrender_phase_from_projection(
        projection=assigned_continue_projection,
        contexts=assigned_recorder.surrender_contexts,
        scenarios=training_scenarios,
        premium=premium,
        settings=settings,
        base_fold_ids=complete_path_ids,
    )
    if income_fit.fallback_used:
        raise RuntimeError(
            "Time-zero Swing LSMC may not replace the fitted Income rule "
            "with a Continue fallback."
        )
    cross_income_policy: Optional[CrossFittedOptimalSurrenderPolicy] = (
        income_fit.cross_fitted_policy
    )

    # The forced-START rollout is both the Growth Bellman branch and a check
    # that the cross-fitted Income policy covers states used outside its
    # randomized assigned-START panel.  Perform it before fitting the START
    # surface so any material coverage failure aborts the fit instead of
    # changing the customer's behavioural policy.
    branch_projection, election_recorder = _project_fixed_election_branch(
        start_step=forced_step,
        product=product,
        policy=policy,
        scenarios=training_scenarios,
        behaviour=behaviour,
        mortality=training_mortality,
        expenses=expenses,
        config=config,
        surrender_policy=cross_income_policy,
    )

    assigned_policy_projection, assigned_policy_recorder = (
        _project_assigned_election_annual_branch(
            assigned_start_steps=assigned_start_steps,
            product=product,
            policy=policy,
            scenarios=training_scenarios,
            behaviour=behaviour,
            mortality=training_mortality,
            expenses=expenses,
            config=config,
            surrender_policy=cross_income_policy,
        )
    )

    # The pooled START surface uses realised cashflows from the fold-pure annual
    # Income rollout.  Every counterfactual row retains its complete-path fold.
    start_surface_failure: Optional[str] = None
    start_value_fold_regressions: tuple[_ContinuationRegression, ...] = ()
    try:
        start_value_raw, start_value_target, start_value_path_ids = (
            _assigned_start_value_training_panel(
                projection=assigned_policy_projection,
                election_contexts=assigned_policy_recorder.election_contexts,
                assigned_start_steps=assigned_start_steps,
                election_steps=election_steps,
                scenarios=training_scenarios,
                premium=premium,
                issue_age=float(policy.age),
                automatic_income_start_age=float(
                    product.automatic_income_start_age
                ),
                settings=settings,
                complete_path_ids=complete_path_ids,
            )
        )
        (
            _start_value_regression,
            _start_value_oof,
            _start_value_folds_used,
            start_value_fold_regressions,
        ) = _cross_fitted_state_value_regression(
            start_value_raw,
            start_value_target,
            premium,
            settings,
            start_value_path_ids,
            core_feature_indices=START_VALUE_CORE_FEATURE_INDICES,
            enforce_unique_path_minimum=True,
        )
        start_value_fold_regressions = tuple(
            replace(
                regression,
                basis_level=f"pooled_annual_start/{regression.basis_level}",
            )
            for regression in start_value_fold_regressions
        )
    except (ValueError, np.linalg.LinAlgError) as exc:
        start_surface_failure = f"annual_start_surface_failed:{exc}"

    # The prevalidated forced-START branch supplies exact WAIT cashflows and
    # annual Growth contexts.  Annual lapse is represented only through the
    # Projector's surrender hook used above.
    _assert_no_optimal_partial_withdrawals(
        branch_projection, context="Annual Growth Bellman branch"
    )
    growth_discounted_cashflow = _discounted_policyholder_cashflows(
        branch_projection, training_scenarios
    )
    if branch_projection.phase_cashflows is None:
        raise RuntimeError("Annual Election fit requires phase cashflow ledgers.")
    objective_discount = _time_zero_curve_discount_factors(
        training_scenarios, len(branch_projection.times)
    )
    growth_pre_election_benefit_0 = (
        branch_projection.phase_cashflows["policyholder_benefits_pre_election"]
        * objective_discount[:, :len(branch_projection.times)]
    )
    forced_post_election_current_0 = (
        branch_projection.phase_cashflows[
            "policyholder_benefits_post_election"
        ][:, forced_step]
        * objective_discount[:, forced_step]
    )
    forced_start_value_0 = (
        forced_post_election_current_0
        + np.sum(growth_discounted_cashflow[:, forced_step + 1:], axis=1)
    )
    wait_path_value_0 = np.sum(growth_discounted_cashflow, axis=1)
    growth_contexts = dict(election_recorder.election_contexts)

    election_regressions: dict[int, _ElectionRegressionPair] = {}
    election_fold_regressions: dict[
        int, tuple[_ElectionRegressionPair, ...]
    ] = {}
    election_fold_ids: dict[int, NDArray[np.int64]] = {}
    election_diagnostics: list[OptimalBehaviourRegressionDiagnostic] = []
    election_panels: dict[
        int, tuple[Array, Array, Array, NDArray[np.int64]]
    ] = {}
    material_election_failures: list[str] = []
    if start_surface_failure is not None:
        material_election_failures.append(start_surface_failure)

    future_value_0 = forced_start_value_0.copy()
    next_step = forced_step
    if start_value_fold_regressions:
        for step in reversed(election_steps[:-1]):
            # WAIT carries every monthly cashflow to the next Anniversary.  At
            # that boundary the already-solved realised action value is used;
            # there is no pathwise maximum of future realised outcomes.
            future_value_0 += (
                np.sum(
                    growth_discounted_cashflow[:, step + 1:next_step], axis=1
                )
                + growth_pre_election_benefit_0[:, next_step]
            )
            wait_realised_0 = future_value_0.copy()
            start_realised_0 = np.zeros(n_paths)
            context = growth_contexts.get(step)
            if context is None:
                raise ValueError(
                    f"Projector did not expose Election context at step {step}."
                )
            scale_0 = objective_discount[:, step] * context.inforce_weight
            eligible = (
                context.voluntary_election_eligible
                & (context.phase == Phase.GROWTH.value)
                & (context.inforce_weight > settings.minimum_inforce_weight)
                & (scale_0 > 1.0e-300)
            )
            eligible_index = np.flatnonzero(eligible)
            observations = int(eligible_index.size)
            accepted = False
            fallback_reason: Optional[str] = None
            folds_used = 0
            wait_target = np.zeros(0)
            start_target = np.zeros(0)
            advantage_oof = np.zeros(0)
            pair: Optional[_ElectionRegressionPair] = None
            fold_pairs: tuple[_ElectionRegressionPair, ...] = ()
            panel_ids = complete_path_ids[eligible_index]
            if observations:
                wait_target = wait_realised_0[eligible] / scale_0[eligible]
                election_features = build_income_election_regression_features(
                    context,
                    premium,
                    policy.age,
                    product.automatic_income_start_age,
                )
                raw = election_features[eligible]
                start_raw = _build_income_start_value_features(
                    election_features
                )[eligible]
                start_target = _predict_fold_pure_regression(
                    start_raw, panel_ids, start_value_fold_regressions
                )
                start_realised_0[eligible_index] = (
                    scale_0[eligible_index] * start_target
                )
                election_panels[step] = (
                    raw, wait_target, start_target, panel_ids
                )
            minimum = _minimum_cross_fit_observations(settings, 1)
            if observations < minimum:
                fallback_reason = f"too_few_observations:{observations}<{minimum}"
            else:
                try:
                    pair, advantage_oof, folds_used, fold_pairs = (
                        _fit_election_regression_pair(
                            raw,
                            wait_target,
                            start_target,
                            premium=premium,
                            settings=settings,
                            fold_ids=panel_ids,
                        )
                    )
                    accepted = bool(
                        pair.stable(settings)
                        and all(item.stable(settings) for item in fold_pairs)
                    )
                    if not accepted:
                        fallback_reason = "election_regression_unstable"
                except (ValueError, np.linalg.LinAlgError) as exc:
                    fallback_reason = f"cross_fit_failed:{exc}"

            # Local annual pooling is the last action-regression fallback after
            # full/core/constant bases inside the cross-fitted Ridge/SVD fit.
            if not accepted and observations:
                neighbours = sorted(
                    (
                        (other_step, panel)
                        for other_step, panel in election_panels.items()
                        if other_step != step
                    ),
                    key=lambda item: abs(item[0] - step),
                )[:2]
                if neighbours:
                    pooled_raw = np.concatenate((
                        raw, *(panel[0] for _, panel in neighbours)
                    ))
                    pooled_wait = np.concatenate((
                        wait_target, *(panel[1] for _, panel in neighbours)
                    ))
                    pooled_start = np.concatenate((
                        start_target, *(panel[2] for _, panel in neighbours)
                    ))
                    pooled_ids = np.concatenate((
                        panel_ids, *(panel[3] for _, panel in neighbours)
                    ))
                    try:
                        pooled_pair, pooled_oof, folds_used, pooled_folds = (
                            _fit_election_regression_pair(
                                pooled_raw,
                                pooled_wait,
                                pooled_start,
                                premium=premium,
                                settings=settings,
                                fold_ids=pooled_ids,
                            )
                        )
                        basis = (
                            "pooled_election_years/"
                            f"{pooled_pair.advantage.basis_level}"
                        )
                        pair = _ElectionRegressionPair(advantage=replace(
                            pooled_pair.advantage, basis_level=basis
                        ))
                        fold_pairs = tuple(
                            _ElectionRegressionPair(advantage=replace(
                                item.advantage, basis_level=basis
                            ))
                            for item in pooled_folds
                        )
                        advantage_oof = pooled_oof[:observations]
                        accepted = bool(
                            pair.stable(settings)
                            and all(item.stable(settings) for item in fold_pairs)
                        )
                        fallback_reason = (
                            None if accepted else "pooled_election_unstable"
                        )
                    except (ValueError, np.linalg.LinAlgError) as exc:
                        fallback_reason = f"pooled_election_failed:{exc}"

            start_action = np.zeros(n_paths, dtype=bool)
            training_action_rate = 0.0
            if accepted and pair is not None:
                buffer = (
                    settings.exercise_tolerance_aud
                    + settings.exercise_buffer_rmse_multiplier
                    * pair.combined_oof_rmse_aud
                )
                selected = advantage_oof > buffer
                start_action[eligible_index] = selected
                training_action_rate = float(np.mean(selected))
                election_regressions[step] = pair
                election_fold_regressions[step] = fold_pairs
                election_fold_ids[step] = np.mod(
                    complete_path_ids, folds_used
                ).astype(np.int64)
            exposure = float(np.mean(np.where(
                eligible, context.inforce_weight, 0.0
            )))
            if not accepted and exposure > settings.immaterial_exposure_fraction:
                material_election_failures.append(
                    f"step={step},exposure={exposure:.12g},reason={fallback_reason}"
                )
            elif not accepted:
                fallback_reason = "immaterial_no_fit"
            future_value_0 = np.where(
                start_action, start_realised_0, wait_realised_0
            )
            election_diagnostics.append(OptimalBehaviourRegressionDiagnostic(
                action_type="income_election",
                phase="growth",
                policy_year=step // STEPS_PER_YEAR,
                decision_step=step,
                observations=observations,
                folds_used=folds_used,
                feature_count=0 if pair is None else pair.advantage.coefficients.size,
                matrix_rank=0 if pair is None else pair.advantage.matrix_rank,
                condition_number=None if pair is None else pair.advantage.condition_number,
                oof_rmse_aud=None if pair is None else pair.combined_oof_rmse_aud,
                oof_r_squared=(
                    None if pair is None
                    else _oof_r_squared(start_target - wait_target, advantage_oof)
                ),
                mean_wait_or_continue_value_aud=(
                    float(np.mean(wait_target)) if wait_target.size else 0.0
                ),
                mean_action_value_aud=(
                    float(np.mean(start_target)) if start_target.size else 0.0
                ),
                training_action_rate=training_action_rate,
                regression_accepted_for_action=accepted,
                fallback_reason=fallback_reason,
                wait_regression_rank=None if pair is None else pair.advantage.matrix_rank,
                wait_regression_condition_number=(
                    None if pair is None else pair.advantage.condition_number
                ),
                wait_regression_oof_rmse_aud=(
                    None if pair is None else pair.advantage.oof_rmse_aud
                ),
                action_regression_rank=None if pair is None else pair.advantage.matrix_rank,
                action_regression_condition_number=(
                    None if pair is None else pair.advantage.condition_number
                ),
                action_regression_oof_rmse_aud=(
                    None if pair is None else pair.advantage.oof_rmse_aud
                ),
                selected_ridge=None if pair is None else pair.advantage.selected_ridge,
                effective_rank=0 if pair is None else pair.advantage.effective_rank,
                basis_level="none" if pair is None else pair.advantage.basis_level,
                oof_policy_uplift_aud=(
                    None if pair is None else float(np.mean(np.where(
                        advantage_oof > (
                            settings.exercise_tolerance_aud
                            + settings.exercise_buffer_rmse_multiplier
                            * pair.advantage.oof_rmse_aud
                        ),
                        start_target - wait_target,
                        0.0,
                    )))
                ),
                relevant_exposure_fraction=exposure,
            ))
            next_step = step

    first_step = election_steps[0]
    bellman_candidate_path_value = (
        np.sum(growth_discounted_cashflow[:, :first_step + 1], axis=1)
        + future_value_0
    )
    wait_value = float(np.mean(wait_path_value_0))

    empty_surrender = OptimalSurrenderPolicy(regressions={}, settings=settings)
    empty_cross_surrender = CrossFittedOptimalSurrenderPolicy(
        regressions_by_step={}, fold_ids_by_step={}, settings=settings
    )
    dynamic_complete = not material_election_failures and income_fit_failure is None
    candidate_policy = OptimalBehaviourPolicy(
        election_regressions=MappingProxyType(dict(sorted(
            election_regressions.items()
        ))),
        surrender_policy=income_fit.policy,
        premium=premium,
        issue_age=float(policy.age),
        settings=settings,
        automatic_income_start_age=float(product.automatic_income_start_age),
        monthly_income_actions_required=False,
        valid=dynamic_complete,
        invalid_reasons=tuple((*material_election_failures,) + (
            () if income_fit_failure is None else (income_fit_failure,)
        )),
    )
    cross_candidate = CrossFittedOptimalBehaviourPolicy(
        election_regressions_by_step=MappingProxyType(dict(sorted(
            election_fold_regressions.items()
        ))),
        election_fold_ids_by_step=MappingProxyType(dict(sorted(
            election_fold_ids.items()
        ))),
        surrender_policy=(
            income_fit.cross_fitted_policy
            if not income_fit.fallback_used else empty_cross_surrender
        ),
        premium=premium,
        issue_age=float(policy.age),
        settings=settings,
        automatic_income_start_age=float(product.automatic_income_start_age),
        monthly_income_actions_required=False,
        valid=dynamic_complete,
        invalid_reasons=candidate_policy.invalid_reasons,
    )
    candidate_path_value = bellman_candidate_path_value
    if dynamic_complete:
        candidate_projection = project(
            product,
            policy,
            training_scenarios,
            behaviour,
            training_mortality,
            expenses=expenses,
            config=config,
            income_election_policy=cross_candidate,
            surrender_policy=cross_candidate,
        )
        _assert_no_optimal_partial_withdrawals(
            candidate_projection, context="Cross-fitted annual candidate"
        )
        candidate_path_value = np.sum(
            _discounted_policyholder_cashflows(
                candidate_projection, training_scenarios
            ),
            axis=1,
        )
    candidate_value = float(np.mean(candidate_path_value))

    # Retain fixed policies only as transparent in-sample comparators.  They do
    # not participate in deployment: the productive customer rule is the
    # direct Bellman argmax and a structurally incomplete fit is an error.
    def fixed_step(year: int) -> int:
        return min(forced_step, max(minimum_step, int(year) * STEPS_PER_YEAR))

    fixed_election_steps = tuple(dict.fromkeys((
        minimum_step,
        fixed_step(5),
        fixed_step(10),
        fixed_step(policy.effective_income_start_year(product)),
        forced_step,
    )))

    def path_values(result: ProjectionResult) -> Array:
        _assert_no_optimal_partial_withdrawals(
            result, context="Annual fixed-policy baseline"
        )
        return np.sum(
            _discounted_policyholder_cashflows(result, training_scenarios),
            axis=1,
        )

    # Fixed-START/Continue paths are a transparent reference for the customer
    # optionality uplift. They are not candidate deployment policies. Do not
    # roll the fitted surrender rule through fixed START dates that are outside
    # the cross-fitted V11 state distribution: doing so can manufacture sparse
    # far-tail coverage requirements which the deployed V11 never reaches.
    fixed_candidates: list[tuple[float, int, str, Array]] = []
    for anchor_step in fixed_election_steps:
        continue_projection, _ = _project_fixed_election_branch(
            start_step=anchor_step,
            product=product,
            policy=policy,
            scenarios=training_scenarios,
            behaviour=behaviour,
            mortality=training_mortality,
            expenses=expenses,
            config=config,
        )
        continue_paths = path_values(continue_projection)
        fixed_candidates.append((
            float(np.mean(continue_paths)), anchor_step, "continue", continue_paths
        ))
    best_fixed_value, best_fixed_step, best_fixed_mode, best_fixed_paths = max(
        fixed_candidates, key=lambda item: item[0]
    )
    no_action_value = max(
        value for value, _step, mode, _paths in fixed_candidates
        if mode == "continue"
    )

    if not dynamic_complete or not candidate_policy.valid:
        reasons = candidate_policy.invalid_reasons or (
            "unknown_structural_fit_failure",
        )
        raise RuntimeError(
            "Time-zero Swing LSMC could not fit every material decision "
            "surface; no behavioural fallback is permitted: "
            + "|".join(reasons)
        )
    use_fixed_fallback = False
    selected_policy = candidate_policy
    selected_cross_policy = cross_candidate
    selected_value = candidate_value
    selected_name = "V11"
    fallback_reason = None

    modelpoint_step = fixed_step(policy.effective_income_start_year(product))
    variants = {
        "V00": OptimalBehaviourPolicy(
            election_regressions=MappingProxyType({}),
            surrender_policy=empty_surrender,
            premium=premium,
            issue_age=float(policy.age),
            settings=settings,
            automatic_income_start_age=float(product.automatic_income_start_age),
            fixed_election_step=modelpoint_step,
            monthly_income_actions_required=False,
        ),
        "V01": OptimalBehaviourPolicy(
            election_regressions=MappingProxyType({}),
            surrender_policy=income_fit.policy,
            premium=premium,
            issue_age=float(policy.age),
            settings=settings,
            automatic_income_start_age=float(product.automatic_income_start_age),
            fixed_election_step=modelpoint_step,
            monthly_income_actions_required=False,
        ),
        # V10 uses only the fitted Election rule and always continues in the
        # Income phase. An unavailable Income regression therefore invalidates
        # V11, but must not invalidate this Election-only control.
        "V10": replace(
            candidate_policy,
            surrender_policy=empty_surrender,
            valid=not material_election_failures,
            invalid_reasons=tuple(material_election_failures),
        ),
        "V11": candidate_policy,
    }

    fit_basis_fingerprint = assumption_fingerprint(
        "time_zero_curve_swing_lsmc_v6",
        training_scenarios.content_fingerprint,
        product,
        policy,
        POLICYHOLDER_LSMC_MORTALITY_BASIS,
        POLICYHOLDER_LSMC_OBJECTIVE_DISCOUNT_BASIS,
        expenses,
        config,
        settings,
        fit_basis_inputs,
    )
    fitted_income_surrender = replace(
        income_fit.policy,
        provenance_fingerprint=assumption_fingerprint(
            fit_basis_fingerprint, "annual_income_lapse_policy"
        ),
    )
    fitted_continue_surrender = replace(
        empty_surrender,
        provenance_fingerprint=assumption_fingerprint(
            fit_basis_fingerprint, "annual_income_continue_policy"
        ),
    )
    candidate_policy = replace(
        candidate_policy,
        surrender_policy=fitted_income_surrender,
        provenance_fingerprint=assumption_fingerprint(
            fit_basis_fingerprint, "candidate_V11_annual_election_and_lapse"
        ),
    )
    selected_policy = replace(
        selected_policy,
        surrender_policy=(
            fitted_income_surrender
            if selected_policy.surrender_policy.regressions
            else fitted_continue_surrender
        ),
        provenance_fingerprint=assumption_fingerprint(
            fit_basis_fingerprint, f"selected_{selected_name}"
        ),
    )
    variants["V11"] = candidate_policy
    variants["V10"] = replace(
        variants["V10"],
        surrender_policy=fitted_continue_surrender,
        provenance_fingerprint=assumption_fingerprint(
            fit_basis_fingerprint, "candidate_V10_annual_election_continue"
        ),
    )
    variants["V00"] = replace(
        variants["V00"],
        surrender_policy=fitted_continue_surrender,
        provenance_fingerprint=assumption_fingerprint(
            fit_basis_fingerprint, "baseline_V00_fixed_election_continue"
        ),
    )
    variants["V01"] = replace(
        variants["V01"],
        surrender_policy=fitted_income_surrender,
        provenance_fingerprint=assumption_fingerprint(
            fit_basis_fingerprint, "candidate_V01_fixed_election_annual_lapse"
        ),
    )
    diagnostics = tuple(sorted(
        (*income_fit.diagnostics, *election_diagnostics),
        key=lambda item: (item.decision_step, item.action_type, item.basis_level),
    ))
    return OptimalBehaviourPolicyFit(
        policy=selected_policy,
        cross_fitted_training_policy=selected_cross_policy,
        diagnostics=diagnostics,
        training_scenario_fingerprint=training_scenarios.content_fingerprint,
        fit_basis_fingerprint=fit_basis_fingerprint,
        training_path_count=n_paths,
        training_policyholder_value_aud=float(selected_value),
        training_wait_policyholder_value_aud=wait_value,
        training_no_action_policyholder_value_aud=float(no_action_value),
        training_candidate_policyholder_value_aud=candidate_value,
        election_fallback_used=use_fixed_fallback,
        surrender_fallback_used=(
            income_fit.fallback_used
            or (use_fixed_fallback and best_fixed_mode == "continue")
        ),
        selected_fixed_election_step=(
            int(best_fixed_step) if use_fixed_fallback else None
        ),
        selected_income_action_mode=(
            best_fixed_mode if use_fixed_fallback else "annual_lapse"
        ),
        valid=True,
        invalid_reasons=(),
        income_action_exposure_coverage=1.0,
        policy_iteration_count=0,
        policy_iteration_converged=True,
        final_action_agreement=1.0,
        final_policy_value_change_aud=0.0,
        candidate_policy=candidate_policy,
        policy_variants=MappingProxyType(variants),
        selected_policy_name=selected_name,
        training_fallback_reason=fallback_reason,
    )


__all__ = [
    "CrossFittedOptimalBehaviourPolicy",
    "CrossFittedOptimalSurrenderPolicy",
    "ELECTION_FEATURE_NAMES",
    "FEATURE_NAMES",
    "INCOME_ACTION_FEATURE_NAMES",
    "PARTIAL_ACTION_FEATURE_NAMES",
    "POLICYHOLDER_LSMC_MORTALITY_BASIS",
    "POLICYHOLDER_LSMC_OBJECTIVE_DISCOUNT_BASIS",
    "IncomeActionAdvantagePolicyFit",
    "IncomeActionRegressionSet",
    "LSMCRegressionDiagnostic",
    "OptimalBehaviourPolicy",
    "OptimalBehaviourPolicyFit",
    "OptimalBehaviourRegressionDiagnostic",
    "OptimalBehaviourLSMCFit",
    "OptimalBehaviourLSMCSettings",
    "OptimalSurrenderPolicy",
    "SurrenderContinuationPolicyFit",
    "SurrenderContinuationRegressionDiagnostic",
    "build_income_election_regression_features",
    "build_income_action_regression_features",
    "build_partial_action_regression_features",
    "build_surrender_regression_features",
    "build_surrender_regression_features_from_arrays",
    "fit_optimal_behaviour_policy",
    "fit_optimal_surrender_policy",
    "fit_income_action_advantage_policy",
    "fit_surrender_continuation_regression",
    "fit_surrender_continuation_policy",
    "mortality_free_policyholder_basis",
    "no_voluntary_action_behaviour",
]
