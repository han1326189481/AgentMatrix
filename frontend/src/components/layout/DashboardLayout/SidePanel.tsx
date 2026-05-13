'use client';

import { Brain, FileText, PenTool, Eye, Scale, Cloud, Cpu, HardDrive, Activity, Settings, ChevronDown, ChevronRight, CheckCircle } from 'lucide-react';

const kpiData = [
  { label: 'API调用次数', value: '1', unit: '/ 1次', percentage: 100, color: 'text-blue-400', bgColor: 'from-blue-500 to-blue-600' },
  { label: '预估节省成本', value: '¥0.113', unit: '', percentage: 62, color: 'text-green-400', bgColor: 'from-green-500 to-green-600' },
  { label: '本地算力负载', value: '34%', unit: '', percentage: 34, color: 'text-purple-400', bgColor: 'from-purple-500 to-purple-600' },
  { label: '响应时间', value: '2.3s', unit: '', percentage: 56, color: 'text-cyan-400', bgColor: 'from-cyan-500 to-cyan-600' },
];

const agentList = [
  { id: 'summary', name: '摘要 Agent', model: 'Qwen2.5-3B', status: 'completed', icon: FileText, color: 'from-blue-500 to-blue-600' },
  { id: 'writer', name: '撰写 Agent', model: 'Qwen2.5-7B', status: 'completed', icon: PenTool, color: 'from-green-500 to-green-600' },
  { id: 'review', name: '评审 Agent', model: 'Qwen2.5-3B', status: 'completed', icon: Eye, color: 'from-yellow-500 to-yellow-600' },
  { id: 'judge', name: '评委 Agent', model: 'Qwen2.5-3B', status: 'processing', icon: Scale, color: 'from-purple-500 to-purple-600' },
  { id: 'api', name: 'API网关', model: 'DeepSeek-V4', status: 'processing', icon: Cloud, color: 'from-orange-500 to-orange-600' },
];

export default function SidePanel() {
  return (
    <aside className="w-80 bg-dark-800 border-r border-dark-700 flex flex-col">
      <div className="p-4 border-b border-dark-700">
        <div className="grid grid-cols-2 gap-3">
          {kpiData.map((kpi, index) => (
            <div key={index} className="bg-dark-700 rounded-lg p-3 border border-dark-600">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-dark-400">{kpi.label}</span>
                <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${kpi.bgColor} flex items-center justify-center relative`}>
                  <svg className="w-8 h-8 -rotate-90">
                    <circle cx="16" cy="16" r="14" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="2" />
                    <circle 
                      cx="16" cy="16" r="14" 
                      fill="none" 
                      stroke="white" 
                      strokeWidth="2" 
                      strokeDasharray={`${kpi.percentage * 0.88} 88`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <span className="absolute text-xs font-bold text-white">{kpi.percentage}%</span>
                </div>
              </div>
              <div className="flex items-baseline gap-1">
                <span className={`text-lg font-bold ${kpi.color}`}>{kpi.value}</span>
                <span className="text-xs text-dark-500">{kpi.unit}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="p-4 border-b border-dark-700">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white">Agent舰队</h3>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full"></span>
              <span className="text-xs text-dark-400">全部启用</span>
            </div>
          </div>
          <div className="space-y-2">
            {agentList.map((agent) => {
              const Icon = agent.icon;
              const isProcessing = agent.status === 'processing';
              const isCompleted = agent.status === 'completed';
              
              return (
                <div 
                  key={agent.id}
                  className={`p-3 rounded-lg border transition-all ${
                    isProcessing 
                      ? 'bg-purple-500/10 border-purple-500/30' 
                      : 'bg-dark-700/50 border-dark-600/50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${agent.color} flex items-center justify-center`}>
                      <Icon className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-white truncate">{agent.name}</span>
                        {isCompleted && <CheckCircle className="w-4 h-4 text-green-400" />}
                        {isProcessing && <span className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />}
                      </div>
                      <span className="text-xs text-dark-400">{agent.model}</span>
                    </div>
                    <span className={`text-xs px-2 py-1 rounded ${
                      isProcessing ? 'bg-purple-500/20 text-purple-400' : 
                      isCompleted ? 'bg-green-500/20 text-green-400' : 'bg-dark-600 text-dark-400'
                    }`}>
                      {isProcessing ? '工作中' : isCompleted ? '已完成' : '待执行'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="p-4 border-b border-dark-700">
          <h3 className="text-sm font-semibold text-white mb-3">资源监控</h3>
          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-dark-400">CPU使用率</span>
                <span className="text-xs text-green-400">34%</span>
              </div>
              <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                <div className="h-full w-[34%] bg-gradient-to-r from-green-500 to-green-400 rounded-full" />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-dark-400">内存占用</span>
                <span className="text-xs text-blue-400">4.2GB/16GB</span>
              </div>
              <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                <div className="h-full w-[26%] bg-gradient-to-r from-blue-500 to-blue-400 rounded-full" />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-dark-400">显存占用</span>
                <span className="text-xs text-purple-400">1.2GB/8GB</span>
              </div>
              <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                <div className="h-full w-[15%] bg-gradient-to-r from-purple-500 to-purple-400 rounded-full" />
              </div>
            </div>
          </div>
        </div>

        <div className="p-4">
          <button className="w-full flex items-center justify-between p-3 bg-dark-700/50 hover:bg-dark-700 rounded-lg border border-dark-600/50 transition-colors">
            <div className="flex items-center gap-3">
              <Settings className="w-5 h-5 text-dark-400" />
              <span className="text-sm text-dark-300">系统设置</span>
            </div>
            <ChevronRight className="w-4 h-4 text-dark-500" />
          </button>
        </div>
      </div>
    </aside>
  );
}