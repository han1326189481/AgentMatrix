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
  ChatRequest,
  ChatResponse,
  ExportRequest,
  ExportResponse,
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

// ==================== Workflow Service ====================
export const workflowService = {
  async execute(input: WorkflowInput): Promise<WorkflowOutput> {
    const response = await api.post<WorkflowOutput>('/workflow/execute', input);
    return response.data;
  },

  async executeParallel(input: WorkflowInput): Promise<WorkflowOutput> {
    const response = await api.post<WorkflowOutput>('/workflow/execute/parallel', input);
    return response.data;
  },

  async getCacheStats(): Promise<{ cache_size: number; max_size: number; ttl: number }> {
    const response = await api.get('/workflow/cache/stats');
    return response.data;
  },

  async clearCache(): Promise<{ status: string; message: string }> {
    const response = await api.post('/workflow/cache/clear');
    return response.data;
  },
};

// ==================== Agent Service ====================
export const agentService = {
  async getAll(): Promise<{ agents: AgentStatusResponse[]; count: number }> {
    const response = await api.get('/agents');
    return response.data;
  },

  async get(agentId: AgentId): Promise<AgentStatusResponse> {
    const response = await api.get<AgentStatusResponse>(`/agents/${agentId}`);
    return response.data;
  },

  async getStatus(agentId: AgentId): Promise<AgentStatusResponse> {
    const response = await api.get<AgentStatusResponse>(`/agents/${agentId}/status`);
    return response.data;
  },

  async executeAgent(agentId: AgentId, input: { content: string; context?: Record<string, unknown> }): Promise<any> {
    const response = await api.post(`/agents/${agentId}/execute`, input);
    return response.data;
  },
};

// ==================== Metrics Service ====================
export const metricsService = {
  async getDashboard(): Promise<Metrics> {
    const response = await api.get<Metrics>('/metrics');
    return response.data;
  },

  async getSystem(): Promise<{ cpu_usage: number; memory_usage: number; disk_usage: number; process_count: number }> {
    const response = await api.get('/metrics/system');
    return response.data;
  },

  async incrementMetric(metricType: string, value: number = 1.0): Promise<{ status: string; metric: string; value: number }> {
    const response = await api.post(`/metrics/increment/${metricType}`, { value });
    return response.data;
  },
};

// ==================== Knowledge Service ====================
export const knowledgeService = {
  async list(): Promise<{ knowledge_base: Record<string, string[]>; keywords: string[]; stats: any }> {
    const response = await api.get('/knowledge');
    return response.data;
  },

  async getStats(): Promise<{ total_entries: number; total_keywords: number; total_size: number }> {
    const response = await api.get('/knowledge/stats');
    return response.data;
  },

  async add(entry: KnowledgeInput): Promise<{ status: string; keyword: string }> {
    const response = await api.post('/knowledge', entry);
    return response.data;
  },

  async search(query: string, limit: number = 5): Promise<{ query: string; results: any[]; count: number }> {
    const response = await api.get('/knowledge/search', { params: { query, limit } });
    return response.data;
  },

  async getKeyword(keyword: string): Promise<{ keyword: string; content: string[] }> {
    const response = await api.get(`/knowledge/keyword/${keyword}`);
    return response.data;
  },

  async updateKeyword(keyword: string, content: string[]): Promise<{ status: string; keyword: string }> {
    const response = await api.put(`/knowledge/keyword/${keyword}`, content);
    return response.data;
  },

  async deleteKeyword(keyword: string): Promise<{ status: string; keyword: string }> {
    const response = await api.delete(`/knowledge/keyword/${keyword}`);
    return response.data;
  },

  async enhance(content: string, keywords: string[]): Promise<{ original: string; enhanced: string; keywords: string[] }> {
    const response = await api.post('/knowledge/enhance', { content, keywords });
    return response.data;
  },
};

// ==================== Export Service ====================
export const exportService = {
  async exportMarkdown(request: ExportRequest): Promise<ExportResponse> {
    const response = await api.post<ExportResponse>('/export/markdown', request);
    return response.data;
  },

  async exportDocx(request: ExportRequest): Promise<ExportResponse> {
    const response = await api.post<ExportResponse>('/export/docx', request);
    return response.data;
  },

  async exportPptx(request: ExportRequest): Promise<ExportResponse> {
    const response = await api.post<ExportResponse>('/export/pptx', request);
    return response.data;
  },

  async download(filename: string): Promise<Blob> {
    const response = await api.get(`/export/download/${filename}`, { responseType: 'blob' });
    return response.data;
  },

  async list(): Promise<{ exports: any[]; count: number }> {
    const response = await api.get('/export/list');
    return response.data;
  },
};

// ==================== Chat Service ====================
export const chatService = {
  async send(request: ChatRequest): Promise<ChatResponse> {
    const response = await api.post<ChatResponse>('/chat/send', request);
    return response.data;
  },

  async sendStream(
    request: ChatRequest,
    onMessage: (data: { type: string; agent_id?: string; agent_name?: string; message?: string; final_result?: string; executed_locally?: boolean; complexity_score?: number; total_duration?: number; steps_count?: number; duration?: number; success?: boolean; error?: string }) => void
  ): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/chat/send/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Failed to get response reader');
    }

    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        while (true) {
          const newlineIndex = buffer.indexOf('\n');
          if (newlineIndex === -1) break;

          const line = buffer.substring(0, newlineIndex);
          buffer = buffer.substring(newlineIndex + 1);

          if (line.startsWith('data: ')) {
            try {
              const parsedData = JSON.parse(line.substring(6));
              onMessage(parsedData);
            } catch (e) {
              console.error('Error parsing stream data:', e);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  async sendBatch(requests: ChatRequest[]): Promise<{ results: ChatResponse[] }> {
    const response = await api.post('/chat/send/batch', requests);
    return response.data;
  },

  async health(): Promise<{ status: string; service: string; cache_size: number }> {
    const response = await api.get('/chat/health');
    return response.data;
  },

  async getCacheStats(): Promise<{
    chat_cache_size: number;
    chat_cache_max_size: number;
    chat_cache_ttl: number;
    workflow_cache_size: number;
    workflow_cache_max_size: number;
    workflow_cache_ttl: number;
  }> {
    const response = await api.get('/chat/cache/stats');
    return response.data;
  },

  async clearCache(): Promise<{ status: string; message: string }> {
    const response = await api.post('/chat/cache/clear');
    return response.data;
  },
};

// ==================== Config Service ====================
export const configService = {
  async get(): Promise<{ ollama_host: string; ollama_model: string; deepseek_api_key_set: boolean; deepseek_model: string; models: any[] }> {
    const response = await api.get('/config');
    return response.data;
  },

  async update(config: { deepseek_api_key?: string; ollama_host?: string }): Promise<{ message: string; saved: boolean }> {
    const response = await api.post('/config', config);
    return response.data;
  },

  async listModels(): Promise<{ models: any[] }> {
    const response = await api.get('/config/models');
    return response.data;
  },

  async createModel(model: { name: string; provider: string; model: string; api_key?: string; display_name?: string; max_tokens?: number; temperature?: number }): Promise<{ message: string; model: any }> {
    const response = await api.post('/config/models', model);
    return response.data;
  },

  async deleteModel(modelName: string): Promise<{ message: string }> {
    const response = await api.delete(`/config/models/${modelName}`);
    return response.data;
  },

  async validateApiKey(request: { provider: string; api_key: string; model?: string }): Promise<{ success: boolean; message: string }> {
    const response = await api.post('/config/validate-key', request);
    return response.data;
  },

  async detectOllama(): Promise<{ ollama_host: string; message: string }> {
    const response = await api.post('/config/detect-ollama');
    return response.data;
  },

  async testOllama(): Promise<{ success: boolean; message: string; details?: Record<string, string> }> {
    const response = await api.post('/config/test-ollama');
    return response.data;
  },

  async testDeepseek(): Promise<{ success: boolean; message: string; details?: Record<string, string> }> {
    const response = await api.post('/config/test-deepseek');
    return response.data;
  },
};

// ==================== Health Service ====================
export const healthService = {
  async check(): Promise<HealthResponse> {
    const response = await api.get<HealthResponse>('/health', { baseURL: API_BASE_URL });
    return response.data;
  },
};

export default api;
