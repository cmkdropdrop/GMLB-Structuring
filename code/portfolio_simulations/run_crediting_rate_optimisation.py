"""Prepare exact Q caches, then launch a read-only cap optimiser.

The optimisation modules are deliberately strict cache readers. This small
orchestrator is the operative entry point: it derives the exact horizon,
sample sizes, seeds and cap grid from the selected optimiser arguments, calls
the sole authorised cache writer for each required sample, and only then
starts the requested reader in a separate process.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence

import numpy as np


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
CODE_ROOT = SCRIPT_DIRECTORY.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from policy_engine import (  # noqa: E402
    ValuationSettings,
    load_equity_allocation,
    load_policyholder_model_points,
)


def _target(mode: str):
    if mode == "dynamic":
        from portfolio_simulations import (  # noqa: PLC0415
            optimize_crediting_rate_dynamic_behaviour_alt as module,
        )
        return module
    if mode == "lsmc":
        from portfolio_simulations import (  # noqa: PLC0415
            optimize_crediting_rate_lsmc as module,
        )
        return module
    raise ValueError("mode must be 'dynamic' or 'lsmc'")


def _reader_module(mode: str):
    """Return the public strict-reader entry point for ``mode``.

    The LSMC implementation exposes shared parsing and cache-key helpers, but
    the public reader is the Bellman compatibility entry point because it
    rejects attempts to select Dynamic or always-Continue customer behaviour.
    """
    if mode == "lsmc":
        from portfolio_simulations import (  # noqa: PLC0415
            optimize_crediting_rate_bellman as module,
        )
        return module
    return _target(mode)


def _required_samples(mode: str, args) -> tuple[tuple[int, int], ...]:
    if mode == "dynamic":
        # Pure Time-0 valuation: management LSMC and every fixed cap use the
        # same complete Q sample.  There is no OOS role or forward roll.
        return ((int(args.n_paths), int(args.seed)),)
    return (
        (int(args.n_paths), int(args.seed)),
        (2 * int(args.benchmark_paths), int(args.seed) + 1),
    )


def _cap_grid(mode: str, module, args) -> tuple[float, ...]:
    values = (
        module.ACTION_CAPS
        if mode == "dynamic"
        else module._configured_action_caps(args.cap_grid)
    )
    caps = tuple(float(value) for value in np.asarray(values, dtype=float))
    if not caps or any(
        not np.isfinite(value) or value < 0.0 for value in caps
    ):
        raise ValueError("The optimiser cap grid is invalid.")
    return caps


def _precompute_commands(
    mode: str,
    runner_arguments: Sequence[str],
) -> tuple[list[list[str]], list[str]]:
    """Return exact cache-writer commands and the strict reader command."""
    module = _target(mode)
    if mode == "lsmc":
        _reader_module(mode)._require_lsmc_mode(tuple(runner_arguments))
    args = module.parse_args(tuple(runner_arguments))
    model_points = load_policyholder_model_points(args.model_points)
    if mode == "dynamic" and len(model_points.model_points) != 1:
        raise ValueError(
            "The Dynamic Time-0 capital-adjusted workflow requires exactly one "
            f"modelpoint before cache preparation; loaded "
            f"{len(model_points.model_points)} from {args.model_points}."
        )
    equity_allocation = load_equity_allocation()
    hedge_cache_defaults = ValuationSettings()
    horizon_years = module._projection_horizon_years(
        model_points, terminal_age=120.0
    )
    caps = _cap_grid(mode, module, args)
    precompute = SCRIPT_DIRECTORY / "precompute_q_market_and_hedge_cache.py"

    commands: list[list[str]] = []
    seen: set[tuple[int, int]] = set()
    for path_count, seed in _required_samples(mode, args):
        identity = (path_count, seed)
        if identity in seen:
            continue
        seen.add(identity)
        command = [
            sys.executable,
            str(precompute),
            "--zero-curve",
            str(Path(args.zero_curve).expanduser().resolve()),
            "--model-parameters",
            str(Path(args.model_parameters).expanduser().resolve()),
            "--equity-allocation",
            str(Path(equity_allocation.source_path).expanduser().resolve()),
            "--market-cache-root",
            str(Path(args.market_cache_root).expanduser().resolve()),
            "--hedge-cache-root",
            str(Path(args.hedge_cache_root).expanduser().resolve()),
            "--horizon-years",
            f"{horizon_years:.12g}",
            "--n-paths",
            str(path_count),
            "--seed",
            str(seed),
            "--heston-substeps",
            str(args.heston_substeps),
            "--market-stress",
            "base",
        ]
        if args.hedge_pricing_method == "mc_conditional":
            command.extend((
                "--cap-grid",
                ",".join(f"{cap:.12g}" for cap in caps),
                "--cross-fit-folds",
                str(hedge_cache_defaults.hedge_cross_fit_folds),
                "--cross-fit-seed",
                str(hedge_cache_defaults.hedge_cross_fit_seed),
                "--ridge",
                f"{hedge_cache_defaults.hedge_ridge:.12g}",
            ))
        else:
            command.append("--market-only")
        commands.append(command)

    strict_arguments = list(runner_arguments)
    if "--require-market-cache" not in strict_arguments:
        strict_arguments.append("--require-market-cache")
    if (
        args.hedge_pricing_method == "mc_conditional"
        and "--require-hedge-cache" not in strict_arguments
    ):
        strict_arguments.append("--require-hedge-cache")
    reader_module = _reader_module(mode)
    reader_command = [
        sys.executable,
        str(Path(reader_module.__file__).resolve()),
    ]
    reader_command.extend(strict_arguments)
    return commands, reader_command


def _run(mode: str, runner_arguments: Sequence[str]) -> int:
    if any(argument in {"-h", "--help"} for argument in runner_arguments):
        module = _reader_module(mode)
        return subprocess.run(
            [sys.executable, str(Path(module.__file__).resolve()), *runner_arguments],
            check=False,
        ).returncode

    commands, reader_command = _precompute_commands(mode, runner_arguments)
    for number, command in enumerate(commands, start=1):
        print(
            f"CACHE PREP {number}/{len(commands)} | "
            f"paths={command[command.index('--n-paths') + 1]} | "
            f"seed={command[command.index('--seed') + 1]}",
            flush=True,
        )
        subprocess.run(command, check=True)
    print(f"START READ-ONLY {mode.upper()} OPTIMISER", flush=True)
    return subprocess.run(reader_command, check=False).returncode


def dynamic_main() -> int:
    """Console entry point for dynamic-policyholder cap optimisation."""
    return _run("dynamic", sys.argv[1:])


def lsmc_main() -> int:
    """Console entry point for LSMC-policyholder cap optimisation."""
    return _run("lsmc", sys.argv[1:])


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in {"dynamic", "lsmc"}:
        print(
            "usage: run_crediting_rate_optimisation.py {dynamic|lsmc} "
            "[optimiser arguments]",
            file=sys.stderr,
        )
        return 2
    return _run(arguments[0], arguments[1:])


if __name__ == "__main__":
    raise SystemExit(main())
