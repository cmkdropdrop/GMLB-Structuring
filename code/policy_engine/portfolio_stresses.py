"""Shared, auditable stress definitions for portfolio valuations.

The stresses in this module are deliberately small, deterministic wrappers
around the existing ``CapitalStresses`` research defaults.  Non-behaviour
stresses are suitable for paired Dynamic-Behaviour and LSMC revaluations; lapse
up/down are Dynamic-only because the LSMC reader rejects behaviour transforms.
They are not a complete regulatory capital specification.  The lapse-up and
lapse-down cases are permanent multiplicative stresses; no mass-lapse event is
modelled here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Callable, Mapping, Optional

import numpy as np

from .behavior import BehaviourModel
from .capital import CapitalStresses
from .esg import ESGConfig, ScenarioSet
from .mortality import MortalityTable
from .product import ExpenseAssumptions


PORTFOLIO_STRESS_DEFINITION_VERSION = "1.1"


def _serialisable(value: object) -> object:
    """Return a JSON-native copy of a stress parameter value."""
    if isinstance(value, Mapping):
        return {str(key): _serialisable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_serialisable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


@dataclass(frozen=True)
class PortfolioStressDefinition:
    """Versioned, serialisable definition of one portfolio revaluation."""

    stress_id: str
    risk_category: str
    label: str
    description: str
    input_transform: str = "none"
    behaviour_transform: str = "none"
    scenario_transform: str = "none"
    parameters: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )
    definition_version: str = PORTFOLIO_STRESS_DEFINITION_VERSION

    def __post_init__(self) -> None:
        if not self.stress_id or not self.risk_category or not self.label:
            raise ValueError("Portfolio stress identifiers and labels cannot be empty.")
        object.__setattr__(
            self,
            "parameters",
            MappingProxyType(dict(self.parameters)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "definition_version": self.definition_version,
            "stress_id": self.stress_id,
            "risk_category": self.risk_category,
            "label": self.label,
            "description": self.description,
            "input_transform": self.input_transform,
            "behaviour_transform": self.behaviour_transform,
            "scenario_transform": self.scenario_transform,
            "parameters": _serialisable(self.parameters),
        }

    def audit_dict(
        self,
        *,
        applied_to_training: bool,
        applied_to_evaluation: bool,
    ) -> dict[str, object]:
        return {
            **self.to_dict(),
            "applied_to_training": bool(applied_to_training),
            "applied_to_evaluation": bool(applied_to_evaluation),
        }


_CAPITAL_STRESSES = CapitalStresses()


PORTFOLIO_STRESSES: Mapping[str, PortfolioStressDefinition] = MappingProxyType({
    "base": PortfolioStressDefinition(
        stress_id="base",
        risk_category="base",
        label="Base",
        description="Unstressed market-consistent portfolio valuation.",
    ),
    "interest_up": PortfolioStressDefinition(
        stress_id="interest_up",
        risk_category="interest_rate",
        label="Interest rates up",
        description=(
            "Tenor-dependent upward zero-curve stress using CapitalStresses."
        ),
        input_transform="esg_zero_curve",
        parameters={
            "tenors_years": _CAPITAL_STRESSES.ir_up_tenors,
            "relative_factors": _CAPITAL_STRESSES.ir_up_factors,
            "minimum_absolute_shift": _CAPITAL_STRESSES.ir_up_min_shift,
        },
    ),
    "interest_down": PortfolioStressDefinition(
        stress_id="interest_down",
        risk_category="interest_rate",
        label="Interest rates down",
        description=(
            "Tenor-dependent downward zero-curve stress using CapitalStresses."
        ),
        input_transform="esg_zero_curve",
        parameters={
            "tenors_years": _CAPITAL_STRESSES.ir_up_tenors,
            "relative_factors": _CAPITAL_STRESSES.ir_dn_factors,
            "minimum_absolute_shift": 0.0,
        },
    ),
    "equity_level_down": PortfolioStressDefinition(
        stress_id="equity_level_down",
        risk_category="equity_level",
        label="Equity level down",
        description=(
            "39% reduction of both simulated equity index levels after time zero."
        ),
        scenario_transform="index_levels_after_time_zero",
        parameters={
            "relative_change": -_CAPITAL_STRESSES.equity_type1,
            "level_multiplier": 1.0 - _CAPITAL_STRESSES.equity_type1,
        },
    ),
    "equity_volatility_up": PortfolioStressDefinition(
        stress_id="equity_volatility_up",
        risk_category="equity_volatility",
        label="Equity volatility up",
        description=(
            "25% relative increase in Black-Scholes volatility and Heston "
            "initial/long-run variance."
        ),
        input_transform="esg_equity_volatility",
        parameters={"relative_change": _CAPITAL_STRESSES.equity_vol_rel},
    ),
    "longevity": PortfolioStressDefinition(
        stress_id="longevity",
        risk_category="longevity",
        label="Longevity",
        description="20% multiplicative reduction in annual mortality rates qx.",
        input_transform="mortality",
        parameters={"qx_multiplier": 1.0 + _CAPITAL_STRESSES.longevity},
    ),
    "mortality": PortfolioStressDefinition(
        stress_id="mortality",
        risk_category="mortality",
        label="Mortality",
        description="15% multiplicative increase in annual mortality rates qx.",
        input_transform="mortality",
        parameters={"qx_multiplier": 1.0 + _CAPITAL_STRESSES.mortality},
    ),
    "lapse_up": PortfolioStressDefinition(
        stress_id="lapse_up",
        risk_category="lapse",
        label="Lapse rates up",
        description=(
            "Permanent 50% increase in annual ordinary lapse baselines and "
            "the performance-sensitive excess-hazard cap."
        ),
        behaviour_transform="scale_lapses",
        parameters={"lapse_multiplier": 1.0 + _CAPITAL_STRESSES.lapse_up},
    ),
    "lapse_down": PortfolioStressDefinition(
        stress_id="lapse_down",
        risk_category="lapse",
        label="Lapse rates down",
        description=(
            "Permanent 50% reduction in annual ordinary lapse baselines and "
            "the performance-sensitive excess-hazard cap."
        ),
        behaviour_transform="scale_lapses",
        parameters={"lapse_multiplier": 1.0 + _CAPITAL_STRESSES.lapse_dn},
    ),
    "expense": PortfolioStressDefinition(
        stress_id="expense",
        risk_category="expense",
        label="Expense",
        description=(
            "10% increase in fixed and investment-value maintenance expenses "
            "plus one percentage point of annual expense inflation."
        ),
        input_transform="expenses",
        parameters={
            "maintenance_multiplier": 1.0 + _CAPITAL_STRESSES.expense_level,
            "expense_inflation_add": _CAPITAL_STRESSES.expense_inflation_add,
        },
    ),
})

PORTFOLIO_STRESS_CHOICES = tuple(PORTFOLIO_STRESSES)
PORTFOLIO_NON_BEHAVIOUR_STRESS_CHOICES = tuple(
    stress_id
    for stress_id, definition in PORTFOLIO_STRESSES.items()
    if definition.behaviour_transform == "none"
)


def get_portfolio_stress(
    stress: str | PortfolioStressDefinition,
) -> PortfolioStressDefinition:
    if isinstance(stress, PortfolioStressDefinition):
        return stress
    try:
        return PORTFOLIO_STRESSES[str(stress)]
    except KeyError as exc:
        choices = ", ".join(PORTFOLIO_STRESS_CHOICES)
        raise ValueError(
            f"Unknown portfolio stress {stress!r}; expected one of: {choices}."
        ) from exc


def apply_portfolio_input_stress(
    stress: str | PortfolioStressDefinition,
    esg_config: ESGConfig,
    mortality: MortalityTable,
    expenses: Optional[ExpenseAssumptions],
) -> tuple[ESGConfig, MortalityTable, Optional[ExpenseAssumptions]]:
    """Apply ESG, mortality or expense input changes for one stress."""
    definition = get_portfolio_stress(stress)
    stressed_esg = esg_config
    stressed_mortality = mortality
    stressed_expenses = expenses

    if definition.input_transform == "esg_zero_curve":
        tenors = np.asarray(esg_config.curve.tenors, dtype=float)
        factors = np.interp(
            tenors,
            np.asarray(definition.parameters["tenors_years"], dtype=float),
            np.asarray(definition.parameters["relative_factors"], dtype=float),
        )
        stressed_curve = esg_config.curve.scaled(
            factors,
            min_abs_shift=float(
                definition.parameters["minimum_absolute_shift"]
            ),
        )
        stressed_esg = esg_config.with_curve(stressed_curve)
    elif definition.input_transform == "esg_equity_volatility":
        stressed_esg = esg_config.bump_equity_vol(
            float(definition.parameters["relative_change"])
        )
    elif definition.input_transform == "mortality":
        stressed_mortality = mortality.stressed(
            float(definition.parameters["qx_multiplier"])
        )
    elif definition.input_transform == "expenses":
        if expenses is None:
            raise ValueError("The expense stress requires expense assumptions.")
        multiplier = float(definition.parameters["maintenance_multiplier"])
        stressed_expenses = replace(
            expenses,
            maintenance_per_policy=expenses.maintenance_per_policy * multiplier,
            maintenance_pct_of_iv=expenses.maintenance_pct_of_iv * multiplier,
            expense_inflation=(
                expenses.expense_inflation
                + float(definition.parameters["expense_inflation_add"])
            ),
        )
    elif definition.input_transform != "none":
        raise ValueError(
            f"Unsupported input transform {definition.input_transform!r}."
        )

    return stressed_esg, stressed_mortality, stressed_expenses


def apply_portfolio_behaviour_stress(
    stress: str | PortfolioStressDefinition,
    behaviour: BehaviourModel,
) -> BehaviourModel:
    """Apply a permanent policyholder-behaviour stress.

    Behaviour stresses are kept separate from market, mortality and expense
    input transforms so they cannot alter a Q-market or hedge-cache identity.
    ``BehaviourModel.scaled_lapses`` scales both the ordinary lapse baselines
    and the independent performance-sensitive lapse cause.
    """
    definition = get_portfolio_stress(stress)
    if definition.behaviour_transform == "none":
        return behaviour
    if definition.behaviour_transform != "scale_lapses":
        raise ValueError(
            "Unsupported behaviour transform "
            f"{definition.behaviour_transform!r}."
        )
    return behaviour.scaled_lapses(
        float(definition.parameters["lapse_multiplier"])
    )


def apply_portfolio_scenario_stress(
    stress: str | PortfolioStressDefinition,
    scenarios: ScenarioSet,
) -> ScenarioSet:
    """Apply the path-level component of a portfolio stress."""
    definition = get_portfolio_stress(stress)
    if definition.scenario_transform == "none":
        return scenarios
    if definition.scenario_transform != "index_levels_after_time_zero":
        raise ValueError(
            "Unsupported scenario transform "
            f"{definition.scenario_transform!r}."
        )

    multiplier = float(definition.parameters["level_multiplier"])
    levels = {
        index: np.array(values, dtype=float, copy=True)
        for index, values in scenarios.index_levels.items()
    }
    for values in levels.values():
        values[:, 1:] *= multiplier
    return replace(scenarios, index_levels=levels)


def portfolio_scenario_transform(
    stress: str | PortfolioStressDefinition,
) -> Optional[Callable[[ScenarioSet], ScenarioSet]]:
    """Return a ScenarioSet callable only when a path transform is required."""
    definition = get_portfolio_stress(stress)
    if definition.scenario_transform == "none":
        return None

    def transform(scenarios: ScenarioSet) -> ScenarioSet:
        return apply_portfolio_scenario_stress(definition, scenarios)

    return transform
