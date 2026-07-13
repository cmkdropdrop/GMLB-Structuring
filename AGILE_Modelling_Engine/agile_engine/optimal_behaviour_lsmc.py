"""LSMC optimal Full-Withdrawal policy for the generic lifetime-income product.

This module is intentionally separate from the archived legacy implementation
in :mod:`agile_engine.lsmc`.  Training cashflows and the final out-of-sample
rollout both use the current monthly projector, including the generic 50/50
Reference Fund, daily fee subledger, monthly income, mortality, MVA, expenses,
hedge costs and crediting margin.

Scope
-----
The operational portfolio has a deterministic model-point Income Election.
The only statistical actions that remain effective are Income-phase Full
Withdrawal and proportional Excess Withdrawal.  For the generic product an
admissible partial withdrawal reduces Account Value and Locked Income by the
same proportion.  Its policyholder value is therefore a convex combination of
Continue and Full Withdrawal (there are no APS mechanics or fixed customer
cashflows).  It cannot improve on both endpoints, so the optimal action set is
reduced without loss to ``CONTINUE | FULL_WITHDRAWAL``.  Growth surrender and
all Growth withdrawals remain contractually prohibited.
"""

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
from .projection import (IncomeElectionDecisionContext, ProjectionConfig,
                         ProjectionResult, SurrenderDecisionContext, project)


Array = NDArray[np.float64]
FEATURE_NAMES = (
    "account_value",
    "account_value_sq",
    "account_value_cu",
    "surrender_value",
    "surrender_value_sq",
    "annual_income",
    "annual_income_sq",
    "guarantee_pv",
    "guarantee_pv_sq",
    "guarantee_log_moneyness",
    "short_rate",
    "short_rate_sq",
    "zero_rate_5y",
    "five_year_rate_slope",
    "global_equity_variance",
    "global_equity_variance_sq",
    "duration_years",
    "announced_cap",
    "previous_reference_return",
    "previous_credited_return",
    "performance_gap",
    "account_value_x_income",
    "account_value_x_guarantee_pv",
    "surrender_value_x_guarantee_pv",
    "account_value_x_short_rate",
    "annual_income_x_short_rate",
    "guarantee_moneyness_x_short_rate",
    "announced_cap_x_account_value",
    "performance_gap_x_guarantee_moneyness",
)


@dataclass(frozen=True)
class OptimalBehaviourLSMCSettings:
    """Numerical settings for the backward LSMC fit."""

    ridge: float = 1.0e-6
    n_folds: int = 5
    fold_seed: int = 9137
    exercise_tolerance_aud: float = 1.0e-8
    exercise_buffer_rmse_multiplier: float = 0.25
    minimum_inforce_weight: float = 1.0e-10
    maximum_condition_number: float = 1.0e10
    fallback_to_no_action_if_training_underperforms: bool = True

    def __post_init__(self) -> None:
        numeric = np.asarray([
            self.ridge,
            self.exercise_tolerance_aud,
            self.exercise_buffer_rmse_multiplier,
            self.minimum_inforce_weight,
            self.maximum_condition_number,
        ], dtype=float)
        if not np.all(np.isfinite(numeric)) or np.any(numeric < 0.0):
            raise ValueError("LSMC numeric controls must be finite and non-negative.")
        if self.maximum_condition_number <= 1.0:
            raise ValueError("maximum_condition_number must exceed one.")
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


@dataclass(frozen=True)
class LSMCRegressionDiagnostic:
    policy_year: int
    decision_step: int
    observations: int
    folds_used: int
    feature_count: int
    matrix_rank: int
    condition_number: float
    oof_rmse_aud: float
    oof_r_squared: float
    mean_immediate_value_aud: float
    mean_continuation_target_aud: float
    training_exercise_rate: float
    regression_accepted_for_exercise: bool

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
) -> Array:
    """Build the canonical 29 policyholder features from compact arrays.

    Each input may be a scalar or a one-dimensional observation array.  The
    inputs are broadcast to one common path/row axis and the result has shape
    ``(n_observations, len(FEATURE_NAMES))``.  This is the array-native entry
    point for fitted-control algorithms: they can retain compact annual state
    tensors instead of thousands of :class:`SurrenderDecisionContext` objects.

    The feature definition is deliberately identical to
    :func:`build_surrender_regression_features`.  No future return, discount,
    hedge result or backing-asset input is accepted by this API.
    """
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
        "previous_credited_return": previous_credited_return,
        "performance_gap": performance_gap,
        "premium": premium,
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
    s = np.maximum(data["surrender_value"], 0.0) / premium_array
    y = np.maximum(data["locked_annual_income"], 0.0) / premium_array
    g = np.maximum(data["guarantee_pv"], 0.0) / premium_array
    m = data["guarantee_log_moneyness"]
    r = data["short_rate"]
    z5 = data["zero_rate_5y"]
    v = np.maximum(data["heston_variance"], 0.0)
    duration = data["duration_years"] / 100.0
    # ``+inf`` is the explicit uncapped benchmark.  Regression design matrices
    # must remain finite, so encode that special state as a documented 100%
    # annual cap sentinel, safely above the admissible 0.25%-20% control grid.
    cap = np.where(np.isposinf(cap_input), 1.0, cap_input)
    reference_return = data["previous_reference_return"]
    credited_return = data["previous_credited_return"]
    gap = np.maximum(data["performance_gap"], 0.0)

    out = np.column_stack((
        x,
        x * x,
        x * x * x,
        s,
        s * s,
        y,
        y * y,
        g,
        g * g,
        m,
        r,
        r * r,
        z5,
        z5 - r,
        v,
        v * v,
        duration,
        cap,
        reference_return,
        credited_return,
        gap,
        x * y,
        x * g,
        s * g,
        x * r,
        y * r,
        m * r,
        cap * x,
        gap * m,
    ))
    if out.shape[1] != len(FEATURE_NAMES):
        raise RuntimeError("LSMC feature names and feature matrix are inconsistent.")
    if not np.all(np.isfinite(out)):
        raise ValueError("Non-finite LSMC state feature encountered.")
    return np.asarray(out, dtype=float)


@dataclass(frozen=True)
class _ContinuationRegression:
    premium: float
    active_feature_indices: NDArray[np.int64]
    orthogonal_components: Array
    centre: Array
    scale: Array
    coefficients: Array
    condition_number: float
    matrix_rank: int
    oof_rmse_aud: float

    def predict_features(self, raw_features: Array) -> Array:
        """Evaluate the frozen continuation model on canonical 29-feature rows."""
        raw = np.asarray(raw_features, dtype=float)
        if raw.ndim != 2 or raw.shape[1] != len(FEATURE_NAMES):
            raise ValueError(
                f"Surrender features must have shape (n, {len(FEATURE_NAMES)})."
            )
        if not np.all(np.isfinite(raw)):
            raise ValueError("Surrender features must be finite.")
        design = np.column_stack((
            np.ones(raw.shape[0]),
            ((
                raw[:, self.active_feature_indices] - self.centre
            ) / self.scale) @ self.orthogonal_components.T,
        ))
        return np.maximum(design @ self.coefficients * self.premium, 0.0)

    def predict(self, context: SurrenderDecisionContext) -> Array:
        raw = build_surrender_regression_features(context, self.premium)
        return self.predict_features(raw)


@dataclass
class OptimalSurrenderPolicy:
    """Frozen continuation regressions used by the monthly projector."""

    regressions: Mapping[int, _ContinuationRegression]
    settings: OptimalBehaviourLSMCSettings
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
        if not context.is_anniversary or step not in self.regressions:
            return np.zeros(n_paths, dtype=bool)
        eligible = (
            context.full_withdrawal_eligible
            & (context.phase == Phase.INCOME.value)
            & (context.inforce_weight > self.settings.minimum_inforce_weight)
        )
        if not np.any(eligible):
            return np.zeros(n_paths, dtype=bool)
        continuation = self.regressions[step].predict(context)
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
        exercise = eligible & (
            context.surrender_value > continuation + buffer
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
    anniversary_only: bool = field(default=True, init=False, repr=False)

    def surrender_mask(
        self,
        *,
        context: SurrenderDecisionContext,
    ) -> NDArray[np.bool_]:
        if not isinstance(context, SurrenderDecisionContext):
            raise TypeError("Cross-fitted surrender requires decision context.")
        step = int(context.step)
        if not context.is_anniversary or step not in self.regressions_by_step:
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
        continuation = np.zeros(context.n_paths)
        stable = np.ones(context.n_paths, dtype=bool)
        buffer = np.full(
            context.n_paths, self.settings.exercise_tolerance_aud, dtype=float
        )
        regressions = self.regressions_by_step[step]
        for fold, regression in enumerate(regressions):
            selected = fold_ids == fold
            if not np.any(selected):
                continue
            prediction = regression.predict(context)
            continuation[selected] = prediction[selected]
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
        return eligible & stable & (
            context.surrender_value > continuation + buffer
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
    """Keep deterministic Election but remove all statistical voluntary actions."""
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


def _fit_regression(
    raw_features: Array,
    target_aud: Array,
    premium: float,
    ridge: float,
    *,
    oof_rmse_aud: float = 0.0,
) -> _ContinuationRegression:
    full_centre = np.mean(raw_features, axis=0)
    full_scale = np.std(raw_features, axis=0)
    active = np.flatnonzero(full_scale > 1.0e-10).astype(np.int64)
    centre = full_centre[active]
    scale = full_scale[active]
    standardised = (raw_features[:, active] - centre) / scale
    if active.size:
        _left, singular, right = np.linalg.svd(
            standardised, full_matrices=False)
        threshold = max(standardised.shape) * np.finfo(float).eps * singular[0]
        components = right[singular > threshold]
    else:
        components = np.zeros((0, 0))
    design = np.column_stack((
        np.ones(raw_features.shape[0]),
        standardised @ components.T,
    ))
    target = np.asarray(target_aud, dtype=float) / premium
    penalty = np.eye(design.shape[1])
    penalty[0, 0] = 0.0
    normal = design.T @ design + ridge * penalty
    rhs = design.T @ target
    try:
        coefficients = np.linalg.solve(normal, rhs)
    except np.linalg.LinAlgError:
        coefficients = np.linalg.lstsq(normal, rhs, rcond=None)[0]
    if not np.all(np.isfinite(coefficients)):
        raise ValueError("LSMC regression produced non-finite coefficients.")
    return _ContinuationRegression(
        premium=float(premium),
        active_feature_indices=active,
        orthogonal_components=np.asarray(components, dtype=float),
        centre=np.asarray(centre, dtype=float),
        scale=np.asarray(scale, dtype=float),
        coefficients=np.asarray(coefficients, dtype=float),
        condition_number=float(np.linalg.cond(normal)),
        matrix_rank=int(np.linalg.matrix_rank(design)),
        oof_rmse_aud=float(oof_rmse_aud),
    )


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
    )


def _cross_fitted_regression(
    raw_features: Array,
    target_aud: Array,
    premium: float,
    settings: OptimalBehaviourLSMCSettings,
    fold_ids: NDArray[np.int64],
) -> tuple[
    _ContinuationRegression,
    Array,
    int,
    tuple[_ContinuationRegression, ...],
]:
    n_obs = raw_features.shape[0]
    feature_count = raw_features.shape[1] + 1
    if n_obs < 2 * feature_count:
        raise ValueError(
            "LSMC requires at least twice as many eligible paths as regression "
            f"features; got {n_obs} paths and {feature_count} features."
        )
    folds_used = min(settings.n_folds, max(2, n_obs // feature_count))
    effective_folds = np.mod(fold_ids[:n_obs], folds_used)
    oof = np.zeros(n_obs)
    fold_regressions: list[_ContinuationRegression] = []
    for fold in range(folds_used):
        test = effective_folds == fold
        train = ~test
        if not np.any(test) or np.count_nonzero(train) < feature_count:
            raise ValueError("Insufficient observations in an LSMC cross-fit fold.")
        regression = _fit_regression(
            raw_features[train], target_aud[train], premium, settings.ridge)
        fold_regressions.append(regression)
        # Use the training-fold standardisation for the held-out prediction.
        held_out = np.column_stack((
            np.ones(np.count_nonzero(test)),
            ((
                raw_features[test][:, regression.active_feature_indices]
                - regression.centre
            ) / regression.scale) @ regression.orthogonal_components.T,
        ))
        oof[test] = np.maximum(
            held_out @ regression.coefficients * premium, 0.0)
    rmse = float(np.sqrt(np.mean((oof - target_aud) ** 2)))
    full = _fit_regression(
        raw_features,
        target_aud,
        premium,
        settings.ridge,
        oof_rmse_aud=rmse,
    )
    fold_regressions = [
        replace(regression, oof_rmse_aud=rmse)
        for regression in fold_regressions
    ]
    return full, oof, folds_used, tuple(fold_regressions)


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

    ``features_by_step[step]`` must have shape ``(n_paths, 29)`` and the target
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
    minimum_observations = 2 * raw_feature_count
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
        ))
        if accepted:
            regressions[step] = regression
            oof_by_step[step] = oof

    policy = OptimalSurrenderPolicy(
        regressions=MappingProxyType(dict(sorted(regressions.items()))),
        settings=settings,
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

    Cross-fitted predictions drive the backward training recursion.  The final
    regression at each anniversary is then frozen and evaluated only on a
    separate scenario set by the portfolio runner.
    """
    policy.validate_against(product)
    if policy.age_pension_plus:
        raise NotImplementedError("Generic optimal behaviour does not support APS.")
    if product.allows_growth_surrender or product.allows_growth_withdrawals:
        raise ValueError("The generic LSMC implementation requires Growth action gates.")
    config = replace(projection_config, record_paths=True, heston_cos=False)
    behaviour = no_voluntary_action_behaviour()
    context_recorder = _SurrenderContextRecorder()
    projection = project(
        product,
        policy,
        training_scenarios,
        behaviour,
        mortality,
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

    policyholder_cashflow = sum(
        projection.cashflows[name]
        for name in (
            "income_paid",
            "death_benefits",
            "surrender_benefits",
            "partial_withdrawals",
            "terminal_closeout",
        )
    )
    discount = training_scenarios.discount[:, :n_steps + 1]
    discounted_cashflow = policyholder_cashflow * discount
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
        if eligible_index.size < 2 * (len(FEATURE_NAMES) + 1):
            # At the hard terminal-age tail there is no material in-force
            # cohort left to fit.  Continuing to the terminal closeout is the
            # conservative admissible action.
            if position > 0:
                previous = decision_steps[position - 1]
                future_value_0 += np.sum(
                    discounted_cashflow[:, previous + 1:step + 1], axis=1)
            continue

        continuation_target = future_value_0[eligible] / scale_0[eligible]
        raw = build_surrender_regression_features(context, premium)[eligible]
        fold_ids = base_fold_ids[eligible_index]
        (
            regression,
            oof_continuation,
            folds_used,
            fold_regressions,
        ) = _cross_fitted_regression(
            raw,
            continuation_target,
            premium,
            settings,
            fold_ids,
        )
        immediate_all = context.surrender_value
        immediate = immediate_all[eligible]
        buffer = (
            settings.exercise_tolerance_aud
            + settings.exercise_buffer_rmse_multiplier
            * regression.oof_rmse_aud
        )
        exercise_eligible = (
            context.full_withdrawal_eligible[eligible]
            & (immediate > oof_continuation + buffer)
        )
        regression_stable = (
            regression.matrix_rank == regression.coefficients.size
            and regression.condition_number <= settings.maximum_condition_number
        )
        exercise_eligible &= regression_stable
        exercise = np.zeros(training_scenarios.n_paths, dtype=bool)
        exercise[eligible_index] = exercise_eligible
        future_value_0 = np.where(
            exercise,
            scale_0 * immediate_all,
            future_value_0,
        )
        residual = continuation_target - oof_continuation
        total_ss = float(np.sum(
            (continuation_target - np.mean(continuation_target)) ** 2))
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
    optimal_policy = OptimalSurrenderPolicy(
        regressions=selected_regressions,
        settings=settings,
    )
    cross_fitted_training_policy = CrossFittedOptimalSurrenderPolicy(
        regressions_by_step=selected_cross_fitted_regressions,
        fold_ids_by_step=selected_cross_fitted_fold_ids,
        settings=settings,
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
    "account_value",
    "account_value_sq",
    "account_value_cu",
    "prospective_annual_income",
    "prospective_annual_income_sq",
    "prospective_guarantee_pv",
    "prospective_guarantee_pv_sq",
    "guarantee_log_moneyness",
    "short_rate",
    "short_rate_sq",
    "zero_rate_5y",
    "five_year_rate_slope",
    "global_equity_variance",
    "global_equity_variance_sq",
    "duration_years",
    "attained_age",
    "previous_cap",
    "previous_reference_return",
    "previous_credited_return",
    "performance_gap",
    "account_value_x_income",
    "account_value_x_guarantee_pv",
    "income_x_guarantee_pv",
    "account_value_x_short_rate",
    "income_x_short_rate",
    "guarantee_moneyness_x_short_rate",
    "previous_cap_x_account_value",
    "performance_gap_x_guarantee_moneyness",
    "prospective_income_rate",
)


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

    def as_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


def build_income_election_regression_features(
    context: IncomeElectionDecisionContext,
    premium: float,
    issue_age: float,
) -> Array:
    """Build adapted Growth-state features without accepting future inputs."""
    if not isinstance(context, IncomeElectionDecisionContext):
        raise TypeError(
            "Income-Election LSMC features require IncomeElectionDecisionContext."
        )
    premium_value = float(premium)
    issue_age_value = float(issue_age)
    if not np.isfinite(premium_value) or premium_value <= 0.0:
        raise ValueError("Income-Election feature premium must be positive and finite.")
    if not np.isfinite(issue_age_value) or issue_age_value < 0.0:
        raise ValueError("Income-Election issue age must be finite and non-negative.")

    x = np.maximum(context.account_value, 0.0) / premium_value
    y = np.maximum(
        context.prospective_locked_annual_income, 0.0
    ) / premium_value
    g = np.maximum(context.guarantee_pv, 0.0) / premium_value
    m = np.asarray(context.guarantee_log_moneyness, dtype=float)
    r = np.asarray(context.short_rate, dtype=float)
    z5 = np.asarray(context.zero_rate_5y, dtype=float)
    v = np.maximum(context.heston_variance, 0.0)
    duration = np.full(context.n_paths, context.duration_years / 100.0)
    attained_age = np.full(
        context.n_paths, (issue_age_value + context.duration_years) / 100.0
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
    previous_credit = np.asarray(
        context.previous_credited_return, dtype=float
    )
    gap = np.maximum(context.performance_gap, 0.0)
    rate = np.asarray(context.prospective_income_rate, dtype=float)

    out = np.column_stack((
        x,
        x * x,
        x * x * x,
        y,
        y * y,
        g,
        g * g,
        m,
        r,
        r * r,
        z5,
        z5 - r,
        v,
        v * v,
        duration,
        attained_age,
        previous_cap,
        previous_reference,
        previous_credit,
        gap,
        x * y,
        x * g,
        y * g,
        x * r,
        y * r,
        m * r,
        previous_cap * x,
        gap * m,
        rate,
    ))
    if out.shape != (context.n_paths, len(ELECTION_FEATURE_NAMES)):
        raise RuntimeError("Income-Election feature matrix is inconsistent.")
    if not np.all(np.isfinite(out)):
        raise ValueError("Non-finite Income-Election LSMC feature encountered.")
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
    wait: _ContinuationRegression
    start: _ContinuationRegression

    @property
    def combined_oof_rmse_aud(self) -> float:
        return float(np.hypot(
            self.wait.oof_rmse_aud,
            self.start.oof_rmse_aud,
        ))

    def stable(self, settings: OptimalBehaviourLSMCSettings) -> bool:
        return (
            _regression_is_stable(self.wait, settings)
            and _regression_is_stable(self.start, settings)
        )

    def predict(
        self,
        context: IncomeElectionDecisionContext,
        premium: float,
        issue_age: float,
    ) -> tuple[Array, Array]:
        raw = build_income_election_regression_features(
            context, premium, issue_age
        )
        return (
            self.wait.predict_features(raw),
            self.start.predict_features(raw),
        )


@dataclass
class OptimalBehaviourPolicy:
    """Frozen phase-aware Policyholder rule used only out of sample."""

    election_regressions: Mapping[int, _ElectionRegressionPair]
    surrender_policy: OptimalSurrenderPolicy
    premium: float
    issue_age: float
    settings: OptimalBehaviourLSMCSettings
    evaluation_statistics: dict[
        tuple[str, int], dict[str, int]
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
        step = int(context.step)
        voluntary_eligible = (
            context.voluntary_election_eligible
            & (context.phase == Phase.GROWTH.value)
            & (context.inforce_weight > self.settings.minimum_inforce_weight)
        )
        forced = np.asarray(context.forced_election, dtype=bool)
        action = np.zeros(context.n_paths, dtype=bool)
        regression = self.election_regressions.get(step)
        if regression is not None and regression.stable(self.settings) \
                and np.any(voluntary_eligible):
            wait_value, start_value = regression.predict(
                context, self.premium, self.issue_age
            )
            buffer = (
                self.settings.exercise_tolerance_aud
                + self.settings.exercise_buffer_rmse_multiplier
                * regression.combined_oof_rmse_aud
            )
            action = voluntary_eligible & (
                start_value > wait_value + buffer
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

    def surrender_mask(
        self,
        *,
        context: SurrenderDecisionContext,
    ) -> NDArray[np.bool_]:
        if not isinstance(context, SurrenderDecisionContext):
            raise TypeError("Optimal surrender requires SurrenderDecisionContext.")
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
    """Training-only combined policy; every complete path stays out of fold."""

    election_regressions_by_step: Mapping[
        int, tuple[_ElectionRegressionPair, ...]
    ]
    election_fold_ids_by_step: Mapping[int, NDArray[np.int64]]
    surrender_policy: CrossFittedOptimalSurrenderPolicy
    premium: float
    issue_age: float
    settings: OptimalBehaviourLSMCSettings
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
        step = int(context.step)
        pairs = self.election_regressions_by_step.get(step)
        if pairs is None:
            return np.zeros(context.n_paths, dtype=bool)
        fold_ids = np.asarray(
            self.election_fold_ids_by_step[step], dtype=np.int64
        )
        if fold_ids.shape != (context.n_paths,):
            raise ValueError(
                "Cross-fitted Election policy requires its original path sample."
            )
        raw = build_income_election_regression_features(
            context, self.premium, self.issue_age
        )
        wait_value = np.zeros(context.n_paths)
        start_value = np.zeros(context.n_paths)
        stable = np.zeros(context.n_paths, dtype=bool)
        buffer = np.full(
            context.n_paths, self.settings.exercise_tolerance_aud
        )
        for fold, pair in enumerate(pairs):
            selected = fold_ids == fold
            if not np.any(selected):
                continue
            wait_prediction = pair.wait.predict_features(raw)
            start_prediction = pair.start.predict_features(raw)
            wait_value[selected] = wait_prediction[selected]
            start_value[selected] = start_prediction[selected]
            stable[selected] = pair.stable(self.settings)
            buffer[selected] += (
                self.settings.exercise_buffer_rmse_multiplier
                * pair.combined_oof_rmse_aud
            )
        eligible = (
            context.voluntary_election_eligible
            & (context.phase == Phase.GROWTH.value)
            & (context.inforce_weight > self.settings.minimum_inforce_weight)
        )
        return eligible & stable & (start_value > wait_value + buffer)

    def surrender_mask(
        self,
        *,
        context: SurrenderDecisionContext,
    ) -> NDArray[np.bool_]:
        return self.surrender_policy.surrender_mask(context=context)


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

    @property
    def training_optionality_uplift_aud(self) -> float:
        return (
            self.training_policyholder_value_aud
            - self.training_no_action_policyholder_value_aud
        )

    @property
    def training_fallback_used(self) -> bool:
        return self.election_fallback_used or self.surrender_fallback_used


__all__ = [
    "CrossFittedOptimalSurrenderPolicy",
    "FEATURE_NAMES",
    "LSMCRegressionDiagnostic",
    "OptimalBehaviourLSMCFit",
    "OptimalBehaviourLSMCSettings",
    "OptimalSurrenderPolicy",
    "SurrenderContinuationPolicyFit",
    "SurrenderContinuationRegressionDiagnostic",
    "build_surrender_regression_features",
    "build_surrender_regression_features_from_arrays",
    "fit_optimal_surrender_policy",
    "fit_surrender_continuation_regression",
    "fit_surrender_continuation_policy",
    "no_voluntary_action_behaviour",
]
