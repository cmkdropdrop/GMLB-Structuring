"""Reusable annual forward-start call-spread pricing on cached Q paths.

The annual payoff for cap ``c`` is ``min(max(R, 0), c)`` on the complete,
monthly rebalanced reference fund.  Conditional start-date values are fitted
out of fold using only market state observable at that anniversary.  No nested
Monte Carlo, policyholder state, notional, mortality, behaviour or fee data are
stored in the resulting hedge-price cache.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Mapping, Optional, Sequence

import numpy as np
from numpy.typing import NDArray

from ._provenance import assumption_fingerprint
from .esg import ScenarioSet, STEPS_PER_YEAR
from .optimal_behaviour_lsmc import (
    OptimalBehaviourLSMCSettings,
    _cross_fitted_regression,
)
from .product import Index


Array = NDArray[np.float64]
IntArray = NDArray[np.int64]

HEDGE_CACHE_SCHEMA_VERSION = "q_hedge_prices_v1"
HEDGE_PRICING_VERSION = "cross_fitted_ridge_v1"
DEFAULT_HEDGE_CROSS_FIT_FOLDS = 5
DEFAULT_HEDGE_CROSS_FIT_SEED = 9137
DEFAULT_HEDGE_RIDGE = 1.0e-6
HEDGE_FEATURE_NAMES = (
    "global_equity_heston_variance",
    "short_rate",
    "one_year_zero_rate",
    "five_year_zero_rate",
    "policy_year",
)

_ARRAY_FILES = {
    "cap_grid": "cap_grid.npy",
    "annual_start_steps": "annual_start_steps.npy",
    "annual_end_steps": "annual_end_steps.npy",
    "rolling_bond_index_5y": "rolling_bond_index_5y.npy",
    "reference_fund_index": "reference_fund_index.npy",
    "annual_reference_fund_return": "annual_reference_fund_return.npy",
    "annual_discount_ratio": "annual_discount_ratio.npy",
    "annual_spread_payoff_per_unit": "annual_spread_payoff_per_unit.npy",
    "annual_fair_price_per_unit": "annual_fair_price_per_unit.npy",
}


class HedgePriceCacheError(RuntimeError):
    """Base error for missing or incompatible annual hedge-price caches."""


class HedgePriceCacheNotFoundError(HedgePriceCacheError):
    """Raised when the exact requested hedge cache is absent."""


class HedgePriceCacheMismatchError(HedgePriceCacheError):
    """Raised when a hedge cache fails strict validation."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    )


def _normalise_cap_grid(values: Sequence[float] | Array) -> Array:
    caps = np.asarray(values, dtype=float)
    if caps.ndim != 1 or caps.size == 0 or not np.all(np.isfinite(caps)) \
            or np.any(caps < 0.0) or np.any(np.diff(caps) <= 0.0):
        raise ValueError(
            "cap_grid must be a finite, strictly increasing non-negative vector."
        )
    return caps


@dataclass(frozen=True)
class HedgePriceCacheSpec:
    """Inputs that uniquely determine one annual conditional price surface."""

    market_cache_key: str
    scenario_fingerprint: str
    n_paths: int
    horizon_years: float
    equity_index: Index
    equity_allocation: float
    allocation_input_sha256: str
    cap_grid: tuple[float, ...]
    training_scenario_fingerprint: str
    cross_fit_folds: int = DEFAULT_HEDGE_CROSS_FIT_FOLDS
    cross_fit_seed: int = DEFAULT_HEDGE_CROSS_FIT_SEED
    ridge: float = DEFAULT_HEDGE_RIDGE
    bond_tenor_years: float = 5.0
    monthly_rebalancing: bool = True
    pricing_version: str = HEDGE_PRICING_VERSION
    schema_version: str = HEDGE_CACHE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "equity_index", Index(self.equity_index))
        caps = tuple(float(value) for value in _normalise_cap_grid(self.cap_grid))
        object.__setattr__(self, "cap_grid", caps)
        for name in (
            "market_cache_key", "scenario_fingerprint",
            "training_scenario_fingerprint", "allocation_input_sha256",
        ):
            value = str(getattr(self, name)).lower()
            if len(value) != 64 or any(
                    character not in "0123456789abcdef" for character in value
            ):
                raise ValueError(f"{name} must be a SHA-256 hex digest.")
            object.__setattr__(self, name, value)
        if self.schema_version != HEDGE_CACHE_SCHEMA_VERSION \
                or self.pricing_version != HEDGE_PRICING_VERSION:
            raise ValueError("Unsupported hedge cache/pricing version.")
        if isinstance(self.n_paths, bool) or not isinstance(
                self.n_paths, (int, np.integer)) or self.n_paths <= 0:
            raise ValueError("n_paths must be a positive integer.")
        if not np.isfinite(self.horizon_years) or self.horizon_years <= 0.0 \
                or not np.isclose(
                    self.horizon_years * STEPS_PER_YEAR,
                    round(self.horizon_years * STEPS_PER_YEAR),
                ):
            raise ValueError("horizon_years must be positive and monthly aligned.")
        if not np.isfinite(self.equity_allocation) \
                or not 0.0 <= self.equity_allocation <= 1.0:
            raise ValueError("equity_allocation must be in [0, 1].")
        if not np.isclose(self.bond_tenor_years, 5.0):
            raise ValueError("The hedge cache requires the fixed five-year bond tenor.")
        if self.monthly_rebalancing is not True:
            raise ValueError("The hedge cache requires monthly rebalancing.")
        for name in ("cross_fit_folds", "cross_fit_seed"):
            value = getattr(self, name)
            minimum = 2 if name == "cross_fit_folds" else 0
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) \
                    or int(value) < minimum:
                raise ValueError(f"{name} is invalid.")
        if not np.isfinite(self.ridge) or self.ridge < 0.0:
            raise ValueError("ridge must be finite and non-negative.")

    def canonical_fields(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "pricing_version": self.pricing_version,
            "market_cache_key": self.market_cache_key,
            "scenario_fingerprint": self.scenario_fingerprint,
            "n_paths": int(self.n_paths),
            "horizon_years": float(self.horizon_years),
            "equity_index": self.equity_index.value,
            "equity_allocation": float(self.equity_allocation),
            "allocation_input_sha256": self.allocation_input_sha256,
            "bond_tenor_years": float(self.bond_tenor_years),
            "monthly_rebalancing": True,
            "cap_grid": list(self.cap_grid),
            "training_scenario_fingerprint": self.training_scenario_fingerprint,
            "cross_fit_folds": int(self.cross_fit_folds),
            "cross_fit_seed": int(self.cross_fit_seed),
            "ridge": float(self.ridge),
            "feature_names": list(HEDGE_FEATURE_NAMES),
        }

    @property
    def cache_key(self) -> str:
        return sha256(
            _canonical_json(self.canonical_fields()).encode("utf-8")
        ).hexdigest()


def annual_call_spread_payoffs(
    annual_reference_fund_return: Array,
    cap_grid: Sequence[float] | Array,
) -> Array:
    """Return ``min(max(R, 0), cap)`` for all paths, years and caps."""
    returns = np.asarray(annual_reference_fund_return, dtype=float)
    caps = _normalise_cap_grid(cap_grid)
    if returns.ndim != 2 or not np.all(np.isfinite(returns)):
        raise ValueError("annual_reference_fund_return must be a finite matrix.")
    return np.minimum(
        np.maximum(returns[:, :, None], 0.0), caps[None, None, :]
    )


def direct_discounted_mc_pv(
    discount_at_end: Array,
    notional_at_start: Array,
    payoff_per_unit: Array,
) -> float | Array:
    """Direct time-zero MC PV for fixed or multiple cap payoff arrays."""
    discount = np.asarray(discount_at_end, dtype=float)
    notional = np.asarray(notional_at_start, dtype=float)
    payoff = np.asarray(payoff_per_unit, dtype=float)
    if discount.ndim != 2 or notional.shape != discount.shape \
            or not np.all(np.isfinite(discount)) \
            or not np.all(np.isfinite(notional)) \
            or np.any(discount <= 0.0) or np.any(notional < 0.0):
        raise ValueError("Discount and notional matrices are inconsistent.")
    if payoff.shape[:2] != discount.shape or payoff.ndim not in (2, 3) \
            or not np.all(np.isfinite(payoff)) or np.any(payoff < 0.0):
        raise ValueError("Payoff array is inconsistent with discount matrices.")
    weights = discount * notional
    if payoff.ndim == 2:
        return float(np.mean(np.sum(weights * payoff, axis=1)))
    return np.mean(np.sum(weights[:, :, None] * payoff, axis=1), axis=0)


def build_annual_pricing_features(
    scenarios: ScenarioSet,
    annual_start_steps: IntArray,
) -> Array:
    """Build the documented anniversary-observable market feature panel."""
    starts = np.asarray(annual_start_steps, dtype=np.int64)
    if starts.ndim != 1 or np.any(starts < 0) \
            or np.any(starts > scenarios.n_steps):
        raise ValueError("annual_start_steps are invalid.")
    if scenarios.variance is None:
        variance = np.full(
            (scenarios.n_paths, starts.size),
            scenarios.config.equity[Index.GLOBAL_EQUITY].sigma ** 2,
        )
    else:
        variance = np.asarray(
            scenarios.variance[Index.GLOBAL_EQUITY][:, starts]
        )
    out = np.empty((scenarios.n_paths, starts.size, len(HEDGE_FEATURE_NAMES)))
    out[:, :, 0] = variance
    out[:, :, 1] = scenarios.short_rate[:, starts]
    for year, step in enumerate(starts):
        out[:, year, 2] = scenarios.zero_rate(int(step), 1.0)
        out[:, year, 3] = scenarios.zero_rate(int(step), 5.0)
        out[:, year, 4] = float(year + 1)
    if not np.all(np.isfinite(out)):
        raise ValueError("Annual hedge-pricing features must be finite.")
    return out


def _fold_ids(n_paths: int, folds: int, seed: int) -> IntArray:
    if n_paths <= folds:
        raise ValueError("Cross-fitting requires more paths than folds.")
    order = np.arange(n_paths, dtype=np.int64)
    np.random.default_rng(seed).shuffle(order)
    ids = np.empty(n_paths, dtype=np.int64)
    ids[order] = np.arange(n_paths, dtype=np.int64) % folds
    return ids


def cross_fitted_conditional_prices(
    *,
    features: Array,
    discounted_payoff_target: Array,
    start_date_discount: Array,
    cap_grid: Sequence[float] | Array,
    one_year_zero_bond_price: Array,
    folds: int = DEFAULT_HEDGE_CROSS_FIT_FOLDS,
    fold_seed: int = DEFAULT_HEDGE_CROSS_FIT_SEED,
    ridge: float = DEFAULT_HEDGE_RIDGE,
) -> tuple[Array, dict[str, np.ndarray]]:
    """Fit pathwise annual prices with complete-path out-of-fold Ridge.

    Every path is predicted only by a regression that excludes that path.
    The returned small model dictionary can be persisted in ``pricing_model.npz``.
    """
    raw = np.asarray(features, dtype=float)
    target = np.asarray(discounted_payoff_target, dtype=float)
    start_discount = np.asarray(start_date_discount, dtype=float)
    caps = _normalise_cap_grid(cap_grid)
    zcb = np.asarray(one_year_zero_bond_price, dtype=float)
    if raw.ndim != 3 or raw.shape[2] != len(HEDGE_FEATURE_NAMES) \
            or target.shape != (raw.shape[0], raw.shape[1], caps.size):
        raise ValueError("Conditional-pricing feature/target shapes are inconsistent.")
    if start_discount.shape != raw.shape[:2] or zcb.shape != raw.shape[:2]:
        raise ValueError("Conditional-pricing discount shapes are inconsistent.")
    if not np.all(np.isfinite(raw)) or not np.all(np.isfinite(target)) \
            or not np.all(np.isfinite(start_discount)) \
            or not np.all(np.isfinite(zcb)) or np.any(target < 0.0) \
            or np.any(start_discount <= 0.0) or np.any(zcb <= 0.0):
        raise ValueError("Conditional-pricing inputs must be finite and valid.")
    if isinstance(folds, bool) or int(folds) < 2:
        raise ValueError("folds must be an integer of at least two.")
    ids = _fold_ids(raw.shape[0], int(folds), int(fold_seed))
    n_paths, n_years, _ = raw.shape
    n_caps = caps.size
    prices = np.zeros((n_paths, n_years, n_caps))
    full_intercept = np.zeros((n_years, n_caps))
    full_coefficients = np.zeros((n_years, n_caps, raw.shape[2]))
    fold_intercept = np.zeros((folds, n_years, n_caps))
    fold_coefficients = np.zeros((folds, n_years, n_caps, raw.shape[2]))
    regression_settings = OptimalBehaviourLSMCSettings(
        ridge=float(ridge),
        ridge_grid=(float(ridge),),
        n_folds=int(folds),
        fold_seed=int(fold_seed),
        relative_svd_cutoff=1.0e-10,
        minimum_regression_observations=2,
        observations_per_coefficient=2,
    )

    for year in range(n_years):
        year_features = raw[:, year, :]
        for cap_index, cap in enumerate(caps):
            if cap == 0.0:
                continue
            full, oof, folds_used, fold_models = _cross_fitted_regression(
                year_features,
                target[:, year, cap_index],
                1.0,
                regression_settings,
                ids,
            )
            if folds_used != folds or len(fold_models) != folds:
                raise ValueError(
                    "Annual hedge pricing could not retain the configured "
                    "cross-fit fold count."
                )
            intercept, coefficients = full.raw_affine_form()
            full_intercept[year, cap_index] = intercept
            full_coefficients[year, cap_index, :] = coefficients
            prices[:, year, cap_index] = oof
            for fold, regression in enumerate(fold_models):
                fold_value, fold_beta = regression.raw_affine_form()
                fold_intercept[fold, year, cap_index] = fold_value
                fold_coefficients[fold, year, cap_index, :] = fold_beta

    # Static no-arbitrage projection on the discrete cap grid.  Since the
    # pointwise upper bounds grow with cap, the two operations are compatible.
    prices = np.maximum.accumulate(np.maximum(prices, 0.0), axis=2)
    upper = zcb[:, :, None] * caps[None, None, :]
    prices = np.minimum(prices, upper)
    if caps[0] == 0.0:
        prices[:, :, 0] = 0.0

    models = {
        "fold_ids": ids,
        "full_intercept": full_intercept,
        "full_coefficients": full_coefficients,
        "fold_intercept": fold_intercept,
        "fold_coefficients": fold_coefficients,
        "feature_names": np.asarray(HEDGE_FEATURE_NAMES),
        "ridge": np.asarray([float(ridge)]),
    }
    return prices, models


@dataclass(frozen=True)
class HedgePriceSurface:
    """Validated path-aligned annual call-spread price artefact."""

    spec: HedgePriceCacheSpec
    cap_grid: Array
    annual_start_steps: IntArray
    annual_end_steps: IntArray
    rolling_bond_index_5y: Array
    reference_fund_index: Array
    annual_reference_fund_return: Array
    annual_discount_ratio: Array
    annual_spread_payoff_per_unit: Array
    annual_fair_price_per_unit: Array
    pricing_model: Mapping[str, np.ndarray]
    source_cache_key: str = ""
    price_surface_fingerprint: str = ""

    def __post_init__(self) -> None:
        def readonly(value: object, dtype: object = float) -> np.ndarray:
            array = np.array(value, dtype=dtype, copy=False, subok=True)
            array.flags.writeable = False
            return array

        caps = readonly(self.cap_grid)
        starts = readonly(self.annual_start_steps, np.int64)
        ends = readonly(self.annual_end_steps, np.int64)
        bond = readonly(self.rolling_bond_index_5y)
        fund = readonly(self.reference_fund_index)
        annual_return = readonly(self.annual_reference_fund_return)
        discount_ratio = readonly(self.annual_discount_ratio)
        payoff = readonly(self.annual_spread_payoff_per_unit)
        fair_price = readonly(self.annual_fair_price_per_unit)
        _normalise_cap_grid(caps)
        n_paths = self.spec.n_paths
        n_steps = int(round(self.spec.horizon_years * STEPS_PER_YEAR))
        n_years = starts.size
        n_caps = caps.size
        expected_starts = np.arange(
            0, n_steps - STEPS_PER_YEAR + 1, STEPS_PER_YEAR,
            dtype=np.int64,
        )
        if not np.array_equal(caps, np.asarray(self.spec.cap_grid)):
            raise ValueError("Surface cap_grid differs from HedgePriceCacheSpec.")
        if not np.array_equal(starts, expected_starts) \
                or not np.array_equal(ends, expected_starts + STEPS_PER_YEAR):
            raise ValueError("Annual hedge start/end grids are invalid.")
        if bond.shape != (n_paths, n_steps + 1) \
                or fund.shape != bond.shape:
            raise ValueError("Stored reference indices have invalid shapes.")
        if annual_return.shape != (n_paths, n_years) \
                or discount_ratio.shape != annual_return.shape:
            raise ValueError("Stored annual return/discount arrays are invalid.")
        expected_cube = (n_paths, n_years, n_caps)
        if payoff.shape != expected_cube or fair_price.shape != expected_cube:
            raise ValueError("Stored annual payoff/price cubes are invalid.")
        floating_arrays = (bond, fund, annual_return, discount_ratio, payoff, fair_price)
        if any(not np.all(np.isfinite(array)) for array in floating_arrays) \
                or np.any(bond <= 0.0) or np.any(fund <= 0.0) \
                or np.any(discount_ratio <= 0.0) or np.any(payoff < 0.0) \
                or np.any(fair_price < -1.0e-14):
            raise ValueError("Stored hedge artefact contains invalid values.")
        if np.any(np.diff(payoff, axis=2) < -1.0e-12) \
                or np.any(np.diff(fair_price, axis=2) < -1.0e-12):
            raise ValueError("Hedge payoff/prices must be monotone in cap.")
        zero_caps = np.flatnonzero(caps == 0.0)
        if zero_caps.size and (
            np.any(payoff[:, :, zero_caps] != 0.0)
            or np.any(fair_price[:, :, zero_caps] != 0.0)
        ):
            raise ValueError("Cap zero must have zero payoff and fair price.")
        models = {
            str(name): readonly(value, np.asarray(value).dtype)
            for name, value in self.pricing_model.items()
        }
        expected_model_keys = {
            "fold_ids", "full_intercept", "full_coefficients",
            "fold_intercept", "fold_coefficients", "feature_names", "ridge",
        }
        if set(models) != expected_model_keys:
            raise ValueError("Hedge pricing model has an invalid array inventory.")
        model_shapes = {
            "fold_ids": (n_paths,),
            "full_intercept": (n_years, n_caps),
            "full_coefficients": (
                n_years, n_caps, len(HEDGE_FEATURE_NAMES)
            ),
            "fold_intercept": (
                self.spec.cross_fit_folds, n_years, n_caps
            ),
            "fold_coefficients": (
                self.spec.cross_fit_folds, n_years, n_caps,
                len(HEDGE_FEATURE_NAMES),
            ),
            "feature_names": (len(HEDGE_FEATURE_NAMES),),
            "ridge": (1,),
        }
        if any(models[name].shape != shape for name, shape in model_shapes.items()):
            raise ValueError("Hedge pricing model has invalid array shapes.")
        fold_ids = models["fold_ids"]
        if not np.issubdtype(fold_ids.dtype, np.integer) \
                or np.any(fold_ids < 0) \
                or np.any(fold_ids >= self.spec.cross_fit_folds) \
                or np.unique(fold_ids).size != self.spec.cross_fit_folds:
            raise ValueError("Hedge pricing model has invalid cross-fit IDs.")
        if not np.array_equal(
            models["feature_names"], np.asarray(HEDGE_FEATURE_NAMES)
        ) or not np.array_equal(
            models["ridge"], np.asarray([self.spec.ridge])
        ):
            raise ValueError("Hedge pricing model metadata differs from its spec.")
        numeric_model_arrays = (
            models["full_intercept"], models["full_coefficients"],
            models["fold_intercept"], models["fold_coefficients"],
        )
        if any(not np.all(np.isfinite(array)) for array in numeric_model_arrays):
            raise ValueError("Hedge pricing model contains non-finite parameters.")
        fingerprint = assumption_fingerprint(
            self.spec.canonical_fields(), caps, starts, ends, bond, fund,
            annual_return, discount_ratio, payoff, fair_price, models,
        )
        if self.price_surface_fingerprint \
                and self.price_surface_fingerprint != fingerprint:
            raise ValueError("Hedge price-surface fingerprint mismatch.")
        source_key = str(self.source_cache_key or self.spec.cache_key).lower()
        if len(source_key) != 64 or any(
                character not in "0123456789abcdef" for character in source_key
        ):
            raise ValueError("source_cache_key must be a SHA-256 hex digest.")
        object.__setattr__(self, "cap_grid", caps)
        object.__setattr__(self, "annual_start_steps", starts)
        object.__setattr__(self, "annual_end_steps", ends)
        object.__setattr__(self, "rolling_bond_index_5y", bond)
        object.__setattr__(self, "reference_fund_index", fund)
        object.__setattr__(self, "annual_reference_fund_return", annual_return)
        object.__setattr__(self, "annual_discount_ratio", discount_ratio)
        object.__setattr__(self, "annual_spread_payoff_per_unit", payoff)
        object.__setattr__(self, "annual_fair_price_per_unit", fair_price)
        object.__setattr__(self, "pricing_model", models)
        object.__setattr__(self, "source_cache_key", source_key)
        object.__setattr__(self, "price_surface_fingerprint", fingerprint)

    @property
    def hedge_cache_key(self) -> str:
        """Key of the on-disk cache entry from which this surface derives."""
        return self.source_cache_key

    def validate_against(
        self,
        scenarios: ScenarioSet,
        cap_grid: Optional[Sequence[float] | Array] = None,
    ) -> None:
        mismatches: list[str] = []
        if scenarios.content_fingerprint != self.spec.scenario_fingerprint:
            mismatches.append("scenario_fingerprint/path_order")
        if scenarios.n_paths != self.spec.n_paths:
            mismatches.append("n_paths")
        if not np.isclose(
            scenarios.times[-1], self.spec.horizon_years,
            rtol=0.0, atol=1.0e-12,
        ):
            mismatches.append("horizon")
        if self.reference_fund_index.shape != (
            scenarios.n_paths, scenarios.n_steps + 1
        ):
            mismatches.append("monthly_grid")
        if cap_grid is not None and not np.array_equal(
            self.cap_grid, _normalise_cap_grid(cap_grid)
        ):
            mismatches.append("cap_grid")
        if mismatches:
            raise HedgePriceCacheMismatchError(
                "Hedge price surface does not match ScenarioSet: "
                + ", ".join(mismatches)
                + "."
            )

    def price_for(self, step: int, cap: float | Array) -> Array:
        """Return exact-grid pathwise prices at one annual start step."""
        positions = np.flatnonzero(self.annual_start_steps == int(step))
        if positions.size != 1:
            raise HedgePriceCacheMismatchError(
                f"No unique annual hedge price exists for start step {step}."
            )
        requested = np.asarray(cap, dtype=float)
        if requested.ndim == 0:
            cap_positions = np.flatnonzero(np.isclose(
                self.cap_grid, float(requested), rtol=0.0, atol=1.0e-12
            ))
            if cap_positions.size != 1:
                raise HedgePriceCacheMismatchError(
                    f"Cap {float(requested):.12g} is absent from hedge cache grid."
                )
            return self.annual_fair_price_per_unit[
                :, positions[0], cap_positions[0]
            ]
        if requested.shape != (self.spec.n_paths,):
            raise ValueError("Pathwise cap must match the hedge-price path count.")
        out = np.empty(self.spec.n_paths)
        assigned = np.zeros(self.spec.n_paths, dtype=bool)
        for cap_index, cached_cap in enumerate(self.cap_grid):
            selected = np.isclose(
                requested, cached_cap, rtol=0.0, atol=1.0e-12
            )
            out[selected] = self.annual_fair_price_per_unit[
                selected, positions[0], cap_index
            ]
            assigned |= selected
        if not np.all(assigned):
            missing = np.unique(requested[~assigned])
            raise HedgePriceCacheMismatchError(
                "Pathwise cap values are absent from hedge cache grid: "
                + ", ".join(f"{value:.12g}" for value in missing[:8])
            )
        return out

    def _transformed(
        self,
        scenarios: ScenarioSet,
        *,
        path_selection: object,
        time_stop: Optional[int] = None,
    ) -> "HedgePriceSurface":
        stop = self.reference_fund_index.shape[1] if time_stop is None else time_stop
        years = self.annual_end_steps <= stop - 1
        new_spec = HedgePriceCacheSpec(
            market_cache_key=self.spec.market_cache_key,
            scenario_fingerprint=scenarios.content_fingerprint,
            n_paths=scenarios.n_paths,
            horizon_years=float(scenarios.times[-1]),
            equity_index=self.spec.equity_index,
            equity_allocation=self.spec.equity_allocation,
            allocation_input_sha256=self.spec.allocation_input_sha256,
            cap_grid=self.spec.cap_grid,
            training_scenario_fingerprint=self.spec.training_scenario_fingerprint,
            cross_fit_folds=self.spec.cross_fit_folds,
            cross_fit_seed=self.spec.cross_fit_seed,
            ridge=self.spec.ridge,
        )
        models = dict(self.pricing_model)
        if "fold_ids" in models:
            models["fold_ids"] = np.asarray(models["fold_ids"])[path_selection]
        if "full_intercept" in models:
            models["full_intercept"] = np.asarray(
                models["full_intercept"]
            )[years]
        if "full_coefficients" in models:
            models["full_coefficients"] = np.asarray(
                models["full_coefficients"]
            )[years]
        if "fold_intercept" in models:
            models["fold_intercept"] = np.asarray(
                models["fold_intercept"]
            )[:, years, :]
        if "fold_coefficients" in models:
            models["fold_coefficients"] = np.asarray(
                models["fold_coefficients"]
            )[:, years, :, :]
        return HedgePriceSurface(
            spec=new_spec,
            cap_grid=self.cap_grid,
            annual_start_steps=self.annual_start_steps[years],
            annual_end_steps=self.annual_end_steps[years],
            rolling_bond_index_5y=np.asarray(
                self.rolling_bond_index_5y[path_selection, :stop]
            ),
            reference_fund_index=np.asarray(
                self.reference_fund_index[path_selection, :stop]
            ),
            annual_reference_fund_return=np.asarray(
                self.annual_reference_fund_return[path_selection][:, years]
            ),
            annual_discount_ratio=np.asarray(
                self.annual_discount_ratio[path_selection][:, years]
            ),
            annual_spread_payoff_per_unit=np.asarray(
                self.annual_spread_payoff_per_unit[path_selection][:, years, :]
            ),
            annual_fair_price_per_unit=np.asarray(
                self.annual_fair_price_per_unit[path_selection][:, years, :]
            ),
            pricing_model=models,
            source_cache_key=self.hedge_cache_key,
        )

    def slice_paths(
        self, start: int, stop: int, scenarios: ScenarioSet,
    ) -> "HedgePriceSurface":
        if start < 0 or stop <= start or stop > self.spec.n_paths:
            raise ValueError("Invalid hedge-price path slice.")
        return self._transformed(
            scenarios, path_selection=slice(start, stop)
        )

    def repeat_paths(
        self, repeats: int, scenarios: ScenarioSet,
    ) -> "HedgePriceSurface":
        if repeats <= 0:
            raise ValueError("repeats must be positive.")
        selection = np.tile(np.arange(self.spec.n_paths), int(repeats))
        return self._transformed(scenarios, path_selection=selection)

    def horizon_prefix(
        self, stop_step: int, scenarios: ScenarioSet,
    ) -> "HedgePriceSurface":
        if stop_step < 1 or stop_step > int(round(
            self.spec.horizon_years * STEPS_PER_YEAR
        )):
            raise ValueError("Invalid hedge-price horizon prefix.")
        return self._transformed(
            scenarios,
            path_selection=slice(None),
            time_stop=int(stop_step) + 1,
        )


def build_hedge_price_surface(
    scenarios: ScenarioSet,
    spec: HedgePriceCacheSpec,
) -> HedgePriceSurface:
    """Derive reference paths, payoffs and cross-fitted annual prices once."""
    if scenarios.content_fingerprint != spec.scenario_fingerprint \
            or scenarios.n_paths != spec.n_paths \
            or not np.isclose(
                scenarios.times[-1], spec.horizon_years,
                rtol=0.0, atol=1.0e-12,
            ):
        raise HedgePriceCacheMismatchError(
            "ScenarioSet does not match HedgePriceCacheSpec."
        )
    starts = np.arange(
        0, scenarios.n_steps - STEPS_PER_YEAR + 1, STEPS_PER_YEAR,
        dtype=np.int64,
    )
    ends = starts + STEPS_PER_YEAR
    bond = scenarios.rolling_zero_bond_index(spec.bond_tenor_years)
    fund = scenarios.monthly_rebalanced_reference_fund_index(
        equity_index=spec.equity_index,
        equity_weight=spec.equity_allocation,
        bond_tenor=spec.bond_tenor_years,
    )
    annual_return = fund[:, ends] / np.maximum(fund[:, starts], 1.0e-300) - 1.0
    discount_ratio = scenarios.discount[:, ends] / scenarios.discount[:, starts]
    payoff = annual_call_spread_payoffs(annual_return, spec.cap_grid)
    target = discount_ratio[:, :, None] * payoff
    features = build_annual_pricing_features(scenarios, starts)
    zcb = np.column_stack([
        scenarios.zero_bond_price(int(step), 1.0) for step in starts
    ])
    fair_price, pricing_model = cross_fitted_conditional_prices(
        features=features,
        discounted_payoff_target=target,
        start_date_discount=scenarios.discount[:, starts],
        cap_grid=spec.cap_grid,
        one_year_zero_bond_price=zcb,
        folds=spec.cross_fit_folds,
        fold_seed=spec.cross_fit_seed,
        ridge=spec.ridge,
    )
    return HedgePriceSurface(
        spec=spec,
        cap_grid=np.asarray(spec.cap_grid),
        annual_start_steps=starts,
        annual_end_steps=ends,
        rolling_bond_index_5y=bond,
        reference_fund_index=fund,
        annual_reference_fund_return=annual_return,
        annual_discount_ratio=discount_ratio,
        annual_spread_payoff_per_unit=payoff,
        annual_fair_price_per_unit=fair_price,
        pricing_model=pricing_model,
    )


def _array_manifest(array: np.ndarray, filename: str) -> dict[str, object]:
    return {
        "file": filename,
        "dtype": np.dtype(array.dtype).str,
        "shape": list(array.shape),
    }


def save_hedge_price_surface(
    cache_root: str | Path,
    surface: HedgePriceSurface,
) -> Path:
    """Write one immutable hedge-price entry without overwriting."""
    if surface.source_cache_key != surface.spec.cache_key:
        raise ValueError(
            "A sliced, repeated or truncated derived surface cannot be saved "
            "as an independent hedge cache."
        )
    root = Path(cache_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / surface.spec.cache_key
    if destination.exists():
        raise FileExistsError(f"Hedge price cache already exists: {destination}")
    arrays = {name: np.asarray(getattr(surface, name)) for name in _ARRAY_FILES}
    temporary = Path(tempfile.mkdtemp(
        prefix=f".{surface.spec.cache_key}.", dir=root
    ))
    try:
        for name, array in arrays.items():
            np.save(temporary / _ARRAY_FILES[name], array, allow_pickle=False)
        np.savez(
            temporary / "pricing_model.npz",
            **{name: np.asarray(value)
               for name, value in surface.pricing_model.items()},
        )
        manifest = {
            "cache_type": "q_hedge_prices",
            "cache_key": surface.spec.cache_key,
            "spec": surface.spec.canonical_fields(),
            "price_surface_fingerprint": surface.price_surface_fingerprint,
            "arrays": {
                name: _array_manifest(array, _ARRAY_FILES[name])
                for name, array in arrays.items()
            },
            "pricing_model_file": "pricing_model.npz",
            "dva_mark_method": "moment_matched_bs",
            "nested_mc_used": False,
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return destination


def load_hedge_price_surface(
    cache_root: str | Path,
    spec: HedgePriceCacheSpec,
    scenarios: ScenarioSet,
    *,
    mmap_mode: Optional[str] = "r",
) -> HedgePriceSurface:
    """Load an exact path-aligned hedge surface and reject every mismatch."""
    directory = Path(cache_root).expanduser().resolve() / spec.cache_key
    if not directory.is_dir():
        raise HedgePriceCacheNotFoundError(
            "Exact hedge price cache not found for key "
            f"{spec.cache_key}: {directory}"
        )
    manifest_path = directory / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HedgePriceCacheMismatchError(
            f"Hedge cache manifest is unreadable: {manifest_path}"
        ) from exc
    if not isinstance(manifest, dict) \
            or manifest.get("cache_type") != "q_hedge_prices" \
            or manifest.get("cache_key") != spec.cache_key \
            or manifest.get("spec") != spec.canonical_fields():
        raise HedgePriceCacheMismatchError(
            f"Hedge cache manifest does not match exact key {spec.cache_key}."
        )
    metadata = manifest.get("arrays")
    if not isinstance(metadata, dict) or set(metadata) != set(_ARRAY_FILES):
        raise HedgePriceCacheMismatchError(
            "Hedge cache manifest has an incomplete array inventory."
        )
    arrays: dict[str, np.ndarray] = {}
    for name, filename in _ARRAY_FILES.items():
        item = metadata[name]
        if not isinstance(item, dict) or item.get("file") != filename:
            raise HedgePriceCacheMismatchError(
                f"Invalid hedge-cache metadata for {name}."
            )
        try:
            value = np.load(
                directory / filename, mmap_mode=mmap_mode, allow_pickle=False
            )
        except (OSError, ValueError) as exc:
            raise HedgePriceCacheMismatchError(
                f"Hedge-cache array is unreadable: {filename}"
            ) from exc
        if list(value.shape) != item.get("shape") \
                or np.dtype(value.dtype).str != item.get("dtype"):
            raise HedgePriceCacheMismatchError(
                f"Hedge-cache array metadata mismatch for {name}."
            )
        arrays[name] = value
    model_path = directory / "pricing_model.npz"
    try:
        with np.load(model_path, allow_pickle=False) as model_archive:
            pricing_model = {
                name: np.array(model_archive[name], copy=True)
                for name in model_archive.files
            }
    except (OSError, ValueError) as exc:
        raise HedgePriceCacheMismatchError(
            f"Hedge pricing model is unreadable: {model_path}"
        ) from exc
    surface = HedgePriceSurface(
        spec=spec,
        pricing_model=pricing_model,
        price_surface_fingerprint=str(manifest.get("price_surface_fingerprint", "")),
        **arrays,
    )
    surface.validate_against(scenarios, spec.cap_grid)
    return surface


__all__ = [
    "DEFAULT_HEDGE_CROSS_FIT_FOLDS",
    "DEFAULT_HEDGE_CROSS_FIT_SEED",
    "DEFAULT_HEDGE_RIDGE",
    "HEDGE_CACHE_SCHEMA_VERSION",
    "HEDGE_FEATURE_NAMES",
    "HEDGE_PRICING_VERSION",
    "HedgePriceCacheError",
    "HedgePriceCacheMismatchError",
    "HedgePriceCacheNotFoundError",
    "HedgePriceCacheSpec",
    "HedgePriceSurface",
    "annual_call_spread_payoffs",
    "build_annual_pricing_features",
    "build_hedge_price_surface",
    "cross_fitted_conditional_prices",
    "direct_discounted_mc_pv",
    "load_hedge_price_surface",
    "save_hedge_price_surface",
]
