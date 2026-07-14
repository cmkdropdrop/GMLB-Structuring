"""Crediting mechanics of the Protected Investment Options.

Point-to-point annual crediting (PDS section 5.3):

Total Protection:      credit = min(max(R, 0), cap)
Partial Protection 10: credit = min(R, cap)            if R >= 0
                       credit = min(0, R + 10%)        if R <  0

In option terms (per unit of Investment Value, R = S_T/S_0 - 1):

* Total Protection  = Call(K=1) - Call(K=1+cap)                (bull call spread)
* Partial 10        = Call(K=1) - Call(K=1+cap) - Put(K=0.90)  (spread - OTM put)

The insurer's standard Total-Protection hedge uses the same bull call spread:
the cap call is sold.  An explicit alternative keeps that cap leg instead,
using the uncapped long Call(K=1); its payoff above the customer cap is then a
separate insurer hedge gain.  This hedge choice does not alter the customer's
``credited_return``.

These static replications drive

* the Daily Value Adjustment (intra-year market value of the crediting
  package plus the zero-bond leg, PDS section 7),
* the crediting margin (option budget vs. forward yield) used in the
  market-consistent P&L decomposition,
* fair-cap solving (setting caps so the package price matches a budget).

Black-Scholes closed forms are exact under the BS and BS-Hull-White ESGs
(with the appropriate integrated volatility). Under the Heston ESGs the
packages are priced with the COS method of Fang/Oosterlee (2008) on the
Heston characteristic function (following Alonso-Garcia/Wood/Ziveyi 2017,
who use the same machinery for crediting-style payoffs): a flat effective
volatility cannot capture the return-variance correlation (skew), which is
worth O(30bp p.a.) on a Total-Protection cap package and would otherwise
leak into the crediting margin (see test_heston_cos.py). Stochastic-rate
add-ons (Heston-Hull-White) enter the COS pricer as an independent Gaussian
variance component, consistent with the Merton adjustment used in the BS
branch. ``hedge_vol_spread`` is applied only in the projection's separate
quote repricing used to derive non-negative execution costs; it does not
contaminate the contractual DVA mid value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import brentq
from scipy.stats import norm

from .product import InvestmentOption, Protection

if TYPE_CHECKING:   # avoid a circular import at runtime
    from .esg import HestonParams

Array = NDArray[np.float64]

PARTIAL_BUFFER = 0.10


class HedgeCapLegMode(str, Enum):
    """Whether the insurer sells the call leg that finances the crediting cap."""

    SOLD = "sold"
    NOT_SOLD = "not_sold"


def _hedge_cap_leg_mode(mode: HedgeCapLegMode | str) -> HedgeCapLegMode:
    try:
        return HedgeCapLegMode(mode)
    except (TypeError, ValueError) as exc:
        raise ValueError("Unknown hedge cap-leg mode.") from exc


def _crediting_terms(protection: Protection, cap: float,
                     buffer: float) -> tuple[Protection, float, float]:
    try:
        protection = Protection(protection)
    except (TypeError, ValueError) as exc:
        raise ValueError("Unknown protection type.") from exc
    cap = float(cap)
    buffer = float(buffer)
    if not np.isfinite(cap) or cap < 0.0:
        raise ValueError("cap must be finite and non-negative.")
    if not np.isfinite(buffer) or not 0.0 <= buffer < 1.0:
        raise ValueError("buffer must be finite and in [0, 1).")
    return protection, cap, buffer


# ---------------------------------------------------------------------------
# Payoffs
# ---------------------------------------------------------------------------

def credited_return(index_return: float | Array, protection: Protection,
                    cap: float, buffer: float = PARTIAL_BUFFER) -> float | Array:
    """Annual credited return for a given point-to-point index return."""
    protection, cap, buffer = _crediting_terms(protection, cap, buffer)
    r = np.asarray(index_return, dtype=float)
    if not np.all(np.isfinite(r)):
        raise ValueError("index_return must be finite.")
    if protection == Protection.TOTAL:
        out = np.minimum(np.maximum(r, 0.0), cap)
    else:
        out = np.where(r >= 0.0, np.minimum(r, cap), np.minimum(0.0, r + buffer))
    return float(out) if np.ndim(index_return) == 0 else out


# ---------------------------------------------------------------------------
# Black-Scholes vanilla building blocks (on the gross return X = S_T / S_0)
# ---------------------------------------------------------------------------

def _bs_call(x0: float | Array, k: float, tau: float, r: float | Array,
             q: float, sigma: float | Array) -> float | Array:
    """BS call on the return ratio with spot ``x0`` (=S_t/S_anniv), strike k.

    Vectorised over spot, rate and volatility (pathwise Heston/HW inputs).
    """
    x0 = np.asarray(x0, dtype=float)
    r = np.asarray(r, dtype=float)
    if tau <= 0.0:
        return np.maximum(x0 - k, 0.0)
    vol = np.maximum(np.asarray(sigma, dtype=float), 1e-8) * np.sqrt(tau)
    fwd = x0 * np.exp((r - q) * tau)
    d1 = (np.log(fwd / k)) / vol + 0.5 * vol
    d2 = d1 - vol
    return np.exp(-r * tau) * (fwd * norm.cdf(d1) - k * norm.cdf(d2))


def _bs_put(x0: float | Array, k: float, tau: float, r: float | Array,
            q: float, sigma: float | Array) -> float | Array:
    x0 = np.asarray(x0, dtype=float)
    r = np.asarray(r, dtype=float)
    if tau <= 0.0:
        return np.maximum(k - x0, 0.0)
    call = _bs_call(x0, k, tau, r, q, sigma)
    return call - x0 * np.exp(-q * tau) + k * np.exp(-np.asarray(r) * tau)


def crediting_package_value(x0: float | Array, protection: Protection, cap: float,
                            tau: float, r: float | Array, q: float, sigma: float,
                            buffer: float = PARTIAL_BUFFER) -> float | Array:
    """PV at time-to-anniversary ``tau`` of the credited-return payoff.

    ``x0`` is the current index level divided by the anniversary-start level.
    Returns the value of the *credit* (can be negative for Partial Protection).
    """
    protection, cap, buffer = _crediting_terms(protection, cap, buffer)
    call_spread = (_bs_call(x0, 1.0, tau, r, q, sigma)
                   - _bs_call(x0, 1.0 + cap, tau, r, q, sigma))
    if protection == Protection.TOTAL:
        return call_spread
    return call_spread - _bs_put(x0, 1.0 - buffer, tau, r, q, sigma)


def hedge_option_package_value(
        x0: float | Array, cap: float, tau: float, r: float | Array,
        q: float, sigma: float | Array,
        cap_leg_mode: HedgeCapLegMode | str = HedgeCapLegMode.SOLD,
) -> float | Array:
    """PV of the insurer's Total-Protection option hedge per unit notional.

    With the standard ``SOLD`` cap leg, the package is
    ``Call(K=1) - Call(K=1+cap)`` on the gross return.  With ``NOT_SOLD`` it is
    the uncapped ``Call(K=1)``.  Inputs may be pathwise arrays and follow the
    vectorisation of the module's Black-Scholes primitives.
    """
    _, cap, _ = _crediting_terms(Protection.TOTAL, cap, PARTIAL_BUFFER)
    mode = _hedge_cap_leg_mode(cap_leg_mode)
    x = np.asarray(x0, dtype=float)
    rates = np.asarray(r, dtype=float)
    vols = np.asarray(sigma, dtype=float)
    tau = float(tau)
    q = float(q)
    if not np.all(np.isfinite(x)) or np.any(x < 0.0):
        raise ValueError("x0 must be finite and non-negative.")
    if not np.all(np.isfinite(rates)):
        raise ValueError("r must be finite.")
    if not np.all(np.isfinite(vols)) or np.any(vols < 0.0):
        raise ValueError("sigma must be finite and non-negative.")
    if not np.isfinite(tau) or tau < 0.0:
        raise ValueError("tau must be finite and non-negative.")
    if not np.isfinite(q):
        raise ValueError("q must be finite.")

    long_call = _bs_call(x, 1.0, tau, rates, q, vols)
    if mode == HedgeCapLegMode.SOLD:
        out = long_call - _bs_call(x, 1.0 + cap, tau, rates, q, vols)
    else:
        out = long_call
    scalar = np.ndim(x0) == 0 and np.ndim(r) == 0 and np.ndim(sigma) == 0
    return float(out) if scalar else np.asarray(out, dtype=float)


def retained_excess_return(
        index_return: float | Array, cap: float,
        cap_leg_mode: HedgeCapLegMode | str = HedgeCapLegMode.SOLD,
) -> float | Array:
    """Insurer payoff above the customer cap when the cap leg is not sold.

    The standard sold-leg strategy has no retained excess.  The alternative
    returns ``max(index_return - cap, 0)`` without changing customer crediting.
    """
    _, cap, _ = _crediting_terms(Protection.TOTAL, cap, PARTIAL_BUFFER)
    mode = _hedge_cap_leg_mode(cap_leg_mode)
    returns = np.asarray(index_return, dtype=float)
    if not np.all(np.isfinite(returns)):
        raise ValueError("index_return must be finite.")
    out = (np.zeros_like(returns) if mode == HedgeCapLegMode.SOLD
           else np.maximum(returns - cap, 0.0))
    return float(out) if np.ndim(index_return) == 0 else out


# ---------------------------------------------------------------------------
# Daily Value Adjustment
# ---------------------------------------------------------------------------

def intra_year_value_factor(x0: float | Array, protection: Protection, cap: float,
                            tau: float, r: float | Array, q: float, sigma: float,
                            buffer: float = PARTIAL_BUFFER) -> float | Array:
    """DVA-consistent intra-year value of 1 unit of anniversary-start IV.

    Replicating-portfolio view (PDS section 7): the unit of Investment Value is
    a zero bond maturing at the next anniversary plus the crediting package,

        value(t) = P(t, T_anniv) + V_package(t).

    At the anniversary this converges to ``1 + credited return``. The factor
    can be above or below the plain pro-rata index reading, exactly like the
    derivative-value component of the contractual DVA.  The PDS pro-rata
    protection minimum and Fixed-Return branch must be applied in a separate
    contractual-value layer and are intentionally not hidden in this hedge
    pricer.
    """
    zcb = np.exp(-np.asarray(r, dtype=float) * max(tau, 0.0))
    return zcb + crediting_package_value(x0, protection, cap, tau, r, q, sigma, buffer)


# ---------------------------------------------------------------------------
# Heston COS pricing of the crediting packages (Fang/Oosterlee 2008)
# ---------------------------------------------------------------------------

def _heston_cf(u: Array, tau: float, v_t: Array, kappa: float, theta: float,
               xi: float, rho: float) -> Array:
    """CF of the *driftless* Heston log return over ``tau`` given ``v_t``.

    Returns E[exp(iu Y)] for Y = ln(S_{t+tau}/S_t) - (r - q) tau, i.e. the
    stochastic component including the -0.5 int v ds compensator, in the
    numerically stable "little Heston trap" formulation (Albrecher et al.).
    ``u``: shape (N,); ``v_t``: shape (n,); output shape (n, N).
    """
    u = np.asarray(u, dtype=complex)[None, :]
    v = np.asarray(v_t, dtype=float)[:, None]
    beta = kappa - 1j * rho * xi * u
    d = np.sqrt(beta ** 2 + xi ** 2 * (1j * u + u ** 2))
    g = (beta - d) / (beta + d)
    e_dt = np.exp(-d * tau)
    frac = (1.0 - g * e_dt) / (1.0 - g)
    C = kappa / xi ** 2 * ((beta - d) * tau - 2.0 * np.log(frac))
    D = (beta - d) / xi ** 2 * (1.0 - e_dt) / (1.0 - g * e_dt)
    return np.exp(C * theta + D * v)


def _cos_chi_psi(u: Array, a: float, b: float, c: float, d: float) -> tuple:
    """COS cosine-series coefficients of e^y and 1 on [c, d] within [a, b]."""
    k_ua = u * (c - a)
    k_ub = u * (d - a)
    chi = (np.cos(k_ub) * np.exp(d) - np.cos(k_ua) * np.exp(c)
           + u * (np.sin(k_ub) * np.exp(d) - np.sin(k_ua) * np.exp(c))) / (1.0 + u ** 2)
    psi = np.empty_like(u)
    psi[0] = d - c
    psi[1:] = (np.sin(k_ub[1:]) - np.sin(k_ua[1:])) / u[1:]
    return chi, psi


def _heston_puts_cos(x0: Array, strikes: tuple, tau: float, r: Array, q: float,
                     v_t: Array, hp: "HestonParams", w: Array,
                     n_terms: int = 128, trunc_l: float = 13.0) -> list:
    """COS puts on the gross return X for several strikes at once.

    Works in the log level y = ln(X_T) so the (expensive) characteristic
    function and phase factors are evaluated once and shared across strikes;
    only the cheap payoff coefficients (K psi - chi over [a, ln K]) differ.
    ``w`` adds an independent Gaussian log-return variance
    (martingale-preserving): Hull-White rate adjustment / hedge-vol spread.
    Returns a list of price arrays, one per strike.
    """
    kp, th, xi, rho = hp.kappa, hp.theta, hp.xi, hp.rho_sv
    ew = (1.0 - np.exp(-kp * tau)) / (kp * tau)
    int_var = (th + (v_t - th) * ew) * tau + np.maximum(w, 0.0)
    mu = np.log(x0) + (r - q) * tau           # y-location before -v/2 drift
    sd_hi = float(np.sqrt(np.max(int_var)))
    ln_ks = [float(np.log(k)) for k in strikes]
    a = min(float(np.min(mu) - 0.5 * np.max(int_var)), min(ln_ks)) \
        - trunc_l * max(sd_hi, 1e-4)
    b = max(float(np.max(mu)), max(ln_ks)) + trunc_l * max(sd_hi, 1e-4)

    n = np.arange(n_terms, dtype=float)
    u = n * np.pi / (b - a)
    cf = _heston_cf(u, tau, v_t, kp, th, xi, rho)
    # drift/level shift exp(iu (mu - a)) and Gaussian add-on
    phase = np.exp(1j * np.outer(mu - a, u)
                   - 0.5 * w[:, None] * (u[None, :] ** 2 + 1j * u[None, :]))
    series = np.real(cf * phase)              # (n_paths, n_terms)
    disc = np.exp(-r * tau)

    out = []
    for k_strike, ln_k in zip(strikes, ln_ks):
        d = min(max(ln_k, a), b)
        chi, psi = _cos_chi_psi(u, a, b, a, d)
        v_put = 2.0 / (b - a) * (float(k_strike) * psi - chi)
        v_put[0] *= 0.5                       # first term half weight
        out.append(np.maximum(disc * (series @ v_put), 0.0))
    return out


def heston_put_cos(x0: float | Array, k: float, tau: float, r: float | Array,
                   q: float, v_t: Array, hp: "HestonParams",
                   extra_gauss_var: float | Array = 0.0,
                   n_terms: int = 128, trunc_l: float = 13.0) -> Array:
    """European put on the gross return X (spot ratio ``x0``, strike ``k``)
    under Heston given the pathwise variance state ``v_t``, via COS.

    Vectorised over paths (x0, r, v_t, extra var); see `_heston_puts_cos`.
    """
    x0 = np.atleast_1d(np.asarray(x0, dtype=float))
    r_in = np.atleast_1d(np.asarray(r, dtype=float))
    v_in = np.atleast_1d(np.asarray(v_t, dtype=float))
    w_in = np.atleast_1d(np.asarray(extra_gauss_var, dtype=float))
    shape = np.broadcast_shapes(x0.shape, r_in.shape, v_in.shape, w_in.shape)
    x0 = np.broadcast_to(x0, shape).astype(float)
    r_arr = np.broadcast_to(r_in, shape).astype(float)
    v_arr = np.broadcast_to(v_in, shape).astype(float)
    w_arr = np.broadcast_to(w_in, shape).astype(float)
    if tau <= 0.0:
        return np.maximum(k - x0, 0.0)
    return _heston_puts_cos(x0, (k,), tau, r_arr, q, v_arr, hp, w_arr,
                            n_terms, trunc_l)[0]


def heston_package_value(x0: float | Array, protection: Protection, cap: float,
                         tau: float, r: float | Array, q: float, v_t: Array,
                         hp: "HestonParams",
                         extra_gauss_var: float | Array = 0.0,
                         buffer: float = PARTIAL_BUFFER) -> Array:
    """PV of the credited-return payoff under Heston (COS, skew-consistent).

    Calls are obtained from COS puts via put-call parity (the COS CF is
    martingale-consistent by construction), so
    Call(1) - Call(1+cap) = Put(1) - Put(1+cap) + cap e^{-r tau}.
    All strikes share one CF evaluation (see `_heston_puts_cos`).
    """
    protection, cap, buffer = _crediting_terms(protection, cap, buffer)
    x0 = np.atleast_1d(np.asarray(x0, dtype=float))
    r_in = np.atleast_1d(np.asarray(r, dtype=float))
    v_in = np.atleast_1d(np.asarray(v_t, dtype=float))
    w_in = np.atleast_1d(np.asarray(extra_gauss_var, dtype=float))
    shape = np.broadcast_shapes(x0.shape, r_in.shape, v_in.shape, w_in.shape)
    x0 = np.broadcast_to(x0, shape).astype(float)
    r_arr = np.broadcast_to(r_in, shape).astype(float)
    v_arr = np.broadcast_to(v_in, shape).astype(float)
    w_arr = np.broadcast_to(w_in, shape).astype(float)
    if tau <= 0.0:
        credit = credited_return(x0 - 1.0, protection, cap, buffer)
        return np.asarray(credit, dtype=float)
    strikes = (1.0, 1.0 + cap) if protection == Protection.TOTAL \
        else (1.0, 1.0 + cap, 1.0 - buffer)
    puts = _heston_puts_cos(x0, strikes, tau, r_arr, q, v_arr, hp, w_arr)
    call_spread = puts[0] - puts[1] + cap * np.exp(-r_arr * tau)
    if protection == Protection.TOTAL:
        return call_spread
    return call_spread - puts[2]


def heston_intra_year_value_factor(x0: float | Array, protection: Protection,
                                   cap: float, tau: float, r: float | Array,
                                   q: float, v_t: Array, hp: "HestonParams",
                                   extra_gauss_var: float | Array = 0.0,
                                   buffer: float = PARTIAL_BUFFER) -> Array:
    """Heston analogue of :func:`intra_year_value_factor` (DVA replication)."""
    zcb = np.exp(-np.asarray(r, dtype=float) * max(tau, 0.0))
    return zcb + heston_package_value(x0, protection, cap, tau, r, q, v_t, hp,
                                      extra_gauss_var, buffer)


# ---------------------------------------------------------------------------
# Cap setting / option budget
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HedgeMarket:
    """Market data used to value the crediting packages for margins/DVA/caps.

    ``sigma`` is the 1y implied (hedge) volatility per index; ``q`` is any
    continuous carry excluded from the referenced return index. The case study's
    return-index default is therefore zero.
    """

    sigma: float = 0.16
    q: float = 0.0

    def __post_init__(self) -> None:
        if not np.isfinite(self.sigma) or self.sigma <= 0.0 \
                or not np.isfinite(self.q) or self.q < 0.0:
            raise ValueError("Hedge sigma must be positive and carry non-negative.")


def fair_cap(protection: Protection, budget: float, r: float, market: HedgeMarket,
             tau: float = 1.0, lo: float = 1e-4, hi: float = 3.0,
             buffer: float = PARTIAL_BUFFER) -> float:
    """Cap such that the package value at anniversary start equals ``budget``.

    ``budget`` is the option spend per unit IV (e.g. forward-yield budget net
    of margin). Raises if the budget is not attainable (e.g. negative budget
    for Total Protection).
    """

    def f(cap: float) -> float:
        return float(crediting_package_value(1.0, protection, cap, tau, r,
                                             market.q, market.sigma, buffer)) - budget

    f_lo, f_hi = f(lo), f(hi)
    if f_lo > 0 and f_hi > 0:
        raise ValueError("Budget below the value of the zero-cap package.")
    if f_lo < 0 and f_hi < 0:
        return hi  # budget above the uncapped package value: cap unbounded
    return float(brentq(f, lo, hi, xtol=1e-8))


def crediting_margin_rate(protection: Protection, cap: float, r_fwd_1y: float,
                          market: HedgeMarket, buffer: float = PARTIAL_BUFFER) -> float:
    """Insurer margin per unit IV from the annual crediting cycle.

    The insurer holds the unit IV in risk-free assets earning the 1y forward
    yield and spends the package premium on the hedge:

        margin = (1 - V_package) * e^{r_fwd} - 1,

    realised at the following anniversary. Zero when caps are set exactly
    budget-neutral; positive when caps are set below the budget-neutral level
    (pricing lever, PDS section 5.5).
    """
    v = float(crediting_package_value(1.0, protection, cap, 1.0, r_fwd_1y,
                                      market.q, market.sigma, buffer))
    return (1.0 - v) * float(np.exp(r_fwd_1y)) - 1.0


def option_cost_table(caps: dict, r: float, markets: dict) -> dict:
    """Package values per option at anniversary start (diagnostics)."""
    out = {}
    for opt, cap in caps.items():
        opt = InvestmentOption(opt)
        mkt: HedgeMarket = markets[opt.index]
        out[opt] = float(crediting_package_value(
            1.0, opt.protection, float(cap), 1.0, r, mkt.q, mkt.sigma))
    return out
