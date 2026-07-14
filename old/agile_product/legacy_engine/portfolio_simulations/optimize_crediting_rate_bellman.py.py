"""Run the crediting-rate optimisation with LSMC Policyholder behaviour.

This compatibility entry point deliberately contains no statistical Dynamic
Behaviour implementation.  It delegates to ``optimize_crediting_rate_lsmc``,
whose combined Policyholder policy uses the same
``fit_optimal_behaviour_policy`` engine API as the LSMC valuation started by
``run_portfolio_risk_analysis.py``.  The fitted policy jointly decides annual
Growth ``WAIT``/``START_INCOME_NOW`` and monthly Income
``CONTINUE``/``PARTIAL_WITHDRAWAL``/``FULL_WITHDRAWAL`` actions.

The delegated optimiser uses its fast defaults: one proxy model point, a coarse
cap grid, three fresh cap-specific finalist fits, and no separate Dynamic or
always-Continue comparison grids.  The comparison grids remain explicitly
available, but they cannot be selected as the customer behaviour used by this
entry point.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

from optimize_crediting_rate_lsmc import main as _run_lsmc_optimisation  # noqa: E402


def _require_lsmc_mode(argv: Sequence[str]) -> None:
    """Reject attempts to reactivate a non-LSMC primary behaviour mode."""
    arguments = tuple(argv)
    for index, argument in enumerate(arguments):
        if argument.startswith("--policyholder-behaviour="):
            mode = argument.split("=", 1)[1]
        elif argument == "--policyholder-behaviour":
            if index + 1 >= len(arguments):
                return  # The delegated argument parser reports the missing value.
            mode = arguments[index + 1]
        else:
            continue
        if mode != "lsmc":
            raise SystemExit(
                "This entry point uses LSMC Policyholder behaviour only; "
                "use --policyholder-behaviour lsmc or omit the option."
            )


def main() -> None:
    """Execute the shared combined-LSMC crediting-rate optimisation."""
    _require_lsmc_mode(sys.argv[1:])
    _run_lsmc_optimisation()


if __name__ == "__main__":
    main()
