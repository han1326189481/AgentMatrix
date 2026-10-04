"""TokenCounter — 上下文 Token 消耗估算器

V4.2: 基于字符统计的 token 估算，用于上下文进度条和压缩触发判断。
- 中文: ~1.5 字符/token（基于 qwen2.5 tokenizer 统计规律）
- 英文: ~4.0 字符/token
- 云端 API 返回精确 token 数后可用于校准
"""
import re
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)


# 估算公式常量
CN_CHARS_PER_TOKEN = 1.5   # 中文约 1.5 字符/token
EN_CHARS_PER_TOKEN = 4.0   # 英文约 4 字符/token

# 中文 Unicode 范围
CN_RANGE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')


@dataclass
class ContextUsage:
    """上下文使用量快照"""
    total_tokens: int = 0
    limit: int = settings.context_max_tokens
    system_tokens: int = 0
    history_tokens: int = 0
    kb_tokens: int = 0
    user_input_tokens: int = 0
    usage_ratio: float = 0.0

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.total_tokens)

    @property
    def is_over_threshold(self) -> bool:
        return self.usage_ratio >= settings.context_compress_threshold

    @property
    def is_overflowing(self) -> bool:
        return self.usage_ratio >= settings.context_overflow_threshold

    def to_dict(self) -> Dict:
        return {
            "total_tokens": self.total_tokens,
            "limit": self.limit,
            "remaining": self.remaining,
            "usage_ratio": round(self.usage_ratio, 4),
            "system_tokens": self.system_tokens,
            "history_tokens": self.history_tokens,
            "kb_tokens": self.kb_tokens,
            "user_input_tokens": self.user_input_tokens,
        }


class TokenCounter:
    """上下文 Token 消耗估算器"""

    def __init__(self, limit: int = None):
        self.limit = limit or settings.context_max_tokens

    def estimate(self, text: str) -> int:
        """混合估算：中文按 1.5 字符/token，英文按 4 字符/token"""
        if not text:
            return 0

        cn_chars = len(CN_RANGE.findall(text))
        en_chars = len(text) - cn_chars

        tokens = int(cn_chars / CN_CHARS_PER_TOKEN + en_chars / EN_CHARS_PER_TOKEN)
        return max(1, tokens)  # 至少 1 token

    def count_context(
        self,
        system_prompt: str = "",
        messages: List[Dict] = None,
        knowledge_context: str = "",
        user_input: str = "",
    ) -> ContextUsage:
        """计算当前对话的 token 消耗"""
        system_tokens = self.estimate(system_prompt)
        history_tokens = sum(
            self.estimate(m.get("content", ""))
            for m in (messages or [])
        )
        kb_tokens = self.estimate(knowledge_context)
        user_input_tokens = self.estimate(user_input)

        total = system_tokens + history_tokens + kb_tokens + user_input_tokens

        return ContextUsage(
            total_tokens=total,
            limit=self.limit,
            system_tokens=system_tokens,
            history_tokens=history_tokens,
            kb_tokens=kb_tokens,
            user_input_tokens=user_input_tokens,
            usage_ratio=round(total / self.limit, 4) if self.limit > 0 else 0.0,
        )

    def calibrate(self, estimated_tokens: int, actual_tokens: int) -> None:
        """用云端 API 返回的精确 token 数校准估算参数（暂未实现）"""
        # 未来可以用线性回归动态调整 CN_CHARS_PER_TOKEN / EN_CHARS_PER_TOKEN
        pass


# 全局单例
_token_counter: Optional[TokenCounter] = None


def get_token_counter() -> TokenCounter:
    """获取 TokenCounter 全局单例"""
    global _token_counter
    if _token_counter is None:
        _token_counter = TokenCounter()
    return _token_counter