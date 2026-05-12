from typing import Dict, Any, Optional
from .agent import BaseAgent
from agents.knowledge.agent import KnowledgeAgent
from agents.summary.agent import SummaryAgent
from agents.writer.agent import WriterAgent
from agents.review.agent import ReviewAgent
from agents.judge.agent import JudgeAgent
from agents.result.agent import ResultAgent


class AgentRegistry:
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        self.agents[agent.agent_id] = agent

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        return self.agents.get(agent_id)

    def get_all_agents(self) -> Dict[str, BaseAgent]:
        return self.agents

    async def initialize_all_agents(self) -> None:
        self.register_agent(KnowledgeAgent())
        self.register_agent(SummaryAgent())
        self.register_agent(WriterAgent())
        self.register_agent(ReviewAgent())
        self.register_agent(JudgeAgent())
        self.register_agent(ResultAgent())

        for agent in self.agents.values():
            await agent.initialize()

    async def shutdown_all_agents(self) -> None:
        for agent in self.agents.values():
            await agent.shutdown()

    def get_all_agent_statuses(self) -> Dict[str, Any]:
        return {
            agent_id: agent.get_status()
            for agent_id, agent in self.agents.items()
        }

    async def execute_agent(self, agent_id: str, input_data: Any) -> Any:
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        return await agent.execute(input_data)