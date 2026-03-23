"""
GovernedVercelAI
================
Subclass wrapper for the Vercel AI SDK (TypeScript/JavaScript).

This module provides two things:
  1. A Python FastAPI middleware that intercepts Vercel AI SDK
     streaming requests and governs them via Constitutional OS.
  2. A TypeScript snippet showing the client-side integration.

The pattern is identical — plan → action → delta, M1–M4,
continuity chain, rollback. The model is never modified.

Python usage (FastAPI middleware)
----------------------------------
from governed_vercel import GovernedVercelMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(
    GovernedVercelMiddleware,
    governance_url="https://constitutional-os-production.up.railway.app",
    agent_id="vercel-agent",
)

TypeScript usage (see TYPESCRIPT_SNIPPET below)
"""

import json
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Callable, Optional

import httpx
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


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

    def to_dict(self): return asdict(self)


# ─── GovernedVercelAI ─────────────────────────────────────────────────────────

class GovernedVercelAI:
    """
    Core governance engine for Vercel AI SDK integration.

    Intercepts:
        propose_plan()    — before streaming begins
        propose_action()  — before each tool call in the stream
        propose_delta()   — before each tool result is committed

    Holds persistent state across the streaming session.
    """

    def __init__(
        self,
        governance_url: str = "https://constitutional-os-production.up.railway.app",
        agent_id: Optional[str] = None,
    ):
        self.governance_url = governance_url
        self.agent_id = agent_id or f"vercel-agent-{uuid.uuid4().hex[:8]}"
        self.continuity_chain: list[ContinuityEntry] = []
        self.session_id = str(uuid.uuid4())
        self._http = httpx.Client(timeout=10.0)

    def propose_plan(self, messages: list) -> MembraneResult:
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            ""
        )
        return self._check("plan", {"last_user_message": last_user[:500]})

    def propose_action(self, tool_name: str, tool_args: dict) -> MembraneResult:
        return self._check("action", {"tool": tool_name, "args": tool_args})

    def propose_delta(self, tool_name: str, result: Any) -> MembraneResult:
        return self._check("delta", {"tool": tool_name, "result": str(result)[:500]})

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
                result = self._parse(resp.json())
                self._log(stage, payload, result)
                return result
        except Exception:
            pass

        result = self._local(stage, payload)
        self._log(stage, payload, result)
        return result

    def _local(self, stage: str, payload: dict) -> MembraneResult:
        s = str(payload).lower()
        if any(k in s for k in ["harm", "weapon", "exploit"]):
            return MembraneResult(False, "M1_SAFETY", 0.0, "Unsafe content detected")
        if any(k in s for k in ["delete", "drop", "overwrite"]):
            return MembraneResult(True, "M2_REVERSIBILITY", 0.5,
                                  "Irreversible — logged", requires_escalation=True)
        return MembraneResult(True, "M1_SAFETY", 1.0, "Passed")

    def _parse(self, data: dict) -> MembraneResult:
        return MembraneResult(
            passed=data.get("passed", True),
            membrane=data.get("membrane", "M1_SAFETY"),
            score=data.get("score", 1.0),
            reason=data.get("reason", "API check"),
            requires_escalation=data.get("requires_escalation", False),
        )

    def _log(self, stage: str, payload: dict, result: MembraneResult):
        self.continuity_chain.append(ContinuityEntry(
            entry_id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            stage=stage,
            payload=payload,
            membranes=[{"membrane": result.membrane, "passed": result.passed,
                        "score": result.score, "reason": result.reason}],
            timestamp=time.time(),
        ))

    def rollback(self, entry_id: str, reason: str) -> bool:
        for e in self.continuity_chain:
            if e.entry_id == entry_id:
                e.rolled_back = True
                return True
        return False

    def close(self):
        self._http.close()


# ─── FastAPI Middleware ────────────────────────────────────────────────────────

class GovernedVercelMiddleware(BaseHTTPMiddleware):
    """
    Drop-in FastAPI middleware that governs Vercel AI SDK requests.

    Intercepts POST /api/chat (or any configurable path) before
    the request reaches the model. Blocks M1 violations, logs
    all stages to the continuity chain.
    """

    def __init__(
        self,
        app: ASGIApp,
        governance_url: str = "https://constitutional-os-production.up.railway.app",
        agent_id: Optional[str] = None,
        governed_path: str = "/api/chat",
    ):
        super().__init__(app)
        self.governance_url = governance_url
        self.agent_id = agent_id or f"vercel-middleware-{uuid.uuid4().hex[:8]}"
        self.governed_path = governed_path
        self.continuity_chains: dict[str, list] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path != self.governed_path or request.method != "POST":
            return await call_next(request)

        body = await request.body()
        try:
            data = json.loads(body)
        except Exception:
            return await call_next(request)

        gov = GovernedVercelAI(
            governance_url=self.governance_url,
            agent_id=self.agent_id,
        )

        # Stage 1: govern the plan
        messages = data.get("messages", [])
        plan_result = gov.propose_plan(messages)

        if not plan_result.passed:
            gov.close()
            return Response(
                content=json.dumps({
                    "error": "blocked",
                    "membrane": plan_result.membrane,
                    "reason": plan_result.reason,
                    "continuity_chain": [e.to_dict() for e in gov.continuity_chain],
                }),
                status_code=403,
                media_type="application/json",
            )

        # Attach governance context to request state for downstream handlers
        request.state.governance = gov
        request.state.plan_result = plan_result

        response = await call_next(request)

        # Store chain for inspection
        session_id = gov.session_id
        self.continuity_chains[session_id] = [e.to_dict() for e in gov.continuity_chain]
        gov.close()

        # Attach chain header for observability
        response.headers["X-Constitutional-OS-Session"] = session_id
        response.headers["X-Constitutional-OS-Chain-Length"] = str(
            len(self.continuity_chains.get(session_id, []))
        )

        return response


# ─── TypeScript integration snippet ───────────────────────────────────────────

TYPESCRIPT_SNIPPET = '''
// governed-vercel.ts
// TypeScript client for Constitutional OS + Vercel AI SDK
//
// Drop this into your Next.js app/api/chat/route.ts

import { streamText } from "ai";
import { openai } from "@ai-sdk/openai";

const GOVERNANCE_URL = "https://constitutional-os-production.up.railway.app";

async function checkMembranes(stage: string, payload: object): Promise<{
  passed: boolean;
  membrane: string;
  reason: string;
  requires_escalation: boolean;
}> {
  try {
    const res = await fetch(`${GOVERNANCE_URL}/v1/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, payload }),
    });
    if (res.ok) return res.json();
  } catch {}
  return { passed: true, membrane: "M1_SAFETY", reason: "fallback", requires_escalation: false };
}

export async function POST(req: Request) {
  const { messages } = await req.json();

  // Stage 1: govern the plan
  const lastMessage = messages[messages.length - 1]?.content ?? "";
  const planCheck = await checkMembranes("plan", { message: lastMessage });

  if (!planCheck.passed) {
    return Response.json(
      { error: "blocked", membrane: planCheck.membrane, reason: planCheck.reason },
      { status: 403 }
    );
  }

  // Stage 2 + 3: govern actions and deltas via tool interception
  const governedTools = {
    myTool: {
      description: "Example governed tool",
      parameters: { query: { type: "string" } },
      execute: async ({ query }: { query: string }) => {
        // Stage 2: action check
        const actionCheck = await checkMembranes("action", { tool: "myTool", query });
        if (!actionCheck.passed) return `[BLOCKED] ${actionCheck.reason}`;
        if (actionCheck.requires_escalation) return "[ESCALATED — M4 Human Primacy]";

        const result = await actualToolLogic(query);

        // Stage 3: delta check
        const deltaCheck = await checkMembranes("delta", { tool: "myTool", result });
        if (!deltaCheck.passed) return `[OUTPUT BLOCKED] ${deltaCheck.reason}`;

        return result;
      },
    },
  };

  const result = streamText({
    model: openai("gpt-4o"),
    messages,
    tools: governedTools,
  });

  return result.toDataStreamResponse();
}

async function actualToolLogic(query: string): Promise<string> {
  // Your actual tool implementation
  return `Result for: ${query}`;
}
'''
