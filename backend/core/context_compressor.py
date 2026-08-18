"""ContextCompressor — 上下文压缩器

V4.2: 当上下文使用率超过阈值时，将历史对话记录压缩为精简的 markdown 摘要。
压缩策略：
- 不调用云端模型（硬编码实现）
- 只保留每轮：用户需求、系统完成了什么、改动了什么
- 生成 markdown 注入回对话上下文
"""
import logging
from typing import List, Dict, Any

from core.context_round_recorder import RoundRecord, get_round_recorder
from core.context_token_counter import ContextUsage, get_token_counter
from app.config import settings

logger = logging.getLogger(__name__)


class ContextCompressor:
    """上下文压缩器 — 将历史对话记录压缩为 markdown 摘要"""

    # 压缩时保留最近 N 轮完整对话（不被压缩）
    KEEP_RECENT = 3

    def __init__(self):
        self._token_counter = get_token_counter()
        self._recorder = get_round_recorder()
        self._compression_count: Dict[str, int] = {}  # sandbox_id → 压缩次数

    def should_compress(self, usage: ContextUsage) -> bool:
        """判断是否需要压缩"""
        return usage.is_over_threshold

    def compress(
        self,
        sandbox_id: str,
        current_messages: List[Dict[str, str]],
        system_prompt: str = "",
    ) -> List[Dict[str, str]]:
        """将历史对话压缩为 markdown 摘要，注入回消息列表

        Args:
            sandbox_id: 沙盒 ID
            current_messages: 当前消息列表 (role/content 格式)
            system_prompt: 系统提示词

        Returns:
            压缩后的消息列表（system prompt + markdown 摘要 + 最近 N 轮）
        """
        records = self._recorder.get_records(sandbox_id)
        if not records:
            logger.info(f"[Compressor] sandbox={sandbox_id} 无历史记录，跳过压缩")
            return current_messages

        # 压缩次数计数
        if sandbox_id not in self._compression_count:
            self._compression_count[sandbox_id] = 0
        self._compression_count[sandbox_id] += 1
        compress_num = self._compression_count[sandbox_id]

        # 生成 markdown 摘要
        markdown = self._generate_markdown(records, compress_num)

        # 保留最近 KEEP_RECENT 轮
        recent = current_messages[-self.KEEP_RECENT * 2:]  # *2 因为每轮有 user+assistant

        # 构建压缩后的消息列表
        compressed = []
        if system_prompt:
            compressed.append({"role": "system", "content": system_prompt})

        # 将 markdown 摘要作为一条 system 消息注入
        compressed.append({
            "role": "system",
            "content": markdown,
        })

        # 追加最近 N 轮完整对话
        compressed.extend(recent)

        before_tokens = self._token_counter.estimate(
            " ".join(m.get("content", "") for m in current_messages)
        )
        after_tokens = self._token_counter.estimate(
            " ".join(m.get("content", "") for m in compressed)
        )
        saved = before_tokens - after_tokens
        logger.info(
            f"[Compressor] sandbox={sandbox_id} #{compress_num} "
            f"rounds={len(records)} before={before_tokens}t after={after_tokens}t "
            f"saved={saved}t ({saved / max(before_tokens, 1) * 100:.0f}%)"
        )

        return compressed

    def _generate_markdown(
        self,
        records: List[RoundRecord],
        compress_num: int,
    ) -> str:
        """生成压缩 markdown 摘要

        格式:
        # 对话摘要（第 N 次压缩）
        ## 第1轮
        - **需求**: xxx
        - **完成**: xxx
        - **改动**: xxx
        """
        lines = [
            f"# 对话摘要（第 {compress_num} 次压缩）",
            f"> 以下为前 {len(records)} 轮对话的关键信息摘要，已按时间顺序排列。",
            "",
        ]

        for record in records:
            lines.append(f"## 第{record.round_number}轮")
            lines.append(f"- **需求**: {record.user_question}")
            if record.keywords:
                lines.append(f"- **关键词**: {', '.join(record.keywords)}")
            if record.problem_solved:
                lines.append(f"- **完成**: {record.problem_solved}")
            if record.changes_made:
                lines.append(f"- **改动**: {record.changes_made}")
            lines.append("")

        return "\n".join(lines)

    def get_compression_count(self, sandbox_id: str) -> int:
        """获取指定沙盒的压缩次数"""
        return self._compression_count.get(sandbox_id, 0)


# 全局单例
_compressor: ContextCompressor = None


def get_compressor() -> ContextCompressor:
    """获取 ContextCompressor 全局单例"""
    global _compressor
    if _compressor is None:
        _compressor = ContextCompressor()
    return _compressor