"""文件操作 API — 安全沙盒（workspace 根目录锁定）

所有路径参数均为相对 workspace 的路径。破坏性操作（覆盖/删除）需显式 confirm 标志。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from core.document_engine.file_ops import (
    list_dir, read_file, write_file, move_path, delete_path,
    search_files, FileOpsError, get_workspace_dir,
)

router = APIRouter()


class FileWriteRequest(BaseModel):
    path: str = Field(..., description="目标文件相对路径")
    content: str = Field(..., description="文本内容")
    confirm_overwrite: bool = Field(default=False, description="覆盖已有文件需显式确认")


class FileMoveRequest(BaseModel):
    path: str = Field(..., description="源路径")
    new_path: str = Field(..., description="目标路径")
    confirm_overwrite: bool = Field(default=False, description="覆盖已有目标需显式确认")


class FileDeleteRequest(BaseModel):
    path: str = Field(..., description="要删除的路径")
    confirm: bool = Field(default=False, description="删除是破坏性操作，必须显式确认")


def _handle(e: FileOpsError):
    raise HTTPException(status_code=e.status_code, detail=str(e))


@router.get("/root")
async def get_root():
    """返回 workspace 根目录绝对路径（供前端提示用户放文件的位置）"""
    return {"root": str(get_workspace_dir())}


@router.get("/list")
async def list_files(path: str = "."):
    """列目录（含子目录树）"""
    try:
        return list_dir(path)
    except FileOpsError as e:
        _handle(e)


@router.get("/read")
async def read_text_file(path: str):
    """读文本文件内容"""
    try:
        return read_file(path)
    except FileOpsError as e:
        _handle(e)


@router.post("/write")
async def write_text_file(req: FileWriteRequest):
    """写/创建文本文件"""
    try:
        return write_file(req.path, req.content, req.confirm_overwrite)
    except FileOpsError as e:
        _handle(e)


@router.post("/move")
async def move_file_or_dir(req: FileMoveRequest):
    """移动/重命名"""
    try:
        return move_path(req.path, req.new_path, req.confirm_overwrite)
    except FileOpsError as e:
        _handle(e)


@router.delete("/delete")
async def delete_file_or_dir(path: str, confirm: bool = False):
    """删除（移入回收站，必须 confirm=true）"""
    try:
        return delete_path(path, confirm)
    except FileOpsError as e:
        _handle(e)


@router.get("/search")
async def search(pattern: str, path: str = "."):
    """按文件名搜索"""
    try:
        return search_files(pattern, path)
    except FileOpsError as e:
        _handle(e)
