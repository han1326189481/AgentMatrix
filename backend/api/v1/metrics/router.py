from fastapi import APIRouter, Depends
from typing import Dict, Any
from app.dependencies import get_agent_registry
from app.config import settings
import time
import psutil
import os

router = APIRouter()

_metrics_data = {
    "total_requests": 0,
    "api_calls": 0,
    "local_executions": 0,
    "cloud_executions": 0,
    "cost_saved": 0.0,
    "start_time": time.time()
}


@router.get("/")
async def get_metrics(registry=Depends(get_agent_registry)):
    cpu_usage = psutil.cpu_percent()
    memory_usage = psutil.virtual_memory().percent
    uptime = time.time() - _metrics_data["start_time"]

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
            "disk_usage": psutil.disk_usage('/').percent
        },
        "workflow": {
            "total_requests": _metrics_data["total_requests"],
            "api_calls": _metrics_data["api_calls"],
            "local_executions": _metrics_data["local_executions"],
            "cloud_executions": _metrics_data["cloud_executions"],
            "cost_saved": _metrics_data["cost_saved"]
        },
        "agents": registry.get_all_agent_statuses()
    }


@router.get("/system")
async def get_system_metrics():
    return {
        "cpu_usage": psutil.cpu_percent(),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "process_count": len(psutil.pids())
    }


@router.post("/increment/{metric_type}")
async def increment_metric(metric_type: str, value: float = 1.0):
    if metric_type in _metrics_data:
        if isinstance(_metrics_data[metric_type], int):
            _metrics_data[metric_type] += int(value)
        elif isinstance(_metrics_data[metric_type], float):
            _metrics_data[metric_type] += value
    return {"status": "success", "metric": metric_type, "value": value}


def _format_uptime(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours}h {minutes}m {secs}s"


def get_metrics_store() -> Dict[str, Any]:
    return _metrics_data
