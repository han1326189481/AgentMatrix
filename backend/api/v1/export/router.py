"""导出 API — V3 实装版

支持四种格式导出：
- markdown: 直接保存 .md 文件
- docx: mistune + python-docx 生成结构化 Word（保留标题层级/列表/表格/代码块）
- pptx: mistune + python-pptx 生成 PPT（按 H2 智能分页）
- mindmap: mistune + pyecharts 生成思维导图 HTML（交互式 Tree）

文件落盘到 backend/exports/，通过 /download/{filename} 接口下载。
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# 使用绝对路径，避免 cwd 不一致导致文件丢失
EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)


def _resolve_export_path(filename: str) -> str:
    """把用户提供的文件名收敛为 EXPORT_DIR 内的安全绝对路径。

    安全约束（P0）：
    - 禁止任何目录分隔符（'/'、'\\'）、上溯序列（'..'）与盘符（':'）；
    - 最终解析路径必须仍位于 EXPORT_DIR 内（双保险，防符号链接/相对路径绕过）。

    非法输入抛 HTTPException(400)，避免经由 filename 造成任意路径写入/读取。
    """
    raw = (filename or "").strip()
    if not raw or any(sep in raw for sep in ("/", "\\")) or ".." in raw or ":" in raw:
        raise HTTPException(status_code=400, detail="非法文件名")
    safe_name = os.path.basename(raw)
    if not safe_name or safe_name in (".", ".."):
        raise HTTPException(status_code=400, detail="非法文件名")
    filepath = os.path.join(EXPORT_DIR, safe_name)
    if os.path.dirname(os.path.realpath(filepath)) != os.path.realpath(EXPORT_DIR):
        raise HTTPException(status_code=400, detail="非法文件名")
    return filepath


class ExportRequest(BaseModel):
    content: str
    format: str
    filename: str = None


@router.post("/markdown")
async def export_markdown(request: ExportRequest):
    """导出为 Markdown 文件"""
    filename = request.filename or f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    if not filename.endswith('.md'):
        filename += '.md'
    filepath = _resolve_export_path(filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(request.content)
        logger.info(f"Markdown exported: {filename} ({len(request.content)} chars)")
        return {
            "status": "success",
            "format": "markdown",
            "filename": filename,
            "filepath": filepath
        }
    except Exception as e:
        logger.error(f"Markdown export failed: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {e}")


@router.post("/docx")
async def export_docx(request: ExportRequest):
    """导出为 Word 文档（结构化，保留标题/列表/表格/代码块）"""
    filename = request.filename or f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    if not filename.endswith('.docx'):
        filename += '.docx'
    filepath = _resolve_export_path(filename)

    try:
        from core.export.converter import convert_to_docx
        convert_to_docx(request.content, filepath)
        return {
            "status": "success",
            "format": "docx",
            "filename": filename,
            "filepath": filepath
        }
    except ImportError as e:
        logger.error(f"Export deps missing: {e}")
        raise HTTPException(status_code=500, detail="导出依赖未安装（python-docx/mistune）")
    except Exception as e:
        logger.error(f"DOCX export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出失败: {e}")


@router.post("/pptx")
async def export_pptx(request: ExportRequest):
    """导出为 PowerPoint 演示文稿（按 H2 智能分页）"""
    filename = request.filename or f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
    if not filename.endswith('.pptx'):
        filename += '.pptx'
    filepath = _resolve_export_path(filename)

    try:
        from core.export.converter import convert_to_pptx
        convert_to_pptx(request.content, filepath)
        return {
            "status": "success",
            "format": "pptx",
            "filename": filename,
            "filepath": filepath
        }
    except ImportError as e:
        logger.error(f"Export deps missing: {e}")
        raise HTTPException(status_code=500, detail="导出依赖未安装（python-pptx/mistune）")
    except Exception as e:
        logger.error(f"PPTX export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出失败: {e}")


@router.post("/mindmap")
async def export_mindmap(request: ExportRequest):
    """导出为思维导图 HTML（pyecharts Tree 渲染，交互式）"""
    filename = request.filename or f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    if not filename.endswith('.html'):
        filename += '.html'
    filepath = _resolve_export_path(filename)

    try:
        from core.export.converter import convert_to_mindmap
        convert_to_mindmap(request.content, filepath)
        return {
            "status": "success",
            "format": "mindmap",
            "filename": filename,
            "filepath": filepath
        }
    except ImportError as e:
        logger.error(f"Export deps missing: {e}")
        raise HTTPException(status_code=500, detail="导出依赖未安装（pyecharts/mistune）")
    except Exception as e:
        logger.error(f"Mindmap export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出失败: {e}")


@router.get("/download/{filename}")
async def download_file(filename: str):
    """下载已生成的导出文件"""
    # 路径收敛与校验统一由 _resolve_export_path 负责
    filepath = _resolve_export_path(filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"文件 {filename} 不存在或已过期")

    # 根据扩展名设置 media_type
    ext = os.path.splitext(filename)[1].lower()
    media_types = {
        '.md': 'text/markdown',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.html': 'text/html',
    }
    media_type = media_types.get(ext, 'application/octet-stream')

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type=media_type
    )


@router.get("/list")
async def list_exports():
    """列出所有已导出的文件"""
    files = []
    for filename in os.listdir(EXPORT_DIR):
        filepath = _resolve_export_path(filename)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            files.append({
                "filename": filename,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    # 按创建时间倒序
    files.sort(key=lambda x: x['created'], reverse=True)
    return {"exports": files, "count": len(files)}
