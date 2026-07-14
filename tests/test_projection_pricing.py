"""Projection & pricing tests: product mechanics, identities, limiting cases."""

import numpy as np
import pytest

from policy_engine import (AgileProduct, BehaviourModel, ESGConfig,
                          FeeSpec, IncomeRateTable,
                          IncomeType, IndexLinkedLifetimeIncomeProduct,
                          MortalityTable, MVASpec, PolicySpec,
                          ProjectionConfig, Protection, ReferenceFundSpec, ScenarioSet,
                          Sex, ValuationSettings, YieldCurve, value_contract,
                          fair_lifetime_income_premium,
                          intra_year_value_factor)
from policy_engine.behavior import (DynamicLapseParams, LapseAssumptions,
                                   WithdrawalBehaviour)
from policy_engine.esg import Measure, simulate
from policy_engine.forward_start_hedge_pricing import (
    HedgePriceCacheSpec,
    build_hedge_price_surface,
)
from policy_engine.product import Index
from policy_engine.projection import project
from portfolio_simulations.optimize_crediting_rate_lsmc import (
    _controlled_product,
    _pathwise_cap_adapter,
)
from dataclasses import replace
from test_scenario_cache import synthetic_scenarios


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

    def test_identity_base(self):
        policy = PolicySpec(age=65, income_start_year=5)
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

    def test_identity_at_earliest_anniversary_income_dva_reset(self):
        policy = PolicySpec(age=65, income_start_year=1.0)
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

    def test_rising_income_is_rejected(self):
        policy = PolicySpec(
            age=65,
            income_start_year=2,
            income_type=IncomeType.RISING,
        )

        with pytest.raises(
            ValueError,
            match="generic product offers Fixed Lifetime Income only",
        ):
            policy.validate_against(AgileProduct())

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

    def test_anniversary_income_start_dva_reset(self):
        """Election uses the contractual Anniversary and starts a new DVA year."""
        product = AgileProduct(fees=FeeSpec(product_fee=0.0,
                                            lifetime_income_premium=0.0))
        policy = PolicySpec(age=65, income_start_year=2.0)
        scen = simulate("black_scholes", CFG, 4.0, 1, seed=31)
        res = project(product, policy, scen, no_lapse_behaviour(), MORT)
        step = 24

        assert res.phase_paths[0, step - 1] == 0
        assert res.phase_paths[0, step] == 1
        assert res.income_paths[0, step] > 0.0
        assert res.cashflows["income_paid"][0, step] == pytest.approx(0.0)
        assert res.cashflows["income_paid"][0, step + 1] > 0.0

        # The insurer's crediting-margin aggregate now records monthly
        # money-market backing income (plus an optional retained hedge gain),
        # rather than an up-front DVA margin.  The customer-contract identity
        # keeps the DVA financing margin in its separate diagnostic ledger.
        np.testing.assert_allclose(
            res.cashflows["crediting_margin"],
            res.cashflows["money_market_income"] + res.cashflows["hedge_gain"],
            rtol=0.0,
            atol=1e-12,
        )
        assert res.cashflows["money_market_income"][0, step] > 0.0
        assert res.cashflows["money_market_income"][0, 30] > 0.0

        # Contract financing is an Anniversary-only identity ledger; it is
        # distinct from monthly money-market P&L.
        assert res.cashflows["contract_financing_margin"][0, step] > 0.0
        assert res.cashflows["contract_financing_margin"][0, 30] \
            == pytest.approx(0.0)
        assert res.cashflows["contract_financing_margin"][0, 36] > 0.0

        rate = product.income_rates.lifetime_income_rate(
            policy.age, policy.sex, policy.income_type, policy.spouse,
            2, policy.spouse_age, policy.spouse_sex, policy.age_pension_plus)
        income_base = res.income_paths[0, step] / rate
        reference_fund = product.reference_fund
        r_cc = scen.forward_zero_cc(step, 1.0)[0]
        sigma = scen.reference_fund_effective_vol(
            step,
            horizon=1.0,
            equity_index=reference_fund.equity_index,
            equity_weight=reference_fund.equity_weight,
            bond_tenor=reference_fund.bond_tenor_years,
        )[0]
        pz_start = intra_year_value_factor(
            1.0,
            Protection.TOTAL,
            reference_fund.cap(2),
            1.0,
            r_cc,
            0.0,
            sigma,
        )
        assert res.iv_paths[0, step] == pytest.approx(income_base * pz_start,
                                                       rel=1e-10)

    def test_off_grid_income_start_rejected_explicitly(self):
        with pytest.raises(ValueError, match="Policy Anniversary"):
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


class TestUnsupportedProductOptions:

    def test_age_pension_plus_is_rejected(self):
        policy = PolicySpec(
            age=65,
            income_start_year=3,
            age_pension_plus=True,
        )

        with pytest.raises(
            ValueError,
            match=r"generic product does not offer Age Pension\+",
        ):
            policy.validate_against(AgileProduct())


class TestReproducibility:

    def test_same_seed_same_value(self):
        policy = PolicySpec(age=65, income_start_year=5)
        r1 = value_contract(AgileProduct(), policy, CFG, MORT, BehaviourModel(),
                            settings=make_settings())
        r2 = value_contract(AgileProduct(), policy, CFG, MORT, BehaviourModel(),
                            settings=make_settings())
        assert r1.insurer_net_value == pytest.approx(r2.insurer_net_value, abs=1e-9)


def _projection_hedge_spec(
    scenarios: ScenarioSet,
    *,
    equity_index: Index = Index.GLOBAL_EQUITY,
    equity_allocation: float = 0.30,
    cap_grid: tuple[float, ...] = (0.0, 0.06, 0.10),
) -> HedgePriceCacheSpec:
    return HedgePriceCacheSpec(
        market_cache_key="1" * 64,
        scenario_fingerprint=scenarios.content_fingerprint,
        n_paths=scenarios.n_paths,
        horizon_years=float(scenarios.times[-1]),
        equity_index=equity_index,
        equity_allocation=equity_allocation,
        allocation_input_sha256="2" * 64,
        cap_grid=cap_grid,
        training_scenario_fingerprint=scenarios.content_fingerprint,
        cross_fit_folds=3,
        cross_fit_seed=11,
        ridge=1.0e-6,
    )


def _short_mc_projection(scenarios: ScenarioSet):
    return project(
        IndexLinkedLifetimeIncomeProduct(
            reference_fund=ReferenceFundSpec(equity_weight=0.30)
        ),
        PolicySpec(age=80.0, income_start_year=1.0),
        scenarios,
        BehaviourModel.static_only(),
        MortalityTable.gompertz_makeham(),
        config=ProjectionConfig(
            record_paths=False,
            max_age=82.0,
            hedge_pricing_method="mc_conditional",
        ),
    )


def test_mc_projection_uses_cached_path_aligned_reference_fund(monkeypatch):
    scenarios = synthetic_scenarios(n_paths=18)
    surface = build_hedge_price_surface(
        scenarios, _projection_hedge_spec(scenarios)
    )
    scenarios.bind_hedge_price_surface(surface)

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("reference fund must come from the hedge cache")

    monkeypatch.setattr(
        ScenarioSet,
        "monthly_rebalanced_reference_fund_index",
        fail_if_recomputed,
    )
    result = _short_mc_projection(scenarios)

    assert np.isfinite(result.pv_insurer_net())


@pytest.mark.parametrize(
    ("mismatch", "message"),
    (
        ("allocation", "equity_allocation"),
        ("index", "equity_index"),
        ("tenor", "bond_tenor_years"),
        ("caps", "cap_grid"),
    ),
)
def test_mc_projection_rejects_reference_fund_cache_mismatch(
    mismatch, message,
):
    scenarios = synthetic_scenarios(n_paths=18)
    spec = _projection_hedge_spec(
        scenarios,
        equity_index=(
            Index.AUS_EQUITY
            if mismatch == "index"
            else Index.GLOBAL_EQUITY
        ),
        equity_allocation=0.45 if mismatch == "allocation" else 0.30,
        cap_grid=(0.0, 0.05, 0.10) if mismatch == "caps"
        else (0.0, 0.06, 0.10),
    )
    surface = build_hedge_price_surface(scenarios, spec)
    if mismatch == "tenor":
        # Both public specifications deliberately enforce five years.  Mutate
        # the frozen cache metadata to exercise the defensive runtime check
        # against a corrupt or incorrectly bound artefact.
        object.__setattr__(surface.spec, "bond_tenor_years", 4.0)
    scenarios.bind_hedge_price_surface(surface)

    with pytest.raises(ValueError, match=message):
        _short_mc_projection(scenarios)


def test_mc_projection_accepts_pathwise_caps_from_exact_cache_grid():
    scenarios = synthetic_scenarios(n_paths=18)
    surface = build_hedge_price_surface(
        scenarios, _projection_hedge_spec(scenarios)
    )
    scenarios.bind_hedge_price_surface(surface)
    cap_grid = np.asarray(surface.cap_grid)
    cap_matrix = np.resize(
        cap_grid,
        (scenarios.n_paths, 2),
    )
    product = _controlled_product(
        IndexLinkedLifetimeIncomeProduct(
            reference_fund=ReferenceFundSpec(equity_weight=0.30)
        ),
        cap_matrix,
    )

    with _pathwise_cap_adapter():
        result = project(
            product,
            PolicySpec(age=80.0, income_start_year=1.0),
            scenarios,
            BehaviourModel.static_only(),
            MortalityTable.gompertz_makeham(),
            config=ProjectionConfig(
                record_paths=False,
                max_age=82.0,
                hedge_pricing_method="mc_conditional",
            ),
        )

    assert np.isfinite(result.pv_insurer_net())


def test_mc_projection_rejects_pathwise_cap_absent_from_cache_grid():
    scenarios = synthetic_scenarios(n_paths=18)
    surface = build_hedge_price_surface(
        scenarios, _projection_hedge_spec(scenarios)
    )
    scenarios.bind_hedge_price_surface(surface)
    cap_matrix = np.full((scenarios.n_paths, 2), 0.06)
    cap_matrix[0, 1] = 0.07
    product = _controlled_product(
        IndexLinkedLifetimeIncomeProduct(
            reference_fund=ReferenceFundSpec(equity_weight=0.30)
        ),
        cap_matrix,
    )

    with _pathwise_cap_adapter(), pytest.raises(ValueError, match="cap_grid"):
        project(
            product,
            PolicySpec(age=80.0, income_start_year=1.0),
            scenarios,
            BehaviourModel.static_only(),
            MortalityTable.gompertz_makeham(),
            config=ProjectionConfig(
                record_paths=False,
                max_age=82.0,
                hedge_pricing_method="mc_conditional",
            ),
        )
