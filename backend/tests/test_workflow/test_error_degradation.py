"""T3: 工作流错误降级测试"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from agents.base.agent import AgentInput, AgentOutput
from models.workflow import WorkflowInput


class TestWorkflowErrorDegradation:
    """测试工作流错误降级"""

    @pytest.fixture(autouse=True)
    def clear_intent_cache(self):
        """每个测试前清除 IntentCache，避免 L2 完整结果缓存在测试间污染"""
        try:
            from core.skill_engine.intent_cache import get_intent_cache
            get_intent_cache().clear()
        except Exception:
            pass
        yield
        try:
            from core.skill_engine.intent_cache import get_intent_cache
            get_intent_cache().clear()
        except Exception:
            pass

    @pytest.fixture
    def mock_registry(self):
        """创建 mock registry，所有 Agent 正常执行"""
        from agents.base.agent_registry import AgentRegistry
        registry = MagicMock(spec=AgentRegistry)
        registry.execute_agent = AsyncMock()

        async def normal_execute(agent_id, agent_input):
            return AgentOutput(
                content=json.dumps({"result": f"output from {agent_id}"}),
                success=True,
                metadata={"knowledge_count": 1} if agent_id == "knowledge" else {}
            )
        registry.execute_agent.side_effect = normal_execute
        return registry

    @pytest.fixture
    def mock_registry_knowledge_fail(self):
        """创建 mock registry，knowledge agent 失败"""
        from agents.base.agent_registry import AgentRegistry
        registry = MagicMock(spec=AgentRegistry)
        registry.execute_agent = AsyncMock()

        async def execute_with_knowledge_fail(agent_id, agent_input):
            if agent_id == "knowledge":
                raise RuntimeError("Knowledge Agent 模拟失败")
            return AgentOutput(
                content=json.dumps({"result": f"output from {agent_id}"}),
                success=True
            )
        registry.execute_agent.side_effect = execute_with_knowledge_fail
        return registry

    @pytest.fixture
    def mock_registry_writer_fail(self):
        """创建 mock registry，writer agent 失败"""
        from agents.base.agent_registry import AgentRegistry
        registry = MagicMock(spec=AgentRegistry)
        registry.execute_agent = AsyncMock()

        async def execute_with_writer_fail(agent_id, agent_input):
            if agent_id == "writer":
                raise RuntimeError("Writer Agent 模拟失败")
            return AgentOutput(
                content=json.dumps({"result": f"output from {agent_id}"}),
                success=True,
                metadata={"knowledge_count": 1} if agent_id == "knowledge" else {}
            )
        registry.execute_agent.side_effect = execute_with_writer_fail
        return registry

    @pytest.fixture
    def mock_registry_multi_fail(self):
        """创建 mock registry，多个 agent 失败"""
        from agents.base.agent_registry import AgentRegistry
        registry = MagicMock(spec=AgentRegistry)
        registry.execute_agent = AsyncMock()

        async def execute_with_multi_fail(agent_id, agent_input):
            if agent_id in ("knowledge", "review"):
                raise RuntimeError(f"{agent_id} Agent 模拟失败")
            return AgentOutput(
                content=json.dumps({"result": f"output from {agent_id}"}),
                success=True,
                metadata={"knowledge_count": 1} if agent_id == "knowledge" else {}
            )
        registry.execute_agent.side_effect = execute_with_multi_fail
        return registry

    @pytest.mark.asyncio
    async def test_knowledge_fail_continues(self, mock_registry_knowledge_fail):
        """knowledge 失败后继续执行后续 Agent"""
        from core.workflow.service import WorkflowService
        service = WorkflowService(mock_registry_knowledge_fail)
        input_data = WorkflowInput(user_input="测试问题")
        result = await service.execute(input_data)

        assert result.partial_success is True
        assert result.error_summary is not None
        assert len(result.error_summary) >= 1
        assert any("knowledge" in err.lower() for err in result.error_summary)
        # 应该有 5 个 step（包括失败的）
        assert len(result.steps) == 5
        # 最终结果不为空
        assert len(result.final_result) > 0

    @pytest.mark.asyncio
    async def test_writer_fail_continues(self, mock_registry_writer_fail):
        """writer 失败后继续执行后续 Agent"""
        from core.workflow.service import WorkflowService
        service = WorkflowService(mock_registry_writer_fail)
        input_data = WorkflowInput(user_input="测试问题")
        result = await service.execute(input_data)

        assert result.partial_success is True
        assert result.error_summary is not None
        assert any("writer" in err.lower() for err in result.error_summary)
        assert len(result.steps) == 5
        assert len(result.final_result) > 0

    @pytest.mark.asyncio
    async def test_multiple_fail_aggregates_errors(self, mock_registry_multi_fail):
        """多个 Agent 失败时 error_summary 聚合正确"""
        from core.workflow.service import WorkflowService
        service = WorkflowService(mock_registry_multi_fail)
        input_data = WorkflowInput(user_input="测试问题")
        result = await service.execute(input_data)

        assert result.partial_success is True
        assert result.error_summary is not None
        assert len(result.error_summary) >= 2
        assert len(result.steps) == 5

    @pytest.mark.asyncio
    async def test_all_success_no_error_summary(self, mock_registry):
        """全部成功时无 error_summary"""
        from core.workflow.service import WorkflowService
        service = WorkflowService(mock_registry)
        input_data = WorkflowInput(user_input="测试问题")
        result = await service.execute(input_data)

        assert result.partial_success is False
        assert result.error_summary is None
        assert len(result.steps) == 5
        assert len(result.final_result) > 0

    @pytest.mark.asyncio
    async def test_stream_execute_error_degradation(self, mock_registry_knowledge_fail):
        """流式执行也支持错误降级"""
        from core.workflow.service import WorkflowService
        service = WorkflowService(mock_registry_knowledge_fail)
        input_data = WorkflowInput(user_input="测试问题")

        events = []
        async for event in service.execute_stream(input_data):
            events.append(event)

        # 应该包含 start 和 complete 事件
        assert any(e["type"] == "start" for e in events)
        assert any(e["type"] == "complete" for e in events)
        # 应该有 agent_error 事件
        assert any(e["type"] == "agent_error" for e in events)
        # complete 事件应包含 error_summary
        complete_event = next(e for e in events if e["type"] == "complete")
        assert complete_event.get("error_summary") is not None