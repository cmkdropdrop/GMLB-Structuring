"""Mortality models.

Provides a generational mortality basis for Australian retirees:

* ``MortalityTable.gompertz_makeham`` — smooth parametric base table calibrated
  approximately to the Australian Life Tables 2020-22 shape (ILLUSTRATIVE;
  replace with the pricing basis via `MortalityTable.from_qx`),
* mortality improvements (flat rate with taper at high ages, generational),
* multiplicative stresses (Solvency-II longevity/mortality shocks),
* joint-life (last survivor) survival used for the Spouse option,
* trapezoidal approximation of complete life expectancy.

References: Fung/Ignatieva/Sherris (2014) motivate systematic mortality risk
for GLWBs; the engine treats longevity risk via the capital-module stresses
on this deterministic generational basis (standard-formula style).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional, Sequence

import numpy as np
from numpy.typing import NDArray

from .product import Sex

Array = NDArray[np.float64]

MAX_AGE = 115


@dataclass(frozen=True)
class MortalityTable:
    """Annual base-table mortality rates ``qx`` by age, plus improvements.

    Parameters
    ----------
    qx_male, qx_female:
        Arrays of length ``MAX_AGE + 1`` with annual death probabilities by
        exact age (index = age). ``qx[MAX_AGE] = 1``.
    base_year:
        Calendar year of the base table.
    improvement_rate:
        Annual mortality improvement applied generationally:
        ``q(x, year) = qx[x] * (1 - improvement(x)) ** (year - base_year)``.
    improvement_taper_age / improvement_end_age:
        Improvement is constant to `taper_age`, then linearly reduced to zero
        at `end_age`.
    stress_multiplier:
        Multiplicative stress on all rates (SII longevity: 0.80).
    q_add_first_year:
        Additive shock to q applied in the first projection year only.  Policy
        duration is deliberately distinct from ``years_from_base`` (calendar
        time used for mortality improvements); used for the mortality-
        catastrophe capital stress.
    """

    qx_male: Array
    qx_female: Array
    base_year: int = 2022
    improvement_rate: float = 0.0125
    improvement_taper_age: float = 90.0
    improvement_end_age: float = 110.0
    stress_multiplier: float = 1.0
    q_add_first_year: float = 0.0

    def __post_init__(self) -> None:
        arrays = []
        for name in ("qx_male", "qx_female"):
            arr = np.array(getattr(self, name), dtype=float, copy=True)
            if arr.shape != (MAX_AGE + 1,) or not np.all(np.isfinite(arr)):
                raise ValueError(f"{name} must be a finite array of length {MAX_AGE + 1}.")
            if np.any((arr < 0.0) | (arr > 1.0)) or not np.isclose(arr[-1], 1.0):
                raise ValueError(f"{name} must contain probabilities in [0,1] and end at 1.")
            arr.setflags(write=False)
            object.__setattr__(self, name, arr)
            arrays.append(arr)
        params = np.asarray([self.base_year, self.improvement_rate,
                             self.improvement_taper_age, self.improvement_end_age,
                             self.stress_multiplier, self.q_add_first_year], dtype=float)
        if not np.all(np.isfinite(params)):
            raise ValueError("Mortality parameters must be finite.")
        if not 0.0 <= self.improvement_rate < 1.0:
            raise ValueError("improvement_rate must be in [0, 1).")
        if self.improvement_end_age <= self.improvement_taper_age:
            raise ValueError("improvement_end_age must exceed taper age.")
        if self.stress_multiplier < 0.0 or self.q_add_first_year < 0.0:
            raise ValueError("Mortality stresses must be non-negative.")

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @staticmethod
    def gompertz_makeham(a_male: float = 3.0e-4, b_male: float = 1.7e-5, c_male: float = 1.103,
                         a_female: float = 2.0e-4, b_female: float = 0.9e-5, c_female: float = 1.106,
                         **kwargs) -> "MortalityTable":
        """ILLUSTRATIVE Gompertz-Makeham fit, approximating ALT 2020-22 shape.

        mu(x) = A + B * c**x;  q(x) = 1 - exp(-integral of mu over [x, x+1]).
        """
        ages = np.arange(MAX_AGE + 1, dtype=float)

        def q_from_gm(a: float, b: float, c: float) -> Array:
            lnc = np.log(c)
            integral = a + b * (c ** ages) * (c - 1.0) / lnc
            q = 1.0 - np.exp(-integral)
            q = np.clip(q, 1e-6, 1.0)
            q[-1] = 1.0
            return q

        return MortalityTable(qx_male=q_from_gm(a_male, b_male, c_male),
                              qx_female=q_from_gm(a_female, b_female, c_female),
                              **kwargs)

    @staticmethod
    def from_qx(ages: Sequence[float], qx_male: Sequence[float],
                qx_female: Sequence[float], *,
                allow_constant_extrapolation: bool = False,
                **kwargs) -> "MortalityTable":
        """Build from an external table (e.g. ALT 2020-22), interpolating gaps.

        Production input must cover ages 0 through 114.  Constant endpoint
        extrapolation is available only through an explicit research override;
        silently extending a two-age table over a lifetime is unsafe.
        """
        ages_arr = np.asarray(ages, float)
        qm_in = np.asarray(qx_male, float)
        qf_in = np.asarray(qx_female, float)
        if ages_arr.ndim != 1 or len(ages_arr) < 2 or qm_in.shape != ages_arr.shape \
                or qf_in.shape != ages_arr.shape:
            raise ValueError("ages and qx arrays must be one-dimensional and equally sized.")
        if not np.all(np.isfinite(ages_arr)) or not np.all(np.diff(ages_arr) > 0) \
                or not np.all(np.isfinite(qm_in)) or not np.all(np.isfinite(qf_in)):
            raise ValueError("Mortality inputs must be finite with strictly increasing ages.")
        if np.any((qm_in < 0.0) | (qm_in > 1.0)) or np.any((qf_in < 0.0) | (qf_in > 1.0)):
            raise ValueError("qx inputs must be probabilities in [0, 1].")
        if not isinstance(allow_constant_extrapolation, (bool, np.bool_)):
            raise ValueError("allow_constant_extrapolation must be boolean.")
        if not allow_constant_extrapolation and (ages_arr[0] > 0.0 or ages_arr[-1] < MAX_AGE - 1):
            raise ValueError("Mortality table must cover ages 0..114; explicitly opt in to endpoint extrapolation.")
        full_ages = np.arange(MAX_AGE + 1, dtype=float)
        qm = np.interp(full_ages, ages_arr, qm_in)
        qf = np.interp(full_ages, ages_arr, qf_in)
        qm[-1] = qf[-1] = 1.0
        return MortalityTable(qx_male=np.clip(qm, 1e-6, 1.0),
                              qx_female=np.clip(qf, 1e-6, 1.0), **kwargs)

    def stressed(self, multiplier: float) -> "MortalityTable":
        if not np.isfinite(multiplier) or multiplier < 0.0:
            raise ValueError("Mortality stress multiplier must be finite and non-negative.")
        return replace(self, stress_multiplier=self.stress_multiplier * multiplier)

    # ------------------------------------------------------------------ #
    # Rates
    # ------------------------------------------------------------------ #

    def _base_qx(self, sex: Sex) -> Array:
        try:
            sex = Sex(sex)
        except (TypeError, ValueError) as exc:
            raise ValueError("sex must be Sex.MALE/'M' or Sex.FEMALE/'F'.") from exc
        return self.qx_male if sex == Sex.MALE else self.qx_female

    def _improvement(self, age: float | Array) -> float | Array:
        age_arr = np.asarray(age, dtype=float)
        w = np.clip((self.improvement_end_age - age_arr) /
                    max(self.improvement_end_age - self.improvement_taper_age, 1e-9),
                    0.0, 1.0)
        out = self.improvement_rate * w
        return float(out) if np.ndim(age) == 0 else out

    def q(self, age: float | Array, sex: Sex, calendar_year: Optional[float] = None,
          years_from_base: Optional[float] = None,
          projection_duration: Optional[float] = None) -> float | Array:
        """Annual death probability at exact age, generationally improved."""
        age_arr = np.asarray(age, dtype=float)
        if years_from_base is None:
            years_from_base = 0.0 if calendar_year is None else calendar_year - self.base_year
        idx = np.clip(age_arr.astype(int), 0, MAX_AGE)
        frac = np.clip(age_arr - idx, 0.0, 1.0)
        table = self._base_qx(sex)
        # q[MAX_AGE] is a terminal sentinel, not a genuine observed rate to
        # interpolate into the preceding year.  Fractional ages below the
        # terminal boundary therefore use at most q[MAX_AGE - 1]; the monthly
        # curve separately forces death in the interval ending at MAX_AGE.
        next_idx = np.minimum(idx + 1, MAX_AGE - 1)
        base = (1.0 - frac) * table[idx] + frac * table[next_idx]
        imp = (1.0 - self._improvement(age_arr)) ** max(float(years_from_base), 0.0)
        q = np.clip(base * imp * self.stress_multiplier, 0.0, 1.0)
        if projection_duration is not None and (
                not np.isfinite(projection_duration) or projection_duration < 0.0):
            raise ValueError("projection_duration must be finite and non-negative.")
        if self.q_add_first_year != 0.0:
            if projection_duration is None:
                raise ValueError("projection_duration is required when q_add_first_year is non-zero.")
            if float(projection_duration) < 1.0:
                q = np.clip(q + self.q_add_first_year, 0.0, 1.0)
        q = np.where(age_arr >= MAX_AGE, 1.0, q)
        return float(q) if np.ndim(age) == 0 else q

    def q_monthly(self, age: float, sex: Sex, years_from_base: float,
                  projection_duration: Optional[float] = None) -> float:
        """Locally convert one annual ``q`` to a monthly probability.

        Productive lifetime projections should use :meth:`monthly_q_curve` so
        the annual rate is anchored once per Policy Year.  Re-evaluating this
        local converter at every fractional age would not reconcile twelve
        monthly survival factors to the underlying annual ``q``.
        """
        q_a = self.q(age, sex, years_from_base=years_from_base,
                     projection_duration=projection_duration)
        return float(1.0 - (1.0 - q_a) ** (1.0 / 12.0))

    def monthly_q_curve(
        self,
        age: float,
        sex: Sex,
        horizon_months: int,
        years_from_base: float = 0.0,
        projection_duration_start: float = 0.0,
    ) -> Array:
        """Conditional monthly death probabilities on a Policy-Year basis.

        One generational annual ``q`` is determined at each Policy
        Anniversary and converted by constant force for the following twelve
        months.  Outside the terminal year this guarantees that the product
        of the twelve monthly survival factors equals ``1 - q_annual``.
        A curve requested between anniversaries first uses the remainder of
        the already anchored Policy-Year rate; ``projection_duration_start``
        therefore has to lie on the engine's monthly grid.

        ``MAX_AGE`` is a hard terminal age: the interval whose end first
        reaches that age has death probability one.  This makes the cashflow
        projection, survival helpers and behaviour annuity factors use the
        same convention and avoids a technical residual death one year later.
        """
        if isinstance(horizon_months, (bool, np.bool_)) \
                or not isinstance(horizon_months, (int, np.integer)) \
                or horizon_months < 0:
            raise ValueError("horizon_months must be a non-negative integer.")
        inputs = np.asarray(
            [age, years_from_base, projection_duration_start], dtype=float)
        if not np.all(np.isfinite(inputs)) or projection_duration_start < 0.0:
            raise ValueError(
                "Monthly mortality inputs must be finite and projection "
                "duration non-negative."
            )
        start_month_float = float(projection_duration_start) * 12.0
        start_month = int(round(start_month_float))
        if abs(start_month_float - start_month) > 1.0e-9:
            raise ValueError(
                "projection_duration_start must fall on the monthly grid."
            )

        n_months = int(horizon_months)
        monthly = np.zeros(n_months, dtype=float)
        issue_age = float(age) - float(projection_duration_start)
        issue_years_from_base = (
            float(years_from_base) - float(projection_duration_start)
        )
        first_policy_year = start_month // 12
        last_absolute_month = start_month + n_months
        final_policy_year = (
            (last_absolute_month - 1) // 12
            if n_months
            else first_policy_year - 1
        )
        for policy_year in range(first_policy_year, final_policy_year + 1):
            q_annual = self.q(
                issue_age + policy_year,
                sex,
                years_from_base=issue_years_from_base + policy_year,
                projection_duration=float(policy_year),
            )
            q_month = 1.0 - (1.0 - float(q_annual)) ** (1.0 / 12.0)
            absolute_lo = max(start_month, policy_year * 12)
            absolute_hi = min(last_absolute_month, (policy_year + 1) * 12)
            lo = absolute_lo - start_month
            hi = absolute_hi - start_month
            monthly[lo:hi] = q_month

        if n_months:
            end_ages = float(age) + np.arange(1, n_months + 1) / 12.0
            monthly[end_ages >= MAX_AGE - 1.0e-12] = 1.0
        return monthly

    def monthly_survival_curve(
        self,
        age: float,
        sex: Sex,
        horizon_months: int,
        years_from_base: float = 0.0,
        projection_duration_start: float = 0.0,
    ) -> Array:
        """Probability alive at monthly grid points 0 through the horizon."""
        q_monthly = self.monthly_q_curve(
            age,
            sex,
            horizon_months,
            years_from_base,
            projection_duration_start,
        )
        survival = np.ones(int(horizon_months) + 1, dtype=float)
        if len(q_monthly):
            survival[1:] = np.cumprod(1.0 - q_monthly)
        return survival

    # ------------------------------------------------------------------ #
    # Survival curves and life expectancy
    # ------------------------------------------------------------------ #

    def survival_curve(self, age: float, sex: Sex, horizon_years: int,
                       years_from_base: float = 0.0,
                       projection_duration_start: float = 0.0) -> Array:
        """P(alive at age + k), sampled from the reconciled monthly curve."""
        if isinstance(horizon_years, (bool, np.bool_)) \
                or not isinstance(horizon_years, (int, np.integer)) \
                or horizon_years < 0:
            raise ValueError("horizon_years must be a non-negative integer.")
        monthly = self.monthly_survival_curve(
            age,
            sex,
            int(horizon_years) * 12,
            years_from_base,
            projection_duration_start,
        )
        return monthly[::12]

    def joint_last_survivor_curve(self, age1: float, sex1: Sex, age2: float, sex2: Sex,
                                  horizon_years: int, years_from_base: float = 0.0,
                                  projection_duration_start: float = 0.0) -> Array:
        """P(at least one alive), assuming independent lives."""
        s1 = self.survival_curve(age1, sex1, horizon_years, years_from_base,
                                 projection_duration_start)
        s2 = self.survival_curve(age2, sex2, horizon_years, years_from_base,
                                 projection_duration_start)
        return s1 + s2 - s1 * s2

    def life_expectancy(self, age: float, sex: Sex, years_from_base: float = 0.0,
                        projection_duration_start: float = 0.0) -> float:
        """Complete expectation of life on the reconciled monthly grid."""
        horizon_months = max(
            int(np.ceil((MAX_AGE - float(age)) * 12.0 - 1.0e-12)),
            0,
        )
        survival = self.monthly_survival_curve(
            age,
            sex,
            horizon_months,
            years_from_base,
            projection_duration_start,
        )
        return float(
            np.sum(0.5 * (survival[:-1] + survival[1:])) / 12.0
        )

    def annuity_factor(self, age: float, sex: Sex, rate: float | Array,
                       years_from_base: float = 0.0,
                       joint_age: Optional[float] = None,
                       joint_sex: Optional[Sex] = None,
                       projection_duration_start: float = 0.0) -> float | Array:
        """Expected PV of 1 p.a. paid monthly in arrears at a flat cc rate.

        Payment-date survival comes from the same reconciled monthly curve as
        the cashflow projection.  The calculation is vectorised over ``rate``
        and evaluated in constant-survival-factor blocks so behaviour signals
        do not require a large path-by-month matrix.
        """
        if (joint_age is None) != (joint_sex is None):
            raise ValueError(
                "joint_age and joint_sex must either both be supplied or both omitted."
            )
        remaining = MAX_AGE - age
        if joint_age is not None and joint_sex is not None:
            remaining = max(remaining, MAX_AGE - joint_age)
        horizon_months = max(
            int(np.ceil(max(float(remaining), 0.0) * 12.0 - 1.0e-12)),
            0,
        )
        r = np.atleast_1d(np.asarray(rate, dtype=float))
        if not np.all(np.isfinite(r)):
            raise ValueError("Annuity discount rates must be finite.")
        monthly_discount = np.exp(-r / 12.0)

        def factor_from_monthly_survival(
            monthly_survival_factors: Array,
        ) -> Array:
            result = np.zeros_like(r)
            survival_start = 1.0
            discount_start = np.ones_like(r)
            start = 0
            n = len(monthly_survival_factors)
            while start < n:
                survival_factor = float(monthly_survival_factors[start])
                end = start + 1
                while (
                    end < n
                    and monthly_survival_factors[end] == survival_factor
                ):
                    end += 1
                length = end - start
                ratio = survival_factor * monthly_discount
                denominator = 1.0 - ratio
                geometric = np.divide(
                    ratio * (1.0 - ratio ** length),
                    denominator,
                    out=np.full_like(ratio, float(length)),
                    where=np.abs(denominator) > 1.0e-14,
                )
                result += survival_start * discount_start * geometric / 12.0
                survival_start *= survival_factor ** length
                discount_start *= monthly_discount ** length
                start = end
            return result

        primary_survival_factors = 1.0 - self.monthly_q_curve(
            age,
            sex,
            horizon_months,
            years_from_base,
            projection_duration_start,
        )
        pv = factor_from_monthly_survival(primary_survival_factors)
        if joint_age is not None and joint_sex is not None:
            spouse_survival_factors = 1.0 - self.monthly_q_curve(
                joint_age,
                joint_sex,
                horizon_months,
                years_from_base,
                projection_duration_start,
            )
            pv = (
                pv
                + factor_from_monthly_survival(spouse_survival_factors)
                - factor_from_monthly_survival(
                    primary_survival_factors * spouse_survival_factors
                )
            )
        return float(pv[0]) if np.ndim(rate) == 0 else pv
