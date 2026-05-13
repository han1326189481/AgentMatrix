import { create } from 'zustand';
import type { Metrics } from '@/types';

interface MetricsStore {
  metrics: Metrics;
  updateMetrics: (data: Partial<Metrics>) => void;
}

const mockMetrics: Metrics = {
  total_requests: 12,
  api_calls: 12,
  cost_saved: 28.5,
  avg_response_time: 1.8,
  cpu_usage: 35,
  gpu_usage: 22,
  local_executions: 8,
  cloud_executions: 4,
  total_tasks: 12,
  uptime_seconds: 3600,
};

export const useMetricsStore = create<MetricsStore>((set) => ({
  metrics: mockMetrics,

  updateMetrics: (data) =>
    set((state) => ({
      metrics: { ...state.metrics, ...data },
    })),
}));
