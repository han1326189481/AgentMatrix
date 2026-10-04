import axios from 'axios';
import { useErrorStore } from '@/stores/errorStore';
import { clearApiTokenCache, getApiToken } from './apiToken';
import type {
  WorkflowInput,
  WorkflowOutput,
  ExportRequest,
  ExportResponse,
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

/** 附加 Bearer 令牌（P0 鉴权）：所有走本实例的 REST 请求统一携带 */
api.interceptors.request.use(async (config) => {
  const token = await getApiToken();
  if (token) {
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  return config;
});

type RetriableConfig = NonNullable<Parameters<typeof api.request>[0]> & { _authRetried?: boolean };

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.message || '请求失败';
      const status = error.response?.status;
      const url = error.config?.url || '';
      console.error(`[API Error] ${url}:`, message);

      // P0: 令牌失效（例如后端重启后重新生成了令牌）→ 清缓存重取，并原请求重试一次
      const config = error.config as RetriableConfig | undefined;
      if (status === 401 && config && !config._authRetried) {
        config._authRetried = true;
        clearApiTokenCache();
        const token = await getApiToken(true);
        if (token) {
          config.headers = config.headers ?? {};
          (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
          return api.request(config);
        }
      }

      // 健康检查请求不触发全局错误提示（SplashScreen 有自己的重试逻辑）
      const isHealthCheck = url.includes('/health');
      if (!isHealthCheck) {
        if (!error.response || status === 0) {
          useErrorStore.getState().showWarning('后端服务连接失败，请检查服务是否正常运行');
        } else if (status === 401) {
          useErrorStore.getState().showError('访问令牌无效，请重启应用以刷新本地令牌');
        } else if (status && status >= 500) {
          useErrorStore.getState().showError(`服务器错误 (${status}): ${message}`);
        }
      }
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
};

// ==================== Export Service ====================
export const exportService = {
  /** 统一导出入口：根据 format 调用对应端点 */
  async export(request: ExportRequest): Promise<ExportResponse> {
    const format = request.format;
    // V3: 支持 markdown / docx / pptx / mindmap 四种格式
    const endpoint = `/export/${format}`;
    const response = await api.post<ExportResponse>(endpoint, request);
    return response.data;
  },
};

// ==================== Config Service ====================
// 仅保留 OllamaGuide 实际使用的方法
export const configService = {
  async listModels(): Promise<{ models: Array<{ name: string; provider: string; model: string }> }> {
    const response = await api.get('/config/models');
    return response.data;
  },

  async detectOllama(host?: string, port?: string): Promise<{ ollama_host: string; message: string }> {
    const response = await api.post('/config/detect-ollama', { host, port });
    return response.data;
  },

  async testOllama(host?: string, port?: string): Promise<{ success: boolean; message: string; details?: Record<string, string> }> {
    const response = await api.post('/config/test-ollama', { host, port });
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
