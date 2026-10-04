'use client';

import { useState, useEffect, useCallback } from 'react';
import { healthService } from '@/services/api/agentService';
import { useErrorStore } from '@/stores/errorStore';

interface SplashScreenProps {
  onReady: () => void;
}

const POLL_INTERVAL_MS = 500;   // V3.5.1: 500ms 轮询，更快感知后端就绪
const HARD_TIMEOUT_MS = 120000; // V3.5.1: 120秒硬超时，覆盖 PyInstaller 首次解压+后端初始化
const MAX_FAILURES = 240;       // V3.5.1: 240次×500ms=120秒，与硬超时对齐

export default function SplashScreen({ onReady }: SplashScreenProps) {
  const [statusText, setStatusText] = useState('正在连接后端服务...');
  const [visible, setVisible] = useState(true);
  const [fadeOut, setFadeOut] = useState(false);

  const checkHealth = useCallback(async (failureCount: number): Promise<void> => {
    try {
      const result = await healthService.check();
      if (result.status === 'ok' || result.status === 'healthy') {
        setStatusText('准备就绪');
        setTimeout(() => {
          setFadeOut(true);
          setTimeout(() => {
            setVisible(false);
            onReady();
          }, 500);
        }, 300);
        return;
      }
      // 后端返回但状态异常
      setStatusText('后端服务异常，正在重试...');
      if (failureCount + 1 >= MAX_FAILURES) {
        triggerFullscreenError('后端服务状态异常，请检查后端日志');
        return;
      }
      scheduleRetry(failureCount + 1);
    } catch (error: unknown) {
      const isConnRefused = error instanceof Error &&
        (error.message.includes('ECONNREFUSED') || error.message.includes('Network Error'));

      if (isConnRefused) {
        setStatusText('后端服务未启动，请检查端口 8000...');
        if (failureCount + 1 >= MAX_FAILURES) {
          triggerFullscreenError(
            '后端服务未响应，请检查端口 8000 是否被占用或后端是否已启动'
          );
          return;
        }
      } else {
        setStatusText('连接失败，正在重试...');
        if (failureCount + 1 >= MAX_FAILURES) {
          triggerFullscreenError('无法连接到后端服务，请检查网络连接');
          return;
        }
      }
      scheduleRetry(failureCount + 1);
    }
  }, [onReady]);

  const scheduleRetry = useCallback((nextFailureCount: number) => {
    setTimeout(() => checkHealth(nextFailureCount), POLL_INTERVAL_MS);
  }, [checkHealth]);

  function triggerFullscreenError(message: string) {
    useErrorStore.getState().showFullscreen(message, () => {
      useErrorStore.getState().dismiss();
      setVisible(false);
      onReady();
    });
    setStatusText('连接失败');
  }

  useEffect(() => {
    // 硬超时：超时后强制过渡到主界面（让用户能手动操作）
    const hardTimeout = setTimeout(() => {
      setFadeOut(true);
      setTimeout(() => {
        setVisible(false);
        onReady();
      }, 500);
    }, HARD_TIMEOUT_MS);

    // 开始轮询
    checkHealth(0);

    return () => clearTimeout(hardTimeout);
  }, [checkHealth, onReady]);

  if (!visible) return null;

  return (
    <div className={`splash-screen ${fadeOut ? 'splash-fade-out' : ''}`}>
      <div className="splash-content">
        <div className="splash-logo">
          <img src="/image/logo.png" alt="AgentMatrix" className="splash-logo-img" />
        </div>
        <h1 className="splash-title">AgentMatrix</h1>
        <p className="splash-subtitle">多智能体协同平台</p>
        <div className="splash-spinner" />
        <p className="splash-status">{statusText}</p>
      </div>
    </div>
  );
}