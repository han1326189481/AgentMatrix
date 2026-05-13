import axios from 'axios';
import type {
  WorkflowInput,
  WorkflowOutput,
  Metrics,
  AgentId,
  AgentStatusResponse,
  KnowledgeEntry,
  KnowledgeInput,
  ExportInput,
  HealthResponse,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000,
});

api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.message || '请求失败';
      console.error(`[API Error] ${error.config?.url}:`, message);
    } else {
      console.error('[API Error] Unexpected error:', error);
    }
    return Promise.reject(error);
  }
);

export const workflowService = {
  async execute(input: WorkflowInput): Promise<WorkflowOutput> {
    const response = await api.post<WorkflowOutput>('/workflow/execute', input);
    return response.data;
  },

  async executeParallel(input: WorkflowInput): Promise<WorkflowOutput> {
    const response = await api.post<WorkflowOutput>('/workflow/execute/parallel', input);
    return response.data;
  },
};

export const agentService = {
  async getAll(): Promise<AgentStatusResponse[]> {
    const response = await api.get<AgentStatusResponse[]>('/agents');
    return response.data;
  },

  async getStatus(agentId: AgentId): Promise<AgentStatusResponse> {
    const response = await api.get<AgentStatusResponse>(`/agents/${agentId}`);
    return response.data;
  },
};

export const metricsService = {
  async getDashboard(): Promise<Metrics> {
    const response = await api.get<Metrics>('/metrics');
    return response.data;
  },
};

export const knowledgeService = {
  async list(): Promise<KnowledgeEntry[]> {
    const response = await api.get<KnowledgeEntry[]>('/knowledge');
    return response.data;
  },

  async add(entry: KnowledgeInput): Promise<KnowledgeEntry> {
    const response = await api.post<KnowledgeEntry>('/knowledge', entry);
    return response.data;
  },

  async query(query: string, topK: number = 5): Promise<KnowledgeEntry[]> {
    const response = await api.post<KnowledgeEntry[]>('/knowledge/query', { query, top_k: topK });
    return response.data;
  },
};

export const exportService = {
  async exportContent(input: ExportInput): Promise<Blob> {
    const response = await api.post('/export', input, {
      responseType: 'blob',
    });
    return response.data;
  },
};

export const healthService = {
  async check(): Promise<HealthResponse> {
    const response = await api.get<HealthResponse>('/health');
    return response.data;
  },
};

export default api;
