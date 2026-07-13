"""Regression specification for the CSV-driven dynamic behaviour basis."""

from pathlib import Path

import numpy as np
import pytest

import agile_engine
from agile_engine import (
    BehaviourModel,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DynamicHazardFunction,
    FractionalLogitFunction,
    load_dynamic_behaviour_assumptions,
)


def test_repository_default_sources_are_cwd_independent():
    root = Path(__file__).resolve().parents[2]
    assert DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY == (
        root / "input_dynamic_behaviour").resolve()
    assert DEFAULT_COST_ASSUMPTIONS_PATH == (
        root / "input_cost_assumptions" / "cost_assumptions.csv").resolve()

    assumptions = load_dynamic_behaviour_assumptions()
    assert assumptions.behaviour.take_up.mode == "dynamic"
    assert assumptions.behaviour.use_dynamic
    assert assumptions.behaviour.use_dynamic_take_up
    assert assumptions.behaviour.use_dynamic_withdrawals
    assert assumptions.behaviour.withdrawals.free_utilisation == pytest.approx(0.25)
    assert assumptions.behaviour.withdrawals.excess_rate == pytest.approx(0.005)
    assert assumptions.source_metadata()["assumption_status"] == "uncalibrated_proxy"
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


def test_loaded_income_lapse_shortfall_response_is_ordered_low_base_high():
    """The versioned proxy bands increase lapse for the same economic state."""
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
        assert with_shortfall > without_shortfall
        probabilities.append(with_shortfall)

    assert probabilities[0] < probabilities[1] < probabilities[2]


def test_competing_performance_risk_is_separate_from_ordinary_base_lapse():
    dynamic = load_dynamic_behaviour_assumptions().behaviour.dynamic
    no_gap = dynamic.income_probability(
        0.0, 0.0, 100_000.0, 1.0, performance_shortfall=0.0
    )
    gap = dynamic.income_probability(
        0.0, 0.0, 100_000.0, 1.0, performance_shortfall=0.10
    )
    assert no_gap == 0.0
    assert gap > 0.04


def test_competing_lapse_causes_reconcile_and_aggregate_over_twelve_months():
    dynamic = load_dynamic_behaviour_assumptions().behaviour.dynamic
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


def test_performance_lapse_deadband_clip_and_lapse_scaling():
    behaviour = load_dynamic_behaviour_assumptions().behaviour
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
    dynamic = load_dynamic_behaviour_assumptions().behaviour.dynamic
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


def test_loaded_take_up_uses_only_current_anniversary_state_covariates():
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

    assert higher_account != pytest.approx(reference)
    assert higher_income != pytest.approx(reference)
    assert different_visible_returns != pytest.approx(reference)
    assert take_up.probability(**{**common, "base_annual": 0.0}) == 0.0
    assert take_up.probability(**{**common, "base_annual": 1.0}) == 1.0


def test_continue_benchmark_preserves_dynamic_election_but_removes_income_exit():
    behaviour = load_dynamic_behaviour_assumptions().behaviour
    benchmark = behaviour.without_post_election_behaviour()

    assert benchmark.take_up == behaviour.take_up
    assert benchmark.dynamic_take_up == behaviour.dynamic_take_up
    assert benchmark.use_dynamic_take_up
    assert benchmark.lapse.income_phase == 0.0
    assert not benchmark.dynamic.enabled
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


def test_csv_base_has_nonzero_premium_response_for_every_component():
    values = load_dynamic_behaviour_assumptions().values
    groups = (
        ("lapse", "growth"),
        ("lapse", "income"),
        ("income_take_up", "growth"),
        ("free_withdrawal_utilisation", "growth"),
        ("excess_withdrawal_rate", "all"),
    )
    for component, phase in groups:
        key = f"coefficient.{component}.{phase}.beta_log_premium"
        assert values[key] != 0.0


def test_lsmc_is_not_an_active_public_behaviour_path():
    assert "LSMCSettings" not in agile_engine.__all__
    assert "value_optimal_behaviour" not in agile_engine.__all__
    with pytest.raises(ValueError, match="archived"):
        BehaviourModel(regime="optimal")
