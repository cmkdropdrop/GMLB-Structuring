"""Sensitivity analysis of value and profitability to typical risk factors.

Runs bump-and-revalue scenarios over the joint (risk-neutral valuation,
real-world profitability) stack with common random numbers, covering the risk
drivers that dominate an FIA+GLWB book:

* interest rates (level +/-100bp),
* equity volatility (+25% relative: cap-hedge budget),
* cap repricing (-100bp on all Maximum Returns),
* longevity (-10% mortality) and mortality (+10%),
* base lapses (+/-50%) and dynamic-response strength (+/-25%),
* income take-up baseline hazards (+/-25%),
* withdrawal utilisation (full free-amount usage; +2% excess p.a.),
* maintenance expenses (+10%),
* equity risk premium (-100bp, real-world only).

Output: one row per scenario with VNB, guarantee value, PVFP@hurdle, NBM and
deltas vs. base.

Note: an instantaneous equity-level shock is not part of this battery because
it requires transforming a simulated ScenarioSet rather than the inputs; it is
covered by ``pricing.greeks`` (equity delta) and the equity module of
``capital.compute_capital`` (-39% type-1 shock).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from .behavior import BehaviourModel
from .capital import CapitalStresses
from .esg import ESGConfig
from .mortality import MortalityTable
from .pricing import ValuationSettings, value_contract
from .product import AgileProduct, ExpenseAssumptions, PolicySpec
from .profitability import (ProfitabilitySettings, ProfitabilityResult,
                            analyse_profitability)


@dataclass
class Scenario:
    name: str
    product: Callable[[AgileProduct], AgileProduct] = lambda p: p
    policy: Callable[[PolicySpec], PolicySpec] = lambda p: p
    esg: Callable[[ESGConfig], ESGConfig] = lambda c: c
    mortality: Callable[[MortalityTable], MortalityTable] = lambda m: m
    behaviour: Callable[[BehaviourModel], BehaviourModel] = lambda b: b
    expenses: Callable[[ExpenseAssumptions], ExpenseAssumptions] = lambda e: e


def standard_scenarios() -> List[Scenario]:
    def shift_reference_fund_cap(
        product: AgileProduct,
        shift: float,
    ) -> AgileProduct:
        reference_fund = product.reference_fund
        stressed_cap = max(
            reference_fund.guaranteed_minimum_cap,
            reference_fund.effective_maximum_return + shift,
        )
        return replace(
            product,
            reference_fund=replace(
                reference_fund,
                scenario_maximum_return=stressed_cap,
            ),
        )

    def scale_lapse_response(b: BehaviourModel, factor: float) -> BehaviourModel:
        def scaled(function):
            return replace(
                function,
                beta_moneyness=function.beta_moneyness * factor,
                beta_log_premium=function.beta_log_premium * factor,
                beta_interaction=function.beta_interaction * factor,
            )
        dynamic = replace(
            b.dynamic,
            growth=scaled(b.dynamic.growth),
            income=scaled(b.dynamic.income),
        )
        return replace(b, dynamic=dynamic)

    def erp_down(c: ESGConfig) -> ESGConfig:
        eq = {k: replace(v, risk_premium=v.risk_premium - 0.01)
              for k, v in c.equity.items()}
        return replace(c, equity=eq)

    return [
        Scenario("base"),
        Scenario("rates +100bp", esg=lambda c: c.with_curve(c.curve.shifted(0.01))),
        Scenario("rates -100bp", esg=lambda c: c.with_curve(c.curve.shifted(-0.01))),
        Scenario("equity vol +25%", esg=lambda c: c.bump_equity_vol(0.25)),
        Scenario(
            "caps -100bp",
            product=lambda p: shift_reference_fund_cap(p, -0.01),
        ),
        Scenario("longevity -10% qx", mortality=lambda m: m.stressed(0.90)),
        Scenario("mortality +10% qx", mortality=lambda m: m.stressed(1.10)),
        Scenario("lapse +50%", behaviour=lambda b: b.scaled_lapses(1.5)),
        Scenario("lapse -50%", behaviour=lambda b: b.scaled_lapses(0.5)),
        Scenario("lapse response +25%",
                 behaviour=lambda b: scale_lapse_response(b, 1.25)),
        Scenario("lapse response -25%",
                 behaviour=lambda b: scale_lapse_response(b, 0.75)),
        Scenario("take-up +25%", behaviour=lambda b: b.scaled_take_up(1.25)),
        Scenario("take-up -25%", behaviour=lambda b: b.scaled_take_up(0.75)),
        Scenario("free withdrawals 100% used", behaviour=lambda b: replace(
            b, withdrawals=replace(b.withdrawals, free_utilisation=1.0))),
        Scenario("excess withdrawals 2% p.a.", behaviour=lambda b: replace(
            b, withdrawals=replace(b.withdrawals, free_utilisation=1.0,
                                   excess_rate=0.02))),
        Scenario("expenses +10%", expenses=lambda e: replace(
            e, maintenance_per_policy=e.maintenance_per_policy * 1.1,
            maintenance_pct_of_iv=e.maintenance_pct_of_iv * 1.1)),
        Scenario("ERP -100bp (RW only)", esg=erp_down),
    ]


def run_sensitivities(product: AgileProduct, policy: PolicySpec,
                      esg_config: ESGConfig, mortality: MortalityTable,
                      behaviour: BehaviourModel, expenses: ExpenseAssumptions,
                      settings: ValuationSettings = ValuationSettings(),
                      prof_settings: ProfitabilitySettings = ProfitabilitySettings(),
                      scenarios: Optional[List[Scenario]] = None,
                      include_capital: bool = False,
                      capital_stresses: CapitalStresses = CapitalStresses()
                      ) -> pd.DataFrame:
    """Run the scenario battery; returns a tidy DataFrame.

    ``include_capital=False`` skips SCR in the profitability run for speed
    and therefore reports gross VNB/PVFP, IRR and payback before capital and
    risk-margin effects.  The risk-neutral guarantee-value columns themselves
    remain unaffected by this reporting switch.
    """
    scenarios = scenarios or standard_scenarios()
    ps = replace(prof_settings, include_capital=include_capital)

    rows = []
    for sc in scenarios:
        prod = sc.product(product)
        pol = sc.policy(policy)
        cfg = sc.esg(esg_config)
        mort = sc.mortality(mortality)
        beh = sc.behaviour(behaviour)
        exp = sc.expenses(expenses)

        val = value_contract(prod, pol, cfg, mort, beh, expenses=exp,
                             settings=settings)
        prof = analyse_profitability(prod, pol, cfg, mort, beh, exp,
                                     settings=settings, prof_settings=ps,
                                     compute_capital_if_missing=include_capital,
                                     valuation_result=val,
                                     capital_stresses=capital_stresses)

        row = {
            "scenario": sc.name,
            "vnb": prof.vnb_market_consistent,
            "guarantee_value": val.guarantee_value,
            "pv_guarantee_claims": val.pv["guarantee_claims"],
            "pv_fees_lip": val.pv["fees_lip"],
            "bel_nonunit": val.bel_nonunit,
            "pvfp_hurdle": prof.pvfp_hurdle,
            "nbm_pct": 100.0 * prof.new_business_margin,
            "pvfp_margin_pct": 100.0 * prof.pvfp_margin,
            "irr_pct": float("nan") if prof.irr is None else 100.0 * prof.irr,
        }
        rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    base_idx = out.index[out["scenario"] == "base"]
    base = out.loc[base_idx[0] if len(base_idx) else out.index[0]]
    out["d_vnb"] = out["vnb"] - base["vnb"]
    out["d_pvfp"] = out["pvfp_hurdle"] - base["pvfp_hurdle"]
    out["d_nbm_pct"] = out["nbm_pct"] - base["nbm_pct"]
    return out
