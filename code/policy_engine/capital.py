"""Solvency-II-style research capital proxy (standard-formula design).

Computes shock-based capital per risk module with revaluation of the
insurer net asset value (NAV = market-consistent PV of insurer net cashflows),
then aggregates with the Solvency II correlation matrices:

Market:  interest (up/down), equity, (optional) equity volatility add-on
Life:    mortality, longevity, lapse (up/down/mass), expense, catastrophe

plus a cost-of-capital risk margin. The engine applies Solvency-II-like
standard-formula calibrations by default but every shock is configurable
parameters. It is not APRA/LAGIC prescribed capital: the APRA fund-level
asset, insurance, concentration, operational and combined-stress architecture
cannot be produced by swapping this stress set.

Notes specific to the case-study product
----------------------------------------
* The Investment Value is an indexed account, not unit-linked: an equity level
  shock affects only the current-year crediting/DVA replication, so equity SCR
  is structurally small; the dominant market risk is interest rate (guarantee
  discounting, MVA window) and volatility (cap-hedge budget).
* Lapse-down is typically the binding lapse stress once the GLWB is
  in-the-money (fewer surrenders = longer guarantee exposure).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Dict, Optional

import numpy as np

from .behavior import BehaviourModel
from .curves import YieldCurve
from .esg import ESGConfig, Measure
from .mortality import MortalityTable
from .pricing import (ValuationSettings, build_scenarios, resolve_horizon,
                      value_contract)
from .product import AgileProduct, ExpenseAssumptions, PolicySpec
from ._provenance import assumption_fingerprint


# ---------------------------------------------------------------------------
# Stress definitions (Solvency II standard formula defaults)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CapitalStresses:
    # interest rate: relative shifts by tenor (SII Art. 166/167 style)
    ir_up_tenors: tuple = (1.0, 5.0, 10.0, 20.0, 30.0)
    ir_up_factors: tuple = (0.70, 0.55, 0.42, 0.26, 0.25)
    ir_dn_factors: tuple = (-0.75, -0.46, -0.31, -0.29, -0.28)
    ir_up_min_shift: float = 0.01
    equity_type1: float = 0.39          # symmetric adjustment set to 0
    equity_vol_rel: float = 0.25        # optional add-on (not SII SF)
    include_equity_vol: bool = True
    longevity: float = -0.20            # q multiplier - 1
    mortality: float = 0.15
    lapse_up: float = 0.50
    lapse_dn: float = -0.50
    lapse_mass: float = 0.40
    expense_level: float = 0.10
    expense_inflation_add: float = 0.01
    cat_mortality_add: float = 0.0015   # additive q in year 1
    coc_rate: float = 0.06

    # correlation matrices
    corr_market: tuple = ((1.0, 0.5, 0.25),   # ir, equity, eq-vol
                          (0.5, 1.0, 0.75),   # (used when IR-down is binding)
                          (0.25, 0.75, 1.0))
    #: SII standard formula (Delegated Reg. Annex IV): the interest-equity
    #: correlation of 0.5 applies only when the *downward* interest stress is
    #: binding; when the upward stress binds it is 0.
    corr_market_ir_up: tuple = ((1.0, 0.0, 0.0),
                                (0.0, 1.0, 0.75),
                                (0.0, 0.75, 1.0))
    corr_life_labels: tuple = ("mortality", "longevity", "lapse", "expense", "cat")
    corr_life: tuple = ((1.00, -0.25, 0.00, 0.25, 0.25),
                        (-0.25, 1.00, 0.25, 0.25, 0.00),
                        (0.00, 0.25, 1.00, 0.50, 0.25),
                        (0.25, 0.25, 0.50, 1.00, 0.25),
                        (0.25, 0.00, 0.25, 0.25, 1.00))
    corr_market_life: float = 0.25

    def __post_init__(self) -> None:
        if not isinstance(self.include_equity_vol, (bool, np.bool_)):
            raise ValueError("include_equity_vol must be boolean.")
        tenors = np.asarray(self.ir_up_tenors, dtype=float)
        up = np.asarray(self.ir_up_factors, dtype=float)
        dn = np.asarray(self.ir_dn_factors, dtype=float)
        if tenors.ndim != 1 or len(tenors) < 2 or len(up) != len(tenors) \
                or len(dn) != len(tenors) or not np.all(np.isfinite(tenors)) \
                or not np.all(np.diff(tenors) > 0.0) or np.any(tenors <= 0.0):
            raise ValueError("Interest stress tenors must be finite, positive, increasing and aligned.")
        if not np.all(np.isfinite(up)) or not np.all(np.isfinite(dn)) \
                or np.any(up < 0.0) or np.any(dn > 0.0):
            raise ValueError("Interest up/down factors have invalid signs or values.")

        numeric = np.asarray([
            self.ir_up_min_shift, self.equity_type1, self.equity_vol_rel,
            self.longevity, self.mortality, self.lapse_up, self.lapse_dn,
            self.lapse_mass, self.expense_level, self.expense_inflation_add,
            self.cat_mortality_add, self.coc_rate, self.corr_market_life,
        ], dtype=float)
        if not np.all(np.isfinite(numeric)):
            raise ValueError("Capital stress parameters must be finite.")
        if self.ir_up_min_shift < 0.0 or not 0.0 <= self.equity_type1 < 1.0 \
                or self.equity_vol_rel < 0.0 or self.longevity <= -1.0 \
                or self.mortality <= -1.0 or self.lapse_up <= -1.0 \
                or self.lapse_dn <= -1.0 or not 0.0 <= self.lapse_mass <= 1.0 \
                or self.expense_level < 0.0 or self.expense_inflation_add < 0.0 \
                or self.cat_mortality_add < 0.0 \
                or self.coc_rate < 0.0 or not -1.0 <= self.corr_market_life <= 1.0:
            raise ValueError("Capital stress magnitudes are outside admissible ranges.")

        def validate_corr(name: str, values, size: int) -> None:
            corr = np.asarray(values, dtype=float)
            if corr.shape != (size, size) or not np.all(np.isfinite(corr)) \
                    or not np.allclose(corr, corr.T, atol=1e-12, rtol=0.0) \
                    or not np.allclose(np.diag(corr), 1.0, atol=1e-12, rtol=0.0) \
                    or np.any(np.abs(corr) > 1.0 + 1e-12) \
                    or np.min(np.linalg.eigvalsh(corr)) < -1e-10:
                raise ValueError(f"{name} must be a symmetric positive-semidefinite correlation matrix.")

        validate_corr("corr_market", self.corr_market, 3)
        validate_corr("corr_market_ir_up", self.corr_market_ir_up, 3)
        validate_corr("corr_life", self.corr_life, 5)
        expected_labels = ("mortality", "longevity", "lapse", "expense", "cat")
        if tuple(self.corr_life_labels) != expected_labels:
            raise ValueError(f"corr_life_labels must be ordered as {expected_labels}.")


@dataclass
class CapitalResult:
    framework: str = field(default="SII_RESEARCH_PROXY_NOT_APRA", init=False)
    nav_base: float
    scr_by_module: Dict[str, float]
    scr_market: float
    scr_life: float
    bscr: float
    risk_margin: float
    scr_pattern: Optional[np.ndarray] = None
    provenance: str = ""
    stresses: CapitalStresses = field(default_factory=CapitalStresses)
    with_risk_margin: bool = True
    scenario_fingerprint: str = ""

    def summary(self) -> Dict[str, float]:
        out = dict(nav_base=self.nav_base, scr_market=self.scr_market,
                   scr_life=self.scr_life, bscr=self.bscr,
                   risk_margin=self.risk_margin)
        out.update({f"scr_{k}": v for k, v in self.scr_by_module.items()})
        return out


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def _aggregate(scrs: np.ndarray, corr: np.ndarray) -> float:
    scrs = np.asarray(scrs, dtype=float)
    return float(np.sqrt(scrs @ np.asarray(corr) @ scrs))


def _market_corr(stresses: CapitalStresses, ir_down_binding: bool) -> np.ndarray:
    """SII market correlation matrix, direction-dependent for interest risk."""
    return np.asarray(stresses.corr_market if ir_down_binding
                      else stresses.corr_market_ir_up)


def compute_capital(product: AgileProduct, policy: PolicySpec,
                    esg_config: ESGConfig, mortality: MortalityTable,
                    behaviour: BehaviourModel,
                    expenses: Optional[ExpenseAssumptions] = None,
                    settings: ValuationSettings = ValuationSettings(),
                    stresses: CapitalStresses = CapitalStresses(),
                    with_risk_margin: bool = True) -> CapitalResult:
    """Shock-based research SCR with revaluation per module.

    All market shocks re-simulate the ESG with the same seed (common random
    numbers); life shocks re-run the projection on the base scenarios.
    """
    if not isinstance(with_risk_margin, (bool, np.bool_)):
        raise ValueError("with_risk_margin must be boolean.")

    def nav(prod=product, pol=policy, cfg=esg_config, mort=mortality,
            beh=behaviour, exp=expenses, scen=None) -> float:
        return value_contract(prod, pol, cfg, mort, beh, expenses=exp,
                              settings=settings, scenarios=scen).insurer_net_value

    # Base scenario set, reused for the base NAV, the equity shock and all
    # life shocks (they do not change the market model, so re-simulating
    # would reproduce the identical paths; caching is numerically neutral).
    # Interest and volatility shocks must re-simulate (same seed = CRN).
    base_scen = build_scenarios(esg_config, settings, Measure.RISK_NEUTRAL,
                                horizon_years=resolve_horizon(settings, policy))
    base_res = value_contract(product, policy, esg_config, mortality, behaviour,
                              expenses=expenses, settings=settings,
                              scenarios=base_scen)
    nav_base = base_res.insurer_net_value

    scr: Dict[str, float] = {}

    # ---- market: interest rate ---------------------------------------- #
    curve = esg_config.curve
    tenors = np.asarray(curve.tenors)
    up_f = np.interp(tenors, stresses.ir_up_tenors, stresses.ir_up_factors)
    dn_f = np.interp(tenors, stresses.ir_up_tenors, stresses.ir_dn_factors)
    curve_up = curve.scaled(up_f, min_abs_shift=stresses.ir_up_min_shift)
    curve_dn = curve.scaled(dn_f)
    nav_ir_up = nav(cfg=esg_config.with_curve(curve_up))
    nav_ir_dn = nav(cfg=esg_config.with_curve(curve_dn))
    scr["interest_up"] = max(0.0, nav_base - nav_ir_up)
    scr["interest_down"] = max(0.0, nav_base - nav_ir_dn)
    scr_ir = max(scr["interest_up"], scr["interest_down"])

    # ---- market: equity level ------------------------------------------ #
    shocked_levels = {ix: lv.copy() for ix, lv in base_scen.index_levels.items()}
    for ix in shocked_levels:
        shocked_levels[ix][:, 1:] *= (1.0 - stresses.equity_type1)
    scen_shocked = replace(base_scen, index_levels=shocked_levels)
    scr["equity"] = max(0.0, nav_base - nav(scen=scen_shocked))

    # ---- market: equity volatility (add-on) ----------------------------- #
    scr["equity_vol"] = 0.0
    if stresses.include_equity_vol:
        cfg_vol = esg_config.bump_equity_vol(stresses.equity_vol_rel)
        scr["equity_vol"] = max(0.0, nav_base - nav(cfg=cfg_vol))

    market_vec = np.array([scr_ir, scr["equity"], scr["equity_vol"]])
    scr_market = _aggregate(market_vec, _market_corr(
        stresses, ir_down_binding=scr["interest_down"] >= scr["interest_up"]))

    # ---- life (base market scenarios re-used, projection re-run) ---------- #
    scr["longevity"] = max(0.0, nav_base - nav(
        mort=mortality.stressed(1.0 + stresses.longevity), scen=base_scen))
    scr["mortality"] = max(0.0, nav_base - nav(
        mort=mortality.stressed(1.0 + stresses.mortality), scen=base_scen))
    scr["lapse_up"] = max(0.0, nav_base - nav(
        beh=behaviour.scaled_lapses(1.0 + stresses.lapse_up), scen=base_scen))
    scr["lapse_down"] = max(0.0, nav_base - nav(
        beh=behaviour.scaled_lapses(1.0 + stresses.lapse_dn), scen=base_scen))
    # mass lapse: fraction of the portfolio surrenders immediately; the lost
    # value is that fraction of the (positive) in-force value.
    scr["lapse_mass"] = max(0.0, stresses.lapse_mass * nav_base)
    scr_lapse = max(scr["lapse_up"], scr["lapse_down"], scr["lapse_mass"])

    if expenses is not None:
        exp_shock = replace(expenses,
                            maintenance_per_policy=expenses.maintenance_per_policy
                            * (1.0 + stresses.expense_level),
                            maintenance_pct_of_iv=expenses.maintenance_pct_of_iv
                            * (1.0 + stresses.expense_level),
                            expense_inflation=expenses.expense_inflation
                            + stresses.expense_inflation_add)
        scr["expense"] = max(0.0, nav_base - nav(exp=exp_shock, scen=base_scen))
    else:
        scr["expense"] = 0.0

    # cat: additive mortality shock in the first projection year only
    # (SII standard formula: +1.5 per mille for the following 12 months).
    cat_table = replace(mortality,
                        q_add_first_year=mortality.q_add_first_year
                        + stresses.cat_mortality_add)
    scr["cat"] = max(0.0, nav_base - nav(mort=cat_table, scen=base_scen))

    life_vec = np.array([scr["mortality"], scr["longevity"], scr_lapse,
                         scr["expense"], scr["cat"]])
    scr_life = _aggregate(life_vec, np.asarray(stresses.corr_life))

    # ---- aggregation ------------------------------------------------------ #
    top_corr = np.array([[1.0, stresses.corr_market_life],
                         [stresses.corr_market_life, 1.0]])
    bscr = _aggregate(np.array([scr_market, scr_life]), top_corr)

    # ---- risk margin (cost of capital on the SCR run-off) ----------------- #
    risk_margin = 0.0
    # The SCR run-off is required by profitability even when the caller elects
    # not to calculate a risk margin.  Previously with_risk_margin=False also
    # returned scr_pattern=None, which profitability silently treated as zero
    # required capital despite a positive BSCR.
    prof = base_res.projection.expected_cashflow_profile()
    driver_pv0 = np.cumsum(
        (prof["guarantee_claims"] + prof["hedge_costs"]
         + prof["expenses"])[::-1])[::-1]
    times = base_res.projection.times
    annual_idx = np.arange(0, len(times), 12)
    df = np.asarray(esg_config.curve.df(times[annual_idx]), dtype=float)
    # Convert the PV(0) tail driver to a value at each run-off date before
    # normalising; otherwise the subsequent RM discounting double-discounts
    # distant cashflows.
    driver_t = driver_pv0[annual_idx] / np.maximum(df, 1e-12)
    if driver_t[0] > 0.0:
        pattern = driver_t / driver_t[0]
    else:
        # A short projection can contain no guarantee claims or insurer costs yet
        # while still carrying market/lapse capital.  Fall back to the
        # expected in-force run-off rather than erasing required capital.
        inforce = np.mean(base_res.projection.inforce[:, annual_idx], axis=0)
        pattern = inforce / max(inforce[0], 1e-12)
    scr_pattern = bscr * pattern
    if with_risk_margin:
        # Cost-of-capital convention: RM = CoC * sum_t SCR(t) * P(0, t+1),
        # i.e. capital held over year (t, t+1] is remunerated at the end of
        # that year (Solvency II Art. 37 style).
        # Market risk is hedgeable and is excluded from this SII-style CoC
        # proxy.  With no operational-risk model available, the life module is
        # the non-hedgeable capital base used here.
        risk_margin = float(stresses.coc_rate * np.sum(
            (scr_life * pattern[:-1]) * df[1:]))

    provenance = assumption_fingerprint(product, policy, esg_config, mortality,
                                        behaviour, expenses, settings, stresses,
                                        with_risk_margin,
                                        base_scen.content_fingerprint)
    return CapitalResult(nav_base=nav_base, scr_by_module=scr,
                         scr_market=scr_market, scr_life=scr_life, bscr=bscr,
                         risk_margin=risk_margin, scr_pattern=scr_pattern,
                         provenance=provenance, stresses=stresses,
                         with_risk_margin=with_risk_margin,
                         scenario_fingerprint=base_scen.content_fingerprint)
