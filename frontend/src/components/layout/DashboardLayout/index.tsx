'use client';

import { useState, useCallback } from 'react';
import { useWorkflowStore } from '@/stores/workflowStore';
import { useAgentStore } from '@/stores/agentStore';
import { workflowService } from '@/services/api/agentService';
import { AGENT_ORDER, AGENT_NAMES, AGENT_MODELS, AGENT_EMOJIS, AGENT_DESCRIPTIONS, AGENT_ICON_CLASSES } from '@/types';
import type { AgentId, WorkflowOutput } from '@/types';

const COMPLEXITY_THRESHOLD = 0.65;

const AGENT_DISPLAY_NAMES: Record<AgentId, string> = {
  knowledge: 'A 摘要 Agent',
  summary: 'B 撰写 Agent',
  writer: 'C 评审 Agent',
  review: '评委 Agent',
  judge: 'API 网关',
  result: '导出 Agent',
};

const AGENT_DISPLAY_COLORS: Record<AgentId, string> = {
  knowledge: 'green',
  summary: 'green',
  writer: 'gold',
  review: 'purple',
  judge: 'blue',
  result: 'green',
};

const AGENT_TIMELINE_COLORS: Record<AgentId, string> = {
  knowledge: 'blue',
  summary: 'blue',
  writer: 'gold',
  review: 'purple',
  judge: 'blue',
  result: 'green',
};

const AGENT_SVG_ICONS: Record<AgentId, React.ReactNode> = {
  knowledge: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  ),
  summary: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  ),
  writer: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5C7 4 7 7 7 7" />
      <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5C17 4 17 7 17 7" />
      <path d="M4 22h16" />
      <path d="M10 22V8h4v14" />
      <path d="M6 8V2" />
      <path d="M18 8V2" />
    </svg>
  ),
  review: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 3L20 7.5V16.5L12 21L4 16.5V7.5L12 3Z" />
      <path d="M12 12L20 7.5" />
      <path d="M12 12V21" />
      <path d="M12 12L4 7.5" />
    </svg>
  ),
  judge: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
    </svg>
  ),
  result: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  ),
};

function ProgressRing({ percentage, color }: { percentage: number; color: string }) {
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="progress-ring">
      <svg width="48" height="48" viewBox="0 0 48 48">
        <circle className="progress-ring-bg" cx="24" cy="24" r={radius} />
        <circle
          className="progress-ring-fill"
          cx="24"
          cy="24"
          r={radius}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="progress-ring-text" style={{ color }}>{percentage}%</span>
    </div>
  );
}

export default function DashboardLayout() {
  const [inputValue, setInputValue] = useState('');
  const [activeTab, setActiveTab] = useState<'output' | 'decision' | 'api'>('output');
  const [threshold, setThreshold] = useState(0.65);

  const {
    isRunning, currentTask, currentStep, elapsedSeconds, useMock,
    completedSteps, result, judgeDecision, complexityScore,
    setCurrentTask, setIsRunning, setCurrentStep,
    setResult, setJudgeDecision, setComplexityScore, addLog, addCompletedStep,
    addWorkflowStep, resetWorkflow,
  } = useWorkflowStore();
  const { agents, updateAgentStatus, resetAllAgents } = useAgentStore();

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
      const apiResult = await workflowService.execute({
        user_input: taskText,
        context: {},
      });

      for (const step of apiResult.steps) {
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

      if (apiResult.complexity_score !== undefined) {
        setComplexityScore(apiResult.complexity_score);
        setJudgeDecision(apiResult.complexity_score >= COMPLEXITY_THRESHOLD ? 'cloud' : 'local');
      }

      setResult(apiResult);
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

  const getNodeStatus = (agentId: AgentId) => {
    if (completedSteps.includes(agentId)) return 'completed';
    if (currentStep === agentId) return 'working';
    return 'pending';
  };

  const apiCallCount = completedSteps.includes('judge') ? 1 : 0;
  const apiCallTotal = 1;
  const apiCallPercent = apiCallTotal > 0 ? Math.round((apiCallCount / apiCallTotal) * 100) : 0;

  const costSaved = completedSteps.length > 0 ? (completedSteps.length * 0.02).toFixed(3) : '0.000';
  const costSavedPercent = completedSteps.length > 0 ? Math.min(62, completedSteps.length * 10) : 0;

  const progressPercent = completedSteps.length > 0 ? Math.round((completedSteps.length / 6) * 100) : 0;

  const now = new Date();
  const getTimeStr = (offset: number) => {
    const d = new Date(now.getTime() - offset * 1000);
    return d.toLocaleTimeString('zh-CN', { hour12: false });
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

  return (
    <>
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <div className="logo-hexagon"></div>
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
              <div className="status-dot"></div>
              <span className="status-text">运行中</span>
              <span className="timer">{formatTime(elapsedSeconds)}</span>
            </div>
          )}
          {!isRunning && currentTask && completedSteps.length > 0 && (
            <div className="task-status">
              <div style={{ width: 8, height: 8, background: 'var(--green)', borderRadius: '50%' }}></div>
              <span style={{ color: 'var(--green)', fontSize: 13, fontWeight: 500 }}>已完成</span>
            </div>
          )}
        </div>
        <div className="header-right">
          <button className="btn btn-primary" onClick={handleSubmit} disabled={(!inputValue.trim() && !currentTask) || isRunning}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            运行任务
          </button>
          <button className="btn btn-secondary" onClick={handleStop} disabled={!isRunning}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="6" y="4" width="4" height="16" />
              <rect x="14" y="4" width="4" height="16" />
            </svg>
            停止
          </button>
          <button className="btn btn-secondary" onClick={handleClear}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            清空
          </button>
          <button className="btn-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="main-container">
        {/* Left Sidebar */}
        <aside className="sidebar-left">
          {/* API Calls */}
          <div className="card animate-in delay-1">
            <div className="card-title">API调用次数</div>
            <div className="card-value">{apiCallCount} / {apiCallTotal}次</div>
            <div className="progress-ring-container">
              <ProgressRing percentage={apiCallPercent} color="var(--blue)" />
              <div style={{ flex: 1 }}>
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{ width: `${apiCallPercent}%`, background: 'var(--blue)' }}></div>
                </div>
              </div>
            </div>
            <div className="card-info" style={{ marginTop: 8 }}>
              <span>纯API模式基准：1次</span>
            </div>
          </div>

          {/* Cost Savings */}
          <div className="card animate-in delay-2">
            <div className="card-title">预估节省成本</div>
            <div className="card-value green">¥{costSaved}</div>
            <div className="progress-ring-container">
              <ProgressRing percentage={costSavedPercent} color="var(--green)" />
              <div style={{ flex: 1 }}>
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{ width: `${costSavedPercent}%`, background: 'var(--green)' }}></div>
                </div>
              </div>
            </div>
            <div className="card-info" style={{ marginTop: 8 }}>
              <span>纯API成本：¥0.18</span>
              <span className="highlight green">节省{costSavedPercent}%</span>
            </div>
          </div>

          {/* Local Compute Load */}
          <div className="card animate-in delay-3">
            <div className="card-title">本地算力负载</div>
            <div className="stats-row">
              <div className="stat-item">
                <div className="stat-label">CPU</div>
                <div className="stat-value">34%</div>
              </div>
              <div className="stat-item">
                <div className="stat-label">显存</div>
                <div className="stat-value">1.2GB</div>
              </div>
            </div>
            <div className="progress-ring-container">
              <ProgressRing percentage={34} color="var(--green)" />
              <div style={{ flex: 1 }}>
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{ width: '34%', background: 'var(--green)' }}></div>
                </div>
              </div>
            </div>
          </div>

          {/* Response Time */}
          <div className="card animate-in delay-4">
            <div className="card-title">响应时间</div>
            <div className="card-value">2.3s</div>
            <div className="progress-ring-container">
              <ProgressRing percentage={56} color="var(--blue)" />
              <div style={{ flex: 1 }}>
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{ width: '56%', background: 'var(--blue)' }}></div>
                </div>
              </div>
            </div>
            <div className="card-info" style={{ marginTop: 8 }}>
              <span>纯API模式：4.1s</span>
              <span className="highlight">更快</span>
            </div>
          </div>

          {/* Agent Fleet */}
          <div className="card animate-in delay-5">
            <div className="agent-fleet-header">
              <span className="agent-fleet-title">Agent舰队</span>
              <span className="agent-fleet-status">全部启用</span>
            </div>

            {AGENT_ORDER.map((agentId) => {
              const agent = agents[agentId];
              const iconClass = AGENT_ICON_CLASSES[agentId];
              const isActive = agent.status === 'processing';
              const isCompleted = agent.status === 'completed';

              return (
                <div key={agentId} className="agent-item">
                  <div className={`agent-icon ${iconClass}`}>
                    {AGENT_SVG_ICONS[agentId]}
                  </div>
                  <div className="agent-info">
                    <div className="agent-name">{AGENT_DISPLAY_NAMES[agentId]}</div>
                    <div className="agent-model">{AGENT_MODELS[agentId]}</div>
                    <div className="agent-desc">{AGENT_DESCRIPTIONS[agentId]}</div>
                  </div>
                  <div className="agent-status">
                    {isCompleted && <span className="status-badge completed">已完成</span>}
                    {isActive && <span className="status-badge working"><span className="spinner"></span> 工作中</span>}
                    {!isActive && !isCompleted && <span className="status-badge idle">空闲</span>}
                    <div className="toggle-switch"></div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Resource Monitor */}
          <div className="card animate-in delay-5">
            <div className="card-title">资源监控</div>
            <div className="resource-item">
              <div className="resource-header">
                <span className="resource-label">CPU使用率</span>
                <span className="resource-value" style={{ color: 'var(--blue)' }}>34%</span>
              </div>
              <div className="resource-chart">
                <svg width="100%" height="32" viewBox="0 0 240 32" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="rgba(59,130,246,0.3)" />
                      <stop offset="100%" stopColor="rgba(59,130,246,0)" />
                    </linearGradient>
                  </defs>
                  <path d="M0,20 Q20,18 40,22 T80,16 T120,20 T160,14 T200,18 T240,22 V32 H0 Z" fill="url(#cpuGrad)" />
                  <path d="M0,20 Q20,18 40,22 T80,16 T120,20 T160,14 T200,18 T240,22" fill="none" stroke="var(--blue)" strokeWidth="1.5" />
                </svg>
              </div>
            </div>
            <div className="resource-item">
              <div className="resource-header">
                <span className="resource-label">内存占用</span>
                <span className="resource-value" style={{ color: 'var(--blue)' }}>4.2GB / 16GB</span>
              </div>
              <div className="resource-chart">
                <svg width="100%" height="32" viewBox="0 0 240 32" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="memGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="rgba(16,185,129,0.3)" />
                      <stop offset="100%" stopColor="rgba(16,185,129,0)" />
                    </linearGradient>
                  </defs>
                  <path d="M0,16 Q30,14 60,18 T120,12 T180,16 T240,14 V32 H0 Z" fill="url(#memGrad)" />
                  <path d="M0,16 Q30,14 60,18 T120,12 T180,16 T240,14" fill="none" stroke="var(--green)" strokeWidth="1.5" />
                </svg>
              </div>
            </div>
            <div className="resource-item">
              <div className="resource-header">
                <span className="resource-label">显存占用</span>
                <span className="resource-value" style={{ color: 'var(--blue)' }}>1.2GB / 8GB</span>
              </div>
              <div className="resource-chart">
                <svg width="100%" height="32" viewBox="0 0 240 32" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="gpuGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="rgba(139,92,246,0.3)" />
                      <stop offset="100%" stopColor="rgba(139,92,246,0)" />
                    </linearGradient>
                  </defs>
                  <path d="M0,24 Q40,20 80,24 T160,18 T240,22 V32 H0 Z" fill="url(#gpuGrad)" />
                  <path d="M0,24 Q40,20 80,24 T160,18 T240,22" fill="none" stroke="var(--purple)" strokeWidth="1.5" />
                </svg>
              </div>
            </div>
          </div>

          {/* System Settings */}
          <div className="card animate-in delay-5">
            <div className="card-title">系统设置</div>
            <div className="setting-item">
              <div className="setting-label">本地模型路径</div>
              <select className="setting-input">
                <option>/models</option>
              </select>
            </div>
            <div className="setting-item">
              <div className="setting-label">API Key</div>
              <input type="password" className="setting-input" defaultValue="sk-******-******-******-demo" readOnly />
            </div>
            <div className="setting-item">
              <div className="setting-label">难度阈值 (置信度)</div>
              <div className="slider-container">
                <input
                  type="range"
                  className="slider"
                  min={30}
                  max={90}
                  value={Math.round(threshold * 100)}
                  onChange={(e) => setThreshold(Number(e.target.value) / 100)}
                />
                <div className="slider-labels">
                  <span className="slider-label">0.3</span>
                  <span className="slider-label">0.9</span>
                </div>
                <div className="slider-value">{threshold.toFixed(2)}</div>
              </div>
            </div>
          </div>
        </aside>

        {/* Center Content */}
        <main className="content-center">
          {/* Pipeline Section */}
          <div className="pipeline-section">
            <div className="section-header">
              <span className="section-title">多智能体协同流水线</span>
              <div className="legend">
                <div className="legend-item">
                  <div className="legend-line solid"></div>
                  <span>数据流</span>
                </div>
                <div className="legend-item">
                  <div className="legend-line dashed"></div>
                  <span>控制流</span>
                </div>
              </div>
            </div>

            <div className="pipeline-container">
              {/* User Input */}
              <div className="pipeline-node blue animate-in delay-1" style={{ minWidth: 240 }}>
                <div className="node-icon">👤</div>
                <div className="node-title">用户输入</div>
                <div className="node-subtitle" style={{ maxWidth: 200, margin: '0 auto' }}>
                  {currentTask || '等待输入任务...'}
                </div>
              </div>

              <div className="arrow-down"></div>

              {/* Parallel Agents */}
              <div className="pipeline-row animate-in delay-2">
                {(['knowledge', 'summary', 'writer'] as AgentId[]).map((agentId) => {
                  const status = getNodeStatus(agentId);
                  return (
                    <div key={agentId} className={`pipeline-node ${AGENT_DISPLAY_COLORS[agentId]}`} style={{ position: 'relative' }}>
                      <div className="node-icon">{AGENT_EMOJIS[agentId]}</div>
                      <div className="node-title">{AGENT_DISPLAY_NAMES[agentId]}</div>
                      <div className="node-subtitle">{AGENT_MODELS[agentId]}</div>
                      <div className={`node-status ${status}`}>
                        {status === 'working' ? (
                          <><span className="spinner"></span> 处理中...</>
                        ) : status === 'completed' ? (
                          '✓ 已完成'
                        ) : (
                          '等待中'
                        )}
                      </div>
                      {agentId === 'writer' && (completedSteps.includes('writer') || currentStep === 'writer') && (
                        <div className="difficulty-box">
                          <div className="difficulty-score">{complexityScore?.toFixed(2) ?? '0.72'}</div>
                          <div className="difficulty-threshold">难度评分</div>
                          <div className="difficulty-threshold">阈值: {threshold.toFixed(2)}</div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="arrow-down"></div>

              {/* Judge Agent */}
              <div className="pipeline-node purple animate-in delay-3" style={{ minWidth: 180 }}>
                <div className="node-icon">⚖️</div>
                <div className="node-title">评委 Agent</div>
                <div className="node-subtitle">{AGENT_MODELS.review}</div>
                <div className={`node-status ${getNodeStatus('review')}`}>
                  {getNodeStatus('review') === 'working' ? (
                    <><span className="spinner"></span> 工作中...</>
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
                  <div className="arrow-down" style={{ height: 20 }}></div>
                </div>
                <div className="branch-arrow">
                  <span className="branch-label orange">困难任务 (&gt; 阈值)</span>
                  <div className="arrow-down" style={{ height: 20 }}></div>
                </div>
              </div>

              {/* Branch Nodes */}
              <div className="pipeline-row animate-in delay-4">
                <div className={`pipeline-node ${judgeDecision === 'local' ? 'green' : ''}`}>
                  <div className="node-icon">🏆</div>
                  <div className="node-title">内部PK胜出</div>
                  <div className="node-subtitle">本地模型输出更优</div>
                </div>
                <div className={`pipeline-node ${judgeDecision === 'cloud' ? 'orange' : ''}`}>
                  <div className="node-icon">☁️</div>
                  <div className="node-title">API网关</div>
                  <div className="node-subtitle">{AGENT_MODELS.judge}</div>
                  <div className={`node-status ${getNodeStatus('judge') === 'completed' ? 'completed' : 'loading'}`}>
                    {getNodeStatus('judge') === 'completed' ? (
                      '✓ 已完成'
                    ) : currentStep === 'judge' ? (
                      <><span className="spinner"></span> 调用中... 245 tokens</>
                    ) : (
                      '等待中'
                    )}
                  </div>
                </div>
              </div>

              <div className="arrow-down"></div>

              {/* Final Output */}
              <div className="pipeline-node blue animate-in delay-5" style={{ minWidth: 200 }}>
                <div className="node-icon">📋</div>
                <div className="node-title">最终答案输出</div>
                <div className="node-subtitle">生成最终完整回答</div>
                <div className={`node-status ${getNodeStatus('result')}`}>
                  {getNodeStatus('result') === 'completed' ? (
                    '✓ 已完成'
                  ) : currentStep === 'result' ? (
                    <><span className="spinner"></span> 生成中...</>
                  ) : (
                    '等待中'
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Final Answer Section */}
          {result && (
            <div className="final-answer-section animate-in delay-5">
              <div className="answer-header">
                <div className="answer-title">
                  最终答案
                  <span className="answer-progress-badge">已完成 {progressPercent}%</span>
                </div>
              </div>

              <div className="answer-container">
                <div
                  className="answer-content"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(result.final_result) }}
                />
                <div className="answer-sidebar">
                  <div className="answer-stat">
                    <div className="answer-stat-label">预计剩余时间</div>
                    <div className="answer-stat-value">{isRunning ? '1.2s' : '0s'}</div>
                  </div>
                  <div className="answer-stat">
                    <div className="answer-stat-label">已使用 tokens</div>
                    <div className="answer-stat-value">1,245</div>
                  </div>
                  <div className="answer-stat">
                    <div className="answer-stat-label">预估费用</div>
                    <div className="answer-stat-value">¥0.067</div>
                  </div>
                  {isRunning && (
                    <div className="stop-generation" onClick={handleStop}>⏹ 停止生成</div>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>

        {/* Right Sidebar */}
        <aside className="sidebar-right">
          <div className="tabs">
            <div className={`tab${activeTab === 'output' ? ' active' : ''}`} onClick={() => setActiveTab('output')}>Agent输出</div>
            <div className={`tab${activeTab === 'decision' ? ' active' : ''}`} onClick={() => setActiveTab('decision')}>评审与决策</div>
            <div className={`tab${activeTab === 'api' ? ' active' : ''}`} onClick={() => setActiveTab('api')}>API调用明细</div>
          </div>

          <div className="tab-content">
            {activeTab === 'output' && (
              <>
                {completedSteps.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)', fontSize: 13 }}>
                    等待任务执行...
                  </div>
                )}
                {completedSteps.map((agentId, index) => (
                  <div key={agentId} className="timeline-item animate-in" style={{ animationDelay: `${index * 0.1}s` }}>
                    <div className="timeline-time">{getTimeStr((completedSteps.length - index) * 3)}</div>
                    <div className={`timeline-icon ${AGENT_TIMELINE_COLORS[agentId]}`}>
                      {AGENT_EMOJIS[agentId]}
                    </div>
                    <div className="timeline-body">
                      <div className="timeline-header">
                        <span className="timeline-title">{AGENT_DISPLAY_NAMES[agentId]}</span>
                        <span className="timeline-link">查看详情</span>
                      </div>
                      {agentId === 'writer' ? (
                        <>
                          <div className="timeline-label">
                            难度评估：<span style={{ color: 'var(--orange)', fontWeight: 600 }}>困难</span>{' '}
                            置信度：<span style={{ color: 'var(--orange)', fontWeight: 600 }}>{complexityScore?.toFixed(2) ?? '0.72'}</span>
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
                          <div className="timeline-content">{currentTask}</div>
                          <div className="timeline-label" style={{ marginTop: 6 }}>输出摘要：</div>
                          <div className="timeline-content">
                            {agentId === 'knowledge' ? '年度计划关键词：智能体协作、技术研究、产品开发、市场推广、团队建设...' :
                             agentId === 'summary' ? '构建高效的多智能体协同生态，提升任务处理效率...' :
                             '最终结果已整合生成'}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                ))}
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
                      <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--orange)' }}>{complexityScore?.toFixed(2) ?? '0.72'}</span>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>阈值：{threshold.toFixed(2)}</span>
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
                        }}>调用API网关增强</span>
                      </div>
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
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)', fontSize: 13 }}>
                    暂无API调用记录
                  </div>
                )}
              </>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}
