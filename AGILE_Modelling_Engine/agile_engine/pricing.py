"""Market-consistent pricing and valuation.

Risk-neutral Monte-Carlo valuation of the generic contract following the
universal GMxB framework of Bauer/Kling/Russ (2008): the contract is priced by
projecting all contract cashflows over risk-neutral ESG paths and discounting
with the pathwise money-market account.

Key outputs
-----------
* component present values (income, guarantee claims, death, surrender, fees,
  crediting margin, MVA),
* BEL split into current Account Value and non-unit part,
* the guarantee "net value" (Lifetime Income Premium income vs. guarantee
  claims) and the fair Lifetime Income Premium,
* market-consistency identity check (premium = PV of financed flows).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Dict, Optional

import numpy as np
from scipy.optimize import brentq

from .behavior import BehaviourModel
from .esg import ESGConfig, Measure, ScenarioSet, simulate
from .mortality import MortalityTable
from .product import (IndexLinkedLifetimeIncomeProduct, ExpenseAssumptions,
                      FeeSpec, PolicySpec)
from .projection import ProjectionConfig, ProjectionResult, project
from ._provenance import assumption_fingerprint


# ---------------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValuationSettings:
    model: str = "heston_hull_white"
    n_paths: int = 20_000
    seed: int = 2026
    heston_substeps: int = 4
    #: Simulation horizon in years. ``None`` (default) resolves per model
    #: point to the projection terminal age of the longer-lived covered life,
    #: so a younger spouse tail is not truncated. A shorter explicit horizon
    #: truncates lifetime-income claims at the closeout.
    horizon_years: Optional[float] = None
    #: Full state paths are expensive and are not needed for normal valuation;
    #: callers that need path diagnostics can opt in explicitly.
    projection: ProjectionConfig = field(
        default_factory=lambda: ProjectionConfig(record_paths=False))
    #: Simplified real-world baseline used by profitability projections.  It
    #: is deliberately separate from the risk-neutral valuation model.
    real_world_model: str = "hull_white_bs"

    def __post_init__(self) -> None:
        if self.model not in ("black_scholes", "heston", "hull_white_bs",
                              "heston_hull_white"):
            raise ValueError(f"Unknown valuation model '{self.model}'.")
        if self.real_world_model not in (
                "black_scholes", "heston", "hull_white_bs",
                "heston_hull_white"):
            raise ValueError(
                f"Unknown real-world model '{self.real_world_model}'.")
        if isinstance(self.n_paths, bool) or not isinstance(self.n_paths, (int, np.integer)) \
                or self.n_paths <= 0:
            raise ValueError("n_paths must be a positive integer.")
        if isinstance(self.seed, bool) or not isinstance(self.seed, (int, np.integer)) \
                or self.seed < 0:
            raise ValueError("seed must be a non-negative integer.")
        if isinstance(self.heston_substeps, bool) \
                or not isinstance(self.heston_substeps, (int, np.integer)) \
                or self.heston_substeps <= 0:
            raise ValueError("heston_substeps must be a positive integer.")
        if self.horizon_years is not None:
            h = float(self.horizon_years)
            if not np.isfinite(h) or h <= 0.0:
                raise ValueError("horizon_years must be positive and finite.")
            if abs(h * 12.0 - round(h * 12.0)) > 1e-9:
                raise ValueError("horizon_years must fall on the monthly grid.")


def resolve_horizon(settings: ValuationSettings, policy: PolicySpec) -> float:
    """Horizon in years: explicit setting, else to the projection max age."""
    if settings.horizon_years is not None:
        return float(settings.horizon_years)
    remaining = settings.projection.max_age - policy.age
    if (policy.spouse and policy.spouse_age is not None
            and policy.spouse_death_election.value == "continue_income"):
        remaining = max(remaining, settings.projection.max_age - policy.spouse_age)
    return float(max(1.0, np.ceil(remaining)))


@dataclass
class ValuationResult:
    pv: Dict[str, float]
    premium: float
    bel_nonunit: float
    bel_total: float
    guarantee_value: float          # PV(claims) - PV(LIP): net cost of the GLWB rider
    insurer_net_value: float        # PV(margins) - claims - hedge/operating costs
    identity_gap: float
    projection: ProjectionResult
    settings: ValuationSettings
    provenance: str

    def summary(self) -> Dict[str, float]:
        out = {f"pv_{k}": v for k, v in self.pv.items()}
        out.update(premium=self.premium, bel_nonunit=self.bel_nonunit,
                   bel_total=self.bel_total, guarantee_value=self.guarantee_value,
                   insurer_net_value=self.insurer_net_value,
                   identity_gap=self.identity_gap)
        return out


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------

def build_scenarios(esg_config: ESGConfig, settings: ValuationSettings,
                    measure: Measure = Measure.RISK_NEUTRAL,
                    horizon_years: Optional[float] = None) -> ScenarioSet:
    horizon = horizon_years if horizon_years is not None else \
        (settings.horizon_years if settings.horizon_years is not None else 45.0)
    kwargs = ({"substeps": settings.heston_substeps}
              if settings.model in ("heston", "heston_hull_white") else {})
    return simulate(settings.model, esg_config, horizon,
                    settings.n_paths, measure=measure, seed=settings.seed,
                    **kwargs)


def value_contract(product: IndexLinkedLifetimeIncomeProduct, policy: PolicySpec,
                   esg_config: ESGConfig, mortality: MortalityTable,
                   behaviour: BehaviourModel,
                   expenses: Optional[ExpenseAssumptions] = None,
                   settings: ValuationSettings = ValuationSettings(),
                   scenarios: Optional[ScenarioSet] = None,
                   surrender_policy: Optional[object] = None,
                   income_election_policy: Optional[object] = None,
                   ) -> ValuationResult:
    """Full risk-neutral valuation of one model point."""
    if scenarios is None:
        scenarios = build_scenarios(esg_config, settings, Measure.RISK_NEUTRAL,
                                    horizon_years=resolve_horizon(settings, policy))
    elif scenarios.measure != Measure.RISK_NEUTRAL:
        raise ValueError("value_contract requires risk-neutral scenarios.")
    else:
        if scenarios.config != esg_config:
            raise ValueError("Supplied scenarios were generated from a different ESG configuration.")
        if scenarios.model_name != settings.model:
            raise ValueError("Supplied scenarios do not match ValuationSettings.model.")
        if scenarios.seed != settings.seed:
            raise ValueError("Supplied scenarios do not match ValuationSettings.seed.")
        if scenarios.n_paths != settings.n_paths:
            raise ValueError("Supplied scenarios do not match ValuationSettings.n_paths.")
        expected_substeps = (settings.heston_substeps
                             if settings.model in ("heston", "heston_hull_white")
                             else None)
        if scenarios.substeps != expected_substeps:
            raise ValueError("Supplied scenarios do not match Heston substep settings.")
        expected_horizon = resolve_horizon(settings, policy)
        if not np.isclose(scenarios.times[-1], expected_horizon,
                          rtol=0.0, atol=1e-12):
            raise ValueError("Supplied scenarios do not match the resolved valuation horizon.")

    # Dividend yield is market data, but older APIs also carried a duplicate
    # product-level copy.  Reject divergence instead of silently valuing the
    # hedge and simulating its underlying under different forwards.
    for ix, params in esg_config.equity.items():
        if ix not in product.dividend_yield or not np.isclose(
                product.dividend_yield[ix], params.dividend_yield,
                rtol=0.0, atol=1e-12):
            raise ValueError("Product and ESG dividend-yield assumptions differ; "
                             "use one consistent market-data basis.")

    res = project(product, policy, scenarios, behaviour, mortality,
                  expenses=expenses, config=settings.projection,
                  surrender_policy=surrender_policy,
                  income_election_policy=income_election_policy)
    pv = res.pv_by_component()

    premium = pv["premium"]
    bel_nonunit = (pv["guarantee_claims"] + pv["hedge_costs"] + pv["expenses"]
                   - pv["fees_product"] - pv["fees_lip"] - pv["crediting_margin"]
                   - pv["mva_retained"] - pv["aps_retained"])
    guarantee_value = pv["guarantee_claims"] - pv["fees_lip"]

    provenance = assumption_fingerprint(product, policy, esg_config, mortality,
                                        behaviour, expenses, settings,
                                        scenarios.content_fingerprint)
    return ValuationResult(pv=pv, premium=premium, bel_nonunit=bel_nonunit,
                           bel_total=policy.net_initial_investment + bel_nonunit,
                           guarantee_value=guarantee_value,
                           insurer_net_value=res.pv_insurer_net(),
                           identity_gap=res.identity_gap(),
                           projection=res, settings=settings,
                           provenance=provenance)


# ---------------------------------------------------------------------------
# Fair-fee solvers (common random numbers)
# ---------------------------------------------------------------------------

def fair_lifetime_income_premium(product: IndexLinkedLifetimeIncomeProduct,
                                 policy: PolicySpec,
                                 esg_config: ESGConfig, mortality: MortalityTable,
                                 behaviour: BehaviourModel,
                                 settings: ValuationSettings = ValuationSettings(),
                                 target: float = 0.0,
                                 lo: float = 0.0, hi: float = 0.05,
                                 tol: float = 1e-6
                                 ) -> float:
    """Solve for the LIP such that the guarantee is value-neutral.

    Default target: PV(guarantee claims) - PV(LIP income) = 0, i.e. the fair
    price of the GLWB rider in the sense of Bauer et al. (2008) / Holz et al.
    (2012). Uses one fixed scenario set (common random numbers) so the
    objective is smooth in the fee.
    """
    scenarios = build_scenarios(esg_config, settings, Measure.RISK_NEUTRAL,
                                horizon_years=resolve_horizon(settings, policy))

    def objective(lip: float) -> float:
        prod = replace(product, fees=replace(product.fees, lifetime_income_premium=lip))
        res = value_contract(prod, policy, esg_config, mortality, behaviour,
                             settings=settings, scenarios=scenarios)
        return res.guarantee_value - target

    f_lo, f_hi = objective(lo), objective(hi)
    tries = 0
    while f_lo * f_hi > 0 and tries < 6:
        hi *= 1.8
        f_hi = objective(hi)
        tries += 1
    if f_lo * f_hi > 0:
        raise RuntimeError(f"Fair-LIP bracket failed: f({lo})={f_lo:.6f}, f({hi})={f_hi:.6f}")
    return float(brentq(objective, lo, hi, xtol=tol))


# ---------------------------------------------------------------------------
# Market-consistent greeks (bump & revalue with common random numbers)
# ---------------------------------------------------------------------------

def greeks(product: IndexLinkedLifetimeIncomeProduct, policy: PolicySpec,
           esg_config: ESGConfig,
           mortality: MortalityTable, behaviour: BehaviourModel,
           settings: ValuationSettings = ValuationSettings(),
           equity_bump: float = 0.01, vol_bump: float = 0.01,
           rate_bump: float = 0.001,
           expenses: Optional[ExpenseAssumptions] = None) -> Dict[str, float]:
    """Finite-difference sensitivities of the insurer net value.

    * equity delta: instantaneous index shock (affects current-year crediting
      and the DVA replication - the account is not unit-linked, so this
      is structurally small compared to a variable annuity),
    * vega: parallel shock to model volatilities (cap-hedge cost channel),
    * rho: parallel zero-curve shift (re-simulated, common random numbers).
    """
    if equity_bump <= 0.0 or vol_bump <= 0.0 or rate_bump <= 0.0:
        raise ValueError("Greek bumps must be strictly positive.")

    def nav(cfg: ESGConfig, scen: Optional[ScenarioSet] = None) -> float:
        return value_contract(product, policy, cfg, mortality, behaviour,
                              expenses=expenses, settings=settings,
                              scenarios=scen).insurer_net_value

    base_scen = build_scenarios(esg_config, settings, Measure.RISK_NEUTRAL,
                                horizon_years=resolve_horizon(settings, policy))
    base = value_contract(product, policy, esg_config, mortality, behaviour,
                          expenses=expenses, settings=settings,
                          scenarios=base_scen).insurer_net_value

    # equity: scale all index levels after t=0
    def equity_shocked(scale: float) -> ScenarioSet:
        levels = {ix: lv.copy() for ix, lv in base_scen.index_levels.items()}
        for ix in levels:
            levels[ix][:, 1:] *= scale
        return replace(base_scen, index_levels=levels)

    nav_eq_up = nav(esg_config, equity_shocked(1.0 + equity_bump))
    nav_eq_dn = nav(esg_config, equity_shocked(1.0 - equity_bump))

    cfg_vol_up = esg_config.bump_equity_vol_abs(vol_bump)  # exact +1 vol point
    nav_vol = nav(cfg_vol_up)

    cfg_r_up = esg_config.with_curve(esg_config.curve.shifted(rate_bump))
    cfg_r_dn = esg_config.with_curve(esg_config.curve.shifted(-rate_bump))
    nav_r_up, nav_r_dn = nav(cfg_r_up), nav(cfg_r_dn)

    p0 = policy.net_initial_investment
    return {
        "nav": base,
        "equity_delta_pct": (nav_eq_up - nav_eq_dn) / (2 * equity_bump) / p0,
        "vega_per_volpt": (nav_vol - base) * (0.01 / vol_bump) / p0,
        "rho_per_100bp": (nav_r_up - nav_r_dn) / (2 * rate_bump) * 0.01 / p0,
    }
