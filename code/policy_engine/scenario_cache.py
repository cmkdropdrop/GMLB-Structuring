"""Strict, file-based cache for risk-neutral Heston-Hull-White scenarios.

Large path arrays are stored as separate ``.npy`` files so readers can use
``numpy.load(..., mmap_mode="r")``.  The JSON manifest contains only small,
canonical metadata.  Cache lookup is exact: a changed seed, horizon, path
count, ESG configuration or market-input hash always produces a different
key and is never treated as a compatible approximation.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Mapping, Optional

import numpy as np

from ._provenance import assumption_fingerprint
from .esg import ESGConfig, Measure, ScenarioSet, STEPS_PER_YEAR
from .product import Index


SCENARIO_CACHE_SCHEMA_VERSION = "q_market_paths_v1"
_ARRAY_FILES = {
    "times": "times.npy",
    "short_rate": "short_rate.npy",
    "discount": "discount.npy",
    "index_global_equity": "index_global_equity.npy",
    "index_aus_equity": "index_aus_equity.npy",
    "variance_global_equity": "variance_global_equity.npy",
    "variance_aus_equity": "variance_aus_equity.npy",
}


class ScenarioCacheError(RuntimeError):
    """Base error for missing, malformed or incompatible scenario caches."""


class ScenarioCacheNotFoundError(ScenarioCacheError):
    """Raised when the exact requested cache key does not exist."""


class ScenarioCacheMismatchError(ScenarioCacheError):
    """Raised when an existing cache fails strict validation."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    )


def _valid_sha256(value: str, label: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest.")
    return text


@dataclass(frozen=True)
class ScenarioCacheSpec:
    """All inputs that determine one reusable Q market-path cache."""

    esg_config_fingerprint: str
    australian_curve_sha256: str
    model_parameters_sha256: str
    horizon_years: float
    n_paths: int
    seed: int
    heston_substeps: int
    measure: Measure = Measure.RISK_NEUTRAL
    model_name: str = "heston_hull_white"
    steps_per_year: int = STEPS_PER_YEAR
    schema_version: str = SCENARIO_CACHE_SCHEMA_VERSION
    market_variant: str = "base"

    def __post_init__(self) -> None:
        object.__setattr__(self, "measure", Measure(self.measure))
        if self.schema_version != SCENARIO_CACHE_SCHEMA_VERSION:
            raise ValueError("Unsupported market-cache schema version.")
        if self.measure != Measure.RISK_NEUTRAL:
            raise ValueError("The reusable market cache requires risk-neutral scenarios.")
        if self.model_name != "heston_hull_white":
            raise ValueError("The reusable market cache requires heston_hull_white.")
        if self.steps_per_year != STEPS_PER_YEAR:
            raise ValueError("The reusable market cache requires a monthly grid.")
        object.__setattr__(
            self, "esg_config_fingerprint",
            _valid_sha256(
                self.esg_config_fingerprint, "esg_config_fingerprint"
            ),
        )
        object.__setattr__(
            self, "australian_curve_sha256",
            _valid_sha256(
                self.australian_curve_sha256, "australian_curve_sha256"
            ),
        )
        object.__setattr__(
            self, "model_parameters_sha256",
            _valid_sha256(
                self.model_parameters_sha256, "model_parameters_sha256"
            ),
        )
        if not np.isfinite(self.horizon_years) or self.horizon_years <= 0.0 \
                or not np.isclose(
                    self.horizon_years * STEPS_PER_YEAR,
                    round(self.horizon_years * STEPS_PER_YEAR),
                ):
            raise ValueError("horizon_years must be positive and monthly aligned.")
        for name in ("n_paths", "heston_substeps"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) \
                    or int(value) <= 0:
                raise ValueError(f"{name} must be a positive integer.")
        if isinstance(self.seed, bool) or not isinstance(
                self.seed, (int, np.integer)) or int(self.seed) < 0:
            raise ValueError("seed must be a non-negative integer.")
        if not str(self.market_variant).strip():
            raise ValueError("market_variant must not be empty.")
        object.__setattr__(self, "market_variant", str(self.market_variant))

    @classmethod
    def from_inputs(
        cls,
        esg_config: ESGConfig,
        *,
        australian_curve_sha256: str,
        model_parameters_sha256: str,
        horizon_years: float,
        n_paths: int,
        seed: int,
        heston_substeps: int,
        market_variant: str = "base",
    ) -> "ScenarioCacheSpec":
        return cls(
            esg_config_fingerprint=assumption_fingerprint(esg_config),
            australian_curve_sha256=australian_curve_sha256,
            model_parameters_sha256=model_parameters_sha256,
            horizon_years=float(horizon_years),
            n_paths=int(n_paths),
            seed=int(seed),
            heston_substeps=int(heston_substeps),
            market_variant=str(market_variant),
        )

    def canonical_fields(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "measure": self.measure.value,
            "model_name": self.model_name,
            "esg_config_fingerprint": self.esg_config_fingerprint,
            "australian_curve_sha256": self.australian_curve_sha256,
            "model_parameters_sha256": self.model_parameters_sha256,
            "horizon_years": float(self.horizon_years),
            "n_paths": int(self.n_paths),
            "seed": int(self.seed),
            "steps_per_year": int(self.steps_per_year),
            "dt": 1.0 / float(self.steps_per_year),
            "heston_substeps": int(self.heston_substeps),
            "market_variant": self.market_variant,
        }

    @property
    def cache_key(self) -> str:
        digest = sha256(_canonical_json(self.canonical_fields()).encode("utf-8"))
        return digest.hexdigest()


def _array_manifest(array: np.ndarray, filename: str) -> dict[str, object]:
    return {
        "file": filename,
        "dtype": np.dtype(array.dtype).str,
        "shape": list(array.shape),
    }


def _scenario_arrays(scenarios: ScenarioSet) -> dict[str, np.ndarray]:
    if scenarios.variance is None:
        raise ValueError("Heston-Hull-White scenarios must contain variance paths.")
    return {
        "times": np.asarray(scenarios.times),
        "short_rate": np.asarray(scenarios.short_rate),
        "discount": np.asarray(scenarios.discount),
        "index_global_equity": np.asarray(
            scenarios.index_levels[Index.GLOBAL_EQUITY]
        ),
        "index_aus_equity": np.asarray(
            scenarios.index_levels[Index.AUS_EQUITY]
        ),
        "variance_global_equity": np.asarray(
            scenarios.variance[Index.GLOBAL_EQUITY]
        ),
        "variance_aus_equity": np.asarray(
            scenarios.variance[Index.AUS_EQUITY]
        ),
    }


def _validate_scenario_against_spec(
    scenarios: ScenarioSet, spec: ScenarioCacheSpec,
) -> None:
    mismatches: list[str] = []
    if scenarios.measure != spec.measure:
        mismatches.append("measure")
    if scenarios.model_name != spec.model_name:
        mismatches.append("model_name")
    if assumption_fingerprint(scenarios.config) != spec.esg_config_fingerprint:
        mismatches.append("esg_config_fingerprint")
    if scenarios.n_paths != spec.n_paths:
        mismatches.append("n_paths")
    if scenarios.seed != spec.seed:
        mismatches.append("seed")
    if scenarios.substeps != spec.heston_substeps:
        mismatches.append("heston_substeps")
    if not np.isclose(
        scenarios.times[-1], spec.horizon_years, rtol=0.0, atol=1.0e-12
    ):
        mismatches.append("horizon_years")
    if not np.isclose(
        scenarios.dt, 1.0 / spec.steps_per_year, rtol=0.0, atol=1.0e-12
    ):
        mismatches.append("monthly_grid")
    if mismatches:
        raise ScenarioCacheMismatchError(
            "ScenarioSet does not match market-cache specification: "
            + ", ".join(mismatches)
            + "."
        )


def save_scenario_set(
    cache_root: str | Path,
    spec: ScenarioCacheSpec,
    scenarios: ScenarioSet,
) -> Path:
    """Write one exact cache entry; existing entries are never overwritten."""
    _validate_scenario_against_spec(scenarios, spec)
    root = Path(cache_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / spec.cache_key
    if destination.exists():
        raise FileExistsError(f"Market cache already exists: {destination}")

    arrays = _scenario_arrays(scenarios)
    temporary = Path(tempfile.mkdtemp(prefix=f".{spec.cache_key}.", dir=root))
    try:
        for name, array in arrays.items():
            np.save(temporary / _ARRAY_FILES[name], array, allow_pickle=False)
        manifest = {
            "cache_type": "q_market_paths",
            "cache_key": spec.cache_key,
            "spec": spec.canonical_fields(),
            "scenario_content_fingerprint": scenarios.content_fingerprint,
            "arrays": {
                name: _array_manifest(array, _ARRAY_FILES[name])
                for name, array in arrays.items()
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return destination


def _load_manifest(path: Path) -> dict[str, object]:
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise ScenarioCacheMismatchError(
            f"Market cache manifest is missing: {manifest_path}"
        )
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ScenarioCacheMismatchError(
            f"Market cache manifest is unreadable: {manifest_path}"
        ) from exc
    if not isinstance(value, dict):
        raise ScenarioCacheMismatchError("Market cache manifest must be an object.")
    return value


def _load_arrays(
    directory: Path,
    manifest: Mapping[str, object],
    mmap_mode: Optional[str],
) -> dict[str, np.ndarray]:
    metadata = manifest.get("arrays")
    if not isinstance(metadata, dict) or set(metadata) != set(_ARRAY_FILES):
        raise ScenarioCacheMismatchError(
            "Market cache manifest has an incomplete array inventory."
        )
    loaded: dict[str, np.ndarray] = {}
    for name, expected_file in _ARRAY_FILES.items():
        item = metadata[name]
        if not isinstance(item, dict) or item.get("file") != expected_file:
            raise ScenarioCacheMismatchError(
                f"Invalid market-cache metadata for array {name}."
            )
        path = directory / expected_file
        if not path.is_file():
            raise ScenarioCacheMismatchError(
                f"Market-cache array is missing: {path}"
            )
        try:
            array = np.load(path, mmap_mode=mmap_mode, allow_pickle=False)
        except (OSError, ValueError) as exc:
            raise ScenarioCacheMismatchError(
                f"Market-cache array is unreadable: {path}"
            ) from exc
        if list(array.shape) != item.get("shape") \
                or np.dtype(array.dtype).str != item.get("dtype"):
            raise ScenarioCacheMismatchError(
                f"Market-cache array metadata mismatch for {name}."
            )
        loaded[name] = array
    return loaded


def load_scenario_set(
    cache_root: str | Path,
    spec: ScenarioCacheSpec,
    esg_config: ESGConfig,
    *,
    mmap_mode: Optional[str] = "r",
) -> ScenarioSet:
    """Load and revalidate exactly one scenario cache entry."""
    if assumption_fingerprint(esg_config) != spec.esg_config_fingerprint:
        raise ScenarioCacheMismatchError(
            "Requested ESG configuration does not match ScenarioCacheSpec."
        )
    directory = Path(cache_root).expanduser().resolve() / spec.cache_key
    if not directory.is_dir():
        raise ScenarioCacheNotFoundError(
            "Exact market cache not found for key "
            f"{spec.cache_key}: {directory}"
        )
    manifest = _load_manifest(directory)
    if manifest.get("cache_type") != "q_market_paths" \
            or manifest.get("cache_key") != spec.cache_key \
            or manifest.get("spec") != spec.canonical_fields():
        raise ScenarioCacheMismatchError(
            f"Market cache manifest does not match exact key {spec.cache_key}."
        )
    arrays = _load_arrays(directory, manifest, mmap_mode)
    scenarios = ScenarioSet.from_storage(
        config=esg_config,
        measure=spec.measure,
        dt=1.0 / spec.steps_per_year,
        times=arrays["times"],
        index_levels={
            Index.GLOBAL_EQUITY: arrays["index_global_equity"],
            Index.AUS_EQUITY: arrays["index_aus_equity"],
        },
        short_rate=arrays["short_rate"],
        discount=arrays["discount"],
        variance={
            Index.GLOBAL_EQUITY: arrays["variance_global_equity"],
            Index.AUS_EQUITY: arrays["variance_aus_equity"],
        },
        stochastic_rates=True,
        model_name=spec.model_name,
        seed=spec.seed,
        substeps=spec.heston_substeps,
    )
    _validate_scenario_against_spec(scenarios, spec)
    expected_fingerprint = manifest.get("scenario_content_fingerprint")
    if scenarios.content_fingerprint != expected_fingerprint:
        raise ScenarioCacheMismatchError(
            "Loaded ScenarioSet content fingerprint differs from manifest; "
            "the cache is corrupt or was modified."
        )
    scenarios.bind_market_cache_identity(spec.cache_key, spec.market_variant)
    return scenarios


__all__ = [
    "SCENARIO_CACHE_SCHEMA_VERSION",
    "ScenarioCacheError",
    "ScenarioCacheMismatchError",
    "ScenarioCacheNotFoundError",
    "ScenarioCacheSpec",
    "load_scenario_set",
    "save_scenario_set",
]
