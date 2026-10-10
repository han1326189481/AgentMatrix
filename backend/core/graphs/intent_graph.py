"""Intent Graph — 意图时间线

记录用户会话历史的时间序列，用于：
- 连续领域检测（同一领域连续提问3次以上 → 触发推荐介入）
- 意图趋势分析（用户兴趣从 A 转向 B）
- 会话摘要（最近N次会话的主题分布）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import Counter
import json
import logging
import os
import shutil
import time

logger = logging.getLogger(__name__)


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
    """意图时间线 — 用户会话历史的时序视图

    持久化（2026-10-10 新增）：`storage/intents/{user_id}.json`。
    此前记录只在内存里，`WorkflowService` 每次请求新建实例 → 重启即清零，
    `get_consecutive_domain_run` 软节流在真实使用中几乎永远返回 0。
    """

    def __init__(self, user_id: str, max_records: int = 100,
                 storage_dir: Optional[str] = None, persist: bool = True):
        self.user_id = user_id
        self.max_records = max_records
        self.records: List[IntentRecord] = []
        # storage_dir 可注入：测试传 tmp_path 即完全隔离生产目录。
        # persist=False 则纯内存，不读不写磁盘。
        self._storage_dir = storage_dir
        self._persist = persist
        if persist:
            self._load()

    @property
    def storage_dir(self) -> str:
        """持久化目录：注入优先，否则走平台默认目录。"""
        if self._storage_dir is not None:
            return self._storage_dir
        from shared.platform import get_intents_dir
        return get_intents_dir()

    @property
    def _file_path(self) -> str:
        return os.path.join(self.storage_dir, f"{self.user_id}.json")

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "max_records": self.max_records,
            "records": [
                {
                    "session_id": r.session_id,
                    "question": r.question,
                    "domain": r.domain,
                    "task_type": r.task_type,
                    "skill_nodes": list(r.skill_nodes),
                    "timestamp": r.timestamp,
                }
                for r in self.records
            ],
        }

    @classmethod
    def from_dict(cls, data: dict, **kwargs) -> "IntentGraph":
        graph = cls(
            user_id=data.get("user_id", "default"),
            max_records=int(data.get("max_records") or 100),
            **kwargs,
        )
        # 绕过 __init__ 的自动 load：数据已在手，直接填。
        graph.records = []
        for raw in (data.get("records") or []):
            if not isinstance(raw, dict):
                continue
            try:
                graph.records.append(IntentRecord(
                    session_id=raw.get("session_id", ""),
                    question=raw.get("question", ""),
                    domain=raw.get("domain", ""),
                    task_type=raw.get("task_type", ""),
                    skill_nodes=list(raw.get("skill_nodes") or []),
                    timestamp=float(raw.get("timestamp") or time.time()),
                ))
            except (TypeError, ValueError) as e:
                # 单条损坏不拖垮整图 —— 这是用户长期积累数据的读路径。
                logger.warning(f"IntentGraph: 跳过损坏记录: {e}")
        graph.records = graph.records[-graph.max_records:]
        return graph

    def _load(self):
        """从磁盘恢复；文件不存在或损坏时保持为空（不抛异常）。"""
        try:
            path = self._file_path
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return
            self.records = []
            for raw in (data.get("records") or []):
                if not isinstance(raw, dict):
                    continue
                try:
                    self.records.append(IntentRecord(
                        session_id=raw.get("session_id", ""),
                        question=raw.get("question", ""),
                        domain=raw.get("domain", ""),
                        task_type=raw.get("task_type", ""),
                        skill_nodes=list(raw.get("skill_nodes") or []),
                        timestamp=float(raw.get("timestamp") or time.time()),
                    ))
                except (TypeError, ValueError) as e:
                    logger.warning(f"IntentGraph: 跳过损坏记录: {e}")
            self.records = self.records[-self.max_records:]
            logger.debug(f"IntentGraph 恢复 {len(self.records)} 条记录 <- {path}")
        except Exception as e:
            logger.warning(f"IntentGraph 加载失败，按空图处理: {e}")

    def save(self) -> bool:
        """原子写 + 保留 .bak。返回是否成功（失败不抛，避免打断主链路）。"""
        if not self._persist:
            return False
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
            path = self._file_path
            if os.path.exists(path):
                shutil.copy2(path, path + ".bak")
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            return True
        except Exception as e:
            logger.warning(f"IntentGraph 持久化失败: {e}")
            return False

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
        # 每次记录即落盘：否则进程退出后软节流信号全部丢失，
        # get_consecutive_domain_run 的跨会话连续计数等于永远为 0。
        self.save()

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

    @staticmethod
    def domains_related(a: str, b: str) -> bool:
        """判断两个领域是否同根（相等或互为点分前缀）

        用于「领域切换 vs 持续关注」判定：
          tech.ai 与 tech.ai.agent → 相关（持续关注同一大方向）
          tech.ai 与 business     → 不相关（发生领域切换）
        """
        a = (a or "").strip()
        b = (b or "").strip()
        if not a or not b:
            return False
        if a == b:
            return True
        return a.startswith(b + ".") or b.startswith(a + ".")

    def get_consecutive_domain_run(self, domain: str = "") -> int:
        """返回**末尾**连续同领域的次数（软节流信号，替代 window 硬判定）

        Args:
            domain: 限定统计的领域；为空则统计末尾记录的所属领域。
                    两者按 `domains_related` 同根匹配（tech.ai ≈ tech.ai.agent）。

        Returns:
            连续次数（0 表示末尾记录无领域或首条即不匹配）
        """
        if not self.records:
            return 0
        tail = self.records[-1].domain
        # 不限定 domain 时以末尾记录的领域为基准
        target = domain or tail
        if not target:
            return 0
        run = 0
        for r in reversed(self.records):
            if r.domain and self.domains_related(r.domain, target):
                run += 1
            else:
                break
        return run

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