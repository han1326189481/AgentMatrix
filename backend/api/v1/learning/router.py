"""Learning Engine API 路由

GET  /api/v1/learning/stats    — 获取学习统计
POST /api/v1/learning/trigger  — 手动触发学习
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

router = APIRouter(prefix="", tags=["learning"])

# 模块级单例，保证学习统计在请求间持久
_learning_engine_instance = None


def _get_learning_engine():
    global _learning_engine_instance
    if _learning_engine_instance is None:
        from core.graphs import get_skill_graph
        from core.graphs.reasoning_graph import ReasoningGraph
        from core.engines.learning_engine import LearningEngine
        _learning_engine_instance = LearningEngine(
            skill_graph=get_skill_graph(),
            reasoning_graph=ReasoningGraph(),
            validator=None,  # PatchValidator 自动创建
        )
    return _learning_engine_instance


class LearningStatsResponse(BaseModel):
    total_sessions: int
    total_validated: int
    total_rejected: int
    deepseek_usage: int
    avg_review_score: float = 0.0
    validator_stats: Optional[Dict[str, Any]] = None


class LearningTriggerRequest(BaseModel):
    user_task: str
    writer_output: str
    skill_path: List[str] = []
    review_score: float


class LearningTriggerResponse(BaseModel):
    knowledge_patches: List[Dict[str, Any]] = []
    reasoning_patches: List[Dict[str, Any]] = []
    workflow_patches: List[Dict[str, Any]] = []
    deepseek_used: bool = False
    validated: int = 0
    rejected: int = 0


def _serialize_patch(patch) -> Dict[str, Any]:
    """序列化 Patch 对象（KnowledgePatch/WorkflowPatch 有 to_dict；ReasoningNode 用 asdict）"""
    if hasattr(patch, "to_dict"):
        return patch.to_dict()
    from dataclasses import asdict
    return asdict(patch)


@router.get("/stats", response_model=LearningStatsResponse)
async def get_learning_stats():
    """获取学习统计"""
    try:
        engine = _get_learning_engine()
        stats = engine.get_stats()
        return LearningStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取学习统计异常: {str(e)}")


@router.post("/trigger", response_model=LearningTriggerResponse)
async def trigger_learning(body: LearningTriggerRequest):
    """手动触发学习

    仅 review_score >= 0.70 的高质量回答会被学习。
    """
    try:
        engine = _get_learning_engine()
        result = engine.learn(
            user_task=body.user_task,
            writer_output=body.writer_output,
            skill_path=body.skill_path,
            review_score=body.review_score,
        )
        return LearningTriggerResponse(
            knowledge_patches=[_serialize_patch(p) for p in result.get("knowledge_patches", [])],
            reasoning_patches=[_serialize_patch(p) for p in result.get("reasoning_patches", [])],
            workflow_patches=[_serialize_patch(p) for p in result.get("workflow_patches", [])],
            deepseek_used=result.get("deepseek_used", False),
            validated=result.get("validated", 0),
            rejected=result.get("rejected", 0),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"触发学习异常: {str(e)}")
