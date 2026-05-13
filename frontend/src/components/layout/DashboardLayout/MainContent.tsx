'use client';

import { useWorkflowStore } from '@/stores/workflowStore';
import type { AgentId } from '@/types';

const AGENT_EMOJIS: Record<AgentId, string> = {
  knowledge: '📄',
  summary: '✏️',
  writer: '🏆',
  review: '⚖️',
  judge: '☁️',
  result: '📋',
};

const AGENT_NAMES: Record<AgentId, string> = {
  knowledge: 'A 摘要 Agent',
  summary: 'B 撰写 Agent',
  writer: 'C 评审 Agent',
  review: '评委 Agent',
  judge: 'API网关',
  result: '最终答案输出',
};

const AGENT_MODELS: Record<AgentId, string> = {
  knowledge: 'Qwen2.5-3B',
  summary: 'Qwen2.5-7B',
  writer: 'Qwen2.5-3B',
  review: 'Qwen2.5-3B',
  judge: 'DeepSeek-V4',
  result: 'Local',
};

const AGENT_COLORS: Record<AgentId, string> = {
  knowledge: 'green',
  summary: 'green',
  writer: 'gold',
  review: 'purple',
  judge: 'orange',
  result: 'blue',
};

export default function MainContent() {
  const { isRunning, currentTask, currentStep, completedSteps, result, judgeDecision } = useWorkflowStore();

  const hasContent = completedSteps.length > 0 || isRunning;

  const getNodeStatus = (agentId: AgentId) => {
    if (completedSteps.includes(agentId)) return 'completed';
    if (currentStep === agentId) return 'working';
    return 'pending';
  };

  const renderMarkdown = (text: string) => {
    return text
      .replace(/^# (.*$)/gm, '<h1>$1</h1>')
      .replace(/^## (.*$)/gm, '<h2>$1</h2>')
      .replace(/^### (.*$)/gm, '<h3>$1</h3>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/^- (.*$)/gm, '<li>$1</li>')
      .replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
      .replace(/\n\n/g, '<br/>');
  };

  const progressPercent = completedSteps.length > 0 ? Math.round((completedSteps.length / 6) * 100) : 0;

  return (
    <main className="content-center">
      {!hasContent ? (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          gap: 40,
          padding: 40,
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{
              width: 80,
              height: 80,
              borderRadius: '50%',
              background: 'rgba(59, 130, 246, 0.1)',
              border: '2px solid rgba(59, 130, 246, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px',
              fontSize: 36,
            }}>
              🧠
            </div>
            <h1 style={{
              fontSize: 32,
              fontWeight: 700,
              color: 'var(--text-primary)',
              marginBottom: 12,
            }}>
              NeuroFlow 多智能体协同平台
            </h1>
            <p style={{
              fontSize: 14,
              color: 'var(--text-secondary)',
              maxWidth: 480,
              margin: '0 auto',
              lineHeight: 1.6,
            }}>
              在顶部任务栏输入您的需求，多个 AI Agent 将协同工作为您生成高质量的结果
            </p>
          </div>

          <div style={{
            display: 'flex',
            gap: 24,
            flexWrap: 'wrap',
            justifyContent: 'center',
          }}>
            {(['knowledge', 'summary', 'writer', 'review', 'judge', 'result'] as AgentId[]).map((agentId, index) => (
              <div key={agentId} style={{ textAlign: 'center', opacity: 0.6 }}>
                <div style={{
                  width: 56,
                  height: 56,
                  borderRadius: 12,
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 24,
                  marginBottom: 8,
                }}>
                  {AGENT_EMOJIS[agentId]}
                </div>
                <div style={{
                  fontSize: 11,
                  color: 'var(--text-secondary)',
                  fontWeight: 500,
                }}>{AGENT_NAMES[agentId]}</div>
                {index < 5 && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 18, marginTop: 8 }}>→</div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <>
          <div className="pipeline-section animate-in delay-1">
            <div className="section-header">
              <span className="section-title">多智能体协同流水线</span>
              <div className="legend">
                <div className="legend-item">
                  <div className="legend-line solid" />
                  <span>数据流</span>
                </div>
                <div className="legend-item">
                  <div className="legend-line dashed" />
                  <span>控制流</span>
                </div>
              </div>
            </div>

            <div className="pipeline-container">
              <div className="pipeline-node blue animate-in delay-1" style={{ minWidth: 240 }}>
                <div className="node-icon">👤</div>
                <div className="node-title">用户输入</div>
                <div className="node-subtitle">{currentTask}</div>
              </div>

              <div className="arrow-down animate-in delay-1" />

              <div className="pipeline-row animate-in delay-2">
                {(['knowledge', 'summary', 'writer'] as AgentId[]).map((agentId) => {
                  const status = getNodeStatus(agentId);
                  return (
                    <div key={agentId} className={`pipeline-node ${AGENT_COLORS[agentId]}`}>
                      <div className="node-icon">{AGENT_EMOJIS[agentId]}</div>
                      <div className="node-title">{AGENT_NAMES[agentId]}</div>
                      <div className="node-subtitle">{AGENT_MODELS[agentId]}</div>
                      <div className={`node-status ${status}`}>
                        {status === 'working' ? (
                          <>
                            <span className="spinner" /> 处理中...
                          </>
                        ) : status === 'completed' ? (
                          '✓ 已完成'
                        ) : (
                          '等待中'
                        )}
                      </div>
                      {agentId === 'writer' && (completedSteps.includes('writer') || currentStep === 'writer') && (
                        <div className="difficulty-box">
                          <div className="difficulty-score">0.72</div>
                          <div className="difficulty-threshold">难度评分</div>
                          <div className="difficulty-threshold">阈值: 0.65</div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="arrow-down animate-in delay-2" />

              <div className={`pipeline-node purple animate-in delay-3`} style={{ minWidth: 180 }}>
                <div className="node-icon">{AGENT_EMOJIS.review}</div>
                <div className="node-title">{AGENT_NAMES.review}</div>
                <div className="node-subtitle">{AGENT_MODELS['review']}</div>
                <div className={`node-status ${getNodeStatus('review')}`}>
                  {getNodeStatus('review') === 'working' ? (
                    <>
                      <span className="spinner" /> 工作中...
                    </>
                  ) : getNodeStatus('review') === 'completed' ? (
                    '✓ 已完成'
                  ) : (
                    '等待中'
                  )}
                </div>
              </div>

              <div className="branch-arrows animate-in delay-4">
                <div className="branch-arrow">
                  <span className="branch-label green">简单任务 (≤ 阈值)</span>
                  <div className="arrow-down" style={{ height: 20 }} />
                </div>
                <div className="branch-arrow">
                  <span className="branch-label orange">困难任务 (&gt; 阈值)</span>
                  <div className="arrow-down" style={{ height: 20 }} />
                </div>
              </div>

              <div className="pipeline-row animate-in delay-4">
                <div className={`pipeline-node green${judgeDecision === 'local' && completedSteps.includes('review') ? ' selected' : ''}`}>
                  <div className="node-icon">🏆</div>
                  <div className="node-title">内部PK胜出</div>
                  <div className="node-subtitle">本地模型输出更优</div>
                  {judgeDecision === 'local' && completedSteps.includes('review') && (
                    <div className="node-status completed">✓ 已选择</div>
                  )}
                </div>
                <div className={`pipeline-node orange${judgeDecision === 'cloud' && completedSteps.includes('judge') ? ' selected' : ''}`}>
                  <div className="node-icon">☁️</div>
                  <div className="node-title">API网关</div>
                  <div className="node-subtitle">DeepSeek-V4</div>
                  {(getNodeStatus('judge') === 'working' || (judgeDecision === 'cloud' && completedSteps.includes('judge'))) && (
                    <div className="node-status loading">
                      {getNodeStatus('judge') === 'working' ? (
                        <>
                          <span className="spinner" /> 调用中... 245 tokens
                        </>
                      ) : (
                        '✓ 已完成'
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="arrow-down animate-in delay-4" />

              <div className="pipeline-node blue animate-in delay-5" style={{ minWidth: 200 }}>
                <div className="node-icon">📋</div>
                <div className="node-title">最终答案输出</div>
                <div className="node-subtitle">生成最终完整回答</div>
              </div>
            </div>
          </div>

          {(result || isRunning) && (
            <div className="final-answer-section animate-in delay-5">
              <div className="answer-header">
                <div className="answer-title">
                  最终答案
                  <span className="answer-progress-badge">
                    {isRunning ? `生成中 ${progressPercent}%` : `已完成 ${progressPercent}%`}
                  </span>
                </div>
              </div>

              <div className="answer-container">
                <div className="answer-content">
                  {result ? (
                    <div dangerouslySetInnerHTML={{ __html: renderMarkdown(result.final_result) }} />
                  ) : (
                    <div>
                      <h1>智能体协作年度计划（2024）</h1>
                      <h2>一、目标概述</h2>
                      <p>本年度计划旨在搭建更加智能、高效、可扩展的多智能体协作系统，提升任务处理效率和用户体验，实现技术创新与商业价值的双重突破。</p>
                      <h2>二、主要工作计划</h2>
                      <h3>1. 技术研发（Q1-Q2）</h3>
                      <ul>
                        <li>优化多智能体协同算法</li>
                        <li>提升任务分配效率</li>
                        <li>增强模型推理能力</li>
                      </ul>
                      <div style={{
                        marginTop: 16,
                        padding: 12,
                        background: 'rgba(59,130,246,0.05)',
                        borderRadius: 6,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                      }}>
                        <span className="spinner" style={{ color: 'var(--blue)' }} />
                        <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>生成中...</span>
                      </div>
                    </div>
                  )}
                </div>

                <div className="answer-sidebar">
                  <div className="answer-stat">
                    <div className="answer-stat-label">预计剩余时间</div>
                    <div className="answer-stat-value">{isRunning ? '1.2s' : '0s'}</div>
                  </div>
                  <div className="answer-stat">
                    <div className="answer-stat-label">已使用 tokens</div>
                    <div className="answer-stat-value">{completedSteps.includes('judge') ? '1,245' : '0'}</div>
                  </div>
                  <div className="answer-stat">
                    <div className="answer-stat-label">预估费用</div>
                    <div className="answer-stat-value">¥0.067</div>
                  </div>
                  {isRunning && (
                    <div className="stop-generation">⏹ 停止生成</div>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </main>
  );
}
