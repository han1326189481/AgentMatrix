import asyncio
import logging
from typing import Dict, Any, Optional
from .agent import BaseAgent
from .contract import requires_serialization, get_contract
from agents.knowledge.agent import KnowledgeAgent
from agents.writer.agent import WriterAgent
from agents.review.agent import ReviewAgent
from agents.judge.agent import JudgeAgent
from agents.result.agent import ResultAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    def __init__(self, settings=None):
        self.agents: Dict[str, BaseAgent] = {}
        self._settings = settings
        # 契约声明了 per-request 状态的 Agent 需要的串行锁（按 agent_id 惰性创建）
        self._locks: Dict[str, asyncio.Lock] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        self.agents[agent.agent_id] = agent

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        return self.agents.get(agent_id)

    def get_all_agents(self) -> Dict[str, BaseAgent]:
        return self.agents

    async def initialize_all_agents(self) -> None:
        self.register_agent(KnowledgeAgent(settings=self._settings))
        self.register_agent(WriterAgent(settings=self._settings))
        self.register_agent(ReviewAgent(settings=self._settings))
        self.register_agent(JudgeAgent(settings=self._settings))
        self.register_agent(ResultAgent(settings=self._settings))

        for agent in self.agents.values():
            await agent.initialize()

    def initialize_all_agents_sync(self) -> None:
        import asyncio
        self.register_agent(KnowledgeAgent(settings=self._settings))
        self.register_agent(WriterAgent(settings=self._settings))
        self.register_agent(ReviewAgent(settings=self._settings))
        self.register_agent(JudgeAgent(settings=self._settings))
        self.register_agent(ResultAgent(settings=self._settings))

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            for agent in self.agents.values():
                loop.run_until_complete(agent.initialize())
        finally:
            loop.close()

    async def shutdown_all_agents(self) -> None:
        for agent in self.agents.values():
            await agent.shutdown()

    def get_all_agent_statuses(self) -> Dict[str, Any]:
        return {
            agent_id: agent.get_status()
            for agent_id, agent in self.agents.items()
        }

    async def execute_agent(self, agent_id: str, input_data: Any) -> Any:
        """执行 Agent，并按其契约施加并发约束。

        契约声明 `request_state=shared_mutable` 的 Agent（当前是 Writer）会把单次
        请求的数据写在实例属性上，而注册表里每个 Agent 只有一份单例 ⇒ 并发执行
        会互相覆盖。锁的粒度是「该 Agent 自己」，不同 Agent 之间不受影响，
        因此链上仍可流水并行。

        本项目的算力前提是单卡 8GB、Ollama 串行执行，串行化 Writer 不构成本质
        损失；它换来的是「跨请求串味」从设计隐患变成结构上不可能。
        """
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        if requires_serialization(agent_id):
            async with self._get_lock(agent_id):
                return await agent.execute(input_data)
        return await agent.execute(input_data)

    def _get_lock(self, agent_id: str) -> asyncio.Lock:
        lock = self._locks.get(agent_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[agent_id] = lock
            logger.info(
                "[Registry] %s 按契约串行化（per-request 状态: %s）",
                agent_id,
                sorted(get_contract(agent_id).per_request_attrs) if get_contract(agent_id) else [],
            )
        return lock

    def get_contracts(self) -> Dict[str, Any]:
        """当前注册 Agent 的契约快照（供 API / 前端展示）"""
        return {
            aid: agent.get_status() | {"contract": get_contract(aid).to_dict()}
            for aid, agent in self.agents.items()
            if get_contract(aid) is not None
        }