"""Path-wise projection of the generic index-linked lifetime-income policy.

The projection engine evolves the full contract state on a monthly grid over
each ESG path and produces probability-weighted cashflows for the insurer and
the policyholder. It is shared by the market-consistent pricing module
(risk-neutral scenarios) and the profitability module (real-world scenarios).

State machine (per path)
------------------------
GROWTH  --income election (>= 1st anniversary)-->  INCOME  --> absorbing
Death and Income-phase full surrender are handled by probability weighting
(deterministic expected decrements and path-dependent dynamic lapse).  Growth
surrender and every Growth withdrawal are structurally prohibited.

Monthly event order (documented convention)
-------------------------------------------
1. Global-Equity and rolling five-year AUD-government-bond evolution, followed
   by monthly 50/50 rebalancing of the complete Reference Fund,
2. Anniversary only: Total-Protection credit with the fixed 6% cap applied
   once to the complete annual Reference-Fund return,
3. ACT/365F Product-Fee/LIP accrual; posting at an Anniversary and immediately
   before a terminating death or Full Withdrawal,
4. expected death decrement for the interval just ended under its
   pre-Election coverage state and post-fee death benefit (no MVA),
5. current-Anniversary dynamic Income take-up by surviving contracts,
6. lifetime income payment to lives surviving to the payment date (monthly,
   in arrears; the first payment falls one month after income election, PDS
   section 13); shortfall beyond Account Value is a Guarantee Claim,
7. dynamically modelled Income-phase Excess/Partial Withdrawals, and
8. Income-phase lapse / Full Withdrawal after event-driven fee posting and MVA.

Daily Value Adjustment modelling proxy (PDS section 7)
-------------------------------------------------------
Intra-year Account Value is valued as a zero bond maturing at the next
Anniversary plus one Total-Protection package on the *complete* Reference
Fund, ``pz_t = P(t,T_anniv) + V_pkg(t)``.
At each anniversary the insurer extracts the cap-setting margin
iv_frame * (1 - pz_s) upfront; afterwards the policyholder pool
iv_frame * pz_t is an exact discounted martingale that converges to the
contractual 1 + credit at the next Anniversary.  The package uses a
joint-model moment-matched volatility derived solely from the existing
Global-Equity and Hull-White parameters.  It is a transparent DVA proxy, not a
claim of exact conditional mixed-fund option valuation.
The CSV hedge-volatility proxy is repriced separately and booked as a
non-negative insurer ``hedge_costs`` outflow at each crediting-period start;
it does not change this customer-facing DVA state.
It still requires reconciliation to an administrative formula and executable
transaction quotes.  Neither COS nor LSMC is used by the portfolio workflow.
"""

from __future__ import annotations

from calendar import isleap
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Dict, Optional

import numpy as np
from numpy.typing import NDArray

from .behavior import BehaviourModel
from .crediting import (credited_return, crediting_package_value,
                        heston_package_value,
                        intra_year_value_factor)
from .esg import ScenarioSet, STEPS_PER_YEAR
from .mortality import MortalityTable
from .product import (IndexLinkedLifetimeIncomeProduct, ExpenseAssumptions, FundingSource,
                      PolicySpec, Phase,
                      Protection, SpouseDeathElection, INCOME_PHASE_OPTION)

Array = NDArray[np.float64]


def _fractional_year_to_date(value: float) -> date:
    """Deterministic date convention for legacy fractional-year inputs.

    Model points currently provide ``commencement_year`` rather than an ISO
    date.  The fraction is mapped to the nearest day of that calendar year;
    this makes ACT/365F accrual reproducible until an explicit commencement
    date is added to the input schema.
    """
    if not np.isfinite(value):
        raise ValueError("commencement_year must be finite.")
    year = int(np.floor(value))
    days = 366 if isleap(year) else 365
    offset = int(round((float(value) - year) * days))
    offset = min(max(offset, 0), days - 1)
    return date(year, 1, 1) + timedelta(days=offset)


def _add_calendar_months(anchor: date, months: int) -> date:
    """Add whole calendar months, clipping the day at month end."""
    if isinstance(months, bool) or not isinstance(months, (int, np.integer)):
        raise ValueError("months must be an integer.")
    serial = anchor.year * 12 + (anchor.month - 1) + int(months)
    year, month0 = divmod(serial, 12)
    month = month0 + 1
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    month_end_day = (next_month - timedelta(days=1)).day
    return date(year, month, min(anchor.day, month_end_day))


def _completed_date_anniversaries(as_of: date, base: date) -> int:
    """Number of complete annual base-date anniversaries at ``as_of``."""
    if as_of < base:
        return 0
    years = as_of.year - base.year
    if (as_of.month, as_of.day) < (base.month, base.day):
        years -= 1
    return max(years, 0)


def _average_expense_inflation_factor(
        interval_start: date, interval_end: date,
        annual_rate: float, base_date: date) -> float:
    """Daily-weighted factor when an annual expense date crosses a month."""
    days = (interval_end - interval_start).days
    if days <= 0:
        raise ValueError("Expense interval must contain at least one day.")
    total = 0.0
    for day_offset in range(days):
        current = interval_start + timedelta(days=day_offset)
        years = _completed_date_anniversaries(current, base_date)
        total += (1.0 + annual_rate) ** years
    return total / days


# ---------------------------------------------------------------------------
# Configuration and result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProjectionConfig:
    dva_enabled: bool = True
    #: Absolute volatility quote add-on used to derive a non-negative hedge
    #: execution/basis cost at the start of each crediting period.  It is not
    #: added to customer DVA values and is not interpreted as a cash expense
    #: rate; see the ``hedge_costs`` cashflow.
    hedge_vol_spread: float = 0.0
    #: record full state paths (IV, income and phase) for diagnostics.
    record_paths: bool = True
    #: maximum projection age of the life insured. The default reaches the
    #: mortality-table terminal age so lifetime-income tails are not truncated.
    max_age: float = 115.0
    #: include the crediting margin cashflow (cap-setting margin).
    crediting_margin_enabled: bool = True
    #: independent, reproducible RNG seed for stochastic income take-up.
    take_up_seed: int = 97
    #: Legacy four-equity-option switch.  The generic mixed reference fund is
    #: always valued with a joint-model moment-matched BS proxy and never with
    #: COS.  Portfolio valuation also sets this flag explicitly to ``False``.
    heston_cos: bool = False

    def __post_init__(self) -> None:
        if not np.isfinite(self.hedge_vol_spread) or not np.isfinite(self.max_age):
            raise ValueError("Projection numeric settings must be finite.")
        if self.hedge_vol_spread < 0.0:
            raise ValueError("hedge_vol_spread must be non-negative.")
        if self.max_age <= 0.0:
            raise ValueError("Projection max_age must be positive.")
        for name in ("dva_enabled", "record_paths", "crediting_margin_enabled",
                     "heston_cos"):
            if not isinstance(getattr(self, name), (bool, np.bool_)):
                raise ValueError(f"{name} must be boolean.")
        if isinstance(self.take_up_seed, bool) \
                or not isinstance(self.take_up_seed, (int, np.integer)) \
                or self.take_up_seed < 0:
            raise ValueError("take_up_seed must be a non-negative integer.")


CASHFLOW_KEYS = (
    "premium", "income_paid", "guarantee_claims", "death_benefits",
    "surrender_benefits", "partial_withdrawals", "terminal_closeout",
    "fees_product", "fees_lip", "crediting_margin", "mva_retained",
    "aps_retained", "hedge_costs", "expenses",
)


@dataclass
class ProjectionResult:
    """Probability-weighted cashflows (n_paths, n_steps+1) and diagnostics.

    All cashflow entries at column ``k`` occur at time ``times[k]`` and are
    already weighted with the in-force probability of the path.
    Policyholder-facing flows are positive. Insurer income (fees, margins,
    MVA retained) and insurer outgo (hedge/operating costs) are each recorded
    as positive magnitudes in their own buckets; net-value formulas apply the
    appropriate sign.
    """

    times: Array
    scenarios: ScenarioSet
    cashflows: Dict[str, Array]
    inforce: Array                 # in-force weight after decrements at t
    iv_paths: Optional[Array]      # legacy alias storage for Account Value
    income_paths: Optional[Array]  # annual income in payment
    phase_paths: Optional[Array]
    survival_primary: Array        # deterministic survival of the life insured
    horizon_years: float

    @property
    def account_value_paths(self) -> Optional[Array]:
        """Pathwise Account Value (canonical public product terminology)."""
        return self.iv_paths

    # ------------------------------------------------------------------ #

    def pv_by_component(self) -> Dict[str, float]:
        n = len(self.times)
        d = self.scenarios.discount[:, :n]
        return {k: float(np.mean(np.sum(cf * d, axis=1)))
                for k, cf in self.cashflows.items()}

    def pv_insurer_net(self) -> float:
        """PV of insurer net cashflow after claims and insurer costs."""
        pv = self.pv_by_component()
        return (pv["fees_product"] + pv["fees_lip"] + pv["crediting_margin"]
                + pv["mva_retained"] + pv["aps_retained"]
                - pv["guarantee_claims"] - pv["hedge_costs"] - pv["expenses"])

    def identity_gap(self) -> float:
        """Market-consistency check: under Q the premium must equal the PV of
        all contract-financed flows,

            P0 = PV(PH benefits) - PV(guarantee claims)
                 + PV(fees) + PV(crediting margin) + PV(MVA / APS retained).

        Returns the relative gap (should be ~0 for risk-neutral scenarios up
        to Monte-Carlo and discretisation error).
        """
        pv = self.pv_by_component()
        ph = (pv["income_paid"] + pv["death_benefits"] + pv["surrender_benefits"]
              + pv["partial_withdrawals"] + pv["terminal_closeout"])
        financed = (ph - pv["guarantee_claims"] + pv["fees_product"] + pv["fees_lip"]
                    + pv["crediting_margin"] + pv["mva_retained"] + pv["aps_retained"])
        p0 = pv["premium"]
        return float((financed - p0) / p0)

    def expected_cashflow_profile(self) -> Dict[str, Array]:
        """E[D_t * CF_t] per period (time-0 present values per time bucket)."""
        d = self.scenarios.discount[:, :len(self.times)]
        return {k: np.mean(cf * d, axis=0) for k, cf in self.cashflows.items()}

    def annual_aggregate(self, key: str, discounted: bool = False) -> Array:
        """Mean cashflow aggregated to policy years.

        Bucket 0 contains the time-0 flows only (premium, acquisition costs,
        upfront crediting margin); bucket ``y >= 1`` contains the flows of
        policy year ``y``, i.e. grid steps ``12(y-1)+1 .. 12y`` (paid at times
        in ``(y-1, y]``). This aligns the buckets with the annual BEL / SCR
        patterns, which are measured at integer policy times: the reserve
        established at ``t = y-1`` unwinds against exactly the year-``y``
        cashflows (used by the profitability recursion).
        """
        cf = self.cashflows[key]
        if discounted:
            cf = cf * self.scenarios.discount[:, :cf.shape[1]]
        mean_cf = np.mean(cf, axis=0)
        n_steps = len(self.times) - 1
        n_years = int(np.ceil(n_steps / STEPS_PER_YEAR)) + 1
        out = np.zeros(n_years)
        out[0] = float(mean_cf[0])
        for y in range(1, n_years):
            lo = (y - 1) * STEPS_PER_YEAR + 1
            hi = min(y * STEPS_PER_YEAR, n_steps)
            out[y] = float(np.sum(mean_cf[lo:hi + 1]))
        return out


# ---------------------------------------------------------------------------
# Precomputed decrement tables
# ---------------------------------------------------------------------------

@dataclass
class _Decrements:
    q_primary_m: Array          # monthly death prob of the life insured per step
    surv_primary: Array         # survival of primary to each grid point
    q_spouse_m: Optional[Array] # monthly death prob of the spouse per step
    lapse_growth_a: Array       # annual base lapse per step (growth)
    lapse_income_a: float


def _build_decrements(policy: PolicySpec, mortality: MortalityTable,
                      behaviour: BehaviourModel, n_steps: int) -> _Decrements:
    issue_offset = policy.commencement_year - mortality.base_year
    q1 = mortality.monthly_q_curve(
        policy.age,
        policy.sex,
        n_steps,
        years_from_base=issue_offset,
        projection_duration_start=0.0,
    )
    surv1 = np.ones(n_steps + 1)
    surv1[1:] = np.cumprod(1.0 - q1)

    q_spouse = None
    if policy.spouse and policy.spouse_age is not None:
        sex2 = policy.spouse_sex or policy.sex
        q_spouse = mortality.monthly_q_curve(
            policy.spouse_age,
            sex2,
            n_steps,
            years_from_base=issue_offset,
            projection_duration_start=0.0,
        )

    lapse_g = np.zeros(n_steps)
    for k in range(n_steps):
        year = k // STEPS_PER_YEAR + 1
        lapse_g[k] = behaviour.lapse.growth_rate(year)

    return _Decrements(q_primary_m=q1, surv_primary=surv1, q_spouse_m=q_spouse,
                       lapse_growth_a=lapse_g,
                       lapse_income_a=behaviour.lapse.income_phase)


# ---------------------------------------------------------------------------
# Main projection
# ---------------------------------------------------------------------------

def project(product: IndexLinkedLifetimeIncomeProduct, policy: PolicySpec,
            scenarios: ScenarioSet,
            behaviour: BehaviourModel, mortality: MortalityTable,
            expenses: Optional[ExpenseAssumptions] = None,
            config: ProjectionConfig = ProjectionConfig()) -> ProjectionResult:
    """Run the monthly projection over all scenario paths."""

    policy.validate_against(product)
    if policy.spouse and behaviour.take_up.mode != "deterministic":
        raise ValueError(
            "Spouse Income requires deterministic Income Election until "
            "pre-Election spouse eligibility is represented for path-dependent "
            "take-up."
        )
    if (
        policy.spouse
        and policy.spouse_death_election == SpouseDeathElection.CONTINUE_INCOME
        and (behaviour.use_dynamic or behaviour.use_dynamic_withdrawals)
    ):
        raise ValueError(
            "Continue-Income Joint Life requires state-independent static "
            "lapse and withdrawal assumptions until separate p11/p10/p01 "
            "Account-Value and fee cohorts are implemented."
        )
    n_paths = scenarios.n_paths
    n_steps = scenarios.n_steps
    times = scenarios.times
    curve = scenarios.config.curve
    # Contractual DVA and mid-market replication values must not absorb an
    # insurer execution-cost assumption.  The spread-bearing configuration is
    # used only to derive the separate, adverse hedge-cost cashflow below.
    market_config = replace(config, hedge_vol_spread=0.0)

    remaining_years = config.max_age - policy.age
    if (policy.spouse and policy.spouse_age is not None
            and policy.spouse_death_election == SpouseDeathElection.CONTINUE_INCOME):
        remaining_years = max(remaining_years, config.max_age - policy.spouse_age)
    if not np.isfinite(remaining_years) or remaining_years <= 0.0:
        raise ValueError("Projection max_age must exceed the terminal age of at least one covered life.")
    horizon_steps = min(
        n_steps,
        int(np.ceil(remaining_years * STEPS_PER_YEAR - 1.0e-12)),
    )
    if horizon_steps < n_steps:
        n_steps = horizon_steps

    reference_spec = product.reference_fund
    reference_fund_level = scenarios.monthly_rebalanced_reference_fund_index(
        equity_index=reference_spec.equity_index,
        equity_weight=reference_spec.equity_weight,
        bond_tenor=reference_spec.bond_tenor_years,
    )
    commencement_date = _fractional_year_to_date(policy.commencement_year)
    grid_dates = tuple(_add_calendar_months(commencement_date, k)
                       for k in range(n_steps + 1))
    fee_day_fractions = np.asarray([
        (grid_dates[k + 1] - grid_dates[k]).days / 365.0
        for k in range(n_steps)
    ], dtype=float)

    dec = _build_decrements(policy, mortality, behaviour, n_steps)
    mortality_issue_offset = policy.commencement_year - mortality.base_year

    def policy_time_to_step(years: float) -> int:
        step_f = float(years) * STEPS_PER_YEAR
        step_i = int(round(step_f))
        if abs(step_f - step_i) > 1e-9:
            raise ValueError("Policy time must fall on the monthly projection grid.")
        return step_i

    take_up = behaviour.take_up
    dynamic_take_up = take_up.mode == "dynamic"
    take_up_draws = None
    if take_up.mode == "deterministic":
        effective_income_start_year = policy.effective_income_start_year(product)
        income_step = np.full(
            n_paths,
            policy_time_to_step(effective_income_start_year),
        )
    elif take_up.mode == "hazard":
        rng = np.random.default_rng(config.take_up_seed)
        income_step = np.full(n_paths, int(take_up.force_by_year) * STEPS_PER_YEAR)
        u = rng.random((n_paths, take_up.force_by_year + 1))
        for y in range(1, take_up.force_by_year):
            p = take_up.probability(y)
            newly = (income_step == take_up.force_by_year * STEPS_PER_YEAR) & (u[:, y] < p)
            income_step[newly] = y * STEPS_PER_YEAR
    else:
        # Dynamic take-up is deliberately not pre-simulated at issue.  One
        # common-random-number draw per path and policy year is stored, while
        # the annual probability itself is evaluated from the market state at
        # the relevant Anniversary Date below.
        rng = np.random.default_rng(config.take_up_seed)
        draw_years = max(int(np.ceil(n_steps / STEPS_PER_YEAR)) + 1,
                         int(take_up.force_by_year) + 1)
        take_up_draws = rng.random((n_paths, draw_years))
        income_step = np.full(n_paths, np.iinfo(np.int32).max, dtype=np.int64)

    min_income_step = product.min_years_before_income * STEPS_PER_YEAR
    income_step = np.maximum(income_step, min_income_step)

    # Case-study convention: force commencement on the first Anniversary
    # after the configured automatic-start age.
    years_to_100 = max(product.automatic_income_start_age - policy.age, 0.0)
    age_100_force_step = (
        max(
            int(np.floor(years_to_100 + 1e-12)) + 1,
            int(product.min_years_before_income),
            1,
        )
        * STEPS_PER_YEAR
    )
    income_step = np.minimum(income_step, age_100_force_step)

    no_scheduled_step = np.iinfo(np.int32).max
    if policy.age_pension_plus:
        if policy.funding_source == FundingSource.NON_SUPERANNUATION:
            # Non-super APS commences at the earlier of income commencement
            # and reaching Pension Age (PDS pp. 15-16).  ``ceil`` puts a
            # fractional birthday on the first monthly grid point not before it.
            pension_t = max(product.aps.pension_age - policy.age, 0.0)
            pension_step = int(np.ceil(pension_t * STEPS_PER_YEAR - 1e-12))
            aps_start_step = np.minimum(income_step, pension_step)
        else:
            # PolicySpec validation requires this field for APS super money.
            release_step = policy_time_to_step(float(policy.condition_of_release_year))
            aps_start_step = np.full(n_paths, release_step, dtype=np.int64)
    else:
        aps_start_step = np.full(n_paths, no_scheduled_step, dtype=np.int64)

    # ---------------- state ------------------------------------------- #
    P0 = policy.net_initial_investment
    iv = np.full(n_paths, P0)                    # current (DVA-consistent) IV
    iv_frame = iv.copy()                          # contractual IV units
    phase = np.zeros(n_paths, dtype=np.int8)      # 0 growth, 1 income, 2 out
    income_annual = np.zeros(n_paths)
    fee_product_accrued = np.zeros(n_paths)
    fee_lip_accrued = np.zeros(n_paths)
    just_elected = np.zeros(n_paths, dtype=bool)  # suppresses the payment in
    # the election month: payments are monthly in arrears, the first one falls
    # one month after the Lifetime Income Commencement Date (PDS section 13).
    w = np.ones(n_paths)                          # in-force probability weight
    complete_growth_years = np.zeros(n_paths, dtype=np.int32)
    free_wd_used = np.zeros(n_paths)
    # The PDS imposes a second, cumulative limit in each Growth-Phase
    # Anniversary year: partial withdrawals inclusive of MVA may not exceed
    # 95% of the IV (or lower APS value) at the start of that year.
    partial_wd_used = np.zeros(n_paths)
    wd_limit_base = np.full(n_paths, P0)

    # Age Pension+ state
    aps_active = np.zeros(n_paths, dtype=bool)
    cas_base = np.zeros(n_paths)
    cas_start_t = np.zeros(n_paths)
    cas_le = np.ones(n_paths)
    cas_wd = np.zeros(n_paths)
    aps_auto_income_step = np.full(n_paths, np.iinfo(np.int32).max, dtype=np.int64)
    # For Spouse-Insured income, last-survivor mortality must be conditioned
    # from the actual income election date, not from policy issue.
    joint_surv_primary = np.ones(n_paths)
    joint_surv_spouse = np.ones(n_paths)

    cfs: Dict[str, Array] = {k: np.zeros((n_paths, n_steps + 1)) for k in CASHFLOW_KEYS}
    cfs["premium"][:, 0] = P0
    # A promotional commencement bonus becomes part of IV/fee/withdrawal bases
    # but is funded by the insurer and therefore an acquisition outflow.
    cfs["expenses"][:, 0] = policy.bonus_interest_amount

    inforce = np.ones((n_paths, n_steps + 1))
    iv_paths = np.zeros((n_paths, n_steps + 1)) if config.record_paths else None
    income_paths = np.zeros((n_paths, n_steps + 1)) if config.record_paths else None
    phase_paths = np.zeros((n_paths, n_steps + 1), dtype=np.int8) if config.record_paths else None
    if iv_paths is not None:
        iv_paths[:, 0] = iv

    exp_assum = expenses
    expense_inflation_factors = None
    if exp_assum is not None:
        expense_base_date = date.fromisoformat(exp_assum.fixed_expense_base_date)
        expense_inflation_factors = np.asarray([
            _average_expense_inflation_factor(
                grid_dates[k], grid_dates[k + 1],
                exp_assum.expense_inflation, expense_base_date)
            for k in range(n_steps)
        ], dtype=float)
        cfs["expenses"][:, 0] += exp_assum.acquisition_pct_of_premium * policy.initial_investment \
            + exp_assum.commission_pct_of_premium * policy.initial_investment

    # anniversary-start snapshots for crediting
    anniv_reference_level = reference_fund_level[:, 0].copy()
    anniv_step = 0

    z_issue_cache: Dict[int, float] = {}

    def issue_zero(tau: float) -> float:
        """Annually compounded zero rate from the issue curve for tenor tau."""
        key = int(round(tau * 12))
        if key not in z_issue_cache:
            z_issue_cache[key] = float(np.expm1(curve.zero(max(tau, 1e-6))))
        return z_issue_cache[key]

    def activate_aps(mask: Array, step: int, t: float) -> None:
        """Lock the Capital Access Schedule state on its contractual date."""
        nonlocal aps_active, cas_base, cas_start_t, cas_le
        nonlocal aps_auto_income_step, wd_limit_base

        if not policy.age_pension_plus:
            return
        activate = np.asarray(mask, dtype=bool) & ~aps_active & (phase < 2)
        if not activate.any():
            return
        le = (float(policy.aps_life_expectancy)
              if policy.aps_life_expectancy is not None
              else mortality.life_expectancy(
                  policy.age + t, policy.sex,
                  years_from_base=mortality_issue_offset + t,
                  projection_duration_start=t))
        aps_active |= activate
        cas_base = np.where(activate, iv, cas_base)
        cas_start_t = np.where(activate, t, cas_start_t)
        cas_le = np.where(activate, le, cas_le)

        # If APS is active in Growth, income must start at the first original
        # policy anniversary strictly after Life Expectancy is reached.
        le_force_year = int(np.floor(t + le + 1e-12)) + 1
        aps_auto_income_step = np.where(
            activate, le_force_year * STEPS_PER_YEAR, aps_auto_income_step)

        # From APS commencement there is no free withdrawal amount.  Reset the
        # cumulative base to the newly established lower contractual value.
        growth_activation = activate & (phase == Phase.GROWTH.value)
        wd_limit_base = np.where(growth_activation, np.minimum(iv, cas_base),
                                 wd_limit_base)

    def package_and_zcb(step: int, tau: float, phase_arr: Array) -> Array:
        """DVA proxy for an option on the *complete* reference fund.

        A single Total-Protection package is valued on the monthly rebalanced
        fund.  Its volatility is moment-matched from the joint equity/Hull-
        White model; no per-sleeve option values and no COS method are used.
        The same package applies in Growth and Income.
        """
        del phase_arr  # reference-fund exposure is phase invariant
        tau_e = max(float(tau), 1e-6)
        r_cc = scenarios.forward_zero_cc(step, tau_e)
        x0 = reference_fund_level[:, step] / np.maximum(
            anniv_reference_level, 1e-300)
        sigma = scenarios.reference_fund_effective_vol(
            step,
            horizon=tau_e,
            equity_index=reference_spec.equity_index,
            equity_weight=reference_spec.equity_weight,
            bond_tenor=reference_spec.bond_tenor_years,
        ) + market_config.hedge_vol_spread
        return np.asarray(intra_year_value_factor(
            x0,
            Protection.TOTAL,
            reference_spec.cap(anniv_step // STEPS_PER_YEAR),
            tau_e,
            r_cc,
            0.0,
            sigma,
        ))

    gross_premium = float(policy.initial_investment)

    def annuity_factor_at(step: int, t: float) -> Array:
        """Pathwise annuity factor under the market state at ``step``."""
        age_now = policy.age + t
        z10 = scenarios.forward_zero_cc(step, 10.0)
        if (policy.spouse
                and policy.spouse_death_election == SpouseDeathElection.CONTINUE_INCOME
                and policy.spouse_age is not None):
            spouse_age_now = policy.spouse_age + t
            spouse_sex = policy.spouse_sex or policy.sex
            common = dict(
                years_from_base=mortality_issue_offset + t,
                projection_duration_start=t,
            )
            both_alive = np.asarray(mortality.annuity_factor(
                age_now, policy.sex, z10,
                joint_age=spouse_age_now, joint_sex=spouse_sex,
                **common), dtype=float)
            primary_only = np.asarray(mortality.annuity_factor(
                age_now, policy.sex, z10, **common), dtype=float)
            spouse_only = np.asarray(mortality.annuity_factor(
                spouse_age_now, spouse_sex, z10, **common), dtype=float)
            p11 = joint_surv_primary * joint_surv_spouse
            p10 = joint_surv_primary * (1.0 - joint_surv_spouse)
            p01 = (1.0 - joint_surv_primary) * joint_surv_spouse
            last_survivor = p11 + p10 + p01
            survivor_mix = np.divide(
                p11 * both_alive + p10 * primary_only + p01 * spouse_only,
                np.maximum(last_survivor, 1e-300),
                out=both_alive.copy(),
                where=last_survivor > 0.0,
            )
            return np.where(
                phase == Phase.INCOME.value, survivor_mix, both_alive)
        return np.asarray(mortality.annuity_factor(
            age_now, policy.sex, z10,
            years_from_base=mortality_issue_offset + t,
            projection_duration_start=t), dtype=float)

    def prospective_income_rate(t: float) -> float:
        return product.income_rates.lifetime_income_rate(
            policy.age, policy.sex, policy.income_type, policy.spouse,
            int(np.floor(t + 1e-12)), policy.spouse_age, policy.spouse_sex,
            policy.age_pension_plus)

    def guarantee_log_moneyness(step: int, t: float,
                                denominator: Array) -> Array:
        """Log PV(guaranteed income) divided by the relevant exit value."""
        af = annuity_factor_at(step, t)
        growth_pv = iv * prospective_income_rate(t) * af
        guarantee_pv = np.where(phase == Phase.INCOME.value,
                                income_annual * af, growth_pv)
        ratio = np.divide(
            guarantee_pv, np.maximum(np.asarray(denominator, dtype=float), 1e-300),
            out=np.full(n_paths, np.exp(2.0)),
            where=np.asarray(denominator, dtype=float) > 1e-12,
        )
        return np.log(np.maximum(ratio, 1e-300))

    def current_mva_signal(step: int, t: float) -> Array:
        """Non-negative current MVA bite used as a withdrawal covariate."""
        tau_rem = product.withdrawals.mva_period_years - t
        if tau_rem <= 0.0:
            return np.zeros(n_paths)
        f = product.mva.factor(issue_zero(tau_rem),
                               scenarios.zero_rate(step, tau_rem), tau_rem)
        return np.clip(np.asarray(f, dtype=float), 0.0, 1.0)

    def wd_dynamic_rates(step: int, t: float) -> tuple[Array, Array]:
        """Expected free and excess withdrawal rates for the current year.

        The fractional-logit responses use current guarantee moneyness, the
        gross paid premium and the current MVA bite.  They are evaluated at
        anniversaries (and an income election) and then held within the year.
        """
        wb = behaviour.withdrawals
        if not behaviour.use_dynamic_withdrawals:
            return (np.full(n_paths, wb.free_utilisation),
                    np.full(n_paths, wb.excess_rate))
        log_mny = guarantee_log_moneyness(step, t, iv)
        mva_signal = current_mva_signal(step, t)
        dwp = behaviour.dynamic_withdrawals
        free = dwp.free_utilisation(
            wb.free_utilisation, log_mny, gross_premium, mva_signal)
        excess = dwp.excess_rate(
            wb.excess_rate, log_mny, gross_premium, mva_signal)
        return np.asarray(free, dtype=float), np.asarray(excess, dtype=float)

    free_utilisation, excess_rate = wd_dynamic_rates(0, 0.0)
    # Income-phase lapse probabilities are evaluated at anniversaries (and at
    # election) and held constant within the policy year.  The base assumption
    # remains annual until after dynamic scaling.
    income_lapse_prob = np.full(
        n_paths, 1.0 - (1.0 - dec.lapse_income_a) ** (1.0 / STEPS_PER_YEAR))

    def reference_package_only(step: int, volatility_spread: float = 0.0) -> Array:
        """One-year Total-Protection package value on the whole fund."""
        r_cc = scenarios.forward_zero_cc(step, 1.0)
        sigma = scenarios.reference_fund_effective_vol(
            step,
            horizon=1.0,
            equity_index=reference_spec.equity_index,
            equity_weight=reference_spec.equity_weight,
            bond_tenor=reference_spec.bond_tenor_years,
        ) + float(volatility_spread)
        return np.asarray(crediting_package_value(
            1.0,
            Protection.TOTAL,
            reference_spec.cap(step // STEPS_PER_YEAR),
            1.0,
            r_cc,
            0.0,
            sigma,
        ))

    def book_hedge_execution_cost(step: int) -> None:
        """Book an adverse, non-negative option-execution cost.

        ``hedge_vol_spread`` is a quote proxy rather than a cash rate.  The
        amount is therefore derived by repricing the annual option package and
        taking the absolute mid-to-spread price difference.  The absolute
        difference is essential for capped call spreads and buffered packages,
        whose *net* vega can be negative; a positive execution-cost assumption
        must never create insurer income.
        """
        if config.hedge_vol_spread == 0.0 or step >= n_steps:
            return
        mid = reference_package_only(step, 0.0)
        spread_quote = reference_package_only(step, config.hedge_vol_spread)
        cost_rate = np.abs(spread_quote - mid)
        cost = iv_frame * cost_rate
        cfs["hedge_costs"][:, step] += w * np.where(
            phase < Phase.TERMINATED.value, cost, 0.0
        )

    def restart_dva_period(step: int) -> None:
        """Start a fresh annual crediting / DVA replication period."""
        nonlocal iv
        if step < n_steps:
            book_hedge_execution_cost(step)
        if config.dva_enabled and step < n_steps:
            # No restart at the final grid point: the horizon closeout pays
            # the current DVA-consistent IV, so no new crediting year is hedged.
            pz_start = package_and_zcb(step, 1.0, phase)
            if config.crediting_margin_enabled:
                margin_up = iv_frame * (1.0 - pz_start)
                cfs["crediting_margin"][:, step] += w * np.where(
                    phase < Phase.TERMINATED.value, margin_up, 0.0)
            iv = iv_frame * pz_start

    def fee_settlement(account_value: Array) -> tuple[Array, Array, Array]:
        """Collectible Product Fee, LIP and post-fee Account Value at an event."""
        available = np.maximum(np.asarray(account_value, dtype=float), 0.0)
        outstanding = fee_product_accrued + fee_lip_accrued
        collected = np.minimum(available, outstanding)
        scale = np.divide(
            collected,
            outstanding,
            out=np.zeros(n_paths),
            where=outstanding > 0.0,
        )
        product_collected = fee_product_accrued * scale
        lip_collected = fee_lip_accrued * scale
        return product_collected, lip_collected, available - collected

    def post_fee_subledger(step: int) -> None:
        """Post all accrued fees for every currently in-force contract."""
        nonlocal iv, iv_frame, fee_product_accrued, fee_lip_accrued
        product_collected, lip_collected, post_fee_av = fee_settlement(iv)
        before = iv.copy()
        iv = post_fee_av
        ratio = np.divide(
            iv,
            np.maximum(before, 1e-300),
            out=np.ones(n_paths),
            where=before > 0.0,
        )
        iv_frame = iv_frame * ratio
        cfs["fees_product"][:, step] += w * product_collected
        cfs["fees_lip"][:, step] += w * lip_collected
        # No arrears are carried after a contractual deduction event.
        fee_product_accrued = np.zeros(n_paths)
        fee_lip_accrued = np.zeros(n_paths)

    def income_lapse_probability_at(step: int, t: float,
                                    surrender_value: Array) -> Array:
        """Monthly income-phase lapse probability at a reset point."""
        log_mny = guarantee_log_moneyness(step, t, surrender_value)
        if behaviour.use_dynamic:
            out = behaviour.dynamic.income_probability(
                dec.lapse_income_a, log_mny, gross_premium,
                1.0 / STEPS_PER_YEAR)
            return np.asarray(out, dtype=float)
        return np.full(
            n_paths,
            1.0 - (1.0 - dec.lapse_income_a) ** (1.0 / STEPS_PER_YEAR),
        )

    def income_election_mask(step: int, t: float, growth: Array,
                             is_anniversary: bool) -> Array:
        """Paths electing income on this grid point.

        Dynamic take-up is an Anniversary decision based on the market state
        then prevailing.  Deterministic and legacy hazard modes retain their
        pre-scheduled dates for isolated contract-mechanics use.
        """
        eligible_growth = np.asarray(growth, dtype=bool) & (iv > 0.0)
        required_step = np.minimum(income_step, aps_auto_income_step)
        if not dynamic_take_up:
            return eligible_growth & (step >= required_step)
        if not is_anniversary or step < min_income_step:
            return np.zeros(n_paths, dtype=bool)

        policy_year = step // STEPS_PER_YEAR
        forced = ((step >= age_100_force_step)
                  | (policy_year >= take_up.force_by_year)
                  | (step >= aps_auto_income_step))
        base_probability = take_up.probability(policy_year)
        if behaviour.use_dynamic_take_up:
            log_mny = guarantee_log_moneyness(step, t, iv)
            probability = np.asarray(behaviour.dynamic_take_up.probability(
                base_probability, log_mny, gross_premium), dtype=float)
        else:
            probability = np.full(n_paths, base_probability)
        draw = take_up_draws[:, policy_year]
        return eligible_growth & (forced | (draw < probability))

    def elect_income(elect: Array, step: int, t: float) -> None:
        """Elect Lifetime Income using the current IV as commencement value."""
        nonlocal phase, income_annual, iv_frame
        nonlocal free_utilisation, excess_rate
        nonlocal joint_surv_primary, joint_surv_spouse, income_lapse_prob

        if not elect.any():
            return

        complete_years = int(np.floor(t + 1e-12))
        rate = product.income_rates.lifetime_income_rate(
            policy.age, policy.sex, policy.income_type, policy.spouse,
            complete_years, policy.spouse_age, policy.spouse_sex,
            policy.age_pension_plus)
        income_annual = np.where(elect, iv * rate, income_annual)
        iv_frame = np.where(elect, iv, iv_frame)
        phase = np.where(elect, Phase.INCOME.value, phase).astype(np.int8)
        just_elected[elect] = True

        if policy.spouse and dec.q_spouse_m is not None:
            joint_surv_primary = np.where(elect, 1.0, joint_surv_primary)
            joint_surv_spouse = np.where(elect, 1.0, joint_surv_spouse)
        free_utilisation, excess_rate = wd_dynamic_rates(step, t)
        election_surrender_value, _ = _surrender_value(
            product, policy, scenarios, step, t, iv, free_wd_used,
            phase, aps_active, issue_zero, P0)
        income_lapse_prob = np.where(
            phase == Phase.INCOME.value,
            income_lapse_probability_at(step, t, election_surrender_value),
            income_lapse_prob)

    # APS may already commence at issue (for example a non-super policy whose
    # Life Insured is at or above Pension Age).
    activate_aps(aps_start_step <= 0, 0, 0.0)

    # upfront crediting margin of the first policy year (see anniversary block)
    if config.dva_enabled and config.crediting_margin_enabled:
        pz0 = package_and_zcb(0, 1.0, phase)
        cfs["crediting_margin"][:, 0] += iv_frame * (1.0 - pz0)
    book_hedge_execution_cost(0)

    # ------------------------------------------------------------------ #
    # main loop
    # ------------------------------------------------------------------ #
    for k in range(n_steps):
        step = k + 1
        t = times[step]
        is_anniv = (step - anniv_step) == STEPS_PER_YEAR
        growth = phase == Phase.GROWTH.value
        income = phase == Phase.INCOME.value
        income_at_interval_start = income.copy()
        w_month_start = w.copy()
        av_month_start = np.maximum(iv.copy(), 0.0)
        fee_base_for_interval = np.where(
            phase < Phase.TERMINATED.value, np.maximum(iv_frame, 0.0), 0.0)
        just_elected[:] = False
        # Payments are in arrears; the Election month has no payment.  Fixed
        # Income remains nominally unchanged except after an Excess Withdrawal.
        income_for_current_payment = income_annual.copy()

        # ---- anniversary crediting ------------------------------------ #
        if is_anniv:
            year_idx = anniv_step // STEPS_PER_YEAR  # caps of the period just ended
            fund_ratio = reference_fund_level[:, step] / np.maximum(
                anniv_reference_level, 1e-300)
            credit = np.asarray(credited_return(
                fund_ratio - 1.0,
                Protection.TOTAL,
                reference_spec.cap(year_idx),
            ))
            new_iv = np.where(
                growth | income,
                iv_frame * (1.0 + credit),
                0.0,
            )

            # Crediting margin without DVA (approximation mode): realised at
            # year end per unit held, (1 - V_pkg) * cash_growth - 1.
            # In DVA mode the margin is extracted upfront below (exact
            # replication accounting). Zero when caps are budget-neutral.
            if config.crediting_margin_enabled and not config.dva_enabled:
                grow_cash = scenarios.discount[:, anniv_step] / np.maximum(
                    scenarios.discount[:, step], 1e-300)
                v_pkg = reference_package_only(anniv_step, 0.0)
                margin = iv_frame * ((1.0 - v_pkg) * grow_cash - 1.0)
                cfs["crediting_margin"][:, step] += w * np.where(phase < 2, margin, 0.0)

            iv_frame = np.maximum(new_iv, 0.0)
            iv = iv_frame.copy()

            complete_growth_years = np.where(growth, complete_growth_years + 1,
                                             complete_growth_years)
            free_wd_used[:] = 0.0
            anniv_reference_level = reference_fund_level[:, step].copy()
            anniv_step = step

        # ---- intra-year DVA value -------------------------------------- #
        if config.dva_enabled and not is_anniv:
            tau = (STEPS_PER_YEAR - (step - anniv_step)) / STEPS_PER_YEAR
            iv = iv_frame * package_and_zcb(step, tau, phase)
        elif not config.dva_enabled and not is_anniv:
            iv = iv_frame.copy()

        alive_mask = phase < Phase.TERMINATED.value

        # ---- daily fee subledger ---------------------------------------- #
        # The monthly market grid supplies a piecewise-constant proxy for the
        # administrative daily Account-Value base.  Exact calendar days are
        # then accrued under ACT/365F.  Accrual is not an insurer cash inflow.
        fee_product_accrued += (
            fee_base_for_interval * product.fees.product_fee
            * fee_day_fractions[k]
        )
        fee_lip_accrued += (
            fee_base_for_interval * product.fees.lifetime_income_premium
            * fee_day_fractions[k]
        )
        if is_anniv:
            # Contractual order: annual credit, then fee posting, then Income
            # Election.  Only collected amounts enter the fee cashflows.
            post_fee_subledger(step)

        # APS commencement is a transaction-date state change and therefore
        # locks the post-fee Investment Value on this monthly grid point.
        activate_aps(step >= aps_start_step, step, t)

        if is_anniv:
            partial_wd_used[:] = 0.0
            mwv_at_anniv = _aps_max_withdrawal(
                product, cas_base, t, cas_start_t, cas_le, cas_wd, aps_active)
            wd_limit_base[:] = np.where(
                phase == Phase.GROWTH.value,
                np.where(aps_active, np.minimum(iv, mwv_at_anniv), iv),
                wd_limit_base)

        # ---- death decrement before the payment date ---------------------- #
        # Income is monthly in arrears and ceases on death.  The death benefit
        # is therefore based on the pre-payment IV, while only survivors to the
        # payment date receive this month's instalment.
        q_m = np.full(n_paths, dec.q_primary_m[k])
        if (policy.spouse and dec.q_spouse_m is not None
                and policy.spouse_death_election == SpouseDeathElection.CONTINUE_INCOME):
            # Joint cover starts at the election timestamp.  The mortality
            # decrement for the interval ending at that timestamp remains a
            # Primary-Life decrement; Last-Survivor mortality starts with the
            # following monthly interval.
            income_spouse = income_at_interval_start
            if income_spouse.any():
                s1 = joint_surv_primary
                s2 = joint_surv_spouse
                s_ls = s1 + s2 - s1 * s2
                s1_next = s1 * (1.0 - dec.q_primary_m[k])
                s2_next = s2 * (1.0 - dec.q_spouse_m[k])
                s_ls_next = s1_next + s2_next - s1_next * s2_next
                q_joint = 1.0 - s_ls_next / np.maximum(s_ls, 1e-300)
                q_m = np.where(income_spouse, q_joint, q_m)
                joint_surv_primary = np.where(income_spouse, s1_next, joint_surv_primary)
                joint_surv_spouse = np.where(income_spouse, s2_next, joint_surv_spouse)
        q_m = np.where(alive_mask, q_m, 0.0)
        death_fee_product, death_fee_lip, death_post_fee_av = fee_settlement(iv)
        death_ben = death_post_fee_av
        if policy.age_pension_plus:
            cap_db = _aps_death_cap(product, cas_base, t, cas_start_t, cas_le,
                                    cas_wd, aps_active)
            death_ben = np.where(aps_active, np.minimum(death_ben, cap_db), death_ben)
            cfs["aps_retained"][:, step] += w * q_m * np.where(
                aps_active, death_post_fee_av - death_ben, 0.0)
        cfs["fees_product"][:, step] += w * q_m * death_fee_product
        cfs["fees_lip"][:, step] += w * q_m * death_fee_lip
        cfs["death_benefits"][:, step] += w * q_m * death_ben
        w = w * (1.0 - q_m)

        # ---- income election / new crediting period ---------------------- #
        # Expected deaths in the interval ending at an Anniversary belong to
        # the pre-election coverage state.  Surviving contracts elect Income
        # only after that decrement; the next crediting/DVA period is therefore
        # funded only for survivors.  This removes the former hybrid in which
        # Primary mortality was combined with post-election DVA state.
        if is_anniv:
            growth = phase == Phase.GROWTH.value
            if growth.any():
                elect = income_election_mask(step, t, growth, True)
                if (dynamic_take_up and policy.age_pension_plus
                        and policy.funding_source == FundingSource.NON_SUPERANNUATION):
                    activate_aps(elect, step, t)
                elect_income(elect, step, t)
            restart_dva_period(step)
            free_utilisation, excess_rate = wd_dynamic_rates(step, t)

        # ---- income payment (monthly, in arrears; first payment one month
        # after the income election, PDS section 13) ----------------------- #
        pay = np.where((phase == 1) & ~just_elected,
                       income_for_current_payment / STEPS_PER_YEAR, 0.0)
        from_iv = np.minimum(pay, iv)
        claim = pay - from_iv
        ratio_iv = np.divide(iv - from_iv, np.maximum(iv, 1e-300),
                             out=np.ones(n_paths), where=iv > 0)
        iv = iv - from_iv
        iv_frame = iv_frame * ratio_iv
        cfs["income_paid"][:, step] += w * pay
        cfs["guarantee_claims"][:, step] += w * claim
        exhausted_av = iv <= 1e-12
        # No-arrears convention: accrued but unposted fees are written off as
        # soon as Account Value is exhausted by regular income.
        fee_product_accrued = np.where(exhausted_av, 0.0, fee_product_accrued)
        fee_lip_accrued = np.where(exhausted_av, 0.0, fee_lip_accrued)

        # ---- scheduled partial withdrawals -------------------------------- #
        wb = behaviour.withdrawals
        wd_scheduled = wb.free_utilisation > 0.0 or wb.excess_rate > 0.0
        if wd_scheduled and (wb.frequency == "monthly" or is_anniv):
            frac = 1.0 / STEPS_PER_YEAR if wb.frequency == "monthly" else 1.0
            _apply_partial_withdrawals(product, policy, scenarios, step, t, iv,
                                       iv_frame, phase, aps_active, cas_base,
                                       cas_start_t, cas_le, cas_wd, free_wd_used,
                                       partial_wd_used, wd_limit_base,
                                       income_annual, w, cfs, wb, issue_zero, P0,
                                       fraction=frac,
                                       free_utilisation=free_utilisation,
                                       excess_rate=excess_rate)

        # ---- lapse / full withdrawal --------------------------------------- #
        lapse_fee_product, lapse_fee_lip, lapse_post_fee_av = fee_settlement(iv)
        sv, mva_amt = _surrender_value(product, policy, scenarios, step, t,
                                       lapse_post_fee_av,
                                       free_wd_used, phase, aps_active,
                                       issue_zero, P0)
        if policy.age_pension_plus:
            mwv = _aps_max_withdrawal(product, cas_base, t, cas_start_t, cas_le,
                                      cas_wd, aps_active)
            # PDS pp. 34-35: an MVA is charged only when IV less MVA is the
            # binding withdrawal value.  If the APS maximum binds, the MVA is
            # not charged separately; the whole residual IV is an APS
            # forfeiture on full withdrawal.
            aps_binds = aps_active & (sv > mwv)
            sv = np.where(aps_binds, mwv, sv)
            mva_amt = np.where(aps_binds, 0.0, mva_amt)
            aps_forfeit = np.where(
                aps_binds,
                np.maximum(lapse_post_fee_av - mwv, 0.0),
                0.0,
            )
        else:
            aps_forfeit = np.zeros(n_paths)

        static_growth_lapse = 1.0 - (
            1.0 - dec.lapse_growth_a[k]) ** (1.0 / STEPS_PER_YEAR)
        if behaviour.use_dynamic:
            exit_ratio = np.divide(
                iv, np.maximum(sv, 1e-300), out=np.ones(n_paths), where=sv > 1e-12)
            exit_ratio = np.where((iv > 1e-12) & (sv <= 1e-12),
                                  np.exp(2.0), exit_ratio)
            growth_lapse_prob = np.asarray(
                behaviour.dynamic.growth_probability(
                    dec.lapse_growth_a[k], np.log(np.maximum(exit_ratio, 1e-300)),
                    gross_premium, 1.0 / STEPS_PER_YEAR),
                dtype=float,
            )
            i_mask = phase == Phase.INCOME.value
            if i_mask.any() and is_anniv:
                income_lapse_prob = np.where(
                    i_mask,
                    income_lapse_probability_at(step, t, sv),
                    income_lapse_prob,
                )
        else:
            growth_lapse_prob = np.full(n_paths, static_growth_lapse)
            income_lapse_prob = np.full(
                n_paths,
                1.0 - (1.0 - dec.lapse_income_a) ** (1.0 / STEPS_PER_YEAR),
            )
        base_lapse = np.where(
            phase == Phase.INCOME.value, income_lapse_prob,
            np.where(phase == Phase.GROWTH.value, growth_lapse_prob, 0.0),
        )
        if not product.allows_growth_surrender:
            base_lapse = np.where(phase == Phase.INCOME.value,
                                  base_lapse, 0.0)
        lapse_eligible = alive_mask & (
            (phase == Phase.INCOME.value)
            | ((phase == Phase.GROWTH.value) & (iv > 0.0))
        )
        base_lapse = np.where(lapse_eligible, base_lapse, 0.0)
        cfs["fees_product"][:, step] += w * base_lapse * lapse_fee_product
        cfs["fees_lip"][:, step] += w * base_lapse * lapse_fee_lip
        cfs["surrender_benefits"][:, step] += w * base_lapse * sv
        cfs["mva_retained"][:, step] += w * base_lapse * mva_amt
        cfs["aps_retained"][:, step] += w * base_lapse * aps_forfeit
        w = w * (1.0 - base_lapse)

        # ---- expenses ----------------------------------------------------- #
        if exp_assum is not None:
            # Fixed expense inflation steps on the source assumption's annual
            # base date; an interval crossing that date is day-weighted.
            # Midpoint in-force exposure prorates terminating deaths and full
            # withdrawals within the monthly interval.
            infl = float(expense_inflation_factors[k])
            exposure_weight = 0.5 * (w_month_start + w)
            fixed_expense = (
                exposure_weight
                * exp_assum.maintenance_per_policy
                * infl / STEPS_PER_YEAR
            )
            weighted_av_exposure = 0.5 * (
                w_month_start * av_month_start
                + w * np.maximum(iv, 0.0)
            )
            variable_expense = (
                weighted_av_exposure
                * exp_assum.maintenance_pct_of_iv / STEPS_PER_YEAR
            )
            cfs["expenses"][:, step] += np.where(
                alive_mask, fixed_expense + variable_expense, 0.0)

        # Terminate exhausted Growth contracts and their in-force exposure.
        # Without a locked Income guarantee, zero Account Value has no
        # remaining benefit or expense state.
        exhausted_growth = (phase == Phase.GROWTH.value) & (iv <= 0.0)
        phase = np.where(exhausted_growth, Phase.TERMINATED.value,
                         phase).astype(np.int8)
        w = np.where(exhausted_growth, 0.0, w)
        fee_product_accrued = np.where(
            exhausted_growth, 0.0, fee_product_accrued)
        fee_lip_accrued = np.where(exhausted_growth, 0.0, fee_lip_accrued)

        inforce[:, step] = w
        if iv_paths is not None:
            iv_paths[:, step] = iv
            income_paths[:, step] = income_annual
            phase_paths[:, step] = phase

    # A deliberately shortened horizon is a valuation truncation, not a
    # mortality event.  Settle accrued fees and report the remaining Account
    # Value in its own closeout bucket.  With the full lifetime horizon the
    # hard terminal-age mortality convention leaves this amount at zero.
    final = n_steps
    residual_mask = (phase < 2)
    terminal_fee_product, terminal_fee_lip, terminal_post_fee_av = \
        fee_settlement(iv)
    cfs["fees_product"][:, final] += w * np.where(
        residual_mask, terminal_fee_product, 0.0)
    cfs["fees_lip"][:, final] += w * np.where(
        residual_mask, terminal_fee_lip, 0.0)
    cfs["terminal_closeout"][:, final] += w * np.where(
        residual_mask, terminal_post_fee_av, 0.0)
    iv = np.where(residual_mask, 0.0, iv)
    iv_frame = np.where(residual_mask, 0.0, iv_frame)
    fee_product_accrued = np.where(residual_mask, 0.0, fee_product_accrued)
    fee_lip_accrued = np.where(residual_mask, 0.0, fee_lip_accrued)
    phase = np.where(
        residual_mask, Phase.TERMINATED.value, phase).astype(np.int8)
    w = np.where(residual_mask, 0.0, w)
    inforce[:, final] = w
    if iv_paths is not None:
        iv_paths[:, final] = iv
        income_paths[:, final] = income_annual
        phase_paths[:, final] = phase

    return ProjectionResult(times=times[:n_steps + 1], scenarios=scenarios,
                            cashflows={k: v[:, :n_steps + 1] for k, v in cfs.items()},
                            inforce=inforce[:, :n_steps + 1],
                            iv_paths=None if iv_paths is None else iv_paths[:, :n_steps + 1],
                            income_paths=None if income_paths is None else income_paths[:, :n_steps + 1],
                            phase_paths=None if phase_paths is None else phase_paths[:, :n_steps + 1],
                            survival_primary=dec.surv_primary,
                            horizon_years=float(times[n_steps]))


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _cos_extra_var(scenarios, config, ix, step, horizon) -> Array:
    """Gaussian add-on variance for the Heston COS package pricer.

    Hull-White rate contribution (pathwise) plus the ``hedge_vol_spread``
    mapped onto the equivalent variance shift of the effective Heston vol when
    deriving the separate execution quote.  Contractual DVA calls pass a
    zero-spread configuration, so the spread has the same first-order quote
    effect as in the BS branch without changing customer value.
    """
    w = scenarios.rate_gauss_var(ix, step, horizon)
    if config.hedge_vol_spread != 0.0:
        hp = scenarios.config.heston[ix]
        v_t = scenarios.variance[ix][:, step]
        var_eq = np.asarray(hp.expected_integrated_variance(v_t, horizon),
                            dtype=float)
        sig_h = np.sqrt(np.maximum(var_eq, 1e-12))
        w = w + ((sig_h + config.hedge_vol_spread) ** 2 - sig_h ** 2) * horizon
    return w


def _package_only(product, scenarios, anniv_step, anniv_index_level, alloc_opts,
                  alloc_w, phase, config) -> Array:
    """Package value at anniversary start (no ZCB), for margin when DVA off."""
    n_paths = scenarios.n_paths
    r_cc = scenarios.forward_zero_cc(anniv_step, 1.0)
    year_idx = anniv_step // STEPS_PER_YEAR
    use_cos = scenarios.variance is not None and config.heston_cos

    def blended(opts, wts) -> Array:
        val = np.zeros(n_paths)
        for opt, wt in zip(opts, wts):
            if wt <= 0.0:
                continue
            ix = opt.index
            cap = product.caps.cap(opt, year_idx)
            if use_cos:
                hp = scenarios.config.heston[ix]
                v_t = scenarios.variance[ix][:, anniv_step]
                w = _cos_extra_var(scenarios, config, ix, anniv_step, 1.0)
                val += wt * np.asarray(heston_package_value(
                    1.0, opt.protection, cap, 1.0, r_cc,
                    scenarios.config.equity[ix].dividend_yield, v_t, hp, w))
            else:
                sig = scenarios.effective_bs_vol(ix, anniv_step, 1.0) \
                    + config.hedge_vol_spread
                val += wt * np.asarray(crediting_package_value(
                    1.0, opt.protection, cap, 1.0, r_cc,
                    scenarios.config.equity[ix].dividend_yield, sig))
        return val

    out = blended(alloc_opts, alloc_w)
    if (phase == Phase.INCOME.value).any():
        if len(alloc_opts) == 1 and alloc_opts[0] == INCOME_PHASE_OPTION:
            income_val = out              # allocation == income option: reuse
        else:
            income_val = blended([INCOME_PHASE_OPTION], np.array([1.0]))
        out = np.where(phase == Phase.INCOME.value, income_val, out)
    return out


def _surrender_value(product, policy, scenarios, step, t, iv, free_wd_used,
                     phase, aps_active, issue_zero, P0):
    """Full-withdrawal value = IV - MVA on the excess over the free amount."""
    n_paths = iv.shape[0]
    tau_rem = product.withdrawals.mva_period_years - t
    if tau_rem <= 0:
        return iv.copy(), np.zeros(n_paths)
    free_remaining = np.where((phase == 0) & ~aps_active,
                              np.maximum(product.withdrawals.free_withdrawal_pct_of_initial
                                         * P0 - free_wd_used, 0.0), 0.0)
    excess = np.maximum(iv - free_remaining, 0.0)
    z_now = scenarios.zero_rate(step, tau_rem)
    z0 = issue_zero(tau_rem)
    f = product.mva.factor(z0, z_now, tau_rem)
    raw = excess * f
    mva_amt = (np.clip(raw, 0.0, excess) if product.mva.only_reduces
               else np.minimum(raw, excess))
    return iv - mva_amt, mva_amt


def _aps_max_withdrawal(product, cas_base, t, cas_start_t, cas_le, cas_wd, aps_active):
    elapsed = np.maximum(t - cas_start_t, 0.0)
    linear = cas_base * np.clip(1.0 - elapsed / np.maximum(cas_le, 1e-9), 0.0, 1.0)
    return np.where(aps_active, np.maximum(linear - cas_wd, 0.0), np.inf)


def _aps_death_cap(product, cas_base, t, cas_start_t, cas_le, cas_wd, aps_active):
    elapsed = np.maximum(t - cas_start_t, 0.0)
    half = product.aps.death_benefit_full_fraction * np.maximum(cas_le, 1e-9)
    # The contractual value drops immediately to the MWV at Half Life
    # Expectancy and thereafter follows the original straight-line CAS run-off.
    before_withdrawals = np.where(
        elapsed < half, cas_base,
        cas_base * np.clip(1.0 - elapsed / np.maximum(cas_le, 1e-9), 0.0, 1.0))
    cap = np.maximum(before_withdrawals - cas_wd, 0.0)
    return np.where(aps_active, cap, np.inf)


def _aps_reduction_terms(iv, mwv, amount_withdrawn, mva_amount, mwv_binds):
    """Contractual APS proportional reduction terms (PDS pp. 68-69).

    ``amount_withdrawn`` is the cash received by the investor.  When the APS
    maximum is binding, MVA is zero and the percentage is cash / MWV.  When
    IV less MVA is binding, it is (cash + MVA) / IV.
    """
    iv_arr = np.asarray(iv, dtype=float)
    mwv_arr = np.asarray(mwv, dtype=float)
    cash = np.asarray(amount_withdrawn, dtype=float)
    mva = np.asarray(mva_amount, dtype=float)
    binds = np.asarray(mwv_binds, dtype=bool)
    pct_mwv = np.divide(cash, np.maximum(mwv_arr, 1e-300),
                        out=np.zeros_like(cash), where=mwv_arr > 0.0)
    pct_iv = np.divide(cash + mva, np.maximum(iv_arr, 1e-300),
                       out=np.zeros_like(cash), where=iv_arr > 0.0)
    pct = np.clip(np.where(binds, pct_mwv, pct_iv), 0.0, 1.0)
    iv_deduction = iv_arr * pct
    aps_retained = np.where(binds,
                            np.maximum(iv_deduction - cash, 0.0), 0.0)
    return pct, iv_deduction, aps_retained


def _apply_partial_withdrawals(product, policy, scenarios, step, t, iv, iv_frame,
                               phase, aps_active, cas_base, cas_start_t, cas_le,
                               cas_wd, free_wd_used, partial_wd_used,
                               wd_limit_base, income_annual, w, cfs,
                               wb, issue_zero, P0, fraction=1.0,
                               free_utilisation=None, excess_rate=None):
    """Scheduled free / excess withdrawals (in place).

    ``fraction`` scales the annualised utilisation to the event frequency
    (1 at anniversaries, 1/12 on the monthly schedule).  The optional
    pathwise ``free_utilisation`` and ``excess_rate`` values are the expected
    fractional-logit responses for the current policy year.  The 5% free
    allowance and cumulative 95% Growth-Phase limit are enforced per
    Anniversary year.
    """
    n_paths = iv.shape[0]
    growth = phase == 0
    free_u = (np.full(n_paths, wb.free_utilisation)
              if free_utilisation is None
              else np.broadcast_to(np.asarray(free_utilisation, dtype=float),
                                   (n_paths,)))
    excess_u = (np.full(n_paths, wb.excess_rate)
                if excess_rate is None
                else np.broadcast_to(np.asarray(excess_rate, dtype=float),
                                     (n_paths,)))
    if not product.allows_growth_withdrawals:
        free_u = np.zeros(n_paths)
        excess_u = np.where(phase == Phase.INCOME.value, excess_u, 0.0)
    min_partial = product.withdrawals.min_withdrawal
    min_residual = product.withdrawals.min_residual_value
    max_pct = product.withdrawals.max_withdrawal_pct_of_iv

    def annual_remaining() -> Array:
        return np.where(
            growth,
            np.maximum(max_pct * wd_limit_base - partial_wd_used, 0.0),
            np.inf)

    # free withdrawals (growth phase, no MVA, within 5% of initial investment)
    if np.any(free_u > 0.0):
        allow = product.withdrawals.free_withdrawal_pct_of_initial * P0
        target = free_u * allow * fraction
        remaining = np.maximum(allow - free_wd_used, 0.0)
        amt = np.where(growth & ~aps_active, np.minimum(target, remaining), 0.0)
        amt = np.minimum(amt, max_pct * iv)
        amt = np.minimum(amt, annual_remaining())
        amt = np.minimum(amt, np.maximum(iv - min_residual, 0.0))
        amt = np.where(amt >= min_partial, amt, 0.0)
        ratio = np.divide(iv - amt, np.maximum(iv, 1e-300), out=np.ones(n_paths), where=iv > 0)
        iv -= amt
        iv_frame *= ratio
        free_wd_used += amt
        partial_wd_used += np.where(growth, amt, 0.0)
        cfs["partial_withdrawals"][:, step] += w * amt

    # excess withdrawals (MVA in window; income reduction in income phase)
    if np.any(excess_u > 0.0):
        requested = excess_u * iv * fraction

        # PDS 15.2/15.3: in the growth phase (without Age Pension+) any
        # remaining Free Withdrawal Amount of the anniversary year is consumed
        # first and attracts no MVA; only the portion above it is an Excess
        # Withdrawal. The used-up part counts against the annual allowance.
        allow = product.withdrawals.free_withdrawal_pct_of_initial * P0
        free_remaining = np.where(growth & ~aps_active,
                                  np.maximum(allow - free_wd_used, 0.0), 0.0)
        tau_rem = product.withdrawals.mva_period_years - t
        if tau_rem > 0:
            z_now = scenarios.zero_rate(step, tau_rem)
            f = product.mva.factor(issue_zero(tau_rem), z_now, tau_rem)
            f = np.asarray(f, dtype=float)
        else:
            f = np.zeros(n_paths)

        def mva_on(gross: Array) -> Array:
            raw = np.asarray(gross, dtype=float) * f
            if product.mva.only_reduces:
                return np.clip(raw, 0.0, gross)
            return np.minimum(raw, gross)

        # Start with the non-APS contractual gross deduction (cash + MVA).
        gross = requested.copy()
        event_cap = np.where(growth, max_pct * iv, np.inf)
        gross = np.minimum(gross, event_cap)
        gross = np.minimum(gross, annual_remaining())
        gross = np.minimum(gross, np.maximum(iv - min_residual, 0.0))

        mwv = _aps_max_withdrawal(product, cas_base, t, cas_start_t, cas_le,
                                  cas_wd, aps_active)
        full_mva = mva_on(iv)
        mwv_binds = aps_active & ((iv - full_mva) > mwv)

        # If IV less MVA binds, the request remains a gross amount inclusive of
        # MVA.  Enforce a residual Withdrawal Value of at least AUD 2,000 on
        # both legs of the lower-of test.
        mva_ratio = np.divide(full_mva, np.maximum(iv, 1e-300),
                              out=np.zeros(n_paths), where=iv > 0.0)
        cash_ratio = 1.0 - mva_ratio
        max_gross_iv_resid = np.where(
            cash_ratio > 0.0,
            np.maximum(iv - min_residual / np.maximum(cash_ratio, 1e-300), 0.0),
            0.0)
        max_gross_mwv_resid = np.where(
            aps_active & (cash_ratio > 0.0),
            np.maximum((mwv - min_residual) / np.maximum(cash_ratio, 1e-300), 0.0),
            np.inf)
        aps_lower_base = np.minimum(iv, mwv)
        aps_event_cap = np.where(growth, max_pct * aps_lower_base, np.inf)
        aps_gross = np.minimum(requested, aps_event_cap)
        aps_gross = np.minimum(aps_gross, annual_remaining())
        aps_gross = np.minimum(aps_gross, max_gross_iv_resid)
        aps_gross = np.minimum(aps_gross, max_gross_mwv_resid)

        # If the APS maximum binds, no MVA is charged.  The requested amount is
        # cash; IV and future income are reduced by cash / MWV, which may be a
        # substantially larger percentage than cash / IV.
        aps_cash = requested.copy()
        aps_cash = np.minimum(aps_cash, aps_event_cap)
        aps_cash = np.minimum(aps_cash, annual_remaining())
        aps_cash = np.minimum(aps_cash, np.maximum(mwv - min_residual, 0.0))

        gross = np.where(aps_active & ~mwv_binds, aps_gross, gross)
        gross = np.where(gross >= min_partial, gross, 0.0)
        free_part = np.where(~aps_active, np.minimum(gross, free_remaining), 0.0)
        mva_amt = mva_on(gross - free_part)
        cash = gross - mva_amt

        aps_cash = np.where(aps_cash >= min_partial, aps_cash, 0.0)
        cash = np.where(mwv_binds, aps_cash, cash)
        mva_amt = np.where(mwv_binds, 0.0, mva_amt)

        pct_aps, aps_iv_deduction, aps_retained = _aps_reduction_terms(
            iv, mwv, cash, mva_amt, mwv_binds)
        iv_deduction = np.where(aps_active, aps_iv_deduction, gross)

        # Usage is defined inclusive of MVA.  In the MWV-binding branch MVA is
        # zero, hence usage is simply the cash amount withdrawn.
        usage = np.where(mwv_binds, cash, gross)

        iv_before = iv.copy()
        ratio = np.divide(iv - iv_deduction, np.maximum(iv, 1e-300),
                          out=np.ones(n_paths), where=iv > 0)
        iv -= iv_deduction
        iv_frame *= ratio
        free_wd_used += np.where(~aps_active, free_part, 0.0)
        partial_wd_used += np.where(growth, usage, 0.0)
        cas_wd += np.where(aps_active, cash, 0.0)

        red_non_aps = np.divide(gross, np.maximum(iv_before, 1e-300),
                                out=np.zeros(n_paths), where=iv_before > 0)
        red = np.where(aps_active, pct_aps, red_non_aps)
        income_annual *= np.where(phase == 1, np.clip(1.0 - red, 0.0, 1.0), 1.0)
        cfs["partial_withdrawals"][:, step] += w * cash
        cfs["mva_retained"][:, step] += w * mva_amt
        cfs["aps_retained"][:, step] += w * np.where(aps_active,
                                                      aps_retained, 0.0)
