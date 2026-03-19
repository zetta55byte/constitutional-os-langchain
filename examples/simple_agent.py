from langchain.agents import initialize_agent, AgentType
from langchain.tools import DuckDuckGoSearchRun
from governed.tool import GovernedTool
from langchain_openai import ChatOpenAI


def main():
    llm = ChatOpenAI(model="gpt-4o-mini")

    search = DuckDuckGoSearchRun()
    governed_search = GovernedTool(real_tool=search)

    agent = initialize_agent(
        [governed_search],
        llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )

    print(agent.run("Search for reversible governance substrates."))


if __name__ == "__main__":
    main()
