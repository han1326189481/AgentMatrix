"""docx_audit — 尺子: 格式规则 vs 实际值比对（V4.5）

比对策略:
- 确定性数值比对，容差: 边距 ±0.05cm、字号 ±0.5pt、行距 ±0.05
- 正文段落 = 非空、无标题级别的段落（表格内文本不参与正文字体检查）
- 逐段报告 violation，附"实际值 vs 要求值"，供 DeepSeek 生成 patch
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.document_engine.docx_reader import parse_docx, DocxReadError
from core.document_engine.format_rules import FormatRules

logger = logging.getLogger(__name__)

# 容差
TOL_CM = 0.05
TOL_PT = 0.5
TOL_SPACING = 0.05

_SIDE_CN = {"top_cm": "上", "bottom_cm": "下", "left_cm": "左", "right_cm": "右"}

# 正文检查排除的样式（主标题/列表/题注等非正文段落）
_EXCLUDED_BODY_STYLES = {
    "title", "list bullet", "list number", "list paragraph",
    "caption", "quote", "subtitle",
    "标题", "列表段落", "题注", "引用", "副标题",
}


def _fmt(v) -> str:
    if v is None:
        return "未设置"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def _check_margins(rules: FormatRules, audit: Dict[str, Any],
                   violations: List[Dict[str, Any]], checks: List[bool]) -> None:
    if not rules.margins or not audit["sections"]:
        return
    actual = audit["sections"][0]["margins"]
    for side, required in rules.margins.model_dump().items():
        if required is None:
            continue
        act = actual.get(side)
        # None 视为不合规（继承默认 2.54/3.18? python-docx 返回的是实际值，None 极少见）
        ok = act is not None and abs(act - required) <= TOL_CM
        checks.append(ok)
        if not ok:
            violations.append({
                "target": "section",
                "index": 0,
                "field": side,
                "actual": act,
                "required": required,
                "message": f"页边距 {_SIDE_CN.get(side, side)} {_fmt(act)}cm，要求 {required}cm",
            })


def _check_body(rules: FormatRules, audit: Dict[str, Any],
                violations: List[Dict[str, Any]], checks: List[bool]) -> None:
    body_paras = [p for p in audit["paragraphs"]
                  if not p["is_empty"] and p["level"] is None
                  and (p["style"] or "").strip().lower() not in _EXCLUDED_BODY_STYLES]
    if not body_paras:
        return

    if rules.body_font:
        spec = rules.body_font
        for p in body_paras:
            if spec.size_pt is not None:
                act = p["font"]["size_pt"]
                ok = act is not None and abs(act - spec.size_pt) <= TOL_PT
                if act is not None or spec.size_pt is not None:
                    checks.append(ok)
                    if not ok:
                        violations.append({
                            "target": "paragraph", "index": p["index"], "field": "font_size",
                            "actual": act, "required": spec.size_pt,
                            "message": f"段落#{p['index']} 字号 {_fmt(act)}pt，要求 {spec.size_pt}pt",
                        })
            if spec.name is not None:
                act = p["font"]["name"]
                ok = act is not None and act == spec.name
                checks.append(ok)
                if not ok:
                    violations.append({
                        "target": "paragraph", "index": p["index"], "field": "font_name",
                        "actual": act, "required": spec.name,
                        "message": f"段落#{p['index']} 字体 {_fmt(act)}，要求 {spec.name}",
                    })
            # bold 只在规则要求 True 时检查
            if spec.bold:
                ok = p["font"]["bold"]
                checks.append(ok)
                if not ok:
                    violations.append({
                        "target": "paragraph", "index": p["index"], "field": "bold",
                        "actual": p["font"]["bold"], "required": True,
                        "message": f"段落#{p['index']} 未加粗",
                    })

    if rules.body_line_spacing is not None:
        for p in body_paras:
            act = p["line_spacing"]
            ok = act is not None and abs(act - rules.body_line_spacing) <= TOL_SPACING
            checks.append(ok)
            if not ok:
                violations.append({
                    "target": "paragraph", "index": p["index"], "field": "line_spacing",
                    "actual": act, "required": rules.body_line_spacing,
                    "message": f"段落#{p['index']} 行距 {_fmt(act)}，要求 {rules.body_line_spacing}",
                })

    if rules.body_first_line_indent_cm is not None:
        for p in body_paras:
            act = p["first_line_indent_cm"]
            ok = act is not None and abs(act - rules.body_first_line_indent_cm) <= TOL_CM
            checks.append(ok)
            if not ok:
                violations.append({
                    "target": "paragraph", "index": p["index"], "field": "first_line_indent",
                    "actual": act, "required": rules.body_first_line_indent_cm,
                    "message": f"段落#{p['index']} 首行缩进 {_fmt(act)}cm，要求 {rules.body_first_line_indent_cm}cm",
                })


def _check_headings(rules: FormatRules, audit: Dict[str, Any],
                    violations: List[Dict[str, Any]], checks: List[bool]) -> None:
    if not rules.heading_styles:
        return
    for p in audit["paragraphs"]:
        if p["is_empty"] or p["level"] is None:
            continue
        spec = rules.heading_styles.get(str(p["level"]))
        if not spec:
            continue
        if spec.size_pt is not None:
            act = p["font"]["size_pt"]
            ok = act is not None and abs(act - spec.size_pt) <= TOL_PT
            checks.append(ok)
            if not ok:
                violations.append({
                    "target": "paragraph", "index": p["index"], "field": "font_size",
                    "actual": act, "required": spec.size_pt,
                    "message": f"标题#{p['index']}(H{p['level']}) 字号 {_fmt(act)}pt，要求 {spec.size_pt}pt",
                })
        if spec.name is not None:
            act = p["font"]["name"]
            ok = act is not None and act == spec.name
            checks.append(ok)
            if not ok:
                violations.append({
                    "target": "paragraph", "index": p["index"], "field": "font_name",
                    "actual": act, "required": spec.name,
                    "message": f"标题#{p['index']}(H{p['level']}) 字体 {_fmt(act)}，要求 {spec.name}",
                })


def audit_docx(docx_path: Path, rules: FormatRules) -> Dict[str, Any]:
    """尺子比对: 返回 violations + 合规率"""
    result = parse_docx(docx_path)
    audit = result["format_audit"]
    stats = result["stats"]

    violations: List[Dict[str, Any]] = []
    checks: List[bool] = []

    _check_margins(rules, audit, violations, checks)
    _check_body(rules, audit, violations, checks)
    _check_headings(rules, audit, violations, checks)

    if rules.heading_hierarchy_strict:
        jumps = stats.get("hierarchy_jumps", [])
        ok = not jumps
        checks.append(ok)
        if not ok:
            violations.append({
                "target": "document", "index": None, "field": "heading_hierarchy",
                "actual": jumps, "required": "无跳级",
                "message": f"标题层级跳级: {'; '.join(jumps)}",
            })

    if rules.require_toc:
        has_toc = ("目录" in result["content_md"][:2000]) or bool(stats["headings"])
        checks.append(has_toc)
        if not has_toc:
            violations.append({
                "target": "document", "index": None, "field": "toc",
                "actual": "无目录", "required": "包含目录",
                "message": "文档缺少目录",
            })

    total = len(checks)
    passed = sum(1 for c in checks if c)
    compliance_rate = round(passed / total, 4) if total else 1.0

    return {
        "file_name": docx_path.name,
        "compliance_rate": compliance_rate,
        "checks_total": total,
        "checks_passed": passed,
        "violations": violations,
        "violation_count": len(violations),
    }
