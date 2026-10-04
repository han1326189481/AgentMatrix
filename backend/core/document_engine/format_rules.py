"""format_rules — 格式规则模型与三入口解析（V4.5 尺子的刻度）

三入口:
1. from_template_docx — 模板文档抽取样式（最精确，直接读 Heading/Normal 有效值）
2. from_rules_text   — 格式说明文档解析（.md 文本 / .docx 提取文本后规则化解析）
3. FormatRules(**dict) — 结构化字典（对话描述经 DeepSeek 结构化后走此入口，P1d 接入）

中文排版习惯内置:
- 中文字号映射: 小四=12pt 三号=16pt 等
- 常见字体别名: 宋体/黑体/楷体/仿宋
"""
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field

from core.document_engine.docx_reader import parse_docx, DocxReadError


class Margins(BaseModel):
    top_cm: Optional[float] = None
    bottom_cm: Optional[float] = None
    left_cm: Optional[float] = None
    right_cm: Optional[float] = None


class FontSpec(BaseModel):
    name: Optional[str] = None
    size_pt: Optional[float] = None
    bold: Optional[bool] = None


class FormatRules(BaseModel):
    """格式规则 — 每个字段 None 表示不检查该项"""
    margins: Optional[Margins] = None
    body_font: Optional[FontSpec] = None
    body_line_spacing: Optional[float] = None
    body_first_line_indent_cm: Optional[float] = None
    heading_styles: Optional[Dict[str, FontSpec]] = None  # {"1": FontSpec, "2": ...}
    require_toc: bool = False
    heading_hierarchy_strict: bool = False

    def active_checks(self) -> int:
        """激活的检查项数量（用于合规率分母）"""
        n = 0
        if self.margins:
            n += sum(1 for v in self.margins.model_dump().values() if v is not None)
        if self.body_font:
            n += sum(1 for v in self.body_font.model_dump().values() if v is not None)
        if self.body_line_spacing is not None:
            n += 1
        if self.body_first_line_indent_cm is not None:
            n += 1
        if self.heading_styles:
            for spec in self.heading_styles.values():
                n += sum(1 for v in spec.model_dump().values() if v is not None)
        if self.heading_hierarchy_strict:
            n += 1
        return n


# ── 中文字号映射 ──
CN_SIZE_MAP = {
    "初号": 42.0, "小初": 36.0,
    "一号": 26.0, "小一": 24.0,
    "二号": 22.0, "小二": 18.0,
    "三号": 16.0, "小三": 15.0,
    "四号": 14.0, "小四": 12.0,
    "五号": 10.5, "小五": 9.0,
    "六号": 7.5, "小六": 6.5,
    "七号": 5.5, "八号": 5.0,
}

FONT_ALIASES = ["宋体", "黑体", "楷体", "仿宋", "微软雅黑", "华文中宋", "Times New Roman",
                "Arial", "Calibri", "等线", "思源黑体", "思源宋体"]

HEADING_WORDS = {
    "一级标题": "1", "二级标题": "2", "三级标题": "3", "四级标题": "4",
    "1级标题": "1", "2级标题": "2", "3级标题": "3", "4级标题": "4",
    "章标题": "1", "节标题": "2",
}


def _size_pt_from_text(text: str) -> Optional[float]:
    """从文本提取字号: '小四'→12，'12pt'→12，'四号字'→14"""
    for cn, pt in CN_SIZE_MAP.items():
        if cn in text:
            return pt
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:pt|磅|号)", text)
    if m:
        v = float(m.group(1))
        # "12号" 不是合法说法，直接当 pt
        return v
    return None


def _font_name_from_text(text: str) -> Optional[str]:
    for f in FONT_ALIASES:
        if f.lower() in text.lower():
            return f
    return None


def _line_spacing_from_text(text: str) -> Optional[float]:
    """'1.5倍行距' / '行距1.5' / '行距为1.5倍' → 1.5"""
    m = re.search(r"(?:行距|行间距)[^0-9]{0,4}(\d+(?:\.\d+)?)\s*倍", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*倍(?:行距|行间距|行高)", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(?:行距|行间距)[^0-9]{0,4}(\d+(?:\.\d+)?)(?!\s*(?:pt|磅|cm|厘米))", text)
    if m and 1.0 <= float(m.group(1)) <= 3.0:
        return float(m.group(1))
    return None


def _margins_from_text(text: str) -> Optional[Dict[str, float]]:
    """'页边距: 上下2.54cm, 左右3.17cm' / '上边距3cm'"""
    result: Dict[str, float] = {}
    # 上下 X / 左右 Y 形式
    m = re.search(r"[上下]\s*(?:边距)?\s*(?:为|是|:|：)?\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)", text)
    if m:
        v = float(m.group(1))
        result["top_cm"] = v
        result["bottom_cm"] = v
    m = re.search(r"[左右]\s*(?:边距)?\s*(?:为|是|:|：)?\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)", text)
    if m:
        v = float(m.group(1))
        result["left_cm"] = v
        result["right_cm"] = v
    if not result:
        for side, key in [("上", "top_cm"), ("下", "bottom_cm"), ("左", "left_cm"), ("右", "right_cm")]:
            m = re.search(rf"{side}边距\s*(?:为|是|:|：)?\s*(\d+(?:\.\d+)?)", text)
            if m:
                result[key] = float(m.group(1))
    return result or None


def parse_rules_text(text: str) -> FormatRules:
    """从格式说明文本（markdown 或纯文本）解析规则

    支持的典型表述（按行扫描，命中即提取）:
    - 正文: 宋体小四 / 正文字号为小四
    - 行距 1.5 倍 / 1.5倍行距
    - 页边距: 上下 2.54cm 左右 3.17cm
    - 一级标题: 黑体三号 / 二级标题 楷体四号加粗
    - 首行缩进 2 字符 (按小四 12pt 折算 ≈ 0.85cm；实际按字号×2/28.35)
    - 需要目录 / 包含目录
    - 标题不得跳级 / 严格标题层级
    """
    rules: Dict[str, Any] = {}
    margins: Dict[str, float] = {}

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # 页边距
        if "边距" in line:
            found = _margins_from_text(line)
            if found:
                margins.update(found)
                continue

        # 行距（正文语境）
        if "行距" in line or "行间距" in line:
            ls = _line_spacing_from_text(line)
            if ls is not None and "标题" not in line:
                rules["body_line_spacing"] = ls
                continue

        # 首行缩进
        if "首行缩进" in line:
            m = re.search(r"首行缩进\s*(\d+(?:\.\d+)?)\s*(?:个?字符|字)", line)
            if m:
                chars = float(m.group(1))
                # 折算: 字符数 × 正文字号(pt) / 28.35 = cm；字号未知时按小四 12pt
                size = _size_pt_from_text(line)
                if size is None and isinstance(rules.get("body_font"), dict):
                    size = rules["body_font"].get("size_pt")
                size = size or 12.0
                rules["body_first_line_indent_cm"] = round(chars * size / 28.35, 2)
                continue
            m = re.search(r"首行缩进\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)", line)
            if m:
                rules["body_first_line_indent_cm"] = float(m.group(1))
                continue

        # 标题样式
        if "标题" in line:
            heading_key = None
            for word, key in HEADING_WORDS.items():
                if word in line:
                    heading_key = key
                    break
            if heading_key:
                spec: Dict[str, Any] = {}
                pt = _size_pt_from_text(line)
                fname = _font_name_from_text(line)
                if pt:
                    spec["size_pt"] = pt
                if fname:
                    spec["name"] = fname
                if "加粗" in line or "粗体" in line:
                    spec["bold"] = True
                if spec:
                    rules.setdefault("heading_styles", {})[heading_key] = spec
                    continue

        # 目录要求
        if re.search(r"(需要|必须|包含|要有).{0,4}目录", line):
            rules["require_toc"] = True
            continue
        # 跳级禁止
        if "跳级" in line or ("标题" in line and "层级" in line and ("严格" in line or "不得" in line or "禁止" in line)):
            rules["heading_hierarchy_strict"] = True
            continue

        # 正文（放在标题之后判断，避免"正文一级标题"误命中）
        if "正文" in line or "body" in line.lower():
            spec: Dict[str, Any] = {}
            pt = _size_pt_from_text(line)
            fname = _font_name_from_text(line)
            if pt:
                spec["size_pt"] = pt
            if fname:
                spec["name"] = fname
            if spec:
                existing = rules.get("body_font") or {}
                existing.update(spec)
                rules["body_font"] = existing
                continue

    if margins:
        rules["margins"] = margins
    return FormatRules(**rules)


def from_template_docx(template_path: Path) -> FormatRules:
    """入口1: 从模板 docx 抽取样式规则（以实际生效值为准）"""
    result = parse_docx(template_path)
    audit = result["format_audit"]
    rules: Dict[str, Any] = {}

    if audit["sections"]:
        m = audit["sections"][0]["margins"]
        if any(v is not None for v in m.values()):
            rules["margins"] = {k: v for k, v in m.items() if v is not None}

    # 正文: 取 Normal 非空段落的主流体（出现最多的组合）
    from collections import Counter
    body_counter: Counter = Counter()
    body_ls_counter: Counter = Counter()
    heading_specs: Dict[str, Dict[str, Any]] = {}
    for p in audit["paragraphs"]:
        if p["is_empty"]:
            continue
        if p["level"]:
            key = str(p["level"])
            spec: Dict[str, Any] = {}
            if p["font"]["name"]:
                spec["name"] = p["font"]["name"]
            if p["font"]["size_pt"]:
                spec["size_pt"] = p["font"]["size_pt"]
            if spec and key not in heading_specs:
                heading_specs[key] = spec
        else:
            body_counter[(p["font"]["name"], p["font"]["size_pt"])] += 1
            if p["line_spacing"]:
                body_ls_counter[p["line_spacing"]] += 1

    if body_counter:
        (fname, fsize), _ = body_counter.most_common(1)[0]
        spec = {}
        if fname:
            spec["name"] = fname
        if fsize:
            spec["size_pt"] = fsize
        if spec:
            rules["body_font"] = spec
    if body_ls_counter:
        rules["body_line_spacing"] = body_ls_counter.most_common(1)[0][0]
    if heading_specs:
        rules["heading_styles"] = heading_specs

    return FormatRules(**rules)


def from_rules_doc(doc_path: Path) -> FormatRules:
    """入口2: 从格式说明文档解析（支持 .md/.txt 直接读，.docx 提取文本后解析）"""
    if doc_path.suffix.lower() in {".md", ".txt"}:
        text = doc_path.read_text(encoding="utf-8", errors="replace")
        return parse_rules_text(text)
    if doc_path.suffix.lower() == ".docx":
        result = parse_docx(doc_path)
        return parse_rules_text(result["content_md"])
    raise DocxReadError(f"不支持的规则文件类型: {doc_path.suffix}（支持 .md/.txt/.docx）", 400)
