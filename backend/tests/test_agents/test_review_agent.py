"""Review Agent 测试"""
import pytest
import json
from agents.review.agent import ReviewAgent
from agents.base.agent import AgentInput


class TestReviewAgent:
    @pytest.mark.asyncio
    async def test_review_simple_conversation(self):
        """简单对话 → 难度极低，高分"""
        agent = ReviewAgent()
        review_input = json.dumps({
            "user_task": "你好",
            "summary": "简单问候",
            "writer_output": "你好！有什么可以帮助你的吗？"
        })
        input_data = AgentInput(content=review_input)

        result = await agent.execute(input_data)

        assert result.success is True
        review_data = json.loads(result.content)
        assert review_data["review_score"] >= 0.80
        assert review_data["difficulty_threshold"] < 0.35
        assert review_data["pass"] is True

    @pytest.mark.asyncio
    async def test_review_medium_complexity(self):
        """中等复杂度问题 → 评分/阈值正确计算"""
        agent = ReviewAgent()
        review_input = json.dumps({
            "user_task": "帮我写一个校园活动策划方案",
            "summary": "用户需要校园活动策划方案",
            "writer_output": "# 校园活动策划方案\n\n## 项目背景\n\n校园活动是丰富学生课余生活的重要组成部分。\n\n## 活动目标\n\n提升学生参与度。\n\n## 活动流程\n\n1. 前期准备\n2. 活动执行\n3. 后期总结\n\n## 预算\n\n预计费用5000元。\n\n## 时间安排\n\n2026年3月。"
        })
        input_data = AgentInput(content=review_input)

        result = await agent.execute(input_data)

        assert result.success is True
        review_data = json.loads(result.content)
        assert "review_score" in review_data
        assert "difficulty_threshold" in review_data
        assert "dimensions" in review_data
        dimensions = review_data["dimensions"]
        assert "accuracy" in dimensions
        assert "professional" in dimensions
        assert "completeness" in dimensions
        assert "reasoning" in dimensions
        assert "structure" in dimensions
        assert "actionable" in dimensions

    @pytest.mark.asyncio
    async def test_review_high_difficulty(self):
        """高难度问题 → 高难度标识及 JSON 输出正确

        2026-10-04: 补上 skill_path。
        V2.4 起难度 = 领域基础难度 + 任务信号加成，base 完全由 domain 决定：
          - skill_path=["root","tech","ai","agent"] → base 0.60 → 高难度
          - 缺省 skill_path=["root","daily"]        → base 0.15 → 中等难度
        旧版用例喂入的是高难度任务却未给领域，落到 daily 域算出 0.43（medium），
        与用例意图不符；production 里 skill_path 由 Knowledge/Writer 链路提供，
        因此这里按生产形态补上，才是对该用例的真实检验。
        """
        agent = ReviewAgent()
        review_input = json.dumps({
            "user_task": "设计一个多智能体协同的端云协同系统架构方案，包含技术选型和风险评估",
            "summary": "复杂系统架构设计任务",
            "skill_path": ["root", "tech", "ai", "agent"],
            "writer_output": "# 系统架构设计方案\n\n## 背景\n\n多智能体系统需要端云协同架构来优化资源分配。\n\n## 技术选型\n\n基于 Kubernetes 和 Docker 进行容器化部署。\n\n## 风险评估\n\n主要风险包括网络延迟、数据一致性等问题。\n\n## 实施步骤\n\n1. 需求分析\n2. 架构设计\n3. 原型开发\n4. 测试验证"
        })
        input_data = AgentInput(content=review_input)

        result = await agent.execute(input_data)

        assert result.success is True
        review_data = json.loads(result.content)
        assert review_data["difficulty_threshold"] >= 0.5
        assert result.metadata["skill_domain"] == "agent"
        assert "issues" in review_data
        assert "suggestions" in review_data

    @pytest.mark.asyncio
    async def test_review_difficulty_falls_back_to_daily_without_skill_path(self):
        """未提供 skill_path 时难度退化为 daily 域基线（V2.4 领域解耦的直接后果）

        锁定这条现状，避免「缺领域 → 复杂任务被误判为简单」这一隐性行为被无声改变：
        一旦 Judge 双门槛依赖难度，缺失领域信息就必须是显式可观测的。
        """
        agent = ReviewAgent()
        review_input = json.dumps({
            "user_task": "设计一个多智能体协同的端云协同系统架构方案",
            "summary": "复杂系统架构设计任务",
            "writer_output": "# 方案\n\n## 背景\n\n略。\n\n## 实施步骤\n\n1. 需求分析\n2. 架构设计"
        })
        input_data = AgentInput(content=review_input)

        result = await agent.execute(input_data)

        assert result.success is True
        review_data = json.loads(result.content)
        # daily 基线下即便命中多个复杂度关键词也上不去 0.5 → 判定为 medium
        assert review_data["difficulty_threshold"] < 0.5
        assert result.metadata["skill_domain"] == "daily"

    @pytest.mark.asyncio
    async def test_review_invalid_json_fallback(self):
        """LLM 返回非法 JSON 时的降级 - 直接输入非JSON文本"""
        agent = ReviewAgent()
        # 直接传入非JSON内容，测试降级逻辑
        input_data = AgentInput(content="这不是JSON")

        result = await agent.execute(input_data)

        # 应正常降级，不崩溃
        assert result.success is True
        review_data = json.loads(result.content)
        assert "review_score" in review_data
        assert "difficulty_threshold" in review_data

    @pytest.mark.asyncio
    async def test_dimensions_in_range(self):
        """验证所有维度分数在 0-1 范围内"""
        agent = ReviewAgent()
        review_input = json.dumps({
            "user_task": "生成校园AI助手方案",
            "summary": "校园AI助手方案需求",
            "writer_output": "# 校园AI助手方案\n\n## 背景\n\n随着AI技术发展，校园场景需要智能化解决方案。\n\n## 方案设计\n\n基于大语言模型构建校园AI助手。\n\n## 预算\n\n预计10万元。"
        })
        input_data = AgentInput(content=review_input)

        result = await agent.execute(input_data)

        assert result.success is True
        review_data = json.loads(result.content)
        dims = review_data["dimensions"]
        for key, dim_data in dims.items():
            if isinstance(dim_data, dict):
                score = dim_data.get("score", 0.5)
                assert 0.0 <= score <= 1.0, f"{key} score = {score} 超出范围"
            else:
                assert 0.0 <= dim_data <= 1.0, f"{key} = {dim_data} 超出范围"

    @pytest.mark.asyncio
    async def test_metadata_consistency(self):
        """验证 metadata 与 content 一致"""
        agent = ReviewAgent()
        review_input = json.dumps({
            "user_task": "测试任务",
            "summary": "测试摘要",
            "writer_output": "测试输出内容"
        })
        input_data = AgentInput(content=review_input)

        result = await agent.execute(input_data)

        assert result.success is True
        review_data = json.loads(result.content)
        assert result.metadata["review_score"] == review_data["review_score"]
        assert result.metadata["difficulty_threshold"] == review_data["difficulty_threshold"]