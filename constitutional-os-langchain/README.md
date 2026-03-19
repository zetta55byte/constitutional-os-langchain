# constitutional-os-langchain

**Constitutional OS governance for LangChain agents.**

Wraps any LangChain tool with membrane-checked governance, continuity chain
logging, and reversible delta support — in one line of code.

[![PyPI](https://img.shields.io/pypi/v/constitutional-os-langchain)](https://pypi.org/project/constitutional-os-langchain/)
[![RFC](https://img.shields.io/badge/RFC-0001-blue)](https://github.com/zetta55byte/constitutional-os/blob/main/rfc/RFC-0001-core-spec.md)
[![Constitutional OS](https://img.shields.io/badge/governed%20by-Constitutional%20OS-purple)](https://github.com/zetta55byte/constitutional-os)

---

## What it does

Every tool call your agent makes is:

- **Membrane-checked** before execution (safety, reversibility, pluralism, human primacy)
- **Logged** to an append-only continuity chain
- **Blocked** if it violates a membrane
- **Deferred** if it requires human approval
- **Reversible** — rollback available on any ratified action

```
Agent proposes action
       ↓
Constitutional OS governance check
       ↓
M1 Safety → M2 Reversibility → M3 Pluralism → M4 Human Primacy
       ↓
verdict: pass | block | defer
       ↓
Execute (if pass) / Stop (if block) / Wait (if defer)
       ↓
Logged to continuity chain
```

---

## Install

```bash
pip install constitutional-os-langchain
```

---

## Quick start

```python
from constitutional_langchain import GovernedTool, GovernanceClient
from langchain.tools import DuckDuckGoSearchRun

# Connect to governance API
client = GovernanceClient(
    base_url="https://constitutional-os-production.up.railway.app"
)

# Wrap any LangChain tool
search         = DuckDuckGoSearchRun()
governed       = GovernedTool(real_tool=search, client=client)

# Every call is now governance-checked
result = governed.run("latest AI governance research")
```

---

## Demo output

```
Demo 1: Safe search action
──────────────────────────────────────────
🟢 PASSED Constitutional OS governance
   Tool:    search
   Log ID:  42

Demo 2: Unsafe delete action (critical + irreversible)
──────────────────────────────────────────
🔴 BLOCKED by Constitutional OS
   Tool:    delete_all_users
   Reason:  Critical autonomous change blocked by M1 safety membrane
   Log ID:  43
   Membranes:
     ✗ M1_safety: Critical autonomous changes are blocked

Demo 3: Significant config change
──────────────────────────────────────────
🟡 DEFERRED by Constitutional OS — human approval required
   Tool:    update_global_config
   Reason:  Significant autonomous change requires human review
   Log ID:  44
```

---

## Use with a LangChain agent

```python
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from constitutional_langchain import GovernedTool, GovernanceClient

client = GovernanceClient()
llm    = ChatOpenAI(model="gpt-4")

# Wrap all your tools
tools = [
    GovernedTool(real_tool=my_tool_1, client=client),
    GovernedTool(real_tool=my_tool_2, client=client, severity="significant"),
    GovernedTool(real_tool=my_tool_3, client=client, reversible=False),
]

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
)

# Every tool call is now governed
agent.run("Do something that requires multiple tools")
```

---

## Severity levels

| Severity | Triggers |
|----------|----------|
| `trivial` | Passes all membranes |
| `normal` | Standard governance check |
| `significant` | Triggers M4 human primacy — deferred |
| `critical` | Blocked by M1 safety membrane |

---

## The four membranes

| Membrane | Blocks/defers when |
|----------|--------------------|
| M1 Safety | `severity=critical` + `autonomy=autonomous` |
| M2 Reversibility | `reversible=False` + `autonomy=autonomous` |
| M3 Pluralism | Action would eliminate future option space |
| M4 Human Primacy | `severity=significant/critical` or `reversible=False` |

---

## Links

- **Constitutional OS:** https://github.com/zetta55byte/constitutional-os
- **RFC-0001:** https://github.com/zetta55byte/constitutional-os/blob/main/rfc/RFC-0001-core-spec.md
- **Paper:** https://zenodo.org/records/19075163
- **Live API:** https://constitutional-os-production.up.railway.app/
- **PyPI:** https://pypi.org/project/constitutional-os/
