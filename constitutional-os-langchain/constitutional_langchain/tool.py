"""
constitutional_langchain/tool.py

GovernedTool: wraps any LangChain BaseTool with Constitutional OS governance.

Every tool call is:
  - membrane-checked before execution
  - logged to the continuity chain
  - blocked or deferred if the governance check fails
  - reversible (rollback available on request)

Usage:
    from constitutional_langchain import GovernedTool, GovernanceClient
    from langchain.tools import DuckDuckGoSearchRun

    client = GovernanceClient()
    search = DuckDuckGoSearchRun()
    governed_search = GovernedTool(real_tool=search, client=client)

    result = governed_search.run("latest AI governance research")
"""

from typing import Optional, Any, Type
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from constitutional_langchain.client import GovernanceClient, GovernanceDecision


class GovernedTool(BaseTool):
    """
    A LangChain tool wrapped with Constitutional OS governance.

    Intercepts every tool call, submits it to the governance API,
    and enforces the verdict before execution.
    """

    name:        str = "governed_tool"
    description: str = "Executes an action only if allowed by Constitutional OS governance."

    real_tool:   Any                        # the underlying LangChain tool
    client:      Any                        # GovernanceClient instance
    severity:    str  = "normal"            # default severity for tool calls
    reversible:  bool = True                # default reversibility assumption
    profile_id:  Optional[str] = None       # constitutional profile to use

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, real_tool: BaseTool, client: Optional[GovernanceClient] = None, **kwargs):
        if client is None:
            client = GovernanceClient()
        super().__init__(
            name        = f"governed_{real_tool.name}",
            description = real_tool.description,
            real_tool   = real_tool,
            client      = client,
            **kwargs,
        )

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Governance-checked tool execution.

        1. Build the action proposal
        2. Submit to Constitutional OS governance API
        3. Enforce the verdict:
           - pass  → execute the real tool
           - block → return error with continuity chain ID
           - defer → return deferral with human approval required
        """
        import uuid

        # Step 1: Submit governance check
        decision = self.client.check(
            action_id  = str(uuid.uuid4())[:8],
            delta_type = "tool_call",
            payload    = {
                "tool_name": self.real_tool.name,
                "tool_input": tool_input,
                "kwargs": kwargs,
            },
            severity   = self.severity,
            reversible = self.reversible,
            profile_id = self.profile_id,
        )

        continuity_id = decision.continuity_entry.get("seq", "unknown")

        # Step 2: Enforce verdict
        if decision.blocked:
            print(f"\n🔴 BLOCKED by Constitutional OS")
            print(f"   Tool:    {self.real_tool.name}")
            print(f"   Reason:  {decision.rationale}")
            print(f"   Log ID:  {continuity_id}")
            _print_membrane_results(decision)
            return {
                "error":              "Action blocked by governance substrate",
                "rationale":          decision.rationale,
                "tool_name":          self.real_tool.name,
                "continuity_id":      continuity_id,
                "rollback_available": decision.rollback_available,
                "membrane_results":   decision.membrane_results,
            }

        if decision.deferred:
            print(f"\n🟡 DEFERRED by Constitutional OS — human approval required")
            print(f"   Tool:    {self.real_tool.name}")
            print(f"   Reason:  {decision.rationale}")
            print(f"   Log ID:  {continuity_id}")
            return {
                "error":                   "Action deferred — awaiting human approval",
                "rationale":               decision.rationale,
                "tool_name":               self.real_tool.name,
                "continuity_id":           continuity_id,
                "requires_human_approval": True,
                "check_id":                decision.check_id,
            }

        # Step 3: Passed — execute
        print(f"\n🟢 PASSED Constitutional OS governance")
        print(f"   Tool:    {self.real_tool.name}")
        print(f"   Log ID:  {continuity_id}")

        result = self.real_tool.run(tool_input, **kwargs)

        return {
            "result":         result,
            "tool_name":      self.real_tool.name,
            "continuity_id":  continuity_id,
            "verdict":        "pass",
        }

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("Use _run for now — async coming in v0.2")


def _print_membrane_results(decision: GovernanceDecision) -> None:
    """Pretty-print membrane results for debugging."""
    if not decision.membrane_results:
        return
    print("   Membranes:")
    for m in decision.membrane_results:
        icon = "✓" if m.get("verdict") == "pass" else "✗"
        print(f"     {icon} {m.get('membrane_id', '?')}: {m.get('reason', '')}")
