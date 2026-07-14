"""Strict loading of the generic Reference Fund equity allocation.

The equity share is a product input, not market data.  The complementary bond
share is always derived as one minus the loaded equity share so the two sleeves
cannot become inconsistent.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from math import isfinite
from pathlib import Path

from .repository_paths import DEFAULT_EQUITY_ALLOCATION_PATH

DEFAULT_EQUITY_ALLOCATION_ID = "generic_reference_fund"

_COLUMNS = (
    "allocation_id",
    "equity_weight",
    "allocation_basis",
    "description",
)


@dataclass(frozen=True)
class EquityAllocation:
    """One validated product-allocation row plus source provenance."""

    allocation_id: str
    equity_weight: float
    allocation_basis: str
    description: str
    source_path: str
    source_sha256: str

    @property
    def bond_weight(self) -> float:
        """Return the complementary nominal-government-bond share."""
        return 1.0 - self.equity_weight

    def source_metadata(self) -> dict[str, object]:
        """Return JSON-serialisable input and provenance metadata."""
        return {
            "allocation_id": self.allocation_id,
            "equity_weight": self.equity_weight,
            "bond_weight": self.bond_weight,
            "allocation_basis": self.allocation_basis,
            "description": self.description,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
        }


def _required_text(
    value: object,
    *,
    column: str,
    row_number: int,
) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(
            f"Missing {column} in equity-allocation CSV row {row_number}."
        )
    return result


def load_equity_allocation(
    path: str | Path | None = None,
    *,
    allocation_id: str = DEFAULT_EQUITY_ALLOCATION_ID,
) -> EquityAllocation:
    """Load one named equity allocation from the repository CSV."""
    source = Path(path) if path is not None else DEFAULT_EQUITY_ALLOCATION_PATH
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Equity-allocation CSV not found: {source}")

    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Equity-allocation CSV must be UTF-8: {source}") from exc

    reader = csv.DictReader(StringIO(text, newline=""))
    fieldnames = tuple(reader.fieldnames or ())
    if fieldnames != _COLUMNS:
        raise ValueError(
            "Equity-allocation CSV columns must be exactly "
            f"{list(_COLUMNS)} in this order; found {list(fieldnames)}."
        )

    requested_id = str(allocation_id).strip()
    if not requested_id:
        raise ValueError("allocation_id must not be empty.")

    selected: tuple[str, float, str, str] | None = None
    seen_ids: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        if not any(str(value or "").strip() for value in row.values()):
            continue
        row_id = _required_text(
            row.get("allocation_id"),
            column="allocation_id",
            row_number=row_number,
        )
        if row_id in seen_ids:
            raise ValueError(
                f"Duplicate allocation_id {row_id!r} in equity-allocation CSV."
            )
        seen_ids.add(row_id)

        raw_weight = str(row.get("equity_weight") or "").strip()
        try:
            equity_weight = float(raw_weight)
        except ValueError as exc:
            raise ValueError(
                "Invalid equity_weight "
                f"{raw_weight!r} in equity-allocation CSV row {row_number}."
            ) from exc
        if not isfinite(equity_weight) or not 0.0 <= equity_weight <= 1.0:
            raise ValueError(
                "equity_weight must be finite and between 0 and 1 in "
                f"equity-allocation CSV row {row_number}."
            )

        allocation_basis = _required_text(
            row.get("allocation_basis"),
            column="allocation_basis",
            row_number=row_number,
        )
        description = _required_text(
            row.get("description"),
            column="description",
            row_number=row_number,
        )
        if row_id == requested_id:
            selected = (
                row_id,
                equity_weight,
                allocation_basis,
                description,
            )

    if selected is None:
        available = ", ".join(sorted(seen_ids)) or "none"
        raise ValueError(
            f"Unknown equity allocation {requested_id!r}; available: {available}."
        )

    return EquityAllocation(
        allocation_id=selected[0],
        equity_weight=selected[1],
        allocation_basis=selected[2],
        description=selected[3],
        source_path=str(source),
        source_sha256=sha256(raw).hexdigest(),
    )
