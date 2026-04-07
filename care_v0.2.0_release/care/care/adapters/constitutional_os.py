"""
Constitutional OS Adapter.

Translates CARE hardening actions → Constitutional OS reversible deltas.

In production, this calls the Constitutional OS Runtime API.
In stub mode (CARE_COS_ENABLED=false), it logs and returns dry-run IDs.

Constitutional OS concepts:
    membrane      — boundary rule (e.g. "no process may escalate privileges")
    delta         — a single auditable, reversible change
    rule coherence— the delta must not violate the security constitution
    audit log     — every applied delta is recorded and can be rolled back
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any

import httpx

from care.config import settings

logger = logging.getLogger(__name__)


# ── Delta structure ───────────────────────────────────────────────────────────

def _make_delta(action: dict[str, Any]) -> dict[str, Any]:
    """Translate a CARE hardening action into a Constitutional OS delta."""
    delta_id = str(uuid.uuid4())
    timestamp = int(time.time())
    payload = json.dumps(action, sort_keys=True)
    checksum = hashlib.sha256(payload.encode()).hexdigest()[:16]

    return {
        "id": delta_id,
        "timestamp": timestamp,
        "checksum": checksum,
        "action_type": action.get("action_type"),
        "target": action.get("target"),
        "from_state": action.get("from_state"),
        "to_state": action.get("to_state"),
        "reason": action.get("reason", ""),
        "uag_link": action.get("uag_link", ""),
        "reversible": True,
        "status": "pending",
        "applied_by": "care-engine",
    }


def _check_membrane(delta: dict[str, Any]) -> tuple[bool, str]:
    """
    Placeholder membrane check.
    Returns (allowed: bool, reason: str).

    Real implementation: POST to Constitutional OS Runtime /membrane/check.
    Rules enforced here (example):
        - "quarantine" requires human approval
        - "segment_network" is auto-approved
        - "disable_capability" requires quorum
    """
    action_type = delta.get("action_type", "")
    if action_type == "quarantine":
        return False, "Quarantine requires human approval via Constitutional OS quorum."
    return True, "Membrane check passed."


# ── Public API ────────────────────────────────────────────────────────────────

def propose_delta(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert a list of hardening actions into Constitutional OS delta objects.
    Runs membrane checks; rejected deltas are flagged but not removed.
    """
    deltas = []
    for action in actions:
        delta = _make_delta(action)
        allowed, reason = _check_membrane(delta)
        delta["membrane_allowed"] = allowed
        delta["membrane_reason"] = reason
        if not allowed:
            delta["status"] = "blocked"
            logger.warning("Delta blocked by membrane: %s — %s", delta["id"], reason)
        deltas.append(delta)

    return deltas


def apply_delta(deltas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Apply approved deltas via Constitutional OS Runtime.

    If COS_ENABLED and endpoint is reachable: POST to /delta/apply.
    Otherwise: stub — mark as applied and log.
    """
    applied = []
    for delta in deltas:
        if not delta.get("membrane_allowed", False):
            continue

        if settings.cos_enabled:
            try:
                r = httpx.post(
                    f"{settings.cos_endpoint}/delta/apply",
                    json=delta,
                    timeout=5.0,
                )
                r.raise_for_status()
                delta["status"] = "applied"
                logger.info("Applied delta %s via Constitutional OS.", delta["id"])
            except Exception as e:
                delta["status"] = "failed"
                delta["error"] = str(e)
                logger.error("Failed to apply delta %s: %s", delta["id"], e)
        else:
            # Stub: log and mark as applied
            delta["status"] = "applied_stub"
            logger.info(
                "[STUB] Would apply delta %s: %s %s → %s",
                delta["id"],
                delta.get("action_type"),
                delta.get("from_state"),
                delta.get("to_state"),
            )

        applied.append(delta)

    return applied


def rollback_delta(delta_id: str) -> dict[str, Any]:
    """
    Roll back a previously applied delta.
    This is a stub — real implementation calls the COS Runtime /delta/rollback.
    """
    logger.info("[STUB] Rolling back delta %s.", delta_id)
    return {"id": delta_id, "status": "rolled_back", "timestamp": int(time.time())}
