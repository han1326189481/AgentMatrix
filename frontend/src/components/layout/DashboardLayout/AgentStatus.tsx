'use client';

import { FileText, PenTool, Eye, Scale, Cloud, CheckCircle, AlertCircle, ChevronRight } from 'lucide-react';

interface AgentStep {
  agent_id: string;
  agent_name: string;
  success: boolean;
  duration_seconds: number;
  metadata?: any;
}

interface AgentStatusProps {
  steps?: AgentStep[];
  isRunning?: boolean;
  complexityScore?: number;
  executedLocally?: boolean;
}

const agentDefinitions = [
  { id: 'knowledge', name: '知识 Agent', model: 'Qwen2.5-1.5B', icon: FileText, color: 'from-blue-500 to-blue-600' },
  { id: 'summary', name: '摘要 Agent', model: 'Qwen2.5-1.5B', icon: PenTool, color: 'from-green-500 to-green-600' },
  { id: 'writer', name: '撰写 Agent', model: 'Qwen2.5-1.5B', icon: Eye, color: 'from-yellow-500 to-yellow-600' },
  { id: 'review', name: '评审 Agent', model: 'Phi4-mini-3.8B', icon: Scale, color: 'from-purple-500 to-purple-600' },
  { id: 'judge', name: '评委 Agent', model: 'Qwen2.5-1.5B', icon: Cloud, color: 'from-orange-500 to-orange-600' },
  { id: 'result', name: '结果 Agent', model: 'Qwen2.5-1.5B', icon: CheckCircle, color: 'from-emerald-500 to-emerald-600' },
];

export default function AgentStatus({ steps = [], isRunning = false, complexityScore = 0, executedLocally = true }: AgentStatusProps) {
  const getAgentStatus = (agentId: string) => {
    const step = steps.find(s => s.agent_id === agentId);
    if (step) {
      return step.success ? 'completed' : 'error';
    }
    if (isRunning) {
      const completedCount = steps.length;
      const agentIndex = agentDefinitions.findIndex(a => a.id === agentId);
      return agentIndex === completedCount ? 'processing' : 'pending';
    }
    return 'pending';
  };

  return (
    <div className="flex flex-col gap-6 min-h-0">
      {/* Agent 执行状态 */}
      <div className="bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 p-6 shadow-xl">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-400" />
              Agent 执行状态
            </h3>
            <p className="text-sm text-slate-400 mt-1">查看每个智能体的执行进度</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full"></span>
              <span className="text-xs text-slate-400">已完成</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-purple-500 rounded-full animate-pulse"></span>
              <span className="text-xs text-slate-400">进行中</span>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          {agentDefinitions.map((agent, index) => {
            const Icon = agent.icon;
            const status = getAgentStatus(agent.id);
            const step = steps.find(s => s.agent_id === agent.id);

            const isCompleted = status === 'completed';
            const isProcessing = status === 'processing';
            const isError = status === 'error';

            return (
              <div 
                key={agent.id}
                className={`relative p-4 rounded-xl border transition-all ${
                  isCompleted 
                    ? 'bg-green-500/10 border-green-500/30 hover:bg-green-500/15' 
                    : isProcessing 
                    ? 'bg-purple-500/10 border-purple-500/30 animate-pulse' 
                    : isError
                    ? 'bg-red-500/10 border-red-500/30'
                    : 'bg-slate-700/30 border-slate-600/30 hover:bg-slate-700/50'
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${agent.color} flex items-center justify-center shadow-lg`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className="text-base font-semibold text-white truncate">{agent.name}</span>
                      {isCompleted && <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />}
                      {isError && <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />}
                    </div>
                    <span className="text-sm text-slate-400">{agent.model}</span>
                  </div>

                  <div className="flex flex-col items-end gap-1">
                    <span className={`text-xs px-3 py-1 rounded-full font-medium ${
                      isCompleted 
                        ? 'bg-green-500/20 text-green-400' 
                        : isProcessing 
                        ? 'bg-purple-500/20 text-purple-400' 
                        : isError
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-slate-600/50 text-slate-400'
                    }`}>
                      {isCompleted ? '已完成' : isProcessing ? '进行中' : isError ? '错误' : '等待中'}
                    </span>
                    {step && step.duration_seconds > 0 && (
                      <span className="text-xs text-slate-400">{step.duration_seconds.toFixed(1)}s</span>
                    )}
                  </div>
                </div>

                {/* 连接线 */}
                {index < agentDefinitions.length - 1 && (
                  <div className="absolute left-10 top-[4.5rem] w-0.5 h-6 bg-gradient-to-b from-slate-600 to-transparent"></div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 复杂度决策 */}
      <div className="bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 p-6 shadow-xl">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Scale className="w-5 h-5 text-purple-400" />
          复杂度决策
        </h3>
        
        <div className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-slate-400">难度评分</span>
              <span className={`text-xl font-bold ${complexityScore > 0.65 ? 'text-orange-400' : 'text-green-400'}`}>
                {complexityScore > 0 ? complexityScore.toFixed(2) : '--'}
              </span>
            </div>
            <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all duration-500 rounded-full ${
                  complexityScore > 0.65 
                    ? 'bg-gradient-to-r from-yellow-500 via-orange-500 to-red-500' 
                    : 'bg-gradient-to-r from-green-500 via-emerald-500 to-teal-500'
                }`}
                style={{ width: complexityScore > 0 ? `${Math.min(complexityScore * 100, 100)}%` : '0%' }}
              />
            </div>
            <div className="flex items-center justify-between mt-2 text-xs text-slate-500">
              <span>0.0</span>
              <span className="text-slate-400 font-medium">阈值: 0.65</span>
              <span>1.0</span>
            </div>
          </div>

          <div className={`p-4 rounded-xl border ${
            executedLocally 
              ? 'bg-green-500/10 border-green-500/30' 
              : 'bg-orange-500/10 border-orange-500/30'
          }`}>
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg ${
                executedLocally 
                  ? 'bg-gradient-to-br from-green-500 to-emerald-600' 
                  : 'bg-gradient-to-br from-orange-500 to-red-600'
              } flex items-center justify-center`}>
                {executedLocally ? (
                  <CheckCircle className="w-5 h-5 text-white" />
                ) : (
                  <Cloud className="w-5 h-5 text-white" />
                )}
              </div>
              <div>
                <p className="text-sm font-medium text-white">
                  {executedLocally ? '本地模型执行' : '云端API执行'}
                </p>
                <p className="text-xs text-slate-400">
                  {executedLocally ? '使用国产算力，节省成本' : '任务复杂，调用DeepSeek增强'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
