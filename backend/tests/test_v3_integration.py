"""V3 全链路集成测试

测试 V3 架构组件链路:
  User Input → TaskClassifier → CognitiveController.decide()
    → Decomposer.decompose() → LocalPlanner.plan()
    → ReasoningGraph.match() → Writer Agent
    → Review → Judge → Result
    → LearningEngine.learn() → PatchValidator → SkillGraph

约束:
- 所有测试不依赖 LLM (Ollama / DeepSeek)，只测试 Graph 和 Engine 的逻辑
- 需要确定图结构的测试使用本地构建的 SkillGraph (隔离全局单例污染)
- 不需要特定图内容的测试使用 get_skill_graph() 单例
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest

from core.graphs import get_skill_graph
from core.graphs.skill_graph import SkillGraph, GraphNode, GraphEdge
from core.graphs.reasoning_graph import ReasoningGraph
from core.engines import (
    CognitiveController,
    Decomposer,
    LocalPlanner,
    LearningEngine,
    PatchValidator,
)
from core.skill_engine.task_engine import TaskClassifier, TaskType
from core.skill_engine.models import KnowledgePatch


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def controller():
    return CognitiveController()


@pytest.fixture
def classifier():
    return TaskClassifier()


@pytest.fixture
def reasoning_graph():
    """每个测试独立的 ReasoningGraph (避免 usage_count 互相污染)"""
    return ReasoningGraph()


@pytest.fixture
def seeded_graph():
    """构建带种子节点的 SkillGraph (技术/AI 领域)，用于 Decomposer / Planner 测试"""
    g = SkillGraph()
    nodes = [
        ("agent", "Agent", "concept", "tech.ai", "自主智能实体"),
        ("memory", "Memory", "concept", "tech.ai", "Agent 记忆模块"),
        ("multi_agent", "Multi-Agent", "concept", "tech.ai", "多智能体协作"),
        ("tool_use", "Tool Use", "concept", "tech.ai", "工具调用能力"),
    ]
    for nid, name, ntype, domain, desc in nodes:
        g.add_node(GraphNode(id=nid, name=name, node_type=ntype,
                             domain=domain, description=desc))
    # has_part: agent 由 memory / multi_agent / tool_use 组成
    g.add_edge(GraphEdge(from_node="agent", to_node="memory", edge_type="has_part"))
    g.add_edge(GraphEdge(from_node="agent", to_node="multi_agent", edge_type="has_part"))
    g.add_edge(GraphEdge(from_node="agent", to_node="tool_use", edge_type="has_part"))
    # prerequisite: 学习 agent 前需要 memory
    g.add_edge(GraphEdge(from_node="memory", to_node="agent", edge_type="prerequisite"))
    # related_to
    g.add_edge(GraphEdge(from_node="multi_agent", to_node="agent", edge_type="related_to"))
    return g


@pytest.fixture
def learning_graph():
    """用于 LearningEngine 测试的小图 (含一个多词节点便于词重叠匹配)"""
    g = SkillGraph()
    g.add_node(GraphNode(id="agent_tool", name="Agent Tool", node_type="concept",
                         domain="tech.ai", description="Agent 工具调用能力"))
    return g


# ============================================================
# 1. TestControllerDispatch — 认知调度器决策
# ============================================================

class TestControllerDispatch:
    """CognitiveController.decide() 调度决策"""

    @pytest.mark.asyncio
    async def test_chat_task_minimal_pipeline(self, controller, classifier):
        """chat 任务只启用 task + skill，不启动 decomposer/planner"""
        profile = classifier.classify("你好")
        assert profile.task_type == TaskType.CHAT

        decision = controller.decide(profile)

        assert decision.task_type == "chat"
        assert "task" in decision.engines
        assert "skill" in decision.engines
        assert "decomposer" not in decision.engines
        assert "planner" not in decision.engines
        assert decision.use_cloud is False
        # chat 策略只启用 2 个引擎 → 预期延迟 < 50ms
        assert controller.get_expected_latency(decision) == "< 50ms"

    @pytest.mark.asyncio
    async def test_analysis_task_full_pipeline(self, controller, classifier):
        """analysis 任务启用 decomposer + planner (always 策略)"""
        profile = classifier.classify("分析一下优缺点")
        assert profile.task_type == TaskType.ANALYSIS

        decision = controller.decide(profile)

        assert decision.task_type == "analysis"
        assert "task" in decision.engines
        assert "skill" in decision.engines
        assert "decomposer" in decision.engines
        assert "planner" in decision.engines

    @pytest.mark.asyncio
    async def test_high_complexity_enables_cloud(self, controller, classifier):
        """complexity > 0.7 启用 cloud + reasoning (analysis 的 optional 含 cloud)"""
        profile = classifier.classify("分析一下优缺点")
        assert profile.task_type == TaskType.ANALYSIS
        # TaskProfile 是可变 dataclass，设置 complexity 属性
        profile.complexity = 0.8

        decision = controller.decide(profile)

        assert decision.complexity == 0.8
        assert "cloud" in decision.engines
        assert "reasoning" in decision.engines
        assert decision.use_cloud is True
        assert decision.use_reasoning is True

    @pytest.mark.asyncio
    async def test_low_confidence_simplifies(self, controller, classifier):
        """confidence < 0.3 简化流程 (移除 decomposer/planner/cloud)"""
        profile = classifier.classify("帮我制定一个学习计划")
        assert profile.task_type == TaskType.PLANNING
        # planning 默认启用 decomposer + planner，低置信度应移除
        profile.confidence = 0.2

        decision = controller.decide(profile)

        assert "decomposer" not in decision.engines
        assert "planner" not in decision.engines
        assert decision.use_cloud is False
        assert "low confidence" in decision.reason.lower()


# ============================================================
# 2. TestDecomposerPlannerChain — 分解器 + 规划器链路
# ============================================================

class TestDecomposerPlannerChain:
    """Decomposer.decompose() → LocalPlanner.plan() 链路"""

    @pytest.mark.asyncio
    async def test_decompose_tech_question(self, seeded_graph):
        """分解技术问题返回 matched_nodes + sub_topics"""
        decomposer = Decomposer(seeded_graph)

        result = decomposer.decompose("Agent 架构设计")

        assert result["matched_nodes"], "应匹配到 Agent 节点"
        assert result["matched_nodes"][0].name == "Agent"
        # agent 有 3 个 has_part 子节点
        assert len(result["sub_topics"]) == 3
        # agent 的前置知识为 memory
        assert any(n.name == "Memory" for n in result["prerequisites"])
        assert result["confidence"] > 0.0

    @pytest.mark.asyncio
    async def test_decompose_simple_greeting(self, seeded_graph):
        """简单问候在图中无匹配，返回空结果"""
        decomposer = Decomposer(seeded_graph)

        result = decomposer.decompose("你好")

        assert result["matched_nodes"] == []
        assert result["sub_topics"] == []
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_plan_from_decompose_result(self, seeded_graph):
        """从分解结果生成步骤 (sub_topics → steps)"""
        decomposer = Decomposer(seeded_graph)
        planner = LocalPlanner(seeded_graph)

        decompose_result = decomposer.decompose("Agent 架构设计")
        steps = planner.plan(decompose_result)

        assert steps, "应从 sub_topics 生成步骤"
        # sub_topics 的节点名应出现在 steps 中
        sub_topic_names = {s["node"].name for s in decompose_result["sub_topics"]}
        assert sub_topic_names.issubset(set(steps))
        assert "Memory" in steps

    @pytest.mark.asyncio
    async def test_detect_skill_gap(self, seeded_graph):
        """检测 Skill Gap：图中不存在的步骤被识别"""
        planner = LocalPlanner(seeded_graph)

        # Memory 在图中，UnknownConcept 不在
        gaps = planner.detect_skill_gap(["Memory", "UnknownConcept"])

        assert "UnknownConcept" in gaps
        assert "Memory" not in gaps


# ============================================================
# 3. TestReasoningInjection — 推理模式注入
# ============================================================

class TestReasoningInjection:
    """ReasoningGraph.match() 推理模式匹配"""

    @pytest.mark.asyncio
    async def test_match_analysis_returns_pattern(self, reasoning_graph):
        """analysis + tech 匹配到 analysis_pattern 推理模式"""
        pattern = reasoning_graph.match(task_type="analysis", domain="tech")

        assert pattern is not None
        assert pattern.pattern_type == "analysis_pattern"
        assert len(pattern.steps) >= 3
        # analysis + tech 应命中对比分析或问题解决模式
        assert pattern.pattern_id in ("comparison_analysis", "problem_solution")

    @pytest.mark.asyncio
    async def test_match_coding_returns_pattern(self, reasoning_graph):
        """coding 匹配到 coding_pattern 推理模式"""
        pattern = reasoning_graph.match(task_type="coding")

        assert pattern is not None
        assert pattern.pattern_type == "coding_pattern"
        assert pattern.pattern_id == "code_design_implement"
        assert len(pattern.steps) >= 3

    @pytest.mark.asyncio
    async def test_pattern_build_prompt(self, reasoning_graph):
        """推理模式能构建 Prompt (含用户问题 + 步骤编号)"""
        pattern = reasoning_graph.match(task_type="coding")
        assert pattern is not None

        prompt = pattern.build_prompt("实现一个快速排序算法")

        assert "实现一个快速排序算法" in prompt
        # 步骤以编号列表呈现
        assert "1." in prompt
        assert "推理结构" in prompt


# ============================================================
# 4. TestLearningPipeline — 学习闭环
# ============================================================

class TestLearningPipeline:
    """LearningEngine.learn() → PatchValidator → SkillGraph 学习链路"""

    @pytest.mark.asyncio
    async def test_learn_high_quality_content(self, learning_graph, reasoning_graph):
        """高质量内容 (review_score=0.85) 生成 patches"""
        engine = LearningEngine(
            skill_graph=learning_graph,
            reasoning_graph=reasoning_graph,
        )

        writer_output = (
            "## Agent Memory Tool\n"
            "This section describes the agent memory tool design."
        )

        result = engine.learn(
            user_task="介绍 Agent 架构",
            writer_output=writer_output,
            skill_path=["root", "tech", "ai"],
            review_score=0.85,
        )

        # review_score >= 0.70 → 触发学习
        assert result["validated"] >= 1
        assert len(result["knowledge_patches"]) >= 1
        # "Agent Memory Tool" 与已有 "Agent Tool" 词重叠 (非子串) → 通过校验
        patch = result["knowledge_patches"][0]
        assert patch.concept_name == "Agent Memory Tool"
        assert patch.related_concepts == ["Agent Tool"]

    @pytest.mark.asyncio
    async def test_learn_low_quality_skipped(self, learning_graph, reasoning_graph):
        """低质量内容 (review_score=0.50) 不学习"""
        engine = LearningEngine(
            skill_graph=learning_graph,
            reasoning_graph=reasoning_graph,
        )

        result = engine.learn(
            user_task="随便聊聊",
            writer_output="## Some Concept\n内容描述。",
            skill_path=["root"],
            review_score=0.50,
        )

        # review_score < 0.70 → 直接跳过
        assert result["validated"] == 0
        assert result["rejected"] == 0
        assert result["knowledge_patches"] == []
        assert result["reasoning_patches"] == []

    @pytest.mark.asyncio
    async def test_apply_patches_to_graph(self, learning_graph, reasoning_graph):
        """应用 patches 后 graph 节点增加"""
        engine = LearningEngine(
            skill_graph=learning_graph,
            reasoning_graph=reasoning_graph,
        )

        writer_output = (
            "## Agent Memory Tool\n"
            "This section describes the agent memory tool design."
        )
        result = engine.learn(
            user_task="介绍 Agent 架构",
            writer_output=writer_output,
            skill_path=["root", "tech", "ai"],
            review_score=0.85,
        )

        before = len(learning_graph.nodes)
        applied = engine.apply_patches(result)
        after = len(learning_graph.nodes)

        assert applied >= 1
        assert after > before
        # 新节点 id 为 concept_name 规范化后的形式
        assert "agent_memory_tool" in learning_graph.nodes

    @pytest.mark.asyncio
    async def test_validator_rejects_duplicate(self, learning_graph):
        """重复概念被 PatchValidator 拒绝"""
        validator = PatchValidator(learning_graph)

        # learning_graph 已有 "Agent Tool" 节点 (id=agent_tool)
        # 构造一个与已有节点同 id 的 patch
        patch = KnowledgePatch(
            concept_name="Agent Tool",
            definition="重复的 Agent Tool 概念定义内容",
            domain="tech.ai",
            related_concepts=[],
            confidence=0.8,
            source="auto_extract",
        )

        result = validator.validate_knowledge(patch)

        assert result.passed is False
        assert any("重复" in err for err in result.errors)
        assert result.patch_type == "knowledge"


# ============================================================
# 5. TestEndToEndFlow — 端到端全链路
# ============================================================

class TestEndToEndFlow:
    """端到端流程：classify → decide → decompose → plan → match → learn"""

    @pytest.mark.asyncio
    async def test_full_pipeline_chat(self, controller, classifier):
        """chat 任务完整流程：classify → decide → 不启动 decomposer"""
        # 使用全局单例 (chat 不依赖图内容)
        skill_graph = get_skill_graph()
        assert skill_graph is not None

        profile = classifier.classify("你好")
        assert profile.task_type == TaskType.CHAT

        decision = controller.decide(profile)

        assert decision.task_type == "chat"
        assert "decomposer" not in decision.engines
        assert "planner" not in decision.engines
        assert decision.use_cloud is False
        # chat 流程简化：2 个引擎
        assert len(decision.engines) == 2

    @pytest.mark.asyncio
    async def test_full_pipeline_analysis(self, controller, classifier, reasoning_graph):
        """analysis 任务完整流程：classify → decide → decompose → plan → match → learn"""
        # 构建本地 seeded graph (含 SQL / NoSQL / 数据库 / Query Engine)
        graph = SkillGraph()
        for nid, name, desc in [
            ("sql", "SQL", "关系型数据库查询语言"),
            ("nosql", "NoSQL", "非关系型数据库"),
            ("database", "数据库", "数据存储系统"),
            ("query_engine", "Query Engine", "查询引擎"),
        ]:
            graph.add_node(GraphNode(id=nid, name=name, node_type="concept",
                                     domain="tech", description=desc))
        graph.add_edge(GraphEdge(from_node="database", to_node="sql", edge_type="has_part"))
        graph.add_edge(GraphEdge(from_node="database", to_node="nosql", edge_type="has_part"))

        decomposer = Decomposer(graph)
        planner = LocalPlanner(graph)
        learning_engine = LearningEngine(
            skill_graph=graph,
            reasoning_graph=reasoning_graph,
        )

        # 1. classify
        profile = classifier.classify("对比分析 SQL 和 NoSQL 数据库")
        assert profile.task_type == TaskType.ANALYSIS
        profile.complexity = 0.8  # > 0.7 启用 cloud + reasoning（开发指南 line 2077）

        # 2. decide
        decision = controller.decide(profile)
        assert "decomposer" in decision.engines
        assert "planner" in decision.engines
        assert "reasoning" in decision.engines

        # 3. decompose
        decompose_result = decomposer.decompose("对比分析 SQL 和 NoSQL 数据库")
        assert decompose_result["matched_nodes"], "应匹配到 SQL/NoSQL/数据库 节点"
        matched_names = {n.name for n in decompose_result["matched_nodes"]}
        assert {"SQL", "NoSQL", "数据库"}.issubset(matched_names)

        # 4. plan
        steps = planner.plan(decompose_result)
        assert steps, "应生成规划步骤"

        # 5. match reasoning
        pattern = reasoning_graph.match(task_type="analysis", domain="tech")
        assert pattern is not None
        assert pattern.pattern_type == "analysis_pattern"

        # 6. learn (writer_output 含一个可通过校验的新概念)
        writer_output = (
            "## Query Cache Engine\n"
            "本节介绍查询缓存引擎的设计与实现，提升数据库性能。"
        )
        learn_result = learning_engine.learn(
            user_task="对比分析 SQL 和 NoSQL 数据库",
            writer_output=writer_output,
            skill_path=["root", "tech"],
            review_score=0.85,
        )
        assert learn_result["validated"] >= 1
        assert len(learn_result["knowledge_patches"]) >= 1

    @pytest.mark.asyncio
    async def test_pipeline_latency(self, controller, classifier):
        """简单对话全链路 < 50ms (classify → decide)"""
        # 预热 (避免首次 import / 缓存开销计入)
        warm_profile = classifier.classify("你好")
        controller.decide(warm_profile)

        start = time.perf_counter()
        profile = classifier.classify("你好")
        decision = controller.decide(profile)
        elapsed = time.perf_counter() - start

        assert decision.task_type == "chat"
        # 简单对话全链路应远低于 50ms
        assert elapsed < 0.05, f"简单对话全链路耗时 {elapsed*1000:.2f}ms 超过 50ms"
