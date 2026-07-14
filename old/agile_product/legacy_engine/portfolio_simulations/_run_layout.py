"""Shared physical output layout for Behaviour benchmark runs."""

from __future__ import annotations

from pathlib import Path


BEHAVIOUR_BENCHMARK_RELATIVE_DIRECTORIES = {
    "deterministic_election_continue": Path("bench") / "v00",
    "deterministic_election_post_behaviour": Path("bench") / "v01",
    "variable_election_continue": Path("bench") / "v10",
}


def behaviour_benchmark_directories(root: Path) -> dict[str, Path]:
    """Map stable logical benchmark IDs to compact physical directories."""
    return {
        benchmark_id: root / relative_directory
        for benchmark_id, relative_directory in (
            BEHAVIOUR_BENCHMARK_RELATIVE_DIRECTORIES.items()
        )
    }


__all__ = [
    "BEHAVIOUR_BENCHMARK_RELATIVE_DIRECTORIES",
    "behaviour_benchmark_directories",
]
