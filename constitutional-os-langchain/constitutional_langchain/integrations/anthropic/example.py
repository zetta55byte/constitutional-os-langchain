# integrations/anthropic/example.py
# ─────────────────────────────────────────────────────────────
# This is the shape of usage — not runnable code.
# It shows how GovernedAnthropicAgent fits into your stack.
# ─────────────────────────────────────────────────────────────

from constitutional_langchain.integrations.constitution import Constitution
from constitutional_langchain.integrations.continuity import ContinuityChain
from constitutional_langchain.integrations.anthropic import GovernedAnthropicAgent

# 1. Create the shared governance objects
constitution = Constitution(
    governance_url="https://constitutional-os-production.up.railway.app",
    agent_id="my-anthropic-agent",
)
chain = ContinuityChain(
    agent_id="my-anthropic-agent",
    session_id=constitution.session_id,
)

# 2. Define your tools
async def search(query: str) -> str:
    """Search the web."""
    ...

async def summarize(text: str) -> str:
    """Summarize a document."""
    ...

# 3. Create the governed agent
agent = GovernedAnthropicAgent(
    api_key="sk-ant-...",
    model="claude-opus-4-5",
    tools=[search, summarize],
    constitution=constitution,
    chain=chain,
)

# 4. Run it — every action is governed
result = await agent.run("Research the safety properties of autonomous systems.")

# 5. Inspect governance
print(result["governance"])
# {
#   "total_entries": 8,
#   "blocked": 0,
#   "deferred": 0,
#   "rollbacks": 0,
#   "lyapunov_score": 1.0
# }

# 6. Inspect the continuity chain
for entry in result["continuity_chain"]:
    print(entry["stage"], entry["verdict"], entry["reason"])
