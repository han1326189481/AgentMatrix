"""Intent Graph — 意图时间线

记录用户会话历史的时间序列，用于：
- 连续领域检测（同一领域连续提问3次以上 → 触发推荐介入）
- 意图趋势分析（用户兴趣从 A 转向 B）
- 会话摘要（最近N次会话的主题分布）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import Counter
import time


@dataclass
class IntentRecord:
    """单次会话的意图记录"""
    session_id: str
    question: str
    domain: str = ""               # 领域（tech/ai/business/daily）
    task_type: str = ""            # 任务类型（qa/coding/writing/analysis）
    skill_nodes: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class IntentGraph:
    """意图时间线 — 用户会话历史的时序视图"""

    def __init__(self, user_id: str, max_records: int = 100):
        self.user_id = user_id
        self.max_records = max_records
        self.records: List[IntentRecord] = []

    def record(self, session_id: str, question: str, domain: str = "",
               task_type: str = "", skill_nodes: Optional[List[str]] = None):
        """记录一次会话意图"""
        self.records.append(IntentRecord(
            session_id=session_id,
            question=question,
            domain=domain,
            task_type=task_type,
            skill_nodes=skill_nodes or [],
        ))
        # 保持最大记录数
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]

    def get_consecutive_domain(self, window: int = 3) -> Optional[str]:
        """检测最近 N 次是否连续同领域

        Returns:
            连续领域名称，或 None
        """
        if len(self.records) < window:
            return None
        recent = self.records[-window:]
        domains = [r.domain for r in recent if r.domain]
        if len(domains) < window:
            return None
        if len(set(domains)) == 1:
            return domains[0]
        return None

    def get_domain_distribution(self, top_n: int = 5) -> List[tuple]:
        """获取领域分布（最近记录）"""
        domains = [r.domain for r in self.records if r.domain]
        return Counter(domains).most_common(top_n)

    def get_task_type_distribution(self, top_n: int = 5) -> List[tuple]:
        """获取任务类型分布"""
        task_types = [r.task_type for r in self.records if r.task_type]
        return Counter(task_types).most_common(top_n)

    def get_recent_skill_nodes(self, limit: int = 10) -> List[str]:
        """获取最近涉及的 Skill 节点（去重）"""
        seen = set()
        nodes = []
        for r in reversed(self.records):
            for node_id in r.skill_nodes:
                if node_id not in seen:
                    seen.add(node_id)
                    nodes.append(node_id)
                    if len(nodes) >= limit:
                        return nodes
        return nodes

    def get_trend(self) -> Optional[str]:
        """检测意图趋势：用户兴趣是否从领域A转向领域B

        比较前一半和后一半的领域分布变化。
        """
        if len(self.records) < 6:
            return None
        mid = len(self.records) // 2
        first_half = [r.domain for r in self.records[:mid] if r.domain]
        second_half = [r.domain for r in self.records[mid:] if r.domain]
        if not first_half or not second_half:
            return None
        first_top = Counter(first_half).most_common(1)[0][0]
        second_top = Counter(second_half).most_common(1)[0][0]
        if first_top != second_top:
            return f"interest_shift: {first_top} → {second_top}"
        return None

    def stats(self) -> dict:
        return {
            "total_records": len(self.records),
            "unique_domains": len(set(r.domain for r in self.records if r.domain)),
            "unique_task_types": len(set(r.task_type for r in self.records if r.task_type)),
            "consecutive_domain": self.get_consecutive_domain(),
            "trend": self.get_trend(),
            "domain_distribution": self.get_domain_distribution(),
            "task_type_distribution": self.get_task_type_distribution(),
        }