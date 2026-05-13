import pytest
from agents.knowledge.agent import KnowledgeAgent
from agents.base.agent import AgentInput


class TestKnowledgeAgent:
    @pytest.mark.asyncio
    async def test_execute(self):
        agent = KnowledgeAgent()
        input_data = AgentInput(content="生成校园AI助手方案")
        
        result = await agent.execute(input_data)
        
        assert result.success is True
        assert "校园AI助手方案" in result.content
        assert "知识增强" in result.content

    @pytest.mark.asyncio
    async def test_extract_keywords(self):
        agent = KnowledgeAgent()
        keywords = agent._extract_keywords("生成校园AI助手方案")
        
        assert isinstance(keywords, list)
        assert "校园" in keywords
        assert "AI" in keywords

    @pytest.mark.asyncio
    async def test_empty_input(self):
        agent = KnowledgeAgent()
        input_data = AgentInput(content="")
        
        result = await agent.execute(input_data)
        
        assert result.success is True
