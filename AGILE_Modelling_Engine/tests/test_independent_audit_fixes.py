"""Regression tests added by the independent July-2026 implementation audit."""

from dataclasses import replace

import numpy as np
import pytest

from agile_engine import (
    AgileProduct,
    BehaviourModel,
    CapitalResult,
    CapitalStresses,
    DynamicLapseParams,
    ESGConfig,
    ExpenseAssumptions,
    HedgeMarket,
    LapseAssumptions,
    MortalityTable,
    MVASpec,
    PolicySpec,
    ProfitabilitySettings,
    ValuationSettings,
    WithdrawalBehaviour,
    analyse_profitability,
    compute_capital,
    credited_return,
    simulate,
    value_contract,
)
from agile_engine.esg import Measure, ScenarioSet
from agile_engine.product import Index
from agile_engine.profitability import _irr
from agile_engine.projection import (
    ProjectionConfig,
    _apply_partial_withdrawals,
    _aps_death_cap,
    _aps_reduction_terms,
    _build_decrements,
    project,
)


def no_lapse(**withdrawals) -> BehaviourModel:
    return BehaviourModel(
        regime="static",
        lapse=LapseAssumptions(growth_phase=(0.0,), income_phase=0.0),
        dynamic=DynamicLapseParams(enabled=False),
        withdrawals=WithdrawalBehaviour(**withdrawals),
    )


def test_return_index_defaults_do_not_double_count_dividends():
    product = AgileProduct()
    config = ESGConfig()
    assert set(product.dividend_yield.values()) == {0.0}
    assert {p.dividend_yield for p in config.equity.values()} == {0.0}
    assert HedgeMarket().q == 0.0


def test_aps_pds_example_reduces_iv_and_income_by_ten_percent():
    pct, deduction, retained = _aps_reduction_terms(
        np.array([100_000.0]), np.array([50_000.0]),
        np.array([5_000.0]), np.array([0.0]), np.array([True]),
    )
    assert pct[0] == pytest.approx(0.10)
    assert deduction[0] == pytest.approx(10_000.0)
    assert 6_000.0 * (1.0 - pct[0]) == pytest.approx(5_400.0)
    assert retained[0] == pytest.approx(5_000.0)


def test_aps_pds_example_is_applied_in_withdrawal_booking():
    product = AgileProduct()
    policy = PolicySpec(age_pension_plus=True, income_start_year=1,
                        aps_life_expectancy=10.0)
    scenario = simulate("black_scholes", ESGConfig(), 6.0, 1, seed=2)
    iv = np.array([100_000.0])
    iv_frame = iv.copy()
    phase = np.array([1], dtype=np.int8)
    active = np.array([True])
    cas_base = np.array([100_000.0])
    cas_start = np.array([0.0])
    cas_le = np.array([10.0])
    cas_wd = np.array([0.0])
    free_used = np.array([0.0])
    partial_used = np.array([0.0])
    limit_base = np.array([100_000.0])
    income = np.array([6_000.0])
    weight = np.array([1.0])
    cfs = {name: np.zeros((1, 73)) for name in
           ("partial_withdrawals", "mva_retained", "aps_retained")}
    curve = scenario.config.curve

    _apply_partial_withdrawals(
        product, policy, scenario, 60, 5.0, iv, iv_frame, phase, active,
        cas_base, cas_start, cas_le, cas_wd, free_used, partial_used,
        limit_base, income, weight, cfs,
        WithdrawalBehaviour(excess_rate=0.05),
        lambda tau: float(np.expm1(curve.zero(tau))), 100_000.0,
    )

    assert cfs["partial_withdrawals"][0, 60] == pytest.approx(5_000.0)
    assert cfs["mva_retained"][0, 60] == pytest.approx(0.0)
    assert cfs["aps_retained"][0, 60] == pytest.approx(5_000.0)
    assert iv[0] == pytest.approx(90_000.0)
    assert income[0] == pytest.approx(5_400.0)
    assert cas_wd[0] == pytest.approx(5_000.0)


def test_aps_death_cap_jumps_to_mwv_and_reflects_withdrawals():
    product = AgileProduct()
    base = np.array([100_000.0])
    start = np.array([0.0])
    le = np.array([10.0])
    withdrawn = np.array([5_000.0])
    active = np.array([True])
    before = _aps_death_cap(product, base, 4.99, start, le, withdrawn, active)
    at_half = _aps_death_cap(product, base, 5.0, start, le, withdrawn, active)
    assert before[0] == pytest.approx(95_000.0)
    assert at_half[0] == pytest.approx(45_000.0)


def test_cat_shock_uses_policy_duration_not_mortality_table_base_year():
    base = MortalityTable.gompertz_makeham()
    cat = replace(base, q_add_first_year=0.0015)
    policy = PolicySpec(commencement_year=2026.5)
    dec_base = _build_decrements(policy, base, no_lapse(), 24)
    dec_cat = _build_decrements(policy, cat, no_lapse(), 24)
    assert np.all(dec_cat.q_primary_m[:12] > dec_base.q_primary_m[:12])
    np.testing.assert_allclose(dec_cat.q_primary_m[12:], dec_base.q_primary_m[12:])


def test_scenario_inputs_are_normalised_and_immutable():
    cfg = ESGConfig()
    scenario = ScenarioSet(
        config=cfg,
        measure=Measure.RISK_NEUTRAL,
        dt=1.0 / 12.0,
        times=[0.0, 1.0 / 12.0],
        index_levels={Index.AUS_EQUITY: [[1.0, 1.01]],
                      Index.GLOBAL_EQUITY: [[1.0, 0.99]]},
        short_rate=[[0.04, 0.04]],
        discount=[[1.0, np.exp(-0.04 / 12.0)]],
        model_name="black_scholes",
        seed=7,
    )
    assert scenario.n_paths == 1
    assert isinstance(scenario.times, np.ndarray)
    with pytest.raises(ValueError):
        scenario.discount[0, 1] = 1.0
    with pytest.raises(TypeError):
        scenario.index_levels[Index.AUS_EQUITY] = np.ones((1, 2))


@pytest.mark.parametrize("kind", ["seed", "paths", "horizon"])
def test_supplied_scenario_provenance_is_enforced(kind):
    cfg = ESGConfig()
    settings = ValuationSettings(model="black_scholes", n_paths=3, seed=11,
                                 horizon_years=1.0)
    n_paths = 2 if kind == "paths" else 3
    seed = 12 if kind == "seed" else 11
    horizon = 2.0 if kind == "horizon" else 1.0
    scenario = simulate("black_scholes", cfg, horizon, n_paths, seed=seed)
    with pytest.raises(ValueError):
        value_contract(AgileProduct(), PolicySpec(income_start_year=1), cfg,
                       MortalityTable.gompertz_makeham(), no_lapse(),
                       settings=settings, scenarios=scenario)


def test_heston_substep_provenance_is_enforced():
    cfg = ESGConfig()
    scenario = simulate("heston", cfg, 1.0, 2, seed=11, substeps=2)
    settings = ValuationSettings(model="heston", n_paths=2, seed=11,
                                 horizon_years=1.0, heston_substeps=4)
    with pytest.raises(ValueError, match="substep"):
        value_contract(AgileProduct(), PolicySpec(income_start_year=1), cfg,
                       MortalityTable.gompertz_makeham(), no_lapse(),
                       settings=settings, scenarios=scenario)


def test_scenario_content_is_part_of_valuation_provenance():
    cfg = ESGConfig()
    settings = ValuationSettings(model="black_scholes", n_paths=2, seed=13,
                                 horizon_years=1.0)
    scenario = simulate("black_scholes", cfg, 1.0, 2, seed=13)
    changed = {k: v.copy() for k, v in scenario.index_levels.items()}
    changed[Index.AUS_EQUITY][:, 1:] *= 1.01
    alternative = replace(scenario, index_levels=changed)
    args = (AgileProduct(), PolicySpec(income_start_year=1), cfg,
            MortalityTable.gompertz_makeham(), no_lapse())
    first = value_contract(*args, settings=settings, scenarios=scenario)
    second = value_contract(*args, settings=settings, scenarios=alternative)
    assert first.provenance != second.provenance


def test_growth_withdrawals_obey_cumulative_anniversary_year_limit():
    policy = PolicySpec(age=65, income_start_year=2)
    scenario = simulate("black_scholes", ESGConfig(), 1.0, 1, seed=3)
    result = project(
        AgileProduct(), policy, scenario,
        no_lapse(excess_rate=1.0, frequency="annual"),
        MortalityTable.gompertz_makeham().stressed(0.0),
        config=ProjectionConfig(dva_enabled=False, crediting_margin_enabled=False),
    )
    control = project(
        AgileProduct(), policy, scenario, no_lapse(),
        MortalityTable.gompertz_makeham().stressed(0.0),
        config=ProjectionConfig(dva_enabled=False, crediting_margin_enabled=False),
    )
    paid = result.annual_aggregate("partial_withdrawals")[1]
    anniversary_base = control.iv_paths[0, 12]
    assert paid <= 0.95 * anniversary_base + 1e-8
    assert paid == pytest.approx(0.95 * anniversary_base, rel=1e-8)


def test_income_in_arrears_is_paid_only_to_month_end_survivors():
    policy = PolicySpec(age=65, income_start_year=1)
    mortality = MortalityTable.gompertz_makeham()
    scenario = simulate("black_scholes", ESGConfig(), 2.0, 1, seed=4)
    result = project(AgileProduct(), policy, scenario, no_lapse(), mortality,
                     config=ProjectionConfig(dva_enabled=False,
                                             crediting_margin_enabled=False))
    step = 13  # first payment month after the anniversary election
    t_start = (step - 1) / 12.0
    q = mortality.q_monthly(
        policy.age + t_start, policy.sex,
        years_from_base=policy.commencement_year - mortality.base_year + t_start,
        projection_duration=t_start,
    )
    expected = (result.inforce[0, step - 1] * (1.0 - q)
                * result.income_paths[0, step] / 12.0)
    assert result.cashflows["income_paid"][0, step] == pytest.approx(expected)


def test_include_capital_false_ignores_supplied_capital_result():
    cfg = ESGConfig()
    policy = PolicySpec(income_start_year=1)
    mortality = MortalityTable.gompertz_makeham()
    expenses = ExpenseAssumptions()
    settings = ValuationSettings(model="black_scholes", n_paths=10, seed=5,
                                 horizon_years=2.0)
    fake = CapitalResult(
        nav_base=0.0, scr_by_module={}, scr_market=0.0, scr_life=0.0,
        bscr=1_000_000.0, risk_margin=500_000.0,
        scr_pattern=np.array([1_000_000.0, 0.0]), provenance="foreign",
    )
    kwargs = dict(product=AgileProduct(), policy=policy, esg_config=cfg,
                  mortality=mortality, behaviour=no_lapse(), expenses=expenses,
                  settings=settings,
                  prof_settings=ProfitabilitySettings(include_capital=False),
                  compute_capital_if_missing=False)
    base = analyse_profitability(**kwargs)
    supplied = analyse_profitability(**kwargs, capital_result=fake)
    assert supplied.capital is None
    np.testing.assert_allclose(supplied.capital_pattern, 0.0)
    assert supplied.vnb_market_consistent == pytest.approx(base.vnb_market_consistent)
    assert supplied.pvfp_hurdle == pytest.approx(base.pvfp_hurdle)


def test_capital_provenance_includes_stresses_and_rm_switch():
    cfg = ESGConfig()
    settings = ValuationSettings(model="black_scholes", n_paths=10, seed=6,
                                 horizon_years=2.0)
    common = dict(product=AgileProduct(), policy=PolicySpec(income_start_year=1),
                  esg_config=cfg, mortality=MortalityTable.gompertz_makeham(),
                  behaviour=no_lapse(), settings=settings)
    s1 = CapitalStresses(include_equity_vol=False, coc_rate=0.01)
    s2 = replace(s1, coc_rate=0.02)
    c1 = compute_capital(**common, stresses=s1, with_risk_margin=False)
    c2 = compute_capital(**common, stresses=s2, with_risk_margin=False)
    c3 = compute_capital(**common, stresses=s1, with_risk_margin=True)
    assert len({c1.provenance, c2.provenance, c3.provenance}) == 3
    assert c1.framework == "SII_RESEARCH_PROXY_NOT_APRA"


def test_validation_and_extended_irr_cases():
    with pytest.raises(ValueError):
        ValuationSettings(n_paths=1.0)
    with pytest.raises(ValueError):
        ValuationSettings(seed=1.0)
    with pytest.raises(ValueError):
        simulate("heston", ESGConfig(), 1.0, 1, substeps=0)
    with pytest.raises(ValueError, match="protection"):
        credited_return(0.1, "typo", 0.1)
    with pytest.raises(ValueError, match="cover ages"):
        MortalityTable.from_qx([65, 66], [0.01, 0.02], [0.008, 0.015])
    with pytest.raises(ValueError):
        CapitalStresses(coc_rate=-0.01)
    with pytest.raises(ValueError):
        CapitalStresses(corr_market=((1.0, 2.0, 0.0),
                                     (2.0, 1.0, 0.0),
                                     (0.0, 0.0, 1.0)))
    assert _irr(np.array([-1.0, 4.0])) == pytest.approx(3.0)
    assert _irr(np.array([-1.0, 0.4])) == pytest.approx(-0.6)


def test_net_investment_limits_and_time_dependent_mva_loading():
    product = AgileProduct(min_investment=20_000.0)
    policy = PolicySpec(initial_investment=20_000.0,
                        upfront_adviser_fee_pct=0.01)
    with pytest.raises(ValueError, match="Investment Amount"):
        policy.validate_against(product)
    mva = MVASpec(cost_loading=0.01,
                  cost_loading_per_remaining_year=0.002)
    assert mva.factor(0.04, 0.04, 5.0) == pytest.approx(0.02)
    illustrative = MVASpec.pds_illustrative_termination_loading()
    assert 100_000.0 * (1.0 - illustrative.factor(0.051, 0.051, 9.0)) \
        == pytest.approx(94_443.0)


def test_optional_bonus_increases_iv_and_is_an_insurer_acquisition_cost():
    policy = PolicySpec(initial_investment=100_000.0, bonus_interest_pct=0.02,
                        income_start_year=1)
    assert policy.net_initial_investment == pytest.approx(102_000.0)
    scenario = simulate("black_scholes", ESGConfig(), 1.0, 1, seed=9)
    result = project(AgileProduct(), policy, scenario, no_lapse(),
                     MortalityTable.gompertz_makeham(),
                     config=ProjectionConfig(dva_enabled=False,
                                             crediting_margin_enabled=False))
    assert result.cashflows["premium"][0, 0] == pytest.approx(102_000.0)
    assert result.cashflows["expenses"][0, 0] == pytest.approx(2_000.0)


def test_age_pension_plus_rejects_adviser_service_fee():
    with pytest.raises(ValueError, match="not available"):
        PolicySpec(age_pension_plus=True, upfront_adviser_fee_pct=0.01)
