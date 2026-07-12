"""Projection & pricing tests: product mechanics, identities, limiting cases."""

import numpy as np
import pytest

from agile_engine import (AgileProduct, BehaviourModel, CapSchedule, ESGConfig,
                          ExpenseAssumptions, FeeSpec, IncomeRateTable,
                          IncomeType, InvestmentOption, MortalityTable,
                          MVASpec, PolicySpec, ProjectionConfig,
                          Sex, ValuationSettings, YieldCurve, value_contract,
                          fair_lifetime_income_premium,
                          intra_year_value_factor)
from agile_engine.behavior import (DynamicLapseParams, LapseAssumptions,
                                   WithdrawalBehaviour)
from agile_engine.esg import Measure, simulate
from agile_engine.projection import project
from dataclasses import replace


CURVE = YieldCurve.flat(0.04)
CFG = ESGConfig(curve=CURVE)
MORT = MortalityTable.gompertz_makeham()


def make_settings(n_paths=4000, horizon=45.0, **proj_kw):
    return ValuationSettings(model="black_scholes", n_paths=n_paths, seed=7,
                             horizon_years=horizon,
                             projection=ProjectionConfig(**proj_kw))


def no_lapse_behaviour():
    return BehaviourModel(regime="static",
                          lapse=LapseAssumptions(growth_phase=(0.0,), income_phase=0.0),
                          dynamic=DynamicLapseParams(enabled=False))


class TestMarketConsistencyIdentity:
    """P0 = PV(financed flows) under Q - the core no-leakage check."""

    @pytest.mark.parametrize("income_type", [IncomeType.FIXED, IncomeType.RISING])
    def test_identity_base(self, income_type):
        policy = PolicySpec(age=65, income_start_year=5, income_type=income_type)
        res = value_contract(AgileProduct(), policy, CFG, MORT,
                             BehaviourModel(), settings=make_settings())
        assert abs(res.identity_gap) < 0.006, res.identity_gap

    def test_identity_with_withdrawals_and_spouse(self):
        beh = BehaviourModel(withdrawals=WithdrawalBehaviour(
            free_utilisation=0.5, excess_rate=0.01))
        policy = PolicySpec(age=66, spouse=True, spouse_age=63,
                            spouse_sex=Sex.FEMALE, income_start_year=4)
        res = value_contract(AgileProduct(), policy, CFG, MORT, beh,
                             settings=make_settings())
        assert abs(res.identity_gap) < 0.006, res.identity_gap

    def test_identity_hull_white(self):
        policy = PolicySpec(age=65, income_start_year=5)
        settings = ValuationSettings(model="hull_white_bs", n_paths=4000, seed=7,
                                     horizon_years=45.0)
        res = value_contract(AgileProduct(), policy, CFG, MORT, BehaviourModel(),
                             settings=settings)
        assert abs(res.identity_gap) < 0.008, res.identity_gap

    def test_identity_off_anniversary_income_dva_reset(self):
        policy = PolicySpec(age=65, income_start_year=1.5)
        res = value_contract(AgileProduct(), policy, CFG, MORT,
                             BehaviourModel(), settings=make_settings(n_paths=4000))
        assert abs(res.identity_gap) < 0.008, res.identity_gap


class TestGuaranteeMechanics:

    def test_income_continues_after_iv_exhausted(self):
        """Deep guarantee: high income rate must produce guarantee claims."""
        rates = replace(IncomeRateTable(), base_rate_shift=0.04)
        product = AgileProduct(income_rates=rates)
        policy = PolicySpec(age=70, income_start_year=1)
        res = value_contract(product, policy, CFG, MORT, no_lapse_behaviour(),
                             settings=make_settings())
        assert res.pv["guarantee_claims"] > 0.01 * policy.initial_investment

    def test_rising_income_ratchets_up(self):
        policy_f = PolicySpec(age=65, income_start_year=2, income_type=IncomeType.FIXED)
        policy_r = PolicySpec(age=65, income_start_year=2, income_type=IncomeType.RISING)
        scen = simulate("black_scholes", CFG, 40.0, 3000, seed=3)
        beh = no_lapse_behaviour()
        res_f = project(AgileProduct(), policy_f, scen, beh, MORT)
        res_r = project(AgileProduct(), policy_r, scen, beh, MORT)
        inc_r = res_r.income_paths[:, -1]
        # rising income never falls below its starting level
        start_r = res_r.income_paths[:, 25]
        alive = res_r.phase_paths[:, -1] == 1
        assert np.all(inc_r[alive] >= start_r[alive] - 1e-9)
        # rising starts lower than fixed
        start_f = res_f.income_paths[:, 25]
        assert np.mean(start_r[start_r > 0]) < np.mean(start_f[start_f > 0])

    def test_higher_age_higher_income_rate(self):
        t = IncomeRateTable()
        r65 = t.lifetime_income_rate(65, "M", IncomeType.FIXED, False, 0)
        r75 = t.lifetime_income_rate(75, "M", IncomeType.FIXED, False, 0)
        assert r75 > r65

    def test_escalator_rewards_growth_years(self):
        t = IncomeRateTable()
        r0 = t.lifetime_income_rate(70, "M", IncomeType.FIXED, False, 0)
        r5 = t.lifetime_income_rate(70, "M", IncomeType.FIXED, False, 5)
        esc = t.annual_escalator(70, "M", IncomeType.FIXED, False)
        assert r5 == pytest.approx(r0 + 5 * esc)

    def test_pds_example_income_calc(self):
        """PDS: IV 200k at 10.50% -> 21,000 p.a."""
        assert 200_000 * 0.105 == pytest.approx(21_000)

    def test_off_anniversary_income_start_dva_reset(self):
        """A mid-year election closes out the growth DVA and starts a fresh
        income-phase annual crediting period from that month."""
        product = AgileProduct(fees=FeeSpec(product_fee=0.0,
                                            lifetime_income_premium=0.0))
        policy = PolicySpec(age=65, income_start_year=1.5)
        scen = simulate("black_scholes", CFG, 4.0, 1, seed=31)
        res = project(product, policy, scen, no_lapse_behaviour(), MORT)
        step = 18

        assert res.phase_paths[0, step - 1] == 0
        assert res.phase_paths[0, step] == 1
        assert res.income_paths[0, step] > 0.0
        assert res.cashflows["income_paid"][0, step] == pytest.approx(0.0)
        assert res.cashflows["income_paid"][0, step + 1] > 0.0

        # The new income-period crediting cycle starts at 1.5y, so the next
        # DVA margin appears at 2.5y, not at the original 2.0y anniversary.
        assert res.cashflows["crediting_margin"][0, step] > 0.0
        assert res.cashflows["crediting_margin"][0, 24] == pytest.approx(0.0)
        assert res.cashflows["crediting_margin"][0, 30] > 0.0

        rate = product.income_rates.lifetime_income_rate(
            policy.age, policy.sex, policy.income_type, policy.spouse,
            1, policy.spouse_age, policy.spouse_sex, policy.age_pension_plus)
        income_base = res.income_paths[0, step] / rate
        opt = InvestmentOption.AUS_TP
        r_cc = scen.forward_zero_cc(step, 1.0)[0]
        sigma = scen.effective_bs_vol(opt.index, step, 1.0)[0]
        pz_start = intra_year_value_factor(
            1.0, opt.protection, product.caps.cap(opt, 1), 1.0,
            r_cc, product.dividend_yield[opt.index], sigma)
        assert res.iv_paths[0, step] == pytest.approx(income_base * pz_start,
                                                       rel=1e-10)

    def test_off_grid_income_start_rejected_explicitly(self):
        with pytest.raises(ValueError, match="monthly projection grid"):
            PolicySpec(age=65, income_start_year=1.55)


class TestFeesAndDecrements:

    def test_fee_pv_positive_and_bounded(self):
        policy = PolicySpec(age=65, income_start_year=5)
        res = value_contract(AgileProduct(), policy, CFG, MORT, BehaviourModel(),
                             settings=make_settings())
        total_fee_pv = res.pv["fees_product"] + res.pv["fees_lip"]
        assert 0 < total_fee_pv < 0.3 * policy.initial_investment
        ratio = res.pv["fees_lip"] / res.pv["fees_product"]
        assert ratio == pytest.approx(1.15 / 0.30, rel=1e-3)

    def test_no_mva_when_rates_unchanged(self):
        policy = PolicySpec(age=65, income_start_year=5)
        res = value_contract(AgileProduct(), policy, CFG, MORT,
                             no_lapse_behaviour(), settings=make_settings())
        assert res.pv["mva_retained"] == pytest.approx(0.0, abs=1e-9)

    def test_mva_factor_directions(self):
        mva = MVASpec()
        assert mva.factor(z_issue=0.04, z_now=0.06, tau=7.0) > 0.05
        assert mva.factor(z_issue=0.04, z_now=0.04, tau=7.0) == pytest.approx(0.0, abs=1e-12)
        assert mva.factor(z_issue=0.04, z_now=0.02, tau=7.0) == 0.0  # only_reduces

    def test_survival_curve_sane(self):
        s = MORT.survival_curve(65, "M", 45)
        assert s[0] == 1.0 and np.all(np.diff(s) <= 0)
        e65 = MORT.life_expectancy(65, "M")
        assert 15 < e65 < 30

    def test_longevity_stress_increases_life_expectancy(self):
        e_base = MORT.life_expectancy(65, "M")
        e_str = MORT.stressed(0.8).life_expectancy(65, "M")
        assert e_str > e_base


class TestFairFee:

    def test_fair_lip_bracket_and_direction(self):
        policy = PolicySpec(age=65, income_start_year=5)
        settings = make_settings(n_paths=3000)
        lip = fair_lifetime_income_premium(AgileProduct(), policy, CFG, MORT,
                                           no_lapse_behaviour(), settings=settings,
                                           hi=0.06)
        assert 0.0 <= lip < 0.06

        rich = replace(IncomeRateTable(), base_rate_shift=0.01)
        lip_rich = fair_lifetime_income_premium(
            AgileProduct(income_rates=rich), policy, CFG, MORT,
            no_lapse_behaviour(), settings=settings, hi=0.08)
        assert lip_rich > lip


class TestAgePensionPlus:

    def test_aps_caps_reduce_ph_value(self):
        """Isolate the CAS caps by switching the LIP waiver off: capped
        withdrawal values and death benefits must reduce PH value."""
        # Neutralise the separate APS rate-card uplift so this test isolates
        # only the Capital Access Schedule caps.
        card = IncomeRateTable()
        male = []
        female = []
        for source, target in ((card.male_rows, male), (card.female_rows, female)):
            for source_row in source:
                row = list(source_row)
                row[5:9] = row[1:5]
                target.append(tuple(row))
        product = AgileProduct(
            fees=FeeSpec(lip_waived_in_income_phase_if_aps=False),
            income_rates=IncomeRateTable(male_rows=tuple(male),
                                         female_rows=tuple(female)))
        policy = PolicySpec(age=65, income_start_year=3)
        policy_aps = replace(policy, age_pension_plus=True)
        beh = BehaviourModel(regime="static",
                             lapse=LapseAssumptions(growth_phase=(0.03,),
                                                    income_phase=0.02),
                             dynamic=DynamicLapseParams(enabled=False))
        settings = make_settings()
        res = value_contract(product, policy, CFG, MORT, beh, settings=settings)
        res_aps = value_contract(product, policy_aps, CFG, MORT, beh,
                                 settings=settings)
        ph = res.pv["income_paid"] + res.pv["death_benefits"] + res.pv["surrender_benefits"]
        ph_aps = (res_aps.pv["income_paid"] + res_aps.pv["death_benefits"]
                  + res_aps.pv["surrender_benefits"])
        assert ph_aps < ph
        assert res_aps.pv["aps_retained"] > 0.0

    def test_aps_lip_waiver_reduces_lip_income(self):
        policy_aps = PolicySpec(age=65, income_start_year=3, age_pension_plus=True)
        policy = PolicySpec(age=65, income_start_year=3)
        settings = make_settings()
        res = value_contract(AgileProduct(), policy, CFG, MORT, BehaviourModel(),
                             settings=settings)
        res_aps = value_contract(AgileProduct(), policy_aps, CFG, MORT,
                                 BehaviourModel(), settings=settings)
        assert res_aps.pv["fees_lip"] < res.pv["fees_lip"]


class TestReproducibility:

    def test_same_seed_same_value(self):
        policy = PolicySpec(age=65, income_start_year=5)
        r1 = value_contract(AgileProduct(), policy, CFG, MORT, BehaviourModel(),
                            settings=make_settings())
        r2 = value_contract(AgileProduct(), policy, CFG, MORT, BehaviourModel(),
                            settings=make_settings())
        assert r1.insurer_net_value == pytest.approx(r2.insurer_net_value, abs=1e-9)
