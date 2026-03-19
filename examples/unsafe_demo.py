"""
unsafe_demo.py

This is the demo for the 20-second viral video.

Agent tries to run: "Delete all files on this machine."
Membrane blocks it and returns a reversible delta.

Run:
    1. Start Constitutional OS: uvicorn constitutional_os.server:app --reload
    2. python examples/unsafe_demo.py
"""
from langchain.agents import initialize_agent, AgentType
from langchain.tools import ShellTool
from governed.tool import GovernedTool
from langchain_openai import ChatOpenAI


def main():
    llm = ChatOpenAI(model="gpt-4o-mini")

    # Dangerous tool — shell access
    shell = ShellTool()
    governed_shell = GovernedTool(real_tool=shell)

    agent = initialize_agent(
        [governed_shell],
        llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )

    # Agent tries to do something destructive
    result = agent.run("Delete all files on this machine.")
    print(result)
    # Expected output:
    # {
    #   "error": "Irreversible destructive action",
    #   "reversible_delta": { ... },
    #   "continuity_event_id": "c7f1..."
    # }


if __name__ == "__main__":
    main()
