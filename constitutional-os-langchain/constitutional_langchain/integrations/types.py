"""
constitutional_os.types
========================
Shared types for all Constitutional OS agent runtime integrations.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class Membrane(str, Enum):
    M1_SAFETY = "M1_SAFETY"
    M2_REVERSIBILITY = "M2_REVERSIBILITY"
    M3_PLURALISM = "M3_PLURALISM"
    M4_HUMAN_PRIMACY = "M4_HUMAN_PRIMACY"


class GovernanceVerdict(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    DEFER = "defer"        # escalate to human


@dataclass
class Action:
    """A proposed tool call — Stage 2 of the governance lifecycle."""
    tool_name: str
    tool_args: dict
    agent_id: str
    session_id: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Delta:
    """A proposed state change — Stage 3 of the governance lifecycle."""
    tool_name: str
    output: Any
    agent_id: str
    session_id: str
    reversible: bool = True
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "output": str(self.output)[:500],
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "reversible": self.reversible,
            "metadata": self.metadata,
        }


@dataclass
class MembraneResult:
    """Result of a single membrane check."""
    passed: bool
    membrane: Membrane
    score: float           # 0.0–1.0
    reason: str
    verdict: GovernanceVerdict = GovernanceVerdict.ALLOW
    requires_escalation: bool = False
    delta_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "membrane": self.membrane.value,
            "score": self.score,
            "reason": self.reason,
            "verdict": self.verdict.value,
            "requires_escalation": self.requires_escalation,
        }


@dataclass
class GovernanceResult:
    """Aggregate result of all four membrane checks for one stage."""
    stage: str             # "plan" | "action" | "delta"
    verdict: GovernanceVerdict
    membranes: list[MembraneResult]
    reason: str
    entry_id: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.verdict == GovernanceVerdict.ALLOW

    @property
    def blocked(self) -> bool:
        return self.verdict == GovernanceVerdict.BLOCK

    @property
    def deferred(self) -> bool:
        return self.verdict == GovernanceVerdict.DEFER

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "entry_id": self.entry_id,
            "membranes": [m.to_dict() for m in self.membranes],
        }
