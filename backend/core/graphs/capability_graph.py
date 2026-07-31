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