"""
Reversible delta structures for the CARE membrane layer.

A delta is the atomic unit of change in Constitutional OS.
Every change applied through CARE is:
    - uniquely identified (UUID)
    - timestamped
    - checksummed
    - reversible (stores from_state so it can be rolled back)
    - auditable (persisted to an in-memory log; swap for persistent store)
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Delta:
    """A single reversible, auditable change."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: int = field(default_factory=lambda: int(time.time()))
    action_type: str = ""
    target: str = ""
    from_state: str = ""
    to_state: str = ""
    reason: str = ""
    uag_link: str = ""
    status: str = "pending"          # pending | applied | rolled_back | blocked | failed
    reversible: bool = True
    applied_by: str = "care-engine"
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            payload = json.dumps({
                "action_type": self.action_type,
                "target": self.target,
                "from_state": self.from_state,
                "to_state": self.to_state,
            }, sort_keys=True)
            self.checksum = hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def rollback(self) -> "Delta":
        """Return the inverse delta (swaps from/to state)."""
        return Delta(
            action_type=self.action_type,
            target=self.target,
            from_state=self.to_state,
            to_state=self.from_state,
            reason=f"Rollback of delta {self.id}: {self.reason}",
            uag_link=self.uag_link,
            applied_by="care-engine/rollback",
        )


# ── In-memory audit log (swap for Redis / Postgres in production) ─────────────

_AUDIT_LOG: list[Delta] = []


def record(delta: Delta) -> None:
    _AUDIT_LOG.append(delta)


def get_log() -> list[dict[str, Any]]:
    return [d.to_dict() for d in _AUDIT_LOG]


def get_delta(delta_id: str) -> Delta | None:
    for d in _AUDIT_LOG:
        if d.id == delta_id:
            return d
    return None


def from_action(action: dict[str, Any]) -> Delta:
    """Construct a Delta from a CARE hardening action dict."""
    return Delta(
        action_type=action.get("action_type", ""),
        target=action.get("target", ""),
        from_state=action.get("from_state", ""),
        to_state=action.get("to_state", ""),
        reason=action.get("reason", ""),
        uag_link=action.get("uag_link", ""),
    )
