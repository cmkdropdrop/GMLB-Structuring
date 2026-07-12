"""ARCHIVED: optimal behaviour via regression-based stochastic control.

This module is retained as research history.  It is intentionally absent from
the public package API, CLI, projection, pricing, capital and profitability
paths.  The active model uses the CSV-configured dynamic statistical functions
in :mod:`agile_engine.behavior`; do not use this module for base-case results.

Worst-case (rational-exercise) valuation of the AGILE contract following
Huang/Kwok (regression-based Monte Carlo for stochastic control of lifelong
guarantees) and the approximate-dynamic-programming layout of the reference
implementation ``more_code.py`` (randomised state sampling per backward step).
The GHQC dynamic-programming work of Shevchenko/Luo (2016/17) is a method
reference; a numerical cross-check against its implementation is still a
production-validation gap.

Decision grid and actions
-------------------------
Annual (anniversary) decisions:

* growth phase:  CONTINUE | START_INCOME (>= 1st anniversary) | SURRENDER
                 | FREE_WITHDRAWAL | FREE_PLUS_EXCESS_WITHDRAWAL
* income phase:  CONTINUE | SURRENDER (full withdrawal, guarantee forfeited)
                 | EXCESS_WITHDRAWAL

The policyholder seeks to maximise the market-consistent value of their own
cashflows.  Because the reported value evaluates one fitted, adapted policy
out of sample, it is a lower bound on the true rational-policyholder value
(which itself is the conservative behavioural liability target).

Adaptedness: forward-pass decisions are made from per-year continuation-value
regressions on time-n states only (IV, income, v_t, r_t) — the realised
year-n return and discount never enter a decision, mirroring the
inner-simulation decision rule of the reference implementation
(more_code.py `_choose_action`). The realised transitions enter only the
out-of-sample evaluation of the resulting (admissible) policy, so the
reported optimal value is a valid lower bound of the true optimal value and
free of look-ahead bias.

Approximations (documented): annual grid (no intra-year DVA), fees applied as
an annual factor, income paid annually in arrears, no Age Pension+, MVA per
the engine's rate-based formula, single or joint life via annual decrements.
Joint-life (Spouse-Insured) decrements are taken from the unconditional
last-survivor curve from issue — election dates vary per path under the
optimal policy, so the election-date conditioning applied by the monthly
projection engine (v1.0.3) is not replicated here; the effect is second
order for the optionality *uplift* reported by this layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from .curves import YieldCurve
from .esg import Measure, ScenarioSet, STEPS_PER_YEAR, simulate
from .esg import ESGConfig
from .mortality import MortalityTable
from .product import (AgileProduct, IncomeType, Index, InvestmentOption,
                      PolicySpec, SpouseDeathElection, INCOME_PHASE_OPTION)
from .crediting import credited_return

Array = NDArray[np.float64]


# ---------------------------------------------------------------------------
# Configuration / result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LSMCSettings:
    model: str = "black_scholes"
    n_train: int = 30_000
    n_eval: int = 50_000
    seed: int = 4711
    horizon_years: Optional[int] = None      # default: to age 105
    ridge: float = 1e-8
    #: include partial-withdrawal actions (free amount; free + excess) in the
    #: control set, on a discrete fraction grid in the spirit of the
    #: discretised optimal-withdrawal DP of Shevchenko/Luo (2016) and the
    #: candidate-grid pricer in the reference library (gmwb_models.py).
    include_withdrawals: bool = True
    #: excess withdrawal as fraction of IV tested by the optimiser.
    withdrawal_fraction: float = 0.10

    def __post_init__(self) -> None:
        if self.model not in ("black_scholes", "heston", "hull_white_bs",
                              "heston_hull_white"):
            raise ValueError("Unknown LSMC market model.")
        for name, value in (("n_train", self.n_train), ("n_eval", self.n_eval)):
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) \
                    or value <= 0:
                raise ValueError(f"{name} must be a positive integer.")
        if isinstance(self.seed, bool) or not isinstance(self.seed, (int, np.integer)) \
                or self.seed < 0:
            raise ValueError("seed must be a non-negative integer.")
        if self.horizon_years is not None and (
                isinstance(self.horizon_years, bool)
                or not isinstance(self.horizon_years, (int, np.integer))
                or self.horizon_years <= 0):
            raise ValueError("LSMC horizon_years must be a positive integer.")
        if not np.isfinite(self.ridge) or self.ridge < 0.0:
            raise ValueError("ridge must be finite and non-negative.")
        if not np.isfinite(self.withdrawal_fraction) \
                or not 0.0 < self.withdrawal_fraction < 1.0:
            raise ValueError("withdrawal_fraction must be in (0, 1).")
        if not isinstance(self.include_withdrawals, (bool, np.bool_)):
            raise ValueError("include_withdrawals must be boolean.")


@dataclass
class LSMCResult:
    value_optimal: float
    value_static: float
    optionality_uplift: float
    exercise_rate_by_year: Array          # share electing income per year (eval run)
    surrender_rate_by_year: Array
    withdrawal_rate_by_year: Array        # share taking partial withdrawals
    settings: LSMCSettings

    def summary(self) -> Dict[str, float]:
        return dict(value_optimal=self.value_optimal, value_static=self.value_static,
                    optionality_uplift=self.optionality_uplift)


# ---------------------------------------------------------------------------
# Regression helpers (pattern from more_code.py, extended feature set)
# ---------------------------------------------------------------------------

def _features(iv: Array, inc: Array, v: Optional[Array], r: Optional[Array],
              p0: float) -> Array:
    x = iv / p0
    y = inc / (0.06 * p0)
    feats = [np.ones_like(x), x, x ** 2, x ** 3, y, y ** 2, x * y]
    if v is not None:
        feats += [v, v * x]
    if r is not None:
        feats += [r, r * x, r * y]
    return np.column_stack(feats)


@dataclass
class _Reg:
    coef: Array
    uses_v: bool
    uses_r: bool
    p0: float

    def predict(self, iv: Array, inc: Array, v: Optional[Array], r: Optional[Array]) -> Array:
        X = _features(iv, inc, v if self.uses_v else None,
                      r if self.uses_r else None, self.p0)
        return np.maximum(X @ self.coef, 0.0)

    @staticmethod
    def fit(iv: Array, inc: Array, v: Optional[Array], r: Optional[Array],
            target: Array, p0: float, ridge: float) -> "_Reg":
        X = _features(iv, inc, v, r, p0)
        xtx = X.T @ X + ridge * np.eye(X.shape[1])
        rhs = X.T @ target
        try:
            coef = np.linalg.solve(xtx, rhs)
        except np.linalg.LinAlgError:
            # Rank-deficient exercise sets occur naturally at early decision
            # dates.  A least-squares fallback is deterministic and preferable
            # to aborting an otherwise valid run when ridge=0 was requested.
            coef = np.linalg.lstsq(X, target, rcond=None)[0]
        return _Reg(coef=coef, uses_v=v is not None, uses_r=r is not None, p0=p0)


# ---------------------------------------------------------------------------
# Annual market data extracted from a monthly ScenarioSet
# ---------------------------------------------------------------------------

@dataclass
class _AnnualMarket:
    credit_alloc: Array      # (n_paths, n_years) credited return, growth allocation
    credit_tp: Array         # credited return of the income-phase option
    disc_year: Array         # (n_paths, n_years) one-year discount factor D_{n+1}/D_n
    v_aus: Optional[Array]   # (n_paths, n_years+1) variance state at anniversaries
    r_short: Optional[Array]
    z_mva: Array             # (n_paths, n_years+1) pathwise zero for the MVA tenor


def _annual_market(scen: ScenarioSet, product: AgileProduct, policy: PolicySpec,
                   n_years: int) -> _AnnualMarket:
    alloc_opts = [InvestmentOption(o) for o in policy.allocation]
    alloc_w = np.array([policy.allocation[o] for o in alloc_opts])
    n_paths = scen.n_paths

    credit_alloc = np.zeros((n_paths, n_years))
    credit_tp = np.zeros((n_paths, n_years))
    disc_year = np.zeros((n_paths, n_years))
    for n in range(n_years):
        k0, k1 = n * STEPS_PER_YEAR, (n + 1) * STEPS_PER_YEAR
        for opt, wt in zip(alloc_opts, alloc_w):
            ratio = scen.index_levels[opt.index][:, k1] / scen.index_levels[opt.index][:, k0]
            credit_alloc[:, n] += wt * np.asarray(credited_return(
                ratio - 1.0, opt.protection, product.caps.cap(opt, n)))
        ratio_tp = (scen.index_levels[INCOME_PHASE_OPTION.index][:, k1]
                    / scen.index_levels[INCOME_PHASE_OPTION.index][:, k0])
        credit_tp[:, n] = np.asarray(credited_return(
            ratio_tp - 1.0, INCOME_PHASE_OPTION.protection,
            product.caps.cap(INCOME_PHASE_OPTION, n)))
        disc_year[:, n] = scen.discount[:, k1] / np.maximum(scen.discount[:, k0], 1e-300)

    v_aus = None
    if scen.variance is not None:
        v_aus = scen.variance[Index.AUS_EQUITY][:, ::STEPS_PER_YEAR][:, :n_years + 1]
    r_short = scen.short_rate[:, ::STEPS_PER_YEAR][:, :n_years + 1] \
        if scen.stochastic_rates else None

    z_mva = np.zeros((n_paths, n_years + 1))
    mva_T = product.withdrawals.mva_period_years
    for n in range(n_years + 1):
        tau = mva_T - n
        if tau > 0:
            z_mva[:, n] = scen.zero_rate(n * STEPS_PER_YEAR, tau)
    return _AnnualMarket(credit_alloc, credit_tp, disc_year, v_aus, r_short, z_mva)


# ---------------------------------------------------------------------------
# Optimal-exercise valuation
# ---------------------------------------------------------------------------

def value_optimal_behaviour(product: AgileProduct, policy: PolicySpec,
                            esg_config: ESGConfig, mortality: MortalityTable,
                            settings: LSMCSettings = LSMCSettings()) -> LSMCResult:
    """Backward LSMC fit + forward out-of-sample evaluation."""
    policy.validate_against(product)
    if policy.age_pension_plus:
        raise NotImplementedError("LSMC does not implement Age Pension+ CAS mechanics.")
    if abs(float(policy.income_start_year) - round(float(policy.income_start_year))) > 1e-9:
        raise ValueError("LSMC uses an annual decision grid and requires an "
                         "anniversary income_start_year. Use value_contract "
                         "for off-anniversary DVA-reset valuation.")
    p0 = policy.net_initial_investment
    horizon = (settings.horizon_years if settings.horizon_years is not None
               else int(min(105 - policy.age, 40)))
    n_years = int(horizon)
    fee = product.fees.total
    curve = esg_config.curve

    # annual decrements
    issue_offset = policy.commencement_year - mortality.base_year
    q1 = np.array([mortality.q(policy.age + n, policy.sex,
                               years_from_base=issue_offset + n,
                               projection_duration=n)
                   for n in range(n_years + 1)])
    spouse_continues = (policy.spouse
                        and policy.spouse_age is not None
                        and policy.spouse_death_election
                        == SpouseDeathElection.CONTINUE_INCOME)
    if spouse_continues:
        sex2 = policy.spouse_sex or policy.sex
        s1 = mortality.survival_curve(policy.age, policy.sex, n_years + 1,
                                      years_from_base=issue_offset)
        s2 = mortality.survival_curve(policy.spouse_age, sex2, n_years + 1,
                                      years_from_base=issue_offset)
        s_ls = s1 + s2 - s1 * s2
        q_income = 1.0 - s_ls[1:] / np.maximum(s_ls[:-1], 1e-300)
        q_income = np.append(q_income, 1.0)
    else:
        q_income = q1

    # residual annuity factor at the horizon (income phase tail value)
    z_long = float(curve.zero(30.0))
    joint_age = policy.spouse_age + n_years if spouse_continues else None
    joint_sex = (policy.spouse_sex or policy.sex) if spouse_continues else None
    tail_af = mortality.annuity_factor(policy.age + n_years, policy.sex, z_long,
                                       years_from_base=issue_offset + n_years,
                                       joint_age=joint_age,
                                       joint_sex=joint_sex,
                                       projection_duration_start=n_years)

    def income_rate(year: int) -> float:
        return product.income_rates.lifetime_income_rate(
            policy.age, policy.sex, policy.income_type, policy.spouse,
            year, policy.spouse_age, policy.spouse_sex,
            policy.age_pension_plus)

    def surrender_value(iv: Array, year: int, z_now: Array, in_growth: bool) -> Array:
        tau = product.withdrawals.mva_period_years - year
        if tau <= 0:
            return iv
        z0 = float(np.expm1(curve.zero(max(tau, 1e-6))))
        f = product.mva.factor(z0, z_now, tau)
        free = product.withdrawals.free_withdrawal_pct_of_initial * p0 if in_growth else 0.0
        excess = np.maximum(iv - free, 0.0)
        return iv - np.clip(excess * f, 0.0, excess)

    # ------------------------------------------------------------------ #
    # training pass (backward)
    # ------------------------------------------------------------------ #
    scen_tr = simulate(settings.model, esg_config, float(n_years),
                       settings.n_train, measure=Measure.RISK_NEUTRAL,
                       seed=settings.seed)
    mkt = _annual_market(scen_tr, product, policy, n_years)
    rng = np.random.default_rng(settings.seed + 1)

    reg_growth: Dict[int, _Reg] = {}
    reg_income: Dict[int, _Reg] = {}
    # Adapted decision signals: E[one-year continuation | time-n state].
    # The forward pass must not see the realised year-n return/discount when
    # choosing an action (cf. more_code.py `_choose_action`, which averages
    # inner simulations for the same reason), so decisions use these
    # continuation regressions instead of realised transitions.
    cont_reg_growth: Dict[int, _Reg] = {}
    cont_reg_income: Dict[int, _Reg] = {}

    def cont_growth(n: int, iv: Array) -> Array:
        """Value at year n (pre-action) if CONTINUE in growth over [n, n+1)."""
        iv_end = iv * (1.0 + mkt.credit_alloc[:, n]) * (1.0 - fee)
        disc = mkt.disc_year[:, n]
        q = q1[n]
        v_next = mkt.v_aus[:, n + 1] if mkt.v_aus is not None else None
        r_next = mkt.r_short[:, n + 1] if mkt.r_short is not None else None
        if n + 1 >= n_years:
            cont = iv_end
        elif (n + 1) in reg_growth:
            cont = reg_growth[n + 1].predict(iv_end, np.zeros_like(iv_end), v_next, r_next)
        else:
            cont = iv_end
        return disc * (q * iv_end + (1.0 - q) * cont)

    def cont_income(n: int, iv: Array, inc: Array) -> Array:
        """Value at year n (pre-action) if CONTINUE in income over [n, n+1)."""
        credit = mkt.credit_tp[:, n]
        inc_next = inc * (1.0 + credit) if policy.income_type == IncomeType.RISING else inc
        iv_pre_payment = iv * (1.0 + credit) * (1.0 - fee)
        iv_end = np.maximum(iv_pre_payment - inc, 0.0)
        disc = mkt.disc_year[:, n]
        q = q_income[n]
        v_next = mkt.v_aus[:, n + 1] if mkt.v_aus is not None else None
        r_next = mkt.r_short[:, n + 1] if mkt.r_short is not None else None
        if n + 1 >= n_years:
            # A terminal approximation cannot add the full account and the
            # full annuity: future income first consumes that same account.
            # max(account, annuity value) is an account-aware lower-order
            # closeout; production use still requires horizon convergence.
            cont = np.maximum(iv_end, inc_next * float(tail_af))
        elif (n + 1) in reg_income:
            cont = reg_income[n + 1].predict(iv_end, inc_next, v_next, r_next)
        else:
            cont = np.maximum(iv_end, inc_next * float(tail_af))
        # Deaths receive pre-payment IV; only survivors to the arrears payment
        # date receive income and continuation value.
        return disc * (q * iv_pre_payment + (1.0 - q) * (inc + cont))

    typical_rate = income_rate(min(max(policy.income_start_year, 1), 15))
    free_allow = product.withdrawals.free_withdrawal_pct_of_initial * p0
    alpha = settings.withdrawal_fraction

    def mva_f(n: int, z_n: Array) -> Array:
        tau = product.withdrawals.mva_period_years - n
        if tau <= 0:
            return np.zeros_like(z_n)
        z0 = float(np.expm1(curve.zero(max(tau, 1e-6))))
        return np.asarray(product.mva.factor(z0, z_n, tau))

    def partial_amount(iv: Array, desired: Array | float) -> Array:
        """Contractually admissible partial-withdrawal amount."""
        legal_max = np.minimum(product.withdrawals.max_withdrawal_pct_of_iv * iv,
                               np.maximum(iv - product.withdrawals.min_residual_value,
                                          0.0))
        amount = np.minimum(np.maximum(np.asarray(desired, dtype=float), 0.0),
                            legal_max)
        return np.where(amount >= product.withdrawals.min_withdrawal, amount, 0.0)

    def growth_withdraw_value(n, iv, z_n, excess_frac):
        """Free amount first (no MVA), then optional excess (MVA in window)."""
        free = partial_amount(iv, np.minimum(free_allow, iv))
        iv_a = iv - free
        total_limit = partial_amount(iv, iv)
        excess = np.minimum(partial_amount(iv_a, excess_frac * iv_a),
                            np.maximum(total_limit - free, 0.0))
        f = mva_f(n, z_n)
        cash = free + excess * (1.0 - f)
        return cash + cont_growth(n, iv_a - excess)

    def income_withdraw_value(n, iv, inc, z_n, excess_frac):
        """Excess withdrawal: MVA in window, proportional income reduction
        (PDS 15.3: reduction = (withdrawal + MVA)/IV = excess_frac)."""
        gross = partial_amount(iv, excess_frac * iv)
        f = mva_f(n, z_n)
        cash = gross * (1.0 - f)
        reduction = np.divide(gross, np.maximum(iv, 1e-300),
                              out=np.zeros_like(iv), where=iv > 0.0)
        return cash + cont_income(n, iv - gross, inc * (1.0 - reduction))

    for n in range(n_years - 1, 0, -1):
        v_n = mkt.v_aus[:, n] if mkt.v_aus is not None else None
        r_n = mkt.r_short[:, n] if mkt.r_short is not None else None
        z_n = mkt.z_mva[:, n]

        # ---- income-phase regressor ---------------------------------- #
        iv_s = p0 * np.clip(rng.lognormal(-0.4, 0.9, settings.n_train), 0.0, 5.0)
        inc_s = typical_rate * p0 * rng.uniform(0.4, 1.8, settings.n_train)
        cont_i = cont_income(n, iv_s, inc_s)
        vals_i = [cont_i,
                  surrender_value(iv_s, n, z_n, in_growth=False)]
        if settings.include_withdrawals:
            vals_i.append(income_withdraw_value(n, iv_s, inc_s, z_n, alpha))
        target = np.maximum.reduce(vals_i)
        reg_income[n] = _Reg.fit(iv_s, inc_s, v_n, r_n, target, p0, settings.ridge)
        cont_reg_income[n] = _Reg.fit(iv_s, inc_s, v_n, r_n, cont_i, p0,
                                      settings.ridge)

        # ---- growth-phase regressor ----------------------------------- #
        iv_g = p0 * np.clip(rng.lognormal(-0.05, 0.45, settings.n_train), 0.05, 4.0)
        cont_g = cont_growth(n, iv_g)
        vals = [cont_g]
        if n >= max(product.min_years_before_income, 1):
            inc_new = iv_g * income_rate(n)
            vals.append(cont_income(n, iv_g, inc_new))
        vals.append(surrender_value(iv_g, n, z_n, in_growth=True))
        if settings.include_withdrawals:
            vals.append(growth_withdraw_value(n, iv_g, z_n, 0.0))
            vals.append(growth_withdraw_value(n, iv_g, z_n, alpha))
        target_g = np.maximum.reduce(vals)
        reg_growth[n] = _Reg.fit(iv_g, np.zeros_like(iv_g), v_n, r_n, target_g,
                                 p0, settings.ridge)
        cont_reg_growth[n] = _Reg.fit(iv_g, np.zeros_like(iv_g), v_n, r_n,
                                      cont_g, p0, settings.ridge)

    # ------------------------------------------------------------------ #
    # evaluation pass (forward, out of sample)
    # ------------------------------------------------------------------ #
    scen_ev = simulate(settings.model, esg_config, float(n_years),
                       settings.n_eval, measure=Measure.RISK_NEUTRAL,
                       seed=settings.seed + 99)
    mkt_ev = _annual_market(scen_ev, product, policy, n_years)

    def run_forward(optimal: bool) -> Tuple[float, Array, Array, Array]:
        n_paths = settings.n_eval
        iv = np.full(n_paths, p0)
        inc = np.zeros(n_paths)
        phase = np.zeros(n_paths, dtype=np.int8)     # 0 growth 1 income 2 out
        w = np.ones(n_paths)
        disc_cum = np.ones(n_paths)
        pv = np.zeros(n_paths)
        elect_rate = np.zeros(n_years)
        surr_rate = np.zeros(n_years)
        wd_rate = np.zeros(n_years)
        with_wd = optimal and settings.include_withdrawals

        for n in range(n_years):
            v_n = mkt_ev.v_aus[:, n] if mkt_ev.v_aus is not None else None
            r_n = mkt_ev.r_short[:, n] if mkt_ev.r_short is not None else None
            z_n = mkt_ev.z_mva[:, n]
            growth = phase == 0
            income = phase == 1

            # --- decisions at anniversary n (n>=1) ---------------------- #
            if n >= 1:
                tau_mva = product.withdrawals.mva_period_years - n
                if tau_mva > 0:
                    z0_n = float(np.expm1(curve.zero(max(tau_mva, 1e-6))))
                    f_mva = np.asarray(product.mva.factor(z0_n, z_n, tau_mva))
                else:
                    f_mva = np.zeros(n_paths)
                if optimal:
                    # Adapted decision signals: candidate values are built
                    # from the time-n continuation regressions and exact
                    # time-n cash amounts only. The realised year-n return /
                    # discount must not enter the decision (no look-ahead);
                    # it enters the *evaluation* below through the actual
                    # state evolution.
                    def dec_growth(iv_arr: Array) -> Array:
                        if n in cont_reg_growth:
                            return cont_reg_growth[n].predict(
                                iv_arr, np.zeros_like(iv_arr), v_n, r_n)
                        return iv_arr

                    def dec_income(iv_arr: Array, inc_arr: Array) -> Array:
                        if n in cont_reg_income:
                            return cont_reg_income[n].predict(iv_arr, inc_arr,
                                                              v_n, r_n)
                        return iv_arr + inc_arr * float(tail_af)

                    # growth-phase action set: 0 continue, 1 start income,
                    # 2 surrender, 3 free withdrawal, 4 free + excess
                    # (discrete withdrawal grid, cf. Shevchenko/Luo 2016)
                    vg_cont = dec_growth(iv)
                    inc_new = iv * income_rate(n)
                    vg_inc = dec_income(iv, inc_new)
                    vg_surr = surrender_value(iv, n, z_n, in_growth=True)
                    if n < max(product.min_years_before_income, 1):
                        vg_inc = np.full_like(vg_inc, -np.inf)
                    cands_g = [vg_cont, vg_inc, vg_surr]
                    if with_wd:
                        free_g = partial_amount(iv, np.minimum(free_allow, iv))
                        iv_af = iv - free_g
                        total_limit = partial_amount(iv, iv)
                        ex_g = np.minimum(partial_amount(iv_af, alpha * iv_af),
                                          np.maximum(total_limit - free_g, 0.0))
                        cash_free = free_g
                        cash_ex = free_g + ex_g * (1.0 - f_mva)
                        cands_g.append(cash_free + dec_growth(iv_af))
                        cands_g.append(cash_ex + dec_growth(iv_af - ex_g))
                    best = np.argmax(np.vstack(cands_g), axis=0)

                    elect = growth & (best == 1)
                    surr_g = growth & (best == 2)
                    wd_free_g = growth & (best == 3) if with_wd else np.zeros_like(growth)
                    wd_ex_g = growth & (best == 4) if with_wd else np.zeros_like(growth)

                    # income-phase action set: 0 continue, 1 surrender,
                    # 2 excess withdrawal (proportional income reduction)
                    vi_cont = dec_income(iv, inc)
                    vi_surr = surrender_value(iv, n, z_n, in_growth=False)
                    cands_i = [vi_cont, vi_surr]
                    if with_wd:
                        gross_i = partial_amount(iv, alpha * iv)
                        red_i = np.divide(gross_i, np.maximum(iv, 1e-300),
                                          out=np.zeros_like(iv), where=iv > 0.0)
                        cands_i.append(gross_i * (1.0 - f_mva)
                                       + dec_income(iv - gross_i,
                                                    inc * (1.0 - red_i)))
                    best_i = np.argmax(np.vstack(cands_i), axis=0)
                    surr_i = income & (best_i == 1) & (iv > 0)
                    wd_i = income & (best_i == 2) if with_wd else np.zeros_like(income)
                else:
                    elect = growth & (n >= policy.income_start_year)
                    surr_g = np.zeros_like(growth)
                    surr_i = np.zeros_like(growth)
                    wd_free_g = np.zeros_like(growth)
                    wd_ex_g = np.zeros_like(growth)
                    wd_i = np.zeros_like(growth)

                if elect.any():
                    inc = np.where(elect, iv * income_rate(n), inc)
                    phase = np.where(elect, 1, phase).astype(np.int8)
                    elect_rate[n] = float(np.mean(w * elect))
                surr = surr_g | surr_i
                if surr.any():
                    sv_g = surrender_value(iv, n, z_n, in_growth=True)
                    sv_i = surrender_value(iv, n, z_n, in_growth=False)
                    sv = np.where(surr_g, sv_g, sv_i)
                    pv += np.where(surr, w * disc_cum * sv, 0.0)
                    phase = np.where(surr, 2, phase).astype(np.int8)
                    surr_rate[n] = float(np.mean(w * surr))
                wd_any = wd_free_g | wd_ex_g | wd_i
                if wd_any.any():
                    free_g = partial_amount(iv, np.minimum(free_allow, iv))
                    iv_af = iv - free_g
                    total_limit = partial_amount(iv, iv)
                    ex_g = np.minimum(partial_amount(iv_af, alpha * iv_af),
                                      np.maximum(total_limit - free_g, 0.0))
                    gross_i = partial_amount(iv, alpha * iv)
                    cash = np.where(wd_free_g, free_g,
                                    np.where(wd_ex_g, free_g + ex_g * (1.0 - f_mva),
                                             np.where(wd_i, gross_i * (1.0 - f_mva),
                                                      0.0)))
                    pv += w * disc_cum * cash
                    red_i = np.divide(gross_i, np.maximum(iv, 1e-300),
                                      out=np.zeros_like(iv), where=iv > 0.0)
                    iv = np.where(wd_free_g, iv_af,
                                  np.where(wd_ex_g, iv_af - ex_g,
                                           np.where(wd_i, iv - gross_i, iv)))
                    inc = np.where(wd_i, inc * (1.0 - red_i), inc)
                    wd_rate[n] = float(np.mean(w * wd_any))
                growth = phase == 0
                income = phase == 1

            # --- evolve year n -> n+1 ----------------------------------- #
            credit = np.where(growth, mkt_ev.credit_alloc[:, n],
                              np.where(income, mkt_ev.credit_tp[:, n], 0.0))
            iv_pre_payment = np.where(
                phase < 2, iv * (1.0 + credit) * (1.0 - fee), 0.0)
            pay = np.where(income, inc, 0.0)
            iv_end = np.where(income, np.maximum(iv_pre_payment - pay, 0.0),
                              iv_pre_payment)
            disc_next = disc_cum * mkt_ev.disc_year[:, n]

            q = np.where(income, q_income[n], q1[n])
            q = np.where(phase < 2, q, 0.0)
            # Payments are in arrears: deaths receive pre-payment IV and only
            # survivors to the payment date receive the annual instalment.
            pv += w * disc_next * (q * iv_pre_payment + (1.0 - q) * pay)
            w = w * (1.0 - q)
            if policy.income_type == IncomeType.RISING:
                inc = np.where(income, inc * (1.0 + mkt_ev.credit_tp[:, n]), inc)
            iv = iv_end
            disc_cum = disc_next
            phase = np.where((phase == 0) & (iv <= 0), 2, phase).astype(np.int8)

        # tail value at horizon
        income = phase == 1
        tail = np.where(income, np.maximum(iv, inc * float(tail_af)),
                         np.where(phase == 0, iv, 0.0))
        pv += w * disc_cum * tail
        return float(np.mean(pv)), elect_rate, surr_rate, wd_rate

    value_opt, elect_rate, surr_rate, wd_rate = run_forward(optimal=True)
    value_static, elect_static, surr_static, wd_static = run_forward(optimal=False)
    if value_opt < value_static:
        # Static is admissible.  If regression error makes the candidate policy
        # worse, report the fallback policy and its matching diagnostics (the
        # old code kept exercise rates from the rejected policy).
        value_opt = value_static
        elect_rate, surr_rate, wd_rate = elect_static, surr_static, wd_static

    return LSMCResult(value_optimal=value_opt, value_static=value_static,
                      optionality_uplift=value_opt - value_static,
                      exercise_rate_by_year=elect_rate,
                      surrender_rate_by_year=surr_rate,
                      withdrawal_rate_by_year=wd_rate,
                      settings=settings)
