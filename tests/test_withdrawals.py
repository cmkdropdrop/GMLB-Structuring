"""Tests for the flexible-withdrawal features:

* monthly (intra-year, DVA-priced) scheduled withdrawals,
* the contractual prohibition of Growth-phase withdrawals,
* dynamic (moneyness-driven) withdrawal utilisation,
* partial-withdrawal actions in the LSMC optimal-behaviour layer.
"""

from dataclasses import replace

import numpy as np
import pytest

from policy_engine import (AgileProduct, BehaviourModel, ESGConfig, FeeSpec,
                          IncomeRateTable, Index, Measure, MortalityTable,
                          MVASpec, PolicySpec, ProjectionConfig, ScenarioSet,
                          ValuationSettings, YieldCurve, value_contract)
from policy_engine.behavior import (DynamicLapseParams, DynamicWithdrawalParams,
                                   FractionalLogitFunction, LapseAssumptions,
                                   WithdrawalBehaviour)
from policy_engine.esg import simulate
from policy_engine.projection import project

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

    def test_growth_withdrawals_are_contractually_blocked(self):
        """Generic-product Growth withdrawals remain zero despite inputs."""
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
        for y in (1, 2, 3, 4, 5):
            assert annual[y] == 0.0

    def test_annual_vs_monthly_similar_value(self):
        """Scheduling frequency changes timing, not the order of magnitude.

        Annual-mode withdrawals occur at the post-payment action boundary;
        monthly mode spreads the same annualised assumption over the year.
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
            regime="dynamic",
            withdrawals=WithdrawalBehaviour(free_utilisation=0.5,
                                            excess_rate=0.02),
            dynamic_withdrawals=DynamicWithdrawalParams(enabled=True))

    def test_less_valuable_guarantee_increases_excess_withdrawal_rate(self):
        """The signed proxy discourages guarantee-destroying ITM withdrawals."""
        params = self._behaviour().dynamic_withdrawals
        out_of_money = params.excess_rate(0.02, -0.40, 100_000.0)
        at_money = params.excess_rate(0.02, 0.0, 100_000.0)
        in_the_money = params.excess_rate(0.02, 0.40, 100_000.0)
        assert out_of_money > at_money > in_the_money

    def test_annual_rate_uses_post_income_payment_state(self, monkeypatch):
        """Annual excess utilisation sees AV after that day's Income."""
        horizon_years = 2.5
        n_steps = int(horizon_years * 12)
        times = np.arange(n_steps + 1, dtype=float) / 12.0
        levels = np.ones((1, n_steps + 1))
        scenarios = ScenarioSet(
            config=ESGConfig(curve=YieldCurve.flat(0.0)),
            measure=Measure.RISK_NEUTRAL,
            dt=1.0 / 12.0,
            times=times,
            index_levels={
                Index.AUS_EQUITY: levels.copy(),
                Index.GLOBAL_EQUITY: levels.copy(),
            },
            short_rate=np.zeros_like(levels),
            discount=np.ones_like(levels),
            model_name="black_scholes",
            seed=1,
        )
        product = AgileProduct(
            fees=FeeSpec(product_fee=0.0, lifetime_income_premium=0.0),
            mva=MVASpec(),
            income_rates=replace(IncomeRateTable(), base_rate_shift=-0.04),
        )
        policy = PolicySpec(age=65, income_start_year=1)
        mortality = MortalityTable.gompertz_makeham().stressed(0.0)
        excess_function = FractionalLogitFunction(
            beta_moneyness=-3.0,
            beta_log_premium=0.0,
            beta_interaction=0.0,
            beta_mva=0.0,
            moneyness_transform="signed",
        )
        behaviour = BehaviourModel(
            regime="dynamic",
            lapse=LapseAssumptions(
                growth_phase=(0.0,), income_phase=0.0
            ),
            dynamic=DynamicLapseParams(enabled=False),
            withdrawals=WithdrawalBehaviour(
                excess_rate=0.20,
                frequency="annual",
            ),
            dynamic_withdrawals=DynamicWithdrawalParams(
                enabled=True,
                excess=excess_function,
            ),
        )

        observed_moneyness = []
        original = DynamicWithdrawalParams.excess_rate

        def recording_excess_rate(
            self, base, log_moneyness, premium, mva_signal=0.0
        ):
            observed_moneyness.append(
                np.asarray(log_moneyness, dtype=float).copy()
            )
            return original(
                self, base, log_moneyness, premium, mva_signal
            )

        monkeypatch.setattr(
            DynamicWithdrawalParams,
            "excess_rate",
            recording_excess_rate,
        )
        result = project(
            product,
            policy,
            scenarios,
            behaviour,
            mortality,
            config=ProjectionConfig(dva_enabled=False, record_paths=True),
        )

        step = 24
        assert result.iv_paths is not None
        assert result.income_paths is not None
        gross_withdrawal = float(
            result.cashflows["partial_withdrawals"][0, step]
        )
        income_payment = float(result.cashflows["income_paid"][0, step])
        post_payment_av = float(result.iv_paths[0, step]) + gross_withdrawal
        pre_payment_av = post_payment_av + income_payment

        t = float(times[step])
        annuity_factor = np.asarray(
            mortality.annuity_factor(
                policy.age + t,
                policy.sex,
                scenarios.forward_zero_cc(step, 10.0),
                years_from_base=(
                    policy.commencement_year - mortality.base_year + t
                ),
                projection_duration_start=t,
            ),
            dtype=float,
        )
        guarantee_pv = float(
            result.income_paths[0, step - 1] * annuity_factor[0]
        )
        post_payment_mny = float(np.log(guarantee_pv / post_payment_av))
        pre_payment_mny = float(np.log(guarantee_pv / pre_payment_av))
        post_payment_rate = float(original(
            behaviour.dynamic_withdrawals,
            behaviour.withdrawals.excess_rate,
            post_payment_mny,
            policy.initial_investment,
            0.0,
        ))
        pre_payment_rate = float(original(
            behaviour.dynamic_withdrawals,
            behaviour.withdrawals.excess_rate,
            pre_payment_mny,
            policy.initial_investment,
            0.0,
        ))
        actual_rate = gross_withdrawal / post_payment_av

        assert any(
            np.isclose(
                float(moneyness[0]),
                post_payment_mny,
                rtol=0.0,
                atol=1.0e-12,
            )
            for moneyness in observed_moneyness
        )
        assert actual_rate == pytest.approx(post_payment_rate, abs=1.0e-12)
        assert abs(actual_rate - pre_payment_rate) > 1.0e-4

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
        from policy_engine.lsmc import LSMCSettings, value_optimal_behaviour
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
        from policy_engine.lsmc import LSMCSettings, value_optimal_behaviour
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
        from policy_engine.lsmc import LSMCSettings, value_optimal_behaviour
        base = LSMCSettings(n_train=6000, n_eval=12000, seed=11,
                            horizon_years=35)
        res_nowd = value_optimal_behaviour(
            AgileProduct(), POLICY, CFG, MORT,
            settings=replace(base, include_withdrawals=False))
        res_wd = value_optimal_behaviour(AgileProduct(), POLICY, CFG, MORT,
                                         settings=base)
        extra = res_wd.value_optimal - res_nowd.value_optimal
        assert extra < 0.02 * POLICY.initial_investment
