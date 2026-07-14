"""Portable repository paths shared by the engine and command-line runners.

All defaults are derived from this file's location.  A cloned repository can
therefore be installed or run without editing machine-specific paths.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_ROOT = PROJECT_ROOT / "code"
INPUT_DATA_ROOT = PROJECT_ROOT / "input_data"
DOCUMENTS_ROOT = PROJECT_ROOT / "documents"
RESULTS_ROOT = PROJECT_ROOT / "results"
RESULTS_RUNS_ROOT = RESULTS_ROOT / "runs"

MARKET_DATA_DIRECTORY = INPUT_DATA_ROOT / "market_data"
COST_ASSUMPTIONS_DIRECTORY = INPUT_DATA_ROOT / "cost_assumptions"
DYNAMIC_BEHAVIOUR_DIRECTORY = INPUT_DATA_ROOT / "dynamic_behaviour"
EQUITY_ALLOCATION_DIRECTORY = INPUT_DATA_ROOT / "equity_allocation"
MC_ANALYSIS_DIRECTORY = INPUT_DATA_ROOT / "mc_analysis"
MODEL_POINTS_DIRECTORY = INPUT_DATA_ROOT / "model_points_policyholders"

DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH = (
    MARKET_DATA_DIRECTORY / "australian_zero_curve.csv"
)
DEFAULT_MODEL_PARAMETERS_PATH = MARKET_DATA_DIRECTORY / "model_parameters.csv"
DEFAULT_COST_ASSUMPTIONS_PATH = (
    COST_ASSUMPTIONS_DIRECTORY / "cost_assumptions.csv"
)
DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY = DYNAMIC_BEHAVIOUR_DIRECTORY
DEFAULT_EQUITY_ALLOCATION_PATH = (
    EQUITY_ALLOCATION_DIRECTORY / "equity_allocation.csv"
)
DEFAULT_MC_ANALYSIS_PATH = MC_ANALYSIS_DIRECTORY / "portfolio_analysis.csv"
DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH = (
    MODEL_POINTS_DIRECTORY / "model_points_policyholders_4_point_proxy.csv"
)
DEFAULT_FAST_POLICYHOLDER_MODEL_POINTS_PATH = (
    MODEL_POINTS_DIRECTORY / "model_points_policyholders_1_point_proxy.csv"
)
DEFAULT_FULL_POLICYHOLDER_MODEL_POINTS_PATH = (
    MODEL_POINTS_DIRECTORY / "model_points_policyholders.csv"
)

Q_CACHE_ROOT = RESULTS_ROOT / "cache"
Q_MARKET_PATH_CACHE_ROOT = Q_CACHE_ROOT / "q_market_paths"
Q_HEDGE_PRICE_CACHE_ROOT = Q_CACHE_ROOT / "q_hedge_prices"


def run_output_directory(runner_name: str) -> Path:
    """Return the canonical unversioned output directory for one runner."""
    if not runner_name or Path(runner_name).name != runner_name:
        raise ValueError("runner_name must be one non-empty path component")
    return RESULTS_RUNS_ROOT / runner_name
