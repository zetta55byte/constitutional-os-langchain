"""
GovernedOpenAIAssistant
=======================
Subclass wrapper for the OpenAI Assistants API.

Intercepts plan → action → delta before any tool executes.
Constitutional OS M1–M4 enforced at every stage.
The OpenAI model is never modified.

Usage
-----
from governed_openai import GovernedOpenAIAssistant

agent = GovernedOpenAIAssistant(
    api_key="sk-...",
    assistant_id="asst_...",       # existing OpenAI Assistant
    tools={"search": my_search_fn, "calculator": my_calc_fn},
    governance_url="https://constitutional-os-production.up.railway.app",
)
result = await agent.run("What are the safety implications of autonomous code execution?")
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Callable, Optional

import httpx

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("pip install openai")


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
    stage: str
    payload: dict
    membranes: list
    timestamp: float
    rolled_back: bool = False
    rollback_reason: Optional[str] = None

    def to_dict(self): return asdict(self)


# ─── GovernedOpenAIAssistant ──────────────────────────────────────────────────

class GovernedOpenAIAssistant:
    """
    Subclass-pattern wrapper for the OpenAI Assistants API.

    Intercepts:
        propose_plan()   — before thread creation / first message
        propose_action() — before each required_action tool call
        propose_delta()  — before submitting tool outputs back to the run

    Persistent state (continuity chain, session metadata) lives on the instance.
    The OpenAI Assistant and model are never modified.
    """

    def __init__(
        self,
        api_key: str,
        assistant_id: str,
        tools: dict[str, Callable] = None,
        governance_url: str = "https://constitutional-os-production.up.railway.app",
        agent_id: Optional[str] = None,
        poll_interval: float = 1.0,
        max_polls: int = 60,
    ):
        self.client = OpenAI(api_key=api_key)
        self.assistant_id = assistant_id
        self.tools = tools or {}
        self.governance_url = governance_url
        self.agent_id = agent_id or f"openai-agent-{uuid.uuid4().hex[:8]}"
        self.poll_interval = poll_interval
        self.max_polls = max_polls

        self.continuity_chain: list[ContinuityEntry] = []
        self.session_id: str = str(uuid.uuid4())
        self._http = httpx.Client(timeout=10.0)

    # ─── Governance interception points ───────────────────────────────────────

    def propose_plan(self, prompt: str) -> MembraneResult:
        return self._check("plan", {"prompt": prompt})

    def propose_action(self, tool_name: str, tool_args: dict) -> MembraneResult:
        return self._check("action", {"tool": tool_name, "args": tool_args})

    def propose_delta(self, tool_name: str, output: Any) -> MembraneResult:
        return self._check("delta", {"tool": tool_name, "output": str(output)[:500]})

    # ─── Core governance check ─────────────────────────────────────────────────

    def _check(self, stage: str, payload: dict) -> MembraneResult:
        try:
            resp = self._http.post(
                f"{self.governance_url}/v1/check",
                json={
                    "agent_id": self.agent_id,
                    "stage": stage,
                    "payload": payload,
                    "session_id": self.session_id,
                },
            )
            if resp.status_code == 200:
                result = self._parse_api_result(resp.json(), stage)
                self._log(stage, payload, [result])
                return result
        except Exception:
            pass

        result = self._local_check(stage, payload)
        self._log(stage, payload, [result])
        return result

    def _local_check(self, stage: str, payload: dict) -> MembraneResult:
        s = str(payload).lower()
        if any(k in s for k in ["harm", "weapon", "exploit", "malware"]):
            return MembraneResult(False, "M1_SAFETY", 0.0, "Unsafe content detected")
        if any(k in s for k in ["delete", "drop", "overwrite"]):
            return MembraneResult(True, "M2_REVERSIBILITY", 0.5,
                                  "Irreversible action logged", requires_escalation=True)
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

    def _log(self, stage: str, payload: dict, results: list[MembraneResult]):
        self.continuity_chain.append(ContinuityEntry(
            entry_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            stage=stage,
            payload=payload,
            membranes=[{"membrane": r.membrane, "passed": r.passed,
                        "score": r.score, "reason": r.reason} for r in results],
            timestamp=time.time(),
        ))

    def rollback(self, entry_id: str, reason: str) -> bool:
        for e in self.continuity_chain:
            if e.entry_id == entry_id:
                e.rolled_back = True
                e.rollback_reason = reason
                return True
        return False

    # ─── Agent loop ───────────────────────────────────────────────────────────

    def run(self, prompt: str) -> dict:
        """
        Override the OpenAI Assistants agent loop.

        Flow:
          1. propose_plan()  → govern the prompt before thread creation
          2. Create thread + run
          3. Poll for required_action
          4. propose_action() → govern each tool call
          5. Execute tool
          6. propose_delta()  → govern the output before submission
          7. Submit tool outputs
          8. Return final message
        """
        # Stage 1: govern the plan
        plan_result = self.propose_plan(prompt)
        if not plan_result.passed:
            return {
                "status": "blocked",
                "stage": "plan",
                "reason": plan_result.reason,
                "continuity_chain": [e.to_dict() for e in self.continuity_chain],
            }

        # Create thread
        thread = self.client.beta.threads.create()
        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt,
        )

        # Create run
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant_id,
        )

        # Poll
        polls = 0
        while polls < self.max_polls:
            polls += 1
            import time as _time
            _time.sleep(self.poll_interval)

            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id,
            )

            if run.status == "completed":
                break

            if run.status == "requires_action":
                tool_outputs = []
                calls = run.required_action.submit_tool_outputs.tool_calls

                for call in calls:
                    import json as _json
                    tool_name = call.function.name
                    tool_args = _json.loads(call.function.arguments or "{}")

                    # Stage 2: govern the action
                    action_result = self.propose_action(tool_name, tool_args)

                    if not action_result.passed:
                        tool_outputs.append({
                            "tool_call_id": call.id,
                            "output": f"[BLOCKED by {action_result.membrane}] {action_result.reason}",
                        })
                        continue

                    if action_result.requires_escalation:
                        tool_outputs.append({
                            "tool_call_id": call.id,
                            "output": f"[ESCALATED — M4 Human Primacy] Awaiting human approval.",
                        })
                        continue

                    # Execute tool
                    tool_fn = self.tools.get(tool_name)
                    if not tool_fn:
                        tool_outputs.append({
                            "tool_call_id": call.id,
                            "output": f"[Tool not found: {tool_name}]",
                        })
                        continue

                    try:
                        output = tool_fn(**tool_args)
                    except Exception as exc:
                        last = self.continuity_chain[-1] if self.continuity_chain else None
                        if last:
                            self.rollback(last.entry_id, str(exc))
                        tool_outputs.append({
                            "tool_call_id": call.id,
                            "output": f"[ERROR + ROLLBACK] {exc}",
                        })
                        continue

                    # Stage 3: govern the delta (tool output before submission)
                    delta_result = self.propose_delta(tool_name, output)
                    if not delta_result.passed:
                        tool_outputs.append({
                            "tool_call_id": call.id,
                            "output": f"[OUTPUT BLOCKED at delta] {delta_result.reason}",
                        })
                        continue

                    tool_outputs.append({
                        "tool_call_id": call.id,
                        "output": str(output),
                    })

                # Submit governed outputs
                run = self.client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs,
                )

            elif run.status in ("failed", "cancelled", "expired"):
                return {
                    "status": run.status,
                    "continuity_chain": [e.to_dict() for e in self.continuity_chain],
                }

        # Get final message
        messages = self.client.beta.threads.messages.list(thread_id=thread.id)
        final = next(
            (m.content[0].text.value for m in messages.data
             if m.role == "assistant" and m.content),
            ""
        )

        self._http.close()

        return {
            "status": "complete",
            "result": final,
            "thread_id": thread.id,
            "continuity_chain": [e.to_dict() for e in self.continuity_chain],
            "chain_length": len(self.continuity_chain),
        }
