"""Focused tests for the pure crediting-cap capital arithmetic."""

from dataclasses import replace
import math

import numpy as np
import pytest

from policy_engine.capital import CapitalStresses
from policy_engine.crediting_capital import (
    MLL_FRAMEWORK,
    PolicyCSMPathArrays,
    adverse_csm_loss,
    aggregate_mll_capital,
    calculate_flexibility_delta,
    calculate_mll_capital,
    calculate_policy_level_csm_mll,
    compare_capital_metrics,
    evaluate_capital_adjusted_csm,
    mll_correlation_matrix,
    model_point_mass_lapse_proxy,
    paired_bootstrap_ratio_delta,
    score_lsmc_value_vectors,
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


def test_policy_level_ratio_can_reject_higher_csm_with_worse_mll():
    higher_csm = calculate_policy_level_csm_mll(
        base_csm=120.0,
        mortality_stressed_csm=60.0,
        longevity_stressed_csm=60.0,
        lapse_up_stressed_csm=60.0,
        lapse_down_stressed_csm=60.0,
        model_point_csms=[1.0],
        model_point_weights=[1.0],
    )
    lower_csm = calculate_policy_level_csm_mll(
        base_csm=100.0,
        mortality_stressed_csm=90.0,
        longevity_stressed_csm=90.0,
        lapse_up_stressed_csm=90.0,
        lapse_down_stressed_csm=90.0,
        model_point_csms=[1.0],
        model_point_weights=[1.0],
    )
    assert higher_csm.csm > lower_csm.csm
    assert higher_csm.mll_capital > lower_csm.mll_capital
    assert higher_csm.csm_to_mll_ratio < lower_csm.csm_to_mll_ratio


def test_policy_level_ratio_is_none_at_materiality_and_mass_lapse_has_no_netting():
    immaterial = calculate_policy_level_csm_mll(
        base_csm=100.0,
        mortality_stressed_csm=100.0,
        longevity_stressed_csm=100.0,
        lapse_up_stressed_csm=100.0,
        lapse_down_stressed_csm=100.0,
        model_point_csms=[-20.0],
        model_point_weights=[1.0],
        capital_materiality=0.0,
    )
    assert immaterial.mll_capital == 0.0
    assert immaterial.csm_to_mll_ratio is None

    mass_lapse = calculate_policy_level_csm_mll(
        base_csm=20.0,
        mortality_stressed_csm=20.0,
        longevity_stressed_csm=20.0,
        lapse_up_stressed_csm=20.0,
        lapse_down_stressed_csm=20.0,
        model_point_csms=[100.0, -80.0],
        model_point_weights=[1.0, 1.0],
    )
    assert mass_lapse.mll.mass_lapse_loss == pytest.approx(40.0)
    assert mass_lapse.mll_capital == pytest.approx(40.0)
    assert mass_lapse.mll.mass_lapse_loss != pytest.approx(
        0.40 * (100.0 - 80.0)
    )


def test_lsmc_value_score_preserves_leading_dimensions_and_scaling():
    # Base CSM = (80 + 20 + 10 + 5 + 5) - (10 + 3 + 4 + 3) = 100.
    vector = np.asarray([
        80.0, 20.0, 10.0, 5.0, 5.0,
        10.0, 3.0, 4.0, 3.0,
        80.0, 85.0, 70.0, 75.0,
        60.0, -10.0,
    ])
    values = np.stack((vector, 10.0 * vector)).reshape(1, 2, -1)
    score = score_lsmc_value_vectors(
        values,
        model_point_weights=[0.5, 2.0],
    )
    assert np.asarray(score.csm).shape == (1, 2)
    assert np.asarray(score.mll_capital).shape == (1, 2)
    assert np.asarray(score.csm_to_mll_ratio).shape == (1, 2)
    assert score.csm[0, 0] == pytest.approx(100.0)
    assert score.csm[0, 1] == pytest.approx(1_000.0)
    assert score.mll_capital[0, 1] == pytest.approx(
        10.0 * score.mll_capital[0, 0]
    )
    assert score.csm_to_mll_ratio[0, 1] == pytest.approx(
        score.csm_to_mll_ratio[0, 0]
    )

    scalar_immaterial = score_lsmc_value_vectors(
        [100.0, 0.0, 0.0, 0.0, 0.0,
         0.0, 0.0, 0.0, 0.0,
         100.0, 100.0, 100.0, 100.0,
         -1.0],
        capital_materiality=0.0,
    )
    assert scalar_immaterial.mll_capital == 0.0
    assert scalar_immaterial.csm_to_mll_ratio is None


def test_lsmc_value_score_rejects_nonfinite_and_bad_shapes():
    with pytest.raises(ValueError, match="at least one model-point"):
        score_lsmc_value_vectors(np.zeros(13))
    invalid = np.zeros(14)
    invalid[-1] = np.nan
    with pytest.raises(ValueError, match="finite"):
        score_lsmc_value_vectors(invalid)
    with pytest.raises(ValueError, match="one value per model-point"):
        score_lsmc_value_vectors(np.zeros(15), model_point_weights=[1.0])


def _constant_policy_paths(
    *, base: float, loss: float, n_paths: int = 24
) -> PolicyCSMPathArrays:
    common_noise = np.linspace(-1.0, 1.0, n_paths)
    base_paths = base + common_noise
    stressed = base - loss + common_noise
    return PolicyCSMPathArrays(
        base_csm_paths=base_paths,
        mortality_stressed_csm_paths=stressed,
        longevity_stressed_csm_paths=stressed,
        lapse_up_stressed_csm_paths=stressed,
        lapse_down_stressed_csm_paths=stressed,
        model_point_base_csm_paths=np.ones((n_paths, 1)),
    )


def test_paired_bootstrap_identical_policies_have_exact_zero_delta():
    policy = _constant_policy_paths(base=100.0, loss=20.0)
    result = paired_bootstrap_ratio_delta(
        policy,
        policy,
        n_resamples=250,
        seed=1234,
    )
    assert result.estimate == pytest.approx(0.0)
    assert result.standard_error == pytest.approx(0.0)
    assert result.ci_lower == pytest.approx(0.0)
    assert result.ci_upper == pytest.approx(0.0)
    assert result.positive_gate_passed is False
    assert result.negative_gate_passed is False


def test_paired_bootstrap_has_clear_positive_and_negative_ratio_gates():
    efficient = _constant_policy_paths(base=120.0, loss=10.0)
    inefficient = _constant_policy_paths(base=100.0, loss=20.0)
    positive = paired_bootstrap_ratio_delta(
        efficient,
        inefficient,
        n_resamples=400,
        seed=2026,
    )
    repeated = paired_bootstrap_ratio_delta(
        efficient,
        inefficient,
        n_resamples=400,
        seed=2026,
    )
    assert positive == repeated
    assert positive.estimate > 0.0
    assert positive.ci_lower > 0.0
    assert positive.positive_gate_passed is True
    assert positive.negative_gate_passed is False

    negative = paired_bootstrap_ratio_delta(
        inefficient,
        efficient,
        n_resamples=400,
        seed=2026,
    )
    assert negative.estimate < 0.0
    assert negative.ci_upper < 0.0
    assert negative.positive_gate_passed is False
    assert negative.negative_gate_passed is True
