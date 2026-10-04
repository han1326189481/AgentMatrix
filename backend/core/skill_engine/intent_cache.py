"""
Skill Engine V2 — 意图缓存

两层缓存架构：
  L1: 意图 → 技能路径映射（轻量，命中率高，跳过领域检测）
  L2: 完整结果缓存（重量，仅缓存 executed_locally=true 且长度 < 5000 的结果）

缓存策略：
  - 指纹：SHA256 归一化查询文本（去标点、去空格、小写）
  - TTL：300 秒（可配置）
  - 最大容量：L1=200, L2=200
  - 淘汰策略：LRU（超过最大容量时淘汰最旧条目）
"""

import hashlib
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class IntentCache:
    """意图缓存 — 两层缓存结构

    Attributes:
        l1_hits: L1 累计命中次数
        l1_misses: L1 累计未命中次数
        l2_hits: L2 累计命中次数
        l2_misses: L2 累计未命中次数
    """

    def __init__(self, max_size: int = 200, ttl: int = 300):
        self._max_size = max_size
        self._ttl = ttl

        # L1: 意图 → 技能路径映射
        self._skill_path_cache: Dict[str, Dict[str, Any]] = {}
        # L2: 完整结果缓存
        self._result_cache: Dict[str, Dict[str, Any]] = {}

        # V4.1: 全局 hit/miss 计数器
        self.l1_hits = 0
        self.l1_misses = 0
        self.l2_hits = 0
        self.l2_misses = 0

    # ============================================================
    # L1: 技能路径缓存
    # ============================================================

    def lookup_skill_path(self, query: str) -> Optional[List[str]]:
        """L1 缓存：查询意图对应的技能路径

        Args:
            query: 用户原始查询

        Returns:
            技能路径列表，未命中返回 None
        """
        fingerprint = self._fingerprint(query)
        entry = self._skill_path_cache.get(fingerprint)

        if entry and not self._is_expired(entry):
            entry["hit_count"] = entry.get("hit_count", 0) + 1
            entry["last_hit"] = datetime.now().isoformat()
            self.l1_hits += 1
            logger.debug(f"IntentCache L1 HIT: {query[:30]}... → {entry['data']}")
            return entry["data"]

        self.l1_misses += 1
        return None

    def store_skill_path(self, query: str, skill_path: List[str]):
        """存储意图 → 技能路径映射

        Args:
            query: 用户原始查询
            skill_path: 检测到的技能路径
        """
        fingerprint = self._fingerprint(query)

        # LRU 淘汰
        if len(self._skill_path_cache) >= self._max_size:
            self._evict_lru(self._skill_path_cache)

        self._skill_path_cache[fingerprint] = {
            "data": skill_path,
            "created_at": datetime.now().isoformat(),
            "ttl": self._ttl,
            "hit_count": 0,
            "last_hit": None,
            "original_query": query[:100],
        }

    # ============================================================
    # L2: 结果缓存
    # ============================================================

    def lookup_result(self, query: str) -> Optional[Dict[str, Any]]:
        """L2 缓存：查询完整结果

        Args:
            query: 用户原始查询

        Returns:
            完整的 WorkflowOutput dict，未命中返回 None
        """
        fingerprint = self._fingerprint(query)
        entry = self._result_cache.get(fingerprint)

        if entry and not self._is_expired(entry):
            entry["hit_count"] = entry.get("hit_count", 0) + 1
            entry["last_hit"] = datetime.now().isoformat()
            self.l2_hits += 1
            logger.info(f"IntentCache L2 HIT: {query[:30]}...")
            return entry["data"]

        self.l2_misses += 1
        return None

    def store_result(self, query: str, result: Dict[str, Any]):
        """存储完整结果

        仅缓存条件：
        1. executed_locally = True（本地执行的结果）
        2. final_result 长度 < 5000 字符

        Args:
            query: 用户原始查询
            result: WorkflowOutput dict
        """
        # 只缓存本地结果
        if not result.get("executed_locally", True):
            return

        # 过长不缓存
        final_result = result.get("final_result", "")
        if len(final_result) > 5000:
            return

        fingerprint = self._fingerprint(query)

        # LRU 淘汰
        if len(self._result_cache) >= self._max_size:
            self._evict_lru(self._result_cache)

        self._result_cache[fingerprint] = {
            "data": result,
            "created_at": datetime.now().isoformat(),
            "ttl": self._ttl,
            "hit_count": 0,
            "last_hit": None,
            "original_query": query[:100],
        }

    # ============================================================
    # 指纹与归一化
    # ============================================================

    @staticmethod
    def _fingerprint(query: str) -> str:
        """生成查询指纹

        1. 归一化：去标点、去多余空格、小写
        2. SHA256 哈希取前16位
        """
        normalized = IntentCache._normalize(query)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _normalize(query: str) -> str:
        """归一化查询文本

        1. 去标点符号（保留中文、英文字母、数字、空格）
        2. 去多余空格
        3. 小写
        """
        # 去标点符号（保留字母数字和空格）
        cleaned = re.sub(r"[^\w\s]", " ", query)
        # 去多余空格
        return " ".join(cleaned.lower().split())

    @staticmethod
    def _is_expired(entry: Dict[str, Any]) -> bool:
        """检查缓存条目是否过期"""
        created_at = entry.get("created_at", "")
        ttl = entry.get("ttl", 300)
        if not created_at:
            return False
        try:
            created = datetime.fromisoformat(created_at)
            return (datetime.now() - created).total_seconds() > ttl
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _evict_lru(cache: Dict[str, Dict]):
        """淘汰最旧条目（LRU）"""
        if not cache:
            return
        # 找最旧的条目
        oldest_key = None
        oldest_time = None
        for key, entry in cache.items():
            created_at = entry.get("created_at", "")
            if created_at:
                try:
                    t = datetime.fromisoformat(created_at)
                    if oldest_time is None or t < oldest_time:
                        oldest_time = t
                        oldest_key = key
                except (ValueError, TypeError):
                    pass

        if oldest_key:
            del cache[oldest_key]
            logger.debug(f"IntentCache: LRU evicted {oldest_key}")

    # ============================================================
    # 缓存管理
    # ============================================================

    def clear(self, layer: str = None):
        """清除缓存

        Args:
            layer: "l1" | "l2" | None（全部清除）
        """
        if layer == "l1" or layer is None:
            self._skill_path_cache.clear()
            self.l1_hits = 0
            self.l1_misses = 0
        if layer == "l2" or layer is None:
            self._result_cache.clear()
            self.l2_hits = 0
            self.l2_misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计（含命中率）"""
        l1_total = self.l1_hits + self.l1_misses
        l2_total = self.l2_hits + self.l2_misses
        overall_total = l1_total + l2_total
        overall_hits = self.l1_hits + self.l2_hits

        return {
            "l1_skill_path": {
                "size": len(self._skill_path_cache),
                "max_size": self._max_size,
                "hits": self.l1_hits,
                "misses": self.l1_misses,
                "hit_rate": round(self.l1_hits / l1_total, 4) if l1_total > 0 else 0.0,
            },
            "l2_result": {
                "size": len(self._result_cache),
                "max_size": self._max_size,
                "hits": self.l2_hits,
                "misses": self.l2_misses,
                "hit_rate": round(self.l2_hits / l2_total, 4) if l2_total > 0 else 0.0,
            },
            "overall": {
                "hits": overall_hits,
                "misses": overall_total - overall_hits,
                "hit_rate": round(overall_hits / overall_total, 4) if overall_total > 0 else 0.0,
            },
            "ttl": self._ttl,
        }

    def get_l1_entries(self) -> List[Dict[str, Any]]:
        """获取所有 L1 缓存条目（用于调试）"""
        return [
            {
                "fingerprint": k,
                "original_query": v.get("original_query", ""),
                "skill_path": v.get("data", []),
                "hit_count": v.get("hit_count", 0),
            }
            for k, v in self._skill_path_cache.items()
        ]


# ============================================================
# 全局单例
# ============================================================

_intent_cache: Optional[IntentCache] = None


def get_intent_cache() -> IntentCache:
    global _intent_cache
    if _intent_cache is None:
        _intent_cache = IntentCache(max_size=200, ttl=300)
    return _intent_cache