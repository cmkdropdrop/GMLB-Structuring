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
