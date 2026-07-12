"""Run the generic policyholder-portfolio valuation.

Every repository model point is valued as a separate representative contract
under one shared risk-neutral Heston-Hull-White scenario set.  The runner then
aggregates the scalar model-point results using ``contract_weight``.  Absolute
portfolio totals are produced only when an explicit total contract count is
provided; otherwise all aggregate monetary values are labelled as normalised
weighted-average values per representative contract.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from agile_engine import (  # noqa: E402
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DEFAULT_MODEL_PARAMETERS_PATH,
    DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
    FeeSpec,
    IndexLinkedLifetimeIncomeProduct,
    MortalityTable,
    ProjectionConfig,
    ReferenceFundSpec,
    ValuationSettings,
    __version__ as ENGINE_VERSION,
    load_cost_assumptions,
    load_dynamic_behaviour_assumptions,
    load_market_assumptions,
    load_policyholder_model_points,
    value_policyholder_portfolio,
)


DEFAULT_OUTPUT_DIRECTORY = (
    Path(__file__).resolve().parent / "output" / "portfolio_valuation"
)
LOGGER_NAME = "agile_engine.portfolio_runner"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _as_float(value: object) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _aud_axis(value: float, _position: object = None) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}bn"
    if absolute >= 1_000_000:
        return f"{value / 1_000_000:.1f}m"
    if absolute >= 1_000:
        return f"{value / 1_000:.0f}k"
    return f"{value:.0f}"


def _summary_value(
    summary: Mapping[str, object],
    metric: str,
    *,
    absolute: bool,
) -> Optional[float]:
    prefix = "portfolio_total_" if absolute else "normalised_average_"
    return _as_float(summary.get(f"{prefix}{metric}"))


def _detail_text(detail: object) -> str:
    if detail is None or detail == "":
        return ""
    if isinstance(detail, Mapping):
        return json.dumps(detail, sort_keys=True, default=str)
    return str(detail)


def _make_progress_callback(logger: logging.Logger):
    """Translate Core ``PortfolioProgress`` events into concise INFO logs."""

    def report(event: object) -> None:
        raw_stage = getattr(event, "stage", "portfolio_progress")
        stage = getattr(raw_stage, "value", raw_stage)
        completed = getattr(event, "completed", None)
        total = getattr(event, "total", None)
        model_point_id = getattr(event, "model_point_id", None)
        detail = _detail_text(getattr(event, "detail", None))

        parts = [str(stage)]
        if completed is not None and total is not None:
            parts.append(f"{completed}/{total}")
        if model_point_id:
            parts.append(str(model_point_id))
        if detail:
            parts.append(detail)
        message = "Portfoliofortschritt | %s"
        payload = " | ".join(parts)
        stage_text = str(stage)
        verbose_solver_event = (
            "evaluation" in stage_text
            or (
                stage_text.startswith("portfolio_")
                and "model_point_completed" in stage_text
            )
        )
        if verbose_solver_event:
            logger.debug(message, payload)
        else:
            logger.info(message, payload)

    return report


def _configure_logging(
    output: Path,
    requested_log_file: Optional[Path],
    level_name: str,
) -> tuple[logging.Logger, Path]:
    log_path = (
        output / "portfolio_valuation.log"
        if requested_log_file is None
        else requested_log_file.expanduser().resolve()
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, level_name.upper()))
    logger.propagate = False
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger, log_path


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-points",
        type=Path,
        default=DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
        help="policyholder model-point CSV",
    )
    parser.add_argument(
        "--cost-assumptions",
        type=Path,
        default=DEFAULT_COST_ASSUMPTIONS_PATH,
        help="repository cost_assumptions.csv",
    )
    parser.add_argument(
        "--cost-assumption-set",
        default=None,
        help="optional assumption_set_id in the cost CSV",
    )
    parser.add_argument(
        "--dynamic-behaviour",
        type=Path,
        default=DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
        help="repository input_dynamic_behaviour directory",
    )
    parser.add_argument(
        "--behaviour-assumption-set",
        default=None,
        help="optional assumption_set_id in the behaviour CSVs",
    )
    parser.add_argument(
        "--zero-curve",
        type=Path,
        default=DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
        help="repository Australian zero-curve CSV",
    )
    parser.add_argument(
        "--model-parameters",
        type=Path,
        default=DEFAULT_MODEL_PARAMETERS_PATH,
        help="repository market-model-parameter CSV",
    )
    parser.add_argument("--n-paths", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument(
        "--crediting-cap-rate",
        type=float,
        default=None,
        help=(
            "optional non-contractual constant Maximum-Return scenario as a "
            "decimal (for example 0.08 for 8%%); the contractual base remains 6%%"
        ),
    )
    parser.add_argument(
        "--portfolio-contract-count",
        type=float,
        default=None,
        help=(
            "total number of represented contracts; if omitted, monetary "
            "aggregates remain normalised weighted averages per contract"
        ),
    )
    parser.add_argument(
        "--fair-lip",
        action="store_true",
        help="solve guarantee-neutral Lifetime Income Premium per model point",
    )
    parser.add_argument(
        "--commercial-break-even-lip",
        action="store_true",
        help="solve insurer-NPV-neutral LIP per model point",
    )
    parser.add_argument(
        "--portfolio-fair-lip",
        action="store_true",
        help="solve one guarantee-neutral LIP against the aggregated portfolio",
    )
    parser.add_argument(
        "--portfolio-commercial-break-even-lip",
        action="store_true",
        help="solve one insurer-NPV-neutral LIP against the aggregated portfolio",
    )
    parser.add_argument("--fair-fee-lower", type=float, default=0.0)
    parser.add_argument("--fair-fee-upper", type=float, default=0.05)
    parser.add_argument("--fair-fee-maximum-upper", type=float, default=0.25)
    parser.add_argument("--fair-fee-tolerance", type=float, default=1.0e-6)
    parser.add_argument(
        "--profitability-materiality-bp",
        type=float,
        default=1.0,
        help=(
            "materiality threshold in basis points of premium for classifying "
            "positive, negative or approximately break-even model-point value"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="output directory for CSV, JSON, log and figure results",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="do not create the default headless matplotlib figures",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
        help="console and file logging level",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help=(
            "optional log-file path; default is "
            "<output>/portfolio_valuation.log"
        ),
    )
    args = parser.parse_args(argv)

    if args.n_paths <= 0:
        parser.error("--n-paths must be positive")
    if args.seed < 0:
        parser.error("--seed must be non-negative")
    if args.heston_substeps <= 0:
        parser.error("--heston-substeps must be positive")
    if args.crediting_cap_rate is not None and (
        not math.isfinite(args.crediting_cap_rate)
        or not 0.0 <= args.crediting_cap_rate <= 1.0
    ):
        parser.error("--crediting-cap-rate must be between 0 and 1")
    if (
        args.portfolio_contract_count is not None
        and (
            not math.isfinite(args.portfolio_contract_count)
            or args.portfolio_contract_count <= 0.0
        )
    ):
        parser.error("--portfolio-contract-count must be positive and finite")
    fair_controls = (
        args.fair_fee_lower,
        args.fair_fee_upper,
        args.fair_fee_maximum_upper,
        args.fair_fee_tolerance,
    )
    if (
        not all(math.isfinite(value) for value in fair_controls)
        or args.fair_fee_lower < 0.0
        or args.fair_fee_upper <= args.fair_fee_lower
        or args.fair_fee_maximum_upper < args.fair_fee_upper
        or args.fair_fee_tolerance <= 0.0
    ):
        parser.error("invalid fair-fee bracket or tolerance")
    if (
        not math.isfinite(args.profitability_materiality_bp)
        or args.profitability_materiality_bp < 0.0
    ):
        parser.error("--profitability-materiality-bp must be finite and non-negative")
    return args


def _build_aggregation_reconciliation(
    summary: Mapping[str, object],
    model_point_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    reconciliation: list[dict[str, object]] = []
    basis_definitions = (
        ("normalised_weighted_average", "normalised_average_", "normalised_contribution_"),
        ("absolute_portfolio", "portfolio_total_", "portfolio_contribution_"),
    )
    for basis, summary_prefix, contribution_prefix in basis_definitions:
        metrics = sorted(
            key[len(summary_prefix):]
            for key in summary
            if key.startswith(summary_prefix)
        )
        for metric in metrics:
            contribution_column = f"{contribution_prefix}{metric}"
            values = [
                _as_float(row.get(contribution_column))
                for row in model_point_rows
            ]
            if not values or any(value is None for value in values):
                continue
            reported = _as_float(summary.get(f"{summary_prefix}{metric}"))
            if reported is None:
                continue
            summed = math.fsum(value for value in values if value is not None)
            difference = summed - reported
            relative = (
                difference / reported
                if not math.isclose(reported, 0.0, abs_tol=1.0e-16)
                else difference
            )
            tolerance = max(1.0e-8, abs(reported) * 1.0e-12)
            reconciliation.append({
                "aggregation_basis": basis,
                "metric": metric,
                "model_point_contribution_column": contribution_column,
                "portfolio_summary_column": f"{summary_prefix}{metric}",
                "model_point_contribution_sum": summed,
                "portfolio_reported_value": reported,
                "absolute_difference": difference,
                "relative_difference": relative,
                "within_numerical_tolerance": abs(difference) <= tolerance,
            })
    total_contract_count = _as_float(summary.get("portfolio_contract_count"))
    if total_contract_count is not None and total_contract_count > 0.0:
        normalised_metrics = sorted(
            key[len("normalised_average_"):]
            for key in summary
            if key.startswith("normalised_average_")
        )
        for metric in normalised_metrics:
            normalised = _as_float(summary.get(f"normalised_average_{metric}"))
            absolute_total = _as_float(summary.get(f"portfolio_total_{metric}"))
            if normalised is None or absolute_total is None:
                continue
            absolute_per_contract = absolute_total / total_contract_count
            difference = absolute_per_contract - normalised
            relative = (
                difference / normalised
                if not math.isclose(normalised, 0.0, abs_tol=1.0e-16)
                else difference
            )
            tolerance = max(1.0e-8, abs(normalised) * 1.0e-12)
            reconciliation.append({
                "aggregation_basis": "absolute_vs_normalised_average",
                "metric": metric,
                "model_point_contribution_column": None,
                "portfolio_summary_column": f"portfolio_total_{metric}",
                "model_point_contribution_sum": absolute_total,
                "portfolio_reported_value": normalised,
                "absolute_portfolio_total": absolute_total,
                "normalised_reported_value": normalised,
                "absolute_total_contract_count": total_contract_count,
                "absolute_value_per_contract": absolute_per_contract,
                "absolute_difference": difference,
                "relative_difference": relative,
                "within_numerical_tolerance": abs(difference) <= tolerance,
            })
    if not reconciliation:
        raise ValueError(
            "No portfolio aggregation reconciliation could be built. Expected "
            "normalised_average_/normalised_contribution_ result columns were "
            "not found."
        )
    return reconciliation


def _build_fair_fee_rows(
    model_point_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not model_point_rows:
        return []
    available: list[str] = []
    for row in model_point_rows:
        for key in row:
            if key not in available:
                available.append(key)

    identity_columns = [
        "model_point_id",
        "source_row_number",
        "contract_weight",
        "represented_contract_count",
        "primary_age",
        "primary_sex",
        "spouse",
        "secondary_age",
        "secondary_sex",
        "income_start_year",
        "effective_income_start_year",
        "behaviour_treatment",
        "per_contract_spouse_survival_to_income_election",
        "charged_lip_rate",
        "profitability_classification",
        "new_business_margin_before_risk_margin",
        "per_contract_new_business_margin_before_risk_margin",
        "per_contract_profitability_materiality_bp",
        "per_contract_profitability_materiality_aud",
        "per_contract_guarantee_value_aud",
        "per_contract_insurer_net_present_value_before_risk_margin_aud",
        "normalised_contribution_insurer_net_present_value_before_risk_margin_aud",
        "portfolio_contribution_insurer_net_present_value_before_risk_margin_aud",
    ]
    diagnostic_columns = [
        key for key in available
        if key.startswith("fair_lip_")
        or key.startswith("commercial_break_even_lip_")
        or key.startswith("charged_minus_fair_lip_")
        or key.startswith("charged_minus_commercial_break_even_lip_")
    ]
    if not diagnostic_columns:
        return []
    selected = [
        key for key in identity_columns if key in available
    ] + [key for key in diagnostic_columns if key not in identity_columns]
    return [{key: row.get(key) for key in selected} for row in model_point_rows]


def _plot_component_decomposition(
    plt: Any,
    FuncFormatter: Any,
    summary: Mapping[str, object],
    output: Path,
    *,
    absolute: bool,
    footer: str,
) -> Optional[Path]:
    definitions = (
        ("Guarantee Claims", ("pv_guarantee_claims_aud",), 1.0),
        ("Expenses", ("pv_expenses_aud", "pv_hedge_costs_aud"), 1.0),
        ("Product Fees", ("pv_product_fees_aud",), -1.0),
        ("LIP", ("pv_lifetime_income_premiums_aud",), -1.0),
        ("Crediting Margin", ("pv_crediting_margin_aud",), -1.0),
        ("MVA retained", ("pv_mva_retained_aud",), -1.0),
    )
    labels: list[str] = []
    values: list[float] = []
    for label, metrics, sign in definitions:
        components = [
            _summary_value(summary, metric, absolute=absolute)
            for metric in metrics
        ]
        if all(component is not None for component in components):
            value = sum(float(component) for component in components)
            labels.append(label)
            values.append(sign * value)
    if not values:
        return None

    fig, ax = plt.subplots(figsize=(13.5, 7.5))
    colors = ["#C4314B" if value >= 0.0 else "#168A45" for value in values]
    bars = ax.bar(range(len(values)), values, color=colors)
    ax.axhline(0.0, color="#1F2937", linewidth=0.9)
    ax.set_xticks(range(len(labels)), labels, rotation=25, ha="right")
    ax.yaxis.set_major_formatter(FuncFormatter(_aud_axis))
    basis = "absolutes Portfolio" if absolute else "normalisierter Durchschnittsvertrag"
    ax.set_ylabel(f"Barwert in AUD ({basis})")
    ax.set_title("Komponenten des Non-Unit Best Estimate Liability", loc="left")
    ax.text(
        0.0,
        1.02,
        "Positive Werte erhöhen die Liability; negative Werte reduzieren sie.",
        transform=ax.transAxes,
        color="#5B6573",
        fontsize=9,
    )
    for bar, value in zip(bars, values):
        offset = 4 if value >= 0.0 else -4
        alignment = "bottom" if value >= 0.0 else "top"
        ax.annotate(
            _aud_axis(value),
            (bar.get_x() + bar.get_width() / 2.0, value),
            xytext=(0, offset),
            textcoords="offset points",
            ha="center",
            va=alignment,
            fontsize=8,
        )
    fig.text(0.01, 0.01, footer, fontsize=8, color="#5B6573")
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    path = output / "01_portfolio_nonunit_bel_components.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _plot_model_point_contributions(
    plt: Any,
    FuncFormatter: Any,
    rows: list[dict[str, object]],
    output: Path,
    *,
    absolute: bool,
    footer: str,
) -> Optional[Path]:
    prefix = "portfolio_contribution_" if absolute else "normalised_contribution_"
    column = f"{prefix}insurer_net_present_value_before_risk_margin_aud"
    points = [
        (str(row.get("model_point_id", "")), _as_float(row.get(column)))
        for row in rows
    ]
    points = [(identifier, value) for identifier, value in points if value is not None]
    if not points:
        return None
    points.sort(key=lambda item: item[1])
    identifiers = [item[0] for item in points]
    values = [item[1] for item in points]

    height = max(8.0, 0.28 * len(points) + 2.0)
    fig, ax = plt.subplots(figsize=(13.5, height))
    positions = list(range(len(points)))
    colors = ["#168A45" if value >= 0.0 else "#C4314B" for value in values]
    ax.barh(positions, values, color=colors)
    ax.set_yticks(positions, identifiers)
    ax.axvline(0.0, color="#1F2937", linewidth=0.9)
    ax.xaxis.set_major_formatter(FuncFormatter(_aud_axis))
    basis = "absoluten Portfoliowert" if absolute else "gewichteten Durchschnittswert"
    ax.set_xlabel(f"Beitrag zum {basis} in AUD")
    ax.set_title(
        "Modellpunktbeiträge zum Insurer NPV before Risk Margin",
        loc="left",
    )
    fig.text(0.01, 0.01, footer, fontsize=8, color="#5B6573")
    fig.tight_layout(rect=(0.0, 0.035, 1.0, 1.0))
    path = output / "02_model_point_npv_contributions.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _plot_model_point_profitability(
    plt: Any,
    np: Any,
    PercentFormatter: Any,
    rows: list[dict[str, object]],
    output: Path,
    *,
    footer: str,
) -> Optional[Path]:
    value_column_candidates = (
        "new_business_margin_before_risk_margin",
        "per_contract_new_business_margin_before_risk_margin",
    )
    premium_column_candidates = ("per_contract_premium_aud", "premium_aud")

    observations: list[tuple[str, bool, float, float, float]] = []
    for row in rows:
        margin = next(
            (
                value
                for key in value_column_candidates
                if (value := _as_float(row.get(key))) is not None
            ),
            None,
        )
        premium = next(
            (
                value
                for key in premium_column_candidates
                if (value := _as_float(row.get(key))) is not None
            ),
            None,
        )
        age = _as_float(row.get("primary_age"))
        if margin is None or premium is None or age is None:
            continue
        observations.append((
            str(row.get("primary_sex", "")),
            _as_bool(row.get("spouse")),
            age,
            premium,
            margin,
        ))
    if not observations:
        return None

    groups = sorted({(sex, spouse) for sex, spouse, _, _, _ in observations})
    ages = sorted({age for _, _, age, _, _ in observations})
    premiums = sorted({premium for _, _, _, premium, _ in observations})
    max_abs = max(abs(item[4]) for item in observations)
    max_abs = max(max_abs, 1.0e-6)

    fig, axes = plt.subplots(2, 2, figsize=(15.5, 10.0), squeeze=False)
    image = None
    for index, axis in enumerate(axes.ravel()):
        if index >= len(groups):
            axis.set_visible(False)
            continue
        sex, spouse = groups[index]
        matrix = np.full((len(premiums), len(ages)), np.nan)
        for obs_sex, obs_spouse, age, premium, margin in observations:
            if obs_sex == sex and obs_spouse == spouse:
                matrix[premiums.index(premium), ages.index(age)] = margin
        image = axis.imshow(
            matrix,
            cmap="RdYlGn",
            vmin=-max_abs,
            vmax=max_abs,
            aspect="auto",
        )
        axis.set_xticks(range(len(ages)), [f"{age:g}" for age in ages])
        axis.set_yticks(
            range(len(premiums)),
            [_aud_axis(premium) for premium in premiums],
        )
        axis.set_xlabel("Eintrittsalter")
        axis.set_ylabel("Einmalbeitrag (AUD)")
        axis.set_title(f"Sex {sex} | {'Joint Life' if spouse else 'Single Life'}")
        for row_index in range(len(premiums)):
            for column_index in range(len(ages)):
                value = matrix[row_index, column_index]
                if np.isfinite(value):
                    text_color = "white" if abs(value) > 0.65 * max_abs else "#1F2937"
                    axis.text(
                        column_index,
                        row_index,
                        f"{100.0 * value:.1f}%",
                        ha="center",
                        va="center",
                        color=text_color,
                        fontsize=8.5,
                    )
    if image is not None:
        colorbar = fig.colorbar(image, ax=axes.ravel().tolist(), shrink=0.82)
        colorbar.ax.yaxis.set_major_formatter(PercentFormatter(1.0))
        colorbar.set_label("New Business Margin before Risk Margin")
    fig.suptitle("Profitabilität der einzelnen Modellpunkte", fontsize=16, x=0.06, ha="left")
    fig.text(0.01, 0.01, footer, fontsize=8, color="#5B6573")
    fig.subplots_adjust(top=0.90, bottom=0.08, left=0.09, right=0.90, hspace=0.30)
    path = output / "03_model_point_profitability_heatmaps.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _plot_exposure_mix(
    plt: Any,
    PercentFormatter: Any,
    rows: list[dict[str, object]],
    output: Path,
    *,
    footer: str,
) -> Optional[Path]:
    ages = sorted({
        age for row in rows
        if (age := _as_float(row.get("primary_age"))) is not None
    })
    if not ages:
        return None

    contract_mix = {(age, spouse): 0.0 for age in ages for spouse in (False, True)}
    premium_mix = {(age, spouse): 0.0 for age in ages for spouse in (False, True)}
    for row in rows:
        age = _as_float(row.get("primary_age"))
        contract_weight = _as_float(row.get("normalised_contract_share"))
        if contract_weight is None:
            contract_weight = _as_float(row.get("contract_weight"))
        premium_weight = _as_float(row.get("premium_volume_weight_control"))
        if age is None:
            continue
        spouse = _as_bool(row.get("spouse"))
        if contract_weight is not None:
            contract_mix[(age, spouse)] += contract_weight
        if premium_weight is not None:
            premium_mix[(age, spouse)] += premium_weight

    fig, axes = plt.subplots(1, 2, figsize=(15.0, 7.3), sharey=True)
    positions = list(range(len(ages)))
    colors = {False: "#007AB3", True: "#00A6A6"}
    for axis, values, title in (
        (axes[0], contract_mix, "Normalised Contract Share"),
        (axes[1], premium_mix, "Premium Volume Weight (Kontrollsicht)"),
    ):
        bottom = [0.0] * len(ages)
        for spouse in (False, True):
            heights = [values[(age, spouse)] for age in ages]
            axis.bar(
                positions,
                heights,
                bottom=bottom,
                color=colors[spouse],
                label="Joint Life" if spouse else "Single Life",
            )
            bottom = [left + right for left, right in zip(bottom, heights)]
        axis.set_xticks(positions, [f"{age:g}" for age in ages])
        axis.set_xlabel("Eintrittsalter")
        axis.set_title(title, loc="left")
        axis.yaxis.set_major_formatter(PercentFormatter(1.0))
        axis.legend()
    axes[0].set_ylabel("Anteil am Gesamtbestand")
    fig.suptitle("Zusammensetzung der Modellpunktpopulation", fontsize=16, x=0.06, ha="left")
    fig.text(
        0.01,
        0.01,
        footer + " | Premium Volume Weight wird nicht als zweites PV-Gewicht verwendet.",
        fontsize=8,
        color="#5B6573",
    )
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 0.94))
    path = output / "04_portfolio_exposure_mix.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _plot_fair_fee_gaps(
    plt: Any,
    rows: list[dict[str, object]],
    output: Path,
    *,
    footer: str,
) -> Optional[Path]:
    series = (
        ("charged_minus_fair_lip_bp", "Charged minus fair LIP", "#007AB3", "o"),
        (
            "charged_minus_commercial_break_even_lip_bp",
            "Charged minus commercial break-even LIP",
            "#E87722",
            "D",
        ),
    )
    identifiers = [str(row.get("model_point_id", "")) for row in rows]
    available = {
        key: [_as_float(row.get(key)) for row in rows]
        for key, _, _, _ in series
    }
    if not any(any(value is not None for value in values) for values in available.values()):
        return None

    height = max(8.0, 0.28 * len(rows) + 2.0)
    fig, ax = plt.subplots(figsize=(13.5, height))
    positions = list(range(len(rows)))
    for key, label, color, marker in series:
        x_values = []
        y_values = []
        for position, value in zip(positions, available[key]):
            if value is not None:
                x_values.append(value)
                y_values.append(position)
        if x_values:
            ax.scatter(x_values, y_values, label=label, color=color, marker=marker, s=30)
    ax.axvline(0.0, color="#1F2937", linewidth=0.9)
    ax.set_yticks(positions, identifiers)
    ax.invert_yaxis()
    ax.set_xlabel("Gebührendifferenz in Basispunkten")
    ax.set_title("Modellpunktbezogene Fair-Fee-Diagnostik", loc="left")
    ax.text(
        0.0,
        1.01,
        "Positive Werte bedeuten: belastete LIP liegt über der modellimplizierten Rate.",
        transform=ax.transAxes,
        color="#5B6573",
        fontsize=9,
    )
    ax.legend()
    fig.text(0.01, 0.01, footer, fontsize=8, color="#5B6573")
    fig.tight_layout(rect=(0.0, 0.035, 1.0, 1.0))
    path = output / "05_model_point_fair_fee_gaps.png"
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _create_plots(
    summary: Mapping[str, object],
    model_point_rows: list[dict[str, object]],
    output: Path,
    *,
    absolute: bool,
    include_fair_fee_plot: bool,
    logger: logging.Logger,
) -> tuple[dict[str, str], str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter, PercentFormatter
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "Default portfolio plots require the project dependency matplotlib. "
            "Reinstall the project dependencies or rerun explicitly with "
            "--no-plots."
        ) from exc

    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#B8C0CC",
        "axes.grid": True,
        "grid.color": "#DDE2E8",
        "grid.alpha": 0.7,
        "grid.linewidth": 0.7,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "legend.frameon": False,
    })

    output.mkdir(parents=True, exist_ok=True)
    basis = (
        "absolute Portfolioaggregation"
        if absolute
        else "normalisierte gewichtete Durchschnittswerte"
    )
    footer = (
        f"Marktkonsistente Research-Bewertung | {basis} | "
        "Heston-Hull-White unter Q | keine Produktionsbasis"
    )
    candidates = [
        _plot_component_decomposition(
            plt,
            FuncFormatter,
            summary,
            output,
            absolute=absolute,
            footer=footer,
        ),
        _plot_model_point_contributions(
            plt,
            FuncFormatter,
            model_point_rows,
            output,
            absolute=absolute,
            footer=footer,
        ),
        _plot_model_point_profitability(
            plt,
            np,
            PercentFormatter,
            model_point_rows,
            output,
            footer=footer,
        ),
        _plot_exposure_mix(
            plt,
            PercentFormatter,
            model_point_rows,
            output,
            footer=footer,
        ),
    ]
    if include_fair_fee_plot:
        candidates.append(
            _plot_fair_fee_gaps(
                plt,
                model_point_rows,
                output,
                footer=footer,
            )
        )

    paths = [path for path in candidates if path is not None]
    if include_fair_fee_plot and not any("fair_fee" in path.name for path in paths):
        logger.warning(
            "Fair-Fee-Grafik übersprungen: kein Modellpunkt besitzt eine gelöste Fee."
        )
    result = {path.stem: str(path) for path in paths}
    return result, str(matplotlib.__version__)


def _result_attribute(result: object, name: str, fallback: object = None) -> object:
    return getattr(result, name, fallback)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    logger, log_path = _configure_logging(output, args.log_file, args.log_level)
    started = time.perf_counter()

    try:
        logger.info("[1/6] Portfolio-Run gestartet | Output: %s", output)
        logger.info("[2/6] Markt-, Kosten-, Behaviour- und Modellpunktdaten laden")
        market = load_market_assumptions(args.zero_curve, args.model_parameters)
        generic_base_product = IndexLinkedLifetimeIncomeProduct(
            reference_fund=ReferenceFundSpec(
                scenario_maximum_return=args.crediting_cap_rate,
            ),
            fees=FeeSpec(lip_waived_in_income_phase_if_aps=False),
            dividend_yield={
                index: parameters.dividend_yield
                for index, parameters in market.esg.equity.items()
            },
        )
        portfolio_projection = ProjectionConfig(
            record_paths=False,
            heston_cos=False,
        )
        costs = load_cost_assumptions(
            args.cost_assumptions,
            assumption_set_id=args.cost_assumption_set,
            value_basis="base",
            product=generic_base_product,
            projection=portfolio_projection,
        )
        behaviour_assumptions = load_dynamic_behaviour_assumptions(
            args.dynamic_behaviour,
            assumption_set_id=args.behaviour_assumption_set,
            value_basis="base",
        )
        # The explicit model-point Income start takes precedence for this
        # portfolio. The behaviour files remain the source for lapse and
        # withdrawal dynamics and retain full provenance.
        portfolio_behaviour = replace(
            behaviour_assumptions.behaviour,
            take_up=replace(
                behaviour_assumptions.behaviour.take_up,
                mode="deterministic",
            ),
        )
        model_points = load_policyholder_model_points(
            args.model_points,
            expected_market_parameter_set_id=market.parameter_set_id,
            expected_yield_curve_id=market.curve_id,
        )
        model_point_count = len(model_points.model_points)
        joint_continue_income_count = sum(
            1
            for point in model_points.model_points
            if point.policy.spouse
            and point.policy.spouse_death_election.value == "continue_income"
        )
        automatic_start_override_count = sum(
            1
            for point in model_points.model_points
            if point.policy.effective_income_start_year(costs.product)
            != int(round(point.policy.income_start_year))
        )
        logger.info(
            "%d Modellpunkte geladen | contract_weight sum=%.12f | "
            "premium_volume_weight sum=%.12f",
            model_point_count,
            model_points.contract_weight_sum,
            model_points.premium_volume_weight_sum,
        )
        if joint_continue_income_count:
            logger.warning(
                "%d Continue-Income-Joint-Life-Modellpunkte: Der bedingt "
                "gemeinsame Zweig verwendet die aus den CSVs geladenen "
                "statischen Basisraten für Income-Lapse und Excess Withdrawal; "
                "der Single-Life-Fallback bleibt dynamisch. Damit wird keine "
                "nichtlineare Behaviour-Funktion auf einen gemittelten "
                "p11/p10/p01-Zustand angewandt.",
                joint_continue_income_count,
            )
        if automatic_start_override_count:
            logger.info(
                "%d Modellpunkte starten wegen des vertraglichen "
                "Automatic-Age-Backstops früher als income_start_year; der "
                "effektive Termin gilt auch für Ratecard und Spouse-Survival.",
                automatic_start_override_count,
            )
        source_contract_count = model_points.total_exposure_count
        if source_contract_count is not None:
            logger.info(
                "Absolute Source-Exposures vorhanden | N_total=%s | "
                "represented_contract_count wird je Modellpunkt direkt aus "
                "exposure_count übernommen.",
                f"{source_contract_count:,.6g}",
            )
            if args.portfolio_contract_count is not None:
                logger.info(
                    "Explizites --portfolio-contract-count=%s wird gegen die "
                    "Source-Exposures validiert.",
                    f"{args.portfolio_contract_count:,.6g}",
                )
        elif args.portfolio_contract_count is None:
            logger.warning(
                "Keine absolute Vertragsanzahl angegeben. Ergebnisse werden "
                "fachgerecht als gewichtete Durchschnittswerte je "
                "repräsentativem Vertrag ausgewiesen; die %d Modellpunktzeilen "
                "werden nicht als %d Policen unterstellt.",
                model_point_count,
                model_point_count,
            )
        else:
            logger.info(
                "Absolute Portfolioaggregation mit N_total=%s; Modellpunkt-"
                "Exposure ist N_total * contract_weight.",
                f"{args.portfolio_contract_count:,.6g}",
            )

        # Explicitly illustrative research mortality, not a governed Australian
        # insured-lives production basis.
        mortality = MortalityTable.gompertz_makeham()
        settings = ValuationSettings(
            model="heston_hull_white",
            n_paths=args.n_paths,
            seed=args.seed,
            heston_substeps=args.heston_substeps,
            horizon_years=None,
            projection=costs.projection,
            real_world_model="hull_white_bs",
        )

        logger.info(
            "[3/6] Einzelbewertung der Modellpunkte und anschließende "
            "Portfolioaggregation | paths=%d | seed=%d | Heston substeps=%d",
            args.n_paths,
            args.seed,
            args.heston_substeps,
        )
        result = value_policyholder_portfolio(
            costs.product,
            model_points,
            market.esg,
            mortality,
            portfolio_behaviour,
            costs.expenses,
            settings=settings,
            portfolio_contract_count=args.portfolio_contract_count,
            calculate_fair_lip=args.fair_lip,
            calculate_commercial_break_even_lip=args.commercial_break_even_lip,
            calculate_portfolio_fair_lip=args.portfolio_fair_lip,
            calculate_portfolio_commercial_break_even_lip=(
                args.portfolio_commercial_break_even_lip
            ),
            profitability_materiality_bp=args.profitability_materiality_bp,
            fair_fee_lower_rate=args.fair_fee_lower,
            fair_fee_upper_rate=args.fair_fee_upper,
            fair_fee_maximum_upper_rate=args.fair_fee_maximum_upper,
            fair_fee_tolerance=args.fair_fee_tolerance,
            progress_callback=_make_progress_callback(logger),
        )

        summary = result.summary_dict()
        summary.update({
            "valuation_as_of_date": market.curve_metadata["as_of_date"],
            "valuation_currency": market.curve_metadata["currency"],
            "market_parameter_set_id": market.parameter_set_id,
            "yield_curve_id": market.curve_id,
            "cost_assumption_set_id": costs.assumption_set_id,
            "behaviour_assumption_set_id": behaviour_assumptions.assumption_set_id,
        })
        model_point_rows = result.model_point_rows()
        if len(model_point_rows) != model_point_count:
            raise ValueError(
                "Portfolio result row count does not match loaded model-point "
                f"count: {len(model_point_rows)} != {model_point_count}."
            )

        logger.info("[4/6] CSV-Ergebnisse und Aggregationsabgleich schreiben")
        summary_path = output / "portfolio_summary.csv"
        model_point_path = output / "model_point_results.csv"
        reconciliation_path = output / "portfolio_aggregation_reconciliation.csv"
        manifest_path = output / "run_manifest.json"
        _write_csv(summary_path, [summary])
        _write_csv(model_point_path, model_point_rows)
        reconciliation_rows = _build_aggregation_reconciliation(
            summary,
            model_point_rows,
        )
        _write_csv(reconciliation_path, reconciliation_rows)

        fair_fee_path: Optional[Path] = None
        if args.fair_lip or args.commercial_break_even_lip:
            fair_fee_rows = _build_fair_fee_rows(model_point_rows)
            if fair_fee_rows:
                fair_fee_path = output / "model_point_fair_fee_results.csv"
                _write_csv(fair_fee_path, fair_fee_rows)
            else:
                logger.warning(
                    "Individuelle Fair Fees wurden angefordert, aber es wurden "
                    "keine Fair-Fee-Diagnosefelder zurückgegeben."
                )

        absolute = bool(summary.get("absolute_portfolio_values_available"))
        resolved_portfolio_contract_count = _result_attribute(
            result,
            "portfolio_contract_count",
        )
        figure_paths: dict[str, str] = {}
        matplotlib_version: Optional[str] = None
        if args.no_plots:
            logger.info("[5/6] Grafikerstellung durch --no-plots deaktiviert")
        else:
            logger.info("[5/6] Headless-Portfolio-Grafiken erstellen")
            figure_paths, matplotlib_version = _create_plots(
                summary,
                model_point_rows,
                output / "figures",
                absolute=absolute,
                include_fair_fee_plot=(
                    args.fair_lip or args.commercial_break_even_lip
                ),
                logger=logger,
            )
            logger.info("%d Grafiken erstellt", len(figure_paths))

        logger.info("[6/6] Run-Manifest schreiben")
        runtime = time.perf_counter() - started
        outputs: dict[str, object] = {
            "portfolio_summary_csv": str(summary_path),
            "model_point_results_csv": str(model_point_path),
            "portfolio_aggregation_reconciliation_csv": str(reconciliation_path),
            "run_manifest_json": str(manifest_path),
            "run_log": str(log_path),
            "figures": figure_paths,
        }
        if fair_fee_path is not None:
            outputs["model_point_fair_fee_results_csv"] = str(fair_fee_path)

        model_limitations = [
            "Research valuation gross of reinsurance.",
            "Mortality is illustrative and not an approved production basis.",
            "Spouse survival to the deterministic Election anniversary and "
            "the Single-Life fallback are modelled under independent lives; "
            "divorce, removal, common shocks and legal eligibility changes "
            "are not modelled.",
            "For Continue-Income Joint Life, the conditional joint branch uses "
            "state-independent static CSV base lapse/withdrawal assumptions; "
            "the Single-Life fallback remains dynamic. Separate p11, p10 and "
            "p01 account-value cohorts are not yet projected, so dynamic "
            "Joint-Life coefficients are deliberately not applied to that "
            "conditional joint branch.",
            "Intra-year DVA is a moment-matched Black-Scholes proxy on the "
            "complete reference fund; COS is not used.",
            "Dynamic lapse and withdrawal inputs are uncalibrated proxies; "
            "the effective deterministic model-point Income start, including "
            "the automatic-age backstop, overrides dynamic take-up.",
            "The five-year government-bond sleeve and fixed 50/50 monthly "
            "rebalancing are product-model proxy conventions.",
            "No bond term premium, credit spreads, defaults, FX layer, "
            "transaction costs or fund-internal charges are modelled.",
        ]
        if not absolute:
            model_limitations.append(
                "No total contract count was supplied; aggregate monetary "
                "results are normalised weighted averages per representative "
                "contract and are not absolute portfolio totals."
            )

        result_settings = _result_attribute(result, "settings", settings)
        manifest = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "runtime_seconds": runtime,
            "engine_version": ENGINE_VERSION,
            "reporting": {
                "plots_requested": not args.no_plots,
                "matplotlib_version": matplotlib_version,
            },
            "method": {
                "product": "generic_index_linked_lifetime_income_case_study",
                "valuation_measure": "risk_neutral",
                "market_model": "heston_hull_white",
                "simulation": "plain_monte_carlo",
                "shared_market_scenarios_across_model_points": True,
                "model_points_valued_separately_before_aggregation": True,
                "income_take_up": (
                    "deterministic_effective_model_point_income_start_year_"
                    "including_automatic_age_backstop"
                ),
                "spouse_election_eligibility": (
                    "spouse_survival_to_election_with_single_life_fallback"
                ),
                "joint_life_behaviour": (
                    "continue_income_joint_branch_uses_static_csv_base_rates;"
                    "single_life_fallback_remains_dynamic;"
                    "no_separate_p11_p10_p01_account_cohorts"
                ),
                "income_lapse_after_account_value_exhaustion": (
                    "remains_active_while_income_guarantee_is_in_force"
                ),
                "monthly_mortality": (
                    "annual_q_anchored_at_policy_anniversary_then_constant_"
                    "force_converted_for_12_months"
                ),
                "terminal_mortality_age": 115,
                "short_horizon_residual": "separate_terminal_closeout_cashflow",
                "cos_used": False,
                "lsmc_used": False,
                "record_state_paths": False,
                "intra_year_dva": (
                    "moment_matched_black_scholes_proxy_on_complete_reference_fund"
                ),
                "crediting_cap_rate": (
                    costs.product.reference_fund.effective_maximum_return
                ),
                "reference_fund": {
                    "specification_vintage": (
                        costs.product.reference_fund.specification_vintage
                    ),
                    "global_equity_weight": costs.product.reference_fund.equity_weight,
                    "australian_government_bond_weight": (
                        1.0 - costs.product.reference_fund.equity_weight
                    ),
                    "bond_tenor_years": (
                        costs.product.reference_fund.bond_tenor_years
                    ),
                    "rebalance_frequency_months": (
                        costs.product.reference_fund.rebalance_frequency_months
                    ),
                    "contractual_maximum_return": (
                        costs.product.reference_fund.maximum_return
                    ),
                    "scenario_maximum_return_override": (
                        costs.product.reference_fund.scenario_maximum_return
                    ),
                },
            },
            "mortality": {
                "basis": "illustrative_gompertz_makeham",
                "calibration_status": "not_calibrated_for_production",
                "description": (
                    "Illustrative Gompertz-Makeham shape approximating ALT "
                    "2020-22; replace with an approved insured-lives basis for "
                    "production use."
                ),
                "base_year": mortality.base_year,
                "annual_improvement_rate": mortality.improvement_rate,
                "improvement_taper_age": mortality.improvement_taper_age,
                "improvement_end_age": mortality.improvement_end_age,
                "monthly_conversion": (
                    "policy_year_annual_q_constant_force_with_annual_"
                    "survival_reconciliation"
                ),
                "terminal_age": 115,
                "terminal_convention": (
                    "death_probability_one_in_interval_ending_at_terminal_age"
                ),
                "behaviour_annuity_factor": (
                    "monthly_in_arrears_on_same_monthly_mortality_curve"
                ),
            },
            "portfolio": {
                "aggregation_basis": summary.get(
                    "aggregation_basis",
                    _result_attribute(result, "aggregation_basis"),
                ),
                "absolute_portfolio_totals_available": absolute,
                "portfolio_contract_count": resolved_portfolio_contract_count,
                "source_exposure_counts_available": (
                    model_points.total_exposure_count is not None
                ),
                "input_model_point_count": model_point_count,
                "output_model_point_row_count": len(model_point_rows),
                "each_csv_row_assumed_to_be_one_policy": False,
                "normalised_pv_weight_source": summary.get(
                    "aggregation_weight_source"
                ),
                "contract_weight_is_sole_pv_weight": (
                    model_points.total_exposure_count is None
                ),
                "source_exposure_count_is_absolute_pv_weight": (
                    model_points.total_exposure_count is not None
                ),
                "premium_volume_weight_is_not_a_pv_weight": True,
                "scenario_horizon_years": _result_attribute(
                    result, "scenario_horizon_years"
                ),
                "scenario_fingerprint": _result_attribute(
                    result, "scenario_fingerprint"
                ),
            },
            "valuation_settings": {
                "n_paths": int(result_settings.n_paths),
                "seed": int(result_settings.seed),
                "heston_substeps": int(result_settings.heston_substeps),
                "horizon_years": result_settings.horizon_years,
                "record_paths": result_settings.projection.record_paths,
                "heston_cos": result_settings.projection.heston_cos,
                "fair_lip_per_model_point_requested": args.fair_lip,
                "commercial_break_even_lip_per_model_point_requested": (
                    args.commercial_break_even_lip
                ),
                "portfolio_fair_lip_requested": args.portfolio_fair_lip,
                "portfolio_commercial_break_even_lip_requested": (
                    args.portfolio_commercial_break_even_lip
                ),
                "fair_fee_lower_rate": args.fair_fee_lower,
                "fair_fee_upper_rate": args.fair_fee_upper,
                "fair_fee_maximum_upper_rate": args.fair_fee_maximum_upper,
                "fair_fee_tolerance": args.fair_fee_tolerance,
                "profitability_materiality_bp": args.profitability_materiality_bp,
            },
            "sources": {
                "model_points": model_points.source_metadata(),
                "market": market.source_metadata(),
                "costs": costs.source_metadata(),
                "dynamic_behaviour": {
                    **behaviour_assumptions.source_metadata(),
                    "portfolio_application": {
                        "income_take_up": (
                            "overridden_by_deterministic_model_point_"
                            "effective_income_start_year"
                        ),
                        "single_life_and_lump_sum_spouse": (
                            "dynamic_income_lapse_and_withdrawal_coefficients"
                        ),
                        "continue_income_joint_branch": (
                            "static_state_independent_csv_base_rates"
                        ),
                        "continue_income_single_life_fallback": (
                            "dynamic_income_lapse_and_withdrawal_coefficients"
                        ),
                        "growth_lapse_and_withdrawals": (
                            "loaded_for_provenance_but_product_gate_forces_zero"
                        ),
                    },
                },
            },
            "model_limitations": model_limitations,
            "outputs": outputs,
            "summary": summary,
        }
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(
                manifest,
                handle,
                indent=2,
                sort_keys=True,
                allow_nan=False,
                default=str,
            )
            handle.write("\n")

        basis_prefix = "portfolio_total_" if absolute else "normalised_average_"
        logger.info(
            "Bewertungsbasis: %s",
            "absolute Portfoliowerte"
            if absolute
            else "normalisierte Werte je repräsentativem Vertrag",
        )
        for label, metric in (
            ("Market-Consistent BEL Total", "market_consistent_bel_total_aud"),
            ("Present Value of Future Charges (PVFC)", "pv_future_fees_aud"),
            (
                "Insurer NPV before Risk Margin",
                "insurer_net_present_value_before_risk_margin_aud",
            ),
        ):
            value = _as_float(summary.get(f"{basis_prefix}{metric}"))
            if value is not None:
                logger.info("%s: AUD %s", label, f"{value:,.2f}")
        logger.info("Portfolio summary: %s", summary_path)
        logger.info("Model-point results: %s", model_point_path)
        logger.info("Aggregation reconciliation: %s", reconciliation_path)
        logger.info("Run manifest: %s", manifest_path)
        logger.info("Run abgeschlossen in %.1f Sekunden", time.perf_counter() - started)
        return 0
    except Exception:
        logger.exception("Portfolio-Run fehlgeschlagen")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
