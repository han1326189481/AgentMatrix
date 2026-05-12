import { create } from 'zustand';
import { agentService } from '@/services/api/agentService';

interface Metrics {
  api_calls: number;
  cost_saved: number;
  avg_response_time: number;
  cpu_usage: number;
  gpu_usage: number;
  local_executions: number;
  cloud_executions: number;
}

interface MetricsStore {
  metrics: Metrics;
  loading: boolean;
  fetchMetrics: () => Promise<void>;
}

const initialMetrics: Metrics = {
  api_calls: 0,
  cost_saved: 0,
  avg_response_time: 0,
  cpu_usage: 0,
  gpu_usage: 0,
  local_executions: 0,
  cloud_executions: 0,
};

export const useMetricsStore = create<MetricsStore>((set) => ({
  metrics: initialMetrics,
  loading: false,

  fetchMetrics: async () => {
    set({ loading: true });
    try {
      const data = await agentService.getMetrics();
      set({ metrics: data });
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    } finally {
      set({ loading: false });
    }
  },
}));