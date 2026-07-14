"""Unit tests: crediting payoffs, option package values, cap solving."""

import numpy as np
import pytest

from policy_engine.crediting import (HedgeCapLegMode, HedgeMarket,
                                    credited_return, crediting_package_value,
                                    fair_cap, hedge_option_package_value,
                                    intra_year_value_factor,
                                    retained_excess_return,
                                    crediting_margin_rate)
from policy_engine.product import Protection


class TestCreditedReturn:
    """Protected-return payoff table (12% cap, 10% participation floor)."""

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


class TestHedgeCapLeg:
    def test_sold_is_default_and_matches_total_protection_package(self):
        args = dict(x0=1.0, cap=0.062, tau=1.0, r=0.04, q=0.035,
                    sigma=0.18)
        hedge = hedge_option_package_value(**args)
        explicit = hedge_option_package_value(
            **args, cap_leg_mode=HedgeCapLegMode.SOLD)
        customer_package = crediting_package_value(
            args["x0"], Protection.TOTAL, args["cap"], args["tau"],
            args["r"], args["q"], args["sigma"])
        assert hedge == pytest.approx(explicit)
        assert hedge == pytest.approx(customer_package)

    def test_not_sold_is_uncapped_long_call(self):
        cap = 0.06
        sold = hedge_option_package_value(
            1.0, cap, 1.0, 0.04, 0.0, 0.2, HedgeCapLegMode.SOLD)
        not_sold = hedge_option_package_value(
            1.0, cap, 1.0, 0.04, 0.0, 0.2, HedgeCapLegMode.NOT_SOLD)
        assert not_sold > sold > 0.0

        # At expiry the package definitions reduce directly to their payoffs.
        assert hedge_option_package_value(
            1.15, cap, 0.0, 0.04, 0.0, 0.2,
            HedgeCapLegMode.SOLD) == pytest.approx(cap)
        assert hedge_option_package_value(
            1.15, cap, 0.0, 0.04, 0.0, 0.2,
            HedgeCapLegMode.NOT_SOLD) == pytest.approx(0.15)

    def test_package_is_vectorised(self):
        x0 = np.array([0.9, 1.0, 1.1])
        rates = np.array([0.02, 0.03, 0.04])
        vols = np.array([0.15, 0.18, 0.21])
        out = hedge_option_package_value(
            x0, 0.06, 0.75, rates, 0.0, vols,
            HedgeCapLegMode.NOT_SOLD)
        assert out.shape == x0.shape
        assert np.all(np.isfinite(out))
        assert np.all(out >= 0.0)

    @pytest.mark.parametrize("mode,expected", [
        (HedgeCapLegMode.SOLD, [0.0, 0.0, 0.0, 0.0]),
        (HedgeCapLegMode.NOT_SOLD, [0.0, 0.0, 0.0, 0.09]),
        ("not_sold", [0.0, 0.0, 0.0, 0.09]),
    ])
    def test_retained_excess_return(self, mode, expected):
        index_return = np.array([-0.1, 0.0, 0.06, 0.15])
        got = retained_excess_return(index_return, 0.06, mode)
        assert got == pytest.approx(expected)

    def test_retained_excess_scalar(self):
        assert retained_excess_return(
            0.15, 0.06, HedgeCapLegMode.NOT_SOLD) == pytest.approx(0.09)
        assert retained_excess_return(
            0.15, 0.06, HedgeCapLegMode.SOLD) == 0.0

    @pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
    def test_non_finite_inputs_rejected(self, bad):
        with pytest.raises(ValueError, match="finite"):
            retained_excess_return(bad, 0.06)
        with pytest.raises(ValueError, match="finite"):
            hedge_option_package_value(1.0, 0.06, 1.0, bad, 0.0, 0.2)

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValueError, match="cap-leg mode"):
            retained_excess_return(0.15, 0.06, "invalid")
