"""Learning Engine API 路由

GET  /api/v1/learning/stats              — 获取学习统计
POST /api/v1/learning/trigger            — 手动触发学习（旧接口，保留兼容）

自学习三层筛网 + 待审队列（2026-09-24 新增）:
GET  /api/v1/learning/pending            — 待审队列列表（可按状态/类型过滤）
GET  /api/v1/learning/pending/{id}       — 单条详情（含权威出处与各层判定）
POST /api/v1/learning/pending/{id}/approve — 审批通过（真正写入图谱 / 技能书）
POST /api/v1/learning/pending/{id}/reject  — 审批拒绝
GET  /api/v1/learning/audit              — 筛网审计账本（每次运行一行，供取证）
GET  /api/v1/learning/filter-config      — 当前筛网参数（质量门槛 / 严格模式 / 自动入库）
"""

from fastapi import APIRouter, HTTPException, Query
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


def _get_intake():
    from core.engines.learning_intake import get_learning_intake
    return get_learning_intake()


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


class PendingItem(BaseModel):
    id: str
    kind: str
    status: str
    created_at: str = ""
    domain: str = "root"
    source: str = "auto_learn"
    trigger: Dict[str, Any] = {}
    filter: Dict[str, Any] = {}
    evidence: List[Dict[str, Any]] = []
    payload: Dict[str, Any] = {}
    review: Dict[str, Any] = {}


class PendingListResponse(BaseModel):
    total: int
    stats: Dict[str, Any] = {}
    items: List[PendingItem] = []


class ReviewActionRequest(BaseModel):
    note: str = ""


class ReviewActionResponse(BaseModel):
    ok: bool
    id: str = ""
    kind: str = ""
    error: str = ""


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
    """手动触发学习（旧接口：直接走 LearningEngine，不经过三层筛网）

    ⚠️ 自学习常态化路径是工作流内的 `learning_intake`（过三层筛网后落待审队列）。
    本接口仅用于人工调试，产出不写待审队列。
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


# ============================================================
# 待审队列（三层筛网产出的人工审批入口）
# ============================================================

@router.get("/pending", response_model=PendingListResponse)
async def list_pending(
    status: Optional[str] = Query(default="pending", description="pending/approved/rejected；传 all 表示全部"),
    kind: Optional[str] = Query(default=None, description="knowledge/skill"),
    limit: int = Query(default=200, ge=1, le=1000),
):
    """待审学习队列列表（默认只看 pending，按时间倒序）"""
    try:
        store = _get_intake().store
        st = None if (status in (None, "", "all")) else status
        items = store.list_items(status=st, kind=kind, limit=limit)
        return PendingListResponse(
            total=len(items),
            stats=store.stats(),
            items=[PendingItem(**it) for it in items],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取待审队列异常: {str(e)}")


@router.get("/pending/{item_id}", response_model=PendingItem)
async def get_pending_item(item_id: str):
    """单条待审详情（含权威出处与三层筛网逐层判定）"""
    try:
        record = _get_intake().store.get(item_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取条目异常: {str(e)}")
    if record is None:
        raise HTTPException(status_code=404, detail=f"条目不存在: {item_id}")
    return PendingItem(**record)


@router.post("/pending/{item_id}/approve", response_model=ReviewActionResponse)
async def approve_pending_item(item_id: str, body: ReviewActionRequest = None):
    """审批通过 —— 真正写入知识图谱 / 技能书（技能补丁会 +1 版本号）"""
    try:
        res = _get_intake().approve(item_id, note=(body.note if body else ""))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审批异常: {str(e)}")
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "审批失败"))
    return ReviewActionResponse(ok=True, id=res.get("id", item_id), kind=res.get("kind", ""))


@router.post("/pending/{item_id}/reject", response_model=ReviewActionResponse)
async def reject_pending_item(item_id: str, body: ReviewActionRequest = None):
    """审批拒绝 —— 条目归档为 rejected，不写入任何位置"""
    try:
        res = _get_intake().reject(item_id, note=(body.note if body else ""))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拒绝异常: {str(e)}")
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "操作失败"))
    return ReviewActionResponse(ok=True, id=res.get("id", item_id))


@router.get("/audit")
async def read_audit(limit: int = Query(default=100, ge=1, le=2000)):
    """筛网审计账本：每次三层筛网运行都留一行（通过/拒绝/入库/审批）"""
    try:
        return {"items": _get_intake().store.read_audit(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取审计账本异常: {str(e)}")


@router.get("/filter-config")
async def get_filter_config():
    """当前三层筛网参数（前端展示 / 答辩取证用）"""
    out: Dict[str, Any] = {}
    try:
        from app.config import settings
        out = {
            "filter_net_enabled": bool(getattr(settings, "filter_net_enabled", True)),
            "filter_min_quality_score": float(getattr(settings, "filter_min_quality_score", 0.80)),
            "filter_max_terms": int(getattr(settings, "filter_max_terms", 6)),
            "filter_require_tier1": bool(getattr(settings, "filter_require_tier1", False)),
            "filter_recheck_enabled": bool(getattr(settings, "filter_recheck_enabled", True)),
            "learning_auto_apply": bool(getattr(settings, "learning_auto_apply", False)),
        }
    except Exception as e:
        out = {"error": str(e)}
    try:
        out["pending_dir"] = _get_intake().store.root
    except Exception:
        pass
    return out
