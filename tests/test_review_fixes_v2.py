"""Regression tests for the second review round (v1.0.2).

1. Behaviour inputs cannot create withdrawals in the generic product's Growth
   phase, where every withdrawal is contractually prohibited.
2. The horizon closeout does not purchase a hedge for a year that never runs;
   it pays the contractual post-credit Account Value.
3. The SII interest-equity correlation is direction-dependent (0.5 only when
   the downward interest stress is binding).
4. The generic product rejects the legacy Age Pension+ option.
"""

from dataclasses import replace

import numpy as np
import pytest

from policy_engine import (AgileProduct, BehaviourModel, CapitalStresses,
                          ESGConfig, MortalityTable, PolicySpec,
                          ValuationSettings, YieldCurve, value_contract)
from policy_engine.behavior import (DynamicLapseParams, LapseAssumptions,
                                   WithdrawalBehaviour)
from policy_engine.capital import _aggregate, _market_corr
from policy_engine.esg import simulate
from policy_engine.projection import project

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


class TestGrowthWithdrawalsAreProhibited:
    """Fix 1: legacy Behaviour inputs cannot enable Growth withdrawals."""

    def _project(self, free_util: float, excess_rate: float = 0.02):
        # income starts beyond the scenario horizon -> pure growth phase
        policy = PolicySpec(age=65, income_start_year=8)
        beh = static_behaviour(free_utilisation=free_util,
                               excess_rate=excess_rate)
        scen = simulate("black_scholes", STEEP_CFG, 6.0, 400, seed=11)
        return project(AgileProduct(), policy, scen, beh, MORT)

    def test_no_mva_within_free_allowance(self):
        """An excess-rate input has no effect before Income election."""
        res = self._project(free_util=0.0)
        assert res.pv_by_component()["partial_withdrawals"] == pytest.approx(0.0)
        assert res.pv_by_component()["mva_retained"] == pytest.approx(0.0, abs=1e-9)

    def test_mva_charged_once_allowance_exhausted(self):
        """Even maximum legacy utilisation cannot create a Growth withdrawal."""
        res = self._project(free_util=1.0)
        assert res.pv_by_component()["partial_withdrawals"] == pytest.approx(0.0)
        assert res.pv_by_component()["mva_retained"] == pytest.approx(0.0, abs=1e-9)

    def test_allowance_shared_between_free_and_excess(self):
        """Mixed legacy withdrawal inputs also remain inactive in Growth."""
        res = self._project(free_util=0.5, excess_rate=0.01)
        assert res.pv_by_component()["partial_withdrawals"] == pytest.approx(0.0)
        assert res.pv_by_component()["mva_retained"] == pytest.approx(0.0, abs=1e-9)


class TestNoNewHedgeAtCloseout:
    """Fix 2: the final anniversary starts no new hedge period."""

    def test_final_step_margin_zero_and_identity_holds(self):
        policy = PolicySpec(age=65, income_start_year=1)
        beh = static_behaviour()
        scen = simulate("black_scholes", ESGConfig(curve=YieldCurve.flat(0.04)),
                        3.0, 2000, seed=7)
        res = project(AgileProduct(), policy, scen, beh, MORT)
        # The final elapsed month still earns real money-market backing income,
        # so the backward-compatible crediting-margin aggregate need not be
        # zero.  No new option spread is purchased at the terminal grid point.
        assert np.allclose(res.cashflows["hedge_costs"][:, -1], 0.0)
        np.testing.assert_allclose(
            res.cashflows["crediting_margin"][:, -1],
            res.cashflows["money_market_income"][:, -1]
            + res.cashflows["hedge_gain"][:, -1],
        )
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


class TestAgePensionPlusIsUnavailable:
    """Fix 4: legacy Age Pension+ inputs fail before projection."""

    @pytest.mark.parametrize("pension_age", [0.0, 67.0])
    def test_generic_product_rejects_age_pension_plus(
        self, pension_age: float,
    ) -> None:
        product = AgileProduct()
        product = replace(
            product, aps=replace(product.aps, pension_age=pension_age)
        )
        policy = PolicySpec(age=60, income_start_year=1, age_pension_plus=True)
        with pytest.raises(ValueError, match=r"does not offer Age Pension\+"):
            policy.validate_against(product)
