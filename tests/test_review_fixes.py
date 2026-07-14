"""Regression tests for the review fixes.

1. Income-phase excess withdrawals remain non-negative and the MVA is bounded
   by the gross account-value deduction.
2. The mortality catastrophe capital stress is an additive shock in the first
   projection year only (previously it shifted the whole table permanently).
3. The dynamic income-phase lapse multiplier is evaluated at anniversaries and
   held for the whole policy year (previously it only acted in the anniversary
   month, diluting the behavioural effect to ~1/12).
4. ``ValuationSettings.horizon_years=None`` resolves to the terminal age of
   the longer-lived covered life, so young-entry/spouse tails are not truncated.
"""

from dataclasses import replace

import numpy as np
import pytest

from policy_engine import (AgileProduct, BehaviourModel, ESGConfig,
                          IncomeRateTable, MortalityTable, PolicySpec,
                          ProjectionConfig, ValuationSettings, YieldCurve,
                          resolve_horizon)
from policy_engine.behavior import (DynamicLapseParams, LapseAssumptions,
                                   WithdrawalBehaviour)
from policy_engine.esg import simulate
from policy_engine.projection import project

MORT = MortalityTable.gompertz_makeham()
STEEP_CURVE = YieldCurve.from_rates((1, 2, 5, 10, 20, 30),
                                    (0.020, 0.025, 0.035, 0.045, 0.050, 0.050))


def static_behaviour(**wd) -> BehaviourModel:
    return BehaviourModel(regime="static",
                          lapse=LapseAssumptions(growth_phase=(0.0,),
                                                 income_phase=0.0),
                          dynamic=DynamicLapseParams(enabled=False),
                          withdrawals=WithdrawalBehaviour(**wd))


class TestIncomeWithdrawalMvaBounds:
    """Fix 1: generic-product Income withdrawals have a bounded MVA."""

    def test_no_negative_partial_withdrawals(self):
        cfg = ESGConfig(curve=STEEP_CURVE)   # forwards > spot => MVA bites
        policy = PolicySpec(age=65, income_start_year=1)
        beh = static_behaviour(excess_rate=0.30)
        scen = simulate("black_scholes", cfg, 30.0, 400, seed=1)
        res = project(AgileProduct(), policy, scen, beh, MORT)
        pw = res.cashflows["partial_withdrawals"]
        assert pw.min() >= -1e-9, pw.min()

    def test_mva_never_exceeds_gross_deduction(self):
        cfg = ESGConfig(curve=STEEP_CURVE)
        policy = PolicySpec(age=65, income_start_year=1)
        beh = static_behaviour(excess_rate=0.30)
        scen = simulate("black_scholes", cfg, 30.0, 400, seed=1)
        res = project(AgileProduct(), policy, scen, beh, MORT)
        gross = (res.cashflows["partial_withdrawals"]
                 + res.cashflows["mva_retained"])
        assert res.cashflows["mva_retained"].min() >= -1e-9
        assert np.all(res.cashflows["mva_retained"] <= gross + 1e-9)


class TestCatShockFirstYearOnly:
    """Fix 2: cat stress = additive q in the first projection year only."""

    def test_q_shocked_only_in_first_year(self):
        cat = replace(MORT, q_add_first_year=0.0015)
        base_y0 = MORT.q(70, "M", years_from_base=0.5)
        cat_y0 = cat.q(70, "M", years_from_base=0.5,
                       projection_duration=0.5)
        assert cat_y0 == pytest.approx(base_y0 + 0.0015, abs=1e-12)
        for yfb in (1.0, 1.5, 10.0):
            assert cat.q(70 + yfb, "M", years_from_base=yfb,
                         projection_duration=yfb) == pytest.approx(
                MORT.q(70 + yfb, "M", years_from_base=yfb), abs=1e-15)

    def test_survival_effect_bounded(self):
        """A one-year +0.15% shock moves 20y survival by roughly 0.15%."""
        cat = replace(MORT, q_add_first_year=0.0015)
        s_base = MORT.survival_curve(65, "M", 20)
        s_cat = cat.survival_curve(65, "M", 20)
        gap = s_base[-1] - s_cat[-1]
        assert 0.0 < gap < 0.0016


class TestDynamicIncomeLapseHeldWithinYear:
    """Fix 3: the ITM dampening acts in every month of the policy year."""

    def test_itm_guarantee_suppresses_income_lapses(self):
        rich = AgileProduct(income_rates=replace(IncomeRateTable(),
                                                 base_rate_shift=0.06))
        policy = PolicySpec(age=65, income_start_year=1)
        lapse = LapseAssumptions(growth_phase=(0.0,), income_phase=0.03)
        beh_dyn = BehaviourModel(regime="dynamic", lapse=lapse,
                                 dynamic=DynamicLapseParams(enabled=True))
        beh_stat = BehaviourModel(regime="static", lapse=lapse,
                                  dynamic=DynamicLapseParams(enabled=False))
        cfg = ESGConfig(curve=YieldCurve.flat(0.04))
        scen = simulate("black_scholes", cfg, 40.0, 2000, seed=5)
        res_dyn = project(rich, policy, scen, beh_dyn, MORT)
        res_stat = project(rich, policy, scen, beh_stat, MORT)
        pv_dyn = res_dyn.pv_by_component()["surrender_benefits"]
        pv_stat = res_stat.pv_by_component()["surrender_benefits"]
        assert pv_stat > 0.0
        # deep ITM -> multiplier at/near its floor (0.2) in *every* month;
        # before the fix only 1 of 12 months was dampened (ratio ~0.93).
        assert pv_dyn < 0.5 * pv_stat


class TestHorizonResolution:
    """Fix 4: default horizon covers the guarantee tail for any entry age."""

    def test_explicit_horizon_unchanged(self):
        s = ValuationSettings(horizon_years=45.0)
        assert resolve_horizon(s, PolicySpec(age=50)) == 45.0

    def test_auto_horizon_reaches_terminal_table_age(self):
        s = ValuationSettings()   # horizon_years=None
        assert resolve_horizon(s, PolicySpec(age=50)) == 65.0
        assert resolve_horizon(s, PolicySpec(age=65)) == 50.0
        s105 = ValuationSettings(projection=ProjectionConfig(max_age=105.0))
        assert resolve_horizon(s105, PolicySpec(age=65)) == 40.0
