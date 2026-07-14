"""Explicitly precompute reusable Q market paths and annual hedge prices.

This is the only repository runner authorised to create these cache entries.
Valuation and optimisation runners are read-only consumers and fail on an
exact-cache mismatch when cache use is required.  ``--market-only`` supports
readers that need Q paths but deliberately use no conditional-MC hedge cache.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

import numpy as np


ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from policy_engine import (  # noqa: E402
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_HEDGE_CROSS_FIT_FOLDS,
    DEFAULT_HEDGE_CROSS_FIT_SEED,
    DEFAULT_MODEL_PARAMETERS_PATH,
    HedgePriceCacheNotFoundError,
    HedgePriceCacheSpec,
    Measure,
    ScenarioCacheNotFoundError,
    ScenarioCacheSpec,
    build_hedge_price_surface,
    load_equity_allocation,
    load_hedge_price_surface,
    load_market_assumptions,
    load_scenario_set,
    save_hedge_price_surface,
    save_scenario_set,
    simulate,
)
from policy_engine.mortality import MortalityTable  # noqa: E402
from policy_engine.portfolio_stresses import (  # noqa: E402
    apply_portfolio_input_stress,
    apply_portfolio_scenario_stress,
    get_portfolio_stress,
)
from policy_engine.repository_paths import (  # noqa: E402
    Q_HEDGE_PRICE_CACHE_ROOT as DEFAULT_HEDGE_CACHE_ROOT,
    Q_MARKET_PATH_CACHE_ROOT as DEFAULT_MARKET_CACHE_ROOT,
)

DEFAULT_CAP_GRID = (0.0025, *tuple(np.arange(1, 21, dtype=float) / 100.0))
MARKET_STRESS_CHOICES = (
    "base", "interest_up", "interest_down", "equity_level_down",
    "equity_volatility_up",
)


def _cap_grid(text: str) -> tuple[float, ...]:
    try:
        values = tuple(float(item.strip()) for item in text.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("cap grid must be comma-separated decimals") from exc
    if not values or any(not np.isfinite(value) or value < 0.0 for value in values) \
            or any(right <= left for left, right in zip(values, values[1:])):
        raise argparse.ArgumentTypeError(
            "cap grid must be finite, non-negative and strictly increasing"
        )
    return values


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zero-curve", type=Path,
                        default=DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH)
    parser.add_argument("--model-parameters", type=Path,
                        default=DEFAULT_MODEL_PARAMETERS_PATH)
    parser.add_argument("--equity-allocation", type=Path, default=None)
    parser.add_argument("--market-cache-root", type=Path,
                        default=DEFAULT_MARKET_CACHE_ROOT)
    parser.add_argument("--hedge-cache-root", type=Path,
                        default=DEFAULT_HEDGE_CACHE_ROOT)
    parser.add_argument("--horizon-years", type=float, required=True)
    parser.add_argument("--n-paths", type=int, required=True)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument(
        "--cap-grid", type=_cap_grid,
        default=tuple(float(value) for value in DEFAULT_CAP_GRID),
    )
    parser.add_argument("--cross-fit-folds", type=int,
                        default=DEFAULT_HEDGE_CROSS_FIT_FOLDS)
    parser.add_argument("--cross-fit-seed", type=int,
                        default=DEFAULT_HEDGE_CROSS_FIT_SEED)
    parser.add_argument("--ridge", type=float, default=1.0e-6)
    parser.add_argument("--market-stress", choices=MARKET_STRESS_CHOICES,
                        default="base")
    parser.add_argument(
        "--market-only",
        action="store_true",
        help="create or validate only the exact Q-market cache entry",
    )
    args = parser.parse_args(argv)
    if args.n_paths <= 0 or args.heston_substeps <= 0:
        parser.error("--n-paths and --heston-substeps must be positive")
    if args.seed < 0 or args.cross_fit_seed < 0:
        parser.error("seeds must be non-negative")
    if not args.market_only and (
        args.cross_fit_folds < 2 or args.n_paths <= args.cross_fit_folds
    ):
        parser.error("cross-fitting needs at least two folds and more paths than folds")
    if not np.isfinite(args.ridge) or args.ridge < 0.0:
        parser.error("--ridge must be finite and non-negative")
    if not np.isfinite(args.horizon_years) or args.horizon_years < 1.0 \
            or not np.isclose(
                args.horizon_years * 12.0, round(args.horizon_years * 12.0)
            ):
        parser.error("--horizon-years must be at least one and monthly aligned")
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    market = load_market_assumptions(args.zero_curve, args.model_parameters)
    allocation = load_equity_allocation(args.equity_allocation)
    stress = get_portfolio_stress(args.market_stress)
    stressed_esg, _, _ = apply_portfolio_input_stress(
        stress, market.esg, MortalityTable.gompertz_makeham(), None
    )
    market_spec = ScenarioCacheSpec.from_inputs(
        stressed_esg,
        australian_curve_sha256=market.source_sha256["curve"],
        model_parameters_sha256=market.source_sha256["model_parameters"],
        horizon_years=args.horizon_years,
        n_paths=args.n_paths,
        seed=args.seed,
        heston_substeps=args.heston_substeps,
        market_variant=stress.stress_id,
    )
    try:
        scenarios = load_scenario_set(
            args.market_cache_root, market_spec, stressed_esg, mmap_mode="r"
        )
        market_status = "existing_validated"
    except ScenarioCacheNotFoundError:
        scenarios = simulate(
            "heston_hull_white",
            stressed_esg,
            args.horizon_years,
            args.n_paths,
            measure=Measure.RISK_NEUTRAL,
            seed=args.seed,
            substeps=args.heston_substeps,
        )
        scenarios = apply_portfolio_scenario_stress(stress, scenarios)
        save_scenario_set(args.market_cache_root, market_spec, scenarios)
        market_status = "created"

    if args.market_only:
        print(json.dumps({
            "market_cache_status": market_status,
            "market_cache_key": market_spec.cache_key,
            "scenario_fingerprint": scenarios.content_fingerprint,
            "hedge_cache_status": "not_requested",
            "market_stress": stress.stress_id,
        }, indent=2))
        return 0

    hedge_spec = HedgePriceCacheSpec(
        market_cache_key=market_spec.cache_key,
        scenario_fingerprint=scenarios.content_fingerprint,
        n_paths=scenarios.n_paths,
        horizon_years=float(scenarios.times[-1]),
        equity_index="global_equity",
        equity_allocation=allocation.equity_weight,
        allocation_input_sha256=allocation.source_sha256,
        cap_grid=args.cap_grid,
        training_scenario_fingerprint=scenarios.content_fingerprint,
        cross_fit_folds=args.cross_fit_folds,
        cross_fit_seed=args.cross_fit_seed,
        ridge=args.ridge,
    )
    try:
        surface = load_hedge_price_surface(
            args.hedge_cache_root, hedge_spec, scenarios, mmap_mode="r"
        )
        hedge_status = "existing_validated"
    except HedgePriceCacheNotFoundError:
        # Only absence permits creation.  A malformed exact entry is never
        # overwritten or silently repaired.
        surface = build_hedge_price_surface(scenarios, hedge_spec)
        save_hedge_price_surface(args.hedge_cache_root, surface)
        hedge_status = "created"

    print(json.dumps({
        "market_cache_status": market_status,
        "market_cache_key": market_spec.cache_key,
        "scenario_fingerprint": scenarios.content_fingerprint,
        "hedge_cache_status": hedge_status,
        "hedge_cache_key": hedge_spec.cache_key,
        "price_surface_fingerprint": surface.price_surface_fingerprint,
        "training_scenario_fingerprint": hedge_spec.training_scenario_fingerprint,
        "cross_fit_folds": hedge_spec.cross_fit_folds,
        "cap_grid": list(hedge_spec.cap_grid),
        "equity_allocation": hedge_spec.equity_allocation,
        "dva_mark_method": "moment_matched_bs",
        "nested_mc_used": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
