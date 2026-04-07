"""
CARE Lockdown Membrane.

When anomaly count from any IP exceeds threshold, freeze all delta application
until manual review. This makes "AI spam" degrade into "no-ops plus alerts."

Also adds:
    - Speed membrane: flag deltas faster than human typing speed
    - Attestation membrane: require signed token for high-impact deltas
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
LOCKDOWN_ENABLED = os.getenv("CARE_LOCKDOWN_ENABLED", "true").lower() == "true"
MIN_HUMAN_DELTA_INTERVAL = float(os.getenv("CARE_MIN_DELTA_INTERVAL", "2.0"))  # seconds
ATTESTATION_SECRET = os.getenv("CARE_ATTESTATION_SECRET", "")
HIGH_IMPACT_ACTIONS = {"quarantine", "segment_network", "disable_capability"}

# ── Global lockdown state ──────────────────────────────────────────────────────
_lockdown_active: bool = False
_lockdown_reason: str = ""
_lockdown_at: float = 0.0
_last_delta_time: float = 0.0


def engage_lockdown(reason: str) -> None:
    """Engage system-wide delta lockdown."""
    global _lockdown_active, _lockdown_reason, _lockdown_at
    _lockdown_active = True
    _lockdown_reason = reason
    _lockdown_at = time.time()
    logger.error("LOCKDOWN ENGAGED: %s", reason)


def release_lockdown() -> None:
    """Manually release lockdown after review."""
    global _lockdown_active, _lockdown_reason
    _lockdown_active = False
    _lockdown_reason = ""
    logger.warning("LOCKDOWN RELEASED by operator.")


def is_locked_down() -> bool:
    return _lockdown_active


def get_lockdown_status() -> dict:
    return {
        "active": _lockdown_active,
        "reason": _lockdown_reason,
        "engaged_at": _lockdown_at if _lockdown_active else None,
    }


# ── Membrane checks ────────────────────────────────────────────────────────────

def check_lockdown_membrane(delta: dict) -> tuple[bool, str]:
    """Block all delta application if system is in lockdown."""
    if not LOCKDOWN_ENABLED:
        return True, "Lockdown disabled."
    if _lockdown_active:
        return False, f"System lockdown active: {_lockdown_reason}"
    return True, "ok"


def check_speed_membrane(delta: dict) -> tuple[bool, str]:
    """
    Flag deltas arriving faster than human typing speed.
    Automated scripts submit deltas in milliseconds; humans take seconds.
    """
    global _last_delta_time
    now = time.time()
    interval = now - _last_delta_time if _last_delta_time > 0 else 999.0
    _last_delta_time = now

    if interval < MIN_HUMAN_DELTA_INTERVAL:
        return False, (
            f"Delta arrived too fast ({interval:.3f}s < {MIN_HUMAN_DELTA_INTERVAL}s). "
            "Automated submission suspected."
        )
    return True, "ok"


def check_attestation_membrane(delta: dict) -> tuple[bool, str]:
    """
    Require HMAC-signed token for high-impact actions.
    Token format: HMAC-SHA256(secret, action_type:target:timestamp)
    """
    action = delta.get("action_type", "")
    if action not in HIGH_IMPACT_ACTIONS:
        return True, "Attestation not required for this action type."
    if not ATTESTATION_SECRET:
        logger.warning("Attestation secret not configured — skipping attestation check.")
        return True, "Attestation secret not configured."

    token = delta.get("attestation_token", "")
    if not token:
        return False, f"High-impact action '{action}' requires attestation_token."

    # Verify HMAC
    target = delta.get("target", "")
    ts = str(delta.get("timestamp", ""))
    message = f"{action}:{target}:{ts}".encode()
    expected = hmac.new(
        ATTESTATION_SECRET.encode(),
        message,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(token, expected):
        return False, "Attestation token invalid."

    return True, "Attestation verified."


def check_all_security_membranes(delta: dict) -> tuple[bool, str]:
    """Run all security membrane checks in order."""
    for check in [check_lockdown_membrane, check_speed_membrane, check_attestation_membrane]:
        allowed, reason = check(delta)
        if not allowed:
            return False, reason
    return True, "All security membranes passed."
