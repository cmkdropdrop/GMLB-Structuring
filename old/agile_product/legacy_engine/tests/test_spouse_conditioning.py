"""Regression tests for Spouse-Insured mortality conditioning."""

import pytest

from agile_engine import (AgileProduct, BehaviourModel, ESGConfig,
                          MortalityTable, PolicySpec, Sex, SpouseDeathElection,
                          YieldCurve)
from agile_engine.behavior import DynamicLapseParams, LapseAssumptions
from agile_engine.esg import STEPS_PER_YEAR, simulate
from agile_engine.projection import project


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
    q_step = election_step - 1
    issue_offset = policy.commencement_year - mortality.base_year
    q_primary = mortality.q_monthly(policy.age + q_step / STEPS_PER_YEAR,
                                    policy.sex,
                                    years_from_base=issue_offset + q_step / STEPS_PER_YEAR)
    q_spouse = mortality.q_monthly(policy.spouse_age + q_step / STEPS_PER_YEAR,
                                   policy.spouse_sex or policy.sex,
                                   years_from_base=issue_offset + q_step / STEPS_PER_YEAR)
    expected_ratio = 1.0 - q_primary * q_spouse
    actual_ratio = res.inforce[0, election_step] / res.inforce[0, election_step - 1]

    assert actual_ratio == pytest.approx(expected_ratio, rel=1e-12, abs=1e-12)


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
    q_step = election_step - 1
    issue_offset = policy.commencement_year - mortality.base_year
    q_primary = mortality.q_monthly(policy.age + q_step / STEPS_PER_YEAR,
                                    policy.sex,
                                    years_from_base=issue_offset + q_step / STEPS_PER_YEAR)
    expected_ratio = 1.0 - q_primary
    actual_ratio = res.inforce[0, election_step] / res.inforce[0, election_step - 1]

    assert actual_ratio == pytest.approx(expected_ratio, rel=1e-12, abs=1e-12)
