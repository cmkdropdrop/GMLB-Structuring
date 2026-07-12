"""Regression tests for the second review round (v1.0.2).

1. Scheduled excess withdrawals in the growth phase consume the remaining
   Free Withdrawal Amount first (no MVA on that part, PDS 15.2/15.3).
2. No upfront crediting margin is booked at the horizon closeout; the
   closeout pays the contractual (post-credit) Investment Value.
3. The SII interest-equity correlation is direction-dependent (0.5 only when
   the downward interest stress is binding).
4. The Age Pension+ LIP waiver applies only from the pension age (PDS 16.5).
"""

from dataclasses import replace

import numpy as np
import pytest

from agile_engine import (AgileProduct, BehaviourModel, CapitalStresses,
                          ESGConfig, MortalityTable, PolicySpec,
                          ValuationSettings, YieldCurve, value_contract)
from agile_engine.behavior import (DynamicLapseParams, LapseAssumptions,
                                   WithdrawalBehaviour)
from agile_engine.capital import _aggregate, _market_corr
from agile_engine.esg import simulate
from agile_engine.projection import project

MORT = MortalityTable.gompertz_makeham()
#: steep curve => forwards above spot => the rate-based MVA factor is positive
STEEP_CURVE = YieldCurve.from_rates((1, 2, 5, 10, 20, 30),
                                    (0.020, 0.025, 0.035, 0.045, 0.050, 0.050))
STEEP_CFG = ESGConfig(curve=STEEP_CURVE)


def static_behaviour(**wd) -> BehaviourModel:
    return BehaviourModel(regime="static",
                          lapse=LapseAssumptions(growth_phase=(0.0,),
                                                 income_phase=0.0),
                          dynamic=DynamicLapseParams(enabled=False),
                          withdrawals=WithdrawalBehaviour(**wd))


class TestExcessWithdrawalsUseFreeAllowanceFirst:
    """Fix 1: within the 5% allowance no MVA is charged (growth phase)."""

    def _project(self, free_util: float, excess_rate: float = 0.02):
        # income starts beyond the scenario horizon -> pure growth phase
        policy = PolicySpec(age=65, income_start_year=8)
        beh = static_behaviour(free_utilisation=free_util,
                               excess_rate=excess_rate)
        scen = simulate("black_scholes", STEEP_CFG, 6.0, 400, seed=11)
        return project(AgileProduct(), policy, scen, beh, MORT)

    def test_no_mva_within_free_allowance(self):
        """2% p.a. of IV stays within the unused 5% allowance -> no MVA."""
        res = self._project(free_util=0.0)
        assert res.pv_by_component()["partial_withdrawals"] > 0.0
        assert res.pv_by_component()["mva_retained"] == pytest.approx(0.0, abs=1e-9)

    def test_mva_charged_once_allowance_exhausted(self):
        """With the allowance fully drawn as free withdrawals, the excess
        withdrawal is a true Excess Withdrawal and attracts MVA."""
        res = self._project(free_util=1.0)
        assert res.pv_by_component()["mva_retained"] > 0.0

    def test_allowance_shared_between_free_and_excess(self):
        """Free 50% utilisation + 1% of IV excess: the excess first fills the
        remaining half of the allowance (2.5% of P0), so still no MVA
        (1% of IV < 2.5% of P0 for any IV reachable under the caps)."""
        res = self._project(free_util=0.5, excess_rate=0.01)
        assert res.pv_by_component()["partial_withdrawals"] > 0.0
        assert res.pv_by_component()["mva_retained"] == pytest.approx(0.0, abs=1e-9)


class TestNoMarginAtCloseout:
    """Fix 2: the final anniversary books no margin for a year that never runs."""

    def test_final_step_margin_zero_and_identity_holds(self):
        policy = PolicySpec(age=65, income_start_year=1)
        beh = static_behaviour()
        scen = simulate("black_scholes", ESGConfig(curve=YieldCurve.flat(0.04)),
                        3.0, 2000, seed=7)
        res = project(AgileProduct(), policy, scen, beh, MORT)
        margin_final = res.cashflows["crediting_margin"][:, -1]
        assert np.allclose(margin_final, 0.0)
        # closeout pays the contractual post-credit IV; no leakage
        assert abs(res.identity_gap()) < 0.006


class TestMarketCorrDirection:
    """Fix 3: SII interest-equity correlation by binding direction."""

    def test_matrix_selection(self):
        st = CapitalStresses()
        m_dn = _market_corr(st, ir_down_binding=True)
        m_up = _market_corr(st, ir_down_binding=False)
        assert m_dn[0, 1] == pytest.approx(0.5)
        assert m_up[0, 1] == pytest.approx(0.0)

    def test_aggregation_differs_when_up_binding(self):
        st = CapitalStresses()
        vec = np.array([100.0, 50.0, 10.0])
        agg_dn = _aggregate(vec, _market_corr(st, True))
        agg_up = _aggregate(vec, _market_corr(st, False))
        assert agg_up < agg_dn


class TestApsLipWaiverPensionAge:
    """Fix 4: LIP waived only from the later of income start and pension age."""

    def _fees_lip(self, pension_age: float) -> np.ndarray:
        product = AgileProduct()
        product = replace(product, aps=replace(product.aps,
                                               pension_age=pension_age))
        policy = PolicySpec(age=60, income_start_year=1, age_pension_plus=True)
        beh = static_behaviour()
        scen = simulate("black_scholes", ESGConfig(curve=YieldCurve.flat(0.04)),
                        15.0, 400, seed=3)
        res = project(product, policy, scen, beh, MORT)
        return res.annual_aggregate("fees_lip")

    def test_lip_charged_before_pension_age(self):
        lip = self._fees_lip(pension_age=67.0)
        # income phase from age 61; LIP must still be charged at ages 61-66
        assert lip[3] > 0.0          # policy year 3 = ages 62-63
        # ... and waived once the pension age is reached (ages >= 67)
        assert lip[10] == pytest.approx(0.0, abs=1e-9)   # ages 69-70

    def test_immediate_waiver_when_pension_age_met(self):
        lip_67 = self._fees_lip(pension_age=67.0)
        lip_0 = self._fees_lip(pension_age=0.0)   # old behaviour
        # waiving earlier can only reduce cumulative LIP income
        assert np.sum(lip_0) < np.sum(lip_67)
        assert lip_0[3] == pytest.approx(0.0, abs=1e-9)
