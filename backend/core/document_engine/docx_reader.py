"""docx_reader — Word 读取: 内容 Markdown + 格式审计表（V4.5 尺子的读数端）

设计原则:
- 一次遍历同时产出两个通道:
  1. content_md  — 语义内容（标题层级/段落/表格/列表），给 LLM 理解
  2. format_audit — 精确格式数值（字号/字体/行距/边距/对齐/缩进），给尺子比对
- 字号/行距带样式继承回退链（run → style → base_style → None）
- 单位统一: 字号 pt、行距倍数、长度 cm（python-docx Emu 对象有 .pt/.cm）
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.table import Table
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)

# 本地化样式名 → 标题级别
_HEADING_MAP = {
    "heading 1": 1, "heading 2": 2, "heading 3": 3,
    "heading 4": 4, "heading 5": 5, "heading 6": 6,
    "标题 1": 1, "标题 2": 2, "标题 3": 3, "标题 4": 4, "标题 5": 5, "标题 6": 6,
}

_ALIGN_MAP = {
    WD_ALIGN_PARAGRAPH.LEFT: "left",
    WD_ALIGN_PARAGRAPH.CENTER: "center",
    WD_ALIGN_PARAGRAPH.RIGHT: "right",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
}


class DocxReadError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _heading_level(style_name: str) -> Optional[int]:
    """样式名 → 标题级别（非标题返回 None）"""
    if not style_name:
        return None
    return _HEADING_MAP.get(style_name.strip().lower())


def _effective_font(run: Any, para_style: Any) -> Dict[str, Any]:
    """字号/字体继承链: run → style → base_style"""
    size_pt = run.font.size.pt if run.font.size else None
    name = run.font.name
    bold = run.font.bold

    s = para_style
    hops = 0
    while s is not None and hops < 6:
        if size_pt is None and s.font.size is not None:
            size_pt = s.font.size.pt
        # python-docx 对中文字体需读 rFonts eastAsia，这里取主名即可
        if name is None and s.font.name is not None:
            name = s.font.name
        if bold is None and s.font.bold is not None:
            bold = s.font.bold
        if size_pt is not None and name is not None:
            break
        s = s.base_style
        hops += 1

    # 中文字体名（宋体等）存在 rFonts/eastAsia
    if name is None and run.element.rPr is not None:
        rfonts = run.element.rPr.find(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts")
        if rfonts is not None:
            ea = rfonts.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia")
            if ea:
                name = ea
    return {"name": name, "size_pt": size_pt, "bold": bool(bold) if bold is not None else False}


def _effective_line_spacing(para: Paragraph, para_style: Any) -> Optional[float]:
    """行距: float=倍数；Length→换算为字符行高近似；None→继承样式"""
    ls = para.paragraph_format.line_spacing
    if ls is not None:
        if isinstance(ls, float) or isinstance(ls, int):
            return round(float(ls), 2)
        # Length 对象（磅或cm精确值）→ 折算倍数（12pt 正文近似）
        try:
            return round(ls.pt / 12.0, 2)
        except Exception:
            return None
    s = para_style
    hops = 0
    while s is not None and hops < 6:
        if s.paragraph_format.line_spacing is not None:
            v = s.paragraph_format.line_spacing
            if isinstance(v, (int, float)):
                return round(float(v), 2)
            try:
                return round(v.pt / 12.0, 2)
            except Exception:
                return None
        s = s.base_style
        hops += 1
    return None


def _iter_body(doc: Document):
    """按文档顺序迭代段落与表格（处理段落与表格交错）"""
    from docx.oxml.ns import qn
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def parse_docx(docx_path: Path) -> Dict[str, Any]:
    """解析 Word: 返回 content_md + format_audit + stats"""
    if not docx_path.exists():
        raise DocxReadError(f"文件不存在: {docx_path.name}", 404)
    if docx_path.suffix.lower() != ".docx":
        raise DocxReadError(f"仅支持 .docx（当前: {docx_path.suffix}）", 400)

    try:
        doc = Document(str(docx_path))
    except Exception as e:
        raise DocxReadError(f"无法打开文档（可能为 .doc 老格式或已损坏）: {e}", 400)

    # ── 节（页面设置）──
    sections: List[Dict[str, Any]] = []
    for i, sec in enumerate(doc.sections):
        sections.append({
            "index": i,
            "page": {
                "width_cm": round(sec.page_width.cm, 2) if sec.page_width else None,
                "height_cm": round(sec.page_height.cm, 2) if sec.page_height else None,
            },
            "margins": {
                "top_cm": round(sec.top_margin.cm, 2) if sec.top_margin else None,
                "bottom_cm": round(sec.bottom_margin.cm, 2) if sec.bottom_margin else None,
                "left_cm": round(sec.left_margin.cm, 2) if sec.left_margin else None,
                "right_cm": round(sec.right_margin.cm, 2) if sec.right_margin else None,
            },
        })

    # ── 正文遍历: 内容 + 格式 ──
    md_lines: List[str] = []
    paragraphs_audit: List[Dict[str, Any]] = []
    tables_audit: List[Dict[str, Any]] = []
    headings: List[Dict[str, Any]] = []
    para_index = 0
    table_index = 0

    for block in _iter_body(doc):
        if isinstance(block, Table):
            # 表格 → Markdown + 审计
            rows = [[cell.text.strip() for cell in row.cells] for row in block.rows]
            if rows:
                md_lines.append("")
                md_lines.append("| " + " | ".join(rows[0]) + " |")
                md_lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
                for r in rows[1:]:
                    md_lines.append("| " + " | ".join(r) + " |")
                md_lines.append("")
            tables_audit.append({
                "index": table_index,
                "rows": len(block.rows),
                "cols": len(block.columns),
                "first_row": rows[0] if rows else [],
            })
            table_index += 1
            continue

        para: Paragraph = block
        text = para.text.strip()
        style_name = para.style.name if para.style else ""
        level = _heading_level(style_name)

        # 格式审计（跳过完全空段落的内容记录，但保留计数）
        font_info = {"name": None, "size_pt": None, "bold": False}
        if para.runs:
            font_info = _effective_font(para.runs[0], para.style)
        align = _ALIGN_MAP.get(para.alignment, "left" if para.alignment is None else str(para.alignment))
        indent = para.paragraph_format.first_line_indent
        audit_item = {
            "index": para_index,
            "style": style_name,
            "level": level,
            "text_head": text[:40],
            "font": font_info,
            "line_spacing": _effective_line_spacing(para, para.style),
            "alignment": align,
            "first_line_indent_cm": round(indent.cm, 2) if indent else 0.0,
            "is_empty": not text,
        }
        paragraphs_audit.append(audit_item)

        # 内容 Markdown
        if text:
            if level:
                md_lines.append("")
                md_lines.append("#" * level + " " + text)
                headings.append({"index": para_index, "level": level, "text": text})
            elif style_name.lower() in ("list paragraph", "列表段落") or text.startswith(("•", "- ", "* ")):
                md_lines.append("- " + text.lstrip("•- ").rstrip())
            else:
                md_lines.append("")
                md_lines.append(text)
        para_index += 1

    # ── 默认样式探测（Normal 样式的字号/字体，正文规范的参照）──
    default_font = {}
    try:
        normal = doc.styles["Normal"]
        default_font = {
            "name": normal.font.name,
            "size_pt": normal.font.size.pt if normal.font.size else None,
        }
    except Exception:
        pass

    content_md = "\n".join(md_lines).strip()
    # 层级跳级检测（H1→H3 之类）
    hierarchy_jumps = []
    for a, b in zip(headings, headings[1:]):
        if b["level"] - a["level"] > 1:
            hierarchy_jumps.append(
                f"段落#{a['index']} H{a['level']}→ 段落#{b['index']} H{b['level']}")

    return {
        "file_name": docx_path.name,
        "content_md": content_md,
        "format_audit": {
            "sections": sections,
            "paragraphs": paragraphs_audit,
            "tables": tables_audit,
            "default_font": default_font,
        },
        "stats": {
            "total_paragraphs": para_index,
            "non_empty_paragraphs": sum(1 for p in paragraphs_audit if not p["is_empty"]),
            "total_tables": table_index,
            "headings": headings,
            "hierarchy_jumps": hierarchy_jumps,
        },
    }
