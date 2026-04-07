"""
CARE Input Validator.

Turns "infinite probing space" into "finite, typed surface."

Two modes (CARE_VALIDATION_MODE):
    "prod"  — strict: reject unknown top-level shapes, enforce schemas
    "lab"   — permissive: allow any JSON, just enforce size limits

Threat model:
    AI scanners probe input shapes systematically to map attack surface.
    Typed validation forces them to conform to known schemas,
    dramatically reducing the useful probe space.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

VALIDATION_MODE = os.getenv("CARE_VALIDATION_MODE", "lab")
MAX_PAYLOAD_BYTES = int(os.getenv("CARE_MAX_PAYLOAD_BYTES", str(64 * 1024)))  # 64KB default
MAX_STATE_DEPTH = int(os.getenv("CARE_MAX_STATE_DEPTH", "8"))
MAX_STATE_KEYS = int(os.getenv("CARE_MAX_STATE_KEYS", "256"))
MAX_STRING_LENGTH = int(os.getenv("CARE_MAX_STRING_LENGTH", "4096"))

# Known valid state types in prod mode
KNOWN_STATE_SCHEMAS = {"iam", "k8s", "generic", "demo"}

# Valid potential names
VALID_POTENTIALS = {"quadratic", "privilege", "blast_radius"}

# Valid backends
VALID_BACKENDS = {"numpy", "jax", "jax-xla", None}


class ValidationError(ValueError):
    pass


def validate_payload_size(raw: bytes) -> None:
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise ValidationError(
            f"Payload too large: {len(raw)} bytes > {MAX_PAYLOAD_BYTES} limit."
        )


def _check_depth(obj: Any, depth: int = 0) -> None:
    if depth > MAX_STATE_DEPTH:
        raise ValidationError(f"State nesting too deep (max {MAX_STATE_DEPTH}).")
    if isinstance(obj, dict):
        if len(obj) > MAX_STATE_KEYS:
            raise ValidationError(f"Too many keys in state dict (max {MAX_STATE_KEYS}).")
        for v in obj.values():
            _check_depth(v, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _check_depth(item, depth + 1)
    elif isinstance(obj, str):
        if len(obj) > MAX_STRING_LENGTH:
            raise ValidationError(f"String value too long (max {MAX_STRING_LENGTH} chars).")


def validate_state(state: Any, mode: str | None = None) -> None:
    """
    Validate the state field of a StateInput payload.
    In prod mode, rejects unknown top-level shapes.
    In lab mode, only enforces size/depth limits.
    """
    m = mode or VALIDATION_MODE

    # Always: depth + key count + string length
    _check_depth(state)

    if m == "prod":
        # In prod mode, top-level state must be a dict
        if not isinstance(state, dict):
            raise ValidationError(
                "Prod mode: state must be a JSON object (dict), "
                f"got {type(state).__name__}."
            )
        # Optionally: check for a _type field to route to schema validators
        state_type = state.get("_type", "generic")
        if state_type not in KNOWN_STATE_SCHEMAS:
            raise ValidationError(
                f"Prod mode: unknown state type '{state_type}'. "
                f"Known types: {KNOWN_STATE_SCHEMAS}."
            )

    # Always: numeric values must be finite
    _check_numeric_sanity(state)


def _check_numeric_sanity(obj: Any) -> None:
    """Reject NaN, Inf — these can cause curvature computation to behave unexpectedly."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValidationError(f"Numeric value is NaN or Inf: {obj}.")
    elif isinstance(obj, dict):
        for v in obj.values():
            _check_numeric_sanity(v)
    elif isinstance(obj, list):
        for item in obj:
            _check_numeric_sanity(item)


def validate_potential(potential: str) -> None:
    if potential not in VALID_POTENTIALS:
        raise ValidationError(
            f"Unknown potential '{potential}'. Valid: {VALID_POTENTIALS}."
        )


def validate_backend(backend: str | None) -> None:
    if backend not in VALID_BACKENDS:
        raise ValidationError(
            f"Unknown backend '{backend}'. Valid: {VALID_BACKENDS}."
        )


def validate_request(state: Any, potential: str, backend: str | None = None) -> None:
    """Full request validation — call this in every endpoint handler."""
    validate_state(state)
    validate_potential(potential)
    validate_backend(backend)
