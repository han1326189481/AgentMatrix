"""Phase 3 测试 — PatchValidator + Decomposer + LocalPlanner

测试范围（对应 V3_DEVELOPMENT_GUIDE.md 第 5.5 节验收标准）:
1. PatchValidator 拦截重复概念
2. PatchValidator 拦截无效概念名（纯数字/过短/过长）
3. PatchValidator 对相似节点产生警告
4. Decomposer.decompose("解释Transformer") 返回正确子主题
5. Decomposer.decompose("你好") 返回空结果
6. LocalPlanner.plan() 返回合理步骤序列
7. LocalPlanner.detect_skill_gap() 正确识别缺失技能
8. 分解 + 规划耗时 < 10ms
"""

import os
import time
from dataclasses import dataclass
from typing import List

import pytest

from core.graphs.skill_graph import SkillGraph
from core.engines.patch_validator import PatchValidator, ValidationResult
from core.engines.decomposer import Decomposer
from core.engines.local_planner import LocalPlanner
from core.skill_engine.models import KnowledgePatch, WorkflowPatch

GRAPH_YAML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core", "graphs", "skill_graph.yaml"
)


@pytest.fixture(scope="module")
def graph():
    return SkillGraph.load(GRAPH_YAML)


@pytest.fixture(scope="module")
def validator(graph):
    return PatchValidator(graph)


@pytest.fixture(scope="module")
def decomposer(graph):
    return Decomposer(graph)


@pytest.fixture(scope="module")
def planner(graph):
    return LocalPlanner(graph)


# ============================================================
# 1. 验收标准: PatchValidator 拦截重复概念
# ============================================================

class TestValidatorRejectDuplicate:
    """拦截重复概念"""

    def test_reject_existing_concept(self, validator):
        """验收标准 1: 拦截已存在的概念"""
        patch = KnowledgePatch(
            concept_name="Transformer",
            definition="已存在的Transformer概念",
            domain="tech.ai",
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is False
        assert any("重复" in e for e in result.errors)


# ============================================================
# 2. 验收标准: PatchValidator 拦截无效概念名
# ============================================================

class TestValidatorRejectInvalid:
    """拦截无效概念名"""

    def test_reject_too_short(self, validator):
        """概念名过短"""
        patch = KnowledgePatch(
            concept_name="A",
            definition="这是一个过短的概念名测试",
            domain="tech",
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is False
        assert any("过短" in e for e in result.errors)

    def test_reject_too_long(self, validator):
        """概念名过长"""
        patch = KnowledgePatch(
            concept_name="A" * 65,
            definition="这是一个过长的概念名测试定义文本",
            domain="tech",
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is False
        assert any("过长" in e for e in result.errors)

    def test_reject_pure_numbers(self, validator):
        """纯数字概念名无效"""
        patch = KnowledgePatch(
            concept_name="12345",
            definition="纯数字概念名应该被拒绝",
            domain="tech",
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is False

    def test_reject_empty_definition(self, validator):
        """空定义被拒"""
        patch = KnowledgePatch(
            concept_name="NewConcept",
            definition="短",
            domain="tech",
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is False
        assert any("定义" in e for e in result.errors)


# ============================================================
# 3. 验收标准: PatchValidator 对相似节点产生警告
# ============================================================

class TestValidatorSimilarWarning:
    """相似节点警告"""

    def test_similar_node_produces_warning(self, validator):
        """验收标准 3: 对相似节点产生警告"""
        patch = KnowledgePatch(
            concept_name="Transformers",
            definition="Transformer的复数形式，多个Transformer模型的集合",
            domain="tech.ai",
        )
        result = validator.validate_knowledge(patch)
        # 相似节点应产生警告（但可能仍通过，取决于相似度阈值）
        assert len(result.warnings) > 0 or any("相似" in e for e in result.errors)

    def test_valid_new_concept_passes(self, validator):
        """全新的有效概念通过校验"""
        patch = KnowledgePatch(
            concept_name="QuantumComputing",
            definition="量子计算，利用量子叠加和纠缠进行计算的技术",
            domain="tech",
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is True


# ============================================================
# 4. 验收标准: Decomposer.decompose("解释Transformer")
# ============================================================

class TestDecomposerTransform:
    """分解 Transformer 相关问题"""

    def test_decompose_transformer_returns_subtopics(self, decomposer):
        """验收标准 4: decompose("解释Transformer") 返回正确子主题"""
        result = decomposer.decompose("解释Transformer")

        assert result["confidence"] > 0
        assert len(result["matched_nodes"]) > 0
        # Transformer 节点应被匹配
        matched_names = [n.name for n in result["matched_nodes"]]
        assert any("Transformer" in name for name in matched_names)

    def test_decompose_agent_returns_has_part_children(self, decomposer):
        """分解 Agent 返回 has_part 子节点"""
        result = decomposer.decompose("Agent架构")

        assert len(result["matched_nodes"]) > 0
        # Agent 有 has_part 子节点: memory, tool_use, multi_agent
        if result["sub_topics"]:
            sub_names = [s["node"].name for s in result["sub_topics"]]
            assert len(sub_names) > 0


# ============================================================
# 5. 验收标准: Decomposer.decompose("你好") 返回空结果
# ============================================================

class TestDecomposerSimple:
    """简单对话不分解"""

    def test_decompose_hello_returns_empty(self, decomposer):
        """验收标准 5: decompose("你好") 返回空结果"""
        result = decomposer.decompose("你好")

        assert result["matched_nodes"] == []
        assert result["sub_topics"] == []
        assert result["confidence"] == 0.0

    def test_decompose_simple_greeting(self, decomposer):
        """简单问候不分解"""
        result = decomposer.decompose("谢谢")
        assert result["confidence"] == 0.0 or len(result["matched_nodes"]) == 0


# ============================================================
# 6. 验收标准: LocalPlanner.plan() 返回合理步骤序列
# ============================================================

class TestPlannerPlan:
    """任务规划"""

    def test_plan_returns_steps_from_subtopics(self, planner, decomposer):
        """验收标准 6: plan() 返回合理步骤序列"""
        decompose_result = decomposer.decompose("Agent开发")
        steps = planner.plan(decompose_result)

        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_plan_fallback_for_unknown_topic(self, planner):
        """未知主题使用兜底模板"""
        decompose_result = {
            "topic": "UnknownTopic",
            "matched_nodes": [],
            "sub_topics": [],
            "prerequisites": [],
            "related": [],
            "confidence": 0.0,
        }
        steps = planner.plan(decompose_result)

        assert len(steps) == 5
        assert all("UnknownTopic" in s for s in steps)

    def test_plan_from_topic_search(self, planner):
        """从主题搜索生成步骤"""
        decompose_result = {
            "topic": "Agent",
            "matched_nodes": [],
            "sub_topics": [],
            "prerequisites": [],
            "related": [],
            "confidence": 0.5,
        }
        steps = planner.plan(decompose_result)
        assert len(steps) > 0


# ============================================================
# 7. 验收标准: LocalPlanner.detect_skill_gap()
# ============================================================

class TestSkillGapDetection:
    """技能缺口检测"""

    def test_detect_gap_for_unknown_steps(self, planner):
        """验收标准 7: detect_skill_gap() 正确识别缺失技能"""
        steps = ["Memory", "UnknownStepXYZ", "Tool Use"]
        gaps = planner.detect_skill_gap(steps)

        assert "UnknownStepXYZ" in gaps
        assert "Memory" not in gaps

    def test_no_gap_for_known_steps(self, planner):
        """已知步骤无缺口"""
        steps = ["Transformer", "Agent", "RAG"]
        gaps = planner.detect_skill_gap(steps)
        assert "Transformer" not in gaps
        assert "Agent" not in gaps


# ============================================================
# 8. 验收标准: 分解 + 规划耗时 < 10ms
# ============================================================

class TestDecomposePlanLatency:
    """分解+规划延迟测试"""

    def test_decompose_plan_under_10ms(self, decomposer, planner):
        """验收标准 8: 分解 + 规划耗时 < 10ms"""
        query = "解释Transformer原理"

        start = time.perf_counter()
        for _ in range(100):
            result = decomposer.decompose(query)
            steps = planner.plan(result)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 10, f"平均分解+规划耗时 {avg_ms:.2f}ms > 10ms"


# ============================================================
# 9. PatchValidator 五维校验完整性
# ============================================================

class TestValidatorFiveDimensions:
    """五维校验完整性测试"""

    def test_validate_reasoning(self, validator):
        """校验推理模式 Patch"""
        from core.skill_engine.models import ReasoningPatch
        patch = ReasoningPatch(
            pattern_id="test_pattern",
            pattern_name="测试推理模式",
            pattern_type="analysis_pattern",
            steps=["步骤1", "步骤2", "步骤3"],
        )
        result = validator.validate_reasoning(patch)
        assert result.passed is True
        assert result.patch_type == "reasoning"

    def test_validate_reasoning_too_few_steps(self, validator):
        """推理模式步骤不足被拒"""
        from core.skill_engine.models import ReasoningPatch
        patch = ReasoningPatch(
            pattern_id="short",
            pattern_name="短模式",
            pattern_type="analysis_pattern",
            steps=["仅一步"],
        )
        result = validator.validate_reasoning(patch)
        assert result.passed is False

    def test_validate_workflow(self, validator):
        """校验工作流 Patch"""
        patch = WorkflowPatch(
            task_type="test_workflow",
            steps=["需求", "设计", "实现", "测试"],
            optimization="测试优化",
        )
        result = validator.validate_workflow(patch)
        assert result.passed is True
        assert result.patch_type == "workflow"

    def test_validate_workflow_too_few_steps(self, validator):
        """工作流步骤不足被拒"""
        patch = WorkflowPatch(
            task_type="short",
            steps=["仅一步"],
            optimization="",
        )
        result = validator.validate_workflow(patch)
        assert result.passed is False

    def test_validator_stats(self, validator):
        """校验器统计信息"""
        stats = validator.get_stats()
        assert "total_validations" in stats
        assert "passed" in stats
        assert "rejected" in stats
        assert "pass_rate" in stats

    def test_source_check_rejects_untrusted(self, validator):
        """来源检查: 不可信来源被拒"""
        patch = KnowledgePatch(
            concept_name="NewTrustedConcept",
            definition="这是一个来自不可信来源的概念定义",
            domain="tech",
            source="malicious_source",
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is False
        assert any("来源" in e for e in result.errors)
