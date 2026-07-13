"""Market-consistent valuation of a weighted policyholder portfolio.

The implementation deliberately performs plain risk-neutral Monte Carlo only.
One common market scenario set is reused for every model point and every
optional fee solve.  Model points are projected sequentially and only scalar
results are retained.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from types import MappingProxyType
from typing import Callable, Mapping, Optional

import numpy as np
from scipy.optimize import brentq

from ._provenance import assumption_fingerprint
from .behavior import BehaviourModel
from .esg import ESGConfig, Measure, ScenarioSet, STEPS_PER_YEAR
from .model_points import PolicyholderModelPoint, PolicyholderModelPointSet
from .mortality import MortalityTable
from .pricing import (
    ValuationResult,
    ValuationSettings,
    build_scenarios,
    resolve_horizon,
    value_contract,
)
from .product import (ExpenseAssumptions, IndexLinkedLifetimeIncomeProduct,
                      PolicySpec, SpouseDeathElection)
from .projection import ProjectionConfig, ProjectionResult


_MONETARY_METRICS = (
    "premium_aud",
    "pv_policyholder_benefits_aud",
    "pv_policyholder_benefits_pre_election_aud",
    "pv_policyholder_benefits_post_election_aud",
    "pv_terminal_closeout_aud",
    "pv_future_fees_aud",
    "pv_product_fees_aud",
    "pv_lifetime_income_premiums_aud",
    "pv_guarantee_claims_aud",
    "pv_expenses_aud",
    "pv_hedge_costs_aud",
    "pv_crediting_margin_aud",
    "pv_money_market_income_aud",
    "pv_hedge_gain_aud",
    "pv_hedge_option_fair_value_costs_aud",
    "pv_hedge_option_markup_costs_aud",
    "pv_hedge_management_fee_costs_aud",
    "pv_hedge_execution_costs_aud",
    "pv_hedge_cost_reconciliation_gap_aud",
    "pv_crediting_margin_reconciliation_gap_aud",
    "pv_growth_fees_aud",
    "pv_growth_crediting_margin_aud",
    "pv_post_election_guarantee_claims_aud",
    "pv_mva_retained_aud",
    "pv_aps_retained_aud",
    "bel_nonunit_aud",
    "bel_total_aud",
    "market_consistent_bel_total_aud",
    "guarantee_value_aud",
    "insurer_net_present_value_before_risk_margin_aud",
)


def _normalised_positive_weights(
    values: tuple[float, ...],
    *,
    label: str,
) -> tuple[float, ...]:
    """Return positive shares with an explicit final floating-point residual."""
    if not values or any(not isfinite(value) or value <= 0.0 for value in values):
        raise ValueError(f"{label} must contain positive finite values.")
    total = sum(values)
    if not isfinite(total) or total <= 0.0:
        raise ValueError(f"{label} must have a positive finite sum.")
    shares = [value / total for value in values]
    shares[-1] = 1.0 - sum(shares[:-1])
    if shares[-1] <= 0.0:
        raise ValueError(f"{label} cannot be normalised to positive shares.")
    return tuple(shares)


@dataclass(frozen=True)
class _ScalarValuation:
    """Projection-free valuation scalars retained by the portfolio layer."""

    pv: Mapping[str, float]
    premium: float
    bel_nonunit: float
    bel_total: float
    guarantee_value: float
    insurer_net_value: float
    identity_gap: float
    behaviour_diagnostics: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "pv", MappingProxyType({
            key: float(value) for key, value in self.pv.items()
        }))
        object.__setattr__(
            self,
            "behaviour_diagnostics",
            MappingProxyType(dict(self.behaviour_diagnostics)),
        )


def _discrete_timing_quantile(
    years: np.ndarray,
    masses: np.ndarray,
    quantile: float,
) -> Optional[float]:
    total = float(np.sum(masses))
    if total <= 0.0:
        return None
    threshold = float(quantile) * total
    index = int(np.searchsorted(np.cumsum(masses), threshold, side="left"))
    return float(years[min(index, len(years) - 1)])


def _projection_behaviour_diagnostics(
    projection: ProjectionResult,
) -> dict[str, object]:
    """Collapse path diagnostics before the portfolio drops projection arrays."""
    required = (
        projection.eligible_growth_exposure,
        projection.income_take_up_probability,
        projection.income_election_events,
        projection.forced_income_election_events,
        projection.growth_exposure,
        projection.income_exposure,
        projection.ordinary_lapse_probabilities,
        projection.performance_lapse_probabilities,
        projection.total_lapse_probabilities,
        projection.ordinary_lapse_events,
        projection.performance_lapse_events,
    )
    if any(value is None for value in required):
        return {}

    eligible = np.asarray(projection.eligible_growth_exposure, dtype=float)
    take_up_probability = np.asarray(
        projection.income_take_up_probability, dtype=float
    )
    election_events = np.asarray(projection.income_election_events, dtype=float)
    forced_events = np.asarray(
        projection.forced_income_election_events, dtype=float
    )
    growth_exposure = np.asarray(projection.growth_exposure, dtype=float)
    income_exposure = np.asarray(projection.income_exposure, dtype=float)
    post_action_income_exposure = np.maximum(
        np.asarray(projection.inforce, dtype=float) - growth_exposure,
        0.0,
    )
    ordinary_probability = np.asarray(
        projection.ordinary_lapse_probabilities, dtype=float
    )
    performance_probability = np.asarray(
        projection.performance_lapse_probabilities, dtype=float
    )
    total_probability = np.asarray(
        projection.total_lapse_probabilities, dtype=float
    )
    n_steps = election_events.shape[1] - 1
    anniversary_steps = np.arange(
        STEPS_PER_YEAR,
        n_steps + 1,
        STEPS_PER_YEAR,
        dtype=int,
    )
    years = anniversary_steps.astype(float) / STEPS_PER_YEAR
    election_mass = np.asarray([
        np.mean(election_events[:, step]) for step in anniversary_steps
    ], dtype=float)
    forced_mass = np.asarray([
        np.mean(forced_events[:, step]) for step in anniversary_steps
    ], dtype=float)
    eligible_mass = np.asarray([
        np.mean(eligible[:, step]) for step in anniversary_steps
    ], dtype=float)
    probability_numerator = np.asarray([
        np.mean(eligible[:, step] * take_up_probability[:, step])
        for step in anniversary_steps
    ], dtype=float)

    total_election_mass = float(np.sum(election_mass))
    total_forced_mass = float(np.sum(forced_mass))
    expected_year = (
        None
        if total_election_mass <= 0.0
        else float(np.sum(years * election_mass) / total_election_mass)
    )
    median_year = _discrete_timing_quantile(years, election_mass, 0.50)
    p10_year = _discrete_timing_quantile(years, election_mass, 0.10)
    p90_year = _discrete_timing_quantile(years, election_mass, 0.90)
    forced_share = (
        None
        if total_election_mass <= 0.0
        else total_forced_mass / total_election_mass
    )
    dt = np.diff(np.asarray(projection.times, dtype=float))
    growth_duration = float(np.sum(
        np.mean(growth_exposure[:, :-1], axis=0) * dt
    ))
    income_duration = float(np.sum(
        np.mean(post_action_income_exposure[:, :-1], axis=0) * dt
    ))
    total_income_exposure = float(np.sum(np.mean(income_exposure, axis=0)))
    horizon = float(projection.horizon_years)

    diagnostics: dict[str, object] = {
        "income_election_event_mass": total_election_mass,
        "income_election_share": total_election_mass,
        "forced_income_election_event_mass": total_forced_mass,
        "forced_income_election_share": forced_share,
        "expected_income_start_year": expected_year,
        "median_income_start_year": median_year,
        "p10_income_start_year": p10_year,
        "p90_income_start_year": p90_year,
        "income_start_year_mean": expected_year,
        "income_start_year_median": median_year,
        "income_start_year_p10": p10_year,
        "income_start_year_p90": p90_year,
        "mean_growth_phase_duration_years": growth_duration,
        "mean_growth_duration": growth_duration,
        "unconditional_growth_exposure_years": growth_duration,
        "unconditional_income_exposure_years": income_duration,
        "income_exposure_months": total_income_exposure,
        "growth_phase_exposure": (
            0.0 if horizon <= 0.0 else growth_duration / horizon
        ),
        "income_phase_exposure": (
            0.0 if horizon <= 0.0 else income_duration / horizon
        ),
    }

    def exposure_weighted_probability(values: np.ndarray) -> Optional[float]:
        if total_income_exposure <= 0.0:
            return None
        return float(np.sum(np.mean(income_exposure * values, axis=0))
                     / total_income_exposure)

    ordinary_lapse_rate = exposure_weighted_probability(ordinary_probability)
    performance_lapse_rate = exposure_weighted_probability(
        performance_probability
    )
    total_lapse_rate = exposure_weighted_probability(total_probability)
    ordinary_event_mass = float(np.sum(np.mean(
        income_exposure * ordinary_probability, axis=0
    )))
    performance_event_mass = float(np.sum(np.mean(
        income_exposure * performance_probability, axis=0
    )))
    total_event_mass = float(np.sum(np.mean(
        income_exposure * total_probability, axis=0
    )))
    diagnostics.update({
        "ordinary_income_lapse_probability": ordinary_lapse_rate,
        "performance_income_lapse_probability": performance_lapse_rate,
        "total_income_lapse_probability": total_lapse_rate,
        "ordinary_income_lapse_rate": ordinary_lapse_rate,
        "performance_income_lapse_rate": performance_lapse_rate,
        "total_income_lapse_rate": total_lapse_rate,
        "ordinary_income_lapse_event_mass": ordinary_event_mass,
        "performance_income_lapse_event_mass": performance_event_mass,
        "total_income_lapse_event_mass": total_event_mass,
    })

    for index, (step, year) in enumerate(zip(anniversary_steps, years)):
        label = int(round(float(year)))
        annual_probability = (
            None
            if eligible_mass[index] <= 0.0
            else probability_numerator[index] / eligible_mass[index]
        )
        election_rate_among_eligible = (
            None
            if eligible_mass[index] <= 0.0
            else election_mass[index] / eligible_mass[index]
        )
        lo = max(step - STEPS_PER_YEAR + 1, 0)
        hi = step + 1
        diagnostics.update({
            f"eligible_growth_exposure_policy_year_{label}": (
                float(eligible_mass[index])
            ),
            f"annual_take_up_probability_policy_year_{label}": (
                annual_probability
            ),
            # Share of the original issue cohort electing in this policy year.
            # The conditional action rate remains available separately below.
            f"income_election_share_policy_year_{label}": float(
                election_mass[index]
            ),
            f"income_election_rate_among_eligible_policy_year_{label}": (
                election_rate_among_eligible
            ),
            f"income_election_event_mass_policy_year_{label}": (
                float(election_mass[index])
            ),
            f"forced_income_election_event_mass_policy_year_{label}": (
                float(forced_mass[index])
            ),
            f"mean_growth_exposure_policy_year_{label}": float(np.mean(
                growth_exposure[:, lo:hi]
            )),
            f"mean_income_exposure_policy_year_{label}": float(np.mean(
                income_exposure[:, lo:hi]
            )),
            f"growth_phase_share_policy_year_{label}": float(np.mean(
                growth_exposure[:, step]
            )),
            f"income_phase_share_policy_year_{label}": float(np.mean(
                post_action_income_exposure[:, step]
            )),
        })
    return diagnostics


def _scalarize(valuation: ValuationResult) -> _ScalarValuation:
    """Drop path arrays before portfolio aggregation or another fee solve."""
    return _ScalarValuation(
        pv=valuation.pv,
        premium=float(valuation.premium),
        bel_nonunit=float(valuation.bel_nonunit),
        bel_total=float(valuation.bel_total),
        guarantee_value=float(valuation.guarantee_value),
        insurer_net_value=float(valuation.insurer_net_value),
        identity_gap=float(valuation.identity_gap),
        behaviour_diagnostics=_projection_behaviour_diagnostics(
            valuation.projection
        ),
    )


@dataclass(frozen=True)
class FairFeeSolveResult:
    """Outcome of one common-random-number fee solve."""

    objective: str
    status: str
    fee_rate: Optional[float]
    lower_rate: float
    upper_rate: float
    objective_at_lower_aud: float
    objective_at_upper_aud: float
    residual_aud: Optional[float]
    iterations: int
    value_basis: str = "per_contract"

    @property
    def solved(self) -> bool:
        return self.fee_rate is not None and self.status.startswith("solved")

    def as_dict(self, prefix: str) -> dict[str, object]:
        return {
            f"{prefix}_objective": self.objective,
            f"{prefix}_value_basis": self.value_basis,
            f"{prefix}_status": self.status,
            f"{prefix}_rate": self.fee_rate,
            f"{prefix}_lower_rate": self.lower_rate,
            f"{prefix}_upper_rate": self.upper_rate,
            f"{prefix}_objective_at_lower_aud": self.objective_at_lower_aud,
            f"{prefix}_objective_at_upper_aud": self.objective_at_upper_aud,
            f"{prefix}_residual_aud": self.residual_aud,
            f"{prefix}_iterations": self.iterations,
        }


@dataclass(frozen=True)
class PortfolioProgress:
    """One progress event emitted by the portfolio valuation workflow."""

    stage: str
    completed: int
    total: int
    model_point_id: Optional[str] = None
    detail: str = ""


@dataclass(frozen=True)
class ModelPointPortfolioValuation:
    """Per-contract value and post-valuation contributions of one model point."""

    model_point: PolicyholderModelPoint
    normalised_contract_share: float
    per_contract_metrics: Mapping[str, object]
    normalised_contribution_metrics: Mapping[str, float]
    represented_contract_count: Optional[float]
    portfolio_contribution_metrics: Optional[Mapping[str, float]]
    fair_lip: Optional[FairFeeSolveResult] = None
    commercial_break_even_lip: Optional[FairFeeSolveResult] = None

    def __post_init__(self) -> None:
        if (
            not isfinite(self.normalised_contract_share)
            or self.normalised_contract_share <= 0.0
        ):
            raise ValueError("normalised_contract_share must be positive and finite.")
        if self.represented_contract_count is not None and (
            not isfinite(self.represented_contract_count)
            or self.represented_contract_count <= 0.0
        ):
            raise ValueError("represented_contract_count must be positive and finite.")
        if (
            self.represented_contract_count is None
        ) != (
            self.portfolio_contribution_metrics is None
        ):
            raise ValueError(
                "Absolute contribution metrics require a represented contract count."
            )
        object.__setattr__(
            self,
            "per_contract_metrics",
            MappingProxyType(dict(self.per_contract_metrics)),
        )
        object.__setattr__(
            self,
            "normalised_contribution_metrics",
            MappingProxyType(dict(self.normalised_contribution_metrics)),
        )
        if self.portfolio_contribution_metrics is not None:
            object.__setattr__(
                self,
                "portfolio_contribution_metrics",
                MappingProxyType(dict(self.portfolio_contribution_metrics)),
            )

    @property
    def metrics(self) -> Mapping[str, object]:
        """Backward-compatible alias for per-contract metrics."""
        return self.per_contract_metrics

    @property
    def weighted_metrics(self) -> Mapping[str, float]:
        """Backward-compatible alias for the available contribution basis."""
        if self.portfolio_contribution_metrics is not None:
            return self.portfolio_contribution_metrics
        return self.normalised_contribution_metrics

    def as_dict(self) -> dict[str, object]:
        policy = self.model_point.policy
        out: dict[str, object] = {
            "model_point_id": self.model_point.model_point_id,
            "source_row_number": self.model_point.source_row_number,
            "contract_weight": self.model_point.contract_weight,
            "normalised_contract_share": self.normalised_contract_share,
            "premium_volume_weight_control": self.model_point.premium_volume_weight,
            "source_exposure_count": self.model_point.exposure_count,
            "represented_contract_count": self.represented_contract_count,
            "primary_age": policy.age,
            "primary_sex": policy.sex.value,
            "spouse": policy.spouse,
            "secondary_age": policy.spouse_age,
            "secondary_sex": None if policy.spouse_sex is None else policy.spouse_sex.value,
            "income_start_year": policy.income_start_year,
            "deterministic_benchmark_income_start_year": (
                policy.income_start_year
            ),
            "effective_income_start_year": self.per_contract_metrics.get(
                "effective_income_start_year"
            ),
            "income_type": policy.income_type.value,
            "source_product_id": self.model_point.product_id,
            "source_product_pds_version": self.model_point.product_pds_version,
            "rate_card_vintage": self.model_point.rate_card_vintage,
            "cap_vintage_legacy_metadata": self.model_point.cap_vintage,
            "market_parameter_set_id": self.model_point.market_parameter_set_id,
            "yield_curve_id": self.model_point.yield_curve_id,
            "charged_lip_rate": self.per_contract_metrics["charged_lip_rate"],
            "profitability_classification": self.per_contract_metrics[
                "profitability_classification"
            ],
            "behaviour_treatment": self.per_contract_metrics.get(
                "behaviour_treatment"
            ),
        }
        out.update({
            f"per_contract_{key}": value
            for key, value in self.per_contract_metrics.items()
        })
        out.update({
            f"normalised_contribution_{key}": value
            for key, value in self.normalised_contribution_metrics.items()
        })
        if self.portfolio_contribution_metrics is not None:
            out.update({
                f"portfolio_contribution_{key}": value
                for key, value in self.portfolio_contribution_metrics.items()
            })
        if self.fair_lip is not None:
            out.update(self.fair_lip.as_dict("fair_lip"))
            if self.fair_lip.fee_rate is not None:
                out["charged_minus_fair_lip_bp"] = (
                    float(self.per_contract_metrics["charged_lip_rate"])
                    - self.fair_lip.fee_rate
                ) * 10_000.0
            else:
                out["charged_minus_fair_lip_bp"] = None
        if self.commercial_break_even_lip is not None:
            out.update(
                self.commercial_break_even_lip.as_dict(
                    "commercial_break_even_lip"
                )
            )
            if self.commercial_break_even_lip.fee_rate is not None:
                out["charged_minus_commercial_break_even_lip_bp"] = (
                    float(self.per_contract_metrics["charged_lip_rate"])
                    - self.commercial_break_even_lip.fee_rate
                ) * 10_000.0
            else:
                out["charged_minus_commercial_break_even_lip_bp"] = None
        return out


@dataclass(frozen=True)
class PortfolioValuationResult:
    """Separated normalised and absolute portfolio valuation results."""

    summary: Mapping[str, object]
    normalised_average_metrics: Mapping[str, float]
    portfolio_total_metrics: Optional[Mapping[str, float]]
    model_points: tuple[ModelPointPortfolioValuation, ...]
    settings: ValuationSettings
    scenario_fingerprint: str
    scenario_horizon_years: float
    aggregation_basis: str
    portfolio_contract_count: Optional[float]
    portfolio_fair_lip: Optional[FairFeeSolveResult] = None
    portfolio_commercial_break_even_lip: Optional[FairFeeSolveResult] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary", MappingProxyType(dict(self.summary)))
        object.__setattr__(
            self,
            "normalised_average_metrics",
            MappingProxyType(dict(self.normalised_average_metrics)),
        )
        if self.portfolio_total_metrics is not None:
            object.__setattr__(
                self,
                "portfolio_total_metrics",
                MappingProxyType(dict(self.portfolio_total_metrics)),
            )

    def summary_dict(self) -> dict[str, object]:
        return dict(self.summary)

    def model_point_rows(self) -> list[dict[str, object]]:
        return [result.as_dict() for result in self.model_points]


def _default_settings() -> ValuationSettings:
    return ValuationSettings(
        model="heston_hull_white",
        projection=ProjectionConfig(record_paths=False, heston_cos=False),
    )


def _portfolio_settings_and_scenarios(
    model_points: PolicyholderModelPointSet,
    esg_config: ESGConfig,
    settings: ValuationSettings,
    scenario_transform: Optional[Callable[[ScenarioSet], ScenarioSet]] = None,
) -> tuple[ValuationSettings, ScenarioSet]:
    horizon_basis = replace(settings, horizon_years=None)
    required_horizon = max(
        resolve_horizon(horizon_basis, point.policy)
        for point in model_points.model_points
    )
    common_horizon = (
        required_horizon
        if settings.horizon_years is None
        else float(settings.horizon_years)
    )
    if common_horizon < required_horizon:
        raise ValueError(
            f"Explicit portfolio horizon {common_horizon} years truncates the "
            f"required lifetime horizon of {required_horizon} years."
        )
    common_settings = replace(settings, horizon_years=common_horizon)
    scenarios = build_scenarios(
        esg_config,
        common_settings,
        measure=Measure.RISK_NEUTRAL,
        horizon_years=common_horizon,
    )
    if scenario_transform is not None:
        if not callable(scenario_transform):
            raise TypeError("scenario_transform must be callable or None.")
        protected = {
            "config_fingerprint": assumption_fingerprint(scenarios.config),
            "measure": scenarios.measure,
            "model_name": scenarios.model_name,
            "seed": scenarios.seed,
            "dt": scenarios.dt,
            "times": np.array(scenarios.times, copy=True),
            "n_paths": scenarios.n_paths,
            "n_steps": scenarios.n_steps,
            "stochastic_rates": scenarios.stochastic_rates,
            "substeps": scenarios.substeps,
        }
        transformed = scenario_transform(scenarios)
        if not isinstance(transformed, ScenarioSet):
            raise TypeError("scenario_transform must return a ScenarioSet.")
        unchanged_attributes = {
            "config": (
                assumption_fingerprint(transformed.config)
                == protected["config_fingerprint"]
            ),
            "measure": transformed.measure == protected["measure"],
            "model_name": transformed.model_name == protected["model_name"],
            "seed": transformed.seed == protected["seed"],
            "dt": transformed.dt == protected["dt"],
            "time_grid": np.array_equal(transformed.times, protected["times"]),
            "path_grid_shape": (
                transformed.n_paths == protected["n_paths"]
                and transformed.n_steps == protected["n_steps"]
            ),
            "stochastic_rates": (
                transformed.stochastic_rates == protected["stochastic_rates"]
            ),
            "substeps": transformed.substeps == protected["substeps"],
        }
        changed = [
            name for name, unchanged in unchanged_attributes.items()
            if not unchanged
        ]
        if changed:
            raise ValueError(
                "scenario_transform changed protected ScenarioSet attributes: "
                + ", ".join(changed)
                + "."
            )
        scenarios = transformed
    return common_settings, scenarios


def _valuation_metrics(
    valuation: _ScalarValuation,
    product: IndexLinkedLifetimeIncomeProduct,
    profitability_materiality_bp: float,
) -> dict[str, object]:
    pv = valuation.pv
    benefits = (
        pv["income_paid"]
        + pv["death_benefits"]
        + pv["surrender_benefits"]
        + pv["partial_withdrawals"]
        + pv["terminal_closeout"]
    )
    future_fees = pv["fees_product"] + pv["fees_lip"]
    premium = valuation.premium
    nbm = valuation.insurer_net_value / premium
    materiality_ratio = profitability_materiality_bp / 10_000.0
    materiality_aud = premium * materiality_ratio
    if valuation.insurer_net_value > materiality_aud:
        profitability = "positive_value"
    elif valuation.insurer_net_value < -materiality_aud:
        profitability = "negative_value"
    else:
        profitability = "approximately_break_even"
    metrics: dict[str, object] = {
        "premium_aud": premium,
        "pv_policyholder_benefits_aud": benefits,
        "pv_policyholder_benefits_pre_election_aud": (
            pv["policyholder_benefits_pre_election"]
        ),
        "pv_policyholder_benefits_post_election_aud": (
            pv["policyholder_benefits_post_election"]
        ),
        "pv_terminal_closeout_aud": pv["terminal_closeout"],
        "pv_future_fees_aud": future_fees,
        "pv_product_fees_aud": pv["fees_product"],
        "pv_lifetime_income_premiums_aud": pv["fees_lip"],
        "pv_guarantee_claims_aud": pv["guarantee_claims"],
        "pv_expenses_aud": pv["expenses"],
        "pv_hedge_costs_aud": pv["hedge_costs"],
        "pv_crediting_margin_aud": pv["crediting_margin"],
        "pv_money_market_income_aud": pv["money_market_income"],
        "pv_hedge_gain_aud": pv["hedge_gain"],
        "pv_hedge_option_fair_value_costs_aud": (
            pv["hedge_option_fair_value_costs"]
        ),
        "pv_hedge_option_markup_costs_aud": pv["hedge_option_markup_costs"],
        "pv_hedge_management_fee_costs_aud": (
            pv["hedge_management_fee_costs"]
        ),
        "pv_hedge_execution_costs_aud": pv["hedge_execution_costs"],
        "pv_hedge_cost_reconciliation_gap_aud": (
            pv["hedge_costs"]
            - pv["hedge_option_fair_value_costs"]
            - pv["hedge_option_markup_costs"]
            - pv["hedge_management_fee_costs"]
            - pv["hedge_execution_costs"]
        ),
        "pv_crediting_margin_reconciliation_gap_aud": (
            pv["crediting_margin"]
            - pv["money_market_income"]
            - pv["hedge_gain"]
        ),
        "pv_growth_fees_aud": pv["growth_fees"],
        "pv_growth_crediting_margin_aud": pv["growth_crediting_margin"],
        "pv_post_election_guarantee_claims_aud": (
            pv["post_election_guarantee_claims"]
        ),
        "pv_mva_retained_aud": pv["mva_retained"],
        "pv_aps_retained_aud": pv["aps_retained"],
        "bel_nonunit_aud": valuation.bel_nonunit,
        "bel_total_aud": valuation.bel_total,
        "market_consistent_bel_total_aud": valuation.bel_total,
        "guarantee_value_aud": valuation.guarantee_value,
        "insurer_net_present_value_before_risk_margin_aud": (
            valuation.insurer_net_value
        ),
        "new_business_margin_before_risk_margin": nbm,
        "profitability_materiality_bp": profitability_materiality_bp,
        "profitability_materiality_aud": materiality_aud,
        "identity_gap": valuation.identity_gap,
        "phase_policyholder_benefit_reconciliation_gap_aud": (
            pv["policyholder_benefits_pre_election"]
            + pv["policyholder_benefits_post_election"]
            - benefits
        ),
        "charged_product_fee_rate": float(product.fees.product_fee),
        "charged_lip_rate": float(product.fees.lifetime_income_premium),
        "profitability_classification": profitability,
    }
    metrics.update(valuation.behaviour_diagnostics)
    return metrics


def _spouse_survival_to_election(
    model_point: PolicyholderModelPoint,
    product: IndexLinkedLifetimeIncomeProduct,
    mortality: MortalityTable,
) -> float:
    """Spouse survival from issue to the deterministic Election anniversary."""
    policy = model_point.policy
    if not policy.spouse or policy.spouse_age is None:
        return 0.0
    steps = policy.effective_income_start_year(product) * 12
    issue_offset = policy.commencement_year - mortality.base_year
    spouse_sex = policy.spouse_sex or policy.sex
    q_monthly = mortality.monthly_q_curve(
        policy.spouse_age,
        spouse_sex,
        steps,
        years_from_base=issue_offset,
        projection_duration_start=0.0,
    )
    survival = float(np.prod(1.0 - q_monthly))
    return float(np.clip(survival, 0.0, 1.0))


def _model_point_behaviour_treatment(
    model_point: PolicyholderModelPoint,
    behaviour: BehaviourModel,
    *,
    force_pathwise_joint_life: bool = False,
) -> str:
    """Describe the effective behaviour basis used for one model point."""
    policy = model_point.policy
    dynamic_active = behaviour.use_dynamic or behaviour.use_dynamic_withdrawals
    pathwise_behaviour = (
        behaviour.take_up.mode != "deterministic"
        or dynamic_active
        or force_pathwise_joint_life
    )
    if policy.spouse and pathwise_behaviour:
        return "pathwise_joint_life_state_dependent"
    if (
        policy.spouse
        and policy.spouse_death_election == SpouseDeathElection.CONTINUE_INCOME
    ):
        return (
            "joint_and_single_branches_static_base"
        )
    if dynamic_active:
        return "dynamic_state_dependent"
    return "static_base"


def _combine_joint_and_single_fallback(
    joint: _ScalarValuation,
    single: _ScalarValuation,
    spouse_survival: float,
) -> _ScalarValuation:
    """Mix conditional Election states without duplicating pre-Election flows.

    With deterministic common Election timing, joint and fallback projections
    are identical before Election.  A convex combination therefore retains
    those cashflows once and assigns post-Election values according to whether
    the spouse survived to the eligibility date.
    """
    s = float(spouse_survival)

    def mixed(left: float, right: float) -> float:
        return s * float(left) + (1.0 - s) * float(right)

    if joint.pv.keys() != single.pv.keys():
        raise ValueError("Joint and Single-Life valuation components differ.")
    pv = {key: mixed(joint.pv[key], single.pv[key]) for key in joint.pv}
    diagnostic_keys = (
        set(joint.behaviour_diagnostics) | set(single.behaviour_diagnostics)
    )
    diagnostics: dict[str, object] = {}
    for key in diagnostic_keys:
        left = joint.behaviour_diagnostics.get(key)
        right = single.behaviour_diagnostics.get(key)
        if isinstance(left, (int, float, np.integer, np.floating)) \
                and isinstance(right, (int, float, np.integer, np.floating)):
            diagnostics[key] = mixed(float(left), float(right))
        elif left is None and right is None:
            diagnostics[key] = None
        elif left == right:
            diagnostics[key] = left
        else:
            # A ratio/quantile with no defined value in one conditional branch
            # is not made precise by silently substituting the other branch.
            diagnostics[key] = None
    income_exposure = diagnostics.get("income_exposure_months")
    if isinstance(income_exposure, (int, float)) and income_exposure > 0.0:
        for cause in ("ordinary", "performance", "total"):
            event = diagnostics.get(f"{cause}_income_lapse_event_mass")
            if isinstance(event, (int, float)):
                rate = float(event) / float(income_exposure)
                diagnostics[f"{cause}_income_lapse_probability"] = rate
                diagnostics[f"{cause}_income_lapse_rate"] = rate
    election_mass = diagnostics.get("income_election_event_mass")
    forced_mass = diagnostics.get("forced_income_election_event_mass")
    if isinstance(election_mass, (int, float)):
        diagnostics["income_election_share"] = float(election_mass)
        diagnostics["forced_income_election_share"] = (
            0.0
            if float(election_mass) <= 0.0
            or not isinstance(forced_mass, (int, float))
            else float(forced_mass) / float(election_mass)
        )
    return _ScalarValuation(
        pv=pv,
        premium=mixed(joint.premium, single.premium),
        bel_nonunit=mixed(joint.bel_nonunit, single.bel_nonunit),
        bel_total=mixed(joint.bel_total, single.bel_total),
        guarantee_value=mixed(joint.guarantee_value, single.guarantee_value),
        insurer_net_value=mixed(
            joint.insurer_net_value, single.insurer_net_value),
        identity_gap=mixed(joint.identity_gap, single.identity_gap),
        behaviour_diagnostics=diagnostics,
    )


def _value_model_point(
    *,
    product: IndexLinkedLifetimeIncomeProduct,
    model_point: PolicyholderModelPoint,
    esg_config: ESGConfig,
    mortality: MortalityTable,
    behaviour: BehaviourModel,
    expenses: Optional[ExpenseAssumptions],
    settings: ValuationSettings,
    scenarios: ScenarioSet,
    surrender_policy_factory: Optional[Callable[[PolicySpec], object]] = None,
    income_action_policy_factory: Optional[
        Callable[[PolicySpec], object]
    ] = None,
    combined_policy_factory: Optional[Callable[[PolicySpec], object]] = None,
) -> _ScalarValuation:
    """Value a model point, including the pre-Election spouse-life split."""
    combined_policy = (
        None
        if combined_policy_factory is None
        else combined_policy_factory(model_point.policy)
    )
    income_action_policy = (
        combined_policy
        if combined_policy is not None
        and callable(getattr(combined_policy, "choose_income_action", None))
        else None
        if income_action_policy_factory is None
        else income_action_policy_factory(model_point.policy)
    )
    surrender_policy = (
        combined_policy
        if combined_policy is not None
        and income_action_policy is None
        and callable(getattr(combined_policy, "surrender_mask", None))
        else None
        if surrender_policy_factory is None
        else surrender_policy_factory(model_point.policy)
    )
    pathwise_behaviour = (
        behaviour.take_up.mode != "deterministic"
        or combined_policy_factory is not None
        or surrender_policy_factory is not None
        or income_action_policy_factory is not None
        or behaviour.use_dynamic
        or behaviour.use_dynamic_withdrawals
        or settings.projection.force_pathwise_joint_life
    )
    joint_behaviour = behaviour
    if (
        model_point.policy.spouse
        and model_point.policy.spouse_death_election
        == SpouseDeathElection.CONTINUE_INCOME
        and (behaviour.use_dynamic or behaviour.use_dynamic_withdrawals)
        and not pathwise_behaviour
    ):
        # A nonlinear response to a mortality-state-averaged annuity factor is
        # not a valid substitute for separately projected p11/p10/p01 account
        # cohorts.  Until those cohorts exist, use the CSV base lapse and
        # withdrawal assumptions for the conditional Joint-Life branch.  They
        # are state independent, so the existing Last-Survivor expected-
        # decrement projection remains internally consistent.
        joint_behaviour = replace(behaviour, regime="static")
    joint_or_single = _scalarize(value_contract(
        product,
        model_point.policy,
        esg_config,
        mortality,
        joint_behaviour,
        expenses=expenses,
        settings=settings,
        scenarios=scenarios,
        surrender_policy=surrender_policy,
        income_election_policy=combined_policy,
        income_action_policy=income_action_policy,
    ))
    if not model_point.policy.spouse or pathwise_behaviour:
        return joint_or_single
    fallback_policy = replace(
        model_point.policy,
        spouse=False,
        spouse_age=None,
        spouse_sex=None,
        spouse_death_election=SpouseDeathElection.CONTINUE_INCOME,
    )
    fallback_point = replace(model_point, policy=fallback_policy)
    single_fallback = _scalarize(value_contract(
        product,
        fallback_point.policy,
        esg_config,
        mortality,
        behaviour,
        expenses=expenses,
        settings=settings,
        scenarios=scenarios,
        surrender_policy=(
            None
            if surrender_policy_factory is None
            else surrender_policy_factory(fallback_point.policy)
        ),
        income_action_policy=(
            None
            if income_action_policy_factory is None
            else income_action_policy_factory(fallback_point.policy)
        ),
    ))
    return _combine_joint_and_single_fallback(
        joint_or_single,
        single_fallback,
        _spouse_survival_to_election(model_point, product, mortality),
    )


def _solve_fee_objective(
    *,
    objective_name: str,
    objective: Callable[[float], float],
    product: IndexLinkedLifetimeIncomeProduct,
    lower_rate: float,
    upper_rate: float,
    maximum_upper_rate: float,
    fee_tolerance: float,
    value_basis: str = "per_contract",
) -> FairFeeSolveResult:
    """Solve one cached fee objective after validating the common controls."""
    if not all(isfinite(value) for value in (
        lower_rate, upper_rate, maximum_upper_rate, fee_tolerance
    )):
        raise ValueError("Fair-fee controls must be finite.")
    if (
        lower_rate < 0.0
        or upper_rate <= lower_rate
        or maximum_upper_rate < upper_rate
        or fee_tolerance <= 0.0
    ):
        raise ValueError("Invalid fair-fee bracket or tolerance.")

    admissible_max = min(
        maximum_upper_rate,
        1.0 - product.fees.product_fee - 1.0e-10,
    )
    if admissible_max <= lower_rate:
        raise ValueError("No admissible Lifetime Income Premium bracket remains.")
    upper = min(upper_rate, admissible_max)

    f_lower = objective(lower_rate)
    f_upper = objective(upper)
    zero_tolerance = 1.0e-8
    if abs(f_lower) <= zero_tolerance:
        return FairFeeSolveResult(
            objective=objective_name,
            status="solved_at_lower_bound",
            fee_rate=lower_rate,
            lower_rate=lower_rate,
            upper_rate=upper,
            objective_at_lower_aud=f_lower,
            objective_at_upper_aud=f_upper,
            residual_aud=f_lower,
            iterations=0,
            value_basis=value_basis,
        )
    if abs(f_upper) <= zero_tolerance:
        return FairFeeSolveResult(
            objective=objective_name,
            status="solved_at_upper_bound",
            fee_rate=upper,
            lower_rate=lower_rate,
            upper_rate=upper,
            objective_at_lower_aud=f_lower,
            objective_at_upper_aud=f_upper,
            residual_aud=f_upper,
            iterations=0,
            value_basis=value_basis,
        )

    expansions = 0
    while f_lower * f_upper > 0.0 and upper < admissible_max:
        expanded = min(max(upper * 1.8, upper + 0.005), admissible_max)
        if expanded <= upper:
            break
        upper = expanded
        f_upper = objective(upper)
        expansions += 1
        if abs(f_upper) <= zero_tolerance:
            return FairFeeSolveResult(
                objective=objective_name,
                status="solved_at_expanded_upper_bound",
                fee_rate=upper,
                lower_rate=lower_rate,
                upper_rate=upper,
                objective_at_lower_aud=f_lower,
                objective_at_upper_aud=f_upper,
                residual_aud=f_upper,
                iterations=expansions,
                value_basis=value_basis,
            )

    if f_lower * f_upper > 0.0:
        direction = "positive" if f_lower > 0.0 else "negative"
        return FairFeeSolveResult(
            objective=objective_name,
            status=f"no_bracket_{direction}_at_both_bounds",
            fee_rate=None,
            lower_rate=lower_rate,
            upper_rate=upper,
            objective_at_lower_aud=f_lower,
            objective_at_upper_aud=f_upper,
            residual_aud=None,
            iterations=expansions,
            value_basis=value_basis,
        )

    root, details = brentq(
        objective,
        lower_rate,
        upper,
        xtol=fee_tolerance,
        rtol=max(4.0 * np.finfo(float).eps, fee_tolerance * 0.01),
        full_output=True,
        disp=False,
    )
    residual = objective(float(root))
    return FairFeeSolveResult(
        objective=objective_name,
        status="solved",
        fee_rate=float(root),
        lower_rate=lower_rate,
        upper_rate=upper,
        objective_at_lower_aud=f_lower,
        objective_at_upper_aud=f_upper,
        residual_aud=residual,
        iterations=int(details.iterations) + expansions,
        value_basis=value_basis,
    )


def _solve_lip_rate(
    *,
    objective_name: str,
    objective_selector: Callable[[_ScalarValuation], float],
    product: IndexLinkedLifetimeIncomeProduct,
    model_point: PolicyholderModelPoint,
    esg_config: ESGConfig,
    mortality: MortalityTable,
    behaviour: BehaviourModel,
    expenses: Optional[ExpenseAssumptions],
    settings: ValuationSettings,
    scenarios: ScenarioSet,
    lower_rate: float,
    upper_rate: float,
    maximum_upper_rate: float,
    fee_tolerance: float,
    evaluation_callback: Optional[Callable[[float, float], None]] = None,
) -> FairFeeSolveResult:
    """Solve one model point with common random numbers."""
    cache: dict[float, float] = {}

    def objective(rate: float) -> float:
        key = float(rate)
        if key not in cache:
            candidate = replace(
                product,
                fees=replace(product.fees, lifetime_income_premium=key),
            )
            valuation = _value_model_point(
                product=candidate,
                model_point=model_point,
                esg_config=esg_config,
                mortality=mortality,
                behaviour=behaviour,
                expenses=expenses,
                settings=settings,
                scenarios=scenarios,
            )
            value = float(objective_selector(valuation))
            if not isfinite(value):
                raise ValueError(
                    f"Non-finite {objective_name} objective at LIP rate {key}."
                )
            cache[key] = value
            if evaluation_callback is not None:
                evaluation_callback(key, value)
        return cache[key]

    return _solve_fee_objective(
        objective_name=objective_name,
        objective=objective,
        product=product,
        lower_rate=lower_rate,
        upper_rate=upper_rate,
        maximum_upper_rate=maximum_upper_rate,
        fee_tolerance=fee_tolerance,
    )


def _solve_portfolio_lip_rate(
    *,
    objective_name: str,
    objective_selector: Callable[[_ScalarValuation], float],
    product: IndexLinkedLifetimeIncomeProduct,
    model_points: tuple[PolicyholderModelPoint, ...],
    contribution_weights: tuple[float, ...],
    esg_config: ESGConfig,
    mortality: MortalityTable,
    behaviour: BehaviourModel,
    expenses: Optional[ExpenseAssumptions],
    settings: ValuationSettings,
    scenarios: ScenarioSet,
    lower_rate: float,
    upper_rate: float,
    maximum_upper_rate: float,
    fee_tolerance: float,
    evaluation_callback: Optional[Callable[[float, float], None]] = None,
    projection_callback: Optional[Callable[[float, int, int, str], None]] = None,
) -> FairFeeSolveResult:
    """Solve one common product fee directly against the portfolio objective."""
    if len(model_points) != len(contribution_weights):
        raise ValueError("Portfolio fee weights must align with model points.")
    if not np.isclose(sum(contribution_weights), 1.0, rtol=0.0, atol=1.0e-9):
        raise ValueError("Portfolio fee weights must sum to one.")

    cache: dict[float, float] = {}

    def objective(rate: float) -> float:
        key = float(rate)
        if key not in cache:
            candidate = replace(
                product,
                fees=replace(product.fees, lifetime_income_premium=key),
            )
            value = 0.0
            total = len(model_points)
            for index, (point, weight) in enumerate(
                zip(model_points, contribution_weights), start=1
            ):
                valuation = _value_model_point(
                    product=candidate,
                    model_point=point,
                    esg_config=esg_config,
                    mortality=mortality,
                    behaviour=behaviour,
                    expenses=expenses,
                    settings=settings,
                    scenarios=scenarios,
                )
                value += weight * float(objective_selector(valuation))
                if projection_callback is not None:
                    projection_callback(key, index, total, point.model_point_id)
            if not isfinite(value):
                raise ValueError(
                    f"Non-finite {objective_name} objective at LIP rate {key}."
                )
            cache[key] = value
            if evaluation_callback is not None:
                evaluation_callback(key, value)
        return cache[key]

    return _solve_fee_objective(
        objective_name=objective_name,
        objective=objective,
        product=product,
        lower_rate=lower_rate,
        upper_rate=upper_rate,
        maximum_upper_rate=maximum_upper_rate,
        fee_tolerance=fee_tolerance,
        value_basis="normalised_portfolio_average_contract",
    )


def value_policyholder_portfolio(
    product: IndexLinkedLifetimeIncomeProduct,
    model_points: PolicyholderModelPointSet,
    esg_config: ESGConfig,
    mortality: MortalityTable,
    behaviour: BehaviourModel,
    expenses: Optional[ExpenseAssumptions] = None,
    *,
    settings: Optional[ValuationSettings] = None,
    portfolio_contract_count: Optional[float] = None,
    calculate_fair_lip: bool = False,
    calculate_commercial_break_even_lip: bool = False,
    calculate_portfolio_fair_lip: bool = False,
    calculate_portfolio_commercial_break_even_lip: bool = False,
    fair_fee_lower_rate: float = 0.0,
    fair_fee_upper_rate: float = 0.05,
    fair_fee_maximum_upper_rate: float = 0.25,
    fair_fee_tolerance: float = 1.0e-6,
    profitability_materiality_bp: float = 1.0,
    progress_callback: Optional[Callable[[PortfolioProgress], None]] = None,
    surrender_policy_factory: Optional[Callable[[PolicySpec], object]] = None,
    income_action_policy_factory: Optional[
        Callable[[PolicySpec], object]
    ] = None,
    combined_policy_factory: Optional[Callable[[PolicySpec], object]] = None,
    scenario_transform: Optional[Callable[[ScenarioSet], ScenarioSet]] = None,
) -> PortfolioValuationResult:
    """Value all model points under one shared risk-neutral scenario set.

    Every source row is projected independently before aggregation.  Per-
    contract values and ``contract_weight`` contributions are always returned.
    Absolute portfolio totals are returned only when source ``exposure_count``
    values or an explicit ``portfolio_contract_count`` provide the represented
    contract count.  ``premium_volume_weight`` remains a reconciliation control
    and is never applied as a second PV weight.

    ``scenario_transform`` may change path values after the shared scenario set
    is generated, but it may not change the market configuration, measure,
    model, seed, monthly grid or path dimensions.

    ``combined_policy_factory`` supplies one frozen out-of-sample policy per
    PolicySpec.  A v2 object implements ``start_income_mask`` and
    ``choose_income_action`` and is passed to the annual Election and monthly
    Income-action gates.  Older objects implementing ``surrender_mask`` remain
    supported as explicit Election/Full-Withdrawal research policies.
    """
    total_model_points = len(model_points.model_points)
    if total_model_points == 0:
        raise ValueError("Policyholder portfolio contains no model points.")

    def notify(
        stage: str,
        completed: int,
        model_point_id: Optional[str] = None,
        detail: str = "",
    ) -> None:
        if progress_callback is not None:
            progress_callback(PortfolioProgress(
                stage=stage,
                completed=completed,
                total=total_model_points,
                model_point_id=model_point_id,
                detail=detail,
            ))

    valuation_settings = settings or _default_settings()
    if valuation_settings.model != "heston_hull_white":
        raise ValueError(
            "Policyholder portfolio valuation requires Heston-Hull-White."
        )
    if valuation_settings.projection.record_paths:
        raise ValueError("Portfolio valuation requires ProjectionConfig.record_paths=False.")
    if valuation_settings.projection.heston_cos:
        raise ValueError("Portfolio valuation requires ProjectionConfig.heston_cos=False.")
    fair_fee_switches = (
        calculate_fair_lip,
        calculate_commercial_break_even_lip,
        calculate_portfolio_fair_lip,
        calculate_portfolio_commercial_break_even_lip,
    )
    if any(not isinstance(value, bool) for value in fair_fee_switches):
        raise ValueError("Fair-fee switches must be boolean.")
    separate_policy_factories = sum(factory is not None for factory in (
        surrender_policy_factory,
        income_action_policy_factory,
    ))
    if combined_policy_factory is not None and separate_policy_factories:
        raise ValueError(
            "Use combined_policy_factory or separate Income-action/Surrender "
            "factories, not both."
        )
    if separate_policy_factories > 1:
        raise ValueError(
            "Use either surrender_policy_factory or "
            "income_action_policy_factory, not both."
        )
    if (surrender_policy_factory is not None
            or income_action_policy_factory is not None
            or combined_policy_factory is not None) and any(fair_fee_switches):
        raise ValueError(
            "Fair-fee solves with LSMC require refitting the exercise policy "
            "at every fee candidate and are not supported by this entry point."
        )
    if (
        isinstance(profitability_materiality_bp, bool)
        or not isfinite(profitability_materiality_bp)
        or profitability_materiality_bp < 0.0
    ):
        raise ValueError("profitability_materiality_bp must be finite and non-negative.")
    has_joint_life = any(
        point.policy.spouse for point in model_points.model_points
    )
    uses_pathwise_joint_life = bool(
        has_joint_life
        and (
            behaviour.take_up.mode != "deterministic"
            or combined_policy_factory is not None
            or surrender_policy_factory is not None
            or income_action_policy_factory is not None
            or behaviour.use_dynamic
            or behaviour.use_dynamic_withdrawals
            or valuation_settings.projection.force_pathwise_joint_life
        )
    )
    joint_continue_income_count = sum(
        1
        for point in model_points.model_points
        if point.policy.spouse
        and point.policy.spouse_death_election
        == SpouseDeathElection.CONTINUE_INCOME
    )
    automatic_start_override_count = sum(
        1
        for point in model_points.model_points
        if point.policy.effective_income_start_year(product)
        != int(round(point.policy.income_start_year))
    )
    if portfolio_contract_count is not None and (
        isinstance(portfolio_contract_count, bool)
        or not isfinite(portfolio_contract_count)
        or portfolio_contract_count <= 0.0
    ):
        raise ValueError("portfolio_contract_count must be positive and finite.")

    contract_weight_shares = _normalised_positive_weights(
        tuple(point.contract_weight for point in model_points.model_points),
        label="model-point contract weights",
    )

    source_contract_count = model_points.total_exposure_count
    if source_contract_count is not None:
        if any(
            point.exposure_count is None
            for point in model_points.model_points
        ):
            raise ValueError(
                "Source total_exposure_count requires exposure_count on every model point."
            )
        if portfolio_contract_count is not None and not np.isclose(
            portfolio_contract_count,
            source_contract_count,
            rtol=0.0,
            atol=1.0e-9,
        ):
            raise ValueError(
                "portfolio_contract_count conflicts with source exposure_count total."
            )
        absolute_contract_count: Optional[float] = float(source_contract_count)
        represented_contract_counts: tuple[Optional[float], ...] = tuple(
            float(point.exposure_count)
            if point.exposure_count is not None else None
            for point in model_points.model_points
        )
        if not np.isclose(
            sum(float(count) for count in represented_contract_counts if count is not None),
            absolute_contract_count,
            rtol=0.0,
            atol=max(1.0e-9, absolute_contract_count * 1.0e-12),
        ):
            raise ValueError(
                "Source exposure_count values do not sum to total_exposure_count."
            )
        aggregation_weights = _normalised_positive_weights(
            tuple(
                float(count) for count in represented_contract_counts
                if count is not None
            ),
            label="source exposure counts",
        )
        aggregation_weight_source = "source_exposure_count"
        aggregation_basis = "absolute_source_exposure_counts"
    elif portfolio_contract_count is not None:
        absolute_contract_count = float(portfolio_contract_count)
        represented_contract_count_values = [
            absolute_contract_count * weight
            for weight in contract_weight_shares
        ]
        represented_contract_count_values[-1] = (
            absolute_contract_count
            - sum(represented_contract_count_values[:-1])
        )
        represented_contract_counts = tuple(represented_contract_count_values)
        aggregation_weights = contract_weight_shares
        aggregation_weight_source = "normalised_contract_weight"
        aggregation_basis = "absolute_total_count_times_contract_weight"
    else:
        absolute_contract_count = None
        represented_contract_counts = tuple(
            None for _ in model_points.model_points
        )
        aggregation_weights = contract_weight_shares
        aggregation_weight_source = "normalised_contract_weight"
        aggregation_basis = "normalised_to_one_representative_contract"

    if not np.isclose(
        product.reference_fund.maximum_return, 0.06, rtol=0.0, atol=1.0e-12
    ):
        raise ValueError("The portfolio product must use the fixed 6% crediting cap.")

    notify("scenario_generation_started", 0)
    common_settings, scenarios = _portfolio_settings_and_scenarios(
        model_points,
        esg_config,
        valuation_settings,
        scenario_transform=scenario_transform,
    )
    notify(
        "scenario_generation_completed",
        0,
        detail=f"fingerprint={scenarios.content_fingerprint}",
    )

    normalised_aggregate = {metric: 0.0 for metric in _MONETARY_METRICS}
    behaviour_normalised_aggregate: dict[str, float] = {}
    take_up_probability_numerator_by_year: dict[int, float] = {}
    portfolio_aggregate = (
        {metric: 0.0 for metric in _MONETARY_METRICS}
        if absolute_contract_count is not None else None
    )
    identity_gap_numerator = 0.0
    point_results: list[ModelPointPortfolioValuation] = []

    for index, (point, aggregation_weight, represented_contract_count) in enumerate(
        zip(
            model_points.model_points,
            aggregation_weights,
            represented_contract_counts,
        ),
        start=1,
    ):
        notify("model_point_started", index - 1, point.model_point_id)
        valuation = _value_model_point(
            product=product,
            model_point=point,
            esg_config=esg_config,
            mortality=mortality,
            behaviour=behaviour,
            expenses=expenses,
            settings=common_settings,
            scenarios=scenarios,
            surrender_policy_factory=surrender_policy_factory,
            income_action_policy_factory=income_action_policy_factory,
            combined_policy_factory=combined_policy_factory,
        )
        metrics = _valuation_metrics(
            valuation,
            product,
            profitability_materiality_bp,
        )
        metrics["income_take_up_mode"] = (
            "combined_policy"
            if combined_policy_factory is not None
            else behaviour.take_up.mode
        )
        deterministic_election = (
            behaviour.take_up.mode == "deterministic"
            and combined_policy_factory is None
        )
        deterministic_benchmark_year = point.policy.effective_income_start_year(
            product
        )
        metrics["deterministic_benchmark_effective_income_start_year"] = (
            deterministic_benchmark_year
        )
        metrics["effective_income_start_year"] = (
            deterministic_benchmark_year if deterministic_election else None
        )
        metrics["behaviour_treatment"] = (
            "combined_policy_optimal_income_election_and_income_actions"
            if combined_policy_factory is not None
            else "lsmc_optimal_income_partial_or_full_withdrawal"
            if income_action_policy_factory is not None
            else "lsmc_optimal_income_full_withdrawal"
            if surrender_policy_factory is not None
            else _model_point_behaviour_treatment(
                point,
                behaviour,
                force_pathwise_joint_life=(
                    common_settings.projection.force_pathwise_joint_life
                ),
            )
        )
        metrics["spouse_survival_to_income_election"] = (
            _spouse_survival_to_election(point, product, mortality)
            if point.policy.spouse and deterministic_election else None
        )
        for metric, value in valuation.behaviour_diagnostics.items():
            if isinstance(value, bool) or not isinstance(
                value, (int, float, np.integer, np.floating)
            ):
                continue
            numeric = float(value)
            if not isfinite(numeric):
                continue
            behaviour_normalised_aggregate[metric] = (
                behaviour_normalised_aggregate.get(metric, 0.0)
                + aggregation_weight * numeric
            )
        for key, value in valuation.behaviour_diagnostics.items():
            prefix = "annual_take_up_probability_policy_year_"
            if not key.startswith(prefix) or value is None:
                continue
            year = int(key[len(prefix):])
            eligible_key = f"eligible_growth_exposure_policy_year_{year}"
            eligible_value = valuation.behaviour_diagnostics.get(eligible_key)
            if eligible_value is None:
                continue
            take_up_probability_numerator_by_year[year] = (
                take_up_probability_numerator_by_year.get(year, 0.0)
                + aggregation_weight * float(value) * float(eligible_value)
            )
        normalised_contribution_metrics = {
            metric: aggregation_weight * float(metrics[metric])
            for metric in _MONETARY_METRICS
        }
        portfolio_contribution_metrics = (
            None
            if represented_contract_count is None
            else {
                metric: represented_contract_count * float(metrics[metric])
                for metric in _MONETARY_METRICS
            }
        )
        for metric, value in normalised_contribution_metrics.items():
            normalised_aggregate[metric] += value
        if (
            portfolio_aggregate is not None
            and portfolio_contribution_metrics is not None
        ):
            for metric, value in portfolio_contribution_metrics.items():
                portfolio_aggregate[metric] += value
        identity_gap_numerator += (
            aggregation_weight
            * float(metrics["premium_aud"])
            * float(metrics["identity_gap"])
        )
        # Do not retain the large cashflow arrays while optional fee roots are
        # reprojected.  All base-run information needed below is now scalar.
        del valuation

        fair_lip = None
        if calculate_fair_lip:
            notify("model_point_fair_lip_started", index - 1, point.model_point_id)
            fair_lip = _solve_lip_rate(
                objective_name="guarantee_value_equals_zero",
                objective_selector=lambda result: result.guarantee_value,
                product=product,
                model_point=point,
                esg_config=esg_config,
                mortality=mortality,
                behaviour=behaviour,
                expenses=expenses,
                settings=common_settings,
                scenarios=scenarios,
                lower_rate=fair_fee_lower_rate,
                upper_rate=fair_fee_upper_rate,
                maximum_upper_rate=fair_fee_maximum_upper_rate,
                fee_tolerance=fair_fee_tolerance,
                evaluation_callback=lambda rate, value, point_id=point.model_point_id: notify(
                    "model_point_fair_lip_evaluation",
                    index - 1,
                    point_id,
                    f"rate={rate:.10g}; objective_aud={value:.10g}",
                ),
            )
            notify(
                "model_point_fair_lip_completed",
                index - 1,
                point.model_point_id,
                fair_lip.status,
            )

        commercial_break_even = None
        if calculate_commercial_break_even_lip:
            notify(
                "model_point_commercial_break_even_lip_started",
                index - 1,
                point.model_point_id,
            )
            commercial_break_even = _solve_lip_rate(
                objective_name="insurer_net_present_value_equals_zero",
                objective_selector=lambda result: result.insurer_net_value,
                product=product,
                model_point=point,
                esg_config=esg_config,
                mortality=mortality,
                behaviour=behaviour,
                expenses=expenses,
                settings=common_settings,
                scenarios=scenarios,
                lower_rate=fair_fee_lower_rate,
                upper_rate=fair_fee_upper_rate,
                maximum_upper_rate=fair_fee_maximum_upper_rate,
                fee_tolerance=fair_fee_tolerance,
                evaluation_callback=lambda rate, value, point_id=point.model_point_id: notify(
                    "model_point_commercial_break_even_lip_evaluation",
                    index - 1,
                    point_id,
                    f"rate={rate:.10g}; objective_aud={value:.10g}",
                ),
            )
            notify(
                "model_point_commercial_break_even_lip_completed",
                index - 1,
                point.model_point_id,
                commercial_break_even.status,
            )

        point_results.append(
            ModelPointPortfolioValuation(
                model_point=point,
                normalised_contract_share=aggregation_weight,
                per_contract_metrics=metrics,
                normalised_contribution_metrics=normalised_contribution_metrics,
                represented_contract_count=represented_contract_count,
                portfolio_contribution_metrics=portfolio_contribution_metrics,
                fair_lip=fair_lip,
                commercial_break_even_lip=commercial_break_even,
            )
        )
        notify(
            "model_point_completed",
            index,
            point.model_point_id,
            (
                "per_contract_npv_aud="
                f"{float(metrics['insurer_net_present_value_before_risk_margin_aud']):.10g}"
            ),
        )

    notify("portfolio_aggregation_completed", total_model_points)

    fee_weights = aggregation_weights
    portfolio_fair_lip = None
    if calculate_portfolio_fair_lip:
        notify("portfolio_fair_lip_started", 0)
        portfolio_fair_lip = _solve_portfolio_lip_rate(
            objective_name="portfolio_guarantee_value_equals_zero",
            objective_selector=lambda result: result.guarantee_value,
            product=product,
            model_points=model_points.model_points,
            contribution_weights=fee_weights,
            esg_config=esg_config,
            mortality=mortality,
            behaviour=behaviour,
            expenses=expenses,
            settings=common_settings,
            scenarios=scenarios,
            lower_rate=fair_fee_lower_rate,
            upper_rate=fair_fee_upper_rate,
            maximum_upper_rate=fair_fee_maximum_upper_rate,
            fee_tolerance=fair_fee_tolerance,
            evaluation_callback=lambda rate, value: notify(
                "portfolio_fair_lip_evaluation_completed",
                total_model_points,
                detail=f"rate={rate:.10g}; objective_aud={value:.10g}",
            ),
            projection_callback=lambda rate, completed, total, point_id: notify(
                "portfolio_fair_lip_model_point_completed",
                completed,
                point_id,
                f"rate={rate:.10g}; fee_projection_total={total}",
            ),
        )
        notify(
            "portfolio_fair_lip_completed",
            total_model_points,
            detail=portfolio_fair_lip.status,
        )

    portfolio_commercial_break_even_lip = None
    if calculate_portfolio_commercial_break_even_lip:
        notify("portfolio_commercial_break_even_lip_started", 0)
        portfolio_commercial_break_even_lip = _solve_portfolio_lip_rate(
            objective_name="portfolio_insurer_net_present_value_equals_zero",
            objective_selector=lambda result: result.insurer_net_value,
            product=product,
            model_points=model_points.model_points,
            contribution_weights=fee_weights,
            esg_config=esg_config,
            mortality=mortality,
            behaviour=behaviour,
            expenses=expenses,
            settings=common_settings,
            scenarios=scenarios,
            lower_rate=fair_fee_lower_rate,
            upper_rate=fair_fee_upper_rate,
            maximum_upper_rate=fair_fee_maximum_upper_rate,
            fee_tolerance=fair_fee_tolerance,
            evaluation_callback=lambda rate, value: notify(
                "portfolio_commercial_break_even_lip_evaluation_completed",
                total_model_points,
                detail=f"rate={rate:.10g}; objective_aud={value:.10g}",
            ),
            projection_callback=lambda rate, completed, total, point_id: notify(
                "portfolio_commercial_break_even_lip_model_point_completed",
                completed,
                point_id,
                f"rate={rate:.10g}; fee_projection_total={total}",
            ),
        )
        notify(
            "portfolio_commercial_break_even_lip_completed",
            total_model_points,
            detail=portfolio_commercial_break_even_lip.status,
        )

    timing_years = sorted({
        int(key.rsplit("_", 1)[1])
        for key in behaviour_normalised_aggregate
        if key.startswith("income_election_event_mass_policy_year_")
    })
    for year in timing_years:
        eligible_key = f"eligible_growth_exposure_policy_year_{year}"
        probability_key = f"annual_take_up_probability_policy_year_{year}"
        election_key = f"income_election_event_mass_policy_year_{year}"
        share_key = f"income_election_share_policy_year_{year}"
        conditional_key = (
            f"income_election_rate_among_eligible_policy_year_{year}"
        )
        exposure = behaviour_normalised_aggregate.get(eligible_key, 0.0)
        behaviour_normalised_aggregate[probability_key] = (
            0.0
            if exposure <= 0.0
            else take_up_probability_numerator_by_year.get(year, 0.0) / exposure
        )
        behaviour_normalised_aggregate[share_key] = (
            behaviour_normalised_aggregate.get(election_key, 0.0)
        )
        behaviour_normalised_aggregate[conditional_key] = (
            0.0 if exposure <= 0.0
            else behaviour_normalised_aggregate.get(election_key, 0.0) / exposure
        )

    if timing_years:
        year_values = np.asarray(timing_years, dtype=float)
        event_values = np.asarray([
            behaviour_normalised_aggregate.get(
                f"income_election_event_mass_policy_year_{year}", 0.0
            )
            for year in timing_years
        ], dtype=float)
        forced_values = np.asarray([
            behaviour_normalised_aggregate.get(
                f"forced_income_election_event_mass_policy_year_{year}", 0.0
            )
            for year in timing_years
        ], dtype=float)
        election_total = float(np.sum(event_values))
        forced_total = float(np.sum(forced_values))
        behaviour_normalised_aggregate["income_election_event_mass"] = (
            election_total
        )
        behaviour_normalised_aggregate["income_election_share"] = election_total
        behaviour_normalised_aggregate[
            "forced_income_election_event_mass"
        ] = forced_total
        if election_total > 0.0:
            expected_year = float(
                np.sum(year_values * event_values) / election_total
            )
            median_year = float(_discrete_timing_quantile(
                year_values, event_values, 0.50
            ))
            p10_year = float(_discrete_timing_quantile(
                year_values, event_values, 0.10
            ))
            p90_year = float(_discrete_timing_quantile(
                year_values, event_values, 0.90
            ))
            behaviour_normalised_aggregate.update({
                "expected_income_start_year": expected_year,
                "median_income_start_year": median_year,
                "p10_income_start_year": p10_year,
                "p90_income_start_year": p90_year,
                "income_start_year_mean": expected_year,
                "income_start_year_median": median_year,
                "income_start_year_p10": p10_year,
                "income_start_year_p90": p90_year,
                "forced_income_election_share": forced_total / election_total,
            })
        else:
            behaviour_normalised_aggregate["forced_income_election_share"] = 0.0

    income_exposure_total = behaviour_normalised_aggregate.get(
        "income_exposure_months", 0.0
    )
    if income_exposure_total > 0.0:
        for cause in ("ordinary", "performance", "total"):
            event_key = f"{cause}_income_lapse_event_mass"
            probability_key = f"{cause}_income_lapse_probability"
            behaviour_normalised_aggregate[probability_key] = (
                behaviour_normalised_aggregate.get(event_key, 0.0)
                / income_exposure_total
            )
            behaviour_normalised_aggregate[
                f"{cause}_income_lapse_rate"
            ] = behaviour_normalised_aggregate[probability_key]

    premium = normalised_aggregate["premium_aud"]
    insurer_value = normalised_aggregate[
        "insurer_net_present_value_before_risk_margin_aud"
    ]
    cross_basis_differences = (
        {
            metric: (
                portfolio_aggregate[metric] / float(absolute_contract_count)
                - normalised_aggregate[metric]
            )
            for metric in _MONETARY_METRICS
        }
        if portfolio_aggregate is not None and absolute_contract_count is not None
        else None
    )
    if cross_basis_differences:
        cross_basis_max_metric = max(
            cross_basis_differences,
            key=lambda metric: abs(cross_basis_differences[metric]),
        )
        cross_basis_max_difference = cross_basis_differences[
            cross_basis_max_metric
        ]
    else:
        cross_basis_max_metric = None
        cross_basis_max_difference = None
    summary: dict[str, object] = {
        f"normalised_average_{metric}": value
        for metric, value in normalised_aggregate.items()
    }
    summary.update({
        f"normalised_average_{metric}": value
        for metric, value in behaviour_normalised_aggregate.items()
    })
    # Behaviour diagnostics are already contract-weighted portfolio averages
    # (or event-mass ratios recomputed after aggregation).  Publish direct
    # aliases for analysis runners and retain the explicit normalised prefix
    # for schema continuity with monetary valuation fields.
    summary.update(behaviour_normalised_aggregate)
    if absolute_contract_count is not None:
        for metric, value in behaviour_normalised_aggregate.items():
            if "event_mass" in metric or "exposure" in metric:
                summary[f"portfolio_total_{metric}"] = (
                    float(absolute_contract_count) * value
                )
    if portfolio_aggregate is not None:
        summary.update({
            f"portfolio_total_{metric}": value
            for metric, value in portfolio_aggregate.items()
        })
    summary.update({
        "aggregation_basis": aggregation_basis,
        "absolute_portfolio_values_available": portfolio_aggregate is not None,
        "portfolio_contract_count": absolute_contract_count,
        "source_exposure_counts_available": source_contract_count is not None,
        "normalised_exposure_total": 1.0,
        "aggregation_weight_source": aggregation_weight_source,
        "aggregation_weight_sum": sum(aggregation_weights),
        "cross_basis_reconciliation_max_absolute_difference_aud": (
            None
            if cross_basis_max_difference is None
            else abs(cross_basis_max_difference)
        ),
        "cross_basis_reconciliation_max_difference_metric": (
            cross_basis_max_metric
        ),
        "model_point_count": len(point_results),
        "contract_weight_sum": model_points.contract_weight_sum,
        "premium_volume_weight_sum_control": (
            model_points.premium_volume_weight_sum
        ),
        "source_weighted_average_premium_aud": (
            model_points.weighted_average_premium_aud
        ),
        "weighted_average_premium_reconciliation_difference_aud": (
            premium - model_points.weighted_average_premium_aud
        ),
        "new_business_margin_before_risk_margin": insurer_value / premium,
        "pv_future_fees_to_premium": (
            normalised_aggregate["pv_future_fees_aud"] / premium
        ),
        "bel_total_to_premium": normalised_aggregate["bel_total_aud"] / premium,
        "premium_weighted_identity_gap": identity_gap_numerator / premium,
        "profitability_materiality_bp": profitability_materiality_bp,
        "profitability_classification": (
            "positive_value"
            if insurer_value / premium > profitability_materiality_bp / 10_000.0
            else "negative_value"
            if insurer_value / premium < -profitability_materiality_bp / 10_000.0
            else "approximately_break_even"
        ),
        "crediting_cap_rate": product.reference_fund.effective_maximum_return,
        "valuation_measure": Measure.RISK_NEUTRAL.value,
        "valuation_model": common_settings.model,
        "scenario_horizon_years": float(scenarios.times[-1]),
        "n_paths": int(common_settings.n_paths),
        "seed": int(common_settings.seed),
        "heston_substeps": int(common_settings.heston_substeps),
        "record_paths": bool(common_settings.projection.record_paths),
        "heston_cos": bool(common_settings.projection.heston_cos),
        "lsmc_used": (
            surrender_policy_factory is not None
            or income_action_policy_factory is not None
            or combined_policy_factory is not None
        ),
        "income_take_up_mode": (
            "combined_policy"
            if combined_policy_factory is not None
            else behaviour.take_up.mode
        ),
        "income_take_up_source": (
            "frozen_combined_income_election_and_income_action_policy"
            if combined_policy_factory is not None
            else
            "effective_model_point_income_start_year_with_automatic_age_backstop"
            if behaviour.take_up.mode == "deterministic"
            else "dynamic_behaviour_assumptions"
        ),
        "automatic_income_start_override_model_point_count": (
            automatic_start_override_count
            if behaviour.take_up.mode == "deterministic"
            and combined_policy_factory is None
            else None
        ),
        "deterministic_benchmark_automatic_income_start_override_"
        "model_point_count": (
            automatic_start_override_count
        ),
        "joint_life_election_treatment": (
            "pathwise_primary_spouse_life_status_at_income_election"
            if uses_pathwise_joint_life
            else "spouse_survival_weighted_joint_and_single_life_fallback"
            if has_joint_life
            else "not_applicable_single_life_portfolio"
        ),
        "joint_life_dependence": (
            "independent_lives" if has_joint_life else "not_applicable"
        ),
        "joint_life_behaviour_treatment": (
            "pathwise_joint_life_combined_election_and_income_action_policy"
            if uses_pathwise_joint_life and combined_policy_factory is not None
            else "pathwise_joint_life_fitted_post_election_income_action_policy"
            if uses_pathwise_joint_life and income_action_policy_factory is not None
            else "pathwise_joint_life_fitted_post_election_surrender_policy"
            if uses_pathwise_joint_life and surrender_policy_factory is not None
            else "pathwise_joint_life_dynamic_state_dependent"
            if uses_pathwise_joint_life
            and (behaviour.use_dynamic or behaviour.use_dynamic_withdrawals)
            else "pathwise_joint_life_deterministic_election_continue_benchmark"
            if uses_pathwise_joint_life
            else
            "joint_and_single_fallback_branches_use_separately_fitted_lsmc_policies"
            if joint_continue_income_count and (
                surrender_policy_factory is not None
                or income_action_policy_factory is not None
            )
            else
            "joint_branch_static_base_single_fallback_dynamic_for_continue_income"
            if joint_continue_income_count
            and (behaviour.use_dynamic or behaviour.use_dynamic_withdrawals)
            else "joint_and_single_branches_static_base_for_continue_income"
            if joint_continue_income_count
            else "dynamic_primary_life_state_for_lump_sum_spouse_option"
            if has_joint_life
            and (behaviour.use_dynamic or behaviour.use_dynamic_withdrawals)
            else "static_base_for_lump_sum_spouse_option"
            if has_joint_life
            else "not_applicable"
        ),
        "joint_continue_income_model_point_count": joint_continue_income_count,
        "joint_life_four_state_account_cohorts": (
            False if has_joint_life else None
        ),
        "joint_life_pathwise_mortality_states": (
            uses_pathwise_joint_life if has_joint_life else None
        ),
        "fair_lip_requested": calculate_fair_lip,
        "fair_lip_solved_count": sum(
            result.fair_lip is not None and result.fair_lip.solved
            for result in point_results
        ),
        "commercial_break_even_lip_requested": (
            calculate_commercial_break_even_lip
        ),
        "commercial_break_even_lip_solved_count": sum(
            result.commercial_break_even_lip is not None
            and result.commercial_break_even_lip.solved
            for result in point_results
        ),
        "portfolio_fair_lip_requested": calculate_portfolio_fair_lip,
        "portfolio_commercial_break_even_lip_requested": (
            calculate_portfolio_commercial_break_even_lip
        ),
        "portfolio_common_fee_solve_weighting": (
            "normalised_represented_contract_share"
        ),
        "portfolio_common_fee_objective_value_basis": (
            "normalised_portfolio_average_contract"
        ),
        "individual_fair_fees_are_not_averaged": True,
    })
    if portfolio_fair_lip is not None:
        summary.update(portfolio_fair_lip.as_dict("portfolio_fair_lip"))
    if portfolio_commercial_break_even_lip is not None:
        summary.update(portfolio_commercial_break_even_lip.as_dict(
            "portfolio_commercial_break_even_lip"
        ))

    notify("portfolio_valuation_completed", total_model_points)

    return PortfolioValuationResult(
        summary=summary,
        normalised_average_metrics=normalised_aggregate,
        portfolio_total_metrics=portfolio_aggregate,
        model_points=tuple(point_results),
        settings=common_settings,
        scenario_fingerprint=scenarios.content_fingerprint,
        scenario_horizon_years=float(scenarios.times[-1]),
        aggregation_basis=aggregation_basis,
        portfolio_contract_count=absolute_contract_count,
        portfolio_fair_lip=portfolio_fair_lip,
        portfolio_commercial_break_even_lip=(
            portfolio_commercial_break_even_lip
        ),
    )


__all__ = [
    "FairFeeSolveResult",
    "ModelPointPortfolioValuation",
    "PortfolioProgress",
    "PortfolioValuationResult",
    "value_policyholder_portfolio",
]
