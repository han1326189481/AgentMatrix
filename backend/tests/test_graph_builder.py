"""GraphBuilder 构建功能测试

测试 GraphBuilder 从 V2.1 的 prompts/skills/tree.yaml 和各域 skill.yaml
构建 V3 Skill Graph 的能力。

覆盖范围:
- 基本构建: build() 返回 SkillGraph、节点/边数量、domain/concept 节点
- tree.yaml 解析: 根节点创建、subdomain_of 边创建
- skill.yaml 解析: concept 节点创建、related_to 边创建
- 手动补充边: has_part / next_step / prerequisite 边存在
- 统计信息: stats() 返回结构、edge_types 分布
"""

import pytest
from core.graphs.graph_builder import GraphBuilder
from core.graphs.skill_graph import SkillGraph


SKILLS_DIR = r"d:\AgentMatrix\backend\prompts\skills"


@pytest.fixture(scope="module")
def graph_builder():
    """模块级 GraphBuilder 实例"""
    return GraphBuilder(skills_dir=SKILLS_DIR)


@pytest.fixture(scope="module")
def built_graph(graph_builder):
    """模块级构建好的 SkillGraph 实例，所有测试复用"""
    return graph_builder.build()


# ============================================================
# 1. TestGraphBuilderBasic
# ============================================================

class TestGraphBuilderBasic:
    """GraphBuilder 基本构建功能"""

    def test_build_returns_skill_graph(self, built_graph):
        """build() 返回 SkillGraph 实例"""
        assert isinstance(built_graph, SkillGraph)

    def test_build_has_nodes(self, built_graph):
        """构建后节点数 > 0"""
        assert len(built_graph.nodes) > 0

    def test_build_has_edges(self, built_graph):
        """构建后边数 > 0"""
        assert len(built_graph.edges) > 0

    def test_build_has_domain_nodes(self, built_graph):
        """构建后有 domain 类型节点"""
        domain_nodes = [n for n in built_graph.nodes.values()
                        if n.node_type == "domain"]
        assert len(domain_nodes) > 0

    def test_build_has_concept_nodes(self, built_graph):
        """构建后有 concept 类型节点"""
        concept_nodes = [n for n in built_graph.nodes.values()
                         if n.node_type == "concept"]
        assert len(concept_nodes) > 0


# ============================================================
# 2. TestGraphBuilderFromTree
# ============================================================

class TestGraphBuilderFromTree:
    """tree.yaml 解析功能"""

    def test_tree_creates_root_node(self, built_graph):
        """tree.yaml 的根节点被创建"""
        assert "root" in built_graph.nodes
        root_node = built_graph.get_node("root")
        assert root_node is not None
        assert root_node.node_type == "domain"

    def test_tree_creates_subdomain_edges(self, built_graph):
        """subdomain_of 边被创建"""
        subdomain_edges = [e for e in built_graph.edges
                           if e.edge_type == "subdomain_of"]
        assert len(subdomain_edges) > 0


# ============================================================
# 3. TestGraphBuilderFromSkills
# ============================================================

class TestGraphBuilderFromSkills:
    """skill.yaml 解析功能"""

    def test_skills_create_concept_nodes(self, built_graph):
        """skill.yaml 中的 concepts 被创建为 concept 节点"""
        # tech/ai/agent/skill.yaml 中有 term "Agent" -> id "agent"
        assert "agent" in built_graph.nodes
        assert built_graph.get_node("agent").node_type == "concept"
        # tech/ai/rag/skill.yaml 中有 term "RAG" -> id "rag"
        assert "rag" in built_graph.nodes
        assert built_graph.get_node("rag").node_type == "concept"
        # tech/ai/llm/skill.yaml 中有 term "Transformer" -> id "transformer"
        assert "transformer" in built_graph.nodes
        assert built_graph.get_node("transformer").node_type == "concept"

    def test_skills_create_related_edges(self, built_graph):
        """related_to 边被创建"""
        related_edges = [e for e in built_graph.edges
                         if e.edge_type == "related_to"]
        assert len(related_edges) > 0


# ============================================================
# 4. TestGraphBuilderManualEdges
# ============================================================

class TestGraphBuilderManualEdges:
    """手动补充的关键关系边"""

    def test_manual_edges_has_part(self, built_graph):
        """has_part 边存在"""
        has_part_edges = [e for e in built_graph.edges
                          if e.edge_type == "has_part"]
        assert len(has_part_edges) > 0

    def test_manual_edges_next_step(self, built_graph):
        """next_step 边存在"""
        next_step_edges = [e for e in built_graph.edges
                           if e.edge_type == "next_step"]
        assert len(next_step_edges) > 0

    def test_manual_edges_prerequisite(self, built_graph):
        """prerequisite 边存在"""
        prerequisite_edges = [e for e in built_graph.edges
                              if e.edge_type == "prerequisite"]
        assert len(prerequisite_edges) > 0


# ============================================================
# 5. TestGraphBuilderStats
# ============================================================

class TestGraphBuilderStats:
    """GraphBuilder 统计信息"""

    def test_stats_returns_dict(self, built_graph):
        """stats() 返回包含 total_nodes, total_edges 的字典"""
        stats = built_graph.stats()
        assert isinstance(stats, dict)
        assert "total_nodes" in stats
        assert "total_edges" in stats
        assert stats["total_nodes"] > 0
        assert stats["total_edges"] > 0

    def test_stats_edge_type_counts(self, built_graph):
        """stats() 包含 edge_types 分布"""
        stats = built_graph.stats()
        assert "edge_types" in stats
        assert isinstance(stats["edge_types"], dict)
        assert len(stats["edge_types"]) > 0
