"""Strict loading of dynamic policyholder-behaviour assumptions.

The repository keeps behavioural experience assumptions separate from market
data and insurer costs.  This module reads the two versioned CSV sources under
``input_dynamic_behaviour`` and constructs the immutable objects consumed by
the monthly projection engine.  Every numeric assumption in the configured
base behaviour is therefore auditable back to a file digest and source row.

The shipped values are deliberately marked ``uncalibrated_proxy``.  They are
literature- and practice-informed starting points, not Australian experience
rates or a production calibration.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from hashlib import sha256
from io import StringIO
from math import isfinite
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Optional

from .behavior import (
    BehaviourModel,
    DynamicHazardFunction,
    DynamicLapseParams,
    DynamicTakeUpParams,
    DynamicWithdrawalParams,
    FractionalLogitFunction,
    IncomeTakeUp,
    LapseAssumptions,
    PerformanceLapseFunction,
    WithdrawalBehaviour,
)


DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY = (
    Path(__file__).resolve().parents[2] / "input_dynamic_behaviour"
)
BASELINES_FILENAME = "dynamic_behaviour_baselines.csv"
COEFFICIENTS_FILENAME = "dynamic_behaviour_coefficients.csv"

_VALUE_COLUMNS = {
    "base": "base_value",
    "low": "low_value",
    "high": "high_value",
}

_BASELINE_COLUMNS = (
    "assumption_set_id",
    "component",
    "phase",
    "policy_year_from",
    "policy_year_to",
    "base_value",
    "low_value",
    "high_value",
    "unit",
    "frequency",
    "is_structural_zero",
    "force_at_year",
    "effective_date",
    "assumption_status",
    "source_reference",
    "notes",
)

_COEFFICIENT_COLUMNS = (
    "assumption_set_id",
    "component",
    "phase",
    "link",
    "moneyness_transform",
    "parameter_name",
    "base_value",
    "low_value",
    "high_value",
    "unit",
    "effective_date",
    "assumption_status",
    "source_reference",
    "notes",
)

_BASELINE_SPEC = {
    ("lapse", "growth"): ("annual_conditional_probability", "monthly"),
    ("lapse", "income"): ("annual_conditional_probability", "monthly"),
    ("income_take_up", "growth"):
        ("annual_conditional_probability", "annual"),
    ("free_withdrawal_utilisation", "growth"):
        ("fraction_of_free_withdrawal_allowance", "annual"),
    ("excess_withdrawal_rate", "all"):
        ("annual_fraction_of_investment_value", "annual"),
}

_SHARED_PARAMETER_UNITS = {
    "reference_premium": "AUD_gross_single_premium",
    "log_moneyness_min": "natural_log_ratio",
    "log_moneyness_max": "natural_log_ratio",
    "log_premium_min": "natural_log_ratio",
    "log_premium_max": "natural_log_ratio",
}

_HAZARD_PARAMETER_UNITS = {
    "beta_moneyness": "log_hazard_coefficient",
    "beta_log_premium": "log_hazard_coefficient",
    "beta_interaction": "log_hazard_interaction_coefficient",
    "output_floor": "annual_conditional_probability",
    "output_cap": "annual_conditional_probability",
    "multiplier_floor": "dimensionless_multiplier",
    "multiplier_cap": "dimensionless_multiplier",
}

_TAKE_UP_PARAMETER_UNITS = {
    **_HAZARD_PARAMETER_UNITS,
    "beta_log_account_value": "log_hazard_coefficient",
    "beta_prospective_income_ratio": "log_hazard_coefficient_per_income_to_premium",
    "beta_reference_return": "log_hazard_coefficient_per_return",
    "beta_credited_return": "log_hazard_coefficient_per_return",
    "beta_performance_gap": "log_hazard_coefficient_per_log_return_gap",
}

_PERFORMANCE_LAPSE_PARAMETER_UNITS = {
    "retention_gamma": "per_natural_log_moneyness",
    "retention_floor": "dimensionless_multiplier",
    "shortfall_deadband": "natural_log_return_shortfall",
    "shortfall_max": "natural_log_return_shortfall",
    "excess_hazard_cap": "annual_integrated_hazard",
    "excess_hazard_scale": "natural_log_return_shortfall",
    "annual_probability_cap": "annual_conditional_probability",
    "log_moneyness_max": "natural_log_ratio",
}

_FRACTIONAL_LOGIT_PARAMETER_UNITS = {
    "beta_moneyness": "log_odds_coefficient",
    "beta_log_premium": "log_odds_coefficient",
    "beta_interaction": "log_odds_interaction_coefficient",
    "beta_mva": "log_odds_coefficient_per_mva_fraction",
    "output_floor": "fraction",
    "output_cap": "fraction",
}

_COEFFICIENT_GROUP_SPEC = {
    ("shared", "all"): (
        "shared", "not_applicable", _SHARED_PARAMETER_UNITS),
    ("lapse", "growth"): (
        "proportional_hazard_cloglog", "signed",
        _HAZARD_PARAMETER_UNITS),
    ("lapse", "income"): (
        "proportional_hazard_cloglog", "signed",
        _HAZARD_PARAMETER_UNITS),
    ("performance_lapse", "all"): (
        "competing_risk_excess_hazard", "positive_part",
        _PERFORMANCE_LAPSE_PARAMETER_UNITS),
    ("income_take_up", "growth"): (
        "proportional_hazard_cloglog", "signed",
        _TAKE_UP_PARAMETER_UNITS),
    ("free_withdrawal_utilisation", "growth"): (
        "fractional_logit", "positive_part",
        _FRACTIONAL_LOGIT_PARAMETER_UNITS),
    ("excess_withdrawal_rate", "all"): (
        "fractional_logit", "positive_part",
        _FRACTIONAL_LOGIT_PARAMETER_UNITS),
}


@dataclass(frozen=True)
class DynamicBehaviourAssumptionSet:
    """CSV-configured behaviour model and auditable source metadata."""

    assumption_set_id: str
    value_basis: str
    source_paths: Mapping[str, str]
    source_sha256: Mapping[str, str]
    effective_dates: tuple[str, ...]
    values: Mapping[str, float]
    behaviour: BehaviourModel

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_paths", MappingProxyType(dict(self.source_paths)))
        object.__setattr__(
            self, "source_sha256", MappingProxyType(dict(self.source_sha256)))
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    @property
    def source_path(self) -> str:
        """Common source directory, retained as a convenient manifest field."""
        return str(Path(self.source_paths["baselines"]).parent)

    def source_metadata(self) -> dict[str, object]:
        """Return a JSON-serialisable provenance record."""
        return {
            "assumption_set_id": self.assumption_set_id,
            "value_basis": self.value_basis,
            "source_paths": dict(self.source_paths),
            "source_sha256": dict(self.source_sha256),
            "effective_dates": list(self.effective_dates),
            "applied_engine_parameters": dict(self.values),
            "assumption_status": "uncalibrated_proxy",
        }


def _parse_number(value: str, *, column: str, row_number: int,
                  source_name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid numeric value {value!r} in {column} at "
            f"{source_name} row {row_number}."
        ) from exc
    if not isfinite(result):
        raise ValueError(
            f"Non-finite value in {column} at {source_name} row {row_number}."
        )
    return result


def _parse_bool(value: str, *, column: str, row_number: int,
                source_name: str) -> bool:
    normalised = value.strip().lower()
    if normalised == "true":
        return True
    if normalised == "false":
        return False
    raise ValueError(
        f"Invalid boolean value {value!r} in {column} at "
        f"{source_name} row {row_number}; expected true or false."
    )


def _parse_positive_int(value: str, *, column: str, row_number: int,
                        source_name: str) -> int:
    stripped = value.strip()
    try:
        result = int(stripped)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid integer value {value!r} in {column} at "
            f"{source_name} row {row_number}."
        ) from exc
    if result < 1 or str(result) != stripped:
        raise ValueError(
            f"{column} must be a canonical positive integer at "
            f"{source_name} row {row_number}."
        )
    return result


def _read_csv(path: Path, expected_columns: tuple[str, ...],
              source_name: str) -> tuple[bytes, list[dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(f"Dynamic-behaviour CSV not found: {path}")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"Dynamic-behaviour CSV must be valid UTF-8: {path}"
        ) from exc

    reader = csv.DictReader(StringIO(text, newline=""))
    actual_columns = tuple(reader.fieldnames or ())
    if actual_columns != expected_columns:
        missing = sorted(set(expected_columns) - set(actual_columns))
        unexpected = sorted(set(actual_columns) - set(expected_columns))
        detail = []
        if missing:
            detail.append("missing: " + ", ".join(missing))
        if unexpected:
            detail.append("unexpected: " + ", ".join(unexpected))
        if not missing and not unexpected:
            detail.append("columns are not in the required order")
        raise ValueError(
            f"Invalid {source_name} schema ({'; '.join(detail)})."
        )

    rows: list[dict[str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(
                f"Unexpected extra CSV fields at {source_name} row {row_number}."
            )
        if any(row.get(column) is None for column in expected_columns):
            raise ValueError(
                f"Incomplete {source_name} row {row_number}."
            )
        parsed = {key: value for key, value in row.items()}
        parsed["_row_number"] = str(row_number)
        rows.append(parsed)
    if not rows:
        raise ValueError(f"{source_name} CSV contains no data rows.")
    return raw, rows


def _require_text(row: Mapping[str, str], column: str, *, source_name: str,
                  row_number: int) -> str:
    value = row[column].strip()
    if not value:
        raise ValueError(
            f"{column} must not be empty at {source_name} row {row_number}."
        )
    return value


def _parse_baselines(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    parsed_rows: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for raw_row in rows:
        row_number = int(raw_row["_row_number"])
        source_name = "baseline"
        row: dict[str, object] = dict(raw_row)
        for column in (
            "assumption_set_id", "component", "phase", "unit", "frequency",
            "effective_date", "assumption_status", "source_reference", "notes",
        ):
            row[column] = _require_text(
                raw_row, column, source_name=source_name, row_number=row_number)
        if row["assumption_status"] != "uncalibrated_proxy":
            raise ValueError(
                f"Unsupported assumption_status at baseline row {row_number}; "
                "expected 'uncalibrated_proxy'."
            )

        year_from = _parse_positive_int(
            raw_row["policy_year_from"], column="policy_year_from",
            row_number=row_number, source_name=source_name)
        year_to_raw = raw_row["policy_year_to"].strip()
        year_to = None if not year_to_raw else _parse_positive_int(
            year_to_raw, column="policy_year_to", row_number=row_number,
            source_name=source_name)
        if year_to is not None and year_to < year_from:
            raise ValueError(
                f"policy_year_to precedes policy_year_from at baseline row "
                f"{row_number}."
            )
        row["_year_from"] = year_from
        row["_year_to"] = year_to
        row["_structural_zero"] = _parse_bool(
            raw_row["is_structural_zero"], column="is_structural_zero",
            row_number=row_number, source_name=source_name)
        row["_force_at_year"] = _parse_bool(
            raw_row["force_at_year"], column="force_at_year",
            row_number=row_number, source_name=source_name)

        for column in _VALUE_COLUMNS.values():
            row[f"_{column}"] = _parse_number(
                raw_row[column], column=column, row_number=row_number,
                source_name=source_name)
        low = float(row["_low_value"])
        base = float(row["_base_value"])
        high = float(row["_high_value"])
        if not low <= base <= high:
            raise ValueError(
                f"Expected low_value <= base_value <= high_value at baseline "
                f"row {row_number}."
            )
        if low < 0.0 or high > 1.0:
            raise ValueError(
                f"Baseline values must be probabilities/fractions in [0, 1] "
                f"at row {row_number}."
            )

        group = (str(row["component"]), str(row["phase"]))
        if group not in _BASELINE_SPEC:
            raise ValueError(
                f"Unsupported baseline component/phase {group!r} at row "
                f"{row_number}."
            )
        expected_unit, expected_frequency = _BASELINE_SPEC[group]
        if row["unit"] != expected_unit or row["frequency"] != expected_frequency:
            raise ValueError(
                f"Unexpected unit/frequency for {group!r} at baseline row "
                f"{row_number}; expected {expected_unit!r}/"
                f"{expected_frequency!r}."
            )
        if bool(row["_structural_zero"]) and (low != 0.0 or high != 0.0):
            raise ValueError(
                f"Structural-zero band must be exactly zero at baseline row "
                f"{row_number}."
            )
        if bool(row["_structural_zero"]) and bool(row["_force_at_year"]):
            raise ValueError(
                f"A baseline band cannot be both structural zero and forced at "
                f"row {row_number}."
            )
        if bool(row["_force_at_year"]):
            if group != ("income_take_up", "growth"):
                raise ValueError(
                    f"force_at_year is only valid for income take-up; baseline "
                    f"row {row_number}."
                )
            if low != 1.0 or high != 1.0:
                raise ValueError(
                    f"Forced take-up band must be exactly one at baseline row "
                    f"{row_number}."
                )
        elif group != ("income_take_up", "growth") \
                and bool(row["_structural_zero"]):
            raise ValueError(
                f"Structural-zero markers are only supported for income take-up; "
                f"baseline row {row_number}."
            )

        key = (
            row["assumption_set_id"], group[0], group[1], year_from, year_to)
        if key in seen:
            raise ValueError(
                f"Duplicate baseline band {key!r} at row {row_number}."
            )
        seen.add(key)
        parsed_rows.append(row)
    return parsed_rows


def _parse_coefficients(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    parsed_rows: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for raw_row in rows:
        row_number = int(raw_row["_row_number"])
        source_name = "coefficient"
        row: dict[str, object] = dict(raw_row)
        for column in (
            "assumption_set_id", "component", "phase", "link",
            "moneyness_transform", "parameter_name", "unit", "effective_date",
            "assumption_status", "source_reference", "notes",
        ):
            row[column] = _require_text(
                raw_row, column, source_name=source_name, row_number=row_number)
        if row["assumption_status"] != "uncalibrated_proxy":
            raise ValueError(
                f"Unsupported assumption_status at coefficient row {row_number}; "
                "expected 'uncalibrated_proxy'."
            )

        for column in _VALUE_COLUMNS.values():
            row[f"_{column}"] = _parse_number(
                raw_row[column], column=column, row_number=row_number,
                source_name=source_name)
        low = float(row["_low_value"])
        base = float(row["_base_value"])
        high = float(row["_high_value"])
        if not low <= base <= high:
            raise ValueError(
                f"Expected low_value <= base_value <= high_value at coefficient "
                f"row {row_number}; signed coefficient bands must be ordered "
                "numerically."
            )

        group = (str(row["component"]), str(row["phase"]))
        if group not in _COEFFICIENT_GROUP_SPEC:
            raise ValueError(
                f"Unsupported coefficient component/phase {group!r} at row "
                f"{row_number}."
            )
        expected_link, expected_transform, parameter_units = \
            _COEFFICIENT_GROUP_SPEC[group]
        if row["link"] != expected_link \
                or row["moneyness_transform"] != expected_transform:
            raise ValueError(
                f"Unexpected link/moneyness_transform for {group!r} at "
                f"coefficient row {row_number}; expected {expected_link!r}/"
                f"{expected_transform!r}."
            )
        parameter = str(row["parameter_name"])
        if parameter not in parameter_units:
            raise ValueError(
                f"Unsupported parameter {parameter!r} for {group!r} at "
                f"coefficient row {row_number}."
            )
        if row["unit"] != parameter_units[parameter]:
            raise ValueError(
                f"Unexpected unit for {group!r}/{parameter!r} at coefficient "
                f"row {row_number}; expected {parameter_units[parameter]!r}."
            )

        key = (
            str(row["assumption_set_id"]), group[0], group[1], parameter)
        if key in seen:
            raise ValueError(
                f"Duplicate coefficient {key!r} at row {row_number}."
            )
        seen.add(key)
        parsed_rows.append(row)
    return parsed_rows


def _select_assumption_set(baselines: list[dict[str, object]],
                           coefficients: list[dict[str, object]],
                           requested: Optional[str]) -> str:
    baseline_sets = {str(row["assumption_set_id"]) for row in baselines}
    coefficient_sets = {str(row["assumption_set_id"]) for row in coefficients}
    if baseline_sets != coefficient_sets:
        raise ValueError(
            "Baseline and coefficient CSVs contain different assumption sets: "
            f"baselines={sorted(baseline_sets)}, "
            f"coefficients={sorted(coefficient_sets)}."
        )
    available = sorted(baseline_sets)
    if requested is None:
        if len(available) != 1:
            raise ValueError(
                "Multiple dynamic-behaviour assumption sets are available; "
                "specify assumption_set_id from: " + ", ".join(available)
            )
        return available[0]
    selected = str(requested)
    if selected not in baseline_sets:
        raise ValueError(
            f"Unknown dynamic-behaviour assumption set {selected!r}; available: "
            + ", ".join(available)
        )
    return selected


def _validate_schedules(rows: list[dict[str, object]]) -> None:
    actual_groups = {
        (str(row["component"]), str(row["phase"])) for row in rows}
    expected_groups = set(_BASELINE_SPEC)
    if actual_groups != expected_groups:
        missing = sorted(expected_groups - actual_groups)
        unexpected = sorted(actual_groups - expected_groups)
        raise ValueError(
            "Dynamic-behaviour baseline groups are incomplete or unexpected; "
            f"missing={missing}, unexpected={unexpected}."
        )

    for group in sorted(expected_groups):
        schedule = sorted(
            (row for row in rows
             if (row["component"], row["phase"]) == group),
            key=lambda row: int(row["_year_from"]),
        )
        expected_start = 1
        for index, row in enumerate(schedule):
            start = int(row["_year_from"])
            end = row["_year_to"]
            if start != expected_start:
                raise ValueError(
                    f"Gap or overlap in {group!r} baseline schedule: expected "
                    f"policy year {expected_start}, got {start}."
                )
            if end is None:
                if index != len(schedule) - 1:
                    raise ValueError(
                        f"Open-ended {group!r} baseline band must be last."
                    )
                expected_start = -1
            else:
                expected_start = int(end) + 1
        if expected_start != -1:
            raise ValueError(
                f"{group!r} baseline schedule must end with an open band."
            )

    # The current typed engine fields for Income lapse and withdrawal
    # severity are scalars.  Accepting multiple valid-looking bands and then
    # applying only the first would silently discard source assumptions.
    # Until those fields become genuine schedules, require the exact schema
    # the projection can consume without loss.
    scalar_groups = (
        ("lapse", "income"),
        ("free_withdrawal_utilisation", "growth"),
        ("excess_withdrawal_rate", "all"),
    )
    for group in scalar_groups:
        schedule = [
            row for row in rows
            if (row["component"], row["phase"]) == group
        ]
        if (
            len(schedule) != 1
            or int(schedule[0]["_year_from"]) != 1
            or schedule[0]["_year_to"] is not None
        ):
            raise ValueError(
                f"{group!r} is represented by one scalar engine assumption "
                "and therefore requires exactly one open baseline band from "
                "policy year 1."
            )

    take_up = [
        row for row in rows
        if (row["component"], row["phase"])
        == ("income_take_up", "growth")]
    structural = [row for row in take_up if bool(row["_structural_zero"])]
    forced = [row for row in take_up if bool(row["_force_at_year"])]
    if len(structural) != 1 or int(structural[0]["_year_from"]) != 1 \
            or structural[0]["_year_to"] != 1:
        raise ValueError(
            "Income take-up must contain exactly one structural-zero band for "
            "policy year 1."
        )
    if len(forced) != 1 or int(forced[0]["_year_from"]) != 15 \
            or forced[0]["_year_to"] is not None:
        raise ValueError(
            "Income take-up must contain exactly one open-ended forced band "
            "beginning at policy year 15."
        )


def _coefficient_values(rows: list[dict[str, object]], value_column: str
                        ) -> dict[tuple[str, str], dict[str, float]]:
    actual_groups = {
        (str(row["component"]), str(row["phase"])) for row in rows}
    expected_groups = set(_COEFFICIENT_GROUP_SPEC)
    if actual_groups != expected_groups:
        missing = sorted(expected_groups - actual_groups)
        unexpected = sorted(actual_groups - expected_groups)
        raise ValueError(
            "Dynamic-behaviour coefficient groups are incomplete or unexpected; "
            f"missing={missing}, unexpected={unexpected}."
        )

    result: dict[tuple[str, str], dict[str, float]] = {}
    for group, (_, _, parameter_units) in _COEFFICIENT_GROUP_SPEC.items():
        group_rows = [
            row for row in rows
            if (row["component"], row["phase"]) == group]
        actual_parameters = {str(row["parameter_name"]) for row in group_rows}
        expected_parameters = set(parameter_units)
        if actual_parameters != expected_parameters:
            missing = sorted(expected_parameters - actual_parameters)
            unexpected = sorted(actual_parameters - expected_parameters)
            raise ValueError(
                f"Coefficient parameters for {group!r} are incomplete or "
                f"unexpected; missing={missing}, unexpected={unexpected}."
            )
        result[group] = {
            str(row["parameter_name"]): float(row[f"_{value_column}"])
            for row in group_rows
        }

    shared = result[("shared", "all")]
    if shared["reference_premium"] <= 0.0:
        raise ValueError("reference_premium must be strictly positive.")
    if not shared["log_moneyness_min"] < shared["log_moneyness_max"]:
        raise ValueError(
            "log_moneyness_min must be below log_moneyness_max.")
    if not shared["log_premium_min"] < shared["log_premium_max"]:
        raise ValueError("log_premium_min must be below log_premium_max.")
    for group in (
        ("lapse", "growth"), ("lapse", "income"),
        ("income_take_up", "growth"),
    ):
        values = result[group]
        if not 0.0 <= values["output_floor"] <= values["output_cap"] <= 1.0:
            raise ValueError(
                f"Invalid annual probability floor/cap for {group!r}."
            )
        if not 0.0 < values["multiplier_floor"] <= 1.0 \
                <= values["multiplier_cap"]:
            raise ValueError(
                f"Hazard multiplier bounds for {group!r} must contain one and "
                "have a strictly positive floor."
            )
    for group in (
        ("free_withdrawal_utilisation", "growth"),
        ("excess_withdrawal_rate", "all"),
    ):
        values = result[group]
        if not 0.0 <= values["output_floor"] < values["output_cap"] <= 1.0:
            raise ValueError(
                f"Invalid fractional-logit output bounds for {group!r}."
            )
    performance = result[("performance_lapse", "all")]
    if not 0.0 <= performance["retention_floor"] <= 1.0:
        raise ValueError("Performance-lapse retention_floor must lie in [0, 1].")
    if not 0.0 <= performance["shortfall_deadband"] \
            <= performance["shortfall_max"]:
        raise ValueError("Invalid performance-lapse shortfall bounds.")
    if performance["excess_hazard_cap"] < 0.0 \
            or performance["excess_hazard_scale"] <= 0.0:
        raise ValueError("Invalid performance-lapse hazard parameters.")
    if not 0.0 < performance["annual_probability_cap"] <= 1.0:
        raise ValueError("Invalid performance-lapse annual probability cap.")
    return result


def _expanded_schedule(rows: list[dict[str, object]], component: str,
                       phase: str, value_column: str, *, stop_before: int | None = None
                       ) -> tuple[float, ...]:
    schedule = sorted(
        (row for row in rows
         if row["component"] == component and row["phase"] == phase),
        key=lambda row: int(row["_year_from"]),
    )
    values: list[float] = []
    for row in schedule:
        start = int(row["_year_from"])
        end_obj = row["_year_to"]
        end = start if end_obj is None else int(end_obj)
        if stop_before is not None:
            if start >= stop_before:
                break
            end = min(end, stop_before - 1)
        values.extend(float(row[f"_{value_column}"]) for _ in range(start, end + 1))
    return tuple(values)


def load_dynamic_behaviour_assumptions(
    directory: str | Path | None = None,
    *,
    assumption_set_id: Optional[str] = None,
    value_basis: str = "base",
    behaviour: Optional[BehaviourModel] = None,
) -> DynamicBehaviourAssumptionSet:
    """Load, validate and apply one dynamic-behaviour assumption set.

    ``directory`` must contain both repository-schema CSV files.  ``value_basis``
    selects their consistently ordered base, low or high band.  Supplying an
    existing ``BehaviourModel`` applies the CSV as an overlay while preserving
    unrelated future behaviour fields.
    """
    if value_basis not in _VALUE_COLUMNS:
        allowed = ", ".join(sorted(_VALUE_COLUMNS))
        raise ValueError(f"value_basis must be one of: {allowed}.")
    value_column = _VALUE_COLUMNS[value_basis]

    source_directory = (
        Path(directory) if directory is not None
        else DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY
    ).expanduser().resolve()
    if not source_directory.is_dir():
        raise FileNotFoundError(
            f"Dynamic-behaviour input directory not found: {source_directory}"
        )
    baseline_path = source_directory / BASELINES_FILENAME
    coefficient_path = source_directory / COEFFICIENTS_FILENAME

    baseline_raw, baseline_rows_raw = _read_csv(
        baseline_path, _BASELINE_COLUMNS, "baseline")
    coefficient_raw, coefficient_rows_raw = _read_csv(
        coefficient_path, _COEFFICIENT_COLUMNS, "coefficient")
    baselines = _parse_baselines(baseline_rows_raw)
    coefficients = _parse_coefficients(coefficient_rows_raw)
    selected_id = _select_assumption_set(
        baselines, coefficients, assumption_set_id)
    selected_baselines = [
        row for row in baselines if row["assumption_set_id"] == selected_id]
    selected_coefficients = [
        row for row in coefficients if row["assumption_set_id"] == selected_id]

    _validate_schedules(selected_baselines)
    coefficient_values = _coefficient_values(
        selected_coefficients, value_column)
    shared = coefficient_values[("shared", "all")]

    def hazard_function(component: str, phase: str) -> DynamicHazardFunction:
        values = coefficient_values[(component, phase)]
        _, transform, _ = _COEFFICIENT_GROUP_SPEC[(component, phase)]
        return DynamicHazardFunction(
            beta_moneyness=values["beta_moneyness"],
            beta_log_premium=values["beta_log_premium"],
            beta_interaction=values["beta_interaction"],
            reference_premium=shared["reference_premium"],
            log_moneyness_min=shared["log_moneyness_min"],
            log_moneyness_max=shared["log_moneyness_max"],
            log_premium_min=shared["log_premium_min"],
            log_premium_max=shared["log_premium_max"],
            moneyness_transform=transform,
            annual_floor=values["output_floor"],
            annual_cap=values["output_cap"],
            multiplier_floor=values["multiplier_floor"],
            multiplier_cap=values["multiplier_cap"],
            beta_mva=0.0,
        )

    def performance_lapse_function() -> PerformanceLapseFunction:
        values = coefficient_values[("performance_lapse", "all")]
        return PerformanceLapseFunction(
            retention_gamma=values["retention_gamma"],
            retention_floor=values["retention_floor"],
            shortfall_deadband=values["shortfall_deadband"],
            shortfall_max=values["shortfall_max"],
            excess_hazard_cap=values["excess_hazard_cap"],
            excess_hazard_scale=values["excess_hazard_scale"],
            annual_probability_cap=values["annual_probability_cap"],
            log_moneyness_max=values["log_moneyness_max"],
        )

    def fractional_function(component: str, phase: str) -> FractionalLogitFunction:
        values = coefficient_values[(component, phase)]
        _, transform, _ = _COEFFICIENT_GROUP_SPEC[(component, phase)]
        return FractionalLogitFunction(
            beta_moneyness=values["beta_moneyness"],
            beta_log_premium=values["beta_log_premium"],
            beta_interaction=values["beta_interaction"],
            reference_premium=shared["reference_premium"],
            log_moneyness_min=shared["log_moneyness_min"],
            log_moneyness_max=shared["log_moneyness_max"],
            log_premium_min=shared["log_premium_min"],
            log_premium_max=shared["log_premium_max"],
            moneyness_transform=transform,
            beta_mva=values["beta_mva"],
            output_floor=values["output_floor"],
            output_cap=values["output_cap"],
        )

    force_rows = [
        row for row in selected_baselines
        if row["component"] == "income_take_up"
        and bool(row["_force_at_year"])
    ]
    force_by_year = int(force_rows[0]["_year_from"])
    lapse_growth = _expanded_schedule(
        selected_baselines, "lapse", "growth", value_column)
    lapse_income = _expanded_schedule(
        selected_baselines, "lapse", "income", value_column)[0]
    take_up_hazard = _expanded_schedule(
        selected_baselines, "income_take_up", "growth", value_column,
        stop_before=force_by_year)
    free_utilisation = _expanded_schedule(
        selected_baselines, "free_withdrawal_utilisation", "growth",
        value_column)[0]
    excess_rate = _expanded_schedule(
        selected_baselines, "excess_withdrawal_rate", "all", value_column)[0]

    configured_lapse = LapseAssumptions(
        growth_phase=lapse_growth, income_phase=lapse_income)
    configured_take_up = IncomeTakeUp(
        mode="dynamic", hazard=take_up_hazard, force_by_year=force_by_year)
    configured_withdrawals = WithdrawalBehaviour(
        free_utilisation=free_utilisation,
        excess_rate=excess_rate,
        frequency="annual",
    )
    configured_dynamic_lapse = DynamicLapseParams(
        enabled=True,
        growth=hazard_function("lapse", "growth"),
        income=hazard_function("lapse", "income"),
        performance=performance_lapse_function(),
    )
    configured_dynamic_take_up = DynamicTakeUpParams(
        enabled=True,
        function=hazard_function("income_take_up", "growth"),
        beta_log_account_value=coefficient_values[
            ("income_take_up", "growth")
        ]["beta_log_account_value"],
        beta_prospective_income_ratio=coefficient_values[
            ("income_take_up", "growth")
        ]["beta_prospective_income_ratio"],
        beta_reference_return=coefficient_values[
            ("income_take_up", "growth")
        ]["beta_reference_return"],
        beta_credited_return=coefficient_values[
            ("income_take_up", "growth")
        ]["beta_credited_return"],
        beta_performance_gap=coefficient_values[
            ("income_take_up", "growth")
        ]["beta_performance_gap"],
    )
    configured_dynamic_withdrawals = DynamicWithdrawalParams(
        enabled=True,
        free=fractional_function("free_withdrawal_utilisation", "growth"),
        excess=fractional_function("excess_withdrawal_rate", "all"),
    )

    base_behaviour = behaviour or BehaviourModel()
    configured_behaviour = replace(
        base_behaviour,
        regime="dynamic",
        lapse=configured_lapse,
        dynamic=configured_dynamic_lapse,
        take_up=configured_take_up,
        dynamic_take_up=configured_dynamic_take_up,
        withdrawals=configured_withdrawals,
        dynamic_withdrawals=configured_dynamic_withdrawals,
    )

    applied_values: dict[str, float] = {}
    for row in selected_baselines:
        end_label = "open" if row["_year_to"] is None else str(row["_year_to"])
        key = (
            f"baseline.{row['component']}.{row['phase']}."
            f"years_{row['_year_from']}_{end_label}"
        )
        applied_values[key] = float(row[f"_{value_column}"])
    for group, values in coefficient_values.items():
        for parameter, value in values.items():
            applied_values[
                f"coefficient.{group[0]}.{group[1]}.{parameter}"
            ] = float(value)

    effective_dates = tuple(sorted({
        str(row["effective_date"])
        for row in (*selected_baselines, *selected_coefficients)
    }))
    return DynamicBehaviourAssumptionSet(
        assumption_set_id=selected_id,
        value_basis=value_basis,
        source_paths={
            "baselines": str(baseline_path),
            "coefficients": str(coefficient_path),
        },
        source_sha256={
            "baselines": sha256(baseline_raw).hexdigest(),
            "coefficients": sha256(coefficient_raw).hexdigest(),
        },
        effective_dates=effective_dates,
        values=applied_values,
        behaviour=configured_behaviour,
    )


__all__ = [
    "BASELINES_FILENAME",
    "COEFFICIENTS_FILENAME",
    "DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY",
    "DynamicBehaviourAssumptionSet",
    "load_dynamic_behaviour_assumptions",
]
