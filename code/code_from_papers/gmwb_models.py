from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Optional, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import brentq, minimize
from scipy.special import gamma as gamma_fn

Array = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]


# ============================================================
# 1) GMWB contract: account dynamics, cashflows and penalties
# ============================================================

@dataclass(frozen=True)
class GMWBContract:
    """
    Guaranteed Minimum Withdrawal Benefit contract.

    W0:
        Initial premium / initial wealth account / initial guarantee account.
    maturity:
        Contract maturity in years.
    events_per_year:
        Withdrawal frequency.
    annual_withdrawal:
        Contractual annual withdrawal. If None, W0 / maturity is used.
    kappa:
        Proportional penalty on withdrawals above the contractual amount G.
        Example: kappa=0.10 means 10% penalty on the excess withdrawal.
    reset_provision:
        If True, excess withdrawals can reset the guarantee account to
        min(A - gamma, max(W - gamma, 0)).
    terminal_penalty:
        If False, no penalty is applied at maturity.
    """

    W0: float = 100.0
    maturity: float = 10.0
    events_per_year: int = 1
    annual_withdrawal: Optional[float] = None
    kappa: float = 0.10
    reset_provision: bool = False
    terminal_penalty: bool = False

    def __post_init__(self) -> None:
        if self.W0 <= 0:
            raise ValueError("W0 must be positive.")
        if self.maturity <= 0:
            raise ValueError("maturity must be positive.")
        if self.events_per_year <= 0:
            raise ValueError("events_per_year must be positive.")
        n_float = self.maturity * self.events_per_year
        if abs(n_float - round(n_float)) > 1e-12:
            raise ValueError("maturity * events_per_year must be an integer.")
        if not (0 <= self.kappa < 1):
            raise ValueError("kappa must be in [0, 1).")

    @property
    def n_events(self) -> int:
        return int(round(self.maturity * self.events_per_year))

    @property
    def dt(self) -> float:
        return 1.0 / self.events_per_year

    @property
    def G(self) -> float:
        annual = self.W0 / self.maturity if self.annual_withdrawal is None else self.annual_withdrawal
        return annual * self.dt


def penalty_cashflow(gamma: float | Array, G: float, kappa: float) -> float | Array:
    """
    Net cashflow received by the policyholder from nominal withdrawal gamma.
    C(gamma) = gamma, if gamma <= G
             = G + (1-kappa) * (gamma-G), otherwise.
    """
    gamma_arr = np.asarray(gamma)
    out = np.where(gamma_arr <= G, gamma_arr, G + (1.0 - kappa) * (gamma_arr - G))
    return float(out) if np.ndim(gamma) == 0 else out


def terminal_cashflow(
    A: float | Array,
    G: float,
    kappa: float,
    terminal_penalty: bool,
) -> float | Array:
    if terminal_penalty:
        return penalty_cashflow(A, G, kappa)
    return A


def after_withdrawal(
    W: float,
    A: float,
    gamma_w: float,
    G: float,
    reset_provision: bool,
) -> Tuple[float, float]:
    """
    Account state immediately after a withdrawal.
    """
    g = min(max(float(gamma_w), 0.0), float(A))
    W_plus = max(W - g, 0.0)

    if reset_provision and g > G:
        A_plus = max(min(A - g, W_plus), 0.0)
    else:
        A_plus = max(A - g, 0.0)

    return W_plus, A_plus


# ============================================================
# 2) Lévy models and risk-neutral characteristic functions
# ============================================================

class LevyModel:
    """
    Risk-neutral log-return characteristic function.

    The method cf(u, dt, r) returns E[exp(i*u*X_dt)]
    for the one-period asset log-return before the VA fee.
    """

    name: str

    def cf(self, u: ComplexArray | Array, dt: float, r: float) -> ComplexArray:
        raise NotImplementedError


@dataclass(frozen=True)
class GBMModel(LevyModel):
    sigma: float = 0.20
    q: float = 0.0
    name: str = "GBM"

    def cf(self, u: ComplexArray | Array, dt: float, r: float) -> ComplexArray:
        u = np.asarray(u, dtype=np.complex128)
        drift = (r - self.q - 0.5 * self.sigma**2) * dt
        var = self.sigma**2 * dt
        return np.exp(1j * u * drift - 0.5 * var * u**2)


@dataclass(frozen=True)
class VGModel(LevyModel):
    sigma: float = 0.1301
    theta: float = -0.3150
    nu: float = 0.1753
    q: float = 0.0
    name: str = "VG"

    def cf(self, u: ComplexArray | Array, dt: float, r: float) -> ComplexArray:
        if 1.0 - self.theta * self.nu - 0.5 * self.sigma**2 * self.nu <= 0:
            raise ValueError("VG martingale correction undefined for these parameters.")

        u = np.asarray(u, dtype=np.complex128)
        jump_cf = (
            1.0
            - 1j * u * self.theta * self.nu
            + 0.5 * self.sigma**2 * self.nu * u**2
        ) ** (-dt / self.nu)

        m = (1.0 / self.nu) * np.log(
            1.0 - self.theta * self.nu - 0.5 * self.sigma**2 * self.nu
        )

        return np.exp(1j * u * (r - self.q + m) * dt) * jump_cf


@dataclass(frozen=True)
class CGMYModel(LevyModel):
    C: float = 0.6817
    G: float = 18.0293
    M: float = 57.6250
    Y: float = 0.8
    sigma: float = 0.0
    q: float = 0.0
    name: str = "CGMY"

    def cf(self, u: ComplexArray | Array, dt: float, r: float) -> ComplexArray:
        if self.M <= 1:
            raise ValueError("CGMY martingale correction needs M > 1.")

        u = np.asarray(u, dtype=np.complex128)
        gam = gamma_fn(-self.Y)

        psi_jump = self.C * gam * (
            (self.M - 1j * u) ** self.Y
            - self.M**self.Y
            + (self.G + 1j * u) ** self.Y
            - self.G**self.Y
        )

        psi_jump_minus_i = self.C * gam * (
            (self.M - 1.0) ** self.Y
            - self.M**self.Y
            + (self.G + 1.0) ** self.Y
            - self.G**self.Y
        )

        drift = r - self.q - 0.5 * self.sigma**2 - psi_jump_minus_i

        return np.exp(
            dt * (1j * u * drift - 0.5 * self.sigma**2 * u**2 + psi_jump)
        )


# ============================================================
# 3) COS density approximation
# ============================================================

def _cos_truncation_interval(
    cf: Callable[[ComplexArray], ComplexArray],
    L: float = 10.0,
    h: float = 2.5e-3,
) -> Tuple[float, float]:
    """
    COS truncation interval [a,b] from numerical cumulants.

    It estimates c1, c2 and c4 from log characteristic function around zero,
    then uses [c1 ± L * sqrt(c2 + sqrt(abs(c4)))].
    """
    xs = np.array([-3, -2, -1, 0, 1, 2, 3], dtype=float) * h
    vals = np.log(cf(xs.astype(np.complex128)))

    real_coef = np.polyfit(xs, vals.real, deg=4)[::-1]
    imag_coef = np.polyfit(xs, vals.imag, deg=4)[::-1]
    coef = real_coef + 1j * imag_coef

    d1 = coef[1]
    d2 = 2.0 * coef[2]
    d4 = 24.0 * coef[4]

    c1 = (d1 / (1j)).real
    c2 = (d2 / ((1j) ** 2)).real
    c4 = (d4 / ((1j) ** 4)).real

    width = L * np.sqrt(max(c2, 1e-14) + np.sqrt(abs(c4)))
    if not np.isfinite(width) or width <= 0:
        width = L * np.sqrt(max(c2, 1e-8))

    return float(c1 - width), float(c1 + width)


def cos_pdf_weights(
    model: LevyModel,
    dt: float,
    r: float,
    n_terms: int = 128,
    n_quad: int = 96,
    L: float = 10.0,
    normalise: bool = True,
) -> Tuple[Array, Array, Tuple[float, float]]:
    """
    Return quadrature nodes y and weights w such that
    E[f(Y)] ≈ sum_j w_j f(y_j).

    The density is represented by a Fourier-cosine expansion.
    """
    cf_dt = lambda u: model.cf(u, dt, r)
    a, b = _cos_truncation_interval(cf_dt, L=L)

    roots, gl_w = np.polynomial.legendre.leggauss(n_quad)
    y = 0.5 * (b - a) * roots + 0.5 * (a + b)
    dy_w = 0.5 * (b - a) * gl_w

    k = np.arange(n_terms, dtype=float)
    u = k * np.pi / (b - a)

    coef = np.real(cf_dt(u) * np.exp(-1j * u * a))
    coef[0] *= 0.5

    angles = np.outer(y - a, u)
    pdf = (2.0 / (b - a)) * (np.cos(angles) @ coef)

    weights = dy_w * pdf
    if normalise:
        s = float(np.sum(weights))
        if abs(s) < 1e-10:
            raise FloatingPointError("COS weights sum close to zero.")
        weights = weights / s

    return y.astype(float), weights.astype(float), (a, b)


# ============================================================
# 4) COS / dynamic programming GMWB pricer
# ============================================================

@dataclass
class COSNumerics:
    w_points: int = 151
    a_points: int = 81
    w_max_mult: float = 5.0
    cos_terms: int = 96
    quad_points: int = 64
    trunc_L: float = 10.0
    withdrawal_grid_size: int = 31
    normalise_density: bool = True


class GMWBCOSPricer:
    """
    Backward GMWB pricer using COS density expansion.

    withdrawal='static':
        gamma = min(G,A) at every non-terminal event.

    withdrawal='dynamic':
        gamma is chosen from a finite grid in [0,A] to maximise
        cashflow + discounted continuation value.

    By default, there is no withdrawal at inception. The first withdrawal
    occurs after one period.
    """

    def __init__(
        self,
        contract: GMWBContract,
        model: LevyModel,
        r: float,
        numerics: COSNumerics = COSNumerics(),
    ) -> None:
        self.contract = contract
        self.model = model
        self.r = float(r)
        self.num = numerics

        self.W_grid = np.linspace(
            0.0,
            contract.W0 * numerics.w_max_mult,
            numerics.w_points,
        )
        self.A_grid = np.linspace(
            0.0,
            contract.W0,
            numerics.a_points,
        )

        self._y, self._yw, self._ab = cos_pdf_weights(
            model=model,
            dt=contract.dt,
            r=self.r,
            n_terms=numerics.cos_terms,
            n_quad=numerics.quad_points,
            L=numerics.trunc_L,
            normalise=numerics.normalise_density,
        )

        self._last_surface: Optional[Array] = None
        self._last_policy: Optional[list[Array]] = None

    def _interp_w(self, row: Array, W_values: Array) -> Array:
        """
        1D interpolation in W with linear extrapolation above W_max.
        """
        Wv = np.maximum(np.asarray(W_values, dtype=float), self.W_grid[0])
        out = np.interp(np.minimum(Wv, self.W_grid[-1]), self.W_grid, row)

        high = Wv > self.W_grid[-1]
        if np.any(high):
            slope = (row[-1] - row[-2]) / (self.W_grid[-1] - self.W_grid[-2])
            out[high] = row[-1] + slope * (Wv[high] - self.W_grid[-1])

        return out

    def _interp_surface(self, V: Array, W_values: Array, A_value: float) -> Array:
        """
        Bilinear interpolation in (A,W); W is vectorised.
        """
        Wv = np.asarray(W_values, dtype=float)
        A = float(np.clip(A_value, self.A_grid[0], self.A_grid[-1]))

        j = int(np.searchsorted(self.A_grid, A, side="right") - 1)
        j = max(0, min(j, len(self.A_grid) - 2))

        a0, a1 = self.A_grid[j], self.A_grid[j + 1]
        wa = 0.0 if a1 == a0 else (A - a0) / (a1 - a0)

        row0 = self._interp_w(V[j], Wv)
        row1 = self._interp_w(V[j + 1], Wv)

        return (1.0 - wa) * row0 + wa * row1

    def _continuation(
        self,
        V_next: Array,
        W_plus: float,
        A_plus: float,
        alpha_fee: float,
    ) -> float:
        """
        Scalar continuation value:
        E[V_next(W_plus * exp(Y-alpha*dt), A_plus)].
        """
        if A_plus <= 1e-12 and W_plus <= 1e-12:
            return 0.0

        fee_factor = np.exp(-alpha_fee * self.contract.dt)
        W_next = W_plus * fee_factor * np.exp(self._y)
        vals = self._interp_surface(V_next, W_next, A_plus)

        return float(np.dot(self._yw, vals))

    def _continuation_vec(
        self,
        V_next: Array,
        W_plus_vec: Array,
        A_plus: float,
        alpha_fee: float,
    ) -> Array:
        """
        Vectorised continuation for an entire W-grid at fixed A_plus.
        """
        Wp = np.asarray(W_plus_vec, dtype=float)

        if A_plus <= 1e-12 and np.all(Wp <= 1e-12):
            return np.zeros_like(Wp)

        fee_factor = np.exp(-alpha_fee * self.contract.dt)
        W_next = Wp[:, None] * fee_factor * np.exp(self._y)[None, :]

        vals = self._interp_surface(
            V_next,
            W_next.ravel(),
            A_plus,
        ).reshape(len(Wp), len(self._y))

        return vals @ self._yw

    def _candidate_withdrawals(
        self,
        A: float,
        withdrawal: Literal["static", "dynamic"],
    ) -> Array:
        c = self.contract

        if A <= 1e-14:
            return np.array([0.0])

        if withdrawal == "static":
            return np.array([min(c.G, A)])

        if withdrawal != "dynamic":
            raise ValueError("withdrawal must be 'static' or 'dynamic'.")

        grid = np.linspace(0.0, A, self.num.withdrawal_grid_size)
        cand = np.unique(np.clip(np.r_[0.0, min(c.G, A), A, grid], 0.0, A))

        return cand

    def build_surface(
        self,
        alpha_fee: float,
        withdrawal: Literal["static", "dynamic"] = "dynamic",
        include_initial_withdrawal: bool = False,
    ) -> Tuple[float, Array, list[Array]]:
        """
        Build the dynamic-programming value surface.

        Returns:
            price, first-event value surface, list of policy surfaces.
        """
        c = self.contract
        N = c.n_events
        disc = np.exp(-self.r * c.dt)

        W_mat, A_mat = np.meshgrid(self.W_grid, self.A_grid)

        V_next = np.maximum(
            W_mat,
            terminal_cashflow(A_mat, c.G, c.kappa, c.terminal_penalty),
        )

        policies: list[Array] = []

        # Non-terminal withdrawal dates t_{N-1},...,t_1.
        # t_N is terminal payoff.
        for _m in range(N - 1, 0, -1):
            V_cur = np.empty_like(V_next)
            gamma_star = np.zeros_like(V_next)

            for ia, A in enumerate(self.A_grid):
                candidates = self._candidate_withdrawals(float(A), withdrawal)

                best_val = np.full_like(self.W_grid, -np.inf, dtype=float)
                best_g = np.zeros_like(self.W_grid, dtype=float)

                for g in candidates:
                    cf = float(penalty_cashflow(g, c.G, c.kappa))
                    Wp = np.maximum(self.W_grid - float(g), 0.0)

                    if c.reset_provision and g > c.G:
                        vals = np.empty_like(self.W_grid)
                        Ap_vec = np.maximum(np.minimum(float(A) - float(g), Wp), 0.0)

                        for idx, (wp_i, ap_i) in enumerate(zip(Wp, Ap_vec)):
                            vals[idx] = cf + disc * self._continuation(
                                V_next,
                                float(wp_i),
                                float(ap_i),
                                alpha_fee,
                            )
                    else:
                        Ap = max(float(A) - float(g), 0.0)
                        vals = cf + disc * self._continuation_vec(
                            V_next,
                            Wp,
                            Ap,
                            alpha_fee,
                        )

                    improve = vals > best_val
                    best_val[improve] = vals[improve]
                    best_g[improve] = float(g)

                V_cur[ia, :] = best_val
                gamma_star[ia, :] = best_g

            V_next = V_cur
            policies.append(gamma_star)

        if include_initial_withdrawal:
            W = c.W0
            A = c.W0
            best_val = -np.inf

            for g in self._candidate_withdrawals(A, withdrawal):
                Wp, Ap = after_withdrawal(
                    W,
                    A,
                    float(g),
                    c.G,
                    c.reset_provision,
                )
                val = penalty_cashflow(g, c.G, c.kappa) + disc * self._continuation(
                    V_next,
                    Wp,
                    Ap,
                    alpha_fee,
                )
                best_val = max(best_val, val)

            price = float(best_val)

        else:
            if N == 1:
                W_next = c.W0 * np.exp(-alpha_fee * c.dt) * np.exp(self._y)
                terminal_vals = np.maximum(
                    W_next,
                    terminal_cashflow(c.W0, c.G, c.kappa, c.terminal_penalty),
                )
                price = float(disc * np.dot(self._yw, terminal_vals))
            else:
                price = float(
                    disc * self._continuation(V_next, c.W0, c.W0, alpha_fee)
                )

        self._last_surface = V_next
        self._last_policy = policies[::-1]

        return price, V_next, policies[::-1]

    def price(
        self,
        alpha_fee: float,
        withdrawal: Literal["static", "dynamic"] = "dynamic",
        include_initial_withdrawal: bool = False,
    ) -> float:
        return self.build_surface(
            alpha_fee,
            withdrawal,
            include_initial_withdrawal,
        )[0]

    def fair_fee(
        self,
        withdrawal: Literal["static", "dynamic"] = "dynamic",
        target_value: Optional[float] = None,
        lo: float = 0.0,
        hi: float = 0.20,
        include_initial_withdrawal: bool = False,
    ) -> float:
        """
        Solve alpha such that price(alpha) equals target_value.
        Default target_value is W0.
        """
        target = self.contract.W0 if target_value is None else target_value

        def f(x: float) -> float:
            return self.price(x, withdrawal, include_initial_withdrawal) - target

        flo = f(lo)
        fhi = f(hi)

        while flo * fhi > 0 and hi < 5.0:
            hi *= 2.0
            fhi = f(hi)

        if flo * fhi > 0:
            raise RuntimeError(
                f"Could not bracket fair fee: f({lo})={flo}, f({hi})={fhi}."
            )

        return float(brentq(f, lo, hi, xtol=1e-7, rtol=1e-7, maxiter=100))

    def finite_difference_delta_gamma(
        self,
        alpha_fee: float,
        withdrawal: Literal["static", "dynamic"] = "dynamic",
        rel_shift: float = 1e-3,
    ) -> Tuple[float, float]:
        """
        Delta/Gamma with respect to the initial investment account,
        holding the guarantee account fixed.
        """
        base_price, V1, _ = self.build_surface(
            alpha_fee,
            withdrawal,
            include_initial_withdrawal=False,
        )

        c = self.contract
        disc = np.exp(-self.r * c.dt)
        h = c.W0 * rel_shift

        def initial_value(w0: float) -> float:
            W_next = w0 * np.exp(-alpha_fee * c.dt) * np.exp(self._y)

            if c.n_events == 1:
                terminal_vals = np.maximum(
                    W_next,
                    terminal_cashflow(c.W0, c.G, c.kappa, c.terminal_penalty),
                )
                return float(disc * np.dot(self._yw, terminal_vals))

            vals = self._interp_surface(V1, W_next, c.W0)
            return float(disc * np.dot(self._yw, vals))

        up = initial_value(c.W0 + h)
        dn = initial_value(max(c.W0 - h, 1e-12))

        delta = (up - dn) / (2.0 * h)
        gamma = (up - 2.0 * base_price + dn) / (h * h)

        return float(delta), float(gamma)


# ============================================================
# 5) European option COS utility for hedge instruments
# ============================================================

def _chi_psi(
    k: Array,
    a: float,
    b: float,
    c: float,
    d: float,
) -> Tuple[Array, Array]:
    """
    COS coefficients for exp(y) and 1 over [c,d] within [a,b].
    """
    kpi = k * np.pi / (b - a)

    psi = np.empty_like(k, dtype=float)
    psi[0] = d - c

    nonzero = k > 0
    psi[nonzero] = (
        np.sin(kpi[nonzero] * (d - a))
        - np.sin(kpi[nonzero] * (c - a))
    ) / kpi[nonzero]

    denom = 1.0 + kpi**2

    term_d = np.exp(d) * (
        np.cos(kpi * (d - a))
        + kpi * np.sin(kpi * (d - a))
    )
    term_c = np.exp(c) * (
        np.cos(kpi * (c - a))
        + kpi * np.sin(kpi * (c - a))
    )

    chi = (term_d - term_c) / denom

    return chi, psi


def european_option_cos(
    S0: float,
    K: float,
    T: float,
    r: float,
    model: LevyModel,
    option: Literal["call", "put"] = "call",
    n_terms: int = 256,
    L: float = 10.0,
) -> Tuple[float, float, float]:
    """
    European option price, delta and gamma via COS.

    Returns:
        price, delta, gamma.
    """
    if S0 <= 0 or K <= 0 or T <= 0:
        raise ValueError("S0, K, T must be positive.")

    x = np.log(S0 / K)

    a0, b0 = _cos_truncation_interval(
        lambda u: model.cf(u, T, r),
        L=L,
    )

    k = np.arange(n_terms, dtype=float)

    def price_only(s: float) -> float:
        xx = np.log(s / K)
        a, b = a0 + xx, b0 + xx
        u = k * np.pi / (b - a)

        if option == "call":
            chi, psi = _chi_psi(k, a, b, 0.0, b)
            Vk = 2.0 / (b - a) * K * (chi - psi)
        elif option == "put":
            chi, psi = _chi_psi(k, a, b, a, 0.0)
            Vk = 2.0 / (b - a) * K * (psi - chi)
        else:
            raise ValueError("option must be 'call' or 'put'.")

        Vk[0] *= 0.5

        phi = (
            np.exp(1j * u * xx)
            * model.cf(u, T, r)
            * np.exp(-1j * u * a)
        )

        return float(np.exp(-r * T) * np.sum(np.real(phi) * Vk))

    price = price_only(S0)

    h = max(1e-4 * S0, 1e-5)
    up = price_only(S0 + h)
    down = price_only(max(S0 - h, 1e-12))

    delta = (up - down) / (2.0 * h)
    gamma = (up - 2.0 * price + down) / (h * h)

    return float(price), float(delta), float(gamma)


# ============================================================
# 6) Local risk-minimisation hedge
# ============================================================

@dataclass(frozen=True)
class HedgeOption:
    option: Literal["call", "put"]
    strike: float
    maturity: float
    price: float

    def payoff(self, S: Array) -> Array:
        if self.option == "call":
            return np.maximum(S - self.strike, 0.0)
        return np.maximum(self.strike - S, 0.0)


def risk_measure(
    loss: Array,
    weights: Array,
    kind: Literal["mean", "variance", "second_moment", "var", "tvar"],
    q: float = 0.95,
) -> float:
    """
    Risk measures for one-period hedging-loss distribution.
    Positive values are losses, negative values are gains.
    """
    w = np.maximum(weights, 0.0)
    w = w / np.sum(w)

    if kind == "mean":
        return float(np.dot(w, loss))

    if kind == "variance":
        mu = np.dot(w, loss)
        return float(np.dot(w, (loss - mu) ** 2))

    if kind == "second_moment":
        return float(np.dot(w, loss**2))

    order = np.argsort(loss)
    xs = loss[order]
    ws = w[order]
    cdf = np.cumsum(ws)

    idx = int(np.searchsorted(cdf, q, side="left"))
    idx = min(idx, len(xs) - 1)
    var = float(xs[idx])

    if kind == "var":
        return var

    if kind == "tvar":
        tail = xs >= var
        return float(np.dot(ws[tail], xs[tail]) / np.sum(ws[tail]))

    raise ValueError(f"Unknown risk measure: {kind}")


def optimise_local_hedge(
    y: Array,
    weights: Array,
    base_loss: Array,
    S0: float,
    options: Sequence[HedgeOption],
    kind: Literal["mean", "variance", "second_moment", "var", "tvar"] = "variance",
    q: float = 0.95,
    budget: Optional[float] = None,
    bounds: Optional[Sequence[Tuple[float, float]]] = None,
) -> Array:
    """
    Choose option quantities theta to minimise a one-period hedging-loss risk measure.
    """
    n = len(options)
    if n == 0:
        return np.zeros(0)

    if bounds is None:
        bounds = [(-np.inf, np.inf)] * n

    S_next = S0 * np.exp(y)
    option_payoffs = np.column_stack([opt.payoff(S_next) for opt in options])
    option_prices = np.array([opt.price for opt in options], dtype=float)

    def objective(theta: Array) -> float:
        hedge_cost = float(np.dot(theta, option_prices))
        hedge_payoff = option_payoffs @ theta
        hedged_loss = base_loss + hedge_cost - hedge_payoff
        return risk_measure(hedged_loss, weights, kind=kind, q=q)

    constraints = []
    if budget is not None:
        constraints.append(
            {
                "type": "ineq",
                "fun": lambda th: budget - float(np.dot(th, option_prices)),
            }
        )

    res = minimize(
        objective,
        x0=np.zeros(n),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500},
    )

    if not res.success:
        raise RuntimeError(f"Hedge optimisation failed: {res.message}")

    return np.asarray(res.x, dtype=float)


# ============================================================
# 7) BSM / MMM / Heston simulation modules
# ============================================================

@dataclass(frozen=True)
class BSMParams:
    sigma: float = 0.20
    r: float = 0.03


@dataclass(frozen=True)
class MMMParams:
    alpha0: float = 1.0
    eta: float = 0.05
    S0: float = 1.0


@dataclass(frozen=True)
class HestonParams:
    v0: float = 0.04
    theta: float = 0.04
    kappa: float = 1.5
    zeta: float = 0.30
    rho: float = -0.5
    r: float = 0.03


@dataclass(frozen=True)
class CIRRateParams:
    r0: float = 0.03
    theta: float = 0.03
    kappa: float = 0.5
    sigma: float = 0.05


def simulate_bsm_paths(
    params: BSMParams,
    S0: float,
    T: float,
    steps: int,
    n_paths: int,
    seed: int = 1,
    risk_neutral: bool = True,
) -> Array:
    rng = np.random.default_rng(seed)
    dt = T / steps
    Z = rng.standard_normal((n_paths, steps))

    if risk_neutral:
        drift = params.r - 0.5 * params.sigma**2
    else:
        drift = 0.5 * params.sigma**2

    log_inc = drift * dt + params.sigma * np.sqrt(dt) * Z
    logS = np.c_[
        np.full(n_paths, np.log(S0)),
        np.log(S0) + np.cumsum(log_inc, axis=1),
    ]

    return np.exp(logS)


def simulate_mmm_paths(
    params: MMMParams,
    T: float,
    steps: int,
    n_paths: int,
    seed: int = 2,
) -> Array:
    """
    Euler full-truncation paths for the MMM GOP:
        dS = alpha0*exp(eta*t) dt + sqrt(alpha0*exp(eta*t)*S) dB.
    """
    rng = np.random.default_rng(seed)
    dt = T / steps

    S = np.empty((n_paths, steps + 1), dtype=float)
    S[:, 0] = params.S0

    for k in range(steps):
        t = k * dt
        alpha_t = params.alpha0 * np.exp(params.eta * t)
        Z = rng.standard_normal(n_paths)
        S_pos = np.maximum(S[:, k], 0.0)

        S[:, k + 1] = np.maximum(
            S_pos
            + alpha_t * dt
            + np.sqrt(alpha_t * S_pos * dt) * Z,
            1e-12,
        )

    return S


def simulate_heston_paths(
    params: HestonParams,
    S0: float,
    T: float,
    steps: int,
    n_paths: int,
    seed: int = 3,
    risk_neutral: bool = True,
) -> Tuple[Array, Array]:
    """
    Heston paths with full-truncation Euler variance.
    """
    rng = np.random.default_rng(seed)
    dt = T / steps

    S = np.empty((n_paths, steps + 1), dtype=float)
    v = np.empty_like(S)

    S[:, 0] = S0
    v[:, 0] = params.v0

    for k in range(steps):
        z1 = rng.standard_normal(n_paths)
        z2 = rng.standard_normal(n_paths)

        dWv = z1 * np.sqrt(dt)
        dWs = (
            params.rho * z1
            + np.sqrt(max(1.0 - params.rho**2, 0.0)) * z2
        ) * np.sqrt(dt)

        v_pos = np.maximum(v[:, k], 0.0)
        drift = params.r if risk_neutral else v_pos

        S[:, k + 1] = S[:, k] * np.exp(
            (drift - 0.5 * v_pos) * dt
            + np.sqrt(v_pos) * dWs
        )

        v[:, k + 1] = np.maximum(
            v[:, k]
            + params.kappa * (params.theta - v_pos) * dt
            + params.zeta * np.sqrt(v_pos) * dWv,
            0.0,
        )

    return S, v


def simulate_cir_rates(
    params: CIRRateParams,
    T: float,
    steps: int,
    n_paths: int,
    seed: int = 4,
) -> Array:
    rng = np.random.default_rng(seed)
    dt = T / steps

    r = np.empty((n_paths, steps + 1), dtype=float)
    r[:, 0] = params.r0

    for k in range(steps):
        z = rng.standard_normal(n_paths)
        rp = np.maximum(r[:, k], 0.0)

        r[:, k + 1] = np.maximum(
            r[:, k]
            + params.kappa * (params.theta - rp) * dt
            + params.sigma * np.sqrt(rp * dt) * z,
            0.0,
        )

    return r


def price_static_gmwb_mc(
    S_paths: Array,
    contract: GMWBContract,
    alpha_fee: float,
    r: float = 0.0,
    discount_mode: Literal["risk_neutral", "benchmark"] = "risk_neutral",
) -> float:
    """
    Static GMWB Monte Carlo price from simulated paths.

    risk_neutral:
        Discount cashflows by exp(-r*t).

    benchmark:
        Benchmark-approach discount factor S(0)/S(t), for discounted GOP paths.
    """
    n_paths, steps_plus_1 = S_paths.shape
    steps = steps_plus_1 - 1
    N = contract.n_events

    if steps % N != 0:
        raise ValueError("S_paths grid must have an integer number of steps per event.")

    stride = steps // N

    W = np.full(n_paths, contract.W0, dtype=float)
    A = np.full(n_paths, contract.W0, dtype=float)
    pv = np.zeros(n_paths, dtype=float)

    for n in range(1, N + 1):
        idx0 = (n - 1) * stride
        idx1 = n * stride

        gross_return = S_paths[:, idx1] / S_paths[:, idx0]
        W *= gross_return * np.exp(-alpha_fee * contract.dt)

        if n < N:
            gamma_w = np.minimum(contract.G, A)
            cash = penalty_cashflow(gamma_w, contract.G, contract.kappa)

            A = np.maximum(A - gamma_w, 0.0)
            W = np.maximum(W - gamma_w, 0.0)

        else:
            cash = np.maximum(
                W,
                terminal_cashflow(
                    A,
                    contract.G,
                    contract.kappa,
                    contract.terminal_penalty,
                ),
            )

            W[:] = 0.0
            A[:] = 0.0

        t = n * contract.dt

        if discount_mode == "risk_neutral":
            df = np.exp(-r * t)
        elif discount_mode == "benchmark":
            df = S_paths[:, 0] / S_paths[:, idx1]
        else:
            raise ValueError("discount_mode must be 'risk_neutral' or 'benchmark'.")

        pv += df * cash

    return float(np.mean(pv))


# ============================================================
# 8) Dahl-Møller / Gompertz stochastic mortality module
# ============================================================

@dataclass(frozen=True)
class DahlMollerParams:
    alpha_mu: float = 0.000233
    beta_mu: float = 0.0000658
    c: float = 1.0959
    delta_tilde: float = 0.2
    gamma_tilde: float = 0.008
    sigma_tilde: float = 0.02

    def mu0(self, age: float, t: float | Array = 0.0) -> float | Array:
        return self.alpha_mu + self.beta_mu * self.c ** (age + t)

    def gamma_mu(self, age: float, t: float) -> float:
        return self.delta_tilde * np.exp(-self.gamma_tilde * t) * self.mu0(age, t)

    def delta_mu(self, age: float, t: float) -> float:
        mu = self.mu0(age, t)
        dmu_dt = self.beta_mu * self.c ** (age + t) * np.log(self.c)
        return self.delta_tilde - dmu_dt / mu

    def sigma_mu(self, age: float, t: float) -> float:
        return self.sigma_tilde * np.sqrt(self.mu0(age, t))


def dahl_moller_survival_probability(
    age: float,
    T: float,
    params: DahlMollerParams = DahlMollerParams(),
    steps: int = 2000,
) -> float:
    """
    Solve the Riccati equations backwards and return S(age, 0, T).
    """
    if T <= 0:
        return 1.0

    dt = T / steps
    A = 0.0
    B = 0.0

    for j in range(steps, 0, -1):
        t = j * dt

        delta = params.delta_mu(age, t)
        sig = params.sigma_mu(age, t)
        gam = params.gamma_mu(age, t)

        dB_dt = delta * B + 0.5 * sig**2 * B**2 - 1.0
        dA_dt = gam * B

        B -= dB_dt * dt
        A -= dA_dt * dt

    mu_start = params.mu0(age, 0.0)

    return float(np.exp(A - B * mu_start))


def deterministic_gompertz_survival(
    age: float,
    T: float,
    params: DahlMollerParams = DahlMollerParams(),
    steps: int = 2000,
) -> float:
    """
    Deterministic Gompertz benchmark survival probability.
    """
    ts = np.linspace(0.0, T, steps + 1)
    mu = params.mu0(age, ts)
    integral = np.trapz(mu, ts)

    return float(np.exp(-integral))


# ============================================================
# 9) Example run
# ============================================================

if __name__ == "__main__":
    contract = GMWBContract(
        W0=100.0,
        maturity=10.0,
        events_per_year=1,
        kappa=0.10,
        reset_provision=False,
        terminal_penalty=False,
    )

    numerics = COSNumerics(
        w_points=81,
        a_points=41,
        w_max_mult=5.0,
        cos_terms=64,
        quad_points=48,
        trunc_L=10.0,
        withdrawal_grid_size=21,
    )

    pricer = GMWBCOSPricer(
        contract=contract,
        model=GBMModel(sigma=0.20),
        r=0.05,
        numerics=numerics,
    )

    value_static = pricer.price(alpha_fee=0.01, withdrawal="static")
    value_dynamic = pricer.price(alpha_fee=0.01, withdrawal="dynamic")

    fair_static = pricer.fair_fee(withdrawal="static", hi=0.20)
    fair_dynamic = pricer.fair_fee(withdrawal="dynamic", hi=0.30)

    delta, gamma = pricer.finite_difference_delta_gamma(
        alpha_fee=fair_dynamic,
        withdrawal="dynamic",
    )

    print("COS GMWB example: GBM, r=5%, sigma=20%, annual withdrawals")
    print(f"price(alpha=1%, static)  = {value_static:.6f}")
    print(f"price(alpha=1%, dynamic) = {value_dynamic:.6f}")
    print(f"fair fee static           = {10000 * fair_static:.2f} bp")
    print(f"fair fee dynamic          = {10000 * fair_dynamic:.2f} bp")
    print(f"delta/gamma at fair fee   = {delta:.6f}, {gamma:.6f}")

    call_price, call_delta, call_gamma = european_option_cos(
        S0=100.0,
        K=100.0,
        T=1.0,
        r=0.05,
        model=GBMModel(sigma=0.20),
        option="call",
        n_terms=256,
    )

    print()
    print("European call via COS")
    print(f"price={call_price:.6f}, delta={call_delta:.6f}, gamma={call_gamma:.6f}")

    S_mmm = simulate_mmm_paths(
        MMMParams(alpha0=1.0, eta=0.05, S0=100.0),
        T=10.0,
        steps=120,
        n_paths=20_000,
        seed=42,
    )

    mmm_benchmark_price = price_static_gmwb_mc(
        S_paths=S_mmm,
        contract=contract,
        alpha_fee=0.01,
        discount_mode="benchmark",
    )

    print()
    print(f"Static GMWB MC under MMM / benchmark discounting = {mmm_benchmark_price:.6f}")

    survival = dahl_moller_survival_probability(age=65, T=10.0)

    print()
    print(f"Dahl-Moller stochastic mortality survival S(65,0,10) = {survival:.6f}")