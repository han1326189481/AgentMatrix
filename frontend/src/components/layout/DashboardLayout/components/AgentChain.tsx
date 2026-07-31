'use client';

import React, { useState } from 'react';
import { useWorkflowStore } from '@/stores/workflowStore';
import type { AgentId, StepMetadata } from '@/types';
import {
  AGENT_DISPLAY_NAMES,
  AGENT_SVG_ICONS,
  AGENT_SUBTITLES,
  getAgentColorValue,
} from '../constants';
import { AGENT_ORDER } from '@/types';

const AgentChain: React.FC = () => {
  const {
    workflowSteps,
    isRunning,
    currentStep,
    completedSteps,
    complexityScore,
    judgeDecision,
    result,
  } = useWorkflowStore();

  const [expandedAgent, setExpandedAgent] = useState<AgentId | null>(null);

  const getStepStatus = (agentId: AgentId): 'completed' | 'running' | 'pending' | 'error' => {
    if (completedSteps.includes(agentId)) return 'completed';
    if (isRunning && currentStep === agentId) return 'running';
    const step = workflowSteps.find((s) => s.agent_id === agentId);
    if (step && !step.success) return 'error';
    return 'pending';
  };

  const getStepData = (agentId: AgentId) => {
    return workflowSteps.find((s) => s.agent_id === agentId);
  };

  const getConnectionStatus = (fromIdx: number): 'active' | 'inactive' => {
    const fromId = AGENT_ORDER[fromIdx];
    const toId = AGENT_ORDER[fromIdx + 1];
    if (!toId) return 'inactive';
    if (completedSteps.includes(fromId) && (completedSteps.includes(toId) || isRunning)) return 'active';
    return 'inactive';
  };

  const toggleExpand = (agentId: AgentId) => {
    setExpandedAgent(expandedAgent === agentId ? null : agentId);
  };

  return (
    <div className="agent-chain-compact">
      <div className="chain-header">
        <h3>多智能体工作流</h3>
        <span className="chain-badge">{AGENT_ORDER.length} Agents</span>
      </div>

      {/* Vertical Chain */}
      <div className="chain-vertical">
        {AGENT_ORDER.map((agentId, idx) => {
          const status = getStepStatus(agentId);
          const step = getStepData(agentId);
          const isExpanded = expandedAgent === agentId;
          const hasDetail = step && (step.input || step.output);
          const agentColor = getAgentColorValue(agentId);

          return (
            <React.Fragment key={agentId}>
              {/* Connection Line */}
              {idx > 0 && (
                <div className={`chain-connection ${getConnectionStatus(idx - 1)}`}>
                  <div className="connection-line" />
                  {getConnectionStatus(idx - 1) === 'active' && (
                    <div className="connection-pulse" />
                  )}
                </div>
              )}

              {/* Agent Node */}
              <div
                className={`chain-node ${status} ${hasDetail ? 'clickable' : ''}`}
                onClick={() => hasDetail && toggleExpand(agentId)}
                style={{ cursor: hasDetail ? 'pointer' : 'default' }}
              >
                <div className="node-indicator" style={{
                  '--agent-color': status === 'error' ? 'var(--red)' : agentColor
                } as React.CSSProperties}>
                  <div className="node-dot" />
                  {status === 'running' && <div className="node-ripple" />}
                </div>

                <div className="node-content">
                  <div className="node-header">
                    <span className="node-icon" style={{ color: agentColor }}>
                      {AGENT_SVG_ICONS[agentId]}
                    </span>
                    <span className="node-name">{AGENT_DISPLAY_NAMES[agentId]}</span>
                    {status === 'running' && <span className="node-badge running">运行中</span>}
                    {status === 'completed' && <span className="node-badge completed">✓</span>}
                    {status === 'error' && <span className="node-badge error">✗</span>}
                    {hasDetail && (
                      <span className="node-expand-icon" style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-muted)' }}>
                        {isExpanded ? '▼' : '▶'}
                      </span>
                    )}
                  </div>

                  <span className="node-subtitle">{AGENT_SUBTITLES[agentId]}</span>

                  {step && (
                    <div className="node-stats">
                      <span className="stat-item">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="10" />
                          <polyline points="12 6 12 12 16 14" />
                        </svg>
                        {step.duration_seconds.toFixed(2)}s
                      </span>
                      {(step.metadata as StepMetadata)?.model_used && (
                        <span className="stat-item">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                            <line x1="8" y1="21" x2="16" y2="21" />
                            <line x1="12" y1="17" x2="12" y2="21" />
                          </svg>
                          {(step.metadata as StepMetadata).model_used}
                        </span>
                      )}
                      {(step.metadata as StepMetadata)?.reasoning_pattern && (
                        <span className="stat-item" style={{ background: 'rgba(139,92,246,0.1)', color: 'var(--purple)', padding: '1px 6px', borderRadius: 8 }}>
                          {(step.metadata as StepMetadata).reasoning_pattern}
                        </span>
                      )}
                      {(step.metadata as StepMetadata)?.error && (
                        <span className="stat-item" style={{ color: 'var(--red)' }}>
                          {(step.metadata as StepMetadata).error}
                        </span>
                      )}
                    </div>
                  )}

                  {/* 展开详情 */}
                  {isExpanded && step && (
                    <div className="node-detail">
                      {step.input && (
                        <div className="detail-section">
                          <div className="detail-label">输入</div>
                          <pre className="detail-code">{step.input.slice(0, 500)}{step.input.length > 500 ? '...' : ''}</pre>
                        </div>
                      )}
                      {step.output && (
                        <div className="detail-section">
                          <div className="detail-label">输出</div>
                          <pre className="detail-code">{step.output.slice(0, 800)}{step.output.length > 800 ? '...' : ''}</pre>
                        </div>
                      )}
                      {step.metadata && Object.keys(step.metadata).length > 0 && (
                        <div className="detail-section">
                          <div className="detail-label">元数据</div>
                          <pre className="detail-code">{JSON.stringify(step.metadata, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {/* Complexity & Decision Summary */}
      {result && (
        <div className="chain-summary">
          <div className="summary-row">
            <span className="summary-label">复杂度评分</span>
            <div className="summary-bar-wrapper">
              <div
                className="summary-bar"
                style={{ width: `${(complexityScore * 100).toFixed(0)}%` }}
              />
            </div>
            <span className="summary-value">{complexityScore.toFixed(2)}</span>
          </div>
          <div className="summary-row">
            <span className="summary-label">执行模式</span>
            <span className={`summary-value ${judgeDecision === 'cloud' ? 'cloud' : 'local'}`}>
              {judgeDecision === 'cloud' ? '云端增强' : '本地执行'}
            </span>
          </div>
          <div className="summary-row">
            <span className="summary-label">总耗时</span>
            <span className="summary-value">{result.total_duration_seconds.toFixed(2)}s</span>
          </div>
          {result.partial_success && result.error_summary && (
            <div className="summary-row" style={{ color: 'var(--red)', fontSize: 11 }}>
              <span className="summary-label">部分失败</span>
              <span>{result.error_summary.length} 个错误</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AgentChain;
