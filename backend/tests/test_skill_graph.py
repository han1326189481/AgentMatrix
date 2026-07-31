"""SkillGraph 数据模型测试 — V3 Phase 1 验收标准

测试范围（对应 V3_DEVELOPMENT_GUIDE.md 第 3.4 节验收标准）:
1. 节点数 >= 30
2. 六种边类型 __post_init__ 校验
3. search_by_name("Transformer") 返回正确节点
4. get_neighbors("agent", "has_part") 返回子节点
5. get_prerequisites("llm") 返回 ["transformer"]
6. get_next_steps("rag") 返回 [("agent", 1.0)]
7. diff() 正确识别新概念
8. find_similar_node("flash attention") 匹配到 "attention"
9. 序列化 → 反序列化 → 再序列化，数据一致
"""

import os
import pytest
from core.graphs.skill_graph import SkillGraph, GraphNode, GraphEdge, EDGE_TYPES

GRAPH_YAML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core", "graphs", "skill_graph.yaml"
)


@pytest.fixture(scope="module")
def graph():
    """加载已生成的 skill_graph.yaml"""
    return SkillGraph.load(GRAPH_YAML)


# ============================================================
# 1. 验收标准: 节点数 >= 30
# ============================================================

class TestGraphNodes:
    """SkillGraph 节点基本验证"""

    def test_node_count_above_30(self, graph):
        """验收标准 1: 节点数 >= 30"""
        assert len(graph.nodes) >= 30

    def test_has_domain_nodes(self, graph):
        """包含 domain 类型节点"""
        domain_nodes = [n for n in graph.nodes.values()
                        if n.node_type == "domain"]
        assert len(domain_nodes) > 0

    def test_has_concept_nodes(self, graph):
        """包含 concept 类型节点"""
        concept_nodes = [n for n in graph.nodes.values()
                         if n.node_type == "concept"]
        assert len(concept_nodes) > 0

    def test_node_has_required_fields(self, graph):
        """每个节点都有 id, name, node_type 字段"""
        for node in graph.nodes.values():
            assert node.id
            assert node.name
            assert node.node_type in ("domain", "concept", "skill")


# ============================================================
# 2. 验收标准: 六种边类型 __post_init__ 校验
# ============================================================

class TestEdgeTypes:
    """六种边类型校验"""

    def test_all_six_edge_types_defined(self):
        """EDGE_TYPES 包含六种边类型"""
        expected = {"has_part", "is_a", "prerequisite",
                    "next_step", "related_to", "subdomain_of"}
        assert set(EDGE_TYPES) == expected

    def test_valid_edge_type_accepted(self):
        """合法 edge_type 通过 __post_init__"""
        for etype in EDGE_TYPES:
            edge = GraphEdge(from_node="a", to_node="b", edge_type=etype)
            assert edge.edge_type == etype

    def test_invalid_edge_type_rejected(self):
        """非法 edge_type 触发 ValueError"""
        with pytest.raises(ValueError):
            GraphEdge(from_node="a", to_node="b", edge_type="invalid_type")

    def test_graph_has_multiple_edge_types(self, graph):
        """图中包含多种边类型"""
        used_types = {e.edge_type for e in graph.edges}
        assert len(used_types) >= 4


# ============================================================
# 3. 验收标准: search_by_name("Transformer")
# ============================================================

class TestGraphSearch:
    """SkillGraph 搜索功能"""

    def test_search_transformer_returns_node(self, graph):
        """验收标准 3: search_by_name("Transformer") 返回正确节点"""
        results = graph.search_by_name("Transformer")
        assert len(results) > 0
        assert any(n.name == "Transformer" for n in results)

    def test_search_by_name_case_insensitive(self, graph):
        """搜索大小写不敏感"""
        results = graph.search_by_name("transformer")
        assert len(results) > 0

    def test_search_by_name_no_match(self, graph):
        """无匹配时返回空列表"""
        results = graph.search_by_name("NonExistentConcept12345")
        assert results == []


# ============================================================
# 4. 验收标准: get_neighbors("agent", "has_part")
# ============================================================

class TestGraphTraversal:
    """SkillGraph 遍历功能"""

    def test_get_neighbors_agent_has_part(self, graph):
        """验收标准 4: get_neighbors("agent", "has_part") 返回子节点

        指南期望 ["memory", "tool", "multi"]，
        实际节点 ID 为 memory, tool_use, multi_agent（来自 skill.yaml）。
        """
        neighbors = graph.get_neighbors("agent", "has_part", depth=1)
        neighbor_ids = {n.id for n in neighbors}
        assert "memory" in neighbor_ids
        assert "tool_use" in neighbor_ids
        assert "multi_agent" in neighbor_ids

    def test_get_children_agent_has_part(self, graph):
        """get_children("agent", "has_part") 返回直接子节点"""
        children = graph.get_children("agent", "has_part")
        assert len(children) >= 3

    def test_get_neighbors_nonexistent_node(self, graph):
        """不存在节点的邻居返回空"""
        neighbors = graph.get_neighbors("nonexistent_node")
        assert neighbors == []


# ============================================================
# 5. 验收标准: get_prerequisites("llm") 返回 ["transformer"]
# ============================================================

class TestPrerequisites:
    """前置知识查询"""

    def test_get_prerequisites_llm_returns_transformer(self, graph):
        """验收标准 5: get_prerequisites("llm") 返回 ["transformer"]"""
        prereqs = graph.get_prerequisites("llm")
        prereq_names = [n.name for n in prereqs]
        assert "Transformer" in prereq_names

    def test_get_prerequisites_transformer_returns_attention(self, graph):
        """get_prerequisites("transformer") 返回 attention"""
        prereqs = graph.get_prerequisites("transformer")
        prereq_names = [n.name for n in prereqs]
        assert "Attention" in prereq_names

    def test_get_prerequisites_no_prereqs(self, graph):
        """无前置知识的节点返回空"""
        prereqs = graph.get_prerequisites("root")
        assert prereqs == []


# ============================================================
# 6. 验收标准: get_next_steps("rag") 返回 [("agent", 1.0)]
# ============================================================

class TestNextSteps:
    """学习路径下一步"""

    def test_get_next_steps_rag_returns_agent(self, graph):
        """验收标准 6: get_next_steps("rag") 返回 [("agent", 1.0)]"""
        steps = graph.get_next_steps("rag")
        assert len(steps) > 0
        step_names = [(n.name, w) for n, w in steps]
        assert ("Agent", 1.0) in step_names

    def test_get_next_steps_sorted_by_weight(self, graph):
        """next_step 按权重降序排列"""
        steps = graph.get_next_steps("rag")
        weights = [w for _, w in steps]
        assert weights == sorted(weights, reverse=True)


# ============================================================
# 7. 验收标准: diff() 正确识别新概念
# ============================================================

class TestGraphDiff:
    """Graph Diff 集合差运算"""

    def test_diff_identifies_new_concepts(self, graph):
        """验收标准 7: diff({"Flash-Attention", "Self-Attention"}) 识别为新概念"""
        new_concepts = graph.diff({"Flash-Attention", "Self-Attention"})
        assert "Flash-Attention" in new_concepts
        assert "Self-Attention" in new_concepts

    def test_diff_excludes_existing_concepts(self, graph):
        """diff 排除已有概念"""
        new_concepts = graph.diff({"Transformer", "RAG", "Agent"})
        assert new_concepts == set()

    def test_diff_case_insensitive(self, graph):
        """diff 大小写不敏感"""
        new_concepts = graph.diff({"transformer", "TRANSFORMER"})
        assert new_concepts == set()


# ============================================================
# 8. 验收标准: find_similar_node("flash attention")
# ============================================================

class TestFindSimilarNode:
    """名称相似度匹配"""

    def test_find_similar_flash_attention_matches_attention(self, graph):
        """验收标准 8: find_similar_node("flash attention") 匹配到 "attention" 节点"""
        similar = graph.find_similar_node("flash attention")
        assert similar is not None
        assert similar.id == "attention"

    def test_find_similar_exact_match(self, graph):
        """精确匹配"""
        similar = graph.find_similar_node("Transformer")
        assert similar is not None
        assert similar.name == "Transformer"

    def test_find_similar_no_match(self, graph):
        """无相似节点时返回 None"""
        similar = graph.find_similar_node("zzz_nonexistent_zzz")
        assert similar is None


# ============================================================
# 9. 验收标准: 序列化 → 反序列化 → 再序列化，数据一致
# ============================================================

class TestSerialization:
    """YAML 序列化一致性"""

    def test_serialization_roundtrip(self, graph):
        """验收标准 9: 序列化 → 反序列化 → 再序列化，数据一致"""
        dict1 = graph.to_dict()
        graph2 = SkillGraph.from_dict(dict1)
        dict2 = graph2.to_dict()

        # 节点数一致
        assert len(dict1["nodes"]) == len(dict2["nodes"])
        # 边数一致
        assert len(dict1["edges"]) == len(dict2["edges"])
        # 节点 ID 集合一致
        assert set(dict1["nodes"].keys()) == set(dict2["nodes"].keys())

    def test_load_from_yaml(self, graph):
        """从 YAML 文件加载成功"""
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0

    def test_save_and_reload(self, graph, tmp_path):
        """保存到临时文件后重新加载，数据一致"""
        tmp_file = str(tmp_path / "test_graph.yaml")
        graph.save(tmp_file)
        reloaded = SkillGraph.load(tmp_file)

        assert len(reloaded.nodes) == len(graph.nodes)
        assert len(reloaded.edges) == len(graph.edges)

    def test_edge_metadata_preserved(self, graph):
        """边的 metadata 在序列化后保留"""
        dict1 = graph.to_dict()
        graph2 = SkillGraph.from_dict(dict1)
        for e1, e2 in zip(graph.edges, graph2.edges):
            assert e1.from_node == e2.from_node
            assert e2.to_node == e2.to_node
            assert e1.edge_type == e2.edge_type
            assert e1.weight == e2.weight
