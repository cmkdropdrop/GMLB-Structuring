"""Deterministic assumption fingerprints for safe result reuse."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from hashlib import sha256
from collections.abc import Mapping

import numpy as np


def assumption_fingerprint(*objects: object) -> str:
    """Hash nested immutable modelling inputs, including NumPy arrays.

    The fingerprint is deliberately internal: it prevents a precomputed
    valuation/capital result from being silently reused with different model
    assumptions.  It is not intended as a cryptographic data signature.
    """

    digest = sha256()

    def add(value: object) -> None:
        if value is None:
            digest.update(b"none;")
        elif isinstance(value, Enum):
            digest.update(f"enum:{value.__class__.__qualname__}:{value.value};".encode())
        elif isinstance(value, (str, bytes, bool, int, float, np.generic)):
            digest.update(f"scalar:{type(value).__name__}:{value!r};".encode())
        elif isinstance(value, np.ndarray):
            arr = np.ascontiguousarray(value)
            digest.update(f"array:{arr.dtype}:{arr.shape};".encode())
            digest.update(arr.tobytes())
        elif is_dataclass(value):
            digest.update(f"dataclass:{value.__class__.__module__}."
                          f"{value.__class__.__qualname__};".encode())
            for item in fields(value):
                digest.update(f"field:{item.name};".encode())
                add(getattr(value, item.name))
        elif isinstance(value, Mapping):
            digest.update(b"mapping;")
            for key in sorted(value, key=lambda x: repr(x)):
                add(key)
                add(value[key])
        elif isinstance(value, (tuple, list)):
            digest.update(f"sequence:{len(value)};".encode())
            for item in value:
                add(item)
        else:
            digest.update(f"repr:{value.__class__.__qualname__}:{value!r};".encode())

    for obj in objects:
        add(obj)
    return digest.hexdigest()

