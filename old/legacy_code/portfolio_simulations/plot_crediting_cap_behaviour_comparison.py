"""Create a transparent comparison of Behaviour and Crediting-Margin effects.

The script reads completed output directories from
``optimize_crediting_rate_lsmc.py``.  It does not rerun valuation and refuses
incomplete result sets.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

CODE_ROOT = Path(__file__).resolve().parents[1]
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from policy_engine.repository_paths import run_output_directory  # noqa: E402

ROOT = run_output_directory("legacy_crediting_cap_behaviour")


def _load(directory: Path) -> tuple[dict[str, object], list[dict[str, str]]]:
    with (directory / "optimization_summary.json").open(encoding="utf-8") as handle:
        summary = json.load(handle)
    if summary.get("status") != "completed":
        raise RuntimeError(f"Result is not completed: {directory}")
    with (directory / "fixed_cap_sanity_checks.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    return summary, rows


def _fixed(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        (
            row for row in rows
            if row["case"].startswith("fixed_cap_")
            and row["cap_percent"]
            and 0.25 <= float(row["cap_percent"]) <= 20.0
        ),
        key=lambda row: float(row["cap_percent"]),
    )


def _static_joint_weight(directory: Path) -> float:
    with (directory / "model_point_projection_treatments.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    return sum(
        float(row["contract_weight"])
        * float(row["spouse_survival_to_effective_income_election"])
        for row in rows
        if row["joint_branch_behaviour_regime"] == "static"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-margin", type=Path,
        default=ROOT / "competing_risk_base_with_margin_v2",
    )
    parser.add_argument(
        "--no-margin", type=Path,
        default=ROOT / "competing_risk_base_no_margin_v2",
    )
    parser.add_argument(
        "--high-behaviour", type=Path,
        default=ROOT / "competing_risk_high_with_margin_v2",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "competing_risk_behaviour_hedge_comparison.png",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    margin_summary, margin_rows = _load(args.with_margin.resolve())
    no_margin_summary, no_margin_rows = _load(args.no_margin.resolve())
    high_summary, high_rows = _load(args.high_behaviour.resolve())
    static_joint_weight = _static_joint_weight(args.with_margin.resolve())
    margin_fixed = _fixed(margin_rows)
    no_margin_fixed = _fixed(no_margin_rows)
    high_fixed = _fixed(high_rows)
    caps = np.asarray([float(row["cap_percent"]) for row in margin_fixed])
    if not np.allclose(
        caps, [float(row["cap_percent"]) for row in no_margin_fixed]
    ) or not np.allclose(
        caps, [float(row["cap_percent"]) for row in high_fixed]
    ):
        raise RuntimeError("Fixed-cap grids do not match.")

    csm_margin = np.asarray([
        float(row["estimated_new_business_csm_proxy_aud"])
        for row in margin_fixed
    ])
    csm_no_margin = np.asarray([
        float(row["estimated_new_business_csm_proxy_aud"])
        for row in no_margin_fixed
    ])
    lapse_base = 100.0 * np.asarray([
        float(row["expected_cumulative_full_surrender_probability"])
        for row in margin_fixed
    ])
    lapse_high = 100.0 * np.asarray([
        float(row["expected_cumulative_full_surrender_probability"])
        for row in high_fixed
    ])

    figure = plt.figure(figsize=(12.5, 10.0))
    grid = figure.add_gridspec(2, 2, height_ratios=(1.0, 0.9))
    csm_axis = figure.add_subplot(grid[0, 0])
    lapse_axis = figure.add_subplot(grid[0, 1])
    direct_axis = figure.add_subplot(grid[1, :])

    csm_axis.plot(caps, csm_margin, marker="o", label="mit Crediting-Margin")
    csm_axis.plot(caps, csm_no_margin, marker="o", label="ohne Crediting-Margin")
    csm_axis.axhline(0.0, color="black", linewidth=0.8)
    csm_axis.set_title("Die Margin dreht das fixe Cap-Optimum")
    csm_axis.set_xlabel("Fixer Cap (%)")
    csm_axis.set_ylabel("New-Business-CSM-Proxy (AUD)")
    csm_axis.grid(alpha=0.25)
    csm_axis.legend()

    lapse_axis.plot(caps, lapse_base, marker="o", label="Behaviour Base")
    lapse_axis.plot(caps, lapse_high, marker="o", label="Behaviour High")
    lapse_axis.set_title("Mehr Kundengutschrift senkt Full Surrender deutlich")
    lapse_axis.set_xlabel("Fixer Cap (%)")
    lapse_axis.set_ylabel("Kumulierte Full-Surrender-Wahrscheinlichkeit (%)")
    lapse_axis.grid(alpha=0.25)
    lapse_axis.legend()

    labels = (
        "Bester fixer Cap\n1–20 %, mit Margin",
        "Flexible Regel\nmit Margin",
        "Bester fixer Cap\n1–20 %, ohne Margin",
        "Flexible Regel\nohne Margin",
    )
    values = np.asarray([
        float(margin_summary["best_fixed_cap_requested_1_to_20_csm_aud"]),
        float(margin_summary["estimated_optimal_new_business_csm_proxy_aud"]),
        float(no_margin_summary["best_fixed_cap_requested_1_to_20_csm_aud"]),
        float(no_margin_summary["estimated_optimal_new_business_csm_proxy_aud"]),
    ])
    bars = direct_axis.bar(
        np.arange(4), values,
        color=("#2F6B9A", "#168A45", "#6B7C93", "#7A9E7E"),
    )
    direct_axis.set_xticks(np.arange(4), labels)
    direct_axis.set_ylabel("Direkt projizierter CSM-Proxy (AUD)")
    direct_axis.set_title(
        "Mit Margin schlägt 0,25 % die fixen 1–20 % – aber nicht die Minimumregel"
    )
    direct_axis.set_ylim(0.0, 1.15 * float(np.max(values)))
    direct_axis.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, values):
        direct_axis.annotate(
            f"AUD {value:,.0f}".replace(",", "."),
            (bar.get_x() + bar.get_width() / 2.0, value),
            xytext=(0, 5), textcoords="offset points", ha="center",
        )

    figure.suptitle(
        "Crediting-Cap: Behaviour- und Margin-Diagnose",
        fontsize=16,
    )
    figure.text(
        0.01, 0.01,
        "Alle CSM-Werte stammen aus direkten Monatsprojektionen. Growth Surrender "
        f"ist vertraglich verboten; {100.0 * static_joint_weight:.2f} % des "
        "Branch-Gewichts bleibt wegen der Joint-Life-Kohortenbegrenzung statisch. "
        "Die validierte flexible Regel fällt mit Margin auf 0,25 % und ohne Margin "
        "auf 20 % zurück; gegenüber der jeweils besten zulässigen Minimumregel ist "
        "der adaptive Zusatzwert daher null. Base/High sind unkalibrierte Proxys.",
        fontsize=8,
    )
    figure.tight_layout(rect=(0.0, 0.045, 1.0, 0.96))
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=170, bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    main()
