/**
 * 本地 API 访问令牌解析（P0 鉴权）
 *
 * 后端开启鉴权后，所有 /api/** 与 /ws 请求都需要令牌。令牌来源按运行环境分两路：
 *
 * 1. Tauri 桌面端（含 `tauri dev`）
 *    Rust 侧 `get_api_token` 命令读取令牌文件：
 *      打包环境 → %APPDATA%/AgentMatrix/.token
 *      开发环境 → backend/.token
 *
 * 2. 浏览器直连 `next dev`
 *    无宿主能力，改走后端开发环境端点 `GET /api/v1/auth/dev-token`。
 *    该端点仅接受回环来源，且打包环境下不注册。
 *
 * 解析结果会被缓存；后端重启若重新生成了令牌，请求层收到 401 后会清缓存重取。
 */

import { isRunningInTauri, tauriInvoke } from '@/utils/tauri';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let cachedToken: string | null = null;
let inflight: Promise<string | null> | null = null;

async function fetchToken(): Promise<string | null> {
  // 1) 宿主注入（Tauri）
  if (isRunningInTauri()) {
    try {
      const token = await tauriInvoke<string>('get_api_token');
      if (token) return token;
    } catch (e) {
      console.warn('[Auth] Tauri 取令牌失败，回退到开发端点:', e);
    }
  }

  // 2) 开发环境端点
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/dev-token`);
    if (res.ok) {
      const data = (await res.json()) as { token?: string };
      if (data?.token) return data.token;
    }
  } catch (e) {
    console.warn('[Auth] 开发环境取令牌失败:', e);
  }

  return null;
}

/**
 * 获取访问令牌（带并发去重与缓存）。
 * 失败返回 null——此时请求会以未授权身份发出，由调用方按 401 处理。
 */
export async function getApiToken(force = false): Promise<string | null> {
  if (!force && cachedToken) return cachedToken;
  if (inflight) return inflight;

  inflight = fetchToken()
    .then((token) => {
      cachedToken = token;
      return token;
    })
    .finally(() => {
      inflight = null;
    });

  return inflight;
}

/** 获取已缓存的令牌（不触发请求），供同步场景使用 */
export function getCachedApiToken(): string | null {
  return cachedToken;
}

/** 清除缓存，下次调用会重新解析 */
export function clearApiTokenCache(): void {
  cachedToken = null;
}
