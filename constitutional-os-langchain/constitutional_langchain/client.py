"""
constitutional_langchain/client.py

Thin client for the Constitutional OS governance API.
Wraps the governance-check endpoint defined in RFC-0001.
"""

import requests
from dataclasses import dataclass
from typing import Optional


@dataclass
class GovernanceDecision:
    verdict: str          # pass | block | defer
    rationale: str
    check_id: str
    requires_human_approval: bool
    rollback_available: bool
    membrane_results: list
    continuity_entry: dict

    @property
    def allowed(self) -> bool:
        return self.verdict == "pass"

    @property
    def blocked(self) -> bool:
        return self.verdict == "block"

    @property
    def deferred(self) -> bool:
        return self.verdict == "defer"


class GovernanceClient:
    """
    Client for the Constitutional OS governance-check API.
    Implements the contract defined in RFC-0001.
    """

    def __init__(
        self,
        base_url: str = "https://constitutional-os-production.up.railway.app",
        api_key: Optional[str] = None,
        timeout: int = 10,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key  = api_key
        self.timeout  = timeout

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def check(
        self,
        action_id:   str,
        delta_type:  str,
        payload:     dict,
        autonomy:    str  = "autonomous",
        severity:    str  = "normal",
        reversible:  bool = True,
        scope:       str  = "local",
        requester:   str  = "langchain-agent",
        profile_id:  Optional[str] = None,
    ) -> GovernanceDecision:
        """
        Submit a proposed action for governance evaluation.
        Returns a GovernanceDecision with verdict: pass | block | defer.
        """
        body = {
            "action_id":  action_id,
            "delta_type": delta_type,
            "payload":    payload,
            "autonomy":   autonomy,
            "severity":   severity,
            "reversible": reversible,
            "scope":      scope,
            "requester":  requester,
        }
        if profile_id:
            body["profile_id"] = profile_id

        try:
            resp = requests.post(
                f"{self.base_url}/governance/check",
                json=body,
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            # Fail open with a warning if governance API is unreachable
            import warnings
            warnings.warn(
                "Constitutional OS governance API unreachable. "
                "Failing open — action will proceed without governance check.",
                RuntimeWarning,
            )
            return GovernanceDecision(
                verdict="pass",
                rationale="Governance API unreachable — failed open",
                check_id="unavailable",
                requires_human_approval=False,
                rollback_available=False,
                membrane_results=[],
                continuity_entry={},
            )

        return GovernanceDecision(
            verdict                = data.get("verdict", "block"),
            rationale              = data.get("rationale", ""),
            check_id               = data.get("check_id", ""),
            requires_human_approval= data.get("requires_human_approval", False),
            rollback_available     = data.get("rollback_available", True),
            membrane_results       = data.get("membrane_results", []),
            continuity_entry       = data.get("continuity_entry", {}),
        )

    def check_tool_call(
        self,
        tool_name: str,
        tool_args: dict,
        severity:  str  = "normal",
        reversible: bool = True,
    ) -> GovernanceDecision:
        """Convenience method for checking a LangChain tool call."""
        import uuid
        return self.check(
            action_id  = str(uuid.uuid4())[:8],
            delta_type = "tool_call",
            payload    = {"tool_name": tool_name, "args": tool_args},
            severity   = severity,
            reversible = reversible,
        )
