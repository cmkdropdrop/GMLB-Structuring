"""Pure crediting-cap capital arithmetic for research comparisons.

The functions in this module consume signed CSM proxy values produced by
separate base and stress revaluations.  They do not build market scenarios,
price hedges, read or write caches, or trigger any valuation runner.  This
keeps the arithmetic usable by a strict cache-reading orchestrator without
creating a second route for risk-neutral path generation.

Only mortality, longevity and lapse (``MLL``) risk are aggregated.  The result
is a deliberately partial life-risk research proxy.  It is not total SCR,
APRA/LAGIC capital, Solvency II regulatory capital, an IFRS 17 Risk Adjustment
or recognised IFRS 17 CSM.  In particular, market, expense, catastrophe,
operational, concentration, tax-absorption and diversification effects outside
the MLL submatrix are absent.

The mass-lapse amount is also a proxy rather than a shock revaluation.  It is
calculated model point by model point as the configured mass-lapse fraction of
positive signed CSM, before portfolio aggregation.  This prevents onerous
model points from offsetting profitable future margins assumed lost in a mass
lapse, but it does not reproduce surrender cashflows, MVA or event expenses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from numbers import Real
from typing import Optional, Sequence

from .capital import CapitalStresses


MLL_FRAMEWORK = "MLL_LIFE_RISK_RESEARCH_PROXY_NOT_REGULATORY_CAPITAL"
MASS_LAPSE_METHOD = "positive_model_point_csm_proxy_not_revaluation"
MLL_LABELS = ("mortality", "longevity", "lapse")
LAPSE_STRESS_ORDER = ("lapse_up", "lapse_down", "mass_lapse")


def _finite_float(value: Real, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number, not {type(value).__name__}.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _nonnegative_float(value: Real, name: str) -> float:
    result = _finite_float(value, name)
    if result < 0.0:
        raise ValueError(f"{name} must be non-negative.")
    return result


def _resolve_stresses(stresses: Optional[CapitalStresses]) -> CapitalStresses:
    if stresses is None:
        return CapitalStresses()
    if not isinstance(stresses, CapitalStresses):
        raise TypeError("stresses must be a CapitalStresses instance or None.")
    return stresses


def adverse_csm_loss(base_csm: Real, stressed_csm: Real) -> float:
    """Return the one-sided loss in signed CSM under one stress.

    A stress that increases signed CSM is favourable and therefore contributes
    zero capital.  Signed CSM is intentionally not clipped at zero before the
    comparison: a stress can make an already onerous portfolio more onerous.
    """

    base = _finite_float(base_csm, "base_csm")
    stressed = _finite_float(stressed_csm, "stressed_csm")
    return max(0.0, base - stressed)


def model_point_mass_lapse_proxy(
    model_point_csms: Sequence[Real],
    model_point_weights: Sequence[Real],
    *,
    mass_lapse_rate: Real = 0.40,
) -> float:
    """Return a modelpoint-wise positive-value mass-lapse proxy.

    ``model_point_weights`` define the caller's aggregation basis and are not
    normalised here.  They may therefore be contract weights, represented
    contract counts or another consistently applied non-negative exposure
    measure.  At least one strictly positive weight is required.
    """

    if isinstance(model_point_csms, (str, bytes)) or isinstance(
        model_point_weights, (str, bytes)
    ):
        raise TypeError("model-point CSMs and weights must be numeric sequences.")
    try:
        csms = tuple(
            _finite_float(value, f"model_point_csms[{index}]")
            for index, value in enumerate(model_point_csms)
        )
        weights = tuple(
            _nonnegative_float(value, f"model_point_weights[{index}]")
            for index, value in enumerate(model_point_weights)
        )
    except TypeError as exc:
        if "not iterable" in str(exc):
            raise TypeError(
                "model-point CSMs and weights must be numeric sequences."
            ) from exc
        raise
    if not csms:
        raise ValueError("At least one model point is required.")
    if len(csms) != len(weights):
        raise ValueError("model_point_csms and model_point_weights must align.")
    if not any(weight > 0.0 for weight in weights):
        raise ValueError("At least one model-point weight must be positive.")

    rate = _finite_float(mass_lapse_rate, "mass_lapse_rate")
    if not 0.0 <= rate <= 1.0:
        raise ValueError("mass_lapse_rate must lie in [0, 1].")
    positive_value = math.fsum(
        weight * max(csm, 0.0) for csm, weight in zip(csms, weights)
    )
    return rate * positive_value


def mll_correlation_matrix(
    stresses: Optional[CapitalStresses] = None,
) -> tuple[tuple[float, float, float], ...]:
    """Extract the mortality/longevity/lapse submatrix by label.

    Label-based extraction prevents a silent result change if a future
    ``CapitalStresses`` implementation reorders the complete life matrix.
    """

    resolved = _resolve_stresses(stresses)
    labels = tuple(str(label) for label in resolved.corr_life_labels)
    missing = tuple(label for label in MLL_LABELS if label not in labels)
    if missing:
        raise ValueError(
            "CapitalStresses.corr_life_labels is missing MLL labels: "
            + ", ".join(missing)
        )
    indices = tuple(labels.index(label) for label in MLL_LABELS)
    matrix = tuple(
        tuple(
            _finite_float(
                resolved.corr_life[row][column],
                f"corr_life[{row}][{column}]",
            )
            for column in indices
        )
        for row in indices
    )
    return matrix


def aggregate_mll_capital(
    mortality_loss: Real,
    longevity_loss: Real,
    lapse_loss: Real,
    *,
    stresses: Optional[CapitalStresses] = None,
) -> float:
    """Aggregate non-negative MLL stand-alone losses by correlation."""

    vector = (
        _nonnegative_float(mortality_loss, "mortality_loss"),
        _nonnegative_float(longevity_loss, "longevity_loss"),
        _nonnegative_float(lapse_loss, "lapse_loss"),
    )
    correlation = mll_correlation_matrix(stresses)
    quadratic = math.fsum(
        vector[row] * correlation[row][column] * vector[column]
        for row in range(3)
        for column in range(3)
    )
    scale = max(1.0, math.fsum(vector) ** 2)
    tolerance = 1.0e-12 * scale
    if quadratic < -tolerance:
        raise ValueError(
            "The MLL correlation quadratic form is materially negative."
        )
    return math.sqrt(max(0.0, quadratic))


@dataclass(frozen=True)
class MLLCapitalResult:
    """Standalone losses and correlated MLL capital for one cap policy."""

    mortality_loss: float
    longevity_loss: float
    lapse_up_loss: float
    lapse_down_loss: float
    mass_lapse_loss: float
    lapse_loss: float
    binding_lapse_stress: str
    capital: float
    mass_lapse_rate: float
    framework: str = field(default=MLL_FRAMEWORK, init=False)
    mass_lapse_method: str = field(default=MASS_LAPSE_METHOD, init=False)
    mass_lapse_is_revaluation: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        names = (
            "mortality_loss",
            "longevity_loss",
            "lapse_up_loss",
            "lapse_down_loss",
            "mass_lapse_loss",
            "lapse_loss",
            "capital",
            "mass_lapse_rate",
        )
        values = {
            name: _nonnegative_float(getattr(self, name), name) for name in names
        }
        if values["mass_lapse_rate"] > 1.0:
            raise ValueError("mass_lapse_rate must lie in [0, 1].")
        lapse_values = {
            "lapse_up": values["lapse_up_loss"],
            "lapse_down": values["lapse_down_loss"],
            "mass_lapse": values["mass_lapse_loss"],
        }
        if self.binding_lapse_stress not in lapse_values:
            raise ValueError("binding_lapse_stress is not a recognised lapse stress.")
        maximum = max(lapse_values.values())
        if not math.isclose(
            values["lapse_loss"], maximum, rel_tol=1.0e-12, abs_tol=1.0e-12
        ):
            raise ValueError("lapse_loss must equal the largest lapse stress loss.")
        if not math.isclose(
            lapse_values[self.binding_lapse_stress],
            maximum,
            rel_tol=1.0e-12,
            abs_tol=1.0e-12,
        ):
            raise ValueError("binding_lapse_stress does not identify a maximum.")


def calculate_mll_capital(
    *,
    base_csm: Real,
    mortality_stressed_csm: Real,
    longevity_stressed_csm: Real,
    lapse_up_stressed_csm: Real,
    lapse_down_stressed_csm: Real,
    model_point_csms: Sequence[Real],
    model_point_weights: Sequence[Real],
    stresses: Optional[CapitalStresses] = None,
) -> MLLCapitalResult:
    """Calculate the complete MLL arithmetic from supplied revaluation CSMs.

    The caller remains responsible for producing cache-valid, path-congruent
    base and stress valuations under one frozen management rule.  No stress is
    simulated or inferred by this function.
    """

    resolved = _resolve_stresses(stresses)
    mortality = adverse_csm_loss(base_csm, mortality_stressed_csm)
    longevity = adverse_csm_loss(base_csm, longevity_stressed_csm)
    lapse_up = adverse_csm_loss(base_csm, lapse_up_stressed_csm)
    lapse_down = adverse_csm_loss(base_csm, lapse_down_stressed_csm)
    mass_lapse = model_point_mass_lapse_proxy(
        model_point_csms,
        model_point_weights,
        mass_lapse_rate=resolved.lapse_mass,
    )
    lapse_by_name = {
        "lapse_up": lapse_up,
        "lapse_down": lapse_down,
        "mass_lapse": mass_lapse,
    }
    # ``max`` is stable, so LAPSE_STRESS_ORDER is the deterministic tie-break.
    binding = max(LAPSE_STRESS_ORDER, key=lapse_by_name.__getitem__)
    lapse = lapse_by_name[binding]
    capital = aggregate_mll_capital(
        mortality, longevity, lapse, stresses=resolved
    )
    return MLLCapitalResult(
        mortality_loss=mortality,
        longevity_loss=longevity,
        lapse_up_loss=lapse_up,
        lapse_down_loss=lapse_down,
        mass_lapse_loss=mass_lapse,
        lapse_loss=lapse,
        binding_lapse_stress=binding,
        capital=capital,
        mass_lapse_rate=resolved.lapse_mass,
    )


@dataclass(frozen=True)
class CapitalAdjustedCSMResult:
    """Signed CSM, capital charge and optional capital-efficiency ratio."""

    csm: float
    capital: float
    capital_hurdle: float
    capital_materiality: float
    capital_charge: float
    capital_adjusted_csm: float
    csm_to_capital: Optional[float]
    framework: str = field(default=MLL_FRAMEWORK, init=False)

    def __post_init__(self) -> None:
        csm = _finite_float(self.csm, "csm")
        capital = _nonnegative_float(self.capital, "capital")
        hurdle = _nonnegative_float(self.capital_hurdle, "capital_hurdle")
        materiality = _nonnegative_float(
            self.capital_materiality, "capital_materiality"
        )
        charge = _nonnegative_float(self.capital_charge, "capital_charge")
        adjusted = _finite_float(
            self.capital_adjusted_csm, "capital_adjusted_csm"
        )
        expected_charge = hurdle * capital
        expected_adjusted = csm - expected_charge
        if not math.isclose(
            charge, expected_charge, rel_tol=1.0e-12, abs_tol=1.0e-12
        ):
            raise ValueError("capital_charge must equal hurdle times capital.")
        if not math.isclose(
            adjusted, expected_adjusted, rel_tol=1.0e-12, abs_tol=1.0e-12
        ):
            raise ValueError("capital_adjusted_csm is inconsistent.")
        if capital <= materiality:
            if self.csm_to_capital is not None:
                raise ValueError(
                    "csm_to_capital must be None at or below materiality."
                )
        else:
            ratio = _finite_float(self.csm_to_capital, "csm_to_capital")
            if not math.isclose(
                ratio, csm / capital, rel_tol=1.0e-12, abs_tol=1.0e-12
            ):
                raise ValueError("csm_to_capital is inconsistent.")


def evaluate_capital_adjusted_csm(
    csm: Real,
    capital: Real,
    *,
    capital_hurdle: Real,
    capital_materiality: Real = 1.0e-9,
) -> CapitalAdjustedCSMResult:
    """Evaluate ``CSM - hurdle * capital`` and the optional raw CSM ratio.

    The AUD capital-adjusted CSM is the robust comparison objective.  The
    optional ``CSM / capital`` ratio is a secondary lifetime value-to-capital
    diagnostic, not annualised RAROC.  It is ``None`` when capital is at or
    below the caller's materiality threshold; no epsilon denominator is used.
    """

    signed_csm = _finite_float(csm, "csm")
    required_capital = _nonnegative_float(capital, "capital")
    hurdle = _nonnegative_float(capital_hurdle, "capital_hurdle")
    materiality = _nonnegative_float(
        capital_materiality, "capital_materiality"
    )
    charge = hurdle * required_capital
    ratio = (
        None
        if required_capital <= materiality
        else signed_csm / required_capital
    )
    return CapitalAdjustedCSMResult(
        csm=signed_csm,
        capital=required_capital,
        capital_hurdle=hurdle,
        capital_materiality=materiality,
        capital_charge=charge,
        capital_adjusted_csm=signed_csm - charge,
        csm_to_capital=ratio,
    )


def _require_same_metric_basis(
    candidate: CapitalAdjustedCSMResult,
    comparator: CapitalAdjustedCSMResult,
) -> None:
    if not isinstance(candidate, CapitalAdjustedCSMResult) or not isinstance(
        comparator, CapitalAdjustedCSMResult
    ):
        raise TypeError(
            "candidate and comparator must be CapitalAdjustedCSMResult values."
        )
    if candidate.capital_hurdle != comparator.capital_hurdle:
        raise ValueError("Capital metrics use different capital hurdles.")
    if candidate.capital_materiality != comparator.capital_materiality:
        raise ValueError("Capital metrics use different materiality thresholds.")


@dataclass(frozen=True)
class CapitalMetricComparison:
    """Candidate-minus-comparator changes on one common metric basis."""

    csm_delta: float
    capital_delta: float
    capital_charge_delta: float
    capital_adjusted_csm_delta: float
    csm_to_capital_delta: Optional[float]


def compare_capital_metrics(
    candidate: CapitalAdjustedCSMResult,
    comparator: CapitalAdjustedCSMResult,
) -> CapitalMetricComparison:
    """Return candidate minus comparator, preserving an unavailable ratio."""

    _require_same_metric_basis(candidate, comparator)
    ratio_delta = (
        None
        if candidate.csm_to_capital is None
        or comparator.csm_to_capital is None
        else candidate.csm_to_capital - comparator.csm_to_capital
    )
    return CapitalMetricComparison(
        csm_delta=candidate.csm - comparator.csm,
        capital_delta=candidate.capital - comparator.capital,
        capital_charge_delta=(
            candidate.capital_charge - comparator.capital_charge
        ),
        capital_adjusted_csm_delta=(
            candidate.capital_adjusted_csm
            - comparator.capital_adjusted_csm
        ),
        csm_to_capital_delta=ratio_delta,
    )


@dataclass(frozen=True)
class FlexibilityDelta:
    """Adaptive result relative to the best supplied fixed-cap result."""

    adaptive: CapitalAdjustedCSMResult
    best_fixed: CapitalAdjustedCSMResult
    best_fixed_index: int
    comparison: CapitalMetricComparison

    @property
    def capital_adjusted_csm_delta(self) -> float:
        return self.comparison.capital_adjusted_csm_delta


def calculate_flexibility_delta(
    adaptive: CapitalAdjustedCSMResult,
    fixed_candidates: Sequence[CapitalAdjustedCSMResult],
) -> FlexibilityDelta:
    """Compare adaptive value with the best fixed capital-adjusted CSM.

    The first fixed candidate wins an exact tie, making selection stable and
    reproducible.  Sample separation is an orchestrator responsibility: final
    evaluation results must not be supplied for policy selection.
    """

    if not isinstance(adaptive, CapitalAdjustedCSMResult):
        raise TypeError("adaptive must be a CapitalAdjustedCSMResult.")
    if isinstance(fixed_candidates, (str, bytes)):
        raise TypeError("fixed_candidates must be a sequence of metrics.")
    try:
        fixed = tuple(fixed_candidates)
    except TypeError as exc:
        raise TypeError("fixed_candidates must be a sequence of metrics.") from exc
    if not fixed:
        raise ValueError("At least one fixed candidate is required.")
    for candidate in fixed:
        _require_same_metric_basis(adaptive, candidate)
    best_index = max(
        range(len(fixed)),
        key=lambda index: fixed[index].capital_adjusted_csm,
    )
    best = fixed[best_index]
    return FlexibilityDelta(
        adaptive=adaptive,
        best_fixed=best,
        best_fixed_index=best_index,
        comparison=compare_capital_metrics(adaptive, best),
    )


__all__ = [
    "CapitalAdjustedCSMResult",
    "CapitalMetricComparison",
    "FlexibilityDelta",
    "MASS_LAPSE_METHOD",
    "MLLCapitalResult",
    "MLL_FRAMEWORK",
    "adverse_csm_loss",
    "aggregate_mll_capital",
    "calculate_flexibility_delta",
    "calculate_mll_capital",
    "compare_capital_metrics",
    "evaluate_capital_adjusted_csm",
    "mll_correlation_matrix",
    "model_point_mass_lapse_proxy",
]
