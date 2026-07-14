"""Independent validation gates for frozen optimal-behaviour policies.

The routines in this module never fit, tune or mutate a policy.  They compare
pathwise risk-neutral Policyholder present values on one held-out validation
sample using common random numbers.  The final valuation sample therefore
remains untouched by policy selection and model-quality gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import numpy as np
from numpy.typing import NDArray


Array = NDArray[np.float64]


def _path_values(value: object, *, name: str) -> Array:
    array = np.asarray(value, dtype=float)
    if array.ndim != 1 or array.size < 2:
        raise ValueError(f"{name} must contain at least two path values.")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} path values must be finite.")
    snapshot = np.array(array, dtype=float, copy=True)
    snapshot.setflags(write=False)
    return snapshot


@dataclass(frozen=True)
class PairedPolicyValidationGate:
    """One paired non-inferiority test against the best fixed benchmark."""

    component: str
    benchmark_name: str
    path_count: int
    policy_mean_aud: float
    benchmark_mean_aud: float
    paired_difference_mean_aud: float
    paired_standard_error_aud: float
    lower_confidence_bound_95_aud: float
    noninferiority_margin_aud: float
    valid: bool

    def as_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class OptimalBehaviourValidationResult:
    """Validation result for a frozen policy on one independent sample."""

    scenario_fingerprint: str
    gates: tuple[PairedPolicyValidationGate, ...]
    benchmark_means_aud: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.scenario_fingerprint:
            raise ValueError("Validation scenario fingerprint is required.")
        object.__setattr__(self, "gates", tuple(self.gates))
        object.__setattr__(
            self,
            "benchmark_means_aud",
            MappingProxyType({
                str(name): float(value)
                for name, value in self.benchmark_means_aud.items()
            }),
        )

    @property
    def valid(self) -> bool:
        return bool(self.gates) and all(gate.valid for gate in self.gates)

    def rows(self) -> list[dict[str, object]]:
        return [
            {
                "validation_scenario_fingerprint": self.scenario_fingerprint,
                **gate.as_dict(),
            }
            for gate in self.gates
        ]


@dataclass(frozen=True)
class ValidationPolicySelection:
    """Candidate/deployed split determined solely on validation paths."""

    candidate_policy_name: str
    selected_policy_name: str
    candidate_valid: bool
    fallback_reason: str | None


def select_deployed_policy(
    result: OptimalBehaviourValidationResult,
    *,
    candidate_policy_name: str = "V11",
    component: str = "combined_policy",
    candidate_fit_valid: bool = True,
) -> ValidationPolicySelection:
    """Select the candidate or its recorded best predeclared benchmark.

    Regression fitting and benchmark construction have already finished when
    this function is called.  It therefore cannot tune the candidate; it only
    makes the validation fallback explicit for the later evaluation rollout.
    """
    gates = tuple(gate for gate in result.gates if gate.component == component)
    if len(gates) != 1:
        raise ValueError(
            f"Validation requires exactly one {component!r} gate."
        )
    gate = gates[0]
    failed_components = tuple(
        item.component for item in result.gates if not item.valid
    )
    if not failed_components and candidate_fit_valid:
        return ValidationPolicySelection(
            candidate_policy_name=str(candidate_policy_name),
            selected_policy_name=str(candidate_policy_name),
            candidate_valid=True,
            fallback_reason=None,
        )
    return ValidationPolicySelection(
        candidate_policy_name=str(candidate_policy_name),
        selected_policy_name=str(gate.benchmark_name),
        candidate_valid=False,
        fallback_reason=(
            "candidate_fit_invalid"
            if not candidate_fit_valid
            else "combined_noninferiority_gate_failed"
            if failed_components == (component,)
            else "component_noninferiority_gate_failed:"
            + "|".join(failed_components)
        ),
    )


def paired_noninferiority_gate(
    policy_path_values_aud: object,
    benchmark_path_values_aud: Mapping[str, object],
    *,
    premium_aud: float,
    component: str,
    confidence_z: float = 1.96,
    margin_basis_points: float = 1.0,
) -> PairedPolicyValidationGate:
    """Compare one frozen policy with the best fixed benchmark by paired CI."""

    policy = _path_values(policy_path_values_aud, name="Policy")
    if not benchmark_path_values_aud:
        raise ValueError("At least one validation benchmark is required.")
    if not np.isfinite(premium_aud) or premium_aud <= 0.0:
        raise ValueError("Validation premium must be positive and finite.")
    if not np.isfinite(confidence_z) or confidence_z < 0.0:
        raise ValueError("confidence_z must be finite and non-negative.")
    if not np.isfinite(margin_basis_points) or margin_basis_points < 0.0:
        raise ValueError("margin_basis_points must be finite and non-negative.")

    benchmarks: dict[str, Array] = {}
    for name, values in benchmark_path_values_aud.items():
        benchmark = _path_values(values, name=f"Benchmark {name}")
        if benchmark.shape != policy.shape:
            raise ValueError(
                "Policy and validation benchmarks must use identical paths."
            )
        benchmarks[str(name)] = benchmark
    benchmark_name = max(
        sorted(benchmarks),
        key=lambda name: float(np.mean(benchmarks[name])),
    )
    benchmark = benchmarks[benchmark_name]
    difference = policy - benchmark
    difference_mean = float(np.mean(difference))
    standard_error = float(
        np.std(difference, ddof=1) / np.sqrt(float(difference.size))
    )
    lower_bound = difference_mean - float(confidence_z) * standard_error
    margin = float(premium_aud) * float(margin_basis_points) / 10_000.0
    return PairedPolicyValidationGate(
        component=str(component),
        benchmark_name=benchmark_name,
        path_count=int(policy.size),
        policy_mean_aud=float(np.mean(policy)),
        benchmark_mean_aud=float(np.mean(benchmark)),
        paired_difference_mean_aud=difference_mean,
        paired_standard_error_aud=standard_error,
        lower_confidence_bound_95_aud=lower_bound,
        noninferiority_margin_aud=margin,
        valid=bool(lower_bound >= -margin),
    )


def build_validation_result(
    *,
    scenario_fingerprint: str,
    gates: tuple[PairedPolicyValidationGate, ...],
    benchmark_path_values_aud: Mapping[str, object],
) -> OptimalBehaviourValidationResult:
    """Freeze validation gates and benchmark means for reporting."""

    means = {
        str(name): float(np.mean(_path_values(values, name=f"Benchmark {name}")))
        for name, values in benchmark_path_values_aud.items()
    }
    return OptimalBehaviourValidationResult(
        scenario_fingerprint=str(scenario_fingerprint),
        gates=tuple(gates),
        benchmark_means_aud=means,
    )


__all__ = [
    "OptimalBehaviourValidationResult",
    "PairedPolicyValidationGate",
    "ValidationPolicySelection",
    "build_validation_result",
    "paired_noninferiority_gate",
    "select_deployed_policy",
]
