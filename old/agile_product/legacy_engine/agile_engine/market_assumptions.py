"""Strict loading of the repository's market assumptions.

The loader deliberately consumes only the two existing CSV sources under
``AGILE_Modelling_Engine/input_market_data``.  It maps every supported row to
an :class:`~agile_engine.esg.ESGConfig` and retains file-level provenance for
run manifests.  No implicit market-data fallbacks or additional calibration
inputs are introduced here.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from math import isfinite
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .curves import YieldCurve
from .esg import (
    ESGConfig,
    EquityParams,
    HestonParams,
    HullWhiteParams,
)
from .product import Index


DEFAULT_MARKET_DATA_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "input_market_data"
)
DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH = (
    DEFAULT_MARKET_DATA_DIRECTORY / "australian_zero_curve.csv"
)
DEFAULT_MODEL_PARAMETERS_PATH = (
    DEFAULT_MARKET_DATA_DIRECTORY / "model_parameters.csv"
)

_CURVE_REQUIRED_COLUMNS = {
    "curve_id",
    "as_of_date",
    "currency",
    "curve_type",
    "tenor_years",
    "zero_rate_cc_decimal",
    "source_compounding",
    "engine_compounding",
    "engine_time_basis",
    "engine_interpolation",
    "engine_extrapolation",
    "source_provider",
    "source_document",
    "source_url",
    "retrieved_at_utc",
    "transformation",
}

_CURVE_INVARIANT_METADATA_COLUMNS = (
    "as_of_date",
    "currency",
    "curve_type",
    "source_compounding",
    "engine_compounding",
    "engine_time_basis",
    "engine_interpolation",
    "engine_extrapolation",
    "source_provider",
    "source_document",
    "source_url",
    "retrieved_at_utc",
    "transformation",
)

_PARAMETER_REQUIRED_COLUMNS = {
    "parameter_set_id",
    "parameter_group",
    "parameter_name",
    "index_id",
    "value",
    "unit",
    "measure_scope",
    "model_scope",
    "calibration_status",
    "effective_date",
    "source_type",
    "source_reference",
    "source_url",
}

_INDEX_IDS = (Index.AUS_EQUITY.value, Index.GLOBAL_EQUITY.value)

# A unit change is intentionally a hard failure: the engine consumes all
# parameters as decimals and cannot infer a conversion safely from a label.
_REQUIRED_PARAMETER_UNITS: dict[tuple[str, str, str], str] = {
    ("equity", "sigma", index_id): "decimal_per_sqrt_year"
    for index_id in _INDEX_IDS
}
_REQUIRED_PARAMETER_UNITS.update({
    ("equity", "dividend_yield", index_id): "decimal_per_year"
    for index_id in _INDEX_IDS
})
_REQUIRED_PARAMETER_UNITS.update({
    ("equity", "risk_premium", index_id): "decimal_per_year"
    for index_id in _INDEX_IDS
})
_REQUIRED_PARAMETER_UNITS.update({
    ("dependence", "equity_correlation", ""): "correlation",
    ("hull_white", "mean_reversion", ""): "per_year",
    ("hull_white", "sigma_r", ""): "decimal_rate_per_sqrt_year",
})
for _index_id in _INDEX_IDS:
    _REQUIRED_PARAMETER_UNITS.update({
        ("heston", "v0", _index_id): "variance_per_year",
        ("heston", "theta", _index_id): "variance_per_year",
        ("heston", "kappa", _index_id): "per_year",
        ("heston", "xi", _index_id): "heston_vol_of_variance",
        ("heston", "rho_sv", _index_id): "correlation",
        ("hull_white", "rho_sr", _index_id): "correlation",
    })


@dataclass(frozen=True)
class MarketAssumptionSet:
    """CSV-configured ESG inputs plus auditable source metadata."""

    curve_id: str
    parameter_set_id: str
    source_paths: Mapping[str, str]
    source_sha256: Mapping[str, str]
    curve_metadata: Mapping[str, str]
    parameter_effective_dates: tuple[str, ...]
    parameter_calibration_statuses: tuple[str, ...]
    parameter_values: Mapping[str, float]
    esg: ESGConfig

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_paths", MappingProxyType(dict(self.source_paths))
        )
        object.__setattr__(
            self, "source_sha256", MappingProxyType(dict(self.source_sha256))
        )
        object.__setattr__(
            self, "curve_metadata", MappingProxyType(dict(self.curve_metadata))
        )
        object.__setattr__(
            self, "parameter_values", MappingProxyType(dict(self.parameter_values))
        )

    def source_metadata(self) -> dict[str, object]:
        """Return JSON-serialisable provenance for a run manifest."""
        return {
            "curve_id": self.curve_id,
            "parameter_set_id": self.parameter_set_id,
            "source_paths": dict(self.source_paths),
            "source_sha256": dict(self.source_sha256),
            "curve_metadata": dict(self.curve_metadata),
            "parameter_effective_dates": list(self.parameter_effective_dates),
            "parameter_calibration_statuses": list(
                self.parameter_calibration_statuses
            ),
            "applied_model_parameters": dict(self.parameter_values),
        }


def _open_csv(
    path: str | Path,
    *,
    label: str,
    required_columns: set[str],
) -> tuple[Path, bytes, list[dict[str, str]]]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"{label} CSV not found: {source}")

    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} CSV must be UTF-8: {source}") from exc

    reader = csv.DictReader(StringIO(text, newline=""))
    fieldnames = list(reader.fieldnames or ())
    if not fieldnames:
        raise ValueError(f"{label} CSV has no header row.")
    if len(fieldnames) != len(set(fieldnames)):
        raise ValueError(f"{label} CSV contains duplicate column names.")
    missing = sorted(required_columns - set(fieldnames))
    if missing:
        raise ValueError(
            f"{label} CSV is missing required columns: {', '.join(missing)}"
        )

    rows: list[dict[str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(
                f"Unexpected extra fields in {label} CSV at row {row_number}."
            )
        if any(row.get(column) is None for column in required_columns):
            raise ValueError(f"Incomplete {label} CSV row {row_number}.")
        parsed = {key: value for key, value in row.items() if key is not None}
        parsed["_row_number"] = str(row_number)
        rows.append(parsed)
    if not rows:
        raise ValueError(f"{label} CSV contains no data rows.")
    return source, raw, rows


def _finite_number(value: str, *, label: str, row_number: int) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid numeric {label} {value!r} at CSV row {row_number}."
        ) from exc
    if not isfinite(result):
        raise ValueError(f"Non-finite {label} at CSV row {row_number}.")
    return result


def _load_curve(
    path: str | Path,
) -> tuple[YieldCurve, str, dict[str, str], Path, bytes]:
    source, raw, rows = _open_csv(
        path,
        label="Australian zero-curve",
        required_columns=_CURVE_REQUIRED_COLUMNS,
    )

    curve_ids = {row["curve_id"].strip() for row in rows}
    if "" in curve_ids:
        raise ValueError("curve_id must not be empty.")
    if len(curve_ids) != 1:
        raise ValueError(
            "Australian zero-curve CSV must contain exactly one curve_id; "
            f"found: {', '.join(sorted(curve_ids))}."
        )
    curve_id = next(iter(curve_ids))

    tenors: list[float] = []
    zero_rates: list[float] = []
    seen_tenors: set[float] = set()
    for row in rows:
        row_number = int(row["_row_number"])
        tenor = _finite_number(
            row["tenor_years"], label="tenor_years", row_number=row_number
        )
        rate = _finite_number(
            row["zero_rate_cc_decimal"],
            label="zero_rate_cc_decimal",
            row_number=row_number,
        )
        if tenor <= 0.0:
            raise ValueError(
                f"tenor_years must be positive at CSV row {row_number}."
            )
        if tenor in seen_tenors:
            raise ValueError(
                f"Duplicate tenor_years {tenor!r} for curve {curve_id!r}."
            )
        seen_tenors.add(tenor)
        tenors.append(tenor)
        zero_rates.append(rate)

    if len(tenors) < 2:
        raise ValueError("Australian zero curve requires at least two points.")
    if any(right <= left for left, right in zip(tenors, tenors[1:])):
        raise ValueError("tenor_years must be strictly increasing in CSV order.")

    curve_metadata: dict[str, str] = {}
    for column in _CURVE_INVARIANT_METADATA_COLUMNS:
        values = {row[column].strip() for row in rows}
        if "" in values:
            raise ValueError(f"Curve metadata column {column!r} must not be empty.")
        if len(values) != 1:
            raise ValueError(
                f"Curve metadata column {column!r} is inconsistent across points."
            )
        curve_metadata[column] = next(iter(values))

    curve = YieldCurve.from_rates(tenors, zero_rates)
    return curve, curve_id, curve_metadata, source, raw


def _parameter_key_label(key: tuple[str, str, str]) -> str:
    group, name, index_id = key
    return f"{group}.{name}" + (f".{index_id}" if index_id else "")


def _load_parameters(
    path: str | Path,
) -> tuple[
    dict[tuple[str, str, str], float],
    str,
    tuple[str, ...],
    tuple[str, ...],
    Path,
    bytes,
]:
    source, raw, rows = _open_csv(
        path,
        label="Market model-parameter",
        required_columns=_PARAMETER_REQUIRED_COLUMNS,
    )

    parameter_set_ids = {row["parameter_set_id"].strip() for row in rows}
    if "" in parameter_set_ids:
        raise ValueError("parameter_set_id must not be empty.")
    if len(parameter_set_ids) != 1:
        raise ValueError(
            "Market model-parameter CSV must contain exactly one parameter_set_id; "
            f"found: {', '.join(sorted(parameter_set_ids))}."
        )
    parameter_set_id = next(iter(parameter_set_ids))

    values: dict[tuple[str, str, str], float] = {}
    for row in rows:
        row_number = int(row["_row_number"])
        key = (
            row["parameter_group"].strip(),
            row["parameter_name"].strip(),
            row["index_id"].strip(),
        )
        if key in values:
            raise ValueError(
                f"Duplicate model parameter {_parameter_key_label(key)!r}."
            )
        expected_unit = _REQUIRED_PARAMETER_UNITS.get(key)
        if expected_unit is None:
            raise ValueError(
                f"Unsupported model parameter {_parameter_key_label(key)!r} "
                f"at CSV row {row_number}."
            )
        unit = row["unit"].strip()
        if unit != expected_unit:
            raise ValueError(
                f"Unexpected unit for {_parameter_key_label(key)!r} at CSV row "
                f"{row_number}: expected {expected_unit!r}, got {unit!r}."
            )
        values[key] = _finite_number(
            row["value"], label=_parameter_key_label(key), row_number=row_number
        )

        for column in (
            "measure_scope",
            "model_scope",
            "calibration_status",
            "effective_date",
            "source_type",
            "source_reference",
        ):
            if not row[column].strip():
                raise ValueError(
                    f"Model-parameter metadata column {column!r} must not be "
                    f"empty at CSV row {row_number}."
                )

    missing = sorted(set(_REQUIRED_PARAMETER_UNITS) - set(values))
    if missing:
        raise ValueError(
            "Market model-parameter CSV is missing required parameters: "
            + ", ".join(_parameter_key_label(key) for key in missing)
        )

    effective_dates = tuple(
        sorted({row["effective_date"].strip() for row in rows})
    )
    calibration_statuses = tuple(
        sorted({row["calibration_status"].strip() for row in rows})
    )
    return (
        values,
        parameter_set_id,
        effective_dates,
        calibration_statuses,
        source,
        raw,
    )


def load_market_assumptions(
    curve_path: str | Path | None = None,
    model_parameters_path: str | Path | None = None,
) -> MarketAssumptionSet:
    """Load the repository zero curve and all ESG model parameters.

    Default paths are resolved relative to this module, not the caller's
    current working directory.  The source files must each contain exactly one
    curve/parameter-set identifier.
    """
    curve_source = (
        DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH
        if curve_path is None
        else Path(curve_path)
    )
    parameter_source = (
        DEFAULT_MODEL_PARAMETERS_PATH
        if model_parameters_path is None
        else Path(model_parameters_path)
    )

    curve, curve_id, curve_metadata, curve_file, curve_raw = _load_curve(
        curve_source
    )
    (
        values,
        parameter_set_id,
        effective_dates,
        calibration_statuses,
        parameters_file,
        parameters_raw,
    ) = _load_parameters(parameter_source)

    def value(group: str, name: str, index_id: str = "") -> float:
        return values[(group, name, index_id)]

    equity = {
        index: EquityParams(
            sigma=value("equity", "sigma", index.value),
            dividend_yield=value("equity", "dividend_yield", index.value),
            risk_premium=value("equity", "risk_premium", index.value),
        )
        for index in Index
    }
    heston = {
        index: HestonParams(
            v0=value("heston", "v0", index.value),
            theta=value("heston", "theta", index.value),
            kappa=value("heston", "kappa", index.value),
            xi=value("heston", "xi", index.value),
            rho_sv=value("heston", "rho_sv", index.value),
        )
        for index in Index
    }
    hull_white = HullWhiteParams(
        mean_reversion=value("hull_white", "mean_reversion"),
        sigma_r=value("hull_white", "sigma_r"),
        rho_sr={
            index: value("hull_white", "rho_sr", index.value)
            for index in Index
        },
    )
    esg = ESGConfig(
        curve=curve,
        equity=equity,
        equity_correlation=value("dependence", "equity_correlation"),
        heston=heston,
        hull_white=hull_white,
    )

    parameter_values = {
        _parameter_key_label(key): number for key, number in sorted(values.items())
    }
    return MarketAssumptionSet(
        curve_id=curve_id,
        parameter_set_id=parameter_set_id,
        source_paths={
            "curve": str(curve_file),
            "model_parameters": str(parameters_file),
        },
        source_sha256={
            "curve": sha256(curve_raw).hexdigest(),
            "model_parameters": sha256(parameters_raw).hexdigest(),
        },
        curve_metadata=curve_metadata,
        parameter_effective_dates=effective_dates,
        parameter_calibration_statuses=calibration_statuses,
        parameter_values=parameter_values,
        esg=esg,
    )


__all__ = [
    "DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH",
    "DEFAULT_MARKET_DATA_DIRECTORY",
    "DEFAULT_MODEL_PARAMETERS_PATH",
    "MarketAssumptionSet",
    "load_market_assumptions",
]
