'use client';

import { useEffect, useState } from 'react';
import { Brain, FileText, PenTool, Eye, Scale, Download, User, ArrowDown, Sparkles } from 'lucide-react';
import { useWorkflowStore } from '@/stores/workflowStore';

const workflowSteps = [
  { id: 'user', icon: User, label: '用户输入', color: 'from-gray-500 to-gray-600', bgColor: 'bg-gray-500' },
  { id: 'knowledge', icon: Brain, label: 'Knowledge', description: '知识检索', color: 'from-blue-500 to-blue-600', bgColor: 'bg-blue-500' },
  { id: 'summary', icon: FileText, label: 'Summary', description: '需求摘要', color: 'from-green-500 to-green-600', bgColor: 'bg-green-500' },
  { id: 'writer', icon: PenTool, label: 'Writer', description: '内容生成', color: 'from-purple-500 to-purple-600', bgColor: 'bg-purple-500' },
  { id: 'review', icon: Eye, label: 'Review', description: '质量评审', color: 'from-yellow-500 to-yellow-600', bgColor: 'bg-yellow-500' },
  { id: 'judge', icon: Scale, label: 'Judge', description: '复杂度判断', color: 'from-red-500 to-red-600', bgColor: 'bg-red-500' },
  { id: 'result', icon: Download, label: 'Result', description: '成果导出', color: 'from-cyan-500 to-cyan-600', bgColor: 'bg-cyan-500' },
];

export default function WorkflowCanvas() {
  const { logs, isRunning } = useWorkflowStore();
  const [activeStep, setActiveStep] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);
  const [stepMessages, setStepMessages] = useState<Record<string, string>>({});

  useEffect(() => {
    if (logs.length === 0) {
      setActiveStep(null);
      setCompletedSteps([]);
      setStepMessages({});
      return;
    }

    const stepMapping: Record<string, string> = {
      system: 'user',
      knowledge: 'knowledge',
      summary: 'summary',
      writer: 'writer',
      review: 'review',
      judge: 'judge',
      result: 'result',
    };

    logs.forEach((log) => {
      const stepId = stepMapping[log.agent];
      if (stepId) {
        setStepMessages((prev) => ({ ...prev, [stepId]: log.message }));
        if (log.type === 'info') {
          setActiveStep(stepId);
        } else if (log.type === 'success') {
          setCompletedSteps((prev) => [...new Set([...prev, stepId])]);
          if (stepId === 'result') {
            setActiveStep(null);
          }
        }
      }
    });
  }, [logs]);

  return (
    <div className="bg-dark-800/80 backdrop-blur-sm rounded-2xl border border-dark-600 p-8 shadow-xl">
      <div className="flex items-center gap-3 mb-8">
        <Sparkles className="w-5 h-5 text-blue-400" />
        <h3 className="text-lg font-semibold text-white">Agent 工作流执行</h3>
        {isRunning && (
          <span className="ml-auto flex items-center gap-2 px-3 py-1.5 bg-blue-500/20 border border-blue-500/30 rounded-full">
            <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>
            <span className="text-sm text-blue-400">执行中</span>
          </span>
        )}
      </div>

      <div className="flex items-center justify-center gap-4 flex-wrap">
        {workflowSteps.map((step, index) => {
          const Icon = step.icon;
          const isActive = activeStep === step.id;
          const isCompleted = completedSteps.includes(step.id);
          const isPassed = index < workflowSteps.findIndex((s) => s.id === activeStep);

          return (
            <div key={step.id} className="flex flex-col items-center">
              <div className="relative">
                <div
                  className={`w-16 h-16 rounded-xl flex items-center justify-center transition-all duration-500 relative overflow-hidden ${
                    isActive
                      ? `bg-gradient-to-br ${step.color} scale-110 shadow-lg shadow-blue-500/40`
                      : isCompleted
                      ? `bg-gradient-to-br ${step.color} opacity-90`
                      : 'bg-dark-700 border border-dark-600'
                  }`}
                >
                  <Icon className={`w-8 h-8 text-white ${isActive ? 'animate-bounce' : ''}`} />
                  
                  {isActive && (
                    <div className="absolute inset-0 bg-white/20 animate-pulse" />
                  )}
                  
                  {isCompleted && (
                    <div className="absolute -top-1 -right-1 w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                      <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-3 text-center">
                <span
                  className={`block text-sm font-semibold transition-colors ${
                    isActive ? 'text-blue-400' : isCompleted ? 'text-green-400' : 'text-dark-400'
                  }`}
                >
                  {step.label}
                </span>
                <span className="block text-xs text-dark-500 mt-1">{step.description}</span>
                
                {stepMessages[step.id] && (
                  <div className={`mt-2 px-2 py-1 rounded-lg text-xs max-w-32 truncate ${
                    isActive ? 'bg-blue-500/20 text-blue-300' : 'bg-dark-700 text-dark-400'
                  }`}>
                    {stepMessages[step.id]}
                  </div>
                )}
              </div>

              {index < workflowSteps.length - 1 && (
                <div className="relative my-4">
                  <div className="flex items-center">
                    <div
                      className={`w-12 h-1 rounded-full transition-all duration-700 ${
                        isPassed || isCompleted
                          ? 'bg-gradient-to-r from-green-400 to-green-500'
                          : 'bg-dark-600'
                      }`}
                    />
                  </div>
                  {isPassed && !isCompleted && (
                    <ArrowDown className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-5 text-green-400 animate-bounce" />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-8 pt-6 border-t border-dark-700">
        <div className="flex items-center justify-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-dark-700 border border-dark-600"></div>
            <span className="text-sm text-dark-400">等待中</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500 animate-pulse"></div>
            <span className="text-sm text-blue-400">执行中</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="text-sm text-green-400">已完成</span>
          </div>
        </div>
      </div>
    </div>
  );
}