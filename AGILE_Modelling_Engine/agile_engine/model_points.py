"""Strict loading of the repository policyholder model points.

The operational default is the fast four-point proxy; the legacy AGILE-shaped
48-point new-business grid remains an explicit alternative.  Only demographic,
premium and contractual election fields are mapped to :class:`PolicySpec`.
The four legacy allocation columns are validated for source integrity but are
deliberately ignored: the generic product's 50/50 reference fund is a
product-wide rule, not a model-point allocation.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from math import isclose, isfinite
from pathlib import Path
from typing import Optional

from .product import (
    FundingSource,
    IncomeType,
    IndexLinkedLifetimeIncomeProduct,
    PolicySpec,
    Sex,
    SpouseDeathElection,
)


DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH = (
    Path(__file__).resolve().parents[2]
    / "input_model_points_policyholders"
    / "model_points_policyholders_4_point_proxy.csv"
)

LEGACY_ALLOCATION_COLUMNS = (
    "allocation_aus_tp",
    "allocation_aus_pp10",
    "allocation_global_tp",
    "allocation_global_pp10",
)

_REQUIRED_COLUMNS = (
    "model_point_id",
    "contract_weight",
    "premium_volume_weight",
    "region",
    "currency",
    "wrapper",
    "product_id",
    "product_pds_version",
    "new_business_indicator",
    "commencement_year",
    "policy_duration_years",
    "current_phase",
    "primary_age",
    "primary_sex",
    "life_basis",
    "spouse",
    "secondary_age",
    "secondary_sex",
    "initial_premium_aud",
    "initial_investment_aud",
    "investment_value_0_aud",
    "locked_income_0_aud",
    "used_free_withdrawal_allowance_0_aud",
    "withdrawal_status",
    "scheduled_partial_withdrawal_rate",
    "income_start_year",
    "income_type",
    "derived_lifetime_income_rate_at_start",
    "spouse_death_election",
    "age_pension_plus",
    "funding_source",
    "condition_of_release_year",
    "aps_life_expectancy_years",
    *LEGACY_ALLOCATION_COLUMNS,
    "upfront_adviser_fee_pct",
    "bonus_interest_pct",
    "rate_card_vintage",
    "cap_vintage",
    "market_parameter_set_id",
    "yield_curve_id",
)

# A production portfolio should supply the represented number of contracts per
# model point.  The repository's current illustrative file predates this field,
# so it remains optional and the portfolio layer can still work with an
# explicitly supplied total contract count and ``contract_weight``.
_OPTIONAL_COLUMNS = ("exposure_count",)

_WEIGHT_TOLERANCE = 1.0e-9
_MONEY_ABS_TOLERANCE = 1.0e-8


@dataclass(frozen=True)
class PolicyholderModelPoint:
    """One validated source row and its engine policy specification."""

    model_point_id: str
    contract_weight: float
    premium_volume_weight: float
    policy: PolicySpec
    initial_premium_aud: float
    product_id: str
    product_pds_version: str
    rate_card_vintage: str
    cap_vintage: str
    market_parameter_set_id: str
    yield_curve_id: str
    source_row_number: int
    exposure_count: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.model_point_id.strip():
            raise ValueError("model_point_id must not be empty.")
        for label, value in (
            ("contract_weight", self.contract_weight),
            ("premium_volume_weight", self.premium_volume_weight),
            ("initial_premium_aud", self.initial_premium_aud),
        ):
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"{label} must be positive and finite.")
        if self.exposure_count is not None and (
            not isfinite(self.exposure_count) or self.exposure_count <= 0.0
        ):
            raise ValueError("exposure_count must be positive and finite.")


@dataclass(frozen=True)
class PolicyholderModelPointSet:
    """Validated model-point portfolio with file-level provenance."""

    model_points: tuple[PolicyholderModelPoint, ...]
    source_path: str
    source_sha256: str
    product_id: str
    product_pds_version: str
    rate_card_vintage: str
    cap_vintage: str
    market_parameter_set_id: str
    yield_curve_id: str
    contract_weight_sum: float
    premium_volume_weight_sum: float
    weighted_average_premium_aud: float
    total_exposure_count: Optional[float] = None
    ignored_legacy_columns: tuple[str, ...] = LEGACY_ALLOCATION_COLUMNS

    def __post_init__(self) -> None:
        points = tuple(self.model_points)
        object.__setattr__(self, "model_points", points)
        if not points:
            raise ValueError("Policyholder model-point set must not be empty.")
        identifiers = [point.model_point_id for point in points]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Policyholder model-point IDs must be unique.")

        contract_weight_sum = sum(point.contract_weight for point in points)
        premium_weight_sum = sum(point.premium_volume_weight for point in points)
        weighted_average_premium = sum(
            point.contract_weight * point.initial_premium_aud for point in points
        )
        for label, supplied, recomputed in (
            ("contract_weight_sum", self.contract_weight_sum, contract_weight_sum),
            (
                "premium_volume_weight_sum",
                self.premium_volume_weight_sum,
                premium_weight_sum,
            ),
            (
                "weighted_average_premium_aud",
                self.weighted_average_premium_aud,
                weighted_average_premium,
            ),
        ):
            tolerance = (
                _MONEY_ABS_TOLERANCE
                if label == "weighted_average_premium_aud"
                else _WEIGHT_TOLERANCE
            )
            if not isfinite(supplied) or not isclose(
                supplied,
                recomputed,
                rel_tol=1.0e-12,
                abs_tol=tolerance,
            ):
                raise ValueError(f"{label} does not reconcile to model points.")
        if not isclose(
            contract_weight_sum, 1.0, rel_tol=0.0, abs_tol=_WEIGHT_TOLERANCE
        ):
            raise ValueError("Model-point contract weights must sum to one.")
        if not isclose(
            premium_weight_sum, 1.0, rel_tol=0.0, abs_tol=_WEIGHT_TOLERANCE
        ):
            raise ValueError("Model-point premium-volume weights must sum to one.")

        point_exposures = [point.exposure_count for point in points]
        if self.total_exposure_count is None:
            if any(exposure is not None for exposure in point_exposures):
                raise ValueError(
                    "Model-point exposure_count values require total_exposure_count."
                )
        else:
            if (
                not isfinite(self.total_exposure_count)
                or self.total_exposure_count <= 0.0
                or any(exposure is None for exposure in point_exposures)
            ):
                raise ValueError(
                    "A positive total_exposure_count requires an exposure on every model point."
                )
            exposure_total = sum(
                float(exposure) for exposure in point_exposures
                if exposure is not None
            )
            exposure_tolerance = max(
                1.0e-9, abs(self.total_exposure_count) * 1.0e-12
            )
            if not isclose(
                exposure_total,
                self.total_exposure_count,
                rel_tol=0.0,
                abs_tol=exposure_tolerance,
            ):
                raise ValueError(
                    "total_exposure_count does not reconcile to model points."
                )
            for point in points:
                expected_weight = float(point.exposure_count) / exposure_total
                if not isclose(
                    point.contract_weight,
                    expected_weight,
                    rel_tol=0.0,
                    abs_tol=_WEIGHT_TOLERANCE,
                ):
                    raise ValueError(
                        "contract_weight does not reconcile to exposure_count for "
                        f"model point {point.model_point_id!r}."
                    )

    def source_metadata(self) -> dict[str, object]:
        """Return JSON-serialisable source and transformation metadata."""
        return {
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "model_point_count": len(self.model_points),
            "product_id_in_source": self.product_id,
            "product_pds_version_in_source": self.product_pds_version,
            "rate_card_vintage": self.rate_card_vintage,
            "cap_vintage_legacy_metadata": self.cap_vintage,
            "market_parameter_set_id": self.market_parameter_set_id,
            "yield_curve_id": self.yield_curve_id,
            "contract_weight_sum": self.contract_weight_sum,
            "premium_volume_weight_sum": self.premium_volume_weight_sum,
            "weighted_average_premium_aud": self.weighted_average_premium_aud,
            "total_exposure_count": self.total_exposure_count,
            "absolute_portfolio_values_available_from_source": (
                self.total_exposure_count is not None
            ),
            "aggregation_rule": (
                "exposure_count"
                if self.total_exposure_count is not None
                else "contract_weight_with_external_total_contract_count"
            ),
            "premium_volume_weight_usage": "exposure_and_reconciliation_only",
            "ignored_legacy_columns": list(self.ignored_legacy_columns),
            "legacy_allocation_treatment": (
                "validated_but_not_mapped; generic product uses its fixed "
                "50/50 Global Equity/Australian Government Bond reference fund"
            ),
            "cap_vintage_treatment": (
                "legacy source metadata only; it does not set the generic "
                "product's fixed 6% Reference-Fund cap"
            ),
        }


def _text(row: dict[str, str], column: str, row_number: int) -> str:
    value = row[column].strip()
    if not value:
        raise ValueError(f"{column} must not be empty at CSV row {row_number}.")
    return value


def _number(row: dict[str, str], column: str, row_number: int) -> float:
    raw = row[column].strip()
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid numeric value {raw!r} in {column} at CSV row {row_number}."
        ) from exc
    if not isfinite(value):
        raise ValueError(f"Non-finite {column} at CSV row {row_number}.")
    return value


def _optional_number(
    row: dict[str, str], column: str, row_number: int
) -> Optional[float]:
    if not row[column].strip():
        return None
    return _number(row, column, row_number)


def _boolean(row: dict[str, str], column: str, row_number: int) -> bool:
    value = row[column].strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(
        f"Invalid boolean value {row[column]!r} in {column} at CSV row "
        f"{row_number}; expected true or false."
    )


def _require_zero(value: float, label: str, row_number: int) -> None:
    if not isclose(value, 0.0, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(f"{label} must be zero at CSV row {row_number}.")


def _require_money_equal(
    left: float, right: float, left_label: str, right_label: str, row_number: int
) -> None:
    if not isclose(
        left,
        right,
        rel_tol=1.0e-12,
        abs_tol=_MONEY_ABS_TOLERANCE,
    ):
        raise ValueError(
            f"New-business reconciliation failed at CSV row {row_number}: "
            f"{left_label}={left} differs from {right_label}={right}."
        )


def load_policyholder_model_points(
    path: str | Path | None = None,
    *,
    expected_market_parameter_set_id: str | None = None,
    expected_yield_curve_id: str | None = None,
) -> PolicyholderModelPointSet:
    """Load the repository's duration-zero policyholder model points.

    Only the currently supported generic new-business state is accepted:
    Growth phase, Fixed Income, no Age Pension+, adviser fee, bonus, locked
    income or initiated withdrawal.  Premium, initial investment and time-zero
    Account Value must reconcile exactly up to a negligible CSV tolerance.
    """
    source = (
        DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH if path is None else Path(path)
    ).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Policyholder model-point CSV not found: {source}")

    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Policyholder model-point CSV must be UTF-8: {source}") from exc

    reader = csv.DictReader(StringIO(text, newline=""))
    fieldnames = tuple(reader.fieldnames or ())
    if len(set(fieldnames)) != len(fieldnames):
        raise ValueError("Policyholder model-point CSV contains duplicate columns.")
    missing = sorted(set(_REQUIRED_COLUMNS) - set(fieldnames))
    extra = sorted(
        set(fieldnames) - set(_REQUIRED_COLUMNS) - set(_OPTIONAL_COLUMNS)
    )
    if missing or extra:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if extra:
            details.append("unexpected: " + ", ".join(extra))
        raise ValueError(
            "Policyholder model-point CSV schema mismatch (" + "; ".join(details) + ")."
        )

    model_points: list[PolicyholderModelPoint] = []
    seen_ids: set[str] = set()
    source_product_ids: set[str] = set()
    source_pds_versions: set[str] = set()
    market_ids: set[str] = set()
    curve_ids: set[str] = set()
    rate_card_vintages: set[str] = set()
    cap_vintages: set[str] = set()
    validation_product = IndexLinkedLifetimeIncomeProduct()

    for row_number, row in enumerate(reader, start=2):
        if (
            None in row
            or any(row.get(column) is None for column in _REQUIRED_COLUMNS)
            or (
                "exposure_count" in fieldnames
                and row.get("exposure_count") is None
            )
        ):
            raise ValueError(f"Malformed or incomplete CSV row {row_number}.")

        model_point_id = _text(row, "model_point_id", row_number)
        if model_point_id in seen_ids:
            raise ValueError(f"Duplicate model_point_id {model_point_id!r}.")
        seen_ids.add(model_point_id)

        contract_weight = _number(row, "contract_weight", row_number)
        premium_volume_weight = _number(row, "premium_volume_weight", row_number)
        if contract_weight <= 0.0 or premium_volume_weight <= 0.0:
            raise ValueError(f"Model-point weights must be positive at CSV row {row_number}.")
        exposure_count = None
        if "exposure_count" in fieldnames:
            exposure_count = _number(row, "exposure_count", row_number)
            if exposure_count <= 0.0:
                raise ValueError(
                    f"exposure_count must be positive at CSV row {row_number}."
                )

        if _text(row, "region", row_number) != "Australia":
            raise ValueError(f"region must be Australia at CSV row {row_number}.")
        if _text(row, "currency", row_number) != "AUD":
            raise ValueError(f"currency must be AUD at CSV row {row_number}.")
        _text(row, "wrapper", row_number)

        product_id = _text(row, "product_id", row_number)
        pds_version = _text(row, "product_pds_version", row_number)
        source_product_ids.add(product_id)
        source_pds_versions.add(pds_version)

        if not _boolean(row, "new_business_indicator", row_number):
            raise ValueError(f"Only new-business model points are supported (row {row_number}).")
        _require_zero(
            _number(row, "policy_duration_years", row_number),
            "policy_duration_years",
            row_number,
        )
        if _text(row, "current_phase", row_number).lower() != "growth":
            raise ValueError(f"current_phase must be growth at CSV row {row_number}.")
        if _text(row, "income_type", row_number).lower() != IncomeType.FIXED.value:
            raise ValueError(f"income_type must be fixed at CSV row {row_number}.")

        spouse = _boolean(row, "spouse", row_number)
        life_basis = _text(row, "life_basis", row_number).lower()
        expected_life_basis = "joint" if spouse else "single"
        if life_basis != expected_life_basis:
            raise ValueError(
                f"life_basis and spouse are inconsistent at CSV row {row_number}."
            )

        secondary_age = _optional_number(row, "secondary_age", row_number)
        secondary_sex_raw = row["secondary_sex"].strip()
        if spouse:
            if secondary_age is None or not secondary_sex_raw:
                raise ValueError(
                    f"Joint-life model point requires secondary life data at row {row_number}."
                )
            secondary_sex: Sex | None = Sex(secondary_sex_raw)
        else:
            if secondary_age is not None or secondary_sex_raw:
                raise ValueError(
                    f"Single-life model point must not contain secondary life data at row {row_number}."
                )
            secondary_sex = None

        premium = _number(row, "initial_premium_aud", row_number)
        investment = _number(row, "initial_investment_aud", row_number)
        account_value_0 = _number(row, "investment_value_0_aud", row_number)
        if premium <= 0.0:
            raise ValueError(f"initial_premium_aud must be positive at CSV row {row_number}.")
        _require_money_equal(
            premium, investment, "initial_premium_aud", "initial_investment_aud", row_number
        )
        _require_money_equal(
            premium, account_value_0, "initial_premium_aud", "investment_value_0_aud", row_number
        )

        _require_zero(_number(row, "locked_income_0_aud", row_number),
                      "locked_income_0_aud", row_number)
        _require_zero(
            _number(row, "used_free_withdrawal_allowance_0_aud", row_number),
            "used_free_withdrawal_allowance_0_aud",
            row_number,
        )
        if _text(row, "withdrawal_status", row_number).lower() != "not_initiated":
            raise ValueError(f"withdrawal_status must be not_initiated at row {row_number}.")
        _require_zero(
            _number(row, "scheduled_partial_withdrawal_rate", row_number),
            "scheduled_partial_withdrawal_rate",
            row_number,
        )

        derived_income_rate = _number(
            row, "derived_lifetime_income_rate_at_start", row_number
        )
        if derived_income_rate <= 0.0:
            raise ValueError(
                f"derived_lifetime_income_rate_at_start must be positive at row {row_number}."
            )

        if _boolean(row, "age_pension_plus", row_number):
            raise ValueError(f"Age Pension+ is not supported at CSV row {row_number}.")
        if (
            row["condition_of_release_year"].strip()
            or row["aps_life_expectancy_years"].strip()
        ):
            raise ValueError(
                f"Age-Pension-specific fields must be empty at CSV row {row_number}."
            )
        _require_zero(_number(row, "upfront_adviser_fee_pct", row_number),
                      "upfront_adviser_fee_pct", row_number)
        _require_zero(_number(row, "bonus_interest_pct", row_number),
                      "bonus_interest_pct", row_number)

        legacy_allocation = [
            _number(row, column, row_number) for column in LEGACY_ALLOCATION_COLUMNS
        ]
        if any(weight < 0.0 for weight in legacy_allocation) or not isclose(
            sum(legacy_allocation), 1.0, rel_tol=0.0, abs_tol=_WEIGHT_TOLERANCE
        ):
            raise ValueError(
                f"Legacy AGILE allocation must be non-negative and sum to one at row {row_number}."
            )

        market_id = _text(row, "market_parameter_set_id", row_number)
        curve_id = _text(row, "yield_curve_id", row_number)
        market_ids.add(market_id)
        curve_ids.add(curve_id)
        rate_card_vintage = _text(row, "rate_card_vintage", row_number)
        cap_vintage = _text(row, "cap_vintage", row_number)
        rate_card_vintages.add(rate_card_vintage)
        cap_vintages.add(cap_vintage)

        policy = PolicySpec(
            age=_number(row, "primary_age", row_number),
            sex=Sex(_text(row, "primary_sex", row_number)),
            funding_source=FundingSource(_text(row, "funding_source", row_number)),
            commencement_year=_number(row, "commencement_year", row_number),
            initial_investment=premium,
            income_start_year=_number(row, "income_start_year", row_number),
            income_type=IncomeType.FIXED,
            spouse=spouse,
            spouse_age=secondary_age,
            spouse_sex=secondary_sex,
            spouse_death_election=SpouseDeathElection(
                _text(row, "spouse_death_election", row_number)
            ),
            age_pension_plus=False,
            condition_of_release_year=None,
            aps_life_expectancy=None,
            upfront_adviser_fee_pct=0.0,
            bonus_interest_pct=0.0,
            # No allocation is supplied: PolicySpec's compatibility field is
            # immaterial to the generic product-wide reference fund.
        )
        policy.validate_against(validation_product)
        effective_income_start_year = policy.effective_income_start_year(
            validation_product
        )
        expected_income_rate = validation_product.income_rates.lifetime_income_rate(
            policy.age,
            policy.sex,
            IncomeType.FIXED,
            policy.spouse,
            effective_income_start_year,
            policy.spouse_age,
            policy.spouse_sex,
            False,
        )
        if not isclose(
            derived_income_rate,
            expected_income_rate,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError(
                "derived_lifetime_income_rate_at_start control does not "
                f"reconcile at CSV row {row_number}: source="
                f"{derived_income_rate}, ratecard={expected_income_rate}, "
                f"effective_income_start_year={effective_income_start_year}."
            )

        model_points.append(
            PolicyholderModelPoint(
                model_point_id=model_point_id,
                contract_weight=contract_weight,
                premium_volume_weight=premium_volume_weight,
                exposure_count=exposure_count,
                policy=policy,
                initial_premium_aud=premium,
                product_id=product_id,
                product_pds_version=pds_version,
                rate_card_vintage=rate_card_vintage,
                cap_vintage=cap_vintage,
                market_parameter_set_id=market_id,
                yield_curve_id=curve_id,
                source_row_number=row_number,
            )
        )

    if not model_points:
        raise ValueError("Policyholder model-point CSV contains no data rows.")
    if len(source_product_ids) != 1 or len(source_pds_versions) != 1:
        raise ValueError("Model points must use one consistent source product/PDS version.")
    if len(market_ids) != 1 or len(curve_ids) != 1:
        raise ValueError("Model points must reference one market parameter set and yield curve.")
    if len(rate_card_vintages) != 1 or len(cap_vintages) != 1:
        raise ValueError("Model points must use consistent rate-card and cap vintages.")
    rate_card_vintage = next(iter(rate_card_vintages))
    if rate_card_vintage != validation_product.income_rates.rate_card_vintage:
        raise ValueError(
            f"Model points reference rate-card vintage {rate_card_vintage!r}, "
            "but the configured product rate card is "
            f"{validation_product.income_rates.rate_card_vintage!r}."
        )

    market_id = next(iter(market_ids))
    curve_id = next(iter(curve_ids))
    if (
        expected_market_parameter_set_id is not None
        and market_id != expected_market_parameter_set_id
    ):
        raise ValueError(
            f"Model points reference market parameter set {market_id!r}, expected "
            f"{expected_market_parameter_set_id!r}."
        )
    if expected_yield_curve_id is not None and curve_id != expected_yield_curve_id:
        raise ValueError(
            f"Model points reference yield curve {curve_id!r}, expected "
            f"{expected_yield_curve_id!r}."
        )

    contract_weight_sum = sum(point.contract_weight for point in model_points)
    premium_volume_weight_sum = sum(
        point.premium_volume_weight for point in model_points
    )
    if not isclose(
        contract_weight_sum, 1.0, rel_tol=0.0, abs_tol=_WEIGHT_TOLERANCE
    ):
        raise ValueError(
            f"contract_weight must sum to one, got {contract_weight_sum:.12f}."
        )
    if not isclose(
        premium_volume_weight_sum, 1.0, rel_tol=0.0, abs_tol=_WEIGHT_TOLERANCE
    ):
        raise ValueError(
            "premium_volume_weight must sum to one, got "
            f"{premium_volume_weight_sum:.12f}."
        )

    weighted_average_premium = sum(
        point.contract_weight * point.initial_premium_aud for point in model_points
    )
    for point in model_points:
        expected_premium_weight = (
            point.contract_weight
            * point.initial_premium_aud
            / weighted_average_premium
        )
        if not isclose(
            point.premium_volume_weight,
            expected_premium_weight,
            rel_tol=0.0,
            abs_tol=_WEIGHT_TOLERANCE,
        ):
            raise ValueError(
                f"premium_volume_weight does not reconcile for model point "
                f"{point.model_point_id!r}."
            )

    total_exposure_count: Optional[float]
    if "exposure_count" in fieldnames:
        total_exposure_count = sum(
            float(point.exposure_count) for point in model_points
            if point.exposure_count is not None
        )
        for point in model_points:
            if point.exposure_count is None:  # defensive; header implies a value
                raise ValueError(
                    f"Missing exposure_count for model point {point.model_point_id!r}."
                )
            expected_contract_weight = point.exposure_count / total_exposure_count
            if not isclose(
                point.contract_weight,
                expected_contract_weight,
                rel_tol=0.0,
                abs_tol=_WEIGHT_TOLERANCE,
            ):
                raise ValueError(
                    "contract_weight does not reconcile to exposure_count for "
                    f"model point {point.model_point_id!r}."
                )
    else:
        total_exposure_count = None

    return PolicyholderModelPointSet(
        model_points=tuple(model_points),
        source_path=str(source),
        source_sha256=sha256(raw).hexdigest(),
        product_id=next(iter(source_product_ids)),
        product_pds_version=next(iter(source_pds_versions)),
        rate_card_vintage=rate_card_vintage,
        cap_vintage=next(iter(cap_vintages)),
        market_parameter_set_id=market_id,
        yield_curve_id=curve_id,
        contract_weight_sum=contract_weight_sum,
        premium_volume_weight_sum=premium_volume_weight_sum,
        weighted_average_premium_aud=weighted_average_premium,
        total_exposure_count=total_exposure_count,
    )


__all__ = [
    "DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH",
    "LEGACY_ALLOCATION_COLUMNS",
    "PolicyholderModelPoint",
    "PolicyholderModelPointSet",
    "load_policyholder_model_points",
]
