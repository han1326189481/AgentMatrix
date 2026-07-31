// 抱怨澄清请求状态管理 — 接收后端 clarify_request WebSocket 消息
// 后端在 V3.4 推送：{ questions, complaint_type, user_input_summary, timestamp }
// 触发条件: 用户输入命中抱怨关键词后，后端生成2-5个澄清问题推送到前端弹窗

import { create } from 'zustand';

export interface ClarifyQuestion {
  id: string;            // 问题ID (q1, q2, ...)
  question: string;      // 问题文本
  options: string[];     // 2个选项 ['A: ...', 'B: ...']
}

export interface ClarifyRequest {
  questions: ClarifyQuestion[];
  complaint_type: string;          // 抱怨类型
  user_input_summary: string;      // 用户输入摘要
  timestamp: string;               // ISO 8601 时间戳
}

interface ClarifyState {
  request: ClarifyRequest | null;  // 当前澄清请求
  visible: boolean;                // 弹窗是否可见
  answers: Record<string, string>; // 用户选择的答案 { q1: 'A' | 'B' | 自定义文本, ... }
  customInput: string;             // 用户在输入框的自定义补充
  webSearchEnabled: boolean;       // V3.5: 是否启用网络搜索再回答（抱怨场景默认 true）
  setRequest: (r: ClarifyRequest) => void;
  setAnswer: (questionId: string, answer: string) => void;
  setCustomInput: (text: string) => void;
  setWebSearchEnabled: (enabled: boolean) => void;
  hide: () => void;
  reset: () => void;
}

export const useClarifyStore = create<ClarifyState>((set) => ({
  request: null,
  visible: false,
  answers: {},
  customInput: '',
  // 默认启用：用户在抱怨，很可能是因为信息过时/不准确，网络搜索能提供最新信息
  webSearchEnabled: true,
  setRequest: (r) =>
    set({ request: r, visible: true, answers: {}, customInput: '', webSearchEnabled: true }),
  setAnswer: (questionId, answer) =>
    set((state) => ({ answers: { ...state.answers, [questionId]: answer } })),
  setCustomInput: (text) => set({ customInput: text }),
  setWebSearchEnabled: (enabled) => set({ webSearchEnabled: enabled }),
  hide: () => set({ visible: false }),
  reset: () =>
    set({ request: null, visible: false, answers: {}, customInput: '', webSearchEnabled: true }),
}));
