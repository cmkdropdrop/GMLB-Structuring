"""Specification for repository market-data and ESG-parameter loading."""

from pathlib import Path

import pytest

from policy_engine import (
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_MODEL_PARAMETERS_PATH,
    Index,
    load_market_assumptions,
)


CONSTANT_EQUITY_VOLATILITY_SENSITIVITY_PATH = (
    Path(__file__).resolve().parents[1]
    / "input_data"
    / "market_data"
    / "model_parameters_constant_equity_vol_low_rate_vol_sensitivity.csv"
)


def test_market_sources_are_repository_relative_and_complete():
    root = Path(__file__).resolve().parents[1]
    assert DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH == (
        root / "input_data" / "market_data" / "australian_zero_curve.csv").resolve()
    assert DEFAULT_MODEL_PARAMETERS_PATH == (
        root / "input_data" / "market_data" / "model_parameters.csv").resolve()

    assumptions = load_market_assumptions()
    assert assumptions.curve_id == "aud_government_zero_2026-06-30"
    assert assumptions.parameter_set_id == "realistic_base_2026-06-30"
    assert assumptions.esg.curve.zero(1.0) == pytest.approx(0.04363404)
    assert assumptions.esg.equity[Index.AUS_EQUITY].sigma == pytest.approx(0.16)
    assert assumptions.esg.heston[Index.AUS_EQUITY].xi == pytest.approx(0.30)
    assert assumptions.esg.hull_white.mean_reversion == pytest.approx(0.10)
    assert set(assumptions.source_sha256) == {"curve", "model_parameters"}


def test_constant_equity_volatility_sensitivity_loads_with_explicit_metadata():
    assumptions = load_market_assumptions(
        model_parameters_path=CONSTANT_EQUITY_VOLATILITY_SENSITIVITY_PATH
    )

    assert assumptions.parameter_set_id == (
        "constant_equity_vol_low_rate_vol_sensitivity_2026-06-30"
    )
    assert assumptions.parameter_calibration_statuses == (
        "sensitivity_proxy_not_calibrated",
    )
    assert assumptions.source_paths["model_parameters"] == str(
        CONSTANT_EQUITY_VOLATILITY_SENSITIVITY_PATH.resolve()
    )
    assert assumptions.esg.hull_white.sigma_r == pytest.approx(0.004)
    for index in Index:
        heston = assumptions.esg.heston[index]
        assert heston.xi == 0.0
        assert heston.v0 == heston.theta > 0.0
