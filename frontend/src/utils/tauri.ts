/**
 * Tauri 环境检测与 invoke 封装
 * 在 Tauri WebView 中使用原生 invoke，在浏览器开发模式中降级处理
 */

let _isTauri: boolean | null = null;

/** 检测是否运行在 Tauri WebView 中 */
export function isRunningInTauri(): boolean {
  if (_isTauri !== null) return _isTauri;
  try {
    _isTauri = typeof window !== 'undefined' && '__TAURI__' in window;
  } catch {
    _isTauri = false;
  }
  return _isTauri;
}

/** 调用 Tauri 命令，自动降级 */
export async function tauriInvoke<T = unknown>(
  command: string,
  args?: Record<string, unknown>
): Promise<T> {
  if (!isRunningInTauri()) {
    console.warn(`[Tauri] Not in Tauri environment, skipping invoke('${command}')`);
    throw new Error('Not running in Tauri environment');
  }
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<T>(command, args);
}

/** 监听 Tauri 事件，自动降级 */
export async function tauriListen<T = unknown>(
  event: string,
  handler: (payload: T) => void
): Promise<() => void> {
  if (!isRunningInTauri()) {
    console.warn(`[Tauri] Not in Tauri environment, skipping listen('${event}')`);
    return () => {};
  }
  const { listen } = await import('@tauri-apps/api/event');
  const unlisten = await listen<T>(event, (e) => handler(e.payload));
  return unlisten;
}