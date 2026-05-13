'use client';

import { useState } from 'react';
import { Play, RefreshCw, FileText, PenTool, Eye, Scale, Cloud, CheckCircle, AlertCircle, TrendingUp, Clock, DollarSign, Cpu, Zap } from 'lucide-react';
import { agentService } from '@/services/api/agentService';
import LogViewer from '@/components/logs/LogViewer';
import ResultPreview from '@/components/result/ResultPreview';

export default function MainContent() {
  const [inputValue, setInputValue] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [logs, setLogs] = useState<Array<{ id: string; timestamp: Date; agent: string; type: 'info' | 'success' | 'warning' | 'error'; message: string }>>([]);
  const [agentSteps, setAgentSteps] = useState<any[]>([]);
  const [complexityScore, setComplexityScore] = useState<number>(0);
  const [executedLocally, setExecutedLocally] = useState<boolean>(true);

  const handleSubmit = async () => {
    if (!inputValue.trim() || isRunning) return;
    
    setIsRunning(true);
    setResult(null);
    setLogs([]);
    setAgentSteps([]);

    const addLog = (agent: string, message: string, type: 'info' | 'success' | 'warning' | 'error') => {
      setLogs(prev => [...prev, {
        id: `${agent}-${Date.now()}`,
        timestamp: new Date(),
        agent,
        type,
        message
      }]);
    };

    addLog('system', '🚀 工作流执行开始', 'info');
    
    try {
      const response = await agentService.executeWorkflow(inputValue);
      
      setAgentSteps(response.steps || []);
      setComplexityScore(response.complexity_score || 0);
      setExecutedLocally(response.executed_locally || true);
      
      response.steps.forEach((step: any) => {
        const agentType = step.agent_id;
        addLog(agentType, `✅ ${step.agent_name}: ${step.success ? '执行成功' : '执行失败'}`, step.success ? 'success' : 'error');
      });
      
      setResult(response.final_result);
      addLog('system', '🎉 工作流执行完成！', 'success');
    } catch (error) {
      console.error('Workflow execution error:', error);
      addLog('system', `❌ 工作流执行失败: ${error}`, 'error');
    }
    
    setIsRunning(false);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const kpiData = [
    { label: '复杂度评分', value: complexityScore > 0 ? complexityScore.toFixed(2) : '--', unit: '', icon: Zap, color: complexityScore > 0.65 ? 'text-orange-400' : 'text-green-400', bgColor: complexityScore > 0.65 ? 'from-orange-500 to-orange-600' : 'from-green-500 to-green-600' },
    { label: '响应时间', value: '2.3', unit: 's', icon: Clock, color: 'text-cyan-400', bgColor: 'from-cyan-500 to-cyan-600' },
    { label: '节省成本', value: '¥0.113', unit: '', icon: DollarSign, color: 'text-green-400', bgColor: 'from-green-500 to-green-600' },
    { label: '本地算力', value: '34', unit: '%', icon: Cpu, color: 'text-purple-400', bgColor: 'from-purple-500 to-purple-600' },
  ];

  const agentDefinitions = [
    { id: 'knowledge', name: '知识 Agent', model: 'Qwen2.5-1.5B', icon: FileText, color: 'from-blue-500 to-blue-600' },
    { id: 'summary', name: '摘要 Agent', model: 'Qwen2.5-1.5B', icon: PenTool, color: 'from-green-500 to-green-600' },
    { id: 'writer', name: '撰写 Agent', model: 'Qwen2.5-1.5B', icon: Eye, color: 'from-yellow-500 to-yellow-600' },
    { id: 'review', name: '评审 Agent', model: 'Phi4-mini-3.8B', icon: Scale, color: 'from-purple-500 to-purple-600' },
    { id: 'judge', name: '评委 Agent', model: 'Qwen2.5-1.5B', icon: Cloud, color: 'from-orange-500 to-orange-600' },
    { id: 'result', name: '结果 Agent', model: 'Qwen2.5-1.5B', icon: CheckCircle, color: 'from-emerald-500 to-emerald-600' },
  ];

  const getAgentStatus = (agentId: string) => {
    const step = agentSteps.find(s => s.agent_id === agentId);
    if (step) return step.success ? 'completed' : 'error';
    if (isRunning) {
      const completedCount = agentSteps.length;
      const agentIndex = agentDefinitions.findIndex(a => a.id === agentId);
      return agentIndex === completedCount ? 'processing' : 'pending';
    }
    return 'pending';
  };

  return (
    <main className="flex-1 p-6 overflow-hidden">
      <div className="h-full flex flex-col gap-6">
        
        {/* KPI指标卡片 - 顶部横向排列 */}
        <div className="grid grid-cols-4 gap-4">
          {kpiData.map((kpi, index) => {
            const Icon = kpi.icon;
            return (
              <div key={index} className="bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 p-5 shadow-xl">
                <div className="flex items-center gap-3 mb-3">
                  <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${kpi.bgColor} flex items-center justify-center shadow-lg`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <span className="text-sm text-slate-400 font-medium">{kpi.label}</span>
                </div>
                <div className="flex items-baseline gap-1">
                  <span className={`text-3xl font-bold ${kpi.color}`}>{kpi.value}</span>
                  {kpi.unit && <span className="text-lg text-slate-400">{kpi.unit}</span>}
                </div>
              </div>
            );
          })}
        </div>

        {/* 主内容区域 - 三列横向布局 */}
        <div className="flex-1 grid grid-cols-12 gap-6 min-h-0">
          
          {/* 左列：Agent状态 */}
          <div className="col-span-3 flex flex-col gap-4 min-h-0">
            {/* Agent执行状态 */}
            <div className="flex-1 bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 p-5 shadow-xl overflow-hidden flex flex-col">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-400" />
                Agent 执行状态
              </h3>
              <div className="flex-1 overflow-y-auto space-y-3">
                {agentDefinitions.map((agent, index) => {
                  const Icon = agent.icon;
                  const status = getAgentStatus(agent.id);
                  const isCompleted = status === 'completed';
                  const isProcessing = status === 'processing';
                  return (
                    <div key={agent.id} className={`p-3 rounded-xl border transition-all ${
                      isCompleted ? 'bg-green-500/10 border-green-500/30' : isProcessing ? 'bg-purple-500/10 border-purple-500/30 animate-pulse' : 'bg-slate-700/30 border-slate-600/30'
                    }`}>
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${agent.color} flex items-center justify-center`}>
                          <Icon className="w-5 h-5 text-white" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className={`text-sm font-medium ${isCompleted ? 'text-green-400' : isProcessing ? 'text-purple-400' : 'text-white'}`}>{agent.name}</span>
                          <span className="block text-xs text-slate-400">{agent.model}</span>
                        </div>
                        <span className={`text-xs px-2 py-1 rounded-full ${
                          isCompleted ? 'bg-green-500/20 text-green-400' : isProcessing ? 'bg-purple-500/20 text-purple-400' : 'bg-slate-600 text-slate-400'
                        }`}>
                          {isCompleted ? '已完成' : isProcessing ? '进行中' : '等待'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 复杂度决策 */}
            <div className="bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 p-5 shadow-xl">
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
                    <div className={`h-full transition-all duration-500 rounded-full ${complexityScore > 0.65 ? 'bg-gradient-to-r from-yellow-500 to-orange-500' : 'bg-gradient-to-r from-green-500 to-emerald-500'}`} style={{ width: complexityScore > 0 ? `${complexityScore * 100}%` : '0%' }} />
                  </div>
                  <div className="flex justify-between mt-2 text-xs text-slate-500">
                    <span>0.0</span>
                    <span className="text-slate-400">阈值: 0.65</span>
                    <span>1.0</span>
                  </div>
                </div>
                <div className={`p-4 rounded-xl border ${executedLocally ? 'bg-green-500/10 border-green-500/30' : 'bg-orange-500/10 border-orange-500/30'}`}>
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg ${executedLocally ? 'bg-gradient-to-br from-green-500 to-emerald-600' : 'bg-gradient-to-br from-orange-500 to-red-600'} flex items-center justify-center`}>
                      {executedLocally ? <CheckCircle className="w-5 h-5 text-white" /> : <Cloud className="w-5 h-5 text-white" />}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{executedLocally ? '本地模型执行' : '云端API执行'}</p>
                      <p className="text-xs text-slate-400">{executedLocally ? '使用国产算力，节省成本' : '任务复杂，调用DeepSeek'}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 中间列：任务输入 + 最终输出（最显眼） */}
          <div className="col-span-6 flex flex-col gap-4 min-h-0">
            {/* 任务输入 */}
            <div className="bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 p-5 shadow-xl">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-400" />
                任务输入
              </h3>
              <div className="space-y-4">
                <textarea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="例如：帮我写一份校园活动策划方案..."
                  className="w-full bg-slate-700/50 border border-slate-600/50 rounded-xl px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 resize-none"
                  rows={3}
                />
                <button
                  onClick={handleSubmit}
                  disabled={isRunning || !inputValue.trim()}
                  className={`flex items-center gap-3 px-8 py-3 rounded-xl font-bold transition-all shadow-lg ${
                    isRunning || !inputValue.trim()
                      ? 'bg-slate-600 text-slate-400 cursor-not-allowed'
                      : 'bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-400 hover:to-emerald-500 text-white hover:shadow-xl hover:shadow-green-500/40'
                  }`}
                >
                  {isRunning ? (
                    <>
                      <RefreshCw className="w-5 h-5 animate-spin" />
                      <span>执行中...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5 fill-current" />
                      <span>运行任务</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* 最终输出结果 - 最显眼！ */}
            <div className="flex-1 bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 shadow-xl overflow-hidden flex flex-col">
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700/50 bg-gradient-to-r from-slate-800/90 to-slate-800/50">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center shadow-lg shadow-green-500/30">
                    <FileText className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">最终输出结果</h3>
                    <p className="text-sm text-slate-400">{result ? '✅ 任务已完成' : '等待任务执行...'}</p>
                  </div>
                </div>
                {result && (
                  <span className="px-3 py-1.5 bg-green-500/20 border border-green-500/30 rounded-lg text-sm font-medium text-green-400">已完成</span>
                )}
              </div>
              <div className="flex-1 overflow-y-auto p-6">
                {result ? (
                  <ResultPreview content={result} />
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center">
                    <div className="w-20 h-20 bg-slate-700/50 rounded-2xl flex items-center justify-center mb-4">
                      <FileText className="w-10 h-10 text-slate-500" />
                    </div>
                    <h4 className="text-base font-medium text-slate-300 mb-2">暂无输出结果</h4>
                    <p className="text-sm text-slate-400">请在上方输入任务并点击"运行任务"开始</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 右列：实时日志 */}
          <div className="col-span-3 flex flex-col min-h-0">
            <div className="flex-1 bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 shadow-xl overflow-hidden flex flex-col">
              <div className="px-5 py-4 border-b border-slate-700/50">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                    <Zap className="w-5 h-5 text-blue-400" />
                    实时日志
                  </h3>
                  <span className="text-xs text-slate-400">{logs.length} 条</span>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto">
                <LogViewer logs={logs} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
