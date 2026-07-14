"""Static aggregation guards for insurer hedge/backing outputs."""

import pytest

from portfolio_simulations.run_portfolio_valuation import (
    _build_aggregation_reconciliation,
)


HEDGE_BACKING_METRICS = (
    "pv_crediting_margin_aud",
    "pv_money_market_income_aud",
    "pv_hedge_gain_aud",
    "pv_hedge_costs_aud",
    "pv_hedge_option_fair_value_costs_aud",
    "pv_hedge_option_markup_costs_aud",
    "pv_hedge_management_fee_costs_aud",
    "pv_hedge_execution_costs_aud",
    "pv_hedge_cost_reconciliation_gap_aud",
    "pv_crediting_margin_reconciliation_gap_aud",
)


def _valid_inputs():
    summary: dict[str, object] = {
        "absolute_portfolio_values_available": False,
    }
    model_point: dict[str, object] = {}
    for index, metric in enumerate(HEDGE_BACKING_METRICS, start=1):
        value = 0.0 if "gap" in metric else float(index)
        summary[f"normalised_average_{metric}"] = value
        model_point[f"normalised_contribution_{metric}"] = value
    return summary, [model_point]


def test_required_hedge_backing_aggregation_fields_reconcile():
    summary, rows = _valid_inputs()

    reconciliation = _build_aggregation_reconciliation(summary, rows)

    assert {
        str(row["metric"]) for row in reconciliation
    } == set(HEDGE_BACKING_METRICS)


def test_missing_required_hedge_backing_contribution_fails_closed():
    summary, rows = _valid_inputs()
    rows[0].pop("normalised_contribution_pv_hedge_gain_aud")

    with pytest.raises(ValueError, match="incomplete"):
        _build_aggregation_reconciliation(summary, rows)


def test_failed_hedge_backing_aggregation_fails_closed():
    summary, rows = _valid_inputs()
    rows[0]["normalised_contribution_pv_hedge_costs_aud"] = 999.0

    with pytest.raises(ValueError, match="failed"):
        _build_aggregation_reconciliation(summary, rows)
