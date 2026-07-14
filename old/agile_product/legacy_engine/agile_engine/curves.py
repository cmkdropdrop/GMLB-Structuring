"""Yield curve utilities.

A minimal, dependency-free zero curve with continuous compounding used across
the engine (discounting, Hull-White fitting, MVA reference rates).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


@dataclass(frozen=True)
class YieldCurve:
    """Zero-coupon yield curve, continuously compounded, act/act in years.

    Parameters
    ----------
    tenors:
        Strictly increasing tenors in years (> 0).
    zero_rates:
        Continuously compounded zero rates for each tenor.

    Rates are interpolated linearly in the zero rate and extrapolated flat.
    """

    tenors: tuple = (1.0, 30.0)
    zero_rates: tuple = (0.04, 0.04)

    def __post_init__(self) -> None:
        t = np.asarray(self.tenors, dtype=float)
        z = np.asarray(self.zero_rates, dtype=float)
        if t.ndim != 1 or z.shape != t.shape:
            raise ValueError("tenors and zero_rates must be 1-D and equally long.")
        if len(t) < 2 or not np.all(np.isfinite(t)) or not np.all(np.isfinite(z)):
            raise ValueError("Yield curve requires at least two finite tenor/rate points.")
        if np.any(t <= 0) or np.any(np.diff(t) <= 0):
            raise ValueError("tenors must be positive and strictly increasing.")
        object.__setattr__(self, "tenors", tuple(float(x) for x in t))
        object.__setattr__(self, "zero_rates", tuple(float(x) for x in z))

    @staticmethod
    def flat(rate: float) -> "YieldCurve":
        return YieldCurve(tenors=(1.0, 50.0), zero_rates=(float(rate), float(rate)))

    @staticmethod
    def from_rates(tenors: Sequence[float], zero_rates: Sequence[float]) -> "YieldCurve":
        return YieldCurve(tenors=tuple(float(x) for x in tenors),
                          zero_rates=tuple(float(x) for x in zero_rates))

    # ------------------------------------------------------------------ #

    def zero(self, t: float | Array) -> float | Array:
        """Zero rate for maturity ``t`` (flat extrapolation)."""
        t_arr = np.asarray(t, dtype=float)
        if not np.all(np.isfinite(t_arr)) or np.any(t_arr < 0.0):
            raise ValueError("Curve maturities must be finite and non-negative.")
        out = np.interp(np.clip(t_arr, self.tenors[0], self.tenors[-1]),
                        np.asarray(self.tenors), np.asarray(self.zero_rates))
        return float(out) if np.ndim(t) == 0 else out

    def df(self, t: float | Array) -> float | Array:
        """Discount factor P(0, t)."""
        t_arr = np.asarray(t, dtype=float)
        out = np.exp(-self.zero(t_arr) * np.maximum(t_arr, 0.0))
        return float(out) if np.ndim(t) == 0 else out

    def forward_df(self, t1: float, t2: float) -> float:
        """Forward discount factor P(0,t2)/P(0,t1)."""
        if t2 < t1:
            raise ValueError("t2 must be >= t1.")
        return float(self.df(t2) / self.df(t1))

    def forward_zero(self, t1: float, t2: float) -> float:
        """Continuously compounded forward zero rate between t1 and t2."""
        if t2 <= t1:
            raise ValueError("t2 must be > t1.")
        return float(-np.log(self.forward_df(t1, t2)) / (t2 - t1))

    def instantaneous_forward(self, t: float | Array, h: float = 1e-4) -> float | Array:
        """Instantaneous forward rate f(0,t) via central differences."""
        if not np.isfinite(h) or h <= 0.0:
            raise ValueError("h must be positive and finite.")
        t_arr = np.asarray(t, dtype=float)
        tp = np.maximum(t_arr, h)
        lo = np.log(self.df(tp - h))
        hi = np.log(self.df(tp + h))
        out = -(hi - lo) / (2.0 * h)
        return float(out) if np.ndim(t) == 0 else out

    def shifted(self, shift: float) -> "YieldCurve":
        """Parallel shift of all zero rates by ``shift`` (absolute, e.g. 0.01)."""
        return YieldCurve(tenors=self.tenors,
                          zero_rates=tuple(z + shift for z in self.zero_rates))

    def scaled(self, factors: Sequence[float] | float, min_abs_shift: float = 0.0) -> "YieldCurve":
        """Relative stress: z -> z * (1 + factor), with optional minimum absolute shift.

        Used for Solvency-II style relative interest rate stresses. ``factors``
        may be a scalar or one factor per tenor.
        """
        z = np.asarray(self.zero_rates, dtype=float)
        f = np.broadcast_to(np.asarray(factors, dtype=float), z.shape)
        stressed = z * (1.0 + f)
        if min_abs_shift > 0.0:
            stressed = np.where(f > 0, np.maximum(stressed, z + min_abs_shift), stressed)
        elif min_abs_shift < 0.0:
            stressed = np.where(f < 0, np.minimum(stressed, z + min_abs_shift), stressed)
        return YieldCurve(tenors=self.tenors, zero_rates=tuple(stressed))
