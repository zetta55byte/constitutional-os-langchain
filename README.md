# LangChain Governed Agent Template

### Powered by Constitutional OS

```
Agent
  │
  ▼
Proposed Action
  │
  ▼
┌─────────────────────────────────────┐
│         Governance Check            │
│                                     │
│  M1 Safety       M2 Reversibility   │
│  M3 Pluralism    M4 Human Primacy   │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
    ALLOW            DENY
       │               │
       ▼               ▼
  Execute Tool    Reversible Delta
       │               │
       └───────┬───────┘
               ▼
       Continuity Chain
       (append-only log)
```

---

## Why This Matters

**Every AI agent that can take actions needs a governance layer.** Without one, you have no way to know what your agent did, why it was allowed, or how to undo it. Constitutional OS provides the substrate: every proposed action passes through four canonical membranes before execution, and every decision — whether allowed or denied — is logged to an append-only continuity chain. This means your agent's behavior is deterministic, auditable, and rollback-ready by design, not by accident.

**Reversibility is not optional at scale.** When an agent takes a wrong action in production — and it will — you need to be able to undo it precisely, not restore from a backup. The reversible delta calculus in Constitutional OS ensures that every ratified action carries its own inverse. You can roll back one action, or ten, or a hundred, without touching anything else. Combined with the continuity chain, this gives you something that doesn't exist anywhere else in the agent ecosystem: a formal audit trail with guaranteed rollback semantics.

---

This repository provides a minimal, production-ready template for building **governed AI agents** using:

- **LangChain**
- **Constitutional OS**
- **Reversible delta calculus**
- **Membrane enforcement**
- **Continuity chain logging**

It demonstrates how to wrap any LangChain tool with a governance substrate that:
- checks every action before execution
- blocks unsafe or irreversible actions
- logs every decision to an append-only continuity chain
- returns reversible deltas when actions are blocked

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Constitutional OS server

```bash
pip install constitutional-os
uvicorn constitutional_os.console.api:app --reload
```

Or use the hosted API:
```bash
export GOVERNANCE_URL=https://constitutional-os-production.up.railway.app/governance/check
```

### 3. Set your OpenAI key

```bash
cp .env.example .env
# Add your OPENAI_API_KEY
```

### 4. Run the simple agent

```bash
python examples/simple_agent.py
```

### 5. Run the unsafe demo (the viral one)

```bash
python examples/unsafe_demo.py
```

Agent tries to run `rm -rf /`. Membrane blocks it. Returns:

```json
{
  "error": "Irreversible destructive action",
  "reversible_delta": { "..." : "..." },
  "continuity_event_id": "c7f1..."
}
```

Then prints the continuity chain:

```
── Continuity Chain (last entries) ─────────────────────
  [  0] 2026-03-18T...  tool_call_blocked    blocked    Agent attempted rm -rf /
  [  1] 2026-03-18T...  membrane_check       deferred   M2 reversibility engaged
─────────────────────────────────────────────────────────
```

---

## How it works

```python
from governed.tool import GovernedTool
from langchain.tools import DuckDuckGoSearchRun

search = DuckDuckGoSearchRun()
governed_search = GovernedTool(real_tool=search)

# Every tool call is now:
# - membrane-checked
# - reversible
# - continuity-logged
# - deterministic
```

Wrap **any** LangChain tool in `GovernedTool` and every action goes through the Constitutional OS governance substrate before execution.

---

## Repo structure

```
langchain-governed-agent/
├── README.md
├── requirements.txt
├── .env.example
├── governed/
│   ├── __init__.py
│   ├── config.py       # GOVERNANCE_URL config
│   ├── client.py       # governance_check() client
│   └── tool.py         # GovernedTool wrapper
└── examples/
    ├── simple_agent.py  # basic governed agent
    └── unsafe_demo.py   # membrane blocks rm -rf /
```

---

## Links

- **Constitutional OS:** https://github.com/zetta55byte/constitutional-os
- **PyPI:** https://pypi.org/project/constitutional-os/
- **Live API:** https://constitutional-os-production.up.railway.app/
- **Paper:** https://zenodo.org/records/19075163
- **RFC-0001:** https://github.com/zetta55byte/constitutional-os/blob/main/rfc/RFC-0001-core-spec.md