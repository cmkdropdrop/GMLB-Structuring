"""Focused tests for the pure crediting-cap capital arithmetic."""

from dataclasses import replace
import math

import pytest

from policy_engine.capital import CapitalStresses
from policy_engine.crediting_capital import (
    MLL_FRAMEWORK,
    adverse_csm_loss,
    aggregate_mll_capital,
    calculate_flexibility_delta,
    calculate_mll_capital,
    compare_capital_metrics,
    evaluate_capital_adjusted_csm,
    mll_correlation_matrix,
    model_point_mass_lapse_proxy,
)


def test_adverse_csm_loss_is_one_sided_and_uses_signed_csm():
    assert adverse_csm_loss(100.0, 70.0) == pytest.approx(30.0)
    assert adverse_csm_loss(100.0, 120.0) == 0.0
    assert adverse_csm_loss(-10.0, -25.0) == pytest.approx(15.0)
    with pytest.raises(ValueError, match="finite"):
        adverse_csm_loss(100.0, math.nan)
    with pytest.raises(TypeError, match="real number"):
        adverse_csm_loss(True, 90.0)


def test_mass_lapse_proxy_applies_positive_part_before_aggregation():
    result = model_point_mass_lapse_proxy(
        [100.0, -80.0, 20.0],
        [0.5, 0.25, 2.0],
        mass_lapse_rate=0.40,
    )
    # 40% * (0.5*100 + 0.25*0 + 2*20), not 40% of net portfolio CSM.
    assert result == pytest.approx(36.0)
    assert result != pytest.approx(0.40 * (50.0 - 20.0 + 40.0))


@pytest.mark.parametrize(
    "csms,weights,rate,error",
    [
        ([], [], 0.4, "At least one model point"),
        ([1.0], [1.0, 2.0], 0.4, "must align"),
        ([1.0], [-1.0], 0.4, "non-negative"),
        ([1.0], [0.0], 0.4, "must be positive"),
        ([1.0], [1.0], 1.1, "lie in"),
    ],
)
def test_mass_lapse_proxy_validates_inputs(csms, weights, rate, error):
    with pytest.raises(ValueError, match=error):
        model_point_mass_lapse_proxy(
            csms, weights, mass_lapse_rate=rate
        )


def test_mll_aggregation_uses_capital_stresses_submatrix():
    assert mll_correlation_matrix() == (
        (1.0, -0.25, 0.0),
        (-0.25, 1.0, 0.25),
        (0.0, 0.25, 1.0),
    )
    # 10^2 + 20^2 + 30^2 - .5*10*20 + .5*20*30 = 1600.
    assert aggregate_mll_capital(10.0, 20.0, 30.0) == pytest.approx(40.0)
    with pytest.raises(ValueError, match="non-negative"):
        aggregate_mll_capital(-1.0, 0.0, 0.0)


def test_mll_capital_selects_largest_lapse_stress_and_uses_custom_mass_rate():
    stresses = replace(CapitalStresses(), lapse_mass=0.25)
    result = calculate_mll_capital(
        base_csm=100.0,
        mortality_stressed_csm=95.0,
        longevity_stressed_csm=90.0,
        lapse_up_stressed_csm=40.0,
        lapse_down_stressed_csm=70.0,
        model_point_csms=[80.0, 20.0],
        model_point_weights=[1.0, 1.0],
        stresses=stresses,
    )
    assert result.mortality_loss == pytest.approx(5.0)
    assert result.longevity_loss == pytest.approx(10.0)
    assert result.lapse_up_loss == pytest.approx(60.0)
    assert result.lapse_down_loss == pytest.approx(30.0)
    assert result.mass_lapse_loss == pytest.approx(25.0)
    assert result.lapse_loss == pytest.approx(60.0)
    assert result.binding_lapse_stress == "lapse_up"
    assert result.capital == pytest.approx(
        aggregate_mll_capital(5.0, 10.0, 60.0, stresses=stresses)
    )
    assert result.framework == MLL_FRAMEWORK
    assert result.mass_lapse_rate == pytest.approx(0.25)
    assert result.mass_lapse_is_revaluation is False


def test_lapse_binding_tie_break_is_deterministic():
    result = calculate_mll_capital(
        base_csm=100.0,
        mortality_stressed_csm=100.0,
        longevity_stressed_csm=100.0,
        lapse_up_stressed_csm=60.0,
        lapse_down_stressed_csm=60.0,
        model_point_csms=[100.0],
        model_point_weights=[1.0],
    )
    assert result.lapse_loss == pytest.approx(40.0)
    assert result.binding_lapse_stress == "lapse_up"


def test_capital_adjusted_csm_is_robust_and_ratio_is_optional():
    metric = evaluate_capital_adjusted_csm(
        100.0, 20.0, capital_hurdle=0.10, capital_materiality=0.01
    )
    assert metric.capital_charge == pytest.approx(2.0)
    assert metric.capital_adjusted_csm == pytest.approx(98.0)
    assert metric.csm_to_capital == pytest.approx(5.0)

    immaterial = evaluate_capital_adjusted_csm(
        100.0, 0.01, capital_hurdle=0.10, capital_materiality=0.01
    )
    assert immaterial.csm_to_capital is None
    assert immaterial.capital_adjusted_csm == pytest.approx(99.999)

    onerous = evaluate_capital_adjusted_csm(
        -10.0, 5.0, capital_hurdle=0.10
    )
    assert onerous.capital_adjusted_csm == pytest.approx(-10.5)
    assert onerous.csm_to_capital == pytest.approx(-2.0)


@pytest.mark.parametrize(
    "csm,capital,hurdle,materiality,error",
    [
        (math.inf, 1.0, 0.1, 0.0, "finite"),
        (1.0, -1.0, 0.1, 0.0, "non-negative"),
        (1.0, 1.0, -0.1, 0.0, "non-negative"),
        (1.0, 1.0, 0.1, -1.0, "non-negative"),
    ],
)
def test_capital_adjusted_csm_validates_edge_cases(
    csm, capital, hurdle, materiality, error
):
    with pytest.raises(ValueError, match=error):
        evaluate_capital_adjusted_csm(
            csm,
            capital,
            capital_hurdle=hurdle,
            capital_materiality=materiality,
        )


def test_comparison_can_prefer_lower_csm_with_better_capital_efficiency():
    candidate = evaluate_capital_adjusted_csm(
        120.0, 100.0, capital_hurdle=0.10
    )
    comparator = evaluate_capital_adjusted_csm(
        115.0, 20.0, capital_hurdle=0.10
    )
    comparison = compare_capital_metrics(candidate, comparator)
    assert comparison.csm_delta == pytest.approx(5.0)
    assert comparison.capital_delta == pytest.approx(80.0)
    assert comparison.capital_charge_delta == pytest.approx(8.0)
    assert comparison.capital_adjusted_csm_delta == pytest.approx(-3.0)
    assert comparison.csm_to_capital_delta == pytest.approx(1.2 - 5.75)


def test_comparison_requires_one_metric_basis_and_preserves_missing_ratio():
    candidate = evaluate_capital_adjusted_csm(
        10.0, 0.0, capital_hurdle=0.10
    )
    comparator = evaluate_capital_adjusted_csm(
        9.0, 2.0, capital_hurdle=0.10
    )
    assert compare_capital_metrics(
        candidate, comparator
    ).csm_to_capital_delta is None

    other_hurdle = evaluate_capital_adjusted_csm(
        9.0, 2.0, capital_hurdle=0.20
    )
    with pytest.raises(ValueError, match="different capital hurdles"):
        compare_capital_metrics(candidate, other_hurdle)


def test_flexibility_delta_uses_best_fixed_capital_adjusted_csm():
    adaptive = evaluate_capital_adjusted_csm(
        100.0, 10.0, capital_hurdle=0.10
    )  # adjusted 99
    fixed = [
        evaluate_capital_adjusted_csm(
            96.0, 10.0, capital_hurdle=0.10
        ),  # adjusted 95
        evaluate_capital_adjusted_csm(
            100.0, 20.0, capital_hurdle=0.10
        ),  # adjusted 98
    ]
    result = calculate_flexibility_delta(adaptive, fixed)
    assert result.best_fixed_index == 1
    assert result.best_fixed is fixed[1]
    assert result.capital_adjusted_csm_delta == pytest.approx(1.0)
    assert result.comparison.csm_delta == pytest.approx(0.0)
    assert result.comparison.capital_delta == pytest.approx(-10.0)

    with pytest.raises(ValueError, match="At least one fixed"):
        calculate_flexibility_delta(adaptive, [])


def test_flexibility_fixed_tie_break_and_portfolio_scaling_are_stable():
    fixed_first = evaluate_capital_adjusted_csm(
        100.0, 20.0, capital_hurdle=0.10
    )
    fixed_second = evaluate_capital_adjusted_csm(
        99.0, 10.0, capital_hurdle=0.10
    )
    adaptive = evaluate_capital_adjusted_csm(
        101.0, 20.0, capital_hurdle=0.10
    )
    result = calculate_flexibility_delta(
        adaptive, [fixed_first, fixed_second]
    )
    assert fixed_first.capital_adjusted_csm == pytest.approx(
        fixed_second.capital_adjusted_csm
    )
    assert result.best_fixed_index == 0

    scaled = evaluate_capital_adjusted_csm(
        1_010.0, 200.0, capital_hurdle=0.10
    )
    assert scaled.capital_adjusted_csm == pytest.approx(
        10.0 * adaptive.capital_adjusted_csm
    )
    assert scaled.csm_to_capital == pytest.approx(adaptive.csm_to_capital)
