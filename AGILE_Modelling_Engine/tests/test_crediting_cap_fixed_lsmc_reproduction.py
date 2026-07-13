"""Fixed-cap and portfolio-weight integration checks for cap optimisation."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from agile_engine import (
    ESGConfig,
    ExpenseAssumptions,
    IndexLinkedLifetimeIncomeProduct,
    MortalityTable,
    PolicySpec,
    ProjectionConfig,
    YieldCurve,
    project,
)
from agile_engine.esg import Measure, simulate
from agile_engine.model_points import (
    PolicyholderModelPoint,
    PolicyholderModelPointSet,
)
from agile_engine.optimal_behaviour_lsmc import (
    OptimalBehaviourLSMCSettings,
    fit_optimal_surrender_policy,
    no_voluntary_action_behaviour,
)
from portfolio_simulations.optimize_crediting_rate_lsmc import (
    _aggregate_portfolio_paths,
    _fit_cap_aware_policyholder_policies,
)


CAP = 0.06
CONTRACT_WEIGHT = 0.40


def _model_points(
    policy: PolicySpec,
    second_policy: PolicySpec,
) -> PolicyholderModelPointSet:
    point = PolicyholderModelPoint(
        model_point_id="fixed-cap-reproduction",
        contract_weight=CONTRACT_WEIGHT,
        # Deliberately unrelated: this must never become a valuation weight.
        premium_volume_weight=0.95,
        policy=policy,
        initial_premium_aud=policy.initial_investment,
        product_id="GENERIC",
        product_pds_version="test",
        rate_card_vintage="test",
        cap_vintage="test",
        market_parameter_set_id="test",
        yield_curve_id="test",
        source_row_number=2,
    )
    second = replace(
        point,
        model_point_id="fixed-cap-weight-check",
        contract_weight=1.0 - CONTRACT_WEIGHT,
        premium_volume_weight=0.05,
        policy=second_policy,
        initial_premium_aud=second_policy.initial_investment,
        source_row_number=3,
    )
    return PolicyholderModelPointSet(
        model_points=(point, second),
        source_path="in-memory",
        source_sha256="test",
        product_id=point.product_id,
        product_pds_version=point.product_pds_version,
        rate_card_vintage=point.rate_card_vintage,
        cap_vintage=point.cap_vintage,
        market_parameter_set_id=point.market_parameter_set_id,
        yield_curve_id=point.yield_curve_id,
        contract_weight_sum=1.0,
        premium_volume_weight_sum=1.0,
        weighted_average_premium_aud=(
            CONTRACT_WEIGHT * policy.initial_investment
            + (1.0 - CONTRACT_WEIGHT) * second_policy.initial_investment
        ),
    )


def test_fixed_cap_optimizer_fit_and_forward_value_reproduce_runner_lsmc():
    product = IndexLinkedLifetimeIncomeProduct()
    fixed_product = replace(
        product,
        reference_fund=replace(
            product.reference_fund,
            scenario_maximum_return=CAP,
        ),
    )
    policy = PolicySpec(
        age=65.0,
        initial_investment=100_000.0,
        income_start_year=1,
    )
    second_policy = replace(
        policy,
        age=66.0,
        initial_investment=130_000.0,
    )
    model_points = _model_points(policy, second_policy)
    mortality = MortalityTable.gompertz_makeham()
    expenses = ExpenseAssumptions()
    config = ProjectionConfig(record_paths=True, heston_cos=False)
    settings = OptimalBehaviourLSMCSettings(
        n_folds=3,
        fold_seed=811,
        exercise_buffer_rmse_multiplier=0.0,
    )
    esg = ESGConfig(curve=YieldCurve.flat(0.04))
    training = simulate(
        "black_scholes",
        esg,
        4.0,
        96,
        measure=Measure.RISK_NEUTRAL,
        seed=810,
    )
    direct_fit = fit_optimal_surrender_policy(
        fixed_product,
        policy,
        training,
        mortality,
        expenses=expenses,
        projection_config=config,
        settings=settings,
    )
    second_direct_fit = fit_optimal_surrender_policy(
        fixed_product,
        second_policy,
        training,
        mortality,
        expenses=expenses,
        projection_config=config,
        settings=settings,
    )
    optimiser_fits = _fit_cap_aware_policyholder_policies(
        cap_matrix=np.full((training.n_paths, 4), CAP),
        scenarios=training,
        product=product,
        model_points=model_points,
        mortality=mortality,
        expenses=expenses,
        projection_config=config,
        settings=settings,
        progress_label="fixed-cap reproduction test",
    )
    optimiser_policy = optimiser_fits.factory(policy)

    assert optimiser_policy.regressions.keys() == direct_fit.policy.regressions.keys()
    for step in optimiser_policy.regressions:
        left = optimiser_policy.regressions[step]
        right = direct_fit.policy.regressions[step]
        np.testing.assert_allclose(left.coefficients, right.coefficients)
        np.testing.assert_allclose(left.centre, right.centre)
        np.testing.assert_allclose(left.scale, right.scale)
        np.testing.assert_allclose(
            left.orthogonal_components, right.orthogonal_components
        )

    evaluation = simulate(
        "black_scholes",
        esg,
        4.0,
        48,
        measure=Measure.RISK_NEUTRAL,
        seed=812,
    )
    behaviour = no_voluntary_action_behaviour()
    aggregated = _aggregate_portfolio_paths(
        scenarios=evaluation,
        cap_matrix=np.full((evaluation.n_paths, 4), CAP),
        product=product,
        model_points=model_points,
        behaviour=behaviour,
        mortality=mortality,
        expenses=expenses,
        projection_config=config,
        collect_states=False,
        progress_label="fixed-cap reproduction evaluation",
        model_point_log_interval=1,
        surrender_policy_factory=optimiser_fits.factory,
    )
    direct = project(
        fixed_product,
        policy,
        evaluation,
        behaviour,
        mortality,
        expenses=expenses,
        config=config,
        surrender_policy=direct_fit.policy,
    )
    second_direct = project(
        fixed_product,
        second_policy,
        evaluation,
        behaviour,
        mortality,
        expenses=expenses,
        config=config,
        surrender_policy=second_direct_fit.policy,
    )
    direct_pv = direct.pv_by_component()
    second_direct_pv = second_direct.pv_by_component()

    customer_keys = (
        "income_paid",
        "death_benefits",
        "surrender_benefits",
        "partial_withdrawals",
        "terminal_closeout",
    )
    expected_customer_pv = (
        CONTRACT_WEIGHT * sum(direct_pv[key] for key in customer_keys)
        + (1.0 - CONTRACT_WEIGHT)
        * sum(second_direct_pv[key] for key in customer_keys)
    )
    np.testing.assert_allclose(
        np.mean(np.sum(aggregated.policyholder_benefits, axis=1)),
        expected_customer_pv,
        rtol=2.0e-12,
        atol=1.0e-8,
    )
    for attribute, cashflow_key in (
        ("fees_product", "fees_product"),
        ("fees_lip", "fees_lip"),
        ("crediting_margin", "crediting_margin"),
        ("mva_retained", "mva_retained"),
        ("aps_retained", "aps_retained"),
        ("guarantee_claims", "guarantee_claims"),
        ("expenses", "expenses"),
        ("hedge_costs", "hedge_costs"),
    ):
        actual = np.mean(np.sum(getattr(aggregated, attribute), axis=1))
        np.testing.assert_allclose(
            actual,
            CONTRACT_WEIGHT * direct_pv[cashflow_key]
            + (1.0 - CONTRACT_WEIGHT) * second_direct_pv[cashflow_key],
            rtol=2.0e-12,
            atol=1.0e-8,
            err_msg=f"portfolio component {attribute!r} did not reconcile",
        )
