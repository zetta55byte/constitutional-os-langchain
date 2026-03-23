"""
GovernedAnthropicAgent
======================
Subclass wrapper for the Anthropic SDK agent loop.

Every plan, action, and delta passes through Constitutional OS
(M1–M4) before any tool executes. The model is never modified —
it just sees tool calls allowed, blocked, or deferred.

Usage
-----
from governed_anthropic import GovernedAnthropicAgent

agent = GovernedAnthropicAgent(
    api_key="sk-ant-...",
    model="claude-opus-4-5",
    tools=[my_tool_a, my_tool_b],
    governance_url="https://constitutional-os-production.up.railway.app",
)
result = await agent.run("Research the safety properties of autonomous systems.")
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

import anthropic
import httpx


# ─── Governance primitives ────────────────────────────────────────────────────

@dataclass
class MembraneResult:
    passed: bool
    membrane: str
    score: float
    reason: str
    requires_escalation: bool = False


@dataclass
class ContinuityEntry:
    entry_id: str
    agent_id: str
    stage: str          # "plan" | "action" | "delta"
    payload: dict
    membranes: list[dict]
    timestamp: float
    rolled_back: bool = False
    rollback_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ─── GovernedAnthropicAgent ───────────────────────────────────────────────────

class GovernedAnthropicAgent:
    """
    Subclass-pattern wrapper around the Anthropic SDK agent loop.

    Intercepts three stages:
        propose_plan()   — before the model starts reasoning
        propose_action() — before each tool call executes
        propose_delta()  — before any state change is committed

    Each stage runs through Constitutional OS M1–M4.
    The Anthropic model itself is never modified.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-5",
        tools: list = None,
        governance_url: str = "https://constitutional-os-production.up.railway.app",
        agent_id: Optional[str] = None,
        max_iterations: int = 10,
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.tools = tools or []
        self.governance_url = governance_url
        self.agent_id = agent_id or f"anthropic-agent-{uuid.uuid4().hex[:8]}"
        self.max_iterations = max_iterations

        # Persistent state — this is why we need a subclass, not a decorator
        self.continuity_chain: list[ContinuityEntry] = []
        self.session_id: str = str(uuid.uuid4())
        self._http = httpx.AsyncClient(timeout=10.0)

    # ─── Governance interception points ───────────────────────────────────────

    async def propose_plan(self, plan: str) -> MembraneResult:
        """Stage 1: governance check before the model starts reasoning."""
        return await self._check("plan", {"plan": plan})

    async def propose_action(self, tool_name: str, tool_input: dict) -> MembraneResult:
        """Stage 2: governance check before each tool call."""
        return await self._check("action", {"tool": tool_name, "input": tool_input})

    async def propose_delta(self, delta: dict) -> MembraneResult:
        """Stage 3: governance check before any state change is committed."""
        return await self._check("delta", delta)

    # ─── Core governance check ─────────────────────────────────────────────────

    async def _check(self, stage: str, payload: dict) -> MembraneResult:
        """
        Send a governance check to Constitutional OS.
        Falls back to local heuristics if API is unreachable.
        """
        try:
            resp = await self._http.post(
                f"{self.governance_url}/v1/check",
                json={
                    "agent_id": self.agent_id,
                    "stage": stage,
                    "payload": payload,
                    "session_id": self.session_id,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                result = self._parse_api_result(data, stage)
                await self._log(stage, payload, [result])
                return result
        except Exception:
            pass

        result = self._local_check(stage, payload)
        await self._log(stage, payload, [result])
        return result

    def _local_check(self, stage: str, payload: dict) -> MembraneResult:
        """Local M1–M4 heuristics when the API is unreachable."""
        payload_str = str(payload).lower()
        unsafe = any(k in payload_str for k in ["harm", "weapon", "exploit", "malware"])
        irreversible = any(k in payload_str for k in ["delete", "drop", "overwrite", "publish"])

        if unsafe:
            return MembraneResult(False, "M1_SAFETY", 0.0, "Unsafe content detected")
        if irreversible:
            return MembraneResult(True, "M2_REVERSIBILITY", 0.5,
                                  "Irreversible action — logged for rollback",
                                  requires_escalation=(stage == "delta"))
        return MembraneResult(True, "M1_SAFETY", 1.0, "Governance check passed")

    def _parse_api_result(self, data: dict, stage: str) -> MembraneResult:
        return MembraneResult(
            passed=data.get("passed", True),
            membrane=data.get("membrane", "M1_SAFETY"),
            score=data.get("score", 1.0),
            reason=data.get("reason", "API check"),
            requires_escalation=data.get("requires_escalation", False),
        )

    # ─── Continuity chain ─────────────────────────────────────────────────────

    async def _log(self, stage: str, payload: dict, results: list[MembraneResult]):
        entry = ContinuityEntry(
            entry_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            stage=stage,
            payload=payload,
            membranes=[
                {"membrane": r.membrane, "passed": r.passed,
                 "score": r.score, "reason": r.reason}
                for r in results
            ],
            timestamp=time.time(),
        )
        self.continuity_chain.append(entry)

    def rollback(self, entry_id: str, reason: str) -> bool:
        for e in self.continuity_chain:
            if e.entry_id == entry_id:
                e.rolled_back = True
                e.rollback_reason = reason
                return True
        return False

    # ─── Agent loop ───────────────────────────────────────────────────────────

    async def run(self, prompt: str) -> dict:
        """
        Override the agent loop.
        Intercepts plan → action → delta at each iteration.
        The model only executes tool calls that pass M1–M4.
        """
        # Stage 1: govern the plan
        plan_result = await self.propose_plan(prompt)
        if not plan_result.passed:
            return {
                "status": "blocked",
                "stage": "plan",
                "reason": plan_result.reason,
                "continuity_chain": [e.to_dict() for e in self.continuity_chain],
            }

        messages = [{"role": "user", "content": prompt}]
        tool_schemas = [self._tool_schema(t) for t in self.tools]
        iterations = 0

        while iterations < self.max_iterations:
            iterations += 1

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                tools=tool_schemas,
                messages=messages,
            )

            # Collect assistant message
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason != "tool_use":
                break

            # Process each tool call through governance
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                # Stage 2: govern the action
                action_result = await self.propose_action(block.name, block.input)

                if not action_result.passed:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"[BLOCKED by {action_result.membrane}] {action_result.reason}",
                    })
                    continue

                if action_result.requires_escalation:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"[ESCALATED — M4 Human Primacy] {action_result.reason}",
                    })
                    continue

                # Stage 3: govern the delta
                delta_result = await self.propose_delta({
                    "tool": block.name,
                    "input": block.input,
                    "iteration": iterations,
                })

                if not delta_result.passed:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"[BLOCKED at delta by {delta_result.membrane}] {delta_result.reason}",
                    })
                    continue

                # All three stages passed — execute the tool
                tool_fn = self._find_tool(block.name)
                if tool_fn:
                    try:
                        result = await tool_fn(**block.input) if asyncio.iscoroutinefunction(tool_fn) \
                            else tool_fn(**block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })
                    except Exception as exc:
                        # Rollback on error
                        last_entry = self.continuity_chain[-1] if self.continuity_chain else None
                        if last_entry:
                            self.rollback(last_entry.entry_id, str(exc))
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"[ERROR + ROLLBACK] {exc}",
                        })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"[Tool not found: {block.name}]",
                    })

            messages.append({"role": "user", "content": tool_results})

        # Extract final text
        final_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                final_text += block.text

        await self._http.aclose()

        return {
            "status": "complete",
            "result": final_text,
            "iterations": iterations,
            "continuity_chain": [e.to_dict() for e in self.continuity_chain],
            "chain_length": len(self.continuity_chain),
        }

    def _tool_schema(self, tool) -> dict:
        if isinstance(tool, dict):
            return tool
        if hasattr(tool, "to_anthropic_schema"):
            return tool.to_anthropic_schema()
        return {"name": str(tool), "description": "", "input_schema": {"type": "object", "properties": {}}}

    def _find_tool(self, name: str):
        for t in self.tools:
            if callable(t) and getattr(t, "__name__", None) == name:
                return t
            if isinstance(t, dict) and t.get("name") == name:
                return t.get("fn")
        return None
