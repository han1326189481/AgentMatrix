"""工作流 API 路由 - 精简版，编排逻辑统一在 WorkflowService"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Tuple, AsyncGenerator
from app.dependencies import get_agent_registry
from models.workflow import WorkflowInput, WorkflowOutput
from core.workflow.service import WorkflowService
from api.v1.metrics.router import get_metrics_store
import time
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class SimpleCache:
    """带 TTL 的简单内存缓存，支持 hit/miss 统计

    Attributes:
        hits: 累计命中次数
        misses: 累计未命中次数
    """

    def __init__(self, maxsize: int = 100, ttl: int = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.hits = 0
        self.misses = 0

    def __contains__(self, key: str) -> bool:
        if key in self.cache:
            _, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                return True
            del self.cache[key]
        self.misses += 1
        return False

    def __getitem__(self, key: str) -> Any:
        # 直接访问内部缓存，不触发 __contains__，避免调用方 if key in cache: return cache[key]
        # 的 hits 重复计数（__contains__ 已计入一次）
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self.cache[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if len(self.cache) >= self.maxsize:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        self.cache[key] = (value, time.time())

    def clear(self) -> None:
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    @property
    def size(self) -> int:
        return len(self.cache)

    @property
    def hit_rate(self) -> float:
        """缓存命中率（0-1），无请求时返回 0"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self.hits + self.misses
        return {
            "size": self.size,
            "max_size": self.maxsize,
            "ttl": self.ttl,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
            "total_requests": total,
        }


workflow_cache = SimpleCache(maxsize=100, ttl=300)


def _get_workflow_service(registry) -> WorkflowService:
    """获取 WorkflowService 实例"""
    return WorkflowService(registry)


def _cache_key(prefix: str, input_data: WorkflowInput) -> str:
    """生成缓存键"""
    return f"{prefix}_{hash(input_data.user_input)}_{hash(str(input_data.context))}"


@router.post("/execute", response_model=WorkflowOutput)
async def execute_workflow(
    input_data: WorkflowInput,
    registry=Depends(get_agent_registry)
):
    """执行工作流（5 Agent 流水线：knowledge → writer → review → judge → result）"""
    cache_key = _cache_key("workflow", input_data)

    # 调试：记录前端传来的 context（用于诊断上下文记忆问题）
    ctx = input_data.context or {}
    history_len = len(ctx.get("history", [])) if isinstance(ctx.get("history"), list) else 0
    logger.info(f"Workflow request: user_input={input_data.user_input[:50]}... "
                f"history_len={history_len} sandbox_id={input_data.sandbox_id}")

    if cache_key in workflow_cache:
        return workflow_cache[cache_key]

    metrics = get_metrics_store()
    metrics["total_requests"] += 1

    try:
        service = _get_workflow_service(registry)
        result = await service.execute(input_data)

        if result.executed_locally:
            metrics["local_executions"] += 1
            metrics["cost_saved"] += 0.01
        else:
            metrics["cloud_executions"] += 1
            metrics["api_calls"] += 1

        if result.executed_locally and len(result.final_result) < 5000:
            workflow_cache[cache_key] = result

        # 沙盒：保存用户消息和助手回复到沙盒数据库
        if input_data.sandbox_id:
            try:
                from core.sandbox import get_sandbox_service
                svc = get_sandbox_service()
                svc.save_chat_message(input_data.sandbox_id, "user", input_data.user_input)
                svc.save_chat_message(input_data.sandbox_id, "assistant", result.final_result)
                svc.increment_message_count(input_data.sandbox_id)
                logger.debug(f"Saved chat messages to sandbox {input_data.sandbox_id}")
            except Exception as e:
                logger.warning(f"Failed to save chat to sandbox: {e}")

            # 保存工作流执行记录（含每个 Agent 步骤）到沙盒数据库
            # 修复：原 ORM 模型已定义但无写入代码，导致 workflow_executions 表 0 行
            try:
                from core.sandbox import get_sandbox_service
                svc = get_sandbox_service()
                svc.save_workflow_execution(
                    sandbox_id=input_data.sandbox_id,
                    user_input=input_data.user_input,
                    final_result=result.final_result,
                    executed_locally=result.executed_locally,
                    complexity_score=result.complexity_score or 0.0,
                    total_duration=result.total_duration_seconds,
                    steps=[
                        {
                            "agent_id": s.agent_id,
                            "agent_name": s.agent_name,
                            "input": s.input,
                            "output": s.output,
                            "success": s.success,
                            "duration_seconds": s.duration_seconds,
                        }
                        for s in result.steps
                    ],
                )
            except Exception as e:
                logger.warning(f"Failed to save workflow execution to sandbox: {e}")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/parallel", response_model=WorkflowOutput)
async def execute_workflow_parallel(
    input_data: WorkflowInput,
    registry=Depends(get_agent_registry)
):
    """并行执行工作流（当前与串行一致，预留异步优化空间）"""
    return await execute_workflow(input_data, registry)


@router.get("/cache/stats")
async def get_cache_stats():
    return workflow_cache.get_stats()


@router.post("/cache/clear")
async def clear_cache():
    workflow_cache.clear()
    return {"status": "success", "message": "Cache cleared"}


async def execute_workflow_stream(
    input_data: WorkflowInput,
    registry
) -> AsyncGenerator[Dict[str, Any], None]:
    """流式执行工作流，实时返回每个步骤的结果（委托 WorkflowService）"""
    service = WorkflowService(registry)
    async for event in service.execute_stream(input_data):
        yield event