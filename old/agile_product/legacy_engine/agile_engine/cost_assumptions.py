"""Typed loading of the repository's cost-assumption source.

The realistic base case is deliberately assembled as an overlay on the
engine's modelling objects.  This keeps non-cost settings (for example the
fixed generic Reference Fund, DVA switches and capital stress correlations) intact
while making ``input_cost_assumptions/cost_assumptions.csv`` the single source
for every numeric cost parameter used by the base run.
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

from .capital import CapitalStresses
from .product import IndexLinkedLifetimeIncomeProduct, ExpenseAssumptions
from .profitability import ProfitabilitySettings
from .projection import ProjectionConfig


DEFAULT_COST_ASSUMPTIONS_PATH = (
    Path(__file__).resolve().parents[2]
    / "input_cost_assumptions"
    / "cost_assumptions.csv"
)

_VALUE_COLUMNS = {
    "base": "base_value",
    "low": "low_value",
    "high": "high_value",
}

_REQUIRED_COLUMNS = {
    "assumption_set_id",
    "category",
    "parameter_name",
    "engine_parameter",
    "base_value",
    "low_value",
    "high_value",
    "unit",
    "perspective",
    "timing",
    "include_in_base_case",
    "engine_support",
    "assumption_status",
    "effective_date",
    "source_reference",
    "notes",
}

# Expected units are checked before values reach the engine.  A changed unit
# must be accompanied by an explicit loader/model change rather than being
# silently interpreted as the old decimal/AUD convention.
_SUPPORTED_PARAMETERS = {
    "FeeSpec.product_fee": "decimal_per_year_on_investment_value",
    "FeeSpec.lifetime_income_premium": "decimal_per_year_on_investment_value",
    "ExpenseAssumptions.acquisition_pct_of_premium": "decimal_of_single_premium",
    "ExpenseAssumptions.maintenance_per_policy": "AUD_per_policy_per_year",
    "ExpenseAssumptions.maintenance_pct_of_iv": "decimal_per_year_on_investment_value",
    "ExpenseAssumptions.expense_inflation": "decimal_per_year",
    "ExpenseAssumptions.commission_pct_of_premium": "decimal_of_single_premium",
    "ProjectionConfig.hedge_vol_spread": "absolute_volatility_add_on",
    "ProjectionConfig.option_fair_value_markup":
        "decimal_of_fair_option_package_value",
    "ProjectionConfig.hedge_reference_management_fee":
        "decimal_per_year_on_hedge_reference_notional",
    "MVASpec.cost_loading_per_remaining_year":
        "decimal_of_withdrawal_base_per_remaining_year",
    "MVASpec.cost_loading": "decimal_of_withdrawal_base",
    "CapitalStresses.coc_rate": "decimal_per_year_on_non_hedgeable_capital",
    "ProfitabilitySettings.hurdle_rate": "decimal_per_year",
    "ProfitabilitySettings.tax_rate": "decimal_of_taxable_profit",
    "ProfitabilitySettings.capital_earning_spread": "decimal_per_year_over_cash",
}


@dataclass(frozen=True)
class CostAssumptionSet:
    """Cost-configured engine inputs plus auditable source metadata."""

    assumption_set_id: str
    value_basis: str
    source_path: str
    source_sha256: str
    effective_dates: tuple[str, ...]
    values: Mapping[str, float]
    excluded_parameters: tuple[str, ...]
    product: IndexLinkedLifetimeIncomeProduct
    expenses: ExpenseAssumptions
    projection: ProjectionConfig
    capital_stresses: CapitalStresses
    profitability: ProfitabilitySettings

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    def source_metadata(self) -> dict[str, object]:
        """Return JSON-serialisable provenance for run manifests."""
        return {
            "assumption_set_id": self.assumption_set_id,
            "value_basis": self.value_basis,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "effective_dates": list(self.effective_dates),
            "applied_engine_parameters": dict(self.values),
            "excluded_parameters": list(self.excluded_parameters),
        }


def _parse_bool(value: str, *, row_number: int) -> bool:
    normalised = value.strip().lower()
    if normalised == "true":
        return True
    if normalised == "false":
        return False
    raise ValueError(
        f"Invalid include_in_base_case value {value!r} at CSV row {row_number}; "
        "expected true or false."
    )


def _parse_number(value: str, *, column: str, row_number: int) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid numeric value {value!r} in {column} at CSV row {row_number}."
        ) from exc
    if not isfinite(result):
        raise ValueError(f"Non-finite value in {column} at CSV row {row_number}.")
    return result


def load_cost_assumptions(
    path: str | Path | None = None,
    *,
    assumption_set_id: Optional[str] = None,
    value_basis: str = "base",
    product: Optional[IndexLinkedLifetimeIncomeProduct] = None,
    expenses: Optional[ExpenseAssumptions] = None,
    projection: Optional[ProjectionConfig] = None,
    capital_stresses: Optional[CapitalStresses] = None,
    profitability: Optional[ProfitabilitySettings] = None,
) -> CostAssumptionSet:
    """Load and apply one cost-assumption set from CSV.

    ``value_basis`` selects the base, low or high column.  Rows explicitly
    excluded from the base case (ongoing adviser fees, personal tax and
    uncalibrated reinsurance in the current file) are retained in provenance
    but never silently applied to the core insurer model.

    Existing objects may be supplied as overlays.  Only fields explicitly
    mapped by the CSV are replaced.
    """
    if value_basis not in _VALUE_COLUMNS:
        allowed = ", ".join(sorted(_VALUE_COLUMNS))
        raise ValueError(f"value_basis must be one of: {allowed}.")

    source = Path(path) if path is not None else DEFAULT_COST_ASSUMPTIONS_PATH
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Cost-assumption CSV not found: {source}")

    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Cost-assumption CSV must be UTF-8: {source}") from exc

    reader = csv.DictReader(StringIO(text, newline=""))
    fieldnames = set(reader.fieldnames or ())
    missing_columns = sorted(_REQUIRED_COLUMNS - fieldnames)
    if missing_columns:
        raise ValueError(
            "Cost-assumption CSV is missing required columns: "
            + ", ".join(missing_columns)
        )

    rows = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"Unexpected extra CSV fields at row {row_number}.")
        if any(row.get(column) is None for column in _REQUIRED_COLUMNS):
            raise ValueError(f"Incomplete cost-assumption CSV row {row_number}.")
        parsed = dict(row)
        parsed["_row_number"] = row_number
        parsed["_include"] = _parse_bool(
            row["include_in_base_case"], row_number=row_number
        )
        for column in _VALUE_COLUMNS.values():
            parsed[f"_{column}"] = _parse_number(
                row[column], column=column, row_number=row_number
            )
        if not (
            parsed["_low_value"]
            <= parsed["_base_value"]
            <= parsed["_high_value"]
        ):
            raise ValueError(
                f"Expected low_value <= base_value <= high_value at CSV row {row_number}."
            )
        rows.append(parsed)

    if not rows:
        raise ValueError("Cost-assumption CSV contains no data rows.")
    available_sets = sorted({row["assumption_set_id"].strip() for row in rows})
    if any(not item for item in available_sets):
        raise ValueError("assumption_set_id must not be empty.")
    if assumption_set_id is None:
        if len(available_sets) != 1:
            raise ValueError(
                "Multiple cost assumption sets are available; specify assumption_set_id "
                f"from: {', '.join(available_sets)}."
            )
        selected_id = available_sets[0]
    else:
        selected_id = str(assumption_set_id)
        if selected_id not in available_sets:
            raise ValueError(
                f"Unknown cost assumption set {selected_id!r}; available: "
                + ", ".join(available_sets)
            )

    selected = [row for row in rows if row["assumption_set_id"].strip() == selected_id]
    active = [row for row in selected if row["_include"]]
    excluded = tuple(
        row["parameter_name"].strip() for row in selected if not row["_include"]
    )

    values: dict[str, float] = {}
    effective_date_by_parameter: dict[str, str] = {}
    value_column = _VALUE_COLUMNS[value_basis]
    for row in active:
        row_number = int(row["_row_number"])
        engine_parameter = row["engine_parameter"].strip()
        if engine_parameter not in _SUPPORTED_PARAMETERS:
            raise ValueError(
                f"Unsupported active engine_parameter {engine_parameter!r} "
                f"at CSV row {row_number}."
            )
        if row["engine_support"].strip() == "not_supported":
            raise ValueError(
                f"Active parameter {engine_parameter!r} is marked not_supported "
                f"at CSV row {row_number}."
            )
        expected_unit = _SUPPORTED_PARAMETERS[engine_parameter]
        if row["unit"].strip() != expected_unit:
            raise ValueError(
                f"Unexpected unit for {engine_parameter!r} at CSV row {row_number}: "
                f"expected {expected_unit!r}, got {row['unit']!r}."
            )
        if engine_parameter in values:
            raise ValueError(
                f"Duplicate active engine_parameter {engine_parameter!r} "
                f"in assumption set {selected_id!r}."
            )
        values[engine_parameter] = float(row[f"_{value_column}"])
        effective_date_by_parameter[engine_parameter] = row["effective_date"].strip()

    missing_parameters = sorted(set(_SUPPORTED_PARAMETERS) - set(values))
    if missing_parameters:
        raise ValueError(
            "Cost assumption set is missing active supported parameters: "
            + ", ".join(missing_parameters)
        )

    base_product = product or IndexLinkedLifetimeIncomeProduct()
    configured_product = replace(
        base_product,
        fees=replace(
            base_product.fees,
            product_fee=values["FeeSpec.product_fee"],
            lifetime_income_premium=values["FeeSpec.lifetime_income_premium"],
        ),
        mva=replace(
            base_product.mva,
            cost_loading=values["MVASpec.cost_loading"],
            cost_loading_per_remaining_year=values[
                "MVASpec.cost_loading_per_remaining_year"
            ],
        ),
    )

    base_expenses = expenses or ExpenseAssumptions()
    configured_expenses = replace(
        base_expenses,
        acquisition_pct_of_premium=values[
            "ExpenseAssumptions.acquisition_pct_of_premium"
        ],
        maintenance_per_policy=values["ExpenseAssumptions.maintenance_per_policy"],
        maintenance_pct_of_iv=values["ExpenseAssumptions.maintenance_pct_of_iv"],
        expense_inflation=values["ExpenseAssumptions.expense_inflation"],
        commission_pct_of_premium=values[
            "ExpenseAssumptions.commission_pct_of_premium"
        ],
        fixed_expense_base_date=effective_date_by_parameter[
            "ExpenseAssumptions.maintenance_per_policy"
        ],
    )

    base_projection = projection or ProjectionConfig()
    configured_projection = replace(
        base_projection,
        hedge_vol_spread=values["ProjectionConfig.hedge_vol_spread"],
        option_fair_value_markup=values[
            "ProjectionConfig.option_fair_value_markup"
        ],
        hedge_reference_management_fee=values[
            "ProjectionConfig.hedge_reference_management_fee"
        ],
    )

    base_capital = capital_stresses or CapitalStresses()
    configured_capital = replace(
        base_capital,
        coc_rate=values["CapitalStresses.coc_rate"],
    )

    base_profitability = profitability or ProfitabilitySettings()
    configured_profitability = replace(
        base_profitability,
        hurdle_rate=values["ProfitabilitySettings.hurdle_rate"],
        tax_rate=values["ProfitabilitySettings.tax_rate"],
        capital_earning_spread=values[
            "ProfitabilitySettings.capital_earning_spread"
        ],
    )

    effective_dates = tuple(sorted({row["effective_date"].strip() for row in selected}))
    return CostAssumptionSet(
        assumption_set_id=selected_id,
        value_basis=value_basis,
        source_path=str(source),
        source_sha256=sha256(raw).hexdigest(),
        effective_dates=effective_dates,
        values=values,
        excluded_parameters=excluded,
        product=configured_product,
        expenses=configured_expenses,
        projection=configured_projection,
        capital_stresses=configured_capital,
        profitability=configured_profitability,
    )


__all__ = [
    "CostAssumptionSet",
    "DEFAULT_COST_ASSUMPTIONS_PATH",
    "load_cost_assumptions",
]
