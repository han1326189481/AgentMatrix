'use client';

import React, { useEffect, useState, useRef, useMemo } from 'react';
import { useWorkflowStore } from '@/stores/workflowStore';
import { socketService } from '@/services/api/socketService';
import type { ContextUsage } from '@/types';

const CONTEXT_LIMIT = 16384;

interface ContextBarProps {
  compact?: boolean;
  /** V4.2: 上下文溢出回调 — 当 usage_ratio >= 0.9 时触发 */
  onOverflow?: (context: ContextUsage) => void;
}

/** 估算 token 数：中文 ~1.5 字符/token，英文 ~4 字符/token */
const estimateTokens = (text: string): number => {
  const cnChars = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  const enChars = text.length - cnChars;
  return Math.max(1, Math.round(cnChars / 1.5 + enChars / 4));
};

/** 格式化 token 数量 */
const formatTokens = (tokens: number): string => {
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
  return String(tokens);
};

/** 根据使用率获取颜色 */
const getColor = (ratio: number): string => {
  if (ratio >= 0.9) return '#ef4444';   // 红色：溢出
  if (ratio >= 0.8) return '#f97316';   // 橙色：警告
  if (ratio >= 0.6) return '#eab308';   // 黄色：注意
  return '#22c55e';                      // 绿色：正常
};

/** 获取使用率文本 */
const getStatusText = (ratio: number): string => {
  if (ratio >= 0.9) return '即将溢出';
  if (ratio >= 0.8) return '接近上限';
  if (ratio >= 0.6) return '使用中';
  return '正常';
};

const ContextBar: React.FC<ContextBarProps> = ({ compact = true, onOverflow }) => {
  const { chatHistory } = useWorkflowStore();
  const [wsContext, setWsContext] = useState<ContextUsage | null>(null);
  const overflowTriggered = useRef(false);

  // V4.3: 根据聊天历史实时计算 token 消耗
  const calculatedContext = useMemo<ContextUsage>(() => {
    let historyTokens = 0;
    let userInputTokens = 0;

    chatHistory.forEach((chat, idx) => {
      const userTokens = estimateTokens(chat.user_input);
      const responseTokens = chat.response ? estimateTokens(chat.response) : 0;

      if (idx === chatHistory.length - 1) {
        userInputTokens = userTokens;
        historyTokens += responseTokens;
      } else {
        historyTokens += userTokens + responseTokens;
      }
    });

    const systemTokens = chatHistory.length > 0 ? 500 : 0;
    const totalTokens = systemTokens + historyTokens + userInputTokens;
    const remaining = Math.max(0, CONTEXT_LIMIT - totalTokens);
    const usageRatio = Math.min(1, totalTokens / CONTEXT_LIMIT);

    return {
      total_tokens: totalTokens,
      limit: CONTEXT_LIMIT,
      remaining,
      usage_ratio: usageRatio,
      system_tokens: systemTokens,
      history_tokens: historyTokens,
      kb_tokens: 0,
      user_input_tokens: userInputTokens,
    };
  }, [chatHistory]);

  const context = wsContext || calculatedContext;

  // WebSocket 实时更新（后端推送时覆盖本地计算）
  useEffect(() => {
    const unsub = socketService.subscribe((msg) => {
      if (msg.type === 'context_usage') {
        setWsContext(msg.data as unknown as ContextUsage);
      }
    });
    return () => unsub();
  }, []);

  // V4.2: 检测上下文溢出，触发弹窗回调
  useEffect(() => {
    if (!context || overflowTriggered.current) return;
    if (context.usage_ratio >= 0.9 && onOverflow) {
      overflowTriggered.current = true;
      onOverflow(context);
    }
  }, [context, onOverflow]);

  const ratio = context.usage_ratio;
  const total = context.total_tokens;
  const limit = context.limit;
  const color = getColor(ratio);
  const status = getStatusText(ratio);

  return (
    <div className="context-bar context-bar--compact" title={`上下文: ${formatTokens(total)} / ${formatTokens(limit)} tokens (${(ratio * 100).toFixed(0)}%)`}>
      <div className="context-bar-inner">
        <div className="context-bar-track">
          <div
            className="context-bar-fill"
            style={{
              width: `${Math.min(ratio * 100, 100)}%`,
              background: color,
              transition: 'width 0.5s ease, background 0.5s ease',
            }}
          />
        </div>
        <span className="context-bar-text" style={{ color }}>
          {formatTokens(total)} / {formatTokens(limit)} {status}
        </span>
      </div>
    </div>
  );
};

export default ContextBar;