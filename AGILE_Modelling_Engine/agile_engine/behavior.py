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
``agile_engine.lsmc`` as archived research code and is not a behaviour regime.

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

    def _signals(self, log_moneyness, premium, mva_signal=0.0) -> tuple[Array, Array, Array]:
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

    def multiplier(self, log_moneyness, premium, mva_signal=0.0) -> float | Array:
        m, z, mva = self._signals(log_moneyness, premium, mva_signal)
        eta = (self.beta_moneyness * m
               + self.beta_log_premium * z
               + self.beta_interaction * m * z
               + self.beta_mva * mva)
        relative_hazard = np.exp(np.clip(eta, -50.0, 50.0))
        relative_hazard = np.clip(relative_hazard,
                                  self.multiplier_floor,
                                  self.multiplier_cap)
        return _scalar_or_array(relative_hazard, log_moneyness, premium, mva_signal)

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
        seq = list(self.growth_phase)
        return float(seq[min(policy_year - 1, len(seq) - 1)]) if seq else 0.0


def _default_growth_lapse_function() -> DynamicHazardFunction:
    return DynamicHazardFunction(
        beta_moneyness=-1.50, beta_log_premium=-0.10,
        beta_interaction=-0.50, moneyness_transform="positive_part",
        annual_floor=0.0, annual_cap=0.30,
        multiplier_floor=0.20, multiplier_cap=3.0,
    )


def _default_income_lapse_function() -> DynamicHazardFunction:
    return DynamicHazardFunction(
        beta_moneyness=-1.50, beta_log_premium=-0.10,
        beta_interaction=-0.50, moneyness_transform="positive_part",
        annual_floor=0.0, annual_cap=0.30,
        multiplier_floor=0.20, multiplier_cap=3.0,
    )


@dataclass(frozen=True)
class DynamicLapseParams:
    enabled: bool = True
    growth: DynamicHazardFunction = field(default_factory=_default_growth_lapse_function)
    income: DynamicHazardFunction = field(default_factory=_default_income_lapse_function)

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, (bool, np.bool_)):
            raise ValueError("Dynamic-lapse enabled must be boolean.")

    def growth_probability(self, base_annual, log_iv_over_surrender,
                           premium, dt: float) -> float | Array:
        if not self.enabled:
            annual = np.asarray(base_annual, dtype=float)
            out = 1.0 - np.power(1.0 - annual, dt)
            return _scalar_or_array(out, base_annual, log_iv_over_surrender, premium)
        return self.growth.step_probability(
            base_annual, log_iv_over_surrender, premium, dt)

    def income_probability(self, base_annual, log_guarantee_moneyness,
                           premium, dt: float) -> float | Array:
        if not self.enabled:
            annual = np.asarray(base_annual, dtype=float)
            out = 1.0 - np.power(1.0 - annual, dt)
            return _scalar_or_array(out, base_annual,
                                    log_guarantee_moneyness, premium)
        return self.income.step_probability(
            base_annual, log_guarantee_moneyness, premium, dt)

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
    contract-mechanics tests.
    """

    mode: str = "deterministic"
    hazard: Sequence[float] = (0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.30, 0.30)
    force_by_year: int = 15

    def __post_init__(self) -> None:
        if self.mode not in ("deterministic", "hazard", "dynamic"):
            raise ValueError(
                "IncomeTakeUp.mode must be 'deterministic', 'hazard' or 'dynamic'.")
        if isinstance(self.force_by_year, bool) \
                or not isinstance(self.force_by_year, (int, np.integer)) \
                or self.force_by_year < 1:
            raise ValueError("force_by_year must be a positive integer.")
        hazard = tuple(float(x) for x in self.hazard)
        values = np.asarray(hazard, dtype=float)
        if not np.all(np.isfinite(values)) or np.any((values < 0.0) | (values > 1.0)):
            raise ValueError("Take-up hazards must be finite probabilities in [0, 1].")
        object.__setattr__(self, "hazard", hazard)

    def probability(self, policy_year: int) -> float:
        if self.mode == "deterministic":
            raise RuntimeError("Deterministic take-up is handled by projection.")
        if policy_year >= self.force_by_year:
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
    enabled: bool = True
    function: DynamicHazardFunction = field(default_factory=_default_take_up_function)

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, (bool, np.bool_)):
            raise ValueError("Dynamic take-up enabled must be boolean.")

    def probability(self, base_annual, log_guarantee_moneyness,
                    premium) -> float | Array:
        if not self.enabled:
            return base_annual
        return self.function.annual_probability(
            base_annual, log_guarantee_moneyness, premium)


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
        beta_interaction=-0.10, beta_mva=-2.0,
        moneyness_transform="positive_part",
    )


def _default_excess_withdrawal_function() -> FractionalLogitFunction:
    return FractionalLogitFunction(
        beta_moneyness=0.50, beta_log_premium=-0.25,
        beta_interaction=-0.10, beta_mva=-2.0,
        moneyness_transform="positive_part",
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
        f = np.maximum(np.asarray(mva_factor, dtype=float), 0.0)
        return np.exp(np.clip(self.free.beta_mva * f, -50.0, 0.0))


@dataclass(frozen=True)
class BehaviourModel:
    """Container for behaviour assumptions.

    Production entry points must use ``load_dynamic_behaviour_assumptions``;
    the bare constructor deliberately retains deterministic/zero mechanics
    defaults so isolated contractual tests need no repository file I/O.
    """

    regime: str = "dynamic"                 # "static" | "dynamic"
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
        return replace(self, lapse=lapse)

    def scaled_take_up(self, factor: float) -> "BehaviourModel":
        if not np.isfinite(factor) or factor < 0.0:
            raise ValueError("Take-up scale factor must be finite and non-negative.")
        hazard = tuple(min(r * factor, 1.0) for r in self.take_up.hazard)
        return replace(self, take_up=replace(self.take_up, hazard=hazard))

    @staticmethod
    def static_only() -> "BehaviourModel":
        return BehaviourModel(
            regime="static",
            dynamic=DynamicLapseParams(enabled=False),
            dynamic_take_up=DynamicTakeUpParams(enabled=False),
            dynamic_withdrawals=DynamicWithdrawalParams(enabled=False),
        )
