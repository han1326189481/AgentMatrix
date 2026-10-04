"""Result Agent 测试"""
import pytest
import json
from agents.result.agent import ResultAgent
from agents.base.agent import AgentInput


class TestResultAgent:
    @pytest.mark.asyncio
    async def test_local_output_no_cloud(self):
        """本地直接输出（无云端润色）"""
        agent = ResultAgent()
        result_input = json.dumps({
            "user_task": "写一篇短文",
            "writer_output": "# 短文标题\n\n这是正文内容。",
            "judge_decision": "local_output",
            "cloud_mode": "none",
            "summary_result": "",
            "executed_locally": True,
            "difficulty_threshold": 0.3,
            "review_result": "{}",
            "judge_result": "{}"
        })
        input_data = AgentInput(content=result_input)

        result = await agent.execute(input_data)

        assert result.success is True
        assert "短文标题" in result.content or "正文内容" in result.content
        assert result.metadata["executed_locally"] is True

    @pytest.mark.asyncio
    async def test_clean_markdown_tags(self):
        """输出格式清理（markdown 标记）"""
        agent = ResultAgent()
        result_input = json.dumps({
            "user_task": "测试",
            "writer_output": "【知识增强】\n【知识库内容】\n1. 知识条目\n\n【需求分析】\n任务类型: 通用",
            "judge_decision": "local_output",
            "cloud_mode": "none",
            "summary_result": "",
            "executed_locally": True,
            "difficulty_threshold": 0.3,
            "review_result": "{}",
            "judge_result": "{}"
        })
        input_data = AgentInput(content=result_input)

        result = await agent.execute(input_data)

        assert result.success is True
        # 中间过程标记应被清理
        assert "【知识增强】" not in result.content
        assert "【知识库内容】" not in result.content
        assert "【需求分析】" not in result.content

    @pytest.mark.asyncio
    async def test_empty_writer_output(self):
        """Writer 输出为空时的处理"""
        agent = ResultAgent()
        result_input = json.dumps({
            "user_task": "测试",
            "writer_output": "",
            "judge_decision": "local_output",
            "cloud_mode": "none",
            "summary_result": "",
            "executed_locally": True,
            "difficulty_threshold": 0.3,
            "review_result": "{}",
            "judge_result": "{}"
        })
        input_data = AgentInput(content=result_input)

        result = await agent.execute(input_data)

        assert result.success is True
        assert "暂无生成内容" in result.content

    @pytest.mark.asyncio
    async def test_invalid_json_input(self):
        """非JSON输入的降级处理"""
        agent = ResultAgent()
        input_data = AgentInput(content="这不是JSON")

        result = await agent.execute(input_data)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_metadata_fields(self):
        """验证 metadata 包含必要字段"""
        agent = ResultAgent()
        result_input = json.dumps({
            "user_task": "测试",
            "writer_output": "测试内容",
            "judge_decision": "local_output",
            "cloud_mode": "none",
            "summary_result": "",
            "executed_locally": True,
            "difficulty_threshold": 0.3,
            "review_result": "{}",
            "judge_result": "{}"
        })
        input_data = AgentInput(content=result_input)

        result = await agent.execute(input_data)

        assert result.success is True
        assert "format" in result.metadata
        assert "length" in result.metadata
        assert "model_used" in result.metadata
        assert "executed_locally" in result.metadata