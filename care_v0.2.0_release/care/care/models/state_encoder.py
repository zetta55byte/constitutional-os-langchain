"""
State Encoder — raw infrastructure state → numerical vector x ∈ ℝⁿ.

Stub implementation: counts and aggregate statistics over a dict/list state.
Replace the `_encode_*` methods with real adapters (aws_iam, k8s, etc.)
or call the adapter layer directly.

The only contract this module must honour:
    encode_state(raw_state: Any) -> np.ndarray   shape (n,), dtype float64
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

import numpy as np

from care.config import settings

logger = logging.getLogger(__name__)


# ── Feature extraction helpers ────────────────────────────────────────────────

def _hash_feature(value: Any, buckets: int = 64) -> float:
    """Deterministic float in [0, 1) from any hashable value."""
    h = int(hashlib.md5(str(value).encode()).hexdigest(), 16)
    return (h % buckets) / buckets


def _flatten_dict(d: dict, prefix: str = "", sep: str = ".") -> dict[str, Any]:
    """Recursively flatten a nested dict."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{sep}{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten_dict(v, key, sep))
        elif isinstance(v, list):
            out[key + ".count"] = len(v)
            for i, item in enumerate(v[:8]):           # cap at 8 list items
                out[f"{key}.{i}"] = item
        else:
            out[key] = v
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def encode_state(raw_state: Any, target_dim: int | None = None) -> np.ndarray:
    """
    Convert raw infrastructure state to a fixed-length float vector.

    Parameters
    ----------
    raw_state:
        Any JSON-serialisable Python object representing infra state.
        Typical inputs: IAM policy dict, K8s manifest dict, YAML-parsed config.
    target_dim:
        Desired output dimension. Defaults to settings.max_state_dim.
        Actual dimension ≤ target_dim (padded with zeros if shorter).

    Returns
    -------
    np.ndarray shape (target_dim,) dtype float64
    """
    dim = target_dim or min(settings.max_state_dim, 64)

    if raw_state is None:
        return np.zeros(dim)

    if isinstance(raw_state, (int, float)):
        x = np.array([float(raw_state)])
    elif isinstance(raw_state, list):
        x = _encode_list(raw_state)
    elif isinstance(raw_state, dict):
        x = _encode_dict(raw_state)
    elif isinstance(raw_state, str):
        x = np.array([len(raw_state), _hash_feature(raw_state)])
    else:
        logger.warning("Unknown state type %s; returning zeros.", type(raw_state))
        x = np.zeros(2)

    # Pad or truncate to target_dim
    if x.shape[0] < dim:
        x = np.pad(x, (0, dim - x.shape[0]))
    else:
        x = x[:dim]

    return x.astype(np.float64)


def _encode_list(lst: list) -> np.ndarray:
    features = [float(len(lst))]
    numeric = [v for v in lst if isinstance(v, (int, float))]
    if numeric:
        arr = np.array(numeric, dtype=float)
        features += [arr.mean(), arr.std(), arr.min(), arr.max()]
    for item in lst[:8]:
        if isinstance(item, dict):
            features.append(float(len(item)))
        elif isinstance(item, str):
            features.append(_hash_feature(item))
    return np.array(features, dtype=float)


def _encode_dict(d: dict) -> np.ndarray:
    flat = _flatten_dict(d)
    features: list[float] = [float(len(flat))]

    for key, val in sorted(flat.items())[:62]:          # cap at 62 features
        if isinstance(val, bool):
            features.append(1.0 if val else 0.0)
        elif isinstance(val, (int, float)):
            features.append(float(val))
        elif isinstance(val, str):
            features.append(_hash_feature(val))
        else:
            features.append(0.0)

    return np.array(features, dtype=float)
