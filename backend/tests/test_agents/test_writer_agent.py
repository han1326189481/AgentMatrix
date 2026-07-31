"""Writer Agent 测试"""
import pytest
import json
from agents.writer.agent import WriterAgent
from agents.base.agent import AgentInput


class TestWriterAgent:
    @pytest.mark.asyncio
    async def test_generate_with_knowledge_template(self):
        """有匹配知识模板时的回答生成"""
        agent = WriterAgent()
        knowledge_input = json.dumps({
            "task": "生成校园AI助手方案",
            "original_question": "生成校园AI助手方案",
            "keywords": ["校园", "AI", "方案"],
            "knowledge_items": ["人工智能技术快速发展，大语言模型具备强大的上下文理解与生成能力。"],
            "requirements": ["需要包含技术架构", "必须考虑安全性"],
            "outline": ["一、需求分析", "二、方案设计", "三、实施步骤"],
            "summary": "用户需求：生成校园AI助手方案 | 关键词：校园, AI, 方案",
            "task_type": "方案设计"
        })
        input_data = AgentInput(content=knowledge_input)

        result = await agent.execute(input_data)

        assert result.success is True
        assert len(result.content) > 0
        assert result.metadata is not None

    @pytest.mark.asyncio
    async def test_generate_without_knowledge(self):
        """无知识模板时的通用回答"""
        agent = WriterAgent()
        knowledge_input = json.dumps({
            "task": "写一篇关于春天的短文",
            "original_question": "写一篇关于春天的短文",
            "keywords": ["春天"],
            "knowledge_items": [],
            "requirements": [],
            "outline": ["一、引言", "二、主体内容", "三、结论"],
            "summary": "用户需求：写一篇关于春天的短文",
            "task_type": "文档撰写"
        })
        input_data = AgentInput(content=knowledge_input)

        result = await agent.execute(input_data)

        assert result.success is True
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_simple_conversation_response(self):
        """简单对话的应答"""
        agent = WriterAgent()
        knowledge_input = json.dumps({
            "task": "你好",
            "original_question": "你好",
            "keywords": [],
            "knowledge_items": [],
            "requirements": [],
            "outline": [],
            "summary": "你好",
            "task_type": "简单对话"
        })
        input_data = AgentInput(content=knowledge_input)

        result = await agent.execute(input_data)

        assert result.success is True
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_empty_input_handling(self):
        """空输入的异常处理"""
        agent = WriterAgent()
        input_data = AgentInput(content="")

        result = await agent.execute(input_data)

        # 空输入也应该能处理，不崩溃
        assert result is not None

    @pytest.mark.asyncio
    async def test_parse_knowledge_output_invalid_json(self):
        """解析非JSON格式的输入"""
        agent = WriterAgent()
        parsed = agent._parse_knowledge_output("这不是JSON格式的输入")

        assert parsed["task"] == "这不是JSON格式的输入"
        assert parsed["keywords"] == []
        assert parsed["task_type"] == "通用任务"

    @pytest.mark.asyncio
    async def test_fact_question_detection(self):
        """事实问题的检测（V2.2: 通过 FactQuestionHandler.can_handle 检测）"""
        from agents.writer.agent import FactQuestionHandler
        agent = WriterAgent()
        handler = FactQuestionHandler(agent)
        parsed = {
            "original_question": "什么是人工智能",
            "keywords": ["AI", "人工智能"],
            "knowledge_items": ["人工智能是模拟人类智能的技术科学。"],
            "requirements": [],
            "outline": [],
            "summary": "",
            "task_type": "通用任务"
        }

        assert handler.can_handle(parsed) is True

    @pytest.mark.asyncio
    async def test_fact_question_without_knowledge(self):
        """无知识库时的事实问题不应标记为事实问答（V2.2: 通过 FactQuestionHandler.can_handle 检测）"""
        from agents.writer.agent import FactQuestionHandler
        agent = WriterAgent()
        handler = FactQuestionHandler(agent)
        parsed = {
            "original_question": "什么是人工智能",
            "keywords": [],
            "knowledge_items": [],
            "requirements": [],
            "outline": [],
            "summary": "",
            "task_type": "通用任务"
        }

        assert handler.can_handle(parsed) is False