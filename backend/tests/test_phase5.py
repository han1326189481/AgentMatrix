"""Phase 5: Reasoning Graph 测试

覆盖范围:
- 5种预置推理模式加载
- match() 函数: task_type + domain + keywords 匹配
- extract_from_text(): 从 Markdown 输出提取模式
- build_prompt(): 推理模式 Prompt 构建
- 性能: 匹配耗时 < 5ms
- Cognitive Controller: reasoning 引擎调度
- Writer Agent: 推理模式注入
"""

import pytest
import time
import sys
import os

# 确保路径正确
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.graphs.reasoning_graph import ReasoningGraph, ReasoningNode


# ============================================================
# Test 1: 预置模式加载
# ============================================================

class TestPresetPatterns:
    """5种预置推理模式正确加载"""

    def test_all_patterns_loaded(self):
        graph = ReasoningGraph()
        assert len(graph.patterns) == 5

    def test_comparison_analysis_exists(self):
        graph = ReasoningGraph()
        pattern = graph.patterns["comparison_analysis"]
        assert pattern.pattern_name == "对比分析模式"
        assert pattern.pattern_type == "analysis_pattern"
        assert len(pattern.steps) == 5
        assert "tech" in pattern.applicable_domains
        assert "analysis" in pattern.applicable_task_types

    def test_problem_solution_exists(self):
        graph = ReasoningGraph()
        pattern = graph.patterns["problem_solution"]
        assert pattern.pattern_name == "问题解决模式"
        assert pattern.pattern_type == "analysis_pattern"
        assert len(pattern.steps) == 5
        assert "tech" in pattern.applicable_domains
        assert "coding" in pattern.applicable_task_types

    def test_concept_explanation_exists(self):
        graph = ReasoningGraph()
        pattern = graph.patterns["concept_explanation"]
        assert pattern.pattern_name == "概念解释模式"
        assert pattern.pattern_type == "explanation_pattern"
        assert len(pattern.steps) == 5
        assert "qa" in pattern.applicable_task_types

    def test_argumentative_writing_exists(self):
        graph = ReasoningGraph()
        pattern = graph.patterns["argumentative_writing"]
        assert pattern.pattern_name == "论证写作模式"
        assert pattern.pattern_type == "writing_pattern"
        assert len(pattern.steps) == 5
        assert "writing" in pattern.applicable_task_types

    def test_code_design_implement_exists(self):
        graph = ReasoningGraph()
        pattern = graph.patterns["code_design_implement"]
        assert pattern.pattern_name == "编码设计实现模式"
        assert pattern.pattern_type == "coding_pattern"
        assert len(pattern.steps) == 5
        assert "coding" in pattern.applicable_task_types

    def test_pattern_types_distinct(self):
        """验证模式类型覆盖"""
        graph = ReasoningGraph()
        types = {p.pattern_type for p in graph.patterns.values()}
        assert "analysis_pattern" in types
        assert "writing_pattern" in types
        assert "coding_pattern" in types
        assert "explanation_pattern" in types


# ============================================================
# Test 2: match() 函数
# ============================================================

class TestMatch:
    """推理模式匹配"""

    def test_match_analysis_tech(self):
        """match(task_type="analysis", domain="tech") → 对比分析模式"""
        graph = ReasoningGraph()
        pattern = graph.match(task_type="analysis", domain="tech")
        assert pattern is not None
        assert pattern.pattern_id == "comparison_analysis"

    def test_match_coding(self):
        """match(task_type="coding") → 编码设计实现模式"""
        graph = ReasoningGraph()
        pattern = graph.match(task_type="coding")
        assert pattern is not None
        assert pattern.pattern_id == "code_design_implement"

    def test_match_writing(self):
        """match(task_type="writing") → 论证写作模式"""
        graph = ReasoningGraph()
        pattern = graph.match(task_type="writing")
        assert pattern is not None
        assert pattern.pattern_id == "argumentative_writing"

    def test_match_qa(self):
        """match(task_type="qa") → 概念解释模式"""
        graph = ReasoningGraph()
        pattern = graph.match(task_type="qa")
        assert pattern is not None
        assert pattern.pattern_id == "concept_explanation"

    def test_match_planning(self):
        """match(task_type="planning") → 对比分析模式（planning 也适用）"""
        graph = ReasoningGraph()
        pattern = graph.match(task_type="planning")
        assert pattern is not None
        assert pattern.pattern_id == "comparison_analysis"

    def test_match_no_match(self):
        """match(task_type="chat") → None（chat 无匹配模式）"""
        graph = ReasoningGraph()
        pattern = graph.match(task_type="chat")
        assert pattern is None

    def test_match_with_domain_boosts_score(self):
        """domain 匹配时加分，同分时优先更专业化的模式"""
        graph = ReasoningGraph()
        # coding + tech: problem_solution=8, code_design_implement=8
        # 同分时 code_design_implement 更专业化（1个task_type vs 2个）
        pattern = graph.match(task_type="coding", domain="tech")
        assert pattern is not None
        assert pattern.pattern_id == "code_design_implement"

    def test_match_with_keywords(self):
        """关键词匹配时加分"""
        graph = ReasoningGraph()
        pattern = graph.match(task_type="analysis", keywords=["对比"])
        assert pattern is not None
        assert pattern.pattern_id == "comparison_analysis"

    def test_match_usage_count_incremented(self):
        """匹配后 usage_count 递增"""
        graph = ReasoningGraph()
        pattern = graph.match(task_type="analysis")
        assert pattern.usage_count == 1
        graph.match(task_type="analysis")
        assert pattern.usage_count == 2


# ============================================================
# Test 3: extract_from_text()
# ============================================================

class TestExtractFromText:
    """从 Markdown 输出中提取推理模式"""

    def test_extract_background_analysis(self):
        """提取 '背景→分析→举例→总结' 模式"""
        text = """## 背景
这是背景介绍。

## 分析
这是分析内容。

## 举例
这是一个例子。

## 总结
这是总结。"""
        graph = ReasoningGraph()
        pattern = graph.extract_from_text(text)
        assert pattern is not None
        assert pattern.pattern_id == "background_analysis_example_summary"
        assert len(pattern.steps) >= 3

    def test_extract_problem_solution(self):
        """提取 '问题→原因→方案→验证' 模式"""
        text = """## 问题
问题描述。

## 原因
原因分析。

## 方案
解决方案。

## 验证
验证方法。"""
        graph = ReasoningGraph()
        pattern = graph.extract_from_text(text)
        assert pattern is not None
        assert pattern.pattern_id == "problem_cause_solution_verify"

    def test_extract_definition_principle(self):
        """提取 '定义→原理→应用→对比' 模式"""
        text = """## 定义
概念定义。

## 原理
核心原理。

## 应用
应用场景。

## 对比
对比分析。"""
        graph = ReasoningGraph()
        pattern = graph.extract_from_text(text)
        assert pattern is not None
        assert pattern.pattern_id == "definition_principle_application_compare"

    def test_extract_swot(self):
        """提取 SWOT 分析模式"""
        text = """## 优势
优势分析。

## 劣势
劣势分析。

## 机会
机会分析。

## 威胁
威胁分析。"""
        graph = ReasoningGraph()
        pattern = graph.extract_from_text(text)
        assert pattern is not None
        assert pattern.pattern_id == "swot_analysis"

    def test_extract_too_few_headers(self):
        """标题少于3个 → 返回 None"""
        text = """## 标题1
内容1

## 标题2
内容2"""
        graph = ReasoningGraph()
        pattern = graph.extract_from_text(text)
        assert pattern is None

    def test_extract_no_match(self):
        """无匹配模式 → 返回 None"""
        text = """## 天气
今天天气很好。

## 心情
心情不错。

## 计划
今天要出去。"""
        graph = ReasoningGraph()
        pattern = graph.extract_from_text(text)
        assert pattern is None

    def test_extract_empty_text(self):
        """空文本 → 返回 None"""
        graph = ReasoningGraph()
        pattern = graph.extract_from_text("")
        assert pattern is None

    def test_extract_partial_match(self):
        """部分匹配但不够3个 → 返回 None"""
        text = """## 背景
一些背景。

## 问题
一个问题。

## 其他
其他内容。"""
        graph = ReasoningGraph()
        pattern = graph.extract_from_text(text)
        # 背景和问题分属不同模式，各自只有2个匹配
        assert pattern is None


# ============================================================
# Test 4: build_prompt()
# ============================================================

class TestBuildPrompt:
    """推理模式 Prompt 构建"""

    def test_build_prompt_contains_steps(self):
        pattern = ReasoningGraph().match(task_type="analysis")
        prompt = pattern.build_prompt("测试问题")
        assert "1. 背景与问题" in prompt
        assert "2. 对比维度定义" in prompt
        assert "测试问题" in prompt

    def test_build_prompt_contains_instruction(self):
        pattern = ReasoningGraph().match(task_type="coding")
        prompt = pattern.build_prompt("写一个排序算法")
        assert "推理结构" in prompt
        assert "写一个排序算法" in prompt
        assert "需求分析" in prompt

    def test_build_prompt_all_steps_numbered(self):
        pattern = ReasoningGraph().match(task_type="writing")
        prompt = pattern.build_prompt("论证AI的重要性")
        for i in range(1, 6):
            assert f"{i}." in prompt

    def test_build_prompt_has_quality_requirement(self):
        pattern = ReasoningGraph().match(task_type="qa")
        prompt = pattern.build_prompt("什么是Transformer")
        assert "实质性内容" in prompt


# ============================================================
# Test 5: ReasoningNode 数据模型
# ============================================================

class TestReasoningNode:
    """ReasoningNode 数据模型"""

    def test_create_node(self):
        node = ReasoningNode(
            pattern_id="test_pattern",
            pattern_name="测试模式",
            pattern_type="analysis_pattern",
            steps=["步骤1", "步骤2", "步骤3"],
            applicable_domains=["tech"],
            applicable_task_types=["analysis"],
            template="## 模板"
        )
        assert node.pattern_id == "test_pattern"
        assert node.pattern_name == "测试模式"
        assert len(node.steps) == 3
        assert node.usage_count == 0
        assert node.avg_effectiveness == 0.0

    def test_build_prompt_single_step(self):
        node = ReasoningNode(
            pattern_id="single",
            pattern_name="单步模式",
            pattern_type="analysis_pattern",
            steps=["唯一步骤"]
        )
        prompt = node.build_prompt("测试")
        assert "1. 唯一步骤" in prompt


# ============================================================
# Test 6: register() + stats()
# ============================================================

class TestRegisterAndStats:
    """注册新模式 + 统计"""

    def test_register_new_pattern(self):
        graph = ReasoningGraph()
        new_pattern = ReasoningNode(
            pattern_id="custom_pattern",
            pattern_name="自定义模式",
            pattern_type="decision_pattern",
            steps=["评估", "权衡", "选择", "验证"],
            applicable_domains=["business"],
            applicable_task_types=["planning"]
        )
        graph.register(new_pattern)
        assert len(graph.patterns) == 6
        assert "custom_pattern" in graph.patterns

    def test_stats_returns_correct_counts(self):
        graph = ReasoningGraph()
        stats = graph.stats()
        assert stats["total_patterns"] == 5
        assert "by_type" in stats
        assert "most_used" in stats
        assert len(stats["most_used"]) <= 3

    def test_stats_after_match(self):
        graph = ReasoningGraph()
        graph.match(task_type="analysis")
        graph.match(task_type="analysis")
        graph.match(task_type="coding")
        stats = graph.stats()
        most_used = stats["most_used"]
        assert len(most_used) > 0
        # 对比分析模式应该被使用最多
        assert most_used[0]["usage_count"] == 2

    def test_get_all_patterns(self):
        graph = ReasoningGraph()
        patterns = graph.get_all_patterns()
        assert len(patterns) == 5
        pattern_ids = {p.pattern_id for p in patterns}
        assert "comparison_analysis" in pattern_ids
        assert "problem_solution" in pattern_ids
        assert "concept_explanation" in pattern_ids
        assert "argumentative_writing" in pattern_ids
        assert "code_design_implement" in pattern_ids


# ============================================================
# Test 7: 性能测试
# ============================================================

class TestPerformance:
    """推理模式匹配耗时 < 5ms"""

    def test_match_performance(self):
        graph = ReasoningGraph()
        # 预热
        graph.match(task_type="analysis", domain="tech")

        start = time.perf_counter()
        for _ in range(100):
            graph.match(task_type="analysis", domain="tech")
        elapsed = (time.perf_counter() - start) / 100 * 1000  # ms

        assert elapsed < 5.0, f"匹配耗时 {elapsed:.2f}ms > 5ms"

    def test_extract_performance(self):
        graph = ReasoningGraph()
        text = """## 背景
背景。

## 分析
分析。

## 举例
举例。

## 总结
总结。"""

        start = time.perf_counter()
        for _ in range(100):
            graph.extract_from_text(text)
        elapsed = (time.perf_counter() - start) / 100 * 1000

        assert elapsed < 5.0, f"提取耗时 {elapsed:.2f}ms > 5ms"

    def test_no_match_is_fast(self):
        """无匹配也应该很快"""
        graph = ReasoningGraph()
        start = time.perf_counter()
        for _ in range(100):
            graph.match(task_type="chat")
        elapsed = (time.perf_counter() - start) / 100 * 1000

        assert elapsed < 5.0, f"无匹配耗时 {elapsed:.2f}ms > 5ms"


# ============================================================
# Test 8: Cognitive Controller reasoning 引擎调度
# ============================================================

class TestCognitiveControllerReasoning:
    """Cognitive Controller 中 reasoning 引擎调度"""

    def test_controller_writing_no_reasoning(self):
        """writing 任务类型在 optional 中不包含 reasoning（开发指南 658-668 行）"""
        from core.engines.cognitive_controller import CognitiveController
        controller = CognitiveController()
        always, optional = controller.engine_policies["writing"]
        assert "reasoning" not in optional

    def test_controller_qa_no_reasoning(self):
        """qa 任务类型在 optional 中不包含 reasoning（开发指南 658-668 行）"""
        from core.engines.cognitive_controller import CognitiveController
        controller = CognitiveController()
        always, optional = controller.engine_policies["qa"]
        assert "reasoning" not in optional

    def test_controller_analysis_has_reasoning(self):
        """analysis 任务类型在 optional 中包含 reasoning"""
        from core.engines.cognitive_controller import CognitiveController
        controller = CognitiveController()
        always, optional = controller.engine_policies["analysis"]
        assert "reasoning" in optional

    def test_controller_planning_has_reasoning(self):
        """planning 任务类型在 optional 中包含 reasoning"""
        from core.engines.cognitive_controller import CognitiveController
        controller = CognitiveController()
        always, optional = controller.engine_policies["planning"]
        assert "reasoning" in optional

    def test_controller_chat_no_reasoning(self):
        """chat 任务类型不在 optional 中包含 reasoning"""
        from core.engines.cognitive_controller import CognitiveController
        controller = CognitiveController()
        always, optional = controller.engine_policies["chat"]
        assert "reasoning" not in optional

    def test_controller_coding_no_reasoning(self):
        """coding 任务类型不在 optional 中包含 reasoning"""
        from core.engines.cognitive_controller import CognitiveController
        controller = CognitiveController()
        always, optional = controller.engine_policies["coding"]
        assert "reasoning" not in optional

    def test_decision_use_reasoning_field(self):
        """PipelineDecision 包含 use_reasoning 字段"""
        from core.engines.cognitive_controller import PipelineDecision
        decision = PipelineDecision(
            task_type="writing",
            engines=["task", "skill", "reasoning"],
            use_reasoning=True,
            reason="test"
        )
        assert decision.use_reasoning is True

    def test_decision_use_reasoning_default_false(self):
        """PipelineDecision 默认 use_reasoning=False"""
        from core.engines.cognitive_controller import PipelineDecision
        decision = PipelineDecision(
            task_type="writing",
            engines=["task", "skill"],
            reason="test"
        )
        assert decision.use_reasoning is False


# ============================================================
# Test 9: Phase 5 集成测试
# ============================================================

class TestPhase5Integration:
    """Phase 5 集成测试"""

    def test_imports(self):
        """验证所有组件可导入"""
        from core.graphs.reasoning_graph import ReasoningGraph, ReasoningNode
        from core.engines.cognitive_controller import CognitiveController, PipelineDecision
        assert True

    def test_full_pipeline_match_to_prompt(self):
        """完整流程: 匹配 → 构建 Prompt"""
        graph = ReasoningGraph()

        # 匹配
        pattern = graph.match(task_type="analysis", domain="tech")
        assert pattern is not None
        assert pattern.pattern_id == "comparison_analysis"

        # 构建 Prompt
        prompt = pattern.build_prompt("比较Python和Java")
        assert "Python和Java" in prompt
        assert "对比维度定义" in prompt
        assert "选择建议" in prompt

    def test_extract_then_register(self):
        """从文本提取模式后注册"""
        graph = ReasoningGraph()
        text = """## 背景
bg

## 分析
analysis

## 举例
example

## 总结
summary"""
        extracted = graph.extract_from_text(text)
        assert extracted is not None

        # 注册新模式
        graph.register(extracted)
        assert len(graph.patterns) == 6
        assert "background_analysis_example_summary" in graph.patterns

    def test_stats_consistency(self):
        """stats 输出一致性"""
        graph = ReasoningGraph()
        stats = graph.stats()
        assert stats["total_patterns"] == 5
        assert sum(stats["by_type"].values()) == 5
        assert len(stats["most_used"]) <= 3