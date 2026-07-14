from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Dict, Literal, Optional, Tuple

import numpy as np


Array = np.ndarray


class ModelKind(str, Enum):
    BS = "bs"
    HESTON = "heston"
    ONE = "one"
    THREE_HALVES = "three_halves"
    VASICEK = "vasicek"


class RatchetType(str, Enum):
    NONE = "none"
    LOOKBACK = "lookback"
    REMAINING_WBB = "remaining_wbb"


@dataclass(frozen=True)
class MarketSpec:
    """
    Risk-neutrales Marktmodell für den Account-Wert W.

    kind:
      "bs"            Black-Scholes: dW/W = (r-alpha)dt + sigma dZ
      "heston"        Heston: dV = kappa(theta-V)dt + volvol sqrt(V)dZ
      "one"           ONE: dV = kappa(theta-V)dt + volvol V dZ
      "three_halves"  3/2: dV = kappa V(theta-V)dt + volvol V^(3/2)dZ
      "vasicek"       BS mit stochastischem Short Rate:
                      dr = kappa_r(theta_r-r)dt + sigma_r dZ
    """
    kind: ModelKind = ModelKind.BS

    # BS / konstante Rate
    r: float = 0.04
    sigma: float = 0.20

    # Stochastische Volatilität
    v0: float = 0.04
    theta: float = 0.04
    kappa: float = 1.00
    volvol: float = 0.30
    rho: float = -0.50

    # Vasicek / Hull-White-artige Short-Rate-Dynamik mit konstanter Langfrist-Mean
    r0: float = 0.04
    theta_r: float = 0.04
    kappa_r: float = 0.15
    sigma_r: float = 0.01
    rho_sr: float = 0.0


@dataclass(frozen=True)
class ContractSpec:
    """
    GLWB/GMWB-Vertrag.

    State-Variablen:
      W = Account-/Policy-Fund-Wert
      B = Benefit Base / Withdrawal Benefit Base
      C = garantierter jährlicher Withdrawal-Betrag

    LOOKBACK:
      B wird bei Ratchet auf max(B, W) gesetzt, C = withdrawal_rate * B.

    REMAINING_WBB:
      B wird bei vertraglichem Withdrawal reduziert, C bleibt zunächst konstant;
      bei Ratchet steigt C um withdrawal_rate * max(W-B, 0) und B wird auf W gesetzt.
    """
    premium: float = 100.0
    initial_account: Optional[float] = None

    maturity_years: int = 57
    withdrawal_rate: float = 0.05
    first_withdrawal_year: int = 1

    alpha_g: float = 0.01
    alpha_m: float = 0.00

    ratchet: RatchetType = RatchetType.LOOKBACK
    ratchet_frequency_years: int = 1
    bonus_rate: float = 0.0

    q_mortality: Optional[Array] = None
    surrender_rates: Optional[Array] = None
    surrender_penalties: Optional[Array] = None

    death_benefit: bool = True
    seed: int = 12345

    @property
    def W0(self) -> float:
        return self.premium if self.initial_account is None else float(self.initial_account)

    @property
    def B0(self) -> float:
        return self.premium

    @property
    def C0(self) -> float:
        return self.withdrawal_rate * self.premium

    @property
    def alpha_total(self) -> float:
        return self.alpha_g + self.alpha_m

    def q(self) -> Array:
        if self.q_mortality is None:
            return illustrative_gompertz_q(self.maturity_years)
        q = np.asarray(self.q_mortality, dtype=float)
        if q.size < self.maturity_years:
            raise ValueError("q_mortality muss mindestens maturity_years Einträge haben.")
        return np.clip(q[: self.maturity_years], 0.0, 1.0)

    def surrender(self) -> Array:
        out = np.zeros(self.maturity_years + 1)
        if self.surrender_rates is not None:
            s = np.asarray(self.surrender_rates, dtype=float)
            out[: min(out.size, s.size)] = s[: min(out.size, s.size)]
        return np.clip(out, 0.0, 1.0)

    def penalties(self) -> Array:
        out = np.zeros(self.maturity_years + 1)
        if self.surrender_penalties is not None:
            p = np.asarray(self.surrender_penalties, dtype=float)
            out[: min(out.size, p.size)] = p[: min(out.size, p.size)]
        return np.clip(out, 0.0, 1.0)

    def is_ratchet_year(self, year: int) -> bool:
        return (
            self.ratchet != RatchetType.NONE
            and self.ratchet_frequency_years > 0
            and year % self.ratchet_frequency_years == 0
        )


def illustrative_gompertz_q(T: int, age0: int = 65) -> Array:
    """
    Demo-Mortalität. Für produktive Rechnungen DAV 2004R, eigene Best-Estimate-
    oder Risikomortalität als q_mortality übergeben.
    q[k] = P(Tod im Jahr k+1 | lebend am Jahresanfang).
    """
    ages = age0 + np.arange(T)
    q = 0.0045 * np.exp(0.085 * (ages - age0))
    q = np.clip(q, 0.0005, 0.65)
    if T > 0:
        q[-1] = 1.0
    return q


def mortality_shock(q: Array, multiplier: float) -> Array:
    out = np.clip(np.asarray(q, dtype=float) * multiplier, 0.0, 1.0)
    if out.size:
        out[-1] = 1.0
    return out


def decreasing_penalties(T: int, first: float = 0.06, years: int = 6) -> Array:
    p = np.zeros(T + 1)
    for y in range(1, min(T, years) + 1):
        p[y] = max(first * (years - y + 1) / years, 0.0)
    return p


def deterministic_surrender_rates(T: int) -> Array:
    """
    Beispiel für exogene Surrender-Raten im Stil der in den Papern diskutierten
    deterministischen Policyholder-Behavior-Annahme.
    """
    s = np.zeros(T + 1)
    vals = {1: 0.06, 2: 0.05, 3: 0.04, 4: 0.03, 5: 0.02}
    for y in range(1, T + 1):
        s[y] = vals.get(y, 0.01)
    return s


def _correlated_normals(rng: np.random.Generator, shape, rho: float) -> Tuple[Array, Array]:
    z1 = rng.standard_normal(shape)
    z2 = rng.standard_normal(shape)
    rho = float(np.clip(rho, -0.999999, 0.999999))
    return z1, rho * z1 + np.sqrt(1.0 - rho * rho) * z2


def evolve_one_year(
    W: Array,
    v: Optional[Array],
    r: Optional[Array],
    market: MarketSpec,
    alpha_total: float,
    rng: np.random.Generator,
    steps_per_year: int = 12,
) -> Tuple[Array, Optional[Array], Optional[Array], Array]:
    """
    Ein-Jahres-Übergang von W inklusive Gebührenabzug alpha_total.
    Rückgabe: W_next, v_next, r_next, df_year.
    """
    W = np.asarray(W, dtype=float).copy()
    shape = W.shape
    dt = 1.0 / int(steps_per_year)
    sqrt_dt = np.sqrt(dt)
    df = np.ones_like(W)

    if market.kind == ModelKind.BS:
        for _ in range(steps_per_year):
            z = rng.standard_normal(shape)
            W *= np.exp(
                (market.r - alpha_total - 0.5 * market.sigma**2) * dt
                + market.sigma * sqrt_dt * z
            )
            df *= np.exp(-market.r * dt)
        return np.maximum(W, 0.0), None, None, df

    if market.kind in (ModelKind.HESTON, ModelKind.ONE, ModelKind.THREE_HALVES):
        if v is None:
            v = np.full_like(W, market.v0)
        else:
            v = np.asarray(v, dtype=float).copy()

        for _ in range(steps_per_year):
            zv, zs = _correlated_normals(rng, shape, market.rho)
            vp = np.maximum(v, 1e-12)

            W *= np.exp(
                (market.r - alpha_total - 0.5 * vp) * dt
                + np.sqrt(vp) * sqrt_dt * zs
            )
            df *= np.exp(-market.r * dt)

            if market.kind == ModelKind.HESTON:
                v = (
                    v
                    + market.kappa * (market.theta - vp) * dt
                    + market.volvol * np.sqrt(vp) * sqrt_dt * zv
                )
                v = np.maximum(v, 1e-12)

            elif market.kind == ModelKind.ONE:
                v = (
                    v
                    + market.kappa * (market.theta - vp) * dt
                    + market.volvol * vp * sqrt_dt * zv
                )
                v = np.maximum(v, 1e-12)

            else:
                logv = (
                    np.log(vp)
                    + (market.kappa * (market.theta - vp) - 0.5 * market.volvol**2 * vp) * dt
                    + market.volvol * np.sqrt(vp) * sqrt_dt * zv
                )
                v = np.exp(np.clip(logv, -30.0, 5.0))

        return np.maximum(W, 0.0), v, None, df

    if market.kind == ModelKind.VASICEK:
        if r is None:
            r = np.full_like(W, market.r0)
        else:
            r = np.asarray(r, dtype=float).copy()

        for _ in range(steps_per_year):
            zr, zs = _correlated_normals(rng, shape, market.rho_sr)

            if market.kappa_r > 1e-12:
                e = np.exp(-market.kappa_r * dt)
                mean = market.theta_r + (r - market.theta_r) * e
                sd = market.sigma_r * np.sqrt((1.0 - e * e) / (2.0 * market.kappa_r))
                r_new = mean + sd * zr
            else:
                r_new = r + market.sigma_r * sqrt_dt * zr

            r_avg = 0.5 * (r + r_new)
            W *= np.exp(
                (r_avg - alpha_total - 0.5 * market.sigma**2) * dt
                + market.sigma * sqrt_dt * zs
            )
            df *= np.exp(-r_avg * dt)
            r = r_new

        return np.maximum(W, 0.0), None, r, df

    raise ValueError(f"Unbekanntes Marktmodell: {market.kind}")


def _apply_ratchet(W: Array, B: Array, C: Array, contract: ContractSpec, year: int) -> Tuple[Array, Array]:
    if not contract.is_ratchet_year(year):
        return B, C

    if contract.ratchet == RatchetType.LOOKBACK:
        B_new = np.maximum(B, W)
        C_new = contract.withdrawal_rate * B_new
        return B_new, C_new

    if contract.ratchet == RatchetType.REMAINING_WBB:
        delta = np.maximum(W - B, 0.0)
        C_new = C + contract.withdrawal_rate * delta
        B_new = np.where(delta > 0.0, W, B)
        return B_new, C_new

    return B, C


def apply_action(
    W: Array,
    B: Array,
    C: Array,
    action: Literal["none", "withdraw", "surrender"],
    contract: ContractSpec,
    year: int,
) -> Tuple[Array, Array, Array, Array]:
    """
    Aktion am Event-Jahr.
    Rückgabe: cashflow_to_policyholder, W_post, B_post, C_post.
    """
    W = np.asarray(W, dtype=float)
    B = np.asarray(B, dtype=float)
    C = np.asarray(C, dtype=float)

    penalty = contract.penalties()[year] if year < contract.penalties().size else 0.0

    if action == "none":
        cash = np.zeros_like(W)
        Wp = W.copy()

        if contract.bonus_rate > 0.0:
            Bp = B * (1.0 + contract.bonus_rate)
            Cp = np.maximum(C, contract.withdrawal_rate * Bp)
        else:
            Bp = B.copy()
            Cp = C.copy()

        Bp, Cp = _apply_ratchet(Wp, Bp, Cp, contract, year)
        return cash, Wp, Bp, Cp

    if action == "withdraw":
        cash = C.copy()
        Wp = np.maximum(W - C, 0.0)

        if contract.ratchet == RatchetType.REMAINING_WBB:
            Bp = np.maximum(B - C, 0.0)
            Cp = C.copy()
        else:
            Bp = B.copy()
            Cp = C.copy()

        Bp, Cp = _apply_ratchet(Wp, Bp, Cp, contract, year)
        return cash, Wp, Bp, Cp

    if action == "surrender":
        excess = np.maximum(W - C, 0.0)
        cash = np.where(W > C, C + (1.0 - penalty) * excess, C)
        zero = np.zeros_like(W)
        return cash, zero, zero, zero

    raise ValueError(f"Unbekannte Aktion: {action}")


def surrender_cash(W: Array, B: Array, C: Array, contract: ContractSpec, year: int) -> Array:
    cash, _, _, _ = apply_action(W, B, C, "surrender", contract, year)
    return cash


def price_static_mc(
    contract: ContractSpec,
    market: MarketSpec,
    n_paths: int = 100_000,
    steps_per_year: int = 12,
    seed: Optional[int] = None,
) -> Tuple[float, float]:
    """
    Monte-Carlo-Pricing bei statischem Verhalten:
      - Tod und deterministische Surrenders werden über Wahrscheinlichkeitsgewichte integriert.
      - Ab first_withdrawal_year zieht der Policyholder C.
    Rückgabe: value, standard_error.
    """
    rng = np.random.default_rng(contract.seed if seed is None else seed)
    T = contract.maturity_years
    q = contract.q()
    surrender_rates = contract.surrender()

    W = np.full(n_paths, contract.W0, dtype=float)
    B = np.full(n_paths, contract.B0, dtype=float)
    C = np.full(n_paths, contract.C0, dtype=float)

    v = (
        np.full(n_paths, market.v0, dtype=float)
        if market.kind in (ModelKind.HESTON, ModelKind.ONE, ModelKind.THREE_HALVES)
        else None
    )
    r = np.full(n_paths, market.r0, dtype=float) if market.kind == ModelKind.VASICEK else None

    df_cum = np.ones(n_paths)
    pv = np.zeros(n_paths)
    alive = 1.0

    for year in range(1, T + 1):
        W, v, r, df_year = evolve_one_year(
            W, v, r, market, contract.alpha_total, rng, steps_per_year
        )
        df_cum *= df_year

        qy = q[year - 1]
        if contract.death_benefit:
            pv += alive * qy * df_cum * W
        alive *= 1.0 - qy

        if alive <= 1e-14:
            break

        sy = surrender_rates[year] if year < surrender_rates.size else 0.0
        if sy > 0.0:
            pv += alive * sy * df_cum * surrender_cash(W, B, C, contract, year)
            alive *= 1.0 - sy

        if year >= contract.first_withdrawal_year:
            cash, W, B, C = apply_action(W, B, C, "withdraw", contract, year)
            pv += alive * df_cum * cash
        else:
            _, W, B, C = apply_action(W, B, C, "none", contract, year)

    return float(np.mean(pv)), float(np.std(pv, ddof=1) / np.sqrt(n_paths))


def polynomial_features(
    W: Array,
    B: Array,
    C: Array,
    v: Optional[Array],
    r: Optional[Array],
    premium: float,
) -> Array:
    eps = 1e-12

    x = np.asarray(W, dtype=float) / np.maximum(np.asarray(B, dtype=float), eps)
    b = np.asarray(B, dtype=float) / premium
    c = np.asarray(C, dtype=float) / (premium * 0.05 + eps)

    feats = [
        np.ones_like(x),
        x,
        x**2,
        x**3,
        b,
        b**2,
        c,
        c**2,
        x * b,
        x * c,
        b * c,
    ]

    if v is not None:
        vv = np.asarray(v, dtype=float)
        feats += [vv, vv**2, x * vv, b * vv]

    if r is not None:
        rr = np.asarray(r, dtype=float)
        feats += [rr, rr**2, x * rr, b * rr]

    return np.column_stack(feats)


@dataclass
class Regressor:
    coef: Array
    premium: float
    uses_v: bool
    uses_r: bool

    def predict(
        self,
        W: Array,
        B: Array,
        C: Array,
        v: Optional[Array],
        r: Optional[Array],
    ) -> Array:
        X = polynomial_features(
            np.asarray(W, dtype=float),
            np.asarray(B, dtype=float),
            np.asarray(C, dtype=float),
            np.asarray(v, dtype=float) if self.uses_v and v is not None else None,
            np.asarray(r, dtype=float) if self.uses_r and r is not None else None,
            self.premium,
        )
        return np.maximum(X @ self.coef, 0.0)

    @staticmethod
    def fit(
        W: Array,
        B: Array,
        C: Array,
        v: Optional[Array],
        r: Optional[Array],
        y: Array,
        premium: float,
        ridge: float = 1e-8,
    ) -> "Regressor":
        uses_v = v is not None
        uses_r = r is not None

        X = polynomial_features(W, B, C, v if uses_v else None, r if uses_r else None, premium)
        y = np.asarray(y, dtype=float)

        xtx = X.T @ X
        xty = X.T @ y
        coef = np.linalg.solve(xtx + ridge * np.eye(xtx.shape[0]), xty)

        return Regressor(coef=coef, premium=premium, uses_v=uses_v, uses_r=uses_r)


def _sample_training_states(
    rng: np.random.Generator,
    n: int,
    contract: ContractSpec,
    market: MarketSpec,
) -> Tuple[Array, Array, Array, Optional[Array], Optional[Array]]:
    P = contract.premium

    B = P * rng.uniform(0.25, 2.5, size=n)
    if contract.ratchet == RatchetType.REMAINING_WBB:
        C = contract.withdrawal_rate * P * rng.uniform(0.5, 3.0, size=n)
    else:
        C = contract.withdrawal_rate * B

    W = B * rng.lognormal(mean=-0.10, sigma=0.75, size=n)
    W = np.clip(W, 0.0, 4.0 * P)

    v = None
    r = None

    if market.kind in (ModelKind.HESTON, ModelKind.ONE, ModelKind.THREE_HALVES):
        v_mean = max(market.theta, 1e-5)
        v = rng.lognormal(mean=np.log(v_mean) - 0.5 * 0.5**2, sigma=0.5, size=n)
        v = np.clip(v, 1e-5, 1.5)

    if market.kind == ModelKind.VASICEK:
        sd_r = max(market.sigma_r / np.sqrt(max(2.0 * market.kappa_r, 1e-6)), 0.005)
        r = rng.normal(market.theta_r, sd_r, size=n)
        r = np.clip(r, -0.05, 0.20)

    return W, B, C, v, r


def _candidate_value_one_step(
    W: Array,
    B: Array,
    C: Array,
    v: Optional[Array],
    r: Optional[Array],
    action: Literal["none", "withdraw", "surrender"],
    year: int,
    contract: ContractSpec,
    market: MarketSpec,
    next_regressor: Optional[Regressor],
    rng: np.random.Generator,
    steps_per_year: int,
    q_year: float,
) -> Array:
    cash, Wp, Bp, Cp = apply_action(W, B, C, action, contract, year)

    if action == "surrender":
        return cash

    if next_regressor is None:
        return cash

    Wn, vn, rn, df = evolve_one_year(
        Wp, v, r, market, contract.alpha_total, rng, steps_per_year
    )

    cont_alive = next_regressor.predict(Wn, Bp, Cp, vn, rn)
    death = Wn if contract.death_benefit else np.zeros_like(Wn)

    return cash + df * (q_year * death + (1.0 - q_year) * cont_alive)


def fit_lsmc_policy(
    contract: ContractSpec,
    market: MarketSpec,
    n_train: int = 50_000,
    steps_per_year: int = 12,
    seed: Optional[int] = None,
) -> Dict[int, Regressor]:
    """
    Approximate Dynamic Programming / LSMC für optimale Bang-Bang-Aktionen:
      "none", "withdraw", "surrender"

    Der Regressor pro Jahr approximiert den Wert conditional alive and before action.
    """
    rng = np.random.default_rng(contract.seed if seed is None else seed)
    T = contract.maturity_years
    q = contract.q()

    regressors: Dict[int, Regressor] = {}
    next_reg: Optional[Regressor] = None

    for year in range(T, 0, -1):
        W, B, C, v, r = _sample_training_states(rng, n_train, contract, market)

        if year < contract.first_withdrawal_year:
            actions: Tuple[Literal["none", "withdraw", "surrender"], ...] = ("none",)
        else:
            actions = ("none", "withdraw", "surrender")

        q_year = q[year] if year < T else 0.0

        vals = [
            _candidate_value_one_step(
                W,
                B,
                C,
                v,
                r,
                action,
                year,
                contract,
                market,
                next_reg,
                rng,
                steps_per_year,
                q_year,
            )
            for action in actions
        ]

        y = np.maximum.reduce(vals)
        reg = Regressor.fit(W, B, C, v, r, y, contract.premium)

        regressors[year] = reg
        next_reg = reg

    return regressors


def _choose_action(
    W: Array,
    B: Array,
    C: Array,
    v: Optional[Array],
    r: Optional[Array],
    year: int,
    contract: ContractSpec,
    market: MarketSpec,
    regressors: Dict[int, Regressor],
    rng: np.random.Generator,
    steps_per_year: int,
    inner_paths: int = 8,
) -> Array:
    if year < contract.first_withdrawal_year:
        return np.full(W.shape, "none", dtype=object)

    next_reg = regressors.get(year + 1)
    q = contract.q()
    q_year = q[year] if year < contract.maturity_years else 0.0

    action_values = {}
    for action in ("none", "withdraw", "surrender"):
        acc = np.zeros_like(W, dtype=float)
        for _ in range(max(1, inner_paths)):
            acc += _candidate_value_one_step(
                W,
                B,
                C,
                v,
                r,
                action,
                year,
                contract,
                market,
                next_reg,
                rng,
                steps_per_year,
                q_year,
            )
        action_values[action] = acc / max(1, inner_paths)

    stacked = np.vstack(
        [action_values["none"], action_values["withdraw"], action_values["surrender"]]
    )
    idx = np.argmax(stacked, axis=0)
    labels = np.array(["none", "withdraw", "surrender"], dtype=object)
    return labels[idx]


def evaluate_lsmc_policy(
    contract: ContractSpec,
    market: MarketSpec,
    regressors: Dict[int, Regressor],
    n_paths: int = 100_000,
    steps_per_year: int = 12,
    inner_paths_policy: int = 8,
    seed: Optional[int] = None,
) -> Tuple[float, float]:
    """
    Out-of-sample-Bewertung der gelernten Strategie.
    """
    rng = np.random.default_rng(contract.seed + 999 if seed is None else seed)
    T = contract.maturity_years
    q = contract.q()

    W = np.full(n_paths, contract.W0, dtype=float)
    B = np.full(n_paths, contract.B0, dtype=float)
    C = np.full(n_paths, contract.C0, dtype=float)

    v = (
        np.full(n_paths, market.v0, dtype=float)
        if market.kind in (ModelKind.HESTON, ModelKind.ONE, ModelKind.THREE_HALVES)
        else None
    )
    r = np.full(n_paths, market.r0, dtype=float) if market.kind == ModelKind.VASICEK else None

    df_cum = np.ones(n_paths)
    pv = np.zeros(n_paths)
    alive = 1.0

    for year in range(1, T + 1):
        W, v, r, df_year = evolve_one_year(
            W, v, r, market, contract.alpha_total, rng, steps_per_year
        )
        df_cum *= df_year

        qy = q[year - 1]
        if contract.death_benefit:
            pv += alive * qy * df_cum * W
        alive *= 1.0 - qy

        if alive <= 1e-14:
            break

        action = _choose_action(
            W,
            B,
            C,
            v,
            r,
            year,
            contract,
            market,
            regressors,
            rng,
            steps_per_year,
            inner_paths_policy,
        )

        for label in ("none", "withdraw", "surrender"):
            mask = action == label
            if not np.any(mask):
                continue

            cash, Wp, Bp, Cp = apply_action(W[mask], B[mask], C[mask], label, contract, year)
            pv[mask] += alive * df_cum[mask] * cash

            W[mask] = Wp
            B[mask] = Bp
            C[mask] = Cp

    return float(np.mean(pv)), float(np.std(pv, ddof=1) / np.sqrt(n_paths))


def price_lsmc_optimal(
    contract: ContractSpec,
    market: MarketSpec,
    n_train: int = 50_000,
    n_eval: int = 100_000,
    steps_per_year: int = 12,
    inner_paths_policy: int = 8,
    seed: Optional[int] = None,
) -> Tuple[float, float, Dict[int, Regressor]]:
    """
    LSMC-Preis unter näherungsweise optimalem Policyholder-Verhalten.

    Der statische Withdrawal-Pfad ist eine zulässige Strategie. Daher wird der
    gemeldete Wert als max(gelernte Strategie, statische Strategie) ausgegeben.
    """
    regs = fit_lsmc_policy(
        contract,
        market,
        n_train=n_train,
        steps_per_year=steps_per_year,
        seed=seed,
    )

    learned_value, learned_se = evaluate_lsmc_policy(
        contract,
        market,
        regs,
        n_paths=n_eval,
        steps_per_year=steps_per_year,
        inner_paths_policy=inner_paths_policy,
        seed=None if seed is None else seed + 1,
    )

    static_value, static_se = price_static_mc(
        contract,
        market,
        n_paths=n_eval,
        steps_per_year=steps_per_year,
        seed=None if seed is None else seed + 2,
    )

    if static_value > learned_value:
        return static_value, static_se, regs

    return learned_value, learned_se, regs


def fair_fee_bisection(
    contract: ContractSpec,
    market: MarketSpec,
    target_value: Optional[float] = None,
    method: Literal["static", "lsmc"] = "static",
    lo: float = 0.0,
    hi: float = 0.10,
    tol: float = 1e-4,
    max_iter: int = 40,
    **pricing_kwargs,
) -> Tuple[float, float]:
    """
    Fair alpha_g: löst PV(alpha_g) = target_value.
    Standardziel ist die gezahlte Prämie.
    """
    target = contract.premium if target_value is None else float(target_value)

    def value_minus_target(alpha: float) -> float:
        c = replace(contract, alpha_g=alpha)
        if method == "static":
            val, _ = price_static_mc(c, market, **pricing_kwargs)
        elif method == "lsmc":
            val, _, _ = price_lsmc_optimal(c, market, **pricing_kwargs)
        else:
            raise ValueError("method muss 'static' oder 'lsmc' sein.")
        return val - target

    flo = value_minus_target(lo)
    fhi = value_minus_target(hi)

    attempts = 0
    while flo * fhi > 0.0 and attempts < 8:
        hi *= 1.75
        fhi = value_minus_target(hi)
        attempts += 1

    if flo * fhi > 0.0:
        raise RuntimeError(
            f"Fee-Bracket findet keine Nullstelle: f({lo})={flo:.6f}, f({hi})={fhi:.6f}"
        )

    mid = 0.5 * (lo + hi)
    fmid = value_minus_target(mid)

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fmid = value_minus_target(mid)

        if abs(fmid) < tol:
            break

        if flo * fmid <= 0.0:
            hi = mid
            fhi = fmid
        else:
            lo = mid
            flo = fmid

    return mid, fmid + target


def greeks_static(
    contract: ContractSpec,
    market: MarketSpec,
    bump_account: float = 1e-3,
    bump_vol: float = 1e-3,
    n_paths: int = 100_000,
    steps_per_year: int = 12,
    seed: Optional[int] = None,
) -> Dict[str, float]:
    """
    Finite-Difference-Greeks für statisches Pricing.
    Delta/Gamma bumpen nur W0, nicht die Benefit Base B0.
    Vega bumpet sigma bei BS/Vasicek bzw. v0/theta bei SV-Modellen näherungsweise.
    """
    base_seed = contract.seed if seed is None else seed
    W0 = contract.W0

    c_up = replace(contract, initial_account=W0 * (1.0 + bump_account))
    c_dn = replace(contract, initial_account=W0 * (1.0 - bump_account))

    v0, _ = price_static_mc(
        contract, market, n_paths=n_paths, steps_per_year=steps_per_year, seed=base_seed
    )
    vu, _ = price_static_mc(
        c_up, market, n_paths=n_paths, steps_per_year=steps_per_year, seed=base_seed
    )
    vd, _ = price_static_mc(
        c_dn, market, n_paths=n_paths, steps_per_year=steps_per_year, seed=base_seed
    )

    dS = W0 * bump_account
    delta = (vu - vd) / (2.0 * dS)
    gamma = (vu - 2.0 * v0 + vd) / (dS * dS)

    if market.kind in (ModelKind.BS, ModelKind.VASICEK):
        m_up = replace(market, sigma=market.sigma + bump_vol)
        m_dn = replace(market, sigma=max(market.sigma - bump_vol, 1e-6))
        dv = bump_vol
    else:
        m_up = replace(market, v0=market.v0 + bump_vol, theta=market.theta + bump_vol)
        m_dn = replace(
            market,
            v0=max(market.v0 - bump_vol, 1e-8),
            theta=max(market.theta - bump_vol, 1e-8),
        )
        dv = bump_vol

    vu_vol, _ = price_static_mc(
        contract, m_up, n_paths=n_paths, steps_per_year=steps_per_year, seed=base_seed
    )
    vd_vol, _ = price_static_mc(
        contract, m_dn, n_paths=n_paths, steps_per_year=steps_per_year, seed=base_seed
    )
    vega = (vu_vol - vd_vol) / (2.0 * dv)

    return {"value": v0, "delta": delta, "gamma": gamma, "vega": vega}


def run_demo() -> None:
    """
    Kleine Rechenprobe. Für belastbare Werte n_paths/n_train deutlich erhöhen.
    """
    T = 30

    q = illustrative_gompertz_q(T)
    penalties = decreasing_penalties(T, first=0.06, years=6)

    contract = ContractSpec(
        premium=100.0,
        maturity_years=T,
        withdrawal_rate=0.05,
        alpha_g=0.012,
        alpha_m=0.005,
        ratchet=RatchetType.LOOKBACK,
        ratchet_frequency_years=1,
        bonus_rate=0.02,
        q_mortality=q,
        surrender_penalties=penalties,
        surrender_rates=None,
        seed=42,
    )

    bs = MarketSpec(kind=ModelKind.BS, r=0.04, sigma=0.20)

    heston = MarketSpec(
        kind=ModelKind.HESTON,
        r=0.04,
        v0=0.04,
        theta=0.04,
        kappa=1.5,
        volvol=0.35,
        rho=-0.5,
    )

    vasicek = MarketSpec(
        kind=ModelKind.VASICEK,
        sigma=0.20,
        r0=0.04,
        theta_r=0.04,
        kappa_r=0.20,
        sigma_r=0.01,
        rho_sr=0.25,
    )

    static_value, static_se = price_static_mc(
        contract, bs, n_paths=20_000, steps_per_year=12, seed=1
    )
    print(f"Static BS value = {static_value:.4f} ± {1.96 * static_se:.4f}")

    fee, value_at_fee = fair_fee_bisection(
        contract,
        bs,
        method="static",
        lo=0.0,
        hi=0.08,
        tol=2e-3,
        n_paths=20_000,
        steps_per_year=12,
        seed=7,
    )
    print(f"Fair alpha_g static BS ≈ {fee:.4%}; value={value_at_fee:.4f}")

    opt_value, opt_se, _ = price_lsmc_optimal(
        contract,
        heston,
        n_train=8_000,
        n_eval=10_000,
        steps_per_year=6,
        inner_paths_policy=4,
        seed=123,
    )
    print(f"Approx. optimal LSMC Heston value = {opt_value:.4f} ± {1.96 * opt_se:.4f}")

    vasicek_value, vasicek_se = price_static_mc(
        contract, vasicek, n_paths=20_000, steps_per_year=12, seed=4
    )
    print(f"Static Vasicek/BS-HW value = {vasicek_value:.4f} ± {1.96 * vasicek_se:.4f}")

    g = greeks_static(contract, bs, n_paths=20_000, steps_per_year=12, seed=11)
    print("Static BS Greeks:", {k: round(v, 6) for k, v in g.items()})

    shocked = replace(contract, q_mortality=mortality_shock(q, 1.10))
    shock_value, shock_se = price_static_mc(
        shocked, bs, n_paths=20_000, steps_per_year=12, seed=1
    )
    print(f"+10% mortality shock value = {shock_value:.4f} ± {1.96 * shock_se:.4f}")

    ds_contract = replace(contract, surrender_rates=deterministic_surrender_rates(T))
    ds_value, ds_se = price_static_mc(ds_contract, bs, n_paths=20_000, steps_per_year=12, seed=1)
    print(f"Static BS with deterministic surrender = {ds_value:.4f} ± {1.96 * ds_se:.4f}")


if __name__ == "__main__":
    run_demo()