'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { useWorkflowStore } from '@/stores/workflowStore';
import { socketService } from '@/services/api/socketService';
import type { ContextUsage } from '@/types';

const CONTEXT_LIMIT = 16384; // 本地模型上下文上限

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

/** 环形进度条 */
const RingGauge: React.FC<{
  ratio: number;
  size?: number;
  color: string;
  label: string;
  value: string;
}> = ({ ratio, size = 120, color, label, value }) => {
  const clamped = Math.max(0, Math.min(1, ratio));
  const strokeWidth = 6;
  const radius = size / 2 - strokeWidth;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped);

  return (
    <div className="context-gauge">
      <svg width={size} height={size} className="context-gauge-ring">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--bg-tertiary)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 0.8s ease, stroke 0.5s ease' }}
        />
      </svg>
      <div className="context-gauge-center">
        <span className="context-gauge-value" style={{ color }}>{value}</span>
        <span className="context-gauge-label">{label}</span>
      </div>
    </div>
  );
};

/** 获取颜色和状态 */
const getUsageTheme = (ratio: number) => {
  if (ratio >= 0.9) return { color: '#ef4444', status: '危险', gradient: 'linear-gradient(135deg, #fef2f2, #fee2e2)' };
  if (ratio >= 0.8) return { color: '#f97316', status: '警告', gradient: 'linear-gradient(135deg, #fff7ed, #ffedd5)' };
  if (ratio >= 0.6) return { color: '#eab308', status: '注意', gradient: 'linear-gradient(135deg, #fefce8, #fef9c3)' };
  return { color: '#22c55e', status: '正常', gradient: 'linear-gradient(135deg, #f0fdf4, #dcfce7)' };
};

const ContextPanel: React.FC = () => {
  const { chatHistory } = useWorkflowStore();
  const [context, setContext] = useState<ContextUsage | null>(null);

  // V4.3: 根据聊天历史实时计算 token 消耗（不再依赖后端 metrics 接口）
  const calculatedContext = useMemo<ContextUsage>(() => {
    let systemTokens = 0;
    let historyTokens = 0;
    let kbTokens = 0;
    let userInputTokens = 0;

    chatHistory.forEach((chat, idx) => {
      const userTokens = estimateTokens(chat.user_input);
      const responseTokens = chat.response ? estimateTokens(chat.response) : 0;

      if (idx === chatHistory.length - 1) {
        // 最后一轮 → 当前输入
        userInputTokens = userTokens;
        historyTokens += responseTokens;
      } else {
        historyTokens += userTokens + responseTokens;
      }
    });

    // 系统提示词估算 ~500 tokens
    systemTokens = chatHistory.length > 0 ? 500 : 0;

    const totalTokens = systemTokens + historyTokens + kbTokens + userInputTokens;
    const remaining = Math.max(0, CONTEXT_LIMIT - totalTokens);
    const usageRatio = Math.min(1, totalTokens / CONTEXT_LIMIT);

    return {
      total_tokens: totalTokens,
      limit: CONTEXT_LIMIT,
      remaining,
      usage_ratio: usageRatio,
      system_tokens: systemTokens,
      history_tokens: historyTokens,
      kb_tokens: kbTokens,
      user_input_tokens: userInputTokens,
    };
  }, [chatHistory]);

  // WebSocket 实时更新（后端推送时覆盖本地计算）
  useEffect(() => {
    const unsub = socketService.subscribe((msg) => {
      if (msg.type === 'context_usage') {
        setContext(msg.data as unknown as ContextUsage);
      }
    });
    return () => unsub();
  }, []);

  // 优先使用后端推送数据，否则使用本地计算
  const display = context || calculatedContext;

  const ratio = display.usage_ratio;
  const total = display.total_tokens;
  const limit = display.limit;
  const systemTokens = display.system_tokens;
  const historyTokens = display.history_tokens;
  const kbTokens = display.kb_tokens;
  const userTokens = display.user_input_tokens;
  const remaining = display.remaining;

  const theme = getUsageTheme(ratio);

  return (
    <div className="context-panel">
      <div className="context-panel-header">
        <h3>上下文使用量</h3>
        <span className="context-panel-status" style={{ color: theme.color }}>
          {theme.status}
        </span>
      </div>

      {/* 环形进度 */}
      <div className="context-panel-gauge-wrap">
        <RingGauge
          ratio={ratio}
          size={140}
          color={theme.color}
          label="已使用"
          value={`${(ratio * 100).toFixed(0)}%`}
        />
      </div>

      {/* 数值摘要 */}
      <div className="context-panel-summary">
        <div className="context-summary-row">
          <span className="context-summary-label">已用</span>
          <span className="context-summary-value" style={{ color: theme.color }}>
            {formatTokens(total)}
          </span>
        </div>
        <div className="context-summary-row">
          <span className="context-summary-label">剩余</span>
          <span className="context-summary-value" style={{ color: '#22c55e' }}>
            {formatTokens(remaining)}
          </span>
        </div>
        <div className="context-summary-row">
          <span className="context-summary-label">上限</span>
          <span className="context-summary-value">{formatTokens(limit)}</span>
        </div>
      </div>

      {/* 分段进度条 */}
      <div className="context-panel-bar-wrap">
        <div className="context-panel-bar">
          {systemTokens > 0 && (
            <div
              className="context-panel-segment context-panel-segment--system"
              style={{ width: `${(systemTokens / limit) * 100}%` }}
              title={`System: ${formatTokens(systemTokens)} tokens`}
            />
          )}
          {kbTokens > 0 && (
            <div
              className="context-panel-segment context-panel-segment--kb"
              style={{ width: `${(kbTokens / limit) * 100}%` }}
              title={`知识库: ${formatTokens(kbTokens)} tokens`}
            />
          )}
          {historyTokens > 0 && (
            <div
              className="context-panel-segment context-panel-segment--history"
              style={{ width: `${(historyTokens / limit) * 100}%` }}
              title={`历史: ${formatTokens(historyTokens)} tokens`}
            />
          )}
          {userTokens > 0 && (
            <div
              className="context-panel-segment context-panel-segment--user"
              style={{ width: `${(userTokens / limit) * 100}%` }}
              title={`当前输入: ${formatTokens(userTokens)} tokens`}
            />
          )}
        </div>
      </div>

      {/* 图例 */}
      <div className="context-panel-legend">
        <div className="context-legend-item">
          <span className="context-legend-dot" style={{ background: '#6366f1' }} />
          <span className="context-legend-label">System</span>
          <span className="context-legend-value">{formatTokens(systemTokens)}</span>
        </div>
        <div className="context-legend-item">
          <span className="context-legend-dot" style={{ background: '#8b5cf6' }} />
          <span className="context-legend-label">知识库</span>
          <span className="context-legend-value">{formatTokens(kbTokens)}</span>
        </div>
        <div className="context-legend-item">
          <span className="context-legend-dot" style={{ background: '#06b6d4' }} />
          <span className="context-legend-label">历史</span>
          <span className="context-legend-value">{formatTokens(historyTokens)}</span>
        </div>
        <div className="context-legend-item">
          <span className="context-legend-dot" style={{ background: '#f59e0b' }} />
          <span className="context-legend-label">当前输入</span>
          <span className="context-legend-value">{formatTokens(userTokens)}</span>
        </div>
      </div>

      {/* 模型信息 */}
      <div className="context-panel-model">
        <div className="context-model-row">
          <span className="context-model-label">本地模型</span>
          <span className="context-model-value">qwen2.5:7b</span>
        </div>
        <div className="context-model-row">
          <span className="context-model-label">上下文窗口</span>
          <span className="context-model-value">16,384 tokens</span>
        </div>
        <div className="context-model-row">
          <span className="context-model-label">云端模型</span>
          <span className="context-model-value">DeepSeek V4 Pro (1M)</span>
        </div>
      </div>

      <style jsx>{`
        .context-panel {
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 16px;
          height: 100%;
          overflow-y: auto;
        }

        .context-panel-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .context-panel-header h3 {
          font-size: 14px;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0;
        }

        .context-panel-status {
          font-size: 12px;
          font-weight: 600;
          padding: 2px 8px;
          border-radius: 4px;
          background: var(--bg-tertiary);
        }

        .context-panel-gauge-wrap {
          display: flex;
          justify-content: center;
          padding: 8px 0;
        }

        .context-gauge {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .context-gauge-ring {
          display: block;
        }

        .context-gauge-center {
          position: absolute;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
        }

        .context-gauge-value {
          font-size: 28px;
          font-weight: 700;
          font-variant-numeric: tabular-nums;
          line-height: 1;
        }

        .context-gauge-label {
          font-size: 11px;
          color: var(--text-muted);
          font-weight: 500;
        }

        .context-panel-summary {
          display: flex;
          justify-content: space-around;
          padding: 8px;
          background: var(--bg-tertiary);
          border-radius: 8px;
        }

        .context-summary-row {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
        }

        .context-summary-label {
          font-size: 10px;
          color: var(--text-muted);
          text-transform: uppercase;
          font-weight: 500;
        }

        .context-summary-value {
          font-size: 16px;
          font-weight: 700;
          font-variant-numeric: tabular-nums;
          color: var(--text-primary);
        }

        .context-panel-bar-wrap {
          padding: 0 4px;
        }

        .context-panel-bar {
          display: flex;
          height: 8px;
          background: var(--bg-tertiary);
          border-radius: 4px;
          overflow: hidden;
          gap: 1px;
        }

        .context-panel-segment {
          height: 100%;
          border-radius: 2px;
          transition: width 0.5s ease;
          min-width: 2px;
        }

        .context-panel-segment--system {
          background: #6366f1;
        }

        .context-panel-segment--kb {
          background: #8b5cf6;
        }

        .context-panel-segment--history {
          background: #06b6d4;
        }

        .context-panel-segment--user {
          background: #f59e0b;
        }

        .context-panel-legend {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding: 0 4px;
        }

        .context-legend-item {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .context-legend-dot {
          width: 8px;
          height: 8px;
          border-radius: 2px;
          flex-shrink: 0;
        }

        .context-legend-label {
          font-size: 11px;
          color: var(--text-secondary);
          flex: 1;
        }

        .context-legend-value {
          font-size: 11px;
          color: var(--text-muted);
          font-variant-numeric: tabular-nums;
        }

        .context-panel-model {
          margin-top: auto;
          padding: 10px;
          background: var(--bg-tertiary);
          border-radius: 8px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .context-model-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .context-model-label {
          font-size: 10px;
          color: var(--text-muted);
          font-weight: 500;
        }

        .context-model-value {
          font-size: 11px;
          color: var(--text-secondary);
          font-weight: 500;
          font-variant-numeric: tabular-nums;
        }
      `}</style>
    </div>
  );
};

export default ContextPanel;