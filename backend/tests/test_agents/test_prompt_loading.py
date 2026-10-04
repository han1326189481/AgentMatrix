"""T1: Prompt 模板加载测试"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock


class TestPromptLoading:
    """测试 PromptManager 模板加载"""

    def test_load_system_prompt_from_template(self):
        """正常加载模板文件"""
        from agents.writer.agent import WriterAgent
        agent = WriterAgent()
        prompt = agent._load_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Writer Agent" in prompt or "内容生成" in prompt

    def test_load_system_prompt_cached(self):
        """模板加载缓存有效性：第二次调用返回同一对象"""
        from agents.writer.agent import WriterAgent
        agent = WriterAgent()
        first = agent._load_system_prompt()
        second = agent._load_system_prompt()
        assert first == second
        assert first is second  # 同一对象（缓存命中）

    def test_load_system_prompt_missing_template(self):
        """模板文件缺失时降级返回空字符串"""
        from agents.base.agent import BaseAgent, AgentInput, AgentOutput

        class TestAgent(BaseAgent):
            async def execute(self, input_data: AgentInput) -> AgentOutput:
                return AgentOutput(content="test")

        agent = TestAgent("nonexistent", "Test Agent")
        prompt = agent._load_system_prompt()
        assert isinstance(prompt, str)
        assert prompt == ""  # 降级返回空字符串

    def test_all_agents_have_template_files(self):
        """所有 5 个 Agent 都有对应的 system.txt 模板文件"""
        import os
        agent_ids = ["knowledge", "writer", "review", "judge", "result"]
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        prompts_dir = os.path.join(base_dir, "prompts", "templates")

        for agent_id in agent_ids:
            template_path = os.path.join(prompts_dir, agent_id, "system.txt")
            assert os.path.exists(template_path), f"Missing template for {agent_id}: {template_path}"
            with open(template_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert len(content) > 50, f"Template for {agent_id} is too short ({len(content)} chars)"

    def test_load_all_agent_prompts(self):
        """所有 Agent 都能成功加载各自的 prompt"""
        from agents.knowledge.agent import KnowledgeAgent
        from agents.writer.agent import WriterAgent
        from agents.review.agent import ReviewAgent
        from agents.judge.agent import JudgeAgent
        from agents.result.agent import ResultAgent

        agents = [
            KnowledgeAgent(), WriterAgent(), ReviewAgent(),
            JudgeAgent(), ResultAgent()
        ]

        for agent in agents:
            prompt = agent._load_system_prompt()
            assert isinstance(prompt, str)
            assert len(prompt) > 0, f"Agent {agent.agent_id} returned empty prompt"