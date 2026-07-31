"""Sandbox API 路由 — 多沙盒管理接口"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from core.sandbox import get_sandbox_service

router = APIRouter()


class CreateSandboxRequest(BaseModel):
    name: str = Field(default="新对话", description="沙盒名称")


class RenameSandboxRequest(BaseModel):
    name: str = Field(..., description="新名称", min_length=1, max_length=50)


class SandboxResponse(BaseModel):
    id: str
    name: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0


@router.post("", response_model=SandboxResponse)
async def create_sandbox(request: CreateSandboxRequest = CreateSandboxRequest()):
    """创建新沙盒"""
    try:
        service = get_sandbox_service()
        result = service.create(name=request.name)
        return SandboxResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[SandboxResponse])
async def list_sandboxes(include_inactive: bool = False):
    """列出所有沙盒"""
    service = get_sandbox_service()
    sandboxes = service.list_sandboxes(include_inactive=include_inactive)
    return [SandboxResponse(**s) for s in sandboxes]


@router.get("/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(sandbox_id: str):
    """获取沙盒详情"""
    service = get_sandbox_service()
    sandbox = service.get(sandbox_id)
    if not sandbox:
        raise HTTPException(status_code=404, detail=f"沙盒不存在: {sandbox_id}")
    return SandboxResponse(**sandbox)


@router.put("/{sandbox_id}/rename")
async def rename_sandbox(sandbox_id: str, request: RenameSandboxRequest):
    """重命名沙盒"""
    service = get_sandbox_service()
    success = service.rename(sandbox_id, request.name)
    if not success:
        raise HTTPException(status_code=404, detail=f"沙盒不存在: {sandbox_id}")
    return {"status": "success", "sandbox_id": sandbox_id, "name": request.name}


@router.delete("/{sandbox_id}")
async def delete_sandbox(sandbox_id: str):
    """删除沙盒"""
    service = get_sandbox_service()
    success = service.delete(sandbox_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"沙盒不存在: {sandbox_id}")
    return {"status": "success", "message": f"沙盒 {sandbox_id} 已删除"}


@router.get("/{sandbox_id}/history")
async def get_sandbox_history(sandbox_id: str, limit: int = 20):
    """获取沙盒对话历史"""
    service = get_sandbox_service()
    history = service.get_chat_history(sandbox_id, limit=limit)
    return {"sandbox_id": sandbox_id, "messages": history, "count": len(history)}