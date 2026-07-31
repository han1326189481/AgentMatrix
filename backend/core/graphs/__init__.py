"""AgentMatrix V3 — Graph 层

Graph First, Engine Second.
Graph = 系统的大脑（数据结构 + 关系）
Engine = 大脑的调用者（调度 + 执行）
"""

import os
from .skill_graph import SkillGraph, GraphNode, GraphEdge, EDGE_TYPES
from .graph_builder import GraphBuilder
from .capability_graph import CapabilityGraph, CapabilityNode, Proficiency
from .reasoning_graph import ReasoningGraph, ReasoningNode
from .intent_graph import IntentGraph, IntentRecord

__all__ = [
    "SkillGraph", "GraphNode", "GraphEdge", "EDGE_TYPES", "GraphBuilder",
    "CapabilityGraph", "CapabilityNode", "Proficiency",
    "ReasoningGraph", "ReasoningNode",
    "IntentGraph", "IntentRecord",
    "get_skill_graph"
]

# 全局单例（懒加载）
_skill_graph_instance: SkillGraph = None


def get_skill_graph() -> SkillGraph:
    """获取 SkillGraph 全局单例

    首次调用时从 skill_graph.yaml 加载，后续调用返回缓存实例。
    """
    global _skill_graph_instance
    if _skill_graph_instance is None:
        yaml_path = os.path.join(os.path.dirname(__file__), "skill_graph.yaml")
        if os.path.exists(yaml_path):
            _skill_graph_instance = SkillGraph.load(yaml_path)
        else:
            # 如果 YAML 不存在，返回空 Graph（首次使用需要运行 GraphBuilder）
            _skill_graph_instance = SkillGraph()
    return _skill_graph_instance


def reload_skill_graph() -> SkillGraph:
    """强制重新加载 SkillGraph"""
    global _skill_graph_instance
    _skill_graph_instance = None
    return get_skill_graph()