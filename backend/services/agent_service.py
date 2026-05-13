from typing import Dict, Any, List, Optional
from agents.base.agent_registry import AgentRegistry
from agents.base.agent import AgentInput, AgentOutput
from models.workflow import WorkflowInput, WorkflowOutput
from core.workflow.service import WorkflowService
from core.dynamic_router import get_dynamic_router
from knowledge.service import KnowledgeService
from api.v1.metrics.router import get_metrics_store
import logging

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self):
        self.agent_registry = AgentRegistry()
        self.workflow_service = WorkflowService(self.agent_registry)
        self.dynamic_router = get_dynamic_router()
        self.knowledge_service = KnowledgeService()
        self.metrics = get_metrics_store()

    async def initialize(self) -> None:
        await self.agent_registry.initialize_all_agents()
        logger.info("AgentService initialized successfully")

    async def shutdown(self) -> None:
        await self.agent_registry.shutdown_all_agents()
        logger.info("AgentService shutdown successfully")

    async def execute_workflow(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> WorkflowOutput:
        workflow_input = WorkflowInput(user_input=user_input, context=context)
        return await self.workflow_service.execute(workflow_input)

    async def execute_single_agent(self, agent_id: str, input_data: AgentInput) -> AgentOutput:
        return await self.agent_registry.execute_agent(agent_id, input_data)

    def get_all_agent_statuses(self) -> Dict[str, Any]:
        return self.agent_registry.get_all_agent_statuses()

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        agent = self.agent_registry.get_agent(agent_id)
        if agent:
            return agent.get_status()
        return None

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "workflow": self.metrics,
            "routing": self.dynamic_router.get_routing_stats(),
            "knowledge": self.knowledge_service.get_knowledge_stats()
        }

    def search_knowledge(self, query: str, limit: int = 5) -> Dict[str, List[str]]:
        return self.knowledge_service.search(query, limit)

    def add_knowledge(self, keyword: str, content: List[str]) -> None:
        self.knowledge_service.add_knowledge(keyword, content)

    def delete_knowledge(self, keyword: str) -> bool:
        return self.knowledge_service.delete_knowledge(keyword)

    async def route_request(self, complexity_score: float, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        return await self.dynamic_router.route(complexity_score, prompt, system_prompt)

    def get_routing_stats(self) -> Dict[str, Any]:
        return self.dynamic_router.get_routing_stats()


_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
