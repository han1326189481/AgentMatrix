"""文档处理 API — Document Engine 接口

P1a: /parse  读取（内容 Markdown + 格式审计表）
P1b: /audit  尺子比对（规则三入口: 模板 docx / 说明文档 md·docx / 内联规则）
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from pathlib import Path

from core.document_engine.file_ops import resolve_workspace_path, FileOpsError
from core.document_engine.docx_reader import parse_docx, DocxReadError
from core.document_engine.format_rules import (
    FormatRules, Margins, FontSpec, from_template_docx, from_rules_doc,
)
from core.document_engine.docx_audit import audit_docx
from core.document_engine.docx_generator import generate_docx, GenerateError
from core.document_engine.pipeline import repair_docx
from core.document_engine.pptx_fixer import fix_pptx, PptxFixError
from core.document_engine.file_ops import get_workspace_dir

router = APIRouter()


class DocumentParseRequest(BaseModel):
    file_path: str = Field(..., description="workspace 内的 docx 相对路径")
    extract: Optional[List[str]] = Field(
        default=None,
        description="提取通道: content(内容md) / format(格式审计)。缺省两者都返回",
    )


class RulesSpec(BaseModel):
    """规则来源（三选一；都为空则返回空规则提示）"""
    template_path: Optional[str] = Field(default=None, description="模板 docx 路径（抽取其样式为规则）")
    rules_path: Optional[str] = Field(default=None, description="格式说明文档路径（.md/.txt/.docx）")
    inline_rules: Optional[FormatRules] = Field(default=None, description="结构化规则（DeepSeek/前端直接给出）")


def _build_rules(spec: Optional[RulesSpec]) -> FormatRules:
    """三入口解析规则"""
    if spec is None:
        raise HTTPException(status_code=400, detail="必须提供 rules（template_path / rules_path / inline_rules 三选一）")
    try:
        if spec.inline_rules is not None and spec.inline_rules.active_checks() > 0:
            return spec.inline_rules
        if spec.template_path:
            return from_template_docx(resolve_workspace_path(spec.template_path))
        if spec.rules_path:
            return from_rules_doc(resolve_workspace_path(spec.rules_path))
    except FileOpsError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except DocxReadError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    raise HTTPException(status_code=400, detail="规则解析结果为空：说明文档中未识别到任何格式规则")


@router.post("/parse")
async def parse_document(req: DocumentParseRequest):
    """解析 Word: 返回内容 Markdown + 格式审计表"""
    try:
        docx_path = resolve_workspace_path(req.file_path)
    except FileOpsError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    try:
        result = parse_docx(docx_path)
    except DocxReadError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档解析内部错误: {e}")

    # 按需裁剪通道（节省 token）
    extract = req.extract
    if extract is not None:
        if "content" not in extract:
            result.pop("content_md", None)
        if "format" not in extract:
            result.pop("format_audit", None)
    return result


class DocumentAuditRequest(BaseModel):
    file_path: str = Field(..., description="被审计的 docx 路径")
    rules: Optional[RulesSpec] = Field(default=None, description="规则来源（三选一）")


@router.post("/audit")
async def audit_document(req: DocumentAuditRequest):
    """尺子比对: 规则 vs 实际格式 → violations + 合规率"""
    rules = _build_rules(req.rules)
    try:
        docx_path = resolve_workspace_path(req.file_path)
    except FileOpsError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    try:
        result = audit_docx(docx_path, rules)
    except DocxReadError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审计内部错误: {e}")
    result["rules_applied"] = rules.model_dump(exclude_none=True)
    return result


class RulesParseRequest(BaseModel):
    rules_path: str = Field(..., description="格式说明文档路径（.md/.txt/.docx）")


@router.post("/rules/parse")
async def parse_rules(req: RulesParseRequest):
    """解析格式说明文档 → FormatRules（预览识别结果）"""
    try:
        path = resolve_workspace_path(req.rules_path)
        rules = from_rules_doc(path)
    except FileOpsError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except DocxReadError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"规则解析内部错误: {e}")
    return {
        "rules_path": req.rules_path,
        "active_checks": rules.active_checks(),
        "rules": rules.model_dump(exclude_none=True),
    }


class DocumentGenerateRequest(BaseModel):
    content_md: str = Field(..., description="Markdown 内容")
    rules: Optional[RulesSpec] = Field(default=None, description="规则来源（三选一；为空则用 Word 默认样式）")
    output_path: str = Field(..., description="输出 docx 相对路径")
    title: Optional[str] = Field(default=None, description="文档主标题（可选，居中不占标题层级）")


@router.post("/generate")
async def generate_document(req: DocumentGenerateRequest):
    """按规则生成合规 Word（生成后自检并返回合规率）"""
    # 规则为空时允许生成（默认样式），有 rules 才构建
    rules = FormatRules()
    if req.rules is not None and (
        req.rules.inline_rules or req.rules.template_path or req.rules.rules_path
    ):
        rules = _build_rules(req.rules)

    # 输出路径在 workspace 内（父目录校验，允许新建文件）
    ws = get_workspace_dir()
    out_abs = (ws / req.output_path).resolve()
    try:
        from core.document_engine.file_ops import _resolve_in_workspace
        _resolve_in_workspace(req.output_path)
    except FileOpsError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    try:
        result = generate_docx(req.content_md, rules, out_abs, req.title)
    except GenerateError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成内部错误: {e}")
    return result


class DocumentModifyRequest(BaseModel):
    file_path: str = Field(..., description="要修复的 docx 路径")
    rules: RulesSpec = Field(..., description="规则来源（三选一，必填）")
    max_rounds: int = Field(default=3, ge=1, le=5, description="验收回路轮次上限")


@router.post("/modify")
async def modify_document(req: DocumentModifyRequest):
    """修改回路: 机械 patch 修复至合规（或降级输出未达标清单）"""
    rules = _build_rules(req.rules)
    try:
        docx_path = resolve_workspace_path(req.file_path)
    except FileOpsError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    try:
        result = repair_docx(docx_path, rules, req.max_rounds)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修改回路内部错误: {e}")
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("detail", "修改失败"))
    # 精简返回（final_audit 的 paragraphs 級明细不需要，只留 violations+合规率）
    fa = result.get("final_audit") or {}
    return {
        "status": result["status"],
        "rounds": result["rounds"],
        "compliance_rate": fa.get("compliance_rate"),
        "checks_passed": fa.get("checks_passed"),
        "checks_total": fa.get("checks_total"),
        "remaining_violations": result.get("remaining_violations", []),
        "history": result.get("history", []),
        "file_path": req.file_path,
    }


class PptxFixRequest(BaseModel):
    file_path: str = Field(..., description="要修复的 pptx 路径")


@router.post("/fix-pptx")
async def fix_pptx_document(req: PptxFixRequest):
    """PPT 轻量修复: 删除空白页 + 清理空文本框（自动备份）"""
    try:
        pptx_path = resolve_workspace_path(req.file_path)
    except FileOpsError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    try:
        return fix_pptx(pptx_path)
    except PptxFixError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PPT 修复内部错误: {e}")
