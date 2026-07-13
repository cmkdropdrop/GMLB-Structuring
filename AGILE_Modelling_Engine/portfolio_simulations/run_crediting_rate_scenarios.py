"""Compare portfolio profitability across constant crediting-cap scenarios.

The script calls ``run_portfolio_valuation.py`` once for every requested
Maximum Return.  All runs use the same risk-neutral model settings and seed,
so the valuation comparisons use common random numbers.  A scenario rate is a
non-contractual design/sensitivity override; the generic product's contractual
base Maximum Return remains 6%.

The comparison is market-consistent and before Risk Margin.  It does not turn
the portfolio runner into a Real-World forecast or a full APRA/IFRS
profitability model.
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

if __package__:
    from ._run_logging import log_to_console
else:
    from _run_logging import log_to_console


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
PORTFOLIO_RUNNER = SCRIPT_DIRECTORY / "run_portfolio_valuation.py"
DEFAULT_OUTPUT_DIRECTORY = SCRIPT_DIRECTORY / "output" / "crediting_rate_scenarios"
DEFAULT_CREDITING_RATES = (0.04, 0.06, 0.12, 0.20)
DEFAULT_BASELINE_RATE = 0.06
HEDGE_CAP_LEG_MODES = ("sold", "not_sold")
DEFAULT_HEDGE_CAP_LEG_MODE = "sold"


def _parse_rate(text: str) -> float:
    """Accept decimals (0.06), percentages (6%) or bare percentage points (6)."""
    raw = str(text).strip()
    is_percent = raw.endswith("%")
    if is_percent:
        raw = raw[:-1].strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid crediting rate: {text!r}") from exc
    if is_percent or value >= 1.0:
        value /= 100.0
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError(
            "crediting rates must be between 0% and 100%"
        )
    return value


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--crediting-rates",
        nargs="+",
        type=_parse_rate,
        default=list(DEFAULT_CREDITING_RATES),
        metavar="RATE",
        help="constant Maximum Returns; accepts 0.06, 6%% or bare 6",
    )
    parser.add_argument(
        "--baseline-rate",
        type=_parse_rate,
        default=DEFAULT_BASELINE_RATE,
        help="comparison baseline; it is added to the run list if necessary",
    )
    parser.add_argument("--n-paths", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument(
        "--hedge-cap-leg-mode",
        choices=HEDGE_CAP_LEG_MODES,
        default=DEFAULT_HEDGE_CAP_LEG_MODE,
        help=(
            "sold uses the standard capped call spread; not_sold buys the "
            "uncapped call and retains the hedge payoff above the customer cap"
        ),
    )
    parser.add_argument("--portfolio-contract-count", type=float, default=None)
    parser.add_argument("--profitability-materiality-bp", type=float, default=1.0)
    parser.add_argument("--model-points", type=Path, default=None)
    parser.add_argument("--cost-assumptions", type=Path, default=None)
    parser.add_argument("--cost-assumption-set", default=None)
    parser.add_argument("--dynamic-behaviour", type=Path, default=None)
    parser.add_argument("--behaviour-assumption-set", default=None)
    parser.add_argument("--zero-curve", type=Path, default=None)
    parser.add_argument("--model-parameters", type=Path, default=None)
    parser.add_argument(
        "--scenario-plots",
        action="store_true",
        help="also retain the standard plots inside every scenario directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="root directory for scenario runs and comparison outputs",
    )
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python executable used to call run_portfolio_valuation.py",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    args = parser.parse_args(argv)

    if args.n_paths <= 0:
        parser.error("--n-paths must be positive")
    if args.seed < 0:
        parser.error("--seed must be non-negative")
    if args.heston_substeps <= 0:
        parser.error("--heston-substeps must be positive")
    if args.portfolio_contract_count is not None and (
        not math.isfinite(args.portfolio_contract_count)
        or args.portfolio_contract_count <= 0.0
    ):
        parser.error("--portfolio-contract-count must be positive and finite")
    if (
        not math.isfinite(args.profitability_materiality_bp)
        or args.profitability_materiality_bp < 0.0
    ):
        parser.error("--profitability-materiality-bp must be finite and non-negative")
    return args


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _as_float(value: object, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Missing or invalid numeric result field: {field}") from exc
    if not math.isfinite(number):
        raise ValueError(f"Non-finite numeric result field: {field}")
    return number


def _read_single_csv_row(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one row in {path}, found {len(rows)}")
    return dict(rows[0])


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty comparison CSV.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _rate_key(rate: float) -> float:
    return round(float(rate), 12)


def _rate_directory_name(rate: float) -> str:
    percentage = f"{100.0 * rate:.6f}".rstrip("0").rstrip(".")
    return f"crediting_rate_{percentage.replace('.', 'p')}pct"


def _optional_argument(command: list[str], flag: str, value: object) -> None:
    if value is not None:
        command.extend((flag, str(value)))


def _portfolio_command(
    args: argparse.Namespace,
    rate: float,
    scenario_output: Path,
) -> list[str]:
    command = [
        str(args.python_executable),
        str(PORTFOLIO_RUNNER),
        "--crediting-cap-rate",
        f"{rate:.12g}",
        "--n-paths",
        str(args.n_paths),
        "--seed",
        str(args.seed),
        "--heston-substeps",
        str(args.heston_substeps),
        "--hedge-cap-leg-mode",
        args.hedge_cap_leg_mode,
        "--profitability-materiality-bp",
        str(args.profitability_materiality_bp),
        "--log-level",
        args.log_level,
        "--output",
        str(scenario_output),
    ]
    if not args.scenario_plots:
        command.append("--no-plots")
    _optional_argument(command, "--portfolio-contract-count", args.portfolio_contract_count)
    _optional_argument(command, "--model-points", args.model_points)
    _optional_argument(command, "--cost-assumptions", args.cost_assumptions)
    _optional_argument(command, "--cost-assumption-set", args.cost_assumption_set)
    _optional_argument(command, "--dynamic-behaviour", args.dynamic_behaviour)
    _optional_argument(
        command, "--behaviour-assumption-set", args.behaviour_assumption_set
    )
    _optional_argument(command, "--zero-curve", args.zero_curve)
    _optional_argument(command, "--model-parameters", args.model_parameters)
    return command


def _scenario_result(
    requested_rate: float,
    scenario_output: Path,
    expected_hedge_cap_leg_mode: str = DEFAULT_HEDGE_CAP_LEG_MODE,
) -> dict[str, object]:
    summary_path = scenario_output / "portfolio_summary.csv"
    manifest_path = scenario_output / "run_manifest.json"
    summary = _read_single_csv_row(summary_path)
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    actual_rate = _as_float(summary.get("crediting_cap_rate"), field="crediting_cap_rate")
    if not math.isclose(actual_rate, requested_rate, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError(
            f"Scenario rate mismatch in {summary_path}: "
            f"requested {requested_rate}, reported {actual_rate}"
        )

    summary_hedge_cap_leg_mode = str(summary.get("hedge_cap_leg_mode", ""))
    if summary_hedge_cap_leg_mode != expected_hedge_cap_leg_mode:
        raise ValueError(
            f"Hedge cap-leg mode mismatch in {summary_path}: requested "
            f"{expected_hedge_cap_leg_mode!r}, reported "
            f"{summary_hedge_cap_leg_mode!r}."
        )
    manifest_modes: list[str] = []
    for section_name in ("method", "valuation_settings"):
        section = manifest.get(section_name)
        if not isinstance(section, Mapping):
            raise ValueError(
                f"Missing {section_name!r} provenance section in {manifest_path}."
            )
        mode = section.get("hedge_cap_leg_mode")
        if mode is None:
            raise ValueError(
                f"Missing hedge_cap_leg_mode in {section_name!r} provenance "
                f"section of {manifest_path}."
            )
        manifest_modes.append(str(mode))
    if set(manifest_modes) != {expected_hedge_cap_leg_mode}:
        raise ValueError(
            f"Hedge cap-leg mode provenance mismatch in {manifest_path}: "
            f"requested {expected_hedge_cap_leg_mode!r}, reported "
            f"{manifest_modes!r}."
        )

    absolute = _as_bool(summary.get("absolute_portfolio_values_available"))
    prefix = "portfolio_total_" if absolute else "normalised_average_"
    basis = "absolute_portfolio" if absolute else "normalised_average_contract"

    def monetary(metric: str) -> float:
        field = f"{prefix}{metric}"
        return _as_float(summary.get(field), field=field)

    administrative_expenses = monetary("pv_expenses_aud")
    hedge_costs = monetary("pv_hedge_costs_aud")
    hedge_option_fair_value_costs = monetary(
        "pv_hedge_option_fair_value_costs_aud"
    )
    hedge_option_markup_costs = monetary("pv_hedge_option_markup_costs_aud")
    hedge_management_fee_costs = monetary("pv_hedge_management_fee_costs_aud")
    hedge_execution_costs = monetary("pv_hedge_execution_costs_aud")
    hedge_component_sum = (
        hedge_option_fair_value_costs
        + hedge_option_markup_costs
        + hedge_management_fee_costs
        + hedge_execution_costs
    )
    if not math.isclose(
        hedge_costs,
        hedge_component_sum,
        rel_tol=1.0e-10,
        abs_tol=max(1.0e-8, 1.0e-10 * abs(hedge_costs)),
    ):
        raise ValueError(
            f"Hedge-cost component reconciliation failed in {summary_path}: "
            f"aggregate={hedge_costs}, components={hedge_component_sum}."
        )
    crediting_margin = monetary("pv_crediting_margin_aud")
    money_market_income = monetary("pv_money_market_income_aud")
    hedge_gain = monetary("pv_hedge_gain_aud")
    if not math.isclose(
        crediting_margin,
        money_market_income + hedge_gain,
        rel_tol=1.0e-10,
        abs_tol=max(1.0e-8, 1.0e-10 * abs(crediting_margin)),
    ):
        raise ValueError(
            f"Crediting-margin component reconciliation failed in "
            f"{summary_path}: aggregate={crediting_margin}, "
            f"components={money_market_income + hedge_gain}."
        )
    if (
        expected_hedge_cap_leg_mode == "sold"
        and not math.isclose(hedge_gain, 0.0, rel_tol=0.0, abs_tol=1.0e-8)
    ):
        raise ValueError(
            f"Sold cap-leg mode reports an above-cap hedge gain in "
            f"{summary_path}."
        )
    insurer_npv = monetary("insurer_net_present_value_before_risk_margin_aud")
    premium = monetary("premium_aud")
    return {
        "crediting_rate": actual_rate,
        "crediting_rate_percent": 100.0 * actual_rate,
        "hedge_cap_leg_mode": summary_hedge_cap_leg_mode,
        "valuation_basis": basis,
        "premium_aud": premium,
        "insurer_npv_before_risk_margin_aud": insurer_npv,
        "new_business_margin_before_risk_margin": _as_float(
            summary.get("new_business_margin_before_risk_margin"),
            field="new_business_margin_before_risk_margin",
        ),
        "profitability_classification": summary.get("profitability_classification"),
        "bel_nonunit_aud": monetary("bel_nonunit_aud"),
        "bel_total_aud": monetary("bel_total_aud"),
        "pv_guarantee_claims_aud": monetary("pv_guarantee_claims_aud"),
        "pv_future_fees_aud": monetary("pv_future_fees_aud"),
        "pv_crediting_margin_aud": crediting_margin,
        "pv_money_market_income_aud": money_market_income,
        "pv_hedge_gain_aud": hedge_gain,
        "pv_hedge_option_fair_value_costs_aud": hedge_option_fair_value_costs,
        "pv_hedge_option_markup_costs_aud": hedge_option_markup_costs,
        "pv_hedge_management_fee_costs_aud": hedge_management_fee_costs,
        "pv_hedge_execution_costs_aud": hedge_execution_costs,
        "pv_hedge_costs_aud": hedge_costs,
        "pv_total_expenses_aud": administrative_expenses + hedge_costs,
        "pv_administrative_expenses_aud_audit": administrative_expenses,
        "pv_hedge_costs_aud_audit": hedge_costs,
        "guarantee_value_aud": monetary("guarantee_value_aud"),
        "scenario_fingerprint": manifest["portfolio"]["scenario_fingerprint"],
        "scenario_output_directory": str(scenario_output),
        "portfolio_summary_csv": str(summary_path),
    }


def _add_baseline_differences(
    rows: list[dict[str, object]],
    baseline_rate: float,
) -> None:
    baseline = next(
        row for row in rows
        if _rate_key(float(row["crediting_rate"])) == _rate_key(baseline_rate)
    )
    baseline_npv = float(baseline["insurer_npv_before_risk_margin_aud"])
    baseline_margin = float(baseline["new_business_margin_before_risk_margin"])
    for row in rows:
        row["baseline_crediting_rate"] = baseline_rate
        row["delta_insurer_npv_aud_vs_baseline"] = (
            float(row["insurer_npv_before_risk_margin_aud"]) - baseline_npv
        )
        row["delta_new_business_margin_percentage_points_vs_baseline"] = 100.0 * (
            float(row["new_business_margin_before_risk_margin"]) - baseline_margin
        )


def _write_report(
    path: Path,
    rows: list[dict[str, object]],
    baseline_rate: float,
    hedge_cap_leg_mode: str = DEFAULT_HEDGE_CAP_LEG_MODE,
) -> None:
    basis = str(rows[0]["valuation_basis"])
    lines = [
        "# Profitabilitätsvergleich der Crediting-Rate-Szenarien",
        "",
        (
            "Die Raten sind nichtvertragliche konstante Maximum-Return-Szenarien. "
            "Der vertragliche Basissatz des generischen Produkts bleibt 6 %."
        ),
        "",
        f"Bewertungsbasis: `{basis}`. Vergleichsbasis: {100.0 * baseline_rate:.2f} %.",
        f"Hedge-Cap-Leg-Modus: `{hedge_cap_leg_mode}`.",
        "",
        "| Crediting Rate | Insurer NPV vor RM | New Business Margin vor RM | Delta NPV zur Basis | Klassifikation |",
        "|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {rate:.2f} % | {npv:,.2f} AUD | {margin:.3f} % | "
            "{delta:,.2f} AUD | {classification} |".format(
                rate=float(row["crediting_rate_percent"]),
                npv=float(row["insurer_npv_before_risk_margin_aud"]),
                margin=100.0 * float(row["new_business_margin_before_risk_margin"]),
                delta=float(row["delta_insurer_npv_aud_vs_baseline"]),
                classification=row["profitability_classification"],
            )
        )
    lines.extend([
        "",
        "## Hedge- und Money-Market-Audit",
        "",
        (
            "| Crediting Rate | Money-Market-Ertrag | Hedge-Gewinn oberhalb Cap | "
            "Fairer Optionswert | Optionsmarge | Management Fee | "
            "Execution-Kosten | Hedgekosten gesamt |"
        ),
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        lines.append(
            "| {rate:.2f} % | {money_market:,.2f} | {hedge_gain:,.2f} | "
            "{fair_value:,.2f} | {markup:,.2f} | {management_fee:,.2f} | "
            "{execution:,.2f} | {hedge_total:,.2f} |".format(
                rate=float(row["crediting_rate_percent"]),
                money_market=float(row["pv_money_market_income_aud"]),
                hedge_gain=float(row["pv_hedge_gain_aud"]),
                fair_value=float(row["pv_hedge_option_fair_value_costs_aud"]),
                markup=float(row["pv_hedge_option_markup_costs_aud"]),
                management_fee=float(row["pv_hedge_management_fee_costs_aud"]),
                execution=float(row["pv_hedge_execution_costs_aud"]),
                hedge_total=float(row["pv_hedge_costs_aud"]),
            )
        )
    lines.extend([
        "",
        (
            "`pv_total_expenses_aud` umfasst Verwaltungskosten sowie den fairen "
            "Optionswert, die Optionsmarge, die Management Fee und etwaige "
            "Execution-Kosten. Die Einzelkomponenten und der Money-Market-Ertrag "
            "bleiben in der Vergleichs-CSV separat auditierbar."
        ),
        "",
        (
            "Alle Szenarien verwenden denselben Seed und dieselben "
            "Heston-Hull-White-Einstellungen. Die identischen "
            "Szenario-Fingerprints bestätigen die Common-Random-Number-Basis."
        ),
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_comparison_plot(
    path: Path,
    rows: list[dict[str, object]],
    baseline_rate: float,
) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    rates = [float(row["crediting_rate_percent"]) for row in rows]
    npvs = [float(row["insurer_npv_before_risk_margin_aud"]) for row in rows]
    margins = [
        100.0 * float(row["new_business_margin_before_risk_margin"])
        for row in rows
    ]
    baseline_percent = 100.0 * baseline_rate

    fig, axes = plt.subplots(2, 1, figsize=(11.5, 8.5), sharex=True)
    axes[0].plot(rates, npvs, marker="o", color="#145DA0", linewidth=2.0)
    axes[0].axhline(0.0, color="#1F2937", linewidth=0.8)
    axes[0].axvline(baseline_percent, color="#6B7280", linestyle="--")
    axes[0].set_ylabel("Insurer NPV vor Risk Margin (AUD)")
    axes[0].set_title("Profitabilität nach Crediting Rate", loc="left")
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].plot(rates, margins, marker="o", color="#168A45", linewidth=2.0)
    axes[1].axhline(0.0, color="#1F2937", linewidth=0.8)
    axes[1].axvline(baseline_percent, color="#6B7280", linestyle="--")
    axes[1].set_xlabel("Konstante Crediting Rate / Maximum Return (%)")
    axes[1].set_ylabel("New Business Margin vor Risk Margin (%)")
    axes[1].grid(axis="y", alpha=0.25)

    fig.text(
        0.01,
        0.01,
        "Nichtvertragliche Design-/Sensitivitätsszenarien; Heston-Hull-White unter Q; Common Random Numbers.",
        fontsize=8,
        color="#5B6573",
    )
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    rates = sorted({
        _rate_key(rate)
        for rate in [*args.crediting_rates, args.baseline_rate]
    })
    log_to_console(
        "Crediting-Rate-Szenarien: "
        + ", ".join(f"{100.0 * rate:.2f}%" for rate in rates)
    )
    log_to_console(
        "Common Random Numbers: "
        f"n_paths={args.n_paths}, seed={args.seed}, "
        f"heston_substeps={args.heston_substeps}"
    )

    rows: list[dict[str, object]] = []
    commands: list[list[str]] = []
    for index, rate in enumerate(rates, start=1):
        scenario_output = output / "scenarios" / _rate_directory_name(rate)
        command = _portfolio_command(args, rate, scenario_output)
        commands.append(command)
        log_to_console(
            f"[{index}/{len(rates)}] Portfolio valuation for "
            f"Crediting Rate {100.0 * rate:.2f}%"
        )
        completed = subprocess.run(command, cwd=str(SCRIPT_DIRECTORY.parent))
        if completed.returncode != 0:
            raise RuntimeError(
                f"Portfolio valuation failed for {100.0 * rate:.4f}% "
                f"with exit code {completed.returncode}."
            )
        rows.append(
            _scenario_result(rate, scenario_output, args.hedge_cap_leg_mode)
        )

    bases = {str(row["valuation_basis"]) for row in rows}
    if len(bases) != 1:
        raise ValueError(f"Scenario runs returned inconsistent valuation bases: {bases}")
    fingerprints = {str(row["scenario_fingerprint"]) for row in rows}
    if len(fingerprints) != 1:
        raise ValueError(
            "Scenario fingerprints differ; the comparison does not have a "
            "valid common-random-number basis."
        )

    _add_baseline_differences(rows, args.baseline_rate)
    comparison_csv = output / "crediting_rate_profitability_comparison.csv"
    report_path = output / "crediting_rate_profitability_report.md"
    plot_path = output / "crediting_rate_profitability_comparison.png"
    manifest_path = output / "comparison_manifest.json"
    _write_csv(comparison_csv, rows)
    _write_report(
        report_path,
        rows,
        args.baseline_rate,
        args.hedge_cap_leg_mode,
    )
    plot_created = _write_comparison_plot(plot_path, rows, args.baseline_rate)

    manifest: Mapping[str, object] = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "market_consistent_crediting_rate_profitability_comparison",
        "contractual_crediting_cap_rate": DEFAULT_BASELINE_RATE,
        "baseline_scenario_rate": args.baseline_rate,
        "scenario_rates": rates,
        "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
        "hedge_cap_leg_interpretation": (
            "short_cap_call_sold"
            if args.hedge_cap_leg_mode == "sold"
            else "cap_call_not_sold_and_excess_payoff_retained"
        ),
        "common_random_numbers": {
            "n_paths": args.n_paths,
            "seed": args.seed,
            "heston_substeps": args.heston_substeps,
            "scenario_fingerprint": next(iter(fingerprints)),
        },
        "portfolio_runner": str(PORTFOLIO_RUNNER),
        "commands": commands,
        "outputs": {
            "comparison_csv": str(comparison_csv),
            "comparison_report": str(report_path),
            "comparison_plot": str(plot_path) if plot_created else None,
        },
        "limitations": [
            "Non-contractual constant Maximum-Return scenarios.",
            "Market-consistent Heston-Hull-White valuation under Q.",
            "Profitability is before Risk Margin and is not a full APRA/IFRS view.",
            "The insurer backing account earns the stochastic AUD overnight money-market return.",
            "Hedge costs include fair option value, purchase markup, management-fee drag and any execution proxy.",
        ],
    }
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")

    log_to_console(f"Comparison CSV: {comparison_csv}")
    log_to_console(f"Comparison report: {report_path}")
    if plot_created:
        log_to_console(f"Comparison plot: {plot_path}")
    else:
        log_to_console(
            "Comparison plot skipped because Matplotlib is unavailable.",
            level="WARNING",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
