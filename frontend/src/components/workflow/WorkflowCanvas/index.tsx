'use client';

import { User, Brain, FileText, PenTool, Eye, Scale, Cloud, Download, CheckCircle2, Loader2, Circle } from 'lucide-react';
import { useWorkflowStore } from '@/stores/workflowStore';
import type { AgentId } from '@/types';

const workflowNodes: { id: string; icon: typeof Brain; label: string; subLabel: string; type: 'input' | 'agent' | 'decision' | 'output' | 'branch'; color?: string }[] = [
  { id: 'user', icon: User, label: '用户输入', subLabel: '', type: 'input' },
  { id: 'knowledge', icon: Brain, label: 'A 摘要', subLabel: 'Qwen2.5-3B', type: 'agent' },
  { id: 'summary', icon: FileText, label: 'B 撰写', subLabel: 'Qwen2.5-7B', type: 'agent' },
  { id: 'writer', icon: PenTool, label: 'C 评审', subLabel: 'Qwen2.5-3B', type: 'agent' },
  { id: 'judge', icon: Scale, label: '评委', subLabel: 'Qwen2.5-3B', type: 'decision' },
  { id: 'local', icon: Download, label: '内部PK胜出', subLabel: '本地模型输出更优', type: 'branch', color: '#10b981' },
  { id: 'cloud', icon: Cloud, label: 'API 网关', subLabel: 'DeepSeek-V4', type: 'branch', color: '#f59e0b' },
  { id: 'result', icon: Download, label: '最终答案输出', subLabel: '生成最终完整回答', type: 'output' },
];

function WorkflowNode({ node, isActive, isCompleted }: {
  node: typeof workflowNodes[0];
  isActive: boolean;
  isCompleted: boolean;
}) {
  const Icon = node.icon;

  if (node.type === 'input') {
    return (
      <div className={`workflow-node flex items-center gap-3 px-4 py-3 rounded-xl border transition-all ${
        isActive ? 'border-accent-cyan bg-accent-cyan/10 active' : 'border-border-light bg-dark-tertiary'
      }`}>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${isActive ? 'bg-accent-cyan/20' : 'bg-dark-elevated'}`}>
          <Icon className={`w-4.5 h-4.5 ${isActive ? 'text-accent-cyan' : 'text-text-muted'}`} />
        </div>
        <div>
          <p className="text-[13px] font-semibold text-text-primary">{node.label}</p>
          <p className="text-[11px] text-text-muted">帮我写一份关于智能体协作的年度计划...</p>
        </div>
      </div>
    );
  }

  if (node.type === 'decision') {
    return (
      <div className={`workflow-node px-4 py-3 rounded-xl border-2 transition-all ${
        isActive ? 'border-accent-purple bg-accent-purple/10 active' : isCompleted ? 'border-accent-purple/40 bg-dark-tertiary' : 'border-border-default bg-dark-tertiary'
      }`}>
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${isActive ? 'bg-accent-purple/20 animate-pulse-slow' : 'bg-dark-elevated'}`}>
            <Icon className={`w-4.5 h-4.5 ${isActive || isCompleted ? 'text-accent-purple' : 'text-text-muted'}`} />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-semibold text-text-primary">{node.label}</span>
              <span className="text-[11px] text-text-tertiary">Agent</span>
            </div>
            <p className="mono-text text-[11px] text-text-tertiary">{node.subLabel}</p>
          </div>
        </div>
        {isActive && (
          <div className="mt-2 pt-2 border-t border-border-default">
            <p className="text-[12px] text-accent-purple">工作中...</p>
            <div className="mt-1.5 flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin text-accent-purple" />
              <span className="text-[11px] text-text-muted">决策中...</span>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (node.type === 'branch') {
    const isCloud = node.id === 'cloud';
    return (
      <div className={`workflow-node px-3 py-2.5 rounded-xl border transition-all ${
        isActive ? `border-${isCloud ? 'amber' : 'emerald'} bg-${isCloud ? 'accent-amber' : 'accent-green'}/10 active` : `border-border-default bg-dark-tertiary`
      }`}>
        <div className="flex items-center gap-2.5">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isActive ? (isCloud ? 'bg-accent-amber/20' : 'bg-accent-green/20') : 'bg-dark-elevated'}`}>
            <Icon className={`w-4 h-4 ${isActive ? (isCloud ? 'text-accent-amber' : 'text-accent-emerald') : 'text-text-muted'}`} />
          </div>
          <div>
            <p className={`text-[12px] font-semibold ${isActive ? (isCloud ? 'text-accent-amber' : 'text-accent-emerald') : 'text-text-primary'}`}>{node.label}</p>
            <p className="text-[10px] text-text-muted">{node.subLabel}</p>
          </div>
        </div>
        {isActive && (
          <div className="mt-1.5 flex items-center gap-1.5 pl-[42px]">
            <Loader2 className={`w-3 h-3 animate-spin ${isCloud ? 'text-accent-amber' : 'text-accent-emerald'}`} />
            <span className={`text-[10px] ${isCloud ? 'text-accent-amber' : 'text-accent-emerald'}`}>调用中...</span>
            <span className="mono-text text-[10px] text-text-muted ml-auto">{Math.floor(Math.random() * 200 + 100)} tokens</span>
          </div>
        )}
      </div>
    );
  }

  if (node.type === 'output') {
    return (
      <div className={`workflow-node flex items-center gap-3 px-4 py-3 rounded-xl border transition-all ${
        isActive ? 'border-accent-cyan bg-accent-cyan/10 active' : isCompleted ? 'border-accent-emerald/40 bg-dark-tertiary' : 'border-border-default bg-dark-tertiary'
      }`}>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${isActive ? 'bg-accent-cyan/20' : 'bg-dark-elevated'}`}>
          <Icon className={`w-4.5 h-4.5 ${isActive || isCompleted ? 'text-accent-cyan' : 'text-text-muted'}`} />
        </div>
        <div>
          <p className="text-[13px] font-semibold text-text-primary">{node.label}</p>
          <p className="text-[11px] text-text-muted">{node.subLabel}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`workflow-node card-dark p-3 transition-all ${isActive ? 'active border-accent-cyan' : ''} ${isCompleted ? 'border-accent-emerald/30' : ''}`}>
      <div className="flex items-center gap-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center relative ${
          isActive ? 'bg-accent-cyan/15' : isCompleted ? 'bg-accent-green/10' : 'bg-dark-tertiary'
        }`}>
          <Icon className={`w-4.5 h-4.5 ${isActive ? 'text-accent-cyan' : isCompleted ? 'text-accent-emerald' : 'text-text-muted'}`} />
          {isCompleted && <CheckCircle2 className="absolute -bottom-1 -right-1 w-4 h-4 text-accent-emerald" />}
          {isActive && <span className="absolute inset-0 rounded-lg border border-accent-cyan/50 animate-ping" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-[13px] font-semibold ${isActive ? 'text-accent-cyan' : isCompleted ? 'text-accent-emerald' : 'text-text-primary'}`}>
              {node.label}
            </span>
            <span className="text-text-muted">Agent</span>
          </div>
          <p className="mono-text text-[11px] text-text-tertiary">{node.subLabel}</p>

          <div className="flex items-center gap-2 mt-1.5">
            {isCompleted && (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-accent-emerald" />
                <span className="text-[11px] text-accent-emerald font-medium">已完成</span>
              </>
            )}
            {isActive && (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-accent-cyan" />
                <span className="text-[11px] text-accent-cyan font-medium">处理中</span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function WorkflowCanvas() {
  const { currentStep, completedSteps, isRunning, judgeDecision } = useWorkflowStore();

  const getNodeState = (id: string) => ({
    isActive: currentStep === id,
    isCompleted: completedSteps.includes(id as AgentId),
  });

  return (
    <div className="card-dark p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="section-title">多智能体协同流水线</h3>
        <div className="flex items-center gap-3">
          <button className="text-[11px] text-accent-cyan hover:text-white transition-colors flex items-center gap-1">
            <span className="w-6 h-0.5 bg-accent-cyan inline-block" /> 数据流
          </button>
          <button className="text-[11px] text-text-tertiary hover:text-text-secondary transition-colors flex items-center gap-1">
            <span className="w-6 h-0.5 bg-text-muted inline-block border-dashed" /> 控制流
          </button>
        </div>
      </div>

      <svg className="w-full absolute pointer-events-none" style={{ zIndex: 0 }}>
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#38bdf8" opacity="0.5" />
          </marker>
          <marker id="arrowhead-green" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#10b981" opacity="0.5" />
          </marker>
          <marker id="arrowhead-amber" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#f59e0b" opacity="0.5" />
          </marker>
        </defs>
      </svg>

      <div className="relative space-y-3">
        <WorkflowNode {...getNodeState('user')} node={workflowNodes[0]} />

        <div className="flex justify-center">
          <div className="w-px h-6 bg-gradient-to-b from-accent-cyan to-transparent" />
        </div>

        <div className="grid grid-cols-3 gap-3">
          <WorkflowNode {...getNodeState('knowledge')} node={workflowNodes[1]} />
          <WorkflowNode {...getNodeState('summary')} node={workflowNodes[2]} />
          <WorkflowNode {...getNodeState('writer')} node={workflowNodes[3]} />
        </div>

        <div className="flex justify-center">
          <div className="w-px h-6 bg-gradient-to-b from-accent-cyan to-transparent" />
        </div>

        <WorkflowNode {...getNodeState('judge')} node={workflowNodes[4]} />

        <div className="grid grid-cols-2 gap-3 mt-3">
          <div className="relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
              <span className="badge-status badge-completed text-[9px] px-2 py-0.5">简单任务 (&lt;=阈值)</span>
            </div>
            <WorkflowNode
              isActive={judgeDecision === 'local' && !completedSteps.includes('result')}
              isCompleted={judgeDecision === 'local'}
              node={workflowNodes[5]}
            />
          </div>
          <div className="relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
              <span className="badge-status badge-warning text-[9px] px-2 py-0.5">困难任务 (&gt; 阈值)</span>
            </div>
            <WorkflowNode
              isActive={judgeDecision === 'cloud' && !completedSteps.includes('result')}
              isCompleted={judgeDecision === 'cloud'}
              node={workflowNodes[6]}
            />
          </div>
        </div>

        <div className="flex justify-center">
          <div className="w-px h-6 bg-gradient-to-b from-accent-cyan to-transparent" />
        </div>

        <WorkflowNode
          isActive={currentStep === 'result'}
          isCompleted={completedSteps.includes('result') || !!judgeDecision}
          node={workflowNodes[7]}
        />

        {!isRunning && completedSteps.length === 0 && (
          <div className="mt-4 pt-4 border-t border-border-default text-center">
            <Circle className="w-6 h-6 text-text-muted mx-auto mb-2 opacity-50" />
            <p className="text-[12px] text-text-tertiary">输入任务后工作流将自动启动</p>
          </div>
        )}
      </div>
    </div>
  );
}
