"""Judge Agent 测试 - V2.1：基于多维 ReviewReport 的路由决策"""
import pytest
import json
from agents.judge.agent import JudgeAgent
from agents.base.agent import AgentInput


def _make_v2_review(dim_scores, weighted_score, difficulty, risk="low", issues=None, suggestions=None):
    """构建 V2 格式的 ReviewReport（6维度）"""
    dims = {}
    for key, score in dim_scores.items():
        dims[key] = {"score": score, "weight": 0.15, "issues": [], "suggestion": ""}
    return {
        "dimensions": dims,
        "overall": {"weighted_score": weighted_score, "pass": weighted_score >= 0.65},
        "risk": {"level": risk, "factors": [], "mitigation": ""},
        "confidence": 0.85,
        "difficulty": {"threshold": difficulty, "level": "medium", "reason": ""},
        "review_score": weighted_score,
        "difficulty_threshold": difficulty,
        "issues": issues or [],
        "suggestions": suggestions or [],
        "pass": weighted_score >= 0.65,
    }


class TestJudgeAgent:
    @pytest.mark.asyncio
    async def test_judge_simple_task(self):
        """测试简单任务：低难度阈值 → 本地输出"""
        agent = JudgeAgent()
        await agent.initialize()

        review_result = _make_v2_review(
            dim_scores={"accuracy": 0.85, "professional": 0.85, "completeness": 0.85,
                        "reasoning": 0.85, "structure": 0.85, "actionable": 0.85},
            weighted_score=0.85, difficulty=0.15,
            suggestions=["简单对话"]
        )

        judge_input = json.dumps({
            "user_task": "你好",
            "review_result": review_result,
            "writer_output": "你好！有什么可以帮助你的吗？"
        })

        output = await agent.execute(AgentInput(content=judge_input))
        result = json.loads(output.content)

        assert result["decision"] == "local_output"
        assert result["difficulty_threshold"] == 0.15
        assert result["cloud_mode"] == "none"

    @pytest.mark.asyncio
    async def test_judge_medium_task_low_quality(self):
        """测试中等难度任务：质量不足 → 云端润色"""
        agent = JudgeAgent()
        await agent.initialize()

        review_result = _make_v2_review(
            dim_scores={"accuracy": 0.50, "professional": 0.55, "completeness": 0.50,
                        "reasoning": 0.60, "structure": 0.50, "actionable": 0.60},
            weighted_score=0.55, difficulty=0.55,
            issues=["内容过短"], suggestions=["增加内容"]
        )

        judge_input = json.dumps({
            "user_task": "写一个活动方案",
            "review_result": review_result,
            "writer_output": "举办活动。"
        })

        output = await agent.execute(AgentInput(content=judge_input))
        result = json.loads(output.content)

        assert result["difficulty_threshold"] == 0.55
        assert result["review_score"] == 0.55
        assert result["decision"] in ("local_output", "cloud_enhance")

    @pytest.mark.asyncio
    async def test_judge_high_difficulty(self):
        """测试高难度任务：difficulty_threshold >= 0.80 → 云端重写"""
        agent = JudgeAgent()
        await agent.initialize()

        review_result = _make_v2_review(
            dim_scores={"accuracy": 0.40, "professional": 0.40, "completeness": 0.40,
                        "reasoning": 0.40, "structure": 0.35, "actionable": 0.40},
            weighted_score=0.40, difficulty=0.85,
            issues=["内容严重不足"], suggestions=["需要云端重写"]
        )

        judge_input = json.dumps({
            "user_task": "设计一个完整的AI系统架构方案",
            "review_result": review_result,
            "writer_output": "AI系统..."
        })

        output = await agent.execute(AgentInput(content=judge_input))
        result = json.loads(output.content)

        assert result["difficulty_threshold"] == 0.85
        assert result["decision"] in ("local_output", "cloud_enhance")

    @pytest.mark.asyncio
    async def test_judge_complex_high_quality(self):
        """测试高难度但高质量任务：difficulty 0.65-0.80, review >= 0.80 → 本地"""
        agent = JudgeAgent()
        await agent.initialize()

        review_result = _make_v2_review(
            dim_scores={"accuracy": 0.88, "professional": 0.87, "completeness": 0.85,
                        "reasoning": 0.85, "structure": 0.88, "actionable": 0.83},
            weighted_score=0.85, difficulty=0.70,
            suggestions=["内容质量良好"]
        )

        judge_input = json.dumps({
            "user_task": "生成完整的系统设计方案",
            "review_result": review_result,
            "writer_output": "## 系统设计方案\n\n### 一、需求分析\n本系统需要满足以下核心需求：高并发处理能力、数据一致性保障、模块化架构设计。系统需要支持日均百万级用户访问。\n\n### 二、架构设计\n采用微服务架构，将系统拆分为用户服务、订单服务、支付服务等独立模块。\n\n### 三、技术选型\n后端使用Spring Cloud，前端使用React，数据库采用MySQL+MongoDB混合方案。"
        })

        output = await agent.execute(AgentInput(content=judge_input))
        result = json.loads(output.content)

        assert result["decision"] == "local_output"
        assert result["review_score"] == 0.85