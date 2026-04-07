"""
CARE membrane policies — rules that govern what changes are permitted.

These mirror the Constitutional OS membrane concept:
    A membrane is a boundary rule that must not be violated,
    regardless of what the curvature engine recommends.

Policies are checked before any delta is applied.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class MembranePolicy:
    """A single membrane policy rule."""
    name: str
    description: str
    check: Callable[[dict[str, Any]], bool]
    block_message: str


# ── Built-in policies ─────────────────────────────────────────────────────────

NO_AUTO_QUARANTINE = MembranePolicy(
    name="no_auto_quarantine",
    description="Quarantine actions require human approval.",
    check=lambda delta: delta.get("action_type") != "quarantine",
    block_message="Quarantine requires explicit human approval.",
)

NO_SILENT_PRIVILEGE_ESCALATION = MembranePolicy(
    name="no_privilege_escalation",
    description="Actions may not escalate privileges.",
    check=lambda delta: delta.get("from_state") != "read_only"
                         or delta.get("to_state") != "admin",
    block_message="Privilege escalation is not permitted via CARE.",
)

REQUIRE_REASON = MembranePolicy(
    name="require_reason",
    description="Every delta must have a non-empty reason.",
    check=lambda delta: bool(delta.get("reason", "").strip()),
    block_message="All deltas must include a reason.",
)


DEFAULT_POLICIES: list[MembranePolicy] = [
    NO_AUTO_QUARANTINE,
    NO_SILENT_PRIVILEGE_ESCALATION,
    REQUIRE_REASON,
]


def check_all(delta: dict[str, Any], policies: list[MembranePolicy] | None = None) -> tuple[bool, str]:
    """
    Run a delta through all membrane policies.
    Returns (allowed: bool, message: str).
    """
    for policy in (policies or DEFAULT_POLICIES):
        if not policy.check(delta):
            return False, f"[{policy.name}] {policy.block_message}"
    return True, "All membrane policies passed."
