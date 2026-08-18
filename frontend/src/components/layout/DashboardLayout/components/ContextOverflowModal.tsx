'use client';

import React from 'react';

interface ContextOverflowModalProps {
  /** 是否显示弹窗 */
  visible: boolean;
  /** 当前上下文使用量 */
  currentTokens: number;
  /** 上下文上限 */
  limit: number;
  /** 选择"新建沙盒" */
  onNewSandbox: () => void;
  /** 选择"云端接管" */
  onSwitchToCloud: () => void;
  /** 选择"我已理解，关闭弹窗" */
  onDismiss: () => void;
}

const ContextOverflowModal: React.FC<ContextOverflowModalProps> = ({
  visible,
  currentTokens,
  limit,
  onNewSandbox,
  onSwitchToCloud,
  onDismiss,
}) => {
  if (!visible) return null;

  const usagePercent = Math.round((currentTokens / limit) * 100);

  return (
    <div className="context-overflow-overlay">
      <div className="context-overflow-modal">
        <div className="context-overflow-header">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#f97316" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <h3>上下文即将溢出</h3>
        </div>

        <div className="context-overflow-body">
          <p className="context-overflow-warning">
            当前上下文使用量已达 <strong>{usagePercent}%</strong>（{Math.round(currentTokens / 1000)}K / {Math.round(limit / 1000)}K tokens），
            即将超出本地模型（qwen2.5:7b）的处理上限。
          </p>

          <div className="context-overflow-risk">
            <h4>⚠️ 重要风险提示 — 请仔细阅读</h4>
            <ul>
              <li>
                <strong>本地模型已无法承载</strong>：当前上下文使用量已达 {usagePercent}%，超出
                本地模型（qwen2.5:7b / 16K tokens）处理上限，继续使用将导致<strong>上下文截断、
                对话历史丢失、回答质量严重下降</strong>。
              </li>
              <li>
                <strong className="context-overflow-highlight">切换至云端模型（DeepSeek V4 Pro）意味着：
                从此刻起，您的每一次提问都将消耗付费 API Token</strong>，
                按 DeepSeek 官方定价实时计费（输入 ¥1.00 / 百万 token，输出 ¥4.00 / 百万 token）。
                费用将从您配置的 DeepSeek API Key 账户中扣除。
              </li>
              <li>
                云端模型上下文上限为 <strong>1,048,576 tokens（1M）</strong>，可满足长期工程需求。
              </li>
            </ul>
          </div>

          <div className="context-overflow-cost-warning">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>
              <strong>请注意：</strong>选择"我已理解风险，关闭提示"后，本次对话<strong>将自动切换至云端付费模型</strong>，
              后续每一次提问都会产生费用，且不再重复提示。如需继续免费使用本地模型，请选择"新建沙盒，重新开始"。
            </span>
          </div>

          <div className="context-overflow-usage">
            <div className="context-overflow-bar">
              <div
                className="context-overflow-bar-fill"
                style={{ width: `${Math.min(usagePercent, 100)}%` }}
              />
            </div>
            <span className="context-overflow-bar-label">
              {Math.round(currentTokens / 1000)}K / {Math.round(limit / 1000)}K tokens
            </span>
          </div>
        </div>

        <div className="context-overflow-actions">
          <button
            className="context-overflow-btn context-overflow-btn--primary"
            onClick={onNewSandbox}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
            新建沙盒，重新开始
          </button>

          <button
            className="context-overflow-btn context-overflow-btn--cloud"
            onClick={onSwitchToCloud}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" />
            </svg>
            云端模型接管，继续对话
          </button>

          <button
            className="context-overflow-btn context-overflow-btn--dismiss"
            onClick={onDismiss}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
            我已理解风险，切换云端付费模式（不再提示）
          </button>
        </div>
      </div>

      <style jsx>{`
        .context-overflow-overlay {
          position: fixed;
          inset: 0;
          background: rgba(15, 23, 42, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 9999;
          backdrop-filter: blur(4px);
        }

        .context-overflow-modal {
          background: #ffffff;
          border-radius: 16px;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
          max-width: 520px;
          width: 90%;
          padding: 28px;
          animation: contextModalIn 0.3s ease;
        }

        @keyframes contextModalIn {
          from { opacity: 0; transform: translateY(20px) scale(0.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .context-overflow-header {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 20px;
        }

        .context-overflow-header h3 {
          font-size: 18px;
          font-weight: 600;
          color: #1e293b;
          margin: 0;
        }

        .context-overflow-warning {
          font-size: 14px;
          color: #475569;
          line-height: 1.6;
          margin: 0 0 16px;
        }

        .context-overflow-warning strong {
          color: #f97316;
        }

        .context-overflow-risk {
          background: #fef3c7;
          border: 1px solid #fcd34d;
          border-radius: 10px;
          padding: 14px 16px;
          margin-bottom: 16px;
        }

        .context-overflow-risk h4 {
          font-size: 13px;
          font-weight: 600;
          color: #92400e;
          margin: 0 0 8px;
        }

        .context-overflow-risk ul {
          margin: 0;
          padding-left: 18px;
        }

        .context-overflow-risk li {
          font-size: 12px;
          color: #78350f;
          line-height: 1.7;
          margin-bottom: 4px;
        }

        .context-overflow-risk li strong {
          color: #dc2626;
        }

        .context-overflow-highlight {
          background: #fef2f2;
          padding: 1px 4px;
          border-radius: 3px;
          border-bottom: 2px solid #dc2626;
        }

        .context-overflow-cost-warning {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 10px;
          padding: 12px 14px;
          margin-bottom: 16px;
        }

        .context-overflow-cost-warning svg {
          flex-shrink: 0;
          margin-top: 1px;
        }

        .context-overflow-cost-warning span {
          font-size: 12px;
          color: #991b1b;
          line-height: 1.6;
        }

        .context-overflow-cost-warning strong {
          color: #dc2626;
        }

        .context-overflow-usage {
          margin-bottom: 20px;
        }

        .context-overflow-bar {
          width: 100%;
          height: 8px;
          background: #f1f5f9;
          border-radius: 4px;
          overflow: hidden;
          margin-bottom: 6px;
        }

        .context-overflow-bar-fill {
          height: 100%;
          background: #f97316;
          border-radius: 4px;
          transition: width 0.5s ease;
        }

        .context-overflow-bar-label {
          font-size: 11px;
          color: #94a3b8;
          font-variant-numeric: tabular-nums;
        }

        .context-overflow-actions {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .context-overflow-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 10px 16px;
          border-radius: 10px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          border: none;
          transition: all 0.2s;
          width: 100%;
        }

        .context-overflow-btn--primary {
          background: #2563eb;
          color: #ffffff;
        }

        .context-overflow-btn--primary:hover {
          background: #1d4ed8;
        }

        .context-overflow-btn--cloud {
          background: #7c3aed;
          color: #ffffff;
        }

        .context-overflow-btn--cloud:hover {
          background: #6d28d9;
        }

        .context-overflow-btn--dismiss {
          background: #fef2f2;
          color: #dc2626;
          font-size: 13px;
          padding: 8px;
          border: 1px solid #fecaca;
        }

        .context-overflow-btn--dismiss:hover {
          background: #fee2e2;
          color: #b91c1c;
          border-color: #fca5a5;
        }
      `}</style>
    </div>
  );
};

export default ContextOverflowModal;