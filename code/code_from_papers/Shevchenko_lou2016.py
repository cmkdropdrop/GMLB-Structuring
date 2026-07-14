# pip install numpy scipy

from __future__ import annotations

from dataclasses import dataclass, replace
import numpy as np
from numpy.polynomial.hermite import hermgauss
from scipy.interpolate import RectBivariateSpline, CubicSpline
from scipy.optimize import brentq


@dataclass(frozen=True)
class VasicekGMWBParams:
    # Contract
    w0: float = 1.0
    T: float = 10.0
    withdrawals_per_year: int = 4
    alpha: float = 0.006       # annual continuous guarantee fee, e.g. 0.006 = 60 bp
    beta: float = 0.10         # penalty on withdrawals above contractual amount

    # Market model under Q
    r0: float = 0.05
    sigma_s: float = 0.20
    sigma_r: float = 0.02
    rho: float = 0.30
    kappa: float = 0.0349
    theta: float = 0.05


@dataclass(frozen=True)
class GHQCGrid:
    # Positive wealth grid is x = log(W / w0). W=0 is added separately as absorbing row.
    x_min: float = -6.0
    x_max: float = 2.7
    nx: int = 45

    # Vasicek rate grid. Choose wide enough for the product maturity and sigma_r.
    r_min: float = -0.12
    r_max: float = 0.22
    nr: int = 21

    # Guarantee account grid: A in [0, w0]
    a_steps: int = 40

    # Gauss-Hermite orders. qx is normally higher because value changes faster in W than in r.
    qx: int = 7
    qr: int = 5


class GHQCGMWBPricer:
    """
    GHQC pricer for the basic GMWB contract in Shevchenko/Luo:
    - stochastic Vasicek short rate;
    - lognormal risky fund correlated with rate;
    - static or optimal withdrawals;
    - no mortality/death benefit.
    """

    def __init__(self, params: VasicekGMWBParams, grid: GHQCGrid = GHQCGrid()):
        self.p = params
        self.grid = grid

        self.N = int(round(params.T * params.withdrawals_per_year))
        if self.N <= 0 or abs(self.N / params.withdrawals_per_year - params.T) > 1e-12:
            raise ValueError("T * withdrawals_per_year must be a positive integer.")
        if not (-0.999999 < params.rho < 0.999999):
            raise ValueError("rho must be inside (-1, 1).")
        if params.kappa <= 0.0:
            raise ValueError("kappa must be positive.")
        if params.w0 <= 0.0:
            raise ValueError("w0 must be positive.")
        if params.beta < 0.0 or params.beta > 1.0:
            raise ValueError("beta must be in [0, 1].")

        self.dt = params.T / self.N
        self.contractual = np.full(self.N + 1, params.w0 * self.dt / params.T)  # indexed by n=1,...,N

        self.x_grid = np.linspace(grid.x_min, grid.x_max, grid.nx + 1)
        self.w_pos = params.w0 * np.exp(self.x_grid)
        self.w_grid = np.r_[0.0, self.w_pos]  # W=0 absorbing row + positive grid
        self.r_grid = np.linspace(grid.r_min, grid.r_max, grid.nr + 1)
        self.a_grid = np.linspace(0.0, params.w0, grid.a_steps + 1)

        self.xi_x, self.lam_x = hermgauss(grid.qx)
        self.xi_r, self.lam_r = hermgauss(grid.qr)

    def cashflow(self, gamma: float | np.ndarray, contractual: float) -> np.ndarray:
        """C_n(gamma): withdrawal cashflow with penalty above contractual amount."""
        gamma = np.asarray(gamma, dtype=float)
        return np.where(
            gamma <= contractual,
            gamma,
            contractual + (1.0 - self.p.beta) * (gamma - contractual),
        )

    def bond_price_step(self, r: float | np.ndarray, dt: float | None = None) -> np.ndarray:
        """P(t, t+dt) under the constant-parameter Vasicek model."""
        p = self.p
        if dt is None:
            dt = self.dt
        B = (1.0 - np.exp(-p.kappa * dt)) / p.kappa
        A = (p.theta - p.sigma_r**2 / (2.0 * p.kappa**2)) * (B - dt) - p.sigma_r**2 * B**2 / (4.0 * p.kappa)
        return np.exp(A - np.asarray(r) * B)

    def _step_moments(self, w: np.ndarray, r: np.ndarray, dt: float | None = None):
        """
        Moments of (ln W_{t+dt}, r_{t+dt}) under the bond numeraire measure.
        w must be strictly positive here.
        """
        p = self.p
        if dt is None:
            dt = self.dt

        k = p.kappa
        b = 1.0 - np.exp(-k * dt)
        a = 1.0 - np.exp(-2.0 * k * dt)

        w = np.asarray(w, dtype=float)
        r = np.asarray(r, dtype=float)

        mu_r = (
            r * np.exp(-k * dt)
            + (p.theta - p.sigma_r**2 / k**2) * b
            + p.sigma_r**2 * a / (2.0 * k**2)
        )
        var_r = p.sigma_r**2 * a / (2.0 * k)

        mu_x = (
            np.log(w)
            + (b / k) * (r + b * p.sigma_r**2 / (2.0 * k**2))
            + (p.theta - p.sigma_r**2 / k**2) * (dt - b / k)
            - (p.rho * p.sigma_s * p.sigma_r / k**2) * (k * dt - b)
            - (p.alpha + 0.5 * p.sigma_s**2) * dt
        )
        var_x = (
            p.sigma_s**2 * dt
            + p.sigma_r**2 * (2.0 * k * dt - 4.0 * b + a) / (2.0 * k**3)
            + 2.0 * p.rho * p.sigma_s * p.sigma_r * (k * dt - b) / k**2
        )
        cov_xr = (
            p.rho * p.sigma_s * p.sigma_r * b / k
            + p.sigma_r**2 * (2.0 * b - a) / (2.0 * k**2)
        )

        var_x = max(float(var_x), 0.0)
        var_r = max(float(var_r), 0.0)
        tau_x = np.sqrt(var_x)
        tau_r = np.sqrt(var_r)
        rho_xr = 0.0 if tau_x * tau_r < 1e-14 else cov_xr / (tau_x * tau_r)
        rho_xr = float(np.clip(rho_xr, -0.999999999, 0.999999999))
        return mu_x, mu_r, tau_x, tau_r, rho_xr

    def _make_evaluator(self, Q: np.ndarray):
        """
        Build vectorized Q(w, r) interpolator.

        Q shape: (len(w_grid), len(r_grid)).
        Q[0, :] is W=0; Q[1:, :] is on x_grid = log(W/w0).
        """
        xg = self.x_grid
        rg = self.r_grid
        w0 = self.p.w0
        w_min = self.w_pos[0]
        w_max = self.w_pos[-1]
        r_min = rg[0]
        r_max = rg[-1]

        kx = min(3, len(xg) - 1)
        ky = min(3, len(rg) - 1)
        spline_pos = RectBivariateSpline(xg, rg, Q[1:, :], kx=kx, ky=ky, s=0.0)
        spline_zero = CubicSpline(rg, Q[0, :], bc_type="not-a-knot", extrapolate=True)

        def eval_q(w, r):
            w_arr, r_arr = np.broadcast_arrays(np.asarray(w, dtype=float), np.asarray(r, dtype=float))
            out = np.empty_like(w_arr, dtype=float)
            rc = np.clip(r_arr, r_min, r_max)

            zero = w_arr <= 0.0
            if np.any(zero):
                out[zero] = spline_zero(rc[zero])

            pos = ~zero
            if np.any(pos):
                wp = w_arr[pos]
                rp = rc[pos]
                vals = np.empty_like(wp, dtype=float)

                low = wp < w_min
                high = wp > w_max
                mid = ~(low | high)

                if np.any(mid):
                    vals[mid] = spline_pos.ev(np.log(wp[mid] / w0), rp[mid])

                if np.any(low):
                    # Linear bridge between W=0 and the first positive grid point.
                    q_zero = spline_zero(rp[low])
                    q_min = spline_pos.ev(np.full(np.sum(low), xg[0]), rp[low])
                    weight = np.clip(wp[low] / w_min, 0.0, 1.0)
                    vals[low] = (1.0 - weight) * q_zero + weight * q_min

                if np.any(high):
                    # Large-wealth asymptotic: the guarantee is negligible and dQ/dW tends to 1.
                    q_max = spline_pos.ev(np.full(np.sum(high), xg[-1]), rp[high])
                    vals[high] = q_max + (wp[high] - w_max)

                out[pos] = vals

            return out

        return eval_q

    def _expectation_grid(self, Q_next: np.ndarray, dt: float | None = None) -> np.ndarray:
        """
        Backward integration over one withdrawal period:
        Q_plus(W_i,r_k) = P(r_k) * E^{bond}[Q_next(W_next,r_next)].
        """
        if dt is None:
            dt = self.dt
        eval_q = self._make_evaluator(Q_next)

        nW = len(self.w_grid)
        nR = len(self.r_grid)
        out = np.empty((nW, nR), dtype=float)

        # W=0 is absorbing; only the rate evolves.
        r_start = self.r_grid
        _, mu_r0, _, tau_r, _ = self._step_moments(np.full_like(r_start, self.p.w0), r_start, dt)
        acc0 = np.zeros_like(r_start)
        for xi, lam in zip(self.xi_r, self.lam_r):
            rq = mu_r0 + np.sqrt(2.0) * tau_r * xi
            acc0 += lam * eval_q(np.zeros_like(rq), rq)
        out[0, :] = self.bond_price_step(r_start, dt) * acc0 / np.sqrt(np.pi)

        # W>0: two-dimensional Gauss-Hermite with spectral rotation.
        W_start = self.w_pos[:, None]
        R_start = self.r_grid[None, :]
        mu_x, mu_r, tau_x, tau_r, rho_xr = self._step_moments(W_start, R_start, dt)

        arot = 0.5 * (np.sqrt(1.0 + rho_xr) + np.sqrt(1.0 - rho_xr))
        brot = 0.5 * (np.sqrt(1.0 + rho_xr) - np.sqrt(1.0 - rho_xr))

        acc = np.zeros_like(mu_x, dtype=float)
        for xi, wx in zip(self.xi_x, self.lam_x):
            for eta, wr in zip(self.xi_r, self.lam_r):
                xq = np.sqrt(2.0) * tau_x * (arot * xi + brot * eta) + mu_x
                rq = np.sqrt(2.0) * tau_r * (brot * xi + arot * eta) + mu_r
                acc += wx * wr * eval_q(np.exp(xq), rq)

        out[1:, :] = self.bond_price_step(self.r_grid, dt)[None, :] * acc / np.pi
        return out

    def _expectation_point(self, Q_next: np.ndarray, w_start: float, r_start: float, dt: float | None = None) -> float:
        """Same backward integration for a single starting point, used at t0."""
        if dt is None:
            dt = self.dt
        eval_q = self._make_evaluator(Q_next)
        P = float(self.bond_price_step(r_start, dt))

        if w_start <= 0.0:
            _, mu_r, _, tau_r, _ = self._step_moments(np.array([self.p.w0]), np.array([r_start]), dt)
            acc = 0.0
            for xi, lam in zip(self.xi_r, self.lam_r):
                rq = float(mu_r[0] + np.sqrt(2.0) * tau_r * xi)
                acc += lam * float(eval_q(0.0, rq))
            return P * acc / np.sqrt(np.pi)

        mu_x, mu_r, tau_x, tau_r, rho_xr = self._step_moments(np.array([w_start]), np.array([r_start]), dt)
        mu_x = float(mu_x[0])
        mu_r = float(mu_r[0])

        arot = 0.5 * (np.sqrt(1.0 + rho_xr) + np.sqrt(1.0 - rho_xr))
        brot = 0.5 * (np.sqrt(1.0 + rho_xr) - np.sqrt(1.0 - rho_xr))

        acc = 0.0
        for xi, wx in zip(self.xi_x, self.lam_x):
            for eta, wr in zip(self.xi_r, self.lam_r):
                xq = np.sqrt(2.0) * tau_x * (arot * xi + brot * eta) + mu_x
                rq = np.sqrt(2.0) * tau_r * (brot * xi + arot * eta) + mu_r
                acc += wx * wr * float(eval_q(np.exp(xq), rq))
        return P * acc / np.pi

    def price_static(self, withdrawals: np.ndarray | None = None) -> float:
        """
        Price for a fixed withdrawal strategy.
        Default: contractual withdrawal w0/N at t_1,...,t_{N-1}, final remaining guarantee at T.
        """
        p = self.p
        if withdrawals is None:
            withdrawals = np.full(self.N - 1, p.w0 / self.N)
        else:
            withdrawals = np.asarray(withdrawals, dtype=float)
            if withdrawals.shape != (self.N - 1,):
                raise ValueError(f"withdrawals must have shape ({self.N - 1},).")

        remaining_A = p.w0 - float(np.sum(withdrawals))
        if remaining_A < -1e-12:
            raise ValueError("Static withdrawals exceed the initial guarantee account.")
        remaining_A = max(0.0, remaining_A)

        # Terminal payoff at t_N^-: max(W, C_N(A)).
        Q = np.maximum(
            self.w_grid[:, None],
            self.cashflow(remaining_A, self.contractual[self.N]),
        ) + np.zeros((len(self.w_grid), len(self.r_grid)))

        # Backward recursion over t_{N-1},...,t_1.
        for n in range(self.N - 1, 0, -1):
            Q_plus = self._expectation_grid(Q)
            gamma = float(withdrawals[n - 1])
            eval_plus = self._make_evaluator(Q_plus)
            W_after = np.maximum(self.w_grid[:, None] - gamma, 0.0)
            R = self.r_grid[None, :]
            Q = eval_plus(W_after, R) + self.cashflow(gamma, self.contractual[n])

        # Backward integration from t0 to t1^-; no withdrawal at t0.
        return self._expectation_point(Q, p.w0, p.r0)

    def price_dynamic(self) -> float:
        """Price under optimal/dynamic withdrawal strategy."""
        nA = len(self.a_grid)
        nW = len(self.w_grid)
        nR = len(self.r_grid)

        # Terminal payoff for every guarantee-account node A.
        Q = np.empty((nA, nW, nR), dtype=float)
        W = self.w_grid[:, None]
        for j, A in enumerate(self.a_grid):
            Q[j, :, :] = np.maximum(W, self.cashflow(A, self.contractual[self.N]))

        # Backward recursion over t_{N-1},...,t_1.
        for n in range(self.N - 1, 0, -1):
            Q_plus = np.empty_like(Q)
            for j in range(nA):
                Q_plus[j] = self._expectation_grid(Q[j])

            # Jump condition: max over A_after nodes <= A_before.
            Q_minus = np.empty_like(Q)
            evals_plus = [self._make_evaluator(Q_plus[i]) for i in range(nA)]

            W_before = self.w_grid[:, None]
            R = self.r_grid[None, :]
            for j, A_before in enumerate(self.a_grid):
                best = np.full((nW, nR), -np.inf)
                for i in range(j + 1):
                    A_after = self.a_grid[i]
                    gamma = A_before - A_after
                    W_after = np.maximum(W_before - gamma, 0.0)
                    candidate = evals_plus[i](W_after, R) + self.cashflow(gamma, self.contractual[n])
                    best = np.maximum(best, candidate)
                Q_minus[j] = best

            Q = Q_minus

        # At t0 the guarantee account equals w0, i.e. last A-grid node.
        return self._expectation_point(Q[-1], self.p.w0, self.p.r0)

    def find_fair_fee(self, mode: str = "dynamic", low: float = 0.0, high: float = 0.05, tol: float = 1e-5) -> float:
        """
        Solve for alpha such that price(alpha) = w0.
        Returns alpha as decimal per year; multiply by 10_000 for basis points.
        """
        if mode not in {"dynamic", "static"}:
            raise ValueError("mode must be 'dynamic' or 'static'.")

        def objective(alpha: float) -> float:
            pricer = GHQCGMWBPricer(replace(self.p, alpha=float(alpha)), self.grid)
            price = pricer.price_dynamic() if mode == "dynamic" else pricer.price_static()
            return price - self.p.w0

        f_low = objective(low)
        f_high = objective(high)
        while f_low * f_high > 0.0 and high < 1.0:
            high *= 2.0
            f_high = objective(high)

        if f_low * f_high > 0.0:
            raise RuntimeError("No fair-fee bracket found. Try a wider [low, high] interval.")

        return float(brentq(objective, low, high, xtol=tol, rtol=tol))


if __name__ == "__main__":
    # Parameters close to the numerical examples in the paper.
    params = VasicekGMWBParams(
        w0=1.0,
        r0=0.05,
        sigma_s=0.20,
        sigma_r=0.02,
        rho=0.30,
        kappa=0.0349,
        theta=0.05,
        alpha=0.006,
        beta=0.10,
        T=10.0,
        withdrawals_per_year=4,
    )
    pricer = GHQCGMWBPricer(params, GHQCGrid())

    print(f"Static GMWB price : {pricer.price_static():.8f}")
    print(f"Dynamic GMWB price: {pricer.price_dynamic():.8f}")

    # The fair-fee calculation repeatedly reprices and is therefore slower.
    # fair_fee = pricer.find_fair_fee(mode="dynamic", low=0.0, high=0.03)
    # print(f"Dynamic fair fee  : {10_000 * fair_fee:.2f} bp")