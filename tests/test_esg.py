"""ESG tests: martingale properties, curve consistency, term structures."""

import numpy as np
import pytest

from policy_engine.curves import YieldCurve
from policy_engine.esg import (ESGConfig, HestonParams, Measure, simulate)
from policy_engine.market_assumptions import load_market_assumptions
from policy_engine.repository_paths import MARKET_DATA_DIRECTORY
from policy_engine.product import Index


@pytest.fixture(scope="module")
def config():
    curve = YieldCurve.from_rates((1, 2, 5, 10, 20, 30),
                                  (0.038, 0.039, 0.041, 0.043, 0.044, 0.044))
    return ESGConfig(curve=curve)


@pytest.mark.parametrize("model,tol_bp", [
    ("black_scholes", 60), ("heston", 80),
    ("hull_white_bs", 60), ("heston_hull_white", 90),
])
def test_equity_martingale(config, model, tol_bp):
    """E[D_T S_T] = e^{-qT} for the configured return-index carry under Q."""
    scen = simulate(model, config, horizon_years=10.0, n_paths=40_000, seed=11)
    for ix in (Index.AUS_EQUITY, Index.GLOBAL_EQUITY):
        q = config.equity[ix].dividend_yield
        for step in (12, 60, 120):
            T = scen.times[step]
            lhs = float(np.mean(scen.discount[:, step] * scen.index_levels[ix][:, step]))
            rhs = float(np.exp(-q * T))
            assert lhs == pytest.approx(rhs, rel=tol_bp * 1e-4), (model, ix, T)


@pytest.mark.parametrize("model", ["hull_white_bs", "heston_hull_white"])
def test_bond_reproduction(config, model):
    """E[D_T] must reproduce the initial discount curve under HW."""
    scen = simulate(model, config, horizon_years=15.0, n_paths=40_000, seed=13)
    for step in (12, 60, 120, 180):
        T = scen.times[step]
        assert float(np.mean(scen.discount[:, step])) == pytest.approx(
            float(config.curve.df(T)), rel=6e-3), (model, T)


def test_deterministic_discount_matches_curve(config):
    scen = simulate("black_scholes", config, 5.0, 100, seed=1)
    T = scen.times[-1]
    assert scen.discount[0, -1] == pytest.approx(float(config.curve.df(T)), rel=1e-12)


def test_real_world_drift_exceeds_risk_neutral(config):
    q_scen = simulate("black_scholes", config, 10.0, 20_000, seed=5,
                      measure=Measure.RISK_NEUTRAL)
    p_scen = simulate("black_scholes", config, 10.0, 20_000, seed=5,
                      measure=Measure.REAL_WORLD)
    ix = Index.AUS_EQUITY
    assert (np.mean(p_scen.index_levels[ix][:, -1])
            > np.mean(q_scen.index_levels[ix][:, -1]))


def test_hw_zero_rate_consistency(config):
    """Pathwise HW zero at t=0 must match the initial curve."""
    scen = simulate("hull_white_bs", config, 2.0, 1000, seed=3)
    z0 = scen.zero_rate(0, 5.0)
    expected = np.expm1(config.curve.forward_zero(0.0, 5.0))
    assert float(np.mean(z0)) == pytest.approx(expected, abs=2e-3)


def test_heston_effective_vol(config):
    scen = simulate("heston", config, 1.0, 100, seed=4)
    sig = scen.effective_bs_vol(Index.AUS_EQUITY, 0, 1.0)
    hp = config.heston[Index.AUS_EQUITY]
    assert np.all(sig > 0.5 * np.sqrt(hp.theta)) and np.all(sig < 2.0 * np.sqrt(hp.theta))


def test_zero_vol_of_variance_requires_stationary_initial_variance():
    with pytest.raises(
        ValueError,
        match="xi=0 fixed-volatility boundary requires v0=theta>0",
    ):
        HestonParams(v0=0.02, theta=0.03, kappa=1.8, xi=0.0)


def test_constant_equity_volatility_sensitivity_keeps_variance_constant():
    assumptions = load_market_assumptions(
        model_parameters_path=(
            MARKET_DATA_DIRECTORY
            / "model_parameters_constant_equity_vol_low_rate_vol_sensitivity.csv"
        )
    )
    scenarios = simulate(
        "heston_hull_white",
        assumptions.esg,
        horizon_years=2.0,
        n_paths=37,
        seed=41,
        substeps=4,
    )

    assert assumptions.esg.hull_white.sigma_r == pytest.approx(0.004)
    assert scenarios.variance is not None
    for index in Index:
        expected = assumptions.esg.heston[index].theta
        assert np.array_equal(
            scenarios.variance[index],
            np.full_like(scenarios.variance[index], expected),
        )
