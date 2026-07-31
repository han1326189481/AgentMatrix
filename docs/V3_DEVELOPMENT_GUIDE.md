# AgentMatrix V3 — Cognitive Agent Architecture 开发指南

> **版本**: V3.0.0-dev
> **日期**: 2026-07-22
> **依赖**: V2.1 Skill Engine（已完成）
> **核心原则**: Graph First, Engine Second — 任何新增模块优先考虑 Graph 数据结构，Engine 只是 Graph 的调用者

---

## 一、版本概述

### 1.1 一句话定位

AgentMatrix 不再只是"多个 Agent 协同工作"，而是一个能够**理解用户、按需规划、学习思维、持续进化**的 Personal Cognitive Agent。

### 1.2 Agent Operating Loop

```
传统 Agent:                    AgentMatrix V3:
                                
User                           User
  │                              │
  ▼                              ▼
LLM                           Personal Brain
  │                              │
  ▼                              ▼
Answer                        Cognitive Controller（按需调度）
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
               Knowledge    Decomposer    Reasoning
             Recommendation    +Planner      Graph
                    │            │            │
                    └────────────┼────────────┘
                                 ▼
                            Skill Graph
                                 │
                                 ▼
                           Workflow（5 Agent）
                                 │
                                 ▼
                              Review
                                 │
                                 ▼
                        Learning Engine
                                 │
                                 ▼
                         Patch Validator
                                 │
                                 ▼
                       [Skill Gap?] → Cloud
```

### 1.3 设计哲学

```
Graph First, Engine Second

Graph = 系统的大脑（数据结构 + 关系）
Engine = 大脑的调用者（调度 + 执行）

Graph 越来越重，Engine 越来越轻。
这是 V3 与 V2.1 最根本的架构差异。
```

### 1.4 两大设计原则

> 1. 任何新增模块是否降低了对云端大模型的依赖？
> 2. 任何新增模块是否增强了系统对同一用户的长期服务能力？

不满足这两条的设计，不进 V3。

### 1.5 六大核心 Graph（V3 真正的主角）

| Graph | 内容 | 核心操作 | 状态 |
|-------|------|----------|------|
| **Skill Graph** | 系统能力：概念节点 + typed edges | search / diff / traverse | 从 tree.yaml 升级 |
| **Capability Graph** | 用户能力：会做什么（不是知道什么） | proficiency / gap detection | **新建** |
| **Reasoning Graph** | 思维模式：怎么思考（不是思考什么） | pattern match / template inject | **新建** |
| **Intent Graph** | 当前任务链：会话时间序列 | intent tracking / domain clustering | **新建** |
| **Workflow Graph** | 任务拆解：可学习优化的步骤序列 | plan generation / step optimization | **新建** |
| **Memory Graph** | 长期记忆：用户偏好 + 历史决策 | context retrieval / preference evolution | 远期规划 |

### 1.6 六大 Engine（Graph 的调用者）

| Engine | 定位 | 调用的 Graph | 状态 |
|--------|------|-------------|------|
| Task Engine | 用户问题解析器 | 无（规则引擎） | **已有，停止迭代** |
| Skill Engine | 技能加载 + Prompt 构建 | Skill Graph | **已有，停止迭代** |
| Review Engine | 质量评审 | 无（规则引擎） | **已有，停止迭代** |
| Cognitive Controller | 按需调度大脑 | 所有 Graph | **新建** |
| Learning Engine | 自动学习闭环 | Skill Graph + Reasoning Graph | **新建** |
| Knowledge Recommendation | 精准知识推荐 | Skill Graph + Capability Graph | **新建** |

---

## 二、架构总览

### 2.1 目录结构（V3 目标态）

```
backend/core/
│
├── graphs/                          ← 新：Graph 层（系统核心）
│   ├── __init__.py
│   ├── skill_graph.py              ← Phase 1: 技能图谱
│   ├── skill_graph.yaml            ← 序列化数据
│   ├── graph_builder.py            ← Phase 1: YAML → Graph 迁移工具
│   ├── capability_graph.py         ← Phase 4: 用户能力图谱
│   ├── reasoning_graph.py          ← Phase 5: 推理模式图谱
│   ├── intent_graph.py             ← Phase 6: 意图时间线
│   └── workflow_graph.py           ← Phase 7: 工作流图谱
│
├── engines/                         ← 瘦身：Engine 只是 Graph 的调用者
│   ├── __init__.py
│   ├── task_engine.py              ← 已有，不变
│   ├── review_engine.py            ← 已有，不变
│   ├── template_engine.py          ← 已有，不变
│   ├── cognitive_controller.py     ← Phase 2: 调度大脑
│   ├── decomposer.py               ← Phase 3: 问题分解
│   ├── local_planner.py            ← Phase 3: 任务规划
│   ├── learning_engine.py          ← Phase 7: 学习引擎
│   ├── patch_validator.py          ← Phase 3: 永久守门人
│   └── knowledge_recommendation.py ← Phase 6: 知识推荐
│
├── personal_brain/                  ← 新：用户认知画像
│   ├── __init__.py
│   └── brain.py                    ← Phase 4: 个人智脑
│
├── skill_engine/                    ← 保留：V2.1 已有模块（不再扩展）
│   ├── skill_tree.py               ← 保留，GraphBuilder 的数据源
│   ├── skill_manager.py
│   ├── skill_learner.py            ← 保留，V3 新 LearningEngine 并行运行
│   ├── intent_cache.py
│   ├── intent_analyzer.py
│   ├── prompt_builder.py
│   └── models.py
│
├── workflow/                        ← 保留：5 Agent 流水线
│   └── service.py                  ← 改造：接入 CognitiveController
│
├── llm/                             ← 保留
├── knowledge/                       ← 保留
└── dynamic_router/                  ← 保留
```

### 2.2 数据流

```
User Input
  │
  ▼
Personal Brain ──→ 注入用户画像到 Context
  │
  ▼
Cognitive Controller ──→ 按 task_type + complexity 决定启用哪些引擎
  │
  ├── [chat] ──→ Task Engine ──→ Writer ──→ Answer
  │
  ├── [qa] ──→ Decomposer(SkillGraph.search) ──→ Writer ──→ Review
  │
  ├── [coding] ──→ Decomposer ──→ Writer ──→ Review
  │
  ├── [writing] ──→ Decomposer ──→ Writer ──→ Review ──→ Learning
  │
  ├── [planning] ──→ Decomposer + Planner(SkillGraph.get_children)
  │                    ──→ KnowledgeRecommendation
  │                    ──→ Writer ──→ Review ──→ Learning
  │
  └── [analysis] ──→ Decomposer + Planner
                       ──→ ReasoningGraph.match → inject pattern
                       ──→ Writer ──→ Review
                       ──→ [Skill Gap?] → Cloud
                       ──→ Learning
                            │
                            ▼
                       PatchValidator → SkillGraph.merge()
```

---

## 三、Phase 1: Skill Graph — 系统基石（4天）

**为什么是 Phase 1**: 所有后续 Graph 和 Engine 都依赖 Skill Graph 的数据结构。没有它，Decomposer、Planner、Learning、Recommendation 全部无法工作。

**依赖**: 无（V2.1 的 `tree.yaml` + 各域 `skill.yaml` 作为数据源）

**产出**:
- `graphs/skill_graph.py` — 核心数据结构
- `graphs/graph_builder.py` — 数据迁移工具
- `graphs/skill_graph.yaml` — 初始 Graph 序列化文件

### 3.1 数据模型

**文件**: `graphs/skill_graph.py`

```python
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

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "node_type": self.node_type, "domain": self.domain,
            "description": self.description, "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GraphNode":
        return cls(**{k: data.get(k, "" if k != "metadata" else {})
                      for k in ["id", "name", "node_type", "domain", "description", "metadata"]})


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
        """关键词匹配搜索"""
        results = []
        query_lower = query.lower()
        for node in self.nodes.values():
            score = 0
            if query_lower in node.name.lower():
                score += 10
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
            graph.add_edge(GraphEdge(**edata))
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
```

### 3.2 Graph Builder（数据迁移）

**文件**: `graphs/graph_builder.py`

```python
"""从 V2.1 tree.yaml + skill.yaml 构建 V3 Skill Graph"""

import os, yaml, logging
from .skill_graph import SkillGraph, GraphNode, GraphEdge

logger = logging.getLogger(__name__)

class GraphBuilder:
    """一次性迁移工具：YAML → Graph

    迁移策略:
    1. tree.yaml 的层级结构 → domain 节点 + subdomain_of 边
    2. 各域 skill.yaml 的 ontology.concepts → concept 节点 + related_to 边
    3. 手动补充 has_part / prerequisite / next_step 边（第一批）
    """

    def __init__(self, skills_dir: str = "prompts/skills"):
        self.skills_dir = skills_dir

    def build(self) -> SkillGraph:
        graph = SkillGraph()

        # 1. 加载 tree.yaml → domain 节点
        tree = self._load_yaml("tree.yaml")
        self._build_from_tree(graph, tree.get("tree", {}))

        # 2. 遍历所有 skill.yaml → concept 节点
        self._build_from_skills(graph)

        # 3. 手动补充关键边（根据领域知识，一次性补充）
        self._add_manual_edges(graph)

        logger.info(f"GraphBuilder: {graph.stats()}")
        return graph

    def _build_from_tree(self, graph: SkillGraph, tree: dict, parent_id: str = None):
        root = tree.get("root", tree)
        if isinstance(root, dict):
            node_id = root.get("id", "root")
            node = GraphNode(
                id=node_id, name=root.get("name", node_id),
                node_type="domain", domain=node_id,
            )
            graph.add_node(node)
            if parent_id:
                graph.add_edge(GraphEdge(
                    from_node=parent_id, to_node=node_id,
                    edge_type="subdomain_of"
                ))
            for child in root.get("children", []):
                self._build_from_tree(graph, {"root": child}, node_id)

    def _build_from_skills(self, graph: SkillGraph):
        for root, dirs, files in os.walk(self.skills_dir):
            if "_pending_patches" in root:
                continue
            for f in files:
                if f == "skill.yaml" and root != self.skills_dir:
                    skill = self._load_yaml(os.path.join(root, f))
                    if not skill:
                        continue
                    domain = skill.get("meta", {}).get("skill_id", "")
                    concepts = skill.get("knowledge", {}).get("ontology", {}).get("concepts", [])
                    for concept in concepts:
                        if not isinstance(concept, dict):
                            continue
                        term = concept.get("term", "")
                        if not term:
                            continue
                        node_id = term.lower().replace(" ", "_").replace("-", "_")
                        if node_id not in graph.nodes:
                            graph.add_node(GraphNode(
                                id=node_id, name=term,
                                node_type="concept", domain=domain,
                                description=concept.get("definition", ""),
                            ))
                        for related in concept.get("related", []):
                            related_id = related.lower().replace(" ", "_").replace("-", "_")
                            if related_id in graph.nodes:
                                graph.add_edge(GraphEdge(
                                    from_node=node_id, to_node=related_id,
                                    edge_type="related_to"
                                ))

    def _add_manual_edges(self, graph: SkillGraph):
        """手动补充关键关系边（第一批种子数据）"""
        manual_edges = [
            # AI 领域 has_part 关系
            ("agent", "memory", "has_part"),
            ("agent", "tool", "has_part"),
            ("agent", "multi", "has_part"),
            ("rag", "retrieval", "has_part"),
            ("rag", "embedding", "has_part"),
            ("rag", "chunking", "has_part"),
            # 学习路径
            ("llm", "rag", "next_step"),
            ("rag", "agent", "next_step"),
            ("agent", "multi", "next_step"),
            # 前置知识
            ("transformer", "llm", "prerequisite"),
            ("attention", "transformer", "prerequisite"),
            ("neural_network", "attention", "prerequisite"),
            # 加密领域
            ("classical", "quantum", "next_step"),
            ("quantum", "post_quantum", "next_step"),
        ]
        for from_id, to_id, edge_type in manual_edges:
            if from_id in graph.nodes and to_id in graph.nodes:
                graph.add_edge(GraphEdge(
                    from_node=from_id, to_node=to_id,
                    edge_type=edge_type
                ))

    def _load_yaml(self, path: str) -> dict:
        full_path = os.path.join(self.skills_dir, path) if not os.path.isabs(path) else path
        if not os.path.exists(full_path):
            return {}
        with open(full_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
```

### 3.3 任务清单

| # | 任务 | 文件 | 预估 |
|---|------|------|------|
| 1.1 | 创建 `graphs/` 目录，实现 `SkillGraph` 完整数据模型 | `graphs/skill_graph.py` | 1天 |
| 1.2 | 实现 `GraphBuilder`（YAML 迁移 + 手动补边） | `graphs/graph_builder.py` | 0.5天 |
| 1.3 | 运行迁移，生成初始 `skill_graph.yaml` | `graphs/skill_graph.yaml` | 0.5天 |
| 1.4 | 编写单元测试（搜索/遍历/Diff/序列化/边类型校验） | `tests/test_skill_graph.py` | 1天 |
| 1.5 | 在 `graphs/__init__.py` 中导出 + 全局单例 | `graphs/__init__.py` | 0.5天 |
| 1.6 | V2.1 全量回归测试（105项） | 全量回归 | 0.5天 |

### 3.4 验收标准

- [ ] `SkillGraph` 从现有数据迁移后节点数 >= 30
- [ ] 六种边类型全部通过 `__post_init__` 校验
- [ ] `search_by_name("Transformer")` 返回正确节点
- [ ] `get_neighbors("agent", "has_part")` 返回 ["memory", "tool", "multi"]
- [ ] `get_prerequisites("llm")` 返回 ["transformer"]
- [ ] `get_next_steps("rag")` 返回 [("agent", 1.0)]
- [ ] `diff({"Flash-Attention", "Self-Attention"})` 正确识别新概念
- [ ] `find_similar_node("flash attention")` 匹配到 "attention" 节点
- [ ] 序列化 → 反序列化 → 再序列化，数据一致
- [ ] V2.1 全量回归测试通过

---

## 四、Phase 2: Cognitive Controller — 调度大脑（3天）

**为什么是 Phase 2**: 在 Skill Graph 就位后，立刻需要调度器。没有 Controller，后续所有新模块接入后都会全量运行，性能倒退。Controller 必须在其他 Engine 之前完成。

**依赖**: Phase 1 (Skill Graph)

**产出**:
- `engines/cognitive_controller.py`
- 改造 `workflow/service.py`

### 4.1 核心逻辑

**文件**: `engines/cognitive_controller.py`

```python
"""Cognitive Controller — 系统调度大脑

职责: 根据任务类型 + 复杂度 + 用户画像，决定启用哪些引擎。
目标: 简单对话 < 50ms，复杂分析 < 200ms。
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PipelineDecision:
    """调度决策"""
    task_type: str
    engines: List[str]           # 要启用的引擎列表
    use_cloud: bool = False      # 是否走云端
    use_learning: bool = False   # 是否触发学习
    use_recommendation: bool = False  # 是否触发推荐
    use_reasoning: bool = False  # 是否注入推理模式
    complexity: float = 0.0
    reason: str = ""             # 决策理由


class CognitiveController:
    """认知调度器

    设计原则:
    - 简单对话只启用 Task + Skill，不启动 Planner/Learning/Cloud
    - 复杂分析启用全部引擎，但 Review/Cloud 仍按需
    - 引擎启用策略可配置，不硬编码
    """

    # 引擎启用策略（可配置）
    ENGINE_POLICIES = {
        # task_type: [always_enabled, optional]
        "chat":      (["task", "skill"], []),
        "qa":        (["task", "skill", "decomposer"], ["learning", "recommendation"]),
        "coding":    (["task", "skill"], ["decomposer"]),
        "writing":   (["task", "skill"], ["decomposer", "learning"]),
        "planning":  (["task", "skill", "decomposer", "planner"],
                      ["learning", "recommendation", "reasoning", "cloud"]),
        "analysis":  (["task", "skill", "decomposer", "planner"],
                      ["learning", "reasoning", "cloud"]),
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        # 允许覆盖默认策略
        if "engine_policies" in self.config:
            self.ENGINE_POLICIES.update(self.config["engine_policies"])

    def decide(self, task_profile, brain=None) -> PipelineDecision:
        """核心决策方法

        Args:
            task_profile: TaskEngine 的输出（TaskProfile）
            brain: PersonalBrain 实例（可选）

        Returns:
            PipelineDecision: 包含引擎列表和决策理由
        """
        task_type = task_profile.task_type.value
        complexity = getattr(task_profile, 'complexity', 0.0)
        confidence = getattr(task_profile, 'confidence', 0.5)

        always, optional = self.ENGINE_POLICIES.get(
            task_type, (["task", "skill"], []))

        engines = list(always)
        reasons = [f"task_type={task_type}"]

        # 复杂度驱动
        if complexity > 0.5:
            if "decomposer" not in engines:
                engines.append("decomposer")
            if "planner" not in engines:
                engines.append("planner")
            reasons.append(f"complexity={complexity:.2f} > 0.5")

        if complexity > 0.7:
            if "cloud" in optional:
                engines.append("cloud")
            if "reasoning" in optional:
                engines.append("reasoning")
            reasons.append(f"complexity={complexity:.2f} > 0.7, enabling cloud+reasoning")

        # 用户画像驱动
        if brain:
            if brain.learning_stage == "intermediate" and "recommendation" in optional:
                engines.append("recommendation")
                reasons.append("user learning_stage=intermediate")

            if brain.learning_stage == "advanced" and "reasoning" in optional:
                engines.append("reasoning")
                reasons.append("user learning_stage=advanced")

        # 低置信度 → 简化流程
        if confidence < 0.3:
            engines = [e for e in engines if e not in ("decomposer", "planner", "cloud")]
            reasons.append(f"low confidence={confidence:.2f}, simplified pipeline")

        # 学习触发条件
        use_learning = ("learning" in engines or
                        (complexity > 0.4 and "learning" in optional))

        return PipelineDecision(
            task_type=task_type,
            engines=engines,
            use_cloud="cloud" in engines,
            use_learning=use_learning,
            use_recommendation="recommendation" in engines,
            use_reasoning="reasoning" in engines,
            complexity=complexity,
            reason="; ".join(reasons)
        )

    def get_expected_latency(self, decision: PipelineDecision) -> str:
        """预估延迟"""
        engine_count = len(decision.engines)
        if engine_count <= 2:
            return "< 50ms"
        elif engine_count <= 4:
            return "< 100ms"
        elif engine_count <= 6:
            return "< 200ms"
        else:
            return "< 500ms"
```

### 4.2 WorkflowService 改造

**文件**: `workflow/service.py`（改造现有文件）

```python
# 改造要点：
# 1. execute() 入口注入 CognitiveController
# 2. 根据 PipelineDecision 决定执行哪些步骤
# 3. 保留原有 5 Agent 流水线作为默认路径

class WorkflowService:
    def __init__(self, ..., controller: CognitiveController = None):
        self.controller = controller or CognitiveController()

    async def execute(self, user_input: str, context: dict = None) -> WorkflowOutput:
        # 1. Task Engine 分类
        task_profile = self.task_engine.classify(user_input)

        # 2. Cognitive Controller 决策
        decision = self.controller.decide(task_profile, brain=self.brain)

        # 3. 按决策执行
        # ... 仅启用 decision.engines 中的引擎
```

### 4.3 任务清单

| # | 任务 | 预估 |
|---|------|------|
| 2.1 | 实现 `CognitiveController` + `PipelineDecision` | 1天 |
| 2.2 | 改造 `WorkflowService.execute()` 接入 Controller | 1天 |
| 2.3 | 测试（chat/qa/coding/writing/planning/analysis 六种引擎差异） | 0.5天 |
| 2.4 | 回归测试 | 0.5天 |

### 4.4 验收标准

- [ ] `chat` 任务仅启用 Task + Skill（2个引擎）
- [ ] `planning` 任务启用全部引擎（6+个引擎）
- [ ] `complexity > 0.7` 时自动启用 cloud + reasoning
- [ ] `confidence < 0.3` 时简化流程
- [ ] 简单对话耗时 < 50ms
- [ ] 每次决策附带 `reason` 说明

---

## 五、Phase 3: Patch Validator + Decomposer + Planner（4天）

**为什么 Phase 3**: Patch Validator 是长期稳定性的关键，必须在 Learning Engine 之前就位。Decomposer 和 Planner 依赖 Skill Graph 的搜索/遍历能力，与 Patch Validator 同时开发效率最高。

**依赖**: Phase 1 (Skill Graph)、Phase 2 (Cognitive Controller)

**产出**:
- `engines/patch_validator.py` — 永久守门人
- `engines/decomposer.py` — 问题分解器
- `engines/local_planner.py` — 任务规划器

### 5.1 Patch Validator（永久模块）

**文件**: `engines/patch_validator.py`

```python
"""Patch Validator — 防止知识污染的最后一道防线

这是一个永久模块，不是 LearningEngine 的子组件。
任何写入 Skill Graph 的操作都必须经过 Validator。

校验维度:
1. 冲突检查: 是否与已有知识矛盾
2. 重复检查: 是否已存在
3. 置信度检查: 概念名称是否有效
4. 完整性检查: 必要字段是否齐全
5. 来源检查: Patch 来源是否可信
"""

import re, logging
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """校验结果"""
    passed: bool
    patch_type: str                # "knowledge" | "reasoning" | "workflow" | "skill"
    patch_name: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class PatchValidator:
    """Patch 校验器 — 永久守门人

    规则:
    1. 概念名长度 2-60 字符
    2. 概念名不能是纯数字/纯符号
    3. 不能与已有节点重复
    4. 定义文本不能为空
    5. 推理模式至少 3 步
    6. 工作流至少 3 步
    """

    def __init__(self, graph):
        self.graph = graph  # SkillGraph 实例
        self.validation_log: List[ValidationResult] = []

    def validate_knowledge(self, patch) -> ValidationResult:
        """校验知识 Patch"""
        errors = []
        warnings = []

        # 1. 重复检查
        node_id = patch.concept_name.lower().replace(" ", "_").replace("-", "_")
        if node_id in self.graph.nodes:
            errors.append(f"重复概念: '{patch.concept_name}' 已存在")

        # 2. 长度检查
        if len(patch.concept_name) < 2:
            errors.append(f"概念名过短: '{patch.concept_name}'")
        if len(patch.concept_name) > 60:
            errors.append(f"概念名过长: {len(patch.concept_name)}字符")

        # 3. 有效性检查
        if not re.search(r'[\u4e00-\u9fff\w]{2,}', patch.concept_name):
            errors.append(f"概念名无效: '{patch.concept_name}' 缺少有意义的内容")

        # 4. 定义检查
        if not patch.definition or len(patch.definition.strip()) < 10:
            errors.append(f"定义过短或为空: '{patch.definition[:20]}...'")

        # 5. 相似节点警告
        similar = self.graph.find_similar_node(patch.concept_name, threshold=0.7)
        if similar and node_id not in self.graph.nodes:
            warnings.append(f"相似节点已存在: '{similar.name}' (id={similar.id})")

        result = ValidationResult(
            passed=len(errors) == 0,
            patch_type="knowledge",
            patch_name=patch.concept_name,
            errors=errors,
            warnings=warnings
        )
        self.validation_log.append(result)
        return result

    def validate_reasoning(self, patch) -> ValidationResult:
        """校验推理模式 Patch"""
        errors = []
        if len(patch.steps) < 3:
            errors.append(f"推理步骤不足: {len(patch.steps)} < 3")
        if not patch.pattern_name:
            errors.append("模式名称为空")

        result = ValidationResult(
            passed=len(errors) == 0,
            patch_type="reasoning",
            patch_name=patch.pattern_name,
            errors=errors
        )
        self.validation_log.append(result)
        return result

    def validate_workflow(self, patch) -> ValidationResult:
        """校验工作流 Patch"""
        errors = []
        if len(patch.steps) < 3:
            errors.append(f"工作流步骤不足: {len(patch.steps)} < 3")

        result = ValidationResult(
            passed=len(errors) == 0,
            patch_type="workflow",
            patch_name=patch.task_type,
            errors=errors
        )
        self.validation_log.append(result)
        return result

    def validate_skill(self, patch) -> ValidationResult:
        """校验技能 Patch"""
        errors = []
        if not patch.domain:
            errors.append("域名为空")

        result = ValidationResult(
            passed=len(errors) == 0,
            patch_type="skill",
            patch_name=patch.domain,
            errors=errors
        )
        self.validation_log.append(result)
        return result

    def get_stats(self) -> dict:
        """获取校验统计"""
        total = len(self.validation_log)
        passed = sum(1 for r in self.validation_log if r.passed)
        return {
            "total_validations": total,
            "passed": passed,
            "rejected": total - passed,
            "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "N/A"
        }
```

### 5.2 Decomposer

**文件**: `engines/decomposer.py`

```python
"""Decomposer — 基于 Skill Graph 的问题分解器（零 LLM）

策略:
1. 关键词提取（正则，非 LLM）
2. SkillGraph.search_by_name() 节点匹配
3. SkillGraph.get_children("has_part") 邻居扩展
4. SkillGraph.get_prerequisites() 前置检测
"""

import re, logging
from typing import List

logger = logging.getLogger(__name__)


class Decomposer:
    """将用户问题分解为相关 Skill 节点"""

    def __init__(self, graph):
        self.graph = graph

    def decompose(self, query: str, max_depth: int = 2) -> dict:
        """分解用户问题

        Returns:
            {
                "topic": "Multi-Agent",
                "matched_nodes": [GraphNode, ...],
                "sub_topics": [{"node": GraphNode, "relation": "has_part"}, ...],
                "prerequisites": [GraphNode, ...],
                "related": [GraphNode, ...],
                "confidence": 0.85
            }
        """
        # 1. 关键词提取
        keywords = self._extract_keywords(query)

        # 2. Graph 节点匹配
        matched = []
        for kw in keywords:
            nodes = self.graph.search_by_name(kw, top_k=3)
            matched.extend(nodes)

        # 去重
        seen = set()
        unique = []
        for n in matched:
            if n.id not in seen:
                seen.add(n.id)
                unique.append(n)

        if not unique:
            return {"topic": query, "matched_nodes": [], "sub_topics": [],
                    "prerequisites": [], "related": [], "confidence": 0.0}

        # 3. 邻居扩展（has_part）
        sub_topics = []
        for node in unique[:3]:
            for child in self.graph.get_children(node.id, "has_part"):
                sub_topics.append({"node": child, "relation": "has_part",
                                   "parent": node.name})

        # 4. 前置知识
        prerequisites = []
        for node in unique[:3]:
            prerequisites.extend(self.graph.get_prerequisites(node.id))

        # 5. 关联知识
        related = []
        for node in unique[:3]:
            neighbors = self.graph.get_neighbors(node.id, "related_to", depth=1)
            related.extend(neighbors[:5])

        confidence = min(0.95, 0.5 + len(unique) * 0.15)

        return {
            "topic": unique[0].name if unique else query,
            "matched_nodes": unique,
            "sub_topics": sub_topics,
            "prerequisites": prerequisites,
            "related": related,
            "confidence": round(confidence, 2)
        }

    def _extract_keywords(self, query: str) -> List[str]:
        """关键词提取（规则，零 LLM）"""
        keywords = []
        # 英文专有名词（大写开头）
        keywords.extend(re.findall(r'\b[A-Z][a-zA-Z]+\b', query))
        # 中文短语（2-4字）
        keywords.extend(re.findall(r'[\u4e00-\u9fff]{2,4}', query))
        # 驼峰命名
        keywords.extend(re.findall(r'\b[a-z]+(?:[A-Z][a-z]+)+\b', query))
        return list(set(keywords))
```

### 5.3 Local Planner

**文件**: `engines/local_planner.py`

```python
"""Local Planner — 基于 Skill Graph 的任务规划器（零 LLM）

策略:
1. 沿 has_part 边遍历，生成步骤序列
2. 无 Graph 匹配时使用通用模板兜底
3. 检测 Skill Gap（计划中是否有 Graph 未覆盖的步骤）
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class LocalPlanner:
    """将复杂任务分解为执行步骤"""

    def __init__(self, graph):
        self.graph = graph

    def plan(self, decomposer_result: dict) -> List[str]:
        """生成任务规划

        Args:
            decomposer_result: Decomposer.decompose() 的输出

        Returns:
            ["需求分析", "模块设计", "通信方案", "Memory设计", "部署方案"]
        """
        steps = []

        # 1. 从 Decomposer 结果中获取 sub_topics
        sub_topics = decomposer_result.get("sub_topics", [])
        if sub_topics:
            steps = [s["node"].name for s in sub_topics]
        else:
            # 2. 回退：搜索主题节点
            topic = decomposer_result.get("topic", "")
            matched = self.graph.search_by_name(topic, top_k=1)
            if matched:
                children = self.graph.get_children(matched[0].id, "has_part")
                steps = [c.name for c in children]

        # 3. 通用模板兜底
        if not steps:
            steps = self._fallback_plan(decomposer_result.get("topic", ""))

        return steps

    def _fallback_plan(self, topic: str) -> List[str]:
        return [
            f"{topic}概述与背景",
            f"{topic}核心概念",
            f"{topic}实现方案",
            f"{topic}最佳实践",
            f"{topic}总结与建议",
        ]

    def detect_skill_gap(self, plan_steps: List[str]) -> List[str]:
        """检测 Skill Gap：哪些步骤在 Graph 中没有对应节点"""
        return [step for step in plan_steps
                if not self.graph.search_by_name(step, top_k=1)]
```

### 5.4 任务清单

| # | 任务 | 文件 | 预估 |
|---|------|------|------|
| 3.1 | 实现 `PatchValidator`（5维校验 + 日志统计） | `engines/patch_validator.py` | 1天 |
| 3.2 | 实现 `Decomposer`（关键词提取 + Graph 匹配 + 邻居扩展） | `engines/decomposer.py` | 1天 |
| 3.3 | 实现 `LocalPlanner`（has_part 遍历 + 兜底模板 + Gap 检测） | `engines/local_planner.py` | 0.5天 |
| 3.4 | 接入 WorkflowService（Controller 调度） | `workflow/service.py` | 0.5天 |
| 3.5 | 编写测试 | `tests/test_phase3.py` | 1天 |

### 5.5 验收标准

- [ ] `PatchValidator` 拦截重复概念
- [ ] `PatchValidator` 拦截无效概念名（纯数字/过短/过长）
- [ ] `PatchValidator` 对相似节点产生警告
- [ ] `Decomposer.decompose("解释Transformer")` 返回正确子主题
- [ ] `Decomposer.decompose("你好")` 返回空结果（简单对话不分解）
- [ ] `LocalPlanner.plan()` 返回合理步骤序列
- [ ] `LocalPlanner.detect_skill_gap()` 正确识别缺失技能
- [ ] 分解 + 规划耗时 < 10ms

---

## 六、Phase 4: Capability Graph + Personal Brain（4天）

**依赖**: Phase 1 (Skill Graph)

**产出**:
- `graphs/capability_graph.py` — 用户能力图谱
- `personal_brain/brain.py` — 个人智脑
- MySQL 新表（`user_profile`、`user_capability`、`user_project`、`user_session_history`）

### 6.1 核心概念

```
Capability Graph ≠ Skill Graph

Skill Graph: 系统知道什么（客观知识）
Capability Graph: 用户会做什么（主观能力）

一个用户可能 Skill Graph 中有 "Transformer" 节点，
但 Capability Graph 中显示 proficiency = "theory"（只会理论，不会实践）。
```

### 6.2 数据模型

**文件**: `graphs/capability_graph.py`

```python
"""Capability Graph — 用户能力图谱

记录用户在每个 Skill 节点上的真实掌握程度。
与 Skill Graph 共享节点 ID，但附加用户维度的 proficiency 信息。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class Proficiency(str, Enum):
    NONE = "none"           # 未接触
    THEORY = "theory"       # 仅理论了解
    PRACTICE = "practice"   # 有实践经验
    PROFICIENT = "proficient"  # 熟练
    EXPERT = "expert"       # 专家


@dataclass
class CapabilityNode:
    """用户能力节点"""
    skill_node_id: str          # 对应 SkillGraph.nodes 的 id
    proficiency: Proficiency = Proficiency.NONE
    evidence: List[str] = field(default_factory=list)  # 证据列表
    last_practiced: Optional[str] = None  # 最后实践时间
    practice_count: int = 0     # 实践次数


class CapabilityGraph:
    """用户能力图谱 — 用户维度的 Skill Graph 子集"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.nodes: Dict[str, CapabilityNode] = {}

    def has(self, skill_node_id: str) -> bool:
        """用户是否已掌握某技能"""
        node = self.nodes.get(skill_node_id)
        return node is not None and node.proficiency not in (Proficiency.NONE,)

    def get_proficiency(self, skill_node_id: str) -> Proficiency:
        node = self.nodes.get(skill_node_id)
        return node.proficiency if node else Proficiency.NONE

    def update(self, skill_node_id: str, proficiency: Proficiency,
               evidence: str = ""):
        """更新能力"""
        if skill_node_id not in self.nodes:
            self.nodes[skill_node_id] = CapabilityNode(
                skill_node_id=skill_node_id, proficiency=proficiency)
        else:
            self.nodes[skill_node_id].proficiency = proficiency
        if evidence:
            self.nodes[skill_node_id].evidence.append(evidence)
        self.nodes[skill_node_id].practice_count += 1

    def get_gaps(self, skill_graph) -> List[str]:
        """获取能力缺口：Skill Graph 中有但用户未掌握的节点"""
        gaps = []
        for node_id in skill_graph.nodes:
            cap = self.nodes.get(node_id)
            if not cap or cap.proficiency in (Proficiency.NONE, Proficiency.THEORY):
                gaps.append(node_id)
        return gaps

    def get_ready_for_next(self, skill_graph) -> List[str]:
        """获取可以学习的下一步（prerequisite 已满足）"""
        ready = []
        for node_id in skill_graph.nodes:
            if self.has(node_id):
                continue
            prereqs = skill_graph.get_prerequisites(node_id)
            if all(self.has(p.id) for p in prereqs):
                ready.append(node_id)
        return ready
```

### 6.3 Personal Brain

**文件**: `personal_brain/brain.py`

```python
"""Personal Brain — 用户认知画像

七维画像:
1. Identity   — 身份（学生/开发者/管理者）
2. Goal       — 长期目标
3. Preference — 表达偏好
4. Capability — 能力图谱
5. Project    — 当前项目
6. Memory     — 关键记忆
7. Context    — 会话上下文
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from graphs.capability_graph import CapabilityGraph


@dataclass
class UserProfile:
    user_id: str
    display_name: str = ""
    identity: str = ""              # "student" | "developer" | "researcher"
    long_term_goals: List[str] = field(default_factory=list)
    preferences: Dict = field(default_factory=dict)
    expression_style: str = ""      # "concise_technical" | "verbose_explanatory"
    learning_stage: str = ""        # "beginner" | "intermediate" | "advanced"


class PersonalBrain:
    """个人智脑 — 系统的用户感知层"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.profile = self._load_profile()
        self.capability = CapabilityGraph(user_id)

    def build_context(self) -> str:
        """构建注入 Prompt 的上下文字符串"""
        parts = []
        if self.profile.identity:
            parts.append(f"用户身份: {self.profile.identity}")
        if self.profile.long_term_goals:
            parts.append(f"长期目标: {', '.join(self.profile.long_term_goals)}")
        if self.profile.preferences:
            prefs = ", ".join(f"{k}={v}" for k, v in self.profile.preferences.items())
            parts.append(f"偏好: {prefs}")
        if self.profile.expression_style:
            parts.append(f"表达风格: {self.profile.expression_style}")
        return "\n".join(parts)

    def update_from_session(self, session_data: dict):
        """从会话中更新画像"""
        # 更新能力图谱
        skill_nodes = session_data.get("skill_nodes", [])
        for node_id in skill_nodes:
            self.capability.update(node_id, "practice",
                                   evidence=f"会话 {session_data.get('session_id')}")

    def _load_profile(self) -> UserProfile:
        # TODO: 从 MySQL 加载
        return UserProfile(user_id=self.user_id)
```

### 6.4 MySQL 表

```sql
CREATE TABLE user_profile (
    user_id VARCHAR(64) PRIMARY KEY,
    display_name VARCHAR(128),
    identity VARCHAR(32),
    long_term_goals JSON,
    preferences JSON,
    expression_style VARCHAR(32),
    learning_stage VARCHAR(32),
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW()
);

CREATE TABLE user_capability (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64),
    skill_node_id VARCHAR(128),
    proficiency VARCHAR(16),
    evidence JSON,
    practice_count INT DEFAULT 0,
    last_practiced DATETIME,
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),
    UNIQUE KEY uk_user_skill (user_id, skill_node_id)
);

CREATE TABLE user_project (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64),
    project_name VARCHAR(256),
    role VARCHAR(64),
    status VARCHAR(32),
    created_at DATETIME DEFAULT NOW()
);

CREATE TABLE user_session_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64),
    session_id VARCHAR(64),
    question TEXT,
    answer_summary TEXT,
    task_type VARCHAR(32),
    skill_nodes JSON,
    review_score DECIMAL(3,2),
    created_at DATETIME DEFAULT NOW(),
    INDEX idx_user_time (user_id, created_at)
);
```

### 6.5 任务清单

| # | 任务 | 预估 |
|---|------|------|
| 4.1 | 创建 MySQL 四表 | 0.5天 |
| 4.2 | 实现 `CapabilityGraph`（proficiency + gap + ready_for_next） | 1天 |
| 4.3 | 实现 `PersonalBrain`（profile + context_build + session_update） | 1天 |
| 4.4 | 接入 WorkflowService（Context 注入 + 会话更新） | 0.5天 |
| 4.5 | 编写测试 | 0.5天 |
| 4.6 | 回归测试 | 0.5天 |

---

## 七、Phase 5: Reasoning Graph — 最大创新点（4天）

**为什么是 Phase 5 且优先级提前**: 这是 V3 最大的创新点。Learning 不再只是学 Knowledge，而是学 Reasoning。Reasoning Graph 让系统从"越来越博学"变成"越来越聪明"。

**依赖**: Phase 1 (Skill Graph)、Phase 2 (Cognitive Controller)

**产出**:
- `graphs/reasoning_graph.py` — 推理模式图谱
- 接入 Writer Agent（推理模式注入）

### 7.1 核心概念

```
传统 Learning:               Reasoning Pattern Learning:

学的是: Knowledge            学的是: Thinking
图的是: "Transformer 是什么"   图的是: "为什么这样分析？用了哪些步骤？"
产物: 概念节点                 产物: 思维模板
效果: 越来越博学              效果: 越来越聪明

Reasoning Graph 的节点不是"知识"，而是"思维方式"。
```

### 7.2 数据模型

**文件**: `graphs/reasoning_graph.py`

```python
"""Reasoning Graph — 推理模式图谱

这是 V3 最大的创新点。
学习的不再是 Knowledge，而是 Reasoning Pattern。

节点类型:
- analysis_pattern    : 分析类模式（对比分析、因果分析、SWOT分析）
- writing_pattern    : 写作类模式（论证、叙事、说明）
- coding_pattern     : 编码类模式（设计→实现→测试→优化）
- decision_pattern   : 决策类模式（评估→权衡→选择→验证）
- explanation_pattern: 解释类模式（定义→原理→举例→总结）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import re


@dataclass
class ReasoningNode:
    """推理模式节点"""
    pattern_id: str                    # "comparison_analysis"
    pattern_name: str                  # "对比分析模式"
    pattern_type: str                  # "analysis_pattern"
    steps: List[str]                   # ["背景", "维度定义", "逐维对比", "总结"]
    applicable_domains: List[str] = field(default_factory=list)
    applicable_task_types: List[str] = field(default_factory=list)
    template: str = ""                 # Prompt 模板
    usage_count: int = 0
    avg_effectiveness: float = 0.0     # 平均效果评分

    def build_prompt(self, user_task: str) -> str:
        """用推理模式构建 Prompt"""
        step_instructions = "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(self.steps)
        )
        return f"""请按照以下推理结构组织你的回答：

{step_instructions}

用户问题: {user_task}

请严格遵循上述结构，每个部分都要有实质性内容。"""


class ReasoningGraph:
    """推理模式图谱 — 思维方式的图结构

    边类型:
    - applicable_to: 模式适用于某领域
    - derived_from : 从哪个模式演化而来
    - composed_of  : 由哪些子模式组成
    - alternative_to: 替代模式
    """

    # 预置推理模式（种子数据）
    PRESET_PATTERNS = {
        "comparison_analysis": ReasoningNode(
            pattern_id="comparison_analysis",
            pattern_name="对比分析模式",
            pattern_type="analysis_pattern",
            steps=["背景与问题", "对比维度定义", "逐维对比分析", "优劣总结", "选择建议"],
            applicable_domains=["tech", "business"],
            applicable_task_types=["analysis", "planning"],
            template="## 背景\n## 对比维度\n## 逐维分析\n## 总结\n## 建议"
        ),
        "problem_solution": ReasoningNode(
            pattern_id="problem_solution",
            pattern_name="问题解决模式",
            pattern_type="analysis_pattern",
            steps=["问题定义", "原因分析", "方案设计", "方案评估", "实施建议"],
            applicable_domains=["tech", "daily"],
            applicable_task_types=["analysis", "coding"],
            template="## 问题\n## 原因\n## 方案\n## 评估\n## 建议"
        ),
        "concept_explanation": ReasoningNode(
            pattern_id="concept_explanation",
            pattern_name="概念解释模式",
            pattern_type="explanation_pattern",
            steps=["定义", "核心原理", "关键特性", "应用场景", "举例说明"],
            applicable_domains=["tech", "ai"],
            applicable_task_types=["qa"],
            template="## 定义\n## 原理\n## 特性\n## 应用\n## 举例"
        ),
        "argumentative_writing": ReasoningNode(
            pattern_id="argumentative_writing",
            pattern_name="论证写作模式",
            pattern_type="writing_pattern",
            steps=["观点提出", "论据支撑", "反驳与回应", "深化论证", "结论"],
            applicable_domains=["business", "daily"],
            applicable_task_types=["writing"],
            template="## 观点\n## 论据\n## 回应\n## 深化\n## 结论"
        ),
        "code_design_implement": ReasoningNode(
            pattern_id="code_design_implement",
            pattern_name="编码设计实现模式",
            pattern_type="coding_pattern",
            steps=["需求分析", "架构设计", "核心实现", "边界处理", "测试验证"],
            applicable_domains=["tech"],
            applicable_task_types=["coding"],
            template="## 分析\n## 设计\n## 实现\n## 边界\n## 测试"
        ),
    }

    def __init__(self):
        self.patterns: Dict[str, ReasoningNode] = {}
        # 加载预置模式
        for pid, pattern in self.PRESET_PATTERNS.items():
            self.patterns[pid] = pattern

    def match(self, task_type: str, domain: str = "",
              keywords: List[str] = None) -> Optional[ReasoningNode]:
        """匹配最佳推理模式

        匹配优先级:
        1. task_type + domain 完全匹配
        2. task_type 匹配
        3. domain 匹配
        4. 关键词匹配
        """
        candidates = []

        for pattern in self.patterns.values():
            score = 0
            if task_type in pattern.applicable_task_types:
                score += 5
            if domain and domain in pattern.applicable_domains:
                score += 3
            if keywords:
                for kw in keywords:
                    if kw in pattern.pattern_name:
                        score += 2
            if score > 0:
                candidates.append((score, pattern))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def register(self, pattern: ReasoningNode):
        """注册新的推理模式"""
        self.patterns[pattern.pattern_id] = pattern

    def extract_from_text(self, text: str) -> Optional[ReasoningNode]:
        """从 Writer 输出中提取推理模式

        检测 Markdown 结构模式:
        - "背景 → 分析 → 举例 → 总结"
        - "问题 → 原因 → 方案 → 验证"
        - "定义 → 原理 → 应用 → 对比"
        """
        headers = re.findall(r'^#{1,3}\s+(.+?)$', text, re.MULTILINE)
        if len(headers) < 3:
            return None

        # 匹配已知模式关键词
        patterns = {
            "background_analysis_example_summary": ["背景", "分析", "举例", "总结"],
            "problem_cause_solution_verify": ["问题", "原因", "方案", "验证"],
            "definition_principle_application_compare": ["定义", "原理", "应用", "对比"],
            "swot_analysis": ["优势", "劣势", "机会", "威胁"],
        }

        for pattern_id, keywords in patterns.items():
            matched = []
            for kw in keywords:
                if any(kw in h for h in headers):
                    matched.append(kw)
            if len(matched) >= 3:
                return ReasoningNode(
                    pattern_id=pattern_id,
                    pattern_name=f"自动提取-{pattern_id}",
                    pattern_type="analysis_pattern",
                    steps=matched,
                    template="\n".join(f"## {s}" for s in matched)
                )

        return None

    def get_all_patterns(self) -> List[ReasoningNode]:
        return list(self.patterns.values())

    def stats(self) -> dict:
        return {
            "total_patterns": len(self.patterns),
            "by_type": {
                ptype: sum(1 for p in self.patterns.values()
                          if p.pattern_type == ptype)
                for ptype in set(p.pattern_type for p in self.patterns.values())
            },
            "most_used": sorted(self.patterns.values(),
                               key=lambda p: p.usage_count, reverse=True)[:3]
        }
```

### 7.3 接入 Writer Agent

```python
# agents/writer/agent.py 改造要点：
# 1. 接收 ReasoningPattern
# 2. 如果有匹配的推理模式，注入到 Prompt 中
# 3. 保持原有生成逻辑不变

class WriterAgent:
    def execute(self, input_data: dict, reasoning_pattern=None) -> str:
        if reasoning_pattern:
            reasoning_instruction = reasoning_pattern.build_prompt(
                input_data.get("user_input", ""))
            # 注入到 system prompt 或 user prompt 中
            input_data["reasoning_instruction"] = reasoning_instruction
        # ... 原有生成逻辑
```

### 7.4 任务清单

| # | 任务 | 预估 |
|---|------|------|
| 5.1 | 实现 `ReasoningGraph` + 5种预置模式 | 1天 |
| 5.2 | 实现 `extract_from_text()`（从 Writer 输出提取模式） | 0.5天 |
| 5.3 | 接入 Writer Agent（推理模式注入） | 1天 |
| 5.4 | 接入 Cognitive Controller（reasoning 引擎调度） | 0.5天 |
| 5.5 | 编写测试（模式匹配 + 提取 + 注入效果） | 1天 |

### 7.5 验收标准

- [ ] 5种预置推理模式正确加载
- [ ] `match(task_type="analysis", domain="tech")` 返回 "对比分析模式"
- [ ] `match(task_type="coding")` 返回 "编码设计实现模式"
- [ ] `extract_from_text()` 从 Markdown 输出中正确提取模式
- [ ] Writer Agent 注入推理模式后输出结构更清晰
- [ ] 推理模式匹配耗时 < 5ms

---

## 八、Phase 6: Knowledge Recommendation（3天）

**依赖**: Phase 1 (Skill Graph)、Phase 4 (Capability Graph + Personal Brain)

**产出**:
- `engines/knowledge_recommendation.py`
- `graphs/intent_graph.py` — 意图时间线
- `GET /api/v1/recommend` 端点

### 8.1 核心原则

```
Knowledge Recommendation ≠ Demand Prediction

推荐不是"猜用户想干什么"，而是基于真实数据和图谱关系的推导。

推荐来源（仅四类，不猜测）:
1. 当前任务: has_part 子节点（你正在学 Agent，建议了解 Memory）
2. Goal: 长期目标的 prerequisite 前置知识（你想学 Agent 开发，需要先学 RAG）
3. Capability: 能力图谱的缺口（你理论了解但没实践过的技能）
4. Skill Graph: next_step 学习路径（学完 K8S 推荐学 Service Mesh）
```

### 8.2 核心实现

**文件**: `engines/knowledge_recommendation.py`

```python
"""Knowledge Recommendation — 基于 Graph Traversal 的精准推荐（零 LLM）"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class KnowledgeRecommendation:
    """知识介入引擎 — 仅基于真实数据推导，不猜测用户意图"""

    def __init__(self, skill_graph, brain=None):
        self.skill_graph = skill_graph
        self.brain = brain

    def recommend(self, current_task: str, active_nodes: List[str],
                  limit: int = 5) -> List[dict]:
        """基于当前上下文推荐知识

        Args:
            current_task: 用户当前问题
            active_nodes: Decomposer 匹配到的 Skill Graph 节点 ID 列表
            limit: 最大推荐数

        Returns:
            [{"type": "sub_topic", "node": "Memory", "reason": "...", "priority": 0.8}, ...]
        """
        recommendations = []

        # 1. 当前任务的子主题（has_part）
        for node_id in active_nodes:
            children = self.skill_graph.get_children(node_id, "has_part")
            for child in children:
                if not self._user_has(child.id):
                    recommendations.append({
                        "type": "sub_topic",
                        "node": child.name,
                        "node_id": child.id,
                        "reason": f"当前主题 '{node_id}' 的组成部分",
                        "priority": 0.8
                    })

        # 2. 学习路径下一步（next_step）
        for node_id in active_nodes:
            next_steps = self.skill_graph.get_next_steps(node_id)
            for next_node, weight in next_steps:
                if not self._user_has(next_node.id):
                    recommendations.append({
                        "type": "next_step",
                        "node": next_node.name,
                        "node_id": next_node.id,
                        "reason": f"'{node_id}' 学习路径的下一步",
                        "priority": weight
                    })

        # 3. 能力缺口（Capability Graph）
        if self.brain:
            gaps = self.brain.capability.get_gaps(self.skill_graph)
            for gap_id in gaps[:5]:
                node = self.skill_graph.get_node(gap_id)
                if node:
                    recommendations.append({
                        "type": "capability_gap",
                        "node": node.name,
                        "node_id": gap_id,
                        "reason": "能力图谱中的缺口",
                        "priority": 0.6
                    })

        # 4. 目标相关的前置知识
        if self.brain and self.brain.profile.long_term_goals:
            for goal in self.brain.profile.long_term_goals:
                goal_nodes = self.skill_graph.search_by_name(goal, top_k=1)
                if goal_nodes:
                    prereqs = self.skill_graph.get_prerequisites(goal_nodes[0].id)
                    for prereq in prereqs:
                        if not self._user_has(prereq.id):
                            recommendations.append({
                                "type": "goal_prerequisite",
                                "node": prereq.name,
                                "node_id": prereq.id,
                                "reason": f"长期目标 '{goal}' 的前置知识",
                                "priority": 0.7
                            })

        # 去重 + 按优先级排序
        seen = set()
        unique = []
        for r in recommendations:
            if r["node_id"] not in seen:
                seen.add(r["node_id"])
                unique.append(r)

        return sorted(unique, key=lambda r: r["priority"], reverse=True)[:limit]

    def _user_has(self, node_id: str) -> bool:
        if self.brain:
            return self.brain.capability.has(node_id)
        return False

    def should_intervene(self) -> bool:
        """判断是否应该介入推荐

        介入条件:
        - 连续3次以上相关领域提问
        - Intent Graph 显示学习路径
        """
        if not self.brain:
            return False
        # TODO: 检查 Intent Graph 连续领域
        return False
```

### 8.3 任务清单

| # | 任务 | 预估 |
|---|------|------|
| 6.1 | 实现 `KnowledgeRecommendation`（四类推荐来源） | 1天 |
| 6.2 | 实现 `IntentGraph`（会话历史时间序列） | 1天 |
| 6.3 | 新增 API `GET /api/v1/recommend` | 0.5天 |
| 6.4 | 测试 | 0.5天 |

---

## 九、Phase 7: Learning Engine V3（3天）

**依赖**: Phase 1-6 全部

**产出**: `engines/learning_engine.py`（Graph-based 重构版）

### 9.1 核心逻辑

**文件**: `engines/learning_engine.py`

```python
"""Learning Engine V3 — Graph-based 自动学习闭环

V3 与 V2.1 SkillLearner 的核心区别:
- V2.1: 基于反馈收集，手动审核
- V3:  基于 Graph Diff，自动发现 + PatchValidator 守门

流程:
Writer Output
  → ConceptExtractor（规则提取，零 LLM）
  → SkillGraph.diff()（集合差，零 LLM）
  → PatchGenerator（生成 Patch）
  → PatchValidator（冲突/重复/置信度检查）
  → SkillGraph.merge()（安全合并）
  → [复杂概念] → DeepSeek 兜底分析
"""

import re, logging
from typing import List, Set, Optional
from engines.patch_validator import PatchValidator

logger = logging.getLogger(__name__)


class LearningEngine:
    """本地优先的学习引擎

    核心原则:
    1. 90% 操作零 LLM（Graph Diff + 名称匹配）
    2. 仅复杂概念走 DeepSeek 兜底
    3. 所有 Patch 必须通过 PatchValidator
    4. 只学习高质量回答（review_score >= 0.70）
    """

    def __init__(self, skill_graph, reasoning_graph=None,
                 validator: PatchValidator = None):
        self.skill_graph = skill_graph
        self.reasoning_graph = reasoning_graph
        self.validator = validator or PatchValidator(skill_graph)
        self.deepseek_enabled = True

    def learn(self, user_task: str, writer_output: str,
              skill_path: List[str], review_score: float) -> dict:
        """从一次回答中学习

        Returns:
            {
                "knowledge_patches": [...],
                "reasoning_patches": [...],
                "workflow_patches": [...],
                "deepseek_used": False,
                "validated": 3,
                "rejected": 1
            }
        """
        result = {
            "knowledge_patches": [],
            "reasoning_patches": [],
            "workflow_patches": [],
            "deepseek_used": False,
            "validated": 0,
            "rejected": 0
        }

        if review_score < 0.70:
            return result

        # 1. 知识提取 + Graph Diff
        concepts = self._extract_concepts(writer_output)
        new_concepts = self.skill_graph.diff(concepts)

        for concept in new_concepts:
            parent = self.skill_graph.find_similar_node(concept)
            if parent:
                patch = self._make_knowledge_patch(concept, parent, skill_path)
            else:
                patch = self._deepseek_analyze(concept, writer_output)
                if patch:
                    result["deepseek_used"] = True

            if patch:
                validation = self.validator.validate_knowledge(patch)
                if validation.passed:
                    result["knowledge_patches"].append(patch)
                    result["validated"] += 1
                else:
                    result["rejected"] += 1

        # 2. 推理模式提取
        if self.reasoning_graph:
            pattern = self.reasoning_graph.extract_from_text(writer_output)
            if pattern:
                validation = self.validator.validate_reasoning(pattern)
                if validation.passed:
                    result["reasoning_patches"].append(pattern)
                    result["validated"] += 1
                else:
                    result["rejected"] += 1

        # 3. 工作流提取
        workflow = self._extract_workflow(writer_output)
        if workflow:
            validation = self.validator.validate_workflow(workflow)
            if validation.passed:
                result["workflow_patches"].append(workflow)
                result["validated"] += 1
            else:
                result["rejected"] += 1

        return result

    def _extract_concepts(self, text: str) -> Set[str]:
        """从文本中提取概念（规则，零 LLM）"""
        concepts = set()
        # Markdown 标题
        headers = re.findall(r'^#{1,3}\s+(.+?)$', text, re.MULTILINE)
        concepts.update(h.strip() for h in headers if 3 < len(h.strip()) < 50)
        # 驼峰命名
        concepts.update(re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', text))
        # 下划线命名
        concepts.update(re.findall(r'\b([a-z]+(?:_[a-z]+)+)\b', text))
        # 中文书名号
        concepts.update(re.findall(r'《(.+?)》', text))
        return concepts

    def _make_knowledge_patch(self, concept: str, parent, skill_path: List[str]):
        """创建知识 Patch"""
        from core.skill_engine.models import KnowledgePatch
        return KnowledgePatch(
            concept_name=concept,
            definition=f"自动提取自回答内容（关联: {parent.name}）",
            domain=skill_path[-1] if skill_path else "root",
            related_concepts=[parent.name]
        )

    def _extract_workflow(self, text: str):
        """提取工作流模式"""
        from core.skill_engine.models import WorkflowPatch
        steps = re.findall(r'^\d+\.\s*\*?\*?(.+?)\*?\*?\s*$', text, re.MULTILINE)
        if len(steps) >= 3:
            return WorkflowPatch(
                task_type="detected", steps=steps[:7],
                optimization="自动提取"
            )
        return None

    def _deepseek_analyze(self, concept: str, context: str):
        """DeepSeek 兜底（仅在本地无法判断时调用）"""
        if not self.deepseek_enabled:
            return None
        # TODO: 调用 DeepSeek API 分析概念
        return None

    def apply_patches(self, patches: dict) -> int:
        """应用已校验的 Patch 到 Skill Graph"""
        count = 0
        for kp in patches.get("knowledge_patches", []):
            node_id = kp.concept_name.lower().replace(" ", "_").replace("-", "_")
            if node_id not in self.skill_graph.nodes:
                from graphs.skill_graph import GraphNode, GraphEdge
                self.skill_graph.add_node(GraphNode(
                    id=node_id, name=kp.concept_name,
                    node_type="concept", domain=kp.domain,
                    description=kp.definition,
                ))
                for related in kp.related_concepts:
                    related_id = related.lower().replace(" ", "_").replace("-", "_")
                    if related_id in self.skill_graph.nodes:
                        self.skill_graph.add_edge(GraphEdge(
                            from_node=node_id, to_node=related_id,
                            edge_type="related_to"
                        ))
                count += 1
        return count
```

### 9.2 任务清单

| # | 任务 | 预估 |
|---|------|------|
| 7.1 | 实现 `LearningEngine`（Graph Diff + PatchValidator + DeepSeek 兜底） | 1天 |
| 7.2 | 接入 WorkflowService（Review 之后自动触发） | 0.5天 |
| 7.3 | 接入 ReasoningGraph（推理模式提取 + 注册） | 0.5天 |
| 7.4 | 编写测试（Graph Diff 准确性 + Validator 拦截 + 端到端学习） | 1天 |

---

## 十、API 规范

### 10.1 新增端点

| 方法 | 路径 | 说明 | Phase |
|------|------|------|-------|
| GET | `/api/v1/graph/stats` | Skill Graph 统计信息 | Phase 1 |
| GET | `/api/v1/graph/search?q=Transformer` | Skill Graph 搜索 | Phase 1 |
| GET | `/api/v1/recommend?user_id=xxx` | 获取知识推荐 | Phase 6 |
| GET | `/api/v1/brain/{user_id}` | 获取用户画像 | Phase 4 |
| GET | `/api/v1/brain/{user_id}/capability` | 获取能力图谱 | Phase 4 |
| PATCH | `/api/v1/brain/{user_id}/capability` | 更新能力等级 | Phase 4 |
| GET | `/api/v1/reasoning/patterns` | 获取推理模式列表 | Phase 5 |
| POST | `/api/v1/learning/trigger` | 手动触发学习 | Phase 7 |
| GET | `/api/v1/learning/stats` | 学习统计 | Phase 7 |

### 10.2 响应示例

```json
// GET /api/v1/recommend?user_id=default
{
  "recommendations": [
    {
      "type": "next_step",
      "node": "agent",
      "node_id": "agent",
      "reason": "'rag' 学习路径的下一步",
      "priority": 0.90
    },
    {
      "type": "capability_gap",
      "node": "multi",
      "node_id": "multi",
      "reason": "能力图谱中的缺口",
      "priority": 0.60
    }
  ],
  "count": 2,
  "generated_at": "2026-07-22T10:00:00"
}
```

---

## 十一、测试策略

### 11.1 测试层次

```
Layer 1: 单元测试（每个模块独立测试）
  ├── tests/test_skill_graph.py          — Graph 数据模型 + 六种边类型
  ├── tests/test_graph_builder.py        — YAML → Graph 迁移
  ├── tests/test_cognitive_controller.py — 六种 task_type 调度差异
  ├── tests/test_patch_validator.py      — 五维校验 + 拦截统计
  ├── tests/test_decomposer.py           — 问题分解 + 关键词提取
  ├── tests/test_local_planner.py        — 任务规划 + Gap 检测
  ├── tests/test_capability_graph.py     — proficiency + gap + ready
  ├── tests/test_personal_brain.py       — 画像 + context 构建
  ├── tests/test_reasoning_graph.py      — 模式匹配 + 提取 + 注入
  ├── tests/test_knowledge_recommendation.py — 四类推荐来源
  └── tests/test_learning_engine.py      — Graph Diff + Validator + 端到端

Layer 2: 集成测试
  └── tests/test_v3_integration.py       — 全链路 + Controller 调度验证

Layer 3: 回归测试
  └── V2.1 全量测试套件（105项，保持不变）
```

### 11.2 关键测试用例

| 测试场景 | 预期结果 |
|----------|----------|
| Graph 搜索 "Transformer" | 返回正确节点 |
| Graph Diff 区分新旧概念 | 返回仅新概念 |
| Controller chat 任务 | 仅启用 Task + Skill |
| Controller planning 任务 | 启用全部引擎 |
| Controller complexity > 0.7 | 启用 cloud + reasoning |
| Validator 拦截重复概念 | 返回 passed=False |
| Validator 拦截无效概念名 | 返回 passed=False |
| Decomposer 分解 "Transformer" | 返回子主题 |
| Decomposer 分解 "你好" | 返回空结果 |
| Planner 生成步骤 | 返回合理序列 |
| Reasoning 匹配 analysis | 返回 "对比分析模式" |
| Reasoning 注入 Writer | 输出结构更清晰 |
| Learning 高质量回答 | 生成 Patch |
| Learning 低质量回答 | 跳过 |
| 简单对话耗时 | < 50ms |
| 复杂分析耗时 | < 200ms |

---

## 十二、从 V2.1 迁移

### 12.1 文件变更清单

```
新增目录:
  backend/core/graphs/                     ← Graph 层
  backend/core/engines/                    ← Engine 层（从 skill_engine 拆出）
  backend/core/personal_brain/             ← 用户画像

新增文件:
  graphs/__init__.py
  graphs/skill_graph.py                   ← Phase 1
  graphs/skill_graph.yaml                 ← Phase 1
  graphs/graph_builder.py                 ← Phase 1
  graphs/capability_graph.py              ← Phase 4
  graphs/reasoning_graph.py               ← Phase 5
  graphs/intent_graph.py                  ← Phase 6
  graphs/workflow_graph.py                ← Phase 7

  engines/__init__.py
  engines/cognitive_controller.py         ← Phase 2
  engines/patch_validator.py              ← Phase 3
  engines/decomposer.py                   ← Phase 3
  engines/local_planner.py                ← Phase 3
  engines/knowledge_recommendation.py     ← Phase 6
  engines/learning_engine.py              ← Phase 7

  personal_brain/__init__.py
  personal_brain/brain.py                 ← Phase 4

修改文件:
  core/skill_engine/__init__.py           ← 导出不变，但标记为 stable
  core/skill_engine/models.py             ← 新增四类 Patch 模型
  core/workflow/service.py                ← 接入 CognitiveController
  agents/writer/agent.py                  ← 接入 ReasoningPattern 注入
  agents/knowledge/agent.py               ← 接入 Decomposer
  api/v1/router.py                        ← 注册新端点

保留不变（标记为 stable，停止迭代）:
  core/skill_engine/task_engine.py
  core/skill_engine/review_engine.py
  core/skill_engine/template_engine.py
  core/skill_engine/skill_tree.py
  core/skill_engine/skill_manager.py
  core/skill_engine/skill_learner.py      ← 保留，V3 LearningEngine 并行运行
  core/skill_engine/intent_cache.py
  core/skill_engine/intent_analyzer.py
  core/skill_engine/prompt_builder.py
  agents/review/agent.py
  agents/judge/agent.py
  agents/result/agent.py
```

### 12.2 兼容性保证

- V2.1 的 `SkillLearner` 保留，V3 `LearningEngine` 并行运行，互不干扰
- 所有现有 API 端点不变
- `tree.yaml` + `skill.yaml` 继续作为数据源，`GraphBuilder` 是单向迁移（不删除源文件）
- WorkflowService 保留原有 5 Agent 流水线，CognitiveController 作为可选调度层
- Task/Skill/Review Engine 标记为 `stable`，不再新增功能

---

## 十三、总时间线

```
Week 1 (6天):
  Day 1-4: Phase 1 — Skill Graph 基础设施
  Day 5-6: Phase 2 — Cognitive Controller

Week 2 (5天):
  Day 1-2: Phase 3 — Patch Validator
  Day 3-4: Phase 3 — Decomposer + Local Planner
  Day 5:   集成测试 Phase 1-3

Week 3 (5天):
  Day 1-3: Phase 4 — Capability Graph + Personal Brain
  Day 4-5: Phase 5 — Reasoning Graph（开始）

Week 4 (5天):
  Day 1-2: Phase 5 — Reasoning Graph（完成 + 接入 Writer）
  Day 3-4: Phase 6 — Knowledge Recommendation
  Day 5:   Phase 7 — Learning Engine V3 + 全量集成测试

Week 5 (3天):
  Day 1-2: 全量回归测试 + 性能基准
  Day 3:   文档更新 + 交付
```

**总计: 约 24 个工作日**

---

## 十四、研发优先级总结

```
P0 (Week 1-2):   Skill Graph + Cognitive Controller + Patch Validator
                 ↑ 没有这三者，后续全部无法工作

P1 (Week 2-3):   Decomposer + Planner + Capability Graph + Personal Brain
                 ↑ 用户体验核心提升

P2 (Week 3-4):   Reasoning Graph
                 ↑ 最大创新点，系统从"博学"到"聪明"

P3 (Week 4-5):   Knowledge Recommendation + Learning Engine V3
                 ↑ 长期价值，自动闭环
```

---

**文档版本**: V3.0.0-dev-2
**更新日期**: 2026-07-22
**适用项目**: AgentMatrix V3 Cognitive Agent Architecture
**核心原则**: Graph First, Engine Second — Graph 越来越重，Engine 越来越轻