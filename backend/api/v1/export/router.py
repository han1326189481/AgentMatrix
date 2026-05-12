from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Dict, Any
from pydantic import BaseModel

router = APIRouter()


class ExportRequest(BaseModel):
    content: str
    format: str = "markdown"
    filename: str = "output"


@router.post("/")
async def export_content(request: ExportRequest):
    formats = ["markdown", "ppt", "word", "mindmap"]
    if request.format not in formats:
        raise HTTPException(status_code=400, detail="不支持的导出格式")
    
    if request.format == "markdown":
        return {"status": "success", "content": request.content, "format": "markdown"}
    
    return {"status": "success", "message": f"正在生成{request.format}文件"}


@router.get("/download/{file_id}")
async def download_file(file_id: str):
    return FileResponse(
        f"exports/{file_id}.md",
        media_type="text/markdown",
        filename=f"{file_id}.md"
    )