"""Tests for the flexible-withdrawal features:

* monthly (intra-year, DVA-priced) scheduled withdrawals,
* the 5% free-allowance cap per anniversary year,
* dynamic (moneyness-driven) withdrawal utilisation,
* partial-withdrawal actions in the LSMC optimal-behaviour layer.
"""

from dataclasses import replace

import numpy as np
import pytest

from agile_engine import (AgileProduct, BehaviourModel, ESGConfig,
                          IncomeRateTable, MortalityTable,
                          MVASpec, PolicySpec, ValuationSettings, YieldCurve,
                          value_contract)
from agile_engine.behavior import (DynamicLapseParams, DynamicWithdrawalParams,
                                   LapseAssumptions, WithdrawalBehaviour)
from agile_engine.esg import simulate
from agile_engine.projection import project

CURVE = YieldCurve.flat(0.04)
CFG = ESGConfig(curve=CURVE)
MORT = MortalityTable.gompertz_makeham()
POLICY = PolicySpec(age=65, income_start_year=5)


def settings(model="black_scholes", n_paths=3000):
    return ValuationSettings(model=model, n_paths=n_paths, seed=7,
                             horizon_years=40.0)


class TestMonthlyWithdrawals:

    @pytest.mark.parametrize("model", ["black_scholes", "hull_white_bs"])
    def test_identity_monthly_schedule(self, model):
        beh = BehaviourModel(withdrawals=WithdrawalBehaviour(
            free_utilisation=1.0, excess_rate=0.02, frequency="monthly"))
        res = value_contract(AgileProduct(), POLICY, CFG, MORT, beh,
                             settings=settings(model))
        assert abs(res.identity_gap) < 0.008, res.identity_gap
        assert res.pv["partial_withdrawals"] > 0.0

    def test_free_allowance_capped_at_5pct_per_year(self):
        """Monthly free withdrawals must sum to exactly the 5% allowance."""
        m0 = MORT.stressed(0.0)  # no deaths
        beh = BehaviourModel(
            regime="static",
            lapse=LapseAssumptions(growth_phase=(0.0,), income_phase=0.0),
            dynamic=DynamicLapseParams(enabled=False),
            withdrawals=WithdrawalBehaviour(free_utilisation=1.0,
                                            frequency="monthly"))
        scen = simulate("black_scholes", CFG, 8.0, 400, seed=3)
        res = project(AgileProduct(), replace(POLICY, income_start_year=7),
                      scen, beh, m0)
        annual = res.annual_aggregate("partial_withdrawals")
        allow = 0.05 * POLICY.initial_investment
        for y in (1, 2, 3, 4, 5):
            assert annual[y] == pytest.approx(allow, rel=1e-6)

    def test_annual_vs_monthly_similar_value(self):
        """Scheduling frequency changes timing, not the order of magnitude.

        Note: annual-mode withdrawals occur at anniversaries *after* a
        same-day income election, so the election year itself is skipped;
        with a long growth phase this boundary effect is small.
        """
        pol = replace(POLICY, income_start_year=20)
        beh_a = BehaviourModel(withdrawals=WithdrawalBehaviour(
            free_utilisation=1.0, frequency="annual"))
        beh_m = BehaviourModel(withdrawals=WithdrawalBehaviour(
            free_utilisation=1.0, frequency="monthly"))
        st = settings()
        pv_a = value_contract(AgileProduct(), pol, CFG, MORT, beh_a,
                              settings=st).pv["partial_withdrawals"]
        pv_m = value_contract(AgileProduct(), pol, CFG, MORT, beh_m,
                              settings=st).pv["partial_withdrawals"]
        assert pv_m == pytest.approx(pv_a, rel=0.10)


class TestDynamicWithdrawalUtilisation:

    def _behaviour(self):
        return BehaviourModel(
            withdrawals=WithdrawalBehaviour(free_utilisation=0.5,
                                            excess_rate=0.02),
            dynamic_withdrawals=DynamicWithdrawalParams(enabled=True))

    def test_itm_guarantee_increases_expected_withdrawals(self):
        """The positive ITM proxy raises expected utilisation."""
        rich = AgileProduct(income_rates=replace(IncomeRateTable(),
                                                 base_rate_shift=0.02))
        poor = AgileProduct(income_rates=replace(IncomeRateTable(),
                                                 base_rate_shift=-0.02))
        st = settings()
        beh = self._behaviour()
        pv_rich = value_contract(rich, POLICY, CFG, MORT, beh,
                                 settings=st).pv["partial_withdrawals"]
        pv_poor = value_contract(poor, POLICY, CFG, MORT, beh,
                                 settings=st).pv["partial_withdrawals"]
        assert pv_rich > pv_poor

    def test_identity_with_dynamic_utilisation(self):
        res = value_contract(AgileProduct(), POLICY, CFG, MORT,
                             self._behaviour(), settings=settings())
        assert abs(res.identity_gap) < 0.008

    def test_static_regime_disables_dynamic_withdrawals(self):
        beh = replace(self._behaviour(), regime="static",
                      dynamic=DynamicLapseParams(enabled=False))
        assert not beh.use_dynamic_withdrawals

    def test_multiplier_direction(self):
        p = DynamicWithdrawalParams(enabled=True)
        deep_itm = p.multiplier(np.array([2.0]))
        deep_otm = p.multiplier(np.array([0.5]))
        assert deep_itm > 1.0
        np.testing.assert_allclose(deep_otm, np.array([1.0]))
        assert p.mva_multiplier(np.array([0.10]))[0] < 1.0
        assert p.mva_multiplier(np.array([0.0]))[0] == 1.0


@pytest.mark.skip(reason="LSMC is retained as archived research code and is inactive.")
class TestLSMCWithdrawals:

    def test_action_set_monotonicity(self):
        """Larger admissible action set cannot reduce the optimal value
        (rationality check, cf. Shevchenko/Luo 2016 dynamic >= static)."""
        from agile_engine.lsmc import LSMCSettings, value_optimal_behaviour
        base = LSMCSettings(n_train=6000, n_eval=12000, seed=11,
                            horizon_years=35)
        res_nowd = value_optimal_behaviour(
            AgileProduct(), POLICY, CFG, MORT,
            settings=replace(base, include_withdrawals=False))
        res_wd = value_optimal_behaviour(AgileProduct(), POLICY, CFG, MORT,
                                         settings=base)
        # same seeds/paths; regression noise tolerance 0.5% of premium
        assert res_wd.value_optimal >= res_nowd.value_optimal - 500
        assert res_wd.value_optimal >= res_wd.value_static - 1e-6

    def test_regression_fallback_has_matching_diagnostics(self):
        """If the learned policy loses out of sample, the reported static
        fallback must not retain actions from the rejected strategy."""
        from agile_engine.lsmc import LSMCSettings, value_optimal_behaviour
        curve = YieldCurve.from_rates((1, 2, 5, 10, 20, 30),
                                      (0.038, 0.039, 0.041, 0.043, 0.044, 0.044))
        cfg = ESGConfig(curve=curve)
        product = AgileProduct(mva=MVASpec(cost_loading=0.50))
        res = value_optimal_behaviour(
            product, POLICY, cfg, MORT,
            settings=LSMCSettings(n_train=10000, n_eval=20000, seed=4711,
                                  horizon_years=38))
        if res.optionality_uplift == pytest.approx(0.0):
            assert np.all(res.withdrawal_rate_by_year == 0.0)
            assert np.all(res.surrender_rate_by_year == 0.0)

    def test_uplift_from_withdrawals_is_small(self):
        """Design neutrality: DVA pricing + proportional income reduction
        (PDS 15.3) mean partial withdrawals add little optionality value."""
        from agile_engine.lsmc import LSMCSettings, value_optimal_behaviour
        base = LSMCSettings(n_train=6000, n_eval=12000, seed=11,
                            horizon_years=35)
        res_nowd = value_optimal_behaviour(
            AgileProduct(), POLICY, CFG, MORT,
            settings=replace(base, include_withdrawals=False))
        res_wd = value_optimal_behaviour(AgileProduct(), POLICY, CFG, MORT,
                                         settings=base)
        extra = res_wd.value_optimal - res_nowd.value_optimal
        assert extra < 0.02 * POLICY.initial_investment
