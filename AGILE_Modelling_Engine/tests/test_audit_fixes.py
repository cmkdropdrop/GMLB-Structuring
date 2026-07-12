"""Regression tests for defects found in the independent production audit."""

from dataclasses import replace

import numpy as np
import pytest

from agile_engine import (
    AgileProduct,
    BehaviourModel,
    DEFAULT_GUARANTEED_MIN_CAPS,
    ESGConfig,
    ExpenseAssumptions,
    IncomeRateTable,
    IncomeType,
    InvestmentOption,
    MortalityTable,
    PolicySpec,
    ProjectionConfig,
    Sex,
    SpouseDeathElection,
    ValuationSettings,
    YieldCurve,
    compute_capital,
    resolve_horizon,
    value_contract,
)
from agile_engine.behavior import DynamicLapseParams, LapseAssumptions
from agile_engine.esg import simulate
from agile_engine.projection import project


def static_no_lapse() -> BehaviourModel:
    return BehaviourModel(
        regime="static",
        lapse=LapseAssumptions(growth_phase=(0.0,), income_phase=0.0),
        dynamic=DynamicLapseParams(enabled=False),
    )


def test_july_2026_rate_card_golden_cells_and_floors():
    card = IncomeRateTable()
    assert DEFAULT_GUARANTEED_MIN_CAPS[InvestmentOption.AUS_TP] == pytest.approx(0.0025)
    assert DEFAULT_GUARANTEED_MIN_CAPS[InvestmentOption.AUS_PP10] == pytest.approx(0.0050)

    # Male, age 65 at policy commencement, single-life Fixed: 7.05% plus
    # 0.35% for each complete Growth-Phase year (July-2026 official flyer).
    assert card.base_rate(65, Sex.MALE, IncomeType.FIXED, False) == pytest.approx(0.0705)
    assert card.annual_escalator(65, Sex.MALE, IncomeType.FIXED, False) == pytest.approx(0.0035)
    assert card.lifetime_income_rate(
        65, Sex.MALE, IncomeType.FIXED, False, 10) == pytest.approx(0.1055)
    assert card.base_rate(
        65, Sex.MALE, IncomeType.FIXED, False,
        age_pension_plus=True) == pytest.approx(0.0710)

    # A younger female spouse supplies both rating age and gender.
    assert card.base_rate(
        65, Sex.MALE, IncomeType.FIXED, True,
        spouse_age=63, spouse_sex=Sex.FEMALE) == pytest.approx(0.0620)


def test_anniversary_income_base_is_after_election_month_fee():
    product = AgileProduct()
    policy = PolicySpec(age=65, income_start_year=1)
    scenarios = simulate("black_scholes", ESGConfig(), 2.0, 8, seed=91)
    result = project(
        product, policy, scenarios, static_no_lapse(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(dva_enabled=False,
                                crediting_margin_enabled=False),
    )
    step = 12
    rate = product.income_rates.lifetime_income_rate(
        policy.age, policy.sex, policy.income_type, policy.spouse, 1,
        policy.spouse_age, policy.spouse_sex, policy.age_pension_plus)
    # No payment occurs in the election month, so post-fee IV is exactly the
    # commencement base that was multiplied by the locked rate.
    np.testing.assert_allclose(result.income_paths[:, step] / rate,
                               result.iv_paths[:, step], rtol=1e-12, atol=1e-8)


def test_joint_life_horizon_and_annuity_include_younger_spouse_tail():
    mortality = MortalityTable.gompertz_makeham()
    joint = mortality.annuity_factor(
        80, Sex.MALE, 0.04, joint_age=50, joint_sex=Sex.FEMALE)
    spouse_single = mortality.annuity_factor(50, Sex.FEMALE, 0.04)
    assert joint >= spouse_single

    policy = PolicySpec(
        age=80, spouse=True, spouse_age=50, spouse_sex=Sex.FEMALE,
        spouse_death_election=SpouseDeathElection.CONTINUE_INCOME,
        income_start_year=1,
    )
    assert resolve_horizon(ValuationSettings(n_paths=10), policy) == 65.0


def test_non_monthly_horizon_and_invalid_inputs_fail_fast():
    with pytest.raises(ValueError, match="monthly"):
        ValuationSettings(horizon_years=1.1)
    with pytest.raises(ValueError, match="positive integer"):
        ValuationSettings(n_paths=0)
    with pytest.raises(ValueError, match="finite"):
        YieldCurve((1.0, 2.0), (0.02, float("nan")))
    with pytest.raises(ValueError, match="finite"):
        PolicySpec(allocation={InvestmentOption.AUS_TP: float("nan")})
    with pytest.raises(ValueError, match="spouse_age and spouse_sex"):
        PolicySpec(spouse=True, spouse_age=60)
    with pytest.raises(ValueError, match="upfront_adviser_fee_pct"):
        PolicySpec(upfront_adviser_fee_pct=1.5)


def test_scenario_and_dividend_provenance_are_checked():
    settings = ValuationSettings(model="black_scholes", n_paths=20,
                                 horizon_years=2.0)
    cfg_1 = ESGConfig(curve=YieldCurve.flat(0.01))
    cfg_4 = ESGConfig(curve=YieldCurve.flat(0.04))
    scenarios = simulate("black_scholes", cfg_1, 2.0, 20, seed=1)
    args = (AgileProduct(), PolicySpec(income_start_year=1), cfg_4,
            MortalityTable.gompertz_makeham(), static_no_lapse())
    with pytest.raises(ValueError, match="different ESG"):
        value_contract(*args, settings=settings, scenarios=scenarios)

    bad_product = replace(
        AgileProduct(),
        dividend_yield={k: 0.01 for k in AgileProduct().dividend_yield},
    )
    with pytest.raises(ValueError, match="dividend-yield"):
        value_contract(bad_product, PolicySpec(income_start_year=1), cfg_4,
                       MortalityTable.gompertz_makeham(), static_no_lapse(),
                       settings=settings)


def test_scr_runoff_survives_risk_margin_switch():
    settings = ValuationSettings(model="black_scholes", n_paths=150,
                                 horizon_years=4.0, seed=3)
    result = compute_capital(
        AgileProduct(), PolicySpec(income_start_year=1), ESGConfig(),
        MortalityTable.gompertz_makeham(), static_no_lapse(),
        expenses=ExpenseAssumptions(), settings=settings,
        with_risk_margin=False,
    )
    assert result.risk_margin == 0.0
    assert result.scr_pattern is not None
    assert result.scr_pattern[0] == pytest.approx(result.bscr)


@pytest.mark.skip(reason="LSMC is retained as archived research code and is inactive.")
def test_lsmc_rejects_unimplemented_age_pension_plus():
    from agile_engine.lsmc import LSMCSettings, value_optimal_behaviour
    with pytest.raises(NotImplementedError, match="Age Pension"):
        value_optimal_behaviour(
            AgileProduct(), PolicySpec(age_pension_plus=True), ESGConfig(),
            MortalityTable.gompertz_makeham(),
            settings=LSMCSettings(n_train=10, n_eval=10, horizon_years=2),
        )


def test_mortality_and_policy_inputs_are_defensively_immutable():
    mortality = MortalityTable.gompertz_makeham()
    with pytest.raises(ValueError):
        mortality.qx_male[65] = 1.0

    source = {InvestmentOption.AUS_TP: 1.0}
    policy = PolicySpec(allocation=source)
    source[InvestmentOption.AUS_TP] = 2.0
    assert sum(policy.allocation.values()) == pytest.approx(1.0)
