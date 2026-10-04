'use client';

import { useState, useCallback } from 'react';
import { useErrorStore } from '@/stores/errorStore';
import type { ErrorLevel } from '@/stores/errorStore';
import { isRunningInTauri, tauriInvoke } from '@/utils/tauri';

const ICONS: Record<ErrorLevel, string> = {
  info: 'i',
  warning: '!',
  error: 'x',
};

const COLORS: Record<ErrorLevel, { border: string; bg: string; text: string }> = {
  info:    { border: 'var(--blue)',   bg: 'rgba(59, 130, 246, 0.1)',  text: 'var(--blue)' },
  warning: { border: 'var(--orange)', bg: 'rgba(245, 158, 11, 0.1)',  text: 'var(--orange)' },
  error:   { border: 'var(--red)',    bg: 'rgba(239, 68, 68, 0.1)',   text: 'var(--red)' },
};

export default function ErrorOverlay() {
  const { level, message, mode, visible, retryAction, dismiss } = useErrorStore();
  const [restarting, setRestarting] = useState(false);
  const [restartMsg, setRestartMsg] = useState('');

  // 手动重启：优先使用 Tauri invoke，降级使用 retryAction
  const handleRestart = useCallback(async () => {
    setRestarting(true);
    setRestartMsg('正在重启后端服务...');

    try {
      if (isRunningInTauri()) {
        await tauriInvoke('restart_sidecar');
        setRestartMsg('后端服务重启成功');
        // 等待后端完全就绪后关闭错误遮罩
        setTimeout(() => {
          dismiss();
          setRestarting(false);
          setRestartMsg('');
        }, 1500);
      } else if (retryAction) {
        // 浏览器模式：执行原有的重试逻辑
        retryAction();
        dismiss();
        setRestarting(false);
        setRestartMsg('');
      } else {
        setRestartMsg('无法重启：未在 Tauri 环境中且无重试操作');
        setRestarting(false);
      }
    } catch (e) {
      setRestartMsg(`重启失败: ${e instanceof Error ? e.message : String(e)}`);
      setRestarting(false);
    }
  }, [retryAction, dismiss]);

  if (!visible) return null;

  const color = COLORS[level];

  // === 全屏遮罩模式 ===
  if (mode === 'fullscreen') {
    return (
      <div className="error-overlay-backdrop" onClick={(e) => e.stopPropagation()}>
        <div className="error-overlay-card">
          <div className="error-overlay-icon" style={{ color: color.text }}>{ICONS[level]}</div>
          <h2 className="error-overlay-title">服务异常</h2>
          <p className="error-overlay-message">{restartMsg || message}</p>
          <div className="error-overlay-actions">
            <button
              className="btn btn-primary"
              onClick={handleRestart}
              disabled={restarting}
            >
              {restarting ? (
                <><div className="splash-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> 重启中...</>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                  </svg>
                  手动重启
                </>
              )}
            </button>
            <button className="btn btn-secondary" onClick={dismiss}>关闭</button>
          </div>
        </div>
      </div>
    );
  }

  // === 通知栏模式 ===
  return (
    <div
      className="error-toast"
      style={{ borderColor: color.border, background: color.bg }}
    >
      <span className="error-toast-icon" style={{ color: color.text }}>{ICONS[level]}</span>
      <span className="error-toast-message">{restartMsg || message}</span>
      {retryAction && (
        <button className="btn btn-secondary" onClick={handleRestart} style={{ fontSize: 12, padding: '4px 12px' }}>
          重试
        </button>
      )}
      <button className="error-toast-close" onClick={dismiss}>&times;</button>
    </div>
  );
}