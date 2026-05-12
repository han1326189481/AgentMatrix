import { useEffect, useState } from 'react';
import { Brain, FileText, PenTool, Eye, Scale, Download, User, ArrowDown } from 'lucide-react';
import { useWorkflowStore } from '@/stores/workflowStore';

const workflowSteps = [
  { id: 'user', icon: User, label: '用户输入', color: 'bg-gray-500' },
  { id: 'knowledge', icon: Brain, label: 'Knowledge', color: 'bg-blue-500' },
  { id: 'summary', icon: FileText, label: 'Summary', color: 'bg-green-500' },
  { id: 'writer', icon: PenTool, label: 'Writer', color: 'bg-purple-500' },
  { id: 'review', icon: Eye, label: 'Review', color: 'bg-yellow-500' },
  { id: 'judge', icon: Scale, label: 'Judge', color: 'bg-red-500' },
  { id: 'result', icon: Download, label: 'Result', color: 'bg-cyan-500' },
];

export default function WorkflowCanvas() {
  const { logs, isRunning } = useWorkflowStore();
  const [activeStep, setActiveStep] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);

  useEffect(() => {
    if (logs.length === 0) {
      setActiveStep(null);
      setCompletedSteps([]);
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
    <div className="bg-dark-800/50 rounded-xl border border-dark-700 p-6">
      <div className="flex flex-col items-center">
        {workflowSteps.map((step, index) => {
          const Icon = step.icon;
          const isActive = activeStep === step.id;
          const isCompleted = completedSteps.includes(step.id);
          const isPassed = index < workflowSteps.findIndex((s) => s.id === activeStep);

          return (
            <div key={step.id} className="flex flex-col items-center">
              <div
                className={`w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300 ${
                  isActive
                    ? `${step.color} animate-pulse scale-110 shadow-lg shadow-blue-500/50`
                    : isCompleted
                    ? `${step.color} opacity-80`
                    : 'bg-dark-600'
                }`}
              >
                <Icon className={`w-8 h-8 text-white ${isActive ? 'animate-bounce' : ''}`} />
              </div>
              <span
                className={`mt-2 text-sm font-medium ${
                  isActive ? 'text-blue-400' : isCompleted ? 'text-green-400' : 'text-dark-400'
                }`}
              >
                {step.label}
              </span>

              {index < workflowSteps.length - 1 && (
                <div className="relative my-4">
                  <div
                    className={`w-1 h-12 transition-all duration-500 ${
                      isPassed || isCompleted
                        ? 'bg-green-500'
                        : 'bg-dark-600'
                    }`}
                  />
                  <ArrowDown
                    className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-4 h-4 ${
                      isPassed || isCompleted ? 'text-green-400' : 'text-dark-500'
                    }`}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {isRunning && activeStep && (
        <div className="mt-6 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>
            <span className="text-sm text-blue-400">
              {workflowSteps.find((s) => s.id === activeStep)?.label} 正在处理...
            </span>
          </div>
        </div>
      )}
    </div>
  );
}