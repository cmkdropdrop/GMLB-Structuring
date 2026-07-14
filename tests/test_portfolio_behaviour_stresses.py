"""Focused contracts for permanent, cache-neutral lapse stresses."""

from __future__ import annotations

import pytest

from policy_engine.behavior import BehaviourModel, LapseAssumptions
from policy_engine.portfolio_stresses import (
    PORTFOLIO_NON_BEHAVIOUR_STRESS_CHOICES,
    PORTFOLIO_STRESSES,
    PORTFOLIO_STRESS_CHOICES,
    PortfolioStressDefinition,
    apply_portfolio_behaviour_stress,
    get_portfolio_stress,
    portfolio_scenario_transform,
)
from portfolio_simulations.run_portfolio_valuation import (
    parse_args as parse_dynamic_args,
)
from portfolio_simulations.run_portfolio_valuation_lsmc import (
    parse_args as parse_lsmc_args,
)


@pytest.mark.parametrize(
    ("stress_id", "expected_multiplier"),
    (("lapse_up", 1.50), ("lapse_down", 0.50)),
)
def test_permanent_lapse_stresses_are_cache_neutral_behaviour_transforms(
    stress_id: str,
    expected_multiplier: float,
) -> None:
    definition = get_portfolio_stress(stress_id)

    assert definition.risk_category == "lapse"
    assert definition.input_transform == "none"
    assert definition.behaviour_transform == "scale_lapses"
    assert definition.scenario_transform == "none"
    assert definition.parameters["lapse_multiplier"] == pytest.approx(
        expected_multiplier
    )
    assert portfolio_scenario_transform(definition) is None
    assert definition.to_dict()["behaviour_transform"] == "scale_lapses"


@pytest.mark.parametrize(
    ("stress_id", "expected_multiplier"),
    (("lapse_up", 1.50), ("lapse_down", 0.50)),
)
def test_lapse_stress_scales_ordinary_and_performance_causes(
    stress_id: str,
    expected_multiplier: float,
) -> None:
    behaviour = BehaviourModel(
        regime="dynamic",
        lapse=LapseAssumptions(
            growth_phase=(0.0, 0.02, 0.04),
            income_phase=0.01,
        ),
    )
    original_performance_cap = behaviour.dynamic.performance.excess_hazard_cap

    stressed = apply_portfolio_behaviour_stress(stress_id, behaviour)

    assert stressed is not behaviour
    assert stressed.regime == "dynamic"
    assert stressed.lapse.growth_phase == pytest.approx(
        (0.0, 0.02 * expected_multiplier, 0.04 * expected_multiplier)
    )
    assert stressed.lapse.income_phase == pytest.approx(
        0.01 * expected_multiplier
    )
    assert stressed.dynamic.performance.excess_hazard_cap == pytest.approx(
        original_performance_cap * expected_multiplier
    )
    assert stressed.take_up is behaviour.take_up
    assert stressed.dynamic_take_up is behaviour.dynamic_take_up
    assert stressed.dynamic_withdrawals is behaviour.dynamic_withdrawals

    assert behaviour.lapse.growth_phase == (0.0, 0.02, 0.04)
    assert behaviour.lapse.income_phase == pytest.approx(0.01)
    assert behaviour.dynamic.performance.excess_hazard_cap == pytest.approx(
        original_performance_cap
    )


@pytest.mark.parametrize("stress_id", ("base", "longevity", "mortality"))
def test_non_behaviour_stress_preserves_behaviour_object(stress_id: str) -> None:
    behaviour = BehaviourModel(regime="dynamic")

    assert apply_portfolio_behaviour_stress(stress_id, behaviour) is behaviour


@pytest.mark.parametrize("stress_id", ("lapse_up", "lapse_down"))
def test_dynamic_portfolio_reader_accepts_lapse_stress(stress_id: str) -> None:
    args = parse_dynamic_args(("--stress-scenario", stress_id))

    assert args.stress_scenario == stress_id


@pytest.mark.parametrize("stress_id", ("lapse_up", "lapse_down"))
def test_lsmc_portfolio_reader_rejects_dynamic_lapse_stress(
    stress_id: str,
) -> None:
    assert stress_id not in PORTFOLIO_NON_BEHAVIOUR_STRESS_CHOICES

    with pytest.raises(SystemExit):
        parse_lsmc_args(("--stress-scenario", stress_id))


def test_no_mass_lapse_stress_is_exposed() -> None:
    assert "lapse_up" in PORTFOLIO_STRESS_CHOICES
    assert "lapse_down" in PORTFOLIO_STRESS_CHOICES
    assert "lapse_mass" not in PORTFOLIO_STRESSES


def test_unknown_behaviour_transform_is_rejected() -> None:
    definition = PortfolioStressDefinition(
        stress_id="unsupported_behaviour",
        risk_category="behaviour",
        label="Unsupported behaviour transform",
        description="Test-only unsupported transform.",
        behaviour_transform="unsupported",
    )

    with pytest.raises(ValueError, match="Unsupported behaviour transform"):
        apply_portfolio_behaviour_stress(
            definition,
            BehaviourModel(regime="dynamic"),
        )
