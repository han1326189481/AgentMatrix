import { configService } from '@/services/api/agentService';

export interface OllamaStatus {
  detected: boolean;
  host: string;
  message: string;
  models: string[];
  checking: boolean;
}

const DETECT_TIMEOUT_MS = 10000;

/**
 * 检测 Ollama 服务是否可用
 * 超时 10 秒，超时视为未检测到
 */
export async function detectOllama(): Promise<OllamaStatus> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), DETECT_TIMEOUT_MS);

    const result = await configService.detectOllama();
    clearTimeout(timeoutId);

    const detected = !result.message.includes('未检测到');

    // 检测到 Ollama 后获取模型列表
    let models: string[] = [];
    if (detected) {
      try {
        const modelsResult = await configService.listModels();
        models = (modelsResult.models || []).map((m: { name: string }) => m.name);
      } catch {
        // 模型列表获取失败不阻塞
      }
    }

    return {
      detected,
      host: result.ollama_host,
      message: result.message,
      models,
      checking: false,
    };
  } catch (error: unknown) {
    const isTimeout = error instanceof DOMException && error.name === 'AbortError';
    return {
      detected: false,
      host: 'http://localhost:11434',
      message: isTimeout ? 'Ollama 检测超时，请检查服务是否正常运行' : 'Ollama 检测失败',
      models: [],
      checking: false,
    };
  }
}

/**
 * 测试 Ollama 连接
 */
export async function testOllama(host?: string, port?: string): Promise<boolean> {
  try {
    const result = await configService.testOllama(host, port);
    return result.success;
  } catch {
    return false;
  }
}