"""docx_modifier — JSON Patch 应用器（V4.5）

设计原则:
- Patch 而非重写: 只改指定属性，绝不重排全文
- op 白名单: 越界 op 直接拒绝
- violation → patch 映射是纯机械的（audit 输出即含 target/index/field/required），
  格式修正场景零云调用；DeepSeek 仅用于内容级修改（后续接入）
"""
import logging
from pathlib import Path
from typing import Dict, Any, List

from docx import Document
from docx.shared import Pt, Cm
from docx.text.paragraph import Paragraph

logger = logging.getLogger(__name__)


class PatchError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# op 白名单
SECTION_OPS = {"set_margin_top_cm", "set_margin_bottom_cm",
               "set_margin_left_cm", "set_margin_right_cm"}
PARA_OPS = {"set_font_size", "set_font_name", "set_font_bold",
            "set_line_spacing", "set_first_line_indent_cm",
            "set_alignment", "set_heading_level", "delete_paragraph", "update_text"}
DOC_OPS = {"insert_heading_text"}  # 文档级（如插入目录标题）


def violations_to_patches(violations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """机械映射: audit violations → patches（确定性，零 LLM）

    映射表:
    - section margins_*      → set_margin_*_cm
    - paragraph font_size    → set_font_size
    - paragraph font_name    → set_font_name
    - paragraph bold         → set_font_bold
    - paragraph line_spacing → set_line_spacing
    - paragraph first_line_indent → set_first_line_indent_cm
    - heading_hierarchy      → set_heading_level（把跳级标题降为上一级+1）
    - toc                    → insert_heading_text（插入目录占位标题）
    """
    patches: List[Dict[str, Any]] = []
    for v in violations:
        target = v.get("target")
        index = v.get("index")
        field = v.get("field")
        required = v.get("required")

        if target == "section":
            side = field.replace("_cm", "")
            patches.append({"target": "section", "index": index,
                            "op": f"set_margin_{side}_cm", "value": required})
        elif target == "paragraph":
            if field == "font_size":
                patches.append({"target": "paragraph", "index": index,
                                "op": "set_font_size", "value": required})
            elif field == "font_name":
                patches.append({"target": "paragraph", "index": index,
                                "op": "set_font_name", "value": required})
            elif field == "bold":
                patches.append({"target": "paragraph", "index": index,
                                "op": "set_font_bold", "value": True})
            elif field == "line_spacing":
                patches.append({"target": "paragraph", "index": index,
                                "op": "set_line_spacing", "value": required})
            elif field == "first_line_indent":
                patches.append({"target": "paragraph", "index": index,
                                "op": "set_first_line_indent_cm", "value": required})
        elif target == "document":
            if field == "heading_hierarchy":
                # jumps 形如 "段落#0 H1→ 段落#2 H3"：后者应改为前级+1
                import re
                actual_text = "; ".join(str(x) for x in v.get("actual", []))
                for m in re.finditer(r"段落#(\d+)\s+H(\d+)\s*[→>]+\s*段落#(\d+)\s+H(\d+)", actual_text):
                    fixed_idx, prev_level = int(m.group(3)), int(m.group(2))
                    patches.append({"target": "paragraph", "index": fixed_idx,
                                    "op": "set_heading_level", "value": prev_level + 1})
            elif field == "toc":
                patches.append({"target": "document", "index": 0,
                                "op": "insert_heading_text", "value": "目录"})
    return patches


def _iter_paragraphs(doc: Document):
    """按 body 顺序取段落（含表格外的全部段落）"""
    from docx.oxml.ns import qn
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)


def apply_patches(docx_path: Path, patches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """应用 patch 列表（应用前自动 .bak 备份）"""
    if not patches:
        return {"status": "success", "applied": 0, "rejected": []}

    # 备份
    bak = docx_path.with_suffix(docx_path.suffix + ".bak")
    import shutil
    shutil.copy2(docx_path, bak)

    doc = Document(str(docx_path))
    paras = list(_iter_paragraphs(doc))

    applied = 0
    rejected: List[Dict[str, Any]] = []

    for patch in patches:
        target = patch.get("target")
        op = patch.get("op")
        index = patch.get("index")
        value = patch.get("value")
        try:
            if target == "section":
                if op not in SECTION_OPS:
                    raise PatchError(f"非法 section op: {op}")
                sec = doc.sections[index]
                side = op.replace("set_margin_", "").replace("_cm", "")
                setattr(sec, f"{side}_margin", Cm(value))
                applied += 1

            elif target == "paragraph":
                if op not in PARA_OPS:
                    raise PatchError(f"非法 paragraph op: {op}")
                if index >= len(paras):
                    raise PatchError(f"段落索引越界: {index}")
                para = paras[index]
                if op == "set_font_size":
                    for run in para.runs:
                        run.font.size = Pt(value)
                    # 无 run 的空段跳过
                    applied += 1
                elif op == "set_font_name":
                    from docx.oxml.ns import qn as _qn
                    for run in para.runs:
                        run.font.name = value
                        rpr = run._element.get_or_add_rPr()
                        rfonts = rpr.find(_qn("w:rFonts"))
                        if rfonts is None:
                            rfonts = rpr.makeelement(_qn("w:rFonts"), {})
                            rpr.append(rfonts)
                        rfonts.set(_qn("w:eastAsia"), value)
                    applied += 1
                elif op == "set_font_bold":
                    for run in para.runs:
                        run.font.bold = value
                    applied += 1
                elif op == "set_line_spacing":
                    para.paragraph_format.line_spacing = float(value)
                    applied += 1
                elif op == "set_first_line_indent_cm":
                    para.paragraph_format.first_line_indent = Cm(value)
                    applied += 1
                elif op == "set_alignment":
                    align_map = {"left": 0, "center": 1, "right": 2, "justify": 3}
                    para.alignment = align_map.get(str(value).lower(), 0)
                    applied += 1
                elif op == "set_heading_level":
                    # 改样式为对应 Heading（保持文本与直接格式）
                    text = para.text
                    new_para = _replace_paragraph(doc, para, text, level=int(value))
                    paras[index] = new_para
                    applied += 1
                elif op == "delete_paragraph":
                    p_el = para._element
                    p_el.getparent().remove(p_el)
                    applied += 1
                elif op == "update_text":
                    if para.runs:
                        para.runs[0].text = value
                        for r in para.runs[1:]:
                            r.text = ""
                    applied += 1

            elif target == "document":
                if op not in DOC_OPS:
                    raise PatchError(f"非法 document op: {op}")
                if op == "insert_heading_text":
                    # 在文首插入标题段
                    from docx.oxml.ns import qn
                    first_p = doc.paragraphs[0] if doc.paragraphs else doc.add_paragraph()
                    new_p = doc.add_paragraph(value, style="Heading 1")
                    first_p._element.addprevious(new_p._element)
                    # 重新缓存段落列表
                    paras = list(_iter_paragraphs(doc))
                    applied += 1
            else:
                raise PatchError(f"非法 target: {target}")
        except PatchError as e:
            rejected.append({"patch": patch, "reason": str(e)})
        except Exception as e:
            rejected.append({"patch": patch, "reason": f"应用失败: {e}"})

    doc.save(str(docx_path))
    logger.info(f"patches applied: {applied}/{len(patches)} (rejected {len(rejected)})")
    return {"status": "success", "applied": applied,
            "rejected": rejected, "backup": str(bak.name)}


def _replace_paragraph(doc: Document, old_para: Paragraph, text: str, level: int) -> Paragraph:
    """用新样式段落替换旧段落（保位置）"""
    new_p = doc.add_paragraph(text, style=f"Heading {level}")
    old_para._element.addnext(new_p._element)
    p_el = old_para._element
    p_el.getparent().remove(p_el)
    return new_p
