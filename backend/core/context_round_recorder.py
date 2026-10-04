"""RoundRecorder — 每轮对话自动记录关键信息

V4.2: 上下文压缩的基础设施。每轮 workflow 完成后自动提取并存储：
- 用户提问 + 关键词
- 解决了什么问题
- 改动了什么内容

用于 ContextCompressor 触发时生成精简的 markdown 摘要。
"""
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class RoundRecord:
    """单轮对话记录"""
    round_number: int
    timestamp: str
    user_question: str
    keywords: List[str] = field(default_factory=list)
    problem_solved: str = ""       # 本轮解决了什么问题
    changes_made: str = ""         # 改动了什么内容
    agent_outputs: Dict[str, str] = field(default_factory=dict)  # agent_id → 输出摘要


class RoundRecorder:
    """每轮对话记录器 — 按沙盒隔离"""

    # 常见提问前缀，用于提取核心关键词
    QUESTION_PREFIXES = re.compile(
        r'^(请问|帮我|麻烦|我想|我要|如何|怎么|怎样|为什么|为何|'
        r'能不能|可以不可以|能不能帮|请帮我|麻烦你|你好|请|'
        r'Write a|Write an|Explain|Describe|What is|How to|Can you|'
        r'Please|Help me|Tell me|Show me|Generate|Create|Make)'
        r'[，,？?！!\s]*',
        re.IGNORECASE
    )

    # 中文标点/虚词分隔符
    SEPARATORS = re.compile(r'[，,。.！!？?；;：:\s\n、的了吗呢吧啊呀]')

    def __init__(self):
        self._records: Dict[str, List[RoundRecord]] = {}  # sandbox_id → records

    def get_records(self, sandbox_id: str) -> List[RoundRecord]:
        """获取指定沙盒的所有轮次记录"""
        return self._records.get(sandbox_id, [])

    def record_round(
        self,
        sandbox_id: str,
        user_input: str,
        workflow_output: Dict[str, Any],
    ) -> RoundRecord:
        """记录一轮对话的关键信息"""
        if sandbox_id not in self._records:
            self._records[sandbox_id] = []

        round_num = len(self._records[sandbox_id]) + 1
        keywords = self._extract_keywords(user_input)
        problem_solved = self._extract_problem_solved(workflow_output)
        changes_made = self._extract_changes_made(workflow_output)
        agent_outputs = self._extract_agent_summaries(workflow_output)

        record = RoundRecord(
            round_number=round_num,
            timestamp=datetime.now().isoformat(),
            user_question=user_input.strip(),
            keywords=keywords,
            problem_solved=problem_solved,
            changes_made=changes_made,
            agent_outputs=agent_outputs,
        )

        self._records[sandbox_id].append(record)
        logger.info(
            f"[RoundRecorder] sandbox={sandbox_id} round={round_num} "
            f"keywords={keywords} solved_len={len(problem_solved)}"
        )
        return record

    def _extract_keywords(self, text: str) -> List[str]:
        """从用户问题中提取核心关键词"""
        cleaned = text.strip().replace('\n', ' ')

        # 去除常见提问前缀
        stripped = self.QUESTION_PREFIXES.sub('', cleaned)

        # 按分隔符拆分
        parts = self.SEPARATORS.split(stripped)
        parts = [p.strip() for p in parts if p.strip() and len(p.strip()) > 1]

        # 过滤纯数字和过短的词
        keywords = []
        for p in parts:
            if len(p) >= 2 and not p.isdigit() and not re.match(r'^[a-zA-Z]$', p):
                keywords.append(p)

        if not keywords and stripped:
            keywords = [stripped[:20]]

        return keywords[:5]  # 最多 5 个关键词

    def _extract_problem_solved(self, workflow_output: Dict[str, Any]) -> str:
        """从 workflow 输出中提取解决了什么问题"""
        final_result = workflow_output.get("final_result", "")

        if not final_result:
            return ""

        # 取 final_result 的前 200 字符作为摘要
        # 同时尝试从 Writer Agent 的输出中提取更精确的摘要
        steps = workflow_output.get("steps", [])
        writer_output = ""
        for step in steps:
            if step.get("agent_id") == "writer" and step.get("success"):
                writer_output = step.get("output", "")

        # 优先使用 Writer 输出的前 150 字符
        source = writer_output if writer_output else final_result
        summary = source[:200].strip()
        if len(source) > 200:
            summary += "..."

        return summary

    def _extract_changes_made(self, workflow_output: Dict[str, Any]) -> str:
        """从 workflow 输出中提取改动了什么"""
        steps = workflow_output.get("steps", [])
        result_output = ""

        for step in steps:
            if step.get("agent_id") == "result" and step.get("success"):
                result_output = step.get("output", "")

        if not result_output:
            # 没有 Result Agent 输出，使用 final_result
            result_output = workflow_output.get("final_result", "")

        # 检测是否有导出/生成/修改文件等操作
        change_indicators = []
        if "导出" in result_output or "export" in result_output.lower():
            change_indicators.append("导出文件")
        if "生成" in result_output or "create" in result_output.lower():
            change_indicators.append("生成内容")
        if "修改" in result_output or "update" in result_output.lower():
            change_indicators.append("修改内容")
        if "保存" in result_output or "save" in result_output.lower():
            change_indicators.append("保存数据")

        if change_indicators:
            return "、".join(change_indicators)

        # 默认：文本生成
        return "文本生成（无文件操作）"

    def _extract_agent_summaries(self, workflow_output: Dict[str, Any]) -> Dict[str, str]:
        """提取各 Agent 输出的简短摘要"""
        summaries = {}
        steps = workflow_output.get("steps", [])
        for step in steps:
            agent_id = step.get("agent_id", "")
            output = step.get("output", "")
            if output and step.get("success"):
                summaries[agent_id] = output[:100] + ("..." if len(output) > 100 else "")
        return summaries

    def clear_sandbox(self, sandbox_id: str) -> None:
        """清除指定沙盒的所有记录"""
        self._records.pop(sandbox_id, None)


# 全局单例
_round_recorder: Optional[RoundRecorder] = None


def get_round_recorder() -> RoundRecorder:
    """获取 RoundRecorder 全局单例"""
    global _round_recorder
    if _round_recorder is None:
        _round_recorder = RoundRecorder()
    return _round_recorder