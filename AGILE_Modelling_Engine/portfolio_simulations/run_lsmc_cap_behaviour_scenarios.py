"""Quantify how constant crediting caps affect LSMC-optimal behaviour.

Each cap receives a fresh LSMC fit.  Training and final evaluation stay
separate, while common seeds make all cap comparisons use common market random
numbers.  Every scenario also retains the Dynamic-Behaviour and Continue
benchmarks produced by ``run_portfolio_valuation_lsmc.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence

import numpy as np


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
LSMC_PORTFOLIO_RUNNER = SCRIPT_DIRECTORY / "run_portfolio_valuation_lsmc.py"
DEFAULT_OUTPUT_DIRECTORY = (
    SCRIPT_DIRECTORY / "output" / "lsmc_cap_behaviour_scenarios"
)
DEFAULT_CAP_RATES = (0.04, 0.06, 0.12, 0.20)
DEFAULT_BASELINE_RATE = 0.06


def _parse_rate(text: str) -> float:
    raw = str(text).strip()
    is_percent = raw.endswith("%")
    if is_percent:
        raw = raw[:-1].strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid cap rate: {text!r}") from exc
    if is_percent or value >= 1.0:
        value /= 100.0
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError("cap rates must be between 0% and 100%")
    return value


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--cap-rates",
        nargs="+",
        type=_parse_rate,
        default=list(DEFAULT_CAP_RATES),
        metavar="RATE",
    )
    parser.add_argument(
        "--baseline-rate", type=_parse_rate, default=DEFAULT_BASELINE_RATE)
    parser.add_argument("--n-paths", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--n-train", type=int, default=4_000)
    parser.add_argument("--train-seed", type=int, default=12026)
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument("--lsmc-folds", type=int, default=5)
    parser.add_argument("--lsmc-ridge", type=float, default=1.0e-6)
    parser.add_argument(
        "--exercise-buffer-rmse-multiplier", type=float, default=0.25)
    parser.add_argument("--portfolio-contract-count", type=float, default=None)
    parser.add_argument("--profitability-materiality-bp", type=float, default=1.0)
    parser.add_argument("--model-points", type=Path, default=None)
    parser.add_argument("--cost-assumptions", type=Path, default=None)
    parser.add_argument("--cost-assumption-set", default=None)
    parser.add_argument("--dynamic-behaviour", type=Path, default=None)
    parser.add_argument("--behaviour-assumption-set", default=None)
    parser.add_argument("--zero-curve", type=Path, default=None)
    parser.add_argument("--model-parameters", type=Path, default=None)
    parser.add_argument("--scenario-plots", action="store_true")
    parser.add_argument(
        "--no-dynamic-benchmark",
        action="store_true",
        help="analyse LSMC versus Continue without loading behaviour CSVs",
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="reuse complete scenario directories instead of rerunning them",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="WARNING",
    )
    args = parser.parse_args(argv)
    for name in ("n_paths", "n_train", "heston_substeps"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.lsmc_folds < 2:
        parser.error("--lsmc-folds must be at least two")
    if args.seed < 0 or args.train_seed < 0 or args.seed == args.train_seed:
        parser.error("evaluation and training seeds must be distinct and non-negative")
    for name in ("lsmc_ridge", "exercise_buffer_rmse_multiplier"):
        value = float(getattr(args, name))
        if not math.isfinite(value) or value < 0.0:
            parser.error(f"--{name.replace('_', '-')} must be non-negative")
    if args.portfolio_contract_count is not None and (
        not math.isfinite(args.portfolio_contract_count)
        or args.portfolio_contract_count <= 0.0
    ):
        parser.error("--portfolio-contract-count must be positive and finite")
    return args


def _rate_key(rate: float) -> float:
    return round(float(rate), 12)


def _rate_directory_name(rate: float) -> str:
    percent = f"{100.0 * rate:.6f}".rstrip("0").rstrip(".")
    return f"cap_{percent.replace('.', 'p')}pct"


def _optional_argument(command: list[str], flag: str, value: object) -> None:
    if value is not None:
        command.extend((flag, str(value)))


def _scenario_command(
    args: argparse.Namespace,
    rate: float,
    scenario_output: Path,
) -> list[str]:
    command = [
        str(args.python_executable),
        str(LSMC_PORTFOLIO_RUNNER),
        "--crediting-cap-rate", f"{rate:.12g}",
        "--n-paths", str(args.n_paths),
        "--seed", str(args.seed),
        "--n-train", str(args.n_train),
        "--train-seed", str(args.train_seed),
        "--heston-substeps", str(args.heston_substeps),
        "--lsmc-folds", str(args.lsmc_folds),
        "--lsmc-ridge", str(args.lsmc_ridge),
        "--exercise-buffer-rmse-multiplier",
        str(args.exercise_buffer_rmse_multiplier),
        "--profitability-materiality-bp",
        str(args.profitability_materiality_bp),
        "--log-level", args.log_level,
        "--output", str(scenario_output),
    ]
    if not args.scenario_plots:
        command.append("--no-plots")
    if args.no_dynamic_benchmark:
        command.append("--no-dynamic-benchmark")
    _optional_argument(command, "--portfolio-contract-count",
                       args.portfolio_contract_count)
    _optional_argument(command, "--model-points", args.model_points)
    _optional_argument(command, "--cost-assumptions", args.cost_assumptions)
    _optional_argument(command, "--cost-assumption-set", args.cost_assumption_set)
    _optional_argument(command, "--dynamic-behaviour", args.dynamic_behaviour)
    _optional_argument(command, "--behaviour-assumption-set",
                       args.behaviour_assumption_set)
    _optional_argument(command, "--zero-curve", args.zero_curve)
    _optional_argument(command, "--model-parameters", args.model_parameters)
    return command


def _read_single_csv_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ValueError(f"Expected one row in {path}, found {len(rows)}")
    return dict(rows[0])


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _as_float(value: object, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Missing or invalid result field {field}") from exc
    if not math.isfinite(result):
        raise ValueError(f"Non-finite result field {field}")
    return result


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _monetary(summary: Mapping[str, object], metric: str) -> float:
    absolute = _as_bool(summary.get("absolute_portfolio_values_available"))
    prefix = "portfolio_total_" if absolute else "normalised_average_"
    field = f"{prefix}{metric}"
    return _as_float(summary.get(field), field)


def _validate_aggregation_reconciliation(path: Path, label: str) -> None:
    rows = _read_csv(path)
    if not rows:
        raise ValueError(f"Empty aggregation reconciliation for {label}: {path}")
    failed = [
        row.get("metric", "<unknown>")
        for row in rows
        if not _as_bool(row.get("within_numerical_tolerance"))
    ]
    if failed:
        raise ValueError(
            f"Aggregation reconciliation failed for {label}: "
            + ", ".join(str(metric) for metric in failed)
        )


def _summary_metrics(summary: Mapping[str, object], label: str) -> dict[str, object]:
    return {
        f"{label}_policyholder_benefits_aud": _monetary(
            summary, "pv_policyholder_benefits_aud"),
        f"{label}_future_fees_aud": _monetary(summary, "pv_future_fees_aud"),
        f"{label}_guarantee_claims_aud": _monetary(
            summary, "pv_guarantee_claims_aud"),
        f"{label}_crediting_margin_aud": _monetary(
            summary, "pv_crediting_margin_aud"),
        f"{label}_bel_total_aud": _monetary(summary, "bel_total_aud"),
        f"{label}_insurer_npv_aud": _monetary(
            summary, "insurer_net_present_value_before_risk_margin_aud"),
        f"{label}_new_business_margin": _as_float(
            summary.get("new_business_margin_before_risk_margin"),
            "new_business_margin_before_risk_margin"),
        f"{label}_identity_gap": _as_float(
            summary.get("premium_weighted_identity_gap"),
            "premium_weighted_identity_gap"),
    }


def _quantile(values: list[float], probability: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), probability))


def _scenario_result(
    rate: float,
    directory: Path,
    *,
    include_dynamic: bool,
) -> dict[str, object]:
    lsmc = _read_single_csv_row(directory / "portfolio_summary.csv")
    continue_summary = _read_single_csv_row(
        directory / "continue_benchmark" / "portfolio_summary.csv")
    dynamic = (
        _read_single_csv_row(
            directory / "dynamic_benchmark" / "portfolio_summary.csv")
        if include_dynamic else None
    )
    with (directory / "run_manifest.json").open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    actual_rate = _as_float(lsmc.get("crediting_cap_rate"), "crediting_cap_rate")
    if not math.isclose(actual_rate, rate, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(f"Cap mismatch in {directory}: {actual_rate} != {rate}")

    _validate_aggregation_reconciliation(
        directory / "portfolio_aggregation_reconciliation.csv", "LSMC")
    _validate_aggregation_reconciliation(
        directory / "continue_benchmark"
        / "portfolio_aggregation_reconciliation.csv",
        "Continue",
    )
    if include_dynamic:
        _validate_aggregation_reconciliation(
            directory / "dynamic_benchmark"
            / "portfolio_aggregation_reconciliation.csv",
            "Dynamic",
        )

    actions = _read_csv(directory / "lsmc_action_summary.csv")
    exercise_count = sum(int(float(row["exercise_path_count"])) for row in actions)
    eligible_count = sum(int(float(row["eligible_path_count"])) for row in actions)
    diagnostics = _read_csv(directory / "lsmc_regression_diagnostics.csv")
    r_squared = [_as_float(row["oof_r_squared"], "oof_r_squared")
                 for row in diagnostics]
    conditions = [_as_float(row["condition_number"], "condition_number")
                  for row in diagnostics]
    accepted = sum(_as_bool(row["regression_accepted_for_exercise"])
                   for row in diagnostics)

    row: dict[str, object] = {
        "cap_rate": actual_rate,
        "cap_rate_percent": 100.0 * actual_rate,
        "valuation_basis": (
            "absolute_portfolio"
            if _as_bool(lsmc.get("absolute_portfolio_values_available"))
            else "normalised_average_contract"
        ),
        "premium_aud": _monetary(lsmc, "premium_aud"),
        **_summary_metrics(continue_summary, "continue"),
        **_summary_metrics(lsmc, "lsmc"),
        "lsmc_exercise_path_count": exercise_count,
        "lsmc_eligible_path_decision_count": eligible_count,
        "lsmc_exercise_rate": (
            exercise_count / eligible_count if eligible_count else 0.0),
        # Unweighted over model-point/path/decision events: this is a useful
        # policy diagnostic, not a portfolio surrender rate.
        "lsmc_unweighted_decision_event_rate": (
            exercise_count / eligible_count if eligible_count else 0.0),
        "lsmc_unique_policy_fits": int(
            manifest["lsmc_settings"]["unique_policy_fits"]),
        "lsmc_training_fallback_policy_count": int(
            manifest["lsmc_settings"]["training_fallback_policy_count"]),
        "lsmc_regression_count": len(diagnostics),
        "lsmc_regression_accepted_count": accepted,
        "lsmc_regression_rejected_count": len(diagnostics) - accepted,
        "lsmc_oof_r_squared_q25": _quantile(r_squared, 0.25),
        "lsmc_oof_r_squared_median": _quantile(r_squared, 0.50),
        "lsmc_condition_number_median": _quantile(conditions, 0.50),
        "lsmc_condition_number_max": max(conditions),
        "evaluation_scenario_fingerprint": manifest[
            "evaluation_settings"]["scenario_fingerprint"],
        "training_scenario_fingerprint": manifest[
            "lsmc_settings"]["training_scenario_fingerprint"],
        "scenario_directory": str(directory),
    }
    if dynamic is not None:
        row.update(_summary_metrics(dynamic, "dynamic"))
    row.update({
        "lsmc_minus_continue_policyholder_benefits_aud": (
            float(row["lsmc_policyholder_benefits_aud"])
            - float(row["continue_policyholder_benefits_aud"])),
    })
    if dynamic is not None:
        row.update({
            "lsmc_minus_dynamic_policyholder_benefits_aud": (
                float(row["lsmc_policyholder_benefits_aud"])
                - float(row["dynamic_policyholder_benefits_aud"])),
            "lsmc_minus_dynamic_insurer_npv_aud": (
                float(row["lsmc_insurer_npv_aud"])
                - float(row["dynamic_insurer_npv_aud"])),
        })
    return row


def _add_baseline_deltas(
    rows: list[dict[str, object]], baseline_rate: float,
) -> None:
    by_rate = {_rate_key(float(row["cap_rate"])): row for row in rows}
    baseline = by_rate[_rate_key(baseline_rate)]
    delta_fields = (
        "lsmc_policyholder_benefits_aud",
        "lsmc_future_fees_aud",
        "lsmc_guarantee_claims_aud",
        "lsmc_crediting_margin_aud",
        "lsmc_bel_total_aud",
        "lsmc_insurer_npv_aud",
        "lsmc_new_business_margin",
        "lsmc_exercise_rate",
    )
    optional_fields = (
        "dynamic_policyholder_benefits_aud",
        "dynamic_insurer_npv_aud",
    )
    for row in rows:
        for field in delta_fields:
            row[f"delta_vs_{100 * baseline_rate:g}pct_{field}"] = (
                float(row[field]) - float(baseline[field]))
        for field in optional_fields:
            if field in row and field in baseline:
                row[f"delta_vs_{100 * baseline_rate:g}pct_{field}"] = (
                    float(row[field]) - float(baseline[field]))
        mechanical = (
            float(row["continue_policyholder_benefits_aud"])
            - float(baseline["continue_policyholder_benefits_aud"])
        )
        behaviour_interaction = (
            float(row["lsmc_minus_continue_policyholder_benefits_aud"])
            - float(baseline[
                "lsmc_minus_continue_policyholder_benefits_aud"])
        )
        total = (
            float(row["lsmc_policyholder_benefits_aud"])
            - float(baseline["lsmc_policyholder_benefits_aud"])
        )
        row["mechanical_continue_change_vs_baseline_aud"] = mechanical
        row["behaviour_interaction_vs_baseline_aud"] = behaviour_interaction
        row["total_lsmc_change_vs_baseline_aud"] = total
        row["cap_effect_decomposition_gap_aud"] = (
            total - mechanical - behaviour_interaction
        )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty cap comparison.")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, rows: list[dict[str, object]]) -> None:
    has_dynamic = "dynamic_policyholder_benefits_aud" in rows[0]
    lines = [
        "# Einfluss des Crediting Caps auf LSMC-Optimalverhalten",
        "",
        "Alle Geldwerte sind AUD auf der in `valuation_basis` ausgewiesenen Basis.",
        "Jedes Cap wurde separat trainiert; Training und Evaluation sind getrennt.",
        (
            "Die Exercise-Rate ist ein ungewichteter Anteil über "
            "Modellpunkt-/Pfad-/Entscheidungsereignisse und keine "
            "portfoliogewichtete Surrender-Rate. Das ökonomische "
            "Verhaltensmaß ist `Δ PH vs Continue`."
        ),
        "",
        (
            "| Cap | Raw Exercise-Rate | PH Benefits LSMC | Δ PH vs Continue | "
            "Δ PH vs Dynamic | Guarantee Claims | Insurer NPV LSMC | "
            "Δ NPV vs Dynamic |"
            if has_dynamic
            else "| Cap | Raw Exercise-Rate | PH Benefits LSMC | Δ PH vs Continue | "
            "Guarantee Claims | Insurer NPV LSMC |"
        ),
        (
            "|---:|---:|---:|---:|---:|---:|---:|---:|"
            if has_dynamic else "|---:|---:|---:|---:|---:|---:|"
        ),
    ]
    for row in rows:
        base = (
            f"| {float(row['cap_rate_percent']):.2f}% | "
            f"{100 * float(row['lsmc_exercise_rate']):.6f}% | "
            f"{float(row['lsmc_policyholder_benefits_aud']):,.2f} | "
            f"{float(row['lsmc_minus_continue_policyholder_benefits_aud']):,.2f} | "
        )
        if has_dynamic:
            base += (
                f"{float(row['lsmc_minus_dynamic_policyholder_benefits_aud']):,.2f} | "
            )
        base += (
            f"{float(row['lsmc_guarantee_claims_aud']):,.2f} | "
            f"{float(row['lsmc_insurer_npv_aud']):,.2f} |"
        )
        if has_dynamic:
            base = base[:-1] + (
                f" {float(row['lsmc_minus_dynamic_insurer_npv_aud']):,.2f} |"
            )
        lines.append(base)
    lines.extend([
        "",
        "## Zerlegung relativ zum Vergleichs-Cap",
        "",
        (
            "`Total LSMC` = mechanischer Cap-Effekt unter Continue + "
            "Interaktion mit der optimalen Verhaltensoption."
        ),
        "",
        "| Cap | Mechanisch (Continue) | Verhaltensinteraktion | Total LSMC | Gap |",
        "|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        lines.append(
            f"| {float(row['cap_rate_percent']):.2f}% | "
            f"{float(row['mechanical_continue_change_vs_baseline_aud']):,.2f} | "
            f"{float(row['behaviour_interaction_vs_baseline_aud']):,.2f} | "
            f"{float(row['total_lsmc_change_vs_baseline_aud']):,.2f} | "
            f"{float(row['cap_effect_decomposition_gap_aud']):.3e} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_plot(path: Path, rows: list[dict[str, object]]) -> Optional[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    caps = np.asarray([float(row["cap_rate_percent"]) for row in rows])
    exercise = 100.0 * np.asarray(
        [float(row["lsmc_exercise_rate"]) for row in rows])
    fig, axes = plt.subplots(3, 1, figsize=(10.5, 12.5), sharex=True)
    axes[0].plot(caps, exercise, marker="o", color="#9b2226")
    axes[0].set_ylabel("LSMC Exercise rate (%)")
    axes[0].set_title("Optimal Full-Withdrawal behaviour")
    axes[0].grid(alpha=0.25)
    ph_series = [("continue", "#0a9396"), ("lsmc", "#005f73")]
    if "dynamic_policyholder_benefits_aud" in rows[0]:
        ph_series.insert(0, ("dynamic", "#6c757d"))
    for label, colour in ph_series:
        axes[1].plot(
            caps,
            [float(row[f"{label}_policyholder_benefits_aud"]) for row in rows],
            marker="o", label=label.title(), color=colour,
        )
    axes[1].set_ylabel("PV policyholder benefits (AUD)")
    axes[1].legend()
    axes[1].grid(alpha=0.25)
    npv_series = [("lsmc", "#bb3e03")]
    if "dynamic_insurer_npv_aud" in rows[0]:
        npv_series.insert(0, ("dynamic", "#6c757d"))
    for label, colour in npv_series:
        axes[2].plot(
            caps,
            [float(row[f"{label}_insurer_npv_aud"]) for row in rows],
            marker="o", label=label.title(), color=colour,
        )
    axes[2].axhline(0.0, color="black", linewidth=0.8)
    axes[2].set_ylabel("Insurer NPV (AUD)")
    axes[2].set_xlabel("Crediting cap (%)")
    axes[2].legend()
    axes[2].grid(alpha=0.25)
    fig.suptitle("Crediting cap sensitivity of LSMC-optimal behaviour")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return str(matplotlib.__version__)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = args.output.expanduser().resolve()
    rates = sorted({_rate_key(rate) for rate in (*args.cap_rates, args.baseline_rate)})
    scenario_root = output / "scenarios"
    rows: list[dict[str, object]] = []
    for index, rate in enumerate(rates, start=1):
        scenario_output = scenario_root / _rate_directory_name(rate)
        required = (
            scenario_output / "portfolio_summary.csv",
            scenario_output / "run_manifest.json",
            scenario_output / "continue_benchmark" / "portfolio_summary.csv",
        )
        if not args.no_dynamic_benchmark:
            required = (*required,
                scenario_output / "dynamic_benchmark" / "portfolio_summary.csv")
        if not args.reuse_existing or not all(path.exists() for path in required):
            print(
                f"[{index}/{len(rates)}] Fit and evaluate cap {100 * rate:.2f}%",
                flush=True,
            )
            subprocess.run(
                _scenario_command(args, rate, scenario_output),
                check=True,
                cwd=str(SCRIPT_DIRECTORY.parent),
            )
        else:
            print(f"[{index}/{len(rates)}] Reuse cap {100 * rate:.2f}%", flush=True)
        rows.append(_scenario_result(
            rate,
            scenario_output,
            include_dynamic=not args.no_dynamic_benchmark,
        ))

    evaluation_fingerprints = {
        str(row["evaluation_scenario_fingerprint"]) for row in rows}
    training_fingerprints = {
        str(row["training_scenario_fingerprint"]) for row in rows}
    if len(evaluation_fingerprints) != 1 or len(training_fingerprints) != 1:
        raise ValueError("Cap scenarios do not use common market path sets.")
    if evaluation_fingerprints == training_fingerprints:
        raise ValueError("Training and evaluation fingerprints must differ.")
    _add_baseline_deltas(rows, args.baseline_rate)

    comparison_csv = output / "lsmc_cap_behaviour_comparison.csv"
    report_path = output / "lsmc_cap_behaviour_report.md"
    plot_path = output / "lsmc_cap_behaviour_comparison.png"
    manifest_path = output / "comparison_manifest.json"
    _write_csv(comparison_csv, rows)
    _write_report(report_path, rows)
    matplotlib_version = _write_plot(plot_path, rows)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "crediting_cap_impact_on_lsmc_optimal_behaviour",
        "contractual_base_cap_rate": DEFAULT_BASELINE_RATE,
        "comparison_baseline_rate": args.baseline_rate,
        "scenario_cap_rates": rates,
        "policy_refitted_for_every_cap": True,
        "dynamic_benchmark_included": not args.no_dynamic_benchmark,
        "common_evaluation_scenario_fingerprint": next(
            iter(evaluation_fingerprints)),
        "common_training_scenario_fingerprint": next(iter(training_fingerprints)),
        "training_and_evaluation_are_distinct": True,
        "settings": {
            "n_paths": args.n_paths,
            "seed": args.seed,
            "n_train": args.n_train,
            "train_seed": args.train_seed,
            "heston_substeps": args.heston_substeps,
            "lsmc_folds": args.lsmc_folds,
            "lsmc_ridge": args.lsmc_ridge,
            "exercise_buffer_rmse_multiplier": (
                args.exercise_buffer_rmse_multiplier),
        },
        "model_limitations": [
            "Every non-6% cap is a non-contractual design sensitivity.",
            "Optimal Full Withdrawal is a conservative annual-grid LSMC lower bound.",
            "The deterministic model-point Income Election remains unchanged.",
            "Partial withdrawal is dominated for this proportional non-APS design.",
            (
                "Exercise counts are unweighted model-point/path/decision-event "
                "diagnostics, not portfolio-weighted surrender rates."
            ),
            (
                "The aggregate output has no pathwise paired confidence interval; "
                "repeat independent training and evaluation seeds before making "
                "statistical-significance claims."
            ),
        ],
        "outputs": {
            "comparison_csv": str(comparison_csv),
            "report": str(report_path),
            "plot": str(plot_path) if matplotlib_version is not None else None,
            "scenario_root": str(scenario_root),
        },
        "matplotlib_version": matplotlib_version,
        "results": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True,
                  allow_nan=False, default=str)
        handle.write("\n")
    print(f"Comparison CSV: {comparison_csv}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
