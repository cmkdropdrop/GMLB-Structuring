"""Strict loader for repository Monte-Carlo analysis inputs."""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Optional

CODE_ROOT = Path(__file__).resolve().parents[1]
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from policy_engine.repository_paths import (  # noqa: E402
    DEFAULT_MC_ANALYSIS_PATH as DEFAULT_MC_ANALYSIS_INPUT_PATH,
    PROJECT_ROOT as REPOSITORY_ROOT,
)

MC_ANALYSIS_COLUMNS = (
    "sample_role",
    "seed_set",
    "n_paths",
    "market_seed",
    "take_up_seed",
    "mortality_seed",
    "description",
)


@dataclass(frozen=True)
class MonteCarloAnalysisInput:
    """One complete, numbered random-number sample definition."""

    sample_role: str
    seed_set: int
    n_paths: int
    market_seed: int
    take_up_seed: int
    mortality_seed: int
    description: str = ""


def _parse_integer(
    raw: object,
    *,
    column: str,
    row_number: int,
    path: Path,
    positive: bool,
) -> int:
    text = str(raw).strip()
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(
            f"{path}: row {row_number} has invalid integer {column}={text!r}."
        ) from exc
    if positive and value <= 0:
        raise ValueError(
            f"{path}: row {row_number} requires positive {column}."
        )
    if not positive and value < 0:
        raise ValueError(
            f"{path}: row {row_number} requires non-negative {column}."
        )
    return value


def load_mc_analysis_inputs(
    path: Optional[Path] = None,
) -> Mapping[str, tuple[MonteCarloAnalysisInput, ...]]:
    """Load and validate all sample roles from the repository CSV."""

    source = (
        DEFAULT_MC_ANALYSIS_INPUT_PATH
        if path is None
        else Path(path).expanduser().resolve()
    )
    if not source.is_file():
        raise FileNotFoundError(f"Monte-Carlo input CSV not found: {source}")

    grouped: dict[str, list[MonteCarloAnalysisInput]] = {}
    seen: set[tuple[str, int]] = set()
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MC_ANALYSIS_COLUMNS:
            raise ValueError(
                f"{source}: expected CSV columns {MC_ANALYSIS_COLUMNS}, "
                f"got {tuple(reader.fieldnames or ())}."
            )
        for row_number, row in enumerate(reader, start=2):
            role = str(row["sample_role"]).strip()
            if not role:
                raise ValueError(
                    f"{source}: row {row_number} has an empty sample_role."
                )
            seed_set = _parse_integer(
                row["seed_set"],
                column="seed_set",
                row_number=row_number,
                path=source,
                positive=True,
            )
            key = (role, seed_set)
            if key in seen:
                raise ValueError(
                    f"{source}: duplicate sample role/seed set {key!r}."
                )
            seen.add(key)
            sample = MonteCarloAnalysisInput(
                sample_role=role,
                seed_set=seed_set,
                n_paths=_parse_integer(
                    row["n_paths"],
                    column="n_paths",
                    row_number=row_number,
                    path=source,
                    positive=True,
                ),
                market_seed=_parse_integer(
                    row["market_seed"],
                    column="market_seed",
                    row_number=row_number,
                    path=source,
                    positive=False,
                ),
                take_up_seed=_parse_integer(
                    row["take_up_seed"],
                    column="take_up_seed",
                    row_number=row_number,
                    path=source,
                    positive=False,
                ),
                mortality_seed=_parse_integer(
                    row["mortality_seed"],
                    column="mortality_seed",
                    row_number=row_number,
                    path=source,
                    positive=False,
                ),
                description=str(row["description"]).strip(),
            )
            grouped.setdefault(role, []).append(sample)

    if not grouped:
        raise ValueError(f"Monte-Carlo input CSV is empty: {source}")

    validated: dict[str, tuple[MonteCarloAnalysisInput, ...]] = {}
    for role, samples in grouped.items():
        ordered = tuple(sorted(samples, key=lambda item: item.seed_set))
        expected_sets = tuple(range(1, len(ordered) + 1))
        actual_sets = tuple(item.seed_set for item in ordered)
        if actual_sets != expected_sets:
            raise ValueError(
                f"{source}: sample role {role!r} must use consecutive "
                f"seed_set values starting at 1; got {actual_sets}."
            )
        path_counts = {item.n_paths for item in ordered}
        if len(path_counts) != 1:
            raise ValueError(
                f"{source}: all seed sets for sample role {role!r} must use "
                "the same n_paths value."
            )
        validated[role] = ordered
    return MappingProxyType(validated)


def require_mc_samples(
    inputs: Mapping[str, tuple[MonteCarloAnalysisInput, ...]],
    sample_role: str,
    count: int,
) -> tuple[MonteCarloAnalysisInput, ...]:
    """Return exactly the number of seed sets selected by the caller."""

    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("Monte-Carlo sample count must be a positive integer.")
    available = inputs.get(sample_role, ())
    if len(available) < count:
        raise ValueError(
            f"Sample role {sample_role!r} provides {len(available)} seed "
            f"set(s), but the script requires {count}."
        )
    return tuple(available[:count])


__all__ = [
    "DEFAULT_MC_ANALYSIS_INPUT_PATH",
    "MC_ANALYSIS_COLUMNS",
    "MonteCarloAnalysisInput",
    "load_mc_analysis_inputs",
    "require_mc_samples",
]
