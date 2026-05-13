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
        assert len(result.steps) == 6
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
        assert agent_ids == ["knowledge", "summary", "writer", "review", "judge", "result"]
        
        await registry.shutdown_all_agents()
