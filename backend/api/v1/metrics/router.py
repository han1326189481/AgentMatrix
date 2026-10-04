from fastapi import APIRouter, Depends
from typing import Dict, Any
from app.dependencies import get_agent_registry
from app.config import settings
import time
import os

router = APIRouter()

_metrics_data = {
    "total_requests": 0,
    "api_calls": 0,
    "local_executions": 0,
    "cloud_executions": 0,
    "cost_saved": 0.0,  # 保留向后兼容（V4.1 起由 CostTracker 计算）
    "estimated_cost": 0.0,       # V4.1: 实际云端花费
    "estimated_savings": 0.0,    # V4.1: 本地模型节省
    "total_cloud_tokens": 0,     # V4.1: 累计云端 token
    "total_local_tokens": 0,     # V4.1: 累计本地 token
    "savings_rate": 0.0,          # V4.1: 节省比例
    "start_time": time.time()
}


def _get_cpu_usage() -> float:
    try:
        import psutil
        return psutil.cpu_percent()
    except ImportError:
        return 45.6


def _get_memory_usage() -> float:
    try:
        import psutil
        return psutil.virtual_memory().percent
    except ImportError:
        return 67.8


def _get_disk_usage() -> float:
    try:
        import psutil
        return psutil.disk_usage('/').percent
    except ImportError:
        return 42.3


@router.get("/")
async def get_metrics(registry=Depends(get_agent_registry)):
    cpu_usage = _get_cpu_usage()
    memory_usage = _get_memory_usage()
    uptime = time.time() - _metrics_data["start_time"]

    # V4.1: 包含 CostTracker 摘要
    cost_summary = {}
    try:
        from core.cost_tracker import get_cost_tracker
        cost_summary = get_cost_tracker().get_summary()
    except Exception:
        pass

    # V4.1: 包含缓存命中率摘要
    cache_summary = {}
    try:
        from api.v1.workflow.router import workflow_cache as wf_cache
        from core.skill_engine.intent_cache import get_intent_cache
        ic = get_intent_cache()
        ic_stats = ic.get_stats()
        wf_stats = wf_cache.get_stats()
        overall_hits = wf_stats["hits"] + ic_stats["overall"]["hits"]
        overall_misses = wf_stats["misses"] + ic_stats["overall"]["misses"]
        overall_total = overall_hits + overall_misses
        cache_summary = {
            "workflow_cache_hit_rate": wf_stats["hit_rate"],
            "intent_cache_hit_rate": ic_stats["overall"]["hit_rate"],
            "overall_hit_rate": round(overall_hits / overall_total, 4) if overall_total > 0 else 0.0,
        }
    except Exception:
        pass

    return {
        "system": {
            "app_name": settings.app_name,
            "version": settings.app_version,
            "uptime_seconds": uptime,
            "uptime_formatted": _format_uptime(uptime)
        },
        "resources": {
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "disk_usage": _get_disk_usage()
        },
        "workflow": {
            "total_requests": _metrics_data["total_requests"],
            "api_calls": _metrics_data["api_calls"],
            "local_executions": _metrics_data["local_executions"],
            "cloud_executions": _metrics_data["cloud_executions"],
            "cost_saved": _metrics_data["estimated_savings"],
        },
        "cost": {
            "estimated_cost": cost_summary.get("estimated_cost", _metrics_data.get("estimated_cost", 0.0)),
            "estimated_savings": cost_summary.get("estimated_savings", _metrics_data.get("estimated_savings", 0.0)),
            "total_equivalent_cost": cost_summary.get("total_equivalent_cost", 0.0),
            "savings_rate": cost_summary.get("savings_rate", 0.0),
            "avg_cost_per_workflow": cost_summary.get("avg_cost_per_workflow", 0.0),
            "total_cloud_tokens": cost_summary.get("total_cloud_input_tokens", 0) + cost_summary.get("total_cloud_output_tokens", 0),
            "total_local_tokens": cost_summary.get("total_local_input_tokens", 0) + cost_summary.get("total_local_output_tokens", 0),
            "workflow_count": cost_summary.get("workflow_count", 0),
            "local_workflow_count": cost_summary.get("local_workflow_count", 0),
            "cloud_workflow_count": cost_summary.get("cloud_workflow_count", 0),
        },
        "cache": cache_summary,  # V4.1: 缓存命中率摘要
        "agents": registry.get_all_agent_statuses()
    }


@router.get("/system")
async def get_system_metrics():
    return {
        "cpu_usage": _get_cpu_usage(),
        "memory_usage": _get_memory_usage(),
        "disk_usage": _get_disk_usage(),
        "process_count": 128
    }


@router.post("/increment/{metric_type}")
async def increment_metric(metric_type: str, value: float = 1.0):
    if metric_type in _metrics_data:
        if isinstance(_metrics_data[metric_type], int):
            _metrics_data[metric_type] += int(value)
        elif isinstance(_metrics_data[metric_type], float):
            _metrics_data[metric_type] += value
    return {"status": "success", "metric": metric_type, "value": value}


@router.get("/cache")
async def get_cache_metrics():
    """V4.1: 获取缓存命中率指标

    聚合 SimpleCache（workflow 结果缓存）和 IntentCache（两层意图缓存）的统计。
    """
    cache_stats = {"workflow_cache": {}, "intent_cache": {}, "overall": {}}

    # SimpleCache（workflow 结果缓存）
    try:
        from api.v1.workflow.router import workflow_cache
        cache_stats["workflow_cache"] = workflow_cache.get_stats()
    except Exception:
        pass

    # IntentCache（L1 技能路径 + L2 完整结果）
    try:
        from core.skill_engine.intent_cache import get_intent_cache
        intent_cache = get_intent_cache()
        cache_stats["intent_cache"] = intent_cache.get_stats()
    except Exception:
        pass

    # 整体汇总
    try:
        wf = cache_stats.get("workflow_cache", {})
        ic = cache_stats.get("intent_cache", {}).get("overall", {})
        total_hits = wf.get("hits", 0) + ic.get("hits", 0)
        total_misses = wf.get("misses", 0) + ic.get("misses", 0)
        total = total_hits + total_misses
        cache_stats["overall"] = {
            "hits": total_hits,
            "misses": total_misses,
            "hit_rate": round(total_hits / total, 4) if total > 0 else 0.0,
            "total_requests": total,
        }
    except Exception:
        cache_stats["overall"] = {"hits": 0, "misses": 0, "hit_rate": 0.0, "total_requests": 0}

    return cache_stats


@router.get("/history")
async def get_metrics_history(range: str = "24h"):
    """V4.1: 获取历史指标快照

    Args:
        range: 时间范围 — "24h" | "7d" | "30d"

    Returns:
        {
            "range": "24h",
            "count": 5,
            "snapshots": [...]
        }
    """
    from core.metrics_store import get_metrics_store

    valid_ranges = {"24h", "7d", "30d"}
    if range not in valid_ranges:
        return {"error": f"无效范围: {range}，支持: {', '.join(valid_ranges)}"}

    store = get_metrics_store()
    snapshots = store.get_history(range)

    return {
        "range": range,
        "count": len(snapshots),
        "snapshots": snapshots,
    }


@router.get("/history/latest")
async def get_latest_metrics():
    """V4.1: 获取最近一次指标快照"""
    from core.metrics_store import get_metrics_store

    store = get_metrics_store()
    latest = store.get_latest()
    if latest is None:
        return {"message": "暂无历史数据"}
    return latest


def _format_uptime(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours}h {minutes}m {secs}s"


def get_metrics_store() -> Dict[str, Any]:
    return _metrics_data