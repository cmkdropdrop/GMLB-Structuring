"""Generic index-linked lifetime-income product specification.

The active product is the independent Australian case study documented in
``Produktdesign_Index_Linked_Lifetime_Income_Fallbeispiel.md``.  It has one
monthly rebalanced reference fund (50% global total-return equity and 50%
rolling five-year Australian-government zero-coupon bonds), Total Protection,
a fixed 6% annual Maximum Return and Fixed Lifetime Income only.

Some AGILE-era enums and rate-card columns remain as compatibility scaffolding
for older research callers.  They do not define the active customer's
investment exposure: the product-wide :class:`ReferenceFundSpec` does.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional, Sequence, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Index(str, Enum):
    AUS_EQUITY = "aus_equity"
    GLOBAL_EQUITY = "global_equity"


class Protection(str, Enum):
    TOTAL = "total"           # annual return floored at 0%
    PARTIAL_10 = "partial_10"  # first 10% of index losses absorbed


class InvestmentOption(str, Enum):
    """The four Protected Investment Options of the growth phase."""

    AUS_TP = "aus_tp"
    AUS_PP10 = "aus_pp10"
    GLOBAL_TP = "global_tp"
    GLOBAL_PP10 = "global_pp10"

    @property
    def index(self) -> Index:
        return Index.AUS_EQUITY if self in (InvestmentOption.AUS_TP, InvestmentOption.AUS_PP10) \
            else Index.GLOBAL_EQUITY

    @property
    def protection(self) -> Protection:
        return Protection.TOTAL if self in (InvestmentOption.AUS_TP, InvestmentOption.GLOBAL_TP) \
            else Protection.PARTIAL_10


class IncomeType(str, Enum):
    FIXED = "fixed"
    RISING = "rising"


class SpouseDeathElection(str, Enum):
    """Benefit path when the Life Insured dies after Spouse Income election."""

    CONTINUE_INCOME = "continue_income"
    LUMP_SUM = "lump_sum"


class Phase(int, Enum):
    GROWTH = 0
    INCOME = 1
    TERMINATED = 2


class Sex(str, Enum):
    MALE = "M"
    FEMALE = "F"


class FundingSource(str, Enum):
    """Funding basis relevant to the Age Pension+ commencement rules."""

    NON_SUPERANNUATION = "non_superannuation"
    SUPERANNUATION = "superannuation"


# The option whose credited returns drive the account and the Rising-Income
# ratchet during the lifetime income phase (PDS section 12).
INCOME_PHASE_OPTION = InvestmentOption.AUS_TP


# ---------------------------------------------------------------------------
# Generic reference fund
# ---------------------------------------------------------------------------

FIXED_REFERENCE_FUND_CAP = 0.06
GENERIC_GUARANTEED_MIN_CAP = 0.0025


@dataclass(frozen=True)
class ReferenceFundSpec:
    """Contractual reference fund of the generic case-study product.

    The strict validation is intentional.  These are product rules, not
    market-model parameters or inferred model-point allocations.
    """

    equity_index: Index = Index.GLOBAL_EQUITY
    equity_weight: float = 0.50
    bond_tenor_years: float = 5.0
    rebalance_frequency_months: int = 1
    maximum_return: float = FIXED_REFERENCE_FUND_CAP
    guaranteed_minimum_cap: float = GENERIC_GUARANTEED_MIN_CAP
    specification_vintage: str = "generic-case-study-2026-07-12"
    #: Optional non-contractual override for design and sensitivity runs.  The
    #: contractual ``maximum_return`` remains fixed at 6% and is retained in
    #: the assumption fingerprint and run manifest.
    scenario_maximum_return: Optional[float] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "equity_index", Index(self.equity_index))
        values = np.asarray([
            self.equity_weight,
            self.bond_tenor_years,
            self.maximum_return,
            self.guaranteed_minimum_cap,
        ], dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError("Reference-fund parameters must be finite.")
        if self.equity_index != Index.GLOBAL_EQUITY:
            raise ValueError("The generic reference fund must use Global Equity.")
        if not np.isclose(self.equity_weight, 0.50, rtol=0.0, atol=1e-12):
            raise ValueError("The generic reference fund must be 50% equity / 50% bonds.")
        if not np.isclose(self.bond_tenor_years, 5.0, rtol=0.0, atol=1e-12):
            raise ValueError("The generic bond sleeve must have constant five-year tenor.")
        if self.rebalance_frequency_months != 1:
            raise ValueError("The generic reference fund must rebalance monthly.")
        if not np.isclose(self.maximum_return, FIXED_REFERENCE_FUND_CAP,
                          rtol=0.0, atol=1e-12):
            raise ValueError("The contractual Maximum Return is fixed at 6%.")
        if not np.isclose(self.guaranteed_minimum_cap, GENERIC_GUARANTEED_MIN_CAP,
                          rtol=0.0, atol=1e-12):
            raise ValueError("The Guaranteed Minimum Cap is fixed at 0.25%.")
        if self.maximum_return < self.guaranteed_minimum_cap:
            raise ValueError("Maximum Return cannot be below its guaranteed minimum.")
        if not str(self.specification_vintage).strip():
            raise ValueError("Reference-fund specification_vintage must not be empty.")
        if self.scenario_maximum_return is not None and (
                not np.isfinite(self.scenario_maximum_return)
                or not 0.0 <= self.scenario_maximum_return <= 1.0):
            raise ValueError(
                "scenario_maximum_return must be between 0% and 100%."
            )

    @property
    def effective_maximum_return(self) -> float:
        """Maximum Return used by the projection, including a scenario override."""
        if self.scenario_maximum_return is not None:
            return float(self.scenario_maximum_return)
        return float(self.maximum_return)

    def cap(self, policy_year: int) -> float:
        """Return the effective constant cap; ``policy_year`` is validated."""
        if isinstance(policy_year, bool) or int(policy_year) != policy_year \
                or policy_year < 0:
            raise ValueError("policy_year must be a non-negative integer.")
        return self.effective_maximum_return


# ---------------------------------------------------------------------------
# Fees
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeeSpec:
    """Ongoing customer charges accrued on the administrative Account Value.

    Product Fee (0.30% p.a.) and Lifetime Income Premium (1.15% p.a.) accrue
    on an ACT/365F basis and are posted only at an Anniversary, immediately
    before a Full Withdrawal, or immediately before a terminating death
    benefit.  The projection owns the corresponding fee subledger.
    """

    product_fee: float = 0.0030
    lifetime_income_premium: float = 0.0115
    # Retained for compatibility with legacy overlays.  The generic product
    # rejects Age Pension+ and therefore never applies this waiver.
    lip_waived_in_income_phase_if_aps: bool = False

    def __post_init__(self) -> None:
        values = np.asarray([self.product_fee, self.lifetime_income_premium], dtype=float)
        if not np.all(np.isfinite(values)) or np.any(values < 0.0):
            raise ValueError("Fee rates must be finite and non-negative.")
        if float(np.sum(values)) >= 1.0:
            raise ValueError("Combined annual fee rates must be below 100%.")
        if not isinstance(self.lip_waived_in_income_phase_if_aps, (bool, np.bool_)):
            raise ValueError("lip_waived_in_income_phase_if_aps must be boolean.")

    @property
    def total(self) -> float:
        return self.product_fee + self.lifetime_income_premium


# ---------------------------------------------------------------------------
# Caps / Maximum Returns
# ---------------------------------------------------------------------------

#: Published Maximum Returns for July 2026 (official AGILE rate sheet).
JULY_2026_CAPS: Mapping[InvestmentOption, float] = MappingProxyType({
    InvestmentOption.AUS_TP: 0.0620,
    InvestmentOption.AUS_PP10: 0.1300,
    InvestmentOption.GLOBAL_TP: 0.0600,
    InvestmentOption.GLOBAL_PP10: 0.1280,
})

#: Published Guaranteed Minimums for July 2026.  These are fixed for a policy
#: at its Commencement Date and must be replaced by the Investor-Certificate
#: values when valuing an in-force contract.
DEFAULT_GUARANTEED_MIN_CAPS: Mapping[InvestmentOption, float] = MappingProxyType({
    InvestmentOption.AUS_TP: 0.0025,
    InvestmentOption.AUS_PP10: 0.0050,
    InvestmentOption.GLOBAL_TP: 0.0025,
    InvestmentOption.GLOBAL_PP10: 0.0050,
})


@dataclass(frozen=True)
class CapSchedule:
    """Maximum Returns per option and policy year.

    Caps are reset annually by the insurer, subject to the guaranteed minimum
    recorded in the Investor Certificate. The engine supports:

    * constant caps (default, current rate sheet),
    * an explicit per-year schedule,
    * a multiplicative stress on all caps (used by sensitivities /
      cap-repricing scenarios).
    """

    initial: Mapping[InvestmentOption, float] = field(
        default_factory=lambda: dict(JULY_2026_CAPS))
    guaranteed_min: Mapping[InvestmentOption, float] = field(
        default_factory=lambda: dict(DEFAULT_GUARANTEED_MIN_CAPS))
    #: Optional {option: sequence of caps by policy year}; overrides `initial`.
    schedule: Optional[Mapping[InvestmentOption, Sequence[float]]] = None
    #: Additive shift applied to every cap (after schedule), floored at the
    #: guaranteed minimum. Used for cap-repricing sensitivities.
    shift: float = 0.0

    def __post_init__(self) -> None:
        initial = {InvestmentOption(k): float(v) for k, v in self.initial.items()}
        floors = {InvestmentOption(k): float(v) for k, v in self.guaranteed_min.items()}
        required = set(InvestmentOption)
        if set(initial) != required or set(floors) != required:
            raise ValueError("Caps and guaranteed minima must contain all four options.")
        values = np.asarray([*initial.values(), *floors.values(), self.shift], dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError("Caps, floors and shifts must be finite.")
        if any(v < 0.0 for v in initial.values()) or any(v < 0.0 for v in floors.values()):
            raise ValueError("Caps and guaranteed minima must be non-negative.")
        if any(initial[o] < floors[o] for o in required):
            raise ValueError("Initial caps cannot be below their guaranteed minima.")
        schedule = None
        if self.schedule is not None:
            schedule_dict = {}
            for key, seq in self.schedule.items():
                option = InvestmentOption(key)
                vals = tuple(float(v) for v in seq)
                if not vals or not np.all(np.isfinite(vals)) or any(v < 0.0 for v in vals):
                    raise ValueError("Every cap schedule must be non-empty, finite and non-negative.")
                schedule_dict[option] = vals
            schedule = MappingProxyType(schedule_dict)
        object.__setattr__(self, "initial", MappingProxyType(initial))
        object.__setattr__(self, "guaranteed_min", MappingProxyType(floors))
        object.__setattr__(self, "schedule", schedule)

    def cap(self, option: InvestmentOption, policy_year: int) -> float:
        option = InvestmentOption(option)
        if int(policy_year) != policy_year or policy_year < 0:
            raise ValueError("policy_year must be a non-negative integer.")
        if self.schedule is not None and option in self.schedule:
            seq = self.schedule[option]
            base = float(seq[min(policy_year, len(seq) - 1)])
        else:
            base = float(self.initial[option])
        return max(base + self.shift, float(self.guaranteed_min[option]))

    def with_shift(self, shift: float) -> "CapSchedule":
        return replace(self, shift=self.shift + shift)


# ---------------------------------------------------------------------------
# Lifetime income rates
# ---------------------------------------------------------------------------

# Official July-2026 rows.  Columns after age are, in order:
# non-APS single rising/fixed, non-APS spouse rising/fixed,
# APS single rising/fixed, APS spouse rising/fixed, escalator rising/fixed.
# Values in the source flyer are percentages; they are converted once here.
_JULY_2026_MALE_PCT = (
    (50, 2.85, 6.00, 2.35, 5.45, 2.85, 6.00, 2.35, 5.45, .15, .20),
    (51, 2.90, 6.05, 2.40, 5.50, 2.90, 6.05, 2.40, 5.50, .15, .20),
    (52, 2.95, 6.10, 2.45, 5.55, 2.95, 6.10, 2.45, 5.55, .15, .20),
    (53, 3.00, 6.15, 2.50, 5.60, 3.00, 6.15, 2.50, 5.60, .15, .20),
    (54, 3.05, 6.20, 2.55, 5.65, 3.05, 6.20, 2.55, 5.65, .15, .20),
    (55, 3.10, 6.25, 2.60, 5.70, 3.10, 6.25, 2.60, 5.70, .20, .25),
    (56, 3.20, 6.30, 2.75, 5.75, 3.20, 6.30, 2.75, 5.75, .20, .25),
    (57, 3.30, 6.40, 2.80, 5.80, 3.30, 6.40, 2.80, 5.80, .20, .25),
    (58, 3.40, 6.45, 2.85, 5.85, 3.40, 6.45, 2.85, 5.85, .20, .25),
    (59, 3.50, 6.50, 2.90, 5.90, 3.50, 6.50, 2.90, 5.90, .20, .25),
    (60, 3.55, 6.55, 2.95, 5.95, 3.55, 6.55, 2.95, 5.95, .25, .30),
    (61, 3.70, 6.65, 3.10, 6.05, 3.70, 6.65, 3.10, 6.05, .25, .30),
    (62, 3.80, 6.75, 3.20, 6.15, 3.80, 6.75, 3.20, 6.15, .25, .30),
    (63, 3.95, 6.85, 3.35, 6.25, 3.95, 6.85, 3.35, 6.25, .25, .30),
    (64, 4.05, 6.95, 3.50, 6.30, 4.05, 6.95, 3.50, 6.30, .25, .30),
    (65, 4.15, 7.05, 3.55, 6.35, 4.20, 7.10, 3.55, 6.35, .30, .35),
    (66, 4.25, 7.15, 3.60, 6.40, 4.30, 7.20, 3.60, 6.40, .30, .35),
    (67, 4.40, 7.30, 3.80, 6.55, 4.45, 7.35, 3.80, 6.55, .30, .35),
    (68, 4.55, 7.45, 3.95, 6.70, 4.60, 7.50, 3.95, 6.70, .30, .35),
    (69, 4.65, 7.50, 4.05, 6.75, 4.80, 7.60, 4.05, 6.75, .30, .35),
    (70, 4.75, 7.55, 4.10, 6.80, 4.95, 7.70, 4.10, 6.80, .35, .40),
    (71, 4.95, 7.75, 4.35, 7.00, 5.15, 7.90, 4.35, 7.05, .35, .40),
    (72, 5.15, 7.95, 4.55, 7.20, 5.35, 8.10, 4.60, 7.25, .35, .40),
    (73, 5.40, 8.20, 4.80, 7.45, 5.60, 8.35, 4.90, 7.60, .35, .40),
    (74, 5.65, 8.40, 5.05, 7.65, 5.85, 8.55, 5.15, 7.90, .35, .40),
    (75, 5.80, 8.55, 5.20, 7.80, 6.15, 8.85, 5.40, 8.05, .40, .45),
    (76, 5.95, 8.65, 5.30, 7.90, 6.40, 9.10, 5.65, 8.20, .40, .45),
    (77, 6.25, 8.90, 5.60, 8.15, 6.70, 9.40, 5.95, 8.60, .40, .45),
    (78, 6.50, 9.15, 5.85, 8.40, 7.00, 9.70, 6.25, 8.95, .40, .45),
    (79, 6.70, 9.30, 6.10, 8.60, 7.35, 10.10, 6.60, 9.30, .40, .45),
    (80, 6.85, 9.45, 6.30, 8.80, 7.70, 10.45, 6.95, 9.65, .45, .50),
)

_JULY_2026_FEMALE_PCT = (
    (50, 2.70, 5.85, 2.30, 5.40, 2.70, 5.85, 2.30, 5.40, .15, .20),
    (51, 2.75, 5.90, 2.35, 5.45, 2.75, 5.90, 2.35, 5.45, .15, .20),
    (52, 2.80, 5.95, 2.40, 5.50, 2.80, 5.95, 2.40, 5.50, .15, .20),
    (53, 2.85, 6.00, 2.45, 5.55, 2.85, 6.00, 2.45, 5.55, .15, .20),
    (54, 2.90, 6.05, 2.50, 5.60, 2.90, 6.05, 2.50, 5.60, .15, .20),
    (55, 2.95, 6.10, 2.55, 5.65, 2.95, 6.10, 2.55, 5.65, .20, .25),
    (56, 3.05, 6.15, 2.70, 5.70, 3.05, 6.15, 2.70, 5.70, .20, .25),
    (57, 3.15, 6.25, 2.75, 5.75, 3.15, 6.25, 2.75, 5.75, .20, .25),
    (58, 3.20, 6.30, 2.80, 5.80, 3.20, 6.30, 2.80, 5.80, .20, .25),
    (59, 3.30, 6.35, 2.85, 5.85, 3.30, 6.35, 2.85, 5.85, .20, .25),
    (60, 3.35, 6.40, 2.90, 5.90, 3.35, 6.40, 2.90, 5.90, .25, .30),
    (61, 3.45, 6.50, 3.05, 6.00, 3.45, 6.50, 3.05, 6.00, .25, .30),
    (62, 3.55, 6.55, 3.15, 6.10, 3.55, 6.55, 3.15, 6.10, .25, .30),
    (63, 3.70, 6.65, 3.30, 6.20, 3.70, 6.65, 3.30, 6.20, .25, .30),
    (64, 3.80, 6.75, 3.40, 6.25, 3.80, 6.75, 3.40, 6.25, .25, .30),
    (65, 3.90, 6.80, 3.45, 6.30, 3.90, 6.85, 3.45, 6.30, .30, .35),
    (66, 3.95, 6.85, 3.50, 6.35, 4.00, 6.95, 3.50, 6.35, .30, .35),
    (67, 4.10, 7.00, 3.70, 6.50, 4.15, 7.10, 3.70, 6.50, .30, .35),
    (68, 4.25, 7.10, 3.85, 6.65, 4.30, 7.20, 3.85, 6.65, .30, .35),
    (69, 4.40, 7.20, 3.95, 6.70, 4.45, 7.30, 3.95, 6.70, .30, .35),
    (70, 4.50, 7.25, 4.00, 6.75, 4.55, 7.40, 4.00, 6.75, .35, .40),
    (71, 4.70, 7.45, 4.25, 6.95, 4.75, 7.60, 4.25, 7.00, .35, .40),
    (72, 4.90, 7.60, 4.45, 7.15, 4.95, 7.75, 4.50, 7.20, .35, .40),
    (73, 5.10, 7.80, 4.70, 7.40, 5.20, 7.95, 4.80, 7.50, .35, .40),
    (74, 5.30, 8.00, 4.95, 7.60, 5.40, 8.15, 5.05, 7.80, .35, .40),
    (75, 5.50, 8.20, 5.10, 7.70, 5.65, 8.40, 5.30, 7.95, .40, .45),
    (76, 5.70, 8.35, 5.20, 7.80, 5.85, 8.65, 5.55, 8.10, .40, .45),
    (77, 5.95, 8.60, 5.45, 8.05, 6.15, 8.90, 5.85, 8.45, .40, .45),
    (78, 6.20, 8.85, 5.70, 8.25, 6.40, 9.15, 6.15, 8.80, .40, .45),
    (79, 6.40, 9.00, 5.95, 8.50, 6.75, 9.50, 6.50, 9.20, .40, .45),
    (80, 6.60, 9.15, 6.20, 8.70, 7.10, 9.85, 6.80, 9.55, .45, .50),
)


def _decimal_rate_rows(rows: Tuple[Tuple[float, ...], ...]) -> Tuple[Tuple[float, ...], ...]:
    return tuple((float(row[0]), *(float(x) / 100.0 for x in row[1:])) for row in rows)


JULY_2026_MALE_INCOME_RATES = _decimal_rate_rows(_JULY_2026_MALE_PCT)
JULY_2026_FEMALE_INCOME_RATES = _decimal_rate_rows(_JULY_2026_FEMALE_PCT)


@dataclass(frozen=True)
class IncomeRateTable:
    """Versioned Lifetime Income rate card reused by the generic case study.

    The official rate is fixed from the policy Commencement Date.  The
    Age-Based Rate uses age and gender *at policy commencement*, not age at
    income commencement.  For the Spouse option, the younger life at policy
    commencement supplies both age and gender.  Complete Growth-Phase years
    add the age- and Fixed/Rising-specific Annual Income Escalator.

    Rows can be replaced wholesale for another rate-card vintage without code
    changes.  ``base_rate_shift`` and ``escalator_multiplier`` are explicit
    modelling stresses; they are not contractual parameters.
    """

    male_rows: Tuple[Tuple[float, ...], ...] = JULY_2026_MALE_INCOME_RATES
    female_rows: Tuple[Tuple[float, ...], ...] = JULY_2026_FEMALE_INCOME_RATES
    rate_card_vintage: str = "2026-07"
    base_rate_shift: float = 0.0
    escalator_multiplier: float = 1.0
    max_escalator_years: Optional[int] = None

    def __post_init__(self) -> None:
        for name, rows in (("male_rows", self.male_rows), ("female_rows", self.female_rows)):
            arr = np.asarray(rows, dtype=float)
            if arr.ndim != 2 or arr.shape[1] != 11 or len(arr) < 2:
                raise ValueError(f"{name} must have 11 columns and at least two age rows.")
            if not np.all(np.isfinite(arr)) or np.any(np.diff(arr[:, 0]) <= 0):
                raise ValueError(f"{name} must be finite and strictly increasing by age.")
            if np.any(arr[:, 1:] < 0.0):
                raise ValueError(f"{name} rates and escalators must be non-negative.")
            object.__setattr__(self, name, tuple(tuple(float(x) for x in row) for row in arr))
        if not np.isfinite(self.base_rate_shift) or not np.isfinite(self.escalator_multiplier):
            raise ValueError("Income-rate stresses must be finite.")
        if self.escalator_multiplier < 0.0:
            raise ValueError("escalator_multiplier must be non-negative.")
        if self.max_escalator_years is not None and (
                isinstance(self.max_escalator_years, bool)
                or not isinstance(self.max_escalator_years, (int, np.integer))
                or self.max_escalator_years < 0):
            raise ValueError("max_escalator_years must be a non-negative integer or None.")

    def _rating_life(self, age: float, sex: Sex, spouse: bool,
                     spouse_age: Optional[float], spouse_sex: Optional[Sex]) -> tuple[float, Sex]:
        rating_age = float(age)
        rating_sex = Sex(sex)
        if spouse:
            if spouse_age is None or spouse_sex is None:
                raise ValueError("spouse_age and spouse_sex are required for Spouse rates.")
            if float(spouse_age) < rating_age:
                rating_age, rating_sex = float(spouse_age), Sex(spouse_sex)
        return rating_age, rating_sex

    def _interpolate(self, age: float, sex: Sex, column: int) -> float:
        rows = np.asarray(self.male_rows if Sex(sex) == Sex.MALE else self.female_rows)
        if age < rows[0, 0] or age > rows[-1, 0]:
            raise ValueError(f"Rating age {age} outside rate-card range "
                             f"[{rows[0, 0]}, {rows[-1, 0]}].")
        return float(np.interp(age, rows[:, 0], rows[:, column]))

    @staticmethod
    def _base_column(income_type: IncomeType, spouse: bool,
                     age_pension_plus: bool) -> int:
        # Row column 0 is age.  Each pair is Rising, Fixed.
        pair_start = 1 + (2 if spouse else 0) + (4 if age_pension_plus else 0)
        return pair_start + (1 if IncomeType(income_type) == IncomeType.FIXED else 0)

    def base_rate(self, age_at_policy_commencement: float, sex: Sex,
                  income_type: IncomeType, spouse: bool,
                  spouse_age: Optional[float] = None,
                  spouse_sex: Optional[Sex] = None,
                  age_pension_plus: bool = False) -> float:
        age, rating_sex = self._rating_life(age_at_policy_commencement, sex,
                                            spouse, spouse_age, spouse_sex)
        column = self._base_column(income_type, spouse, age_pension_plus)
        return max(self._interpolate(age, rating_sex, column) + self.base_rate_shift, 0.0)

    def annual_escalator(self, age_at_policy_commencement: float, sex: Sex,
                         income_type: IncomeType, spouse: bool,
                         spouse_age: Optional[float] = None,
                         spouse_sex: Optional[Sex] = None) -> float:
        age, rating_sex = self._rating_life(age_at_policy_commencement, sex,
                                            spouse, spouse_age, spouse_sex)
        column = 10 if IncomeType(income_type) == IncomeType.FIXED else 9
        return self._interpolate(age, rating_sex, column) * self.escalator_multiplier

    def lifetime_income_rate(self, age_at_policy_commencement: float, sex: Sex,
                             income_type: IncomeType, spouse: bool,
                             complete_growth_years: int,
                             spouse_age: Optional[float] = None,
                             spouse_sex: Optional[Sex] = None,
                             age_pension_plus: bool = False) -> float:
        years = int(complete_growth_years)
        if years < 0 or years != complete_growth_years:
            raise ValueError("complete_growth_years must be a non-negative integer.")
        if self.max_escalator_years is not None:
            years = min(years, self.max_escalator_years)
        base = self.base_rate(age_at_policy_commencement, sex, income_type, spouse,
                              spouse_age, spouse_sex, age_pension_plus)
        escalator = self.annual_escalator(age_at_policy_commencement, sex,
                                          income_type, spouse, spouse_age,
                                          spouse_sex)
        return base + escalator * years


# ---------------------------------------------------------------------------
# Withdrawals / MVA / Age Pension+
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WithdrawalRules:
    """Income-phase withdrawal mechanics of the generic case study."""

    # Growth withdrawals are contractually prohibited.  The structural zero
    # also prevents behaviour assumptions from recreating a free allowance.
    free_withdrawal_pct_of_initial: float = 0.0
    min_withdrawal: float = 100.0
    # No separate 95% cap applies in Income; the AUD 2,000 residual controls a
    # partial withdrawal.  One is retained as a harmless mathematical ceiling.
    max_withdrawal_pct_of_iv: float = 1.0
    min_residual_value: float = 2_000.0
    mva_period_years: float = 10.0

    def __post_init__(self) -> None:
        values = np.asarray([self.free_withdrawal_pct_of_initial, self.min_withdrawal,
                             self.max_withdrawal_pct_of_iv, self.min_residual_value,
                             self.mva_period_years], dtype=float)
        if not np.all(np.isfinite(values)) or np.any(values < 0.0):
            raise ValueError("Withdrawal parameters must be finite and non-negative.")
        if self.free_withdrawal_pct_of_initial > 1.0:
            raise ValueError("Free-withdrawal percentage cannot exceed 100%.")
        if not 0.0 < self.max_withdrawal_pct_of_iv <= 1.0:
            raise ValueError("Maximum partial-withdrawal percentage must be in (0, 1].")


@dataclass(frozen=True)
class MVASpec:
    """Market Value Adjustment model (PDS section 8).

    The PDS does not publish a closed formula; the engine uses the standard
    interest-rate based form

        MVA_factor(t) = 1 - [(1 + z_issue + spread) / (1 + z_t + spread)] ** tau

    where ``tau`` is the remaining time in the 10-year MVA window and ``z`` are
    zero rates for tenor tau (issue curve vs. current/pathwise curve). If rates
    rise after issue the factor is positive and the withdrawal value is
    reduced. ``only_reduces`` floors the adjustment at zero (no MVA gains),
    ``cost_loading`` adds a fixed proportional termination-cost charge and
    ``cost_loading_per_remaining_year`` supports the run-off shape visible in
    the PDS illustration.  Both remain calibration inputs: the PDS does not
    disclose Allianz's production MVA formula.  The neutral constructor keeps
    both cost loadings at zero for explicit tests/custom runs; the realistic
    base loading is supplied by ``load_cost_assumptions`` from the repository
    cost CSV.
    """

    only_reduces: bool = True
    cost_loading: float = 0.0
    cost_loading_per_remaining_year: float = 0.0
    spread: float = 0.0

    @classmethod
    def pds_illustrative_termination_loading(cls, **kwargs) -> "MVASpec":
        """Return the linear no-rate-move loading implied by PDS page 61.

        The illustrative 19-Jan-2026 PDS table has a 5.557% adjustment at the
        end of year 1 and zero at year 10, implying 0.61744% per remaining
        year.  This helper reproduces only that illustrative run-off component;
        it is not Allianz's undisclosed production MVA calibration.
        """
        if "cost_loading_per_remaining_year" in kwargs:
            raise ValueError("The illustrative per-year loading is set by this constructor.")
        return cls(cost_loading_per_remaining_year=0.05557 / 9.0, **kwargs)

    def __post_init__(self) -> None:
        if not isinstance(self.only_reduces, (bool, np.bool_)):
            raise ValueError("only_reduces must be boolean.")
        if not np.isfinite(self.cost_loading) \
                or not np.isfinite(self.cost_loading_per_remaining_year) \
                or not np.isfinite(self.spread):
            raise ValueError("MVA parameters must be finite.")
        if self.cost_loading < 0.0 or self.cost_loading_per_remaining_year < 0.0:
            raise ValueError("MVA cost loadings must be non-negative.")

    def factor(self, z_issue: float, z_now: float | np.ndarray,
               tau: float) -> float | np.ndarray:
        values = np.asarray(z_now, dtype=float)
        if not np.isfinite(z_issue) or not np.isfinite(tau) or not np.all(np.isfinite(values)):
            raise ValueError("MVA rates and tenor must be finite.")
        if (1.0 + z_issue + self.spread) <= 0.0 or np.any(
                1.0 + values + self.spread <= 0.0):
            raise ValueError("MVA rates plus spread must be greater than -100%.")
        if tau <= 0.0:
            return np.zeros_like(values) if np.ndim(z_now) else 0.0
        ratio = ((1.0 + z_issue + self.spread) /
                 (1.0 + values + self.spread)) ** float(tau)
        f = 1.0 - ratio
        f = f + self.cost_loading + self.cost_loading_per_remaining_year * float(tau)
        if self.only_reduces:
            f = np.clip(f, 0.0, 1.0)
        else:
            f = np.minimum(f, 1.0)
        return float(f) if np.ndim(z_now) == 0 else f


@dataclass(frozen=True)
class AgePensionPlusSpec:
    """Age Pension+ / Capital Access Schedule (CAS) limits (PDS section 16).

    * Maximum Withdrawal Value declines linearly from 100% of the Investment
      Value at election to zero at life expectancy; withdrawals reduce it
      dollar-for-dollar.
    * Maximum (lump-sum) Benefit on Death is 100% of the CAS base for the
      first half of the life-expectancy period, then declines linearly to zero
      (standard CAS design; configurable).
    * All withdrawals after election are Excess Withdrawals; no Free
      Withdrawal Amount applies.
    """

    death_benefit_full_fraction: float = 0.5  # fraction of LE with 100% death cap
    #: Australian Age Pension eligibility age. The Lifetime Income Premium is
    #: waived in the income phase only from the later of income commencement
    #: and this age (PDS 16.5 condition-of-release proxy).
    pension_age: float = 67.0

    def __post_init__(self) -> None:
        if not np.isfinite(self.death_benefit_full_fraction) or not np.isfinite(self.pension_age):
            raise ValueError("Age Pension+ parameters must be finite.")
        if not 0.0 <= self.death_benefit_full_fraction < 1.0:
            raise ValueError("death_benefit_full_fraction must be in [0, 1).")
        if self.pension_age < 0.0:
            raise ValueError("pension_age must be non-negative.")

    def max_withdrawal_value(self, base: float, elapsed: float, life_expectancy: float,
                             withdrawals_since_election: float) -> float:
        if life_expectancy <= 0:
            return 0.0
        linear = base * max(0.0, 1.0 - elapsed / life_expectancy)
        return max(0.0, linear - withdrawals_since_election)

    def max_death_benefit(self, base: float, elapsed: float, life_expectancy: float,
                          withdrawals_since_election: float = 0.0) -> float:
        if life_expectancy <= 0:
            return 0.0
        half = self.death_benefit_full_fraction * life_expectancy
        if elapsed < half:
            before_withdrawals = base
        else:
            # PDS: at Half Life Expectancy the death cap immediately becomes
            # the Maximum Withdrawal Value and then follows its straight-line
            # run-off, rather than declining from 100% to zero over the second
            # half of the period.
            before_withdrawals = base * max(0.0, 1.0 - elapsed / life_expectancy)
        return max(0.0, before_withdrawals - withdrawals_since_election)


# ---------------------------------------------------------------------------
# Product and policy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IndexLinkedLifetimeIncomeProduct:
    """Commercial specification of the generic lifetime-income case study."""

    reference_fund: ReferenceFundSpec = field(default_factory=ReferenceFundSpec)
    fees: FeeSpec = field(default_factory=FeeSpec)
    # Legacy four-option cap structure remains available to old research code,
    # but is not used by the active generic product projection.
    caps: CapSchedule = field(default_factory=CapSchedule)
    income_rates: IncomeRateTable = field(default_factory=IncomeRateTable)
    withdrawals: WithdrawalRules = field(default_factory=WithdrawalRules)
    mva: MVASpec = field(default_factory=MVASpec)
    aps: AgePensionPlusSpec = field(default_factory=AgePensionPlusSpec)
    min_investment: float = 20_000.0
    max_investment: float = 5_000_000.0
    min_entry_age: float = 50.0
    max_entry_age: float = 80.0
    min_years_before_income: int = 1
    automatic_income_start_age: float = 100.0
    product_id: str = "GENERIC_INDEX_LINKED_LIFETIME_INCOME"
    #: Continuous carry excluded from the published index level (annual, by
    #: index).  Both contractual underlyings are return indices -- S&P/ASX 200
    #: Total Return and MSCI World Net in AUD -- so the production default is
    #: zero.  A non-zero value must be an explicitly calibrated index carry,
    #: not the constituents' cash-dividend yield.
    dividend_yield: Mapping[Index, float] = field(
        default_factory=lambda: {Index.AUS_EQUITY: 0.0, Index.GLOBAL_EQUITY: 0.0})

    def __post_init__(self) -> None:
        limits = np.asarray([self.min_investment, self.max_investment,
                             self.min_entry_age, self.max_entry_age,
                             self.min_years_before_income,
                             self.automatic_income_start_age], dtype=float)
        if not np.all(np.isfinite(limits)):
            raise ValueError("Product limits must be finite.")
        if self.min_investment <= 0.0 or self.max_investment < self.min_investment:
            raise ValueError("Invalid product investment limits.")
        if self.min_entry_age < 0.0 or self.max_entry_age < self.min_entry_age:
            raise ValueError("Invalid product entry-age limits.")
        if isinstance(self.min_years_before_income, bool) \
                or not isinstance(self.min_years_before_income, (int, np.integer)) \
                or self.min_years_before_income < 0:
            raise ValueError("min_years_before_income must be a non-negative integer.")
        if self.automatic_income_start_age <= self.min_entry_age:
            raise ValueError("automatic_income_start_age must exceed the minimum entry age.")
        if not str(self.product_id).strip():
            raise ValueError("product_id must not be empty.")
        div = {Index(k): float(v) for k, v in self.dividend_yield.items()}
        if set(div) != set(Index) or not np.all(np.isfinite(list(div.values()))) \
                or any(v < 0.0 for v in div.values()):
            raise ValueError("Dividend yields must be finite, non-negative and supplied for both indices.")
        object.__setattr__(self, "dividend_yield", MappingProxyType(div))

    @property
    def allows_growth_withdrawals(self) -> bool:
        return False

    @property
    def allows_growth_surrender(self) -> bool:
        return False


# Backwards-compatible import name.  New code should use the explicit generic
# name; both names refer to the same product class and defaults.
AgileProduct = IndexLinkedLifetimeIncomeProduct


@dataclass(frozen=True)
class PolicySpec:
    """One model point representing a covered policyholder."""

    age: float = 65.0
    sex: Sex = Sex.MALE
    funding_source: FundingSource = FundingSource.NON_SUPERANNUATION
    #: Calendar year (including a fractional year) of policy commencement.
    #: This anchors generational mortality improvements to the table base year.
    commencement_year: float = 2026.5
    initial_investment: float = 100_000.0
    #: Legacy AGILE allocation retained only for input compatibility.  The
    #: generic product always uses its product-wide 50/50 Reference Fund.
    allocation: Mapping[InvestmentOption, float] = field(
        default_factory=lambda: {InvestmentOption.AUS_TP: 1.0})
    #: Planned income commencement in policy years.  The contractual election
    #: grid contains Policy Anniversaries only.
    income_start_year: float = 5.0
    income_type: IncomeType = IncomeType.FIXED
    spouse: bool = False
    spouse_age: Optional[float] = None
    spouse_sex: Optional[Sex] = None
    #: PDS section 17.3: with Spouse-Insured there are two paths at death of
    #: the Life Insured. The default preserves the joint-life income-continuation
    #: valuation; set to LUMP_SUM to model an immediate death-benefit election.
    spouse_death_election: SpouseDeathElection = SpouseDeathElection.CONTINUE_INCOME
    age_pension_plus: bool = False
    #: For superannuation money, policy duration at which the relevant
    #: condition of release is met. Required when Age Pension+ is selected on
    #: a superannuation model point. Non-superannuation commencement is derived
    #: as the earlier of income commencement and Pension Age.
    condition_of_release_year: Optional[float] = None
    #: Contractual/social-security life expectancy used by the Capital Access
    #: Schedule.  If omitted, the projection uses its mortality basis as an
    #: explicitly non-production fallback; production model points should set it.
    aps_life_expectancy: Optional[float] = None
    #: Optional upfront adviser fee (reduces the initial investment amount).
    upfront_adviser_fee_pct: float = 0.0
    #: Optional commencement bonus as a fraction of Initial Investment.  This
    #: is zero by default because promotional offers are capacity-/date-limited;
    #: e.g. set 0.02 for the 18-May to 31-Jul-2026 offer when eligibility is
    #: confirmed.  The bonus forms part of Investment Amount thereafter.
    bonus_interest_pct: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.spouse, (bool, np.bool_)) \
                or not isinstance(self.age_pension_plus, (bool, np.bool_)):
            raise ValueError("spouse and age_pension_plus must be boolean.")
        object.__setattr__(self, "sex", Sex(self.sex))
        object.__setattr__(self, "funding_source", FundingSource(self.funding_source))
        object.__setattr__(self, "income_type", IncomeType(self.income_type))
        object.__setattr__(self, "spouse_death_election",
                           SpouseDeathElection(self.spouse_death_election))
        if self.spouse_sex is not None:
            object.__setattr__(self, "spouse_sex", Sex(self.spouse_sex))
        numeric = [self.age, self.commencement_year, self.initial_investment,
                   self.income_start_year, self.upfront_adviser_fee_pct,
                   self.bonus_interest_pct]
        if self.spouse_age is not None:
            numeric.append(self.spouse_age)
        if self.aps_life_expectancy is not None:
            numeric.append(self.aps_life_expectancy)
        if self.condition_of_release_year is not None:
            numeric.append(self.condition_of_release_year)
        if not np.all(np.isfinite(np.asarray(numeric, dtype=float))):
            raise ValueError("Policy numeric inputs must be finite.")
        alloc = {InvestmentOption(k): float(v) for k, v in self.allocation.items()}
        if not alloc or not np.all(np.isfinite(list(alloc.values()))):
            raise ValueError("Allocation weights must be finite and non-empty.")
        total = sum(alloc.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Allocation must sum to 1, got {total}.")
        if any(w < 0 for w in alloc.values()):
            raise ValueError("Allocation weights must be non-negative.")
        object.__setattr__(self, "allocation", MappingProxyType(alloc))
        if self.age < 0.0 or self.initial_investment <= 0.0:
            raise ValueError("Age and initial investment must be positive.")
        if not 0.0 <= self.upfront_adviser_fee_pct < 1.0:
            raise ValueError("upfront_adviser_fee_pct must be in [0, 1).")
        if not 0.0 <= self.bonus_interest_pct < 1.0:
            raise ValueError("bonus_interest_pct must be in [0, 1).")
        if self.age_pension_plus and self.upfront_adviser_fee_pct > 0.0:
            raise ValueError("Adviser Service Fees are not available with Age Pension+.")
        if self.spouse and (self.spouse_age is None or self.spouse_sex is None):
            raise ValueError("spouse_age and spouse_sex are required for the spouse option.")
        if not self.spouse and (self.spouse_age is not None or self.spouse_sex is not None):
            raise ValueError("spouse_age/spouse_sex require spouse=True.")
        if not self.spouse and self.spouse_death_election != SpouseDeathElection.CONTINUE_INCOME:
            raise ValueError("A spouse death election requires spouse=True.")
        if self.aps_life_expectancy is not None and self.aps_life_expectancy <= 0.0:
            raise ValueError("aps_life_expectancy must be positive when supplied.")
        if self.condition_of_release_year is not None:
            release_step = float(self.condition_of_release_year) * 12.0
            if self.condition_of_release_year < 0.0 \
                    or abs(release_step - round(release_step)) > 1e-9:
                raise ValueError("condition_of_release_year must be non-negative and on the monthly grid.")
        if self.funding_source == FundingSource.SUPERANNUATION \
                and self.age_pension_plus and self.condition_of_release_year is None:
            raise ValueError("Age Pension+ superannuation policies require condition_of_release_year.")
        if self.funding_source == FundingSource.NON_SUPERANNUATION \
                and self.condition_of_release_year is not None:
            raise ValueError("condition_of_release_year applies only to superannuation funding.")
        if not self.age_pension_plus and self.condition_of_release_year is not None:
            raise ValueError("condition_of_release_year requires age_pension_plus=True.")
        if abs(float(self.income_start_year) - round(float(self.income_start_year))) > 1e-9:
            raise ValueError("income_start_year must fall on a Policy Anniversary.")
        if self.income_start_year < 1:
            raise ValueError("Income cannot start before the first anniversary (PDS 9.1).")

    @property
    def base_investment_amount(self) -> float:
        """Investment Amount before any promotional bonus."""
        return self.initial_investment * (1.0 - self.upfront_adviser_fee_pct)

    @property
    def bonus_interest_amount(self) -> float:
        return self.initial_investment * self.bonus_interest_pct

    @property
    def net_initial_investment(self) -> float:
        return self.base_investment_amount + self.bonus_interest_amount

    def validate_against(
        self, product: IndexLinkedLifetimeIncomeProduct
    ) -> None:
        # The compatibility fields remain in PolicySpec, but the active
        # generic product requires the single premium to equal opening AV.
        if not (product.min_investment <= self.base_investment_amount
                <= product.max_investment):
            raise ValueError("Base Investment Amount outside product limits.")
        if not (product.min_entry_age <= self.age <= product.max_entry_age):
            raise ValueError("Entry age outside 50-80 band.")
        if self.spouse and self.spouse_age is not None and not (
                product.min_entry_age <= self.spouse_age <= product.max_entry_age):
            raise ValueError("Spouse age outside 50-80 band at commencement (PDS 3.1).")
        if self.income_start_year < product.min_years_before_income:
            raise ValueError("Income start before minimum growth period.")
        if self.net_initial_investment <= 0.0:
            raise ValueError("Upfront adviser fee leaves no investable premium.")
        if self.income_type != IncomeType.FIXED:
            raise ValueError("The generic product offers Fixed Lifetime Income only.")
        if self.age_pension_plus:
            raise ValueError("The generic product does not offer Age Pension+.")
        if self.upfront_adviser_fee_pct != 0.0:
            raise ValueError("The generic product does not offer an upfront adviser fee.")
        if self.bonus_interest_pct != 0.0:
            raise ValueError("The generic product has no commencement bonus.")
        if not np.isclose(self.net_initial_investment, self.initial_investment,
                          rtol=0.0, atol=1e-9):
            raise ValueError("Generic-product Account Value must start at the single premium.")

    def effective_income_start_year(
        self, product: IndexLinkedLifetimeIncomeProduct
    ) -> int:
        """Resolve the deterministic Income Election anniversary.

        The model-point anniversary remains the primary contractual input, but
        Income must start no later than the first Policy Anniversary strictly
        after the automatic-start age is reached.  Keeping this resolution on
        ``PolicySpec`` gives projection, rate-card validation and the
        pre-Election spouse-survival split one common convention.
        """
        scheduled = max(
            int(round(float(self.income_start_year))),
            int(product.min_years_before_income),
        )
        years_to_automatic_age = max(
            float(product.automatic_income_start_age) - float(self.age),
            0.0,
        )
        automatic_anniversary = max(
            int(np.floor(years_to_automatic_age + 1.0e-12)) + 1,
            int(product.min_years_before_income),
            1,
        )
        return min(scheduled, automatic_anniversary)


@dataclass(frozen=True)
class ExpenseAssumptions:
    """Insurer maintenance/acquisition expenses (profitability view).

    Constructor defaults are retained for backwards-compatible custom/unit
    runs.  The realistic base case must use ``load_cost_assumptions`` so these
    values and their provenance come from the repository cost CSV.  They are
    insurer expenses, not deductions from customer Account Value.
    """

    acquisition_pct_of_premium: float = 0.02
    maintenance_per_policy: float = 80.0        # p.a., inflating
    maintenance_pct_of_iv: float = 0.0005       # p.a.
    expense_inflation: float = 0.025
    commission_pct_of_premium: float = 0.0
    fixed_expense_base_date: str = "2026-07-12"

    def __post_init__(self) -> None:
        values = np.asarray([self.acquisition_pct_of_premium,
                             self.maintenance_per_policy,
                             self.maintenance_pct_of_iv,
                             self.expense_inflation,
                             self.commission_pct_of_premium], dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError("Expense assumptions must be finite.")
        if np.any(values[[0, 1, 2, 4]] < 0.0) or self.expense_inflation <= -1.0:
            raise ValueError("Expenses must be non-negative and inflation greater than -100%.")
        try:
            date.fromisoformat(self.fixed_expense_base_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("fixed_expense_base_date must be an ISO date.") from exc
