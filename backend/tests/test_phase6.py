"""Phase 6: Knowledge Recommendation 测试

覆盖范围:
- IntentGraph: 记录/连续领域/分布/趋势/统计
- KnowledgeRecommendation: 四类推荐来源
- KnowledgeRecommendation: should_intervene()
- KnowledgeRecommendation: recommend_for_context()
- API: GET /api/v1/recommend
"""

import pytest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.graphs.intent_graph import IntentGraph, IntentRecord
from core.engines.knowledge_recommendation import KnowledgeRecommendation


# ============================================================
# Test 1: IntentGraph
# ============================================================

class TestIntentGraph:
    """IntentGraph 意图时间线"""

    def test_create_empty(self):
        graph = IntentGraph(user_id="test_user")
        assert graph.user_id == "test_user"
        assert len(graph.records) == 0

    def test_record_single(self):
        graph = IntentGraph(user_id="test_user")
        graph.record("session_1", "什么是Transformer", domain="ai", task_type="qa")
        assert len(graph.records) == 1
        assert graph.records[0].domain == "ai"
        assert graph.records[0].task_type == "qa"

    def test_record_multiple(self):
        graph = IntentGraph(user_id="test_user")
        for i in range(5):
            graph.record(f"session_{i}", f"question_{i}", domain="ai", task_type="qa")
        assert len(graph.records) == 5

    def test_consecutive_domain_detected(self):
        graph = IntentGraph(user_id="test_user")
        for i in range(3):
            graph.record(f"session_{i}", f"question_{i}", domain="ai", task_type="qa")
        assert graph.get_consecutive_domain(window=3) == "ai"

    def test_consecutive_domain_not_detected(self):
        graph = IntentGraph(user_id="test_user")
        graph.record("s1", "q1", domain="ai", task_type="qa")
        graph.record("s2", "q2", domain="business", task_type="writing")
        graph.record("s3", "q3", domain="ai", task_type="qa")
        assert graph.get_consecutive_domain(window=3) is None

    def test_consecutive_domain_insufficient(self):
        graph = IntentGraph(user_id="test_user")
        graph.record("s1", "q1", domain="ai", task_type="qa")
        graph.record("s2", "q2", domain="ai", task_type="qa")
        assert graph.get_consecutive_domain(window=3) is None

    def test_consecutive_domain_empty(self):
        graph = IntentGraph(user_id="test_user")
        # 部分记录无 domain
        graph.record("s1", "q1", domain="ai", task_type="qa")
        graph.record("s2", "q2", domain="", task_type="qa")
        graph.record("s3", "q3", domain="ai", task_type="qa")
        assert graph.get_consecutive_domain(window=3) is None

    def test_domain_distribution(self):
        graph = IntentGraph(user_id="test_user")
        graph.record("s1", "q1", domain="ai", task_type="qa")
        graph.record("s2", "q2", domain="ai", task_type="qa")
        graph.record("s3", "q3", domain="business", task_type="writing")
        dist = graph.get_domain_distribution()
        assert len(dist) == 2
        assert dist[0] == ("ai", 2)

    def test_task_type_distribution(self):
        graph = IntentGraph(user_id="test_user")
        graph.record("s1", "q1", domain="ai", task_type="qa")
        graph.record("s2", "q2", domain="ai", task_type="coding")
        graph.record("s3", "q3", domain="ai", task_type="qa")
        dist = graph.get_task_type_distribution()
        assert len(dist) == 2
        assert dist[0] == ("qa", 2)

    def test_get_recent_skill_nodes(self):
        graph = IntentGraph(user_id="test_user")
        graph.record("s1", "q1", skill_nodes=["transformer", "attention"])
        graph.record("s2", "q2", skill_nodes=["transformer", "rnn"])
        nodes = graph.get_recent_skill_nodes()
        assert "transformer" in nodes
        assert "attention" in nodes
        assert "rnn" in nodes

    def test_trend_detected(self):
        graph = IntentGraph(user_id="test_user")
        # 前一半 ai
        for i in range(3):
            graph.record(f"s{i}", f"q{i}", domain="ai", task_type="qa")
        # 后一半 business
        for i in range(3, 6):
            graph.record(f"s{i}", f"q{i}", domain="business", task_type="writing")
        trend = graph.get_trend()
        assert trend is not None
        assert "ai" in trend
        assert "business" in trend

    def test_trend_insufficient(self):
        graph = IntentGraph(user_id="test_user")
        for i in range(3):
            graph.record(f"s{i}", f"q{i}", domain="ai", task_type="qa")
        assert graph.get_trend() is None

    def test_stats(self):
        graph = IntentGraph(user_id="test_user")
        graph.record("s1", "q1", domain="ai", task_type="qa")
        graph.record("s2", "q2", domain="ai", task_type="coding")
        graph.record("s3", "q3", domain="business", task_type="writing")
        stats = graph.stats()
        assert stats["total_records"] == 3
        assert stats["unique_domains"] == 2
        assert stats["unique_task_types"] == 3

    def test_max_records_limit(self):
        graph = IntentGraph(user_id="test_user", max_records=5)
        for i in range(10):
            graph.record(f"s{i}", f"q{i}", domain="ai", task_type="qa")
        assert len(graph.records) == 5

    def test_skip_empty_domain_in_distribution(self):
        graph = IntentGraph(user_id="test_user")
        graph.record("s1", "q1", domain="", task_type="qa")
        dist = graph.get_domain_distribution()
        assert len(dist) == 0


# ============================================================
# Test 2: KnowledgeRecommendation
# ============================================================

class TestKnowledgeRecommendation:
    """四类推荐来源"""

    @pytest.fixture
    def skill_graph(self):
        """构建测试用 Skill Graph"""
        from core.graphs.skill_graph import SkillGraph, GraphNode, GraphEdge
        g = SkillGraph()

        # 节点
        g.add_node(GraphNode(id="agent", name="Agent", node_type="concept", domain="ai"))
        g.add_node(GraphNode(id="memory", name="Memory", node_type="concept", domain="ai"))
        g.add_node(GraphNode(id="planning", name="Planning", node_type="concept", domain="ai"))
        g.add_node(GraphNode(id="rag", name="RAG", node_type="concept", domain="ai"))
        g.add_node(GraphNode(id="llm", name="LLM", node_type="concept", domain="ai"))
        g.add_node(GraphNode(id="python", name="Python", node_type="skill", domain="tech"))
        g.add_node(GraphNode(id="fastapi", name="FastAPI", node_type="skill", domain="tech"))

        # has_part: Agent 由 Memory + Planning 组成
        g.add_edge(GraphEdge(from_node="agent", to_node="memory", edge_type="has_part"))
        g.add_edge(GraphEdge(from_node="agent", to_node="planning", edge_type="has_part"))

        # next_step: Python → FastAPI
        g.add_edge(GraphEdge(from_node="python", to_node="fastapi", edge_type="next_step", weight=0.85))

        # prerequisite: Agent 需要先学 RAG
        g.add_edge(GraphEdge(from_node="rag", to_node="agent", edge_type="prerequisite"))

        return g

    @pytest.fixture
    def brain(self):
        """构建测试用 PersonalBrain（无能力）"""
        from core.personal_brain.brain import PersonalBrain
        brain = PersonalBrain(user_id="test_user")
        # 设置长期目标
        brain.profile.long_term_goals = ["Agent"]
        return brain

    def test_recommend_sub_topic(self, skill_graph, brain):
        """推荐子主题：Agent 的 has_part 子节点"""
        recommender = KnowledgeRecommendation(skill_graph, brain)
        recs = recommender.recommend("学习Agent", ["agent"])
        sub_topics = [r for r in recs if r["type"] == "sub_topic"]
        assert len(sub_topics) >= 1
        node_ids = {r["node_id"] for r in sub_topics}
        assert "memory" in node_ids or "planning" in node_ids

    def test_recommend_next_step(self, skill_graph, brain):
        """推荐学习路径下一步：Python → FastAPI"""
        recommender = KnowledgeRecommendation(skill_graph, brain)
        recs = recommender.recommend("学习Python", ["python"])
        next_steps = [r for r in recs if r["type"] == "next_step"]
        assert len(next_steps) >= 1
        assert next_steps[0]["node_id"] == "fastapi"
        assert next_steps[0]["priority"] == 0.85

    def test_recommend_capability_gap(self, skill_graph, brain):
        """推荐能力缺口"""
        recommender = KnowledgeRecommendation(skill_graph, brain)
        recs = recommender.recommend("学习新技术", ["agent"])
        gaps = [r for r in recs if r["type"] == "capability_gap"]
        # 用户没有掌握任何技能，所以所有节点都是缺口
        assert len(gaps) >= 1

    def test_recommend_goal_prerequisite(self, skill_graph, brain):
        """推荐目标前置知识：Agent 目标 → RAG 前置"""
        recommender = KnowledgeRecommendation(skill_graph, brain)
        recs = recommender.recommend("学习Agent", ["agent"])
        prereqs = [r for r in recs if r["type"] == "goal_prerequisite"]
        assert len(prereqs) >= 1
        assert prereqs[0]["node_id"] == "rag"

    def test_recommend_deduplication(self, skill_graph, brain):
        """去重：同一 node_id 只出现一次"""
        recommender = KnowledgeRecommendation(skill_graph, brain)
        recs = recommender.recommend("学习Agent", ["agent"])
        node_ids = [r["node_id"] for r in recs]
        assert len(node_ids) == len(set(node_ids))

    def test_recommend_limit(self, skill_graph, brain):
        """limit 参数生效"""
        recommender = KnowledgeRecommendation(skill_graph, brain)
        recs = recommender.recommend("学习Agent", ["agent"], limit=3)
        assert len(recs) <= 3

    def test_recommend_sorted_by_priority(self, skill_graph, brain):
        """推荐结果按优先级降序排列"""
        recommender = KnowledgeRecommendation(skill_graph, brain)
        recs = recommender.recommend("学习Agent", ["agent"])
        for i in range(len(recs) - 1):
            assert recs[i]["priority"] >= recs[i + 1]["priority"]

    def test_recommend_fields(self, skill_graph, brain):
        """每条推荐包含必要字段"""
        recommender = KnowledgeRecommendation(skill_graph, brain)
        recs = recommender.recommend("学习Agent", ["agent"])
        for r in recs:
            assert "type" in r
            assert "node" in r
            assert "node_id" in r
            assert "reason" in r
            assert "priority" in r
            assert r["type"] in ("sub_topic", "next_step", "capability_gap", "goal_prerequisite")
            assert 0.0 <= r["priority"] <= 1.0

    def test_recommend_empty_active_nodes(self, skill_graph, brain):
        """空活跃节点时返回能力缺口 + 目标前置"""
        recommender = KnowledgeRecommendation(skill_graph, brain)
        recs = recommender.recommend("任意问题", [])
        # 仅返回能力缺口和目标前置
        types = {r["type"] for r in recs}
        assert "sub_topic" not in types
        assert "next_step" not in types

    def test_recommend_no_brain(self, skill_graph):
        """无 brain 时仅返回 sub_topic + next_step"""
        recommender = KnowledgeRecommendation(skill_graph, brain=None)
        recs = recommender.recommend("学习Agent", ["agent"])
        types = {r["type"] for r in recs}
        assert "capability_gap" not in types
        assert "goal_prerequisite" not in types

    def test_user_has_skips_recommendation(self, skill_graph, brain):
        """用户已掌握的技能不推荐"""
        # 先将 memory 标记为已掌握
        brain.capability.update("memory", "practice", evidence="test")
        recommender = KnowledgeRecommendation(skill_graph, brain)
        recs = recommender.recommend("学习Agent", ["agent"])
        # memory 不应出现在推荐中
        memory_recs = [r for r in recs if r["node_id"] == "memory"]
        assert len(memory_recs) == 0


# ============================================================
# Test 3: should_intervene + recommend_for_context
# ============================================================

class TestIntervene:
    """介入判断 + 上下文推荐"""

    @pytest.fixture
    def skill_graph(self):
        from core.graphs.skill_graph import SkillGraph, GraphNode, GraphEdge
        g = SkillGraph()
        g.add_node(GraphNode(id="agent", name="Agent", node_type="concept", domain="ai"))
        g.add_node(GraphNode(id="memory", name="Memory", node_type="concept", domain="ai"))
        g.add_edge(GraphEdge(from_node="agent", to_node="memory", edge_type="has_part"))
        return g

    def test_should_intervene_false_without_intent(self, skill_graph):
        recommender = KnowledgeRecommendation(skill_graph)
        assert recommender.should_intervene() is False

    def test_should_intervene_true_with_consecutive(self, skill_graph):
        recommender = KnowledgeRecommendation(skill_graph)
        intent = IntentGraph(user_id="test")
        for i in range(3):
            intent.record(f"s{i}", f"q{i}", domain="ai", task_type="qa")
        assert recommender.should_intervene(intent) is True

    def test_should_intervene_false_with_mixed(self, skill_graph):
        recommender = KnowledgeRecommendation(skill_graph)
        intent = IntentGraph(user_id="test")
        intent.record("s1", "q1", domain="ai", task_type="qa")
        intent.record("s2", "q2", domain="business", task_type="writing")
        intent.record("s3", "q3", domain="ai", task_type="qa")
        assert recommender.should_intervene(intent) is False

    def test_recommend_for_context_empty_when_no_intervene(self, skill_graph):
        recommender = KnowledgeRecommendation(skill_graph)
        intent = IntentGraph(user_id="test")
        intent.record("s1", "q1", domain="ai", task_type="qa")
        intent.record("s2", "q2", domain="business", task_type="qa")
        intent.record("s3", "q3", domain="daily", task_type="qa")
        result = recommender.recommend_for_context("test", ["agent"], intent)
        assert result["should_intervene"] is False
        assert len(result["recommendations"]) == 0

    def test_recommend_for_context_returns_recommendations(self, skill_graph):
        recommender = KnowledgeRecommendation(skill_graph)
        intent = IntentGraph(user_id="test")
        for i in range(3):
            intent.record(f"s{i}", f"q{i}", domain="ai", task_type="qa")
        result = recommender.recommend_for_context("test", ["agent"], intent)
        assert result["should_intervene"] is True
        assert len(result["recommendations"]) > 0
        assert result["reason"] != ""

    def test_recommend_for_context_fields(self, skill_graph):
        recommender = KnowledgeRecommendation(skill_graph)
        result = recommender.recommend_for_context("test", ["agent"])
        assert "should_intervene" in result
        assert "recommendations" in result
        assert "reason" in result
        assert "total" in result


# ============================================================
# Test 4: IntentRecord 数据模型
# ============================================================

class TestIntentRecord:
    """IntentRecord 数据模型"""

    def test_create_default(self):
        record = IntentRecord(session_id="s1", question="q1")
        assert record.session_id == "s1"
        assert record.question == "q1"
        assert record.domain == ""
        assert record.task_type == ""
        assert record.skill_nodes == []
        assert record.timestamp > 0

    def test_create_full(self):
        record = IntentRecord(
            session_id="s1",
            question="q1",
            domain="ai",
            task_type="qa",
            skill_nodes=["transformer", "attention"],
            timestamp=1000.0
        )
        assert record.domain == "ai"
        assert record.task_type == "qa"
        assert len(record.skill_nodes) == 2
        assert record.timestamp == 1000.0


# ============================================================
# Test 5: Phase 6 集成测试
# ============================================================

class TestPhase6Integration:
    """Phase 6 集成测试"""

    def test_imports(self):
        from core.graphs.intent_graph import IntentGraph, IntentRecord
        from core.engines.knowledge_recommendation import KnowledgeRecommendation
        assert True

    def test_full_pipeline(self):
        """完整流程：IntentGraph → KnowledgeRecommendation → 推荐结果"""
        from core.graphs.skill_graph import SkillGraph, GraphNode, GraphEdge

        # 构建 Skill Graph
        g = SkillGraph()
        g.add_node(GraphNode(id="agent", name="Agent", node_type="concept", domain="ai"))
        g.add_node(GraphNode(id="memory", name="Memory", node_type="concept", domain="ai"))
        g.add_node(GraphNode(id="rag", name="RAG", node_type="concept", domain="ai"))
        g.add_edge(GraphEdge(from_node="agent", to_node="memory", edge_type="has_part"))
        g.add_edge(GraphEdge(from_node="rag", to_node="agent", edge_type="prerequisite"))

        # 构建 PersonalBrain
        from core.personal_brain.brain import PersonalBrain
        brain = PersonalBrain(user_id="test_user")
        brain.profile.long_term_goals = ["Agent"]

        # 构建 IntentGraph
        intent = IntentGraph(user_id="test_user")
        for i in range(3):
            intent.record(f"s{i}", f"question about AI {i}", domain="ai", task_type="qa")

        # 推荐
        recommender = KnowledgeRecommendation(g, brain)
        result = recommender.recommend_for_context(
            "学习Agent开发", ["agent"], intent, limit=5
        )

        assert result["should_intervene"] is True
        assert len(result["recommendations"]) > 0
        assert result["total"] == len(result["recommendations"])

        # 验证推荐类型
        types = {r["type"] for r in result["recommendations"]}
        assert "sub_topic" in types  # Memory 作为 has_part
        assert "goal_prerequisite" in types  # RAG 作为 Agent 前置

    def test_intent_graph_stats(self):
        intent = IntentGraph(user_id="test")
        intent.record("s1", "q1", domain="ai", task_type="qa")
        intent.record("s2", "q2", domain="ai", task_type="coding")
        stats = intent.stats()
        assert "total_records" in stats
        assert "unique_domains" in stats
        assert "domain_distribution" in stats
        assert "consecutive_domain" in stats