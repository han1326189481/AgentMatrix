import React from 'react';
import type { AgentId } from '@/types';
import { AGENT_NAMES, AGENT_COLORS, COMPLEXITY_THRESHOLD } from '@/types';

// 统一从 types 导入，消除重复定义
export { AGENT_NAMES as AGENT_DISPLAY_NAMES, AGENT_COLORS as AGENT_DISPLAY_COLORS, COMPLEXITY_THRESHOLD };
export { AGENT_COLORS as AGENT_TIMELINE_COLORS };

// AGENT_COLORS 语义键 → CSS 变量字符串（消除组件内 colorMap 重复 + 硬编码颜色）
// violet 复用 --purple（项目未单独定义 --violet）
export const AGENT_COLOR_VALUES: Record<string, string> = {
  purple: 'var(--purple)',
  blue: 'var(--blue)',
  orange: 'var(--orange)',
  violet: 'var(--purple)',
  green: 'var(--green)',
};

/** 根据 AgentId 获取对应的 CSS 变量颜色字符串 */
export function getAgentColorValue(agentId: string): string {
  const key = AGENT_COLORS[agentId as AgentId];
  return AGENT_COLOR_VALUES[key] || 'var(--text-muted)';
}

export const AGENT_NODE_CLASSES: Record<AgentId, string> = {
  knowledge: 'node-knowledge',
  writer: 'node-writer',
  review: 'node-review',
  judge: 'node-judge',
  result: 'node-result',
};

export const AGENT_SVG_ICONS: Record<AgentId, React.ReactNode> = {
  knowledge: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      <line x1="12" y1="6" x2="12" y2="10" />
      <line x1="10" y1="8" x2="14" y2="8" />
    </svg>
  ),
  writer: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  ),
  review: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  judge: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="2" x2="12" y2="22" />
      <path d="M5 7l7-5 7 5" />
      <line x1="5" y1="7" x2="19" y2="7" />
      <line x1="5" y1="12" x2="19" y2="12" />
      <path d="M3 17l3 3" />
      <path d="M21 17l-3 3" />
      <line x1="6" y1="20" x2="18" y2="20" />
    </svg>
  ),
  result: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  ),
};

export const AGENT_SUBTITLES: Record<AgentId, string> = {
  knowledge: '知识库检索与上下文增强',
  writer: '内容初稿生成与规划',
  review: '质量评估与难度评分',
  judge: '路由决策与路径选择',
  result: '格式化最终输出',
};

export const formatTime = (seconds: number): string => {
  const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
  const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
};

// renderMarkdown 已移除 — 改用 react-markdown 组件渲染（修复 XSS）
