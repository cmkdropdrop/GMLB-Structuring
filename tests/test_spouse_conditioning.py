"""Regression tests for Spouse-Insured mortality conditioning."""

import pytest

from policy_engine import (AgileProduct, BehaviourModel, ESGConfig,
                          MortalityTable, PolicySpec, Sex, SpouseDeathElection,
                          YieldCurve)
from policy_engine.behavior import DynamicLapseParams, LapseAssumptions
from policy_engine.esg import STEPS_PER_YEAR, simulate
from policy_engine.projection import project


def no_lapse_behaviour() -> BehaviourModel:
    return BehaviourModel(regime="static",
                          lapse=LapseAssumptions(growth_phase=(0.0,),
                                                 income_phase=0.0),
                          dynamic=DynamicLapseParams(enabled=False))


def test_spouse_last_survivor_mortality_starts_at_income_election():
    """The joint-life state is reset when the Spouse option is elected.

    Before the fix, the first post-election decrement used the unconditional
    last-survivor decrement from policy issue. For a late income start this
    implicitly allowed the spouse to have died before the option existed and
    overstated the extinction probability of the joint income.
    """
    mortality = MortalityTable.gompertz_makeham()
    policy = PolicySpec(age=65, spouse=True, spouse_age=65,
                        spouse_sex=Sex.FEMALE, income_start_year=10)
    scenarios = simulate("black_scholes", ESGConfig(curve=YieldCurve.flat(0.04)),
                         12.0, 1, seed=23)

    res = project(AgileProduct(), policy, scenarios, no_lapse_behaviour(),
                  mortality)

    election_step = policy.income_start_year * STEPS_PER_YEAR
    issue_offset = policy.commencement_year - mortality.base_year
    q_primary = mortality.monthly_q_curve(
        policy.age,
        policy.sex,
        election_step + 1,
        years_from_base=issue_offset,
        projection_duration_start=0.0,
    )
    q_spouse = mortality.monthly_q_curve(
        policy.spouse_age,
        policy.spouse_sex or policy.sex,
        election_step + 1,
        years_from_base=issue_offset,
        projection_duration_start=0.0,
    )

    # The interval ending at the Election timestamp is still Primary-only.
    election_ratio = (
        res.inforce[0, election_step]
        / res.inforce[0, election_step - 1]
    )
    assert election_ratio == pytest.approx(
        1.0 - q_primary[election_step - 1], rel=1e-12, abs=1e-12
    )

    # Both lives are conditioned alive at Election; Last-Survivor mortality
    # therefore starts in the following monthly interval.
    post_election_ratio = (
        res.inforce[0, election_step + 1]
        / res.inforce[0, election_step]
    )
    expected_post_election_ratio = (
        1.0 - q_primary[election_step] * q_spouse[election_step]
    )
    assert post_election_ratio == pytest.approx(
        expected_post_election_ratio, rel=1e-12, abs=1e-12
    )


def test_spouse_lump_sum_path_uses_primary_death_decrement():
    """PDS 17.3 also allows a lump-sum death-benefit path.

    In that case income does not continue to last survivor; the death
    decrement remains the Life Insured's own mortality in the income phase.
    """
    mortality = MortalityTable.gompertz_makeham()
    policy = PolicySpec(age=65, spouse=True, spouse_age=65,
                        spouse_sex=Sex.FEMALE,
                        spouse_death_election=SpouseDeathElection.LUMP_SUM,
                        income_start_year=1)
    scenarios = simulate("black_scholes", ESGConfig(curve=YieldCurve.flat(0.04)),
                         2.0, 1, seed=24)

    res = project(AgileProduct(), policy, scenarios, no_lapse_behaviour(),
                  mortality)

    election_step = policy.income_start_year * STEPS_PER_YEAR
    issue_offset = policy.commencement_year - mortality.base_year
    q_primary = mortality.monthly_q_curve(
        policy.age,
        policy.sex,
        election_step,
        years_from_base=issue_offset,
        projection_duration_start=0.0,
    )
    expected_ratio = 1.0 - q_primary[election_step - 1]
    actual_ratio = res.inforce[0, election_step] / res.inforce[0, election_step - 1]

    assert actual_ratio == pytest.approx(expected_ratio, rel=1e-12, abs=1e-12)
