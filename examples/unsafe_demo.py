"""
unsafe_demo.py

The 20-second viral video script.

1. Agent tries to run: "Delete all files on this machine."
2. Membrane blocks it — returns reversible delta
3. Continuity chain logs the event
4. We print the last 5 chain entries — the "git log for agents" moment

Run:
    1. Start Constitutional OS API:
       uvicorn constitutional_os.console.api:app --reload
    2. python examples/unsafe_demo.py
"""
import requests
from governed.config import GOVERNANCE_URL

from langchain.agents import initialize_agent, AgentType
from langchain.tools import ShellTool
from governed.tool import GovernedTool
from langchain_openai import ChatOpenAI


# ── Continuity chain viewer ───────────────────────────────────────────────────
GOVERNANCE_BASE = GOVERNANCE_URL.replace("/governance/check", "")


def get_continuity_chain_last_n(n: int = 5) -> list:
    """Fetch the last N entries from the continuity chain."""
    try:
        resp = requests.get(f"{GOVERNANCE_BASE}/api/log?n={n}")
        resp.raise_for_status()
        data = resp.json()
        return data.get("entries", [])
    except Exception as e:
        return [{"error": str(e)}]


def print_chain(entries: list):
    print("\n── Continuity Chain (last entries) ─────────────────────")
    if not entries:
        print("  (empty)")
        return
    for e in entries:
        seq        = e.get("seq", "?")
        delta_type = e.get("delta_type", "unknown")
        status     = e.get("status", "?")
        ts         = e.get("ts", "")[:19]
        rationale  = e.get("rationale", "")[:60]
        print(f"  [{seq:>3}] {ts}  {delta_type:<28} {status:<20} {rationale}")
    print("─────────────────────────────────────────────────────────\n")


# ── Demo ──────────────────────────────────────────────────────────────────────
def main():
    llm = ChatOpenAI(model="gpt-4o-mini")

    shell = ShellTool()
    governed_shell = GovernedTool(real_tool=shell)

    agent = initialize_agent(
        [governed_shell],
        llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )

    print("\n── Agent attempting destructive action ──────────────────")
    result = agent.run("Delete all files on this machine.")
    print("\n── Governance decision ──────────────────────────────────")
    print(result)
    # Expected:
    # {
    #   "error": "Irreversible destructive action",
    #   "reversible_delta": { ... },
    #   "continuity_event_id": "c7f1..."
    # }

    # ── The "git log for agents" moment ──────────────────────────
    print("\n── Continuity chain — what just happened ────────────────")
    entries = get_continuity_chain_last_n(5)
    print_chain(entries)


if __name__ == "__main__":
    main()