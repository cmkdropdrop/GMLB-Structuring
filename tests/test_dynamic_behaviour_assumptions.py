"""Regression specification for the CSV-driven dynamic behaviour basis."""

from pathlib import Path

import numpy as np
import pytest

import policy_engine
from policy_engine import (
    BehaviourModel,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DynamicHazardFunction,
    DynamicTakeUpParams,
    FractionalLogitFunction,
    load_dynamic_behaviour_assumptions,
)
from policy_engine.behavior import DynamicLapseParams


def test_repository_default_sources_are_cwd_independent(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    assert DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY == (
        root / "input_data" / "dynamic_behaviour").resolve()
    assert DEFAULT_COST_ASSUMPTIONS_PATH == (
        root / "input_data" / "cost_assumptions" / "cost_assumptions.csv").resolve()

    monkeypatch.chdir(tmp_path)
    assumptions = load_dynamic_behaviour_assumptions()
    assert assumptions.behaviour.take_up.mode == "dynamic"
    assert assumptions.behaviour.use_dynamic
    assert assumptions.behaviour.use_dynamic_take_up
    assert assumptions.behaviour.use_dynamic_withdrawals
    assert assumptions.assumption_set_id == "dynamic_proxy_2026-07-13_v2"
    assert assumptions.behaviour.lapse.growth_phase == (0.0,)
    assert assumptions.behaviour.withdrawals.free_utilisation == 0.0
    assert assumptions.behaviour.withdrawals.excess_rate == pytest.approx(0.005)
    assert assumptions.behaviour.take_up.force_by_year is None
    metadata = assumptions.source_metadata()
    assert metadata["assumption_status"] == "mixed"
    assert metadata["assumption_statuses"] == [
        "contractual_constraint",
        "uncalibrated_proxy",
    ]
    assert set(assumptions.source_sha256) == {"baselines", "coefficients"}


def test_proportional_hazard_is_anchored_and_aggregates_exactly():
    function = DynamicHazardFunction(
        beta_moneyness=-1.5,
        beta_log_premium=-0.1,
        beta_interaction=-0.5,
        moneyness_transform="positive_part",
    )
    base = 0.12
    annual = function.annual_probability(base, 0.0, 100_000.0)
    monthly = function.step_probability(base, 0.0, 100_000.0, 1.0 / 12.0)
    assert annual == pytest.approx(base)
    assert 1.0 - (1.0 - monthly) ** 12 == pytest.approx(annual)
    assert function.annual_probability(base, 0.3, 200_000.0) < annual
    assert function.annual_probability(0.0, 0.3, 200_000.0) == 0.0


def test_performance_lapse_is_disabled_in_low_but_active_in_base_and_high():
    """The configured cap-gap cause is active in the central projection basis."""
    fixed_base_lapse = 0.005
    fixed_moneyness = 0.0
    fixed_premium = 100_000.0
    shortfall = 0.10

    probabilities = []
    for value_basis in ("low", "base", "high"):
        dynamic = load_dynamic_behaviour_assumptions(
            value_basis=value_basis
        ).behaviour.dynamic
        without_shortfall = dynamic.income_probability(
            fixed_base_lapse,
            fixed_moneyness,
            fixed_premium,
            1.0,
            performance_shortfall=0.0,
        )
        with_shortfall = dynamic.income_probability(
            fixed_base_lapse,
            fixed_moneyness,
            fixed_premium,
            1.0,
            performance_shortfall=shortfall,
        )
        assert without_shortfall == pytest.approx(fixed_base_lapse)
        probabilities.append(with_shortfall)

    assert probabilities[0] == pytest.approx(fixed_base_lapse)
    assert probabilities[1] > fixed_base_lapse
    assert probabilities[2] > fixed_base_lapse


def test_competing_performance_risk_is_separate_from_ordinary_base_lapse():
    dynamic = load_dynamic_behaviour_assumptions(
        value_basis="high"
    ).behaviour.dynamic
    no_gap = dynamic.income_probability(
        0.0, 0.0, 100_000.0, 1.0, performance_shortfall=0.0
    )
    gap = dynamic.income_probability(
        0.0, 0.0, 100_000.0, 1.0, performance_shortfall=0.10
    )
    assert no_gap == 0.0
    assert gap > 0.04


def test_competing_lapse_causes_reconcile_and_aggregate_over_twelve_months():
    dynamic = load_dynamic_behaviour_assumptions(
        value_basis="high"
    ).behaviour.dynamic
    ordinary_month, performance_month = dynamic.income_cause_probabilities(
        0.005,
        0.0,
        100_000.0,
        1.0 / 12.0,
        performance_shortfall=0.10,
    )
    annual = dynamic.income_probability(
        0.005, 0.0, 100_000.0, 1.0, performance_shortfall=0.10
    )
    assert ordinary_month > 0.0
    assert performance_month > 0.0
    assert 1.0 - (1.0 - ordinary_month - performance_month) ** 12 \
        == pytest.approx(annual)


def test_combined_cap_cannot_reduce_a_certain_ordinary_exit():
    dynamic = load_dynamic_behaviour_assumptions().behaviour.dynamic
    ordinary, performance = dynamic.income_cause_probabilities(
        1.0,
        0.0,
        100_000.0,
        1.0 / 12.0,
        performance_shortfall=0.30,
    )

    assert ordinary == 1.0
    assert performance == 0.0
    assert dynamic.income_probability(
        1.0,
        0.0,
        100_000.0,
        1.0 / 12.0,
        performance_shortfall=0.30,
    ) == 1.0


def test_cause_probabilities_remain_nonnegative_on_a_signal_grid():
    moneyness, gap = np.meshgrid(
        np.linspace(-np.log(2.0), np.log(2.0), 41),
        np.linspace(0.0, 0.50, 21),
    )
    for basis in ("low", "base", "high"):
        dynamic = load_dynamic_behaviour_assumptions(
            value_basis=basis
        ).behaviour.dynamic
        ordinary, performance = dynamic.income_cause_probabilities(
            0.005,
            moneyness,
            100_000.0,
            1.0 / 12.0,
            performance_shortfall=gap,
        )
        total = dynamic.income_probability(
            0.005,
            moneyness,
            100_000.0,
            1.0 / 12.0,
            performance_shortfall=gap,
        )
        assert np.all(np.asarray(ordinary) >= 0.0)
        assert np.all(np.asarray(performance) >= 0.0)
        np.testing.assert_allclose(
            np.asarray(ordinary) + np.asarray(performance),
            total,
            rtol=0.0,
            atol=1.0e-15,
        )


@pytest.mark.parametrize("base", [-0.1, 1.1, np.nan])
def test_disabled_lapse_rejects_invalid_base_probability(base):
    dynamic = DynamicLapseParams(enabled=False)
    with pytest.raises(ValueError, match="Base hazard probabilities"):
        dynamic.income_probability(base, 0.0, 100_000.0, 1.0 / 12.0)


@pytest.mark.parametrize("dt", [0.0, 1.1, np.nan])
def test_disabled_lapse_rejects_invalid_time_step(dt):
    dynamic = DynamicLapseParams(enabled=False)
    with pytest.raises(ValueError, match="time step"):
        dynamic.growth_probability(0.05, 0.0, 100_000.0, dt)


def test_performance_lapse_deadband_clip_and_lapse_scaling():
    behaviour = load_dynamic_behaviour_assumptions(
        value_basis="high"
    ).behaviour
    dynamic = behaviour.dynamic
    at_deadband = dynamic.income_probability(
        0.0, 0.0, 100_000.0, 1.0, performance_shortfall=0.02
    )
    clipped = dynamic.income_probability(
        0.0, 0.0, 100_000.0, 1.0, performance_shortfall=0.32
    )
    beyond_clip = dynamic.income_probability(
        0.0, 0.0, 100_000.0, 1.0, performance_shortfall=3.00
    )
    assert at_deadband == 0.0
    assert clipped == pytest.approx(beyond_clip)

    zero_stress = behaviour.scaled_lapses(0.0)
    assert zero_stress.dynamic.income_probability(
        0.0, 0.0, 100_000.0, 1.0, performance_shortfall=0.30
    ) == 0.0
    assert behaviour.scaled_lapses(1.5).dynamic.performance.excess_hazard_cap \
        == pytest.approx(1.5 * dynamic.performance.excess_hazard_cap)


def test_signed_moneyness_and_common_retention_have_expected_directions():
    dynamic = load_dynamic_behaviour_assumptions(
        value_basis="high"
    ).behaviour.dynamic
    ordinary_otm = dynamic.income_probability(
        0.005, -0.40, 100_000.0, 1.0, performance_shortfall=0.0
    )
    ordinary_atm = dynamic.income_probability(
        0.005, 0.0, 100_000.0, 1.0, performance_shortfall=0.0
    )
    gap_atm = dynamic.income_probability(
        0.005, 0.0, 100_000.0, 1.0, performance_shortfall=0.10
    )
    gap_itm = dynamic.income_probability(
        0.005, np.log(2.0), 100_000.0, 1.0,
        performance_shortfall=0.10,
    )
    assert ordinary_otm > ordinary_atm
    assert gap_atm > ordinary_atm
    assert gap_itm < gap_atm


def test_take_up_hazard_uses_market_and_gross_premium_covariates():
    function = DynamicHazardFunction(
        beta_moneyness=4.0,
        beta_log_premium=0.5,
        beta_interaction=0.25,
        moneyness_transform="signed",
        annual_cap=0.5,
        multiplier_floor=0.05,
        multiplier_cap=25.0,
    )
    base = 0.10
    reference = function.annual_probability(base, 0.0, 100_000.0)
    assert function.annual_probability(base, 0.2, 100_000.0) > reference
    assert function.annual_probability(base, 0.0, 200_000.0) > reference


def test_loaded_take_up_uses_governed_moneyness_and_performance_gap_covariates():
    take_up = load_dynamic_behaviour_assumptions().behaviour.dynamic_take_up
    common = dict(
        base_annual=0.10,
        log_guarantee_moneyness=0.0,
        premium=100_000.0,
        account_value=100_000.0,
        prospective_annual_income=8_000.0,
        previous_reference_return=0.06,
        previous_credited_return=0.04,
        performance_gap=0.02,
    )
    reference = take_up.probability(**common)
    higher_account = take_up.probability(
        **{**common, "account_value": 120_000.0}
    )
    higher_income = take_up.probability(
        **{**common, "prospective_annual_income": 10_000.0}
    )
    different_visible_returns = take_up.probability(
        **{
            **common,
            "previous_reference_return": 0.12,
            "previous_credited_return": 0.02,
            "performance_gap": 0.10,
        }
    )
    higher_moneyness = take_up.probability(
        **{**common, "log_guarantee_moneyness": 0.20}
    )
    higher_premium = take_up.probability(
        **{**common, "premium": 200_000.0}
    )

    assert higher_account == pytest.approx(reference)
    assert higher_income == pytest.approx(reference)
    assert different_visible_returns > reference
    assert higher_premium == pytest.approx(reference)
    assert higher_moneyness > reference
    assert take_up.probability(**{**common, "base_annual": 0.0}) == 0.0
    assert take_up.probability(**{**common, "base_annual": 1.0}) == 1.0


def test_take_up_caps_the_complete_relative_hazard_once():
    function = DynamicHazardFunction(
        beta_moneyness=0.0,
        beta_log_premium=0.0,
        beta_interaction=0.0,
        annual_cap=1.0,
        multiplier_floor=0.05,
        multiplier_cap=25.0,
    )
    take_up = DynamicTakeUpParams(
        function=function,
        beta_log_account_value=10.0,
    )
    probability = take_up.probability(
        0.10,
        0.0,
        100_000.0,
        account_value=1.0,
    )
    expected_floor_probability = 1.0 - (1.0 - 0.10) ** 0.05
    assert probability == pytest.approx(expected_floor_probability)


def test_continue_benchmark_preserves_dynamic_election_but_removes_income_exit():
    behaviour = load_dynamic_behaviour_assumptions().behaviour
    benchmark = behaviour.without_post_election_behaviour()

    assert benchmark.take_up == behaviour.take_up
    assert benchmark.dynamic_take_up == behaviour.dynamic_take_up
    assert benchmark.use_dynamic_take_up
    assert benchmark.lapse.income_phase == 0.0
    assert not benchmark.dynamic.enabled
    assert not benchmark.dynamic_withdrawals.enabled
    assert not benchmark.use_dynamic_withdrawals
    assert benchmark.withdrawals.free_utilisation == 0.0
    assert benchmark.withdrawals.excess_rate == 0.0


def test_fractional_logit_uses_market_premium_and_mva():
    function = FractionalLogitFunction(
        beta_moneyness=0.5,
        beta_log_premium=-0.25,
        beta_interaction=-0.1,
        beta_mva=-2.0,
        moneyness_transform="positive_part",
    )
    base = 0.25
    reference = function.response(base, 0.0, 100_000.0, 0.0)
    assert reference == pytest.approx(base)
    assert function.response(base, 0.3, 100_000.0, 0.0) > reference
    assert function.response(base, 0.0, 200_000.0, 0.0) < reference
    assert function.response(base, 0.0, 100_000.0, 0.1) < reference
    assert np.isfinite(function.response(base, 1e6, 1e12, 1.0))
    with pytest.raises(ValueError, match="MVA signal"):
        function.response(base, 0.0, 100_000.0, -0.01)
    with pytest.raises(ValueError, match="MVA signal"):
        function.response(base, 0.0, 100_000.0, 1.01)


def test_loaded_excess_withdrawal_uses_signed_moneyness_and_mva():
    withdrawals = (
        load_dynamic_behaviour_assumptions().behaviour.dynamic_withdrawals
    )
    base = 0.005
    out_of_money = withdrawals.excess_rate(base, -0.40, 100_000.0, 0.0)
    at_money = withdrawals.excess_rate(base, 0.0, 100_000.0, 0.0)
    in_the_money = withdrawals.excess_rate(base, 0.40, 100_000.0, 0.0)
    with_mva = withdrawals.excess_rate(base, 0.0, 100_000.0, 0.10)

    assert out_of_money > at_money > in_the_money
    assert with_mva < at_money


def test_csv_base_activates_only_governed_covariates():
    values = load_dynamic_behaviour_assumptions().values
    zero_parameters = (
        "coefficient.lapse.growth.beta_moneyness",
        "coefficient.lapse.income.beta_log_premium",
        "coefficient.lapse.income.beta_interaction",
        "coefficient.income_take_up.growth.beta_log_premium",
        "coefficient.income_take_up.growth.beta_interaction",
        "coefficient.income_take_up.growth.beta_log_account_value",
        "coefficient.income_take_up.growth.beta_prospective_income_ratio",
        "coefficient.income_take_up.growth.beta_reference_return",
        "coefficient.income_take_up.growth.beta_credited_return",
        "coefficient.free_withdrawal_utilisation.growth.beta_mva",
        "coefficient.excess_withdrawal_rate.all.beta_log_premium",
        "coefficient.excess_withdrawal_rate.all.beta_interaction",
    )
    for key in zero_parameters:
        assert values[key] == 0.0
    assert values["coefficient.lapse.income.beta_moneyness"] == -1.5
    assert values["coefficient.income_take_up.growth.beta_moneyness"] == 4.0
    assert values[
        "coefficient.income_take_up.growth.beta_performance_gap"
    ] == 4.0
    assert values[
        "coefficient.excess_withdrawal_rate.all.beta_moneyness"
    ] == -0.5
    assert values["coefficient.excess_withdrawal_rate.all.beta_mva"] == -2.0
    assert (
        load_dynamic_behaviour_assumptions()
        .behaviour.dynamic_withdrawals.excess.moneyness_transform
        == "signed"
    )


def test_lsmc_is_not_an_active_public_behaviour_path():
    assert "LSMCSettings" not in policy_engine.__all__
    assert "value_optimal_behaviour" not in policy_engine.__all__
    with pytest.raises(ValueError, match="archived"):
        BehaviourModel(regime="optimal")
    assert BehaviourModel().regime == "static"
