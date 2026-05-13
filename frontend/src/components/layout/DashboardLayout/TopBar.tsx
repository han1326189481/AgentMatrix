'use client';

import { Play, Square, Trash2, Sun } from 'lucide-react';
import { useState, useCallback } from 'react';
import { useWorkflowStore } from '@/stores/workflowStore';
import { useAgentStore } from '@/stores/agentStore';
import { workflowService } from '@/services/api/agentService';
import { AGENT_ORDER, AGENT_NAMES } from '@/types';
import type { AgentId, WorkflowOutput } from '@/types';

const COMPLEXITY_THRESHOLD = 0.65;

export default function TopBar() {
  const [inputValue, setInputValue] = useState('');
  const {
    isRunning, currentTask, elapsedSeconds, useMock,
    setCurrentTask, setIsRunning, setCurrentStep,
    setResult, setJudgeDecision, setComplexityScore, addLog, addCompletedStep,
    addWorkflowStep, completedSteps, resetWorkflow,
  } = useWorkflowStore();
  const { updateAgentStatus, resetAllAgents } = useAgentStore();

  const formatTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
    const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
  };

  const executeWithMock = useCallback(async (taskText: string) => {
    setCurrentTask(taskText);
    setIsRunning(true);
    setInputValue('');

    const startTime = new Date().toISOString();

    for (const agentId of AGENT_ORDER) {
      setCurrentStep(agentId);
      updateAgentStatus(agentId, 'processing');
      addLog(agentId, 'info', `${AGENT_NAMES[agentId]} 开始处理...`);

      const stepStart = Date.now();
      await new Promise((resolve) => setTimeout(resolve, 800 + Math.random() * 1200));
      const duration = (Date.now() - stepStart) / 1000;

      addCompletedStep(agentId);
      updateAgentStatus(agentId, 'completed');

      if (agentId === 'writer') {
        setComplexityScore(0.72);
        addLog(agentId, 'success', '难度评估: 0.72 (困难) - 超过阈值 0.65');
      }

      if (agentId === 'review') {
        const isComplex = 0.72 >= COMPLEXITY_THRESHOLD;
        setJudgeDecision(isComplex ? 'cloud' : 'local');
        addLog(agentId, isComplex ? 'warning' : 'success',
          `决策: ${isComplex ? '调用API网关 - 难度评分0.72 > 阈值0.65' : '本地处理 - 难度评分0.38 < 阈值0.65'}`
        );
      }

      addLog(agentId, 'success', `${AGENT_NAMES[agentId]} 处理完成 (${duration.toFixed(1)}s)`);
    }

    const mockResult: WorkflowOutput = {
      final_result: `# 智能体协作年度计划（2024）\n\n## 一、目标概述\n\n本年度计划旨在搭建更加智能、高效、可扩展的多智能体协作系统，提升任务处理效率和用户体验，实现技术创新与商业价值的双重突破。\n\n## 二、主要工作计划\n\n### 1. 技术研发（Q1-Q2）\n\n- 优化多智能体协同算法\n- 提升任务分配效率\n- 增强模型推理能力\n\n### 2. 产品迭代（Q2-Q3）\n\n- 用户界面优化升级\n- 新增知识库管理功能\n- 支持自定义Agent配置\n\n### 3. 生态建设（Q3-Q4）\n\n- 开放API接口\n- 建设开发者社区\n- 推动行业应用落地\n\n## 三、预算规划\n\n| 项目 | Q1 | Q2 | Q3 | Q4 | 合计 |\n|------|-----|-----|-----|-----|------|\n| 研发投入 | 50万 | 45万 | 35万 | 30万 | 160万 |\n| 云服务 | 10万 | 12万 | 15万 | 15万 | 52万 |\n| 人力成本 | 80万 | 80万 | 80万 | 80万 | 320万 |`,
      steps: [],
      executed_locally: false,
      total_duration_seconds: 12.6,
      start_time: startTime,
      end_time: new Date().toISOString(),
      complexity_score: 0.72,
    };

    setResult(mockResult);
    addLog('result', 'success', '所有步骤已完成，最终结果已生成');
    setIsRunning(false);
    setCurrentStep(null);
  }, [setCurrentTask, setIsRunning, setCurrentStep, setResult, setJudgeDecision, setComplexityScore, addLog, addCompletedStep, addWorkflowStep, updateAgentStatus]);

  const executeWithAPI = useCallback(async (taskText: string) => {
    setCurrentTask(taskText);
    setIsRunning(true);
    setInputValue('');

    try {
      const result = await workflowService.execute({
        user_input: taskText,
        context: {},
      });

      for (const step of result.steps) {
        const agentId = AGENT_ORDER.find(
          (id) => step.agent_id === id || step.agent_name.includes(AGENT_NAMES[id])
        ) as AgentId | undefined;
        if (agentId) {
          addCompletedStep(agentId);
          addWorkflowStep(step);
          updateAgentStatus(agentId, step.success ? 'completed' : 'error');
          addLog(agentId, step.success ? 'success' : 'error',
            `${step.agent_name}: ${step.success ? '完成' : '失败'} (${step.duration_seconds.toFixed(1)}s)`
          );
        }
      }

      if (result.complexity_score !== undefined) {
        setComplexityScore(result.complexity_score);
        setJudgeDecision(result.complexity_score >= COMPLEXITY_THRESHOLD ? 'cloud' : 'local');
      }

      setResult(result);
      addLog('result', 'success', '工作流执行完成');
    } catch (error) {
      console.error('[Workflow API Error]', error);
      addLog(undefined, 'error', '后端API调用失败，切换到本地模拟模式');
      setIsRunning(false);
      setCurrentStep(null);
      await executeWithMock(taskText);
      return;
    } finally {
      setIsRunning(false);
      setCurrentStep(null);
    }
  }, [setCurrentTask, setIsRunning, setCurrentStep, setResult, setJudgeDecision, setComplexityScore, addLog, addCompletedStep, addWorkflowStep, updateAgentStatus, executeWithMock]);

  const handleSubmit = async () => {
    const taskText = inputValue.trim() || currentTask;
    if (!taskText || isRunning) return;

    if (useMock) {
      await executeWithMock(taskText);
    } else {
      await executeWithAPI(taskText);
    }
  };

  const handleStop = () => {
    setIsRunning(false);
    setCurrentStep(null);
  };

  const handleClear = () => {
    resetWorkflow();
    resetAllAgents();
    setInputValue('');
  };

  return (
    <header className="header">
      <div className="header-left">
        <div className="logo">
          <div className="logo-hexagon">N</div>
          <span className="logo-text">NeuroFlow</span>
          <span className="logo-subtitle">多智能体协同平台</span>
        </div>

        <div className="task-bar">
          <span className="task-label">任务：</span>
          {currentTask && !isRunning && completedSteps.length > 0 ? (
            <span className="task-text">{currentTask}</span>
          ) : (
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder="输入您的任务需求... 例如：帮我写一份关于智能体协作的年度计划"
              className="task-input"
            />
          )}
        </div>

        {isRunning && (
          <div className="task-status">
            <div className="status-dot" />
            <span className="status-text">运行中</span>
            <span className="timer">{formatTime(elapsedSeconds)}</span>
          </div>
        )}

        {!isRunning && currentTask && completedSteps.length > 0 && (
          <div className="task-status">
            <div style={{
              width: 8,
              height: 8,
              background: 'var(--green)',
              borderRadius: '50%',
            }} />
            <span style={{ color: 'var(--green)', fontSize: 13, fontWeight: 500 }}>已完成</span>
          </div>
        )}
      </div>

      <div className="header-right">
        <button className="btn btn-primary" onClick={handleSubmit} disabled={(!inputValue.trim() && !currentTask) || isRunning}>
          <Play size={14} />
          运行任务
        </button>
        <button className="btn btn-secondary" onClick={handleStop} disabled={!isRunning}>
          <Square size={14} />
          停止
        </button>
        <button className="btn btn-secondary" onClick={handleClear}>
          <Trash2 size={14} />
          清空
        </button>
        <button className="btn-icon">
          <Sun size={16} />
        </button>
      </div>
    </header>
  );
}
