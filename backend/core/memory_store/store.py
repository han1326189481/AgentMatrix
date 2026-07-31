"""MemoryStore — 长期记忆 JSON 文件存储

持久化路径: storage/memory/{user_id}.json

设计原则:
- 每条记忆包含: id, content, timestamp, importance, source, category
- 最大容量: 200 条记忆（超出时自动清理低重要性旧记忆）
- 跨沙盒共享: 同一用户的所有沙盒共享记忆
- 文件格式: JSON 数组，读写加锁保证线程安全
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import json
import os
import threading
import time
import logging
from shared.platform import get_memory_dir

logger = logging.getLogger(__name__)

MAX_MEMORIES = 200
MIN_IMPORTANCE = 0.3  # 记忆重要性低于此值不存储


@dataclass
class MemoryItem:
    id: str
    content: str
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5        # 0.0 ~ 1.0
    source: str = "session"        # "session" | "manual" | "inferred"
    category: str = "general"      # "fact" | "preference" | "goal" | "event" | "general"
    access_count: int = 0          # 被检索次数（用于淘汰策略）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryItem":
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            importance=data.get("importance", 0.5),
            source=data.get("source", "session"),
            category=data.get("category", "general"),
            access_count=data.get("access_count", 0),
        )


class MemoryStore:
    """长期记忆存储 — JSON 文件持久化"""

    _file_lock = threading.Lock()
    _instances: Dict[str, "MemoryStore"] = {}

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._memories: Optional[List[MemoryItem]] = None
        self._dirty = False

    @property
    def _memory_path(self) -> str:
        return os.path.join(get_memory_dir(), f"{self.user_id}.json")

    def _ensure_loaded(self):
        """懒加载记忆数据"""
        if self._memories is not None:
            return
        self._memories = self._load_all()

    def _load_all(self) -> List[MemoryItem]:
        """从 JSON 文件加载所有记忆"""
        try:
            if os.path.exists(self._memory_path):
                with self._file_lock:
                    with open(self._memory_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                if isinstance(data, list):
                    memories = [MemoryItem.from_dict(item) for item in data]
                    logger.info(f"MemoryStore: loaded {len(memories)} memories for user={self.user_id}")
                    return memories
        except json.JSONDecodeError as e:
            logger.warning(f"Memory file corrupted, resetting: {self._memory_path} error={e}")
        except Exception as e:
            logger.warning(f"Failed to load memories: {self._memory_path} error={e}")
        return []

    def _save_all(self):
        """将所有记忆持久化到 JSON 文件"""
        if self._memories is None:
            return
        try:
            with self._file_lock:
                with open(self._memory_path, "w", encoding="utf-8") as f:
                    json.dump(
                        [m.to_dict() for m in self._memories],
                        f, ensure_ascii=False, indent=2
                    )
            self._dirty = False
        except Exception as e:
            logger.error(f"Failed to save memories: {self._memory_path} error={e}")

    def _prune(self):
        """淘汰低重要性旧记忆，保持总量在 MAX_MEMORIES 以内"""
        if self._memories is None or len(self._memories) <= MAX_MEMORIES:
            return

        # 打分策略：importance * 0.6 + recency * 0.25 + access_count * 0.15
        now = time.time()
        def score(m: MemoryItem) -> float:
            recency = max(0, 1.0 - (now - m.timestamp) / (365 * 86400))  # 一年内线性衰减
            access_bonus = min(m.access_count / 10, 1.0)  # 最多访问10次满分
            return m.importance * 0.6 + recency * 0.25 + access_bonus * 0.15

        self._memories.sort(key=score, reverse=True)
        removed = self._memories[MAX_MEMORIES:]
        self._memories = self._memories[:MAX_MEMORIES]
        self._dirty = True
        logger.info(
            f"MemoryStore: pruned {len(removed)} low-score memories, "
            f"kept {len(self._memories)} (threshold={score(self._memories[-1]):.2f})"
        )

    def add(self, content: str, importance: float = 0.5,
            source: str = "session", category: str = "general") -> Optional[str]:
        """添加一条记忆，返回记忆 ID"""
        if importance < MIN_IMPORTANCE:
            logger.debug(f"Memory skipped (importance={importance:.2f} < {MIN_IMPORTANCE})")
            return None

        self._ensure_loaded()
        memory_id = f"mem_{int(time.time() * 1000)}_{len(self._memories)}"
        item = MemoryItem(
            id=memory_id,
            content=content,
            importance=importance,
            source=source,
            category=category,
        )
        self._memories.append(item)
        self._dirty = True
        self._prune()
        self._save_all()
        logger.debug(f"Memory added: id={memory_id}, importance={importance:.2f}, category={category}")
        return memory_id

    def get_recent(self, limit: int = 10) -> List[MemoryItem]:
        """获取最近 N 条记忆"""
        self._ensure_loaded()
        sorted_memories = sorted(self._memories, key=lambda m: m.timestamp, reverse=True)
        return sorted_memories[:limit]

    def get_important(self, limit: int = 10) -> List[MemoryItem]:
        """获取最重要的 N 条记忆"""
        self._ensure_loaded()
        sorted_memories = sorted(self._memories, key=lambda m: m.importance, reverse=True)
        # 增加访问计数
        for m in sorted_memories[:limit]:
            m.access_count += 1
        self._dirty = True
        self._save_all()
        return sorted_memories[:limit]

    def search(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """搜索相关记忆（简单关键词匹配 + 重要性排序）"""
        self._ensure_loaded()
        query_lower = query.lower()
        matched = []
        for m in self._memories:
            if query_lower in m.content.lower():
                matched.append(m)
        # 按 (importance * 0.7 + recency * 0.3) 排序
        now = time.time()
        def rank(m: MemoryItem) -> float:
            recency = max(0, 1.0 - (now - m.timestamp) / (365 * 86400))
            return m.importance * 0.7 + recency * 0.3
        matched.sort(key=rank, reverse=True)
        # 增加访问计数
        for m in matched[:limit]:
            m.access_count += 1
        if matched:
            self._dirty = True
            self._save_all()
        return matched[:limit]

    def build_context(self, recent_limit: int = 5, important_limit: int = 3) -> str:
        """构建长期记忆上下文（供系统提示注入）"""
        self._ensure_loaded()
        if not self._memories:
            return ""

        parts = ["[用户长期记忆]"]

        important = self.get_important(important_limit)
        if important:
            parts.append("重要记忆:")
            for m in important:
                parts.append(f"  - {m.content}")

        recent = self.get_recent(recent_limit)
        recent_filtered = [m for m in recent if m not in important]
        if recent_filtered:
            parts.append("最近记忆:")
            for m in recent_filtered[:3]:
                parts.append(f"  - {m.content}")

        return "\n".join(parts)

    def delete(self, memory_id: str) -> bool:
        """删除指定记忆"""
        self._ensure_loaded()
        for i, m in enumerate(self._memories):
            if m.id == memory_id:
                self._memories.pop(i)
                self._dirty = True
                self._save_all()
                return True
        return False

    def clear(self):
        """清空所有记忆"""
        self._memories = []
        self._dirty = True
        self._save_all()
        logger.info(f"MemoryStore: cleared all memories for user={self.user_id}")

    def count(self) -> int:
        self._ensure_loaded()
        return len(self._memories)

    def stats(self) -> dict:
        self._ensure_loaded()
        categories = {}
        for m in self._memories:
            categories[m.category] = categories.get(m.category, 0) + 1
        return {
            "total": len(self._memories),
            "max_capacity": MAX_MEMORIES,
            "categories": categories,
            "avg_importance": round(
                sum(m.importance for m in self._memories) / max(len(self._memories), 1), 2
            ),
        }


def get_memory_store(user_id: str = "default") -> MemoryStore:
    """获取 MemoryStore 实例（每次新建，确保从文件加载最新数据）"""
    return MemoryStore(user_id)