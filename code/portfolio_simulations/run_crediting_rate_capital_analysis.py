"""Dynamic-only crediting-cap profitability and life-capital analysis.

This orchestrator studies fixed crediting caps under the repository's
statistical Dynamic Policyholder Behaviour model.  It never fits or applies a
Policyholder LSMC policy.  For every cap it performs common-random-number base,
mortality, longevity, lapse-up and lapse-down revaluations, all through the
strict cache-reading ``run_portfolio_valuation.py`` entry point.

Only ``precompute_q_market_and_hedge_cache.py`` is allowed to prepare missing
Q-market and conditional-MC hedge-price caches.  Non-market stresses reuse the
same exact market and hedge cache as the base case.  The resulting
Mortality/Longevity/Lapse (MLL) amount is a research life-risk capital proxy,
not APRA capital, a complete Solvency Capital Requirement or IFRS 17 CSM.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
CODE_ROOT = SCRIPT_DIRECTORY.parent
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from policy_engine import load_policyholder_model_points  # noqa: E402
from policy_engine.pricing import ValuationSettings, resolve_horizon  # noqa: E402
from policy_engine.repository_paths import (  # noqa: E402
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DEFAULT_MODEL_PARAMETERS_PATH,
    DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
    Q_HEDGE_PRICE_CACHE_ROOT,
    Q_MARKET_PATH_CACHE_ROOT,
    run_output_directory,
)

from portfolio_simulations._mc_analysis_inputs import (  # noqa: E402
    load_mc_analysis_inputs,
    require_mc_samples,
)


ENGINE_VERSION = "3.0.0"
STRESS_IDS = ("base", "mortality", "longevity", "lapse_up", "lapse_down")
DEFAULT_CAP_GRID = (0.0025, 0.01, 0.06, 0.12)
DEFAULT_BASELINE_CAP = 0.06
DEFAULT_OUTPUT_ROOT = run_output_directory("crediting_rate_capital_analysis")
DYNAMIC_READER = SCRIPT_DIRECTORY / "run_portfolio_valuation.py"
CACHE_PRECOMPUTE_RUNNER = (
    SCRIPT_DIRECTORY / "precompute_q_market_and_hedge_cache.py"
)

SUMMARY_FIELDS: Mapping[str, str] = {
    "premium_aud": "normalised_average_premium_aud",
    "csm_aud": (
        "normalised_average_insurer_net_present_value_before_risk_margin_aud"
    ),
    "pv_fee_income_aud": "normalised_average_pv_future_fees_aud",
    "pv_crediting_margin_aud": "normalised_average_pv_crediting_margin_aud",
    "pv_mva_retained_aud": "normalised_average_pv_mva_retained_aud",
    "pv_aps_retained_aud": "normalised_average_pv_aps_retained_aud",
    "pv_claims_aud": "normalised_average_pv_guarantee_claims_aud",
    "pv_expenses_aud": "normalised_average_pv_expenses_aud",
    "pv_hedge_costs_aud": "normalised_average_pv_hedge_costs_aud",
    "income_start_year_mean": "normalised_average_income_start_year_mean",
    "income_election_share": "normalised_average_income_election_share",
    "ordinary_income_lapse_rate": (
        "normalised_average_ordinary_income_lapse_rate"
    ),
    "performance_income_lapse_rate": (
        "normalised_average_performance_income_lapse_rate"
    ),
    "total_income_lapse_rate": "normalised_average_total_income_lapse_rate",
    "ordinary_income_lapse_event_mass": (
        "normalised_average_ordinary_income_lapse_event_mass"
    ),
    "performance_income_lapse_event_mass": (
        "normalised_average_performance_income_lapse_event_mass"
    ),
    "total_income_lapse_event_mass": (
        "normalised_average_total_income_lapse_event_mass"
    ),
    "growth_phase_exposure": "normalised_average_growth_phase_exposure",
    "income_phase_exposure": "normalised_average_income_phase_exposure",
}


@dataclass(frozen=True)
class ValuationJob:
    """One isolated Dynamic-Behaviour cap/stress revaluation."""

    sequence: int
    cap: float
    stress_id: str
    output: Path
    command: tuple[str, ...]


def _parse_cap_grid(raw: str) -> tuple[float, ...]:
    try:
        values = tuple(float(item.strip()) for item in raw.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--cap-grid must be a comma-separated list of decimal rates"
        ) from exc
    if not values or any(
        not math.isfinite(value) or value < 0.0 or value > 1.0
        for value in values
    ):
        raise argparse.ArgumentTypeError(
            "--cap-grid values must be finite rates between zero and one"
        )
    if len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("--cap-grid values must be unique")
    return tuple(sorted(values))


def _cap_label(cap: float) -> str:
    text = f"{100.0 * cap:.8f}".rstrip("0").rstrip(".")
    return text.replace(".", "p") + "pct"


def _utc_run_id(now: Optional[datetime] = None) -> str:
    value = datetime.now(timezone.utc) if now is None else now
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    evaluation = require_mc_samples(load_mc_analysis_inputs(), "evaluation", 1)[0]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-points", type=Path,
                        default=DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH)
    parser.add_argument("--cost-assumptions", type=Path,
                        default=DEFAULT_COST_ASSUMPTIONS_PATH)
    parser.add_argument("--cost-assumption-set", default=None)
    parser.add_argument("--dynamic-behaviour", type=Path,
                        default=DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY)
    parser.add_argument("--behaviour-assumption-set", default=None)
    parser.add_argument("--zero-curve", type=Path,
                        default=DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH)
    parser.add_argument("--model-parameters", type=Path,
                        default=DEFAULT_MODEL_PARAMETERS_PATH)
    parser.add_argument(
        "--cap-grid",
        type=_parse_cap_grid,
        default=DEFAULT_CAP_GRID,
        help="comma-separated fixed-cap rates (default: 0.0025,0.01,0.06,0.12)",
    )
    parser.add_argument("--baseline-cap", type=float,
                        default=DEFAULT_BASELINE_CAP)
    parser.add_argument("--n-paths", type=int, default=evaluation.n_paths)
    parser.add_argument("--seed", type=int, default=evaluation.market_seed)
    parser.add_argument("--take-up-seed", type=int,
                        default=evaluation.take_up_seed)
    parser.add_argument("--mortality-seed", type=int,
                        default=evaluation.mortality_seed)
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument("--market-cache-root", type=Path,
                        default=Q_MARKET_PATH_CACHE_ROOT)
    parser.add_argument("--hedge-cache-root", type=Path,
                        default=Q_HEDGE_PRICE_CACHE_ROOT)
    parser.add_argument(
        "--hedge-pricing-method",
        choices=("mc_conditional", "moment_matched_bs"),
        default="mc_conditional",
    )
    parser.add_argument(
        "--objective",
        choices=("capital_adjusted_csm", "csm_to_capital"),
        default="capital_adjusted_csm",
        help=(
            "deployment ranking; capital_adjusted_csm is the robust default, "
            "while csm_to_capital is a secondary lifetime efficiency ratio"
        ),
    )
    parser.add_argument(
        "--capital-hurdle-rate",
        type=float,
        default=0.06,
        help="one-year capital charge applied to the MLL proxy (default: 6%%)",
    )
    parser.add_argument(
        "--capital-materiality-bp",
        type=float,
        default=1.0,
        help="minimum MLL capital for reporting a CSM/capital ratio, in bp of premium",
    )
    parser.add_argument(
        "--mass-lapse-fraction",
        type=float,
        default=0.40,
        help=(
            "model-point positive-value proxy fraction; this is not a mass-"
            "lapse revaluation (default: 40%%)"
        ),
    )
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--blas-threads", type=int, default=1)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)

    args.cap_grid = tuple(float(value) for value in args.cap_grid)
    if args.n_paths <= 0 or args.heston_substeps <= 0:
        parser.error("--n-paths and --heston-substeps must be positive")
    if min(args.seed, args.take_up_seed, args.mortality_seed) < 0:
        parser.error("all seeds must be non-negative")
    if args.max_workers <= 0 or args.blas_threads <= 0:
        parser.error("--max-workers and --blas-threads must be positive")
    if not math.isfinite(args.baseline_cap) or not any(
        math.isclose(args.baseline_cap, cap, rel_tol=0.0, abs_tol=1e-12)
        for cap in args.cap_grid
    ):
        parser.error("--baseline-cap must occur exactly in --cap-grid")
    if (
        not math.isfinite(args.capital_hurdle_rate)
        or args.capital_hurdle_rate < 0.0
    ):
        parser.error("--capital-hurdle-rate must be finite and non-negative")
    if (
        not math.isfinite(args.capital_materiality_bp)
        or args.capital_materiality_bp < 0.0
    ):
        parser.error("--capital-materiality-bp must be finite and non-negative")
    if (
        not math.isfinite(args.mass_lapse_fraction)
        or not 0.0 <= args.mass_lapse_fraction <= 1.0
    ):
        parser.error("--mass-lapse-fraction must lie in [0, 1]")
    return args


def _projection_horizon_years(model_points_path: Path) -> float:
    model_points = load_policyholder_model_points(model_points_path)
    basis = ValuationSettings(horizon_years=None)
    return float(max(
        resolve_horizon(basis, point.policy)
        for point in model_points.model_points
    ))


def _run_logged_command(
    command: Sequence[str],
    output: Path,
    *,
    blas_threads: int,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    log_path = output / "orchestrator_console.log"
    environment = os.environ.copy()
    for name in (
        "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        environment[name] = str(blas_threads)
    with log_path.open("w", encoding="utf-8") as handle:
        completed = subprocess.run(
            list(command),
            cwd=str(Path.cwd()),
            stdout=handle,
            stderr=subprocess.STDOUT,
            env=environment,
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}; see {log_path}"
        )


def _precompute_commands(
    args: argparse.Namespace,
    *,
    horizon_years: float,
    output: Path,
) -> tuple[tuple[tuple[str, ...], Path], ...]:
    commands = []
    for cap in args.cap_grid:
        command = [
            sys.executable,
            str(CACHE_PRECOMPUTE_RUNNER.resolve()),
            "--zero-curve", str(args.zero_curve.expanduser().resolve()),
            "--model-parameters", str(args.model_parameters.expanduser().resolve()),
            "--market-cache-root", str(args.market_cache_root.expanduser().resolve()),
            "--hedge-cache-root", str(args.hedge_cache_root.expanduser().resolve()),
            "--horizon-years", f"{horizon_years:.12g}",
            "--n-paths", str(args.n_paths),
            "--seed", str(args.seed),
            "--heston-substeps", str(args.heston_substeps),
            "--market-stress", "base",
        ]
        if args.hedge_pricing_method == "mc_conditional":
            command.extend(("--cap-grid", f"{cap:.12g}"))
        else:
            command.append("--market-only")
        commands.append((
            tuple(command),
            output / "cache_precompute" / _cap_label(cap),
        ))
    return tuple(commands)


def _valuation_command(
    args: argparse.Namespace,
    *,
    cap: float,
    stress_id: str,
    output: Path,
) -> tuple[str, ...]:
    command = [
        sys.executable,
        str(DYNAMIC_READER.resolve()),
        "--model-points", str(args.model_points.expanduser().resolve()),
        "--cost-assumptions", str(args.cost_assumptions.expanduser().resolve()),
        "--dynamic-behaviour", str(args.dynamic_behaviour.expanduser().resolve()),
        "--zero-curve", str(args.zero_curve.expanduser().resolve()),
        "--model-parameters", str(args.model_parameters.expanduser().resolve()),
        "--n-paths", str(args.n_paths),
        "--seed", str(args.seed),
        "--take-up-seed", str(args.take_up_seed),
        "--mortality-seed", str(args.mortality_seed),
        "--heston-substeps", str(args.heston_substeps),
        "--market-cache-root", str(args.market_cache_root.expanduser().resolve()),
        "--hedge-cache-root", str(args.hedge_cache_root.expanduser().resolve()),
        "--hedge-pricing-method", args.hedge_pricing_method,
        "--income-election-mode", "dynamic",
        "--post-income-behaviour", "dynamic",
        "--stress-scenario", stress_id,
        "--crediting-cap-rate", f"{cap:.12g}",
        "--require-market-cache",
        "--no-plots",
        "--log-level", "WARNING",
        "--output", str(output.resolve()),
    ]
    if args.hedge_pricing_method == "mc_conditional":
        command.append("--require-hedge-cache")
    if args.cost_assumption_set is not None:
        command.extend(("--cost-assumption-set", args.cost_assumption_set))
    if args.behaviour_assumption_set is not None:
        command.extend((
            "--behaviour-assumption-set", args.behaviour_assumption_set,
        ))
    return tuple(command)


def _assert_dynamic_only_command(command: Sequence[str]) -> None:
    tokens = tuple(str(token).lower() for token in command)
    joined = " ".join(tokens)
    if Path(command[1]).resolve() != DYNAMIC_READER.resolve():
        raise ValueError("Capital analysis may only call the Dynamic reader.")
    forbidden = (
        "run_portfolio_valuation_lsmc.py",
        "optimize_crediting_rate_lsmc.py",
        "optimize_crediting_rate_bellman.py",
    )
    if any(token in joined for token in forbidden):
        raise ValueError("Policyholder-LSMC command detected and blocked.")
    required_pairs = {
        "--income-election-mode": "dynamic",
        "--post-income-behaviour": "dynamic",
    }
    for flag, value in required_pairs.items():
        if flag not in tokens or tokens[tokens.index(flag) + 1] != value:
            raise ValueError(f"Dynamic-only command is missing {flag} {value}.")
    if "--require-market-cache" not in tokens:
        raise ValueError("Dynamic-only command must require the market cache.")


def _build_jobs(args: argparse.Namespace, output: Path) -> tuple[ValuationJob, ...]:
    jobs = []
    sequence = 0
    for cap in args.cap_grid:
        for stress_id in STRESS_IDS:
            sequence += 1
            job_output = (
                output / "scenarios" / f"cap_{_cap_label(cap)}" / stress_id
            )
            command = _valuation_command(
                args, cap=cap, stress_id=stress_id, output=job_output
            )
            _assert_dynamic_only_command(command)
            jobs.append(ValuationJob(
                sequence=sequence,
                cap=cap,
                stress_id=stress_id,
                output=job_output,
                command=command,
            ))
    return tuple(jobs)


def _execute_jobs(
    jobs: Sequence[ValuationJob],
    *,
    max_workers: int,
    blas_threads: int,
) -> None:
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _run_logged_command,
                job.command,
                job.output,
                blas_threads=blas_threads,
            ): job
            for job in jobs
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                future.result()
            except Exception as exc:
                raise RuntimeError(
                    f"Dynamic valuation failed for cap={job.cap:.6g}, "
                    f"stress={job.stress_id}."
                ) from exc


def _read_single_csv(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one row in {path}; got {len(rows)}.")
    return dict(rows[0])


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _as_float(row: Mapping[str, object], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Missing or invalid numeric result field {key!r}.") from exc
    if not math.isfinite(value):
        raise ValueError(f"Result field {key!r} must be finite.")
    return value


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"Expected a boolean value, got {value!r}.")


def _validate_dynamic_output(
    job: ValuationJob,
    summary: Mapping[str, object],
    manifest: Mapping[str, object],
    *,
    hedge_pricing_method: str,
) -> None:
    method = manifest.get("method")
    settings = manifest.get("valuation_settings")
    stress = manifest.get("stress_scenario")
    if not isinstance(method, Mapping) or not isinstance(settings, Mapping):
        raise ValueError(f"Incomplete Dynamic manifest in {job.output}.")
    if _as_bool(summary.get("lsmc_used")) or _as_bool(method.get("lsmc_used")):
        raise ValueError("Policyholder LSMC was used; capital run is invalid.")
    if settings.get("income_election_mode") != "dynamic" or settings.get(
        "post_income_behaviour"
    ) != "dynamic":
        raise ValueError("Capital run did not retain complete Dynamic Behaviour.")
    if not _as_bool(settings.get("require_market_cache")):
        raise ValueError("Capital run did not enforce the market cache.")
    if hedge_pricing_method == "mc_conditional" and not _as_bool(
        settings.get("require_hedge_cache")
    ):
        raise ValueError("Conditional-MC capital run did not enforce hedge cache.")
    if not isinstance(stress, Mapping):
        raise ValueError(f"Dynamic manifest has no stress definition in {job.output}.")
    if stress.get("stress_id") != job.stress_id:
        raise ValueError("Dynamic manifest stress does not match the job.")
    if not math.isclose(
        _as_float(summary, "crediting_cap_rate"),
        job.cap,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("Dynamic output uses a different crediting cap.")


def _positive_model_point_value(
    rows: Iterable[Mapping[str, object]],
) -> float:
    candidates = (
        "normalised_contribution_insurer_net_present_value_before_risk_margin_aud",
    )
    total = 0.0
    for row in rows:
        selected = next(
            (key for key in candidates if str(row.get(key, "")).strip() != ""),
            None,
        )
        if selected is None:
            raise ValueError("Model-point CSM contribution is missing.")
        total += max(_as_float(row, selected), 0.0)
    return total


def _collect_scenario_rows(
    jobs: Sequence[ValuationJob],
    *,
    hedge_pricing_method: str,
) -> tuple[list[dict[str, object]], dict[float, float]]:
    scenario_rows: list[dict[str, object]] = []
    positive_base_value: dict[float, float] = {}
    identity_by_cap: dict[float, tuple[str, str, str, str]] = {}
    for job in sorted(jobs, key=lambda item: item.sequence):
        summary = _read_single_csv(job.output / "portfolio_summary.csv")
        with (job.output / "run_manifest.json").open(
            "r", encoding="utf-8"
        ) as handle:
            manifest = json.load(handle)
        _validate_dynamic_output(
            job, summary, manifest,
            hedge_pricing_method=hedge_pricing_method,
        )
        identity = tuple(str(summary.get(key, "")) for key in (
            "market_cache_key",
            "scenario_fingerprint",
            "hedge_cache_key",
            "hedge_price_surface_fingerprint",
        ))
        if job.cap in identity_by_cap and identity != identity_by_cap[job.cap]:
            raise ValueError(
                "A non-market stress changed the market or hedge cache identity."
            )
        identity_by_cap.setdefault(job.cap, identity)
        row: dict[str, object] = {
            "crediting_cap_rate": job.cap,
            "crediting_cap_rate_percent": 100.0 * job.cap,
            "stress_scenario_id": job.stress_id,
            "policyholder_behaviour": "dynamic",
            "policyholder_lsmc_used": False,
            "market_cache_key": identity[0],
            "scenario_fingerprint": identity[1],
            "hedge_cache_key": identity[2],
            "hedge_price_surface_fingerprint": identity[3],
            "scenario_directory": str(job.output.resolve()),
        }
        for output_name, source_name in SUMMARY_FIELDS.items():
            row[output_name] = _as_float(summary, source_name)
        reconciled_csm = (
            float(row["pv_fee_income_aud"])
            + float(row["pv_crediting_margin_aud"])
            + float(row["pv_mva_retained_aud"])
            + float(row["pv_aps_retained_aud"])
            - float(row["pv_claims_aud"])
            - float(row["pv_expenses_aud"])
            - float(row["pv_hedge_costs_aud"])
        )
        reconciliation_gap = float(row["csm_aud"]) - reconciled_csm
        tolerance = 1.0e-8 * max(abs(float(row["csm_aud"])), 1.0)
        if abs(reconciliation_gap) > tolerance:
            raise ValueError(
                "Dynamic CSM components do not reconcile for "
                f"cap={job.cap:.6g}, stress={job.stress_id}: "
                f"gap={reconciliation_gap:.12g}."
            )
        row["csm_reconciliation_gap_aud"] = reconciliation_gap
        scenario_rows.append(row)
        if job.stress_id == "base":
            positive_base_value[job.cap] = _positive_model_point_value(
                _read_csv(job.output / "model_point_results.csv")
            )
    return scenario_rows, positive_base_value


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _build_capital_rows(
    scenario_rows: Sequence[Mapping[str, object]],
    positive_base_value: Mapping[float, float],
    *,
    baseline_cap: float,
    capital_hurdle_rate: float,
    capital_materiality_bp: float,
    mass_lapse_fraction: float,
    objective: str,
) -> list[dict[str, object]]:
    # Imported here so the pure calculation module remains independently
    # testable and this orchestrator remains cheap to import for CLI help.
    from policy_engine.crediting_capital import (  # noqa: PLC0415
        MASS_LAPSE_METHOD,
        adverse_csm_loss,
        aggregate_mll_capital,
        evaluate_capital_adjusted_csm,
        model_point_mass_lapse_proxy,
    )

    indexed = {
        (float(row["crediting_cap_rate"]), str(row["stress_scenario_id"])): row
        for row in scenario_rows
    }
    caps = sorted({key[0] for key in indexed})
    rows: list[dict[str, object]] = []
    for cap in caps:
        by_stress = {stress: indexed[(cap, stress)] for stress in STRESS_IDS}
        base_csm = float(by_stress["base"]["csm_aud"])
        mortality_signed = base_csm - float(by_stress["mortality"]["csm_aud"])
        longevity_signed = base_csm - float(by_stress["longevity"]["csm_aud"])
        lapse_up_signed = base_csm - float(by_stress["lapse_up"]["csm_aud"])
        lapse_down_signed = base_csm - float(by_stress["lapse_down"]["csm_aud"])
        mortality_capital = adverse_csm_loss(base_csm, float(
            by_stress["mortality"]["csm_aud"]
        ))
        longevity_capital = adverse_csm_loss(base_csm, float(
            by_stress["longevity"]["csm_aud"]
        ))
        lapse_up_capital = adverse_csm_loss(base_csm, float(
            by_stress["lapse_up"]["csm_aud"]
        ))
        lapse_down_capital = adverse_csm_loss(base_csm, float(
            by_stress["lapse_down"]["csm_aud"]
        ))
        mass_lapse_capital = model_point_mass_lapse_proxy(
            [float(positive_base_value[cap])],
            [1.0],
            mass_lapse_rate=mass_lapse_fraction,
        )
        lapse_by_name = {
            "lapse_up": lapse_up_capital,
            "lapse_down": lapse_down_capital,
            "mass_lapse": mass_lapse_capital,
        }
        permanent_lapse_by_name = {
            "lapse_up": lapse_up_capital,
            "lapse_down": lapse_down_capital,
        }
        binding_permanent_lapse_stress = max(
            ("lapse_up", "lapse_down"),
            key=permanent_lapse_by_name.__getitem__,
        )
        permanent_lapse_capital = permanent_lapse_by_name[
            binding_permanent_lapse_stress
        ]
        binding_lapse_stress = max(
            ("lapse_up", "lapse_down", "mass_lapse"),
            key=lapse_by_name.__getitem__,
        )
        lapse_capital = lapse_by_name[binding_lapse_stress]
        mll_permanent_lapse_only = aggregate_mll_capital(
            mortality_capital,
            longevity_capital,
            permanent_lapse_capital,
        )
        mll_life_capital = aggregate_mll_capital(
            mortality_capital,
            longevity_capital,
            lapse_capital,
        )
        premium = float(by_stress["base"]["premium_aud"])
        materiality = premium * capital_materiality_bp / 10_000.0
        metrics = evaluate_capital_adjusted_csm(
            base_csm,
            mll_life_capital,
            capital_hurdle=capital_hurdle_rate,
            capital_materiality=materiality,
        )
        row = {
            "crediting_cap_rate": cap,
            "crediting_cap_rate_percent": 100.0 * cap,
            "base_csm_aud": base_csm,
            "premium_aud": float(by_stress["base"]["premium_aud"]),
            "mortality_stressed_csm_aud": float(
                by_stress["mortality"]["csm_aud"]
            ),
            "longevity_stressed_csm_aud": float(
                by_stress["longevity"]["csm_aud"]
            ),
            "lapse_up_stressed_csm_aud": float(
                by_stress["lapse_up"]["csm_aud"]
            ),
            "lapse_down_stressed_csm_aud": float(
                by_stress["lapse_down"]["csm_aud"]
            ),
            "mortality_signed_csm_loss_aud": mortality_signed,
            "longevity_signed_csm_loss_aud": longevity_signed,
            "lapse_up_signed_csm_loss_aud": lapse_up_signed,
            "lapse_down_signed_csm_loss_aud": lapse_down_signed,
            "mortality_capital_aud": mortality_capital,
            "longevity_capital_aud": longevity_capital,
            "lapse_up_capital_aud": lapse_up_capital,
            "lapse_down_capital_aud": lapse_down_capital,
            "positive_model_point_csm_aud": float(positive_base_value[cap]),
            "mass_lapse_capital_proxy_aud": mass_lapse_capital,
            "mass_lapse_method": MASS_LAPSE_METHOD,
            "permanent_lapse_capital_aud": permanent_lapse_capital,
            "binding_permanent_lapse_stress": binding_permanent_lapse_stress,
            "lapse_capital_aud": lapse_capital,
            "binding_lapse_stress": binding_lapse_stress,
            "mass_lapse_proxy_is_binding": (
                binding_lapse_stress == "mass_lapse"
            ),
            "mll_permanent_lapse_only_capital_proxy_aud": (
                mll_permanent_lapse_only
            ),
            "mll_life_capital_proxy_aud": mll_life_capital,
            "mass_lapse_incremental_mll_capital_aud": (
                mll_life_capital - mll_permanent_lapse_only
            ),
            "capital_hurdle_rate": capital_hurdle_rate,
            "one_year_capital_charge_aud": metrics.capital_charge,
            "capital_adjusted_csm_aud": metrics.capital_adjusted_csm,
            "csm_to_capital_ratio": metrics.csm_to_capital,
            "capital_adjusted_csm_to_capital_ratio": (
                None
                if metrics.csm_to_capital is None
                else metrics.capital_adjusted_csm / metrics.capital
            ),
            "capital_ratio_materiality_aud": metrics.capital_materiality,
            "total_income_lapse_event_mass": float(
                by_stress["base"]["total_income_lapse_event_mass"]
            ),
            "ordinary_income_lapse_event_mass": float(
                by_stress["base"]["ordinary_income_lapse_event_mass"]
            ),
            "performance_income_lapse_event_mass": float(
                by_stress["base"]["performance_income_lapse_event_mass"]
            ),
            "income_start_year_mean": float(
                by_stress["base"]["income_start_year_mean"]
            ),
            "is_contractual_baseline_cap": math.isclose(
                cap, baseline_cap, rel_tol=0.0, abs_tol=1e-12
            ),
        }
        rows.append(row)

    eligible = [
        row for row in rows
        if objective == "capital_adjusted_csm"
        or row["csm_to_capital_ratio"] is not None
    ]
    if not eligible:
        raise ValueError("No cap has material capital for ratio-based selection.")
    objective_field = (
        "capital_adjusted_csm_aud"
        if objective == "capital_adjusted_csm"
        else "csm_to_capital_ratio"
    )
    selected = max(
        eligible,
        key=lambda row: (float(row[objective_field]), -float(row["crediting_cap_rate"])),
    )
    baseline = next(row for row in rows if row["is_contractual_baseline_cap"])
    for row in rows:
        row["selection_objective"] = objective
        row["selection_objective_value"] = row[objective_field]
        row["is_selected_cap"] = row is selected
        row["csm_uplift_vs_baseline_aud"] = (
            float(row["base_csm_aud"]) - float(baseline["base_csm_aud"])
        )
        row["capital_release_vs_baseline_aud"] = (
            float(baseline["mll_life_capital_proxy_aud"])
            - float(row["mll_life_capital_proxy_aud"])
        )
        row["capital_adjusted_value_vs_baseline_aud"] = (
            float(row["capital_adjusted_csm_aud"])
            - float(baseline["capital_adjusted_csm_aud"])
        )
    return rows


def _create_plots(
    capital_rows: Sequence[Mapping[str, object]],
    output: Path,
    *,
    baseline_cap: float,
) -> dict[str, str]:
    import matplotlib  # noqa: PLC0415
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    output.mkdir(parents=True, exist_ok=True)
    caps = np.asarray([float(row["crediting_cap_rate_percent"])
                       for row in capital_rows])
    csm = np.asarray([float(row["base_csm_aud"]) for row in capital_rows])
    capital = np.asarray([float(row["mll_life_capital_proxy_aud"])
                          for row in capital_rows])
    adjusted = np.asarray([float(row["capital_adjusted_csm_aud"])
                           for row in capital_rows])
    baseline_percent = 100.0 * baseline_cap
    paths: dict[str, str] = {}

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), constrained_layout=True)
    axes[0].plot(caps, csm / 1_000.0, marker="o", label="CSM proxy")
    axes[0].plot(caps, capital / 1_000.0, marker="s", label="MLL capital proxy")
    axes[0].axhline(0.0, color="#777777", linewidth=0.8)
    axes[0].axvline(baseline_percent, color="#666666", linestyle="--", linewidth=1)
    axes[0].set(xlabel="Crediting cap (%)", ylabel="AUD thousand",
                title="Profit and life-risk capital")
    axes[0].legend(frameon=False)
    axes[0].grid(alpha=0.2)
    axes[1].plot(caps, adjusted / 1_000.0, marker="o", color="#6f4aa8")
    axes[1].axhline(0.0, color="#777777", linewidth=0.8)
    axes[1].axvline(baseline_percent, color="#666666", linestyle="--", linewidth=1)
    axes[1].set(xlabel="Crediting cap (%)", ylabel="AUD thousand",
                title="Capital-adjusted CSM (one-year charge)")
    axes[1].grid(alpha=0.2)
    path = output / "01_csm_and_mll_capital_by_crediting_cap.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths["csm_and_capital"] = str(path.resolve())

    fig, ax = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    for field, label, marker in (
        ("mortality_capital_aud", "Mortality", "o"),
        ("longevity_capital_aud", "Longevity", "s"),
        ("lapse_capital_aud", "Lapse (binding)", "^"),
        ("mll_life_capital_proxy_aud", "Aggregated MLL", "D"),
    ):
        ax.plot(caps, [float(row[field]) / 1_000.0 for row in capital_rows],
                marker=marker, label=label)
    ax.axvline(baseline_percent, color="#666666", linestyle="--", linewidth=1)
    ax.set(xlabel="Crediting cap (%)", ylabel="Capital proxy (AUD thousand)",
           title="Mortality, longevity and lapse capital by cap")
    ax.legend(frameon=False, ncol=2)
    ax.grid(alpha=0.2)
    path = output / "02_mll_capital_modules_by_crediting_cap.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths["capital_modules"] = str(path.resolve())

    fig, ax = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    ordinary = np.asarray([float(row["ordinary_income_lapse_event_mass"])
                           for row in capital_rows])
    performance = np.asarray([float(row["performance_income_lapse_event_mass"])
                              for row in capital_rows])
    total = np.asarray([float(row["total_income_lapse_event_mass"])
                        for row in capital_rows])
    ax.plot(caps, 100.0 * ordinary, marker="o", label="Ordinary")
    ax.plot(caps, 100.0 * performance, marker="s", label="Performance-sensitive")
    ax.plot(caps, 100.0 * total, marker="D", linewidth=2, label="Total")
    ax.axvline(baseline_percent, color="#666666", linestyle="--", linewidth=1)
    ax.set(xlabel="Crediting cap (%)",
           ylabel="Expected cumulative Income lapse event mass (%)",
           title="Dynamic Policyholder lapse response")
    ax.legend(frameon=False)
    ax.grid(alpha=0.2)
    path = output / "03_dynamic_lapse_response_by_crediting_cap.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths["dynamic_lapse"] = str(path.resolve())
    return paths


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = (
        args.output.expanduser().resolve()
        if args.output is not None
        else (DEFAULT_OUTPUT_ROOT / _utc_run_id()).resolve()
    )
    output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    horizon_years = _projection_horizon_years(args.model_points)

    print(
        "DYNAMIC-ONLY CAPITAL ANALYSIS | "
        f"caps={len(args.cap_grid)} | stresses={len(STRESS_IDS)} | "
        "Policyholder LSMC blocked",
        flush=True,
    )
    precompute = _precompute_commands(
        args, horizon_years=horizon_years, output=output
    )
    for number, (command, command_output) in enumerate(precompute, start=1):
        print(
            f"CACHE PREP {number}/{len(precompute)} | "
            f"cap={100.0 * args.cap_grid[number - 1]:.4g}%",
            flush=True,
        )
        _run_logged_command(
            command, command_output, blas_threads=args.blas_threads
        )

    jobs = _build_jobs(args, output)
    print(f"START {len(jobs)} DYNAMIC REVALUATIONS", flush=True)
    _execute_jobs(
        jobs,
        max_workers=args.max_workers,
        blas_threads=args.blas_threads,
    )
    scenario_rows, positive_base_value = _collect_scenario_rows(
        jobs, hedge_pricing_method=args.hedge_pricing_method
    )
    capital_rows = _build_capital_rows(
        scenario_rows,
        positive_base_value,
        baseline_cap=args.baseline_cap,
        capital_hurdle_rate=args.capital_hurdle_rate,
        capital_materiality_bp=args.capital_materiality_bp,
        mass_lapse_fraction=args.mass_lapse_fraction,
        objective=args.objective,
    )
    scenario_csv = output / "dynamic_stress_revaluations_by_crediting_cap.csv"
    capital_csv = output / "crediting_capital_results.csv"
    _write_csv(scenario_csv, scenario_rows)
    _write_csv(capital_csv, capital_rows)
    plot_paths = {} if args.no_plots else _create_plots(
        capital_rows, output / "plots", baseline_cap=args.baseline_cap
    )

    selected = next(row for row in capital_rows if row["is_selected_cap"])
    baseline = next(
        row for row in capital_rows if row["is_contractual_baseline_cap"]
    )
    completed = datetime.now(timezone.utc)
    manifest = {
        "generated_at_utc": completed.isoformat(),
        "started_at_utc": started.isoformat(),
        "runtime_seconds": (completed - started).total_seconds(),
        "engine_version": ENGINE_VERSION,
        "method": {
            "policyholder_behaviour": "dynamic_statistical",
            "policyholder_lsmc_used": False,
            "policyholder_lsmc_hard_block": True,
            "valuation_measure": "risk_neutral",
            "market_model": "heston_hull_white",
            "market_cache_required": True,
            "hedge_cache_required": args.hedge_pricing_method == "mc_conditional",
            "cache_writer": str(CACHE_PRECOMPUTE_RUNNER.resolve()),
            "valuation_reader": str(DYNAMIC_READER.resolve()),
            "capital_scope": "mortality_longevity_lapse_research_proxy",
            "not_total_scr": True,
            "not_apra_capital": True,
            "mass_lapse_method": selected["mass_lapse_method"],
            "capital_adjustment": "one_year_hurdle_charge_not_full_risk_margin",
        },
        "settings": {
            "cap_grid": list(args.cap_grid),
            "baseline_cap": args.baseline_cap,
            "stress_ids": list(STRESS_IDS),
            "n_paths": args.n_paths,
            "market_seed": args.seed,
            "take_up_seed": args.take_up_seed,
            "mortality_seed": args.mortality_seed,
            "heston_substeps": args.heston_substeps,
            "horizon_years": horizon_years,
            "hedge_pricing_method": args.hedge_pricing_method,
            "objective": args.objective,
            "capital_hurdle_rate": args.capital_hurdle_rate,
            "capital_materiality_bp": args.capital_materiality_bp,
            "mass_lapse_fraction": args.mass_lapse_fraction,
            "max_workers": args.max_workers,
            "blas_threads": args.blas_threads,
        },
        "selection": {
            "selected_cap": selected["crediting_cap_rate"],
            "selected_cap_percent": selected["crediting_cap_rate_percent"],
            "selection_objective": args.objective,
            "selection_objective_value": selected["selection_objective_value"],
            "contractual_baseline_cap": args.baseline_cap,
            "capital_adjusted_value_vs_baseline_aud": selected[
                "capital_adjusted_value_vs_baseline_aud"
            ],
            "csm_uplift_vs_baseline_aud": selected[
                "csm_uplift_vs_baseline_aud"
            ],
            "capital_release_vs_baseline_aud": selected[
                "capital_release_vs_baseline_aud"
            ],
            "baseline_capital_adjusted_csm_aud": baseline[
                "capital_adjusted_csm_aud"
            ],
        },
        "limitations": [
            "The MLL amount is a partial research life-risk capital proxy, not APRA capital or total SCR.",
            "Mass lapse is a model-point positive-value proxy, not an immediate-surrender revaluation.",
            "The capital charge is one year at the selected hurdle rate, not a full projected risk margin.",
            "Dynamic Behaviour and Gompertz-Makeham mortality are illustrative, uncalibrated proxies.",
            "The selected cap is the best point on the supplied discrete grid, not a continuous global optimum.",
            "The analysis values fixed cap designs; it does not establish value for an annual adaptive cap policy.",
        ],
        "sources": {
            "model_points": str(args.model_points.expanduser().resolve()),
            "cost_assumptions": str(args.cost_assumptions.expanduser().resolve()),
            "dynamic_behaviour": str(args.dynamic_behaviour.expanduser().resolve()),
            "zero_curve": str(args.zero_curve.expanduser().resolve()),
            "model_parameters": str(args.model_parameters.expanduser().resolve()),
            "market_cache_root": str(args.market_cache_root.expanduser().resolve()),
            "hedge_cache_root": str(args.hedge_cache_root.expanduser().resolve()),
        },
        "outputs": {
            "dynamic_stress_revaluations_csv": str(scenario_csv.resolve()),
            "crediting_capital_results_csv": str(capital_csv.resolve()),
            "plots": plot_paths,
        },
    }
    manifest_path = output / "run_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")

    print(
        "RUN COMPLETE | "
        f"selected cap={float(selected['crediting_cap_rate_percent']):.4g}% | "
        f"capital-adjusted value vs {100.0 * args.baseline_cap:.4g}%="
        f"{float(selected['capital_adjusted_value_vs_baseline_aud']):,.2f} AUD | "
        f"output={output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
