"""Cognitive Controller 测试 — V3 Phase 2 验收标准

测试范围（对应 V3_DEVELOPMENT_GUIDE.md 第 4.4 节验收标准）:
1. chat 任务仅启用 Task + Skill（2个引擎）
2. planning 任务启用全部引擎（6+个引擎）
3. complexity > 0.7 时自动启用 cloud + reasoning
4. confidence < 0.3 时简化流程
5. 简单对话耗时 < 50ms
6. 每次决策附带 reason 说明
"""

import time
from dataclasses import dataclass
from enum import Enum

import pytest

from core.engines.cognitive_controller import CognitiveController, PipelineDecision
from core.skill_engine.task_engine import TaskProfile, TaskType


# ============================================================
# 测试辅助
# ============================================================

def make_profile(task_type: TaskType, complexity: float = 0.0,
                 confidence: float = 0.5, domain: str = "daily") -> TaskProfile:
    """创建测试用 TaskProfile"""
    return TaskProfile(
        task_type=task_type,
        complexity=complexity,
        confidence=confidence,
        domain=domain,
    )


class MockBrain:
    """模拟 PersonalBrain"""

    def __init__(self, learning_stage: str = ""):
        self.learning_stage = learning_stage
        self.profile = type("Profile", (), {"long_term_goals": []})()


@pytest.fixture
def controller():
    return CognitiveController()


# ============================================================
# 1. 验收标准: chat 任务仅启用 Task + Skill
# ============================================================

class TestChatTask:
    """chat 任务引擎调度"""

    def test_chat_enables_only_task_and_skill(self, controller):
        """验收标准 1: chat 任务仅启用 Task + Skill（2个引擎）"""
        profile = make_profile(TaskType.CHAT)
        decision = controller.decide(profile)

        assert decision.task_type == "chat"
        assert "task" in decision.engines
        assert "skill" in decision.engines
        # chat 不应启用 decomposer/planner/cloud/learning
        assert "decomposer" not in decision.engines
        assert "planner" not in decision.engines
        assert "cloud" not in decision.engines
        assert len(decision.engines) == 2

    def test_chat_high_complexity_still_minimal(self, controller):
        """chat 即使高复杂度也不启用 cloud（chat 的 optional 为空）"""
        profile = make_profile(TaskType.CHAT, complexity=0.9)
        decision = controller.decide(profile)

        assert "cloud" not in decision.engines
        assert "reasoning" not in decision.engines


# ============================================================
# 2. 验收标准: planning 任务启用全部引擎
# ============================================================

class TestPlanningTask:
    """planning 任务引擎调度"""

    def test_planning_enables_many_engines(self, controller):
        """验收标准 2: planning 任务启用全部引擎（6+个引擎）"""
        profile = make_profile(TaskType.PLANNING, complexity=0.8)
        decision = controller.decide(profile)

        assert decision.task_type == "planning"
        # planning 的 always_enabled: task, skill, decomposer, planner
        assert "task" in decision.engines
        assert "skill" in decision.engines
        assert "decomposer" in decision.engines
        assert "planner" in decision.engines
        # 高复杂度应启用 cloud + reasoning
        assert "cloud" in decision.engines
        assert "reasoning" in decision.engines
        # 引擎数 >= 6
        assert len(decision.engines) >= 6

    def test_planning_low_complexity_no_cloud(self, controller):
        """planning 低复杂度不启用 cloud"""
        profile = make_profile(TaskType.PLANNING, complexity=0.3)
        decision = controller.decide(profile)

        assert "cloud" not in decision.engines
        assert "task" in decision.engines
        assert "planner" in decision.engines


# ============================================================
# 3. 验收标准: complexity > 0.7 启用 cloud + reasoning
# ============================================================

class TestComplexityDriven:
    """复杂度驱动的引擎启用"""

    def test_high_complexity_enables_cloud_and_reasoning(self, controller):
        """验收标准 3: complexity > 0.7 时自动启用 cloud + reasoning"""
        profile = make_profile(TaskType.ANALYSIS, complexity=0.8)
        decision = controller.decide(profile)

        assert "cloud" in decision.engines
        assert "reasoning" in decision.engines
        assert decision.use_cloud is True
        assert decision.use_reasoning is True

    def test_medium_complexity_no_cloud(self, controller):
        """complexity 0.5-0.7 不启用 cloud"""
        profile = make_profile(TaskType.ANALYSIS, complexity=0.6)
        decision = controller.decide(profile)

        assert "cloud" not in decision.engines
        # 但应该有 decomposer + planner（complexity > 0.5）
        assert "decomposer" in decision.engines
        assert "planner" in decision.engines

    def test_low_complexity_minimal(self, controller):
        """complexity < 0.5 不额外启用"""
        profile = make_profile(TaskType.QA, complexity=0.3)
        decision = controller.decide(profile)

        assert "cloud" not in decision.engines
        assert "planner" not in decision.engines


# ============================================================
# 4. 验收标准: confidence < 0.3 简化流程
# ============================================================

class TestConfidenceDriven:
    """置信度驱动的流程简化"""

    def test_low_confidence_simplifies_pipeline(self, controller):
        """验收标准 4: confidence < 0.3 时简化流程"""
        profile = make_profile(TaskType.PLANNING, complexity=0.8, confidence=0.2)
        decision = controller.decide(profile)

        # 低置信度应移除 decomposer, planner, cloud
        assert "decomposer" not in decision.engines
        assert "planner" not in decision.engines
        assert "cloud" not in decision.engines
        assert "low confidence" in decision.reason

    def test_normal_confidence_keeps_engines(self, controller):
        """正常置信度保留所有引擎"""
        profile = make_profile(TaskType.PLANNING, complexity=0.8, confidence=0.7)
        decision = controller.decide(profile)

        assert "decomposer" in decision.engines
        assert "planner" in decision.engines


# ============================================================
# 5. 验收标准: 简单对话耗时 < 50ms
# ============================================================

class TestLatency:
    """决策延迟测试"""

    def test_chat_decision_under_50ms(self, controller):
        """验收标准 5: 简单对话耗时 < 50ms"""
        profile = make_profile(TaskType.CHAT)

        start = time.perf_counter()
        for _ in range(100):
            controller.decide(profile)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 50, f"平均决策耗时 {avg_ms:.2f}ms > 50ms"

    def test_expected_latency_chat(self, controller):
        """chat 任务预期延迟 < 50ms"""
        profile = make_profile(TaskType.CHAT)
        decision = controller.decide(profile)
        latency = controller.get_expected_latency(decision)
        assert latency == "< 50ms"

    def test_expected_latency_planning(self, controller):
        """planning 任务预期延迟合理"""
        profile = make_profile(TaskType.PLANNING, complexity=0.8)
        decision = controller.decide(profile)
        latency = controller.get_expected_latency(decision)
        # 6+ 引擎应在 < 200ms 或 < 500ms 范围
        assert latency in ("< 100ms", "< 200ms", "< 500ms")


# ============================================================
# 6. 验收标准: 每次决策附带 reason
# ============================================================

class TestDecisionReason:
    """决策理由说明"""

    def test_decision_has_reason(self, controller):
        """验收标准 6: 每次决策附带 reason 说明"""
        profile = make_profile(TaskType.CHAT)
        decision = controller.decide(profile)

        assert decision.reason
        assert isinstance(decision.reason, str)
        assert len(decision.reason) > 0

    def test_reason_contains_task_type(self, controller):
        """reason 包含 task_type 信息"""
        profile = make_profile(TaskType.QA)
        decision = controller.decide(profile)

        assert "task_type=qa" in decision.reason

    def test_reason_contains_complexity_when_high(self, controller):
        """高复杂度时 reason 包含 complexity 信息"""
        profile = make_profile(TaskType.ANALYSIS, complexity=0.8)
        decision = controller.decide(profile)

        assert "complexity=0.80" in decision.reason

    def test_reason_contains_confidence_when_low(self, controller):
        """低置信度时 reason 包含 confidence 信息"""
        profile = make_profile(TaskType.QA, confidence=0.2)
        decision = controller.decide(profile)

        assert "low confidence" in decision.reason


# ============================================================
# 7. 用户画像驱动测试
# ============================================================

class TestBrainDriven:
    """用户画像驱动的引擎启用"""

    def test_intermediate_brain_enables_recommendation(self, controller):
        """intermediate 学习阶段启用 recommendation"""
        profile = make_profile(TaskType.QA, complexity=0.3)
        brain = MockBrain(learning_stage="intermediate")
        decision = controller.decide(profile, brain=brain)

        assert "recommendation" in decision.engines
        assert decision.use_recommendation is True

    def test_advanced_brain_enables_reasoning(self, controller):
        """advanced 学习阶段启用 reasoning"""
        profile = make_profile(TaskType.PLANNING, complexity=0.3)
        brain = MockBrain(learning_stage="advanced")
        decision = controller.decide(profile, brain=brain)

        assert "reasoning" in decision.engines
        assert decision.use_reasoning is True


# ============================================================
# 8. PipelineDecision 数据结构测试
# ============================================================

class TestPipelineDecision:
    """PipelineDecision 数据结构"""

    def test_decision_has_all_fields(self, controller):
        """PipelineDecision 包含所有必要字段"""
        profile = make_profile(TaskType.ANALYSIS, complexity=0.8)
        decision = controller.decide(profile)

        assert hasattr(decision, "task_type")
        assert hasattr(decision, "engines")
        assert hasattr(decision, "use_cloud")
        assert hasattr(decision, "use_learning")
        assert hasattr(decision, "use_recommendation")
        assert hasattr(decision, "use_reasoning")
        assert hasattr(decision, "complexity")
        assert hasattr(decision, "reason")

    def test_learning_triggered_when_in_engines(self, controller):
        """learning 在 engines 中时 use_learning 为 True"""
        profile = make_profile(TaskType.PLANNING, complexity=0.5)
        decision = controller.decide(profile)

        # planning 的 optional 包含 learning, complexity > 0.4 触发
        assert decision.use_learning is True
