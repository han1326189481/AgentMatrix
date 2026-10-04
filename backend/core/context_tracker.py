"""ContextTracker — 上下文压缩三件套的编排层

── 为什么需要这一层 ──
`context_round_recorder` / `context_token_counter` / `context_compressor` 三个模块
本身完整可跑，但 V4.2 只做到「模块写完」就停了：全仓没有任何调用方，前端
ContextBar / ContextPanel / ContextOverflowModal 已建好并监听 `context_usage`
推送，后端**一个端点、一条推送都没有**——典型的能力悬空。

接线点其实只有两处，但两处需要同一套编排：
1. 每轮工作流结束后（`WorkflowService.execute` / `execute_stream`）：
   记录本轮 → 计算用量 → 超阈值则压缩 → 推送前端
2. `GET /api/v1/context/usage` 等查询端点：返回同一份快照

如果两边各写一遍，迟早漂移。所以编排收在这里，service 与 router 都只调这一层。

── 与前端的分工 ──
前端在拿不到推送时会用 chatHistory 本地估算（`ContextBar.tsx:51`）。后端推送是
权威值，但只覆盖它真正知道的维度：history / user_input 由本轮真实文本算出；
system 取 Writer 系统提示词的真实 token 数（首次加载后缓存），不用「~500」估。
kb（知识库注入）在 Agent 内部生成、编排层拿不到，故置 0——宁可少算也不虚报。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.context_compressor import get_compressor
from core.context_round_recorder import get_round_recorder
from core.context_token_counter import ContextUsage, get_token_counter
from app.config import settings

logger = logging.getLogger(__name__)

# 未显式指定沙盒时的兜底桶：保证功能在没有多沙盒的调用路径上也能生效
DEFAULT_SANDBOX = "default"


class ContextTracker:
    """上下文用量追踪 + 压缩编排（无内部可变状态，状态都在三件套单例里）"""

    def __init__(self):
        self._recorder = get_round_recorder()
        self._counter = get_token_counter()
        self._compressor = get_compressor()
        self._system_tokens_cache: Optional[int] = None
        # sandbox_id → 最近一次压缩产出的摘要（供下一轮在客户端未带 history 时接续）
        self._carry_summary: Dict[str, str] = {}

    # ==========================================================
    # 用量计算
    # ==========================================================

    def _system_prompt_tokens(self) -> int:
        """Writer 系统提示词的真实 token 数（懒加载 + 缓存）

        加载失败时返回 0 —— 与「不虚报」原则一致：拿不到就不算，
        而不是拍一个 ~500 的数字把进度条推高。
        """
        if self._system_tokens_cache is not None:
            return self._system_tokens_cache
        tokens = 0
        try:
            from prompts.template_manager import get_prompt_manager
            tpl = get_prompt_manager().get_template("writer", "system")
            if tpl and getattr(tpl, "template", ""):
                tokens = self._counter.estimate(tpl.template)
        except Exception as e:
            logger.debug("[ContextTracker] Writer 系统提示词加载失败（按 0 计）: %s", e)
        self._system_tokens_cache = tokens
        return tokens

    def _history_messages(self, sandbox_id: str) -> List[Dict[str, str]]:
        """把历轮记录还原成消息列表（user/assistant 成对）"""
        messages: List[Dict[str, str]] = []
        for rec in self._recorder.get_records(sandbox_id):
            messages.append({"role": "user", "content": rec.user_question})
            messages.append({"role": "assistant", "content": rec.problem_solved or ""})
        return messages

    def compute_usage(
        self, sandbox_id: str, user_input: str = "", messages: Optional[List[Dict]] = None
    ) -> ContextUsage:
        """计算沙盒当前上下文用量

        Args:
            user_input: 正在进行的这一轮的用户输入（若为空则取最近一轮记录）
        """
        sid = sandbox_id or DEFAULT_SANDBOX
        msgs = messages if messages is not None else self._history_messages(sid)

        if not user_input:
            records = self._recorder.get_records(sid)
            if records:
                user_input = records[-1].user_question
                # 最近一轮的 user 已被算进 history，摘出来避免重复计数
                if len(msgs) >= 2 and msgs[-2].get("role") == "user":
                    msgs = msgs[:-2] + [msgs[-1]]

        usage = self._counter.count_context(
            system_prompt="",  # system 在下面单独按真实 token 数覆盖
            messages=msgs,
            knowledge_context="",
            user_input=user_input,
        )
        # count_context 只接受字符串，这里已知 token 数，直接组装 ContextUsage
        system_tokens = self._system_prompt_tokens() if (msgs or user_input) else 0
        total = system_tokens + usage.history_tokens + usage.user_input_tokens
        return ContextUsage(
            total_tokens=total,
            limit=usage.limit,
            system_tokens=system_tokens,
            history_tokens=usage.history_tokens,
            kb_tokens=0,
            user_input_tokens=usage.user_input_tokens,
            usage_ratio=round(total / usage.limit, 4) if usage.limit > 0 else 0.0,
        )

    # ==========================================================
    # 每轮结束后的追踪
    # ==========================================================

    def track(
        self,
        sandbox_id: Optional[str],
        user_input: str,
        workflow_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        """记录本轮 → 计算用量 → 超阈值则压缩 → 返回可直接推送前端的 payload

        不抛异常：上下文追踪出问题绝不能影响主链路返回。
        """
        sid = sandbox_id or DEFAULT_SANDBOX
        try:
            self._recorder.record_round(sid, user_input, workflow_output)

            records = self._recorder.get_records(sid)
            # 已有记录里最后一轮就是本轮 → history 只取之前的轮次
            history = self._history_messages(sid)[:-2] if records else []

            usage = self.compute_usage(sid, user_input=user_input, messages=history)

            compressed = False
            summary = ""
            if self._compressor.should_compress(usage) and len(records) > self._compressor.KEEP_RECENT:
                summary = self._compress(sid, history)
                if summary:
                    compressed = True
                    self._carry_summary[sid] = summary
                    # 压缩后重算：历史只剩「摘要 + 最近 N 轮」
                    after_msgs = [{"role": "system", "content": summary}]
                    after_msgs.extend(history[-self._compressor.KEEP_RECENT * 2:])
                    usage = self.compute_usage(sid, user_input=user_input, messages=after_msgs)

            payload = usage.to_dict()
            payload.update({
                "sandbox_id": sid,
                "round": len(records),
                "compressed": compressed,
                "compression_count": self._compressor.get_compression_count(sid),
                "message": (
                    f"上下文已达 {usage.usage_ratio * 100:.0f}%，"
                    f"已压缩为摘要（第 {self._compressor.get_compression_count(sid)} 次）"
                    if compressed else
                    f"上下文使用率 {usage.usage_ratio * 100:.0f}%"
                ),
            })
            logger.info(
                "[ContextTracker] sandbox=%s round=%d usage=%.1f%% compressed=%s",
                sid, len(records), usage.usage_ratio * 100, compressed,
            )
            return payload
        except Exception as e:
            logger.warning("[ContextTracker] 追踪失败（不影响主链路）: %s", e)
            return {}

    def _compress(self, sandbox_id: str, history: List[Dict[str, str]]) -> str:
        """把历轮历史压成 markdown 摘要，返回摘要文本（失败返回空串）"""
        try:
            compressed = self._compressor.compress(sandbox_id, history, system_prompt="")
        except Exception as e:
            logger.warning("[ContextTracker] 压缩失败: %s", e)
            return ""
        # compress() 产出 [system(空则略) , summary, ...recent]，摘要固定在第 1 或第 2 条
        for msg in compressed:
            content = msg.get("content", "")
            if content.startswith("# 对话摘要"):
                return content
        return ""

    # ==========================================================
    # 下一轮的接续 / 清空
    # ==========================================================

    def pending_history(self, sandbox_id: Optional[str]) -> Optional[List[Dict[str, str]]]:
        """返回压缩后的历史（客户端未自带 history 时用于接续上下文）

        仅当本沙盒发生过压缩时返回；形态与前端 `context.history` 一致
        （`[{"user":..., "assistant":...}]`），可直接塞回 `context["history"]`。
        """
        sid = sandbox_id or DEFAULT_SANDBOX
        summary = self._carry_summary.get(sid)
        if not summary:
            return None
        return [{"user": "【此前对话摘要】", "assistant": summary}]

    def snapshot(self, sandbox_id: Optional[str]) -> Dict[str, Any]:
        """查询端点用的快照（含轮次记录）"""
        sid = sandbox_id or DEFAULT_SANDBOX
        usage = self.compute_usage(sid)
        records = self._recorder.get_records(sid)
        out = usage.to_dict()
        out.update({
            "sandbox_id": sid,
            "round": len(records),
            "compression_count": self._compressor.get_compression_count(sid),
            "records": [
                {
                    "round": r.round_number,
                    "timestamp": r.timestamp,
                    "user_question": r.user_question,
                    "keywords": r.keywords,
                    "problem_solved": r.problem_solved,
                    "changes_made": r.changes_made,
                }
                for r in records
            ],
        })
        return out

    def compress_now(
        self, sandbox_id: Optional[str], messages: Optional[List[Dict]] = None,
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """手动触发一次压缩（API 用）：返回压缩后的消息列表与摘要"""
        sid = sandbox_id or DEFAULT_SANDBOX
        msgs = messages if messages is not None else self._history_messages(sid)
        compressed = self._compressor.compress(sid, msgs, system_prompt=system_prompt)
        summary = next(
            (m.get("content", "") for m in compressed if m.get("content", "").startswith("# 对话摘要")),
            "",
        )
        if summary:
            self._carry_summary[sid] = summary
        before = self._counter.estimate(" ".join(m.get("content", "") for m in msgs))
        after = self._counter.estimate(" ".join(m.get("content", "") for m in compressed))
        return {
            "sandbox_id": sid,
            "compression_count": self._compressor.get_compression_count(sid),
            "before_tokens": before,
            "after_tokens": after,
            "saved_tokens": max(0, before - after),
            "summary": summary,
            "messages": compressed,
        }

    def clear(self, sandbox_id: Optional[str]) -> None:
        """清空沙盒的轮次记录与接续摘要（新建沙盒 / 重置对话）"""
        sid = sandbox_id or DEFAULT_SANDBOX
        self._recorder.clear_sandbox(sid)
        self._carry_summary.pop(sid, None)
        logger.info("[ContextTracker] 已清空沙盒上下文: %s", sid)

    # ---------- 配置快照（供前端展示） ----------

    def config(self) -> Dict[str, Any]:
        return {
            "context_max_tokens": settings.context_max_tokens,
            "context_compress_threshold": settings.context_compress_threshold,
            "context_overflow_threshold": settings.context_overflow_threshold,
            "keep_recent_rounds": self._compressor.KEEP_RECENT,
        }


# 全局单例
_tracker: Optional[ContextTracker] = None


def get_context_tracker() -> ContextTracker:
    global _tracker
    if _tracker is None:
        _tracker = ContextTracker()
    return _tracker
