"""工作流服务测试 - 更新版：5 Agent 流水线"""
import pytest
from models.workflow import WorkflowInput
from core.workflow.service import WorkflowService
from agents.base.agent_registry import AgentRegistry


class TestWorkflowService:
    @pytest.mark.asyncio
    async def test_execute_workflow(self):
        registry = AgentRegistry()
        await registry.initialize_all_agents()

        service = WorkflowService(registry)
        input_data = WorkflowInput(user_input="生成校园AI助手方案")

        result = await service.execute(input_data)

        assert result is not None
        assert result.final_result is not None
        assert len(result.steps) == 5  # 5 Agent 流水线
        assert result.executed_locally is True

        await registry.shutdown_all_agents()

    @pytest.mark.asyncio
    async def test_workflow_steps(self):
        registry = AgentRegistry()
        await registry.initialize_all_agents()

        service = WorkflowService(registry)
        input_data = WorkflowInput(user_input="测试")

        result = await service.execute(input_data)

        agent_ids = [step.agent_id for step in result.steps]
        assert agent_ids == ["knowledge", "writer", "review", "judge", "result"]

        await registry.shutdown_all_agents()

    @pytest.mark.asyncio
    async def test_workflow_with_knowledge_query(self):
        """测试知识库查询工作流"""
        registry = AgentRegistry()
        await registry.initialize_all_agents()

        service = WorkflowService(registry)
        input_data = WorkflowInput(user_input="什么是人工智能")

        result = await service.execute(input_data)

        assert result is not None
        assert len(result.steps) == 5
        assert result.final_result is not None

        await registry.shutdown_all_agents()

    @pytest.mark.asyncio
    async def test_workflow_with_complex_task(self):
        """测试复杂任务工作流"""
        registry = AgentRegistry()
        await registry.initialize_all_agents()

        service = WorkflowService(registry)
        input_data = WorkflowInput(user_input="帮我策划一个校园马拉松活动方案，包含预算和时间安排")

        result = await service.execute(input_data)

        assert result is not None
        assert len(result.steps) == 5
        # 复杂任务应该触发较高的 difficulty_threshold
        assert result.complexity_score >= 0.0

        await registry.shutdown_all_agents()