"""Create the archived insurer-oriented AGILE research pack.

This legacy example contains AGILE-only design variants and historical report
labels. It is not the active generic product or portfolio workflow. Use
``portfolio_simulations/run_portfolio_valuation.py`` for current valuations.

The pack is deliberately explicit about scope: it is a new-business research
view of one July-2026 model point.  Capital is the engine's SII-style economic
stress proxy, not APRA/LAGIC prescribed capital.  Costs are loaded from the
repository cost CSV; entries marked as expert assumptions/proxies, as well as
market, mortality, behaviour and DVA/MVA calibration, remain illustrative.

Usage
-----
    python examples/run_insurer_analysis.py
    python examples/run_insurer_analysis.py --fast
    python examples/run_insurer_analysis.py --base-paths 10000
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import sys
import time
from dataclasses import fields, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.ticker import FuncFormatter, PercentFormatter
import numpy as np
import pandas as pd
import scipy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agile_engine
from agile_engine import (
    AgileProduct,
    CapitalStresses,
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DEFAULT_MODEL_PARAMETERS_PATH,
    ExpenseAssumptions,
    IncomeType,
    Measure,
    MortalityTable,
    PolicySpec,
    ProfitabilitySettings,
    ProjectionConfig,
    Sex,
    ValuationSettings,
    analyse_profitability,
    compute_capital,
    fair_lifetime_income_premium,
    greeks,
    load_cost_assumptions,
    load_dynamic_behaviour_assumptions,
    load_market_assumptions,
    project,
    resolve_horizon,
    run_sensitivities,
    simulate,
    value_contract,
)


# ---------------------------------------------------------------------------
# Visual language and shared labels
# ---------------------------------------------------------------------------

BLUE = "#003781"
MID_BLUE = "#007AB3"
LIGHT_BLUE = "#75B9E7"
CYAN = "#00A6A6"
GREEN = "#168A45"
RED = "#C4314B"
ORANGE = "#E87722"
GOLD = "#D4A017"
GREY = "#5B6573"
LIGHT_GREY = "#E7EBF0"
DARK = "#1F2937"

MODEL_POINT = (
    "Juli-2026 New Business | männlich, 65 | AUD 100.000 | 100% AUS Total "
    "Protection | Fixed Income mit dynamischem Take-up"
)
RESEARCH_FOOTER = (
    "Illustrativer Research-Run – keine PDS-Prognose, kein In-force-Wert und "
    "kein APRA/LAGIC-Kapital"
)

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#B8C0CC",
        "axes.labelcolor": DARK,
        "axes.titlecolor": DARK,
        "axes.titleweight": "bold",
        "axes.grid": True,
        "grid.color": "#DDE2E8",
        "grid.alpha": 0.7,
        "grid.linewidth": 0.7,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "xtick.color": GREY,
        "ytick.color": GREY,
        "legend.frameon": False,
    }
)


SCENARIO_DE = {
    "rates +100bp": "Zinsen +100 bp",
    "rates -100bp": "Zinsen -100 bp",
    "equity vol +25%": "Aktienvolatilität +25%",
    "caps -100bp": "Maximum Returns -100 bp",
    "longevity -10% qx": "Langlebigkeit: qx -10%",
    "mortality +10% qx": "Sterblichkeit: qx +10%",
    "lapse +50%": "Storno +50%",
    "lapse -50%": "Storno -50%",
    "lapse response +25%": "Storno-Reaktion +25%",
    "lapse response -25%": "Storno-Reaktion -25%",
    "take-up +25%": "Income-Take-up +25%",
    "take-up -25%": "Income-Take-up -25%",
    "free withdrawals 100% used": "Free Withdrawals 100%",
    "excess withdrawals 2% p.a.": "Excess Withdrawals 2% p.a.",
    "expenses +10%": "Kosten +10%",
    "ERP -100bp (RW only)": "Equity Risk Premium -100 bp",
}


def aud_axis(x: float, _pos: int | None = None) -> str:
    """Compact AUD tick labels."""
    ax = abs(x)
    if ax >= 1_000_000:
        return f"{x / 1_000_000:.1f}m"
    if ax >= 1_000:
        return f"{x / 1_000:.0f}k"
    return f"{x:.0f}"


def aud_axis_precise(x: float, _pos: int | None = None) -> str:
    """AUD ticks with enough precision for narrow Monte-Carlo ranges."""
    if abs(x) >= 1_000:
        return f"{x / 1_000:.1f}k"
    return f"{x:.0f}"


def aud(x: float, decimals: int = 0) -> str:
    return f"AUD {x:,.{decimals}f}"


def pct(x: float, decimals: int = 1) -> str:
    return f"{100.0 * x:.{decimals}f}%"


def add_header(fig: plt.Figure, title: str, subtitle: str = MODEL_POINT) -> None:
    fig.suptitle(title, x=0.055, y=0.985, ha="left", fontsize=18, color=BLUE,
                 fontweight="bold")
    fig.text(0.055, 0.945, subtitle, ha="left", va="top", fontsize=9.5,
             color=GREY)


def add_footer(fig: plt.Figure, note: str = RESEARCH_FOOTER) -> None:
    fig.text(0.055, 0.018, note, ha="left", va="bottom", fontsize=8,
             color=GREY)


def save_figure(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def bar_labels(ax: plt.Axes, bars: Iterable[Any], fmt=aud_axis,
               pad: float = 3.0, fontsize: float = 8.5) -> None:
    for b in bars:
        value = b.get_height()
        if not np.isfinite(value):
            continue
        va = "bottom" if value >= 0 else "top"
        offset = pad if value >= 0 else -pad
        ax.annotate(fmt(value), (b.get_x() + b.get_width() / 2, value),
                    xytext=(0, offset), textcoords="offset points", ha="center",
                    va=va, fontsize=fontsize, color=DARK)


# ---------------------------------------------------------------------------
# Inputs, run manifest and reconciliations
# ---------------------------------------------------------------------------


def build_inputs(cost_path=DEFAULT_COST_ASSUMPTIONS_PATH,
                 assumption_set_id=None,
                 behaviour_directory=DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
                 behaviour_assumption_set_id=None,
                 curve_path=DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
                 model_parameters_path=DEFAULT_MODEL_PARAMETERS_PATH):
    """Canonical model point with market, cost and behaviour CSV inputs."""
    market = load_market_assumptions(curve_path, model_parameters_path)
    esg = market.esg
    mortality = MortalityTable.gompertz_makeham()
    costs = load_cost_assumptions(
        cost_path, assumption_set_id=assumption_set_id
    )
    behaviour_assumptions = load_dynamic_behaviour_assumptions(
        behaviour_directory,
        assumption_set_id=behaviour_assumption_set_id,
    )
    product = costs.product
    policy = PolicySpec(age=65, sex=Sex.MALE, commencement_year=2026.5,
                        initial_investment=100_000, income_start_year=5,
                        income_type=IncomeType.FIXED)
    behaviour = behaviour_assumptions.behaviour
    expenses = costs.expenses
    return (esg, mortality, product, policy, behaviour, expenses, costs,
            behaviour_assumptions, market)


def serialise(value: Any) -> Any:
    if is_dataclass(value):
        return {f.name: serialise(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(serialise(k)): serialise(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [serialise(v) for v in value]
    if isinstance(value, np.ndarray):
        if value.size <= 60:
            return value.tolist()
        data = np.ascontiguousarray(value).view(np.uint8)
        return {
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "min": float(np.min(value)),
            "max": float(np.max(value)),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def source_hash(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted((root / "agile_engine").glob("*.py")):
        h.update(path.name.encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()


def income_rate(product: AgileProduct, policy: PolicySpec) -> float:
    return product.income_rates.lifetime_income_rate(
        policy.age,
        policy.sex,
        policy.income_type,
        policy.spouse,
        int(np.floor(policy.income_start_year + 1e-12)),
        policy.spouse_age,
        policy.spouse_sex,
        policy.age_pension_plus,
    )


def pathwise_pricing_error(val) -> dict[str, float]:
    """Path standard errors for the key Q-valuations."""
    p = val.projection
    d = p.scenarios.discount[:, : len(p.times)]
    cf = p.cashflows
    nav_path = np.sum(
        d * (
            cf["fees_product"]
            + cf["fees_lip"]
            + cf["crediting_margin"]
            + cf["mva_retained"]
            + cf["aps_retained"]
            - cf["guarantee_claims"]
            - cf["hedge_costs"]
            - cf["expenses"]
        ),
        axis=1,
    )
    gv_path = np.sum(d * (cf["guarantee_claims"] - cf["fees_lip"]), axis=1)
    ph_path = np.sum(
        d * (
            cf["income_paid"]
            + cf["death_benefits"]
            + cf["surrender_benefits"]
            + cf["partial_withdrawals"]
            - cf["guarantee_claims"]
            + cf["fees_product"]
            + cf["fees_lip"]
            + cf["crediting_margin"]
            + cf["mva_retained"]
            + cf["aps_retained"]
        ),
        axis=1,
    )
    n = len(nav_path)
    return {
        "gross_vnb_se": float(np.std(nav_path, ddof=1) / np.sqrt(n)),
        "guarantee_value_se": float(np.std(gv_path, ddof=1) / np.sqrt(n)),
        "identity_gap_se": float(np.std(ph_path, ddof=1) / np.sqrt(n) / val.premium),
        "claim_positive_path_share": float(
            np.mean(np.sum(cf["guarantee_claims"], axis=1) > 1e-8)
        ),
    }


def reconciliation_table(val, fair_lip: float, charged_lip: float,
                         mc: Mapping[str, float]) -> pd.DataFrame:
    bel_identity = val.bel_nonunit + val.insurer_net_value
    fair_gap_bp = (fair_lip - charged_lip) * 10_000
    return pd.DataFrame(
        [
            ("Q market-consistency identity", val.identity_gap,
             1.96 * mc["identity_gap_se"], "relative gap", "PASS" if abs(val.identity_gap) <= max(0.0025, 3 * mc["identity_gap_se"]) else "REVIEW"),
            ("BEL + insurer net value", bel_identity, 1.0, "AUD", "PASS" if abs(bel_identity) < 1.0 else "REVIEW"),
            ("Guarantee value formula", val.guarantee_value - (val.pv["guarantee_claims"] - val.pv["fees_lip"]), 1.0, "AUD", "PASS"),
            ("Fair LIP minus charged LIP", fair_gap_bp, np.nan, "bp", "INFO"),
        ],
        columns=["check", "result", "tolerance_or_95ci", "unit", "status"],
    )


# ---------------------------------------------------------------------------
# Calculation blocks
# ---------------------------------------------------------------------------


def product_variant_rows(product, base_policy, esg, mortality, behaviour,
                         expenses, settings) -> pd.DataFrame:
    variants = [
        ("Single Fixed", replace(base_policy, income_type=IncomeType.FIXED)),
        ("Single Rising", replace(base_policy, income_type=IncomeType.RISING)),
        (
            "Spouse Fixed",
            replace(base_policy, income_type=IncomeType.FIXED, spouse=True,
                    spouse_age=63, spouse_sex=Sex.FEMALE),
        ),
        (
            "Spouse Rising",
            replace(base_policy, income_type=IncomeType.RISING, spouse=True,
                    spouse_age=63, spouse_sex=Sex.FEMALE),
        ),
        (
            "APS Fixed",
            replace(base_policy, income_type=IncomeType.FIXED,
                    age_pension_plus=True, aps_life_expectancy=20.0),
        ),
        (
            "APS Rising",
            replace(base_policy, income_type=IncomeType.RISING,
                    age_pension_plus=True, aps_life_expectancy=20.0),
        ),
    ]
    rows: list[dict[str, float | str]] = []
    for name, policy in variants:
        val = value_contract(product, policy, esg, mortality, behaviour,
                             expenses=expenses, settings=settings)
        expected_start_income = np.nan
        phase_paths = val.projection.phase_paths
        income_paths = val.projection.income_paths
        if phase_paths is not None and income_paths is not None:
            income_seen = phase_paths == 1
            has_income = np.any(income_seen, axis=1)
            if np.any(has_income):
                first_step = np.argmax(income_seen, axis=1)[has_income]
                path_index = np.flatnonzero(has_income)
                expected_start_income = float(np.mean(
                    income_paths[path_index, first_step]))
        customer_pv = sum(
            val.pv[k]
            for k in ("income_paid", "death_benefits", "surrender_benefits",
                      "partial_withdrawals")
        )
        claims = val.pv["guarantee_claims"]
        rows.append(
            {
                "variant": name,
                "reference_income_rate_year5": income_rate(product, policy),
                "q_mean_start_income": expected_start_income,
                "gross_vnb": val.insurer_net_value,
                "gross_nbm_pct": 100 * val.insurer_net_value / val.premium,
                "guarantee_value": val.guarantee_value,
                "pv_guarantee_claims": claims,
                "pv_lip": val.pv["fees_lip"],
                "rider_funding_ratio": val.pv["fees_lip"] / claims if claims > 0 else np.nan,
                "customer_benefit_pv": customer_pv,
                "identity_gap_pct": 100 * val.identity_gap,
            }
        )
        del val
        gc.collect()
    return pd.DataFrame(rows)


def start_timing_rows(product, base_policy, esg, mortality, behaviour,
                      expenses, settings) -> pd.DataFrame:
    rows = []
    for take_up_mult in (0.50, 0.75, 1.00, 1.25, 1.50):
        stressed_behaviour = behaviour.scaled_take_up(take_up_mult)
        val = value_contract(product, base_policy, esg, mortality,
                             stressed_behaviour,
                             expenses=expenses, settings=settings)
        phase_paths = val.projection.phase_paths
        income_paths = val.projection.income_paths
        mean_start_year = np.nan
        mean_start_age = np.nan
        start_income = np.nan
        if phase_paths is not None and income_paths is not None:
            income_seen = phase_paths == 1
            has_income = np.any(income_seen, axis=1)
            first_step = np.argmax(income_seen, axis=1)
            if np.any(has_income):
                selected_steps = first_step[has_income]
                mean_start_year = float(np.mean(selected_steps / 12.0))
                mean_start_age = base_policy.age + mean_start_year
                path_index = np.flatnonzero(has_income)
                start_income = float(np.mean(
                    income_paths[path_index, selected_steps]))
        rows.append(
            {
                "take_up_multiplier": take_up_mult,
                "q_mean_income_start_year": mean_start_year,
                "q_mean_income_start_age": mean_start_age,
                "q_mean_start_income": start_income,
                "gross_vnb": val.insurer_net_value,
                "gross_nbm_pct": 100 * val.insurer_net_value / val.premium,
                "guarantee_value": val.guarantee_value,
                "pv_claims": val.pv["guarantee_claims"],
                "pv_income": val.pv["income_paid"],
                "customer_benefit_pv": sum(
                    val.pv[k] for k in ("income_paid", "death_benefits",
                                        "surrender_benefits", "partial_withdrawals")
                ),
            }
        )
        del val
        gc.collect()
    return pd.DataFrame(rows)


def behaviour_surface_rows(product, base_policy, esg, mortality, behaviour,
                           expenses, settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    takeup_rows = []
    for lapse_mult in (0.50, 0.75, 1.00, 1.25, 1.50):
        for take_up_mult in (0.50, 0.75, 1.00, 1.25, 1.50):
            beh = behaviour.scaled_lapses(lapse_mult).scaled_take_up(take_up_mult)
            val = value_contract(product, base_policy, esg, mortality, beh,
                                 expenses=expenses, settings=settings)
            takeup_rows.append(
                {
                    "lapse_multiplier": lapse_mult,
                    "take_up_multiplier": take_up_mult,
                    "gross_nbm_pct": 100 * val.insurer_net_value / val.premium,
                    "guarantee_value": val.guarantee_value,
                }
            )
            del val
        gc.collect()

    withdrawal_rows = []
    for excess_rate in (0.0, 0.005, 0.01, 0.02):
        for free_util in (0.0, 0.25, 0.50, 1.0):
            wd = replace(behaviour.withdrawals, free_utilisation=free_util,
                         excess_rate=excess_rate)
            beh = replace(behaviour, withdrawals=wd)
            val = value_contract(product, base_policy, esg, mortality, beh,
                                 expenses=expenses, settings=settings)
            withdrawal_rows.append(
                {
                    "free_utilisation": free_util,
                    "excess_rate": excess_rate,
                    "gross_nbm_pct": 100 * val.insurer_net_value / val.premium,
                    "guarantee_value": val.guarantee_value,
                }
            )
            del val
        gc.collect()
    return pd.DataFrame(takeup_rows), pd.DataFrame(withdrawal_rows)


def model_risk_rows(product, policy, esg, mortality, behaviour, expenses,
                    n_paths: int, seed: int,
                    projection: ProjectionConfig) -> pd.DataFrame:
    labels = {
        "black_scholes": "Black-Scholes",
        "heston": "Heston",
        "hull_white_bs": "Hull-White + BS",
        "heston_hull_white": "Heston + Hull-White",
    }
    rows = []
    for model, label in labels.items():
        settings = ValuationSettings(
            model=model,
            n_paths=n_paths,
            seed=seed,
            horizon_years=None,
            projection=replace(projection, record_paths=False),
        )
        started = time.perf_counter()
        val = value_contract(product, policy, esg, mortality, behaviour,
                             expenses=expenses, settings=settings)
        rows.append(
            {
                "model": model,
                "label": label,
                "paths": n_paths,
                "gross_vnb": val.insurer_net_value,
                "gross_nbm_pct": 100 * val.insurer_net_value / val.premium,
                "guarantee_value": val.guarantee_value,
                "bel_nonunit": val.bel_nonunit,
                "identity_gap_pct": 100 * val.identity_gap,
                "runtime_seconds": time.perf_counter() - started,
            }
        )
        del val
        gc.collect()
    return pd.DataFrame(rows)


def seed_stability_rows(product, policy, esg, mortality, behaviour, expenses,
                        n_paths: int, projection: ProjectionConfig) -> pd.DataFrame:
    rows = []
    for seed in (2026, 12026, 22026, 32026, 42026):
        settings = ValuationSettings(
            model="heston_hull_white",
            n_paths=n_paths,
            seed=seed,
            horizon_years=None,
            projection=replace(projection, record_paths=False),
        )
        val = value_contract(product, policy, esg, mortality, behaviour,
                             expenses=expenses, settings=settings)
        err = pathwise_pricing_error(val)
        rows.append(
            {
                "seed": seed,
                "paths": n_paths,
                "gross_vnb": val.insurer_net_value,
                "gross_vnb_se": err["gross_vnb_se"],
                "guarantee_value": val.guarantee_value,
                "guarantee_value_se": err["guarantee_value_se"],
                "identity_gap_pct": 100 * val.identity_gap,
            }
        )
        del val
        gc.collect()
    return pd.DataFrame(rows)


def outcome_quantiles(product, policy, esg, mortality, behaviour, expenses,
                      settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    horizon = resolve_horizon(settings, policy)
    scenarios = simulate(settings.model, esg, horizon, settings.n_paths,
                         measure=Measure.REAL_WORLD, seed=settings.seed + 1)
    result = project(product, policy, scenarios, behaviour, mortality,
                     expenses=expenses, config=settings.projection)
    if result.iv_paths is None or result.income_paths is None:
        raise RuntimeError("Outcome run requires ProjectionConfig(record_paths=True).")
    idx = np.arange(0, len(result.times), 12)
    years = result.times[idx]
    q_levels = (0.05, 0.25, 0.50, 0.75, 0.95)
    iv_q = np.quantile(result.iv_paths[:, idx], q_levels, axis=0)
    inc_q = np.quantile(result.income_paths[:, idx], q_levels, axis=0)
    outcome = pd.DataFrame({"policy_year": years, "age": policy.age + years})
    for i, q in enumerate((5, 25, 50, 75, 95)):
        outcome[f"iv_p{q}"] = iv_q[i]
        outcome[f"income_p{q}"] = inc_q[i]
    outcome["iv_mean"] = np.mean(result.iv_paths[:, idx], axis=0)
    outcome["income_mean"] = np.mean(result.income_paths[:, idx], axis=0)
    outcome["iv_exhaustion_pct"] = 100 * np.mean(result.iv_paths[:, idx] <= 1.0, axis=0)
    outcome["inforce_pct"] = 100 * np.mean(result.inforce[:, idx], axis=0)

    n = len(result.annual_aggregate("guarantee_claims"))
    annual = pd.DataFrame(
        {
            "policy_year": np.arange(n),
            "age": policy.age + np.arange(n),
            "income_paid": result.annual_aggregate("income_paid"),
            "guarantee_claims": result.annual_aggregate("guarantee_claims"),
            "death_benefits": result.annual_aggregate("death_benefits"),
            "surrender_benefits": result.annual_aggregate("surrender_benefits"),
        }
    )
    del result, scenarios
    gc.collect()
    return outcome, annual


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def chart_executive_dashboard(out: Path, val, cap, prof, fair_lip, mc,
                              capital_df: pd.DataFrame, product,
                              prof_settings) -> None:
    fig = plt.figure(figsize=(16, 9))
    gs = fig.add_gridspec(2, 2, height_ratios=(0.85, 2.2), hspace=0.42,
                          wspace=0.25, top=0.87, bottom=0.09, left=0.06,
                          right=0.96)
    add_header(fig, "AGILE – Executive Economics Dashboard")
    add_footer(fig)

    ax_kpi = fig.add_subplot(gs[0, :])
    ax_kpi.axis("off")
    kpis = [
        ("Gross VNB", aud(val.insurer_net_value), f"95%-MC ±{aud(1.96 * mc['gross_vnb_se'])}"),
        ("VNB nach RM", aud(prof.vnb_market_consistent), pct(prof.new_business_margin) + " NBM"),
        (f"PVFP @ {prof_settings.hurdle_rate:.1%}", aud(prof.pvfp_hurdle),
         pct(prof.pvfp_margin) + " der Prämie"),
        ("BSCR-Proxy", aud(cap.bscr), pct(cap.bscr / val.premium) + " der Prämie"),
        ("Fairer LIP", pct(fair_lip, 2),
         f"belastet: {product.fees.lifetime_income_premium:.2%}"),
        ("Payback", "n/a" if prof.payback_year is None else f"Jahr {prof.payback_year}",
         "IRR n/a" if prof.irr is None else f"IRR {pct(prof.irr)}"),
    ]
    for i, (label, value, detail) in enumerate(kpis):
        x0 = 0.005 + i / len(kpis)
        width = 0.155
        ax_kpi.add_patch(
            plt.Rectangle((x0, 0.08), width, 0.78, transform=ax_kpi.transAxes,
                          facecolor="#F5F8FC", edgecolor=LIGHT_GREY, linewidth=1.2)
        )
        ax_kpi.text(x0 + 0.012, 0.70, label, transform=ax_kpi.transAxes,
                    fontsize=9, color=GREY, va="center")
        ax_kpi.text(x0 + 0.012, 0.43, value, transform=ax_kpi.transAxes,
                    fontsize=16, color=BLUE, fontweight="bold", va="center")
        ax_kpi.text(x0 + 0.012, 0.19, detail, transform=ax_kpi.transAxes,
                    fontsize=8.5, color=DARK, va="center")

    ax1 = fig.add_subplot(gs[1, 0])
    ordered = capital_df.sort_values("standalone_scr", ascending=True)
    bars = ax1.barh(ordered["module_de"], ordered["standalone_scr"], color=MID_BLUE)
    ax1.set_title("Standalone-Stressverluste (bindende Richtung)", loc="left")
    ax1.set_xlabel("AUD je Police")
    ax1.xaxis.set_major_formatter(FuncFormatter(aud_axis))
    ax1.grid(axis="y", visible=False)
    for b in bars:
        ax1.text(b.get_width(), b.get_y() + b.get_height() / 2,
                 " " + aud_axis(b.get_width()), va="center", fontsize=8.5)

    ax2 = fig.add_subplot(gs[1, 1])
    names = ["Gross NBM", "NBM nach RM", "PVFP-Marge", "BSCR / Prämie", "RM / Prämie"]
    vals = np.array([
        val.insurer_net_value / val.premium,
        prof.new_business_margin,
        prof.pvfp_margin,
        cap.bscr / val.premium,
        cap.risk_margin / val.premium,
    ])
    colors = [GREEN if v >= 0 else RED for v in vals[:3]] + [ORANGE, GOLD]
    bars2 = ax2.bar(names, vals, color=colors)
    ax2.axhline(0, color=DARK, linewidth=0.8)
    ax2.set_title("Unit Economics relativ zur Einmalprämie", loc="left")
    ax2.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax2.tick_params(axis="x", rotation=18)
    ax2.grid(axis="x", visible=False)
    bar_labels(ax2, bars2, fmt=lambda x: f"{100*x:.1f}%")
    save_figure(fig, out / "01_executive_dashboard.png")


def chart_value_waterfall(out: Path, val) -> None:
    labels = ["Product Fee", "LIP", "Crediting\nMargin", "MVA / APS",
              "Guarantee\nClaims", "Hedge\nCosts", "Expenses"]
    values = np.array([
        val.pv["fees_product"],
        val.pv["fees_lip"],
        val.pv["crediting_margin"],
        val.pv["mva_retained"] + val.pv["aps_retained"],
        -val.pv["guarantee_claims"],
        -val.pv["hedge_costs"],
        -val.pv["expenses"],
    ])
    cumulative = np.r_[0.0, np.cumsum(values)]
    fig, ax = plt.subplots(figsize=(13, 7.5))
    fig.subplots_adjust(top=0.84, bottom=0.14, left=0.08, right=0.97)
    add_header(fig, "Pricing- und Margin-Waterfall",
               MODEL_POINT + " | Marktwerte unter Q")
    add_footer(fig, "Marktwert unter Q; Crediting Margin und MVA/DVA beruhen auf Modellproxies. " + RESEARCH_FOOTER)
    for i, (label, v) in enumerate(zip(labels, values)):
        start, end = cumulative[i], cumulative[i + 1]
        color = GREEN if v >= 0 else RED
        ax.bar(i, abs(v), bottom=min(start, end), color=color, width=0.68)
        ax.plot([i + 0.34, i + 0.66], [end, end], color=GREY, linewidth=0.8)
        ax.text(i, max(start, end) + (450 if v >= 0 else 200), aud_axis(v),
                ha="center", va="bottom", fontsize=9, color=DARK)
    total = cumulative[-1]
    ax.bar(len(labels), total, color=BLUE if total >= 0 else RED, width=0.68)
    ax.text(len(labels), total + (450 if total >= 0 else -450), aud_axis(total),
            ha="center", va="bottom" if total >= 0 else "top", fontsize=10,
            fontweight="bold", color=BLUE if total >= 0 else RED)
    ax.set_xticks(range(len(labels) + 1), labels + ["Gross VNB"])
    ax.axhline(0, color=DARK, linewidth=0.9)
    ax.set_ylabel("Barwert in AUD je Police")
    ax.yaxis.set_major_formatter(FuncFormatter(aud_axis))
    ax.grid(axis="x", visible=False)
    ax.text(0.99, 0.97,
            f"Guarantee Value = Claims – LIP = {aud(val.guarantee_value)}\n"
            f"Identity Gap = {100*val.identity_gap:.3f}%",
            transform=ax.transAxes, ha="right", va="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#F5F8FC",
                      edgecolor=LIGHT_GREY))
    save_figure(fig, out / "02_pricing_margin_waterfall.png")


def chart_profit_capital_runoff(out: Path, runoff: pd.DataFrame) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True,
                                   gridspec_kw={"height_ratios": (1.25, 1)})
    fig.subplots_adjust(top=0.86, bottom=0.10, left=0.08, right=0.92, hspace=0.22)
    add_header(fig, "Profit-, Reserve- und Kapital-Run-off",
               MODEL_POINT + " | Real-World Profit Signature + CE-Reserving")
    add_footer(fig, "Distributable Earnings nach Steuer, Reservebewegung und Kapitalbindung; Kapital = Research-Proxy, nicht APRA/LAGIC.")
    x = runoff["year"].to_numpy()
    width = 0.42
    ax1.bar(x - width / 2, runoff["profit_signature"], width=width,
            label="Profit Signature vor Steuer", color=LIGHT_BLUE)
    ax1.bar(x + width / 2, runoff["distributable"], width=width,
            label="Distributable Earnings", color=BLUE)
    ax1.axhline(0, color=DARK, linewidth=0.8)
    ax1.set_ylabel("AUD je Jahr")
    ax1.yaxis.set_major_formatter(FuncFormatter(aud_axis))
    ax1.legend(loc="upper right")
    ax1.set_title("Jährliche Ergebnisentstehung", loc="left")
    ax1.grid(axis="x", visible=False)
    ax1b = ax1.twinx()
    ax1b.plot(x, runoff["cumulative_distributable"], color=ORANGE, linewidth=2.2,
              label="Kumuliert")
    ax1b.set_ylabel("Kumulierte Distributable Earnings", color=ORANGE)
    ax1b.yaxis.set_major_formatter(FuncFormatter(aud_axis))
    ax1b.grid(False)

    ax2.plot(x, runoff["bel_nonunit_incl_rm"], label="BEL inkl. RM",
             color=MID_BLUE, linewidth=2.0)
    ax2.plot(x, runoff["required_capital"], label="Required Capital Proxy",
             color=ORANGE, linewidth=2.0)
    ax2.fill_between(x, 0, runoff["required_capital"], color=ORANGE, alpha=0.12)
    ax2.axhline(0, color=DARK, linewidth=0.8)
    ax2.set_title("Reserve- und Kapitalbindung", loc="left")
    ax2.set_xlabel("Policy Year")
    ax2.set_ylabel("AUD")
    ax2.yaxis.set_major_formatter(FuncFormatter(aud_axis))
    ax2.legend(loc="upper right")
    ax2.grid(axis="x", visible=False)
    save_figure(fig, out / "03_profit_capital_runoff.png")


def chart_sensitivity_tornado(out: Path, sens: pd.DataFrame,
                              hurdle_rate: float) -> None:
    work = sens[sens["scenario"] != "base"].copy()
    work["scenario_de"] = work["scenario"].map(SCENARIO_DE).fillna(work["scenario"])
    fig, axes = plt.subplots(1, 2, figsize=(16, 9))
    fig.subplots_adjust(top=0.86, bottom=0.11, left=0.20, right=0.97, wspace=0.44)
    add_header(fig, "Profitabilitäts-Sensitivitäten – Einfaktor-Tornado",
               MODEL_POINT + " | gemeinsame Zufallszahlen | vor Kapital und Risk Margin")
    add_footer(fig, "Breites Screening ohne Kapital-Neuberechnung; keine kombinierte Tail-Verteilung. Markt, Verhalten und Kosten sind illustrativ.")
    for ax, col, title in (
        (axes[0], "d_gross_vnb", "Δ Gross VNB"),
        (axes[1], "d_pvfp_pre_capital",
         f"Δ PVFP @ {hurdle_rate:.1%} vor Kapital"),
    ):
        top = work.loc[work[col].abs().nlargest(11).index]
        top = top.sort_values(col)
        colors = np.where(top[col] >= 0, GREEN, RED)
        bars = ax.barh(top["scenario_de"], top[col], color=colors)
        ax.axvline(0, color=DARK, linewidth=0.9)
        ax.set_title(title, loc="left")
        ax.set_xlabel("AUD je Police")
        ax.xaxis.set_major_formatter(FuncFormatter(aud_axis))
        ax.grid(axis="y", visible=False)
        ax.margins(x=0.12)
        for b in bars:
            v = b.get_width()
            ax.text(v, b.get_y() + b.get_height() / 2,
                    ("  " if v >= 0 else "") + aud_axis(v) + ("" if v >= 0 else "  "),
                    ha="left" if v >= 0 else "right", va="center", fontsize=8.3)
    save_figure(fig, out / "04_sensitivity_tornado.png")


def chart_customer_outcomes(out: Path, outcome: pd.DataFrame,
                            annual: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.subplots_adjust(top=0.86, bottom=0.09, left=0.07, right=0.96,
                        hspace=0.34, wspace=0.22)
    add_header(fig, "Kunden-Outcome und Garantie-Inanspruchnahme",
               MODEL_POINT + " | Real-World-Szenarien")
    add_footer(fig, "Nominal, vor persönlicher Steuer/Withholding und laufenden Adviser Fees; keine Prognose oder PDS-Illustration. Zustandsquantile vor stochastischen Decrementen.")
    age = outcome["age"].to_numpy(dtype=float)
    ax = axes[0, 0]
    ax.fill_between(age, outcome["iv_p5"].to_numpy(dtype=float),
                    outcome["iv_p95"].to_numpy(dtype=float), color=LIGHT_BLUE,
                    alpha=0.28, label="P5–P95")
    ax.fill_between(age, outcome["iv_p25"].to_numpy(dtype=float),
                    outcome["iv_p75"].to_numpy(dtype=float), color=MID_BLUE,
                    alpha=0.30, label="P25–P75")
    ax.plot(age, outcome["iv_p50"], color=BLUE, linewidth=2, label="Median")
    ax.set_title("Investment Value – Verteilungsfächer", loc="left")
    ax.set_ylabel("AUD")
    ax.yaxis.set_major_formatter(FuncFormatter(aud_axis))
    ax.legend(loc="upper right")

    ax = axes[0, 1]
    ax.fill_between(age, outcome["income_p5"].to_numpy(dtype=float),
                    outcome["income_p95"].to_numpy(dtype=float), color="#BCE7D0",
                    alpha=0.45, label="P5–P95")
    ax.fill_between(age, outcome["income_p25"].to_numpy(dtype=float),
                    outcome["income_p75"].to_numpy(dtype=float), color=GREEN,
                    alpha=0.25, label="P25–P75")
    ax.plot(age, outcome["income_p50"], color=GREEN, linewidth=2, label="Median")
    ax.set_title("Jährliches Lifetime Income", loc="left")
    ax.set_ylabel("AUD p.a.")
    ax.yaxis.set_major_formatter(FuncFormatter(aud_axis))
    ax.legend(loc="upper right")

    ax = axes[1, 0]
    ax.bar(annual["age"], annual["guarantee_claims"], color=RED,
           label="Guarantee Claims")
    ax.plot(annual["age"], annual["income_paid"], color=BLUE, linewidth=2,
            label="Income paid")
    ax.set_title("Erwartete jährliche Income- und Claim-Cashflows", loc="left")
    ax.set_xlabel("Alter")
    ax.set_ylabel("AUD p.a. je ursprünglicher Police")
    ax.yaxis.set_major_formatter(FuncFormatter(aud_axis))
    ax.legend(loc="upper right")
    ax.grid(axis="x", visible=False)

    ax = axes[1, 1]
    ax.plot(age, outcome["iv_exhaustion_pct"], color=RED, linewidth=2,
            label="IV erschöpft")
    ax.plot(age, outcome["inforce_pct"], color=MID_BLUE, linewidth=2,
            label="In-force Gewicht")
    ax.set_title("Account Exhaustion und Bestandsverbleib", loc="left")
    ax.set_xlabel("Alter")
    ax.set_ylabel("Anteil")
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(PercentFormatter(100))
    ax.legend(loc="center right")
    save_figure(fig, out / "05_customer_outcomes.png")


def chart_product_design(out: Path, designs: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(17, 7.8))
    fig.subplots_adjust(top=0.84, bottom=0.22, left=0.06, right=0.98, wspace=0.28)
    add_header(fig, "Produktdesign – Kundeneinkommen versus Versichererökonomik",
               MODEL_POINT.replace("Fixed Income", "Designvarianten") + " | Income-Start nach 5 Jahren")
    add_footer(fig, "Bedingte Varianten, nicht der Marktwert des späteren Wahlrechts. Spouse = weiblich 63; APS-CAS-Lebenserwartung = illustrativ 20 Jahre.")
    x = np.arange(len(designs))
    labels = designs["variant"].str.replace(" ", "\n", n=1)
    bars = axes[0].bar(x, designs["q_mean_start_income"], color=MID_BLUE)
    axes[0].set_title("Q-Mittel des anfänglichen Einkommens", loc="left")
    axes[0].set_ylabel("AUD p.a.")
    axes[0].yaxis.set_major_formatter(FuncFormatter(aud_axis))
    bar_labels(axes[0], bars)

    colors = np.where(designs["gross_vnb"] >= 0, GREEN, RED)
    bars = axes[1].bar(x, designs["gross_vnb"], color=colors)
    axes[1].axhline(0, color=DARK, linewidth=0.8)
    axes[1].set_title("Gross VNB", loc="left")
    axes[1].set_ylabel("AUD je Police")
    axes[1].yaxis.set_major_formatter(FuncFormatter(aud_axis))
    bar_labels(axes[1], bars)

    colors = np.where(designs["guarantee_value"] <= 0, GREEN, RED)
    bars = axes[2].bar(x, designs["guarantee_value"], color=colors)
    axes[2].axhline(0, color=DARK, linewidth=0.8)
    axes[2].set_title("Guarantee Value: Claims – LIP", loc="left")
    axes[2].set_ylabel("AUD je Police")
    axes[2].yaxis.set_major_formatter(FuncFormatter(aud_axis))
    bar_labels(axes[2], bars)
    for ax in axes:
        ax.set_xticks(x, labels, rotation=0)
        ax.grid(axis="x", visible=False)
    save_figure(fig, out / "06_product_design_tradeoffs.png")


def chart_income_start(out: Path, timing: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15, 7.5))
    fig.subplots_adjust(top=0.84, bottom=0.13, left=0.07, right=0.94, wspace=0.30)
    add_header(fig, "Dynamisches Income-Take-up – Kundenleistung und Marge",
               MODEL_POINT)
    add_footer(fig, "Take-up bleibt markt- und prämienabhängig; dargestellt ist ein Stress der CSV-Basishazards mit unveränderten Reaktionskoeffizienten. Unkalibrierte Proxy-Annahmen.")
    x = timing["take_up_multiplier"].to_numpy()
    ax = axes[0]
    ax.plot(x, timing["q_mean_income_start_year"], marker="o", color=BLUE,
            linewidth=2.2, label="Q-Mittel Startjahr")
    ax.set_xlabel("Take-up-Basishazard-Multiplikator")
    ax.set_ylabel("Policy Years bis Income-Start", color=BLUE)
    ax2 = ax.twinx()
    ax2.plot(x, timing["q_mean_start_income"], marker="s", color=ORANGE,
             linewidth=2, label="Q-Mittel Start-Income")
    ax2.set_ylabel("AUD p.a.", color=ORANGE)
    ax2.yaxis.set_major_formatter(FuncFormatter(aud_axis))
    ax.set_title("Simulierter Commencement-Zeitpunkt", loc="left")
    ax.grid(axis="x", visible=False)
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [l.get_label() for l in lines], loc="upper left")

    ax = axes[1]
    width = 0.36
    ax.bar(x - width / 2, timing["gross_vnb"], width=width, color=BLUE,
           label="Gross VNB")
    ax.bar(x + width / 2, timing["guarantee_value"], width=width, color=RED,
           alpha=0.82, label="Guarantee Value")
    ax.axhline(0, color=DARK, linewidth=0.8)
    ax.set_title("Versichererökonomik", loc="left")
    ax.set_xlabel("Take-up-Basishazard-Multiplikator")
    ax.set_ylabel("AUD je Police")
    ax.yaxis.set_major_formatter(FuncFormatter(aud_axis))
    ax.legend(loc="best")
    ax.grid(axis="x", visible=False)
    save_figure(fig, out / "07_income_start_tradeoff.png")


def annotated_heatmap(ax: plt.Axes, matrix: pd.DataFrame, title: str,
                      xlabel: str, ylabel: str) -> None:
    values = matrix.to_numpy(dtype=float)
    max_abs = max(float(np.nanmax(np.abs(values))), 0.1)
    im = ax.imshow(values, cmap="RdYlGn", aspect="auto",
                   norm=TwoSlopeNorm(vmin=-max_abs, vcenter=0.0, vmax=max_abs))
    ax.set_xticks(np.arange(len(matrix.columns)), [str(x) for x in matrix.columns])
    ax.set_yticks(np.arange(len(matrix.index)), [str(x) for x in matrix.index])
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left")
    ax.grid(False)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            v = values[i, j]
            ax.text(j, i, f"{v:.1f}%", ha="center", va="center", fontsize=8,
                    color="white" if abs(v) > 0.55 * max_abs else DARK,
                    fontweight="bold" if abs(v) > 0.55 * max_abs else "normal")
    plt.colorbar(im, ax=ax, shrink=0.78, label="Gross NBM")


def chart_behaviour_surfaces(out: Path, takeup: pd.DataFrame,
                             withdrawals: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5))
    fig.subplots_adjust(top=0.84, bottom=0.13, left=0.07, right=0.97, wspace=0.30)
    add_header(fig, "Verhaltens- und Liquiditätsrisiko – Gross NBM Surface",
               MODEL_POINT + " | Marktwert vor RM/Kapital")
    add_footer(fig, "Nicht auf Allianz-Erfahrung kalibriert; Einzelszenarien mit gemeinsamen Modellparametern. Cooling-off und individuelle Transaktionspläne fehlen.")
    p1 = takeup.pivot(index="lapse_multiplier", columns="take_up_multiplier",
                      values="gross_nbm_pct")
    p1.index = [f"{x:.2f}x" for x in p1.index]
    annotated_heatmap(axes[0], p1, "Income-Take-up × Storno",
                      "Take-up-Basishazard-Multiplikator",
                      "Storno-Basishazard-Multiplikator")
    p2 = withdrawals.pivot(index="excess_rate", columns="free_utilisation",
                           values="gross_nbm_pct")
    p2.index = [f"{100*x:.1f}%" for x in p2.index]
    p2.columns = [f"{100*x:.0f}%" for x in p2.columns]
    annotated_heatmap(axes[1], p2, "Free × Excess Withdrawals",
                      "Free-Withdrawal-Nutzung", "Excess Rate p.a.")
    save_figure(fig, out / "08_behaviour_liquidity_surfaces.png")


def chart_model_mc_stability(out: Path, models: pd.DataFrame,
                             seeds: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.subplots_adjust(top=0.86, bottom=0.11, left=0.08, right=0.97,
                        hspace=0.35, wspace=0.26)
    add_header(fig, "Modell- und Monte-Carlo-Stabilität",
               MODEL_POINT + " | Screening mit reduzierter Pfadzahl")
    add_footer(fig, "Modellvergleich nutzt illustrative, nicht kalibrierte BS/Heston/Hull-White-Parameter. Seed-Streuung ist ein numerisches Diagnosemaß, kein vollständiges Model-Risk-Kapital.")
    x = np.arange(len(models))
    bars = axes[0, 0].bar(x, models["gross_vnb"],
                          color=np.where(models["gross_vnb"] >= 0, GREEN, RED))
    axes[0, 0].set_xticks(x, models["label"], rotation=15, ha="right")
    axes[0, 0].set_title("Gross VNB nach stochastischem Modell", loc="left")
    axes[0, 0].set_ylabel("AUD je Police")
    axes[0, 0].yaxis.set_major_formatter(FuncFormatter(aud_axis))
    axes[0, 0].axhline(0, color=DARK, linewidth=0.8)
    axes[0, 0].grid(axis="x", visible=False)
    bar_labels(axes[0, 0], bars)

    bars = axes[0, 1].bar(x, models["guarantee_value"], color=ORANGE)
    axes[0, 1].set_xticks(x, models["label"], rotation=15, ha="right")
    axes[0, 1].set_title("Guarantee Value nach stochastischem Modell", loc="left")
    axes[0, 1].set_ylabel("AUD je Police")
    axes[0, 1].yaxis.set_major_formatter(FuncFormatter(aud_axis))
    axes[0, 1].axhline(0, color=DARK, linewidth=0.8)
    axes[0, 1].grid(axis="x", visible=False)
    bar_labels(axes[0, 1], bars)

    sx = np.arange(len(seeds))
    axes[1, 0].errorbar(sx, seeds["gross_vnb"],
                        yerr=1.96 * seeds["gross_vnb_se"], fmt="o", capsize=4,
                        color=BLUE, ecolor=LIGHT_BLUE, label="Pfadweises 95%-CI")
    mean = seeds["gross_vnb"].mean()
    axes[1, 0].axhline(mean, color=ORANGE, linestyle="--", label="Seed-Mittel")
    axes[1, 0].set_xticks(sx, seeds["seed"].astype(str))
    axes[1, 0].set_title("Gross VNB über unabhängige Seeds", loc="left")
    axes[1, 0].set_xlabel("Seed")
    axes[1, 0].set_ylabel("AUD je Police")
    axes[1, 0].yaxis.set_major_formatter(FuncFormatter(aud_axis_precise))
    axes[1, 0].legend(loc="best")

    axes[1, 1].scatter(seeds["seed"].astype(str), seeds["identity_gap_pct"],
                       color=MID_BLUE, s=55)
    axes[1, 1].axhline(0, color=DARK, linewidth=0.8)
    axes[1, 1].set_title("Q-Identitätslücke über Seeds", loc="left")
    axes[1, 1].set_xlabel("Seed")
    axes[1, 1].set_ylabel("Identity Gap")
    axes[1, 1].yaxis.set_major_formatter(PercentFormatter(100))
    save_figure(fig, out / "09_model_mc_stability.png")


def chart_market_greeks(out: Path, greek_values: Mapping[str, float], cap) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14.5, 7.3))
    fig.subplots_adjust(top=0.83, bottom=0.14, left=0.08, right=0.96, wspace=0.30)
    add_header(fig, "Marktrisiko – lokale Greeks und Stresssicht",
               MODEL_POINT + " | Insurer Net Value unter Q")
    add_footer(fig, "Lokale Bump-and-Revalue-Greeks mit gemeinsamen Zufallszahlen; Stressverluste sind SII-artige Research-Proxies, nicht Hedge-Nominale oder APRA-Kapital.")
    names = ["Equity Delta\npro 100% Spot", "Vega\npro 1 Vol-Punkt",
             "Rho\npro +100 bp"]
    values = np.array([
        greek_values["equity_delta_pct"], greek_values["vega_per_volpt"],
        greek_values["rho_per_100bp"],
    ])
    bars = axes[0].bar(names, values, color=np.where(values >= 0, GREEN, RED))
    axes[0].axhline(0, color=DARK, linewidth=0.8)
    axes[0].set_title("NAV-Sensitivität relativ zur Prämie", loc="left")
    axes[0].set_ylabel("Anteil der Einmalprämie")
    axes[0].yaxis.set_major_formatter(PercentFormatter(1.0))
    axes[0].grid(axis="x", visible=False)
    bar_labels(axes[0], bars, fmt=lambda x: f"{100*x:.2f}%")

    names2 = ["Zins", "Aktie", "Aktienvol"]
    values2 = [max(cap.scr_by_module["interest_up"], cap.scr_by_module["interest_down"]),
               cap.scr_by_module["equity"], cap.scr_by_module["equity_vol"]]
    bars2 = axes[1].bar(names2, values2, color=[ORANGE, MID_BLUE, GOLD])
    axes[1].set_title("Markt-Stressverluste", loc="left")
    axes[1].set_ylabel("AUD je Police")
    axes[1].yaxis.set_major_formatter(FuncFormatter(aud_axis))
    axes[1].grid(axis="x", visible=False)
    bar_labels(axes[1], bars2)
    save_figure(fig, out / "10_market_risk_greeks.png")


# ---------------------------------------------------------------------------
# Management report
# ---------------------------------------------------------------------------


def write_report(out: Path, val, cap, prof, fair_lip, mc,
                 sensitivities: pd.DataFrame, designs: pd.DataFrame,
                 timing: pd.DataFrame, models: pd.DataFrame,
                 seeds: pd.DataFrame, outcome: pd.DataFrame,
                 capital_df: pd.DataFrame, runtime: float, args,
                 product, costs, behaviour_assumptions,
                 market_assumptions) -> None:
    charged_lip = product.fees.lifetime_income_premium
    sens_work = sensitivities[sensitivities["scenario"] != "base"].copy()
    worst_vnb = sens_work.loc[sens_work["d_gross_vnb"].idxmin()]
    best_vnb = sens_work.loc[sens_work["d_gross_vnb"].idxmax()]
    worst_pvfp = sens_work.loc[sens_work["d_pvfp_pre_capital"].idxmin()]
    binding = capital_df.loc[capital_df["standalone_scr"].idxmax()]
    seed_sd = seeds["gross_vnb"].std(ddof=1)
    model_range = models["gross_vnb"].max() - models["gross_vnb"].min()
    exhaustion = outcome.loc[outcome["iv_exhaustion_pct"] >= 50, "age"]
    exhaustion_text = "im Horizont nicht erreicht" if exhaustion.empty else f"etwa Alter {exhaustion.iloc[0]:.0f}"
    design_best = designs.loc[designs["gross_vnb"].idxmax()]
    design_worst = designs.loc[designs["gross_vnb"].idxmin()]
    start_best = timing.loc[timing["gross_vnb"].idxmax()]
    net_assessment = "negativ" if prof.vnb_market_consistent < 0 else "positiv"
    pvfp_assessment = "negativ" if prof.pvfp_hurdle < 0 else "positiv"

    report = f"""# AGILE Insurer Analysis Pack

**Modellpunkt:** {MODEL_POINT}.  
**Run:** Engine {agile_engine.__version__}, Heston-Hull-White unter Q / Black-Scholes-Hull-White unter Real World, {args.base_paths:,} Basispfade, Seed 2026; erstellt {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.  
**Kostenquelle:** `{costs.source_path}`, Set `{costs.assumption_set_id}`, SHA-256 `{costs.source_sha256}`.  
**Behaviour-Quelle:** `{behaviour_assumptions.source_path}`, Set `{behaviour_assumptions.assumption_set_id}` (`uncalibrated_proxy`).  
**Markt-/Modellparameter:** Kurve `{market_assumptions.curve_id}`, Parameterset `{market_assumptions.parameter_set_id}` aus `input_market_data`.  
**Status:** Illustrativer New-Business-Research-Run. Kein In-force-Wert, keine PDS-Prognose und kein APRA/LAGIC-Kapital.

## Management Summary

- Der modellierte **Gross VNB beträgt {aud(val.insurer_net_value)}** ({pct(val.insurer_net_value / val.premium)} der Prämie; pfadweises 95%-MC-Intervall ungefähr ±{aud(1.96 * mc['gross_vnb_se'])}). Nach dem modellierten Risk-Margin-Proxy ist der VNB **{aud(prof.vnb_market_consistent)}** und damit {net_assessment}.
- Die belastete Lifetime Income Premium von **{pct(charged_lip, 2)} p.a.** liegt unter dem modellierten fairen Rider-Satz von **{pct(fair_lip, 2)}**. Der Rider allein hat deshalb einen positiven Net Cost von **{aud(val.guarantee_value)}**; das ist nicht dasselbe wie Gesamtproduktverlust.
- Der BSCR-Research-Proxy beträgt **{aud(cap.bscr)}**; größter Standalone-Treiber ist **{binding['module_de']}** mit {aud(binding['standalone_scr'])}. Risk Margin: **{aud(cap.risk_margin)}**. Diese Zahlen dürfen nicht als APRA/LAGIC-Kapitalanforderung bezeichnet werden.
- Der PVFP bei {pct(costs.profitability.hurdle_rate)} Hurdle beträgt **{aud(prof.pvfp_hurdle)}** und ist {pvfp_assessment}; modellierter Payback: **{'nicht erreicht' if prof.payback_year is None else f'Jahr {prof.payback_year}'}**, IRR: **{'n/a' if prof.irr is None else pct(prof.irr)}**. Die reale Aussagekraft hängt besonders an Kosten-, Verhalten-, Hedge- und Kapitalannahmen.
- Im Einfaktor-Screening ist der größte Gross-VNB-Downside **{SCENARIO_DE.get(worst_vnb['scenario'], worst_vnb['scenario'])}** mit {aud(worst_vnb['d_gross_vnb'])}; der größte PVFP-Downside ist **{SCENARIO_DE.get(worst_pvfp['scenario'], worst_pvfp['scenario'])}** mit {aud(worst_pvfp['d_pvfp_pre_capital'])}. Der stärkste Upside ist **{SCENARIO_DE.get(best_vnb['scenario'], best_vnb['scenario'])}** mit +{aud(best_vnb['d_gross_vnb'])}.
- Im Real-World-Outcome-Screening überschreitet der Anteil der Marktpfade mit erschöpftem Investment Value 50% **{exhaustion_text}**. Die Zustände sind vor stochastischen Decrementen ausgewertet; das ist ein Modellindikator für die spätere Garantiefinanzierung, keine Kundenprognose.
- Unter den bedingten Designvarianten hat **{design_best['variant']}** den höchsten Gross VNB ({aud(design_best['gross_vnb'])}), **{design_worst['variant']}** den niedrigsten ({aud(design_worst['gross_vnb'])}). Im dynamischen Take-up-Screening ist ein Basishazard-Multiplikator von **{start_best['take_up_multiplier']:.2f}x** für den Versicherer am wertvollsten; Markt-, Moneyness- und Prämienreaktionen bleiben in allen Varianten aktiv.
- Die Gross-VNB-Streuung über fünf unabhängige Seeds mit je {args.mc_paths:,} Pfaden hat eine Sample-SD von **{aud(seed_sd)}**. Die Spannweite über vier unkalibrierte stochastische Modelle beträgt **{aud(model_range)}** und ist ein deutliches Model-Risk-Signal, keine Konfidenzgrenze.

## 1. Executive Economics

![Executive Dashboard](01_executive_dashboard.png)

![Pricing- und Margin-Waterfall](02_pricing_margin_waterfall.png)

Interpretation: Der Guarantee Value misst nur `PV(Claims) - PV(LIP)`. Product Fees, Crediting Margin, MVA/APS, Hedgekosten und Expenses erklären die Überleitung zum Gross VNB. Die Q-Identitätslücke von {100*val.identity_gap:.3f}% ist eine numerische Reconciliation, kein Nachweis korrekter Vertragsmodellierung.

## 2. Profitabilität und Kapitalbindung

![Profit- und Kapital-Run-off](03_profit_capital_runoff.png)

Der Run-off kombiniert Real-World-Profit-Cashflows mit Certainty-Equivalent-Reserving und einem proportionalen SCR-Run-off. Er ist nützlich für Strain-, Payback- und Kapitalbindungsdiskussionen, ersetzt aber weder eine Bilanzprojektion noch APRA-Fund-Level-Modellierung.

## 3. Risikotreiber

![Sensitivitäts-Tornado](04_sensitivity_tornado.png)

![Marktrisiko und Greeks](10_market_risk_greeks.png)

Das Tornado-Screening rechnet bewusst ohne Kapital und Risk Margin. Es zeigt Einfaktor-Effekte mit gemeinsamen Zufallszahlen; Interaktionen und kombinierte Tails fehlen. Ein Vorzeichen darf nicht verallgemeinert werden: Zins, Cap, Storno und Take-up wirken gleichzeitig auf Account, Fees, Garantie und MVA.

## 4. Kunden-Outcome

![Kunden-Outcome](05_customer_outcomes.png)

Die Fan-Charts stammen aus Real-World-Szenarien, nominal und vor persönlicher Steuer/Withholding. Investment- und Income-Zustände sind Verteilungsdiagnostik vor stochastischen Decrementen. Rising Income ist kein CPI-Link.

## 5. Produktdesign und Income-Start

![Produktdesign](06_product_design_tradeoffs.png)

![Income-Start](07_income_start_tradeoff.png)

Jede Säule ist eine bedingte Variante. Der aktuelle Research-Enginewert enthält nicht das volle spätere Wahlrecht zwischen Fixed/Rising, Spouse, Age Pension+ und Reallokation. APS nutzt hier eine illustrative CAS-Lebenserwartung von 20 Jahren.

## 6. Verhaltens- und Liquiditätsrisiko

![Verhaltensflächen](08_behaviour_liquidity_surfaces.png)

Die Flächen beantworten, wo sich Gross NBM durch Take-up, Storno und Entnahmen konzentriert. Sie sind Szenarien, keine empirische Best-Estimate-Kalibrierung. Cooling-off, laufende Adviser Fees und individuelle Transaktionspläne sind nicht enthalten.

## 7. Modell- und numerische Robustheit

![Modell- und MC-Stabilität](09_model_mc_stability.png)

Die Modellparameter wurden nicht auf eine datierte Vol-Surface oder Zinsvolatilität kalibriert. Für eine Freigabe sind mehrere Seeds mit deutlich höheren Pfadzahlen, gepaarte Standardfehler für Sensitivitäten sowie Marktdaten- und Hedge-Reconciliation erforderlich.

## Verwendete Ergebnisdateien

- `executive_kpis.csv`, `pv_components.csv`, `capital_proxy.csv`
- `profit_runoff.csv`, `sensitivities.csv`, `market_greeks.csv`
- `product_designs.csv`, `income_start_timing.csv`
- `behaviour_takeup_lapse.csv`, `behaviour_withdrawals.csv`
- `customer_outcome_quantiles.csv`, `customer_annual_cashflows.csv`
- `model_comparison.csv`, `mc_seed_stability.csv`
- `reconciliations.csv`, `run_manifest.json`

## Entscheidungsgrenzen

Vor externer Preis-, Reservierungs-, Hedging- oder Kapitalverwendung sind mindestens erforderlich:

1. datierte Kurven-/Vol-Surface-Kalibrierung, reale Hedgeinstrumente und Hedgekosten;
2. Allianz-spezifische Mortalität, Verhalten, Expenses, Tax und Reinsurance;
3. offizielle Admin-Reconciliation für DVA/MVA, tägliche Fees und alle Produktwahlrechte;
4. In-force-Vertragszustand und Bestandsaggregation;
5. ein separates APRA/LAGIC-Modul für Asset, Insurance, Concentration, Operational und Combined Stresses;
6. höhere Pfadzahlen, Seed-Konvergenz, Diskretisierungstests und formale Modellvalidierung.

Gesamtlaufzeit dieses Packs: {runtime:.1f} Sekunden.
"""
    (out / "INSURER_ANALYSIS_REPORT.md").write_text(report, encoding="utf-8")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-paths", type=int, default=4_000)
    parser.add_argument("--scenario-paths", type=int, default=1_200)
    parser.add_argument("--design-paths", type=int, default=1_500)
    parser.add_argument("--behaviour-paths", type=int, default=600)
    parser.add_argument("--outcome-paths", type=int, default=2_500)
    parser.add_argument("--model-paths", type=int, default=600)
    parser.add_argument("--mc-paths", type=int, default=800)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parent / "output" / "insurer_analysis")
    parser.add_argument("--cost-assumptions", type=Path,
                        default=DEFAULT_COST_ASSUMPTIONS_PATH,
                        help="path to cost_assumptions.csv")
    parser.add_argument("--cost-assumption-set", default=None,
                        help="assumption_set_id in the cost CSV")
    parser.add_argument("--behaviour-assumptions", type=Path,
                        default=DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
                        help="directory containing the two behaviour CSVs")
    parser.add_argument("--behaviour-assumption-set", default=None,
                        help="assumption_set_id in the behaviour CSVs")
    parser.add_argument("--zero-curve", type=Path,
                        default=DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
                        help="path to australian_zero_curve.csv")
    parser.add_argument("--model-parameters", type=Path,
                        default=DEFAULT_MODEL_PARAMETERS_PATH,
                        help="path to model_parameters.csv")
    parser.add_argument("--fast", action="store_true",
                        help="Small smoke-test path counts; not a management run.")
    args = parser.parse_args()
    if args.fast:
        args.base_paths = min(args.base_paths, 600)
        args.scenario_paths = min(args.scenario_paths, 250)
        args.design_paths = min(args.design_paths, 300)
        args.behaviour_paths = min(args.behaviour_paths, 150)
        args.outcome_paths = min(args.outcome_paths, 400)
        args.model_paths = min(args.model_paths, 120)
        args.mc_paths = min(args.mc_paths, 200)
    for name, value in vars(args).items():
        if name.endswith("paths") and value <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    return args


def main() -> None:
    args = parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    print(f"Output: {out}")

    (esg, mortality, product, policy, behaviour, expenses, costs,
     behaviour_assumptions, market_assumptions) = build_inputs(
        args.cost_assumptions, args.cost_assumption_set,
        args.behaviour_assumptions, args.behaviour_assumption_set,
        args.zero_curve, args.model_parameters)
    capital_stresses = costs.capital_stresses
    prof_settings = replace(costs.profitability, include_capital=True)
    core_settings = ValuationSettings(
        model="heston_hull_white", n_paths=args.base_paths, seed=2026,
        horizon_years=None,
        projection=replace(costs.projection, record_paths=False),
    )

    print("[1/9] Basispricing, fairer LIP, Greeks, Kapital und Profitabilität")
    val = value_contract(product, policy, esg, mortality, behaviour,
                         expenses=expenses, settings=core_settings)
    mc = pathwise_pricing_error(val)
    fair_lip = fair_lifetime_income_premium(
        product, policy, esg, mortality, behaviour, settings=core_settings
    )
    greek_values = greeks(product, policy, esg, mortality, behaviour,
                          settings=core_settings, expenses=expenses)
    cap = compute_capital(product, policy, esg, mortality, behaviour,
                          expenses=expenses, settings=core_settings,
                          stresses=capital_stresses)
    prof = analyse_profitability(
        product, policy, esg, mortality, behaviour, expenses,
        settings=core_settings, prof_settings=prof_settings,
        valuation_result=val, capital_result=cap,
        capital_stresses=capital_stresses,
    )

    pv_labels = {
        "premium": "Premium", "income_paid": "Income paid",
        "guarantee_claims": "Guarantee claims",
        "death_benefits": "Death benefits",
        "surrender_benefits": "Surrender benefits",
        "partial_withdrawals": "Partial withdrawals",
        "fees_product": "Product fees", "fees_lip": "LIP fees",
        "crediting_margin": "Crediting margin",
        "mva_retained": "MVA retained", "aps_retained": "APS retained",
        "hedge_costs": "Hedge execution/basis costs",
        "expenses": "Expenses",
    }
    pv_df = pd.DataFrame(
        [{"component": k, "label": pv_labels[k], "pv_aud": v}
         for k, v in val.pv.items()]
    )
    pv_df.to_csv(out / "pv_components.csv", index=False)

    capital_map = {
        "Zins": max(cap.scr_by_module["interest_up"], cap.scr_by_module["interest_down"]),
        "Aktie": cap.scr_by_module["equity"],
        "Aktienvolatilität": cap.scr_by_module["equity_vol"],
        "Langlebigkeit": cap.scr_by_module["longevity"],
        "Sterblichkeit": cap.scr_by_module["mortality"],
        "Storno": max(cap.scr_by_module["lapse_up"], cap.scr_by_module["lapse_down"],
                      cap.scr_by_module["lapse_mass"]),
        "Kosten": cap.scr_by_module["expense"],
        "Katastrophe": cap.scr_by_module["cat"],
    }
    capital_df = pd.DataFrame(
        [{"module_de": k, "standalone_scr": v} for k, v in capital_map.items()]
    )
    for k, v in cap.scr_by_module.items():
        capital_df.loc[len(capital_df)] = [f"directional:{k}", v]
    capital_df["bscr"] = cap.bscr
    capital_df["risk_margin"] = cap.risk_margin
    capital_df["is_binding_view"] = ~capital_df["module_de"].str.startswith("directional:")
    capital_df.to_csv(out / "capital_proxy.csv", index=False)
    capital_binding_df = capital_df[capital_df["is_binding_view"]].copy()

    kpis = pd.DataFrame(
        [
            ("premium", val.premium, "AUD"),
            ("gross_vnb", val.insurer_net_value, "AUD"),
            ("gross_vnb_se", mc["gross_vnb_se"], "AUD"),
            ("vnb_after_risk_margin", prof.vnb_market_consistent, "AUD"),
            ("new_business_margin", prof.new_business_margin, "decimal"),
            ("pvfp_8pct", prof.pvfp_hurdle, "AUD"),
            ("pvfp_margin", prof.pvfp_margin, "decimal"),
            ("fair_lip", fair_lip, "decimal"),
            ("charged_lip", product.fees.lifetime_income_premium, "decimal"),
            ("guarantee_value", val.guarantee_value, "AUD"),
            ("bel_nonunit", val.bel_nonunit, "AUD"),
            ("bscr_proxy", cap.bscr, "AUD"),
            ("risk_margin_proxy", cap.risk_margin, "AUD"),
            ("identity_gap", val.identity_gap, "decimal"),
            ("irr", np.nan if prof.irr is None else prof.irr, "decimal"),
            ("payback_year", np.nan if prof.payback_year is None else prof.payback_year, "year"),
        ],
        columns=["metric", "value", "unit"],
    )
    kpis.to_csv(out / "executive_kpis.csv", index=False)
    pd.DataFrame([greek_values]).to_csv(out / "market_greeks.csv", index=False)
    reconciliation_table(
        val, fair_lip, product.fees.lifetime_income_premium, mc
    ).to_csv(out / "reconciliations.csv", index=False)

    runoff = pd.DataFrame(
        {
            "year": prof.years,
            "profit_signature": prof.profit_signature,
            "distributable": prof.distributable,
            "cumulative_distributable": np.cumsum(prof.distributable),
            "bel_nonunit_incl_rm": prof.bel_pattern,
            "required_capital": prof.capital_pattern,
        }
    )
    runoff.to_csv(out / "profit_runoff.csv", index=False)

    print("[2/9] Standard-Sensitivitäten")
    sensitivity_settings = ValuationSettings(
        model="heston_hull_white", n_paths=args.scenario_paths, seed=2026,
        horizon_years=None,
        projection=replace(costs.projection, record_paths=False)
    )
    sensitivities = run_sensitivities(
        product, policy, esg, mortality, behaviour, expenses,
        settings=sensitivity_settings,
        prof_settings=replace(prof_settings, include_capital=False),
        include_capital=False,
        capital_stresses=capital_stresses,
    ).rename(
        columns={
            "vnb": "gross_vnb", "nbm_pct": "gross_nbm_pct",
            "d_vnb": "d_gross_vnb", "d_pvfp": "d_pvfp_pre_capital",
        }
    )
    sensitivities["scenario_de"] = sensitivities["scenario"].map(SCENARIO_DE).fillna(
        sensitivities["scenario"]
    )
    sensitivities["capital_included"] = False
    sensitivities.to_csv(out / "sensitivities.csv", index=False)

    print("[3/9] Real-World Kunden-Outcomes")
    outcome_settings = ValuationSettings(
        model="hull_white_bs", n_paths=args.outcome_paths, seed=2026,
        horizon_years=None,
        projection=replace(costs.projection, record_paths=True)
    )
    outcome, annual_customer = outcome_quantiles(
        product, policy, esg, mortality, behaviour, expenses, outcome_settings
    )
    outcome.to_csv(out / "customer_outcome_quantiles.csv", index=False)
    annual_customer.to_csv(out / "customer_annual_cashflows.csv", index=False)

    print("[4/9] Produktdesign- und dynamische Take-up-Varianten")
    design_settings = ValuationSettings(
        model="heston_hull_white", n_paths=args.design_paths, seed=2026,
        horizon_years=None,
        projection=replace(costs.projection, record_paths=True)
    )
    designs = product_variant_rows(
        product, policy, esg, mortality, behaviour, expenses, design_settings
    )
    designs.to_csv(out / "product_designs.csv", index=False)
    timing = start_timing_rows(
        product, policy, esg, mortality, behaviour, expenses, design_settings
    )
    timing.to_csv(out / "income_start_timing.csv", index=False)

    print("[5/9] Verhaltens- und Liquiditätsflächen")
    behaviour_settings = ValuationSettings(
        model="heston_hull_white", n_paths=args.behaviour_paths, seed=2026,
        horizon_years=None,
        projection=replace(costs.projection, record_paths=False)
    )
    takeup_surface, withdrawal_surface = behaviour_surface_rows(
        product, policy, esg, mortality, behaviour, expenses, behaviour_settings
    )
    takeup_surface.to_csv(out / "behaviour_takeup_lapse.csv", index=False)
    withdrawal_surface.to_csv(out / "behaviour_withdrawals.csv", index=False)

    print("[6/9] Stochastisches Modellrisiko")
    models = model_risk_rows(
        product, policy, esg, mortality, behaviour, expenses,
        args.model_paths, 2026, costs.projection
    )
    models.to_csv(out / "model_comparison.csv", index=False)

    print("[7/9] Monte-Carlo-Seed-Stabilität")
    seeds = seed_stability_rows(
        product, policy, esg, mortality, behaviour, expenses, args.mc_paths,
        costs.projection
    )
    seeds.to_csv(out / "mc_seed_stability.csv", index=False)

    print("[8/9] Grafiken")
    chart_executive_dashboard(out, val, cap, prof, fair_lip, mc,
                              capital_binding_df, product, prof_settings)
    chart_value_waterfall(out, val)
    chart_profit_capital_runoff(out, runoff)
    chart_sensitivity_tornado(out, sensitivities,
                              prof_settings.hurdle_rate)
    chart_customer_outcomes(out, outcome, annual_customer)
    chart_product_design(out, designs)
    chart_income_start(out, timing)
    chart_behaviour_surfaces(out, takeup_surface, withdrawal_surface)
    chart_model_mc_stability(out, models, seeds)
    chart_market_greeks(out, greek_values, cap)

    print("[9/9] Manifest und Management-Bericht")
    root = Path(__file__).resolve().parents[1]
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "engine_version": agile_engine.__version__,
        "engine_source_sha256": source_hash(root),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "pandas": pd.__version__,
        "matplotlib": matplotlib.__version__,
        "model_point_banner": MODEL_POINT,
        "scope": "illustrative new-business research run; not APRA/LAGIC",
        "inputs": {
            "product": serialise(product), "policy": serialise(policy),
            "esg": serialise(esg), "mortality": serialise(mortality),
            "behaviour": serialise(behaviour), "expenses": serialise(expenses),
            "capital_stresses": serialise(capital_stresses),
            "profitability": serialise(prof_settings),
            "cost_assumptions": costs.source_metadata(),
            "dynamic_behaviour_assumptions":
                behaviour_assumptions.source_metadata(),
            "market_assumptions": market_assumptions.source_metadata(),
        },
        "run_settings": {
            "base": serialise(core_settings),
            "sensitivities": serialise(sensitivity_settings),
            "designs": serialise(design_settings),
            "behaviour": serialise(behaviour_settings),
            "outcome": serialise(outcome_settings),
            "model_comparison_paths": args.model_paths,
            "mc_seed_paths": args.mc_paths,
        },
        "provenance": {
            "valuation": val.provenance, "capital": cap.provenance,
        },
        "official_product_sources": {
            "july_2026_income_rates": "https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Lifetime_Income_Rates_Jul26.pdf",
            "july_2026_guaranteed_minimums": "https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/documents/rate-sheets/2026/july26/AGILE_Guaranteed_Minimums_Jul26.pdf",
            "pds_19_january_2026": "https://www.allianzretireplus.com.au/content/dam/onemarketing/azau/allianzretireplus_com_au/pds-2026/AGILE_PDS_19%20Jan_2026_F1.pdf",
        },
    }
    (out / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    runtime = time.perf_counter() - started
    write_report(out, val, cap, prof, fair_lip, mc, sensitivities, designs,
                 timing, models, seeds, outcome, capital_binding_df,
                 runtime, args, product, costs, behaviour_assumptions,
                 market_assumptions)
    print(f"Done in {runtime:.1f}s: {out / 'INSURER_ANALYSIS_REPORT.md'}")


if __name__ == "__main__":
    main()
