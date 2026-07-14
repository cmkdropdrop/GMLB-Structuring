"""Contracts for the Dynamic-only crediting-cap capital orchestrator."""

from pathlib import Path

import pytest

from portfolio_simulations import run_crediting_rate_capital_analysis as runner


def test_defaults_are_dynamic_only_and_capital_adjusted() -> None:
    args = runner.parse_args([])

    assert args.cap_grid == (0.0025, 0.01, 0.06, 0.12)
    assert args.baseline_cap == pytest.approx(0.06)
    assert args.objective == "capital_adjusted_csm"
    assert args.capital_hurdle_rate == pytest.approx(0.06)
    assert args.mass_lapse_fraction == pytest.approx(0.40)
    assert runner.STRESS_IDS == (
        "base",
        "mortality",
        "longevity",
        "lapse_up",
        "lapse_down",
    )


def test_baseline_cap_must_be_on_grid() -> None:
    with pytest.raises(SystemExit):
        runner.parse_args(["--cap-grid", "0.01,0.02", "--baseline-cap", "0.06"])


def test_child_command_hard_codes_complete_dynamic_behaviour(tmp_path: Path) -> None:
    args = runner.parse_args([
        "--cap-grid", "0.06",
        "--baseline-cap", "0.06",
    ])
    command = runner._valuation_command(
        args,
        cap=0.06,
        stress_id="longevity",
        output=tmp_path / "valuation",
    )

    runner._assert_dynamic_only_command(command)
    assert Path(command[1]).resolve() == runner.DYNAMIC_READER.resolve()
    assert command[command.index("--income-election-mode") + 1] == "dynamic"
    assert command[command.index("--post-income-behaviour") + 1] == "dynamic"
    assert "--require-market-cache" in command
    assert "--require-hedge-cache" in command
    assert "lsmc" not in " ".join(command).lower()


def test_hard_gate_rejects_policyholder_lsmc_target() -> None:
    command = (
        "python",
        str(runner.SCRIPT_DIRECTORY / "run_portfolio_valuation_lsmc.py"),
        "--income-election-mode",
        "dynamic",
        "--post-income-behaviour",
        "dynamic",
        "--require-market-cache",
    )
    with pytest.raises(ValueError, match="Dynamic reader"):
        runner._assert_dynamic_only_command(command)


def test_precompute_uses_authorised_writer_and_exact_single_cap_grids(
    tmp_path: Path,
) -> None:
    args = runner.parse_args([
        "--cap-grid", "0.01,0.06",
        "--baseline-cap", "0.06",
        "--n-paths", "17",
        "--seed", "123",
    ])
    commands = runner._precompute_commands(
        args,
        horizon_years=53.0,
        output=tmp_path,
    )

    assert len(commands) == 2
    assert [command[0][command[0].index("--cap-grid") + 1]
            for command in commands] == ["0.01", "0.06"]
    for command, _output in commands:
        assert Path(command[1]).resolve() == runner.CACHE_PRECOMPUTE_RUNNER.resolve()
        assert command[command.index("--market-stress") + 1] == "base"
        assert command[command.index("--n-paths") + 1] == "17"
        assert command[command.index("--seed") + 1] == "123"


def _scenario(cap: float, stress: str, csm: float) -> dict[str, object]:
    return {
        "crediting_cap_rate": cap,
        "stress_scenario_id": stress,
        "csm_aud": csm,
        "premium_aud": 1_000.0,
        "total_income_lapse_event_mass": 0.10,
        "ordinary_income_lapse_event_mass": 0.02,
        "performance_income_lapse_event_mass": 0.08,
        "income_start_year_mean": 5.0,
    }


def test_capital_adjusted_selection_can_reject_higher_csm_with_more_capital() -> None:
    scenarios = []
    values = {
        0.01: {
            "base": 100.0,
            "mortality": 105.0,
            "longevity": 90.0,
            "lapse_up": 95.0,
            "lapse_down": 100.0,
        },
        0.06: {
            "base": 105.0,
            "mortality": 110.0,
            "longevity": 95.0,
            "lapse_up": 105.0,
            "lapse_down": 105.0,
        },
    }
    for cap, stresses in values.items():
        scenarios.extend(
            _scenario(cap, stress, csm) for stress, csm in stresses.items()
        )

    rows = runner._build_capital_rows(
        scenarios,
        positive_base_value={0.01: 100.0, 0.06: 300.0},
        baseline_cap=0.06,
        capital_hurdle_rate=0.10,
        capital_materiality_bp=1.0,
        mass_lapse_fraction=0.40,
        objective="capital_adjusted_csm",
    )

    selected = next(row for row in rows if row["is_selected_cap"])
    assert selected["crediting_cap_rate"] == pytest.approx(0.01)
    assert selected["base_csm_aud"] < 105.0
    assert selected["mll_life_capital_proxy_aud"] < next(
        row["mll_life_capital_proxy_aud"]
        for row in rows
        if row["crediting_cap_rate"] == pytest.approx(0.06)
    )
    assert selected["mass_lapse_proxy_is_binding"] is True
    assert (
        selected["mll_life_capital_proxy_aud"]
        > selected["mll_permanent_lapse_only_capital_proxy_aud"]
    )
    assert selected["capital_adjusted_value_vs_baseline_aud"] > 0.0


def test_positive_model_point_value_does_not_net_onerous_cells() -> None:
    value = runner._positive_model_point_value([
        {
            "normalised_contribution_insurer_net_present_value_before_risk_margin_aud":
                "10",
        },
        {
            "normalised_contribution_insurer_net_present_value_before_risk_margin_aud":
                "-9",
        },
    ])

    assert value == pytest.approx(10.0)


def test_dynamic_output_validation_requires_stress_manifest_block(
    tmp_path: Path,
) -> None:
    job = runner.ValuationJob(
        sequence=1,
        cap=0.06,
        stress_id="base",
        output=tmp_path,
        command=(),
    )
    summary = {"lsmc_used": False, "crediting_cap_rate": 0.06}
    manifest = {
        "method": {"lsmc_used": False},
        "valuation_settings": {
            "income_election_mode": "dynamic",
            "post_income_behaviour": "dynamic",
            "require_market_cache": True,
            "require_hedge_cache": True,
        },
    }

    with pytest.raises(ValueError, match="no stress definition"):
        runner._validate_dynamic_output(
            job,
            summary,
            manifest,
            hedge_pricing_method="mc_conditional",
        )
