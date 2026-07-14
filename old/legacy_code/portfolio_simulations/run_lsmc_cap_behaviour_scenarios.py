"""Quantify how crediting caps and stresses affect joint LSMC behaviour.

Each cap/stress cell receives a fresh joint Income-Election/post-Election fit.
Training and final evaluation stay separate, while common seeds make cap
comparisons within a stress use common random numbers.  Every scenario retains
the three factorial Behaviour benchmarks and, optionally, Dynamic Behaviour
produced by ``run_portfolio_valuation_lsmc.py``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence

import numpy as np

if __package__:
    from ._mc_analysis_inputs import (
        load_mc_analysis_inputs,
        require_mc_samples,
    )
    from ._run_layout import behaviour_benchmark_directories
    from ._run_logging import log_to_console
else:
    from _mc_analysis_inputs import (
        load_mc_analysis_inputs,
        require_mc_samples,
    )
    from _run_layout import behaviour_benchmark_directories
    from _run_logging import log_to_console


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
ENGINE_ROOT = SCRIPT_DIRECTORY.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from policy_engine import (  # noqa: E402
    DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
    DEFAULT_COST_ASSUMPTIONS_PATH,
    DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY,
    DEFAULT_MODEL_PARAMETERS_PATH,
    DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH,
    HedgeCapLegMode,
)
from policy_engine.repository_paths import run_output_directory  # noqa: E402

LSMC_PORTFOLIO_RUNNER = SCRIPT_DIRECTORY / "run_portfolio_valuation_lsmc.py"
DEFAULT_OUTPUT_DIRECTORY = run_output_directory("lsmc_cap_behaviour_scenarios")
DEFAULT_CAP_RATES = (0.04, 0.06, 0.12, 0.20)
DEFAULT_BASELINE_RATE = 0.06
STRESS_SCENARIOS = (
    "base",
    "interest_up",
    "interest_down",
    "equity_level_down",
    "equity_volatility_up",
    "longevity",
    "mortality",
    "expense",
)

BEHAVIOUR_FIELDS: dict[str, tuple[str, ...]] = {
    "income_start_year_mean": (
        "income_start_year_mean", "expected_income_start_year"),
    "income_start_year_median": (
        "income_start_year_median", "median_income_start_year"),
    "income_start_year_p10": (
        "income_start_year_p10", "p10_income_start_year", "income_start_year_q10"),
    "income_start_year_p90": (
        "income_start_year_p90", "p90_income_start_year", "income_start_year_q90"),
    "income_election_share": (
        "income_election_share", "cumulative_income_election_share"),
    "forced_income_election_share": (
        "forced_income_election_share", "forced_income_start_share"),
    "mean_growth_duration": (
        "mean_growth_duration",
        "mean_growth_duration_years",
    ),
    "growth_phase_exposure": ("growth_phase_exposure", "growth_phase_share"),
    "income_phase_exposure": ("income_phase_exposure", "income_phase_share"),
    "ordinary_income_lapse_rate": (
        "ordinary_income_lapse_rate", "income_lapse_ordinary_rate"),
    "performance_income_lapse_rate": (
        "performance_income_lapse_rate", "income_lapse_performance_rate"),
    "total_income_lapse_rate": (
        "total_income_lapse_rate", "income_lapse_total_rate",
        "income_phase_lapse_rate", "income_phase_full_withdrawal_rate"),
}

PHASE_MONETARY_FIELDS = (
    "pv_policyholder_benefits_pre_election_aud",
    "pv_policyholder_benefits_post_election_aud",
    "pv_growth_fees_aud",
    "pv_growth_crediting_margin_aud",
    "pv_post_election_guarantee_claims_aud",
)

HEDGE_MONETARY_FIELDS = (
    "pv_money_market_income_aud",
    "pv_hedge_gain_aud",
    "pv_hedge_option_fair_value_costs_aud",
    "pv_hedge_option_markup_costs_aud",
    "pv_hedge_management_fee_costs_aud",
    "pv_hedge_execution_costs_aud",
    "pv_hedge_costs_aud",
)
HEDGE_CAP_LEG_MODES = tuple(mode.value for mode in HedgeCapLegMode)
LSMC_TRAINING_SEED_SET_COUNT = 3


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
    mc_inputs = load_mc_analysis_inputs()
    evaluation_input = require_mc_samples(
        mc_inputs, "evaluation", 1
    )[0]
    training_inputs = require_mc_samples(
        mc_inputs,
        "lsmc_training",
        LSMC_TRAINING_SEED_SET_COUNT,
    )
    validation_input = require_mc_samples(
        mc_inputs, "lsmc_validation", 1
    )[0]
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
    parser.add_argument(
        "--stress-scenarios",
        nargs="+",
        choices=STRESS_SCENARIOS,
        default=["base"],
        metavar="STRESS",
        help=(
            "cap-by-stress cells to refit independently; include base for the "
            "unstressed comparison"
        ),
    )
    parser.add_argument(
        "--n-paths", type=int, default=evaluation_input.n_paths
    )
    parser.add_argument(
        "--seed", type=int, default=evaluation_input.market_seed
    )
    parser.add_argument(
        "--take-up-seed", type=int, default=evaluation_input.take_up_seed
    )
    parser.add_argument(
        "--mortality-seed", type=int, default=evaluation_input.mortality_seed
    )
    parser.add_argument(
        "--n-train", type=int, default=training_inputs[0].n_paths
    )
    parser.add_argument(
        "--train-seed", type=int, default=training_inputs[0].market_seed
    )
    parser.add_argument(
        "--train-take-up-seed",
        type=int,
        default=training_inputs[0].take_up_seed,
    )
    parser.add_argument(
        "--train-mortality-seed",
        type=int,
        default=training_inputs[0].mortality_seed,
    )
    parser.add_argument(
        "--train-seed-2", type=int, default=training_inputs[1].market_seed
    )
    parser.add_argument(
        "--train-take-up-seed-2",
        type=int,
        default=training_inputs[1].take_up_seed,
    )
    parser.add_argument(
        "--train-mortality-seed-2",
        type=int,
        default=training_inputs[1].mortality_seed,
    )
    parser.add_argument(
        "--train-seed-3", type=int, default=training_inputs[2].market_seed
    )
    parser.add_argument(
        "--train-take-up-seed-3",
        type=int,
        default=training_inputs[2].take_up_seed,
    )
    parser.add_argument(
        "--train-mortality-seed-3",
        type=int,
        default=training_inputs[2].mortality_seed,
    )
    parser.add_argument(
        "--n-validation", type=int, default=validation_input.n_paths
    )
    parser.add_argument(
        "--validation-seed", type=int, default=validation_input.market_seed
    )
    parser.add_argument(
        "--validation-take-up-seed",
        type=int,
        default=validation_input.take_up_seed,
    )
    parser.add_argument(
        "--validation-mortality-seed",
        type=int,
        default=validation_input.mortality_seed,
    )
    parser.add_argument("--heston-substeps", type=int, default=4)
    parser.add_argument("--market-cache-root", type=Path, default=None)
    parser.add_argument("--hedge-cache-root", type=Path, default=None)
    parser.add_argument(
        "--hedge-pricing-method",
        choices=("mc_conditional", "moment_matched_bs"),
        default="mc_conditional",
    )
    parser.add_argument("--require-market-cache", action="store_true")
    parser.add_argument("--require-hedge-cache", action="store_true")
    parser.add_argument(
        "--hedge-cap-leg-mode",
        choices=HEDGE_CAP_LEG_MODES,
        default=HedgeCapLegMode.SOLD.value,
        help=(
            "sold uses the standard capped call spread; not_sold retains the "
            "hedge payoff above the customer cap"
        ),
    )
    parser.add_argument("--lsmc-folds", type=int, default=5)
    parser.add_argument(
        "--lsmc-ridge",
        type=float,
        choices=(0.0, 1.0e-8, 1.0e-6, 1.0e-4, 1.0e-2),
        default=1.0e-6,
    )
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
    args.stress_scenarios = list(dict.fromkeys(args.stress_scenarios))
    for name in ("n_paths", "n_train", "n_validation", "heston_substeps"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.lsmc_folds < 2:
        parser.error("--lsmc-folds must be at least two")
    seed_names = (
        "seed",
        "take_up_seed",
        "mortality_seed",
        "train_seed",
        "train_take_up_seed",
        "train_mortality_seed",
        "train_seed_2",
        "train_take_up_seed_2",
        "train_mortality_seed_2",
        "train_seed_3",
        "train_take_up_seed_3",
        "train_mortality_seed_3",
        "validation_seed",
        "validation_take_up_seed",
        "validation_mortality_seed",
    )
    if any(getattr(args, name) < 0 for name in seed_names):
        parser.error("all seeds must be non-negative")
    market_seeds = (
        args.train_seed,
        args.train_seed_2,
        args.train_seed_3,
        args.validation_seed,
        args.seed,
    )
    take_up_seeds = (
        args.train_take_up_seed,
        args.train_take_up_seed_2,
        args.train_take_up_seed_3,
        args.validation_take_up_seed,
        args.take_up_seed,
    )
    mortality_seeds = (
        args.train_mortality_seed,
        args.train_mortality_seed_2,
        args.train_mortality_seed_3,
        args.validation_mortality_seed,
        args.mortality_seed,
    )
    if len(set(market_seeds)) != 5:
        parser.error(
            "all three training, validation and evaluation market seeds must differ"
        )
    if len(set(take_up_seeds)) != 5:
        parser.error(
            "all three training, validation and evaluation take-up seeds must differ"
        )
    if len(set(mortality_seeds)) != 5:
        parser.error(
            "all three training, validation and evaluation mortality seeds must differ"
        )
    for name in ("lsmc_ridge", "exercise_buffer_rmse_multiplier"):
        value = float(getattr(args, name))
        if not math.isfinite(value) or value < 0.0:
            parser.error(f"--{name.replace('_', '-')} must be non-negative")
    if args.portfolio_contract_count is not None and (
        not math.isfinite(args.portfolio_contract_count)
        or args.portfolio_contract_count <= 0.0
    ):
        parser.error("--portfolio-contract-count must be positive and finite")
    if (
        not math.isfinite(args.profitability_materiality_bp)
        or args.profitability_materiality_bp < 0.0
    ):
        parser.error("--profitability-materiality-bp must be non-negative")
    for name in (
        "model_points",
        "cost_assumptions",
        "dynamic_behaviour",
        "zero_curve",
        "model_parameters",
    ):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.expanduser().resolve())
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
    stress_scenario: str,
    scenario_output: Path,
) -> list[str]:
    command = [
        str(args.python_executable),
        str(LSMC_PORTFOLIO_RUNNER),
        "--crediting-cap-rate", f"{rate:.12g}",
        "--stress-scenario", stress_scenario,
        "--n-paths", str(args.n_paths),
        "--seed", str(args.seed),
        "--take-up-seed", str(args.take_up_seed),
        "--mortality-seed", str(args.mortality_seed),
        "--n-train", str(args.n_train),
        "--train-seed", str(args.train_seed),
        "--train-take-up-seed", str(args.train_take_up_seed),
        "--train-mortality-seed", str(args.train_mortality_seed),
        "--train-seed-2", str(args.train_seed_2),
        "--train-take-up-seed-2", str(args.train_take_up_seed_2),
        "--train-mortality-seed-2", str(args.train_mortality_seed_2),
        "--train-seed-3", str(args.train_seed_3),
        "--train-take-up-seed-3", str(args.train_take_up_seed_3),
        "--train-mortality-seed-3", str(args.train_mortality_seed_3),
        "--n-validation", str(args.n_validation),
        "--validation-seed", str(args.validation_seed),
        "--validation-take-up-seed", str(args.validation_take_up_seed),
        "--validation-mortality-seed", str(args.validation_mortality_seed),
        "--heston-substeps", str(args.heston_substeps),
        "--hedge-cap-leg-mode", args.hedge_cap_leg_mode,
        "--hedge-pricing-method", args.hedge_pricing_method,
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
    _optional_argument(command, "--market-cache-root", args.market_cache_root)
    _optional_argument(command, "--hedge-cache-root", args.hedge_cache_root)
    if args.require_market_cache:
        command.append("--require-market-cache")
    if args.require_hedge_cache:
        command.append("--require-hedge-cache")
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


def _first_float(
    row: Mapping[str, object],
    fields: Sequence[str],
    label: str,
) -> float:
    for field in fields:
        if row.get(field) not in (None, ""):
            return _as_float(row.get(field), field)
    raise ValueError(f"Missing {label}; expected one of {', '.join(fields)}")


def _behaviour_metrics(summary: Mapping[str, object]) -> dict[str, float]:
    output = {
        canonical: _first_float(
            summary,
            (*aliases, *(f"normalised_average_{name}" for name in aliases)),
            canonical,
        )
        for canonical, aliases in BEHAVIOUR_FIELDS.items()
    }
    for raw_key, raw_value in summary.items():
        key = str(raw_key)
        canonical = key.removeprefix("normalised_average_")
        if re.match(
            r"^(?:income_election_share|growth_phase_share|income_phase_share)_policy_year_\d+$",
            canonical,
        ):
            output[canonical] = _as_float(raw_value, key)
    if not any(
        key.startswith("income_election_share_policy_year_") for key in output
    ):
        raise ValueError("Portfolio summary has no policy-year Election buckets.")
    if not any(
        key.startswith("growth_phase_share_policy_year_") for key in output
    ):
        raise ValueError("Portfolio summary has no policy-year Growth buckets.")
    return output


def _normalised_action_tokens(method: Mapping[str, object]) -> set[str]:
    tokens: set[str] = set()
    for key, value in method.items():
        if "action_set" not in str(key).lower():
            continue
        values = value if isinstance(value, (list, tuple, set)) else [value]
        for item in values:
            tokens.update(
                token for token in re.split(r"[^a-z0-9]+", str(item).lower())
                if token
            )
    combined = set(tokens)
    if {"start", "income"}.issubset(tokens):
        combined.add("start_income")
    if {"full", "withdrawal"}.issubset(tokens):
        combined.add("full_withdrawal")
    if {"partial", "withdrawal"}.issubset(tokens):
        combined.add("partial_withdrawal")
    return combined


def _fit_basis_fingerprint(manifest: Mapping[str, object]) -> str:
    settings = manifest.get("lsmc_settings")
    if not isinstance(settings, Mapping):
        raise ValueError("LSMC manifest has no lsmc_settings object.")
    direct = settings.get("fit_basis_fingerprint")
    if direct not in (None, ""):
        return str(direct)
    candidates = (
        settings.get("fit_basis_fingerprints"),
        settings.get("policy_fit_basis_fingerprints"),
    )
    for candidate in candidates:
        if isinstance(candidate, Mapping) and candidate:
            payload = candidate
        elif isinstance(candidate, (list, tuple)) and candidate:
            payload = list(candidate)
        else:
            continue
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
    raise ValueError(
        "LSMC manifest has no runner-produced fit-basis fingerprint; old or "
        "non-auditable outputs cannot be reused."
    )


_LSMC_VALIDATION_COMPONENTS = {
    "election_only",
    "income_action_only",
    "combined_policy",
}


def _expected_training_seed_triplets(
    args: argparse.Namespace,
) -> tuple[dict[str, object], ...]:
    return (
        {
            "seed_index": 1,
            "market_seed": args.train_seed,
            "take_up_seed": args.train_take_up_seed,
            "mortality_seed": args.train_mortality_seed,
            "primary": True,
        },
        {
            "seed_index": 2,
            "market_seed": args.train_seed_2,
            "take_up_seed": args.train_take_up_seed_2,
            "mortality_seed": args.train_mortality_seed_2,
            "primary": False,
        },
        {
            "seed_index": 3,
            "market_seed": args.train_seed_3,
            "take_up_seed": args.train_take_up_seed_3,
            "mortality_seed": args.train_mortality_seed_3,
            "primary": False,
        },
    )


def _validate_gate_set(gates: object, *, label: str) -> None:
    if not isinstance(gates, list) or len(gates) != 3:
        raise ValueError(f"{label} must contain exactly three validation gates.")
    if any(
        not isinstance(gate, Mapping) or not _as_bool(gate.get("valid"))
        for gate in gates
    ):
        raise ValueError(f"{label} contains an invalid validation gate.")
    components = {
        str(gate.get("component", "")).strip()
        for gate in gates
        if isinstance(gate, Mapping)
    }
    if components != _LSMC_VALIDATION_COMPONENTS:
        raise ValueError(
            f"{label} must contain Election-, Income-action- and Combined gates."
        )


def _validate_multi_seed_evidence(
    directory: Path,
    manifest: Mapping[str, object],
    validation_manifest: Mapping[str, object],
    *,
    expected_args: argparse.Namespace,
) -> tuple[str, str, str]:
    lsmc_settings = manifest.get("lsmc_settings")
    validation_settings = manifest.get("validation_settings")
    evaluation_settings = manifest.get("evaluation_settings")
    if not all(
        isinstance(item, Mapping)
        for item in (lsmc_settings, validation_settings, evaluation_settings)
    ):
        raise ValueError("LSMC three-seed settings are incomplete.")
    assert isinstance(lsmc_settings, Mapping)
    assert isinstance(validation_settings, Mapping)
    assert isinstance(evaluation_settings, Mapping)

    expected_triplets = _expected_training_seed_triplets(expected_args)
    triplets = lsmc_settings.get("training_seed_triplets")
    if not isinstance(triplets, list) or len(triplets) != 3:
        raise ValueError("LSMC manifest must contain exactly three seed triplets.")
    for index, (actual, expected) in enumerate(
        zip(triplets, expected_triplets), start=1
    ):
        if not isinstance(actual, Mapping):
            raise ValueError(f"LSMC training seed triplet {index} is malformed.")
        for field in ("seed_index", "market_seed", "take_up_seed", "mortality_seed"):
            if int(_as_float(actual.get(field), field)) != int(expected[field]):
                raise ValueError(
                    f"LSMC training seed triplet {index} changed {field}."
                )
        if _as_bool(actual.get("primary")) is not bool(expected["primary"]):
            raise ValueError(
                f"LSMC training seed triplet {index} has the wrong primary flag."
            )

    raw_fingerprints = lsmc_settings.get("training_scenario_fingerprints")
    if not isinstance(raw_fingerprints, list) or len(raw_fingerprints) != 3:
        raise ValueError(
            "LSMC manifest must contain exactly three training fingerprints."
        )
    training_fingerprints = tuple(
        str(value).strip() for value in raw_fingerprints
    )
    validation_fingerprint = str(
        validation_settings.get("scenario_fingerprint", "")
    ).strip()
    evaluation_fingerprint = str(
        evaluation_settings.get("scenario_fingerprint", "")
    ).strip()
    fingerprint_set = {
        *training_fingerprints,
        validation_fingerprint,
        evaluation_fingerprint,
    }
    if "" in fingerprint_set or len(set(training_fingerprints)) != 3 \
            or len(fingerprint_set) != 5:
        raise ValueError(
            "All three training, validation and evaluation fingerprints must differ."
        )
    if str(lsmc_settings.get("training_scenario_fingerprint", "")).strip() \
            != training_fingerprints[0]:
        raise ValueError(
            "Backward-compatible training fingerprint is not primary seed 1."
        )
    if int(_as_float(
        lsmc_settings.get("training_seed_count"), "training_seed_count"
    )) != 3 or int(_as_float(
        lsmc_settings.get("primary_training_seed_index"),
        "primary_training_seed_index",
    )) != 1:
        raise ValueError("LSMC primary training seed 1 is not predeclared.")
    if lsmc_settings.get("evaluation_used_for_training_seed_selection") is not False:
        raise ValueError("LSMC training-seed selection used final evaluation data.")
    selection_rule = str(
        lsmc_settings.get("primary_seed_selection_rule", "")
    ).lower()
    if "predeclared" not in selection_rule or "not_evaluation" not in selection_rule:
        raise ValueError("LSMC primary seed-selection rule is not predeclared.")

    gates_by_seed = validation_settings.get("gates_by_training_seed")
    expected_gate_keys = {
        "training_seed_1",
        "training_seed_2",
        "training_seed_3",
    }
    if not isinstance(gates_by_seed, Mapping) or set(gates_by_seed) != expected_gate_keys:
        raise ValueError("LSMC manifest has no complete gates-by-seed mapping.")
    for index in range(1, 4):
        _validate_gate_set(
            gates_by_seed[f"training_seed_{index}"],
            label=f"LSMC manifest training seed {index}",
        )
    if not _as_bool(
        validation_settings.get("every_seed_passes_election_income_combined")
    ):
        raise ValueError("Not every LSMC training seed passed all three gates.")

    if not isinstance(validation_manifest, Mapping) or not _as_bool(
        validation_manifest.get("valid")
    ):
        raise ValueError("Independent LSMC validation manifest is invalid.")
    if int(_as_float(
        validation_manifest.get("training_seed_count"),
        "validation training_seed_count",
    )) != 3:
        raise ValueError("Validation manifest does not evidence three seed fits.")
    if validation_manifest.get("seed_selection_using_evaluation") is not False:
        raise ValueError("Validation manifest permits evaluation-based selection.")
    if int(_as_float(
        validation_manifest.get("primary_training_seed_index"),
        "validation primary_training_seed_index",
    )) != 1:
        raise ValueError("Validation manifest does not predeclare seed 1.")
    top_level_gates = validation_manifest.get("gates")
    if not isinstance(top_level_gates, list) or len(top_level_gates) != 9:
        raise ValueError("Validation manifest must contain exactly nine gates.")
    grouped_gates: dict[int, list[Mapping[str, object]]] = {1: [], 2: [], 3: []}
    for gate in top_level_gates:
        if not isinstance(gate, Mapping) or not _as_bool(gate.get("valid")):
            raise ValueError("Validation manifest contains an invalid top-level gate.")
        seed_index = int(_as_float(
            gate.get("training_seed_index"), "gate training_seed_index"
        ))
        if seed_index not in grouped_gates:
            raise ValueError("Validation gate refers to an unknown training seed.")
        grouped_gates[seed_index].append(gate)
    for index, gates in grouped_gates.items():
        _validate_gate_set(
            gates,
            label=f"Validation manifest top-level seed {index}",
        )
        expected = expected_triplets[index - 1]
        for gate in gates:
            if str(gate.get("training_scenario_fingerprint", "")).strip() != (
                training_fingerprints[index - 1]
            ):
                raise ValueError("Top-level validation gate changed its sample.")
            for field, expected_field in (
                ("training_market_seed", "market_seed"),
                ("training_take_up_seed", "take_up_seed"),
                ("training_mortality_seed", "mortality_seed"),
            ):
                if int(_as_float(gate.get(field), field)) != int(
                    expected[expected_field]
                ):
                    raise ValueError(
                        f"Top-level validation gate {index} changed {field}."
                    )

    training_runs = validation_manifest.get("training_runs")
    if not isinstance(training_runs, list) or len(training_runs) != 3:
        raise ValueError("Validation manifest must contain exactly three runs.")
    for index, (run, expected, fingerprint) in enumerate(
        zip(training_runs, expected_triplets, training_fingerprints), start=1
    ):
        if not isinstance(run, Mapping) or not _as_bool(run.get("valid")):
            raise ValueError(f"Validation training run {index} is invalid.")
        for field in ("seed_index", "market_seed", "take_up_seed", "mortality_seed"):
            if int(_as_float(run.get(field), field)) != int(expected[field]):
                raise ValueError(
                    f"Validation training run {index} changed {field}."
                )
        if _as_bool(run.get("primary")) is not bool(expected["primary"]):
            raise ValueError(
                f"Validation training run {index} has the wrong primary flag."
            )
        if str(run.get("training_scenario_fingerprint", "")).strip() != fingerprint:
            raise ValueError(
                f"Validation training run {index} changed its fingerprint."
            )
        _validate_gate_set(
            run.get("gates"), label=f"Validation training run {index}"
        )

    final_evaluations = evaluation_settings.get("multi_seed_final_evaluation")
    evaluation_fingerprints = evaluation_settings.get(
        "multi_seed_evaluation_scenario_fingerprints"
    )
    if not isinstance(final_evaluations, list) or len(final_evaluations) != 3:
        raise ValueError("LSMC manifest must report three final evaluations.")
    if not isinstance(evaluation_fingerprints, list) or len(
        evaluation_fingerprints
    ) != 3 or any(
        str(value).strip() != evaluation_fingerprint
        for value in evaluation_fingerprints
    ):
        raise ValueError("The three LSMC fits do not share one final evaluation.")
    if evaluation_settings.get("training_seed_selected_using_evaluation") is not False:
        raise ValueError("Final evaluation was used to select a training seed.")
    for index, (row, expected, fingerprint) in enumerate(
        zip(final_evaluations, expected_triplets, training_fingerprints), start=1
    ):
        if not isinstance(row, Mapping):
            raise ValueError(f"Final evaluation row {index} is malformed.")
        if int(_as_float(
            row.get("training_seed_index"), "evaluation training_seed_index"
        )) != index:
            raise ValueError("Final evaluation training-seed order changed.")
        if _as_bool(row.get("primary_training_seed")) is not bool(
            expected["primary"]
        ):
            raise ValueError("Final evaluation primary-seed flag is inconsistent.")
        if str(row.get("training_scenario_fingerprint", "")).strip() != fingerprint:
            raise ValueError("Final evaluation changed a training fingerprint.")
        for field, expected_field in (
            ("training_market_seed", "market_seed"),
            ("training_take_up_seed", "take_up_seed"),
            ("training_mortality_seed", "mortality_seed"),
        ):
            if int(_as_float(row.get(field), field)) != int(
                expected[expected_field]
            ):
                raise ValueError(f"Final evaluation row {index} changed {field}.")
        if str(row.get("evaluation_scenario_fingerprint", "")).strip() \
                != evaluation_fingerprint:
            raise ValueError("Final evaluations do not use one common sample.")
        if row.get("evaluation_used_for_seed_selection") is not False:
            raise ValueError("Final evaluation row permits seed selection.")
        if _as_bool(row.get("selected_for_primary_outputs")) is not (index == 1):
            raise ValueError("Only predeclared training seed 1 may drive outputs.")

    report_rows = _read_csv(
        directory / "lsmc_multi_seed_validation_evaluation.csv"
    )
    if len(report_rows) != 3:
        raise ValueError("Multi-seed CSV must contain exactly three rows.")
    for index, (row, expected, fingerprint) in enumerate(
        zip(report_rows, expected_triplets, training_fingerprints), start=1
    ):
        if int(_as_float(
            row.get("training_seed_index"), "CSV training_seed_index"
        )) != index:
            raise ValueError("Multi-seed CSV training-seed order changed.")
        if _as_bool(row.get("primary_training_seed")) is not bool(
            expected["primary"]
        ):
            raise ValueError("Multi-seed CSV primary-seed flag is inconsistent.")
        for field, expected_field in (
            ("training_market_seed", "market_seed"),
            ("training_take_up_seed", "take_up_seed"),
            ("training_mortality_seed", "mortality_seed"),
        ):
            if int(_as_float(row.get(field), field)) != int(expected[expected_field]):
                raise ValueError(f"Multi-seed CSV row {index} changed {field}.")
        if str(row.get("training_scenario_fingerprint", "")).strip() != fingerprint:
            raise ValueError("Multi-seed CSV changed a training fingerprint.")
        if str(row.get("validation_scenario_fingerprint", "")).strip() \
                != validation_fingerprint or str(
                    row.get("evaluation_scenario_fingerprint", "")
                ).strip() != evaluation_fingerprint:
            raise ValueError("Multi-seed CSV changed validation/evaluation samples.")
        if not _as_bool(row.get("all_fits_valid")) or not _as_bool(
            row.get("validation_valid")
        ):
            raise ValueError("Multi-seed CSV contains an invalid fit or gate set.")
        if _as_bool(row.get("selected_for_primary_outputs")) is not (index == 1):
            raise ValueError("Multi-seed CSV did not preselect seed 1.")
        if _as_bool(row.get("evaluation_used_for_seed_selection")):
            raise ValueError("Multi-seed CSV evidences evaluation-based selection.")
        csv_selection_rule = str(row.get("selection_rule", "")).lower()
        if "predeclared" not in csv_selection_rule or "not_evaluation" not in (
            csv_selection_rule
        ):
            raise ValueError("Multi-seed CSV has no predeclared selection rule.")
        for component in _LSMC_VALIDATION_COMPONENTS:
            if not _as_bool(row.get(f"validation_{component}_valid")):
                raise ValueError(
                    f"Multi-seed CSV row {index} failed {component}."
                )
    return training_fingerprints


def _manifest_hedge_cap_leg_mode(manifest: Mapping[str, object]) -> str:
    values: list[str] = []
    for section_name in ("method", "lsmc_settings", "evaluation_settings"):
        section = manifest.get(section_name)
        if not isinstance(section, Mapping):
            raise ValueError(
                f"LSMC manifest has no {section_name} object for hedge-mode audit."
            )
        value = section.get("hedge_cap_leg_mode")
        if value in (None, ""):
            raise ValueError(
                f"LSMC manifest {section_name} has no hedge_cap_leg_mode."
            )
        values.append(str(value))
    if len(set(values)) != 1 or values[0] not in HEDGE_CAP_LEG_MODES:
        raise ValueError(
            "LSMC manifest contains inconsistent or invalid hedge-cap-leg modes."
        )
    return values[0]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_source_file(
    *,
    recorded_path: object,
    recorded_sha256: object,
    expected_path: Path,
    label: str,
) -> None:
    expected = expected_path.expanduser().resolve()
    recorded = Path(str(recorded_path)).expanduser().resolve()
    if recorded != expected:
        raise ValueError(
            f"Reused {label} path differs: {recorded} != {expected}."
        )
    if not expected.is_file():
        raise ValueError(f"Current {label} source does not exist: {expected}")
    actual_hash = _file_sha256(expected)
    if str(recorded_sha256).lower() != actual_hash:
        raise ValueError(
            f"Reused {label} source hash differs from the current file."
        )


def _validate_source_provenance(
    manifest: Mapping[str, object],
    args: argparse.Namespace,
) -> None:
    sources = manifest.get("sources")
    if not isinstance(sources, Mapping):
        raise ValueError("LSMC manifest has no auditable sources object.")

    model_points = sources.get("model_points")
    market = sources.get("market")
    costs = sources.get("costs")
    dynamic = sources.get("dynamic_behaviour_benchmark_only")
    if not all(isinstance(item, Mapping) for item in (
        model_points, market, costs
    )):
        raise ValueError("LSMC source provenance is incomplete.")

    expected_model_points = (
        args.model_points or DEFAULT_POLICYHOLDER_MODEL_POINTS_PATH
    )
    expected_costs = args.cost_assumptions or DEFAULT_COST_ASSUMPTIONS_PATH
    _validate_source_file(
        recorded_path=model_points.get("source_path"),
        recorded_sha256=model_points.get("source_sha256"),
        expected_path=expected_model_points,
        label="model-point",
    )
    _validate_source_file(
        recorded_path=costs.get("source_path"),
        recorded_sha256=costs.get("source_sha256"),
        expected_path=expected_costs,
        label="cost-assumption",
    )
    if args.cost_assumption_set is not None and str(
        costs.get("assumption_set_id")
    ) != str(args.cost_assumption_set):
        raise ValueError("Reused cost assumption-set ID differs.")

    market_paths = market.get("source_paths")
    market_hashes = market.get("source_sha256")
    if not isinstance(market_paths, Mapping) or not isinstance(
        market_hashes, Mapping
    ):
        raise ValueError("LSMC market-source provenance is incomplete.")
    _validate_source_file(
        recorded_path=market_paths.get("curve"),
        recorded_sha256=market_hashes.get("curve"),
        expected_path=args.zero_curve or DEFAULT_AUSTRALIAN_ZERO_CURVE_PATH,
        label="zero-curve",
    )
    _validate_source_file(
        recorded_path=market_paths.get("model_parameters"),
        recorded_sha256=market_hashes.get("model_parameters"),
        expected_path=args.model_parameters or DEFAULT_MODEL_PARAMETERS_PATH,
        label="model-parameter",
    )

    if args.no_dynamic_benchmark:
        if dynamic is not None:
            raise ValueError(
                "Reused output unexpectedly contains a Dynamic benchmark."
            )
        return
    if not isinstance(dynamic, Mapping):
        raise ValueError("Reused output has no Dynamic source provenance.")
    if args.behaviour_assumption_set is not None and str(
        dynamic.get("assumption_set_id")
    ) != str(args.behaviour_assumption_set):
        raise ValueError("Reused behaviour assumption-set ID differs.")
    dynamic_paths = dynamic.get("source_paths")
    dynamic_hashes = dynamic.get("source_sha256")
    if not isinstance(dynamic_paths, Mapping) or not isinstance(
        dynamic_hashes, Mapping
    ) or set(dynamic_paths) != set(dynamic_hashes):
        raise ValueError("Dynamic source provenance is incomplete.")
    expected_directory = (
        args.dynamic_behaviour or DEFAULT_DYNAMIC_BEHAVIOUR_DIRECTORY
    ).expanduser().resolve()
    for key, recorded_path in dynamic_paths.items():
        expected_path = expected_directory / Path(str(recorded_path)).name
        _validate_source_file(
            recorded_path=recorded_path,
            recorded_sha256=dynamic_hashes[key],
            expected_path=expected_path,
            label=f"dynamic-behaviour {key}",
        )


def _validate_joint_policy_manifest(
    manifest: Mapping[str, object],
    summary: Mapping[str, object],
    *,
    expected_stress: str,
    expected_args: Optional[argparse.Namespace],
) -> str:
    method = manifest.get("method")
    if not isinstance(method, Mapping):
        raise ValueError("LSMC manifest has no method object.")
    manifest_hedge_mode = _manifest_hedge_cap_leg_mode(manifest)
    tokens = _normalised_action_tokens(method)
    required_tokens = {
        "wait",
        "start_income",
        "continue",
        "partial_withdrawal",
        "full_withdrawal",
    }
    if not required_tokens.issubset(tokens):
        raise ValueError(
            "LSMC manifest does not evidence the joint Growth WAIT/START_INCOME "
            "and monthly Income CONTINUE/PARTIAL_WITHDRAWAL/FULL_WITHDRAWAL "
            "action sets."
        )
    election = " ".join((
        str(method.get("income_election", "")),
        str(method.get("income_election_mode", "")),
        str(summary.get("lsmc_income_election", "")),
    )).lower()
    if "deterministic" in election or not any(
        token in election for token in ("optimal", "pathwise", "bellman", "dynamic")
    ):
        raise ValueError("LSMC output still uses or fails to evidence fixed Election.")
    decision_grid = " ".join((
        str(method.get("income_election_decision_grid", "")),
        str(method.get("decision_frequency", "")),
        str(summary.get("lsmc_decision_grid", "")),
    )).lower()
    if "annivers" not in decision_grid:
        raise ValueError("LSMC Election grid is not contractual policy anniversaries.")
    forced_rule = " ".join((
        str(method.get("forced_income_start", "")),
        str(method.get("forced_income_election", "")),
        str(summary.get("lsmc_forced_election_rule", "")),
    )).lower()
    if "100" not in forced_rule:
        raise ValueError("LSMC manifest does not evidence forced Election at age 100.")
    joint_life = str(
        method.get("joint_life_behaviour")
        or method.get("joint_life_election_treatment")
        or ""
    ).lower()
    if not all(token in joint_life for token in ("pathwise", "primary", "spouse")):
        raise ValueError(
            "LSMC manifest does not evidence separate pathwise Primary/Spouse "
            "life status."
        )
    benchmarks = method.get("behaviour_benchmarks")
    if not isinstance(benchmarks, Mapping):
        benchmarks = manifest.get("behaviour_benchmarks")
    if not isinstance(benchmarks, Mapping) or not {
        "deterministic_election_continue",
        "deterministic_election_post_behaviour",
        "variable_election_continue",
    }.issubset(benchmarks):
        raise ValueError(
            "LSMC manifest does not identify all three factorial benchmarks."
        )

    stress = manifest.get("stress_scenario")
    stress_id = (
        stress.get("stress_scenario_id", stress.get("stress_id"))
        if isinstance(stress, Mapping) else stress
    )
    summary_stress = summary.get("stress_scenario_id")
    actual_stress = summary_stress if summary_stress not in (None, "") else stress_id
    if str(actual_stress) != expected_stress:
        raise ValueError(
            f"Stress mismatch: {actual_stress!r} != {expected_stress!r}."
        )
    if expected_args is not None:
        if manifest_hedge_mode != expected_args.hedge_cap_leg_mode:
            raise ValueError(
                "Hedge cap-leg mode mismatch in runner manifest: "
                f"{manifest_hedge_mode!r} != "
                f"{expected_args.hedge_cap_leg_mode!r}."
            )
        _validate_source_provenance(manifest, expected_args)
        lsmc_settings = manifest.get("lsmc_settings")
        validation = manifest.get("validation_settings")
        evaluation = manifest.get("evaluation_settings")
        if not isinstance(lsmc_settings, Mapping) or not isinstance(
            evaluation, Mapping
        ) or not isinstance(validation, Mapping):
            raise ValueError("LSMC manifest settings are incomplete.")
        if not _as_bool(validation.get("valid")):
            raise ValueError("Reused LSMC policy did not pass validation.")
        if not _as_bool(lsmc_settings.get("force_pathwise_joint_life")) \
                or not _as_bool(evaluation.get("force_pathwise_joint_life")):
            raise ValueError(
                "All LSMC factorial arms must use pathwise Joint-Life states."
            )
        numeric_checks = (
            (lsmc_settings, "n_train", expected_args.n_train),
            (lsmc_settings, "train_seed", expected_args.train_seed),
            (
                lsmc_settings,
                "train_take_up_seed",
                expected_args.train_take_up_seed,
            ),
            (
                lsmc_settings,
                "train_mortality_seed",
                expected_args.train_mortality_seed,
            ),
            (lsmc_settings, "n_folds", expected_args.lsmc_folds),
            (lsmc_settings, "ridge", expected_args.lsmc_ridge),
            (
                lsmc_settings,
                "exercise_buffer_rmse_multiplier",
                expected_args.exercise_buffer_rmse_multiplier,
            ),
            (validation, "n_paths", expected_args.n_validation),
            (validation, "seed", expected_args.validation_seed),
            (
                validation,
                "take_up_seed",
                expected_args.validation_take_up_seed,
            ),
            (
                validation,
                "mortality_seed",
                expected_args.validation_mortality_seed,
            ),
            (evaluation, "n_paths", expected_args.n_paths),
            (evaluation, "seed", expected_args.seed),
            (evaluation, "take_up_seed", expected_args.take_up_seed),
            (evaluation, "mortality_seed", expected_args.mortality_seed),
            (evaluation, "heston_substeps", expected_args.heston_substeps),
        )
        for container, field, expected in numeric_checks:
            actual = _as_float(container.get(field), field)
            if not math.isclose(
                actual, float(expected), rel_tol=1.0e-12, abs_tol=1.0e-12
            ):
                raise ValueError(f"Manifest {field} mismatch: {actual} != {expected}")
        raw_training_fingerprints = lsmc_settings.get(
            "training_scenario_fingerprints"
        )
        if not isinstance(raw_training_fingerprints, list) or len(
            raw_training_fingerprints
        ) != 3:
            raise ValueError("Manifest does not contain three training samples.")
        fingerprints = {
            *(str(value) for value in raw_training_fingerprints),
            str(validation.get("scenario_fingerprint", "")),
            str(evaluation.get("scenario_fingerprint", "")),
        }
        if "" in fingerprints or len(fingerprints) != 5:
            raise ValueError(
                "All three training, validation and evaluation fingerprints "
                "must differ."
            )
        materiality = _as_float(
            summary.get("profitability_materiality_bp"),
            "profitability_materiality_bp",
        )
        if not math.isclose(
            materiality,
            float(expected_args.profitability_materiality_bp),
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("Profitability materiality mismatch.")
        if expected_args.portfolio_contract_count is not None:
            contract_count = _as_float(
                summary.get("portfolio_contract_count"),
                "portfolio_contract_count",
            )
            if not math.isclose(
                contract_count,
                float(expected_args.portfolio_contract_count),
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            ):
                raise ValueError("Portfolio contract-count mismatch.")
    return _fit_basis_fingerprint(manifest)


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


def _hedge_summary_metrics(
    summary: Mapping[str, object],
    label: str,
) -> dict[str, float]:
    return {
        f"{label}_{metric}": _monetary(summary, metric)
        for metric in HEDGE_MONETARY_FIELDS
    }


def _validate_hedge_summary(
    summary: Mapping[str, object],
    label: str,
    hedge_cap_leg_mode: str,
) -> None:
    values = {
        metric: _monetary(summary, metric)
        for metric in HEDGE_MONETARY_FIELDS
    }
    component_cost = sum(
        values[metric]
        for metric in (
            "pv_hedge_option_fair_value_costs_aud",
            "pv_hedge_option_markup_costs_aud",
            "pv_hedge_management_fee_costs_aud",
            "pv_hedge_execution_costs_aud",
        )
    )
    total_cost = values["pv_hedge_costs_aud"]
    if not math.isclose(
        total_cost,
        component_cost,
        rel_tol=1.0e-10,
        abs_tol=1.0e-8,
    ):
        raise ValueError(
            f"{label} hedge-cost components do not reconcile: "
            f"{total_cost} != {component_cost}."
        )
    crediting_margin = _monetary(summary, "pv_crediting_margin_aud")
    backing_and_gain = (
        values["pv_money_market_income_aud"]
        + values["pv_hedge_gain_aud"]
    )
    if not math.isclose(
        crediting_margin,
        backing_and_gain,
        rel_tol=1.0e-10,
        abs_tol=1.0e-8,
    ):
        raise ValueError(
            f"{label} crediting-margin components do not reconcile: "
            f"{crediting_margin} != {backing_and_gain}."
        )
    if hedge_cap_leg_mode == HedgeCapLegMode.SOLD.value and not math.isclose(
        values["pv_hedge_gain_aud"],
        0.0,
        rel_tol=0.0,
        abs_tol=1.0e-8,
    ):
        raise ValueError(
            f"{label} reports hedge gain although the cap leg is sold."
        )


def _summary_metrics(summary: Mapping[str, object], label: str) -> dict[str, object]:
    output: dict[str, object] = {
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
    for metric in PHASE_MONETARY_FIELDS:
        output[f"{label}_{metric.removeprefix('pv_')}"] = _monetary(
            summary, metric
        )
    output.update(_hedge_summary_metrics(summary, label))
    output.update({
        f"{label}_{field}": value
        for field, value in _behaviour_metrics(summary).items()
    })
    return output


def _quantile(values: list[float], probability: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), probability))


def _scenario_result(
    rate: float,
    directory: Path,
    *,
    include_dynamic: bool,
    expected_stress: str = "base",
    expected_args: Optional[argparse.Namespace] = None,
) -> dict[str, object]:
    lsmc = _read_single_csv_row(directory / "portfolio_summary.csv")
    benchmark_directories = behaviour_benchmark_directories(directory)
    deterministic_continue = _read_single_csv_row(
        benchmark_directories["deterministic_election_continue"]
        / "portfolio_summary.csv"
    )
    deterministic_post = _read_single_csv_row(
        benchmark_directories["deterministic_election_post_behaviour"]
        / "portfolio_summary.csv"
    )
    variable_continue = _read_single_csv_row(
        benchmark_directories["variable_election_continue"]
        / "portfolio_summary.csv"
    )
    dynamic = (
        _read_single_csv_row(
            directory / "dynamic_benchmark" / "portfolio_summary.csv")
        if include_dynamic else None
    )
    with (directory / "run_manifest.json").open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    with (directory / "lsmc_validation_manifest.json").open(
        "r", encoding="utf-8"
    ) as handle:
        validation_manifest = json.load(handle)
    validation_settings = manifest.get("validation_settings")
    if not isinstance(validation_settings, Mapping):
        raise ValueError("LSMC manifest has no validation_settings object.")
    if not isinstance(validation_manifest, Mapping):
        raise ValueError("LSMC validation manifest is not a JSON object.")
    if str(validation_manifest.get("scenario_fingerprint")) != str(
        validation_settings.get("scenario_fingerprint")
    ):
        raise ValueError(
            "Validation and run manifests use different validation samples."
        )
    if expected_args is None:
        raise ValueError("Three-seed validation requires the requested seed basis.")
    training_fingerprints = _validate_multi_seed_evidence(
        directory,
        manifest,
        validation_manifest,
        expected_args=expected_args,
    )
    fit_basis_fingerprint = _validate_joint_policy_manifest(
        manifest,
        lsmc,
        expected_stress=expected_stress,
        expected_args=expected_args,
    )
    labelled_summaries: list[tuple[str, Mapping[str, object]]] = [
        ("LSMC", lsmc),
        ("deterministic/Continue", deterministic_continue),
        ("deterministic/Post", deterministic_post),
        ("variable/Continue", variable_continue),
    ]
    if dynamic is not None:
        labelled_summaries.append(("Dynamic", dynamic))
    manifest_hedge_mode = _manifest_hedge_cap_leg_mode(manifest)
    expected_hedge_mode = (
        expected_args.hedge_cap_leg_mode
        if expected_args is not None
        else manifest_hedge_mode
    )
    scenario_fingerprints: set[str] = set()
    for benchmark_label, summary in labelled_summaries:
        summary_rate = _as_float(
            summary.get("crediting_cap_rate"),
            f"{benchmark_label} crediting_cap_rate",
        )
        if not math.isclose(
            summary_rate, rate, rel_tol=0.0, abs_tol=1.0e-12
        ):
            raise ValueError(
                f"{benchmark_label} cap mismatch in {directory}: "
                f"{summary_rate} != {rate}"
            )
        summary_stress = str(summary.get("stress_scenario_id", ""))
        if summary_stress != expected_stress:
            raise ValueError(
                f"{benchmark_label} stress mismatch in {directory}: "
                f"{summary_stress!r} != {expected_stress!r}"
            )
        summary_hedge_mode = str(summary.get("hedge_cap_leg_mode", ""))
        if summary_hedge_mode != expected_hedge_mode:
            raise ValueError(
                f"{benchmark_label} hedge cap-leg mode mismatch in {directory}: "
                f"{summary_hedge_mode!r} != {expected_hedge_mode!r}"
            )
        _validate_hedge_summary(
            summary,
            benchmark_label,
            expected_hedge_mode,
        )
        fingerprint = str(summary.get("scenario_fingerprint", "")).strip()
        if not fingerprint:
            raise ValueError(
                f"{benchmark_label} summary has no scenario fingerprint."
            )
        scenario_fingerprints.add(fingerprint)
    if len(scenario_fingerprints) != 1:
        raise ValueError(
            "Behaviour benchmark summaries do not use one common evaluation "
            "scenario set."
        )
    actual_rate = _as_float(lsmc.get("crediting_cap_rate"), "crediting_cap_rate")

    _validate_aggregation_reconciliation(
        directory / "portfolio_aggregation_reconciliation.csv", "LSMC")
    _validate_aggregation_reconciliation(
        benchmark_directories["deterministic_election_continue"]
        / "portfolio_aggregation_reconciliation.csv",
        "deterministic Election / Continue",
    )
    _validate_aggregation_reconciliation(
        benchmark_directories["deterministic_election_post_behaviour"]
        / "portfolio_aggregation_reconciliation.csv",
        "deterministic Election / fitted post-Election behaviour",
    )
    _validate_aggregation_reconciliation(
        benchmark_directories["variable_election_continue"]
        / "portfolio_aggregation_reconciliation.csv",
        "fitted Election / Continue",
    )
    if include_dynamic:
        _validate_aggregation_reconciliation(
            directory / "dynamic_benchmark"
            / "portfolio_aggregation_reconciliation.csv",
            "Dynamic",
        )

    for benchmark_label, summary in labelled_summaries:
        total = _monetary(summary, "pv_policyholder_benefits_aud")
        phased = (
            _monetary(summary, "pv_policyholder_benefits_pre_election_aud")
            + _monetary(summary, "pv_policyholder_benefits_post_election_aud")
        )
        if not math.isclose(total, phased, rel_tol=1.0e-10, abs_tol=1.0e-8):
            raise ValueError(f"{benchmark_label} pre/post-Election PV does not reconcile.")

    all_actions = _read_csv(directory / "lsmc_action_summary.csv")
    action_seed_indices: set[int] = set()
    for action in all_actions:
        seed_index = int(_as_float(
            action.get("training_seed_index"),
            "action training_seed_index",
        ))
        if seed_index not in (1, 2, 3):
            raise ValueError("LSMC action summary has an unknown training seed.")
        action_seed_indices.add(seed_index)
        if _as_bool(action.get("primary_training_seed")) is not (
            seed_index == 1
        ):
            raise ValueError(
                "LSMC action summary has an inconsistent primary flag."
            )
    if action_seed_indices != {1, 2, 3}:
        raise ValueError("LSMC action summary does not cover all three seeds.")
    # Canonical cap-cell counts remain the predeclared Seed-1/V11 output.
    # Seed 2/3 distributions stay available in the direct action CSV.
    actions = [
        action for action in all_actions
        if _as_bool(action.get("primary_training_seed"))
    ]
    action_groups = {
        action_type: [
            item for item in actions
            if str(item.get("action_type", "")).strip().lower() == action_type
        ]
        for action_type in (
            "income_election",
            "continue",
            "partial_withdrawal",
            "full_withdrawal",
        )
    }
    if any(not group for group in action_groups.values()):
        raise ValueError(
            "LSMC action summary must separate Election and monthly "
            "Continue/Partial/Full actions."
        )

    def action_totals(action_type: str) -> tuple[int, int, int]:
        selected = eligible = forced = 0
        for item in action_groups[action_type]:
            selected += int(_first_float(
                item,
                (
                    "action_path_count",
                    "selected_action_path_count",
                    "start_income_path_count"
                    if action_type == "income_election"
                    else f"{action_type}_path_count",
                ),
                f"{action_type} action count",
            ))
            eligible += int(_as_float(
                item.get("eligible_path_count"), "eligible_path_count"
            ))
            if item.get("forced_path_count") not in (None, ""):
                forced += int(_as_float(
                    item.get("forced_path_count"), "forced_path_count"
                ))
        return selected, eligible, forced

    election_count, election_eligible, forced_election_count = action_totals(
        "income_election"
    )
    continue_count, continue_eligible, _ = action_totals("continue")
    partial_count, partial_eligible, _ = action_totals("partial_withdrawal")
    withdrawal_count, withdrawal_eligible, _ = action_totals("full_withdrawal")
    diagnostics = _read_csv(directory / "lsmc_regression_diagnostics.csv")
    diagnostic_seed_indices: set[int] = set()
    for diagnostic in diagnostics:
        seed_index = int(_as_float(
            diagnostic.get("training_seed_index"),
            "diagnostic training_seed_index",
        ))
        if seed_index not in (1, 2, 3):
            raise ValueError("LSMC regression diagnostic has an unknown seed.")
        diagnostic_seed_indices.add(seed_index)
        if str(diagnostic.get("training_scenario_fingerprint")) != (
            training_fingerprints[seed_index - 1]
        ):
            raise ValueError(
                "LSMC regression diagnostics changed a training fingerprint."
            )
        if _as_bool(diagnostic.get("primary_training_seed")) is not (
            seed_index == 1
        ):
            raise ValueError(
                "LSMC regression diagnostic has an inconsistent primary flag."
            )
    if diagnostic_seed_indices != {1, 2, 3}:
        raise ValueError("LSMC diagnostics do not cover all three training seeds.")
    diagnostic_groups = {
        action_type: [
            item for item in diagnostics
            if str(item.get("action_type", "")).strip().lower() == action_type
        ]
        for action_type in (
            "income_election",
            "partial_withdrawal",
            "full_withdrawal",
        )
    }
    if any(not group for group in diagnostic_groups.values()):
        raise ValueError(
            "LSMC regression diagnostics must separate Election, Partial and "
            "Full-Withdrawal fits."
        )
    # Only documented immaterial-no-fit rows legitimately have no numerical
    # R-squared/condition number.  Material missing/unstable regressions make
    # the validation manifest invalid and the scenario runner abort upstream.
    r_squared = [
        _as_float(row["oof_r_squared"], "oof_r_squared")
        for row in diagnostics
        if row.get("oof_r_squared") not in (None, "")
    ]
    conditions = [
        _as_float(row["condition_number"], "condition_number")
        for row in diagnostics
        if row.get("condition_number") not in (None, "")
    ]
    accepted = sum(_as_bool(
        row.get(
            "regression_accepted_for_action",
            row.get("regression_accepted_for_exercise"),
        )
    ) for row in diagnostics)
    try:
        summary_training_fingerprints = tuple(json.loads(str(
            lsmc.get("lsmc_training_scenario_fingerprints_json", "")
        )))
        summary_training_triplets = json.loads(str(
            lsmc.get("lsmc_training_seed_triplets_json", "")
        ))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("LSMC summary has no valid three-seed evidence.") from exc
    if summary_training_fingerprints != training_fingerprints:
        raise ValueError("LSMC summary changed the three training fingerprints.")
    if summary_training_triplets != list(
        _expected_training_seed_triplets(expected_args)
    ):
        raise ValueError("LSMC summary changed the three training seed triplets.")
    if int(_as_float(
        lsmc.get("lsmc_training_seed_count"), "lsmc_training_seed_count"
    )) != 3 or not _as_bool(
        lsmc.get("lsmc_validation_all_three_seeds_valid")
    ) or not _as_bool(
        lsmc.get("lsmc_final_evaluation_all_three_seeds_reported")
    ):
        raise ValueError("LSMC summary has incomplete three-seed evidence.")

    row: dict[str, object] = {
        "cap_rate": actual_rate,
        "cap_rate_percent": 100.0 * actual_rate,
        "stress_scenario_id": expected_stress,
        "hedge_cap_leg_mode": expected_hedge_mode,
        "valuation_basis": (
            "absolute_portfolio"
            if _as_bool(lsmc.get("absolute_portfolio_values_available"))
            else "normalised_average_contract"
        ),
        "premium_aud": _monetary(lsmc, "premium_aud"),
        **_summary_metrics(deterministic_continue, "continue"),
        **_summary_metrics(deterministic_post, "deterministic_post"),
        **_summary_metrics(variable_continue, "variable_continue"),
        **_summary_metrics(lsmc, "lsmc"),
        "lsmc_income_election_action_path_count": election_count,
        "lsmc_income_election_eligible_path_count": election_eligible,
        "lsmc_forced_income_election_path_count": forced_election_count,
        "lsmc_continue_action_path_count": continue_count,
        "lsmc_continue_eligible_path_count": continue_eligible,
        "lsmc_partial_withdrawal_action_path_count": partial_count,
        "lsmc_partial_withdrawal_eligible_path_count": partial_eligible,
        "lsmc_full_withdrawal_action_path_count": withdrawal_count,
        "lsmc_full_withdrawal_eligible_path_count": withdrawal_eligible,
        # Unweighted fit diagnostics, not portfolio take-up/surrender rates.
        "lsmc_unweighted_income_election_action_rate": (
            election_count / election_eligible if election_eligible else 0.0
        ),
        "lsmc_unweighted_full_withdrawal_action_rate": (
            withdrawal_count / withdrawal_eligible
            if withdrawal_eligible else 0.0
        ),
        "lsmc_unweighted_partial_withdrawal_action_rate": (
            partial_count / partial_eligible if partial_eligible else 0.0
        ),
        "lsmc_unique_policy_fits": int(
            manifest["lsmc_settings"]["unique_policy_fits"]),
        "lsmc_training_fallback_policy_count": int(_first_float(
            manifest["lsmc_settings"],
            (
                "training_fallback_policy_count",
                "training_fallback_fit_count",
            ),
            "training fallback policy count",
        )),
        "lsmc_regression_count": len(diagnostics),
        "lsmc_regression_accepted_count": accepted,
        "lsmc_regression_rejected_count": len(diagnostics) - accepted,
        "lsmc_oof_r_squared_q25": (
            None if not r_squared else _quantile(r_squared, 0.25)
        ),
        "lsmc_oof_r_squared_median": (
            None if not r_squared else _quantile(r_squared, 0.50)
        ),
        "lsmc_condition_number_median": (
            None if not conditions else _quantile(conditions, 0.50)
        ),
        "lsmc_condition_number_max": (
            None if not conditions else max(conditions)
        ),
        "evaluation_scenario_fingerprint": manifest[
            "evaluation_settings"]["scenario_fingerprint"],
        "training_scenario_fingerprint": manifest[
            "lsmc_settings"]["training_scenario_fingerprint"],
        "training_scenario_fingerprints_json": json.dumps(
            list(training_fingerprints)
        ),
        "training_scenario_fingerprint_1": training_fingerprints[0],
        "training_scenario_fingerprint_2": training_fingerprints[1],
        "training_scenario_fingerprint_3": training_fingerprints[2],
        "training_seed_triplets_json": json.dumps(
            list(_expected_training_seed_triplets(expected_args)),
            sort_keys=True,
        ),
        "primary_training_seed_index": 1,
        "every_training_seed_passes_validation": True,
        "evaluation_used_for_training_seed_selection": False,
        "validation_scenario_fingerprint": manifest[
            "validation_settings"]["scenario_fingerprint"],
        "lsmc_fit_basis_fingerprint": fit_basis_fingerprint,
        "lsmc_multi_seed_validation_evaluation_csv": str(
            directory / "lsmc_multi_seed_validation_evaluation.csv"
        ),
        "scenario_directory": str(directory),
    }
    row.update({
        metric: _monetary(lsmc, metric)
        for metric in HEDGE_MONETARY_FIELDS
    })
    for action_type, group in diagnostic_groups.items():
        prefix = "election" if action_type == "income_election" else "withdrawal"
        group_accepted = sum(
            _as_bool(item.get(
                "regression_accepted_for_action",
                item.get("regression_accepted_for_exercise"),
            ))
            for item in group
        )
        row[f"lsmc_{prefix}_regression_accepted_share"] = (
            group_accepted / len(group)
        )
        group_r_squared = [
            _as_float(item["oof_r_squared"], "oof_r_squared")
            for item in group
            if item.get("oof_r_squared") not in (None, "")
        ]
        row[f"lsmc_{prefix}_oof_r_squared_median"] = (
            None
            if not group_r_squared
            else _quantile(group_r_squared, 0.50)
        )
    if dynamic is not None:
        row.update(_summary_metrics(dynamic, "dynamic"))
    row.update({
        "lsmc_minus_continue_policyholder_benefits_aud": (
            float(row["lsmc_policyholder_benefits_aud"])
            - float(row["continue_policyholder_benefits_aud"])),
    })
    for metric in ("policyholder_benefits_aud", "insurer_npv_aud"):
        value_00 = float(row[f"continue_{metric}"])
        value_01 = float(row[f"deterministic_post_{metric}"])
        value_10 = float(row[f"variable_continue_{metric}"])
        value_11 = float(row[f"lsmc_{metric}"])
        election_effect = value_10 - value_00
        post_effect = value_01 - value_00
        interaction = value_11 - value_10 - value_01 + value_00
        total = value_11 - value_00
        prefix = f"lsmc_factorial_{metric.removesuffix('_aud')}"
        row.update({
            f"{prefix}_income_election_effect_aud": election_effect,
            f"{prefix}_post_election_effect_aud": post_effect,
            f"{prefix}_interaction_effect_aud": interaction,
            f"{prefix}_total_effect_aud": total,
            f"{prefix}_reconciliation_gap_aud": (
                total - election_effect - post_effect - interaction
            ),
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
    delta_fields = (
        "lsmc_policyholder_benefits_aud",
        "lsmc_future_fees_aud",
        "lsmc_guarantee_claims_aud",
        "lsmc_crediting_margin_aud",
        "lsmc_bel_total_aud",
        "lsmc_insurer_npv_aud",
        "lsmc_new_business_margin",
        "lsmc_income_start_year_mean",
        "lsmc_income_start_year_median",
        "lsmc_income_election_share",
        "lsmc_forced_income_election_share",
        "lsmc_mean_growth_duration",
        "lsmc_growth_phase_exposure",
        "lsmc_income_phase_exposure",
        "lsmc_total_income_lapse_rate",
        "lsmc_unweighted_income_election_action_rate",
        "lsmc_unweighted_partial_withdrawal_action_rate",
        "lsmc_unweighted_full_withdrawal_action_rate",
    )
    optional_fields = (
        "dynamic_policyholder_benefits_aud",
        "dynamic_insurer_npv_aud",
    )
    stress_ids = list(dict.fromkeys(
        str(row.get("stress_scenario_id", "base")) for row in rows
    ))
    for stress_id in stress_ids:
        group = [
            row for row in rows
            if str(row.get("stress_scenario_id", "base")) == stress_id
        ]
        by_rate = {_rate_key(float(row["cap_rate"])): row for row in group}
        baseline = by_rate[_rate_key(baseline_rate)]
        for row in group:
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
        "# Einfluss von Crediting Cap und Stress auf LSMC-Optimalverhalten",
        "",
        "Alle Geldwerte sind AUD auf der in `valuation_basis` ausgewiesenen Basis.",
        (
            "Hedge-Cap-Leg-Modus: "
            f"`{rows[0]['hedge_cap_leg_mode']}`. `sold` ist der Standardfall; "
            "`not_sold` behaelt den Hedge-Payoff oberhalb des Kunden-Caps."
        ),
        (
            "Jede Cap×Stress-Zelle wurde als gemeinsame Election-/Post-Election-"
            "Policy separat trainiert; Training, Validation und Evaluation "
            "sind getrennt. "
            "Growth-Aktionen sind WAIT/START_INCOME, Income-Aktionen "
            "CONTINUE/PARTIAL_WITHDRAWAL/FULL_WITHDRAWAL."
        ),
        (
            "Income-Election-, Forced-Election-, Phasen- und Lapse-Kennzahlen "
            "sind portfolio-/Q-pfad-/In-force-gewichtet. Die Action-"
            "Raten sind ungewichtete Fit-Diagnostik und weder Take-up- noch "
            "Surrender-Rate des Portfolios."
        ),
        "",
        (
            "| Stress | Cap | Start mean | median | p10 | p90 | Election | "
            "Forced | Growth-Dauer | Income-Lapse | Election action | "
            "Partial action | Full Withdrawal action | PH Benefits | Insurer NPV |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['stress_scenario_id']} | "
            f"{float(row['cap_rate_percent']):.2f}% | "
            f"{float(row['lsmc_income_start_year_mean']):.3f} | "
            f"{float(row['lsmc_income_start_year_median']):.3f} | "
            f"{float(row['lsmc_income_start_year_p10']):.3f} | "
            f"{float(row['lsmc_income_start_year_p90']):.3f} | "
            f"{100.0 * float(row['lsmc_income_election_share']):.3f}% | "
            f"{100.0 * float(row['lsmc_forced_income_election_share']):.3f}% | "
            f"{float(row['lsmc_mean_growth_duration']):.3f} | "
            f"{100.0 * float(row['lsmc_total_income_lapse_rate']):.3f}% | "
            f"{100.0 * float(row['lsmc_unweighted_income_election_action_rate']):.3f}% | "
            f"{100.0 * float(row['lsmc_unweighted_partial_withdrawal_action_rate']):.3f}% | "
            f"{100.0 * float(row['lsmc_unweighted_full_withdrawal_action_rate']):.3f}% | "
            f"{float(row['lsmc_policyholder_benefits_aud']):,.2f} | "
            f"{float(row['lsmc_insurer_npv_aud']):,.2f} |"
        )
    hedge_report_benchmarks = [
        ("V00 deterministic Election / Continue", "continue"),
        ("V01 deterministic Election / Post Behaviour", "deterministic_post"),
        ("V10 fitted Election / Continue", "variable_continue"),
        ("V11 joint LSMC", "lsmc"),
    ]
    if has_dynamic:
        hedge_report_benchmarks.append(("Dynamic benchmark", "dynamic"))
    lines.extend([
        "",
        "## Money-Market- und Hedge-Komponenten aller Behaviour-Arme",
        "",
        (
            "Die Komponenten stammen getrennt aus `pv_money_market_income_aud`, "
            "`pv_hedge_gain_aud`, `pv_hedge_option_fair_value_costs_aud`, "
            "`pv_hedge_option_markup_costs_aud`, "
            "`pv_hedge_management_fee_costs_aud`, "
            "`pv_hedge_execution_costs_aud` und `pv_hedge_costs_aud`."
        ),
        "",
        (
            "| Stress | Cap | Behaviour-Arm | MM income | Hedge gain | "
            "Fair option | Markup | Management fee | Execution | "
            "Hedge costs total |"
        ),
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        for benchmark_label, prefix in hedge_report_benchmarks:
            lines.append(
                f"| {row['stress_scenario_id']} | "
                f"{float(row['cap_rate_percent']):.2f}% | "
                f"{benchmark_label} | "
                f"{float(row[f'{prefix}_pv_money_market_income_aud']):,.2f} | "
                f"{float(row[f'{prefix}_pv_hedge_gain_aud']):,.2f} | "
                f"{float(row[f'{prefix}_pv_hedge_option_fair_value_costs_aud']):,.2f} | "
                f"{float(row[f'{prefix}_pv_hedge_option_markup_costs_aud']):,.2f} | "
                f"{float(row[f'{prefix}_pv_hedge_management_fee_costs_aud']):,.2f} | "
                f"{float(row[f'{prefix}_pv_hedge_execution_costs_aud']):,.2f} | "
                f"{float(row[f'{prefix}_pv_hedge_costs_aud']):,.2f} |"
            )
    lines.extend([
        "",
        "## 2×2-Zerlegung der gemeinsamen Policy",
        "",
        (
            "V00 ist deterministische Election + Continue, V01 "
            "deterministische Election + gefittetes Post-Election Behaviour, "
            "V10 gefittete Election + Continue und V11 die vollständige "
            "gemeinsame Policy."
        ),
        "",
        "| Stress | Cap | Kennzahl | Election | Post | Interaktion | Gesamt | Gap |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        for metric, label in (
            ("policyholder_benefits", "PH Benefits"),
            ("insurer_npv", "Insurer NPV"),
        ):
            prefix = f"lsmc_factorial_{metric}"
            lines.append(
                f"| {row['stress_scenario_id']} | "
                f"{float(row['cap_rate_percent']):.2f}% | {label} | "
                f"{float(row[f'{prefix}_income_election_effect_aud']):,.2f} | "
                f"{float(row[f'{prefix}_post_election_effect_aud']):,.2f} | "
                f"{float(row[f'{prefix}_interaction_effect_aud']):,.2f} | "
                f"{float(row[f'{prefix}_total_effect_aud']):,.2f} | "
                f"{float(row[f'{prefix}_reconciliation_gap_aud']):.3e} |"
            )
    if has_dynamic:
        lines.extend([
            "",
            "Die vollständige Dynamic-Policy ist zusätzlich in der CSV als "
            "separater statistischer Benchmark enthalten; sie ist keine der "
            "vier LSMC-Faktorzellen.",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_plot(path: Path, rows: list[dict[str, object]]) -> Optional[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    stress_ids = list(dict.fromkeys(
        str(row.get("stress_scenario_id", "base")) for row in rows
    ))
    fig, axes = plt.subplots(3, 1, figsize=(11.5, 13.0), sharex=True)
    for stress_id in stress_ids:
        group = [
            row for row in rows
            if str(row.get("stress_scenario_id", "base")) == stress_id
        ]
        caps = np.asarray([float(row["cap_rate_percent"]) for row in group])
        axes[0].plot(
            caps,
            [100.0 * float(row["lsmc_unweighted_income_election_action_rate"])
             for row in group],
            marker="o",
            label=f"{stress_id}: Election",
        )
        axes[0].plot(
            caps,
            [100.0 * float(row["lsmc_unweighted_partial_withdrawal_action_rate"])
             for row in group],
            marker="^",
            linestyle=":",
            label=f"{stress_id}: Partial Withdrawal",
        )
        axes[0].plot(
            caps,
            [100.0 * float(row["lsmc_unweighted_full_withdrawal_action_rate"])
             for row in group],
            marker="s",
            linestyle="--",
            label=f"{stress_id}: Full Withdrawal",
        )
        axes[1].plot(
            caps,
            [float(row["lsmc_income_start_year_mean"]) for row in group],
            marker="o",
            label=stress_id,
        )
        axes[2].plot(
            caps,
            [float(row["lsmc_insurer_npv_aud"]) for row in group],
            marker="o",
            label=stress_id,
        )
    axes[0].set_ylabel("unweighted action rate (%)")
    axes[0].set_title(
        "Separate LSMC Election, Partial- and Full-Withdrawal diagnostics"
    )
    axes[0].legend(fontsize=8, ncol=2)
    axes[0].grid(alpha=0.25)
    axes[1].set_ylabel("mean Income start policy year")
    axes[1].set_title("Portfolio-weighted Income-Election timing")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.25)
    axes[2].axhline(0.0, color="black", linewidth=0.8)
    axes[2].set_ylabel("Insurer NPV (AUD)")
    axes[2].set_xlabel("Crediting cap (%)")
    axes[2].legend(fontsize=8)
    axes[2].grid(alpha=0.25)
    fig.suptitle("Cap×stress sensitivity of the joint LSMC behaviour policy")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return str(matplotlib.__version__)


def _scenario_directory(output: Path, stress_id: str, rate: float) -> Path:
    if stress_id == "base":
        return output / "scenarios" / _rate_directory_name(rate)
    return (
        output
        / "stress_scenarios"
        / stress_id
        / _rate_directory_name(rate)
    )


def _required_scenario_outputs(
    scenario_output: Path,
    *,
    include_dynamic: bool,
) -> tuple[Path, ...]:
    benchmark_directories = behaviour_benchmark_directories(scenario_output)
    required = (
        scenario_output / "portfolio_summary.csv",
        scenario_output / "run_manifest.json",
        scenario_output / "lsmc_action_summary.csv",
        scenario_output / "lsmc_regression_diagnostics.csv",
        scenario_output / "lsmc_validation_summary.csv",
        scenario_output / "lsmc_validation_manifest.json",
        scenario_output / "lsmc_multi_seed_validation_evaluation.csv",
        benchmark_directories["variable_election_continue"]
        / "portfolio_summary.csv",
        benchmark_directories["variable_election_continue"]
        / "portfolio_aggregation_reconciliation.csv",
        benchmark_directories["deterministic_election_continue"]
        / "portfolio_summary.csv",
        benchmark_directories["deterministic_election_continue"]
        / "portfolio_aggregation_reconciliation.csv",
        benchmark_directories["deterministic_election_post_behaviour"]
        / "portfolio_summary.csv",
        benchmark_directories["deterministic_election_post_behaviour"]
        / "portfolio_aggregation_reconciliation.csv",
    )
    if include_dynamic:
        required = (
            *required,
            scenario_output / "dynamic_benchmark" / "portfolio_summary.csv",
            scenario_output / "dynamic_benchmark"
            / "portfolio_aggregation_reconciliation.csv",
        )
    return required


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    for artifact_name in (
        "lsmc_cap_behaviour_comparison.csv",
        "lsmc_cap_behaviour_report.md",
        "comparison_manifest.json",
    ):
        stale_artifact = (output / artifact_name).resolve()
        if stale_artifact.parent != output:
            raise RuntimeError("Unsafe stale cap-comparison output path.")
        if stale_artifact.is_file():
            stale_artifact.unlink()
    rates = sorted({_rate_key(rate) for rate in (*args.cap_rates, args.baseline_rate)})
    rows: list[dict[str, object]] = []
    commands: list[dict[str, object]] = []
    cells = [
        (stress_id, rate)
        for stress_id in args.stress_scenarios
        for rate in rates
    ]
    for index, (stress_id, rate) in enumerate(cells, start=1):
        scenario_output = _scenario_directory(output, stress_id, rate)
        include_dynamic = not args.no_dynamic_benchmark
        required = _required_scenario_outputs(
            scenario_output,
            include_dynamic=include_dynamic,
        )
        command = _scenario_command(args, rate, stress_id, scenario_output)
        scenario_row: Optional[dict[str, object]] = None
        reuse_validation = "not_requested"
        if args.reuse_existing and all(path.is_file() for path in required):
            try:
                scenario_row = _scenario_result(
                    rate,
                    scenario_output,
                    include_dynamic=include_dynamic,
                    expected_stress=stress_id,
                    expected_args=args,
                )
                reuse_validation = "validated"
            except (OSError, ValueError, TypeError, KeyError, csv.Error) as exc:
                reuse_validation = (
                    f"rejected_{type(exc).__name__}:"
                    + " ".join(str(exc).split())
                )
                log_to_console(
                    f"[{index}/{len(cells)}] Reject reuse {stress_id} / "
                    f"{100 * rate:.2f}%: {exc}",
                    level="WARNING",
                )
        elif args.reuse_existing:
            reuse_validation = "rejected_incomplete"

        if scenario_row is None:
            log_to_console(
                f"[{index}/{len(cells)}] Fit {stress_id} / cap {100 * rate:.2f}%"
            )
            subprocess.run(
                command,
                check=True,
                cwd=str(SCRIPT_DIRECTORY.parent),
            )
            scenario_row = _scenario_result(
                rate,
                scenario_output,
                include_dynamic=include_dynamic,
                expected_stress=stress_id,
                expected_args=args,
            )
        else:
            log_to_console(
                f"[{index}/{len(cells)}] Reuse {stress_id} / "
                f"cap {100 * rate:.2f}%"
            )
        rows.append(scenario_row)
        commands.append({
            "stress_scenario_id": stress_id,
            "crediting_cap_rate": rate,
            "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
            "execution_mode": (
                "reused" if reuse_validation == "validated" else "executed"
            ),
            "reuse_validation": reuse_validation,
            "command": command,
            "scenario_directory": str(scenario_output),
            "lsmc_fit_basis_fingerprint": scenario_row[
                "lsmc_fit_basis_fingerprint"
            ],
        })

    evaluation_fingerprints_by_stress: dict[str, str] = {}
    training_fingerprints_by_stress: dict[str, str] = {}
    all_training_fingerprints_by_stress: dict[str, list[str]] = {}
    validation_fingerprints_by_stress: dict[str, str] = {}
    for stress_id in args.stress_scenarios:
        group = [row for row in rows if row["stress_scenario_id"] == stress_id]
        evaluation_fingerprints = {
            str(row["evaluation_scenario_fingerprint"]) for row in group
        }
        training_fingerprints = {
            str(row["training_scenario_fingerprint"]) for row in group
        }
        encoded_training_fingerprints = {
            str(row["training_scenario_fingerprints_json"]) for row in group
        }
        seed_triplet_evidence = {
            str(row["training_seed_triplets_json"]) for row in group
        }
        validation_fingerprints = {
            str(row["validation_scenario_fingerprint"]) for row in group
        }
        if (
            len(evaluation_fingerprints) != 1
            or len(training_fingerprints) != 1
            or len(encoded_training_fingerprints) != 1
            or len(seed_triplet_evidence) != 1
            or len(validation_fingerprints) != 1
        ):
            raise ValueError(
                f"Cap scenarios for {stress_id!r} do not use common path sets."
            )
        evaluation_fingerprint = next(iter(evaluation_fingerprints))
        training_fingerprint = next(iter(training_fingerprints))
        try:
            all_training_fingerprints = tuple(json.loads(
                next(iter(encoded_training_fingerprints))
            ))
            recorded_seed_triplets = json.loads(
                next(iter(seed_triplet_evidence))
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Cap scenarios for {stress_id!r} have malformed three-seed "
                "evidence."
            ) from exc
        if len(all_training_fingerprints) != 3 or all_training_fingerprints[0] \
                != training_fingerprint:
            raise ValueError(
                f"Cap scenarios for {stress_id!r} changed primary seed 1."
            )
        expected_seed_triplets = list(_expected_training_seed_triplets(args))
        if recorded_seed_triplets != expected_seed_triplets:
            raise ValueError(
                f"Cap scenarios for {stress_id!r} changed training seeds."
            )
        for row in group:
            explicit = tuple(
                str(row[f"training_scenario_fingerprint_{index}"])
                for index in range(1, 4)
            )
            if explicit != all_training_fingerprints:
                raise ValueError(
                    f"Cap scenarios for {stress_id!r} have inconsistent "
                    "training fingerprints."
                )
            if int(row["primary_training_seed_index"]) != 1 or not _as_bool(
                row["every_training_seed_passes_validation"]
            ) or _as_bool(row["evaluation_used_for_training_seed_selection"]):
                raise ValueError(
                    f"Cap scenarios for {stress_id!r} violate the three-seed "
                    "acceptance rule."
                )
        validation_fingerprint = next(iter(validation_fingerprints))
        if len({
            evaluation_fingerprint,
            *all_training_fingerprints,
            validation_fingerprint,
        }) != 5:
            raise ValueError(
                "All three training, validation and evaluation fingerprints "
                "must differ."
            )
        evaluation_fingerprints_by_stress[stress_id] = evaluation_fingerprint
        training_fingerprints_by_stress[stress_id] = training_fingerprint
        all_training_fingerprints_by_stress[stress_id] = list(
            all_training_fingerprints
        )
        validation_fingerprints_by_stress[stress_id] = validation_fingerprint
    fit_fingerprints = {
        str(row["lsmc_fit_basis_fingerprint"]) for row in rows
    }
    if len(fit_fingerprints) != len(rows):
        raise ValueError(
            "A Joint-Policy fit basis was reused across distinct cap×stress "
            "cells; every cell must be refitted."
        )
    for row in rows:
        for metric in ("policyholder_benefits", "insurer_npv"):
            gap = float(row[
                f"lsmc_factorial_{metric}_reconciliation_gap_aud"
            ])
            if not math.isclose(gap, 0.0, rel_tol=1.0e-10, abs_tol=1.0e-8):
                raise ValueError("LSMC factorial decomposition does not reconcile.")
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
        "purpose": "crediting_cap_and_stress_impact_on_joint_lsmc_behaviour",
        "contractual_base_cap_rate": DEFAULT_BASELINE_RATE,
        "comparison_baseline_rate": args.baseline_rate,
        "scenario_cap_rates": rates,
        "stress_scenarios": args.stress_scenarios,
        "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
        "joint_policy_refitted_for_every_cap_stress_cell": True,
        "income_election_action_set": ["WAIT", "START_INCOME"],
        "post_income_action_set": [
            "CONTINUE",
            "PARTIAL_WITHDRAWAL",
            "FULL_WITHDRAWAL",
        ],
        "decision_grid": {
            "income_election": "contractual_policy_anniversaries",
            "income_actions": "monthly",
        },
        "forced_income_start": (
            "first_policy_anniversary_after_primary_attains_age_100"
        ),
        "joint_life_behaviour": (
            "pathwise_separate_primary_and_spouse_life_status"
        ),
        "dynamic_benchmark_included": not args.no_dynamic_benchmark,
        "evaluation_scenario_fingerprint_by_stress": (
            evaluation_fingerprints_by_stress
        ),
        "training_scenario_fingerprint_by_stress": (
            training_fingerprints_by_stress
        ),
        "training_scenario_fingerprints_by_stress": (
            all_training_fingerprints_by_stress
        ),
        "validation_scenario_fingerprint_by_stress": (
            validation_fingerprints_by_stress
        ),
        "lsmc_fit_basis_fingerprint_by_cell": {
            (
                f"{row['stress_scenario_id']}|"
                f"{float(row['cap_rate_percent']):.8f}%"
            ): row["lsmc_fit_basis_fingerprint"]
            for row in rows
        },
        "training_validation_evaluation_are_distinct": True,
        "all_three_training_validation_evaluation_are_distinct": True,
        "every_training_seed_passes_election_income_combined": True,
        "primary_training_seed_index": 1,
        "evaluation_used_for_training_seed_selection": False,
        "multi_seed_validation_evaluation_csv_required_per_cell": True,
        "settings": {
            "n_paths": args.n_paths,
            "seed": args.seed,
            "take_up_seed": args.take_up_seed,
            "mortality_seed": args.mortality_seed,
            "n_train": args.n_train,
            "train_seed": args.train_seed,
            "train_take_up_seed": args.train_take_up_seed,
            "train_mortality_seed": args.train_mortality_seed,
            "train_seed_2": args.train_seed_2,
            "train_take_up_seed_2": args.train_take_up_seed_2,
            "train_mortality_seed_2": args.train_mortality_seed_2,
            "train_seed_3": args.train_seed_3,
            "train_take_up_seed_3": args.train_take_up_seed_3,
            "train_mortality_seed_3": args.train_mortality_seed_3,
            "training_seed_triplets": list(
                _expected_training_seed_triplets(args)
            ),
            "primary_training_seed_index": 1,
            "training_seed_selection_rule": (
                "predeclared_seed_1_not_evaluation_based"
            ),
            "n_validation": args.n_validation,
            "validation_seed": args.validation_seed,
            "validation_take_up_seed": args.validation_take_up_seed,
            "validation_mortality_seed": args.validation_mortality_seed,
            "heston_substeps": args.heston_substeps,
            "hedge_cap_leg_mode": args.hedge_cap_leg_mode,
            "lsmc_folds": args.lsmc_folds,
            "lsmc_ridge": args.lsmc_ridge,
            "exercise_buffer_rmse_multiplier": (
                args.exercise_buffer_rmse_multiplier),
        },
        "model_limitations": [
            "Every non-6% cap is a non-contractual design sensitivity.",
            "Income Election is annual; Continue, Partial and Full Withdrawal "
            "are monthly LSMC actions.",
            "Deterministic model-point Income Election is retained only in explicit factorial benchmarks.",
            "Partial withdrawal uses a finite adaptive gross-amount grid.",
            (
                "Election, Partial- and Full-Withdrawal action counts are unweighted "
                "model-point/path/decision-event diagnostics, not portfolio-"
                "weighted take-up or surrender rates."
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
            "scenario_root": str(output / "scenarios"),
            "stress_scenario_root": str(output / "stress_scenarios"),
        },
        "commands": commands,
        "reporting": {
            "behaviour_metric_weighting": (
                "model_point_contract_weight_x_q_path_probability_x_"
                "pathwise_in_force_survival_weight"
            ),
            "lsmc_action_diagnostic_weighting": (
                "unweighted_eligible_model_point_path_decision_events"
            ),
            "money_market_and_hedge_components": list(HEDGE_MONETARY_FIELDS),
        },
        "matplotlib_version": matplotlib_version,
        "results": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True,
                  allow_nan=False, default=str)
        handle.write("\n")
    log_to_console(f"Comparison CSV: {comparison_csv}")
    log_to_console(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
