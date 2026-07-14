"""Default/override contract for the fast four-point portfolio proxy."""

from pathlib import Path

import pytest

from policy_engine import (
    DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
    load_policyholder_model_points,
)
from portfolio_simulations.run_portfolio_risk_analysis import (
    DEFAULT_MODEL_POINTS_PATH as RISK_DEFAULT_MODEL_POINTS_PATH,
)


EXPECTED_DEFAULT_FILENAME = "model_points_policyholders_4_point_proxy.csv"
FULL_GRID_FILENAME = "model_points_policyholders.csv"


def test_all_default_entry_points_use_four_point_proxy():
    assert DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH.name == EXPECTED_DEFAULT_FILENAME
    assert RISK_DEFAULT_MODEL_POINTS_PATH == DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH
    assert DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH.is_file()


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
