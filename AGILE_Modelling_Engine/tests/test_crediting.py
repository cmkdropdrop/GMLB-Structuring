"""Unit tests: crediting payoffs, option package values, cap solving."""

import numpy as np
import pytest

from agile_engine.crediting import (HedgeMarket, credited_return,
                                    crediting_package_value, fair_cap,
                                    intra_year_value_factor,
                                    crediting_margin_rate)
from agile_engine.product import Protection


class TestCreditedReturn:
    """Payoff table from AGILE.md section 5.3 (cap 12%, partial 10%)."""

    @pytest.mark.parametrize("idx_ret,expected", [
        (0.15, 0.12), (0.06, 0.06), (-0.05, 0.0), (-0.10, 0.0), (-0.18, -0.08),
    ])
    def test_partial_protection_pds_table(self, idx_ret, expected):
        got = credited_return(idx_ret, Protection.PARTIAL_10, cap=0.12)
        assert got == pytest.approx(expected, abs=1e-12)

    @pytest.mark.parametrize("idx_ret,expected", [
        (0.15, 0.062), (0.03, 0.03), (-0.05, 0.0), (-0.40, 0.0),
    ])
    def test_total_protection(self, idx_ret, expected):
        got = credited_return(idx_ret, Protection.TOTAL, cap=0.062)
        assert got == pytest.approx(expected, abs=1e-12)

    def test_vectorised(self):
        r = np.array([-0.2, -0.05, 0.0, 0.05, 0.5])
        out = credited_return(r, Protection.TOTAL, cap=0.06)
        assert out.shape == r.shape
        assert np.all(out >= 0.0) and np.all(out <= 0.06)


class TestPackageValue:
    """Closed-form package values vs Monte-Carlo expectation."""

    def setup_method(self):
        self.r, self.q, self.sigma = 0.04, 0.035, 0.18
        self.rng = np.random.default_rng(7)
        z = self.rng.standard_normal(2_000_000)
        self.x_T = np.exp((self.r - self.q - 0.5 * self.sigma ** 2) + self.sigma * z)

    @pytest.mark.parametrize("protection,cap", [
        (Protection.TOTAL, 0.062), (Protection.PARTIAL_10, 0.13),
    ])
    def test_matches_mc(self, protection, cap):
        payoff = credited_return(self.x_T - 1.0, protection, cap)
        mc = np.exp(-self.r) * np.mean(payoff)
        cf = crediting_package_value(1.0, protection, cap, 1.0, self.r,
                                     self.q, self.sigma)
        assert cf == pytest.approx(mc, abs=4e-4)

    def test_total_protection_value_nonnegative(self):
        v = crediting_package_value(1.0, Protection.TOTAL, 0.06, 1.0,
                                    0.04, 0.04, 0.2)
        assert v > 0.0

    def test_dva_factor_converges_to_credit(self):
        """As tau -> 0 the intra-year factor tends to 1 + credited return."""
        for x0, prot, cap in [(1.15, Protection.TOTAL, 0.062),
                              (0.82, Protection.PARTIAL_10, 0.13)]:
            f = intra_year_value_factor(x0, prot, cap, 1e-9, 0.04, 0.035, 0.18)
            credit = credited_return(x0 - 1.0, prot, cap)
            assert f == pytest.approx(1.0 + credit, abs=1e-6)

    def test_higher_protection_needs_lower_cap(self):
        """Same budget: Total Protection cap < Partial Protection cap (PDS 5.5)."""
        mkt = HedgeMarket(sigma=0.16, q=0.04)
        budget = 0.030
        cap_tp = fair_cap(Protection.TOTAL, budget, 0.04, mkt)
        cap_pp = fair_cap(Protection.PARTIAL_10, budget + 1e-9, 0.04, mkt, hi=5.0) \
            if crediting_package_value(1.0, Protection.PARTIAL_10, 5.0, 1.0, 0.04,
                                       mkt.q, mkt.sigma) > budget else 5.0
        assert cap_tp < cap_pp

    def test_margin_zero_when_budget_neutral(self):
        mkt = HedgeMarket(sigma=0.16, q=0.04)
        r = 0.04
        budget = 1.0 - np.exp(-r)   # full forward-yield budget
        cap = fair_cap(Protection.TOTAL, budget, r, mkt)
        m = crediting_margin_rate(Protection.TOTAL, cap, r, mkt)
        assert m == pytest.approx(0.0, abs=1e-10)
