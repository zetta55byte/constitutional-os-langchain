# integrations/vercel/example.py
# This is the shape of usage — not runnable code.
# Two patterns: Python streaming agent + FastAPI middleware.
# For TypeScript/Next.js see agent.py -> TYPESCRIPT_SNIPPET

from fastapi import FastAPI
from constitutional_langchain.integrations.constitution import Constitution
from constitutional_langchain.integrations.continuity import ContinuityChain
from constitutional_langchain.integrations.vercel import GovernedVercelAgent, GovernanceMiddleware

constitution = Constitution(
    governance_url="https://constitutional-os-production.up.railway.app",
    agent_id="my-vercel-agent",
)
chain = ContinuityChain(
    agent_id="my-vercel-agent",
    session_id=constitution.session_id,
)

async def search(query: str) -> str:
    """Search the web."""
    ...

# Pattern A: async streaming agent
agent = GovernedVercelAgent(
    constitution=constitution,
    chain=chain,
    tools={"search": search},
)

# Stream governed output — tool calls paused, governed, then resumed
async for chunk in agent.stream(messages, model_fn=my_model_fn):
    print(chunk)

# Pattern B: FastAPI middleware
app = FastAPI()
app.add_middleware(
    GovernanceMiddleware,
    constitution=constitution,
    chain=chain,
    governed_path="/api/chat",
)

# Every POST /api/chat now:
#   1. Checks M1-M4 on the plan
#   2. Adds X-Constitutional-OS-Session header
#   3. Adds X-Constitutional-OS-Lyapunov header

# Pattern C: TypeScript / Next.js
# from constitutional_langchain.integrations.vercel import TYPESCRIPT_SNIPPET
# Drop into: app/api/chat/route.ts
