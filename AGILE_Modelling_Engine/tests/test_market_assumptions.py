"""Specification for repository market-data and ESG-parameter loading."""

from pathlib import Path

import pytest

from agile_engine import (
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_MODEL_PARAMETERS_PATH,
    Index,
    load_market_assumptions,
)


def test_market_sources_are_repository_relative_and_complete():
    root = Path(__file__).resolve().parents[1]
    assert DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH == (
        root / "input_market_data" / "australian_zero_curve.csv").resolve()
    assert DEFAULT_MODEL_PARAMETERS_PATH == (
        root / "input_market_data" / "model_parameters.csv").resolve()

    assumptions = load_market_assumptions()
    assert assumptions.curve_id == "aud_government_zero_2026-06-30"
    assert assumptions.parameter_set_id == "realistic_base_2026-06-30"
    assert assumptions.esg.curve.zero(1.0) == pytest.approx(0.04363404)
    assert assumptions.esg.equity[Index.AUS_EQUITY].sigma == pytest.approx(0.16)
    assert assumptions.esg.heston[Index.AUS_EQUITY].xi == pytest.approx(0.30)
    assert assumptions.esg.hull_white.mean_reversion == pytest.approx(0.10)
    assert set(assumptions.source_sha256) == {"curve", "model_parameters"}
