# integrations/openai/example.py
# This is the shape of usage — not runnable code.

from openai import OpenAI
from constitutional_langchain.integrations.constitution import Constitution
from constitutional_langchain.integrations.continuity import ContinuityChain
from constitutional_langchain.integrations.openai import GovernedOpenAIAssistant

# 1. Create the shared governance objects
constitution = Constitution(
    governance_url="https://constitutional-os-production.up.railway.app",
    agent_id="my-openai-agent",
)
chain = ContinuityChain(
    agent_id="my-openai-agent",
    session_id=constitution.session_id,
)

# 2. Define your tools
def search(query: str) -> str:
    """Search the web."""
    ...

def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    ...

# 3. Create the governed assistant
agent = GovernedOpenAIAssistant(
    client=OpenAI(api_key="sk-..."),
    constitution=constitution,
    chain=chain,
    assistant_id="asst_...",
    tools={"search": search, "calculator": calculator},
)

# 4. Run it — every required_action tool call is governed
result = agent.run("Summarize the latest AI governance papers.")

# 5. Inspect governance
print(result["governance"])
# {
#   "total_entries": 6,
#   "blocked": 0,
#   "deferred": 0,
#   "rollbacks": 0,
#   "lyapunov_score": 1.0
# }

print(result["thread_id"])   # OpenAI thread ID for continuity
