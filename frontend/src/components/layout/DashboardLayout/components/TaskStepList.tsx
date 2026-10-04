'use client';

import React from 'react';
import { useWorkflowStore } from '@/stores/workflowStore';
import { AGENT_ORDER, AGENT_NAMES } from '@/types';
import type { AgentId } from '@/types';
import { getAgentColorValue } from '../constants';

/**
 * V3.1: 任务拆分列表 — 取代笼统的工作流动画图
 *
 * 设计理念：
 * - 有 plan_steps 时：显示"用户能看懂的逐条任务列表"，每条任务标注 Agent
 * - 无 plan_steps 时：兜底显示 5 Agent 执行进度（简洁列表，非圆圈连线）
 * - 底部：复杂度评分 + 执行模式 + 总耗时（保留原 AgentChain 的 summary）
 */
const TaskStepList: React.FC = () => {
  const {
    taskSteps,
    workflowSteps,
    isRunning,
    currentStep,
    completedSteps,
    complexityScore,
    judgeDecision,
    result,
  } = useWorkflowStore();

  // 判断 Agent 状态
  const getAgentStatus = (agentId: AgentId): 'completed' | 'running' | 'pending' | 'error' => {
    if (completedSteps.includes(agentId)) return 'completed';
    if (isRunning && currentStep === agentId) return 'running';
    const step = workflowSteps.find((s) => s.agent_id === agentId);
    if (step && !step.success) return 'error';
    return 'pending';
  };

  const getAgentDuration = (agentId: string): number => {
    const step = workflowSteps.find((s) => s.agent_id === agentId);
    return step?.duration_seconds || 0;
  };

  // 有任务拆分时：显示逐条任务列表
  const hasTaskSteps = taskSteps.length > 0;

  return (
    <div className="task-step-list">
      <div className="task-list-header">
        <h3>{hasTaskSteps ? '任务拆分执行' : '工作流执行'}</h3>
        <span className="task-list-badge">
          {hasTaskSteps ? `${taskSteps.length} 条任务` : `${AGENT_ORDER.length} Agents`}
        </span>
      </div>

      {/* 任务拆分列表（有 plan_steps 时） */}
      {hasTaskSteps ? (
        <div className="task-items">
          {taskSteps.map((task) => {
            const agentColor = getAgentColorValue(task.agent_id);
            const agentStatus = getAgentStatus(task.agent_id as AgentId);
            const duration = getAgentDuration(task.agent_id);

            return (
              <div key={task.step_id} className="task-item">
                {/* 任务标题行 */}
                <div className="task-item-header">
                  <span className="task-step-num">{task.step_id}</span>
                  <span className="task-title">{task.title}</span>
                  {task.status === 'completed' && (
                    <span className="task-status completed">✓</span>
                  )}
                </div>

                {/* Agent 标注 */}
                <div className="task-agent-tag" style={{ '--agent-color': agentColor } as React.CSSProperties}>
                  <span className="agent-dot" style={{ background: agentColor }} />
                  <span className="agent-label" style={{ color: agentColor }}>
                    {task.agent_name}
                  </span>
                  {duration > 0 && (
                    <span className="agent-duration">{duration.toFixed(2)}s</span>
                  )}
                  {agentStatus === 'running' && (
                    <span className="agent-running-badge">运行中</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* 兜底：无任务拆分时显示简洁 Agent 列表（非圆圈连线动画） */
        <div className="agent-simple-list">
          {AGENT_ORDER.map((agentId) => {
            const status = getAgentStatus(agentId);
            const step = workflowSteps.find((s) => s.agent_id === agentId);
            const agentColor = getAgentColorValue(agentId);
            const duration = step?.duration_seconds || 0;

            return (
              <div key={agentId} className={`agent-simple-item ${status}`}>
                <div className="agent-simple-left">
                  <span className="agent-status-dot" style={{
                    background: status === 'completed' ? 'var(--green)'
                      : status === 'running' ? agentColor
                      : status === 'error' ? 'var(--red)'
                      : 'var(--text-muted)'
                  }} />
                  <span className="agent-simple-name">{AGENT_NAMES[agentId]}</span>
                </div>
                <div className="agent-simple-right">
                  {status === 'running' && <span className="running-badge">运行中</span>}
                  {status === 'completed' && <span className="done-badge">✓</span>}
                  {status === 'error' && <span className="error-badge">✗</span>}
                  {duration > 0 && <span className="duration-tag">{duration.toFixed(2)}s</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 底部摘要：复杂度 + 执行模式 + 总耗时 */}
      {result && (
        <div className="task-summary">
          <div className="summary-row">
            <span className="summary-label">复杂度</span>
            <div className="summary-bar-wrapper">
              <div
                className="summary-bar"
                style={{
                  width: `${(complexityScore * 100).toFixed(0)}%`,
                  background: complexityScore >= 0.65
                    ? 'linear-gradient(90deg, var(--orange), var(--red))'
                    : 'linear-gradient(90deg, var(--green), var(--blue))',
                }}
              />
            </div>
            <span className="summary-value">{complexityScore.toFixed(2)}</span>
          </div>
          <div className="summary-row">
            <span className="summary-label">执行模式</span>
            <span className={`summary-value ${judgeDecision === 'cloud' ? 'cloud' : 'local'}`}>
              {judgeDecision === 'cloud' ? '☁ 云端增强' : '💻 本地执行'}
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

export default TaskStepList;
