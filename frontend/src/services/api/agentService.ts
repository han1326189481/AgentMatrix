import axios from 'axios';
import type {
  WorkflowInput,
  WorkflowOutput,
  Metrics,
  MetricsResponse,
  AgentId,
  AgentStatusResponse,
  AgentsListResponse,
  KnowledgeItem,
  KnowledgeListResponse,
  KnowledgeSearchResponse,
  ExportRequest,
  ExportResponse,
  HealthResponse,
  ChatRequest,
  ChatResponse,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
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
    const response = await api.post<WorkflowOutput>('/api/v1/workflow/execute', input);
    return response.data;
  },

  async executeParallel(input: WorkflowInput): Promise<WorkflowOutput> {
    const response = await api.post<WorkflowOutput>('/api/v1/workflow/execute/parallel', input);
    return response.data;
  },

  async getCacheStats() {
    const response = await api.get('/api/v1/workflow/cache/stats');
    return response.data;
  },

  async clearCache() {
    const response = await api.post('/api/v1/workflow/cache/clear');
    return response.data;
  },
};

export const agentService = {
  async getAll(): Promise<AgentsListResponse> {
    const response = await api.get<AgentsListResponse>('/api/v1/agents');
    return response.data;
  },

  async getStatus(agentId: AgentId): Promise<AgentStatusResponse> {
    const response = await api.get<AgentStatusResponse>(`/api/v1/agents/${agentId}`);
    return response.data;
  },

  async executeAgent(agentId: AgentId, content: string, context?: Record<string, unknown>) {
    const response = await api.post(`/api/v1/agents/${agentId}/execute`, {
      content,
      context: context || {},
    });
    return response.data;
  },
};

export const metricsService = {
  async getDashboard(): Promise<MetricsResponse> {
    const response = await api.get<MetricsResponse>('/api/v1/metrics');
    return response.data;
  },

  async getSystemMetrics() {
    const response = await api.get('/api/v1/metrics/system');
    return response.data;
  },

  toFlatMetrics(data: MetricsResponse): Metrics {
    return {
      total_requests: data.workflow.total_requests,
      local_executions: data.workflow.local_executions,
      cloud_executions: data.workflow.cloud_executions,
      api_calls: data.workflow.api_calls,
      cost_saved: data.workflow.cost_saved,
      avg_response_time: 0,
      cpu_usage: data.resources.cpu_usage,
      gpu_usage: 0,
      total_tasks: data.workflow.total_requests,
      uptime_seconds: data.system.uptime_seconds,
    };
  },
};

export const knowledgeService = {
  async list(): Promise<KnowledgeListResponse> {
    const response = await api.get<KnowledgeListResponse>('/api/v1/knowledge');
    return response.data;
  },

  async add(item: KnowledgeItem): Promise<{ status: string; keyword: string }> {
    const response = await api.post('/api/v1/knowledge', item);
    return response.data;
  },

  async search(query: string, limit: number = 5): Promise<KnowledgeSearchResponse> {
    const response = await api.get<KnowledgeSearchResponse>('/api/v1/knowledge/search', {
      params: { query, limit },
    });
    return response.data;
  },

  async getByKeyword(keyword: string) {
    const response = await api.get(`/api/v1/knowledge/keyword/${encodeURIComponent(keyword)}`);
    return response.data;
  },

  async updateKeyword(keyword: string, content: string[]) {
    const response = await api.put(`/api/v1/knowledge/keyword/${encodeURIComponent(keyword)}`, content);
    return response.data;
  },

  async deleteKeyword(keyword: string) {
    const response = await api.delete(`/api/v1/knowledge/keyword/${encodeURIComponent(keyword)}`);
    return response.data;
  },

  async enhance(content: string, keywords: string[]) {
    const response = await api.post('/api/v1/knowledge/enhance', null, {
      params: { content, keywords: keywords.join(',') },
    });
    return response.data;
  },
};

export const exportService = {
  async exportMarkdown(request: ExportRequest): Promise<ExportResponse> {
    const response = await api.post<ExportResponse>('/api/v1/export/markdown', request);
    return response.data;
  },

  async exportDocx(request: ExportRequest): Promise<ExportResponse> {
    const response = await api.post<ExportResponse>('/api/v1/export/docx', request);
    return response.data;
  },

  async exportPptx(request: ExportRequest): Promise<ExportResponse> {
    const response = await api.post<ExportResponse>('/api/v1/export/pptx', request);
    return response.data;
  },

  async downloadFile(filename: string): Promise<Blob> {
    const response = await api.get(`/api/v1/export/download/${filename}`, {
      responseType: 'blob',
    });
    return response.data;
  },

  async listExports() {
    const response = await api.get('/api/v1/export/list');
    return response.data;
  },
};

export const chatService = {
  async send(request: ChatRequest): Promise<ChatResponse> {
    const response = await api.post<ChatResponse>('/api/v1/chat/send', request);
    return response.data;
  },

  async sendBatch(requests: ChatRequest[]) {
    const response = await api.post('/api/v1/chat/send/batch', requests);
    return response.data;
  },

  async health() {
    const response = await api.get('/api/v1/chat/health');
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
