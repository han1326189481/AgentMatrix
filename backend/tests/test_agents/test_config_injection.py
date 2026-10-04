"""T4: 配置注入测试"""
import pytest
from unittest.mock import MagicMock


class MockSettings:
    """模拟配置对象"""
    def __init__(self):
        self.deepseek_api_key = "mock-api-key-12345"
        self.deepseek_model = "deepseek-chat-mock"


class TestConfigInjection:
    """测试配置注入"""

    def test_agent_receives_injected_settings(self):
        """Agent 使用注入的 settings

        注：模型名（cloud_model / local_model）由 ModelRegistry 单一数据源提供，
        不受注入 settings 影响（见 BaseAgent.__init__ 与 core/model_registry.py 顶部
        的设计原则「模型名只在这里定义一次」）。注入 settings 生效的是 API Key 等
        运行期配置。故此处断言「注入值 + 取值链路」，不断言 cloud_model ——
        后者与单一数据源设计冲突（原断言 'deepseek-chat-mock' 正是因此长期不成立）。
        """
        from agents.result.agent import ResultAgent
        from core.model_registry import get_cloud_model

        mock_settings = MockSettings()
        agent = ResultAgent(settings=mock_settings)

        # 注入的 settings 确实是生效的那一份
        assert agent._get_settings() is mock_settings
        assert agent._get_settings().deepseek_model == "deepseek-chat-mock"
        assert agent._get_settings().deepseek_api_key == "mock-api-key-12345"
        # 模型名来自全局 ModelRegistry（非注入 settings）
        assert agent.cloud_model == get_cloud_model()

    def test_agent_falls_back_to_global_settings(self):
        """未注入 settings 时回退到全局配置"""
        from agents.result.agent import ResultAgent
        agent = ResultAgent()  # 不传 settings
        # 应该回退到全局 settings
        settings = agent._get_settings()
        assert settings is not None

    def test_agent_with_settings_prefers_injected(self):
        """Agent 优先使用注入的 settings 而非全局配置"""
        from agents.judge.agent import JudgeAgent
        mock_settings = MockSettings()
        agent = JudgeAgent(settings=mock_settings)
        settings = agent._get_settings()
        assert settings is mock_settings
        assert settings.deepseek_api_key == "mock-api-key-12345"

    def test_agent_registry_passes_settings(self):
        """AgentRegistry 初始化时传递 settings 给所有 Agent"""
        from agents.base.agent_registry import AgentRegistry
        mock_settings = MockSettings()
        registry = AgentRegistry(settings=mock_settings)
        registry.initialize_all_agents_sync()

        for agent_id, agent in registry.agents.items():
            settings = agent._get_settings()
            assert settings is mock_settings, f"Agent {agent_id} did not receive injected settings"