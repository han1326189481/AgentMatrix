from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import yaml, os

# ============================================================
# 六种边类型（Skill Graph 的关系语义）
# ============================================================
# has_part       : A 由 B 组成        (Agent → Memory)
# is_a           : A 是 B 的一种      (Transformer → Neural Network)
# prerequisite   : 学 A 前需要 B      (RNN → Attention)
# next_step      : 学完 A 推荐学 B    (K8S → Service Mesh)
# related_to     : A 与 B 相关        (Docker → K8S)
# subdomain_of   : A 属于 B 域        (LLM → AI)
# ============================================================

EDGE_TYPES = ["has_part", "is_a", "prerequisite", "next_step", "related_to", "subdomain_of"]


@dataclass
class GraphNode:
    """Skill Graph 节点"""
    id: str                              # "transformer"
    name: str                            # "Transformer"
    node_type: str                       # "domain" | "concept" | "skill"
    domain: str = ""                     # "tech.ai.llm"
    description: str = ""                # 节点描述
    embedding: Optional[List[float]] = None  # 可选，语义搜索
    metadata: Dict = field(default_factory=dict)
    # V2.4 (2026-07-30): 节点级别名列表，用于拓宽检索匹配
    #   存放同义词、口头语、代称、英文词等，供 search_by_name 匹配
    #   例: BM25 节点 aliases = ["Okapi BM25", "Best Match 25", "BM25算法"]
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "node_type": self.node_type, "domain": self.domain,
            "description": self.description, "metadata": self.metadata,
            "aliases": self.aliases,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GraphNode":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            node_type=data.get("node_type", ""),
            domain=data.get("domain", ""),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
            aliases=data.get("aliases", []) or [],
        )


@dataclass
class GraphEdge:
    """Skill Graph 边"""
    from_node: str
    to_node: str
    edge_type: str    # 必须是 EDGE_TYPES 之一
    weight: float = 1.0
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if self.edge_type not in EDGE_TYPES:
            raise ValueError(f"Invalid edge_type: {self.edge_type}, must be one of {EDGE_TYPES}")

    def to_dict(self) -> dict:
        return {
            "from": self.from_node, "to": self.to_node,
            "type": self.edge_type, "weight": self.weight
        }


class SkillGraph:
    """技能图谱 — V3 核心数据结构

    所有 Engine 的底层依赖。提供：
    - 搜索：关键词匹配 / Embedding 语义搜索
    - 遍历：邻居扩展 / 子节点 / 前置知识 / 下一步
    - Diff：集合差运算，识别新概念
    - 序列化：YAML 持久化
    """

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._adj_out: Dict[str, List[GraphEdge]] = {}  # 出边索引
        self._adj_in: Dict[str, List[GraphEdge]] = {}   # 入边索引

    # ========== 基本操作 ==========

    def add_node(self, node: GraphNode):
        self.nodes[node.id] = node
        self._adj_out.setdefault(node.id, [])
        self._adj_in.setdefault(node.id, [])

    def add_edge(self, edge: GraphEdge):
        self.edges.append(edge)
        self._adj_out.setdefault(edge.from_node, []).append(edge)
        self._adj_in.setdefault(edge.to_node, []).append(edge)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self.nodes.get(node_id)

    def remove_node(self, node_id: str):
        """删除节点及其关联边"""
        if node_id in self.nodes:
            del self.nodes[node_id]
        self._adj_out.pop(node_id, None)
        self._adj_in.pop(node_id, None)
        self.edges = [e for e in self.edges
                      if e.from_node != node_id and e.to_node != node_id]

    # ========== 图搜索（零 LLM）==========

    def search_by_name(self, query: str, top_k: int = 5) -> List[GraphNode]:
        """关键词匹配搜索

        V2.4 (2026-07-30): 新增 aliases 匹配分支
          匹配优先级: name(10) > aliases(9) > id(8) > description(3)
          aliases 匹配支持同义词、口头语、代称、英文词等节点级别名
        """
        results = []
        query_lower = query.lower()
        for node in self.nodes.values():
            score = 0
            if query_lower in node.name.lower():
                score += 10
            # V2.4: 节点级别名匹配（权重介于 name 和 id 之间）
            if not score and node.aliases:
                for alias in node.aliases:
                    if alias and query_lower in alias.lower():
                        score += 9
                        break
            if query_lower in node.id.lower():
                score += 8
            if query_lower in node.description.lower():
                score += 3
            if score > 0:
                results.append((score, node))
        results.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in results[:top_k]]

    def search_by_embedding(self, embedding: List[float], top_k: int = 5) -> List[GraphNode]:
        """Embedding 相似度搜索（备选）"""
        import numpy as np
        query_vec = np.array(embedding)
        results = []
        for node in self.nodes.values():
            if node.embedding:
                node_vec = np.array(node.embedding)
                sim = np.dot(query_vec, node_vec) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(node_vec) + 1e-8)
                results.append((sim, node))
        results.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in results[:top_k]]

    # ========== 图遍历（零 LLM）==========

    def get_neighbors(self, node_id: str, edge_type: Optional[str] = None,
                      direction: str = "out", depth: int = 1) -> List[GraphNode]:
        """获取邻居节点（支持类型过滤 + 深度遍历）"""
        if node_id not in self.nodes:
            return []
        visited = {node_id}
        current = {node_id}
        for _ in range(depth):
            next_level = set()
            for nid in current:
                adj = self._adj_out[nid] if direction == "out" else self._adj_in[nid]
                for edge in adj:
                    if edge_type is None or edge.edge_type == edge_type:
                        target = edge.to_node if direction == "out" else edge.from_node
                        if target not in visited:
                            visited.add(target)
                            next_level.add(target)
            current = next_level
        return [self.nodes[nid] for nid in visited if nid != node_id]

    def get_children(self, node_id: str, edge_type: str = "has_part") -> List[GraphNode]:
        """获取直接子节点（has_part 方向）"""
        return [self.nodes[edge.to_node]
                for edge in self._adj_out.get(node_id, [])
                if edge.edge_type == edge_type and edge.to_node in self.nodes]

    def get_parents(self, node_id: str, edge_type: str = "has_part") -> List[GraphNode]:
        """获取直接父节点"""
        return [self.nodes[edge.from_node]
                for edge in self._adj_in.get(node_id, [])
                if edge.edge_type == edge_type and edge.from_node in self.nodes]

    def get_next_steps(self, node_id: str) -> List[Tuple[GraphNode, float]]:
        """获取学习路径下一步（按权重排序）"""
        steps = [(self.nodes[edge.to_node], edge.weight)
                 for edge in self._adj_out.get(node_id, [])
                 if edge.edge_type == "next_step" and edge.to_node in self.nodes]
        steps.sort(key=lambda x: x[1], reverse=True)
        return steps

    def get_prerequisites(self, node_id: str) -> List[GraphNode]:
        """获取前置知识（prerequisite 入边）"""
        return [self.nodes[edge.from_node]
                for edge in self._adj_in.get(node_id, [])
                if edge.edge_type == "prerequisite" and edge.from_node in self.nodes]

    def get_domain_tree(self, node_id: str) -> List[GraphNode]:
        """获取域层级树（subdomain_of 方向）"""
        return self.get_children(node_id, "subdomain_of")

    # ========== Graph Diff（零 LLM）==========

    def get_all_node_names(self) -> Set[str]:
        return {node.name.lower() for node in self.nodes.values()}

    def get_all_node_ids(self) -> Set[str]:
        return set(self.nodes.keys())

    def diff(self, concept_names: Set[str]) -> Set[str]:
        """Graph Diff：返回不在图中的新概念（集合差运算）"""
        existing = self.get_all_node_names()
        existing.update(self.get_all_node_ids())
        return {c for c in concept_names if c.lower() not in existing}

    def find_similar_node(self, name: str, threshold: float = 0.6) -> Optional[GraphNode]:
        """名称相似度匹配：找到最相似的已有节点（零 LLM）"""
        name_lower = name.lower()
        best_score, best_node = 0, None
        for node in self.nodes.values():
            if name_lower in node.name.lower() or node.name.lower() in name_lower:
                score = 0.8
            else:
                words1 = set(name_lower.replace("-", " ").replace("_", " ").split())
                words2 = set(node.name.lower().replace("-", " ").replace("_", " ").split())
                score = len(words1 & words2) / len(words1 | words2) if words1 and words2 else 0
            if score > best_score and score >= threshold:
                best_score, best_node = score, node
        return best_node

    # ========== 序列化 ==========

    def to_dict(self) -> dict:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillGraph":
        graph = cls()
        for nid, ndata in data.get("nodes", {}).items():
            graph.add_node(GraphNode.from_dict(ndata))
        for edata in data.get("edges", []):
            # to_dict 序列化时用 "from"/"to"/"type"，反序列化映射回构造函数参数名
            graph.add_edge(GraphEdge(
                from_node=edata.get("from", ""),
                to_node=edata.get("to", ""),
                edge_type=edata.get("type", ""),
                weight=edata.get("weight", 1.0),
                metadata=edata.get("metadata", {}),
            ))
        return graph

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)

    @classmethod
    def load(cls, path: str) -> "SkillGraph":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(yaml.safe_load(f) or {})

    def stats(self) -> dict:
        edge_type_counts = {}
        for e in self.edges:
            edge_type_counts[e.edge_type] = edge_type_counts.get(e.edge_type, 0) + 1
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "domain_nodes": sum(1 for n in self.nodes.values() if n.node_type == "domain"),
            "concept_nodes": sum(1 for n in self.nodes.values() if n.node_type == "concept"),
            "skill_nodes": sum(1 for n in self.nodes.values() if n.node_type == "skill"),
            "edge_types": edge_type_counts
        }