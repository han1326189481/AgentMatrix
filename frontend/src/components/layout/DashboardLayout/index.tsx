'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useWorkflowStore } from '@/stores/workflowStore';
import { useAgentStore } from '@/stores/agentStore';
import { workflowService, chatService } from '@/services/api/agentService';
import { AGENT_ORDER, AGENT_NAMES, AGENT_MODELS, AGENT_EMOJIS, AGENT_DESCRIPTIONS, AGENT_ICON_CLASSES } from '@/types';
import type { AgentId, WorkflowOutput, LogEntry } from '@/types';

const COMPLEXITY_THRESHOLD = 0.65;

const AGENT_DISPLAY_NAMES: Record<AgentId, string> = {
  knowledge: 'Knowledge Agent',
  summary: 'A摘要Agent',
  writer: 'B撰写Agent',
  review: 'Review Agent',
  judge: 'Judge Agent',
  result: 'Result Agent',
};

const AGENT_DISPLAY_COLORS: Record<AgentId, string> = {
  knowledge: 'purple',
  summary: 'emerald',
  writer: 'blue',
  review: 'orange',
  judge: 'violet',
  result: 'green',
};

const AGENT_TIMELINE_COLORS: Record<AgentId, string> = {
  knowledge: 'purple',
  summary: 'emerald',
  writer: 'blue',
  review: 'orange',
  judge: 'violet',
  result: 'green',
};

const AGENT_NODE_CLASSES: Record<AgentId, string> = {
  knowledge: 'node-knowledge',
  summary: 'node-summary',
  writer: 'node-writer',
  review: 'node-review',
  judge: 'node-judge',
  result: 'node-result',
};

const AGENT_SVG_ICONS: Record<AgentId, React.ReactNode> = {
  knowledge: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      <line x1="12" y1="6" x2="12" y2="10" />
      <line x1="10" y1="8" x2="14" y2="8" />
    </svg>
  ),
  summary: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  ),
  writer: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  ),
  review: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  judge: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="2" x2="12" y2="22" />
      <path d="M5 7l7-5 7 5" />
      <line x1="5" y1="7" x2="19" y2="7" />
      <line x1="5" y1="12" x2="19" y2="12" />
      <path d="M3 17l3 3" />
      <path d="M21 17l-3 3" />
      <line x1="6" y1="20" x2="18" y2="20" />
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

const AGENT_OUTPUT_SUMMARIES: Record<AgentId, string> = {
  knowledge: '检索到相关知识库内容：智能体协作、技术研究、产品开发...',
  summary: '构建高效的多智能体协同生态，提升任务处理效率...',
  writer: '基于知识库上下文生成初稿，包含多维度内容规划...',
  review: '质量评估完成：内容完整性0.85，逻辑清晰度0.78...',
  judge: '最终决策：调用API网关增强，难度评分0.72 > 阈值0.65...',
  result: '最终结果已整合生成',
};

const AGENT_DETAIL_OUTPUTS: Record<AgentId, string> = {
  knowledge: '检索到相关知识库内容：智能体协作、技术研究、产品开发...',
  summary: '构建高效的多智能体协同生态，提升任务处理效率...',
  writer: '基于知识库上下文生成初稿，包含多维度内容规划...',
  review: '质量评估完成：内容完整性0.85，逻辑清晰度0.78...',
  judge: '最终决策：调用API网关增强，难度评分0.72 > 阈值0.65...',
  result: '最终结果已整合生成',
};

const NODE_DETAIL_INFO: Record<string, { input: string; output: string; duration: string; model: string }> = {
  '用户输入': { input: '用户自然语言输入', output: '结构化任务描述', duration: '-', model: '-' },
  'Knowledge Agent': { input: '用户原始输入', output: '知识库检索结果 + 用户原始输入', duration: '0.8s', model: 'Qwen2.5-3B' },
  'A摘要Agent': { input: '知识库增强后的输入', output: '关键信息摘要与提取', duration: '1.2s', model: 'Qwen2.5-3B' },
  'B撰写Agent': { input: '知识库增强后的输入', output: '内容初稿生成', duration: '1.8s', model: 'Qwen2.5-7B' },
  'Review Agent': { input: 'B撰写Agent输出', output: '质量评分与修改建议', duration: '0.9s', model: 'Qwen2.5-3B' },
  'Judge Agent': { input: 'Review Agent输出 + 阈值0.65', output: '最终决策与路径选择', duration: '1.1s', model: 'Qwen2.5-3B' },
  '内部PK胜出': { input: '本地模型输出', output: '优化后的本地结果', duration: '0.8s', model: 'Local' },
  'API网关': { input: '高难度任务', output: '云端增强生成结果', duration: '4.4s', model: 'DeepSeek-V4' },
  '最终答案输出': { input: '整合后内容', output: '格式化最终回答', duration: '0.5s', model: 'Local' },
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
          cx="24" cy="24" r={radius}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="progress-ring-text" style={{ color }}>{percentage}%</span>
    </div>
  );
}

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  target: string;
  type: 'node' | 'agent';
}

export default function DashboardLayout() {
  const [inputValue, setInputValue] = useState('');
  const [activeTab, setActiveTab] = useState<'output' | 'decision' | 'api'>('output');
  const [threshold, setThreshold] = useState(0.65);
  const [isDarkTheme, setIsDarkTheme] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('neuroflow-theme');
      return saved !== 'light';
    }
    return true;
  });
  const [consoleExpanded, setConsoleExpanded] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [modelPath, setModelPath] = useState('/models');
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [nodeDetail, setNodeDetail] = useState<string | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<{ title: string; message: string; onConfirm: () => void } | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({ visible: false, x: 0, y: 0, target: '', type: 'node' });
  const [expandedAgentDetails, setExpandedAgentDetails] = useState<Set<string>>(new Set());
  const [taskListOpen, setTaskListOpen] = useState(false);
  const [cpuData, setCpuData] = useState<number[]>([20, 22, 18, 24, 16, 20, 14, 18, 22, 20]);
  const [memData, setMemData] = useState<number[]>([16, 14, 18, 12, 16, 14, 18, 16, 14, 16]);
  const [gpuData, setGpuData] = useState<number[]>([24, 20, 24, 18, 22, 24, 20, 22, 18, 24]);
  const [cpuValue, setCpuValue] = useState(34);
  const [memValue, setMemValue] = useState(4.2);
  const [gpuValue, setGpuValue] = useState(1.2);

  const contextMenuRef = useRef<HTMLDivElement>(null);

  const {
    isRunning, currentTask, currentStep, elapsedSeconds, useMock,
    completedSteps, result, judgeDecision, complexityScore, logs,
    setCurrentTask, setIsRunning, setCurrentStep,
    setResult, setJudgeDecision, setComplexityScore, addLog, addCompletedStep,
    addWorkflowStep, resetWorkflow,
  } = useWorkflowStore();
  const { agents, updateAgentStatus, resetAllAgents, toggleAgentEnabled } = useAgentStore();

  useEffect(() => {
    if (isDarkTheme) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('neuroflow-theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('neuroflow-theme', 'light');
    }
  }, [isDarkTheme]);

  useEffect(() => {
    const interval = setInterval(() => {
      const newCpu = 30 + Math.random() * 15;
      const newMem = 3.8 + Math.random() * 1.2;
      const newGpu = 1.0 + Math.random() * 0.6;
      setCpuValue(Math.round(newCpu));
      setMemValue(parseFloat(newMem.toFixed(1)));
      setGpuValue(parseFloat(newGpu.toFixed(1)));
      setCpuData(prev => [...prev.slice(1), 32 - (newCpu / 100) * 28]);
      setMemData(prev => [...prev.slice(1), 32 - (newMem / 16) * 28]);
      setGpuData(prev => [...prev.slice(1), 32 - (newGpu / 8) * 28]);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClick = () => {
      setContextMenu(prev => ({ ...prev, visible: false }));
      setShowModelDropdown(false);
    };
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, []);

  const formatTime = (seconds: number) => {
    const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
    const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
  };

  const generateSvgPath = (data: number[]) => {
    const points = data.map((y, i) => {
      const x = (i / (data.length - 1)) * 240;
      return `${i === 0 ? 'M' : 'T'}${x},${y}`;
    });
    const firstX = 0;
    const firstY = data[0];
    return `M${firstX},${firstY} ${data.slice(1).map((y, i) => {
      const x = ((i + 1) / (data.length - 1)) * 240;
      return `Q${x - 12},${y < data[i] ? y - 2 : y + 2} ${x},${y}`;
    }).join(' ')}`;
  };

  const executeWithMock = useCallback(async (taskText: string) => {
    setCurrentTask(taskText);
    setIsRunning(true);
    setInputValue('');

    const startTime = new Date().toISOString();

    for (const agentId of AGENT_ORDER) {
      if (!agents[agentId].enabled) continue;
      setCurrentStep(agentId);
      updateAgentStatus(agentId, 'processing');
      addLog(agentId, 'info', `${AGENT_NAMES[agentId]} 开始处理...`);

      const stepStart = Date.now();
      await new Promise((resolve) => setTimeout(resolve, 800 + Math.random() * 1200));
      const duration = (Date.now() - stepStart) / 1000;

      addCompletedStep(agentId);
      updateAgentStatus(agentId, 'completed');

      if (agentId === 'judge') {
        setComplexityScore(0.72);
        const isComplex = 0.72 >= COMPLEXITY_THRESHOLD;
        setJudgeDecision(isComplex ? 'cloud' : 'local');
        addLog(agentId, 'info', `难度评估: 0.72 (困难) - 超过阈值 0.65`);
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
  }, [setCurrentTask, setIsRunning, setCurrentStep, setResult, setJudgeDecision, setComplexityScore, addLog, addCompletedStep, addWorkflowStep, updateAgentStatus, agents]);

  const executeWithAPI = useCallback(async (taskText: string) => {
    setCurrentTask(taskText);
    setIsRunning(true);
    setInputValue('');
    setResult(null);

    try {
      await chatService.sendStream(
        { content: taskText },
        (data) => {
          switch (data.type) {
            case 'start':
              addLog('system', 'info', '工作流开始执行');
              break;

            case 'agent_start':
              if (data.agent_id) {
                updateAgentStatus(data.agent_id as AgentId, 'processing');
                setCurrentStep(data.agent_id as AgentId);
                addLog(data.agent_id, 'info', `${data.agent_name} 开始处理...`);
              }
              break;

            case 'agent_complete':
              if (data.agent_id) {
                const agentId = data.agent_id as AgentId;
                addCompletedStep(agentId);
                updateAgentStatus(agentId, data.success ? 'completed' : 'error');
                setCurrentStep(null);
                addLog(agentId, data.success ? 'success' : 'error',
                  `${data.agent_name} ${data.success ? '完成' : '失败'} (${data.duration}s)`
                );

                if (agentId === 'judge' && data.complexity_score !== undefined) {
                  setComplexityScore(data.complexity_score);
                  setJudgeDecision(data.executed_locally ? 'local' : 'cloud');
                  addLog(agentId, 'info', `复杂度评分: ${data.complexity_score.toFixed(2)}`);
                  addLog(agentId, data.executed_locally ? 'success' : 'warning',
                    `决策: ${data.executed_locally ? '本地处理' : '云端处理'}`
                  );
                }
              }
              break;

            case 'agent_error':
              if (data.agent_id) {
                const agentId = data.agent_id as AgentId;
                updateAgentStatus(agentId, 'error');
                setCurrentStep(null);
                addLog(agentId, 'error', `${data.agent_name} 执行出错: ${data.error}`);
              }
              break;

            case 'complete':
              console.log('[DEBUG] Received complete event:', data);
              if (data.final_result) {
                console.log('[DEBUG] final_result length:', data.final_result.length);
                console.log('[DEBUG] final_result preview:', data.final_result.substring(0, 100));
                setResult({
                  final_result: data.final_result,
                  steps: [],
                  executed_locally: data.executed_locally,
                  total_duration_seconds: data.total_duration,
                  start_time: new Date().toISOString(),
                  end_time: new Date().toISOString(),
                  complexity_score: data.complexity_score,
                });
              }
              addLog('result', 'success', '所有步骤已完成，最终结果已生成');
              break;

            case 'error':
              addLog('system', 'error', `工作流执行失败: ${data.error}`);
              break;
          }
        }
      );
    } catch (error) {
      console.error('[Workflow API Error]', error);
      console.error('[DEBUG] Falling back to mock data!');
      addLog(undefined, 'error', '后端API调用失败，切换到本地模拟模式');
      await executeWithMock(taskText);
      return;
    } finally {
      setIsRunning(false);
      setCurrentStep(null);
    }
  }, [setCurrentTask, setIsRunning, setInputValue, setResult, setCurrentStep, setComplexityScore, setJudgeDecision, addLog, addCompletedStep, addWorkflowStep, updateAgentStatus, executeWithMock]);

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
    setConfirmDialog({
      title: '停止任务',
      message: '确定要停止当前正在运行的任务吗？已完成的步骤将保留。',
      onConfirm: () => {
        setIsRunning(false);
        setCurrentStep(null);
        setConfirmDialog(null);
      },
    });
  };

  const handleClear = () => {
    setConfirmDialog({
      title: '清空数据',
      message: '确定要清空所有任务数据吗？此操作不可撤销。',
      onConfirm: () => {
        resetWorkflow();
        resetAllAgents();
        setInputValue('');
        setConfirmDialog(null);
      },
    });
  };

  const handleContextMenu = (e: React.MouseEvent, target: string, type: 'node' | 'agent') => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      target,
      type,
    });
  };

  const handleContextAction = (action: string) => {
    if (action === 'copy') {
      navigator.clipboard?.writeText(contextMenu.target);
    } else if (action === 'rerun') {
      setInputValue(contextMenu.target);
    } else if (action === 'detail') {
      setNodeDetail(contextMenu.target);
    }
    setContextMenu(prev => ({ ...prev, visible: false }));
  };

  const toggleAgentDetail = (agentId: string) => {
    setExpandedAgentDetails(prev => {
      const next = new Set(prev);
      if (next.has(agentId)) next.delete(agentId);
      else next.add(agentId);
      return next;
    });
  };

  const getNodeStatus = (agentId: AgentId) => {
    if (completedSteps.includes(agentId)) return 'completed';
    if (currentStep === agentId) return 'working';
    return 'pending';
  };

  const getArrowClass = (fromAgent: AgentId | null, toAgent: AgentId | null) => {
    if (!fromAgent && toAgent) {
      if (completedSteps.includes(toAgent)) return 'flow-success';
      if (currentStep === toAgent) return 'flow-active';
      return '';
    }
    if (fromAgent && completedSteps.includes(fromAgent)) {
      if (toAgent && (completedSteps.includes(toAgent) || currentStep === toAgent)) return 'flow-success';
      return '';
    }
    if (fromAgent && currentStep === fromAgent) return 'flow-active';
    return '';
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

  const enabledCount = Object.values(agents).filter(a => a.enabled).length;

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

  const renderResourceChart = (data: number[], gradId: string, strokeColor: string, fillColor: string) => {
    const pathD = generateSvgPath(data);
    const fillD = `${pathD} V32 H0 Z`;
    return (
      <svg width="100%" height="32" viewBox="0 0 240 32" preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={fillColor} />
            <stop offset="100%" stopColor={fillColor.replace(/[\d.]+\)$/, '0)')} />
          </linearGradient>
        </defs>
        <path d={fillD} fill={`url(#${gradId})`} />
        <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="1.5" />
      </svg>
    );
  };

  return (
    <>
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <div className="logo-hexagon"></div>
            <span className="logo-text">NeuroFlow</span>
            <span className="logo-subtitle">多智能体协同平台</span>
          </div>
          <div className="task-bar" style={{ cursor: 'pointer' }} onClick={() => setTaskListOpen(!taskListOpen)}>
            <span className="task-label">任务：1</span>
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
                onClick={(e) => e.stopPropagation()}
                placeholder="输入您的任务需求... 例如：帮我写一份关于智能体协作的年度计划"
                className="task-input"
              />
            )}
            {taskListOpen && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0,
                background: 'var(--bg-card)', border: '1px solid var(--border-color)',
                borderRadius: 8, padding: 8, zIndex: 50, marginTop: 4,
                boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
              }}>
                {currentTask ? (
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', padding: '4px 8px' }}>
                    {currentTask}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '4px 8px' }}>暂无任务</div>
                )}
              </div>
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
              <div style={{ width: 8, height: 8, background: 'var(--green)', borderRadius: '50%', boxShadow: '0 0 6px rgba(16, 185, 129, 0.5)' }}></div>
              <span style={{ color: 'var(--green)', fontSize: 13, fontWeight: 500 }}>已完成</span>
            </div>
          )}
        </div>
        <div className="header-right">
          <button
            className={`btn btn-primary${isRunning ? ' running' : ''}`}
            onClick={isRunning ? handleStop : handleSubmit}
            disabled={!isRunning && (!inputValue.trim() && !currentTask)}
          >
            {isRunning ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="6" y="4" width="4" height="16" />
                  <rect x="14" y="4" width="4" height="16" />
                </svg>
                停止
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                运行任务
              </>
            )}
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
          <button className="btn-icon" onClick={() => setIsDarkTheme(!isDarkTheme)} title={isDarkTheme ? '切换浅色主题' : '切换深色主题'}>
            {isDarkTheme ? (
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
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
          </button>
        </div>
      </header>

      <div className="main-container">
        <aside className="sidebar-left">
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

          <div className="card animate-in delay-3">
            <div className="card-title">本地算力负载</div>
            <div className="stats-row">
              <div className="stat-item">
                <div className="stat-label">CPU</div>
                <div className="stat-value">{cpuValue}%</div>
              </div>
              <div className="stat-item">
                <div className="stat-label">显存</div>
                <div className="stat-value">{gpuValue}GB</div>
              </div>
            </div>
            <div className="progress-ring-container">
              <ProgressRing percentage={cpuValue} color="var(--green)" />
              <div style={{ flex: 1 }}>
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{ width: `${cpuValue}%`, background: 'var(--green)' }}></div>
                </div>
              </div>
            </div>
          </div>

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

          <div className="card animate-in delay-5">
            <div className="agent-fleet-header">
              <span className="agent-fleet-title">Agent舰队</span>
              <span className="agent-fleet-status">{enabledCount}/6 启用</span>
            </div>

            {AGENT_ORDER.map((agentId) => {
              const agent = agents[agentId];
              const iconClass = AGENT_ICON_CLASSES[agentId];
              const isActive = agent.status === 'processing';
              const isCompleted = agent.status === 'completed';

              return (
                <div
                  key={agentId}
                  className={`agent-item${!agent.enabled ? ' disabled-agent' : ''}`}
                  onContextMenu={(e) => handleContextMenu(e, AGENT_DISPLAY_NAMES[agentId], 'agent')}
                >
                  <div className={`agent-icon ${iconClass}`}>
                    {AGENT_SVG_ICONS[agentId]}
                  </div>
                  <div className="agent-info">
                    <div className="agent-name">{AGENT_DISPLAY_NAMES[agentId]}</div>
                    <div className="agent-model">{AGENT_MODELS[agentId]}</div>
                    <div className="agent-desc">{AGENT_DESCRIPTIONS[agentId]}</div>
                  </div>
                  <div className="agent-status">
                    {isCompleted && <span className="status-badge completed" style={{ color: 'var(--green)', fontSize: 12 }}><span className="checkmark-anim">✓</span> 已完成</span>}
                    {isActive && <span className="status-badge working"><span className="spinner"></span> 工作中</span>}
                    {!isActive && !isCompleted && <span className="status-badge idle">空闲</span>}
                    <div
                      className={`toggle-switch${!agent.enabled ? ' off' : ''}`}
                      onClick={() => toggleAgentEnabled(agentId)}
                      title={agent.enabled ? '点击禁用' : '点击启用'}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="card animate-in delay-5">
            <div className="card-title">资源监控</div>
            <div className="resource-item">
              <div className="resource-header">
                <span className="resource-label">CPU使用率</span>
                <span className="resource-value" style={{ color: 'var(--blue)' }}>{cpuValue}%</span>
              </div>
              <div className="resource-chart">
                {renderResourceChart(cpuData, 'cpuGrad', 'var(--blue)', 'rgba(59,130,246,0.3)')}
              </div>
            </div>
            <div className="resource-item">
              <div className="resource-header">
                <span className="resource-label">内存占用</span>
                <span className="resource-value" style={{ color: 'var(--blue)' }}>{memValue}GB / 16GB</span>
              </div>
              <div className="resource-chart">
                {renderResourceChart(memData, 'memGrad', 'var(--green)', 'rgba(16,185,129,0.3)')}
              </div>
            </div>
            <div className="resource-item">
              <div className="resource-header">
                <span className="resource-label">显存占用</span>
                <span className="resource-value" style={{ color: 'var(--blue)' }}>{gpuValue}GB / 8GB</span>
              </div>
              <div className="resource-chart">
                {renderResourceChart(gpuData, 'gpuGrad', 'var(--purple)', 'rgba(139,92,246,0.3)')}
              </div>
            </div>
          </div>

          <div className="card animate-in delay-5">
            <div className="card-title">系统设置</div>
            <div className="setting-item">
              <div className="setting-label">本地模型路径</div>
              <div style={{ position: 'relative' }}>
                <select
                  className="setting-input"
                  value={modelPath}
                  onChange={(e) => setModelPath(e.target.value)}
                  style={{ cursor: 'pointer' }}
                >
                  <option value="/models">/models</option>
                  <option value="/models/qwen">/models/qwen</option>
                  <option value="/models/deepseek">/models/deepseek</option>
                  <option value="/opt/llm/models">/opt/llm/models</option>
                </select>
              </div>
            </div>
            <div className="setting-item">
              <div className="setting-label">API Key</div>
              <div className="api-key-wrapper">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  className="setting-input with-toggle"
                  defaultValue="sk-******-******-******-demo"
                  readOnly={!showApiKey}
                  style={{ cursor: showApiKey ? 'text' : 'default' }}
                />
                <button
                  className="api-key-toggle"
                  onClick={() => setShowApiKey(!showApiKey)}
                  type="button"
                >
                  {showApiKey ? '🔒' : '👁'}
                </button>
              </div>
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

          <div className="console-log-section">
            <div className="console-log-header" onClick={() => setConsoleExpanded(!consoleExpanded)}>
              <span className="console-log-title">控制台日志</span>
              <span className={`console-log-toggle${consoleExpanded ? ' expanded' : ''}`}>▼</span>
            </div>
            <div className={`console-log-entries${consoleExpanded ? ' expanded' : ''}`}>
              {logs.length === 0 ? (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '8px 0' }}>暂无日志</div>
              ) : (
                [...logs].reverse().slice(0, 50).map((log: LogEntry) => (
                  <div key={log.id} className="console-log-entry">
                    <span className="console-log-time">
                      {new Date(log.timestamp).toLocaleTimeString('zh-CN', { hour12: false })}
                    </span>
                    <span className={`console-log-type ${log.type}`}>{log.type.toUpperCase()}</span>
                    <span className="console-log-msg">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </aside>

        <main className="content-center">
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
              <div
                className="pipeline-node node-input animate-in delay-1"
                onClick={() => setNodeDetail('用户输入')}
                onContextMenu={(e) => handleContextMenu(e, '用户输入', 'node')}
              >
                <div className="node-icon">👤</div>
                <div className="node-title">用户输入</div>
                <div className="node-subtitle">{currentTask || '等待输入任务...'}</div>
              </div>

              <div className={`arrow-down data-flow ${getArrowClass(null, 'knowledge')}`}></div>

              <div
                className={`pipeline-node ${AGENT_NODE_CLASSES.knowledge} ${getNodeStatus('knowledge') === 'completed' ? 'node-completed' : ''} ${getNodeStatus('knowledge') === 'working' ? 'node-working' : ''} animate-in delay-2`}
                onClick={() => setNodeDetail(AGENT_DISPLAY_NAMES.knowledge)}
                onContextMenu={(e) => handleContextMenu(e, AGENT_DISPLAY_NAMES.knowledge, 'node')}
              >
                <div className="node-icon">{AGENT_EMOJIS.knowledge}</div>
                <div className="node-title">{AGENT_DISPLAY_NAMES.knowledge}</div>
                <div className="node-subtitle">知识库检索与上下文增强</div>
                <div className={`node-status ${getNodeStatus('knowledge')}`}>
                  {getNodeStatus('knowledge') === 'working' ? (
                    <><span className="spinner"></span> 检索中...</>
                  ) : getNodeStatus('knowledge') === 'completed' ? (
                    <><span className="checkmark-anim">✓</span> 已完成</>
                  ) : (
                    '等待中'
                  )}
                </div>
              </div>

              <div className={`arrow-down data-flow ${getArrowClass('knowledge', 'summary')}`}></div>

              <div className="pipeline-row animate-in delay-3">
                {(['summary', 'writer'] as AgentId[]).map((agentId) => {
                  const status = getNodeStatus(agentId);
                  const subtitles: Record<AgentId, string> = {
                    knowledge: '知识库检索与上下文增强',
                    summary: '关键信息摘要与提取',
                    writer: '内容初稿生成与规划',
                    review: '质量评估与修改建议',
                    judge: '最终决策与路径选择',
                    result: '生成最终完整回答',
                  };
                  return (
                    <div
                      key={agentId}
                      className={`pipeline-node ${AGENT_NODE_CLASSES[agentId]} ${status === 'completed' ? 'node-completed' : ''} ${status === 'working' ? 'node-working' : ''}`}
                      onClick={() => setNodeDetail(AGENT_DISPLAY_NAMES[agentId])}
                      onContextMenu={(e) => handleContextMenu(e, AGENT_DISPLAY_NAMES[agentId], 'node')}
                    >
                      <div className="node-icon">{AGENT_EMOJIS[agentId]}</div>
                      <div className="node-title">{AGENT_DISPLAY_NAMES[agentId]}</div>
                      <div className="node-subtitle">{subtitles[agentId]}</div>
                      <div className={`node-status ${status}`}>
                        {status === 'working' ? (
                          <><span className="spinner"></span> 处理中...</>
                        ) : status === 'completed' ? (
                          <><span className="checkmark-anim">✓</span> 已完成</>
                        ) : (
                          '等待中'
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className={`arrow-down data-flow ${getArrowClass('writer', 'review')}`}></div>

              <div
                className={`pipeline-node node-review ${getNodeStatus('review') === 'completed' ? 'node-completed' : ''} ${getNodeStatus('review') === 'working' ? 'node-working' : ''} animate-in delay-4`}
                onClick={() => setNodeDetail(AGENT_DISPLAY_NAMES.review)}
                onContextMenu={(e) => handleContextMenu(e, AGENT_DISPLAY_NAMES.review, 'node')}
              >
                <div className="node-icon">{AGENT_EMOJIS.review}</div>
                <div className="node-title">{AGENT_DISPLAY_NAMES.review}</div>
                <div className="node-subtitle">质量评估与修改建议</div>
                <div className={`node-status ${getNodeStatus('review')}`}>
                  {getNodeStatus('review') === 'working' ? (
                    <><span className="spinner"></span> 评审中...</>
                  ) : getNodeStatus('review') === 'completed' ? (
                    <><span className="checkmark-anim">✓</span> 已完成</>
                  ) : (
                    '等待中'
                  )}
                </div>
              </div>

              <div className={`arrow-down data-flow ${getArrowClass('review', 'judge')}`}></div>

              <div
                className={`pipeline-node node-judge ${getNodeStatus('judge') === 'completed' ? 'node-completed' : ''} ${getNodeStatus('judge') === 'working' ? 'node-working' : ''} animate-in delay-5`}
                onClick={() => setNodeDetail(AGENT_DISPLAY_NAMES.judge)}
                onContextMenu={(e) => handleContextMenu(e, AGENT_DISPLAY_NAMES.judge, 'node')}
              >
                <div className="node-icon">{AGENT_EMOJIS.judge}</div>
                <div className="node-title">{AGENT_DISPLAY_NAMES.judge}</div>
                <div className="node-subtitle">最终决策与路径选择</div>
                <div className={`node-status ${getNodeStatus('judge')}`}>
                  {getNodeStatus('judge') === 'working' ? (
                    <><span className="spinner"></span> 决策中...</>
                  ) : getNodeStatus('judge') === 'completed' ? (
                    <><span className="checkmark-anim">✓</span> 已完成</>
                  ) : (
                    '等待中'
                  )}
                </div>
                {(completedSteps.includes('judge') || currentStep === 'judge') && (
                  <div className="difficulty-box">
                    <div className="difficulty-score">{complexityScore?.toFixed(2) ?? '0.72'}</div>
                    <div className="difficulty-threshold">难度评分</div>
                    <div className="difficulty-threshold">阈值: {threshold.toFixed(2)}</div>
                  </div>
                )}
              </div>

              <div className="branch-arrows animate-in delay-6">
                <div className="branch-arrow">
                  <span className="branch-label green">简单任务 (≤ 阈值)</span>
                  <div className={`arrow-down ${judgeDecision === 'local' ? 'flow-success' : ''}`} style={{ height: 20 }}></div>
                </div>
                <div className="branch-arrow">
                  <span className="branch-label orange">困难任务 (&gt; 阈值)</span>
                  <div className={`arrow-down ${judgeDecision === 'cloud' ? 'flow-active' : ''}`} style={{ height: 20 }}></div>
                </div>
              </div>

              <div className="pipeline-row animate-in delay-6">
                <div
                  className={`pipeline-node node-pk ${judgeDecision === 'local' ? 'node-completed' : ''}`}
                  onClick={() => setNodeDetail('内部PK胜出')}
                  onContextMenu={(e) => handleContextMenu(e, '内部PK胜出', 'node')}
                >
                  <div className="node-icon">🏆</div>
                  <div className="node-title">内部PK胜出</div>
                  <div className="node-subtitle">本地模型输出更优</div>
                </div>
                <div
                  className={`pipeline-node node-api ${judgeDecision === 'cloud' ? 'node-completed' : ''}`}
                  onClick={() => setNodeDetail('API网关')}
                  onContextMenu={(e) => handleContextMenu(e, 'API网关', 'node')}
                >
                  <div className="node-icon">☁️</div>
                  <div className="node-title">API网关</div>
                  <div className="node-subtitle">云端增强与生成</div>
                  <div className={`node-status ${getNodeStatus('judge') === 'completed' ? 'completed' : 'loading'}`}>
                    {getNodeStatus('judge') === 'completed' ? (
                      <><span className="checkmark-anim">✓</span> 已完成</>
                    ) : currentStep === 'judge' ? (
                      <><span className="spinner"></span> 调用中...</>
                    ) : (
                      '等待中'
                    )}
                  </div>
                </div>
              </div>

              <div className={`arrow-down ${getArrowClass('judge', 'result')}`}></div>

              <div
                className={`pipeline-node node-output ${getNodeStatus('result') === 'completed' ? 'node-completed' : ''} ${getNodeStatus('result') === 'working' ? 'node-working' : ''} animate-in delay-7`}
                onClick={() => setNodeDetail('最终答案输出')}
                onContextMenu={(e) => handleContextMenu(e, '最终答案输出', 'node')}
              >
                <div className="node-icon">📋</div>
                <div className="node-title">最终答案输出</div>
                <div className="node-subtitle">生成最终完整回答</div>
                <div className={`node-status ${getNodeStatus('result')}`}>
                  {getNodeStatus('result') === 'completed' ? (
                    <><span className="checkmark-anim">✓</span> 已完成</>
                  ) : currentStep === 'result' ? (
                    <><span className="spinner"></span> 生成中...</>
                  ) : (
                    '等待中'
                  )}
                </div>
              </div>
            </div>
          </div>

          {result && (
            <div className="final-answer-section animate-in delay-5">
              <div className="answer-header" style={{
                background: 'linear-gradient(to right, rgba(37, 99, 235, 0.2), transparent)',
                borderBottom: '1px solid var(--border-color)',
                paddingBottom: '16px',
                marginBottom: '16px',
              }}>
                <div className="answer-title" style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)' }}>最终答案</span>
                  <span style={{
                    marginLeft: '12px',
                    padding: '2px 8px',
                    borderRadius: '9999px',
                    background: 'rgba(16, 185, 129, 0.2)',
                    color: 'var(--green)',
                    fontSize: '12px',
                    fontWeight: 500,
                  }}>已完成 {progressPercent}%</span>
                </div>
              </div>

              <div className="answer-container">
                <div
                  className="answer-content custom-scrollbar"
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
                  <div
                    key={agentId}
                    className="timeline-item animate-in"
                    style={{ animationDelay: `${index * 0.1}s` }}
                    onContextMenu={(e) => handleContextMenu(e, AGENT_DISPLAY_NAMES[agentId], 'agent')}
                  >
                    <div className="timeline-time">{getTimeStr((completedSteps.length - index) * 3)}</div>
                    <div className={`timeline-icon ${AGENT_TIMELINE_COLORS[agentId]}`}>
                      {AGENT_EMOJIS[agentId]}
                    </div>
                    <div className="timeline-body">
                      <div className="timeline-header">
                        <span className="timeline-title">{AGENT_DISPLAY_NAMES[agentId]}</span>
                        <span className="timeline-link" style={{ color: 'var(--blue)', cursor: 'pointer' }} onClick={() => toggleAgentDetail(agentId)}>
                          {expandedAgentDetails.has(agentId) ? '收起' : '查看详情'}
                        </span>
                      </div>
                      {expandedAgentDetails.has(agentId) && (
                        <div style={{ marginTop: 8, padding: '8px', background: 'var(--bg-primary)', borderRadius: 6, fontSize: 11 }}>
                          <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>输入：</div>
                          <div style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>{currentTask}</div>
                          <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>输出摘要：</div>
                          <div style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>
                            {AGENT_DETAIL_OUTPUTS[agentId]}
                          </div>
                          <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>运行时间：</div>
                          <div style={{ color: 'var(--text-secondary)', marginBottom: 4 }}>
                            {(0.8 + Math.random() * 1.5).toFixed(1)}s
                          </div>
                          <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>使用模型：</div>
                          <div style={{ color: 'var(--text-secondary)' }}>{AGENT_MODELS[agentId]}</div>
                        </div>
                      )}
                      {!expandedAgentDetails.has(agentId) && (
                        <>
                          {agentId === 'writer' ? (
                            <>
                              <div className="timeline-label">
                                内容生成：<span style={{ color: 'var(--blue)', fontWeight: 600 }}>初稿已完成</span>
                              </div>
                              <div className="timeline-label" style={{ marginTop: 6 }}>生成概要：</div>
                              <ul className="timeline-list">
                                <li>基于知识库上下文生成初稿</li>
                                <li>包含多维度内容规划</li>
                                <li>已整合摘要Agent的关键信息</li>
                              </ul>
                            </>
                          ) : agentId === 'review' ? (
                            <>
                              <div className="timeline-label">
                                质量评估：<span style={{ color: 'var(--orange)', fontWeight: 600 }}>需改进</span>
                              </div>
                              <div className="timeline-label" style={{ marginTop: 6 }}>评估结果：</div>
                              <ul className="timeline-list">
                                <li>内容完整性：0.85 / 逻辑清晰度：0.78</li>
                                <li>专业性：0.72 / 创新性：0.65</li>
                                <li>建议调用云端大模型增强</li>
                              </ul>
                            </>
                          ) : agentId === 'judge' ? (
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
                          ) : (
                            <>
                              <div className="timeline-label">输入：</div>
                              <div className="timeline-content">{currentTask}</div>
                              <div className="timeline-label" style={{ marginTop: 6 }}>输出摘要：</div>
                              <div className="timeline-content">
                                {AGENT_OUTPUT_SUMMARIES[agentId]}
                              </div>
                            </>
                          )}
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
                  <div className="timeline-icon orange">🔍</div>
                  <div className="timeline-body">
                    <div className="timeline-header">
                      <span className="timeline-title">质量评估</span>
                      <span className="timeline-link" style={{ color: 'var(--blue)' }}>详情</span>
                    </div>
                    <div className="timeline-label">执行Agent：Review Agent</div>
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr',
                      gap: 6,
                      margin: '8px 0',
                      padding: '8px 12px',
                      background: 'rgba(249, 115, 22, 0.1)',
                      borderRadius: 8,
                      border: '1px solid rgba(249, 115, 22, 0.2)',
                    }}>
                      {[
                        { label: '内容完整性', score: '0.85' },
                        { label: '逻辑清晰度', score: '0.78' },
                        { label: '专业性', score: '0.72' },
                        { label: '创新性', score: '0.65' },
                      ].map((item) => (
                        <div key={item.label} style={{ fontSize: 11 }}>
                          <span style={{ color: 'var(--text-muted)' }}>{item.label}：</span>
                          <span style={{ color: 'var(--orange)', fontWeight: 600 }}>{item.score}</span>
                        </div>
                      ))}
                    </div>
                    <div className="timeline-label">修改建议：</div>
                    <ul className="timeline-list">
                      <li>增加数据支撑和具体案例</li>
                      <li>优化逻辑结构，增强论证连贯性</li>
                      <li>补充专业术语解释</li>
                    </ul>
                  </div>
                </div>

                <div className="timeline-item animate-in" style={{ animationDelay: '0.1s' }}>
                  <div className="timeline-icon violet">⚖️</div>
                  <div className="timeline-body">
                    <div className="timeline-header">
                      <span className="timeline-title">最终决策</span>
                      <span className="timeline-link" style={{ color: 'var(--blue)' }}>详情</span>
                    </div>
                    <div className="timeline-label">执行Agent：Judge Agent</div>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      margin: '8px 0',
                      padding: '8px 12px',
                      background: 'rgba(139, 92, 246, 0.15)',
                      borderRadius: 8,
                      border: '1px solid rgba(139, 92, 246, 0.3)',
                    }}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>复杂度评分：</span>
                      <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--purple)' }}>{complexityScore?.toFixed(2) ?? '0.72'}</span>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>阈值：{threshold.toFixed(2)}</span>
                    </div>
                    <div style={{ margin: '8px 0', display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '8px 12px',
                          borderRadius: 8,
                          background: judgeDecision === 'local' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                          border: `1px solid ${judgeDecision === 'local' ? 'rgba(16, 185, 129, 0.3)' : 'var(--border-color)'}`,
                          cursor: 'pointer',
                          transition: 'all 0.25s ease',
                        }}
                        onClick={() => setJudgeDecision('local')}
                      >
                        <div style={{
                          width: 20, height: 20, borderRadius: '50%',
                          background: judgeDecision === 'local' ? 'var(--green)' : 'var(--text-muted)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          transition: 'background-color 0.25s ease',
                        }}>
                          {judgeDecision === 'local' && <span style={{ color: 'white', fontSize: 12 }}>✓</span>}
                        </div>
                        <span style={{
                          fontSize: 12,
                          color: judgeDecision === 'local' ? 'var(--green)' : 'var(--text-secondary)',
                          fontWeight: judgeDecision === 'local' ? 600 : 400,
                          transition: 'color 0.25s ease',
                        }}>本地模型直接输出</span>
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '8px 12px',
                          borderRadius: 8,
                          background: judgeDecision === 'cloud' ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                          border: `1px solid ${judgeDecision === 'cloud' ? 'rgba(59, 130, 246, 0.3)' : 'var(--border-color)'}`,
                          cursor: 'pointer',
                          transition: 'all 0.25s ease',
                        }}
                        onClick={() => setJudgeDecision('cloud')}
                      >
                        <div style={{
                          width: 20, height: 20, borderRadius: '50%',
                          background: judgeDecision === 'cloud' ? 'var(--blue)' : 'var(--text-muted)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          transition: 'background-color 0.25s ease',
                        }}>
                          {judgeDecision === 'cloud' && <span style={{ color: 'white', fontSize: 12 }}>✓</span>}
                        </div>
                        <span style={{
                          fontSize: 12,
                          color: judgeDecision === 'cloud' ? 'var(--blue)' : 'var(--text-secondary)',
                          fontWeight: judgeDecision === 'cloud' ? 600 : 400,
                          transition: 'color 0.25s ease',
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
                        {[
                          { label: '模型', value: 'DeepSeek-V4', color: 'var(--text-primary)' },
                          { label: 'Token消耗', value: '1,247', color: 'var(--purple)' },
                          { label: '费用', value: '¥0.067', color: 'var(--orange)' },
                          { label: '延迟', value: '4.4s', color: 'var(--green)' },
                        ].map((item) => (
                          <div
                            key={item.label}
                            style={{
                              background: 'var(--bg-primary)',
                              padding: 10,
                              borderRadius: 8,
                              border: '1px solid var(--border-color)',
                              transition: 'all 0.25s ease',
                              cursor: 'default',
                            }}
                            className="api-stat-card"
                          >
                            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>{item.label}</div>
                            <div style={{ fontSize: 13, fontWeight: 700, color: item.color }}>{item.value}</div>
                          </div>
                        ))}
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

      {nodeDetail && (
        <div className="node-detail-modal" onClick={() => setNodeDetail(null)}>
          <div className="node-detail-panel" onClick={(e) => e.stopPropagation()}>
            <h3>
              <span>{nodeDetail}</span>
              <button
                style={{
                  marginLeft: 'auto', background: 'none', border: 'none',
                  color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18,
                  transition: 'color 0.2s',
                }}
                onClick={() => setNodeDetail(null)}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
              >
                ✕
              </button>
            </h3>
            {NODE_DETAIL_INFO[nodeDetail] && (
              <>
                <div className="node-detail-row">
                  <span className="node-detail-label">输入</span>
                  <span className="node-detail-value">{NODE_DETAIL_INFO[nodeDetail].input}</span>
                </div>
                <div className="node-detail-row">
                  <span className="node-detail-label">输出</span>
                  <span className="node-detail-value">{NODE_DETAIL_INFO[nodeDetail].output}</span>
                </div>
                <div className="node-detail-row">
                  <span className="node-detail-label">运行时间</span>
                  <span className="node-detail-value">{NODE_DETAIL_INFO[nodeDetail].duration}</span>
                </div>
                <div className="node-detail-row">
                  <span className="node-detail-label">使用模型</span>
                  <span className="node-detail-value">{NODE_DETAIL_INFO[nodeDetail].model}</span>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {confirmDialog && (
        <div className="confirm-dialog" onClick={() => setConfirmDialog(null)}>
          <div className="confirm-dialog-content" onClick={(e) => e.stopPropagation()}>
            <h4>{confirmDialog.title}</h4>
            <p>{confirmDialog.message}</p>
            <div className="confirm-dialog-actions">
              <button className="btn btn-secondary" onClick={() => setConfirmDialog(null)}>取消</button>
              <button className="btn btn-primary" onClick={confirmDialog.onConfirm}>确定</button>
            </div>
          </div>
        </div>
      )}

      {contextMenu.visible && (
        <div
          ref={contextMenuRef}
          className="context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="context-menu-item" onClick={() => handleContextAction('copy')}>
            📋 复制名称
          </div>
          <div className="context-menu-item" onClick={() => handleContextAction('detail')}>
            🔍 查看详情
          </div>
          {contextMenu.type === 'node' && (
            <div className="context-menu-item" onClick={() => handleContextAction('rerun')}>
              🔄 重新运行
            </div>
          )}
          <div className="context-menu-item danger" onClick={() => setContextMenu(prev => ({ ...prev, visible: false }))}>
            ✕ 关闭
          </div>
        </div>
      )}
    </>
  );
}
