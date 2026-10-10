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
        """更新能力

        `proficiency` 允许传枚举或字符串（调用方两处都有：
        `update_from_session` 传 "practice" 字符串，API 层传枚举），
        在此统一成枚举，避免落盘后同一字段混两种类型。
        """
        if isinstance(proficiency, str) and not isinstance(proficiency, Proficiency):
            proficiency = Proficiency(proficiency)
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

    # ============================================================
    # 序列化（2026-10-10 新增）
    #
    # 设计约束：**本类不碰文件 I/O**，只负责 dict <-> 对象。
    # 落盘由 `PersonalBrain._save_capability()` 负责，与既有的
    # `_save_profile()` 同构 —— 这样 conftest 里
    # `_isolate_personal_brain_profiles` 那条 fixture 只要 patch
    # `brain.get_profiles_dir`，本图的落盘路径就自动被隔离。
    # ⚠️ 若把 open()/json.dump 写进本类并自己 import get_profiles_dir，
    #    fixture 覆盖不到 → 测试会直接写进生产 storage/profiles/。
    #    （与 2026-09-24 知识库清空事故同款漏网，不要改这个约定。）
    # ============================================================

    def to_dict(self) -> dict:
        """序列化为可 JSON 化的 dict"""
        return {
            "user_id": self.user_id,
            "nodes": {
                node_id: {
                    "skill_node_id": n.skill_node_id,
                    # Proficiency 是 str Enum，json 不认识 Enum 本身，
                    # 必须取 .value 否则 TypeError: Object of type ... is not JSON serializable
                    "proficiency": (n.proficiency.value
                                    if isinstance(n.proficiency, Proficiency)
                                    else str(n.proficiency)),
                    "evidence": list(n.evidence),
                    "last_practiced": n.last_practiced,
                    "practice_count": n.practice_count,
                }
                for node_id, n in self.nodes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict, user_id: str = "") -> "CapabilityGraph":
        """从 dict 恢复。

        逐节点 try/except：单个节点数据损坏（枚举值非法、字段缺失）时
        跳过该节点而不是整图报废 —— 这是读用户积累数据的路径，
        丢一条远好过丢全部。
        """
        graph = cls(user_id or data.get("user_id", "default"))
        raw_nodes = data.get("nodes") or {}
        if not isinstance(raw_nodes, dict):
            return graph
        for node_id, raw in raw_nodes.items():
            if not isinstance(raw, dict):
                continue
            try:
                prof = Proficiency(raw.get("proficiency", Proficiency.NONE.value))
            except ValueError:
                prof = Proficiency.NONE
            graph.nodes[node_id] = CapabilityNode(
                skill_node_id=raw.get("skill_node_id", node_id),
                proficiency=prof,
                evidence=list(raw.get("evidence") or []),
                last_practiced=raw.get("last_practiced"),
                practice_count=int(raw.get("practice_count") or 0),
            )
        return graph