"""Policyholder behaviour assumptions and dynamic response functions.

The production baseline uses established actuarial statistical forms:

* discrete-time proportional hazards / complementary-log-log responses for
  lapse and income take-up; and
* fractional-logit responses for expected withdrawal utilisation.

Every dynamic function is anchored to a duration-specific base assumption and
uses both a market signal and ``log(gross premium / reference premium)``.  The
market signal is the clipped log moneyness appropriate to the action.  Static
objects remain available for isolated mechanics tests, but they are not the
repository base case.  The separate LSMC implementation is retained in
``policy_engine.lsmc`` as archived research code and is not a behaviour regime.

All lapse and take-up rates are annual.  The dynamic annual hazard is converted
to the monthly projection grid only after applying the market and premium
covariates.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional, Sequence

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]


def _scalar_or_array(result: Array, *inputs) -> float | Array:
    return float(result) if all(np.ndim(value) == 0 for value in inputs) else result


def _validate_transform(value: str) -> None:
    if value not in ("signed", "positive_part"):
        raise ValueError("moneyness_transform must be 'signed' or 'positive_part'.")


@dataclass(frozen=True)
class DynamicHazardFunction:
    """Proportional-hazard response for an annual event probability.

    For base annual probability ``p0``, log moneyness ``m`` and gross premium
    ``P``, the annual integrated hazard is

        mu = -log(1-p0) * clip(exp(eta), multiplier_floor, multiplier_cap)

        eta = beta_m * m + beta_p * z + beta_mp * m*z + beta_mva * MVA
        z   = clip(log(P / reference_premium), z_min, z_max).

    This is the standard Cox/proportional-hazard form on a discrete projection
    grid.  At ATM and the reference premium, the base probability is recovered
    exactly.  A structural base probability of zero remains zero.
    """

    beta_moneyness: float
    beta_log_premium: float
    beta_interaction: float
    reference_premium: float = 100_000.0
    log_moneyness_min: float = -float(np.log(2.0))
    log_moneyness_max: float = float(np.log(2.0))
    log_premium_min: float = -2.0
    log_premium_max: float = 2.0
    moneyness_transform: str = "signed"
    annual_floor: float = 0.0
    annual_cap: float = 1.0
    multiplier_floor: float = 0.0
    multiplier_cap: float = 100.0
    beta_mva: float = 0.0

    def __post_init__(self) -> None:
        _validate_transform(self.moneyness_transform)
        values = np.asarray([
            self.beta_moneyness, self.beta_log_premium,
            self.beta_interaction, self.beta_mva, self.reference_premium,
            self.log_moneyness_min, self.log_moneyness_max,
            self.log_premium_min, self.log_premium_max,
            self.annual_floor, self.annual_cap,
            self.multiplier_floor, self.multiplier_cap,
        ], dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError("Dynamic-hazard parameters must be finite.")
        if self.reference_premium <= 0.0:
            raise ValueError("reference_premium must be positive.")
        if self.log_moneyness_min >= self.log_moneyness_max \
                or self.log_premium_min >= self.log_premium_max:
            raise ValueError("Dynamic-hazard signal bounds must be increasing.")
        if not 0.0 <= self.annual_floor <= self.annual_cap <= 1.0:
            raise ValueError("Dynamic-hazard annual floor/cap must lie in [0, 1].")
        if self.multiplier_floor < 0.0 \
                or self.multiplier_cap < self.multiplier_floor:
            raise ValueError("Invalid dynamic-hazard multiplier floor/cap.")
    def _signals(self, log_moneyness, premium,
                 mva_signal=0.0) -> tuple[Array, Array, Array]:
        m, p, mva = np.broadcast_arrays(
            np.asarray(log_moneyness, dtype=float),
            np.asarray(premium, dtype=float),
            np.asarray(mva_signal, dtype=float),
        )
        if not np.all(np.isfinite(m)) or not np.all(np.isfinite(p)) \
                or not np.all(np.isfinite(mva)):
            raise ValueError("Dynamic-hazard inputs must be finite.")
        if np.any(p <= 0.0):
            raise ValueError("Gross premium must be positive.")
        m = np.clip(m, self.log_moneyness_min, self.log_moneyness_max)
        if self.moneyness_transform == "positive_part":
            m = np.maximum(m, 0.0)
        z = np.clip(np.log(p / self.reference_premium),
                    self.log_premium_min, self.log_premium_max)
        return m, z, mva

    def log_multiplier(self, log_moneyness, premium,
                       mva_signal=0.0) -> float | Array:
        """Uncapped log relative hazard for the supplied state."""
        m, z, mva = self._signals(log_moneyness, premium, mva_signal)
        eta = (self.beta_moneyness * m
               + self.beta_log_premium * z
               + self.beta_interaction * m * z
               + self.beta_mva * mva)
        return _scalar_or_array(
            np.asarray(eta, dtype=float),
            log_moneyness,
            premium,
            mva_signal,
        )

    def multiplier(self, log_moneyness, premium,
                   mva_signal=0.0) -> float | Array:
        eta = np.asarray(
            self.log_multiplier(log_moneyness, premium, mva_signal),
            dtype=float,
        )
        relative_hazard = np.exp(np.clip(eta, -50.0, 50.0))
        relative_hazard = np.clip(
            relative_hazard,
            self.multiplier_floor,
            self.multiplier_cap,
        )
        return _scalar_or_array(
            relative_hazard, log_moneyness, premium, mva_signal
        )

    def annual_probability(self, base_probability, log_moneyness, premium,
                           mva_signal=0.0) -> float | Array:
        base, m, p, mva = np.broadcast_arrays(
            np.asarray(base_probability, dtype=float),
            np.asarray(log_moneyness, dtype=float),
            np.asarray(premium, dtype=float),
            np.asarray(mva_signal, dtype=float),
        )
        if not np.all(np.isfinite(base)) or np.any((base < 0.0) | (base > 1.0)):
            raise ValueError("Base hazard probabilities must lie in [0, 1].")
        relative_hazard = np.asarray(self.multiplier(m, p, mva), dtype=float)
        safe_base = np.minimum(base, 1.0 - 1e-15)
        mu0 = -np.log1p(-safe_base)
        adjusted = -np.expm1(-mu0 * relative_hazard)
        adjusted = np.clip(adjusted, self.annual_floor, self.annual_cap)
        adjusted = np.where(base <= 0.0, 0.0,
                            np.where(base >= 1.0, 1.0, adjusted))
        return _scalar_or_array(adjusted, base_probability, log_moneyness,
                                premium, mva_signal)

    def step_probability(self, base_probability, log_moneyness, premium,
                         dt: float, mva_signal=0.0) -> float | Array:
        if not np.isfinite(dt) or not 0.0 < dt <= 1.0:
            raise ValueError("Behaviour time step must be in (0, 1].")
        annual = np.asarray(self.annual_probability(
            base_probability, log_moneyness, premium, mva_signal), dtype=float)
        step = 1.0 - np.power(1.0 - annual, float(dt))
        return _scalar_or_array(step, base_probability, log_moneyness,
                                premium, mva_signal)


@dataclass(frozen=True)
class PerformanceLapseFunction:
    """Cause-specific stress hazard from a customer-visible crediting gap.

    ``g`` is the positive trailing log gap between the Reference-Fund factor
    and the credited factor after a deadband.  For the supplied Total-
    Protection design it is therefore principally a cap-shortfall signal, not
    a general measure of poor market performance.  The raw stress hazard rises
    smoothly towards ``excess_hazard_cap``.  A valuable guarantee applies a
    separate retention gate, but the performance cause is never constrained to
    be a multiple of the small ordinary lapse baseline:

        r(m)     = max(retention_floor, exp(-retention_gamma * max(m, 0)))
        mu_gap   = r(m) * mu_max * (1 - exp(-g / scale))

    This is deliberately an uncalibrated competing-risk proxy.  It prevents
    guarantee moneyness and the cap-shortfall signal from cancelling inside one
    linear predictor while preserving rational retention for valuable
    guarantees.  The supplied central assumption set activates it explicitly;
    that choice is a model-risk convention, not an experience calibration.
    """

    retention_gamma: float = 1.50
    retention_floor: float = 0.20
    shortfall_deadband: float = 0.02
    shortfall_max: float = 0.30
    excess_hazard_cap: float = 0.08
    excess_hazard_scale: float = 0.08
    annual_probability_cap: float = 0.30
    log_moneyness_max: float = float(np.log(4.0))

    def __post_init__(self) -> None:
        values = np.asarray([
            self.retention_gamma,
            self.retention_floor,
            self.shortfall_deadband,
            self.shortfall_max,
            self.excess_hazard_cap,
            self.excess_hazard_scale,
            self.annual_probability_cap,
            self.log_moneyness_max,
        ], dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError("Performance-lapse parameters must be finite.")
        if self.retention_gamma < 0.0:
            raise ValueError("retention_gamma must be non-negative.")
        if not 0.0 <= self.retention_floor <= 1.0:
            raise ValueError("retention_floor must lie in [0, 1].")
        if not 0.0 <= self.shortfall_deadband <= self.shortfall_max:
            raise ValueError(
                "shortfall_deadband must lie between zero and shortfall_max."
            )
        if self.excess_hazard_cap < 0.0:
            raise ValueError("excess_hazard_cap must be non-negative.")
        if self.excess_hazard_scale <= 0.0:
            raise ValueError("excess_hazard_scale must be positive.")
        if not 0.0 < self.annual_probability_cap <= 1.0:
            raise ValueError("annual_probability_cap must lie in (0, 1].")
        if self.log_moneyness_max <= 0.0:
            raise ValueError("log_moneyness_max must be positive.")

    def annual_excess_hazard(
        self,
        performance_shortfall,
        log_guarantee_moneyness,
    ) -> float | Array:
        gap, moneyness = np.broadcast_arrays(
            np.asarray(performance_shortfall, dtype=float),
            np.asarray(log_guarantee_moneyness, dtype=float),
        )
        if not np.all(np.isfinite(gap)) or not np.all(np.isfinite(moneyness)):
            raise ValueError("Performance-lapse inputs must be finite.")
        effective_gap = np.clip(
            np.maximum(gap - self.shortfall_deadband, 0.0),
            0.0,
            self.shortfall_max,
        )
        retention_moneyness = np.clip(
            np.maximum(moneyness, 0.0),
            0.0,
            self.log_moneyness_max,
        )
        retention = np.maximum(
            self.retention_floor,
            np.exp(-self.retention_gamma * retention_moneyness),
        )
        hazard = (
            retention
            * self.excess_hazard_cap
            * (1.0 - np.exp(-effective_gap / self.excess_hazard_scale))
        )
        return _scalar_or_array(
            hazard, performance_shortfall, log_guarantee_moneyness
        )


@dataclass(frozen=True)
class FractionalLogitFunction:
    """Fractional-logit response for an expected utilisation in [0, 1]."""

    beta_moneyness: float
    beta_log_premium: float
    beta_interaction: float
    reference_premium: float = 100_000.0
    log_moneyness_min: float = -float(np.log(2.0))
    log_moneyness_max: float = float(np.log(2.0))
    log_premium_min: float = -2.0
    log_premium_max: float = 2.0
    moneyness_transform: str = "positive_part"
    beta_mva: float = 0.0
    output_floor: float = 0.0
    output_cap: float = 1.0

    def __post_init__(self) -> None:
        _validate_transform(self.moneyness_transform)
        values = np.asarray([
            self.beta_moneyness, self.beta_log_premium,
            self.beta_interaction, self.beta_mva, self.reference_premium,
            self.log_moneyness_min, self.log_moneyness_max,
            self.log_premium_min, self.log_premium_max,
            self.output_floor, self.output_cap,
        ], dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError("Fractional-logit parameters must be finite.")
        if self.reference_premium <= 0.0:
            raise ValueError("reference_premium must be positive.")
        if self.log_moneyness_min >= self.log_moneyness_max \
                or self.log_premium_min >= self.log_premium_max:
            raise ValueError("Fractional-logit signal bounds must be increasing.")
        if not 0.0 <= self.output_floor <= self.output_cap <= 1.0:
            raise ValueError("Fractional-logit output floor/cap must lie in [0, 1].")

    def _linear_predictor(self, log_moneyness, premium, mva_signal=0.0) -> Array:
        m, p, mva = np.broadcast_arrays(
            np.asarray(log_moneyness, dtype=float),
            np.asarray(premium, dtype=float),
            np.asarray(mva_signal, dtype=float),
        )
        if not np.all(np.isfinite(m)) or not np.all(np.isfinite(p)) \
                or not np.all(np.isfinite(mva)):
            raise ValueError("Fractional-logit inputs must be finite.")
        if np.any(p <= 0.0):
            raise ValueError("Gross premium must be positive.")
        if np.any((mva < 0.0) | (mva > 1.0)):
            raise ValueError("MVA signal must lie in [0, 1].")
        m = np.clip(m, self.log_moneyness_min, self.log_moneyness_max)
        if self.moneyness_transform == "positive_part":
            m = np.maximum(m, 0.0)
        z = np.clip(np.log(p / self.reference_premium),
                    self.log_premium_min, self.log_premium_max)
        return (self.beta_moneyness * m
                + self.beta_log_premium * z
                + self.beta_interaction * m * z
                + self.beta_mva * mva)

    def odds_multiplier(self, log_moneyness, premium, mva_signal=0.0) -> float | Array:
        eta = self._linear_predictor(log_moneyness, premium, mva_signal)
        multiplier = np.exp(np.clip(eta, -50.0, 50.0))
        return _scalar_or_array(multiplier, log_moneyness, premium, mva_signal)

    def response(self, base_response, log_moneyness, premium,
                 mva_signal=0.0) -> float | Array:
        base, m, p, mva = np.broadcast_arrays(
            np.asarray(base_response, dtype=float),
            np.asarray(log_moneyness, dtype=float),
            np.asarray(premium, dtype=float),
            np.asarray(mva_signal, dtype=float),
        )
        if not np.all(np.isfinite(base)) or np.any((base < 0.0) | (base > 1.0)):
            raise ValueError("Base utilisation must lie in [0, 1].")
        eta = self._linear_predictor(m, p, mva)
        clipped = np.clip(base, 1e-12, 1.0 - 1e-12)
        logit_base = np.log(clipped) - np.log1p(-clipped)
        linear = np.clip(logit_base + eta, -50.0, 50.0)
        adjusted = 1.0 / (1.0 + np.exp(-linear))
        adjusted = np.clip(adjusted, self.output_floor, self.output_cap)
        adjusted = np.where(base <= 0.0, 0.0,
                            np.where(base >= 1.0, 1.0, adjusted))
        return _scalar_or_array(adjusted, base_response, log_moneyness,
                                premium, mva_signal)


@dataclass(frozen=True)
class LapseAssumptions:
    """Base annual full-surrender probabilities by policy year."""

    growth_phase: Sequence[float] = (0.03, 0.035, 0.04, 0.04, 0.04, 0.035,
                                     0.03, 0.03, 0.025, 0.02, 0.02)
    income_phase: float = 0.005

    def __post_init__(self) -> None:
        growth = tuple(float(x) for x in self.growth_phase)
        values = np.asarray((*growth, self.income_phase), dtype=float)
        if not np.all(np.isfinite(values)) or np.any((values < 0.0) | (values > 1.0)):
            raise ValueError("Lapse rates must be finite probabilities in [0, 1].")
        object.__setattr__(self, "growth_phase", growth)

    def growth_rate(self, policy_year: int) -> float:
        if isinstance(policy_year, bool) \
                or not isinstance(policy_year, (int, np.integer)) \
                or policy_year < 1:
            raise ValueError("policy_year must be a positive integer.")
        seq = list(self.growth_phase)
        return float(seq[min(policy_year - 1, len(seq) - 1)]) if seq else 0.0


def _default_growth_lapse_function() -> DynamicHazardFunction:
    return DynamicHazardFunction(
        beta_moneyness=-1.50, beta_log_premium=-0.10,
        beta_interaction=-0.50, moneyness_transform="signed",
        annual_floor=0.0, annual_cap=0.30,
        multiplier_floor=0.20, multiplier_cap=3.0,
    )


def _default_income_lapse_function() -> DynamicHazardFunction:
    return DynamicHazardFunction(
        beta_moneyness=-1.50, beta_log_premium=-0.10,
        beta_interaction=-0.50, moneyness_transform="signed",
        annual_floor=0.0, annual_cap=0.30,
        multiplier_floor=0.20, multiplier_cap=3.0,
    )


@dataclass(frozen=True)
class DynamicLapseParams:
    enabled: bool = True
    growth: DynamicHazardFunction = field(default_factory=_default_growth_lapse_function)
    income: DynamicHazardFunction = field(default_factory=_default_income_lapse_function)
    performance: PerformanceLapseFunction = field(
        default_factory=PerformanceLapseFunction
    )

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, (bool, np.bool_)):
            raise ValueError("Dynamic-lapse enabled must be boolean.")

    @staticmethod
    def _static_step_probability(base_annual, dt: float, *states):
        """Validated annual-to-step conversion when dynamics are disabled."""
        if not np.isfinite(dt) or not 0.0 < dt <= 1.0:
            raise ValueError("Behaviour time step must be in (0, 1].")
        arrays = np.broadcast_arrays(
            np.asarray(base_annual, dtype=float),
            *(np.asarray(state, dtype=float) for state in states),
        )
        annual = arrays[0]
        if not np.all(np.isfinite(annual)) or np.any(
            (annual < 0.0) | (annual > 1.0)
        ):
            raise ValueError("Base hazard probabilities must lie in [0, 1].")
        step = 1.0 - np.power(1.0 - annual, float(dt))
        return _scalar_or_array(step, base_annual, *states)

    def growth_probability(self, base_annual, log_iv_over_surrender,
                           premium, dt: float,
                           performance_shortfall=0.0) -> float | Array:
        if not self.enabled:
            return self._static_step_probability(
                base_annual,
                dt,
                log_iv_over_surrender,
                premium,
                performance_shortfall,
            )
        return self._combined_step_probability(
            self.growth,
            base_annual,
            log_iv_over_surrender,
            premium,
            dt,
            performance_shortfall,
        )

    def income_probability(self, base_annual, log_guarantee_moneyness,
                           premium, dt: float,
                           performance_shortfall=0.0) -> float | Array:
        if not self.enabled:
            return self._static_step_probability(
                base_annual,
                dt,
                log_guarantee_moneyness,
                premium,
                performance_shortfall,
            )
        return self._combined_step_probability(
            self.income,
            base_annual,
            log_guarantee_moneyness,
            premium,
            dt,
            performance_shortfall,
        )

    def _combined_step_probability(
        self,
        ordinary: DynamicHazardFunction,
        base_annual,
        log_moneyness,
        premium,
        dt: float,
        performance_shortfall,
    ) -> float | Array:
        """Combine ordinary and performance lapse as independent annual risks."""
        ordinary_step, performance_step = self._cause_step_probabilities(
            ordinary,
            base_annual,
            log_moneyness,
            premium,
            dt,
            performance_shortfall,
        )
        combined = np.asarray(ordinary_step) + np.asarray(performance_step)
        return _scalar_or_array(
            combined,
            base_annual,
            log_moneyness,
            premium,
            performance_shortfall,
        )

    def _cause_step_probabilities(
        self,
        ordinary: DynamicHazardFunction,
        base_annual,
        log_moneyness,
        premium,
        dt: float,
        performance_shortfall,
    ) -> tuple[float | Array, float | Array]:
        """Return mutually exclusive ordinary and performance exit masses.

        The total cause-specific annual hazard is first subjected to the
        combined annual probability cap.  The resulting step probability is
        then allocated in proportion to the uncapped cause hazards.  The two
        returned probabilities therefore add exactly to the modelled lapse
        probability without double counting simultaneous exits.
        """
        if not np.isfinite(dt) or not 0.0 < dt <= 1.0:
            raise ValueError("Behaviour time step must be in (0, 1].")
        ordinary_annual = np.asarray(
            ordinary.annual_probability(
                base_annual, log_moneyness, premium
            ),
            dtype=float,
        )
        performance_hazard = np.asarray(
            self.performance.annual_excess_hazard(
                performance_shortfall,
                log_moneyness,
            ),
            dtype=float,
        )
        ordinary_annual, performance_hazard = np.broadcast_arrays(
            ordinary_annual, performance_hazard
        )
        ordinary_hazard = -np.log1p(
            -np.minimum(ordinary_annual, 1.0 - 1.0e-15)
        )
        total_hazard = ordinary_hazard + performance_hazard
        combined_annual = -np.expm1(-total_hazard)
        # The cap limits only the incremental combined risk.  It must never
        # reduce an already larger ordinary probability (in particular an
        # exact contractual/base probability of one).
        combined_annual = np.maximum(
            ordinary_annual,
            np.minimum(
                combined_annual,
                self.performance.annual_probability_cap,
            ),
        )
        total_step = 1.0 - np.power(1.0 - combined_annual, float(dt))
        ordinary_step = np.divide(
            total_step * ordinary_hazard,
            total_hazard,
            out=np.zeros_like(total_step),
            where=total_hazard > 0.0,
        )
        ordinary_step = np.clip(ordinary_step, 0.0, total_step)
        performance_step = total_step - ordinary_step
        certain_ordinary = ordinary_annual >= 1.0
        ordinary_step = np.where(certain_ordinary, 1.0, ordinary_step)
        performance_step = np.where(certain_ordinary, 0.0, performance_step)
        ordinary_out = _scalar_or_array(
            ordinary_step,
            base_annual,
            log_moneyness,
            premium,
            performance_shortfall,
        )
        performance_out = _scalar_or_array(
            performance_step,
            base_annual,
            log_moneyness,
            premium,
            performance_shortfall,
        )
        return ordinary_out, performance_out

    def income_cause_probabilities(
        self,
        base_annual,
        log_guarantee_moneyness,
        premium,
        dt: float,
        performance_shortfall=0.0,
    ) -> tuple[float | Array, float | Array]:
        """Ordinary and performance cause probabilities for diagnostics."""
        if not self.enabled:
            ordinary = self._static_step_probability(
                base_annual,
                dt,
                log_guarantee_moneyness,
                premium,
                performance_shortfall,
            )
            zero = np.zeros_like(np.asarray(ordinary, dtype=float))
            return (
                ordinary,
                _scalar_or_array(
                    zero,
                    base_annual,
                    log_guarantee_moneyness,
                    premium,
                    performance_shortfall,
                ),
            )
        return self._cause_step_probabilities(
            self.income,
            base_annual,
            log_guarantee_moneyness,
            premium,
            dt,
            performance_shortfall,
        )

    def growth_cause_probabilities(
        self,
        base_annual,
        log_iv_over_surrender,
        premium,
        dt: float,
        performance_shortfall=0.0,
    ) -> tuple[float | Array, float | Array]:
        """Ordinary and performance cause probabilities for diagnostics."""
        if not self.enabled:
            ordinary = self._static_step_probability(
                base_annual,
                dt,
                log_iv_over_surrender,
                premium,
                performance_shortfall,
            )
            zero = np.zeros_like(np.asarray(ordinary, dtype=float))
            return (
                ordinary,
                _scalar_or_array(
                    zero,
                    base_annual,
                    log_iv_over_surrender,
                    premium,
                    performance_shortfall,
                ),
            )
        return self._cause_step_probabilities(
            self.growth,
            base_annual,
            log_iv_over_surrender,
            premium,
            dt,
            performance_shortfall,
        )

    # Compatibility diagnostics: return relative hazards for ratio inputs.
    def income_multiplier(self, moneyness, premium: Optional[float] = None):
        ref = self.income.reference_premium if premium is None else premium
        ratio = np.maximum(np.asarray(moneyness, dtype=float), 1e-300)
        return self.income.multiplier(np.log(ratio), ref)

    def growth_multiplier(self, sv_over_iv, premium: Optional[float] = None):
        ref = self.growth.reference_premium if premium is None else premium
        ratio = np.maximum(np.asarray(sv_over_iv, dtype=float), 1e-300)
        return self.growth.multiplier(-np.log(ratio), ref)


@dataclass(frozen=True)
class IncomeTakeUp:
    """Base income-commencement assumptions.

    ``dynamic`` uses the annual duration baseline as a proportional hazard
    which is re-evaluated from current market state and premium at each policy
    anniversary.  ``hazard`` retains the legacy market-independent draw and
    ``deterministic`` retains a fixed ``PolicySpec.income_start_year`` for
    contract-mechanics tests.  ``force_by_year`` is an optional legacy
    behavioural probability-one band; contractual automatic commencement is
    enforced separately by the projection.
    """

    mode: str = "deterministic"
    hazard: Sequence[float] = (0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.30, 0.30)
    force_by_year: Optional[int] = None

    def __post_init__(self) -> None:
        if self.mode not in ("deterministic", "hazard", "dynamic"):
            raise ValueError(
                "IncomeTakeUp.mode must be 'deterministic', 'hazard' or 'dynamic'.")
        if self.force_by_year is not None and (
            isinstance(self.force_by_year, bool)
            or not isinstance(self.force_by_year, (int, np.integer))
            or self.force_by_year < 1
        ):
            raise ValueError("force_by_year must be None or a positive integer.")
        hazard = tuple(float(x) for x in self.hazard)
        values = np.asarray(hazard, dtype=float)
        if not np.all(np.isfinite(values)) or np.any((values < 0.0) | (values > 1.0)):
            raise ValueError("Take-up hazards must be finite probabilities in [0, 1].")
        object.__setattr__(self, "hazard", hazard)

    def probability(self, policy_year: int) -> float:
        if self.mode == "deterministic":
            raise RuntimeError("Deterministic take-up is handled by projection.")
        if isinstance(policy_year, bool) \
                or not isinstance(policy_year, (int, np.integer)) \
                or policy_year < 1:
            raise ValueError("policy_year must be a positive integer.")
        if self.force_by_year is not None and policy_year >= self.force_by_year:
            return 1.0
        seq = list(self.hazard)
        return float(seq[min(policy_year - 1, len(seq) - 1)]) if seq else 0.0


def _default_take_up_function() -> DynamicHazardFunction:
    return DynamicHazardFunction(
        beta_moneyness=4.00, beta_log_premium=0.50,
        beta_interaction=0.25, moneyness_transform="signed",
        annual_floor=0.0, annual_cap=0.50,
        multiplier_floor=0.05, multiplier_cap=25.0,
    )


@dataclass(frozen=True)
class DynamicTakeUpParams:
    """State-dependent annual Income-Election response.

    The core proportional-hazard response retains its governed guarantee-
    moneyness and issue-premium coefficients.  The additional coefficients
    expose only states known at the current Anniversary: post-credit/post-fee
    Account Value, prospective annual income if elected now, and the previous
    complete-fund/credited returns.  They are versioned Behaviour proxies, not
    market inputs or a physical calibration.
    """

    enabled: bool = True
    function: DynamicHazardFunction = field(default_factory=_default_take_up_function)
    beta_log_account_value: float = 0.0
    beta_prospective_income_ratio: float = 0.0
    beta_reference_return: float = 0.0
    beta_credited_return: float = 0.0
    beta_performance_gap: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, (bool, np.bool_)):
            raise ValueError("Dynamic take-up enabled must be boolean.")
        values = np.asarray([
            self.beta_log_account_value,
            self.beta_prospective_income_ratio,
            self.beta_reference_return,
            self.beta_credited_return,
            self.beta_performance_gap,
        ], dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError("Dynamic take-up state coefficients must be finite.")

    def probability(
        self,
        base_annual,
        log_guarantee_moneyness,
        premium,
        *,
        account_value=None,
        prospective_annual_income=None,
        previous_reference_return=0.0,
        previous_credited_return=0.0,
        performance_gap=0.0,
    ) -> float | Array:
        if not self.enabled:
            return base_annual
        account = premium if account_value is None else account_value
        prospective = (
            np.asarray(account, dtype=float) * 0.0
            if prospective_annual_income is None
            else prospective_annual_income
        )
        base, m, paid, av, income, reference_return, credited_return, gap = (
            np.broadcast_arrays(
                np.asarray(base_annual, dtype=float),
                np.asarray(log_guarantee_moneyness, dtype=float),
                np.asarray(premium, dtype=float),
                np.asarray(account, dtype=float),
                np.asarray(prospective, dtype=float),
                np.asarray(previous_reference_return, dtype=float),
                np.asarray(previous_credited_return, dtype=float),
                np.asarray(performance_gap, dtype=float),
            )
        )
        if (
            np.any((base < 0.0) | (base > 1.0))
            or np.any(paid <= 0.0)
            or np.any(av < 0.0)
            or np.any(income < 0.0)
            or not all(np.all(np.isfinite(value)) for value in (
                base, m, paid, av, income,
                reference_return, credited_return, gap,
            ))
        ):
            raise ValueError("Dynamic take-up states must be finite and non-negative where required.")
        log_av = np.clip(
            np.log(np.maximum(av, 1.0e-300) / paid),
            self.function.log_premium_min,
            self.function.log_premium_max,
        )
        income_ratio = np.clip(income / paid, 0.0, 1.0)
        reference_return = np.clip(reference_return, -1.0, 1.0)
        credited_return = np.clip(credited_return, -1.0, 1.0)
        gap = np.clip(gap, 0.0, 1.0)
        extra_eta = (
            self.beta_log_account_value * log_av
            + self.beta_prospective_income_ratio * income_ratio
            + self.beta_reference_return * reference_return
            + self.beta_credited_return * credited_return
            + self.beta_performance_gap * gap
        )
        core_eta = np.asarray(
            self.function.log_multiplier(m, paid), dtype=float
        )
        relative = np.exp(np.clip(core_eta + extra_eta, -50.0, 50.0))
        relative = np.clip(
            relative,
            self.function.multiplier_floor,
            self.function.multiplier_cap,
        )
        safe_base = np.minimum(base, 1.0 - 1.0e-15)
        adjusted = -np.expm1(np.log1p(-safe_base) * relative)
        adjusted = np.clip(
            adjusted,
            self.function.annual_floor,
            self.function.annual_cap,
        )
        adjusted = np.where(
            base <= 0.0,
            0.0,
            np.where(base >= 1.0, 1.0, adjusted),
        )
        return _scalar_or_array(
            np.asarray(adjusted, dtype=float),
            base_annual,
            log_guarantee_moneyness,
            premium,
            account,
            prospective,
            previous_reference_return,
            previous_credited_return,
            performance_gap,
        )


@dataclass(frozen=True)
class WithdrawalBehaviour:
    """Base expected partial-withdrawal utilisation.

    ``free_utilisation`` is the expected fraction of the annual Free
    Withdrawal Amount used. ``excess_rate`` is the expected annual gross
    excess withdrawal as a fraction of current IV.  In the dynamic production
    basis both are transformed pathwise by fractional-logit functions.
    """

    free_utilisation: float = 0.0
    excess_rate: float = 0.0
    frequency: str = "annual"

    def __post_init__(self) -> None:
        if self.frequency not in ("annual", "monthly"):
            raise ValueError("frequency must be 'annual' or 'monthly'.")
        values = np.asarray([self.free_utilisation, self.excess_rate], dtype=float)
        if not np.all(np.isfinite(values)) or np.any(values < 0.0):
            raise ValueError("Withdrawal assumptions must be finite and non-negative.")
        if self.free_utilisation > 1.0 or self.excess_rate > 1.0:
            raise ValueError("Withdrawal utilisation/rate cannot exceed 100%.")


def _default_free_withdrawal_function() -> FractionalLogitFunction:
    return FractionalLogitFunction(
        beta_moneyness=0.50, beta_log_premium=-0.25,
        beta_interaction=-0.10, beta_mva=0.0,
        moneyness_transform="positive_part",
    )


def _default_excess_withdrawal_function() -> FractionalLogitFunction:
    return FractionalLogitFunction(
        beta_moneyness=-0.50, beta_log_premium=-0.25,
        beta_interaction=-0.10, beta_mva=-2.0,
        moneyness_transform="signed",
    )


@dataclass(frozen=True)
class DynamicWithdrawalParams:
    enabled: bool = True
    free: FractionalLogitFunction = field(
        default_factory=_default_free_withdrawal_function)
    excess: FractionalLogitFunction = field(
        default_factory=_default_excess_withdrawal_function)

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, (bool, np.bool_)):
            raise ValueError("Dynamic-withdrawal enabled must be boolean.")

    def free_utilisation(self, base, log_guarantee_moneyness,
                         premium, mva_signal=0.0) -> float | Array:
        if not self.enabled:
            return base
        return self.free.response(base, log_guarantee_moneyness,
                                  premium, mva_signal)

    def excess_rate(self, base, log_guarantee_moneyness,
                    premium, mva_signal=0.0) -> float | Array:
        if not self.enabled:
            return base
        return self.excess.response(base, log_guarantee_moneyness,
                                    premium, mva_signal)

    # Compatibility diagnostics for the legacy multiplier API.
    def multiplier(self, moneyness, premium: Optional[float] = None):
        ref = self.free.reference_premium if premium is None else premium
        ratio = np.maximum(np.asarray(moneyness, dtype=float), 1e-300)
        return self.free.odds_multiplier(np.log(ratio), ref)

    def mva_multiplier(self, mva_factor):
        """Legacy diagnostic for the active excess-withdrawal MVA effect."""
        f = np.asarray(mva_factor, dtype=float)
        if not np.all(np.isfinite(f)):
            raise ValueError("MVA factors must be finite.")
        f = np.clip(f, 0.0, 1.0)
        return np.exp(np.clip(self.excess.beta_mva * f, -50.0, 50.0))


@dataclass(frozen=True)
class BehaviourModel:
    """Container for behaviour assumptions.

    Production entry points must use ``load_dynamic_behaviour_assumptions``;
    the bare constructor deliberately retains deterministic/zero mechanics
    defaults so isolated contractual tests need no repository file I/O.
    """

    regime: str = "static"                  # "static" | "dynamic"
    lapse: LapseAssumptions = field(default_factory=LapseAssumptions)
    dynamic: DynamicLapseParams = field(default_factory=DynamicLapseParams)
    take_up: IncomeTakeUp = field(default_factory=IncomeTakeUp)
    dynamic_take_up: DynamicTakeUpParams = field(default_factory=DynamicTakeUpParams)
    withdrawals: WithdrawalBehaviour = field(default_factory=WithdrawalBehaviour)
    dynamic_withdrawals: DynamicWithdrawalParams = field(
        default_factory=DynamicWithdrawalParams)

    def __post_init__(self) -> None:
        if self.regime == "optimal":
            raise ValueError(
                "LSMC optimal behaviour is temporarily archived and is not an active regime.")
        if self.regime not in ("static", "dynamic"):
            raise ValueError("regime must be 'static' or 'dynamic'.")

    @property
    def use_dynamic(self) -> bool:
        return self.regime == "dynamic" and self.dynamic.enabled

    @property
    def use_dynamic_take_up(self) -> bool:
        return (self.regime == "dynamic" and self.take_up.mode == "dynamic"
                and self.dynamic_take_up.enabled)

    @property
    def use_dynamic_withdrawals(self) -> bool:
        return self.regime == "dynamic" and self.dynamic_withdrawals.enabled

    def scaled_lapses(self, factor: float) -> "BehaviourModel":
        if not np.isfinite(factor) or factor < 0.0:
            raise ValueError("Lapse scale factor must be finite and non-negative.")
        lapse = LapseAssumptions(
            growth_phase=tuple(min(r * factor, 1.0) for r in self.lapse.growth_phase),
            income_phase=min(self.lapse.income_phase * factor, 1.0))
        # A lapse stress applies to both independent exit causes.  Keeping the
        # performance cause unchanged would make ``factor=0`` leave material
        # lapse in place and would understate conventional lapse stresses.
        performance = replace(
            self.dynamic.performance,
            excess_hazard_cap=self.dynamic.performance.excess_hazard_cap * factor,
        )
        return replace(
            self,
            lapse=lapse,
            dynamic=replace(self.dynamic, performance=performance),
        )

    def scaled_take_up(self, factor: float) -> "BehaviourModel":
        if not np.isfinite(factor) or factor < 0.0:
            raise ValueError("Take-up scale factor must be finite and non-negative.")
        hazard = tuple(min(r * factor, 1.0) for r in self.take_up.hazard)
        return replace(self, take_up=replace(self.take_up, hazard=hazard))

    def without_post_election_behaviour(self) -> "BehaviourModel":
        """Retain Election assumptions but remove voluntary Income exits.

        This is the explicit Continue benchmark used to separate the value of
        a changed Income-Election time from behaviour after Election.  Product
        gates already prohibit every Growth withdrawal and surrender action.
        """
        return replace(
            self,
            lapse=replace(self.lapse, income_phase=0.0),
            dynamic=replace(self.dynamic, enabled=False),
            dynamic_withdrawals=replace(
                self.dynamic_withdrawals, enabled=False
            ),
            withdrawals=WithdrawalBehaviour(
                free_utilisation=0.0,
                excess_rate=0.0,
                frequency=self.withdrawals.frequency,
            ),
        )

    @staticmethod
    def static_only() -> "BehaviourModel":
        return BehaviourModel(
            regime="static",
            dynamic=DynamicLapseParams(enabled=False),
            dynamic_take_up=DynamicTakeUpParams(enabled=False),
            dynamic_withdrawals=DynamicWithdrawalParams(enabled=False),
        )
