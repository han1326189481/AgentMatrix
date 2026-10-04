"""doc_task_detector — 文档任务识别（V4.5 Agent 集成入口）

职责:
1. 文件发现（双通道）:
   a. 显式通道: context.documents（前端文件选择器传入）
   b. 隐式通道: user_input 中提到的文件名（后缀匹配 + workspace 文件名子串匹配）
2. 意图判定（确定性关键词规则，零 LLM）:
   - repair_docx: 修复/规范/调整格式 + target.docx + rules
   - generate_docx: 生成/写一份/创建 + rules（target 可选=模板）
   - fix_pptx: 清理/修复 + target.pptx
   - read_only: 提到文档但无修改意图（内容注入知识库，由 Writer 正常回答）
   - none: 非文档任务（走原工作流，零开销）
"""
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

from core.document_engine.file_ops import get_workspace_dir, FileOpsError

logger = logging.getLogger(__name__)

# 意图关键词（按优先级）
_REPAIR_WORDS = ["修复", "修正", "修正格式", "修改格式", "调整格式", "规范格式",
                 "格式修复", "按格式", "按规范修", "改成规范", "整改"]
_GENERATE_WORDS = ["生成", "写一份", "做一份", "创建一份", "输出一份", "生成一份",
                   "写一个文档", "做成word", "做成Word", "转为word", "转成word", "导出为word"]
# PPT 修复动词（目标已是 pptx 时，出现任一动词即判定修复意图）
_FIX_PPTX_VERBS = ["清理", "删除", "删掉", "去掉", "移除", "修复", "修正", "整理"]
_READ_HINT_WORDS = ["读一下", "看看", "总结", "读读", "分析一下", "检查一下", "看一下"]


@dataclass
class DocTask:
    """文档任务描述（序列化后随 Knowledge 输出传递给 Result Agent）"""
    task_type: str = "none"          # repair_docx / generate_docx / fix_pptx / read_only / none
    target_path: Optional[str] = None  # 处理对象（workspace 相对路径）
    rules_path: Optional[str] = None   # 格式规则文档路径
    template_path: Optional[str] = None  # 生成模式的模板（target 为 docx 且任务是生成时）
    reference_paths: List[str] = field(default_factory=list)  # 参考文档（只读）
    output_path: Optional[str] = None   # 生成模式的输出路径（自动推导）
    detection_source: str = ""          # explicit / implicit
    reason: str = ""                    # 判定理由（透出给日志/前端）

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, "", [])}


def _workspace_files() -> List[Path]:
    """workspace 内全部文件（扁平列表，深度不限）"""
    ws = get_workspace_dir()
    return [p for p in ws.rglob("*") if p.is_file() and not p.name.endswith(".bak")]


def _extract_explicit_docs(context: Optional[Dict]) -> List[Dict[str, str]]:
    """显式通道: context.documents = [{path, role?}]"""
    if not context or not isinstance(context, dict):
        return []
    docs = context.get("documents", [])
    if not isinstance(docs, list):
        return []
    result = []
    for d in docs:
        if isinstance(d, dict) and d.get("path"):
            result.append({"path": str(d["path"]), "role": d.get("role", "")})
        elif isinstance(d, str):
            result.append({"path": d, "role": ""})
    return result


def _extract_implicit_files(user_input: str, ws_files: List[Path]) -> List[str]:
    """隐式通道: 从 user_input 提取文件名

    1. 文件名匹配（主通道）: workspace 文件名（含扩展名）出现在输入中
       （不用正则反向提取——正则贪婪匹配会把'按格式规范.md'整体吞掉，
         连同前面的介词'按'一起匹配，导致找不到文件）
    2. 相对路径匹配: 用户写了 'docs/测试.docx' 完整相对路径
    3. 无后缀 stem 匹配（补充）: 用户说'把测试文档修一下' 且 workspace 有 '测试文档.docx'
    """
    found: List[str] = []
    ws = get_workspace_dir()
    input_lower = user_input.lower()

    for f in ws_files:
        if f.suffix.lower() not in {".docx", ".pptx", ".md", ".txt"}:
            continue
        rel = str(f.relative_to(ws)).replace("\\", "/")
        # 1. 文件名（含扩展名）出现在输入中
        if f.name.lower() in input_lower:
            if rel not in found:
                found.append(rel)
            continue
        # 2. 完整相对路径出现在输入中
        if rel.lower() in input_lower:
            if rel not in found:
                found.append(rel)
            continue
        # 3. 无后缀 stem 匹配 — 仅当还没找到同类型文件时补充（防误匹配）
        if not any(p.endswith(f.suffix.lower()) for p in found):
            stem = f.stem
            if len(stem) >= 2 and stem in user_input:
                if rel not in found:
                    found.append(rel)

    return found


def _classify_role(path: str, user_input: str) -> str:
    """推断文件角色: rules（规则文档）/ target（处理对象）"""
    name = Path(path).name.lower()
    # 规则文档特征：文件名或用户输入中的规则语境
    rules_name_hints = ["规范", "格式", "要求", "规则", "标准", "spec", "rule", "format"]
    if any(h in name for h in rules_name_hints) and Path(path).suffix.lower() in {".md", ".txt", ".docx"}:
        return "rules"
    if "按" in user_input and Path(path).suffix.lower() == ".md":
        # "按xxx.md" 语境
        return "rules"
    return "target"


def detect_doc_task(user_input: str,
                    context: Optional[Dict] = None) -> DocTask:
    """入口: 识别文档任务。非文档任务返回 task_type='none'（零副作用）"""
    task = DocTask()
    try:
        ws_files = _workspace_files()
    except Exception as e:
        logger.warning(f"doc_task_detector: workspace 扫描失败: {e}")
        return task

    # ── 文件发现 ──
    explicit = _extract_explicit_docs(context)
    implicit = _extract_implicit_files(user_input, ws_files)

    if explicit:
        task.detection_source = "explicit"
        targets = [d for d in explicit if d["role"] != "rules"]
        rules = [d for d in explicit if d["role"] == "rules"]
        # 角色未指定时推断
        if not rules:
            for d in explicit:
                if d["role"] == "" and _classify_role(d["path"], user_input) == "rules":
                    rules = [{"path": d["path"], "role": "rules"}]
                    targets = [t for t in targets if t["path"] != d["path"]]
                    break
        if rules:
            task.rules_path = rules[0]["path"]
        if targets:
            task.target_path = targets[0]["path"]
        task.reference_paths = [t["path"] for t in targets[1:]]
    elif implicit:
        task.detection_source = "implicit"
        # implicit 发现的文件分角色
        for p in implicit:
            if _classify_role(p, user_input) == "rules" and not task.rules_path:
                task.rules_path = p
            elif not task.target_path:
                task.target_path = p
            else:
                task.reference_paths.append(p)

    # 无任何文档引用 → 非文档任务
    if not task.target_path and not task.rules_path:
        return DocTask(task_type="none")

    # ── 意图判定（确定性规则）──
    input_lower = user_input.lower()
    has_pptx_target = bool(task.target_path and task.target_path.lower().endswith(".pptx"))

    # 1. PPT 修复（目标已是 pptx，出现修复动词即判定；对象词仅作日志参考）
    if has_pptx_target:
        if any(v in user_input for v in _FIX_PPTX_VERBS):
            task.task_type = "fix_pptx"
            task.reason = f"检测到 PPT 修复意图 + 目标 {task.target_path}"
            return task
        # 有 pptx 但无修复意图 → 只读
        task.task_type = "read_only"
        task.reason = f"引用 PPT {task.target_path} 但无修复意图"
        return task

    # 2. Word 修复（target docx + rules + 修复词）
    docx_target = bool(task.target_path and task.target_path.lower().endswith(".docx"))
    if docx_target and task.rules_path:
        if any(w in user_input for w in _REPAIR_WORDS):
            task.task_type = "repair_docx"
            task.reason = f"目标 {task.target_path} + 规则 {task.rules_path} + 修复意图"
            return task
        # 无修复词但 target+rules 齐备 → 默认修复（最常见场景）
        task.task_type = "repair_docx"
        task.reason = f"目标+规则齐备，默认修复模式"
        return task

    # 3. Word 生成（生成词 + rules；target 可为模板）
    if any(w in user_input for w in _GENERATE_WORDS):
        if task.rules_path or docx_target or not task.target_path:
            task.task_type = "generate_docx"
            if docx_target:
                # target 是模板
                task.template_path = task.target_path
                task.target_path = None
            # 输出路径自动推导（剥离"生成一份"等动作前缀）
            base = "生成文档.docx"
            m = re.search(r"[\w\u4e00-\u9fff\-]+(?:文档|报告|总结|方案|论文|说明书)", user_input)
            if m:
                name = m.group(0)
                name = re.sub(r"^(?:按|根据|帮我)?(?:生成|写|做|创建|输出|导出|转[为成])+(?:一份|一个|个)?", "", name)
                if name:
                    base = name + ".docx"
            task.output_path = f"generated/{base}"
            task.reason = "生成意图" + (f" + 规则 {task.rules_path}" if task.rules_path else "")
            return task

    # 4. 只读（提到文档、读/总结等意图，或意图不明）
    task.task_type = "read_only"
    task.reason = (f"引用文档 {task.target_path or task.rules_path}，"
                   f"无修改/生成意图" + ("（含读取提示词）" if any(w in user_input for w in _READ_HINT_WORDS) else ""))
    return task
