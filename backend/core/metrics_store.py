"""MetricsStore — 指标历史持久化

职责:
- 每次 workflow 完成后保存指标快照到 SQLite
- 支持按时间范围查询历史数据
- 自动清理过期数据（保留 30 天）

使用方式:
    from core.metrics_store import get_metrics_store

    store = get_metrics_store()
    store.save_snapshot(cache_stats, cost_summary)
    history = store.get_history("24h")
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 数据保留天数
RETENTION_DAYS = 30
# 聚合间隔：同一小时内的快照合并
AGGREGATION_INTERVAL_MINUTES = 60


class MetricsStore:
    """指标历史存储 — 线程安全单例"""

    _instance: Optional["MetricsStore"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MetricsStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        """初始化数据库和表"""
        from app.config import settings
        from shared.platform import get_db_path

        db_path = get_db_path()
        self._db_path = db_path

        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                -- 缓存命中率
                cache_hits INTEGER NOT NULL DEFAULT 0,
                cache_misses INTEGER NOT NULL DEFAULT 0,
                cache_hit_rate REAL NOT NULL DEFAULT 0.0,
                workflow_cache_hit_rate REAL NOT NULL DEFAULT 0.0,
                intent_cache_hit_rate REAL NOT NULL DEFAULT 0.0,
                -- 成本统计
                estimated_cost REAL NOT NULL DEFAULT 0.0,
                estimated_savings REAL NOT NULL DEFAULT 0.0,
                savings_rate REAL NOT NULL DEFAULT 0.0,
                avg_cost_per_workflow REAL NOT NULL DEFAULT 0.0,
                -- token 统计
                total_cloud_tokens INTEGER NOT NULL DEFAULT 0,
                total_local_tokens INTEGER NOT NULL DEFAULT 0,
                -- 执行统计
                workflow_count INTEGER NOT NULL DEFAULT 0,
                local_workflow_count INTEGER NOT NULL DEFAULT 0,
                cloud_workflow_count INTEGER NOT NULL DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
            ON metrics_snapshots(timestamp)
        """)

        conn.commit()
        conn.close()
        logger.info(f"MetricsStore initialized: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def save_snapshot(
        self,
        cache_stats: Dict[str, Any],
        cost_summary: Dict[str, Any],
    ):
        """保存一次指标快照

        Args:
            cache_stats: 缓存统计（来自 SimpleCache.get_stats() + IntentCache.get_stats()）
            cost_summary: 成本摘要（来自 CostTracker.get_summary()）
        """
        conn = self._get_conn()
        try:
            now = datetime.now().isoformat()

            # 检查是否与上次快照在同一小时内（聚合去重）
            last = conn.execute(
                "SELECT id, timestamp FROM metrics_snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()

            if last:
                last_ts = datetime.fromisoformat(last["timestamp"])
                if (datetime.now() - last_ts).total_seconds() < AGGREGATION_INTERVAL_MINUTES * 60:
                    # 同一小时内，更新最后一条记录
                    conn.execute("""
                        UPDATE metrics_snapshots SET
                            timestamp = ?,
                            estimated_cost = ?,
                            estimated_savings = ?,
                            savings_rate = ?,
                            avg_cost_per_workflow = ?,
                            total_cloud_tokens = ?,
                            total_local_tokens = ?,
                            workflow_count = ?,
                            local_workflow_count = ?,
                            cloud_workflow_count = ?,
                            cache_hits = ?,
                            cache_misses = ?,
                            cache_hit_rate = ?,
                            workflow_cache_hit_rate = ?,
                            intent_cache_hit_rate = ?
                        WHERE id = ?
                    """, (
                        now,
                        cost_summary.get("estimated_cost", 0.0),
                        cost_summary.get("estimated_savings", 0.0),
                        cost_summary.get("savings_rate", 0.0),
                        cost_summary.get("avg_cost_per_workflow", 0.0),
                        cost_summary.get("total_cloud_input_tokens", 0) + cost_summary.get("total_cloud_output_tokens", 0),
                        cost_summary.get("total_local_input_tokens", 0) + cost_summary.get("total_local_output_tokens", 0),
                        cost_summary.get("workflow_count", 0),
                        cost_summary.get("local_workflow_count", 0),
                        cost_summary.get("cloud_workflow_count", 0),
                        cache_stats.get("hits", 0),
                        cache_stats.get("misses", 0),
                        cache_stats.get("overall_hit_rate", 0.0),
                        cache_stats.get("workflow_cache_hit_rate", 0.0),
                        cache_stats.get("intent_cache_hit_rate", 0.0),
                        last["id"],
                    ))
                    conn.commit()
                    return

            # 新快照
            conn.execute("""
                INSERT INTO metrics_snapshots (
                    timestamp,
                    cache_hits, cache_misses,
                    cache_hit_rate, workflow_cache_hit_rate, intent_cache_hit_rate,
                    estimated_cost, estimated_savings, savings_rate, avg_cost_per_workflow,
                    total_cloud_tokens, total_local_tokens,
                    workflow_count, local_workflow_count, cloud_workflow_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now,
                cache_stats.get("hits", 0),
                cache_stats.get("misses", 0),
                cache_stats.get("overall_hit_rate", 0.0),
                cache_stats.get("workflow_cache_hit_rate", 0.0),
                cache_stats.get("intent_cache_hit_rate", 0.0),
                cost_summary.get("estimated_cost", 0.0),
                cost_summary.get("estimated_savings", 0.0),
                cost_summary.get("savings_rate", 0.0),
                cost_summary.get("avg_cost_per_workflow", 0.0),
                cost_summary.get("total_cloud_input_tokens", 0) + cost_summary.get("total_cloud_output_tokens", 0),
                cost_summary.get("total_local_input_tokens", 0) + cost_summary.get("total_local_output_tokens", 0),
                cost_summary.get("workflow_count", 0),
                cost_summary.get("local_workflow_count", 0),
                cost_summary.get("cloud_workflow_count", 0),
            ))

            conn.commit()
            logger.debug(
                f"MetricsStore: snapshot saved — "
                f"cost=¥{cost_summary.get('estimated_cost', 0):.6f}, "
                f"savings=¥{cost_summary.get('estimated_savings', 0):.6f}"
            )

            # 自动清理过期数据
            self._cleanup_expired(conn)
        except Exception as e:
            logger.warning(f"MetricsStore: save_snapshot failed: {e}")
        finally:
            conn.close()

    def get_history(self, range_str: str = "24h") -> List[Dict[str, Any]]:
        """查询历史指标快照

        Args:
            range_str: 时间范围，"24h" | "7d" | "30d"

        Returns:
            按时间排序的快照列表
        """
        now = datetime.now()
        range_map = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = range_map.get(range_str, timedelta(hours=24))
        since = (now - delta).isoformat()

        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM metrics_snapshots WHERE timestamp >= ? ORDER BY timestamp ASC",
                (since,),
            ).fetchall()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.warning(f"MetricsStore: get_history failed: {e}")
            return []
        finally:
            conn.close()

    def get_latest(self) -> Optional[Dict[str, Any]]:
        """获取最近一次快照"""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM metrics_snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.warning(f"MetricsStore: get_latest failed: {e}")
            return None
        finally:
            conn.close()

    def _cleanup_expired(self, conn: sqlite3.Connection):
        """清理过期数据"""
        cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).isoformat()
        deleted = conn.execute(
            "DELETE FROM metrics_snapshots WHERE timestamp < ?",
            (cutoff,),
        ).rowcount
        if deleted > 0:
            conn.commit()
            logger.info(f"MetricsStore: cleaned {deleted} expired snapshots (>{RETENTION_DAYS}d)")


def get_metrics_store() -> MetricsStore:
    """获取全局 MetricsStore 单例"""
    return MetricsStore()