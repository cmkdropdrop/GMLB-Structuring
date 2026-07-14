"""Default/override contracts for general and customer-LSMC model points."""

from pathlib import Path

import pytest

from policy_engine import (
    DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
    load_market_assumptions,
    load_policyholder_model_points,
)
from policy_engine.repository_paths import (
    DEFAULT_FAST_POLICYHOLDER_MODEL_POINTS_PATH,
)
from portfolio_simulations.run_portfolio_risk_analysis import (
    DEFAULT_MODEL_POINTS_PATH as RISK_DEFAULT_MODEL_POINTS_PATH,
)


EXPECTED_DEFAULT_FILENAME = "model_points_policyholders_4_point_proxy.csv"
FULL_GRID_FILENAME = "model_points_policyholders.csv"
SENSITIVITY_MODEL_POINTS_FILENAME = (
    "model_points_policyholders_4_point_"
    "constant_equity_vol_low_rate_vol_sensitivity.csv"
)
SENSITIVITY_MODEL_PARAMETERS_FILENAME = (
    "model_parameters_constant_equity_vol_low_rate_vol_sensitivity.csv"
)


def test_risk_customer_lsmc_defaults_to_one_point_fast_proxy():
    assert DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH.name == EXPECTED_DEFAULT_FILENAME
    assert RISK_DEFAULT_MODEL_POINTS_PATH == (
        DEFAULT_FAST_POLICYHOLDER_MODEL_POINTS_PATH
    )
    assert RISK_DEFAULT_MODEL_POINTS_PATH.name == (
        "model_points_policyholders_1_point_proxy.csv"
    )
    assert DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH.is_file()
    assert RISK_DEFAULT_MODEL_POINTS_PATH.is_file()


def test_default_proxy_and_explicit_full_grid_remain_available():
    proxy = load_policyholder_model_points()
    full_path = Path(proxy.source_path).with_name(FULL_GRID_FILENAME)
    full = load_policyholder_model_points(full_path)

    assert len(proxy.model_points) == 4
    assert len(full.model_points) == 48
    assert sum(point.contract_weight for point in proxy.model_points) \
        == pytest.approx(1.0, abs=1e-12)
    assert sum(point.contract_weight for point in full.model_points) \
        == pytest.approx(1.0, abs=1e-12)


def test_four_point_sensitivity_matches_explicit_market_parameter_set():
    root = Path(__file__).resolve().parents[1]
    assumptions = load_market_assumptions(
        model_parameters_path=(
            root
            / "input_data"
            / "market_data"
            / SENSITIVITY_MODEL_PARAMETERS_FILENAME
        )
    )
    model_points = load_policyholder_model_points(
        root
        / "input_data"
        / "model_points_policyholders"
        / SENSITIVITY_MODEL_POINTS_FILENAME,
        expected_market_parameter_set_id=assumptions.parameter_set_id,
        expected_yield_curve_id=assumptions.curve_id,
    )

    assert assumptions.parameter_set_id == (
        "constant_equity_vol_low_rate_vol_sensitivity_2026-06-30"
    )
    assert model_points.market_parameter_set_id == assumptions.parameter_set_id
    assert model_points.yield_curve_id == assumptions.curve_id
    assert len(model_points.model_points) == 4
