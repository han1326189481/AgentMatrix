"""Context API 路由 — 上下文压缩三件套的对外接口

V4.2 前端已建好 ContextBar / ContextPanel / ContextOverflowModal，
但后端此前**没有任何 /context 端点**，UI 只能靠本地估算空转。
本路由把 `core/context_tracker.py` 的编排能力暴露出去。

GET    /api/v1/context/usage?sandbox_id=   — 当前上下文用量快照（含逐轮记录）
GET    /api/v1/context/config              — 阈值配置（前端展示 / 答辩取证）
POST   /api/v1/context/compress            — 手动触发一次压缩
DELETE /api/v1/context/{sandbox_id}        — 清空沙盒上下文（新建沙盒 / 重置对话）
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.context_tracker import get_context_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["context"])


class CompressRequest(BaseModel):
    sandbox_id: Optional[str] = Field(default=None, description="沙盒 ID（缺省为 default 桶）")
    messages: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="待压缩的消息列表（role/content）；缺省用服务端轮次记录重建"
    )
    system_prompt: str = Field(default="", description="系统提示词（压缩后置顶保留）")


@router.get("/usage")
async def get_context_usage(sandbox_id: Optional[str] = Query(default=None)):
    """上下文用量快照（total/limit/usage_ratio + 逐轮记录）"""
    try:
        return get_context_tracker().snapshot(sandbox_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取上下文用量异常: {e}")


@router.get("/config")
async def get_context_config():
    """上下文阈值配置（上限 / 压缩阈值 / 溢出阈值 / 保留轮数）"""
    try:
        return get_context_tracker().config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取上下文配置异常: {e}")


@router.post("/compress")
async def compress_context(body: CompressRequest = CompressRequest()):
    """手动触发一次上下文压缩，返回压缩后消息列表与节省的 token"""
    try:
        return get_context_tracker().compress_now(
            body.sandbox_id, messages=body.messages, system_prompt=body.system_prompt
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上下文压缩异常: {e}")


@router.delete("/{sandbox_id}")
async def clear_context(sandbox_id: str):
    """清空指定沙盒的轮次记录与接续摘要"""
    try:
        get_context_tracker().clear(sandbox_id)
        return {"status": "success", "sandbox_id": sandbox_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空上下文异常: {e}")
