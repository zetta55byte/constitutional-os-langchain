from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from .client import governance_check


class GovernedTool(BaseTool):
    """Wrap any LangChain tool with Constitutional OS governance."""

    name: str = "governed_tool"
    description: str = "Executes an action only if allowed by governance substrate."
    real_tool: BaseTool

    def _run(
        self,
        *args,
        run_manager: CallbackManagerForToolRun = None,
        **kwargs
    ):
        # 1. Construct the action proposal
        action = {
            "type": "tool_call",
            "tool_name": self.real_tool.name,
            "args": args,
            "kwargs": kwargs,
        }

        # 2. Governance check
        decision = governance_check(action)

        if not decision["allowed"]:
            # 3. Blocked by membrane — return reversible delta
            return {
                "error": decision["reason"],
                "reversible_delta": decision.get("delta"),
                "continuity_event_id": decision.get("continuity_event_id"),
            }

        # 4. Allowed — execute the real tool
        result = self.real_tool.run(*args, **kwargs)
        return {
            "result": result,
            "continuity_event_id": decision.get("continuity_event_id"),
        }

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError("Async not implemented for this demo.")
