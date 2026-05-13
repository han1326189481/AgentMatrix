'use client';

import { useState } from 'react';
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

const AGENT_COLORS: Record<AgentId, string> = {
  knowledge: 'blue',
  summary: 'blue',
  writer: 'gold',
  review: 'purple',
  judge: 'blue',
  result: 'green',
};

const AGENT_DISPLAY_NAMES: Record<AgentId, string> = {
  knowledge: 'A 摘要 Agent',
  summary: 'B 撰写 Agent',
  writer: 'C 评审 Agent',
  review: '评委 Agent',
  judge: 'API 网关',
  result: '导出 Agent',
};

const MOCK_OUTPUTS: Record<string, { input: string; output: string }> = {
  knowledge: {
    input: '帮我写一份关于智能体协作的年度计划，包含预算和时间线',
    output: '年度计划关键词：智能体协作、技术研究、产品开发、市场推广、团队建设...',
  },
  summary: {
    input: '关键信息：智能体协作年度计划，含预算和时间线',
    output: '# 智能体协作年度计划（2024）\n## 一、目标概述\n构建高效的多智能体协同生态，提升任务处理效率...',
  },
  writer: {
    input: '需求摘要：智能体协作系统年度计划',
    output: '难度评估：困难 置信度：0.72',
  },
  review: {
    input: '复杂度评分 0.72，超过阈值',
    output: '决策：调用API网关',
  },
  judge: {
    input: '决策：切换云端增强模式',
    output: '状态：调用中... 预计剩余 2.1s',
  },
  result: {
    input: '所有Agent输出汇总',
    output: '最终结果已整合生成',
  },
};

export default function RightPanel() {
  const [activeTab, setActiveTab] = useState<'output' | 'decision' | 'api'>('output');
  const { completedSteps, judgeDecision } = useWorkflowStore();

  const tabs = [
    { key: 'output' as const, label: 'Agent输出' },
    { key: 'decision' as const, label: '评审与决策' },
    { key: 'api' as const, label: 'API调用明细' },
  ];

  const now = new Date();
  const getTimeStr = (offset: number) => {
    const d = new Date(now.getTime() - offset * 1000);
    return d.toLocaleTimeString('zh-CN', { hour12: false });
  };

  return (
    <aside className="sidebar-right">
      <div className="tabs">
        {tabs.map((tab) => (
          <div
            key={tab.key}
            className={`tab${activeTab === tab.key ? ' active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </div>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === 'output' && (
          <>
            {completedSteps.length === 0 && (
              <div style={{
                textAlign: 'center',
                padding: '60px 20px',
                color: 'var(--text-muted)',
                fontSize: 13,
              }}>
                等待任务执行...
              </div>
            )}
            {completedSteps.map((agentId, index) => {
              const mockData = MOCK_OUTPUTS[agentId];
              if (!mockData) return null;

              return (
                <div
                  key={agentId}
                  className="timeline-item animate-in"
                  style={{ animationDelay: `${index * 0.1}s` }}
                >
                  <div className="timeline-time">{getTimeStr((completedSteps.length - index) * 3)}</div>
                  <div className={`timeline-icon ${AGENT_COLORS[agentId as AgentId]}`}>
                    {AGENT_EMOJIS[agentId as AgentId]}
                  </div>
                  <div className="timeline-body">
                    <div className="timeline-header">
                      <span className="timeline-title">{AGENT_DISPLAY_NAMES[agentId as AgentId]}</span>
                      <span className="timeline-link">查看详情</span>
                    </div>
                    {agentId === 'writer' ? (
                      <>
                        <div className="timeline-label">
                          难度评估：<span style={{ color: 'var(--orange)', fontWeight: 600 }}>困难</span>{' '}
                          置信度：<span style={{ color: 'var(--orange)', fontWeight: 600 }}>0.72</span>
                        </div>
                        <div className="timeline-label" style={{ marginTop: 6 }}>评估理由：</div>
                        <ul className="timeline-list">
                          <li>需要多维度规划和逻辑整合</li>
                          <li>包含预算估算和时间线安排</li>
                          <li>需要专业知识和经验支持</li>
                        </ul>
                      </>
                    ) : agentId === 'review' ? (
                      <>
                        <div className="timeline-label">
                          决策：<span style={{ color: 'var(--blue)', fontWeight: 600 }}>调用API网关</span>
                        </div>
                        <div className="timeline-label" style={{ marginTop: 6 }}>理由：</div>
                        <ul className="timeline-list">
                          <li>难度评分0.72 &gt; 阈值0.65</li>
                          <li>本地模型置信度不足</li>
                          <li>需要更高质量的专业内容</li>
                        </ul>
                      </>
                    ) : agentId === 'judge' ? (
                      <>
                        <div className="timeline-label">
                          状态：<span style={{ color: 'var(--orange)', fontWeight: 600 }}>调用中... 预计剩余 2.1s</span>
                        </div>
                        <div className="timeline-label" style={{ marginTop: 6 }}>模型：DeepSeek-V4 大模型</div>
                        <div className="timeline-label">
                          已使用 tokens：<span style={{ color: 'var(--text-primary)' }}>245</span>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="timeline-label">输入：</div>
                        <div className="timeline-content">{mockData.input}</div>
                        <div className="timeline-label" style={{ marginTop: 6 }}>输出摘要：</div>
                        <div className="timeline-content">{mockData.output}</div>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </>
        )}

        {activeTab === 'decision' && (
          <>
            <div className="timeline-item animate-in">
              <div className="timeline-icon gold">🏆</div>
              <div className="timeline-body">
                <div className="timeline-header">
                  <span className="timeline-title">复杂度评估</span>
                  <span className="timeline-link">详情</span>
                </div>
                <div className="timeline-label">执行Agent：C 评审 Agent</div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  margin: '8px 0',
                  padding: '8px 12px',
                  background: 'rgba(245, 158, 11, 0.15)',
                  borderRadius: 8,
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                }}>
                  <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>复杂度评分：</span>
                  <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--orange)' }}>0.72</span>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>阈值：0.65</span>
                </div>
                <div className="timeline-label">决策结果：</div>
                <div className="timeline-content" style={{
                  color: 'var(--orange)',
                  fontWeight: 600,
                  padding: '6px 10px',
                  background: 'rgba(245, 158, 11, 0.1)',
                  borderRadius: 6,
                  display: 'inline-block',
                }}>
                  ⚠️ 困难任务 - 切换云端模式
                </div>
              </div>
            </div>

            <div className="timeline-item animate-in" style={{ animationDelay: '0.1s' }}>
              <div className="timeline-icon purple">⚖️</div>
              <div className="timeline-body">
                <div className="timeline-header">
                  <span className="timeline-title">路径选择</span>
                  <span className="timeline-link">详情</span>
                </div>
                <div className="timeline-label">执行Agent：评委 Agent</div>
                <div style={{ margin: '8px 0', display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '8px 12px',
                    borderRadius: 8,
                    background: judgeDecision === 'local' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                    border: `1px solid ${judgeDecision === 'local' ? 'rgba(16, 185, 129, 0.3)' : 'var(--border-color)'}`,
                  }}>
                    <div style={{
                      width: 20,
                      height: 20,
                      borderRadius: '50%',
                      background: judgeDecision === 'local' ? 'var(--green)' : 'var(--text-muted)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      {judgeDecision === 'local' && <span style={{ color: 'white', fontSize: 12 }}>✓</span>}
                    </div>
                    <span style={{
                      fontSize: 12,
                      color: judgeDecision === 'local' ? 'var(--green)' : 'var(--text-secondary)',
                      fontWeight: judgeDecision === 'local' ? 600 : 400,
                    }}>本地模型直接输出</span>
                  </div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '8px 12px',
                    borderRadius: 8,
                    background: judgeDecision === 'cloud' ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                    border: `1px solid ${judgeDecision === 'cloud' ? 'rgba(59, 130, 246, 0.3)' : 'var(--border-color)'}`,
                  }}>
                    <div style={{
                      width: 20,
                      height: 20,
                      borderRadius: '50%',
                      background: judgeDecision === 'cloud' ? 'var(--blue)' : 'var(--text-muted)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      {judgeDecision === 'cloud' && <span style={{ color: 'white', fontSize: 12 }}>✓</span>}
                    </div>
                    <span style={{
                      fontSize: 12,
                      color: judgeDecision === 'cloud' ? 'var(--blue)' : 'var(--text-secondary)',
                      fontWeight: judgeDecision === 'cloud' ? 600 : 400,
                    }}>云端增强模式</span>
                  </div>
                </div>
                <div className="timeline-label">选择结果：</div>
                <div className="timeline-content" style={{
                  color: judgeDecision === 'cloud' ? 'var(--blue)' : 'var(--green)',
                  fontWeight: 600,
                  padding: '6px 10px',
                  background: judgeDecision === 'cloud' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                  borderRadius: 6,
                  display: 'inline-block',
                }}>
                  ✓ {judgeDecision === 'cloud' ? '云端增强模式' : '本地模型直接输出'}
                </div>
              </div>
            </div>
          </>
        )}

        {activeTab === 'api' && (
          <>
            {completedSteps.includes('judge') ? (
              <div className="timeline-item animate-in">
                <div className="timeline-icon blue">☁️</div>
                <div className="timeline-body">
                  <div className="timeline-header">
                    <span className="timeline-title">API调用 #1</span>
                    <span className="timeline-time">{getTimeStr(30)}</span>
                  </div>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: 10,
                    marginTop: 10,
                  }}>
                    <div style={{
                      background: 'var(--bg-primary)',
                      padding: 10,
                      borderRadius: 8,
                      border: '1px solid var(--border-color)',
                    }}>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>模型</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>DeepSeek-V4</div>
                    </div>
                    <div style={{
                      background: 'var(--bg-primary)',
                      padding: 10,
                      borderRadius: 8,
                      border: '1px solid var(--border-color)',
                    }}>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>Token消耗</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--purple)' }}>1,247</div>
                    </div>
                    <div style={{
                      background: 'var(--bg-primary)',
                      padding: 10,
                      borderRadius: 8,
                      border: '1px solid var(--border-color)',
                    }}>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>费用</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--orange)' }}>¥0.067</div>
                    </div>
                    <div style={{
                      background: 'var(--bg-primary)',
                      padding: 10,
                      borderRadius: 8,
                      border: '1px solid var(--border-color)',
                    }}>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>延迟</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--green)' }}>4.4s</div>
                    </div>
                  </div>
                  <div className="timeline-label" style={{ marginTop: 10 }}>用途</div>
                  <div className="timeline-content">年度计划内容生成</div>
                </div>
              </div>
            ) : (
              <div style={{
                textAlign: 'center',
                padding: '60px 20px',
                color: 'var(--text-muted)',
                fontSize: 13,
              }}>
                暂无API调用记录
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
