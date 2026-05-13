import pytest
from agents.judge.agent import JudgeAgent
from agents.base.agent import AgentInput


class TestJudgeAgent:
    @pytest.mark.asyncio
    async def test_execute(self):
        agent = JudgeAgent()
        input_data = AgentInput(content="测试内容")
        
        result = await agent.execute(input_data)
        
        assert result.success is True
        assert "complexity_score" in result.content

    @pytest.mark.asyncio
    async def test_complexity_threshold(self):
        agent = JudgeAgent()
        
        input_data_high = AgentInput(content="复杂任务：深度分析AI模型架构，涉及算法研究和系统设计")
        result_high = await agent.execute(input_data_high)
        
        input_data_low = AgentInput(content="简单任务：生成一个简单的问候语")
        result_low = await agent.execute(input_data_low)
        
        assert result_high.metadata["complexity_score"] >= result_low.metadata["complexity_score"]
