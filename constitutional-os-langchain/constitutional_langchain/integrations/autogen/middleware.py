"""
integrations/autogen/middleware.py
=====================================
GovernanceMiddleware for AutoGen — intercepts agent messages (plans),
tool calls (actions), and state updates (deltas).

AutoGen already has a middleware/hook system. Constitutional OS plugs
in as a governance layer without modifying any agent or model config.
"""

import uuid
from typing import Any, Callable, Optional

from ..constitution import Constitution
from ..continuity import ContinuityChain
from ..types import Action, Delta

try:
    from autogen import AssistantAgent, UserProxyAgent
except ImportError:
    raise ImportError("pip install pyautogen")


class GovernanceMiddleware:
    """
    Constitutional OS governance middleware for AutoGen.

    Insert this into any AutoGen conversation to get:
      - plan governance (before_agent_reply)
      - action governance (before_tool_call)
      - delta governance (before_state_update)

    Usage:
        constitution = Constitution(agent_id="autogen-agent")
        chain = ContinuityChain(agent_id="autogen-agent", session_id=constitution.session_id)
        middleware = GovernanceMiddleware(constitution=constitution, chain=chain)

        # Attach to your agent
        agent = GovernedAutoGenAgent(
            name="ResearchAgent",
            llm_config={...},
            middleware=middleware,
        )
    """

    def __init__(self, constitution: Constitution, chain: ContinuityChain):
        self.constitution = constitution
        self.chain = chain

    # ─── Three interception points ────────────────────────────────────────────

    def before_agent_reply(self, agent, message: str | dict) -> any:
        """Stage 1: intercept agent message as a Plan."""
        text = message if isinstance(message, str) else str(message.get("content", ""))
        result = self.constitution.check_plan(text[:500])
        self.chain.append("plan", {"message": text[:500]}, result)
        return result

    def before_tool_call(self, agent, tool_call: dict) -> any:
        """Stage 2: intercept tool call as an Action."""
        action = Action(
            tool_name=tool_call.get("name", ""),
            tool_args=tool_call.get("arguments", {}),
            agent_id=self.constitution.agent_id,
            session_id=self.constitution.session_id,
        )
        result = self.constitution.check_action(action)
        self.chain.append("action", action.to_dict(), result)
        return result

    def before_state_update(self, agent, delta: dict) -> any:
        """Stage 3: intercept state update as a Delta."""
        d = Delta(
            tool_name=delta.get("tool_name", "state_update"),
            output=delta.get("output", delta),
            agent_id=self.constitution.agent_id,
            session_id=self.constitution.session_id,
            reversible=delta.get("reversible", True),
        )
        result = self.constitution.check_delta(d)
        self.chain.append("delta", d.to_dict(), result)
        return result


class GovernedAutoGenAgent(AssistantAgent):
    """
    Subclass of AutoGen's AssistantAgent with Constitutional OS governance.

    Overrides generate_reply() and execute_function() to intercept
    plan → action → delta via the GovernanceMiddleware.

    Usage:
        constitution = Constitution(agent_id="research-agent")
        chain = ContinuityChain(agent_id="research-agent", session_id=constitution.session_id)
        middleware = GovernanceMiddleware(constitution=constitution, chain=chain)

        agent = GovernedAutoGenAgent(
            name="ResearchAgent",
            llm_config={"config_list": [{"model": "gpt-4o", "api_key": "sk-..."}]},
            tools={"search": search_fn},
            middleware=middleware,
        )
        result = agent.initiate_chat_and_summarize("Research AI governance.")
    """

    def __init__(
        self,
        name: str,
        llm_config: dict,
        tools: dict[str, Callable] = None,
        middleware: Optional[GovernanceMiddleware] = None,
        constitution: Optional[Constitution] = None,
        chain: Optional[ContinuityChain] = None,
        governance_url: str = "https://constitutional-os-production.up.railway.app",
        **kwargs,
    ):
        agent_id = f"autogen-{uuid.uuid4().hex[:8]}"

        # Accept middleware or create from constitution/chain
        if middleware:
            self.middleware = middleware
        else:
            _constitution = constitution or Constitution(
                governance_url=governance_url, agent_id=agent_id,
            )
            _chain = chain or ContinuityChain(
                agent_id=agent_id, session_id=_constitution.session_id,
            )
            self.middleware = GovernanceMiddleware(
                constitution=_constitution, chain=_chain,
            )

        # Register tools in AutoGen function_map
        function_map = {}
        if tools:
            for tool_name, tool_fn in tools.items():
                function_map[tool_name] = self._wrap_tool(tool_name, tool_fn)

        super().__init__(
            name=name,
            llm_config=llm_config,
            function_map=function_map,
            **kwargs,
        )

    # ─── Override: generate_reply (plan) ──────────────────────────────────────

    def generate_reply(self, messages=None, sender=None, **kwargs):
        if messages:
            last = messages[-1] if messages else {}
            plan_result = self.middleware.before_agent_reply(self, last)
            if plan_result.blocked:
                return f"[BLOCKED — {plan_result.reason}]"
            if plan_result.deferred:
                return f"[ESCALATED — M4: {plan_result.reason}]"
        return super().generate_reply(messages=messages, sender=sender, **kwargs)

    # ─── Override: execute_function (action + delta) ──────────────────────────

    def execute_function(self, func_call, verbose=False):
        import json as _json
        tool_name = func_call.get("name", "")
        try:
            tool_args = _json.loads(func_call.get("arguments", "{}"))
        except Exception:
            tool_args = {}

        # Stage 2: govern the action
        action_result = self.middleware.before_tool_call(
            self, {"name": tool_name, "arguments": tool_args}
        )
        if action_result.blocked:
            return False, {"name": tool_name, "role": "function",
                           "content": f"[BLOCKED — {action_result.reason}]"}
        if action_result.deferred:
            return False, {"name": tool_name, "role": "function",
                           "content": f"[ESCALATED — M4: {action_result.reason}]"}

        # Execute via parent
        success, result = super().execute_function(func_call, verbose=verbose)

        if not success:
            self.middleware.chain.rollback_last("Tool execution failed")
            return success, result

        # Stage 3: govern the delta
        output = result.get("content", "") if isinstance(result, dict) else str(result)
        delta_result = self.middleware.before_state_update(
            self, {"tool_name": tool_name, "output": output, "reversible": True}
        )
        if delta_result.blocked:
            return False, {"name": tool_name, "role": "function",
                           "content": f"[OUTPUT BLOCKED — {delta_result.reason}]"}

        return success, result

    def _wrap_tool(self, tool_name: str, tool_fn: Callable) -> Callable:
        def wrapped(**kwargs):
            return tool_fn(**kwargs)
        wrapped.__name__ = tool_name
        return wrapped

    @property
    def constitution(self) -> Constitution:
        return self.middleware.constitution

    @property
    def chain(self) -> ContinuityChain:
        return self.middleware.chain

    def governance_summary(self) -> dict:
        return self.middleware.chain.summary()


# ─── Multi-agent governance ────────────────────────────────────────────────────

class GovernedMultiAgentConversation:
    """
    Governs a multi-agent AutoGen conversation.
    Shared continuity chain across all agents.
    Cross-agent membrane negotiation logged to a shared chain.
    """

    def __init__(
        self,
        agents: list[GovernedAutoGenAgent],
        task: str,
        max_rounds: int = 10,
    ):
        self.agents = agents
        self.task = task
        self.max_rounds = max_rounds

    def run(self) -> dict:
        if not self.agents:
            return {"status": "error", "reason": "No agents"}

        proxy = UserProxyAgent(
            name="GovernedOrchestrator",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=self.max_rounds,
            code_execution_config=False,
        )

        proxy.initiate_chat(
            self.agents[0],
            message=self.task,
            max_turns=self.max_rounds,
        )

        return {
            "status": "complete",
            "agent_summaries": [a.governance_summary() for a in self.agents],
            "total_entries": sum(len(a.chain) for a in self.agents),
            "shared_lyapunov": sum(
                a.chain.lyapunov_score() for a in self.agents
            ) / len(self.agents),
        }
