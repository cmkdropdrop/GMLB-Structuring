"""Economic scenario generators.

Supported market models (choice follows Goudenege/Molent/Zanette 2015, who
price GLWBs under both Heston and Black-Scholes-Hull-White; the Vasicek/HW
mechanics mirror Shevchenko/Luo 2016/17):

* ``BlackScholesESG``      - two correlated GBM equity indices, deterministic curve
* ``HestonESG``            - Heston stochastic volatility per index, deterministic curve
* ``HullWhiteESG``         - BS equities + 1-factor Hull-White short rate
                             (exact joint simulation of rate, integrated rate and equities)
* ``HestonHullWhiteESG``   - Heston equities + Hull-White short rate (hybrid scheme)

All generators produce a ``ScenarioSet`` on a monthly grid with pathwise
discount factors, and support the risk-neutral and real-world measures.
Martingale properties are enforced by construction (exact schemes) or verified
in the test suite (hybrid scheme).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Dict, Mapping, Optional

import numpy as np
from numpy.typing import NDArray

from .curves import YieldCurve
from .product import Index
from ._provenance import assumption_fingerprint

Array = NDArray[np.float64]

STEPS_PER_YEAR = 12


class Measure(str, Enum):
    RISK_NEUTRAL = "risk_neutral"
    REAL_WORLD = "real_world"


# ---------------------------------------------------------------------------
# Parameter containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EquityParams:
    """Per-index return-index parameters.

    ``dividend_yield`` is retained as a generic continuous carry excluded from
    the simulated index level. It is zero for the case study's total-return
    and MSCI World Net in AUD indices; using the constituents' cash-dividend
    yield here would double-count dividends.
    """

    sigma: float = 0.16          # BS / BS-HW diffusion volatility
    dividend_yield: float = 0.0   # excluded index carry; zero for return indices
    risk_premium: float = 0.045   # real-world excess return over cash (total return)

    def __post_init__(self) -> None:
        values = np.asarray([self.sigma, self.dividend_yield, self.risk_premium])
        if not np.all(np.isfinite(values)):
            raise ValueError("Equity parameters must be finite.")
        if self.sigma <= 0.0 or self.dividend_yield < 0.0:
            raise ValueError("Equity sigma must be positive and dividend yield non-negative.")


@dataclass(frozen=True)
class HestonParams:
    v0: float = 0.0256
    theta: float = 0.0256
    kappa: float = 1.8
    xi: float = 0.35             # vol of variance
    rho_sv: float = -0.6

    def __post_init__(self) -> None:
        values = np.asarray([self.v0, self.theta, self.kappa, self.xi, self.rho_sv])
        if not np.all(np.isfinite(values)):
            raise ValueError("Heston parameters must be finite.")
        if self.v0 < 0.0 or self.theta <= 0.0 or self.kappa <= 0.0 or self.xi < 0.0:
            raise ValueError(
                "Heston variances and xi must be non-negative, with positive "
                "theta and kappa."
            )
        if self.xi == 0.0 and self.v0 != self.theta:
            raise ValueError(
                "The xi=0 fixed-volatility boundary requires v0=theta>0."
            )
        if not -1.0 <= self.rho_sv <= 1.0:
            raise ValueError("Heston rho_sv must be in [-1, 1].")

    def feller_ok(self) -> bool:
        return 2.0 * self.kappa * self.theta >= self.xi ** 2

    def expected_integrated_variance(self, v_t: float | Array, horizon: float = 1.0) -> float | Array:
        """E[ (1/T) int_t^{t+T} v_s ds | v_t ] under the Heston dynamics."""
        k = self.kappa
        w = (1.0 - np.exp(-k * horizon)) / (k * horizon)
        return self.theta + (np.asarray(v_t, dtype=float) - self.theta) * w


@dataclass(frozen=True)
class HullWhiteParams:
    mean_reversion: float = 0.03
    sigma_r: float = 0.008
    #: Correlation between the short-rate Brownian and each equity Brownian.
    rho_sr: Mapping[Index, float] = field(
        default_factory=lambda: {Index.AUS_EQUITY: -0.20, Index.GLOBAL_EQUITY: -0.20})

    def __post_init__(self) -> None:
        if not np.isfinite(self.mean_reversion) or not np.isfinite(self.sigma_r):
            raise ValueError("Hull-White parameters must be finite.")
        if self.mean_reversion <= 0.0 or self.sigma_r < 0.0:
            raise ValueError("Hull-White mean reversion must be positive and sigma non-negative.")
        corr = {Index(k): float(v) for k, v in self.rho_sr.items()}
        if set(corr) != set(Index) or not np.all(np.isfinite(list(corr.values()))) \
                or any(abs(v) >= 1.0 for v in corr.values()):
            raise ValueError("rho_sr must contain finite correlations strictly inside (-1, 1).")
        object.__setattr__(self, "rho_sr", MappingProxyType(corr))

    def b(self, tau: float | Array) -> float | Array:
        a = self.mean_reversion
        tau = np.asarray(tau, dtype=float)
        out = (1.0 - np.exp(-a * tau)) / a
        return float(out) if np.ndim(tau) == 0 else out


@dataclass(frozen=True)
class ESGConfig:
    curve: YieldCurve = field(default_factory=lambda: YieldCurve.flat(0.04))
    equity: Mapping[Index, EquityParams] = field(default_factory=lambda: {
        Index.AUS_EQUITY: EquityParams(sigma=0.16, dividend_yield=0.0, risk_premium=0.045),
        Index.GLOBAL_EQUITY: EquityParams(sigma=0.15, dividend_yield=0.0, risk_premium=0.045),
    })
    equity_correlation: float = 0.75
    heston: Mapping[Index, HestonParams] = field(default_factory=lambda: {
        Index.AUS_EQUITY: HestonParams(v0=0.0256, theta=0.0256, kappa=1.8, xi=0.35, rho_sv=-0.6),
        Index.GLOBAL_EQUITY: HestonParams(v0=0.0225, theta=0.0225, kappa=2.0, xi=0.32, rho_sv=-0.65),
    })
    hull_white: HullWhiteParams = field(default_factory=HullWhiteParams)

    def __post_init__(self) -> None:
        equity = {Index(k): v for k, v in self.equity.items()}
        heston = {Index(k): v for k, v in self.heston.items()}
        if set(equity) != set(Index) or set(heston) != set(Index):
            raise ValueError("Equity and Heston parameters are required for both indices.")
        if not np.isfinite(self.equity_correlation) or not -1.0 < self.equity_correlation < 1.0:
            raise ValueError("equity_correlation must be finite and strictly inside (-1, 1).")
        # Validate the joint [rate, AUS equity, global equity] diffusion block.
        c1 = self.hull_white.rho_sr[Index.AUS_EQUITY]
        c2 = self.hull_white.rho_sr[Index.GLOBAL_EQUITY]
        corr = np.array([[1.0, c1, c2],
                         [c1, 1.0, self.equity_correlation],
                         [c2, self.equity_correlation, 1.0]])
        if np.min(np.linalg.eigvalsh(corr)) <= 1e-10:
            raise ValueError("Rate/equity correlation matrix must be positive definite.")
        # The Heston-HW construction imposes Corr(rate, variance)=0 while
        # retaining Corr(equity, variance)=rho_sv.  This requires the stated
        # residual variance to be non-negative.
        for ix in Index:
            c = self.hull_white.rho_sr[ix]
            if self.heston[ix].rho_sv ** 2 > 1.0 - c ** 2 + 1e-12:
                raise ValueError("rho_sv is incompatible with zero rate-variance correlation.")
        object.__setattr__(self, "equity", MappingProxyType(equity))
        object.__setattr__(self, "heston", MappingProxyType(heston))

    def bump_equity_vol(self, rel: float) -> "ESGConfig":
        eq = {k: replace(v, sigma=v.sigma * (1.0 + rel)) for k, v in self.equity.items()}
        hs = {k: replace(v, v0=v.v0 * (1.0 + rel) ** 2, theta=v.theta * (1.0 + rel) ** 2)
              for k, v in self.heston.items()}
        return replace(self, equity=eq, heston=hs)

    def bump_equity_vol_abs(self, add: float) -> "ESGConfig":
        """Additive vol bump: sigma -> sigma + add per index (exact vol
        points); Heston v0/theta are shifted so sqrt(v) moves by ``add``."""
        eq = {k: replace(v, sigma=max(v.sigma + add, 1e-6))
              for k, v in self.equity.items()}
        hs = {k: replace(v, v0=max(np.sqrt(v.v0) + add, 1e-6) ** 2,
                         theta=max(np.sqrt(v.theta) + add, 1e-6) ** 2)
              for k, v in self.heston.items()}
        return replace(self, equity=eq, heston=hs)

    def with_curve(self, curve: YieldCurve) -> "ESGConfig":
        return replace(self, curve=curve)


# ---------------------------------------------------------------------------
# Scenario container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScenarioSet:
    """Simulated market scenarios on a monthly grid.

    Attributes
    ----------
    index_levels:
        {index: array (n_paths, n_steps+1)}, normalised to 1.0 at t=0.
    short_rate:
        Pathwise short rate (n_paths, n_steps+1); deterministic models store
        the instantaneous forward curve broadcast across paths.
    discount:
        Pathwise discount factor from time 0 to each grid time, i.e.
        exp(-int_0^t r_s ds) (n_paths, n_steps+1).
    variance:
        Heston instantaneous variance per index (None otherwise).
    """

    config: ESGConfig
    measure: Measure
    dt: float
    times: Array
    index_levels: Dict[Index, Array]
    short_rate: Array
    discount: Array
    variance: Optional[Dict[Index, Array]] = None
    stochastic_rates: bool = False
    model_name: str = "black_scholes"
    seed: int = 2026
    substeps: Optional[int] = None
    content_fingerprint: str = field(init=False, repr=False)
    _derived_cache: dict[tuple[object, ...], object] = field(
        init=False, repr=False, compare=False)
    # Internal simulators transfer exclusive ownership of freshly allocated
    # arrays and can avoid a second multi-GB copy.  External construction keeps
    # the safe copying default.
    _copy_inputs: bool = field(default=True, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "measure", Measure(self.measure))
        if isinstance(self.seed, bool) or not isinstance(self.seed, (int, np.integer)) \
                or self.seed < 0:
            raise ValueError("Scenario seed must be a non-negative integer.")
        if not isinstance(self._copy_inputs, (bool, np.bool_)):
            raise ValueError("_copy_inputs must be boolean.")
        copy_inputs = bool(self._copy_inputs)

        def snapshot(value: object) -> Array:
            # ``subok=True`` preserves a read-only ``numpy.memmap`` returned by
            # the scenario cache.  Normal external construction still takes a
            # defensive base-ndarray copy.
            return np.array(
                value, dtype=float, copy=copy_inputs, subok=not copy_inputs,
            )

        times = snapshot(self.times)
        if times.ndim != 1 or len(times) < 2 or not np.all(np.isfinite(times)) \
                or not np.isclose(times[0], 0.0):
            raise ValueError("Scenario times must be a finite one-dimensional grid from zero.")
        if not np.isfinite(self.dt) or self.dt <= 0.0 \
                or not np.allclose(np.diff(times), self.dt, rtol=0.0, atol=1e-12) \
                or not np.isclose(self.dt, 1.0 / STEPS_PER_YEAR):
            raise ValueError("Scenario grid must be uniform and monthly.")
        levels = {Index(k): snapshot(v)
                  for k, v in self.index_levels.items()}
        if set(levels) != set(Index):
            raise ValueError("Scenario levels are required for both indices.")
        shapes = {v.shape for v in levels.values()}
        if len(shapes) != 1:
            raise ValueError("All index-level arrays must have the same shape.")
        shape = next(iter(shapes))
        if len(shape) != 2 or shape[0] <= 0 or shape[1] != len(times):
            raise ValueError("Scenario arrays must have shape (positive paths, len(times)).")
        for values in levels.values():
            if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
                raise ValueError("Index levels must be finite and strictly positive.")
            if not np.allclose(values[:, 0], 1.0, rtol=0.0, atol=1e-12):
                raise ValueError("Index levels must be normalised to 1 at time zero.")
        short_rate = snapshot(self.short_rate)
        discount = snapshot(self.discount)
        for name, arr in (("short_rate", short_rate), ("discount", discount)):
            if arr.shape != shape or not np.all(np.isfinite(arr)):
                raise ValueError(f"{name} must be finite and match the scenario shape.")
        if np.any(discount <= 0.0) or not np.allclose(
                discount[:, 0], 1.0, rtol=0.0, atol=1e-12):
            raise ValueError("Discount factors must be strictly positive.")
        variance = None
        if self.variance is not None:
            variance = {Index(k): snapshot(v)
                        for k, v in self.variance.items()}
            if set(variance) != set(Index):
                raise ValueError("Variance paths are required for both indices.")
            for arr in variance.values():
                if arr.shape != shape or not np.all(np.isfinite(arr)) \
                        or np.any(arr < 0.0):
                    raise ValueError("Variance paths must be finite, non-negative and shape-consistent.")
        if self.model_name not in ("black_scholes", "heston", "hull_white_bs",
                                   "heston_hull_white"):
            raise ValueError("Unknown ScenarioSet model_name.")
        if not isinstance(self.stochastic_rates, (bool, np.bool_)):
            raise ValueError("stochastic_rates must be boolean.")
        expects_variance = self.model_name in ("heston", "heston_hull_white")
        expects_rates = self.model_name in ("hull_white_bs", "heston_hull_white")
        if (variance is not None) != expects_variance:
            raise ValueError("Variance state is inconsistent with model_name.")
        if bool(self.stochastic_rates) != expects_rates:
            raise ValueError("stochastic_rates is inconsistent with model_name.")
        if expects_variance:
            if isinstance(self.substeps, bool) \
                    or not isinstance(self.substeps, (int, np.integer)) \
                    or self.substeps <= 0:
                raise ValueError("Heston ScenarioSets require positive integer substeps.")
        elif self.substeps is not None:
            raise ValueError("substeps apply only to Heston ScenarioSets.")

        # Store immutable snapshots.  Without normalisation a list-backed set
        # passed validation but failed later; without copies an external owner
        # could mutate scenarios after valuation and invalidate provenance.
        arrays = [times, short_rate, discount, *levels.values()]
        if variance is not None:
            arrays.extend(variance.values())
        for arr in arrays:
            arr.flags.writeable = False
        object.__setattr__(self, "times", times)
        object.__setattr__(self, "index_levels", MappingProxyType(levels))
        object.__setattr__(self, "short_rate", short_rate)
        object.__setattr__(self, "discount", discount)
        object.__setattr__(self, "variance", None if variance is None
                           else MappingProxyType(variance))
        object.__setattr__(self, "content_fingerprint", assumption_fingerprint(
            self.config, self.measure, self.dt, times, levels, short_rate,
            discount, variance, self.stochastic_rates, self.model_name,
            self.seed, self.substeps))
        object.__setattr__(self, "_derived_cache", {})

    @property
    def n_paths(self) -> int:
        return next(iter(self.index_levels.values())).shape[0]

    @property
    def n_steps(self) -> int:
        return len(self.times) - 1

    @classmethod
    def from_storage(
        cls,
        *,
        config: ESGConfig,
        measure: Measure,
        dt: float,
        times: Array,
        index_levels: Dict[Index, Array],
        short_rate: Array,
        discount: Array,
        variance: Optional[Dict[Index, Array]],
        stochastic_rates: bool,
        model_name: str,
        seed: int,
        substeps: Optional[int],
    ) -> "ScenarioSet":
        """Restore validated immutable arrays without duplicating storage.

        This constructor is intended for trusted array containers such as
        read-only ``.npy`` memory maps.  It skips only defensive copying; the
        complete shape, finiteness, model-state and fingerprint validation in
        :meth:`__post_init__` still runs.
        """
        return cls(
            config=config,
            measure=measure,
            dt=dt,
            times=times,
            index_levels=index_levels,
            short_rate=short_rate,
            discount=discount,
            variance=variance,
            stochastic_rates=stochastic_rates,
            model_name=model_name,
            seed=seed,
            substeps=substeps,
            _copy_inputs=False,
        )

    @property
    def hedge_price_surface(self) -> Optional[object]:
        """The strictly scenario-bound annual hedge surface, if attached."""
        return self._derived_cache.get(("hedge_price_surface",))

    @property
    def market_cache_key(self) -> Optional[str]:
        """Exact market-cache key this set was restored from, if any."""
        value = self._derived_cache.get(("market_cache_key",))
        return None if value is None else str(value)

    @property
    def market_variant(self) -> Optional[str]:
        """Pre-applied market variant recorded by the market cache, if any."""
        value = self._derived_cache.get(("market_variant",))
        return None if value is None else str(value)

    def bind_market_cache_identity(self, cache_key: str, market_variant: str) -> None:
        """Record the immutable cache provenance of a restored scenario set."""
        if not str(cache_key).strip() or not str(market_variant).strip():
            raise ValueError("Market-cache key and variant must not be empty.")
        values = {
            ("market_cache_key",): str(cache_key),
            ("market_variant",): str(market_variant),
        }
        for key, value in values.items():
            existing = self._derived_cache.get(key)
            if existing is not None and existing != value:
                raise ValueError("ScenarioSet already has different market-cache provenance.")
            self._derived_cache[key] = value

    def bind_hedge_price_surface(self, surface: object) -> None:
        """Attach one validated hedge surface without changing market content.

        Derived pricing data are deliberately excluded from the market-path
        fingerprint.  The surface performs the reverse validation against this
        exact path count, order, horizon and fingerprint before it is stored.
        """
        validator = getattr(surface, "validate_against", None)
        if validator is None or not callable(validator):
            raise TypeError("Hedge price surface must provide validate_against().")
        validator(self)
        key = ("hedge_price_surface",)
        existing = self._derived_cache.get(key)
        if existing is not None and existing is not surface:
            raise ValueError("ScenarioSet already has a different hedge surface.")
        self._derived_cache[key] = surface

    def money_market_accumulation(self, start_step: int, end_step: int) -> Array:
        """Pathwise accumulation of the continuously rolled AUD overnight account.

        ``discount`` is constructed from the simulated integral of the short
        rate.  Its reciprocal ratio is therefore the stochastic money-market
        accumulation over the requested interval.  This is the daily-roll
        economic equivalent on the engine's monthly cashflow grid and is
        independent of every equity or Reference-Fund return.
        """
        for name, step in (("start_step", start_step), ("end_step", end_step)):
            if isinstance(step, bool) or not isinstance(step, (int, np.integer)):
                raise ValueError(f"{name} must be an integer scenario-grid index.")
            if step < 0 or step > self.n_steps:
                raise ValueError(f"{name} must be a valid scenario-grid index.")
        if end_step < start_step:
            raise ValueError("end_step must not precede start_step.")
        return self.discount[:, start_step] / np.maximum(
            self.discount[:, end_step], 1e-300,
        )

    # ---------------- pathwise term structure (MVA, annuity factors) ------ #

    def zero_rate(self, step: int, tenor: float) -> Array:
        """Pathwise zero rate z_t(tenor), annually compounded, at grid step."""
        t = float(self.times[step])
        if not self.stochastic_rates:
            z_cc = self.config.curve.forward_zero(t, t + max(tenor, 1e-6))
            z = np.full(self.n_paths, np.expm1(z_cc))
            return z
        hw = self.config.hull_white
        curve = self.config.curve
        a, sig = hw.mean_reversion, hw.sigma_r
        b = hw.b(tenor)
        f0t = curve.instantaneous_forward(t)
        p0 = curve.forward_df(t, t + tenor)
        r_t = self.short_rate[:, step]
        ln_p = (np.log(p0) + b * (f0t - r_t)
                - sig ** 2 / (4.0 * a) * (1.0 - np.exp(-2.0 * a * t)) * b ** 2)
        z_cc = -ln_p / max(tenor, 1e-6)
        return np.expm1(z_cc)

    def zero_bond_price(self, step: int, tenor: float) -> Array:
        """Pathwise price of an AUD zero-coupon bond maturing in ``tenor``.

        Prices are derived from the same Hull-White term structure used by the
        scenario set.  This is the sole building block for the generic
        product's nominal Australian-government bond sleeve.
        """
        if isinstance(step, bool) or not isinstance(step, (int, np.integer)) \
                or step < 0 or step > self.n_steps:
            raise ValueError("step must be a valid scenario-grid index.")
        if not np.isfinite(tenor) or tenor < 0.0:
            raise ValueError("tenor must be finite and non-negative.")
        if tenor == 0.0:
            return np.ones(self.n_paths)
        return np.exp(-float(tenor) * np.log1p(self.zero_rate(step, tenor)))

    def rolling_zero_bond_index(self, tenor: float = 5.0) -> Array:
        """Monthly total-return index of a constant-tenor zero-bond sleeve.

        During month ``k`` the bond bought at the previous month end ages by
        one grid interval.  It is valued first and only then rolled into a new
        ``tenor``-year bond.  The return therefore contains carry, price change
        and roll-down without a short-rate fallback.
        """
        if not np.isfinite(tenor) or tenor <= self.dt:
            raise ValueError("Bond tenor must exceed one monthly grid interval.")
        cache_key = ("rolling_zero_bond_index", float(tenor))
        cached = self._derived_cache.get(cache_key)
        if cached is not None:
            return cached
        out = np.ones((self.n_paths, self.n_steps + 1))
        price_at_purchase = self.zero_bond_price(0, tenor)
        remaining = float(tenor) - self.dt
        for step in range(1, self.n_steps + 1):
            price_before_roll = self.zero_bond_price(step, remaining)
            monthly_return = np.divide(
                price_before_roll,
                np.maximum(price_at_purchase, 1e-300),
            ) - 1.0
            out[:, step] = out[:, step - 1] * (1.0 + monthly_return)
            price_at_purchase = self.zero_bond_price(step, tenor)
        out.flags.writeable = False
        self._derived_cache[cache_key] = out
        return out

    def monthly_rebalanced_reference_fund_index(
            self, equity_index: Index = Index.GLOBAL_EQUITY,
            equity_weight: float = 0.30, bond_tenor: float = 5.0) -> Array:
        """Index of the generic monthly rebalanced equity/bond reference fund."""
        equity_index = Index(equity_index)
        if not np.isfinite(equity_weight) or not 0.0 <= equity_weight <= 1.0:
            raise ValueError("equity_weight must be in [0, 1].")
        cache_key = (
            "monthly_rebalanced_reference_fund_index",
            equity_index.value,
            float(equity_weight),
            float(bond_tenor),
        )
        cached = self._derived_cache.get(cache_key)
        if cached is not None:
            return cached
        bond = self.rolling_zero_bond_index(bond_tenor)
        equity = self.index_levels[equity_index]
        out = np.ones_like(equity)
        w_equity = float(equity_weight)
        for step in range(1, self.n_steps + 1):
            r_equity = equity[:, step] / equity[:, step - 1] - 1.0
            r_bond = bond[:, step] / bond[:, step - 1] - 1.0
            r_fund = w_equity * r_equity + (1.0 - w_equity) * r_bond
            out[:, step] = out[:, step - 1] * (1.0 + r_fund)
        out.flags.writeable = False
        self._derived_cache[cache_key] = out
        return out

    def reference_fund_effective_vol(
            self, step: int, horizon: float = 1.0,
            equity_index: Index = Index.GLOBAL_EQUITY,
            equity_weight: float = 0.30, bond_tenor: float = 5.0) -> Array:
        """Moment-matched option volatility for the complete reference fund.

        The fund's rolling-bond diffusion is combined with the zero-bond
        numeraire volatility over the option horizon.  This generalises the
        Merton/Hull-White adjustment in :meth:`effective_bs_vol`; in particular
        ``equity_weight=1`` reduces to that stochastic-rate adjustment.  No
        separate volatility surface or bond parameter is introduced.
        """
        equity_index = Index(equity_index)
        if not np.isfinite(horizon) or horizon <= 0.0:
            raise ValueError("horizon must be positive and finite.")
        if not np.isfinite(equity_weight) or not 0.0 <= equity_weight <= 1.0:
            raise ValueError("equity_weight must be in [0, 1].")
        if self.variance is None:
            sigma_equity = np.full(
                self.n_paths, self.config.equity[equity_index].sigma)
        else:
            hp = self.config.heston[equity_index]
            expected_var = hp.expected_integrated_variance(
                self.variance[equity_index][:, step], horizon)
            sigma_equity = np.sqrt(np.maximum(expected_var, 1e-12))
        w = float(equity_weight)
        equity_loading = w * sigma_equity
        total_variance = equity_loading ** 2 * float(horizon)
        if self.stochastic_rates:
            hw = self.config.hull_white
            a = hw.mean_reversion
            sigma_r = hw.sigma_r
            rho = hw.rho_sr[equity_index]
            T = float(horizon)
            B_T = float(hw.b(T))
            # Integrals from 0..T of B(s) and B(s)^2.
            integral_B = (T - B_T) / a
            integral_B2 = (
                T - 2.0 * B_T
                + (1.0 - np.exp(-2.0 * a * T)) / (2.0 * a)
            ) / (a ** 2)
            # Reference-fund instantaneous rate loading is
            # -(1-w) B(5) sigma_r.  Relative to the T-bond numeraire the
            # loading is [B(s) - (1-w)B(5)] sigma_r.
            rolling_bond_loading = (1.0 - w) * float(hw.b(float(bond_tenor)))
            integral_rate_loading = integral_B - rolling_bond_loading * T
            integral_rate_loading_sq = (
                integral_B2
                - 2.0 * rolling_bond_loading * integral_B
                + rolling_bond_loading ** 2 * T
            )
            total_variance = (
                total_variance
                + sigma_r ** 2 * integral_rate_loading_sq
                + 2.0 * rho * equity_loading * sigma_r
                * integral_rate_loading
            )
        return np.sqrt(np.maximum(total_variance, 1e-12) / float(horizon))

    def effective_bs_vol(self, index: Index, step: int, horizon: float = 1.0) -> Array:
        """Model-consistent effective BS volatility for a `horizon`-year option.

        * BS: constant sigma.
        * Heston: sqrt of expected integrated variance (conditional on v_t).
        * (BS-)HW: Merton adjustment for stochastic rates.
        Combined Heston-HW: both effects.
        """
        cfg = self.config
        if self.variance is not None:
            v_t = self.variance[index][:, step]
            hp = cfg.heston[index]
            var_eq = np.asarray(hp.expected_integrated_variance(v_t, horizon), dtype=float)
            sig_eq_sq = var_eq
            rho = float(cfg.hull_white.rho_sr.get(index, 0.0))
            sig_for_cross = np.sqrt(np.maximum(var_eq, 1e-12))
        else:
            sig = cfg.equity[index].sigma
            sig_eq_sq = np.full(self.n_paths, sig ** 2)
            rho = float(cfg.hull_white.rho_sr.get(index, 0.0))
            sig_for_cross = np.full(self.n_paths, sig)
        if not self.stochastic_rates:
            return np.sqrt(sig_eq_sq)
        a = cfg.hull_white.mean_reversion
        sr = cfg.hull_white.sigma_r
        T = horizon
        B = (1.0 - np.exp(-a * T)) / a
        var_r = sr ** 2 / a ** 2 * (T - 2.0 * B + (1.0 - np.exp(-2.0 * a * T)) / (2.0 * a))
        cross = 2.0 * rho * sr / a * (T - B) * sig_for_cross
        total = sig_eq_sq * T + var_r + cross
        return np.sqrt(np.maximum(total, 1e-10) / T)

    def forward_zero_cc(self, step: int, tenor: float) -> Array:
        """Pathwise continuously compounded zero rate (for option pricing)."""
        z_ann = self.zero_rate(step, tenor)
        return np.log1p(z_ann)

    def rate_gauss_var(self, index: Index, step: int, horizon: float = 1.0) -> Array:
        """Gaussian log-return variance added by Hull-White rates over ``horizon``.

        Variance of the integrated short rate plus the equity-rate covariance
        term (the same ingredients as the Merton adjustment inside
        :meth:`effective_bs_vol`), pathwise; zero for deterministic-rate
        models. Used as the independent Gaussian add-on of the Heston COS
        package pricer. The cross term can make the total slightly negative
        (rho_sr < 0); the magnitude is tiny for realistic calibrations and
        the COS pricer handles it, but extreme parameter sets should fall
        back to the BS branch (``ProjectionConfig.heston_cos = False``).
        """
        if not self.stochastic_rates:
            return np.zeros(self.n_paths)
        cfg = self.config
        rho = float(cfg.hull_white.rho_sr.get(index, 0.0))
        if self.variance is not None:
            hp = cfg.heston[index]
            v_t = self.variance[index][:, step]
            var_eq = np.asarray(hp.expected_integrated_variance(v_t, horizon),
                                dtype=float)
            sig_for_cross = np.sqrt(np.maximum(var_eq, 1e-12))
        else:
            sig_for_cross = np.full(self.n_paths, cfg.equity[index].sigma)
        a = cfg.hull_white.mean_reversion
        sr = cfg.hull_white.sigma_r
        T = horizon
        B = (1.0 - np.exp(-a * T)) / a
        var_r = sr ** 2 / a ** 2 * (T - 2.0 * B + (1.0 - np.exp(-2.0 * a * T)) / (2.0 * a))
        cross = 2.0 * rho * sr / a * (T - B) * sig_for_cross
        return var_r + cross


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def _grid(horizon_years: float) -> Array:
    if not np.isfinite(horizon_years) or horizon_years <= 0.0:
        raise ValueError("horizon_years must be positive and finite.")
    n_float = float(horizon_years) * STEPS_PER_YEAR
    n = int(round(n_float))
    if abs(n_float - n) > 1e-9:
        raise ValueError("horizon_years must fall on the monthly simulation grid.")
    return np.arange(n + 1, dtype=float) / STEPS_PER_YEAR


def _validate_simulation_controls(n_paths: int, seed: int,
                                  substeps: Optional[int] = None) -> None:
    if isinstance(n_paths, bool) or not isinstance(n_paths, (int, np.integer)) \
            or n_paths <= 0:
        raise ValueError("n_paths must be a positive integer.")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a non-negative integer.")
    if substeps is not None and (isinstance(substeps, bool)
                                 or not isinstance(substeps, (int, np.integer))
                                 or substeps <= 0):
        raise ValueError("substeps must be a positive integer.")


def _equity_chol(rho: float, n_idx: int) -> Array:
    corr = np.full((n_idx, n_idx), rho, dtype=float)
    np.fill_diagonal(corr, 1.0)
    return np.linalg.cholesky(corr)


INDICES = (Index.AUS_EQUITY, Index.GLOBAL_EQUITY)


# ---------------------------------------------------------------------------
# Black-Scholes (deterministic rates)
# ---------------------------------------------------------------------------

def simulate_black_scholes(config: ESGConfig, horizon_years: float, n_paths: int,
                           measure: Measure = Measure.RISK_NEUTRAL,
                           seed: int = 2026) -> ScenarioSet:
    _validate_simulation_controls(n_paths, seed)
    times = _grid(horizon_years)
    n_steps = len(times) - 1
    dt = 1.0 / STEPS_PER_YEAR
    rng = np.random.default_rng(seed)
    chol = _equity_chol(config.equity_correlation, len(INDICES))

    fwd = np.array([config.curve.forward_zero(times[k], times[k + 1]) for k in range(n_steps)])
    levels = {ix: np.empty((n_paths, n_steps + 1)) for ix in INDICES}
    for ix in INDICES:
        levels[ix][:, 0] = 1.0

    for k in range(n_steps):
        z = rng.standard_normal((n_paths, len(INDICES))) @ chol.T
        for j, ix in enumerate(INDICES):
            p = config.equity[ix]
            drift = (fwd[k] if measure == Measure.RISK_NEUTRAL else fwd[k] + p.risk_premium)
            mu = (drift - p.dividend_yield - 0.5 * p.sigma ** 2) * dt
            levels[ix][:, k + 1] = levels[ix][:, k] * np.exp(mu + p.sigma * np.sqrt(dt) * z[:, j])

    df = np.asarray(config.curve.df(times), dtype=float)
    discount = np.broadcast_to(df, (n_paths, n_steps + 1)).copy()
    short = np.broadcast_to(config.curve.instantaneous_forward(times), (n_paths, n_steps + 1)).copy()

    return ScenarioSet(config=config, measure=measure, dt=dt, times=times,
                       index_levels=levels, short_rate=short, discount=discount,
                       variance=None, stochastic_rates=False, model_name="black_scholes",
                       seed=int(seed), substeps=None, _copy_inputs=False)


# ---------------------------------------------------------------------------
# Heston (deterministic rates)
# ---------------------------------------------------------------------------

def simulate_heston(config: ESGConfig, horizon_years: float, n_paths: int,
                    measure: Measure = Measure.RISK_NEUTRAL,
                    seed: int = 2026, substeps: int = 4) -> ScenarioSet:
    """Full-truncation Euler for the variance, log-Euler for the equity.

    Substepping (default 4 per month) controls the discretisation bias; the
    martingale test in the suite documents the residual error.
    """
    _validate_simulation_controls(n_paths, seed, substeps)
    times = _grid(horizon_years)
    n_steps = len(times) - 1
    dt = 1.0 / STEPS_PER_YEAR
    h = dt / substeps
    rng = np.random.default_rng(seed)
    chol = _equity_chol(config.equity_correlation, len(INDICES))

    fwd = np.array([config.curve.forward_zero(times[k], times[k + 1]) for k in range(n_steps)])
    levels = {ix: np.empty((n_paths, n_steps + 1)) for ix in INDICES}
    var = {ix: np.empty((n_paths, n_steps + 1)) for ix in INDICES}
    v_cur = {}
    for ix in INDICES:
        levels[ix][:, 0] = 1.0
        var[ix][:, 0] = config.heston[ix].v0
        v_cur[ix] = np.full(n_paths, config.heston[ix].v0)

    log_s = {ix: np.zeros(n_paths) for ix in INDICES}
    for k in range(n_steps):
        for _ in range(substeps):
            z_eq = rng.standard_normal((n_paths, len(INDICES))) @ chol.T
            z_perp = rng.standard_normal((n_paths, len(INDICES)))
            for j, ix in enumerate(INDICES):
                hp = config.heston[ix]
                p = config.equity[ix]
                vp = np.maximum(v_cur[ix], 0.0)
                drift = fwd[k] if measure == Measure.RISK_NEUTRAL else fwd[k] + p.risk_premium
                z_s = z_eq[:, j]
                z_v = hp.rho_sv * z_s + np.sqrt(1.0 - hp.rho_sv ** 2) * z_perp[:, j]
                log_s[ix] += ((drift - p.dividend_yield - 0.5 * vp) * h
                              + np.sqrt(vp * h) * z_s)
                v_cur[ix] = (v_cur[ix] + hp.kappa * (hp.theta - vp) * h
                             + hp.xi * np.sqrt(vp * h) * z_v)
        for ix in INDICES:
            levels[ix][:, k + 1] = np.exp(log_s[ix])
            var[ix][:, k + 1] = np.maximum(v_cur[ix], 0.0)

    df = np.asarray(config.curve.df(times), dtype=float)
    discount = np.broadcast_to(df, (n_paths, n_steps + 1)).copy()
    short = np.broadcast_to(config.curve.instantaneous_forward(times), (n_paths, n_steps + 1)).copy()

    return ScenarioSet(config=config, measure=measure, dt=dt, times=times,
                       index_levels=levels, short_rate=short, discount=discount,
                       variance=var, stochastic_rates=False, model_name="heston",
                       seed=int(seed), substeps=int(substeps), _copy_inputs=False)


# ---------------------------------------------------------------------------
# Hull-White short rate + BS equities (exact joint scheme)
# ---------------------------------------------------------------------------

def _hw_phi(a: float, sig: float, t: float | Array) -> float | Array:
    """phi(t) = (sig^2 / 2a^2) * int_0^t (1 - e^{-as})^2 ds."""
    t = np.asarray(t, dtype=float)
    b = (1.0 - np.exp(-a * t)) / a
    integral = t - 2.0 * b + (1.0 - np.exp(-2.0 * a * t)) / (2.0 * a)
    out = sig ** 2 / (2.0 * a ** 2) * integral
    return float(out) if np.ndim(t) == 0 else out


def simulate_hull_white_bs(config: ESGConfig, horizon_years: float, n_paths: int,
                           measure: Measure = Measure.RISK_NEUTRAL,
                           seed: int = 2026) -> ScenarioSet:
    """Exact joint simulation of (x_t, int x dt, ln S^1, ln S^2).

    x is the zero-mean OU factor of Hull-White fitted to the initial curve;
    the equity log-returns use the pathwise integrated short rate, so
    E[D_T S_T] = S_0 e^{-qT} holds exactly. Under the real-world measure an
    equity risk premium is added (no bond term premium by default).
    """
    _validate_simulation_controls(n_paths, seed)
    hw = config.hull_white
    a, sig_r = hw.mean_reversion, hw.sigma_r
    times = _grid(horizon_years)
    n_steps = len(times) - 1
    dt = 1.0 / STEPS_PER_YEAR
    rng = np.random.default_rng(seed)

    e1 = np.exp(-a * dt)
    B = (1.0 - e1) / a
    v_x = sig_r ** 2 * (1.0 - e1 ** 2) / (2.0 * a)
    v_y = sig_r ** 2 / a ** 2 * (dt - 2.0 * B + (1.0 - e1 ** 2) / (2.0 * a))
    c_xy = sig_r ** 2 / (2.0 * a ** 2) * (1.0 - e1) ** 2

    sig_s = {ix: config.equity[ix].sigma for ix in INDICES}
    rho_sr = {ix: float(hw.rho_sr.get(ix, 0.0)) for ix in INDICES}
    rho_ss = config.equity_correlation

    # Covariance of [x', Y, E_aus, E_glob] per step (E_i = sig_i * dW_i shocks)
    n_dim = 2 + len(INDICES)
    cov = np.zeros((n_dim, n_dim))
    cov[0, 0] = v_x
    cov[1, 1] = v_y
    cov[0, 1] = cov[1, 0] = c_xy
    for j, ix in enumerate(INDICES):
        s = sig_s[ix]
        cov[0, 2 + j] = cov[2 + j, 0] = rho_sr[ix] * s * sig_r * B
        cov[1, 2 + j] = cov[2 + j, 1] = rho_sr[ix] * s * sig_r * (dt - B) / a
        cov[2 + j, 2 + j] = s ** 2 * dt
    for j1 in range(len(INDICES)):
        for j2 in range(j1 + 1, len(INDICES)):
            c = rho_ss * sig_s[INDICES[j1]] * sig_s[INDICES[j2]] * dt
            cov[2 + j1, 2 + j2] = cov[2 + j2, 2 + j1] = c
    # guard tiny negative eigenvalues from float noise
    chol = np.linalg.cholesky(cov + 1e-16 * np.eye(n_dim))

    # deterministic pieces
    ln_p_step = np.array([np.log(config.curve.forward_df(times[k], times[k + 1]))
                          for k in range(n_steps)])
    phi = _hw_phi(a, sig_r, times)
    alpha = (np.asarray(config.curve.instantaneous_forward(times), dtype=float)
             + sig_r ** 2 / (2.0 * a ** 2) * (1.0 - np.exp(-a * times)) ** 2)

    x = np.zeros(n_paths)
    int_r = np.zeros(n_paths)
    log_s = {ix: np.zeros(n_paths) for ix in INDICES}

    levels = {ix: np.empty((n_paths, n_steps + 1)) for ix in INDICES}
    short = np.empty((n_paths, n_steps + 1))
    discount = np.empty((n_paths, n_steps + 1))
    for ix in INDICES:
        levels[ix][:, 0] = 1.0
    short[:, 0] = alpha[0]
    discount[:, 0] = 1.0

    for k in range(n_steps):
        z = rng.standard_normal((n_paths, n_dim)) @ chol.T
        x_new = x * e1 + z[:, 0]
        y = x * B + z[:, 1]                              # int_t^{t+dt} x ds
        int_alpha = -ln_p_step[k] + (phi[k + 1] - phi[k])  # int alpha ds
        int_r_step = y + int_alpha
        int_r += int_r_step
        for j, ix in enumerate(INDICES):
            p = config.equity[ix]
            prem = 0.0 if measure == Measure.RISK_NEUTRAL else p.risk_premium * dt
            log_s[ix] += (int_r_step + prem - p.dividend_yield * dt
                          - 0.5 * p.sigma ** 2 * dt + z[:, 2 + j])
            levels[ix][:, k + 1] = np.exp(log_s[ix])
        x = x_new
        short[:, k + 1] = alpha[k + 1] + x
        discount[:, k + 1] = np.exp(-int_r)

    return ScenarioSet(config=config, measure=measure, dt=dt, times=times,
                       index_levels=levels, short_rate=short, discount=discount,
                       variance=None, stochastic_rates=True, model_name="hull_white_bs",
                       seed=int(seed), substeps=None, _copy_inputs=False)


# ---------------------------------------------------------------------------
# Heston + Hull-White (hybrid scheme)
# ---------------------------------------------------------------------------

def simulate_heston_hull_white(config: ESGConfig, horizon_years: float, n_paths: int,
                               measure: Measure = Measure.RISK_NEUTRAL,
                               seed: int = 2026, substeps: int = 4) -> ScenarioSet:
    """Heston equities with a Hull-White short rate.

    Hybrid scheme: the OU rate factor is simulated exactly per substep, the
    integrated rate by trapezoid, variance by full-truncation Euler, equity by
    log-Euler. Correlations: equity-vol (per index), equity-rate, equity-equity;
    rate-vol is explicitly orthogonalised to zero.
    """
    _validate_simulation_controls(n_paths, seed, substeps)
    hw = config.hull_white
    a, sig_r = hw.mean_reversion, hw.sigma_r
    times = _grid(horizon_years)
    n_steps = len(times) - 1
    dt = 1.0 / STEPS_PER_YEAR
    h = dt / substeps
    rng = np.random.default_rng(seed)

    e1 = np.exp(-a * h)
    sd_x = sig_r * np.sqrt((1.0 - e1 ** 2) / (2.0 * a))

    # Correlation matrix for [z_r, z_s_aus, z_s_glob] (variance shocks built
    # from z_s and independent normals via rho_sv).
    rho_ss = config.equity_correlation
    rho_sr = {ix: float(hw.rho_sr.get(ix, 0.0)) for ix in INDICES}
    corr = np.array([
        [1.0, rho_sr[INDICES[0]], rho_sr[INDICES[1]]],
        [rho_sr[INDICES[0]], 1.0, rho_ss],
        [rho_sr[INDICES[1]], rho_ss, 1.0],
    ])
    chol = np.linalg.cholesky(corr + 1e-12 * np.eye(3))

    sub_times = np.linspace(0.0, times[-1], n_steps * substeps + 1)
    alpha = (np.asarray(config.curve.instantaneous_forward(sub_times), dtype=float)
             + sig_r ** 2 / (2.0 * a ** 2) * (1.0 - np.exp(-a * sub_times)) ** 2)

    x = np.zeros(n_paths)
    int_r = np.zeros(n_paths)
    log_s = {ix: np.zeros(n_paths) for ix in INDICES}
    v_cur = {ix: np.full(n_paths, config.heston[ix].v0) for ix in INDICES}

    levels = {ix: np.empty((n_paths, n_steps + 1)) for ix in INDICES}
    var = {ix: np.empty((n_paths, n_steps + 1)) for ix in INDICES}
    short = np.empty((n_paths, n_steps + 1))
    discount = np.empty((n_paths, n_steps + 1))
    for ix in INDICES:
        levels[ix][:, 0] = 1.0
        var[ix][:, 0] = config.heston[ix].v0
    short[:, 0] = alpha[0]
    discount[:, 0] = 1.0

    idx_sub = 0
    for k in range(n_steps):
        for _ in range(substeps):
            z = rng.standard_normal((n_paths, 3)) @ chol.T
            z_vperp = rng.standard_normal((n_paths, len(INDICES)))
            r_old = alpha[idx_sub] + x
            x = x * e1 + sd_x * z[:, 0]
            idx_sub += 1
            r_new = alpha[idx_sub] + x
            r_avg = 0.5 * (r_old + r_new)
            int_r += r_avg * h
            for j, ix in enumerate(INDICES):
                hp = config.heston[ix]
                p = config.equity[ix]
                vp = np.maximum(v_cur[ix], 0.0)
                prem = 0.0 if measure == Measure.RISK_NEUTRAL else p.risk_premium
                z_s = z[:, 1 + j]
                # Preserve Corr(z_v,z_s)=rho_sv while enforcing
                # Corr(z_v,z_r)=0.  The previous construction inherited
                # rho_sv*rho_sr rate-variance correlation despite documenting
                # it as zero.
                c_sr = rho_sr[ix]
                denom = 1.0 - c_sr ** 2
                a_sv = hp.rho_sv / denom
                b_sr = -hp.rho_sv * c_sr / denom
                residual = max(1.0 - hp.rho_sv ** 2 / denom, 0.0)
                z_v = (a_sv * z_s + b_sr * z[:, 0]
                       + np.sqrt(residual) * z_vperp[:, j])
                log_s[ix] += ((r_avg + prem - p.dividend_yield - 0.5 * vp) * h
                              + np.sqrt(vp * h) * z_s)
                v_cur[ix] = (v_cur[ix] + hp.kappa * (hp.theta - vp) * h
                             + hp.xi * np.sqrt(vp * h) * z_v)
        for ix in INDICES:
            levels[ix][:, k + 1] = np.exp(log_s[ix])
            var[ix][:, k + 1] = np.maximum(v_cur[ix], 0.0)
        short[:, k + 1] = alpha[idx_sub] + x
        discount[:, k + 1] = np.exp(-int_r)

    return ScenarioSet(config=config, measure=measure, dt=dt, times=times,
                       index_levels=levels, short_rate=short, discount=discount,
                       variance=var, stochastic_rates=True, model_name="heston_hull_white",
                       seed=int(seed), substeps=int(substeps), _copy_inputs=False)


# ---------------------------------------------------------------------------
# Model dispatcher
# ---------------------------------------------------------------------------

MODELS = {
    "black_scholes": simulate_black_scholes,
    "heston": simulate_heston,
    "hull_white_bs": simulate_hull_white_bs,
    "heston_hull_white": simulate_heston_hull_white,
}


def simulate(model: str, config: ESGConfig, horizon_years: float, n_paths: int,
             measure: Measure = Measure.RISK_NEUTRAL, seed: int = 2026,
             **kwargs) -> ScenarioSet:
    if model not in MODELS:
        raise ValueError(f"Unknown model '{model}'. Available: {sorted(MODELS)}")
    _validate_simulation_controls(n_paths, seed)
    measure = Measure(measure)
    return MODELS[model](config, horizon_years, int(n_paths), measure=measure,
                         seed=seed, **kwargs)
