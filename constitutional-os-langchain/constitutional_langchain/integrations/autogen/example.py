# integrations/autogen/example.py
# This is the shape of usage — not runnable code.

from constitutional_langchain.integrations.constitution import Constitution
from constitutional_langchain.integrations.continuity import ContinuityChain
from constitutional_langchain.integrations.autogen import (
    GovernanceMiddleware, GovernedAutoGenAgent, GovernedMultiAgentConversation,
)

constitution = Constitution(
    governance_url="https://constitutional-os-production.up.railway.app",
    agent_id="research-agent",
)
chain = ContinuityChain(agent_id="research-agent", session_id=constitution.session_id)
middleware = GovernanceMiddleware(constitution=constitution, chain=chain)

def search(query: str) -> str: ...
def summarize(text: str) -> str: ...

agent = GovernedAutoGenAgent(
    name="ResearchAgent",
    llm_config={"config_list": [{"model": "gpt-4o", "api_key": "sk-..."}]},
    tools={"search": search, "summarize": summarize},
    middleware=middleware,
)

print(agent.governance_summary())
# {"total_entries": 12, "blocked": 1, "lyapunov_score": 0.97}

# Multi-agent
conversation = GovernedMultiAgentConversation(
    agents=[agent_a, agent_b],
    task="Research and summarize AI governance frameworks.",
)
result = conversation.run()
print(result["shared_lyapunov"])
