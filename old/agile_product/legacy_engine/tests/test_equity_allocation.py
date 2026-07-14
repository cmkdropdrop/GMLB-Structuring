"""Regression tests for the product-level equity-allocation input."""

from __future__ import annotations

from pathlib import Path

import pytest

from agile_engine import (
    DEFAULT_EQUITY_ALLOCATION_ID,
    DEFAULT_EQUITY_ALLOCATION_PATH,
    ReferenceFundSpec,
    load_equity_allocation,
)


def _write_allocation(path: Path, equity_weight: str) -> None:
    path.write_text(
        "allocation_id,equity_weight,allocation_basis,description\n"
        f"generic_reference_fund,{equity_weight},product_design_input,Test row\n",
        encoding="utf-8",
    )


def test_default_equity_allocation_is_loaded_with_provenance() -> None:
    allocation = load_equity_allocation()

    assert allocation.allocation_id == DEFAULT_EQUITY_ALLOCATION_ID
    assert allocation.equity_weight == pytest.approx(0.30)
    assert allocation.bond_weight == pytest.approx(0.70)
    assert allocation.allocation_basis == "product_design_input"
    assert Path(allocation.source_path) == DEFAULT_EQUITY_ALLOCATION_PATH.resolve()
    assert len(allocation.source_sha256) == 64
    assert allocation.source_metadata()["bond_weight"] == pytest.approx(0.70)


def test_reference_fund_accepts_csv_configurable_equity_weight() -> None:
    reference_fund = ReferenceFundSpec(equity_weight=0.45)

    assert reference_fund.equity_weight == pytest.approx(0.45)


@pytest.mark.parametrize("equity_weight", ["-0.01", "1.01", "nan"])
def test_loader_rejects_invalid_equity_weight(
    tmp_path: Path,
    equity_weight: str,
) -> None:
    path = tmp_path / "equity_allocation.csv"
    _write_allocation(path, equity_weight)

    with pytest.raises(ValueError, match="equity_weight"):
        load_equity_allocation(path)


@pytest.mark.parametrize("equity_weight", [-0.01, 1.01])
def test_reference_fund_rejects_out_of_range_equity_weight(
    equity_weight: float,
) -> None:
    with pytest.raises(ValueError, match="equity_weight"):
        ReferenceFundSpec(equity_weight=equity_weight)
