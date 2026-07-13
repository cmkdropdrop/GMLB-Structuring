"""Focused regression tests for the annual crediting-cap LSMC helpers."""

from types import SimpleNamespace

import numpy as np
import pytest

from agile_engine import (
    HedgeCapLegMode,
    IndexLinkedLifetimeIncomeProduct,
    Measure,
    MortalityTable,
    PolicySpec,
    ProjectionConfig,
    ReferenceFundSpec,
    load_cost_assumptions,
    load_dynamic_behaviour_assumptions,
    load_market_assumptions,
    project,
    simulate,
)
from agile_engine.crediting import (hedge_option_package_value,
                                    intra_year_value_factor)
from agile_engine.optimal_behaviour_lsmc import (
    OptimalBehaviourLSMCSettings,
    OptimalSurrenderPolicy,
)
from agile_engine.product import Protection
from portfolio_simulations.optimize_crediting_rate_lsmc import (
    ACTION_CAPS,
    BackwardResult,
    COMBINED_FOLLOWER_VERSION,
    CONTROL_STATE_FEATURE_NAMES,
    ControlStateInputs,
    CoupledPolicyholderFitSet,
    PathwiseReferenceFundSpec,
    PolicyholderFitSet,
    RegressionPolicyYear,
    _annual_start_discounted_paths,
    _adaptive_policy_passes_validation,
    _annual_discounted_control_paths,
    _annual_discounted_paths,
    _constant_first_year_policy,
    _controlled_product,
    _control_state_inputs,
    _control_state_paths,
    _csm_benchmark_row,
    _pathwise_cap_adapter,
    _policy_payload,
    _policy_signature,
    _rollout_cap_policy,
    _slice_scenarios,
    _vector_hedge_option_package_value,
    _vector_intra_year_value_factor,
    _vector_retained_excess_return,
)


def _minimal_backward_result() -> BackwardResult:
    n_features = len(CONTROL_STATE_FEATURE_NAMES)
    policy_year = RegressionPolicyYear(
        year=0,
        raw_mean=np.zeros(n_features),
        raw_scale=np.ones(n_features),
        coefficients=np.zeros((len(ACTION_CAPS), 1, 1)),
        action_caps=ACTION_CAPS.copy(),
        action_value_standard_error=np.ones(len(ACTION_CAPS)),
    )
    return BackwardResult(
        first_year_cap=0.08,
        pv_new_business_csm_proxy=0.0,
        pv_guarantee_claims=0.0,
        pv_other_insurer_funded_benefits=0.0,
        pv_fees_product=0.0,
        pv_fees_lip=0.0,
        pv_crediting_margin=0.0,
        pv_mva_retained=0.0,
        pv_aps_retained=0.0,
        pv_expenses=0.0,
        pv_hedge_costs=0.0,
        standard_error_new_business_csm_proxy=0.0,
        first_year_action_rows=[],
        policy_year_rows=[],
        regression_rows=[],
        policy_years=[policy_year],
        reconciliation_gap=0.0,
        economically_active_policy_years=(0,),
        inactive_market_tail_year_count=0,
    )


def test_action_caps_are_minimum_plus_every_whole_percent_through_twenty():
    expected = np.array([0.0025, *[percent / 100.0 for percent in range(1, 21)]])

    assert ACTION_CAPS.shape == (21,)
    np.testing.assert_allclose(ACTION_CAPS, expected, rtol=0.0, atol=1.0e-15)


@pytest.mark.parametrize(
    (
        "insurer_stable",
        "policyholder_passed",
        "rollout_valid",
        "delta",
        "standard_error",
        "expected",
    ),
    [
        (True, True, True, 196.01, 100.0, True),
        (True, True, True, 196.00, 100.0, False),
        (False, True, True, 1_000.0, 1.0, False),
        (True, False, True, 1_000.0, 1.0, False),
        (True, True, False, 1_000.0, 1.0, False),
        (True, True, True, float("nan"), 1.0, False),
        (True, True, True, 1_000.0, -1.0, False),
    ],
)
def test_adaptive_deployment_gate_is_validation_only_and_conservative(
    insurer_stable,
    policyholder_passed,
    rollout_valid,
    delta,
    standard_error,
    expected,
):
    assert _adaptive_policy_passes_validation(
        insurer_regression_stable=insurer_stable,
        policyholder_validation_passed=policyholder_passed,
        causal_rollout_valid=rollout_valid,
        csm_delta_aud=delta,
        paired_standard_error_aud=standard_error,
    ) is expected


def _minimal_combined_policy():
    return SimpleNamespace(
        valid=True,
        invalid_reasons=(),
        monthly_income_actions_required=True,
        surrender_policy=SimpleNamespace(regressions={}),
        start_income_mask=lambda *, context: context,
        choose_income_action=lambda *, context: context,
    )


def _minimal_combined_fit(*, valid=True, invalid_reasons=()):
    cross_fitted = _minimal_combined_policy()
    return SimpleNamespace(
        fit_version=COMBINED_FOLLOWER_VERSION,
        valid=valid,
        invalid_reasons=tuple(invalid_reasons),
        policy=_minimal_combined_policy(),
        cross_fitted_training_policy=cross_fitted,
        diagnostics=(),
        training_fallback_used=False,
    )


def test_policyholder_fit_set_factory_rejects_legacy_and_invalid_fits():
    policy_spec = PolicySpec(age=65.0, income_start_year=5.0)
    signature = _policy_signature(policy_spec)
    legacy_fit = SimpleNamespace(
        fit_version="legacy_surrender_only_v1",
        valid=True,
        invalid_reasons=(),
        policy=OptimalSurrenderPolicy(
            regressions={},
            settings=OptimalBehaviourLSMCSettings(),
        ),
        diagnostics=(),
        training_fallback_used=False,
    )
    invalid_v2_fit = _minimal_combined_fit(
        valid=False,
        invalid_reasons=("material_income_action_fit_failure",),
    )

    for fit, expected_message in (
        (legacy_fit, "deployment requires"),
        (invalid_v2_fit, "invalid combined follower"),
    ):
        fit_set = PolicyholderFitSet(
            fits={signature: fit},
            scenario_fingerprint="training",
            cap_schedule_fingerprint="cap-schedule",
        )
        with pytest.raises(RuntimeError, match=expected_message):
            fit_set.factory(policy_spec)


def test_policyholder_fit_set_factory_returns_the_same_combined_v2_policy():
    policy_spec = PolicySpec(age=65.0, income_start_year=5.0)
    signature = _policy_signature(policy_spec)
    fit = _minimal_combined_fit()
    fit_set = PolicyholderFitSet(
        fits={signature: fit},
        scenario_fingerprint="training",
        cap_schedule_fingerprint="cap-schedule",
    )

    deployed = fit_set.factory(policy_spec)

    assert deployed is fit.policy
    assert fit_set.factory(policy_spec) is deployed
    assert callable(deployed.start_income_mask)
    assert callable(deployed.choose_income_action)
    assert deployed.monthly_income_actions_required is True
    assert deployed.surrender_policy.regressions == {}


def test_coupled_fit_set_exposes_legacy_policy_only_as_benchmark():
    policy_spec = PolicySpec(age=65.0, income_start_year=5.0)
    signature = _policy_signature(policy_spec)
    legacy_policy = OptimalSurrenderPolicy(
        regressions={},
        settings=OptimalBehaviourLSMCSettings(),
    )
    fit_set = CoupledPolicyholderFitSet(
        policies={signature: legacy_policy},
        scenario_fingerprint="training",
        cap_schedule_fingerprint="control-randomisation",
    )

    assert fit_set.deployment_eligible is False
    with pytest.raises(RuntimeError, match="cannot be deployed"):
        fit_set.factory(policy_spec)
    assert fit_set.benchmark_factory(policy_spec) is legacy_policy


def test_coupled_and_fixed_fit_sets_deploy_the_same_combined_v2_surface():
    policy_spec = PolicySpec(age=65.0, income_start_year=5.0)
    signature = _policy_signature(policy_spec)
    fit = _minimal_combined_fit()
    fixed = PolicyholderFitSet(
        fits={signature: fit},
        scenario_fingerprint="training",
        cap_schedule_fingerprint="fixed-cap",
    )
    coupled = CoupledPolicyholderFitSet(
        policies={},
        fits={signature: fit},
        scenario_fingerprint="training",
        cap_schedule_fingerprint="randomised-caps",
    )

    assert coupled.deployment_eligible is True
    assert coupled.follower_contract_version == COMBINED_FOLLOWER_VERSION
    assert coupled.factory(policy_spec) is fixed.factory(policy_spec)
    assert coupled.training_factory(policy_spec) is (
        fit.cross_fitted_training_policy
    )
    assert callable(coupled.factory(policy_spec).start_income_mask)
    assert callable(coupled.factory(policy_spec).choose_income_action)


@pytest.mark.parametrize(
    ("adaptive_selected", "expected_type", "coefficients_authoritative"),
    [
        (False, "fixed_cap_fallback", False),
        (True, "adaptive_fitted_q", True),
    ],
)
def test_policy_payload_identifies_the_actually_deployed_rule(
    adaptive_selected,
    expected_type,
    coefficients_authoritative,
):
    payload = _policy_payload(
        _minimal_backward_result(),
        CONTROL_STATE_FEATURE_NAMES,
        {"projection": "test"},
        fixed_fallback_cap=0.0025,
        deployed_first_year_cap=(0.08 if adaptive_selected else 0.0025),
        adaptive_policy_selected=adaptive_selected,
        validation_delta_aud=(-23_000.0 if not adaptive_selected else 3_000.0),
        validation_paired_standard_error_aud=800.0,
        advantage_screen_multiplier=1.96,
    )
    deployment = payload["deployment"]

    assert deployment["policy_type"] == expected_type
    assert deployment["adaptive_policy_selected"] is adaptive_selected
    assert (
        deployment["fitted_coefficients_authoritative_for_deployment"]
        is coefficients_authoritative
    )
    assert deployment["fixed_fallback_cap_decimal"] == pytest.approx(0.0025)
    assert deployment["advantage_screen_is_confidence_interval"] is False
    assert payload["application_rule"] == deployment["deployed_rule"]
    if adaptive_selected:
        assert "year-specific fitted-Q coefficients" in payload["application_rule"]
    else:
        assert "Ignore the fitted-Q coefficients" in payload["application_rule"]


def test_annual_discounted_paths_adds_time_zero_cashflow_to_first_year():
    cashflow = np.zeros((2, 25), dtype=float)
    cashflow[:, 0] = (7.0, -3.0)
    cashflow[:, 1] = (2.0, 5.0)
    cashflow[:, 12] = (4.0, 6.0)
    cashflow[:, 13] = (8.0, 9.0)
    cashflow[:, 24] = (10.0, 11.0)
    discount = np.vstack((
        np.linspace(1.0, 0.76, 25),
        np.linspace(0.98, 0.74, 25),
    ))

    without_time_zero = _annual_discounted_paths(
        cashflow, discount, n_years=2
    )
    with_time_zero = _annual_discounted_paths(
        cashflow,
        discount,
        n_years=2,
        include_time_zero_in_first_year=True,
    )

    expected_increment = np.zeros_like(with_time_zero)
    expected_increment[:, 0] = cashflow[:, 0] * discount[:, 0]
    np.testing.assert_allclose(
        with_time_zero,
        without_time_zero + expected_increment,
        rtol=0.0,
        atol=0.0,
    )
    assert np.all(with_time_zero[:, 0] != expected_increment[:, 0])


def test_annual_start_discounted_paths_assigns_only_anniversary_cashflows():
    """DVA value/cost cashflows belong to the cap selected at year start."""
    cashflow = np.zeros((2, 25), dtype=float)
    cashflow[:, 0] = (7.0, -3.0)
    cashflow[:, 12] = (4.0, 6.0)
    cashflow[:, 24] = (10.0, 11.0)
    discount = np.vstack((
        np.linspace(1.0, 0.76, 25),
        np.linspace(0.98, 0.74, 25),
    ))

    actual = _annual_start_discounted_paths(
        cashflow, discount, n_years=3
    )
    expected = np.column_stack((
        cashflow[:, 0] * discount[:, 0],
        cashflow[:, 12] * discount[:, 12],
        cashflow[:, 24] * discount[:, 24],
    ))
    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=0.0)

    off_anniversary = cashflow.copy()
    off_anniversary[:, 13] = (0.01, -0.02)
    with pytest.raises(RuntimeError, match="away from control-year starts"):
        _annual_start_discounted_paths(
            off_anniversary, discount, n_years=3
        )


def test_annual_control_paths_split_anniversary_pre_and_post_cap_and_reconcile():
    """Only the post-announcement part moves into the new control year."""
    cashflow = np.zeros((2, 25), dtype=float)
    post_cap = np.zeros_like(cashflow)
    cashflow[:, 0] = (3.0, -2.0)
    cashflow[:, 5] = (4.0, 5.0)
    cashflow[:, 12] = (11.0, -7.0)
    post_cap[:, 12] = (2.5, -1.5)
    cashflow[:, 13] = (6.0, 8.0)
    cashflow[:, 24] = (9.0, 10.0)
    discount = np.vstack((
        np.linspace(1.0, 0.76, 25),
        np.linspace(0.98, 0.74, 25),
    ))

    actual = _annual_discounted_control_paths(
        cashflow,
        post_cap,
        discount,
        n_years=2,
    )
    anniversary_total = cashflow[:, 12] * discount[:, 12]
    anniversary_post_cap = post_cap[:, 12] * discount[:, 12]
    expected = np.column_stack((
        cashflow[:, 0] * discount[:, 0]
        + cashflow[:, 5] * discount[:, 5]
        + anniversary_total
        - anniversary_post_cap,
        anniversary_post_cap
        + cashflow[:, 13] * discount[:, 13]
        + cashflow[:, 24] * discount[:, 24],
    ))

    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=3.0e-15)
    np.testing.assert_allclose(
        np.sum(actual, axis=1),
        np.sum(cashflow * discount, axis=1),
        rtol=0.0,
        atol=1.0e-14,
    )


@pytest.mark.parametrize("protection", [Protection.TOTAL, Protection.PARTIAL_10])
def test_vector_intra_year_value_factor_matches_engine_scalar_and_vector(
    protection,
):
    scalar_arguments = dict(
        x0=1.04,
        protection=protection,
        cap=0.08,
        tau=0.65,
        rate=0.035,
        dividend_yield=0.02,
        sigma=0.19,
        buffer=0.10,
    )
    scalar_actual = _vector_intra_year_value_factor(**scalar_arguments)
    scalar_expected = intra_year_value_factor(
        scalar_arguments["x0"],
        protection,
        scalar_arguments["cap"],
        scalar_arguments["tau"],
        scalar_arguments["rate"],
        scalar_arguments["dividend_yield"],
        scalar_arguments["sigma"],
        scalar_arguments["buffer"],
    )

    assert isinstance(scalar_actual, float)
    assert scalar_actual == pytest.approx(scalar_expected, rel=2.0e-13)

    x0 = np.array([0.86, 1.00, 1.17])
    caps = np.array([0.0025, 0.07, 0.20])
    rates = np.array([0.01, 0.035, 0.06])
    sigmas = np.array([0.12, 0.19, 0.31])
    vector_actual = _vector_intra_year_value_factor(
        x0,
        protection,
        caps,
        0.65,
        rates,
        0.02,
        sigmas,
        0.10,
    )
    vector_expected = np.array([
        intra_year_value_factor(
            spot, protection, cap, 0.65, rate, 0.02, sigma, 0.10
        )
        for spot, cap, rate, sigma in zip(x0, caps, rates, sigmas)
    ])

    np.testing.assert_allclose(
        vector_actual, vector_expected, rtol=2.0e-13, atol=2.0e-13
    )


@pytest.mark.parametrize(
    "mode", [HedgeCapLegMode.SOLD, HedgeCapLegMode.NOT_SOLD]
)
def test_vector_hedge_package_supports_pathwise_caps_and_uncapped(mode):
    x0 = np.array([0.88, 0.92, 1.00, 1.08, 1.16])
    caps = np.array([0.0, 0.0025, 0.07, 0.20, np.inf])
    rates = np.array([0.01, 0.02, 0.03, 0.05, 0.07])
    sigmas = np.array([0.10, 0.12, 0.18, 0.24, 0.30])

    actual = _vector_hedge_option_package_value(
        x0, caps, 0.75, rates, 0.0, sigmas, mode
    )
    expected = np.array([
        hedge_option_package_value(
            spot,
            cap if np.isfinite(cap) else 0.06,
            0.75,
            rate,
            0.0,
            sigma,
            (
                mode
                if np.isfinite(cap) or mode == HedgeCapLegMode.NOT_SOLD
                else HedgeCapLegMode.NOT_SOLD
            ),
        )
        for spot, cap, rate, sigma in zip(x0, caps, rates, sigmas)
    ])

    np.testing.assert_allclose(actual, expected, rtol=2.0e-13, atol=2.0e-13)


def test_vector_retained_excess_supports_pathwise_caps_and_uncapped():
    returns = np.array([0.02, -0.10, 0.05, 0.15, 0.30])
    caps = np.array([0.0, 0.0025, 0.07, 0.10, np.inf])

    np.testing.assert_array_equal(
        _vector_retained_excess_return(
            returns, caps, HedgeCapLegMode.SOLD
        ),
        np.zeros_like(returns),
    )
    np.testing.assert_allclose(
        _vector_retained_excess_return(
            returns, caps, HedgeCapLegMode.NOT_SOLD
        ),
        np.array([0.02, 0.0, 0.0, 0.05, 0.0]),
        rtol=0.0,
        atol=1.0e-15,
    )


def test_control_states_are_strictly_pre_action_for_each_decision_year():
    n_paths, n_years = 2, 3
    market_features = (
        np.arange(n_paths * (n_years + 1) * 5, dtype=float)
        .reshape(n_paths, n_years + 1, 5)
        / 100.0
    )
    annual_returns = np.array([
        [0.30, 0.35, 0.40],
        [0.25, 0.32, 0.38],
    ])
    inputs = ControlStateInputs(market_features, annual_returns)
    baseline_caps = np.full((n_paths, n_years), 0.01)
    baseline_states = _control_state_paths(inputs, baseline_caps)

    for year in range(n_years):
        current_and_later_caps = baseline_caps.copy()
        current_and_later_caps[:, year:] = 0.20
        changed_states = _control_state_paths(inputs, current_and_later_caps)

        np.testing.assert_array_equal(
            changed_states[:, year, :], baseline_states[:, year, :]
        )
        assert not np.allclose(
            changed_states[:, year + 1, :],
            baseline_states[:, year + 1, :],
        )

        later_caps_only = baseline_caps.copy()
        later_caps_only[:, year + 1:] = 0.20
        later_only_states = _control_state_paths(inputs, later_caps_only)
        np.testing.assert_array_equal(
            later_only_states[:, year + 1, :],
            baseline_states[:, year + 1, :],
        )


def test_control_state_inputs_support_a_partial_final_policy_year():
    """A fractional projection horizon clips only the terminal observation."""
    market = load_market_assumptions()
    product = IndexLinkedLifetimeIncomeProduct(
        reference_fund=ReferenceFundSpec(),
        dividend_yield={
            index: parameters.dividend_yield
            for index, parameters in market.esg.equity.items()
        },
    )
    scenarios = simulate(
        "heston_hull_white",
        market.esg,
        horizon_years=1.5,
        n_paths=2,
        measure=Measure.RISK_NEUTRAL,
        seed=811,
    )

    inputs = _control_state_inputs(scenarios, product, n_years=2)
    reference = scenarios.monthly_rebalanced_reference_fund_index(
        equity_index=product.reference_fund.equity_index,
        equity_weight=product.reference_fund.equity_weight,
        bond_tenor=product.reference_fund.bond_tenor_years,
    )
    expected_last_partial_return = (
        reference[:, scenarios.n_steps] / reference[:, 12] - 1.0
    )

    assert scenarios.n_steps == 18
    assert inputs.market_features.shape == (2, 3, 5)
    assert inputs.annual_reference_fund_return.shape == (2, 2)
    np.testing.assert_allclose(
        inputs.annual_reference_fund_return[:, 1],
        expected_last_partial_return,
        rtol=2.0e-13,
        atol=2.0e-13,
    )


def test_training_validation_and_evaluation_scenario_fingerprints_are_distinct():
    market = load_market_assumptions()
    training = simulate(
        "heston_hull_white",
        market.esg,
        horizon_years=1.0,
        n_paths=4,
        measure=Measure.RISK_NEUTRAL,
        seed=901,
    )
    benchmark_parent = simulate(
        "heston_hull_white",
        market.esg,
        horizon_years=1.0,
        n_paths=8,
        measure=Measure.RISK_NEUTRAL,
        seed=902,
    )
    validation = _slice_scenarios(benchmark_parent, 0, 4)
    evaluation = _slice_scenarios(benchmark_parent, 4, 8)

    assert len({
        training.content_fingerprint,
        validation.content_fingerprint,
        evaluation.content_fingerprint,
    }) == 3


def test_csm_benchmark_self_comparison_and_component_reconciliation():
    components = {
        "fees_product": np.array([10.0, 12.0, 14.0]),
        "fees_lip": np.array([1.0, 2.0, 3.0]),
        "crediting_margin": np.array([4.0, 5.0, 6.0]),
        "mva_retained": np.array([0.5, 1.0, 1.5]),
        "aps_retained": np.array([1.0, 0.0, 2.0]),
        "guarantee_claims": np.array([3.0, 4.0, 5.0]),
        "other_insurer_funded_benefits": np.array([0.5, 1.0, 1.5]),
        "expenses": np.array([2.0, 2.5, 3.0]),
        "hedge_costs": np.array([0.25, 0.5, 0.75]),
        "terminal_closeout": np.array([100.0, 200.0, 300.0]),
    }
    future_fees = components["fees_product"] + components["fees_lip"]
    other_margins = (
        components["crediting_margin"]
        + components["mva_retained"]
        + components["aps_retained"]
    )
    benefits = (
        components["guarantee_claims"]
        + components["other_insurer_funded_benefits"]
    )
    costs = components["expenses"] + components["hedge_costs"]
    csm_paths = future_fees + other_margins - benefits - costs
    portfolio_scale = 2.5

    row = _csm_benchmark_row(
        label="self",
        cap=0.06,
        definition="paired self-comparison",
        components=components,
        csm_paths=csm_paths,
        best_fixed_paths=csm_paths.copy(),
        portfolio_scale=portfolio_scale,
        is_best_fixed=True,
    )

    assert row[
        "new_business_csm_difference_vs_best_fixed_admissible_aud"
    ] == 0.0
    assert row[
        "paired_standard_error_new_business_csm_difference_vs_best_fixed_aud"
    ] == 0.0
    assert row["new_business_csm_component_reconciliation_gap_aud"] == 0.0
    assert row[
        "new_business_csm_component_reconciliation_max_absolute_aud"
    ] == 0.0
    assert row["estimated_new_business_csm_proxy_aud"] == pytest.approx(
        portfolio_scale * np.mean(csm_paths)
    )
    assert row["estimated_new_business_csm_proxy_aud"] == pytest.approx(
        row["pv_future_fees_aud"]
        + row["pv_other_insurer_margins_aud"]
        - row["pv_total_insurer_funded_benefits_aud"]
        - row["pv_total_costs_aud"]
    )
    assert row["pv_terminal_closeout_excluded_aud"] == pytest.approx(
        portfolio_scale * np.mean(components["terminal_closeout"])
    )


def test_constant_pathwise_cap_adapter_matches_standard_projection_by_component():
    """A pathwise constant 6% cap is the ordinary contractual projection."""
    market = load_market_assumptions()
    base_product = IndexLinkedLifetimeIncomeProduct(
        reference_fund=ReferenceFundSpec(),
        dividend_yield={
            index: parameters.dividend_yield
            for index, parameters in market.esg.equity.items()
        },
    )
    projection_config = ProjectionConfig(
        dva_enabled=True,
        record_paths=True,
        heston_cos=False,
    )
    costs = load_cost_assumptions(
        product=base_product,
        projection=projection_config,
    )
    behaviour = load_dynamic_behaviour_assumptions().behaviour
    mortality = MortalityTable.gompertz_makeham()
    policy = PolicySpec(age=65.0, income_start_year=1.0)
    scenarios = simulate(
        "heston_hull_white",
        market.esg,
        horizon_years=2.0,
        n_paths=4,
        measure=Measure.RISK_NEUTRAL,
        seed=1729,
    )
    assert scenarios.measure == Measure.RISK_NEUTRAL
    assert costs.projection.dva_enabled

    standard = project(
        costs.product,
        policy,
        scenarios,
        behaviour,
        mortality,
        expenses=costs.expenses,
        config=costs.projection,
    )
    cap_matrix = np.full((scenarios.n_paths, 2), 0.06)
    controlled_product = _controlled_product(costs.product, cap_matrix)
    assert isinstance(controlled_product.reference_fund, PathwiseReferenceFundSpec)
    with _pathwise_cap_adapter():
        pathwise = project(
            controlled_product,
            policy,
            scenarios,
            behaviour,
            mortality,
            expenses=costs.expenses,
            config=costs.projection,
        )

    assert standard.iv_paths is not None
    assert pathwise.iv_paths is not None
    np.testing.assert_allclose(
        pathwise.iv_paths, standard.iv_paths, rtol=2.0e-13, atol=1.0e-9
    )
    np.testing.assert_allclose(
        pathwise.inforce, standard.inforce, rtol=2.0e-13, atol=1.0e-12
    )
    assert pathwise.cashflows.keys() == standard.cashflows.keys()
    for key in standard.cashflows:
        np.testing.assert_allclose(
            pathwise.cashflows[key],
            standard.cashflows[key],
            rtol=2.0e-13,
            atol=1.0e-9,
            err_msg=f"cashflow component {key!r} differs",
        )


def test_rollout_requires_significant_gain_and_has_one_first_year_action():
    n_paths = 5
    market_features = np.zeros((n_paths, 2, 5), dtype=float)
    market_features[:, 0, 0] = np.linspace(0.01, 0.05, n_paths)
    market_features[:, 0, 1] = np.linspace(0.02, 0.06, n_paths)
    market_features[:, 1, :] = market_features[:, 0, :] + 0.01
    inputs = ControlStateInputs(
        market_features=market_features,
        annual_reference_fund_return=np.linspace(0.02, 0.18, n_paths)[:, None],
    )
    fallback_cap = 0.06
    alternative_cap = 0.12
    fallback_action = int(np.flatnonzero(np.isclose(ACTION_CAPS, fallback_cap))[0])
    alternative_action = int(
        np.flatnonzero(np.isclose(ACTION_CAPS, alternative_cap))[0]
    )
    raw_first_year_state = _control_state_paths(
        inputs, np.full((n_paths, 1), fallback_cap)
    )[:, 0, :]
    standard_errors = np.full(len(ACTION_CAPS), 0.05)

    def constant_policy(alternative_advantage):
        action_values = np.full((len(ACTION_CAPS), 1), -1.0)
        action_values[fallback_action, 0] = 0.0
        action_values[alternative_action, 0] = alternative_advantage
        return _constant_first_year_policy(
            year=0,
            raw_state=raw_first_year_state,
            action_values=action_values,
            action_standard_errors=standard_errors,
            feature_names=CONTROL_STATE_FEATURE_NAMES,
        )

    insignificant = _rollout_cap_policy(
        inputs,
        [constant_policy(alternative_advantage=0.05)],
        CONTROL_STATE_FEATURE_NAMES,
        fallback_cap=fallback_cap,
        advantage_screen_multiplier=1.96,
    )
    np.testing.assert_allclose(
        insignificant[:, 0],
        np.full(n_paths, fallback_cap),
        rtol=0.0,
        atol=1.0e-15,
    )
    assert np.unique(insignificant[:, 0]).size == 1

    significant = _rollout_cap_policy(
        inputs,
        [constant_policy(alternative_advantage=0.50)],
        CONTROL_STATE_FEATURE_NAMES,
        fallback_cap=fallback_cap,
        advantage_screen_multiplier=1.96,
    )
    np.testing.assert_allclose(
        significant[:, 0],
        np.full(n_paths, alternative_cap),
        rtol=0.0,
        atol=1.0e-15,
    )
    assert np.unique(significant[:, 0]).size == 1


def test_flexible_policy_class_can_represent_one_fixed_cap_in_every_year():
    n_paths = 7
    n_years = 2
    inputs = ControlStateInputs(
        market_features=np.zeros((n_paths, n_years + 1, 5)),
        annual_reference_fund_return=np.zeros((n_paths, n_years)),
    )
    fallback_cap = 0.06
    fixed_cap = 0.08
    fixed_action = int(np.flatnonzero(np.isclose(ACTION_CAPS, fixed_cap))[0])
    raw = _control_state_paths(
        inputs, np.full((n_paths, n_years), fallback_cap)
    )
    policies = []
    for year in range(n_years):
        values = np.full((len(ACTION_CAPS), 1), -1.0)
        values[fixed_action, 0] = 1.0
        policies.append(_constant_first_year_policy(
            year=year,
            raw_state=raw[:, year, :],
            action_values=values,
            action_standard_errors=np.zeros(len(ACTION_CAPS)),
            feature_names=CONTROL_STATE_FEATURE_NAMES,
        ))

    caps = _rollout_cap_policy(
        inputs,
        policies,
        CONTROL_STATE_FEATURE_NAMES,
        fallback_cap=fallback_cap,
    )
    np.testing.assert_allclose(caps, fixed_cap, rtol=0.0, atol=1.0e-15)
