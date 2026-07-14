"""Cache-preparation contract for the cap-optimisation entry points."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from portfolio_simulations import run_crediting_rate_optimisation as runner


def _option(command: list[str], name: str) -> str:
    return command[command.index(name) + 1]


def test_dynamic_orchestrator_derives_one_exact_time_zero_cache_sample():
    commands, reader = runner._precompute_commands(
        "dynamic",
        (
            "--n-paths", "882",
            "--seed", "7",
            "--hedge-pricing-method", "mc_conditional",
        ),
    )

    assert len(commands) == 1
    assert [int(_option(command, "--n-paths")) for command in commands] \
        == [882]
    assert [int(_option(command, "--seed")) for command in commands] \
        == [7]
    assert all(float(_option(command, "--horizon-years")) == 58.0
               for command in commands)
    cap_grid = tuple(float(value) for value in _option(
        commands[0], "--cap-grid"
    ).split(","))
    assert cap_grid == tuple(float(value) for value in runner._target(
        "dynamic"
    ).ACTION_CAPS)
    assert cap_grid[0] == 0.0025
    assert cap_grid[-1] == 0.20
    assert len(cap_grid) == 21
    assert all(Path(_option(command, "--equity-allocation")).is_file()
               for command in commands)
    assert all(int(_option(command, "--cross-fit-folds")) == 5
               for command in commands)
    assert all(int(_option(command, "--cross-fit-seed")) == 9137
               for command in commands)
    assert all(float(_option(command, "--ridge")) == 1.0e-6
               for command in commands)
    assert "--require-market-cache" in reader
    assert "--require-hedge-cache" in reader
    assert Path(reader[1]).name \
        == "optimize_crediting_rate_dynamic_behaviour_alt.py"
    assert "lsmc" not in " ".join(reader).lower()


def test_proxy_pricing_prepares_market_cache_only():
    commands, reader = runner._precompute_commands(
        "lsmc", ("--hedge-pricing-method", "moment_matched_bs")
    )

    assert len(commands) == 2
    assert all("--market-only" in command for command in commands)
    assert all("--cap-grid" not in command for command in commands)
    assert "--require-market-cache" in reader
    assert "--require-hedge-cache" not in reader
    assert Path(reader[1]).name == "optimize_crediting_rate_bellman.py"


def test_lsmc_orchestrator_rejects_non_lsmc_primary_behaviour():
    with pytest.raises(SystemExit, match="LSMC Policyholder behaviour only"):
        runner._precompute_commands(
            "lsmc", ("--policyholder-behaviour", "dynamic")
        )


def test_orchestrator_runs_all_writers_before_reader(monkeypatch):
    writers = [
        ["python", "precompute", "--n-paths", "10", "--seed", "1"],
        ["python", "precompute", "--n-paths", "20", "--seed", "2"],
    ]
    reader_command = ["python", "reader"]
    monkeypatch.setattr(
        runner,
        "_precompute_commands",
        lambda _mode, _arguments: (writers, reader_command),
    )
    calls: list[tuple[list[str], bool]] = []

    def fake_run(command, *, check):
        calls.append((list(command), bool(check)))
        return SimpleNamespace(returncode=17 if command is reader_command else 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner._run("dynamic", ()) == 17
    assert calls == [
        (writers[0], True),
        (writers[1], True),
        (reader_command, False),
    ]
