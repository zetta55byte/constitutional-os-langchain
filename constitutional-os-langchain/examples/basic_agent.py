"""
examples/basic_agent.py

Reference demo: LangChain agent with Constitutional OS governance.

Shows:
  1. A safe action passing governance (search)
  2. An unsafe action blocked by M1 safety membrane (delete all users)
  3. A significant action deferred for human review
  4. Continuity chain IDs on every action

Run:
    pip install constitutional-os-langchain langchain langchain-openai
    export OPENAI_API_KEY=sk-...
    python examples/basic_agent.py
"""

import os
from constitutional_langchain import GovernedTool, GovernanceClient
from langchain_core.tools import BaseTool


# ── Toy tools for the demo ─────────────────────────────────────────────────

class SearchTool(BaseTool):
    name: str        = "search"
    description: str = "Search for information on a topic"

    def _run(self, query: str, **kwargs) -> str:
        return f"[Search results for: {query}] — Found 3 relevant articles."

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError


class DeleteAllUsersTool(BaseTool):
    name: str        = "delete_all_users"
    description: str = "Delete all users from the database"

    def _run(self, *args, **kwargs) -> str:
        return "All users deleted."   # should never reach this

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError


class UpdateConfigTool(BaseTool):
    name: str        = "update_global_config"
    description: str = "Update global system configuration"

    def _run(self, config: str, **kwargs) -> str:
        return f"Config updated: {config}"

    async def _arun(self, *args, **kwargs):
        raise NotImplementedError


# ── Run the demo ───────────────────────────────────────────────────────────

def run_demo():
    print("=" * 60)
    print("  Constitutional OS × LangChain — Governance Demo")
    print("=" * 60)

    # Connect to the governance API
    client = GovernanceClient(
        base_url="https://constitutional-os-production.up.railway.app",
        # api_key="your-key-here"  # add when auth is implemented
    )

    # Wrap tools with governance
    governed_search = GovernedTool(
        real_tool  = SearchTool(),
        client     = client,
        severity   = "normal",
        reversible = True,
    )

    governed_delete = GovernedTool(
        real_tool  = DeleteAllUsersTool(),
        client     = client,
        severity   = "critical",    # will trigger M1 safety membrane
        reversible = False,         # will trigger M2 reversibility membrane
    )

    governed_config = GovernedTool(
        real_tool  = UpdateConfigTool(),
        client     = client,
        severity   = "significant", # will trigger M4 human primacy membrane
        reversible = True,
    )

    # ── Demo 1: Safe action — should PASS ─────────────────────────────────
    print("\n" + "─" * 50)
    print("Demo 1: Safe search action")
    print("─" * 50)
    result = governed_search.run("latest AI governance research")
    print(f"Result: {result}")

    # ── Demo 2: Unsafe action — should BLOCK ──────────────────────────────
    print("\n" + "─" * 50)
    print("Demo 2: Unsafe delete action (critical + irreversible)")
    print("─" * 50)
    result = governed_delete.run("confirm=true")
    print(f"Result: {result}")

    # ── Demo 3: Significant action — should DEFER ─────────────────────────
    print("\n" + "─" * 50)
    print("Demo 3: Significant config change (human approval required)")
    print("─" * 50)
    result = governed_config.run('{"max_agents": 1000}')
    print(f"Result: {result}")

    print("\n" + "=" * 60)
    print("Every action logged to continuity chain.")
    print("Blocked actions never executed.")
    print("Deferred actions wait for human approval.")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
