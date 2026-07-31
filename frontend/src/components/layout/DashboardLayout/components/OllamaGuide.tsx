'use client';

import { useState, useCallback } from 'react';
import { detectOllama, testOllama } from '@/services/ollamaService';
import type { OllamaStatus } from '@/services/ollamaService';

interface OllamaGuideProps {
  onStatusChange?: (status: OllamaStatus) => void;
}

export default function OllamaGuide({ onStatusChange }: OllamaGuideProps) {
  const [status, setStatus] = useState<OllamaStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const handleDetect = useCallback(async () => {
    setLoading(true);
    const result = await detectOllama();
    setStatus(result);
    onStatusChange?.(result);
    setLoading(false);
  }, [onStatusChange]);

  const handleRetest = useCallback(async () => {
    setLoading(true);
    const ok = await testOllama();
    if (ok) {
      // 重新检测以获取完整状态
      const result = await detectOllama();
      setStatus(result);
      onStatusChange?.(result);
    } else {
      setStatus({
        detected: false,
        host: 'http://localhost:11434',
        message: 'Ollama 服务仍未检测到，请确认已安装并启动',
        models: [],
        checking: false,
      });
    }
    setLoading(false);
  }, [onStatusChange]);

  const handleCopyCommand = useCallback((cmd: string) => {
    navigator.clipboard.writeText(cmd).catch(() => {});
  }, []);

  // 已检测到 Ollama 且有模型
  if (status?.detected && status.models.length > 0) {
    return (
      <div className="card animate-in">
        <div className="card-title">Ollama 状态</div>
        <div className="ollama-status ok">
          <span className="ollama-dot" />
          <span>已连接 — {status.host}</span>
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
          已安装模型：{status.models.join(', ')}
        </div>
      </div>
    );
  }

  // 已检测到 Ollama 但无模型
  if (status?.detected && status.models.length === 0) {
    return (
      <div className="card animate-in">
        <div className="card-title">Ollama 状态</div>
        <div className="ollama-status ok">
          <span className="ollama-dot" />
          <span>已连接 — {status.host}</span>
        </div>
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
            未检测到已安装的模型，请先下载模型：
          </div>
          <div className="ollama-command">
            <code>ollama pull llama3.2</code>
            <button className="ollama-copy-btn" onClick={() => handleCopyCommand('ollama pull llama3.2')} title="复制命令">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
            </button>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
            在终端中运行上述命令下载模型，然后点击重新检测
          </div>
        </div>
        <button className="btn btn-secondary" onClick={handleRetest} disabled={loading} style={{ marginTop: 12, width: '100%', justifyContent: 'center' }}>
          {loading ? '检测中...' : '重新检测'}
        </button>
      </div>
    );
  }

  // 未检测或未检测到
  return (
    <div className="card animate-in">
      <div className="card-title">Ollama 服务</div>
      {status && !status.detected ? (
        <>
          <div className="ollama-status error">
            <span className="ollama-dot" />
            <span>{status.message}</span>
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
              请先安装 Ollama 并启动服务：
            </div>
            <a
              href="https://ollama.com/download"
              target="_blank"
              rel="noopener noreferrer"
              className="ollama-link"
            >
              前往 Ollama 官网下载 →
            </a>
          </div>
          <button className="btn btn-secondary" onClick={handleRetest} disabled={loading} style={{ marginTop: 12, width: '100%', justifyContent: 'center' }}>
            {loading ? '检测中...' : '重新检测'}
          </button>
        </>
      ) : (
        <button className="btn btn-secondary" onClick={handleDetect} disabled={loading} style={{ width: '100%', justifyContent: 'center' }}>
          {loading ? '检测中...' : '检测 Ollama 服务'}
        </button>
      )}
    </div>
  );
}