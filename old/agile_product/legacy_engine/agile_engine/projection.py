"""Path-wise projection of the generic index-linked lifetime-income policy.

The projection engine evolves the full contract state on a monthly grid over
each ESG path and produces probability-weighted cashflows for the insurer and
the policyholder. It is shared by the market-consistent pricing module
(risk-neutral scenarios) and the profitability module (real-world scenarios).

State machine (per path)
------------------------
GROWTH  --income election (>= 1st anniversary)-->  INCOME  --> absorbing
Death and Income-phase full surrender are handled by probability weighting
(deterministic expected decrements and path-dependent dynamic lapse).  Growth
surrender and every Growth withdrawal are structurally prohibited.

Monthly event order (documented convention)
-------------------------------------------
1. Global-Equity and rolling five-year AUD-government-bond evolution, followed
   by monthly rebalancing of the complete Reference Fund to its configured
   equity/bond target allocation,
2. Anniversary only: Total-Protection credit with the fixed 6% cap applied
   once to the complete annual Reference-Fund return,
3. ACT/365F Product-Fee/LIP accrual; posting at an Anniversary and immediately
   before a terminating death or Full Withdrawal,
4. expected death decrement for the interval just ended under its
   pre-Election coverage state and post-fee death benefit (no MVA),
5. current-Anniversary dynamic Income take-up by surviving contracts,
6. Anniversary only: announcement of the next crediting-year cap and restart
   of its DVA/hedge period; the old cap has already been used in step 2,
7. lifetime income payment to lives surviving to the payment date (monthly,
   in arrears; the first payment falls one month after income election, PDS
   section 13); shortfall beyond Account Value is a Guarantee Claim,
8. exactly one voluntary Income action: either the configured statistical
   Partial/Excess-Withdrawal-and-lapse path or an external unified
   CONTINUE/PARTIAL/FULL policy action.

Daily Value Adjustment and insurer hedge/backing model
-------------------------------------------------------
Intra-year Account Value is valued as a zero bond maturing at the next
Anniversary plus one Total-Protection package on the *complete* Reference
Fund, ``pz_t = P(t,T_anniv) + V_pkg(t)``.
The customer-facing value ``iv_frame * pz_t`` is an exact discounted
martingale that converges to the contractual 1 + credit at the next
Anniversary.  The package uses a
joint-model moment-matched volatility derived solely from the existing
Global-Equity and Hull-White parameters.  It is a transparent DVA proxy, not a
claim of exact conditional mixed-fund option valuation.

The insurer backing is separate.  The administrative crediting frame is held
in a continuously rolled AUD overnight account; its pathwise income is
obtained from the simulated short-rate integral.  The under-year DVA option
mark remains a customer-liability value, not a backing asset.  At each
crediting-period start, the insurer buys either the standard capped call spread
or, explicitly, an
uncapped long call.  Fair premium, purchase markup, hedge-reference management
fee and any legacy execution proxy are insurer hedge costs.  They never alter
the customer Reference Fund, Account Value, credited return or claims.  The
uncapped alternative alone records the option payoff above the customer cap as
an insurer hedge gain.  Neither COS nor LSMC is used to value this intra-year
DVA package.
"""

from __future__ import annotations

from calendar import isleap
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from enum import Enum
from inspect import Parameter, signature
from types import MappingProxyType
from typing import Dict, Mapping, Optional

import numpy as np
from numpy.typing import NDArray

from .behavior import BehaviourModel
from .crediting import (HedgeCapLegMode, credited_return,
                        crediting_package_value, hedge_option_package_value,
                        heston_package_value,
                        intra_year_value_factor, retained_excess_return)
from .esg import ScenarioSet, STEPS_PER_YEAR
from .mortality import MortalityTable
from .product import (IndexLinkedLifetimeIncomeProduct, ExpenseAssumptions, FundingSource,
                      PolicySpec, Phase,
                      Protection, SpouseDeathElection, INCOME_PHASE_OPTION)

Array = NDArray[np.float64]


class IncomeActionType(str, Enum):
    """Mutually exclusive voluntary actions available in Income phase."""

    CONTINUE = "continue"
    PARTIAL_WITHDRAWAL = "partial_withdrawal"
    FULL_WITHDRAWAL = "full_withdrawal"


@dataclass(frozen=True)
class IncomeActionDecision:
    """Immutable pathwise decision returned by an optimal Income policy.

    ``action_type`` accepts exact :class:`IncomeActionType` members or their
    string values.  A Partial Withdrawal specifies its gross amount as a
    fraction of ``context.max_partial_gross_amount``.  CONTINUE and FULL must
    carry a zero fraction so the three actions remain strictly exclusive.
    """

    action_type: object
    partial_fraction_of_max: Array

    def __post_init__(self) -> None:
        supplied_actions = np.asarray(self.action_type, dtype=object)
        if supplied_actions.ndim != 1:
            raise ValueError("Income action_type must be one-dimensional.")

        normalised = np.empty(supplied_actions.shape, dtype="<U18")
        for index, supplied in enumerate(supplied_actions):
            try:
                action = (
                    supplied
                    if isinstance(supplied, IncomeActionType)
                    else IncomeActionType(supplied)
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Income action_type contains an unknown action."
                ) from exc
            normalised[index] = action.value

        fractions = np.array(
            self.partial_fraction_of_max, dtype=float, copy=True
        )
        if fractions.ndim != 1:
            raise ValueError(
                "partial_fraction_of_max must be one-dimensional."
            )
        if fractions.shape != normalised.shape:
            raise ValueError(
                "Income action arrays must share one scenario-path shape."
            )
        if not np.all(np.isfinite(fractions)) or not np.all(
            (fractions >= 0.0) & (fractions <= 1.0)
        ):
            raise ValueError(
                "partial_fraction_of_max must contain finite values in [0, 1]."
            )

        partial = normalised == IncomeActionType.PARTIAL_WITHDRAWAL.value
        if np.any(partial & (fractions <= 0.0)):
            raise ValueError(
                "PARTIAL_WITHDRAWAL requires a strictly positive fraction."
            )
        if np.any(~partial & (fractions != 0.0)):
            raise ValueError(
                "CONTINUE and FULL_WITHDRAWAL require a zero partial fraction."
            )

        normalised.setflags(write=False)
        fractions.setflags(write=False)
        object.__setattr__(self, "action_type", normalised)
        object.__setattr__(self, "partial_fraction_of_max", fractions)

    @property
    def n_paths(self) -> int:
        """Number of scenario paths represented by the decision."""
        return int(self.action_type.shape[0])


@dataclass(frozen=True)
class IncomeActionDecisionContext:
    """Read-only state at the monthly voluntary Income-action boundary.

    The boundary is after mortality, any Income Election and the regular
    monthly Fixed-Income payment.  It contains customer-observable current
    state only: no future market paths, discount factors, backing assets or
    hedge results.  ``max_partial_gross_amount`` is the largest contractual
    gross deduction which preserves the minimum residual Account Value;
    cash received can be smaller because MVA is applied by the projector.
    """

    step: int
    phase: NDArray[np.int8]
    inforce_weight: Array
    partial_withdrawal_eligible: NDArray[np.bool_]
    full_withdrawal_eligible: NDArray[np.bool_]
    max_partial_gross_amount: Array
    account_value: Array
    locked_annual_income: Array
    guarantee_pv: Array
    guarantee_log_moneyness: Array
    mva_factor: Array
    surrender_value: Array
    short_rate: Array
    zero_rate_5y: Array
    heston_variance: Array
    duration_years: float
    mva_remaining_years: float
    attained_age: Array
    time_to_forced_election: Array
    primary_alive: NDArray[np.bool_]
    spouse_alive: NDArray[np.bool_]
    announced_cap: Array
    previous_reference_return: Array
    previous_credited_return: Array
    performance_gap: Array
    just_elected: NDArray[np.bool_]

    def __post_init__(self) -> None:
        if isinstance(self.step, bool) or int(self.step) != self.step or self.step < 0:
            raise ValueError("Income-action step must be a non-negative integer.")
        if not np.isfinite(self.duration_years) or self.duration_years < 0.0:
            raise ValueError(
                "Income-action duration_years must be finite and non-negative."
            )
        if (
            not np.isfinite(self.mva_remaining_years)
            or self.mva_remaining_years < 0.0
        ):
            raise ValueError(
                "Income-action mva_remaining_years must be finite/non-negative."
            )

        array_dtypes: dict[str, object] = {
            "phase": np.int8,
            "inforce_weight": float,
            "partial_withdrawal_eligible": bool,
            "full_withdrawal_eligible": bool,
            "max_partial_gross_amount": float,
            "account_value": float,
            "locked_annual_income": float,
            "guarantee_pv": float,
            "guarantee_log_moneyness": float,
            "mva_factor": float,
            "surrender_value": float,
            "short_rate": float,
            "zero_rate_5y": float,
            "heston_variance": float,
            "attained_age": float,
            "time_to_forced_election": float,
            "primary_alive": bool,
            "spouse_alive": bool,
            "announced_cap": float,
            "previous_reference_return": float,
            "previous_credited_return": float,
            "performance_gap": float,
            "just_elected": bool,
        }
        expected_shape: Optional[tuple[int, ...]] = None
        for name, dtype in array_dtypes.items():
            value = np.array(getattr(self, name), dtype=dtype, copy=True)
            if value.ndim != 1:
                raise ValueError(
                    f"Income-action context {name} must be one-dimensional."
                )
            if expected_shape is None:
                expected_shape = value.shape
            elif value.shape != expected_shape:
                raise ValueError(
                    "Income-action context arrays must share one path shape."
                )
            if dtype not in (bool, np.int8):
                valid = (
                    np.all(~np.isnan(value) & (value >= 0.0))
                    if name == "announced_cap"
                    else np.all(np.isfinite(value))
                )
                if not valid:
                    raise ValueError(
                        f"Income-action context {name} is invalid."
                    )
            value.setflags(write=False)
            object.__setattr__(self, name, value)

        if not np.all(np.isin(
            self.phase,
            np.asarray([
                Phase.GROWTH.value,
                Phase.INCOME.value,
                Phase.TERMINATED.value,
            ], dtype=np.int8),
        )):
            raise ValueError("Income-action context contains an unknown phase.")
        for name in (
            "inforce_weight",
            "max_partial_gross_amount",
            "account_value",
            "locked_annual_income",
            "guarantee_pv",
            "mva_factor",
            "surrender_value",
            "attained_age",
            "time_to_forced_election",
        ):
            if np.any(getattr(self, name) < 0.0):
                raise ValueError(
                    f"Income-action context {name} must be non-negative."
                )
        if np.any(self.mva_factor > 1.0 + 1.0e-12):
            raise ValueError("Income-action mva_factor must not exceed one.")
        if np.any(
            self.partial_withdrawal_eligible
            & (self.phase != Phase.INCOME.value)
        ) or np.any(
            self.full_withdrawal_eligible
            & (self.phase != Phase.INCOME.value)
        ):
            raise ValueError("Income actions are eligible only in Income phase.")
        if np.any(
            self.full_withdrawal_eligible & self.just_elected
        ):
            raise ValueError(
                "Full Withdrawal cannot be eligible in the Election month."
            )

    @property
    def n_paths(self) -> int:
        """Number of scenario paths represented by the context."""
        return int(self.account_value.shape[0])


def _frozen_path_array(
    value: object,
    *,
    name: str,
    dtype: object = float,
    shape: Optional[tuple[int, ...]] = None,
    allow_positive_infinity: bool = False,
) -> NDArray:
    """Return one defensive, read-only one-dimensional path array."""
    array = np.array(value, dtype=dtype, copy=True)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional.")
    if shape is not None and array.shape != shape:
        raise ValueError(f"{name} must share the scenario-path shape {shape}.")
    if dtype not in (bool, np.bool_, np.int8):
        valid = np.isfinite(array)
        if allow_positive_infinity:
            valid |= np.isposinf(array)
        if not np.all(valid):
            qualifier = "finite values or positive infinity" if (
                allow_positive_infinity
            ) else "finite values"
            raise ValueError(f"{name} must contain {qualifier}.")
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class IncomeActionState:
    """Complete array-native state at a voluntary Income-action boundary.

    This is an engine/training surface, not an information surface offered to
    a Policyholder policy.  It deliberately carries the fee, mortality and
    DVA subledgers needed to propagate a counterfactual action to the next
    monthly boundary.  All fields are defensively copied and read-only.

    The v2 optimal-action engine supports the generic product without Age
    Pension Plus.  Growth paths may be present in a collected panel, but the
    transition functions prohibit voluntary actions on those paths.
    """

    step: int
    path_index: NDArray[np.int64]
    gross_premium: Array
    attained_age: Array
    time_to_forced_election: Array
    account_value: Array
    iv_frame: Array
    locked_annual_income: Array
    phase: NDArray[np.int8]
    inforce_weight: Array
    fee_product_accrued: Array
    fee_lip_accrued: Array
    primary_alive: NDArray[np.bool_]
    spouse_alive: NDArray[np.bool_]
    joint_income_cover: NDArray[np.bool_]
    joint_survival_primary: Array
    joint_survival_spouse: Array
    previous_reference_return: Array
    previous_credited_return: Array
    performance_gap: Array
    announced_cap: Array
    just_elected: NDArray[np.bool_]

    def __post_init__(self) -> None:
        if (
            isinstance(self.step, bool)
            or int(self.step) != self.step
            or self.step < 0
        ):
            raise ValueError("Income-action state step must be non-negative.")
        dtypes: dict[str, object] = {
            "path_index": np.int64,
            "gross_premium": float,
            "attained_age": float,
            "time_to_forced_election": float,
            "account_value": float,
            "iv_frame": float,
            "locked_annual_income": float,
            "phase": np.int8,
            "inforce_weight": float,
            "fee_product_accrued": float,
            "fee_lip_accrued": float,
            "primary_alive": bool,
            "spouse_alive": bool,
            "joint_income_cover": bool,
            "joint_survival_primary": float,
            "joint_survival_spouse": float,
            "previous_reference_return": float,
            "previous_credited_return": float,
            "performance_gap": float,
            "announced_cap": float,
            "just_elected": bool,
        }
        shape: Optional[tuple[int, ...]] = None
        for name, dtype in dtypes.items():
            value = _frozen_path_array(
                getattr(self, name), name=f"Income-action state {name}",
                dtype=dtype, shape=shape,
                allow_positive_infinity=name == "announced_cap",
            )
            if shape is None:
                shape = value.shape
            object.__setattr__(self, name, value)

        if not np.all(np.isin(
            self.phase,
            np.asarray([
                Phase.GROWTH.value,
                Phase.INCOME.value,
                Phase.TERMINATED.value,
            ], dtype=np.int8),
        )):
            raise ValueError("Income-action state contains an unknown phase.")
        if np.any(self.path_index < 0) or np.unique(self.path_index).size != self.n_paths:
            raise ValueError("Income-action state path_index must be unique/non-negative.")
        for name in (
            "gross_premium",
            "attained_age",
            "time_to_forced_election",
            "account_value",
            "iv_frame",
            "locked_annual_income",
            "inforce_weight",
            "fee_product_accrued",
            "fee_lip_accrued",
            "performance_gap",
            "announced_cap",
        ):
            if np.any(getattr(self, name) < 0.0):
                raise ValueError(f"Income-action state {name} must be non-negative.")
        if np.any(self.gross_premium <= 0.0):
            raise ValueError("Income-action state gross_premium must be positive.")
        for name in ("joint_survival_primary", "joint_survival_spouse"):
            value = getattr(self, name)
            if np.any((value < 0.0) | (value > 1.0)):
                raise ValueError(f"Income-action state {name} must be in [0, 1].")

    @property
    def n_paths(self) -> int:
        return int(self.account_value.shape[0])


@dataclass(frozen=True)
class IncomeMonthScenarioSlice:
    """Exogenous current/next-boundary data for one Income month.

    The object is intentionally explicit: market-model, mortality and discount
    simulation remain owned by the canonical projector.  A Forward pass can
    collect these immutable slices once, and every CONTINUE/PARTIAL/FULL
    counterfactual then advances under the *same* market and mortality shock.

    ``anniversary_credit_rate`` is used only when ``is_anniversary`` is true.
    ``next_dva_factor`` maps the post-credit/post-fee IV frame to customer
    Account Value at the next action boundary (one when DVA is disabled).
    ``terminating_death_probability`` is either a sampled 0/1 event or the
    expected monthly decrement used by the deterministic projector.
    """

    current_step: int
    next_step: int
    current_duration_years: float
    next_duration_years: float
    is_anniversary: bool
    terminal_next: bool
    fee_year_fraction: float
    current_mva_factor: Array
    current_annuity_factor: Array
    current_short_rate: Array
    current_zero_rate_5y: Array
    current_heston_variance: Array
    anniversary_credit_rate: Array
    next_dva_factor: Array
    terminating_death_probability: Array
    next_primary_alive: NDArray[np.bool_]
    next_spouse_alive: NDArray[np.bool_]
    next_joint_income_cover: NDArray[np.bool_]
    next_joint_survival_primary: Array
    next_joint_survival_spouse: Array
    next_mva_factor: Array
    next_annuity_factor: Array
    next_short_rate: Array
    next_zero_rate_5y: Array
    next_heston_variance: Array
    next_announced_cap: Array
    next_reference_return: Array
    next_credited_return: Array
    next_performance_gap: Array
    discount_ratio: Array

    def __post_init__(self) -> None:
        for name in ("current_step", "next_step"):
            value = getattr(self, name)
            if isinstance(value, bool) or int(value) != value or value < 0:
                raise ValueError(f"Income-month {name} must be non-negative.")
        if self.next_step != self.current_step + 1:
            raise ValueError("Income-month slices must span exactly one grid step.")
        if (
            not np.isfinite(self.current_duration_years)
            or not np.isfinite(self.next_duration_years)
            or self.current_duration_years < 0.0
            or self.next_duration_years <= self.current_duration_years
        ):
            raise ValueError("Income-month durations must be increasing and finite.")
        if not isinstance(self.is_anniversary, (bool, np.bool_)):
            raise ValueError("Income-month is_anniversary must be boolean.")
        if not isinstance(self.terminal_next, (bool, np.bool_)):
            raise ValueError("Income-month terminal_next must be boolean.")
        if not np.isfinite(self.fee_year_fraction) or self.fee_year_fraction <= 0.0:
            raise ValueError("Income-month fee_year_fraction must be positive.")

        dtypes: dict[str, object] = {
            "current_mva_factor": float,
            "current_annuity_factor": float,
            "current_short_rate": float,
            "current_zero_rate_5y": float,
            "current_heston_variance": float,
            "anniversary_credit_rate": float,
            "next_dva_factor": float,
            "terminating_death_probability": float,
            "next_primary_alive": bool,
            "next_spouse_alive": bool,
            "next_joint_income_cover": bool,
            "next_joint_survival_primary": float,
            "next_joint_survival_spouse": float,
            "next_mva_factor": float,
            "next_annuity_factor": float,
            "next_short_rate": float,
            "next_zero_rate_5y": float,
            "next_heston_variance": float,
            "next_announced_cap": float,
            "next_reference_return": float,
            "next_credited_return": float,
            "next_performance_gap": float,
            "discount_ratio": float,
        }
        shape: Optional[tuple[int, ...]] = None
        for name, dtype in dtypes.items():
            value = _frozen_path_array(
                getattr(self, name), name=f"Income-month slice {name}",
                dtype=dtype, shape=shape,
                allow_positive_infinity=name == "next_announced_cap",
            )
            if shape is None:
                shape = value.shape
            object.__setattr__(self, name, value)

        for name in ("current_mva_factor", "next_mva_factor"):
            value = getattr(self, name)
            if np.any((value < 0.0) | (value > 1.0 + 1.0e-12)):
                raise ValueError(f"Income-month {name} must be in [0, 1].")
        for name in (
            "current_annuity_factor",
            "current_heston_variance",
            "anniversary_credit_rate",
            "next_dva_factor",
            "next_annuity_factor",
            "next_heston_variance",
            "next_announced_cap",
            "next_performance_gap",
            "discount_ratio",
        ):
            if np.any(getattr(self, name) < 0.0):
                raise ValueError(f"Income-month {name} must be non-negative.")
        if np.any(self.next_dva_factor <= 0.0):
            raise ValueError("Income-month next_dva_factor must be positive.")
        if np.any(self.discount_ratio <= 0.0):
            raise ValueError("Income-month discount_ratio must be positive.")
        probability = self.terminating_death_probability
        if np.any((probability < 0.0) | (probability > 1.0)):
            raise ValueError(
                "Income-month terminating_death_probability must be in [0, 1]."
            )
        for name in ("next_joint_survival_primary", "next_joint_survival_spouse"):
            value = getattr(self, name)
            if np.any((value < 0.0) | (value > 1.0)):
                raise ValueError(f"Income-month {name} must be in [0, 1].")

    @property
    def n_paths(self) -> int:
        return int(self.current_mva_factor.shape[0])


@dataclass(frozen=True)
class IncomeActionTransition:
    """Immediate action cashflows and exact post-action contract state.

    Cashflows are already multiplied by ``state.inforce_weight``, matching the
    canonical projector ledgers.  A Partial Withdrawal has no fee cashflow;
    Full Withdrawal posts both fee subledgers before surrender settlement.
    """

    executed_decision: IncomeActionDecision
    post_action_state: IncomeActionState
    gross_partial_deduction: Array
    partial_withdrawal_cashflow: Array
    surrender_benefit_cashflow: Array
    fees_product_cashflow: Array
    fees_lip_cashflow: Array
    mva_retained_cashflow: Array

    def __post_init__(self) -> None:
        if not isinstance(self.executed_decision, IncomeActionDecision):
            raise TypeError("executed_decision must be IncomeActionDecision.")
        if not isinstance(self.post_action_state, IncomeActionState):
            raise TypeError("post_action_state must be IncomeActionState.")
        n_paths = self.post_action_state.n_paths
        if self.executed_decision.n_paths != n_paths:
            raise ValueError("Income action transition path shapes do not match.")
        for name in (
            "gross_partial_deduction",
            "partial_withdrawal_cashflow",
            "surrender_benefit_cashflow",
            "fees_product_cashflow",
            "fees_lip_cashflow",
            "mva_retained_cashflow",
        ):
            value = _frozen_path_array(
                getattr(self, name), name=f"Income action transition {name}",
                shape=(n_paths,),
            )
            if np.any(value < 0.0):
                raise ValueError(f"Income action transition {name} is negative.")
            object.__setattr__(self, name, value)

    @property
    def policyholder_cashflow(self) -> Array:
        value = np.asarray(
            self.partial_withdrawal_cashflow + self.surrender_benefit_cashflow,
            dtype=float,
        )
        value.setflags(write=False)
        return value


@dataclass(frozen=True)
class IncomeMonthTransition:
    """Mandatory cashflows and next state after one Income month."""

    next_state: IncomeActionState
    next_context: IncomeActionDecisionContext
    income_cashflow: Array
    death_benefit_cashflow: Array
    terminal_closeout_cashflow: Array
    guarantee_claim_cashflow: Array
    fees_product_cashflow: Array
    fees_lip_cashflow: Array
    discount_ratio: Array

    def __post_init__(self) -> None:
        if not isinstance(self.next_state, IncomeActionState):
            raise TypeError("next_state must be IncomeActionState.")
        if not isinstance(self.next_context, IncomeActionDecisionContext):
            raise TypeError("next_context must be IncomeActionDecisionContext.")
        n_paths = self.next_state.n_paths
        if self.next_context.n_paths != n_paths:
            raise ValueError("Income month transition path shapes do not match.")
        for name in (
            "income_cashflow",
            "death_benefit_cashflow",
            "terminal_closeout_cashflow",
            "guarantee_claim_cashflow",
            "fees_product_cashflow",
            "fees_lip_cashflow",
            "discount_ratio",
        ):
            value = _frozen_path_array(
                getattr(self, name), name=f"Income month transition {name}",
                shape=(n_paths,),
            )
            if np.any(value < 0.0):
                raise ValueError(f"Income month transition {name} is negative.")
            object.__setattr__(self, name, value)

    @property
    def mandatory_policyholder_cashflow(self) -> Array:
        value = np.asarray(
            self.income_cashflow
            + self.death_benefit_cashflow
            + self.terminal_closeout_cashflow,
            dtype=float,
        )
        value.setflags(write=False)
        return value


class IncomeTransitionPanelCollector:
    """Minimal recorder for one projector run's monthly Income panels.

    The projector calls :meth:`observe_income_transition` once for each step
    which has positive Income exposure.  Stored state/slice objects are already
    immutable; mapping snapshots are exposed read-only.  Reusing one collector
    for two projections without constructing a fresh instance is rejected so
    model-point panels cannot be mixed accidentally.
    """

    def __init__(self) -> None:
        self._states_by_step: dict[int, IncomeActionState] = {}
        self._slices_by_step: dict[int, IncomeMonthScenarioSlice] = {}

    def observe_income_transition(
        self,
        *,
        state: IncomeActionState,
        scenario_slice: IncomeMonthScenarioSlice,
    ) -> None:
        if not isinstance(state, IncomeActionState):
            raise TypeError("Collected state must be IncomeActionState.")
        if not isinstance(scenario_slice, IncomeMonthScenarioSlice):
            raise TypeError(
                "Collected scenario_slice must be IncomeMonthScenarioSlice."
            )
        if state.step != scenario_slice.current_step:
            raise ValueError("Collected Income state/slice steps do not match.")
        if state.n_paths != scenario_slice.n_paths:
            raise ValueError("Collected Income state/slice shapes do not match.")
        if state.step in self._states_by_step:
            raise ValueError(
                f"Income transition step {state.step} was collected twice."
            )
        self._states_by_step[state.step] = state
        self._slices_by_step[state.step] = scenario_slice

    @property
    def states_by_step(self) -> Mapping[int, IncomeActionState]:
        return MappingProxyType(dict(self._states_by_step))

    @property
    def slices_by_step(self) -> Mapping[int, IncomeMonthScenarioSlice]:
        return MappingProxyType(dict(self._slices_by_step))


def _settle_fee_subledger_arrays(
    account_value: object,
    fee_product_accrued: object,
    fee_lip_accrued: object,
) -> tuple[Array, Array, Array]:
    """Pure fee settlement shared by projector and Bellman transitions."""
    available = np.maximum(np.asarray(account_value, dtype=float), 0.0)
    product_due = np.maximum(np.asarray(fee_product_accrued, dtype=float), 0.0)
    lip_due = np.maximum(np.asarray(fee_lip_accrued, dtype=float), 0.0)
    if available.shape != product_due.shape or available.shape != lip_due.shape:
        raise ValueError("Fee-subledger arrays must share one path shape.")
    outstanding = product_due + lip_due
    collected = np.minimum(available, outstanding)
    scale = np.divide(
        collected,
        outstanding,
        out=np.zeros_like(available),
        where=outstanding > 0.0,
    )
    return product_due * scale, lip_due * scale, available - collected


def _income_mva_amount(gross: object, mva_factor: object) -> Array:
    """MVA retained from a generic-product gross Income withdrawal."""
    gross_array = np.maximum(np.asarray(gross, dtype=float), 0.0)
    factor = np.asarray(mva_factor, dtype=float)
    if gross_array.shape != factor.shape:
        raise ValueError("Income MVA arrays must share one path shape.")
    return np.clip(gross_array * factor, 0.0, gross_array)


def _income_partial_action_values(
    account_value: object,
    iv_frame: object,
    locked_annual_income: object,
    gross_deduction: object,
    mva_factor: object,
) -> tuple[Array, Array, Array, Array, Array]:
    """Pure generic-product Partial-Withdrawal formulas.

    Returns post-action Account Value, IV frame, locked annual income, cash
    received and MVA retained.  The caller is responsible for enforcing the
    AUD 100 minimum and AUD 2,000 residual gates.
    """
    account = np.maximum(np.asarray(account_value, dtype=float), 0.0)
    frame = np.maximum(np.asarray(iv_frame, dtype=float), 0.0)
    income = np.maximum(np.asarray(locked_annual_income, dtype=float), 0.0)
    gross = np.maximum(np.asarray(gross_deduction, dtype=float), 0.0)
    if not (
        account.shape == frame.shape == income.shape == gross.shape
        == np.asarray(mva_factor).shape
    ):
        raise ValueError("Income Partial-Withdrawal arrays must share one shape.")
    gross = np.minimum(gross, account)
    mva = _income_mva_amount(gross, mva_factor)
    cash = gross - mva
    post_account = account - gross
    ratio = np.divide(
        post_account,
        np.maximum(account, 1.0e-300),
        out=np.ones_like(account),
        where=account > 0.0,
    )
    post_frame = frame * ratio
    post_income = income * np.clip(1.0 - np.divide(
        gross,
        np.maximum(account, 1.0e-300),
        out=np.zeros_like(account),
        where=account > 0.0,
    ), 0.0, 1.0)
    return post_account, post_frame, post_income, cash, mva


def _income_action_context_from_values(
    *,
    state: IncomeActionState,
    product: IndexLinkedLifetimeIncomeProduct,
    step: int,
    duration_years: float,
    terminal: bool,
    mva_factor: Array,
    annuity_factor: Array,
    short_rate: Array,
    zero_rate_5y: Array,
    heston_variance: Array,
) -> IncomeActionDecisionContext:
    """Build the public observable context from a complete private state."""
    n_paths = state.n_paths
    for name, value in (
        ("mva_factor", mva_factor),
        ("annuity_factor", annuity_factor),
        ("short_rate", short_rate),
        ("zero_rate_5y", zero_rate_5y),
        ("heston_variance", heston_variance),
    ):
        if np.asarray(value).shape != (n_paths,):
            raise ValueError(f"Income-action {name} must have one value per path.")

    _, _, post_fee_account = _settle_fee_subledger_arrays(
        state.account_value,
        state.fee_product_accrued,
        state.fee_lip_accrued,
    )
    surrender_mva = _income_mva_amount(post_fee_account, mva_factor)
    surrender_value = post_fee_account - surrender_mva
    guarantee_pv = np.maximum(
        state.locked_annual_income * np.asarray(annuity_factor, dtype=float),
        0.0,
    )
    guarantee_ratio = np.divide(
        guarantee_pv,
        np.maximum(surrender_value, 1.0e-300),
        out=np.full(n_paths, np.exp(2.0)),
        where=surrender_value > 1.0e-12,
    )
    log_moneyness = np.log(np.maximum(guarantee_ratio, 1.0e-300))
    max_partial = np.maximum(
        state.account_value - product.withdrawals.min_residual_value,
        0.0,
    )
    income_state = (
        (state.phase == Phase.INCOME.value)
        & (state.inforce_weight > 0.0)
    )
    partial_eligible = (
        income_state
        & ~bool(terminal)
        & (max_partial >= product.withdrawals.min_withdrawal)
    )
    materiality = 1.0e-12 * state.gross_premium
    positive_guarantee = income_state & (guarantee_pv > materiality)
    zero_exit_with_guarantee = (
        (surrender_value <= materiality) & positive_guarantee
    )
    full_eligible = (
        income_state
        & ~bool(terminal)
        & ~state.just_elected
        & (surrender_value > materiality)
        & ~zero_exit_with_guarantee
    )
    return IncomeActionDecisionContext(
        step=int(step),
        phase=state.phase,
        inforce_weight=state.inforce_weight,
        partial_withdrawal_eligible=partial_eligible,
        full_withdrawal_eligible=full_eligible,
        max_partial_gross_amount=max_partial,
        account_value=state.account_value,
        locked_annual_income=state.locked_annual_income,
        guarantee_pv=guarantee_pv,
        guarantee_log_moneyness=log_moneyness,
        mva_factor=mva_factor,
        surrender_value=surrender_value,
        short_rate=short_rate,
        zero_rate_5y=zero_rate_5y,
        heston_variance=heston_variance,
        duration_years=float(duration_years),
        mva_remaining_years=max(
            product.withdrawals.mva_period_years - float(duration_years), 0.0
        ),
        attained_age=state.attained_age,
        time_to_forced_election=state.time_to_forced_election,
        primary_alive=state.primary_alive,
        spouse_alive=state.spouse_alive,
        announced_cap=state.announced_cap,
        previous_reference_return=state.previous_reference_return,
        previous_credited_return=state.previous_credited_return,
        performance_gap=state.performance_gap,
        just_elected=state.just_elected,
    )


def build_income_action_decision_context(
    state: IncomeActionState,
    product: IndexLinkedLifetimeIncomeProduct,
    scenario_slice: IncomeMonthScenarioSlice,
    *,
    terminal: bool = False,
) -> IncomeActionDecisionContext:
    """Return the safe policy context at ``state`` from a training slice."""
    if not isinstance(state, IncomeActionState):
        raise TypeError("state must be IncomeActionState.")
    if not isinstance(scenario_slice, IncomeMonthScenarioSlice):
        raise TypeError("scenario_slice must be IncomeMonthScenarioSlice.")
    if state.step != scenario_slice.current_step:
        raise ValueError("State and Income-month slice steps do not match.")
    if state.n_paths != scenario_slice.n_paths:
        raise ValueError("State and Income-month slice path shapes do not match.")
    return _income_action_context_from_values(
        state=state,
        product=product,
        step=state.step,
        duration_years=scenario_slice.current_duration_years,
        terminal=terminal,
        mva_factor=scenario_slice.current_mva_factor,
        annuity_factor=scenario_slice.current_annuity_factor,
        short_rate=scenario_slice.current_short_rate,
        zero_rate_5y=scenario_slice.current_zero_rate_5y,
        heston_variance=scenario_slice.current_heston_variance,
    )


def apply_income_action(
    state: IncomeActionState,
    decision: IncomeActionDecision,
    product: IndexLinkedLifetimeIncomeProduct,
    scenario_slice: IncomeMonthScenarioSlice,
    *,
    terminal: bool = False,
) -> IncomeActionTransition:
    """Apply one CONTINUE/PARTIAL/FULL action without advancing the market.

    PARTIAL uses the same gross-deduction, MVA and proportional locked-income
    reduction as the monthly projector.  FULL first settles both accrued fee
    ledgers, then applies MVA, pays the surrender value and terminates both the
    contract and its income guarantee.  No action is admissible in Growth or
    on the terminal projection point.
    """
    if not isinstance(decision, IncomeActionDecision):
        raise TypeError("decision must be IncomeActionDecision.")
    context = build_income_action_decision_context(
        state, product, scenario_slice, terminal=terminal
    )
    if decision.n_paths != state.n_paths:
        raise ValueError("Decision and Income-action state shapes do not match.")

    action_type = np.asarray(decision.action_type)
    requested_partial = (
        action_type == IncomeActionType.PARTIAL_WITHDRAWAL.value
    )
    requested_full = action_type == IncomeActionType.FULL_WITHDRAWAL.value
    gross_request = (
        decision.partial_fraction_of_max
        * context.max_partial_gross_amount
    )
    # Product convention: a requested gross amount below AUD 100 is CONTINUE.
    partial = requested_partial & (
        gross_request >= product.withdrawals.min_withdrawal
    )
    if np.any(partial & ~context.partial_withdrawal_eligible):
        raise ValueError(
            "PARTIAL_WITHDRAWAL was selected on an ineligible Income path."
        )
    if np.any(requested_full & ~context.full_withdrawal_eligible):
        raise ValueError(
            "FULL_WITHDRAWAL was selected on an ineligible Income path."
        )
    full = requested_full
    gross = np.where(partial, gross_request, 0.0)

    (
        partial_account,
        partial_frame,
        partial_income,
        partial_cash,
        partial_mva,
    ) = _income_partial_action_values(
        state.account_value,
        state.iv_frame,
        state.locked_annual_income,
        gross,
        scenario_slice.current_mva_factor,
    )

    fee_product, fee_lip, full_post_fee_account = (
        _settle_fee_subledger_arrays(
            state.account_value,
            state.fee_product_accrued,
            state.fee_lip_accrued,
        )
    )
    full_mva = _income_mva_amount(
        full_post_fee_account, scenario_slice.current_mva_factor
    )
    full_cash = full_post_fee_account - full_mva

    account = np.where(partial, partial_account, state.account_value)
    frame = np.where(partial, partial_frame, state.iv_frame)
    income = np.where(partial, partial_income, state.locked_annual_income)
    account = np.where(full, 0.0, account)
    frame = np.where(full, 0.0, frame)
    income = np.where(full, 0.0, income)
    phase = np.where(
        full, Phase.TERMINATED.value, state.phase
    ).astype(np.int8)
    inforce = np.where(full, 0.0, state.inforce_weight)
    fee_product_after = np.where(full, 0.0, state.fee_product_accrued)
    fee_lip_after = np.where(full, 0.0, state.fee_lip_accrued)

    post_state = replace(
        state,
        account_value=account,
        iv_frame=frame,
        locked_annual_income=income,
        phase=phase,
        inforce_weight=inforce,
        fee_product_accrued=fee_product_after,
        fee_lip_accrued=fee_lip_after,
        joint_income_cover=np.where(
            full, False, state.joint_income_cover
        ),
        just_elected=np.where(full, False, state.just_elected),
    )
    executed_action = np.full(
        state.n_paths, IncomeActionType.CONTINUE.value, dtype="<U18"
    )
    executed_fraction = np.zeros(state.n_paths)
    executed_action[partial] = IncomeActionType.PARTIAL_WITHDRAWAL.value
    executed_fraction[partial] = decision.partial_fraction_of_max[partial]
    executed_action[full] = IncomeActionType.FULL_WITHDRAWAL.value
    executed = IncomeActionDecision(
        action_type=executed_action,
        partial_fraction_of_max=executed_fraction,
    )
    weight = state.inforce_weight
    return IncomeActionTransition(
        executed_decision=executed,
        post_action_state=post_state,
        gross_partial_deduction=gross,
        partial_withdrawal_cashflow=weight * np.where(
            partial, partial_cash, 0.0
        ),
        surrender_benefit_cashflow=weight * np.where(full, full_cash, 0.0),
        fees_product_cashflow=weight * np.where(full, fee_product, 0.0),
        fees_lip_cashflow=weight * np.where(full, fee_lip, 0.0),
        mva_retained_cashflow=weight * (
            np.where(partial, partial_mva, 0.0)
            + np.where(full, full_mva, 0.0)
        ),
    )


def advance_income_month(
    post_action_state: IncomeActionState,
    product: IndexLinkedLifetimeIncomeProduct,
    policy: PolicySpec,
    scenario_slice: IncomeMonthScenarioSlice,
) -> IncomeMonthTransition:
    """Advance a generic-product post-action state to the next action point.

    The event order matches the Policyholder-relevant projector order:
    market/Anniversary credit, fee accrual and Anniversary posting, terminating
    mortality/death benefit, Anniversary DVA restart, and mandatory monthly
    Fixed Income.  Mortality and market generation themselves are deliberately
    outside this pure kernel and arrive through ``scenario_slice`` so every
    counterfactual action uses common random numbers.
    """
    if not isinstance(post_action_state, IncomeActionState):
        raise TypeError("post_action_state must be IncomeActionState.")
    if not isinstance(scenario_slice, IncomeMonthScenarioSlice):
        raise TypeError("scenario_slice must be IncomeMonthScenarioSlice.")
    if policy.age_pension_plus:
        raise NotImplementedError(
            "Optimal monthly Income actions do not support Age Pension Plus."
        )
    if post_action_state.step != scenario_slice.current_step:
        raise ValueError("Post-action state and Income-month step do not match.")
    if post_action_state.n_paths != scenario_slice.n_paths:
        raise ValueError("Post-action state and Income-month shapes do not match.")
    active_growth = (
        (post_action_state.phase == Phase.GROWTH.value)
        & (post_action_state.inforce_weight > 0.0)
    )
    if np.any(active_growth):
        raise ValueError("advance_income_month accepts Income/terminated states only.")

    state = post_action_state
    active = state.phase < Phase.TERMINATED.value
    frame_start = np.maximum(state.iv_frame, 0.0)
    frame = frame_start.copy()
    fee_product = state.fee_product_accrued + np.where(
        active,
        frame_start * product.fees.product_fee
        * scenario_slice.fee_year_fraction,
        0.0,
    )
    fee_lip = state.fee_lip_accrued + np.where(
        active,
        frame_start * product.fees.lifetime_income_premium
        * scenario_slice.fee_year_fraction,
        0.0,
    )

    if scenario_slice.is_anniversary:
        frame = np.where(
            active,
            frame * (1.0 + scenario_slice.anniversary_credit_rate),
            0.0,
        )
        account = frame.copy()
        posted_product, posted_lip, post_fee_account = (
            _settle_fee_subledger_arrays(account, fee_product, fee_lip)
        )
        ratio = np.divide(
            post_fee_account,
            np.maximum(account, 1.0e-300),
            out=np.ones(state.n_paths),
            where=account > 0.0,
        )
        frame = frame * ratio
        account = post_fee_account
        fee_product = np.zeros(state.n_paths)
        fee_lip = np.zeros(state.n_paths)
        fee_product_cashflow = state.inforce_weight * posted_product
        fee_lip_cashflow = state.inforce_weight * posted_lip
    else:
        account = frame * scenario_slice.next_dva_factor
        fee_product_cashflow = np.zeros(state.n_paths)
        fee_lip_cashflow = np.zeros(state.n_paths)

    death_probability = np.where(
        active, scenario_slice.terminating_death_probability, 0.0
    )
    death_fee_product, death_fee_lip, death_post_fee_account = (
        _settle_fee_subledger_arrays(account, fee_product, fee_lip)
    )
    death_weight = state.inforce_weight * death_probability
    death_benefit_cashflow = death_weight * death_post_fee_account
    fee_product_cashflow = (
        fee_product_cashflow + death_weight * death_fee_product
    )
    fee_lip_cashflow = fee_lip_cashflow + death_weight * death_fee_lip

    certain_death = death_probability >= 1.0 - 1.0e-15
    phase = np.where(
        certain_death, Phase.TERMINATED.value, state.phase
    ).astype(np.int8)
    frame = np.where(certain_death, 0.0, frame)
    account = np.where(certain_death, 0.0, account)
    locked_income = np.where(
        certain_death, 0.0, state.locked_annual_income
    )
    fee_product = np.where(certain_death, 0.0, fee_product)
    fee_lip = np.where(certain_death, 0.0, fee_lip)
    inforce = state.inforce_weight * (1.0 - death_probability)

    # At an Anniversary the new DVA/hedge year starts after fee and mortality
    # settlement.  At a non-Anniversary this factor was already used above.
    if scenario_slice.is_anniversary:
        account = frame * scenario_slice.next_dva_factor

    pay = np.where(
        phase == Phase.INCOME.value,
        locked_income / STEPS_PER_YEAR,
        0.0,
    )
    from_account = np.minimum(pay, account)
    guarantee_claim = pay - from_account
    ratio = np.divide(
        account - from_account,
        np.maximum(account, 1.0e-300),
        out=np.ones(state.n_paths),
        where=account > 0.0,
    )
    account = account - from_account
    frame = frame * ratio
    income_cashflow = inforce * pay
    guarantee_claim_cashflow = inforce * guarantee_claim
    exhausted = account <= 1.0e-12
    fee_product = np.where(exhausted, 0.0, fee_product)
    fee_lip = np.where(exhausted, 0.0, fee_lip)

    terminal_closeout_cashflow = np.zeros(state.n_paths)
    if scenario_slice.terminal_next:
        # A truncated horizon is a valuation closeout, not a death or a
        # voluntary FULL action.  Match the canonical projector: settle the
        # survivor fee subledger, pay the remaining Account Value without MVA,
        # and terminate contract and guarantee at the same grid timestamp.
        terminal_mask = phase < Phase.TERMINATED.value
        (
            terminal_fee_product,
            terminal_fee_lip,
            terminal_post_fee_account,
        ) = _settle_fee_subledger_arrays(account, fee_product, fee_lip)
        fee_product_cashflow = fee_product_cashflow + inforce * np.where(
            terminal_mask, terminal_fee_product, 0.0
        )
        fee_lip_cashflow = fee_lip_cashflow + inforce * np.where(
            terminal_mask, terminal_fee_lip, 0.0
        )
        terminal_closeout_cashflow = inforce * np.where(
            terminal_mask, terminal_post_fee_account, 0.0
        )
        account = np.where(terminal_mask, 0.0, account)
        frame = np.where(terminal_mask, 0.0, frame)
        locked_income = np.where(terminal_mask, 0.0, locked_income)
        fee_product = np.where(terminal_mask, 0.0, fee_product)
        fee_lip = np.where(terminal_mask, 0.0, fee_lip)
        phase = np.where(
            terminal_mask, Phase.TERMINATED.value, phase
        ).astype(np.int8)
        inforce = np.where(terminal_mask, 0.0, inforce)

    if scenario_slice.is_anniversary:
        previous_reference_return = scenario_slice.next_reference_return
        previous_credited_return = scenario_slice.next_credited_return
        performance_gap = scenario_slice.next_performance_gap
        announced_cap = scenario_slice.next_announced_cap
    else:
        previous_reference_return = state.previous_reference_return
        previous_credited_return = state.previous_credited_return
        performance_gap = state.performance_gap
        announced_cap = state.announced_cap

    next_state = IncomeActionState(
        step=scenario_slice.next_step,
        path_index=state.path_index,
        gross_premium=state.gross_premium,
        attained_age=(
            state.attained_age
            + scenario_slice.next_duration_years
            - scenario_slice.current_duration_years
        ),
        time_to_forced_election=np.maximum(
            state.time_to_forced_election
            - (
                scenario_slice.next_duration_years
                - scenario_slice.current_duration_years
            ),
            0.0,
        ),
        account_value=account,
        iv_frame=frame,
        locked_annual_income=locked_income,
        phase=phase,
        inforce_weight=inforce,
        fee_product_accrued=fee_product,
        fee_lip_accrued=fee_lip,
        primary_alive=scenario_slice.next_primary_alive,
        spouse_alive=scenario_slice.next_spouse_alive,
        joint_income_cover=np.where(
            phase == Phase.TERMINATED.value,
            False,
            scenario_slice.next_joint_income_cover,
        ),
        joint_survival_primary=scenario_slice.next_joint_survival_primary,
        joint_survival_spouse=scenario_slice.next_joint_survival_spouse,
        previous_reference_return=previous_reference_return,
        previous_credited_return=previous_credited_return,
        performance_gap=performance_gap,
        announced_cap=announced_cap,
        just_elected=np.zeros(state.n_paths, dtype=bool),
    )
    next_context = _income_action_context_from_values(
        state=next_state,
        product=product,
        step=scenario_slice.next_step,
        duration_years=scenario_slice.next_duration_years,
        terminal=scenario_slice.terminal_next,
        mva_factor=scenario_slice.next_mva_factor,
        annuity_factor=scenario_slice.next_annuity_factor,
        short_rate=scenario_slice.next_short_rate,
        zero_rate_5y=scenario_slice.next_zero_rate_5y,
        heston_variance=scenario_slice.next_heston_variance,
    )
    return IncomeMonthTransition(
        next_state=next_state,
        next_context=next_context,
        income_cashflow=income_cashflow,
        death_benefit_cashflow=death_benefit_cashflow,
        terminal_closeout_cashflow=terminal_closeout_cashflow,
        guarantee_claim_cashflow=guarantee_claim_cashflow,
        fees_product_cashflow=fee_product_cashflow,
        fees_lip_cashflow=fee_lip_cashflow,
        discount_ratio=scenario_slice.discount_ratio,
    )


@dataclass(frozen=True)
class SurrenderDecisionContext:
    """Observable state at the contractual Full-Withdrawal event point.

    Context-aware research policies receive this object instead of the full
    :class:`~agile_engine.esg.ScenarioSet`.  Every path array is defensively
    copied and marked read-only so a policy cannot mutate projector state.  In
    particular, the context contains no future market paths, discount factors,
    insurer hedge P&L or backing-asset information.

    ``announced_cap`` is the cap for the crediting year which starts at this
    event point.  At an Anniversary, ``previous_*`` describes the crediting
    year which has just ended under its old cap.
    """

    step: int
    time: float
    is_anniversary: bool
    policy_year: int
    duration_years: float
    phase: NDArray[np.int8]
    account_value: Array
    surrender_value: Array
    locked_annual_income: Array
    guarantee_pv: Array
    guarantee_moneyness: Array
    guarantee_log_moneyness: Array
    short_rate: Array
    zero_rate_5y: Array
    heston_variance: Array
    announced_cap: Array
    previous_reference_return: Array
    previous_credited_return: Array
    performance_gap: Array
    inforce_weight: Array
    just_elected: NDArray[np.bool_]
    full_withdrawal_eligible: NDArray[np.bool_]
    mva_factor: Optional[Array] = None
    attained_age: Optional[Array] = None
    primary_alive: Optional[NDArray[np.bool_]] = None
    spouse_alive: Optional[NDArray[np.bool_]] = None

    def __post_init__(self) -> None:
        if isinstance(self.step, bool) or int(self.step) != self.step or self.step < 0:
            raise ValueError("Surrender decision step must be a non-negative integer.")
        if (
            isinstance(self.policy_year, bool)
            or int(self.policy_year) != self.policy_year
            or self.policy_year < 0
        ):
            raise ValueError("Surrender policy year must be a non-negative integer.")
        if not np.isfinite(self.time) or not np.isfinite(self.duration_years):
            raise ValueError("Surrender decision time and duration must be finite.")
        if not isinstance(self.is_anniversary, (bool, np.bool_)):
            raise ValueError("is_anniversary must be boolean.")

        path_shape = np.asarray(self.account_value).shape
        if len(path_shape) != 1:
            raise ValueError("Surrender context account_value must be one-dimensional.")
        optional_defaults = {
            "mva_factor": np.zeros(path_shape),
            "attained_age": np.full(path_shape, float(self.duration_years)),
            "primary_alive": np.ones(path_shape, dtype=bool),
            "spouse_alive": np.zeros(path_shape, dtype=bool),
        }
        for name, default in optional_defaults.items():
            if getattr(self, name) is None:
                object.__setattr__(self, name, default)

        array_dtypes: dict[str, object] = {
            "phase": np.int8,
            "account_value": float,
            "surrender_value": float,
            "locked_annual_income": float,
            "guarantee_pv": float,
            "guarantee_moneyness": float,
            "guarantee_log_moneyness": float,
            "short_rate": float,
            "zero_rate_5y": float,
            "heston_variance": float,
            "announced_cap": float,
            "previous_reference_return": float,
            "previous_credited_return": float,
            "performance_gap": float,
            "inforce_weight": float,
            "just_elected": bool,
            "full_withdrawal_eligible": bool,
            "mva_factor": float,
            "attained_age": float,
            "primary_alive": bool,
            "spouse_alive": bool,
        }
        expected_shape: Optional[tuple[int, ...]] = None
        for name, dtype in array_dtypes.items():
            value = np.array(getattr(self, name), dtype=dtype, copy=True)
            if value.ndim != 1:
                raise ValueError(f"Surrender context {name} must be one-dimensional.")
            if expected_shape is None:
                expected_shape = value.shape
            elif value.shape != expected_shape:
                raise ValueError("Surrender context arrays must share one path shape.")
            if dtype not in (bool, np.int8):
                cap_with_uncapped_sentinel = name == "announced_cap"
                valid = (
                    np.all(~np.isnan(value) & (value >= 0.0))
                    if cap_with_uncapped_sentinel
                    else np.all(np.isfinite(value))
                )
                if not valid:
                    raise ValueError(f"Surrender context {name} is invalid.")
            value.setflags(write=False)
            object.__setattr__(self, name, value)

    @property
    def n_paths(self) -> int:
        """Number of scenario paths represented by the context."""
        return int(self.account_value.shape[0])


@dataclass(frozen=True)
class IncomeElectionDecisionContext:
    """Read-only state at an admissible Income-Election Anniversary.

    The context is assembled after the old crediting-year return, regular fee
    posting and the mortality decrement for the interval just ended, and
    before the next crediting period is announced.  It deliberately contains
    no future market path, future discount factor, hedge result or backing-
    asset information.  A combined research policy may therefore implement
    ``start_income_mask(*, context=...)`` without receiving the full scenario
    set.

    ``forced_election`` contains contractual product gates only.  In
    particular, a Behaviour assumption whose annual take-up probability is
    one is still a behavioural election and is not re-labelled as forced.
    """

    step: int
    time: float
    is_anniversary: bool
    policy_year: int
    duration_years: float
    phase: NDArray[np.int8]
    account_value: Array
    prospective_locked_annual_income: Array
    prospective_income_rate: Array
    guarantee_pv: Array
    guarantee_moneyness: Array
    guarantee_log_moneyness: Array
    short_rate: Array
    zero_rate_5y: Array
    heston_variance: Array
    mva_factor: Array
    mva_remaining_years: float
    attained_age: Array
    time_to_forced_election: Array
    primary_alive: NDArray[np.bool_]
    spouse_alive: NDArray[np.bool_]
    previous_cap: Array
    previous_reference_return: Array
    previous_credited_return: Array
    performance_gap: Array
    inforce_weight: Array
    voluntary_election_eligible: NDArray[np.bool_]
    forced_election: NDArray[np.bool_]

    def __post_init__(self) -> None:
        if isinstance(self.step, bool) or int(self.step) != self.step or self.step < 0:
            raise ValueError(
                "Income-Election decision step must be a non-negative integer."
            )
        if (
            isinstance(self.policy_year, bool)
            or int(self.policy_year) != self.policy_year
            or self.policy_year < 0
        ):
            raise ValueError(
                "Income-Election policy year must be a non-negative integer."
            )
        if not np.isfinite(self.time) or not np.isfinite(self.duration_years):
            raise ValueError(
                "Income-Election decision time and duration must be finite."
            )
        if (
            not np.isfinite(self.mva_remaining_years)
            or self.mva_remaining_years < 0.0
        ):
            raise ValueError(
                "Income-Election mva_remaining_years must be finite/non-negative."
            )
        if not isinstance(self.is_anniversary, (bool, np.bool_)):
            raise ValueError("is_anniversary must be boolean.")

        array_dtypes: dict[str, object] = {
            "phase": np.int8,
            "account_value": float,
            "prospective_locked_annual_income": float,
            "prospective_income_rate": float,
            "guarantee_pv": float,
            "guarantee_moneyness": float,
            "guarantee_log_moneyness": float,
            "short_rate": float,
            "zero_rate_5y": float,
            "heston_variance": float,
            "mva_factor": float,
            "attained_age": float,
            "time_to_forced_election": float,
            "primary_alive": bool,
            "spouse_alive": bool,
            "previous_cap": float,
            "previous_reference_return": float,
            "previous_credited_return": float,
            "performance_gap": float,
            "inforce_weight": float,
            "voluntary_election_eligible": bool,
            "forced_election": bool,
        }
        expected_shape: Optional[tuple[int, ...]] = None
        for name, dtype in array_dtypes.items():
            value = np.array(getattr(self, name), dtype=dtype, copy=True)
            if value.ndim != 1:
                raise ValueError(
                    f"Income-Election context {name} must be one-dimensional."
                )
            if expected_shape is None:
                expected_shape = value.shape
            elif value.shape != expected_shape:
                raise ValueError(
                    "Income-Election context arrays must share one path shape."
                )
            if dtype not in (bool, np.int8):
                valid = (
                    np.all(~np.isnan(value) & (value >= 0.0))
                    if name == "previous_cap"
                    else np.all(np.isfinite(value))
                )
                if not valid:
                    raise ValueError(
                        f"Income-Election context {name} is invalid."
                    )
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        for name in (
            "mva_factor",
            "attained_age",
            "time_to_forced_election",
        ):
            if np.any(getattr(self, name) < 0.0):
                raise ValueError(
                    f"Income-Election context {name} must be non-negative."
                )
        if np.any(self.mva_factor > 1.0 + 1.0e-12):
            raise ValueError("Income-Election mva_factor must not exceed one.")

    @property
    def n_paths(self) -> int:
        """Number of scenario paths represented by the context."""
        return int(self.account_value.shape[0])


@dataclass(frozen=True)
class CreditingCapDecisionContext:
    """Observable portfolio building block immediately before a new cap.

    The callback is an observer, not a product-control mechanism.  It records
    the state after old-cap crediting, fee posting, mortality and Income
    Election, but before the new cap starts the hedge/DVA period.  Aggregating
    these per-policy contexts with ``contract_weight`` gives the leader state
    without allowing the current cap to leak into its own decision.
    """

    step: int
    time: float
    policy_year: int
    phase: NDArray[np.int8]
    account_value: Array
    surrender_value: Array
    locked_annual_income: Array
    guarantee_pv: Array
    guarantee_moneyness: Array
    guarantee_log_moneyness: Array
    short_rate: Array
    zero_rate_5y: Array
    heston_variance: Array
    previous_cap: Array
    previous_reference_return: Array
    previous_credited_return: Array
    performance_gap: Array
    inforce_weight: Array
    just_elected: NDArray[np.bool_]

    def __post_init__(self) -> None:
        if isinstance(self.step, bool) or int(self.step) != self.step or self.step < 0:
            raise ValueError("Crediting-cap decision step must be non-negative.")
        if (
            isinstance(self.policy_year, bool)
            or int(self.policy_year) != self.policy_year
            or self.policy_year < 0
        ):
            raise ValueError("Crediting-cap policy year must be non-negative.")
        if not np.isfinite(self.time):
            raise ValueError("Crediting-cap decision time must be finite.")
        array_dtypes: dict[str, object] = {
            "phase": np.int8,
            "account_value": float,
            "surrender_value": float,
            "locked_annual_income": float,
            "guarantee_pv": float,
            "guarantee_moneyness": float,
            "guarantee_log_moneyness": float,
            "short_rate": float,
            "zero_rate_5y": float,
            "heston_variance": float,
            "previous_cap": float,
            "previous_reference_return": float,
            "previous_credited_return": float,
            "performance_gap": float,
            "inforce_weight": float,
            "just_elected": bool,
        }
        expected_shape: Optional[tuple[int, ...]] = None
        for name, dtype in array_dtypes.items():
            value = np.array(getattr(self, name), dtype=dtype, copy=True)
            if value.ndim != 1:
                raise ValueError(f"Crediting-cap context {name} must be one-dimensional.")
            if expected_shape is None:
                expected_shape = value.shape
            elif value.shape != expected_shape:
                raise ValueError("Crediting-cap context arrays must share one shape.")
            if dtype not in (bool, np.int8):
                cap_with_uncapped_sentinel = name == "previous_cap"
                valid = (
                    np.all(~np.isnan(value) & (value >= 0.0))
                    if cap_with_uncapped_sentinel
                    else np.all(np.isfinite(value))
                )
                if not valid:
                    raise ValueError(f"Crediting-cap context {name} is invalid.")
            value.setflags(write=False)
            object.__setattr__(self, name, value)

    @property
    def n_paths(self) -> int:
        return int(self.account_value.shape[0])


def _context_aware_surrender_policy(policy: object) -> bool:
    """Return whether a hook explicitly opts into the safe context API."""
    method = getattr(policy, "surrender_mask", None)
    if method is None:
        raise TypeError("surrender_policy must provide a surrender_mask method.")
    try:
        return "context" in signature(method).parameters
    except (TypeError, ValueError):
        # Some extension callables do not expose a Python signature.  Preserve
        # their historical keyword API rather than guessing that they support
        # the new context contract.
        return False


def _fractional_year_to_date(value: float) -> date:
    """Deterministic date convention for legacy fractional-year inputs.

    Model points currently provide ``commencement_year`` rather than an ISO
    date.  The fraction is mapped to the nearest day of that calendar year;
    this makes ACT/365F accrual reproducible until an explicit commencement
    date is added to the input schema.
    """
    if not np.isfinite(value):
        raise ValueError("commencement_year must be finite.")
    year = int(np.floor(value))
    days = 366 if isleap(year) else 365
    offset = int(round((float(value) - year) * days))
    offset = min(max(offset, 0), days - 1)
    return date(year, 1, 1) + timedelta(days=offset)


def _add_calendar_months(anchor: date, months: int) -> date:
    """Add whole calendar months, clipping the day at month end."""
    if isinstance(months, bool) or not isinstance(months, (int, np.integer)):
        raise ValueError("months must be an integer.")
    serial = anchor.year * 12 + (anchor.month - 1) + int(months)
    year, month0 = divmod(serial, 12)
    month = month0 + 1
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    month_end_day = (next_month - timedelta(days=1)).day
    return date(year, month, min(anchor.day, month_end_day))


def _completed_date_anniversaries(as_of: date, base: date) -> int:
    """Number of complete annual base-date anniversaries at ``as_of``."""
    if as_of < base:
        return 0
    years = as_of.year - base.year
    if (as_of.month, as_of.day) < (base.month, base.day):
        years -= 1
    return max(years, 0)


def _average_expense_inflation_factor(
        interval_start: date, interval_end: date,
        annual_rate: float, base_date: date) -> float:
    """Daily-weighted factor when an annual expense date crosses a month."""
    days = (interval_end - interval_start).days
    if days <= 0:
        raise ValueError("Expense interval must contain at least one day.")
    total = 0.0
    for day_offset in range(days):
        current = interval_start + timedelta(days=day_offset)
        years = _completed_date_anniversaries(current, base_date)
        total += (1.0 + annual_rate) ** years
    return total / days


# ---------------------------------------------------------------------------
# Configuration and result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProjectionConfig:
    dva_enabled: bool = True
    #: Absolute volatility quote add-on used to derive a non-negative hedge
    #: execution/basis cost at the start of each crediting period.  It is not
    #: added to customer DVA values and is not interpreted as a cash expense
    #: rate; see the ``hedge_costs`` cashflow.
    hedge_vol_spread: float = 0.0
    #: Purchase-price markup as a fraction of the fair option-package value.
    #: ``0.005`` means a quote of 100.5% of fair value, not 50bp of notional.
    option_fair_value_markup: float = 0.005
    #: Annual notional-cost proxy for the hedge-reference management-fee drag.
    #: It is an insurer cost only and never reduces customer Reference-Fund
    #: return or the contractual option payoff path.
    hedge_reference_management_fee: float = 0.003
    #: Annual hedge purchase-price method.  ``mc_conditional`` requires an
    #: exact path-aligned :class:`HedgePriceSurface` bound to the ScenarioSet;
    #: ``moment_matched_bs`` is the explicit legacy fallback.  The intra-year
    #: customer DVA mark remains moment matched under both choices.
    hedge_pricing_method: str = "moment_matched_bs"
    #: The standard strategy sells the cap call.  ``NOT_SOLD`` buys the
    #: uncapped positive-return call and retains its payoff above the cap.
    hedge_cap_leg_mode: HedgeCapLegMode = HedgeCapLegMode.SOLD
    #: record full state paths (IV, income and phase) for diagnostics.
    record_paths: bool = True
    #: maximum projection age of the life insured. The default reaches the
    #: mortality-table terminal age so lifetime-income tails are not truncated.
    max_age: float = 115.0
    #: Include insurer backing income and optional retained hedge gain in the
    #: backward-compatible aggregate ``crediting_margin`` cashflow.
    crediting_margin_enabled: bool = True
    #: independent, reproducible RNG seed for stochastic income take-up.
    take_up_seed: int = 97
    #: Independent, reproducible mortality seed used whenever separate
    #: pathwise Joint-Life states are required.  A standalone deterministic
    #: projection keeps the historical expected-decrement implementation
    #: unless ``force_pathwise_joint_life`` is enabled.
    mortality_seed: int = 193
    #: Force separate sampled Primary/Spouse life states for Joint-Life
    #: portfolios.  Portfolio behaviour-factor runs enable this for every arm
    #: so V00/V01/V10/V11 share the same mortality random numbers; the default
    #: preserves the expected-decrement treatment for standalone deterministic
    #: projections.
    force_pathwise_joint_life: bool = False
    #: Legacy four-equity-option switch.  The generic mixed reference fund is
    #: always valued with a joint-model moment-matched BS proxy and never with
    #: COS.  Portfolio valuation also sets this flag explicitly to ``False``.
    heston_cos: bool = False

    def __post_init__(self) -> None:
        numeric = np.asarray([
            self.hedge_vol_spread,
            self.option_fair_value_markup,
            self.hedge_reference_management_fee,
            self.max_age,
        ], dtype=float)
        if not np.all(np.isfinite(numeric)):
            raise ValueError("Projection numeric settings must be finite.")
        if self.hedge_vol_spread < 0.0:
            raise ValueError("hedge_vol_spread must be non-negative.")
        if self.option_fair_value_markup < 0.0:
            raise ValueError("option_fair_value_markup must be non-negative.")
        if not 0.0 <= self.hedge_reference_management_fee < 1.0:
            raise ValueError(
                "hedge_reference_management_fee must be in [0, 1)."
            )
        if self.max_age <= 0.0:
            raise ValueError("Projection max_age must be positive.")
        if self.hedge_pricing_method not in (
                "mc_conditional", "moment_matched_bs"):
            raise ValueError(
                "hedge_pricing_method must be 'mc_conditional' or "
                "'moment_matched_bs'."
            )
        try:
            object.__setattr__(
                self,
                "hedge_cap_leg_mode",
                HedgeCapLegMode(self.hedge_cap_leg_mode),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Unknown hedge_cap_leg_mode.") from exc
        for name in ("dva_enabled", "record_paths", "crediting_margin_enabled",
                     "force_pathwise_joint_life", "heston_cos"):
            if not isinstance(getattr(self, name), (bool, np.bool_)):
                raise ValueError(f"{name} must be boolean.")
        for name in ("take_up_seed", "mortality_seed"):
            value = getattr(self, name)
            if isinstance(value, bool) \
                    or not isinstance(value, (int, np.integer)) \
                    or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")


CASHFLOW_KEYS = (
    "premium", "income_paid", "guarantee_claims", "death_benefits",
    "surrender_benefits", "partial_withdrawals", "terminal_closeout",
    "fees_product", "fees_lip", "crediting_margin", "money_market_income",
    "hedge_gain", "mva_retained", "aps_retained", "hedge_costs",
    "hedge_option_fair_value_costs", "hedge_option_fair_value_bs_proxy",
    "hedge_option_markup_costs",
    "hedge_management_fee_costs", "hedge_execution_costs",
    "contract_financing_margin", "expenses",
)

PHASE_CASHFLOW_KEYS = (
    "policyholder_benefits_pre_election",
    "policyholder_benefits_post_election",
    "growth_fees",
    "growth_crediting_margin",
    "post_election_guarantee_claims",
)


@dataclass(frozen=True)
class SurrenderActionValueContext:
    """Read-only cashflow values at the Full-Withdrawal action boundary.

    ``decision_context`` is the exact customer-observable context passed to a
    context-aware ``surrender_policy`` at this event point.  The two cashflow
    mappings are an observer-only accounting surface:

    * ``post_cap_common_cashflows`` contains cashflows at the current grid
      point from the most recent cap-decision boundary through immediately
      before the Policyholder action.  At an Anniversary this excludes every
      old-cap, fee, mortality and Election cashflow which preceded the new-cap
      announcement.
    * ``full_withdrawal_post_action_cashflows`` contains the exact
      probability-weighted settlement and midpoint expense which would be
      booked if every currently eligible path chose ``FULL_WITHDRAWAL``.

    It contains no ScenarioSet, future market path, backing-asset or hedge-P&L
    surface.  All arrays and both mappings are defensively copied and made
    read-only.  This context is passed only to ``surrender_decision_observer``;
    it is never passed to the Policyholder policy.
    """

    decision_context: SurrenderDecisionContext
    post_cap_common_cashflows: Mapping[str, Array]
    full_withdrawal_post_action_cashflows: Mapping[str, Array]

    def __post_init__(self) -> None:
        if not isinstance(self.decision_context, SurrenderDecisionContext):
            raise TypeError(
                "decision_context must be an exact SurrenderDecisionContext."
            )

        for field_name in (
            "post_cap_common_cashflows",
            "full_withdrawal_post_action_cashflows",
        ):
            supplied = getattr(self, field_name)
            if set(supplied) != set(CASHFLOW_KEYS):
                raise ValueError(
                    f"{field_name} must contain exactly the canonical cashflow keys."
                )
            snapshot: dict[str, Array] = {}
            for key in CASHFLOW_KEYS:
                value = np.array(supplied[key], dtype=float, copy=True)
                if value.shape != (self.decision_context.n_paths,):
                    raise ValueError(
                        f"{field_name}[{key!r}] must have one value per path."
                    )
                if not np.all(np.isfinite(value)):
                    raise ValueError(
                        f"{field_name}[{key!r}] must contain finite values."
                    )
                value.setflags(write=False)
                snapshot[key] = value
            object.__setattr__(
                self, field_name, MappingProxyType(snapshot)
            )

    @property
    def n_paths(self) -> int:
        return self.decision_context.n_paths

    @property
    def step(self) -> int:
        return self.decision_context.step


@dataclass
class ProjectionResult:
    """Probability-weighted cashflows (n_paths, n_steps+1) and diagnostics.

    All cashflow entries at column ``k`` occur at time ``times[k]`` and are
    already weighted with the in-force probability of the path.
    Policyholder-facing flows are positive. Insurer income (fees, backing
    income, hedge gains and MVA retained) and insurer outgo (hedge/operating
    costs) are recorded in separate buckets; net-value formulas apply the
    appropriate sign. ``crediting_margin`` and ``hedge_costs`` are the
    backward-compatible P&L aggregates. Their component buckets are audit
    diagnostics and must not be added to insurer net value a second time.
    ``contract_financing_margin`` is a customer-contract identity diagnostic;
    it is not an additional insurer P&L cashflow.
    """

    times: Array
    scenarios: ScenarioSet
    cashflows: Dict[str, Array]
    inforce: Array                 # in-force weight after decrements at t
    lapse_events: Array            # probability mass exiting by full surrender
    iv_paths: Optional[Array]      # legacy alias storage for Account Value
    income_paths: Optional[Array]  # annual income in payment
    phase_paths: Optional[Array]
    survival_primary: Array        # deterministic survival of the life insured
    horizon_years: float
    ordinary_lapse_events: Optional[Array] = None
    performance_lapse_events: Optional[Array] = None
    ordinary_lapse_probabilities: Optional[Array] = None
    performance_lapse_probabilities: Optional[Array] = None
    total_lapse_probabilities: Optional[Array] = None
    eligible_growth_exposure: Optional[Array] = None
    income_take_up_probability: Optional[Array] = None
    income_election_events: Optional[Array] = None
    forced_income_election_events: Optional[Array] = None
    growth_exposure: Optional[Array] = None
    income_exposure: Optional[Array] = None
    phase_cashflows: Optional[Dict[str, Array]] = None
    post_cap_cashflows: Optional[Dict[str, Array]] = None
    post_cap_lapse_events: Optional[Array] = None
    post_surrender_cashflows: Optional[Dict[str, Array]] = None

    @property
    def account_value_paths(self) -> Optional[Array]:
        """Pathwise Account Value (canonical public product terminology)."""
        return self.iv_paths

    # ------------------------------------------------------------------ #

    def pv_by_component(self) -> Dict[str, float]:
        n = len(self.times)
        d = self.scenarios.discount[:, :n]
        return {k: float(np.mean(np.sum(cf * d, axis=1)))
                for k, cf in self.cashflows.items()}

    def pv_phase_by_component(self) -> Dict[str, float]:
        """PV of exact transaction-time Growth/Election phase ledgers."""
        if self.phase_cashflows is None:
            return {}
        n = len(self.times)
        d = self.scenarios.discount[:, :n]
        return {
            key: float(np.mean(np.sum(cashflow * d, axis=1)))
            for key, cashflow in self.phase_cashflows.items()
        }

    def pv_insurer_net(self) -> float:
        """PV of insurer net cashflow after claims and insurer costs."""
        pv = self.pv_by_component()
        return (pv["fees_product"] + pv["fees_lip"] + pv["crediting_margin"]
                + pv["mva_retained"] + pv["aps_retained"]
                - pv["guarantee_claims"] - pv["hedge_costs"] - pv["expenses"])

    def identity_gap(self) -> float:
        """Market-consistency check: under Q the premium must equal the PV of
        all contract-financed flows,

            P0 = PV(PH benefits) - PV(guarantee claims)
                 + PV(fees) + PV(contract financing margin)
                 + PV(MVA / APS retained).

        The identity is deliberately independent of the insurer's chosen
        backing and hedge execution.  Money-market income, actual hedge costs,
        retained excess gains and operating expenses are shareholder P&L and
        are therefore excluded here.

        Returns the relative gap (should be ~0 for risk-neutral scenarios up
        to Monte-Carlo and discretisation error).
        """
        pv = self.pv_by_component()
        ph = (pv["income_paid"] + pv["death_benefits"] + pv["surrender_benefits"]
              + pv["partial_withdrawals"] + pv["terminal_closeout"])
        financed = (
            ph - pv["guarantee_claims"]
            + pv["fees_product"] + pv["fees_lip"]
            + pv["contract_financing_margin"]
            + pv["mva_retained"] + pv["aps_retained"]
        )
        p0 = pv["premium"]
        return float((financed - p0) / p0)

    def expected_cashflow_profile(self) -> Dict[str, Array]:
        """E[D_t * CF_t] per period (time-0 present values per time bucket)."""
        d = self.scenarios.discount[:, :len(self.times)]
        return {k: np.mean(cf * d, axis=0) for k, cf in self.cashflows.items()}

    def annual_aggregate(self, key: str, discounted: bool = False) -> Array:
        """Mean cashflow aggregated to policy years.

        Bucket 0 contains the time-0 flows only (premium, acquisition costs,
        upfront crediting margin); bucket ``y >= 1`` contains the flows of
        policy year ``y``, i.e. grid steps ``12(y-1)+1 .. 12y`` (paid at times
        in ``(y-1, y]``). This aligns the buckets with the annual BEL / SCR
        patterns, which are measured at integer policy times: the reserve
        established at ``t = y-1`` unwinds against exactly the year-``y``
        cashflows (used by the profitability recursion).
        """
        cf = self.cashflows[key]
        if discounted:
            cf = cf * self.scenarios.discount[:, :cf.shape[1]]
        mean_cf = np.mean(cf, axis=0)
        n_steps = len(self.times) - 1
        n_years = int(np.ceil(n_steps / STEPS_PER_YEAR)) + 1
        out = np.zeros(n_years)
        out[0] = float(mean_cf[0])
        for y in range(1, n_years):
            lo = (y - 1) * STEPS_PER_YEAR + 1
            hi = min(y * STEPS_PER_YEAR, n_steps)
            out[y] = float(np.sum(mean_cf[lo:hi + 1]))
        return out


# ---------------------------------------------------------------------------
# Precomputed decrement tables
# ---------------------------------------------------------------------------

@dataclass
class _Decrements:
    q_primary_m: Array          # monthly death prob of the life insured per step
    surv_primary: Array         # survival of primary to each grid point
    q_spouse_m: Optional[Array] # monthly death prob of the spouse per step
    lapse_growth_a: Array       # annual base lapse per step (growth)
    lapse_income_a: float


def _build_decrements(policy: PolicySpec, mortality: MortalityTable,
                      behaviour: BehaviourModel, n_steps: int) -> _Decrements:
    issue_offset = policy.commencement_year - mortality.base_year
    q1 = mortality.monthly_q_curve(
        policy.age,
        policy.sex,
        n_steps,
        years_from_base=issue_offset,
        projection_duration_start=0.0,
    )
    surv1 = np.ones(n_steps + 1)
    surv1[1:] = np.cumprod(1.0 - q1)

    q_spouse = None
    if policy.spouse and policy.spouse_age is not None:
        sex2 = policy.spouse_sex or policy.sex
        q_spouse = mortality.monthly_q_curve(
            policy.spouse_age,
            sex2,
            n_steps,
            years_from_base=issue_offset,
            projection_duration_start=0.0,
        )

    lapse_g = np.zeros(n_steps)
    for k in range(n_steps):
        year = k // STEPS_PER_YEAR + 1
        lapse_g[k] = behaviour.lapse.growth_rate(year)

    return _Decrements(q_primary_m=q1, surv_primary=surv1, q_spouse_m=q_spouse,
                       lapse_growth_a=lapse_g,
                       lapse_income_a=behaviour.lapse.income_phase)


# ---------------------------------------------------------------------------
# Main projection
# ---------------------------------------------------------------------------

def _annual_take_up_uniforms(
    seed: int,
    n_paths: int,
    n_years: int,
) -> Array:
    """Return horizon-stable take-up uniforms indexed by path and year.

    Draw policy years on the leading RNG axis before transposing to the
    projector's ``(path, year)`` layout.  Extending ``n_years`` therefore only
    appends draws: every existing path/year pair keeps the same uniform.  A
    common seed still gives identical draws across product alternatives.
    """
    return np.random.default_rng(seed).random((n_years, n_paths)).T


def project(product: IndexLinkedLifetimeIncomeProduct, policy: PolicySpec,
            scenarios: ScenarioSet,
            behaviour: BehaviourModel, mortality: MortalityTable,
            expenses: Optional[ExpenseAssumptions] = None,
            config: ProjectionConfig = ProjectionConfig(),
            surrender_policy: Optional[object] = None,
            income_election_policy: Optional[object] = None,
            income_action_policy: Optional[object] = None,
            cap_decision_observer: Optional[object] = None,
            surrender_decision_observer: Optional[object] = None,
            income_transition_observer: Optional[object] = None,
            ) -> ProjectionResult:
    """Run the monthly projection over all scenario paths.

    ``surrender_policy`` is an optional research hook for an independently
    fitted, pathwise exercise rule.  New hooks implement
    ``surrender_mask(*, context: SurrenderDecisionContext)`` and therefore see
    only customer-observable state at the existing Full-Withdrawal event point.
    The historical keyword signature remains supported for repository
    compatibility.  The hook is deliberately separate from
    :class:`BehaviourModel`: statistical behaviour remains the production
    regime, while an optimal-policy rollout must still pass through this exact
    monthly cashflow engine.  When supplied, it replaces the statistical lapse
    probability; all fees, MVA, mortality and accounting order stay unchanged.

    ``income_election_policy`` is the corresponding strict hook at the annual
    Growth-phase action boundary.  A hook implements
    ``start_income_mask(*, context: IncomeElectionDecisionContext)``.  Invalid
    outputs and unexpected policy exceptions propagate instead of becoming a
    silent WAIT decision.  Contractual gates remain owned by the product, and
    a forced start always overrides the voluntary hook.

    ``income_action_policy`` is the unified optimal-action hook after the
    regular monthly Fixed-Income payment.  It implements
    ``choose_income_action(*, context: IncomeActionDecisionContext)`` and
    returns one strictly pathwise :class:`IncomeActionDecision`.  When
    supplied it replaces statistical Income-phase Partial/Excess Withdrawals
    and lapse, while Growth behaviour and the complete no-hook projection path
    remain unchanged.  It is mutually exclusive with ``surrender_policy``;
    the latter remains available for fixed-Election/Full-Withdrawal-only
    compatibility studies.

    ``cap_decision_observer`` is a read-only research observer.  Its
    ``observe_cap_decision(*, context: CreditingCapDecisionContext)`` method is
    called at issue and at every Anniversary after old-cap crediting, fee
    posting, mortality and Income Election, but before the next cap starts a
    new DVA/hedge period.  It cannot alter the product state or choose a cap.

    ``surrender_decision_observer`` is called immediately before the existing
    Full-Withdrawal action.  Its
    ``observe_surrender_decision(*, context: SurrenderActionValueContext)``
    method sees the exact Policyholder decision context, post-cap common
    current-step cashflows and the exact counterfactual FULL_WITHDRAWAL
    settlement/expense cashflows.  The richer action-value context is never
    passed to ``surrender_policy`` and cannot alter the action or product state.

    ``income_transition_observer`` is an engine/training observer, never a
    Policyholder information surface.  Its
    ``observe_income_transition(*, state, scenario_slice)`` method receives a
    pre-action :class:`IncomeActionState` and the immutable exogenous shock to
    the next monthly action boundary.  Calls are delayed by one grid step so
    the slice contains the mortality draw actually consumed by the projector;
    no future field is added to :class:`IncomeActionDecisionContext`.
    """

    policy.validate_against(product)
    if income_action_policy is not None and surrender_policy is not None:
        raise ValueError(
            "income_action_policy and surrender_policy are mutually exclusive."
        )
    if income_action_policy is not None and policy.age_pension_plus:
        raise NotImplementedError(
            "Optimal monthly Income actions do not support Age Pension Plus."
        )
    if income_transition_observer is not None and policy.age_pension_plus:
        raise NotImplementedError(
            "Income transition panels do not support Age Pension Plus."
        )
    if income_action_policy is None:
        income_action_method = None
    else:
        income_action_method = getattr(
            income_action_policy, "choose_income_action", None
        )
        if income_action_method is None or not callable(income_action_method):
            raise TypeError(
                "income_action_policy must provide a choose_income_action method."
            )
    if income_transition_observer is None:
        income_transition_observer_method = None
    else:
        income_transition_observer_method = getattr(
            income_transition_observer, "observe_income_transition", None
        )
        if (
            income_transition_observer_method is None
            or not callable(income_transition_observer_method)
        ):
            raise TypeError(
                "income_transition_observer must provide an "
                "observe_income_transition method."
            )
    take_up = behaviour.take_up
    policy_controlled_election = income_election_policy is not None
    pathwise_joint_life = bool(
        policy.spouse
        and (
            take_up.mode != "deterministic"
            or policy_controlled_election
            or surrender_policy is not None
            or income_action_policy is not None
            or income_transition_observer is not None
            or behaviour.use_dynamic
            or behaviour.use_dynamic_withdrawals
            or config.force_pathwise_joint_life
        )
    )
    if (
        policy.spouse
        and policy.spouse_death_election == SpouseDeathElection.CONTINUE_INCOME
        and (behaviour.use_dynamic or behaviour.use_dynamic_withdrawals)
        and not pathwise_joint_life
    ):
        raise ValueError(
            "Continue-Income Joint Life requires state-independent static "
            "lapse and withdrawal assumptions until separate p11/p10/p01 "
            "Account-Value and fee cohorts are implemented."
        )
    n_paths = scenarios.n_paths
    n_steps = scenarios.n_steps
    times = scenarios.times
    curve = scenarios.config.curve
    # Contractual DVA and mid-market replication values must not absorb an
    # insurer execution-cost assumption.  The spread-bearing configuration is
    # used only to derive the separate, adverse hedge-cost cashflow below.
    market_config = replace(config, hedge_vol_spread=0.0)

    remaining_years = config.max_age - policy.age
    if (policy.spouse and policy.spouse_age is not None
            and policy.spouse_death_election == SpouseDeathElection.CONTINUE_INCOME):
        remaining_years = max(remaining_years, config.max_age - policy.spouse_age)
    if not np.isfinite(remaining_years) or remaining_years <= 0.0:
        raise ValueError("Projection max_age must exceed the terminal age of at least one covered life.")
    horizon_steps = min(
        n_steps,
        int(np.ceil(remaining_years * STEPS_PER_YEAR - 1.0e-12)),
    )
    if horizon_steps < n_steps:
        n_steps = horizon_steps

    reference_spec = product.reference_fund
    hedge_price_surface = scenarios.hedge_price_surface
    if config.hedge_pricing_method == "mc_conditional":
        if hedge_price_surface is None:
            raise ValueError(
                "mc_conditional hedge pricing requires an exact validated "
                "HedgePriceSurface bound to the ScenarioSet."
            )
        if config.hedge_cap_leg_mode != HedgeCapLegMode.SOLD:
            raise ValueError(
                "mc_conditional currently prices the standard sold-cap call "
                "spread only; use moment_matched_bs for an uncapped long call."
            )
        hedge_price_surface.validate_against(scenarios)
    reference_fund_level = scenarios.monthly_rebalanced_reference_fund_index(
        equity_index=reference_spec.equity_index,
        equity_weight=reference_spec.equity_weight,
        bond_tenor=reference_spec.bond_tenor_years,
    )
    commencement_date = _fractional_year_to_date(policy.commencement_year)
    grid_dates = tuple(_add_calendar_months(commencement_date, k)
                       for k in range(n_steps + 1))
    fee_day_fractions = np.asarray([
        (grid_dates[k + 1] - grid_dates[k]).days / 365.0
        for k in range(n_steps)
    ], dtype=float)

    dec = _build_decrements(policy, mortality, behaviour, n_steps)
    mortality_issue_offset = policy.commencement_year - mortality.base_year

    def policy_time_to_step(years: float) -> int:
        step_f = float(years) * STEPS_PER_YEAR
        step_i = int(round(step_f))
        if abs(step_f - step_i) > 1e-9:
            raise ValueError("Policy time must fall on the monthly projection grid.")
        return step_i

    dynamic_take_up = (
        take_up.mode == "dynamic" and not policy_controlled_election
    )
    no_scheduled_step = np.iinfo(np.int32).max
    take_up_draws = None
    if take_up.mode == "deterministic" and not policy_controlled_election:
        effective_income_start_year = policy.effective_income_start_year(product)
        income_step = np.full(
            n_paths,
            policy_time_to_step(effective_income_start_year),
        )
    elif take_up.mode == "hazard" and not policy_controlled_election:
        last_projection_year = int(np.ceil(n_steps / STEPS_PER_YEAR))
        income_step = np.full(
            n_paths, no_scheduled_step, dtype=np.int64
        )
        u = _annual_take_up_uniforms(
            config.take_up_seed,
            n_paths,
            last_projection_year + 1,
        )
        for y in range(1, last_projection_year + 1):
            p = take_up.probability(y)
            newly = (income_step == no_scheduled_step) & (u[:, y] < p)
            income_step[newly] = y * STEPS_PER_YEAR
    elif dynamic_take_up:
        # Dynamic take-up is deliberately not pre-simulated at issue.  One
        # common-random-number draw per path and policy year is stored, while
        # the annual probability itself is evaluated from the market state at
        # the relevant Anniversary Date below.
        draw_years = int(np.ceil(n_steps / STEPS_PER_YEAR)) + 1
        take_up_draws = _annual_take_up_uniforms(
            config.take_up_seed,
            n_paths,
            draw_years,
        )
        income_step = np.full(n_paths, no_scheduled_step, dtype=np.int64)
    else:
        # A Policy-controlled Election has no model-point scheduled date.  The
        # object is queried only at eligible Anniversaries below.  Missing,
        # malformed or unstable voluntary decisions are hard errors; only a
        # valid WAIT decision can defer to a later contractual force.
        income_step = np.full(n_paths, no_scheduled_step, dtype=np.int64)

    min_income_step = product.min_years_before_income * STEPS_PER_YEAR
    income_step = np.maximum(income_step, min_income_step)

    # Case-study convention: force commencement on the first Anniversary
    # after the configured automatic-start age.
    years_to_100 = max(product.automatic_income_start_age - policy.age, 0.0)
    age_100_force_step = (
        max(
            int(np.floor(years_to_100 + 1e-12)) + 1,
            int(product.min_years_before_income),
            1,
        )
        * STEPS_PER_YEAR
    )
    income_step = np.minimum(income_step, age_100_force_step)

    if policy.age_pension_plus:
        if policy.funding_source == FundingSource.NON_SUPERANNUATION:
            # Non-super APS commences at the earlier of income commencement
            # and reaching Pension Age (PDS pp. 15-16).  ``ceil`` puts a
            # fractional birthday on the first monthly grid point not before it.
            pension_t = max(product.aps.pension_age - policy.age, 0.0)
            pension_step = int(np.ceil(pension_t * STEPS_PER_YEAR - 1e-12))
            aps_start_step = np.minimum(income_step, pension_step)
        else:
            # PolicySpec validation requires this field for APS super money.
            release_step = policy_time_to_step(float(policy.condition_of_release_year))
            aps_start_step = np.full(n_paths, release_step, dtype=np.int64)
    else:
        aps_start_step = np.full(n_paths, no_scheduled_step, dtype=np.int64)

    # ---------------- state ------------------------------------------- #
    P0 = policy.net_initial_investment
    iv = np.full(n_paths, P0)                    # current (DVA-consistent) IV
    iv_frame = iv.copy()                          # contractual IV units
    phase = np.zeros(n_paths, dtype=np.int8)      # 0 growth, 1 income, 2 out
    income_annual = np.zeros(n_paths)
    fee_product_accrued = np.zeros(n_paths)
    fee_lip_accrued = np.zeros(n_paths)
    just_elected = np.zeros(n_paths, dtype=bool)  # suppresses the payment in
    # the election month: payments are monthly in arrears, the first one falls
    # one month after the Lifetime Income Commencement Date (PDS section 13).
    w = np.ones(n_paths)                          # in-force probability weight
    # Nonlinear Joint-Life behaviour cannot act on a mortality-state-averaged
    # p11/p10/p01 value, so those cases simulate Primary/Spouse status with a
    # separate reproducible seed.  Portfolio factor runners also force this
    # treatment for their deterministic arms to keep one common mortality
    # basis; standalone deterministic calls retain the historical expected-
    # decrement fallback unless explicitly configured otherwise.
    primary_alive = np.ones(n_paths, dtype=bool)
    spouse_alive = np.ones(n_paths, dtype=bool)
    joint_income_cover = np.zeros(n_paths, dtype=bool)
    mortality_rng = (
        np.random.default_rng(config.mortality_seed)
        if pathwise_joint_life else None
    )
    complete_growth_years = np.zeros(n_paths, dtype=np.int32)
    free_wd_used = np.zeros(n_paths)
    # The PDS imposes a second, cumulative limit in each Growth-Phase
    # Anniversary year: partial withdrawals inclusive of MVA may not exceed
    # 95% of the IV (or lower APS value) at the start of that year.
    partial_wd_used = np.zeros(n_paths)
    wd_limit_base = np.full(n_paths, P0)

    # Age Pension+ state
    aps_active = np.zeros(n_paths, dtype=bool)
    cas_base = np.zeros(n_paths)
    cas_start_t = np.zeros(n_paths)
    cas_le = np.ones(n_paths)
    cas_wd = np.zeros(n_paths)
    aps_auto_income_step = np.full(n_paths, np.iinfo(np.int32).max, dtype=np.int64)
    # For Spouse-Insured income, last-survivor mortality must be conditioned
    # from the actual income election date, not from policy issue.
    joint_surv_primary = np.ones(n_paths)
    joint_surv_spouse = np.ones(n_paths)
    # This flag survives termination and therefore identifies the contractual
    # phase in which a cashflow was generated even after ``phase`` becomes
    # TERMINATED.  It is updated exactly at the Election transaction boundary.
    has_elected_income = np.zeros(n_paths, dtype=bool)

    cfs: Dict[str, Array] = {k: np.zeros((n_paths, n_steps + 1)) for k in CASHFLOW_KEYS}
    phase_cfs: Dict[str, Array] = {
        key: np.zeros((n_paths, n_steps + 1))
        for key in PHASE_CASHFLOW_KEYS
    }

    def classify_phase_cashflow_delta(
        step: int,
        before: Mapping[str, Array],
        post_election: NDArray[np.bool_],
    ) -> None:
        """Book one exact event-order slice to the phase-analysis ledger."""
        post = np.asarray(post_election, dtype=bool)
        if post.shape != (n_paths,):
            raise ValueError("Phase cashflow mask must have one value per path.")

        def delta(key: str) -> Array:
            return cfs[key][:, step] - np.asarray(before[key], dtype=float)

        benefits = sum(
            (delta(key) for key in (
                "income_paid",
                "death_benefits",
                "surrender_benefits",
                "partial_withdrawals",
                "terminal_closeout",
            )),
            np.zeros(n_paths),
        )
        fees = delta("fees_product") + delta("fees_lip")
        phase_cfs["policyholder_benefits_pre_election"][:, step] += np.where(
            post, 0.0, benefits
        )
        phase_cfs["policyholder_benefits_post_election"][:, step] += np.where(
            post, benefits, 0.0
        )
        phase_cfs["growth_fees"][:, step] += np.where(post, 0.0, fees)
        phase_cfs["growth_crediting_margin"][:, step] += np.where(
            post, 0.0, delta("crediting_margin")
        )
        phase_cfs["post_election_guarantee_claims"][:, step] += np.where(
            post, delta("guarantee_claims"), 0.0
        )
    # Anniversary timestamps contain events on both sides of the new-cap
    # announcement.  This auxiliary ledger records only the cashflow portion
    # after that boundary, without changing the canonical cashflow buckets.
    post_cap_cfs: Dict[str, Array] = {
        key: np.zeros((n_paths, n_steps + 1)) for key in CASHFLOW_KEYS
    }
    post_cap_lapse_events = np.zeros((n_paths, n_steps + 1))
    # Cashflows strictly after the Policyholder Full-Withdrawal decision
    # boundary.  This ledger is populated on every monthly event point so a
    # discounted annual interval can be split exactly at its action timestamp.
    post_surrender_cfs: Dict[str, Array] = {
        key: np.zeros((n_paths, n_steps + 1)) for key in CASHFLOW_KEYS
    }
    cfs["premium"][:, 0] = P0
    # A promotional commencement bonus becomes part of IV/fee/withdrawal bases
    # but is funded by the insurer and therefore an acquisition outflow.
    cfs["expenses"][:, 0] = policy.bonus_interest_amount

    inforce = np.ones((n_paths, n_steps + 1))
    lapse_events = np.zeros((n_paths, n_steps + 1))
    ordinary_lapse_events = np.zeros((n_paths, n_steps + 1))
    performance_lapse_events = np.zeros((n_paths, n_steps + 1))
    ordinary_lapse_probabilities = np.zeros((n_paths, n_steps + 1))
    performance_lapse_probabilities = np.zeros((n_paths, n_steps + 1))
    total_lapse_probabilities = np.zeros((n_paths, n_steps + 1))
    eligible_growth_exposure = np.zeros((n_paths, n_steps + 1))
    income_take_up_probability = np.zeros((n_paths, n_steps + 1))
    income_election_events = np.zeros((n_paths, n_steps + 1))
    forced_income_election_events = np.zeros((n_paths, n_steps + 1))
    growth_exposure = np.zeros((n_paths, n_steps + 1))
    income_exposure = np.zeros((n_paths, n_steps + 1))
    growth_exposure[:, 0] = 1.0
    iv_paths = np.zeros((n_paths, n_steps + 1)) if config.record_paths else None
    income_paths = np.zeros((n_paths, n_steps + 1)) if config.record_paths else None
    phase_paths = np.zeros((n_paths, n_steps + 1), dtype=np.int8) if config.record_paths else None
    if iv_paths is not None:
        iv_paths[:, 0] = iv

    exp_assum = expenses
    expense_inflation_factors = None
    if exp_assum is not None:
        expense_base_date = date.fromisoformat(exp_assum.fixed_expense_base_date)
        expense_inflation_factors = np.asarray([
            _average_expense_inflation_factor(
                grid_dates[k], grid_dates[k + 1],
                exp_assum.expense_inflation, expense_base_date)
            for k in range(n_steps)
        ], dtype=float)
        cfs["expenses"][:, 0] += exp_assum.acquisition_pct_of_premium * policy.initial_investment \
            + exp_assum.commission_pct_of_premium * policy.initial_investment

    # anniversary-start snapshots for crediting
    anniv_reference_level = reference_fund_level[:, 0].copy()
    anniv_step = 0
    # Trailing realised reference-fund performance not passed through to the
    # customer.  It is zero at issue and updated only after annual crediting,
    # so the behaviour model never sees future market performance.
    previous_reference_return = np.zeros(n_paths)
    previous_credited_return = np.zeros(n_paths)
    performance_shortfall = np.zeros(n_paths)
    previous_cap = np.zeros(n_paths)

    z_issue_cache: Dict[int, float] = {}

    def issue_zero(tau: float) -> float:
        """Annually compounded zero rate from the issue curve for tenor tau."""
        key = int(round(tau * 12))
        if key not in z_issue_cache:
            z_issue_cache[key] = float(np.expm1(curve.zero(max(tau, 1e-6))))
        return z_issue_cache[key]

    def activate_aps(mask: Array, step: int, t: float) -> None:
        """Lock the Capital Access Schedule state on its contractual date."""
        nonlocal aps_active, cas_base, cas_start_t, cas_le
        nonlocal aps_auto_income_step, wd_limit_base

        if not policy.age_pension_plus:
            return
        activate = np.asarray(mask, dtype=bool) & ~aps_active & (phase < 2)
        if not activate.any():
            return
        le = (float(policy.aps_life_expectancy)
              if policy.aps_life_expectancy is not None
              else mortality.life_expectancy(
                  policy.age + t, policy.sex,
                  years_from_base=mortality_issue_offset + t,
                  projection_duration_start=t))
        aps_active |= activate
        cas_base = np.where(activate, iv, cas_base)
        cas_start_t = np.where(activate, t, cas_start_t)
        cas_le = np.where(activate, le, cas_le)

        # If APS is active in Growth, income must start at the first original
        # policy anniversary strictly after Life Expectancy is reached.
        le_force_year = int(np.floor(t + le + 1e-12)) + 1
        aps_auto_income_step = np.where(
            activate, le_force_year * STEPS_PER_YEAR, aps_auto_income_step)

        # From APS commencement there is no free withdrawal amount.  Reset the
        # cumulative base to the newly established lower contractual value.
        growth_activation = activate & (phase == Phase.GROWTH.value)
        wd_limit_base = np.where(growth_activation, np.minimum(iv, cas_base),
                                 wd_limit_base)

    def package_and_zcb(step: int, tau: float, phase_arr: Array) -> Array:
        """DVA proxy for an option on the *complete* reference fund.

        A single Total-Protection package is valued on the monthly rebalanced
        fund.  Its volatility is moment-matched from the joint equity/Hull-
        White model; no per-sleeve option values and no COS method are used.
        The same package applies in Growth and Income.
        """
        del phase_arr  # reference-fund exposure is phase invariant
        tau_e = max(float(tau), 1e-6)
        r_cc = scenarios.forward_zero_cc(step, tau_e)
        x0 = reference_fund_level[:, step] / np.maximum(
            anniv_reference_level, 1e-300)
        sigma = scenarios.reference_fund_effective_vol(
            step,
            horizon=tau_e,
            equity_index=reference_spec.equity_index,
            equity_weight=reference_spec.equity_weight,
            bond_tenor=reference_spec.bond_tenor_years,
        ) + market_config.hedge_vol_spread
        return np.asarray(intra_year_value_factor(
            x0,
            Protection.TOTAL,
            reference_spec.cap(anniv_step // STEPS_PER_YEAR),
            tau_e,
            r_cc,
            0.0,
            sigma,
        ))

    gross_premium = float(policy.initial_investment)

    def annuity_factor_for_state(
        step: int,
        t: float,
        phase_state: NDArray[np.int8],
        primary_alive_state: NDArray[np.bool_],
        spouse_alive_state: NDArray[np.bool_],
        joint_income_cover_state: NDArray[np.bool_],
        joint_surv_primary_state: Array,
        joint_surv_spouse_state: Array,
    ) -> Array:
        """Pathwise annuity factor for an explicit mortality/phase state."""
        age_now = policy.age + t
        z10 = scenarios.forward_zero_cc(step, 10.0)
        if policy.spouse and policy.spouse_age is not None:
            spouse_age_now = policy.spouse_age + t
            spouse_sex = policy.spouse_sex or policy.sex
            common = dict(
                years_from_base=mortality_issue_offset + t,
                projection_duration_start=t,
            )
            primary_only = np.asarray(mortality.annuity_factor(
                age_now, policy.sex, z10, **common), dtype=float)
            spouse_only = np.asarray(mortality.annuity_factor(
                spouse_age_now, spouse_sex, z10, **common), dtype=float)
            if (
                policy.spouse_death_election
                == SpouseDeathElection.CONTINUE_INCOME
            ):
                both_alive = np.asarray(mortality.annuity_factor(
                    age_now, policy.sex, z10,
                    joint_age=spouse_age_now, joint_sex=spouse_sex,
                    **common), dtype=float)
            else:
                # Under a Lump-Sum election the income stream remains exposed
                # to Primary-Life mortality even though the lower Spouse rate
                # is locked while both lives are eligible.
                both_alive = primary_only

            if pathwise_joint_life:
                primary_component = np.where(
                    primary_alive_state, primary_only, 0.0
                )
                if (
                    policy.spouse_death_election
                    == SpouseDeathElection.CONTINUE_INCOME
                ):
                    joint_component = np.where(
                        primary_alive_state & spouse_alive_state,
                        both_alive,
                        np.where(
                            primary_alive_state,
                            primary_only,
                            np.where(spouse_alive_state, spouse_only, 0.0),
                        ),
                    )
                else:
                    joint_component = primary_component
                growth_component = np.where(
                    primary_alive_state & spouse_alive_state,
                    both_alive,
                    primary_component,
                )
                income_component = np.where(
                    joint_income_cover_state,
                    joint_component,
                    primary_component,
                )
                return np.where(
                    phase_state == Phase.INCOME.value,
                    income_component,
                    growth_component,
                )

            if (
                policy.spouse_death_election
                != SpouseDeathElection.CONTINUE_INCOME
            ):
                return primary_only
            p11 = joint_surv_primary_state * joint_surv_spouse_state
            p10 = joint_surv_primary_state * (1.0 - joint_surv_spouse_state)
            p01 = (1.0 - joint_surv_primary_state) * joint_surv_spouse_state
            last_survivor = p11 + p10 + p01
            survivor_mix = np.divide(
                p11 * both_alive + p10 * primary_only + p01 * spouse_only,
                np.maximum(last_survivor, 1e-300),
                out=both_alive.copy(),
                where=last_survivor > 0.0,
            )
            return np.where(
                phase_state == Phase.INCOME.value, survivor_mix, both_alive)
        return np.asarray(mortality.annuity_factor(
            age_now, policy.sex, z10,
            years_from_base=mortality_issue_offset + t,
            projection_duration_start=t), dtype=float)

    def annuity_factor_at(step: int, t: float) -> Array:
        """Pathwise annuity factor under the current projector state."""
        return annuity_factor_for_state(
            step,
            t,
            phase,
            primary_alive,
            spouse_alive,
            joint_income_cover,
            joint_surv_primary,
            joint_surv_spouse,
        )

    def prospective_income_rate(t: float) -> Array:
        """Income rate available now, respecting current Spouse eligibility."""
        complete_years = int(np.floor(t + 1e-12))
        if pathwise_joint_life:
            joint_rate = product.income_rates.lifetime_income_rate(
                policy.age, policy.sex, policy.income_type, True,
                complete_years, policy.spouse_age, policy.spouse_sex,
                policy.age_pension_plus)
            single_rate = product.income_rates.lifetime_income_rate(
                policy.age, policy.sex, policy.income_type, False,
                complete_years, None, None, policy.age_pension_plus)
            return np.where(
                primary_alive & spouse_alive,
                joint_rate,
                single_rate,
            ).astype(float)
        rate = product.income_rates.lifetime_income_rate(
            policy.age, policy.sex, policy.income_type, policy.spouse,
            complete_years, policy.spouse_age, policy.spouse_sex,
            policy.age_pension_plus)
        return np.full(n_paths, float(rate))

    def guarantee_pv_at(step: int, t: float) -> Array:
        """Pathwise PV of the remaining contractual lifetime-income stream."""
        af = annuity_factor_at(step, t)
        growth_pv = iv * prospective_income_rate(t) * af
        return np.maximum(np.where(
            phase == Phase.INCOME.value,
            income_annual * af,
            growth_pv,
        ), 0.0)

    def guarantee_log_moneyness(step: int, t: float,
                                denominator: Array) -> Array:
        """Log PV(guaranteed income) divided by the relevant exit value."""
        guarantee_pv = guarantee_pv_at(step, t)
        ratio = np.divide(
            guarantee_pv, np.maximum(np.asarray(denominator, dtype=float), 1e-300),
            out=np.full(n_paths, np.exp(2.0)),
            where=np.asarray(denominator, dtype=float) > 1e-12,
        )
        return np.log(np.maximum(ratio, 1e-300))

    def as_path_array(value: object, *, name: str) -> Array:
        """Broadcast a scalar or validate a pathwise product quantity."""
        arr = np.asarray(value, dtype=float)
        if arr.ndim == 0:
            return np.full(n_paths, float(arr))
        if arr.shape != (n_paths,):
            raise ValueError(
                f"{name} must be scalar or have one value per scenario path."
            )
        return arr.copy()

    def observe_cap_decision(step: int, t: float) -> None:
        """Expose the exact pre-leader-action state without mutating it."""
        if cap_decision_observer is None:
            return
        method = getattr(cap_decision_observer, "observe_cap_decision", None)
        if method is None or not callable(method):
            raise TypeError(
                "cap_decision_observer must provide an "
                "observe_cap_decision method."
            )

        _, _, post_fee_av = fee_settlement(iv)
        surrender_value, _ = _surrender_value(
            product, policy, scenarios, step, t, post_fee_av,
            free_wd_used, phase, aps_active, issue_zero, P0,
        )
        if policy.age_pension_plus:
            mwv = _aps_max_withdrawal(
                product, cas_base, t, cas_start_t, cas_le, cas_wd, aps_active,
            )
            surrender_value = np.where(
                aps_active & (surrender_value > mwv), mwv, surrender_value,
            )

        guarantee_pv = guarantee_pv_at(step, t)
        guarantee_ratio = np.divide(
            guarantee_pv,
            np.maximum(np.asarray(surrender_value, dtype=float), 1e-300),
            out=np.full(n_paths, np.exp(2.0)),
            where=np.asarray(surrender_value, dtype=float) > 1e-12,
        )
        guarantee_log_mny = np.log(np.maximum(guarantee_ratio, 1e-300))
        if scenarios.variance is None:
            heston_variance = np.zeros(n_paths)
        else:
            heston_variance = np.asarray(
                scenarios.variance[reference_spec.equity_index][:, step],
                dtype=float,
            )
        zero_rate_5y = as_path_array(
            scenarios.zero_rate(step, 5.0), name="five-year zero rate",
        )
        context = CreditingCapDecisionContext(
            step=int(step),
            time=float(t),
            policy_year=int(step // STEPS_PER_YEAR),
            phase=phase,
            account_value=iv,
            surrender_value=surrender_value,
            locked_annual_income=income_annual,
            guarantee_pv=guarantee_pv,
            guarantee_moneyness=np.exp(
                np.clip(guarantee_log_mny, -50.0, 50.0)
            ),
            guarantee_log_moneyness=guarantee_log_mny,
            short_rate=scenarios.short_rate[:, step],
            zero_rate_5y=zero_rate_5y,
            heston_variance=heston_variance,
            previous_cap=previous_cap,
            previous_reference_return=previous_reference_return,
            previous_credited_return=previous_credited_return,
            performance_gap=performance_shortfall,
            inforce_weight=w,
            just_elected=just_elected,
        )
        method(context=context)

    def current_mva_signal(step: int, t: float) -> Array:
        """Non-negative current MVA bite used as a withdrawal covariate."""
        tau_rem = product.withdrawals.mva_period_years - t
        if tau_rem <= 0.0:
            return np.zeros(n_paths)
        f = product.mva.factor(issue_zero(tau_rem),
                               scenarios.zero_rate(step, tau_rem), tau_rem)
        return np.clip(np.asarray(f, dtype=float), 0.0, 1.0)

    def income_transition_state(
        step: int,
        path_index: NDArray[np.int64],
    ) -> IncomeActionState:
        """Snapshot the complete pre-action Income state for a path subset."""
        idx = np.asarray(path_index, dtype=np.int64)
        if idx.ndim != 1:
            raise ValueError("Income transition path indices must be one-dimensional.")
        if pathwise_joint_life:
            cover = joint_income_cover
        else:
            expected_joint_cover = bool(
                policy.spouse
                and policy.spouse_age is not None
                and policy.spouse_death_election
                == SpouseDeathElection.CONTINUE_INCOME
            )
            cover = np.where(
                phase == Phase.INCOME.value,
                expected_joint_cover,
                False,
            )
        announced = as_path_array(
            reference_spec.cap(anniv_step // STEPS_PER_YEAR),
            name="announced crediting cap",
        )
        return IncomeActionState(
            step=int(step),
            path_index=idx,
            gross_premium=np.full(idx.size, gross_premium),
            attained_age=np.full(idx.size, policy.age + times[step]),
            time_to_forced_election=np.full(
                idx.size,
                max(age_100_force_step / STEPS_PER_YEAR - times[step], 0.0),
            ),
            account_value=iv[idx],
            iv_frame=iv_frame[idx],
            locked_annual_income=income_annual[idx],
            phase=phase[idx],
            inforce_weight=w[idx],
            fee_product_accrued=fee_product_accrued[idx],
            fee_lip_accrued=fee_lip_accrued[idx],
            primary_alive=primary_alive[idx],
            spouse_alive=(
                spouse_alive[idx]
                if policy.spouse
                else np.zeros(idx.size, dtype=bool)
            ),
            joint_income_cover=cover[idx],
            joint_survival_primary=joint_surv_primary[idx],
            joint_survival_spouse=joint_surv_spouse[idx],
            previous_reference_return=previous_reference_return[idx],
            previous_credited_return=previous_credited_return[idx],
            performance_gap=performance_shortfall[idx],
            announced_cap=announced[idx],
            just_elected=just_elected[idx],
        )

    def income_transition_mortality_shock(
        interval_index: int,
        state: IncomeActionState,
        primary_draw: Optional[Array],
        spouse_draw: Optional[Array],
    ) -> tuple[
        Array,
        NDArray[np.bool_],
        NDArray[np.bool_],
        NDArray[np.bool_],
        Array,
        Array,
    ]:
        """Mortality shock for a pending Income state, independent of action."""
        idx = state.path_index
        if pathwise_joint_life:
            if primary_draw is None or spouse_draw is None or dec.q_spouse_m is None:
                raise RuntimeError(
                    "Pathwise Income transition mortality draws are missing."
                )
            primary_died = (
                state.primary_alive
                & (np.asarray(primary_draw)[idx] < dec.q_primary_m[interval_index])
            )
            spouse_died = (
                state.spouse_alive
                & (np.asarray(spouse_draw)[idx] < dec.q_spouse_m[interval_index])
            )
            next_primary = state.primary_alive & ~primary_died
            next_spouse = state.spouse_alive & ~spouse_died
            continue_joint = (
                state.joint_income_cover
                & (
                    policy.spouse_death_election
                    == SpouseDeathElection.CONTINUE_INCOME
                )
            )
            terminating = np.where(
                continue_joint,
                ~next_primary & ~next_spouse,
                primary_died,
            )
            return (
                terminating.astype(float),
                next_primary,
                next_spouse,
                state.joint_income_cover,
                state.joint_survival_primary,
                state.joint_survival_spouse,
            )

        primary_probability = np.full(
            state.n_paths, dec.q_primary_m[interval_index]
        )
        next_joint_primary = state.joint_survival_primary.copy()
        next_joint_spouse = state.joint_survival_spouse.copy()
        death_probability = primary_probability
        if (
            dec.q_spouse_m is not None
            and policy.spouse_death_election
            == SpouseDeathElection.CONTINUE_INCOME
        ):
            cover = state.joint_income_cover
            s1 = state.joint_survival_primary
            s2 = state.joint_survival_spouse
            s_ls = s1 + s2 - s1 * s2
            s1_next = s1 * (1.0 - dec.q_primary_m[interval_index])
            s2_next = s2 * (1.0 - dec.q_spouse_m[interval_index])
            s_ls_next = s1_next + s2_next - s1_next * s2_next
            q_joint = 1.0 - np.divide(
                s_ls_next,
                np.maximum(s_ls, 1.0e-300),
                out=np.ones_like(s_ls_next),
                where=s_ls > 0.0,
            )
            death_probability = np.where(cover, q_joint, death_probability)
            next_joint_primary = np.where(cover, s1_next, s1)
            next_joint_spouse = np.where(cover, s2_next, s2)
        return (
            np.clip(death_probability, 0.0, 1.0),
            state.primary_alive,
            state.spouse_alive,
            state.joint_income_cover,
            next_joint_primary,
            next_joint_spouse,
        )

    def wd_dynamic_rates(step: int, t: float) -> tuple[Array, Array]:
        """Expected free and excess withdrawal rates for the current step.

        The fractional-logit responses use current guarantee moneyness, the
        gross paid premium and, for excess withdrawals, the current MVA bite.
        """
        wb = behaviour.withdrawals
        if not behaviour.use_dynamic_withdrawals:
            return (np.full(n_paths, wb.free_utilisation),
                    np.full(n_paths, wb.excess_rate))
        log_mny = guarantee_log_moneyness(step, t, iv)
        mva_signal = current_mva_signal(step, t)
        dwp = behaviour.dynamic_withdrawals
        # The contractual free amount is MVA-free.  Only the excess-
        # withdrawal response may use the current MVA bite as a covariate.
        free = dwp.free_utilisation(
            wb.free_utilisation, log_mny, gross_premium, 0.0)
        excess = dwp.excess_rate(
            wb.excess_rate, log_mny, gross_premium, mva_signal)
        return np.asarray(free, dtype=float), np.asarray(excess, dtype=float)

    free_utilisation, excess_rate = wd_dynamic_rates(0, 0.0)
    # Initial values are replaced at every monthly Full-Withdrawal boundary.
    # The annual base assumption is dynamically scaled from current state and
    # only then converted to mutually exclusive monthly cause probabilities.
    income_lapse_ordinary_prob = np.full(
        n_paths,
        1.0 - (1.0 - dec.lapse_income_a) ** (1.0 / STEPS_PER_YEAR),
    )
    income_lapse_performance_prob = np.zeros(n_paths)

    def reference_customer_package_value(step: int) -> Array:
        """Fair capped customer package used only by the contract identity."""
        r_cc = scenarios.forward_zero_cc(step, 1.0)
        sigma = scenarios.reference_fund_effective_vol(
            step,
            horizon=1.0,
            equity_index=reference_spec.equity_index,
            equity_weight=reference_spec.equity_weight,
            bond_tenor=reference_spec.bond_tenor_years,
        )
        return np.asarray(crediting_package_value(
            1.0,
            Protection.TOTAL,
            reference_spec.cap(step // STEPS_PER_YEAR),
            1.0,
            r_cc,
            0.0,
            sigma,
        ))

    def reference_hedge_option_value(
            step: int, volatility_spread: float = 0.0) -> Array:
        """Fair one-year insurer hedge value on the complete Reference Fund."""
        if config.hedge_pricing_method == "mc_conditional" \
                and volatility_spread == 0.0:
            return np.asarray(hedge_price_surface.price_for(
                step,
                reference_spec.cap(step // STEPS_PER_YEAR),
            ))
        r_cc = scenarios.forward_zero_cc(step, 1.0)
        sigma = scenarios.reference_fund_effective_vol(
            step,
            horizon=1.0,
            equity_index=reference_spec.equity_index,
            equity_weight=reference_spec.equity_weight,
            bond_tenor=reference_spec.bond_tenor_years,
        ) + float(volatility_spread)
        return np.asarray(hedge_option_package_value(
            1.0,
            reference_spec.cap(step // STEPS_PER_YEAR),
            1.0,
            r_cc,
            0.0,
            sigma,
            config.hedge_cap_leg_mode,
        ))

    def book_annual_hedge_costs(step: int) -> None:
        """Book the annual option purchase and all incremental hedge costs.

        Fair value and its relative purchase markup are charged at the start
        of the crediting period.  The 30bp hedge-reference management fee is an
        annual cost on hedge notional; it is not a customer fund fee.  The
        optional legacy volatility-spread repricing remains a separate,
        non-negative execution component and is zero in the standard CSV.
        """
        if step >= n_steps:
            return
        active = phase < Phase.TERMINATED.value
        fair_rate = np.maximum(reference_hedge_option_value(step, 0.0), 0.0)
        fair_cost = iv_frame * fair_rate
        if config.hedge_pricing_method == "mc_conditional":
            r_cc = scenarios.forward_zero_cc(step, 1.0)
            sigma = scenarios.reference_fund_effective_vol(
                step,
                horizon=1.0,
                equity_index=reference_spec.equity_index,
                equity_weight=reference_spec.equity_weight,
                bond_tenor=reference_spec.bond_tenor_years,
            )
            bs_proxy_rate = np.asarray(hedge_option_package_value(
                1.0,
                reference_spec.cap(step // STEPS_PER_YEAR),
                1.0,
                r_cc,
                0.0,
                sigma,
                config.hedge_cap_leg_mode,
            ))
        else:
            bs_proxy_rate = fair_rate
        bs_proxy_cost = iv_frame * np.maximum(bs_proxy_rate, 0.0)
        markup_cost = fair_cost * config.option_fair_value_markup
        management_cost = (
            iv_frame * config.hedge_reference_management_fee
        )
        if config.hedge_vol_spread > 0.0:
            spread_quote = reference_hedge_option_value(
                step, config.hedge_vol_spread,
            )
            execution_cost = iv_frame * np.abs(spread_quote - bs_proxy_rate)
        else:
            execution_cost = np.zeros(n_paths)

        components = {
            "hedge_option_fair_value_costs": fair_cost,
            "hedge_option_markup_costs": markup_cost,
            "hedge_management_fee_costs": management_cost,
            "hedge_execution_costs": execution_cost,
        }
        aggregate = np.zeros(n_paths)
        for key, amount in components.items():
            weighted = w * np.where(active, amount, 0.0)
            cfs[key][:, step] += weighted
            aggregate += weighted
        cfs["hedge_option_fair_value_bs_proxy"][:, step] += (
            w * np.where(active, bs_proxy_cost, 0.0)
        )
        cfs["hedge_costs"][:, step] += aggregate

    def restart_dva_period(step: int) -> None:
        """Start a fresh annual crediting / DVA replication period."""
        nonlocal iv
        if step < n_steps:
            book_annual_hedge_costs(step)
        if config.dva_enabled and step < n_steps:
            # No restart at the final grid point: the horizon closeout pays
            # the current DVA-consistent IV, so no new crediting year is hedged.
            pz_start = package_and_zcb(step, 1.0, phase)
            financing_margin = iv_frame * (1.0 - pz_start)
            cfs["contract_financing_margin"][:, step] += w * np.where(
                phase < Phase.TERMINATED.value,
                financing_margin,
                0.0,
            )
            iv = iv_frame * pz_start

    def fee_settlement(account_value: Array) -> tuple[Array, Array, Array]:
        """Collectible Product Fee, LIP and post-fee Account Value at an event."""
        return _settle_fee_subledger_arrays(
            account_value,
            fee_product_accrued,
            fee_lip_accrued,
        )

    def post_fee_subledger(step: int) -> None:
        """Post all accrued fees for every currently in-force contract."""
        nonlocal iv, iv_frame, fee_product_accrued, fee_lip_accrued
        product_collected, lip_collected, post_fee_av = fee_settlement(iv)
        before = iv.copy()
        iv = post_fee_av
        ratio = np.divide(
            iv,
            np.maximum(before, 1e-300),
            out=np.ones(n_paths),
            where=before > 0.0,
        )
        iv_frame = iv_frame * ratio
        cfs["fees_product"][:, step] += w * product_collected
        cfs["fees_lip"][:, step] += w * lip_collected
        # No arrears are carried after a contractual deduction event.
        fee_product_accrued = np.zeros(n_paths)
        fee_lip_accrued = np.zeros(n_paths)

    def income_lapse_cause_probabilities_at(
        step: int,
        t: float,
        surrender_value: Array,
    ) -> tuple[Array, Array]:
        """Mutually exclusive monthly income-lapse cause probabilities."""
        log_mny = guarantee_log_moneyness(step, t, surrender_value)
        if behaviour.use_dynamic:
            ordinary, performance = behaviour.dynamic.income_cause_probabilities(
                dec.lapse_income_a, log_mny, gross_premium,
                1.0 / STEPS_PER_YEAR,
                performance_shortfall=performance_shortfall)
            return (
                np.asarray(ordinary, dtype=float),
                np.asarray(performance, dtype=float),
            )
        ordinary = np.full(
            n_paths,
            1.0 - (1.0 - dec.lapse_income_a) ** (1.0 / STEPS_PER_YEAR),
        )
        return ordinary, np.zeros(n_paths)

    def income_election_context(
        step: int,
        t: float,
        eligible: NDArray[np.bool_],
        forced: NDArray[np.bool_],
    ) -> IncomeElectionDecisionContext:
        """Build the exact post-mortality, pre-new-cap Election context."""
        rate = prospective_income_rate(t)
        prospective_income = np.maximum(iv, 0.0) * rate
        guarantee_pv = np.maximum(prospective_income * annuity_factor_at(step, t), 0.0)
        ratio = np.divide(
            guarantee_pv,
            np.maximum(np.asarray(iv, dtype=float), 1.0e-300),
            out=np.full(n_paths, np.exp(2.0)),
            where=np.asarray(iv, dtype=float) > 1.0e-12,
        )
        log_mny = np.log(np.maximum(ratio, 1.0e-300))
        if scenarios.variance is None:
            heston_variance = np.zeros(n_paths)
        else:
            heston_variance = np.asarray(
                scenarios.variance[reference_spec.equity_index][:, step],
                dtype=float,
            )
        return IncomeElectionDecisionContext(
            step=int(step),
            time=float(t),
            is_anniversary=True,
            policy_year=int(step // STEPS_PER_YEAR),
            duration_years=float(t),
            phase=phase,
            account_value=iv,
            prospective_locked_annual_income=prospective_income,
            prospective_income_rate=rate,
            guarantee_pv=guarantee_pv,
            guarantee_moneyness=np.exp(np.clip(log_mny, -50.0, 50.0)),
            guarantee_log_moneyness=log_mny,
            short_rate=scenarios.short_rate[:, step],
            zero_rate_5y=as_path_array(
                scenarios.zero_rate(step, 5.0), name="five-year zero rate",
            ),
            heston_variance=heston_variance,
            mva_factor=current_mva_signal(step, t),
            mva_remaining_years=max(
                product.withdrawals.mva_period_years - float(t), 0.0
            ),
            attained_age=np.full(n_paths, policy.age + float(t)),
            time_to_forced_election=np.full(
                n_paths,
                max(age_100_force_step / STEPS_PER_YEAR - float(t), 0.0),
            ),
            primary_alive=primary_alive,
            spouse_alive=(
                spouse_alive
                if policy.spouse
                else np.zeros(n_paths, dtype=bool)
            ),
            previous_cap=previous_cap,
            previous_reference_return=previous_reference_return,
            previous_credited_return=previous_credited_return,
            performance_gap=performance_shortfall,
            inforce_weight=w,
            voluntary_election_eligible=eligible & ~forced,
            forced_election=forced,
        )

    def income_action_context(
        step: int,
        t: float,
    ) -> IncomeActionDecisionContext:
        """Build the post-Fixed-Income voluntary-action context."""
        _, _, full_post_fee_av = fee_settlement(iv)
        surrender_value, _ = _surrender_value(
            product,
            policy,
            scenarios,
            step,
            t,
            full_post_fee_av,
            free_wd_used,
            phase,
            aps_active,
            issue_zero,
            P0,
        )
        guarantee_pv = guarantee_pv_at(step, t)
        guarantee_ratio = np.divide(
            guarantee_pv,
            np.maximum(surrender_value, 1.0e-300),
            out=np.full(n_paths, np.exp(2.0)),
            where=surrender_value > 1.0e-12,
        )
        guarantee_log_mny = np.log(
            np.maximum(guarantee_ratio, 1.0e-300)
        )
        max_partial = np.maximum(
            iv - product.withdrawals.min_residual_value, 0.0
        )
        income_state = (
            (phase == Phase.INCOME.value)
            & (w > 0.0)
        )
        partial_eligible = (
            income_state
            & (step < n_steps)
            & (max_partial >= product.withdrawals.min_withdrawal)
        )
        positive_income_guarantee = (
            income_state
            & (guarantee_pv > 1.0e-12 * gross_premium)
        )
        zero_exit_with_guarantee = (
            (surrender_value <= 1.0e-12 * gross_premium)
            & positive_income_guarantee
        )
        full_eligible = (
            income_state
            & (step < n_steps)
            & ~just_elected
            & (surrender_value > 1.0e-12 * gross_premium)
            & ~zero_exit_with_guarantee
        )
        if scenarios.variance is None:
            heston_variance = np.zeros(n_paths)
        else:
            heston_variance = np.asarray(
                scenarios.variance[reference_spec.equity_index][:, step],
                dtype=float,
            )
        return IncomeActionDecisionContext(
            step=int(step),
            phase=phase,
            inforce_weight=w,
            partial_withdrawal_eligible=partial_eligible,
            full_withdrawal_eligible=full_eligible,
            max_partial_gross_amount=max_partial,
            account_value=iv,
            locked_annual_income=income_annual,
            guarantee_pv=guarantee_pv,
            guarantee_log_moneyness=guarantee_log_mny,
            mva_factor=current_mva_signal(step, t),
            surrender_value=surrender_value,
            short_rate=scenarios.short_rate[:, step],
            zero_rate_5y=as_path_array(
                scenarios.zero_rate(step, 5.0), name="five-year zero rate",
            ),
            heston_variance=heston_variance,
            duration_years=float(t),
            mva_remaining_years=max(
                product.withdrawals.mva_period_years - float(t), 0.0
            ),
            attained_age=np.full(n_paths, policy.age + float(t)),
            time_to_forced_election=np.full(
                n_paths,
                max(age_100_force_step / STEPS_PER_YEAR - float(t), 0.0),
            ),
            primary_alive=primary_alive,
            spouse_alive=(
                spouse_alive
                if policy.spouse
                else np.zeros(n_paths, dtype=bool)
            ),
            announced_cap=as_path_array(
                reference_spec.cap(anniv_step // STEPS_PER_YEAR),
                name="announced crediting cap",
            ),
            previous_reference_return=previous_reference_return,
            previous_credited_return=previous_credited_return,
            performance_gap=performance_shortfall,
            just_elected=just_elected,
        )

    def choose_income_action(
        context: IncomeActionDecisionContext,
    ) -> tuple[NDArray[np.bool_], NDArray[np.bool_], Array]:
        """Validate one strict hook decision and return executable actions."""
        if income_action_method is None:
            return (
                np.zeros(n_paths, dtype=bool),
                np.zeros(n_paths, dtype=bool),
                np.zeros(n_paths),
            )
        decision = income_action_method(context=context)
        if not isinstance(decision, IncomeActionDecision):
            raise TypeError(
                "choose_income_action must return an IncomeActionDecision."
            )
        if decision.n_paths != n_paths:
            raise ValueError(
                "IncomeActionDecision must contain one action per scenario path."
            )

        action_type = decision.action_type
        requested_partial = (
            action_type == IncomeActionType.PARTIAL_WITHDRAWAL.value
        )
        full = action_type == IncomeActionType.FULL_WITHDRAWAL.value
        gross = (
            decision.partial_fraction_of_max
            * context.max_partial_gross_amount
        )
        # Contract rule: a gross request below the AUD minimum is CONTINUE,
        # not a smaller Partial Withdrawal.
        partial = requested_partial & (
            gross >= product.withdrawals.min_withdrawal
        )
        gross = np.where(partial, gross, 0.0)

        if np.any(partial & ~context.partial_withdrawal_eligible):
            raise ValueError(
                "Income policy selected PARTIAL_WITHDRAWAL on an ineligible path."
            )
        if np.any(full & ~context.full_withdrawal_eligible):
            raise ValueError(
                "Income policy selected FULL_WITHDRAWAL on an ineligible path."
            )
        return partial, full, gross

    def state_aware_dynamic_take_up_probability(
        base_probability: float,
        context: IncomeElectionDecisionContext,
    ) -> Array:
        """Call the configured take-up response with all observable state.

        Existing three-covariate Behaviour objects remain supported.  A richer
        versioned response can opt into any of the named state arguments below
        without exposing a ScenarioSet or future path.  The Election
        response receives Account Value, prospective locked income and the
        completed-year return diagnostics explicitly; no composite sign is
        hardcoded in the projector.
        """
        method = behaviour.dynamic_take_up.probability
        try:
            parameters = signature(method).parameters
        except (TypeError, ValueError):
            parameters = {}
        supports_state = (
            "account_value" in parameters
            or any(
                parameter.kind == Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            )
        )
        if supports_state:
            value = method(
                base_probability,
                context.guarantee_log_moneyness,
                gross_premium,
                account_value=context.account_value,
                prospective_annual_income=(
                    context.prospective_locked_annual_income
                ),
                previous_reference_return=context.previous_reference_return,
                previous_credited_return=context.previous_credited_return,
                performance_gap=context.performance_gap,
            )
        else:
            # Extension callables with the historical three-argument API are
            # still supported, but a TypeError raised inside a rich callable
            # is no longer swallowed as an accidental compatibility fallback.
            value = method(
                base_probability,
                context.guarantee_log_moneyness,
                gross_premium,
            )
        probability = np.asarray(value, dtype=float)
        if probability.ndim == 0:
            probability = np.full(n_paths, float(probability))
        if probability.shape != (n_paths,) or not np.all(np.isfinite(probability)):
            raise ValueError(
                "Dynamic Income take-up must return one finite probability per path."
            )
        return np.clip(probability, 0.0, 1.0)

    def policy_election_mask(
        context: IncomeElectionDecisionContext,
    ) -> NDArray[np.bool_]:
        """Return one strict voluntary Policy action per path."""
        if income_election_policy is None:
            return np.zeros(n_paths, dtype=bool)
        method = getattr(income_election_policy, "start_income_mask", None)
        if method is None or not callable(method):
            raise TypeError(
                "income_election_policy must provide a start_income_mask method."
            )
        decision = np.asarray(method(context=context))
        if decision.shape != (n_paths,):
            raise ValueError(
                "income_election_policy must return one decision per path."
            )
        if np.issubdtype(decision.dtype, np.bool_):
            return decision.astype(bool, copy=True)
        if not np.issubdtype(decision.dtype, np.number):
            raise TypeError(
                "income_election_policy decisions must be boolean or binary."
            )
        if not np.all(np.isfinite(decision)) or not np.all(
            (decision == 0) | (decision == 1)
        ):
            raise ValueError(
                "income_election_policy decisions must be finite and binary."
            )
        return decision.astype(bool)

    def income_election_decision(
        step: int,
        t: float,
        growth: Array,
        is_anniversary: bool,
    ) -> tuple[NDArray[np.bool_], Array, Array, NDArray[np.bool_]]:
        """Election mask, annual probability, eligible exposure and force."""
        eligible = (
            np.asarray(growth, dtype=bool)
            & (iv > 0.0)
            & (w > 0.0)
        )
        if not is_anniversary or step < min_income_step:
            zero_b = np.zeros(n_paths, dtype=bool)
            return zero_b, np.zeros(n_paths), eligible.astype(float), zero_b

        # These are the only contractual forced starts.  An optional legacy
        # Behaviour ``force_by_year`` remains a behavioural probability-one
        # event and is deliberately not reported in the forced-event ledger.
        forced = eligible & (
            (step >= age_100_force_step)
            | (step >= aps_auto_income_step)
        )
        context = income_election_context(step, t, eligible, forced)

        if policy_controlled_election:
            voluntary = policy_election_mask(context)
            probability = voluntary.astype(float)
        elif dynamic_take_up:
            policy_year = step // STEPS_PER_YEAR
            base_probability = take_up.probability(policy_year)
            if behaviour.use_dynamic_take_up:
                probability = state_aware_dynamic_take_up_probability(
                    base_probability, context
                )
            else:
                probability = np.full(n_paths, base_probability)
            if take_up_draws is None:
                raise RuntimeError("Dynamic take-up draws were not initialised.")
            voluntary = take_up_draws[:, policy_year] < probability
        else:
            required_step = np.minimum(income_step, aps_auto_income_step)
            voluntary = step >= required_step
            probability = np.asarray(voluntary, dtype=float)

        probability = np.where(context.voluntary_election_eligible,
                               probability, 0.0)
        elect = eligible & (forced | voluntary)
        total_probability = np.where(forced, 1.0, probability)
        return elect, total_probability, eligible.astype(float), forced

    def elect_income(elect: Array, step: int, t: float) -> None:
        """Elect Lifetime Income using the current IV as commencement value."""
        nonlocal phase, income_annual, iv_frame
        nonlocal free_utilisation, excess_rate
        nonlocal joint_surv_primary, joint_surv_spouse, joint_income_cover
        nonlocal income_lapse_ordinary_prob, income_lapse_performance_prob

        if not elect.any():
            return

        rate = prospective_income_rate(t)
        income_annual = np.where(elect, iv * rate, income_annual)
        iv_frame = np.where(elect, iv, iv_frame)
        phase = np.where(elect, Phase.INCOME.value, phase).astype(np.int8)
        just_elected[elect] = True

        if pathwise_joint_life:
            joint_income_cover = np.where(
                elect, primary_alive & spouse_alive, joint_income_cover
            )
        elif policy.spouse and dec.q_spouse_m is not None:
            joint_surv_primary = np.where(elect, 1.0, joint_surv_primary)
            joint_surv_spouse = np.where(elect, 1.0, joint_surv_spouse)
        free_utilisation, excess_rate = wd_dynamic_rates(step, t)
        election_surrender_value, _ = _surrender_value(
            product, policy, scenarios, step, t, iv, free_wd_used,
            phase, aps_active, issue_zero, P0)
        election_ordinary, election_performance = (
            income_lapse_cause_probabilities_at(
                step, t, election_surrender_value
            )
        )
        income_mask = phase == Phase.INCOME.value
        income_lapse_ordinary_prob = np.where(
            income_mask, election_ordinary, income_lapse_ordinary_prob
        )
        income_lapse_performance_prob = np.where(
            income_mask, election_performance, income_lapse_performance_prob
        )

    # APS may already commence at issue (for example a non-super policy whose
    # Life Insured is at or above Pension Age).
    activate_aps(aps_start_step <= 0, 0, 0.0)

    # The first cap is selected at issue from state which is independent of
    # that cap.  In particular this observer runs before hedge execution or
    # the first DVA package is started.
    observe_cap_decision(0, 0.0)
    issue_pre_cap_cashflows = {
        key: values[:, 0].copy() for key, values in cfs.items()
    }

    # The contract-financing margin preserves the customer-flow identity.  It
    # is not insurer P&L; actual backing income and hedge costs are separate.
    if config.dva_enabled:
        pz0 = package_and_zcb(0, 1.0, phase)
        cfs["contract_financing_margin"][:, 0] += iv_frame * (1.0 - pz0)
    book_annual_hedge_costs(0)
    for key in CASHFLOW_KEYS:
        post_cap_cfs[key][:, 0] = (
            cfs[key][:, 0] - issue_pre_cap_cashflows[key]
        )
    classify_phase_cashflow_delta(
        0,
        {key: np.zeros(n_paths) for key in CASHFLOW_KEYS},
        has_elected_income,
    )

    context_aware_surrender = (
        False
        if surrender_policy is None
        else _context_aware_surrender_policy(surrender_policy)
    )
    anniversary_only_surrender = bool(
        surrender_policy is not None
        and getattr(surrender_policy, "anniversary_only", False)
    )
    if surrender_decision_observer is None:
        surrender_observer_method = None
        anniversary_only_surrender_observer = False
    else:
        surrender_observer_method = getattr(
            surrender_decision_observer, "observe_surrender_decision", None
        )
        if surrender_observer_method is None or not callable(
            surrender_observer_method
        ):
            raise TypeError(
                "surrender_decision_observer must provide an "
                "observe_surrender_decision method."
            )
        anniversary_only_surrender_observer = bool(
            getattr(surrender_decision_observer, "anniversary_only", False)
        )

    def post_action_expense_cashflow(
        interval_index: int,
        month_start_weight: Array,
        month_start_account_value: Array,
        post_action_weight: Array,
        post_action_account_value: Array,
        alive_at_action_interval: NDArray[np.bool_],
    ) -> Array:
        """Exact midpoint maintenance expense for a post-action state."""
        if exp_assum is None:
            return np.zeros(n_paths)
        if expense_inflation_factors is None:
            raise RuntimeError("Expense inflation factors were not initialised.")
        infl = float(expense_inflation_factors[interval_index])
        exposure_weight = 0.5 * (
            month_start_weight + post_action_weight
        )
        fixed_expense = (
            exposure_weight
            * exp_assum.maintenance_per_policy
            * infl / STEPS_PER_YEAR
        )
        weighted_av_exposure = 0.5 * (
            month_start_weight * month_start_account_value
            + post_action_weight * np.maximum(post_action_account_value, 0.0)
        )
        variable_expense = (
            weighted_av_exposure
            * exp_assum.maintenance_pct_of_iv / STEPS_PER_YEAR
        )
        return np.where(
            alive_at_action_interval, fixed_expense + variable_expense, 0.0
        )

    # ------------------------------------------------------------------ #
    # main loop
    # ------------------------------------------------------------------ #
    final_pre_surrender_cashflows: Optional[dict[str, Array]] = None
    pending_income_transition: Optional[dict[str, object]] = None
    for k in range(n_steps):
        step = k + 1
        t = times[step]
        interval_credit_rate = np.zeros(n_paths)
        primary_mortality_draw: Optional[Array] = None
        spouse_mortality_draw: Optional[Array] = None
        step_start_cashflows = {
            key: values[:, step].copy() for key, values in cfs.items()
        }
        is_anniv = (step - anniv_step) == STEPS_PER_YEAR
        growth = phase == Phase.GROWTH.value
        income = phase == Phase.INCOME.value
        income_at_interval_start = income.copy()
        w_month_start = w.copy()
        av_month_start = np.maximum(iv.copy(), 0.0)
        backing_base_for_interval = np.where(
            phase < Phase.TERMINATED.value, np.maximum(iv_frame, 0.0), 0.0)
        fee_base_for_interval = np.where(
            phase < Phase.TERMINATED.value, np.maximum(iv_frame, 0.0), 0.0)
        if config.crediting_margin_enabled:
            # The insurer backs the administrative crediting frame in a
            # continuously rolled overnight account, never in the customer
            # Reference Fund.  ``iv`` can include the under-year DVA option
            # mark and is a customer-liability value, not a backing asset.
            # The discount-factor ratio is the
            # pathwise simulated short-rate accumulation and therefore the
            # daily/continuous overnight equivalent over this interval.
            overnight_return = (
                scenarios.money_market_accumulation(k, step) - 1.0
            )
            backing_income = (
                w_month_start * backing_base_for_interval * overnight_return
            )
            cfs["money_market_income"][:, step] += backing_income
            cfs["crediting_margin"][:, step] += backing_income
        just_elected[:] = False
        pre_cap_step_cashflows: Optional[dict[str, Array]] = None
        pre_cap_step_lapse: Optional[Array] = None
        # Payments are in arrears; the Election month has no payment.  Fixed
        # Income remains nominally unchanged except after an Excess Withdrawal.
        income_for_current_payment = income_annual.copy()

        # ---- anniversary crediting ------------------------------------ #
        if is_anniv:
            year_idx = anniv_step // STEPS_PER_YEAR  # caps of the period just ended
            previous_cap = as_path_array(
                reference_spec.cap(year_idx), name="previous crediting cap",
            )
            fund_ratio = reference_fund_level[:, step] / np.maximum(
                anniv_reference_level, 1e-300)
            credit = np.asarray(credited_return(
                fund_ratio - 1.0,
                Protection.TOTAL,
                reference_spec.cap(year_idx),
            ))
            interval_credit_rate = np.asarray(credit, dtype=float).copy()
            previous_reference_return = np.asarray(
                fund_ratio - 1.0, dtype=float).copy()
            previous_credited_return = np.asarray(credit, dtype=float).copy()
            # Customer-visible log gap between the complete Reference Fund
            # and the credited factor for the period just ended.  Under Total
            # Protection it is positive principally when the Reference-Fund
            # return exceeds the contractual cap.  Insurer backing assets and
            # hedge P&L are deliberately excluded.  The governed Base and High
            # bases activate the uncalibrated excess-hazard proxy; Low disables
            # it.
            performance_shortfall = np.maximum(
                np.log(np.maximum(fund_ratio, 1.0e-300))
                - np.log1p(np.maximum(credit, -1.0 + 1.0e-15)),
                0.0,
            )
            new_iv = np.where(
                growth | income,
                iv_frame * (1.0 + credit),
                0.0,
            )

            if not config.dva_enabled:
                grow_cash = scenarios.money_market_accumulation(
                    anniv_step, step,
                )
                customer_package = reference_customer_package_value(anniv_step)
                financing_margin = iv_frame * (
                    (1.0 - customer_package) * grow_cash - 1.0
                )
                cfs["contract_financing_margin"][:, step] += w * np.where(
                    growth | income,
                    financing_margin,
                    0.0,
                )

            if config.crediting_margin_enabled:
                # Only the explicit uncapped hedge retains performance above
                # the customer's cap.  It has already incurred the higher
                # long-call fair premium at the start of this crediting year.
                retained_rate = np.asarray(retained_excess_return(
                    previous_reference_return,
                    reference_spec.cap(year_idx),
                    config.hedge_cap_leg_mode,
                ))
                gain = w * np.where(
                    growth | income,
                    iv_frame * retained_rate,
                    0.0,
                )
                cfs["hedge_gain"][:, step] += gain
                cfs["crediting_margin"][:, step] += gain

            iv_frame = np.maximum(new_iv, 0.0)
            iv = iv_frame.copy()

            complete_growth_years = np.where(growth, complete_growth_years + 1,
                                             complete_growth_years)
            free_wd_used[:] = 0.0
            anniv_reference_level = reference_fund_level[:, step].copy()
            anniv_step = step

        # ---- intra-year DVA value -------------------------------------- #
        if config.dva_enabled and not is_anniv:
            tau = (STEPS_PER_YEAR - (step - anniv_step)) / STEPS_PER_YEAR
            iv = iv_frame * package_and_zcb(step, tau, phase)
        elif not config.dva_enabled and not is_anniv:
            iv = iv_frame.copy()

        alive_mask = phase < Phase.TERMINATED.value

        # ---- daily fee subledger ---------------------------------------- #
        # The monthly market grid supplies a piecewise-constant proxy for the
        # administrative daily Account-Value base.  Exact calendar days are
        # then accrued under ACT/365F.  Accrual is not an insurer cash inflow.
        fee_product_accrued += (
            fee_base_for_interval * product.fees.product_fee
            * fee_day_fractions[k]
        )
        fee_lip_accrued += (
            fee_base_for_interval * product.fees.lifetime_income_premium
            * fee_day_fractions[k]
        )
        if is_anniv:
            # Contractual order: annual credit, then fee posting, then Income
            # Election.  Only collected amounts enter the fee cashflows.
            post_fee_subledger(step)

        # APS commencement is a transaction-date state change and therefore
        # locks the post-fee Investment Value on this monthly grid point.
        activate_aps(step >= aps_start_step, step, t)

        if is_anniv:
            partial_wd_used[:] = 0.0
            mwv_at_anniv = _aps_max_withdrawal(
                product, cas_base, t, cas_start_t, cas_le, cas_wd, aps_active)
            wd_limit_base[:] = np.where(
                phase == Phase.GROWTH.value,
                np.where(aps_active, np.minimum(iv, mwv_at_anniv), iv),
                wd_limit_base)

        # ---- death decrement before the payment date ---------------------- #
        # Income is monthly in arrears and ceases on death.  The death benefit
        # is therefore based on the pre-payment IV, while only survivors to the
        # payment date receive this month's instalment.
        if pathwise_joint_life:
            if mortality_rng is None or dec.q_spouse_m is None:
                raise RuntimeError(
                    "Pathwise Joint-Life mortality was not initialised."
            )
            primary_before = primary_alive.copy()
            spouse_before = spouse_alive.copy()
            primary_mortality_draw = mortality_rng.random(n_paths)
            spouse_mortality_draw = mortality_rng.random(n_paths)
            primary_died = (
                alive_mask
                & primary_before
                & (primary_mortality_draw < dec.q_primary_m[k])
            )
            spouse_died = (
                alive_mask
                & spouse_before
                & (spouse_mortality_draw < dec.q_spouse_m[k])
            )
            primary_alive = primary_before & ~primary_died
            spouse_alive = spouse_before & ~spouse_died

            growth_before_election = phase == Phase.GROWTH.value
            income_before_election = income_at_interval_start
            continue_joint = (
                income_before_election
                & joint_income_cover
                & (
                    policy.spouse_death_election
                    == SpouseDeathElection.CONTINUE_INCOME
                )
            )
            last_survivor_died = (
                continue_joint & ~primary_alive & ~spouse_alive
            )
            primary_termination = (
                (growth_before_election | (income_before_election & ~continue_joint))
                & primary_died
            )
            terminating_death = alive_mask & (
                last_survivor_died | primary_termination
            )

            death_fee_product, death_fee_lip, death_post_fee_av = fee_settlement(iv)
            death_ben = death_post_fee_av
            if policy.age_pension_plus:
                cap_db = _aps_death_cap(
                    product, cas_base, t, cas_start_t, cas_le,
                    cas_wd, aps_active,
                )
                death_ben = np.where(
                    aps_active, np.minimum(death_ben, cap_db), death_ben
                )
                cfs["aps_retained"][:, step] += w * terminating_death * np.where(
                    aps_active, death_post_fee_av - death_ben, 0.0
                )
            cfs["fees_product"][:, step] += (
                w * terminating_death * death_fee_product
            )
            cfs["fees_lip"][:, step] += w * terminating_death * death_fee_lip
            cfs["death_benefits"][:, step] += w * terminating_death * death_ben

            iv = np.where(terminating_death, 0.0, iv)
            iv_frame = np.where(terminating_death, 0.0, iv_frame)
            income_annual = np.where(terminating_death, 0.0, income_annual)
            fee_product_accrued = np.where(
                terminating_death, 0.0, fee_product_accrued
            )
            fee_lip_accrued = np.where(
                terminating_death, 0.0, fee_lip_accrued
            )
            phase = np.where(
                terminating_death, Phase.TERMINATED.value, phase
            ).astype(np.int8)
            w = np.where(terminating_death, 0.0, w)
        else:
            q_m = np.full(n_paths, dec.q_primary_m[k])
            if (policy.spouse and dec.q_spouse_m is not None
                    and policy.spouse_death_election == SpouseDeathElection.CONTINUE_INCOME):
                # Joint cover starts at the election timestamp.  The mortality
                # decrement for the interval ending at that timestamp remains a
                # Primary-Life decrement; Last-Survivor mortality starts with
                # the following monthly interval.
                income_spouse = income_at_interval_start
                if income_spouse.any():
                    s1 = joint_surv_primary
                    s2 = joint_surv_spouse
                    s_ls = s1 + s2 - s1 * s2
                    s1_next = s1 * (1.0 - dec.q_primary_m[k])
                    s2_next = s2 * (1.0 - dec.q_spouse_m[k])
                    s_ls_next = s1_next + s2_next - s1_next * s2_next
                    q_joint = 1.0 - s_ls_next / np.maximum(s_ls, 1e-300)
                    q_m = np.where(income_spouse, q_joint, q_m)
                    joint_surv_primary = np.where(
                        income_spouse, s1_next, joint_surv_primary
                    )
                    joint_surv_spouse = np.where(
                        income_spouse, s2_next, joint_surv_spouse
                    )
            q_m = np.where(alive_mask, q_m, 0.0)
            death_fee_product, death_fee_lip, death_post_fee_av = fee_settlement(iv)
            death_ben = death_post_fee_av
            if policy.age_pension_plus:
                cap_db = _aps_death_cap(product, cas_base, t, cas_start_t, cas_le,
                                        cas_wd, aps_active)
                death_ben = np.where(
                    aps_active, np.minimum(death_ben, cap_db), death_ben
                )
                cfs["aps_retained"][:, step] += w * q_m * np.where(
                    aps_active, death_post_fee_av - death_ben, 0.0)
            cfs["fees_product"][:, step] += w * q_m * death_fee_product
            cfs["fees_lip"][:, step] += w * q_m * death_fee_lip
            cfs["death_benefits"][:, step] += w * q_m * death_ben
            w = w * (1.0 - q_m)

        # ---- income election / new crediting period ---------------------- #
        # Expected deaths in the interval ending at an Anniversary belong to
        # the pre-election coverage state.  Surviving contracts elect Income
        # only after that decrement; the next crediting/DVA period is therefore
        # funded only for survivors.  This removes the former hybrid in which
        # Primary mortality was combined with post-election DVA state.
        classify_phase_cashflow_delta(
            step, step_start_cashflows, has_elected_income
        )
        election_boundary_cashflows = {
            key: values[:, step].copy() for key, values in cfs.items()
        }
        if is_anniv:
            growth = phase == Phase.GROWTH.value
            if growth.any():
                elect, take_up_probability, eligible, forced = (
                    income_election_decision(step, t, growth, True)
                )
                eligible_growth_exposure[:, step] = w * eligible
                income_take_up_probability[:, step] = take_up_probability
                income_election_events[:, step] = w * elect.astype(float)
                forced_income_election_events[:, step] = (
                    w * (elect & forced).astype(float)
                )
                if ((dynamic_take_up or policy_controlled_election)
                        and policy.age_pension_plus
                        and policy.funding_source == FundingSource.NON_SUPERANNUATION):
                    activate_aps(elect, step, t)
                elect_income(elect, step, t)
                has_elected_income[elect] = True
            pre_cap_step_cashflows = {
                key: values[:, step].copy() for key, values in cfs.items()
            }
            pre_cap_step_lapse = lapse_events[:, step].copy()
            observe_cap_decision(step, float(t))
            restart_dva_period(step)
            free_utilisation, excess_rate = wd_dynamic_rates(step, t)

        # This is an end-of-transaction-point state: contracts which elected
        # at this Anniversary are no longer counted in the subsequent Growth
        # interval, while the separate eligible exposure above remains the
        # correct pre-Election denominator.
        growth_exposure[:, step] = w * (
            phase == Phase.GROWTH.value
        ).astype(float)

        # ---- income payment (monthly, in arrears; first payment one month
        # after the income election, PDS section 13) ----------------------- #
        pay = np.where((phase == 1) & ~just_elected,
                       income_for_current_payment / STEPS_PER_YEAR, 0.0)
        from_iv = np.minimum(pay, iv)
        claim = pay - from_iv
        ratio_iv = np.divide(iv - from_iv, np.maximum(iv, 1e-300),
                             out=np.ones(n_paths), where=iv > 0)
        iv = iv - from_iv
        iv_frame = iv_frame * ratio_iv
        cfs["income_paid"][:, step] += w * pay
        cfs["guarantee_claims"][:, step] += w * claim
        exhausted_av = iv <= 1e-12
        # No-arrears convention: accrued but unposted fees are written off as
        # soon as Account Value is exhausted by regular income.
        fee_product_accrued = np.where(exhausted_av, 0.0, fee_product_accrued)
        fee_lip_accrued = np.where(exhausted_av, 0.0, fee_lip_accrued)

        # ---- read-only Income Bellman transition panel -------------------- #
        # The previous pre-action state is emitted only now, after the exact
        # mortality draw and next-boundary market state are known.  This is a
        # training observer; none of these future fields enters the policy's
        # IncomeActionDecisionContext above.
        if (
            income_transition_observer_method is not None
            and pending_income_transition is not None
        ):
            prior_state = pending_income_transition["state"]
            if not isinstance(prior_state, IncomeActionState):
                raise RuntimeError("Pending Income transition state is invalid.")
            (
                transition_death_probability,
                transition_primary_alive,
                transition_spouse_alive,
                transition_joint_cover,
                transition_joint_surv_primary,
                transition_joint_surv_spouse,
            ) = income_transition_mortality_shock(
                k,
                prior_state,
                primary_mortality_draw,
                spouse_mortality_draw,
            )
            idx = prior_state.path_index
            potential_phase = phase.copy()
            potential_primary_alive = primary_alive.copy()
            potential_spouse_alive = spouse_alive.copy()
            potential_joint_cover = joint_income_cover.copy()
            potential_joint_surv_primary = joint_surv_primary.copy()
            potential_joint_surv_spouse = joint_surv_spouse.copy()
            potential_phase[idx] = np.where(
                transition_death_probability >= 1.0 - 1.0e-15,
                Phase.TERMINATED.value,
                Phase.INCOME.value,
            ).astype(np.int8)
            potential_primary_alive[idx] = transition_primary_alive
            potential_spouse_alive[idx] = transition_spouse_alive
            potential_joint_cover[idx] = transition_joint_cover
            potential_joint_surv_primary[idx] = transition_joint_surv_primary
            potential_joint_surv_spouse[idx] = transition_joint_surv_spouse
            next_annuity_factor = annuity_factor_for_state(
                step,
                float(t),
                potential_phase,
                potential_primary_alive,
                potential_spouse_alive,
                potential_joint_cover,
                potential_joint_surv_primary,
                potential_joint_surv_spouse,
            )[idx]
            if config.dva_enabled:
                if is_anniv:
                    next_dva_factor = (
                        package_and_zcb(step, 1.0, potential_phase)
                        if step < n_steps
                        else np.ones(n_paths)
                    )
                else:
                    tau_to_anniversary = (
                        STEPS_PER_YEAR - (step - anniv_step)
                    ) / STEPS_PER_YEAR
                    next_dva_factor = package_and_zcb(
                        step, tau_to_anniversary, potential_phase
                    )
            else:
                next_dva_factor = np.ones(n_paths)
            if scenarios.variance is None:
                next_heston_variance = np.zeros(n_paths)
            else:
                next_heston_variance = np.asarray(
                    scenarios.variance[reference_spec.equity_index][:, step],
                    dtype=float,
                )
            next_announced_cap = as_path_array(
                reference_spec.cap(anniv_step // STEPS_PER_YEAR),
                name="announced crediting cap",
            )
            discount_ratio = np.divide(
                scenarios.discount[idx, step],
                np.maximum(
                    scenarios.discount[idx, prior_state.step], 1.0e-300
                ),
            )
            scenario_slice = IncomeMonthScenarioSlice(
                current_step=prior_state.step,
                next_step=int(step),
                current_duration_years=float(
                    pending_income_transition["duration_years"]
                ),
                next_duration_years=float(t),
                is_anniversary=bool(is_anniv),
                terminal_next=bool(step >= n_steps),
                fee_year_fraction=float(fee_day_fractions[k]),
                current_mva_factor=pending_income_transition["mva_factor"],
                current_annuity_factor=(
                    pending_income_transition["annuity_factor"]
                ),
                current_short_rate=pending_income_transition["short_rate"],
                current_zero_rate_5y=pending_income_transition["zero_rate_5y"],
                current_heston_variance=(
                    pending_income_transition["heston_variance"]
                ),
                anniversary_credit_rate=interval_credit_rate[idx],
                next_dva_factor=np.asarray(next_dva_factor, dtype=float)[idx],
                terminating_death_probability=transition_death_probability,
                next_primary_alive=transition_primary_alive,
                next_spouse_alive=transition_spouse_alive,
                next_joint_income_cover=transition_joint_cover,
                next_joint_survival_primary=transition_joint_surv_primary,
                next_joint_survival_spouse=transition_joint_surv_spouse,
                next_mva_factor=current_mva_signal(step, float(t))[idx],
                next_annuity_factor=next_annuity_factor,
                next_short_rate=scenarios.short_rate[idx, step],
                next_zero_rate_5y=as_path_array(
                    scenarios.zero_rate(step, 5.0), name="five-year zero rate",
                )[idx],
                next_heston_variance=next_heston_variance[idx],
                next_announced_cap=next_announced_cap[idx],
                next_reference_return=previous_reference_return[idx],
                next_credited_return=previous_credited_return[idx],
                next_performance_gap=performance_shortfall[idx],
                discount_ratio=discount_ratio,
            )
            income_transition_observer_method(
                state=prior_state,
                scenario_slice=scenario_slice,
            )

        pending_income_transition = None
        if income_transition_observer_method is not None and step < n_steps:
            transition_path_index = np.flatnonzero(
                (phase == Phase.INCOME.value) & (w > 0.0)
            ).astype(np.int64)
            if transition_path_index.size:
                transition_state = income_transition_state(
                    step, transition_path_index
                )
                if scenarios.variance is None:
                    current_heston_variance = np.zeros(n_paths)
                else:
                    current_heston_variance = np.asarray(
                        scenarios.variance[
                            reference_spec.equity_index
                        ][:, step],
                        dtype=float,
                    )
                pending_income_transition = {
                    "state": transition_state,
                    "duration_years": float(t),
                    "mva_factor": current_mva_signal(step, float(t))[
                        transition_path_index
                    ],
                    "annuity_factor": annuity_factor_at(step, float(t))[
                        transition_path_index
                    ],
                    "short_rate": scenarios.short_rate[
                        transition_path_index, step
                    ],
                    "zero_rate_5y": as_path_array(
                        scenarios.zero_rate(step, 5.0),
                        name="five-year zero rate",
                    )[transition_path_index],
                    "heston_variance": current_heston_variance[
                        transition_path_index
                    ],
                }

        # ---- scheduled partial withdrawals -------------------------------- #
        wb = behaviour.withdrawals
        wd_scheduled = wb.free_utilisation > 0.0 or wb.excess_rate > 0.0
        # Evaluate at the actual action boundary.  In annual mode this is
        # deliberately after the regular Income payment, just like the amount
        # and contractual eligibility checks applied below.
        if wb.frequency == "monthly" or is_anniv:
            free_utilisation, excess_rate = wd_dynamic_rates(step, float(t))
        if income_action_policy is None:
            # Keep the historical Static/Dynamic path byte-for-byte isolated
            # from the new optimal-action branch.
            if wd_scheduled and (wb.frequency == "monthly" or is_anniv):
                frac = (
                    1.0 / STEPS_PER_YEAR
                    if wb.frequency == "monthly"
                    else 1.0
                )
                _apply_partial_withdrawals(
                    product, policy, scenarios, step, t, iv,
                    iv_frame, phase, aps_active, cas_base,
                    cas_start_t, cas_le, cas_wd, free_wd_used,
                    partial_wd_used, wd_limit_base,
                    income_annual, w, cfs, wb, issue_zero, P0,
                    fraction=frac,
                    free_utilisation=free_utilisation,
                    excess_rate=excess_rate,
                )
        elif (
            product.allows_growth_withdrawals
            and wd_scheduled
            and (wb.frequency == "monthly" or is_anniv)
        ):
            # The unified hook owns Income withdrawals only.  If another
            # product explicitly permits Growth withdrawals, preserve those
            # pre-existing Behaviour assumptions without allowing them to
            # leak into Income paths.
            frac = (
                1.0 / STEPS_PER_YEAR
                if wb.frequency == "monthly"
                else 1.0
            )
            growth_mask = phase == Phase.GROWTH.value
            _apply_partial_withdrawals(
                product, policy, scenarios, step, t, iv,
                iv_frame, phase, aps_active, cas_base,
                cas_start_t, cas_le, cas_wd, free_wd_used,
                partial_wd_used, wd_limit_base,
                income_annual, w, cfs, wb, issue_zero, P0,
                fraction=frac,
                free_utilisation=np.where(
                    growth_mask, free_utilisation, 0.0
                ),
                excess_rate=np.where(
                    growth_mask, excess_rate, 0.0
                ),
            )

        income_action_full_mask = np.zeros(n_paths, dtype=bool)
        if (
            income_action_policy is not None
            and step < n_steps
            and np.any((phase == Phase.INCOME.value) & (w > 0.0))
        ):
            action_context = income_action_context(step, float(t))
            (
                income_action_partial_mask,
                income_action_full_mask,
                income_action_partial_gross,
            ) = choose_income_action(action_context)
            if income_action_partial_mask.any():
                (
                    iv,
                    iv_frame,
                    income_annual,
                    income_action_partial_cash,
                    income_action_partial_mva,
                ) = _income_partial_action_values(
                    iv,
                    iv_frame,
                    income_annual,
                    income_action_partial_gross,
                    current_mva_signal(step, float(t)),
                )
                cfs["partial_withdrawals"][:, step] += (
                    w * income_action_partial_cash
                )
                cfs["mva_retained"][:, step] += (
                    w * income_action_partial_mva
                )

        # ---- lapse / full withdrawal --------------------------------------- #
        lapse_fee_product, lapse_fee_lip, lapse_post_fee_av = fee_settlement(iv)
        sv, mva_amt = _surrender_value(product, policy, scenarios, step, t,
                                       lapse_post_fee_av,
                                       free_wd_used, phase, aps_active,
                                       issue_zero, P0)
        if policy.age_pension_plus:
            mwv = _aps_max_withdrawal(product, cas_base, t, cas_start_t, cas_le,
                                      cas_wd, aps_active)
            # PDS pp. 34-35: an MVA is charged only when IV less MVA is the
            # binding withdrawal value.  If the APS maximum binds, the MVA is
            # not charged separately; the whole residual IV is an APS
            # forfeiture on full withdrawal.
            aps_binds = aps_active & (sv > mwv)
            sv = np.where(aps_binds, mwv, sv)
            mva_amt = np.where(aps_binds, 0.0, mva_amt)
            aps_forfeit = np.where(
                aps_binds,
                np.maximum(lapse_post_fee_av - mwv, 0.0),
                0.0,
            )
        else:
            aps_forfeit = np.zeros(n_paths)

        static_growth_lapse = 1.0 - (
            1.0 - dec.lapse_growth_a[k]) ** (1.0 / STEPS_PER_YEAR)
        if behaviour.use_dynamic:
            exit_ratio = np.divide(
                iv, np.maximum(sv, 1e-300), out=np.ones(n_paths), where=sv > 1e-12)
            exit_ratio = np.where((iv > 1e-12) & (sv <= 1e-12),
                                  np.exp(2.0), exit_ratio)
            growth_ordinary_prob, growth_performance_prob = (
                behaviour.dynamic.growth_cause_probabilities(
                    dec.lapse_growth_a[k], np.log(np.maximum(exit_ratio, 1e-300)),
                    gross_premium, 1.0 / STEPS_PER_YEAR,
                    performance_shortfall=performance_shortfall
                )
            )
            growth_ordinary_prob = np.asarray(growth_ordinary_prob, dtype=float)
            growth_performance_prob = np.asarray(
                growth_performance_prob, dtype=float
            )
            i_mask = phase == Phase.INCOME.value
            if i_mask.any():
                current_ordinary, current_performance = (
                    income_lapse_cause_probabilities_at(step, t, sv)
                )
                income_lapse_ordinary_prob = np.where(
                    i_mask, current_ordinary, income_lapse_ordinary_prob
                )
                income_lapse_performance_prob = np.where(
                    i_mask,
                    current_performance,
                    income_lapse_performance_prob,
                )
        else:
            growth_ordinary_prob = np.full(n_paths, static_growth_lapse)
            growth_performance_prob = np.zeros(n_paths)
            income_lapse_ordinary_prob = np.full(
                n_paths,
                1.0 - (1.0 - dec.lapse_income_a) ** (1.0 / STEPS_PER_YEAR),
            )
            income_lapse_performance_prob = np.zeros(n_paths)
        ordinary_lapse = np.where(
            phase == Phase.INCOME.value, income_lapse_ordinary_prob,
            np.where(phase == Phase.GROWTH.value, growth_ordinary_prob, 0.0),
        )
        performance_lapse = np.where(
            phase == Phase.INCOME.value, income_lapse_performance_prob,
            np.where(
                phase == Phase.GROWTH.value, growth_performance_prob, 0.0
            ),
        )
        if income_action_policy is not None:
            # The unified decision is deterministic conditional on each path.
            # It replaces both ordinary and performance-driven Income lapse;
            # Growth Behaviour probabilities remain exactly as configured.
            income_mask = phase == Phase.INCOME.value
            ordinary_lapse = np.where(
                income_mask,
                income_action_full_mask.astype(float),
                ordinary_lapse,
            )
            performance_lapse = np.where(
                income_mask, 0.0, performance_lapse
            )
        # Exact action boundary: everything currently in ``cfs[:, step]`` is
        # common to CONTINUE and FULL_WITHDRAWAL.  Settlement and midpoint
        # expense are booked only after this snapshot.
        pre_surrender_step_cashflows = {
            key: values[:, step].copy() for key, values in cfs.items()
        }
        if step == n_steps:
            final_pre_surrender_cashflows = pre_surrender_step_cashflows

        external_lapse_eligible: Optional[NDArray[np.bool_]] = None
        policy_action_point = bool(
            surrender_policy is not None
            and (not anniversary_only_surrender or is_anniv)
        )
        observer_action_point = bool(
            surrender_observer_method is not None
            and (not anniversary_only_surrender_observer or is_anniv)
        )
        decision_context: Optional[SurrenderDecisionContext] = None
        if policy_action_point or observer_action_point:
            guarantee_pv = guarantee_pv_at(step, t)
            guarantee_ratio = np.divide(
                guarantee_pv,
                np.maximum(np.asarray(sv, dtype=float), 1e-300),
                out=np.full(n_paths, np.exp(2.0)),
                where=np.asarray(sv, dtype=float) > 1e-12,
            )
            guarantee_log_mny = np.log(np.maximum(guarantee_ratio, 1e-300))
            guarantee_mny = np.exp(np.clip(guarantee_log_mny, -50.0, 50.0))
            positive_income_guarantee = (
                (phase == Phase.INCOME.value)
                & (guarantee_pv > 1.0e-12 * gross_premium)
            )
            zero_exit_with_guarantee = (
                (sv <= 1.0e-12 * gross_premium)
                & positive_income_guarantee
            )
            # These contractual gates define the admissible action set for
            # both an external policy and the observer's counterfactual value.
            action_lapse_eligible = (
                alive_mask
                & (w > 0.0)
                & (phase == Phase.INCOME.value)
                & ~just_elected
                & ~zero_exit_with_guarantee
            )
            if scenarios.variance is None:
                heston_variance = np.zeros(n_paths)
            else:
                heston_variance = np.asarray(
                    scenarios.variance[reference_spec.equity_index][:, step],
                    dtype=float,
                )
            zero_rate_5y = as_path_array(
                scenarios.zero_rate(step, 5.0), name="five-year zero rate",
            )
            decision_context = SurrenderDecisionContext(
                step=int(step),
                time=float(t),
                is_anniversary=bool(is_anniv),
                policy_year=int(step // STEPS_PER_YEAR),
                duration_years=float(t),
                phase=phase,
                account_value=iv,
                surrender_value=sv,
                locked_annual_income=income_annual,
                guarantee_pv=guarantee_pv,
                guarantee_moneyness=guarantee_mny,
                guarantee_log_moneyness=guarantee_log_mny,
                short_rate=scenarios.short_rate[:, step],
                zero_rate_5y=zero_rate_5y,
                heston_variance=heston_variance,
                announced_cap=as_path_array(
                    reference_spec.cap(anniv_step // STEPS_PER_YEAR),
                    name="announced crediting cap",
                ),
                previous_reference_return=previous_reference_return,
                previous_credited_return=previous_credited_return,
                performance_gap=performance_shortfall,
                inforce_weight=w,
                just_elected=just_elected,
                full_withdrawal_eligible=action_lapse_eligible,
                mva_factor=current_mva_signal(step, float(t)),
                attained_age=np.full(n_paths, policy.age + float(t)),
                primary_alive=primary_alive,
                spouse_alive=(
                    spouse_alive
                    if policy.spouse
                    else np.zeros(n_paths, dtype=bool)
                ),
            )

            if observer_action_point:
                if pre_cap_step_cashflows is None:
                    post_cap_common = {
                        key: values.copy()
                        for key, values in pre_surrender_step_cashflows.items()
                    }
                else:
                    post_cap_common = {
                        key: (
                            pre_surrender_step_cashflows[key]
                            - pre_cap_step_cashflows[key]
                        )
                        for key in CASHFLOW_KEYS
                    }
                exercise = action_lapse_eligible.astype(float)
                exercise_weight = w * exercise
                full_post_weight = w * (1.0 - exercise)
                full_action_cashflows = {
                    key: np.zeros(n_paths) for key in CASHFLOW_KEYS
                }
                full_action_cashflows["fees_product"] = (
                    exercise_weight * lapse_fee_product
                )
                full_action_cashflows["fees_lip"] = (
                    exercise_weight * lapse_fee_lip
                )
                full_action_cashflows["surrender_benefits"] = (
                    exercise_weight * sv
                )
                full_action_cashflows["mva_retained"] = (
                    exercise_weight * mva_amt
                )
                full_action_cashflows["aps_retained"] = (
                    exercise_weight * aps_forfeit
                )
                full_action_cashflows["expenses"] = (
                    post_action_expense_cashflow(
                        k,
                        w_month_start,
                        av_month_start,
                        full_post_weight,
                        iv,
                        alive_mask,
                    )
                )
                surrender_observer_method(context=SurrenderActionValueContext(
                    decision_context=decision_context,
                    post_cap_common_cashflows=post_cap_common,
                    full_withdrawal_post_action_cashflows=(
                        full_action_cashflows
                    ),
                ))

        if surrender_policy is not None:
            if not policy_action_point:
                surrender_mask = np.zeros(n_paths, dtype=bool)
                external_lapse_eligible = np.zeros(n_paths, dtype=bool)
            else:
                if decision_context is None:
                    raise RuntimeError(
                        "Surrender decision context was not initialised."
                    )
                external_lapse_eligible = (
                    decision_context.full_withdrawal_eligible
                )
                if context_aware_surrender:
                    decision = surrender_policy.surrender_mask(
                        context=decision_context
                    )
                else:
                    # Backward-compatible research hook.  New policies should
                    # opt into ``context`` so future ScenarioSet arrays are not
                    # in their information surface.
                    decision = surrender_policy.surrender_mask(
                        step=step,
                        time=float(t),
                        is_anniversary=bool(is_anniv),
                        phase=phase,
                        account_value=iv,
                        annual_income=income_annual,
                        surrender_value=sv,
                        inforce_weight=w,
                        scenarios=scenarios,
                    )
                surrender_mask = np.asarray(decision, dtype=bool)
            if surrender_mask.shape != (n_paths,):
                raise ValueError(
                    "surrender_policy must return one boolean per scenario path."
                )
            ordinary_lapse = surrender_mask.astype(float)
            performance_lapse = np.zeros(n_paths)
        # Income Election and Full Surrender cannot occur on the same event
        # timestamp.  Newly elected contracts first become lapse-eligible in
        # the following monthly interval.
        ordinary_lapse = np.where(just_elected, 0.0, ordinary_lapse)
        performance_lapse = np.where(just_elected, 0.0, performance_lapse)
        if surrender_policy is not None or not product.allows_growth_surrender:
            ordinary_lapse = np.where(
                phase == Phase.INCOME.value, ordinary_lapse, 0.0
            )
            performance_lapse = np.where(
                phase == Phase.INCOME.value, performance_lapse, 0.0
            )
        # A customer cannot rationally exchange a strictly positive remaining
        # lifetime-income guarantee for a zero surrender payment.  Ordinary
        # and performance-driven full surrender therefore stop once the
        # customer exit value is exhausted.
        positive_exit_value = sv > 1.0e-12 * gross_premium
        if surrender_policy is None:
            lapse_eligible = alive_mask & positive_exit_value & (
                (phase == Phase.INCOME.value)
                | ((phase == Phase.GROWTH.value) & (iv > 0.0))
            )
        else:
            if external_lapse_eligible is None:
                raise RuntimeError("External surrender eligibility was not initialised.")
            lapse_eligible = external_lapse_eligible
        ordinary_lapse = np.where(lapse_eligible, ordinary_lapse, 0.0)
        performance_lapse = np.where(lapse_eligible, performance_lapse, 0.0)
        base_lapse = ordinary_lapse + performance_lapse
        income_exposure[:, step] = w * (
            phase == Phase.INCOME.value
        ).astype(float)
        ordinary_lapse_probabilities[:, step] = ordinary_lapse
        performance_lapse_probabilities[:, step] = performance_lapse
        total_lapse_probabilities[:, step] = base_lapse
        lapse_events[:, step] = w * base_lapse
        ordinary_lapse_events[:, step] = w * ordinary_lapse
        performance_lapse_events[:, step] = w * performance_lapse
        cfs["fees_product"][:, step] += w * base_lapse * lapse_fee_product
        cfs["fees_lip"][:, step] += w * base_lapse * lapse_fee_lip
        cfs["surrender_benefits"][:, step] += w * base_lapse * sv
        cfs["mva_retained"][:, step] += w * base_lapse * mva_amt
        cfs["aps_retained"][:, step] += w * base_lapse * aps_forfeit
        w = w * (1.0 - base_lapse)
        if surrender_policy is not None:
            # A fitted annual FULL_WITHDRAWAL is a pathwise stopping action,
            # not a fractional statistical cohort decrement.  Preserve the
            # existing fee/MVA settlement above, then make the contractual
            # absorbing state explicit so no later Income, death benefit or
            # terminal value can arise on the exercised path.
            deterministic_full = surrender_mask & (
                base_lapse >= 1.0 - 1.0e-15
            )
            iv = np.where(deterministic_full, 0.0, iv)
            iv_frame = np.where(deterministic_full, 0.0, iv_frame)
            income_annual = np.where(
                deterministic_full, 0.0, income_annual
            )
            fee_product_accrued = np.where(
                deterministic_full, 0.0, fee_product_accrued
            )
            fee_lip_accrued = np.where(
                deterministic_full, 0.0, fee_lip_accrued
            )
            joint_income_cover = np.where(
                deterministic_full, False, joint_income_cover
            )
            phase = np.where(
                deterministic_full, Phase.TERMINATED.value, phase
            ).astype(np.int8)
        if income_action_policy is not None:
            # FULL is a deterministic unified action, not an expected lapse
            # cohort.  Its contract, guarantee and fee subledger terminate.
            # Statistical/no-hook lapse paths retain the historical weighted
            # cohort representation unchanged.
            deterministic_full = income_action_full_mask & (
                base_lapse >= 1.0 - 1.0e-15
            )
            iv = np.where(deterministic_full, 0.0, iv)
            iv_frame = np.where(deterministic_full, 0.0, iv_frame)
            income_annual = np.where(
                deterministic_full, 0.0, income_annual
            )
            fee_product_accrued = np.where(
                deterministic_full, 0.0, fee_product_accrued
            )
            fee_lip_accrued = np.where(
                deterministic_full, 0.0, fee_lip_accrued
            )
            joint_income_cover = np.where(
                deterministic_full, False, joint_income_cover
            )
            phase = np.where(
                deterministic_full, Phase.TERMINATED.value, phase
            ).astype(np.int8)

        # ---- expenses ----------------------------------------------------- #
        if exp_assum is not None:
            # Fixed expense inflation steps on the source assumption's annual
            # base date; an interval crossing that date is day-weighted.
            # Midpoint in-force exposure prorates terminating deaths and full
            # withdrawals within the monthly interval.
            cfs["expenses"][:, step] += post_action_expense_cashflow(
                k,
                w_month_start,
                av_month_start,
                w,
                iv,
                alive_mask,
            )

        # Terminate exhausted Growth contracts and their in-force exposure.
        # Without a locked Income guarantee, zero Account Value has no
        # remaining benefit or expense state.
        exhausted_growth = (phase == Phase.GROWTH.value) & (iv <= 0.0)
        phase = np.where(exhausted_growth, Phase.TERMINATED.value,
                         phase).astype(np.int8)
        w = np.where(exhausted_growth, 0.0, w)
        fee_product_accrued = np.where(
            exhausted_growth, 0.0, fee_product_accrued)
        fee_lip_accrued = np.where(exhausted_growth, 0.0, fee_lip_accrued)

        inforce[:, step] = w
        if step < n_steps:
            for key in CASHFLOW_KEYS:
                post_surrender_cfs[key][:, step] = (
                    cfs[key][:, step]
                    - pre_surrender_step_cashflows[key]
                )
        if pre_cap_step_cashflows is not None:
            for key in CASHFLOW_KEYS:
                post_cap_cfs[key][:, step] = (
                    cfs[key][:, step] - pre_cap_step_cashflows[key]
                )
            if pre_cap_step_lapse is None:
                raise RuntimeError("Anniversary lapse boundary was not initialised.")
            post_cap_lapse_events[:, step] = (
                lapse_events[:, step] - pre_cap_step_lapse
            )
        classify_phase_cashflow_delta(
            step, election_boundary_cashflows, has_elected_income
        )
        if iv_paths is not None:
            iv_paths[:, step] = iv
            income_paths[:, step] = income_annual
            phase_paths[:, step] = phase

    # A deliberately shortened horizon is a valuation truncation, not a
    # mortality event.  Settle accrued fees and report the remaining Account
    # Value in its own closeout bucket.  With the full lifetime horizon the
    # hard terminal-age mortality convention leaves this amount at zero.
    final = n_steps
    terminal_phase_boundary_cashflows = {
        key: values[:, final].copy() for key, values in cfs.items()
    }
    residual_mask = (phase < 2)
    terminal_fee_product, terminal_fee_lip, terminal_post_fee_av = \
        fee_settlement(iv)
    cfs["fees_product"][:, final] += w * np.where(
        residual_mask, terminal_fee_product, 0.0)
    cfs["fees_lip"][:, final] += w * np.where(
        residual_mask, terminal_fee_lip, 0.0)
    cfs["terminal_closeout"][:, final] += w * np.where(
        residual_mask, terminal_post_fee_av, 0.0)
    iv = np.where(residual_mask, 0.0, iv)
    iv_frame = np.where(residual_mask, 0.0, iv_frame)
    fee_product_accrued = np.where(residual_mask, 0.0, fee_product_accrued)
    fee_lip_accrued = np.where(residual_mask, 0.0, fee_lip_accrued)
    phase = np.where(
        residual_mask, Phase.TERMINATED.value, phase).astype(np.int8)
    w = np.where(residual_mask, 0.0, w)
    classify_phase_cashflow_delta(
        final, terminal_phase_boundary_cashflows, has_elected_income
    )
    inforce[:, final] = w
    if final_pre_surrender_cashflows is not None:
        for key in CASHFLOW_KEYS:
            post_surrender_cfs[key][:, final] = (
                cfs[key][:, final]
                - final_pre_surrender_cashflows[key]
            )
    if iv_paths is not None:
        iv_paths[:, final] = iv
        income_paths[:, final] = income_annual
        phase_paths[:, final] = phase

    return ProjectionResult(times=times[:n_steps + 1], scenarios=scenarios,
                            cashflows={k: v[:, :n_steps + 1] for k, v in cfs.items()},
                            inforce=inforce[:, :n_steps + 1],
                            lapse_events=lapse_events[:, :n_steps + 1],
                            iv_paths=None if iv_paths is None else iv_paths[:, :n_steps + 1],
                            income_paths=None if income_paths is None else income_paths[:, :n_steps + 1],
                            phase_paths=None if phase_paths is None else phase_paths[:, :n_steps + 1],
                            survival_primary=dec.surv_primary,
                            horizon_years=float(times[n_steps]),
                            ordinary_lapse_events=(
                                ordinary_lapse_events[:, :n_steps + 1]
                            ),
                            performance_lapse_events=(
                                performance_lapse_events[:, :n_steps + 1]
                            ),
                            ordinary_lapse_probabilities=(
                                ordinary_lapse_probabilities[:, :n_steps + 1]
                            ),
                            performance_lapse_probabilities=(
                                performance_lapse_probabilities[:, :n_steps + 1]
                            ),
                            total_lapse_probabilities=(
                                total_lapse_probabilities[:, :n_steps + 1]
                            ),
                            eligible_growth_exposure=(
                                eligible_growth_exposure[:, :n_steps + 1]
                            ),
                            income_take_up_probability=(
                                income_take_up_probability[:, :n_steps + 1]
                            ),
                            income_election_events=(
                                income_election_events[:, :n_steps + 1]
                            ),
                            forced_income_election_events=(
                                forced_income_election_events[:, :n_steps + 1]
                            ),
                            growth_exposure=(
                                growth_exposure[:, :n_steps + 1]
                            ),
                            income_exposure=(
                                income_exposure[:, :n_steps + 1]
                            ),
                            phase_cashflows={
                                key: value[:, :n_steps + 1]
                                for key, value in phase_cfs.items()
                            },
                            post_cap_cashflows={
                                key: value[:, :n_steps + 1]
                                for key, value in post_cap_cfs.items()
                            },
                            post_cap_lapse_events=(
                                post_cap_lapse_events[:, :n_steps + 1]
                            ),
                            post_surrender_cashflows={
                                key: value[:, :n_steps + 1]
                                for key, value in post_surrender_cfs.items()
                            })


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _cos_extra_var(scenarios, config, ix, step, horizon) -> Array:
    """Gaussian add-on variance for the Heston COS package pricer.

    Hull-White rate contribution (pathwise) plus the ``hedge_vol_spread``
    mapped onto the equivalent variance shift of the effective Heston vol when
    deriving the separate execution quote.  Contractual DVA calls pass a
    zero-spread configuration, so the spread has the same first-order quote
    effect as in the BS branch without changing customer value.
    """
    w = scenarios.rate_gauss_var(ix, step, horizon)
    if config.hedge_vol_spread != 0.0:
        hp = scenarios.config.heston[ix]
        v_t = scenarios.variance[ix][:, step]
        var_eq = np.asarray(hp.expected_integrated_variance(v_t, horizon),
                            dtype=float)
        sig_h = np.sqrt(np.maximum(var_eq, 1e-12))
        w = w + ((sig_h + config.hedge_vol_spread) ** 2 - sig_h ** 2) * horizon
    return w


def _package_only(product, scenarios, anniv_step, anniv_index_level, alloc_opts,
                  alloc_w, phase, config) -> Array:
    """Package value at anniversary start (no ZCB), for margin when DVA off."""
    n_paths = scenarios.n_paths
    r_cc = scenarios.forward_zero_cc(anniv_step, 1.0)
    year_idx = anniv_step // STEPS_PER_YEAR
    use_cos = scenarios.variance is not None and config.heston_cos

    def blended(opts, wts) -> Array:
        val = np.zeros(n_paths)
        for opt, wt in zip(opts, wts):
            if wt <= 0.0:
                continue
            ix = opt.index
            cap = product.caps.cap(opt, year_idx)
            if use_cos:
                hp = scenarios.config.heston[ix]
                v_t = scenarios.variance[ix][:, anniv_step]
                w = _cos_extra_var(scenarios, config, ix, anniv_step, 1.0)
                val += wt * np.asarray(heston_package_value(
                    1.0, opt.protection, cap, 1.0, r_cc,
                    scenarios.config.equity[ix].dividend_yield, v_t, hp, w))
            else:
                sig = scenarios.effective_bs_vol(ix, anniv_step, 1.0) \
                    + config.hedge_vol_spread
                val += wt * np.asarray(crediting_package_value(
                    1.0, opt.protection, cap, 1.0, r_cc,
                    scenarios.config.equity[ix].dividend_yield, sig))
        return val

    out = blended(alloc_opts, alloc_w)
    if (phase == Phase.INCOME.value).any():
        if len(alloc_opts) == 1 and alloc_opts[0] == INCOME_PHASE_OPTION:
            income_val = out              # allocation == income option: reuse
        else:
            income_val = blended([INCOME_PHASE_OPTION], np.array([1.0]))
        out = np.where(phase == Phase.INCOME.value, income_val, out)
    return out


def _surrender_value(product, policy, scenarios, step, t, iv, free_wd_used,
                     phase, aps_active, issue_zero, P0):
    """Full-withdrawal value = IV - MVA on the excess over the free amount."""
    n_paths = iv.shape[0]
    tau_rem = product.withdrawals.mva_period_years - t
    if tau_rem <= 0:
        return iv.copy(), np.zeros(n_paths)
    free_remaining = np.where((phase == 0) & ~aps_active,
                              np.maximum(product.withdrawals.free_withdrawal_pct_of_initial
                                         * P0 - free_wd_used, 0.0), 0.0)
    excess = np.maximum(iv - free_remaining, 0.0)
    z_now = scenarios.zero_rate(step, tau_rem)
    z0 = issue_zero(tau_rem)
    f = product.mva.factor(z0, z_now, tau_rem)
    raw = excess * f
    mva_amt = (np.clip(raw, 0.0, excess) if product.mva.only_reduces
               else np.minimum(raw, excess))
    return iv - mva_amt, mva_amt


def _aps_max_withdrawal(product, cas_base, t, cas_start_t, cas_le, cas_wd, aps_active):
    elapsed = np.maximum(t - cas_start_t, 0.0)
    linear = cas_base * np.clip(1.0 - elapsed / np.maximum(cas_le, 1e-9), 0.0, 1.0)
    return np.where(aps_active, np.maximum(linear - cas_wd, 0.0), np.inf)


def _aps_death_cap(product, cas_base, t, cas_start_t, cas_le, cas_wd, aps_active):
    elapsed = np.maximum(t - cas_start_t, 0.0)
    half = product.aps.death_benefit_full_fraction * np.maximum(cas_le, 1e-9)
    # The contractual value drops immediately to the MWV at Half Life
    # Expectancy and thereafter follows the original straight-line CAS run-off.
    before_withdrawals = np.where(
        elapsed < half, cas_base,
        cas_base * np.clip(1.0 - elapsed / np.maximum(cas_le, 1e-9), 0.0, 1.0))
    cap = np.maximum(before_withdrawals - cas_wd, 0.0)
    return np.where(aps_active, cap, np.inf)


def _aps_reduction_terms(iv, mwv, amount_withdrawn, mva_amount, mwv_binds):
    """Contractual APS proportional reduction terms (PDS pp. 68-69).

    ``amount_withdrawn`` is the cash received by the investor.  When the APS
    maximum is binding, MVA is zero and the percentage is cash / MWV.  When
    IV less MVA is binding, it is (cash + MVA) / IV.
    """
    iv_arr = np.asarray(iv, dtype=float)
    mwv_arr = np.asarray(mwv, dtype=float)
    cash = np.asarray(amount_withdrawn, dtype=float)
    mva = np.asarray(mva_amount, dtype=float)
    binds = np.asarray(mwv_binds, dtype=bool)
    pct_mwv = np.divide(cash, np.maximum(mwv_arr, 1e-300),
                        out=np.zeros_like(cash), where=mwv_arr > 0.0)
    pct_iv = np.divide(cash + mva, np.maximum(iv_arr, 1e-300),
                       out=np.zeros_like(cash), where=iv_arr > 0.0)
    pct = np.clip(np.where(binds, pct_mwv, pct_iv), 0.0, 1.0)
    iv_deduction = iv_arr * pct
    aps_retained = np.where(binds,
                            np.maximum(iv_deduction - cash, 0.0), 0.0)
    return pct, iv_deduction, aps_retained


def _apply_partial_withdrawals(product, policy, scenarios, step, t, iv, iv_frame,
                               phase, aps_active, cas_base, cas_start_t, cas_le,
                               cas_wd, free_wd_used, partial_wd_used,
                               wd_limit_base, income_annual, w, cfs,
                               wb, issue_zero, P0, fraction=1.0,
                               free_utilisation=None, excess_rate=None):
    """Scheduled free / excess withdrawals (in place).

    ``fraction`` scales the annualised utilisation to the event frequency
    (1 at anniversaries, 1/12 on the monthly schedule).  The optional
    pathwise ``free_utilisation`` and ``excess_rate`` values are the expected
    fractional-logit responses for the current policy year.  The 5% free
    allowance and cumulative 95% Growth-Phase limit are enforced per
    Anniversary year.
    """
    n_paths = iv.shape[0]
    growth = phase == 0
    free_u = (np.full(n_paths, wb.free_utilisation)
              if free_utilisation is None
              else np.broadcast_to(np.asarray(free_utilisation, dtype=float),
                                   (n_paths,)))
    excess_u = (np.full(n_paths, wb.excess_rate)
                if excess_rate is None
                else np.broadcast_to(np.asarray(excess_rate, dtype=float),
                                     (n_paths,)))
    if not product.allows_growth_withdrawals:
        free_u = np.zeros(n_paths)
        excess_u = np.where(phase == Phase.INCOME.value, excess_u, 0.0)
    min_partial = product.withdrawals.min_withdrawal
    min_residual = product.withdrawals.min_residual_value
    max_pct = product.withdrawals.max_withdrawal_pct_of_iv

    def annual_remaining() -> Array:
        return np.where(
            growth,
            np.maximum(max_pct * wd_limit_base - partial_wd_used, 0.0),
            np.inf)

    # free withdrawals (growth phase, no MVA, within 5% of initial investment)
    if np.any(free_u > 0.0):
        allow = product.withdrawals.free_withdrawal_pct_of_initial * P0
        target = free_u * allow * fraction
        remaining = np.maximum(allow - free_wd_used, 0.0)
        amt = np.where(growth & ~aps_active, np.minimum(target, remaining), 0.0)
        amt = np.minimum(amt, max_pct * iv)
        amt = np.minimum(amt, annual_remaining())
        amt = np.minimum(amt, np.maximum(iv - min_residual, 0.0))
        amt = np.where(amt >= min_partial, amt, 0.0)
        ratio = np.divide(iv - amt, np.maximum(iv, 1e-300), out=np.ones(n_paths), where=iv > 0)
        iv -= amt
        iv_frame *= ratio
        free_wd_used += amt
        partial_wd_used += np.where(growth, amt, 0.0)
        cfs["partial_withdrawals"][:, step] += w * amt

    # excess withdrawals (MVA in window; income reduction in income phase)
    if np.any(excess_u > 0.0):
        requested = excess_u * iv * fraction

        # PDS 15.2/15.3: in the growth phase (without Age Pension+) any
        # remaining Free Withdrawal Amount of the anniversary year is consumed
        # first and attracts no MVA; only the portion above it is an Excess
        # Withdrawal. The used-up part counts against the annual allowance.
        allow = product.withdrawals.free_withdrawal_pct_of_initial * P0
        free_remaining = np.where(growth & ~aps_active,
                                  np.maximum(allow - free_wd_used, 0.0), 0.0)
        tau_rem = product.withdrawals.mva_period_years - t
        if tau_rem > 0:
            z_now = scenarios.zero_rate(step, tau_rem)
            f = product.mva.factor(issue_zero(tau_rem), z_now, tau_rem)
            f = np.asarray(f, dtype=float)
        else:
            f = np.zeros(n_paths)

        def mva_on(gross: Array) -> Array:
            raw = np.asarray(gross, dtype=float) * f
            if product.mva.only_reduces:
                return np.clip(raw, 0.0, gross)
            return np.minimum(raw, gross)

        # Start with the non-APS contractual gross deduction (cash + MVA).
        gross = requested.copy()
        event_cap = np.where(growth, max_pct * iv, np.inf)
        gross = np.minimum(gross, event_cap)
        gross = np.minimum(gross, annual_remaining())
        gross = np.minimum(gross, np.maximum(iv - min_residual, 0.0))

        mwv = _aps_max_withdrawal(product, cas_base, t, cas_start_t, cas_le,
                                  cas_wd, aps_active)
        full_mva = mva_on(iv)
        mwv_binds = aps_active & ((iv - full_mva) > mwv)

        # If IV less MVA binds, the request remains a gross amount inclusive of
        # MVA.  Enforce a residual Withdrawal Value of at least AUD 2,000 on
        # both legs of the lower-of test.
        mva_ratio = np.divide(full_mva, np.maximum(iv, 1e-300),
                              out=np.zeros(n_paths), where=iv > 0.0)
        cash_ratio = 1.0 - mva_ratio
        max_gross_iv_resid = np.where(
            cash_ratio > 0.0,
            np.maximum(iv - min_residual / np.maximum(cash_ratio, 1e-300), 0.0),
            0.0)
        max_gross_mwv_resid = np.where(
            aps_active & (cash_ratio > 0.0),
            np.maximum((mwv - min_residual) / np.maximum(cash_ratio, 1e-300), 0.0),
            np.inf)
        aps_lower_base = np.minimum(iv, mwv)
        aps_event_cap = np.where(growth, max_pct * aps_lower_base, np.inf)
        aps_gross = np.minimum(requested, aps_event_cap)
        aps_gross = np.minimum(aps_gross, annual_remaining())
        aps_gross = np.minimum(aps_gross, max_gross_iv_resid)
        aps_gross = np.minimum(aps_gross, max_gross_mwv_resid)

        # If the APS maximum binds, no MVA is charged.  The requested amount is
        # cash; IV and future income are reduced by cash / MWV, which may be a
        # substantially larger percentage than cash / IV.
        aps_cash = requested.copy()
        aps_cash = np.minimum(aps_cash, aps_event_cap)
        aps_cash = np.minimum(aps_cash, annual_remaining())
        aps_cash = np.minimum(aps_cash, np.maximum(mwv - min_residual, 0.0))

        gross = np.where(aps_active & ~mwv_binds, aps_gross, gross)
        gross = np.where(gross >= min_partial, gross, 0.0)
        free_part = np.where(~aps_active, np.minimum(gross, free_remaining), 0.0)
        mva_amt = mva_on(gross - free_part)
        cash = gross - mva_amt

        aps_cash = np.where(aps_cash >= min_partial, aps_cash, 0.0)
        cash = np.where(mwv_binds, aps_cash, cash)
        mva_amt = np.where(mwv_binds, 0.0, mva_amt)

        pct_aps, aps_iv_deduction, aps_retained = _aps_reduction_terms(
            iv, mwv, cash, mva_amt, mwv_binds)
        iv_deduction = np.where(aps_active, aps_iv_deduction, gross)

        # Usage is defined inclusive of MVA.  In the MWV-binding branch MVA is
        # zero, hence usage is simply the cash amount withdrawn.
        usage = np.where(mwv_binds, cash, gross)

        iv_before = iv.copy()
        ratio = np.divide(iv - iv_deduction, np.maximum(iv, 1e-300),
                          out=np.ones(n_paths), where=iv > 0)
        iv -= iv_deduction
        iv_frame *= ratio
        free_wd_used += np.where(~aps_active, free_part, 0.0)
        partial_wd_used += np.where(growth, usage, 0.0)
        cas_wd += np.where(aps_active, cash, 0.0)

        red_non_aps = np.divide(gross, np.maximum(iv_before, 1e-300),
                                out=np.zeros(n_paths), where=iv_before > 0)
        red = np.where(aps_active, pct_aps, red_non_aps)
        income_annual *= np.where(phase == 1, np.clip(1.0 - red, 0.0, 1.0), 1.0)
        cfs["partial_withdrawals"][:, step] += w * cash
        cfs["mva_retained"][:, step] += w * mva_amt
        cfs["aps_retained"][:, step] += w * np.where(aps_active,
                                                      aps_retained, 0.0)
