// 知识库质检状态管理 — 接收后端 audit_progress WebSocket 消息
// 后端在 V3.3 推送：{ phase, current, total, message, stats, timestamp }

import { create } from 'zustand';

export interface AuditStats {
  total?: number;
  filtered?: number;
  wiki_replaced?: number;
  cloud_replaced?: number;
  removed?: number;
  skipped?: number;
  errors?: number;
}

export interface AuditProgress {
  phase: 'start' | 'processing' | 'completed' | 'error';
  current: number;
  total: number;
  message: string;
  stats?: AuditStats;
  timestamp: string;
}

interface AuditState {
  progress: AuditProgress | null;
  visible: boolean;          // 弹窗是否可见
  setProgress: (p: AuditProgress) => void;
  hide: () => void;
}

export const useAuditStore = create<AuditState>((set) => ({
  progress: null,
  visible: false,
  setProgress: (p) => {
    // phase=start/processing 时显示进度；completed 后再保留 3 秒自动关闭
    set({ progress: p, visible: true });
  },
  hide: () => set({ visible: false }),
}));
