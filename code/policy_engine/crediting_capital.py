"""Pure MLL future-profit-at-risk arithmetic for research comparisons.

The functions in this module consume the repository's signed *custom CSM*
values produced by separate base and stress revaluations.  That custom CSM is
the present value of insurer income less claims and costs.  On the frozen
cashflow basis used by the caller, ``base custom CSM - stressed custom CSM`` is
therefore an insurer future-profit/value loss proxy (and, where only the
non-unit BEL changes, its algebraic counterpart is an increase in that BEL).
It is not a change in recognised IFRS 17 CSM.

The functions do not build market scenarios, price hedges, read or write
caches, or trigger any valuation runner.  This keeps the arithmetic usable by
a strict cache-reading orchestrator without creating a second route for
risk-neutral path generation.

Only mortality, longevity and lapse (``MLL``) losses are aggregated.  The
result is a deliberately partial MLL future-profit-at-risk (``MLL-FPAR``)
research proxy.  It is not APRA/LAGIC required capital, total SCR, Solvency II
regulatory capital, an IFRS 17 Risk Adjustment, or recognised IFRS 17 CSM.  In
particular, adjusted policy liabilities/RFBEL, termination-value floors and the
complete insurer balance sheet are not calculated; market, expense,
catastrophe, operational, concentration, tax-absorption and diversification
effects outside the MLL submatrix are also absent.

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

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .capital import CapitalStresses


MLL_FUTURE_PROFIT_RISK_FRAMEWORK = (
    "MLL_FUTURE_PROFIT_AT_RISK_RESEARCH_PROXY_NOT_REGULATORY_CAPITAL"
)
MLL_VALUE_BASIS = (
    "ONE_SIDED_LOSS_IN_REPOSITORY_CUSTOM_CSM_AS_INSURER_"
    "FUTURE_PROFIT_VALUE_PROXY"
)
REGULATORY_CAPITAL_CALCULATED = False
APRA_LAGIC_CAPITAL_CALCULATED = False
IFRS17_CSM_CALCULATED = False

# Backwards-compatible public name.  New code should use the explicit
# ``MLL_FUTURE_PROFIT_RISK_FRAMEWORK`` name.
MLL_FRAMEWORK = MLL_FUTURE_PROFIT_RISK_FRAMEWORK
MLL_LEGACY_FRAMEWORK = "MLL_LIFE_RISK_RESEARCH_PROXY_NOT_REGULATORY_CAPITAL"
MASS_LAPSE_METHOD = "positive_model_point_csm_proxy_not_revaluation"
MLL_LABELS = ("mortality", "longevity", "lapse")
LAPSE_STRESS_ORDER = ("lapse_up", "lapse_down", "mass_lapse")

# Frozen value-vector contract for the management-LSMC interface.  The first
# nine values deliberately follow the insurer-component ordering used by the
# dynamic crediting-rate optimiser.  Four complete stressed CSM values follow;
# all remaining columns are signed base CSM values by model point.
LSMC_BASE_COMPONENT_NAMES = (
    "fees_product",
    "fees_lip",
    "crediting_margin",
    "mva_retained",
    "aps_retained",
    "guarantee_claims",
    "other_insurer_funded_benefits",
    "expenses",
    "hedge_costs",
)
LSMC_STRESS_CSM_NAMES = (
    "mortality_stressed_csm",
    "longevity_stressed_csm",
    "lapse_up_stressed_csm",
    "lapse_down_stressed_csm",
)
LSMC_FIXED_VALUE_COUNT = len(LSMC_BASE_COMPONENT_NAMES) + len(
    LSMC_STRESS_CSM_NAMES
)


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


def adverse_future_profit_loss(
    base_custom_csm: Real,
    stressed_custom_csm: Real,
) -> float:
    """Return the one-sided insurer future-profit/value loss under one stress.

    The inputs are repository-specific custom CSM values, not recognised
    IFRS 17 CSM balances.  A stress that increases custom CSM is favourable and
    therefore contributes zero to MLL-FPAR.  Custom CSM is intentionally not
    clipped at zero before the comparison: a stress can make an already
    onerous portfolio more onerous.
    """

    base = _finite_float(base_custom_csm, "base_custom_csm")
    stressed = _finite_float(stressed_custom_csm, "stressed_custom_csm")
    return max(0.0, base - stressed)


def adverse_csm_loss(base_csm: Real, stressed_csm: Real) -> float:
    """Legacy alias for :func:`adverse_future_profit_loss`.

    ``csm`` here means the repository's custom profitability measure, not an
    IFRS 17 CSM balance and not regulatory capital.
    """

    return adverse_future_profit_loss(base_csm, stressed_csm)


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


def aggregate_mll_future_profit_risk(
    mortality_loss: Real,
    longevity_loss: Real,
    lapse_loss: Real,
    *,
    stresses: Optional[CapitalStresses] = None,
) -> float:
    """Aggregate non-negative MLL future-profit losses by correlation.

    The correlation matrix is a research aggregation convention.  This result
    is not an APRA/LAGIC capital requirement or a complete regulatory module.
    """

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


def aggregate_mll_capital(
    mortality_loss: Real,
    longevity_loss: Real,
    lapse_loss: Real,
    *,
    stresses: Optional[CapitalStresses] = None,
) -> float:
    """Legacy alias for :func:`aggregate_mll_future_profit_risk`."""

    return aggregate_mll_future_profit_risk(
        mortality_loss,
        longevity_loss,
        lapse_loss,
        stresses=stresses,
    )


@dataclass(frozen=True)
class MLLCapitalResult:
    """Standalone losses and correlated MLL-FPAR for one cap policy.

    The ``capital`` attribute is retained only for compatibility.  New code
    should use :attr:`future_profit_risk`.  The explicit status fields prevent
    this research proxy from being reported as APRA/LAGIC or other regulatory
    capital.
    """

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
    risk_measure_basis: str = field(default=MLL_VALUE_BASIS, init=False)
    regulatory_capital_calculated: bool = field(
        default=REGULATORY_CAPITAL_CALCULATED,
        init=False,
    )
    apra_lagic_capital_calculated: bool = field(
        default=APRA_LAGIC_CAPITAL_CALCULATED,
        init=False,
    )
    ifrs17_csm_calculated: bool = field(
        default=IFRS17_CSM_CALCULATED,
        init=False,
    )
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

    @property
    def future_profit_risk(self) -> float:
        """Correlated MLL future-profit-at-risk research proxy.

        This is the canonical name for the numeric value stored in the legacy
        ``capital`` field.
        """

        return self.capital

    @property
    def value_basis(self) -> str:
        """Descriptive alias for :attr:`risk_measure_basis`."""

        return self.risk_measure_basis


# Canonical result name; ``MLLCapitalResult`` remains import-compatible.
MLLFutureProfitRiskResult = MLLCapitalResult


def calculate_mll_future_profit_risk(
    *,
    base_csm: Real,
    mortality_stressed_csm: Real,
    longevity_stressed_csm: Real,
    lapse_up_stressed_csm: Real,
    lapse_down_stressed_csm: Real,
    model_point_csms: Sequence[Real],
    model_point_weights: Sequence[Real],
    stresses: Optional[CapitalStresses] = None,
) -> MLLFutureProfitRiskResult:
    """Calculate MLL-FPAR from supplied custom-CSM stress revaluations.

    The caller remains responsible for producing cache-valid, path-congruent
    base and stress valuations under one frozen management rule.  No stress is
    simulated or inferred by this function.  A stressed reduction in the
    repository's custom CSM is treated as an insurer future-profit/value loss;
    it is not a movement in recognised IFRS 17 CSM and does not calculate
    APRA/LAGIC policy liabilities or required capital.
    """

    resolved = _resolve_stresses(stresses)
    mortality = adverse_future_profit_loss(base_csm, mortality_stressed_csm)
    longevity = adverse_future_profit_loss(base_csm, longevity_stressed_csm)
    lapse_up = adverse_future_profit_loss(base_csm, lapse_up_stressed_csm)
    lapse_down = adverse_future_profit_loss(base_csm, lapse_down_stressed_csm)
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
    future_profit_risk = aggregate_mll_future_profit_risk(
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
        capital=future_profit_risk,
        mass_lapse_rate=resolved.lapse_mass,
    )


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
    """Legacy alias for :func:`calculate_mll_future_profit_risk`."""

    return calculate_mll_future_profit_risk(
        base_csm=base_csm,
        mortality_stressed_csm=mortality_stressed_csm,
        longevity_stressed_csm=longevity_stressed_csm,
        lapse_up_stressed_csm=lapse_up_stressed_csm,
        lapse_down_stressed_csm=lapse_down_stressed_csm,
        model_point_csms=model_point_csms,
        model_point_weights=model_point_weights,
        stresses=stresses,
    )


@dataclass(frozen=True)
class CapitalAdjustedCSMResult:
    """Custom CSM with an optional MLL-FPAR research penalty.

    The capital-named fields are retained for backwards compatibility.  Their
    canonical properties below deliberately say ``risk`` or ``penalty``: the
    weight is a dimensionless research preference, not a regulatory capital
    charge or cost-of-capital calibration.
    """

    csm: float
    capital: float
    capital_hurdle: float
    capital_materiality: float
    capital_charge: float
    capital_adjusted_csm: float
    csm_to_capital: Optional[float]
    framework: str = field(default=MLL_FRAMEWORK, init=False)
    risk_measure_basis: str = field(default=MLL_VALUE_BASIS, init=False)
    regulatory_capital_calculated: bool = field(
        default=REGULATORY_CAPITAL_CALCULATED,
        init=False,
    )
    apra_lagic_capital_calculated: bool = field(
        default=APRA_LAGIC_CAPITAL_CALCULATED,
        init=False,
    )
    ifrs17_csm_calculated: bool = field(
        default=IFRS17_CSM_CALCULATED,
        init=False,
    )

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

    @property
    def future_profit_risk(self) -> float:
        """MLL future-profit-at-risk proxy (legacy field: ``capital``)."""

        return self.capital

    @property
    def value_basis(self) -> str:
        """Descriptive alias for :attr:`risk_measure_basis`."""

        return self.risk_measure_basis

    @property
    def risk_penalty_weight(self) -> float:
        """Dimensionless research weight (legacy: ``capital_hurdle``)."""

        return self.capital_hurdle

    @property
    def risk_materiality(self) -> float:
        """MLL-FPAR materiality threshold."""

        return self.capital_materiality

    @property
    def risk_penalty(self) -> float:
        """Research penalty ``weight * MLL-FPAR``."""

        return self.capital_charge

    @property
    def risk_penalized_csm(self) -> float:
        """Custom CSM less the research MLL-FPAR penalty."""

        return self.capital_adjusted_csm

    @property
    def csm_to_mll_risk_ratio(self) -> Optional[float]:
        """Custom-CSM-to-MLL-FPAR ratio, if the denominator is material."""

        return self.csm_to_capital


# Canonical result name; the legacy class name remains stable for callers.
RiskPenalizedCSMResult = CapitalAdjustedCSMResult


def evaluate_risk_penalized_csm(
    csm: Real,
    future_profit_risk: Real,
    *,
    risk_penalty_weight: Real,
    risk_materiality: Real = 1.0e-9,
) -> RiskPenalizedCSMResult:
    """Evaluate ``custom CSM - weight * MLL-FPAR`` and its optional ratio.

    This is a research sensitivity, not an APRA/LAGIC capital charge, cost of
    capital or annualised RAROC.  The ratio is ``None`` when MLL-FPAR is at or
    below the caller's materiality threshold; no epsilon denominator is used.
    """

    signed_csm = _finite_float(csm, "csm")
    risk = _nonnegative_float(future_profit_risk, "future_profit_risk")
    weight = _nonnegative_float(risk_penalty_weight, "risk_penalty_weight")
    materiality = _nonnegative_float(
        risk_materiality, "risk_materiality"
    )
    penalty = weight * risk
    ratio = (
        None
        if risk <= materiality
        else signed_csm / risk
    )
    return CapitalAdjustedCSMResult(
        csm=signed_csm,
        capital=risk,
        capital_hurdle=weight,
        capital_materiality=materiality,
        capital_charge=penalty,
        capital_adjusted_csm=signed_csm - penalty,
        csm_to_capital=ratio,
    )


def evaluate_capital_adjusted_csm(
    csm: Real,
    capital: Real,
    *,
    capital_hurdle: Real,
    capital_materiality: Real = 1.0e-9,
) -> CapitalAdjustedCSMResult:
    """Legacy alias for :func:`evaluate_risk_penalized_csm`."""

    return evaluate_risk_penalized_csm(
        csm,
        capital,
        risk_penalty_weight=capital_hurdle,
        risk_materiality=capital_materiality,
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
    """Candidate-minus-comparator changes on one common research basis."""

    csm_delta: float
    capital_delta: float
    capital_charge_delta: float
    capital_adjusted_csm_delta: float
    csm_to_capital_delta: Optional[float]

    @property
    def future_profit_risk_delta(self) -> float:
        return self.capital_delta

    @property
    def risk_penalty_delta(self) -> float:
        return self.capital_charge_delta

    @property
    def risk_penalized_csm_delta(self) -> float:
        return self.capital_adjusted_csm_delta

    @property
    def csm_to_mll_risk_ratio_delta(self) -> Optional[float]:
        return self.csm_to_capital_delta


RiskMetricComparison = CapitalMetricComparison


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


# Canonical comparison name; legacy field aliases remain available on the
# returned immutable result.
compare_risk_metrics = compare_capital_metrics


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

    @property
    def risk_penalized_csm_delta(self) -> float:
        """Canonical alias for the MLL-FPAR-penalised CSM change."""

        return self.comparison.risk_penalized_csm_delta


def calculate_flexibility_delta(
    adaptive: CapitalAdjustedCSMResult,
    fixed_candidates: Sequence[CapitalAdjustedCSMResult],
) -> FlexibilityDelta:
    """Compare adaptive value with the best fixed risk-penalised custom CSM.

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


# ---------------------------------------------------------------------------
# Policy-level CSM/MLL score used outside the annual Bellman recursion
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyLevelCSMMLLResult:
    """Policy-level custom-CSM/MLL-FPAR ratio on one aggregation basis.

    The supplied CSM values are already policy-level expectation values.  In
    particular, this class performs no path averaging.  ``mll`` retains the
    standalone stress losses and binding lapse stress for audit, while the
    ratio is deliberately unavailable at or below ``capital_materiality``.
    """

    csm: float
    mll: MLLCapitalResult
    capital_materiality: float
    csm_to_mll_ratio: Optional[float]

    def __post_init__(self) -> None:
        csm = _finite_float(self.csm, "csm")
        if not isinstance(self.mll, MLLCapitalResult):
            raise TypeError("mll must be an MLLCapitalResult.")
        materiality = _nonnegative_float(
            self.capital_materiality, "capital_materiality"
        )
        if self.mll.capital <= materiality:
            if self.csm_to_mll_ratio is not None:
                raise ValueError(
                    "csm_to_mll_ratio must be None at or below materiality."
                )
        else:
            ratio = _finite_float(
                self.csm_to_mll_ratio, "csm_to_mll_ratio"
            )
            if not math.isclose(
                ratio,
                csm / self.mll.capital,
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            ):
                raise ValueError("csm_to_mll_ratio is inconsistent.")

    @property
    def mll_capital(self) -> float:
        """Legacy alias for :attr:`future_profit_risk`."""

        return self.mll.capital

    @property
    def csm_to_capital(self) -> Optional[float]:
        """Legacy alias for :attr:`csm_to_mll_risk_ratio`."""

        return self.csm_to_mll_ratio

    @property
    def future_profit_risk(self) -> float:
        """Correlated MLL future-profit-at-risk research proxy."""

        return self.mll.future_profit_risk

    @property
    def csm_to_mll_risk_ratio(self) -> Optional[float]:
        """Custom-CSM-to-MLL-FPAR ratio, if the denominator is material."""

        return self.csm_to_mll_ratio

    @property
    def regulatory_capital_calculated(self) -> bool:
        return self.mll.regulatory_capital_calculated

    @property
    def apra_lagic_capital_calculated(self) -> bool:
        return self.mll.apra_lagic_capital_calculated

    @property
    def ifrs17_csm_calculated(self) -> bool:
        return self.mll.ifrs17_csm_calculated


def calculate_policy_level_csm_mll(
    *,
    base_csm: Real,
    mortality_stressed_csm: Real,
    longevity_stressed_csm: Real,
    lapse_up_stressed_csm: Real,
    lapse_down_stressed_csm: Real,
    model_point_csms: Sequence[Real],
    model_point_weights: Sequence[Real],
    capital_materiality: Real = 1.0e-9,
    stresses: Optional[CapitalStresses] = None,
) -> PolicyLevelCSMMLLResult:
    """Calculate custom CSM, MLL-FPAR and their policy-level ratio.

    ``model_point_csms`` are signed base CSM values.  Their positive part is
    taken *per model point* inside the mass-lapse proxy, before the supplied
    non-negative weights are aggregated.  A negative model point therefore
    cannot net a profitable model point for mass lapse.
    """

    csm = _finite_float(base_csm, "base_csm")
    materiality = _nonnegative_float(
        capital_materiality, "capital_materiality"
    )
    mll = calculate_mll_future_profit_risk(
        base_csm=csm,
        mortality_stressed_csm=mortality_stressed_csm,
        longevity_stressed_csm=longevity_stressed_csm,
        lapse_up_stressed_csm=lapse_up_stressed_csm,
        lapse_down_stressed_csm=lapse_down_stressed_csm,
        model_point_csms=model_point_csms,
        model_point_weights=model_point_weights,
        stresses=stresses,
    )
    ratio = None if mll.capital <= materiality else csm / mll.capital
    return PolicyLevelCSMMLLResult(
        csm=csm,
        mll=mll,
        capital_materiality=materiality,
        csm_to_mll_ratio=ratio,
    )


def _finite_array(values: ArrayLike, name: str) -> NDArray[np.float64]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a numeric array.")
    try:
        original = np.asarray(values)
        if original.dtype.kind == "b":
            raise TypeError(f"{name} must be numeric, not boolean.")
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a numeric array.") from exc
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values.")
    return np.asarray(array, dtype=float)


def _model_point_weight_array(
    model_point_weights: Optional[ArrayLike],
    model_point_count: int,
) -> NDArray[np.float64]:
    if model_point_count <= 0:
        raise ValueError("At least one model-point CSM column is required.")
    weights = (
        np.ones(model_point_count, dtype=float)
        if model_point_weights is None
        else _finite_array(model_point_weights, "model_point_weights")
    )
    if weights.shape != (model_point_count,):
        raise ValueError(
            "model_point_weights must have one value per model-point column."
        )
    if np.any(weights < 0.0):
        raise ValueError("model_point_weights must be non-negative.")
    if not np.any(weights > 0.0):
        raise ValueError("At least one model-point weight must be positive.")
    return weights


def _vectorised_mll_metrics(
    *,
    base_csm: NDArray[np.float64],
    mortality_stressed_csm: NDArray[np.float64],
    longevity_stressed_csm: NDArray[np.float64],
    lapse_up_stressed_csm: NDArray[np.float64],
    lapse_down_stressed_csm: NDArray[np.float64],
    model_point_csms: NDArray[np.float64],
    model_point_weights: NDArray[np.float64],
    stresses: CapitalStresses,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
]:
    """Vectorised MLL arithmetic on already aggregated value arrays."""

    leading_shape = base_csm.shape
    named = {
        "mortality_stressed_csm": mortality_stressed_csm,
        "longevity_stressed_csm": longevity_stressed_csm,
        "lapse_up_stressed_csm": lapse_up_stressed_csm,
        "lapse_down_stressed_csm": lapse_down_stressed_csm,
    }
    for name, values in named.items():
        if values.shape != leading_shape:
            raise ValueError(f"{name} does not match the base CSM shape.")
    if model_point_csms.shape != leading_shape + (
        model_point_weights.size,
    ):
        raise ValueError(
            "model_point_csms must share all leading dimensions and end in "
            "the model-point axis."
        )

    mortality = np.maximum(base_csm - mortality_stressed_csm, 0.0)
    longevity = np.maximum(base_csm - longevity_stressed_csm, 0.0)
    lapse_up = np.maximum(base_csm - lapse_up_stressed_csm, 0.0)
    lapse_down = np.maximum(base_csm - lapse_down_stressed_csm, 0.0)
    mass_lapse = stresses.lapse_mass * np.sum(
        np.maximum(model_point_csms, 0.0) * model_point_weights,
        axis=-1,
    )
    lapse = np.maximum(np.maximum(lapse_up, lapse_down), mass_lapse)
    modules = np.stack((mortality, longevity, lapse), axis=-1)
    correlation = np.asarray(mll_correlation_matrix(stresses), dtype=float)
    quadratic = np.einsum(
        "...i,ij,...j->...", modules, correlation, modules
    )
    tolerance = 1.0e-12 * np.maximum(
        1.0, np.sum(modules, axis=-1) ** 2
    )
    if np.any(quadratic < -tolerance):
        raise ValueError(
            "The MLL correlation quadratic form is materially negative."
        )
    capital = np.sqrt(np.maximum(quadratic, 0.0))
    return mortality, longevity, lapse, mass_lapse, capital


def _score_output(
    values: NDArray[np.float64],
) -> float | NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim == 0:
        return float(array)
    snapshot = np.array(array, dtype=float, copy=True)
    snapshot.flags.writeable = False
    return snapshot


@dataclass(frozen=True)
class LSMCCSMMLLScore:
    """Custom-CSM/MLL-FPAR outputs for management-LSMC value vectors.

    Array inputs preserve every leading dimension.  For an array result,
    non-material ratio cells are represented by ``NaN`` because NumPy arrays
    cannot represent elementwise ``None`` without losing numeric semantics.
    A single value vector instead returns ``None`` for an immaterial ratio.
    """

    csm: float | NDArray[np.float64]
    mll_capital: float | NDArray[np.float64]
    csm_to_mll_ratio: Optional[float] | NDArray[np.float64]
    mortality_loss: float | NDArray[np.float64]
    longevity_loss: float | NDArray[np.float64]
    lapse_loss: float | NDArray[np.float64]
    mass_lapse_loss: float | NDArray[np.float64]
    capital_materiality: float

    @property
    def score(self) -> Optional[float] | NDArray[np.float64]:
        """The custom-CSM/MLL-FPAR score used for policy comparison."""

        return self.csm_to_mll_risk_ratio

    @property
    def future_profit_risk(self) -> float | NDArray[np.float64]:
        """Canonical alias for the legacy ``mll_capital`` field."""

        return self.mll_capital

    @property
    def csm_to_mll_risk_ratio(
        self,
    ) -> Optional[float] | NDArray[np.float64]:
        """Custom-CSM-to-MLL-FPAR ratio."""

        return self.csm_to_mll_ratio

    @property
    def risk_materiality(self) -> float:
        return self.capital_materiality

    @property
    def regulatory_capital_calculated(self) -> bool:
        return REGULATORY_CAPITAL_CALCULATED

    @property
    def apra_lagic_capital_calculated(self) -> bool:
        return APRA_LAGIC_CAPITAL_CALCULATED

    @property
    def ifrs17_csm_calculated(self) -> bool:
        return IFRS17_CSM_CALCULATED


def score_lsmc_value_vectors(
    values: ArrayLike,
    *,
    model_point_weights: Optional[ArrayLike] = None,
    capital_materiality: Real = 1.0e-9,
    stresses: Optional[CapitalStresses] = None,
) -> LSMCCSMMLLScore:
    """Score scalar or array-valued management-LSMC value vectors.

    The final axis is strictly

    ``[9 base insurer components, 4 stressed CSMs, P base model-point CSMs]``.

    The nine base components follow :data:`LSMC_BASE_COMPONENT_NAMES`; the
    first five are income and the final four are claims/costs.  This function
    intentionally contains no pathwise mean, resampling or policy selection
    logic.  Every leading dimension is treated as an independent, already
    aggregated value vector.
    """

    array = _finite_array(values, "values")
    if array.ndim < 1:
        raise ValueError("values must have a final value-vector axis.")
    model_point_count = array.shape[-1] - LSMC_FIXED_VALUE_COUNT
    if model_point_count <= 0:
        raise ValueError(
            "values must contain nine base components, four stressed CSMs "
            "and at least one model-point CSM."
        )
    weights = _model_point_weight_array(
        model_point_weights, model_point_count
    )
    materiality = _nonnegative_float(
        capital_materiality, "capital_materiality"
    )
    resolved = _resolve_stresses(stresses)

    base_components = array[..., : len(LSMC_BASE_COMPONENT_NAMES)]
    csm = (
        np.sum(base_components[..., :5], axis=-1)
        - np.sum(base_components[..., 5:], axis=-1)
    )
    stress_start = len(LSMC_BASE_COMPONENT_NAMES)
    mortality_stressed = array[..., stress_start]
    longevity_stressed = array[..., stress_start + 1]
    lapse_up_stressed = array[..., stress_start + 2]
    lapse_down_stressed = array[..., stress_start + 3]
    model_point_csms = array[..., LSMC_FIXED_VALUE_COUNT:]
    mortality, longevity, lapse, mass_lapse, capital = (
        _vectorised_mll_metrics(
            base_csm=np.asarray(csm, dtype=float),
            mortality_stressed_csm=np.asarray(
                mortality_stressed, dtype=float
            ),
            longevity_stressed_csm=np.asarray(
                longevity_stressed, dtype=float
            ),
            lapse_up_stressed_csm=np.asarray(lapse_up_stressed, dtype=float),
            lapse_down_stressed_csm=np.asarray(
                lapse_down_stressed, dtype=float
            ),
            model_point_csms=np.asarray(model_point_csms, dtype=float),
            model_point_weights=weights,
            stresses=resolved,
        )
    )
    material = capital > materiality
    ratio_values = np.full(capital.shape, np.nan, dtype=float)
    np.divide(csm, capital, out=ratio_values, where=material)
    ratio: Optional[float] | NDArray[np.float64]
    if ratio_values.ndim == 0:
        ratio = float(ratio_values) if bool(material) else None
    else:
        ratio = _score_output(ratio_values)
    return LSMCCSMMLLScore(
        csm=_score_output(np.asarray(csm, dtype=float)),
        mll_capital=_score_output(capital),
        csm_to_mll_ratio=ratio,
        mortality_loss=_score_output(mortality),
        longevity_loss=_score_output(longevity),
        lapse_loss=_score_output(lapse),
        mass_lapse_loss=_score_output(mass_lapse),
        capital_materiality=materiality,
    )


# ---------------------------------------------------------------------------
# Paired policy-level bootstrap; path generation remains outside this module
# ---------------------------------------------------------------------------


def _path_vector(values: ArrayLike, name: str) -> NDArray[np.float64]:
    array = _finite_array(values, name)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional array.")
    snapshot = np.array(array, dtype=float, copy=True)
    snapshot.flags.writeable = False
    return snapshot


def _path_model_point_matrix(
    values: ArrayLike, name: str
) -> NDArray[np.float64]:
    array = _finite_array(values, name)
    if array.ndim != 2 or min(array.shape) <= 0:
        raise ValueError(
            f"{name} must have shape (paths, positive model-point count)."
        )
    snapshot = np.array(array, dtype=float, copy=True)
    snapshot.flags.writeable = False
    return snapshot


@dataclass(frozen=True)
class PolicyCSMPathArrays:
    """Aligned pathwise CSM inputs for one frozen management policy.

    Each stress field is a complete portfolio CSM path.  The model-point
    matrix stores signed base CSM paths with paths on axis zero.  The bootstrap
    takes model-point means first and only then applies the positive part, so
    it never substitutes ``mean(max(pathwise CSM, 0))`` for the required
    ``max(mean CSM, 0)``.
    """

    base_csm_paths: ArrayLike
    mortality_stressed_csm_paths: ArrayLike
    longevity_stressed_csm_paths: ArrayLike
    lapse_up_stressed_csm_paths: ArrayLike
    lapse_down_stressed_csm_paths: ArrayLike
    model_point_base_csm_paths: ArrayLike

    def __post_init__(self) -> None:
        path_fields = (
            "base_csm_paths",
            "mortality_stressed_csm_paths",
            "longevity_stressed_csm_paths",
            "lapse_up_stressed_csm_paths",
            "lapse_down_stressed_csm_paths",
        )
        converted = {
            name: _path_vector(getattr(self, name), name)
            for name in path_fields
        }
        path_count = converted["base_csm_paths"].size
        for name, array in converted.items():
            if array.size != path_count:
                raise ValueError(
                    f"{name} must have the same path count as base_csm_paths."
                )
            object.__setattr__(self, name, array)
        model_points = _path_model_point_matrix(
            self.model_point_base_csm_paths,
            "model_point_base_csm_paths",
        )
        if model_points.shape[0] != path_count:
            raise ValueError(
                "model_point_base_csm_paths must share the portfolio path axis."
            )
        object.__setattr__(self, "model_point_base_csm_paths", model_points)

    @property
    def n_paths(self) -> int:
        return int(np.asarray(self.base_csm_paths).size)

    @property
    def model_point_count(self) -> int:
        return int(np.asarray(self.model_point_base_csm_paths).shape[1])


@dataclass(frozen=True)
class PairedBootstrapRatioDelta:
    """Percentile-bootstrap inference for candidate-minus-comparator ratio."""

    estimate: float
    standard_error: float
    ci_lower: float
    ci_upper: float
    confidence_level: float
    n_resamples: int
    seed: int

    def __post_init__(self) -> None:
        for name in ("estimate", "standard_error", "ci_lower", "ci_upper"):
            _finite_float(getattr(self, name), name)
        if self.standard_error < 0.0:
            raise ValueError("standard_error must be non-negative.")
        level = _finite_float(self.confidence_level, "confidence_level")
        if not 0.0 < level < 1.0:
            raise ValueError("confidence_level must lie strictly between 0 and 1.")
        if self.ci_lower > self.ci_upper:
            raise ValueError("Bootstrap confidence interval is reversed.")
        if isinstance(self.n_resamples, bool) or self.n_resamples < 2:
            raise ValueError("n_resamples must be at least two.")
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer.")

    @property
    def positive_gate_passed(self) -> bool:
        """True only when the complete confidence interval is above zero."""

        return self.ci_lower > 0.0

    @property
    def negative_gate_passed(self) -> bool:
        """True only when the complete confidence interval is below zero."""

        return self.ci_upper < 0.0


def _bootstrap_ratio_values(
    paths: PolicyCSMPathArrays,
    indices: NDArray[np.int64],
    *,
    model_point_weights: NDArray[np.float64],
    capital_materiality: float,
    stresses: CapitalStresses,
) -> NDArray[np.float64]:
    def means(values: ArrayLike) -> NDArray[np.float64]:
        return np.mean(np.asarray(values, dtype=float)[indices], axis=1)

    base = means(paths.base_csm_paths)
    mortality = means(paths.mortality_stressed_csm_paths)
    longevity = means(paths.longevity_stressed_csm_paths)
    lapse_up = means(paths.lapse_up_stressed_csm_paths)
    lapse_down = means(paths.lapse_down_stressed_csm_paths)
    model_points = np.mean(
        np.asarray(paths.model_point_base_csm_paths, dtype=float)[indices, :],
        axis=1,
    )
    _, _, _, _, capital = _vectorised_mll_metrics(
        base_csm=base,
        mortality_stressed_csm=mortality,
        longevity_stressed_csm=longevity,
        lapse_up_stressed_csm=lapse_up,
        lapse_down_stressed_csm=lapse_down,
        model_point_csms=model_points,
        model_point_weights=model_point_weights,
        stresses=stresses,
    )
    if np.any(capital <= capital_materiality):
        raise ValueError(
            "CSM/MLL ratio is undefined in at least one bootstrap resample "
            "because MLL-FPAR is at or below materiality."
        )
    ratio = base / capital
    if not np.all(np.isfinite(ratio)):
        raise ValueError("Bootstrap CSM/MLL ratios are non-finite.")
    return np.asarray(ratio, dtype=float)


def _full_sample_ratio(
    paths: PolicyCSMPathArrays,
    *,
    model_point_weights: NDArray[np.float64],
    capital_materiality: float,
    stresses: CapitalStresses,
) -> float:
    result = calculate_policy_level_csm_mll(
        base_csm=float(np.mean(paths.base_csm_paths)),
        mortality_stressed_csm=float(
            np.mean(paths.mortality_stressed_csm_paths)
        ),
        longevity_stressed_csm=float(
            np.mean(paths.longevity_stressed_csm_paths)
        ),
        lapse_up_stressed_csm=float(
            np.mean(paths.lapse_up_stressed_csm_paths)
        ),
        lapse_down_stressed_csm=float(
            np.mean(paths.lapse_down_stressed_csm_paths)
        ),
        model_point_csms=np.mean(
            np.asarray(paths.model_point_base_csm_paths, dtype=float), axis=0
        ),
        model_point_weights=model_point_weights,
        capital_materiality=capital_materiality,
        stresses=stresses,
    )
    if result.csm_to_mll_ratio is None:
        raise ValueError(
            "CSM/MLL ratio is undefined for the full sample because MLL "
            "capital is at or below materiality."
        )
    return result.csm_to_mll_ratio


def paired_bootstrap_ratio_delta(
    candidate: PolicyCSMPathArrays,
    comparator: PolicyCSMPathArrays,
    *,
    model_point_weights: Optional[ArrayLike] = None,
    capital_materiality: Real = 1.0e-9,
    stresses: Optional[CapitalStresses] = None,
    n_resamples: int = 2_000,
    confidence_level: Real = 0.95,
    seed: int = 0,
) -> PairedBootstrapRatioDelta:
    """Paired path-block bootstrap of a policy CSM/MLL-ratio delta.

    Candidate minus comparator is the sign convention.  One random index
    matrix is reused for both policies, every stress and every model point, so
    common-random-number dependence is preserved.  The caller is responsible
    for supplying arrays whose path rows genuinely refer to the same market
    and projector draws; shape equality alone cannot prove provenance.

    The returned interval is the ordinary two-sided percentile interval.  No
    resample with immaterial MLL-FPAR is silently dropped, since doing so
    would condition and bias a ratio estimator.
    """

    if not isinstance(candidate, PolicyCSMPathArrays) or not isinstance(
        comparator, PolicyCSMPathArrays
    ):
        raise TypeError(
            "candidate and comparator must be PolicyCSMPathArrays values."
        )
    if candidate.n_paths != comparator.n_paths:
        raise ValueError("Candidate and comparator path counts must match.")
    if candidate.model_point_count != comparator.model_point_count:
        raise ValueError(
            "Candidate and comparator model-point columns must match."
        )
    if candidate.n_paths < 2:
        raise ValueError("Paired bootstrap requires at least two paths.")
    if isinstance(n_resamples, bool) or not isinstance(
        n_resamples, (int, np.integer)
    ) or int(n_resamples) < 2:
        raise ValueError("n_resamples must be an integer of at least two.")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) \
            or int(seed) < 0:
        raise ValueError("seed must be a non-negative integer.")
    level = _finite_float(confidence_level, "confidence_level")
    if not 0.0 < level < 1.0:
        raise ValueError("confidence_level must lie strictly between 0 and 1.")
    materiality = _nonnegative_float(
        capital_materiality, "capital_materiality"
    )
    resolved = _resolve_stresses(stresses)
    weights = _model_point_weight_array(
        model_point_weights, candidate.model_point_count
    )

    estimate = _full_sample_ratio(
        candidate,
        model_point_weights=weights,
        capital_materiality=materiality,
        stresses=resolved,
    ) - _full_sample_ratio(
        comparator,
        model_point_weights=weights,
        capital_materiality=materiality,
        stresses=resolved,
    )

    rng = np.random.default_rng(int(seed))
    replicate_count = int(n_resamples)
    deltas = np.empty(replicate_count, dtype=float)
    # Keep the temporary integer and model-point tensors bounded for the
    # repository's larger OOS samples while retaining vectorised arithmetic.
    batch_size = max(1, min(256, 1_000_000 // candidate.n_paths))
    for start in range(0, replicate_count, batch_size):
        stop = min(start + batch_size, replicate_count)
        indices = rng.integers(
            0,
            candidate.n_paths,
            size=(stop - start, candidate.n_paths),
            dtype=np.int64,
        )
        candidate_ratio = _bootstrap_ratio_values(
            candidate,
            indices,
            model_point_weights=weights,
            capital_materiality=materiality,
            stresses=resolved,
        )
        comparator_ratio = _bootstrap_ratio_values(
            comparator,
            indices,
            model_point_weights=weights,
            capital_materiality=materiality,
            stresses=resolved,
        )
        deltas[start:stop] = candidate_ratio - comparator_ratio

    alpha = 0.5 * (1.0 - level)
    lower, upper = np.quantile(deltas, (alpha, 1.0 - alpha))
    return PairedBootstrapRatioDelta(
        estimate=float(estimate),
        standard_error=float(np.std(deltas, ddof=1)),
        ci_lower=float(lower),
        ci_upper=float(upper),
        confidence_level=level,
        n_resamples=replicate_count,
        seed=int(seed),
    )


# Descriptive alias for callers that prefer the complete metric name.
paired_bootstrap_csm_to_mll_delta = paired_bootstrap_ratio_delta
paired_bootstrap_csm_to_mll_risk_delta = paired_bootstrap_ratio_delta


__all__ = [
    "APRA_LAGIC_CAPITAL_CALCULATED",
    "CapitalAdjustedCSMResult",
    "CapitalMetricComparison",
    "FlexibilityDelta",
    "IFRS17_CSM_CALCULATED",
    "LSMC_BASE_COMPONENT_NAMES",
    "LSMC_FIXED_VALUE_COUNT",
    "LSMC_STRESS_CSM_NAMES",
    "LSMCCSMMLLScore",
    "MASS_LAPSE_METHOD",
    "MLLCapitalResult",
    "MLLFutureProfitRiskResult",
    "MLL_FRAMEWORK",
    "MLL_FUTURE_PROFIT_RISK_FRAMEWORK",
    "MLL_LEGACY_FRAMEWORK",
    "MLL_VALUE_BASIS",
    "PairedBootstrapRatioDelta",
    "PolicyCSMPathArrays",
    "PolicyLevelCSMMLLResult",
    "REGULATORY_CAPITAL_CALCULATED",
    "RiskMetricComparison",
    "RiskPenalizedCSMResult",
    "adverse_csm_loss",
    "adverse_future_profit_loss",
    "aggregate_mll_capital",
    "aggregate_mll_future_profit_risk",
    "calculate_flexibility_delta",
    "calculate_mll_capital",
    "calculate_mll_future_profit_risk",
    "calculate_policy_level_csm_mll",
    "compare_capital_metrics",
    "compare_risk_metrics",
    "evaluate_capital_adjusted_csm",
    "evaluate_risk_penalized_csm",
    "mll_correlation_matrix",
    "model_point_mass_lapse_proxy",
    "paired_bootstrap_csm_to_mll_delta",
    "paired_bootstrap_csm_to_mll_risk_delta",
    "paired_bootstrap_ratio_delta",
    "score_lsmc_value_vectors",
]
