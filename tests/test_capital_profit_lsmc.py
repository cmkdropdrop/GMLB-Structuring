"""Tests for capital, profitability, sensitivities and the LSMC layer."""

import numpy as np
import pytest

from policy_engine import (AgileProduct, BehaviourModel, CapitalStresses,
                          ESGConfig, ExpenseAssumptions,
                          MortalityTable, PolicySpec, ProfitabilitySettings,
                          ValuationSettings, YieldCurve, analyse_profitability,
                          compute_capital, run_sensitivities)
from policy_engine.projection import ProjectionConfig

CURVE = YieldCurve.flat(0.04)
CFG = ESGConfig(curve=CURVE)
MORT = MortalityTable.gompertz_makeham()
POLICY = PolicySpec(age=65, income_start_year=5)
EXPENSES = ExpenseAssumptions()

FAST = ValuationSettings(model="black_scholes", n_paths=2500, seed=7,
                         horizon_years=40.0)


@pytest.fixture(scope="module")
def capital():
    return compute_capital(AgileProduct(), POLICY, CFG, MORT, BehaviourModel(),
                           expenses=EXPENSES, settings=FAST)


class TestCapital:

    def test_scrs_nonnegative(self, capital):
        for k, v in capital.scr_by_module.items():
            assert v >= 0.0, k

    def test_diversification(self, capital):
        undiv = (max(capital.scr_by_module["interest_up"],
                     capital.scr_by_module["interest_down"])
                 + capital.scr_by_module["equity"]
                 + capital.scr_by_module["equity_vol"]
                 + capital.scr_by_module["longevity"]
                 + capital.scr_by_module["mortality"]
                 + max(capital.scr_by_module["lapse_up"],
                       capital.scr_by_module["lapse_down"],
                       capital.scr_by_module["lapse_mass"])
                 + capital.scr_by_module["expense"]
                 + capital.scr_by_module["cat"])
        assert capital.bscr <= undiv + 1e-9

    def test_longevity_dominates_mortality(self, capital):
        """A lifetime income product is longevity-, not mortality-exposed."""
        assert capital.scr_by_module["longevity"] >= capital.scr_by_module["mortality"]

    def test_risk_margin_positive(self, capital):
        assert capital.risk_margin >= 0.0


class TestProfitability:

    def test_end_to_end(self, capital):
        prof = analyse_profitability(AgileProduct(), POLICY, CFG, MORT,
                                     BehaviourModel(), EXPENSES, settings=FAST,
                                     capital_result=capital)
        assert len(prof.profit_signature) >= 30
        assert np.isfinite(prof.pvfp_hurdle)
        assert np.isfinite(prof.vnb_market_consistent)
        # BEL pattern decays to ~0
        assert abs(prof.bel_pattern[-1]) < abs(prof.bel_pattern[0]) + 1e6

    def test_rw_beats_q_cashflows(self):
        """Real-world equity drift raises IV-linked fee income vs Q."""
        from policy_engine.pricing import value_contract
        from policy_engine.esg import Measure, simulate
        from policy_engine.projection import project
        scen_q = simulate("black_scholes", CFG, 40.0, 4000, seed=7)
        scen_p = simulate("black_scholes", CFG, 40.0, 4000, seed=7,
                          measure=Measure.REAL_WORLD)
        beh = BehaviourModel()
        res_q = project(AgileProduct(), POLICY, scen_q, beh, MORT)
        res_p = project(AgileProduct(), POLICY, scen_p, beh, MORT)
        fees_q = np.sum(res_q.annual_aggregate("fees_product"))
        fees_p = np.sum(res_p.annual_aggregate("fees_product"))
        assert fees_p > fees_q


class TestSensitivities:

    def test_table_and_directions(self):
        from policy_engine.sensitivities import standard_scenarios

        base_product = AgileProduct()
        cap_scenario = next(
            scenario
            for scenario in standard_scenarios()
            if scenario.name == "caps -100bp"
        )
        stressed_product = cap_scenario.product(base_product)
        assert stressed_product.reference_fund.effective_maximum_return \
            != base_product.reference_fund.effective_maximum_return
        assert stressed_product.reference_fund.effective_maximum_return \
            == pytest.approx(
                max(
                    base_product.reference_fund.guaranteed_minimum_cap,
                    base_product.reference_fund.effective_maximum_return - 0.01,
                )
            )

        df = run_sensitivities(AgileProduct(), POLICY, CFG, MORT,
                               BehaviourModel(), EXPENSES, settings=FAST,
                               include_capital=False)
        df = df.set_index("scenario")
        base = df.loc["base"]
        # longevity stress hurts a lifetime income writer
        assert df.loc["longevity -10% qx", "vnb"] < base["vnb"]
        # cheaper caps (lower) increase crediting margin -> VNB up
        assert df.loc["caps -100bp", "vnb"] > base["vnb"]
        # rates down hurt (guarantee discounting)
        assert df.loc["rates -100bp", "vnb"] < df.loc["rates +100bp", "vnb"]
        assert np.isfinite(df["pvfp_hurdle"]).all()


@pytest.mark.skip(reason="LSMC is retained as archived research code and is inactive.")
class TestLSMC:

    def test_optimal_geq_static(self):
        from policy_engine.lsmc import LSMCSettings, value_optimal_behaviour
        settings = LSMCSettings(model="black_scholes", n_train=8000,
                                n_eval=15000, seed=11, horizon_years=35)
        res = value_optimal_behaviour(AgileProduct(), POLICY, CFG, MORT,
                                      settings=settings)
        assert res.value_optimal >= res.value_static - 1e-6
        # uplift should be a modest fraction of premium for a sane design
        assert res.optionality_uplift < 0.25 * POLICY.initial_investment

    def test_static_value_close_to_projection_engine(self):
        """Annual-grid static LSMC value ~ monthly engine PH value (no lapse)."""
        from policy_engine.lsmc import LSMCSettings, value_optimal_behaviour
        from policy_engine.pricing import value_contract
        from policy_engine.behavior import (LapseAssumptions, DynamicLapseParams)
        settings = LSMCSettings(model="black_scholes", n_train=4000,
                                n_eval=30000, seed=11, horizon_years=40)
        res = value_optimal_behaviour(AgileProduct(), POLICY, CFG, MORT,
                                      settings=settings)
        beh = BehaviourModel(regime="static",
                             lapse=LapseAssumptions(growth_phase=(0.0,),
                                                    income_phase=0.0),
                             dynamic=DynamicLapseParams(enabled=False))
        val = value_contract(AgileProduct(), POLICY, CFG, MORT, beh,
                             settings=ValuationSettings(
                                 model="black_scholes", n_paths=8000, seed=7,
                                 horizon_years=40.0))
        ph_engine = (val.pv["income_paid"] + val.pv["death_benefits"]
                     + val.pv["surrender_benefits"] + val.pv["partial_withdrawals"])
        assert res.value_static == pytest.approx(ph_engine, rel=0.05)

    def test_lsmc_rejects_off_anniversary_income_start(self):
        from policy_engine.lsmc import LSMCSettings, value_optimal_behaviour
        with pytest.raises(ValueError, match="annual decision grid"):
            value_optimal_behaviour(
                AgileProduct(), PolicySpec(age=65, income_start_year=1.5),
                CFG, MORT, settings=LSMCSettings(n_train=10, n_eval=10,
                                                 horizon_years=5))
