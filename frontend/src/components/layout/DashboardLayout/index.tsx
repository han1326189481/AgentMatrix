'use client';

import React, { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { useWorkflowStore } from '@/stores/workflowStore';
import { sandboxService } from '@/services/api/sandboxService';
import ThemeToggle from './components/ThemeToggle';
import DecisionCard from './components/DecisionCard';
import OllamaGuide from './components/OllamaGuide';
import ErrorOverlay from './components/ErrorOverlay';
import AuditNotification from './components/AuditNotification';
import ClarifyNotification from './components/ClarifyNotification';
import MetricsBar from './components/MetricsBar';
import ContextBar from './components/ContextBar';
import ContextPanel from './components/ContextPanel';
import ContextOverflowModal from './components/ContextOverflowModal';
import SandboxSidebar from './components/SandboxSidebar';
import CloudModelSettingsModal from './components/CloudModelSettingsModal';
import { isCloudModelConfigured } from '@/services/api/settingsService';
import { useTheme } from './ThemeProvider';
import type { ContextUsage } from '@/types';

// V3: ChatInterface 禁用 SSR，避免 recommendEnabled/chatHistory 等
// localStorage 状态在 SSR/CSR 不一致导致的 Hydration 错误
// 聊天界面本就是纯客户端交互组件，不需要 SSR
const ChatInterface = dynamic(() => import('./components/ChatInterface'), {
  ssr: false,
  loading: () => (
    <div style={{ padding: '20px', textAlign: 'center', color: '#888' }}>
      正在加载聊天界面...
    </div>
  ),
});

const DashboardLayout: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const { isRunning, initWebSocket, sandboxId, setSandboxId, setForceCloud } = useWorkflowStore();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [sandboxPanelOpen, setSandboxPanelOpen] = useState(true);

  // V3.5.1: 云端模型设置弹窗（首次启动引导 + 日常设置）
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // V4.2: 上下文溢出弹窗状态
  const [overflowContext, setOverflowContext] = useState<ContextUsage | null>(null);
  const [overflowDismissed, setOverflowDismissed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('agentmatrix_overflow_dismissed') === 'true';
  });

  // V4.2: 上下文溢出回调 — 仅当未被 dismiss 时弹窗
  const handleOverflow = useCallback((ctx: ContextUsage) => {
    if (!overflowDismissed) {
      setOverflowContext(ctx);
    }
  }, [overflowDismissed]);

  // V4.2: 选项一 — 新建沙盒，重新开始
  const handleNewSandbox = useCallback(async () => {
    try {
      const newSandbox = await sandboxService.create('新对话（上下文溢出后重建）');
      setSandboxId(newSandbox.id);
    } catch (e) {
      console.error('创建新沙盒失败:', e);
    }
    setOverflowContext(null);
  }, [setSandboxId]);

  // V4.2: 选项二 — 云端模型接管，继续对话
  const handleSwitchToCloud = useCallback(() => {
    setForceCloud(true);
    setOverflowContext(null);
  }, [setForceCloud]);

  // V4.2: 选项三 — 我已理解风险，切换云端付费模式（不再提示）
  const handleDismissOverflow = useCallback(() => {
    setForceCloud(true);
    if (typeof window !== 'undefined') {
      localStorage.setItem('agentmatrix_overflow_dismissed', 'true');
    }
    setOverflowDismissed(true);
    setOverflowContext(null);
  }, [setForceCloud]);

  // 初始化 WebSocket 连接（仅客户端）
  // initWebSocket 返回 cleanup 函数，防止 StrictMode 重复注册 handler
  useEffect(() => {
    const cleanup = initWebSocket();
    return cleanup;
  }, [initWebSocket]);

  // V3.5.1: 首次启动检测 — 后端启动后检查密钥是否已配置
  // 延迟 2 秒检测，等待后端启动完成（桌面端 Rust 侧启动后端有延迟）
  useEffect(() => {
    const timer = setTimeout(async () => {
      const configured = await isCloudModelConfigured();
      if (!configured) {
        setShowOnboarding(true);
      }
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="dashboard-layout">
      {/* Top Bar */}
      <header className="dashboard-topbar">
        <div className="topbar-left">
          <button 
            className="topbar-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            title="切换侧边栏"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <div className="topbar-brand">
            <span className="brand-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </span>
            <span className="brand-text">AgentMatrix</span>
          </div>
        </div>

        <div className="topbar-center">
          {isRunning && (
            <div className="running-bar">
              <div className="running-dots-small">
                <span /><span /><span />
              </div>
              <span>Agent 工作流运行中</span>
            </div>
          )}
        </div>

        <div className="topbar-right">
          {/* V4.1: 实时指标面板（缓存命中率 + 成本节省） */}
          <MetricsBar compact />
          <div className="topbar-divider" />
          {/* V4.2: 上下文使用进度条 */}
          <ContextBar compact onOverflow={handleOverflow} />
          <div className="topbar-divider" />
          <button
            className="topbar-btn"
            onClick={() => setRightPanelOpen(!rightPanelOpen)}
            title="切换工作流面板"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7" />
              <rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
            </svg>
          </button>
          {/* V3.5.1: 云端模型设置按钮 */}
          <button
            className="topbar-btn"
            onClick={() => setShowSettings(true)}
            title="云端模型设置"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
      </header>

      <div className="dashboard-body">
        {/* Left Sidebar */}
        <aside className={`dashboard-sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
          <div className="sidebar-content">
            <DecisionCard />
            <div className="sidebar-divider" />
            <OllamaGuide />
          </div>
        </aside>

        {/* 沙盒侧边栏 — 对话列表 */}
        <SandboxSidebar
          collapsed={!sandboxPanelOpen}
          onToggle={() => setSandboxPanelOpen(!sandboxPanelOpen)}
        />

        {/* Main Chat Area */}
        <main className="dashboard-main">
          <ChatInterface />
        </main>

        {/* Right Panel - 上下文使用量监控 */}
        <aside className={`dashboard-right ${rightPanelOpen ? 'open' : 'closed'}`}>
          <div className="right-content">
            <ContextPanel />
          </div>
        </aside>
      </div>

      {/* Error Overlay */}
      <ErrorOverlay />

      {/* V3.3: 知识库质检弹窗 */}
      <AuditNotification />

      {/* V3.4: 抱怨澄清弹窗 */}
      <ClarifyNotification />

      {/* V3.5.1: 首次启动引导弹窗（检测到无密钥时自动弹出） */}
      {showOnboarding && (
        <CloudModelSettingsModal
          mode="onboarding"
          onClose={() => setShowOnboarding(false)}
        />
      )}

      {/* V3.5.1: 云端模型设置弹窗（点击齿轮按钮打开） */}
      {showSettings && (
        <CloudModelSettingsModal
          mode="settings"
          onClose={() => setShowSettings(false)}
        />
      )}

      {/* V4.2: 上下文溢出弹窗（一次性 — 选项三 dismiss 后不再显示） */}
      <ContextOverflowModal
        visible={overflowContext !== null}
        currentTokens={overflowContext?.total_tokens ?? 0}
        limit={overflowContext?.limit ?? 16384}
        onNewSandbox={handleNewSandbox}
        onSwitchToCloud={handleSwitchToCloud}
        onDismiss={handleDismissOverflow}
      />
    </div>
  );
};

export default DashboardLayout;