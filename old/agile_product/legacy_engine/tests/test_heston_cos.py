"""Regression tests for the v1.1.0 review fix: Heston COS package pricing.

Background. The DVA replication values every crediting package (bull call
spread, minus the 10%-OTM put for Partial Protection) on each monthly grid
point and extracts the cap-setting margin at anniversaries. Up to v1.0.7
those packages were priced with a Black-Scholes closed form on the effective
volatility sqrt(E[int v]) under the Heston ESGs. A flat effective volatility
cannot capture the return-variance correlation (rho_sv = -0.6 base): the
short OTM call of the spread is overpriced relative to Heston, the package
is underpriced by O(30bp p.a.), and the projection booked that amount as
extra crediting margin. The market-consistency identity showed the leak:
identity_gap ~ +2.5% of the premium under Heston / Heston-Hull-White vs.
< 10bp under BS / BS-HW.

Fix. Packages are priced with the COS method (Fang/Oosterlee 2008) on the
Heston characteristic function, conditional on the pathwise variance state,
with Hull-White rate contributions and the hedge-vol spread mapped onto an
independent Gaussian variance add-on. `ProjectionConfig.heston_cos = False`
restores the previous approximation.
"""

import numpy as np
import pytest

from agile_engine import (AgileProduct, BehaviourModel, ESGConfig,
                          MortalityTable, PolicySpec, ProjectionConfig,
                          ValuationSettings, YieldCurve, value_contract)
from agile_engine.crediting import (credited_return, crediting_package_value,
                                    heston_package_value, heston_put_cos)
from agile_engine.esg import HestonParams
from agile_engine.product import Protection

CURVE = YieldCurve.flat(0.04)
CFG = ESGConfig(curve=CURVE)
MORT = MortalityTable.gompertz_makeham()
POLICY = PolicySpec(age=65, income_start_year=5)
HP = HestonParams(v0=0.0256, theta=0.0256, kappa=1.8, xi=0.35, rho_sv=-0.6)
R, Q = 0.04, 0.04


def _heston_mc_terminal(n=250_000, m=64, seed=1):
    """Brute-force fine-Euler simulation of the 1y gross return under HP."""
    rng = np.random.default_rng(seed)
    h = 1.0 / m
    v = np.full(n, HP.v0)
    x = np.zeros(n)
    for _ in range(m):
        z1 = rng.standard_normal(n)
        z2 = HP.rho_sv * z1 + np.sqrt(1 - HP.rho_sv ** 2) * rng.standard_normal(n)
        vp = np.maximum(v, 0.0)
        x += (R - Q - 0.5 * vp) * h + np.sqrt(vp * h) * z1
        v += HP.kappa * (HP.theta - vp) * h + HP.xi * np.sqrt(vp * h) * z2
    return np.exp(x)


class TestCosPricer:

    def test_degenerates_to_bs_when_vol_of_vol_vanishes(self):
        """xi -> 0, rho = 0: COS must reproduce the BS closed form."""
        hp0 = HestonParams(v0=0.0256, theta=0.0256, kappa=1.8, xi=1e-6,
                           rho_sv=0.0)
        for prot, cap in [(Protection.TOTAL, 0.062),
                          (Protection.PARTIAL_10, 0.13)]:
            for x0 in (0.85, 1.0, 1.12):
                cos = heston_package_value(np.array([x0]), prot, cap, 1.0,
                                           R, Q, np.array([0.0256]), hp0)[0]
                bs = float(crediting_package_value(x0, prot, cap, 1.0, R, Q,
                                                   0.16))
                assert cos == pytest.approx(bs, abs=3e-6), (prot, x0)

    def test_puts_and_packages_match_brute_force_heston(self):
        """COS vs. fine-Euler MC within the MC error at base parameters."""
        x_t = _heston_mc_terminal()
        for k in (0.9, 1.0, 1.062):
            mc = np.exp(-R) * float(np.mean(np.maximum(k - x_t, 0.0)))
            cos = heston_put_cos(np.array([1.0]), k, 1.0, R, Q,
                                 np.array([HP.v0]), HP)[0]
            assert cos == pytest.approx(mc, abs=8e-4), k
        for prot, cap in [(Protection.TOTAL, 0.062),
                          (Protection.PARTIAL_10, 0.13)]:
            mc = np.exp(-R) * float(np.mean(
                credited_return(x_t - 1.0, prot, cap)))
            cos = heston_package_value(np.array([1.0]), prot, cap, 1.0, R, Q,
                                       np.array([HP.v0]), HP)[0]
            assert cos == pytest.approx(mc, abs=8e-4), prot

    def test_deep_itm_put_parity(self):
        """Martingale consistency: Put(K=3) ~ K e^{-r} - x0 e^{-q}."""
        p3 = heston_put_cos(np.array([1.0]), 3.0, 1.0, R, Q,
                            np.array([HP.v0]), HP)[0]
        assert p3 == pytest.approx(3 * np.exp(-R) - np.exp(-Q), abs=5e-5)

    def test_skew_effect_direction_and_size(self):
        """With rho < 0 the TP package is worth MORE than the BS proxy
        (short OTM call cheapens); the effect is the ~30bp p.a. that used
        to leak into the crediting margin."""
        cos = heston_package_value(np.array([1.0]), Protection.TOTAL, 0.062,
                                   1.0, R, Q, np.array([HP.v0]), HP)[0]
        bs = float(crediting_package_value(1.0, Protection.TOTAL, 0.062, 1.0,
                                           R, Q, np.sqrt(HP.v0)))
        assert 0.0015 < cos - bs < 0.007

    def test_gaussian_add_on_is_exact_in_the_bs_limit(self):
        """xi -> 0, rho = 0: COS with add-on w equals BS at sqrt(v0 + w).

        The add-on is an exact independent-variance composition (CF product),
        not a heuristic — this pins down both direction and size.
        """
        hp0 = HestonParams(v0=0.0256, theta=0.0256, kappa=1.8, xi=1e-6,
                           rho_sv=0.0)
        cosw = heston_package_value(np.array([1.0]), Protection.TOTAL, 0.062,
                                    1.0, R, Q, np.array([0.0256]), hp0,
                                    0.01)[0]
        bsw = float(crediting_package_value(
            1.0, Protection.TOTAL, 0.062, 1.0, R, Q,
            float(np.sqrt(0.0256 + 0.01))))
        assert cosw == pytest.approx(bsw, abs=5e-7)

    def test_gaussian_add_on_dilutes_the_skew_premium(self):
        """Under rho = -0.6 the TP package trades above the flat-vol BS
        proxy; mixing in independent Gaussian variance dilutes the skew and
        moves the value back toward the BS level (direction verified against
        brute-force MC: 0.02709 -> 0.02583 for w = 1%)."""
        bs = float(crediting_package_value(1.0, Protection.TOTAL, 0.062, 1.0,
                                           R, Q, float(np.sqrt(HP.v0))))
        c0 = heston_package_value(np.array([1.0]), Protection.TOTAL, 0.062,
                                  1.0, R, Q, np.array([HP.v0]), HP, 0.0)[0]
        c1 = heston_package_value(np.array([1.0]), Protection.TOTAL, 0.062,
                                  1.0, R, Q, np.array([HP.v0]), HP, 0.01)[0]
        assert bs < c1 < c0

    def test_vectorised_over_paths_and_intra_year(self):
        x0 = np.array([0.8, 0.95, 1.0, 1.1, 1.3])
        v = np.array([0.01, 0.02, 0.0256, 0.04, 0.09])
        out = heston_package_value(x0, Protection.PARTIAL_10, 0.13, 1.0 / 12,
                                   R, Q, v, HP)
        assert out.shape == (5,) and np.all(np.isfinite(out))
        # scalar spot with pathwise rates/variances broadcasts too
        r_arr = np.full(7, R)
        out2 = heston_package_value(1.0, Protection.TOTAL, 0.062, 1.0, r_arr,
                                    Q, np.full(7, HP.v0), HP)
        assert out2.shape == (7,)


class TestHestonIdentity:
    """The market-consistency identity now holds under the Heston ESGs.

    Residual tolerance covers the ESG Euler discretisation (full-truncation,
    4 substeps/month) and MC noise at 2,000 paths; before the fix the gap
    was +2.5% (heston) / +2.6% (heston_hull_white) at the same settings.
    """

    @pytest.mark.parametrize("model,tol", [("heston", 0.008),
                                           ("heston_hull_white", 0.008)])
    def test_identity_gap_small(self, model, tol):
        settings = ValuationSettings(model=model, n_paths=2000, seed=7,
                                     horizon_years=40.0)
        res = value_contract(AgileProduct(), POLICY, CFG, MORT,
                             BehaviourModel(), settings=settings)
        assert abs(res.identity_gap) < tol, res.identity_gap

    def test_legacy_flag_reproduces_effective_vol_approximation(self):
        """`heston_cos=False` restores the (biased) BS approximation, and the
        bias it removes is material — this documents why the fix matters."""
        settings_cos = ValuationSettings(model="heston", n_paths=1500, seed=7,
                                         horizon_years=35.0)
        settings_bs = ValuationSettings(
            model="heston", n_paths=1500, seed=7, horizon_years=35.0,
            projection=ProjectionConfig(heston_cos=False))
        res_cos = value_contract(AgileProduct(), POLICY, CFG, MORT,
                                 BehaviourModel(), settings=settings_cos)
        res_bs = value_contract(AgileProduct(), POLICY, CFG, MORT,
                                BehaviourModel(), settings=settings_bs)
        assert res_bs.identity_gap > res_cos.identity_gap + 0.015
        # the removed bias sat in the crediting margin (insurer income)
        assert res_bs.pv["crediting_margin"] > res_cos.pv["crediting_margin"]
