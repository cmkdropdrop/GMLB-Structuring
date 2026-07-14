"""Profitability analysis.

Combines a real-world projection (expected experience) with market-consistent
reserving (certainty-equivalent BEL run-off from the risk-neutral valuation)
and the capital module to produce a shareholder view:

* annual profit signature (fees + stochastic overnight backing income
  + optional retained hedge gain + MVA/APS retained - guarantee claims
  - option/hedge costs - expenses),
* distributable earnings after reserve movements and cost of required capital,
* PVFP at hurdle rate, new-business margin, IRR, payback year.

Methodological choices (documented limitations)
-----------------------------------------------
* Reserving uses the certainty-equivalent BEL pattern: BEL_t is the forward
  value of remaining risk-neutral expected cashflows. No nested stochastics -
  reserve volatility is captured through the sensitivity module instead.
* Required capital follows the SCR run-off pattern from the capital module
  (proportional driver approach).
* Real-world experience uses ``settings.real_world_model`` (repository base:
  Black-Scholes-Hull-White), independently of the Q valuation model.
* The insurer's administrative Account-Value backing earns the pathwise AUD
  overnight rate and is independent of the customer Reference Fund.  Annual
  option fair value, purchase markup and hedge-reference management fee are
  explicit insurer costs.  ``ProjectionConfig.hedge_vol_spread`` remains a
  disabled-by-default legacy execution proxy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np
from numpy.typing import NDArray

from .behavior import BehaviourModel
from .capital import CapitalResult, CapitalStresses, compute_capital
from .esg import ESGConfig, Measure, simulate
from .mortality import MortalityTable
from .pricing import (ValuationResult, ValuationSettings, resolve_horizon,
                      value_contract)
from .product import (IndexLinkedLifetimeIncomeProduct, ExpenseAssumptions,
                      PolicySpec)
from .projection import ProjectionResult, project, STEPS_PER_YEAR
from ._provenance import assumption_fingerprint

Array = NDArray[np.float64]


@dataclass(frozen=True)
class ProfitabilitySettings:
    hurdle_rate: float = 0.08
    tax_rate: float = 0.30
    capital_earning_spread: float = 0.0   # capital invested at cash + spread
    include_capital: bool = True

    def __post_init__(self) -> None:
        values = np.asarray([self.hurdle_rate, self.tax_rate,
                             self.capital_earning_spread], dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError("Profitability settings must be finite.")
        if self.hurdle_rate <= -1.0 or not 0.0 <= self.tax_rate <= 1.0:
            raise ValueError("hurdle_rate must exceed -100% and tax_rate be in [0,1].")
        if not isinstance(self.include_capital, (bool, np.bool_)):
            raise ValueError("include_capital must be boolean.")


@dataclass
class ProfitabilityResult:
    years: Array
    profit_signature: Array          # pre-tax insurer net cashflow per year (RW)
    distributable: Array             # post-tax, post-capital shareholder cashflow
    bel_pattern: Array
    capital_pattern: Array
    pvfp_hurdle: float
    vnb_market_consistent: float     # risk-neutral insurer net value - risk margin
    new_business_margin: float       # VNB / premium
    pvfp_margin: float               # PVFP@hurdle / premium
    irr: Optional[float]
    payback_year: Optional[int]
    capital: Optional[CapitalResult]

    def summary(self) -> Dict[str, float]:
        return dict(pvfp_hurdle=self.pvfp_hurdle,
                    vnb_market_consistent=self.vnb_market_consistent,
                    new_business_margin=self.new_business_margin,
                    pvfp_margin=self.pvfp_margin,
                    irr=float("nan") if self.irr is None else self.irr,
                    payback_year=-1 if self.payback_year is None else self.payback_year)


# ---------------------------------------------------------------------------

def _annual_net_cashflow(res: ProjectionResult) -> Array:
    """Insurer net cashflow per policy year (undiscounted, expected)."""
    income = (res.annual_aggregate("fees_product") + res.annual_aggregate("fees_lip")
              + res.annual_aggregate("crediting_margin")
              + res.annual_aggregate("mva_retained")
              + res.annual_aggregate("aps_retained"))
    outgo = (res.annual_aggregate("guarantee_claims")
             + res.annual_aggregate("hedge_costs")
             + res.annual_aggregate("expenses"))
    return income - outgo


def _bel_runoff(res_q: ProjectionResult, curve) -> Array:
    """Certainty-equivalent BEL at each policy year (non-unit, can be negative)."""
    prof = res_q.expected_cashflow_profile()
    net_pv = (prof["guarantee_claims"] + prof["hedge_costs"] + prof["expenses"]
              - prof["fees_product"] - prof["fees_lip"] - prof["crediting_margin"]
              - prof["mva_retained"] - prof["aps_retained"])
    remaining = np.cumsum(net_pv[::-1])[::-1]        # PV(0) of flows >= t
    times = res_q.times
    annual_idx = np.arange(0, len(times), STEPS_PER_YEAR)
    df = np.asarray(curve.df(times[annual_idx]), dtype=float)
    bel = np.zeros(len(annual_idx))
    for i, k in enumerate(annual_idx):
        tail = remaining[k + 1] if k + 1 < len(net_pv) else 0.0
        bel[i] = tail / max(df[i], 1e-12)
    return bel


def _irr(cashflows: Array) -> Optional[float]:
    """Lowest real IRR above -100%, found on a broad log-rate grid."""
    cf = np.asarray(cashflows, dtype=float)
    if np.all(cf >= 0) or np.all(cf <= 0):
        return None

    def npv_log(log_accumulation: float) -> float:
        t = np.arange(len(cf))
        exponent = -log_accumulation * t
        exponent -= np.max(exponent)
        cf_scale = max(float(np.max(np.abs(cf))), 1.0)
        # Positive rescaling preserves roots/signs and avoids overflow for
        # rates extremely close to -100% over long projection horizons.
        return float(np.sum((cf / cf_scale) * np.exp(exponent)))

    # Searching in log(1+r) is stable arbitrarily close to -100% and covers
    # IRRs well above the former hard 200% ceiling.  Multiple-IRR cashflows are
    # inherently ambiguous; return the lowest sign-changing root.
    grid = np.linspace(-20.0, float(np.log1p(1.0e6)), 2001)
    values = np.asarray([npv_log(x) for x in grid])
    exact = np.flatnonzero(np.isclose(values, 0.0, rtol=0.0, atol=1e-12))
    if len(exact):
        return float(np.expm1(grid[int(exact[0])]))
    crossings = np.flatnonzero(values[:-1] * values[1:] < 0.0)
    if len(crossings) == 0:
        return None
    i = int(crossings[0])
    lo, hi = float(grid[i]), float(grid[i + 1])
    f_lo = float(values[i])
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = npv_log(mid)
        if abs(f_mid) < 1e-10:
            break
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return float(np.expm1(0.5 * (lo + hi)))


# ---------------------------------------------------------------------------

def analyse_profitability(product: IndexLinkedLifetimeIncomeProduct,
                          policy: PolicySpec,
                          esg_config: ESGConfig, mortality: MortalityTable,
                          behaviour: BehaviourModel,
                          expenses: ExpenseAssumptions,
                          settings: ValuationSettings = ValuationSettings(),
                          prof_settings: ProfitabilitySettings = ProfitabilitySettings(),
                          capital_result: Optional[CapitalResult] = None,
                          compute_capital_if_missing: bool = True,
                          capital_stresses: CapitalStresses = CapitalStresses(),
                          valuation_result: Optional[ValuationResult] = None
                          ) -> ProfitabilityResult:
    """End-to-end profitability of one model point (new business view).

    ``valuation_result`` may be supplied to reuse an existing risk-neutral
    valuation (must have been produced with identical product / policy /
    assumptions / settings, e.g. by the sensitivity runner); otherwise the
    valuation is computed here.
    """
    if not isinstance(compute_capital_if_missing, (bool, np.bool_)):
        raise ValueError("compute_capital_if_missing must be boolean.")

    # 1) market-consistent valuation (reserving basis + VNB)
    if valuation_result is not None:
        expected_provenance = assumption_fingerprint(
            product, policy, esg_config, mortality, behaviour, expenses,
            settings,
            valuation_result.projection.scenarios.content_fingerprint)
        if valuation_result.provenance != expected_provenance:
            raise ValueError("valuation_result was produced from different assumptions or scenarios.")
    val_q = valuation_result if valuation_result is not None else value_contract(
        product, policy, esg_config, mortality, behaviour,
        expenses=expenses, settings=settings)

    # 2) real-world experience
    rw_model = settings.real_world_model
    sim_kwargs = ({"substeps": settings.heston_substeps}
                  if rw_model in ("heston", "heston_hull_white") else {})
    scen_rw = simulate(rw_model, esg_config,
                       resolve_horizon(settings, policy),
                       settings.n_paths, measure=Measure.REAL_WORLD,
                       seed=settings.seed + 1, **sim_kwargs)
    res_rw = project(product, policy, scen_rw, behaviour, mortality,
                     expenses=expenses, config=settings.projection)

    signature = _annual_net_cashflow(res_rw)
    n_years = len(signature)
    years = np.arange(n_years, dtype=float)

    # 3) reserves and capital patterns
    bel = _bel_runoff(val_q.projection, esg_config.curve)
    bel = bel[:n_years] if len(bel) >= n_years else np.pad(bel, (0, n_years - len(bel)))

    # The flag is authoritative: a supplied CapitalResult must not silently
    # turn capital back on when the caller explicitly requested a gross view.
    capital = capital_result if prof_settings.include_capital else None
    if capital is not None:
        expected_capital_provenance = assumption_fingerprint(
            product, policy, esg_config, mortality, behaviour, expenses,
            settings, capital_stresses, capital.with_risk_margin,
            capital.scenario_fingerprint)
        if capital.provenance != expected_capital_provenance:
            raise ValueError("capital_result was produced from different assumptions or stresses.")
    if capital is None and prof_settings.include_capital and compute_capital_if_missing:
        capital = compute_capital(product, policy, esg_config, mortality, behaviour,
                                  expenses=expenses, settings=settings,
                                  stresses=capital_stresses)
    rm_pat = np.zeros(n_years)
    if capital is not None and capital.scr_pattern is not None:
        cap_pat = np.asarray(capital.scr_pattern, dtype=float)
        cap_pat = cap_pat[:n_years] if len(cap_pat) >= n_years else np.pad(
            cap_pat, (0, n_years - len(cap_pat)))
        # Risk margin is a liability/reserve, not required capital.  Allocate
        # its run-off to BEL instead of adding it to the SCR pattern (which
        # previously double-classified it and distorted capital income).
        if capital.risk_margin > 0.0 and cap_pat[0] > 0.0:
            rm_pat = capital.risk_margin * cap_pat / cap_pat[0]
    else:
        cap_pat = np.zeros(n_years)
    bel = bel + rm_pat

    # 4) distributable earnings
    curve = esg_config.curve
    fwd = np.array([curve.forward_zero(max(y - 1.0, 0.0), max(y, 1e-6))
                    for y in range(1, n_years + 1)])
    tax = prof_settings.tax_rate
    distributable = np.zeros(n_years)
    # year 0: acquisition strain + initial capital injection
    reserve_change_0 = bel[0]  # from 0 (pre-issue) to BEL_0
    profit_0 = signature[0] - reserve_change_0
    distributable[0] = (1.0 - tax) * profit_0 - cap_pat[0]
    for y in range(1, n_years):
        interest_on_reserve = bel[y - 1] * (np.exp(fwd[y - 1]) - 1.0)
        d_bel = bel[y] - bel[y - 1]
        profit = signature[y] + interest_on_reserve - d_bel
        cap_release = cap_pat[y - 1] - cap_pat[y]
        cap_income = cap_pat[y - 1] * (np.exp(fwd[y - 1]) - 1.0
                                       + prof_settings.capital_earning_spread)
        distributable[y] = (1.0 - tax) * (profit + cap_income) + cap_release

    # 5) metrics
    hurdle = prof_settings.hurdle_rate
    disc_h = (1.0 + hurdle) ** -years
    # PVFP is the shareholder present value of distributable earnings and
    # therefore includes reserve and (when requested) capital strain/release.
    # The old implementation discounted raw margin cashflows and was invariant
    # to include_capital despite presenting the result as profitability.
    pvfp = float(np.sum(distributable * disc_h))
    p0 = val_q.premium
    vnb = val_q.insurer_net_value - (capital.risk_margin if capital else 0.0)
    irr = _irr(distributable)
    cum = np.cumsum(distributable)
    payback = int(np.argmax(cum > 0)) if np.any(cum > 0) else None
    if payback == 0 and distributable[0] <= 0:
        payback = None

    return ProfitabilityResult(years=years, profit_signature=signature,
                               distributable=distributable, bel_pattern=bel,
                               capital_pattern=cap_pat, pvfp_hurdle=pvfp,
                               vnb_market_consistent=vnb,
                               new_business_margin=vnb / p0,
                               pvfp_margin=pvfp / p0, irr=irr,
                               payback_year=payback, capital=capital)
