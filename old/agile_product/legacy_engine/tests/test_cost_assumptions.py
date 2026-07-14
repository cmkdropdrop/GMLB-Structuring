"""Regression tests for the repository-wide cost-assumption source."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from agile_engine import (
    BehaviourModel,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DynamicLapseParams,
    ESGConfig,
    LapseAssumptions,
    Measure,
    MortalityTable,
    MVASpec,
    PolicySpec,
    ProjectionConfig,
    ValuationSettings,
    YieldCurve,
    greeks,
    load_cost_assumptions,
    value_contract,
)


CURVE = YieldCurve.flat(0.04)
ESG = ESGConfig(curve=CURVE)
MORTALITY = MortalityTable.gompertz_makeham()
POLICY = PolicySpec(age=65, income_start_year=1)


EXPECTED_VALUES = {
    "base": {
        "FeeSpec.product_fee": 0.003,
        "FeeSpec.lifetime_income_premium": 0.0115,
        "ExpenseAssumptions.acquisition_pct_of_premium": 0.02,
        "ExpenseAssumptions.maintenance_per_policy": 80.0,
        "ExpenseAssumptions.maintenance_pct_of_iv": 0.0005,
        "ExpenseAssumptions.expense_inflation": 0.025,
        "ExpenseAssumptions.commission_pct_of_premium": 0.0,
        "ProjectionConfig.hedge_vol_spread": 0.0,
        "ProjectionConfig.option_fair_value_markup": 0.005,
        "ProjectionConfig.hedge_reference_management_fee": 0.003,
        "MVASpec.cost_loading_per_remaining_year": 0.0061744444,
        "MVASpec.cost_loading": 0.0,
        "CapitalStresses.coc_rate": 0.06,
        "ProfitabilitySettings.hurdle_rate": 0.08,
        "ProfitabilitySettings.tax_rate": 0.30,
        "ProfitabilitySettings.capital_earning_spread": 0.0,
    },
    "low": {
        "FeeSpec.product_fee": 0.003,
        "FeeSpec.lifetime_income_premium": 0.0115,
        "ExpenseAssumptions.acquisition_pct_of_premium": 0.015,
        "ExpenseAssumptions.maintenance_per_policy": 60.0,
        "ExpenseAssumptions.maintenance_pct_of_iv": 0.00025,
        "ExpenseAssumptions.expense_inflation": 0.02,
        "ExpenseAssumptions.commission_pct_of_premium": 0.0,
        "ProjectionConfig.hedge_vol_spread": 0.0,
        "ProjectionConfig.option_fair_value_markup": 0.005,
        "ProjectionConfig.hedge_reference_management_fee": 0.003,
        "MVASpec.cost_loading_per_remaining_year": 0.004,
        "MVASpec.cost_loading": 0.0,
        "CapitalStresses.coc_rate": 0.04,
        "ProfitabilitySettings.hurdle_rate": 0.06,
        "ProfitabilitySettings.tax_rate": 0.25,
        "ProfitabilitySettings.capital_earning_spread": -0.0025,
    },
    "high": {
        "FeeSpec.product_fee": 0.003,
        "FeeSpec.lifetime_income_premium": 0.0115,
        "ExpenseAssumptions.acquisition_pct_of_premium": 0.035,
        "ExpenseAssumptions.maintenance_per_policy": 120.0,
        "ExpenseAssumptions.maintenance_pct_of_iv": 0.001,
        "ExpenseAssumptions.expense_inflation": 0.04,
        "ExpenseAssumptions.commission_pct_of_premium": 0.01,
        "ProjectionConfig.hedge_vol_spread": 0.0,
        "ProjectionConfig.option_fair_value_markup": 0.005,
        "ProjectionConfig.hedge_reference_management_fee": 0.003,
        "MVASpec.cost_loading_per_remaining_year": 0.008,
        "MVASpec.cost_loading": 0.01,
        "CapitalStresses.coc_rate": 0.08,
        "ProfitabilitySettings.hurdle_rate": 0.10,
        "ProfitabilitySettings.tax_rate": 0.30,
        "ProfitabilitySettings.capital_earning_spread": 0.0025,
    },
}


def _configured_values(costs):
    """Read the mapped engine fields without relying on ``costs.values``."""
    return {
        "FeeSpec.product_fee": costs.product.fees.product_fee,
        "FeeSpec.lifetime_income_premium": (
            costs.product.fees.lifetime_income_premium
        ),
        "ExpenseAssumptions.acquisition_pct_of_premium": (
            costs.expenses.acquisition_pct_of_premium
        ),
        "ExpenseAssumptions.maintenance_per_policy": (
            costs.expenses.maintenance_per_policy
        ),
        "ExpenseAssumptions.maintenance_pct_of_iv": (
            costs.expenses.maintenance_pct_of_iv
        ),
        "ExpenseAssumptions.expense_inflation": costs.expenses.expense_inflation,
        "ExpenseAssumptions.commission_pct_of_premium": (
            costs.expenses.commission_pct_of_premium
        ),
        "ProjectionConfig.hedge_vol_spread": costs.projection.hedge_vol_spread,
        "ProjectionConfig.option_fair_value_markup": (
            costs.projection.option_fair_value_markup
        ),
        "ProjectionConfig.hedge_reference_management_fee": (
            costs.projection.hedge_reference_management_fee
        ),
        "MVASpec.cost_loading_per_remaining_year": (
            costs.product.mva.cost_loading_per_remaining_year
        ),
        "MVASpec.cost_loading": costs.product.mva.cost_loading,
        "CapitalStresses.coc_rate": costs.capital_stresses.coc_rate,
        "ProfitabilitySettings.hurdle_rate": costs.profitability.hurdle_rate,
        "ProfitabilitySettings.tax_rate": costs.profitability.tax_rate,
        "ProfitabilitySettings.capital_earning_spread": (
            costs.profitability.capital_earning_spread
        ),
    }


def _canonical_csv():
    with DEFAULT_COST_ASSUMPTIONS_PATH.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or ()), list(reader)


def _write_csv(path: Path, fieldnames, rows) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _static_behaviour(growth_lapse: float = 0.0) -> BehaviourModel:
    return BehaviourModel(
        regime="static",
        lapse=LapseAssumptions(
            growth_phase=(growth_lapse,), income_phase=0.0
        ),
        dynamic=DynamicLapseParams(enabled=False),
    )


@pytest.mark.parametrize("value_basis", ["base", "low", "high"])
def test_canonical_base_low_high_mapping(value_basis):
    costs = load_cost_assumptions(value_basis=value_basis)
    expected = EXPECTED_VALUES[value_basis]

    assert costs.value_basis == value_basis
    assert dict(costs.values) == pytest.approx(expected)
    assert _configured_values(costs) == pytest.approx(expected)


def test_exclusions_metadata_and_default_path_are_cwd_independent(
    tmp_path, monkeypatch
):
    expected_path = DEFAULT_COST_ASSUMPTIONS_PATH.resolve()
    expected_digest = hashlib.sha256(expected_path.read_bytes()).hexdigest()
    monkeypatch.chdir(tmp_path)

    costs = load_cost_assumptions()
    metadata = costs.source_metadata()

    assert Path(costs.source_path) == expected_path
    assert costs.assumption_set_id == "realistic_base_2026-07-12"
    assert costs.effective_dates == (
        "2026-01-19",
        "2026-07-12",
        "2026-07-13",
    )
    assert costs.source_sha256 == expected_digest
    assert costs.excluded_parameters == (
        "ongoing_adviser_service_fee",
        "tax_and_withholding",
        "reinsurance_cost",
    )
    assert "not_in_core_engine" not in costs.values
    assert metadata["source_path"] == str(expected_path)
    assert metadata["source_sha256"] == expected_digest
    assert metadata["applied_engine_parameters"] == dict(costs.values)
    assert metadata["excluded_parameters"] == list(costs.excluded_parameters)
    json.dumps(metadata)  # manifest metadata must remain JSON-serialisable


def test_invalid_value_basis_is_rejected():
    with pytest.raises(ValueError, match="value_basis"):
        load_cost_assumptions(value_basis="central")


def test_missing_required_csv_column_is_rejected(tmp_path):
    fieldnames, rows = _canonical_csv()
    fieldnames.remove("unit")
    rows = [{key: value for key, value in row.items() if key != "unit"}
            for row in rows]
    path = _write_csv(tmp_path / "missing_column.csv", fieldnames, rows)

    with pytest.raises(ValueError, match="missing required columns: unit"):
        load_cost_assumptions(path)


@pytest.mark.parametrize(
    ("column", "invalid_value", "message"),
    [
        ("include_in_base_case", "yes", "Invalid include_in_base_case"),
        ("base_value", "not-a-number", "Invalid numeric value"),
        ("high_value", "nan", "Non-finite value"),
    ],
)
def test_invalid_csv_scalars_are_rejected(
    tmp_path, column, invalid_value, message
):
    fieldnames, rows = _canonical_csv()
    rows[0][column] = invalid_value
    path = _write_csv(tmp_path / f"invalid_{column}.csv", fieldnames, rows)

    with pytest.raises(ValueError, match=message):
        load_cost_assumptions(path)


def test_non_monotone_low_base_high_values_are_rejected(tmp_path):
    fieldnames, rows = _canonical_csv()
    rows[0]["low_value"] = "0.004"
    path = _write_csv(tmp_path / "non_monotone.csv", fieldnames, rows)

    with pytest.raises(ValueError, match="low_value <= base_value <= high_value"):
        load_cost_assumptions(path)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("unsupported", "Unsupported active engine_parameter"),
        ("not_supported", "marked not_supported"),
        ("wrong_unit", "Unexpected unit"),
        ("duplicate", "Duplicate active engine_parameter"),
        ("missing", "missing active supported parameters"),
    ],
)
def test_active_mapping_integrity_is_validated(tmp_path, case, message):
    fieldnames, rows = _canonical_csv()
    if case == "unsupported":
        rows[0]["engine_parameter"] = "Unknown.cost"
    elif case == "not_supported":
        rows[0]["engine_support"] = "not_supported"
    elif case == "wrong_unit":
        rows[0]["unit"] = "percent"
    elif case == "duplicate":
        rows.append(dict(rows[0]))
    else:
        rows[0]["include_in_base_case"] = "false"
    path = _write_csv(tmp_path / f"{case}.csv", fieldnames, rows)

    with pytest.raises(ValueError, match=message):
        load_cost_assumptions(path)


def test_assumption_set_selection_is_unambiguous(tmp_path):
    fieldnames, rows = _canonical_csv()
    other = dict(rows[0])
    other["assumption_set_id"] = "other_set"
    rows.append(other)
    path = _write_csv(tmp_path / "multiple_sets.csv", fieldnames, rows)

    with pytest.raises(ValueError, match="Multiple cost assumption sets"):
        load_cost_assumptions(path)
    with pytest.raises(ValueError, match="Unknown cost assumption set"):
        load_cost_assumptions(path, assumption_set_id="missing_set")


def test_legacy_hedge_vol_spread_is_a_nonnegative_incremental_cost():
    costs = load_cost_assumptions()
    no_cost_projection = replace(
        costs.projection, hedge_vol_spread=0.0, record_paths=False
    )
    spread_projection = replace(no_cost_projection, hedge_vol_spread=0.005)
    settings = ValuationSettings(
        model="black_scholes",
        n_paths=8,
        seed=13,
        horizon_years=2.0,
        projection=no_cost_projection,
    )
    no_cost = value_contract(
        costs.product, POLICY, ESG, MORTALITY, _static_behaviour(),
        settings=settings,
    )
    with_cost = value_contract(
        costs.product, POLICY, ESG, MORTALITY, _static_behaviour(),
        settings=replace(settings, projection=spread_projection),
    )

    hedge_cashflows = with_cost.projection.cashflows["hedge_costs"]
    assert np.all(hedge_cashflows >= 0.0)
    assert with_cost.pv["hedge_costs"] > no_cost.pv["hedge_costs"]
    assert with_cost.insurer_net_value < no_cost.insurer_net_value
    assert no_cost.insurer_net_value - with_cost.insurer_net_value == pytest.approx(
        with_cost.pv["hedge_costs"] - no_cost.pv["hedge_costs"],
        rel=1e-12,
        abs=1e-10,
    )


def test_base_mva_loading_is_retained_and_increases_insurer_nav():
    costs = load_cost_assumptions()
    assert costs.product.mva.factor(0.04, 0.04, 9.0) == pytest.approx(
        0.05557, abs=5e-10
    )
    product_without_loading = replace(costs.product, mva=MVASpec())
    settings = ValuationSettings(
        model="black_scholes",
        n_paths=8,
        seed=17,
        horizon_years=1.0,
        projection=ProjectionConfig(
            hedge_vol_spread=0.0, record_paths=False
        ),
    )
    behaviour = _static_behaviour(growth_lapse=0.25)

    with_loading = value_contract(
        costs.product, POLICY, ESG, MORTALITY, behaviour, settings=settings
    )
    without_loading = value_contract(
        product_without_loading, POLICY, ESG, MORTALITY, behaviour,
        settings=settings,
    )

    assert with_loading.pv["mva_retained"] > 0.0
    assert without_loading.pv["mva_retained"] == pytest.approx(0.0, abs=1e-12)
    assert with_loading.insurer_net_value - without_loading.insurer_net_value \
        == pytest.approx(with_loading.pv["mva_retained"],
                         rel=1e-12, abs=1e-10)


def test_greeks_reconcile_to_expense_aware_bump_and_revalue():
    costs = load_cost_assumptions()
    settings = ValuationSettings(
        model="black_scholes",
        n_paths=4,
        seed=19,
        horizon_years=1.0,
        projection=replace(costs.projection, record_paths=False),
    )
    behaviour = _static_behaviour()
    equity_bump = 0.01
    vol_bump = 0.01
    rate_bump = 0.001

    def nav(config, scenarios=None):
        return value_contract(
            costs.product,
            POLICY,
            config,
            MORTALITY,
            behaviour,
            expenses=costs.expenses,
            settings=settings,
            scenarios=scenarios,
        ).insurer_net_value

    direct = value_contract(
        costs.product, POLICY, ESG, MORTALITY, behaviour,
        expenses=costs.expenses, settings=settings,
    )
    base_scenarios = direct.projection.scenarios

    def equity_shocked(scale):
        levels = {index: values.copy()
                  for index, values in base_scenarios.index_levels.items()}
        for values in levels.values():
            values[:, 1:] *= scale
        return replace(base_scenarios, index_levels=levels)

    nav_equity_up = nav(ESG, equity_shocked(1.0 + equity_bump))
    nav_equity_down = nav(ESG, equity_shocked(1.0 - equity_bump))
    nav_vol_up = nav(ESG.bump_equity_vol_abs(vol_bump))
    nav_rate_up = nav(ESG.with_curve(CURVE.shifted(rate_bump)))
    nav_rate_down = nav(ESG.with_curve(CURVE.shifted(-rate_bump)))
    p0 = POLICY.net_initial_investment
    expected = {
        "nav": direct.insurer_net_value,
        "equity_delta_pct": (
            (nav_equity_up - nav_equity_down) / (2.0 * equity_bump) / p0
        ),
        "vega_per_volpt": (nav_vol_up - direct.insurer_net_value) / p0,
        "rho_per_100bp": (
            (nav_rate_up - nav_rate_down) / (2.0 * rate_bump) * 0.01 / p0
        ),
    }

    actual = greeks(
        costs.product,
        POLICY,
        ESG,
        MORTALITY,
        behaviour,
        settings=settings,
        equity_bump=equity_bump,
        vol_bump=vol_bump,
        rate_bump=rate_bump,
        expenses=costs.expenses,
    )
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)

    without_expenses = value_contract(
        costs.product, POLICY, ESG, MORTALITY, behaviour, settings=settings
    )
    assert direct.pv["expenses"] > 0.0
    assert without_expenses.insurer_net_value - direct.insurer_net_value \
        == pytest.approx(direct.pv["expenses"], rel=1e-12, abs=1e-10)
