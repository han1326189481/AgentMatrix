'use client';

import { useState } from 'react';
import { Play, RefreshCw, FileText, CheckCircle, AlertCircle, TrendingUp, Clock, DollarSign, Cpu, Zap } from 'lucide-react';
import { agentService } from '@/services/api/agentService';
import LogViewer from '@/components/logs/LogViewer';
import ResultPreview from '@/components/result/ResultPreview';
import AgentStatus from './AgentStatus';
import KPIDashboard from './KPIDashboard';

export default function ContentArea() {
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
      addLog('knowledge', '📚 知识检索开始', 'info');
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

  return (
    <div className="flex-1 overflow-hidden p-6">
      <div className="max-w-7xl mx-auto h-full flex flex-col gap-6">
        
        {/* 第一行：KPI指标卡片 */}
        <KPIDashboard 
          complexityScore={complexityScore}
          executedLocally={executedLocally}
        />

        {/* 第二行：主要内容区域 */}
        <div className="flex-1 grid grid-cols-12 gap-6 min-h-0">
          
          {/* 左列：Agent状态与工作流 */}
          <div className="col-span-4 flex flex-col gap-6 min-h-0">
            <AgentStatus 
              steps={agentSteps} 
              isRunning={isRunning}
              complexityScore={complexityScore}
              executedLocally={executedLocally}
            />
          </div>

          {/* 中右列：任务输入 + 最终输出 */}
          <div className="col-span-8 flex flex-col gap-6 min-h-0">
            
            {/* 任务输入区域 */}
            <div className="bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 p-6 shadow-xl">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-xl flex items-center justify-center">
                  <FileText className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">任务输入</h3>
                  <p className="text-sm text-slate-400">请输入您要完成的任务</p>
                </div>
              </div>
              
              <div className="space-y-4">
                <textarea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="例如：帮我写一份关于校园科技节的详细策划方案，包括活动安排、预算和人员分工..."
                  className="w-full bg-slate-700/50 border border-slate-600/50 rounded-xl px-5 py-4 text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 resize-none transition-all text-base"
                  rows={4}
                />
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 text-sm text-slate-400">
                    <span>按 Enter 快速发送</span>
                  </div>
                  <button
                    onClick={handleSubmit}
                    disabled={isRunning || !inputValue.trim()}
                    className={`flex items-center gap-3 px-8 py-4 rounded-xl font-bold text-base transition-all shadow-xl ${
                      isRunning || !inputValue.trim()
                        ? 'bg-slate-600 text-slate-400 cursor-not-allowed shadow-none'
                        : 'bg-gradient-to-r from-green-500 via-emerald-500 to-green-600 hover:from-green-400 hover:via-emerald-400 hover:to-green-500 text-white hover:shadow-2xl hover:shadow-green-500/40 hover:scale-105 active:scale-95'
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
            </div>

            {/* 最终输出区域 - 最显眼的位置！ */}
            <div className="flex-1 bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 shadow-xl overflow-hidden flex flex-col min-h-0">
              <div className="flex items-center justify-between px-6 py-5 border-b border-slate-700/50 bg-gradient-to-r from-slate-800/90 to-slate-800/50">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center shadow-lg shadow-green-500/30">
                    <FileText className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-white">最终输出结果</h3>
                    <p className="text-sm text-slate-400">
                      {result ? '✅ 任务已完成，查看下方结果' : '等待任务执行...'}
                    </p>
                  </div>
                  {result && (
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-green-500/20 border border-green-500/30 rounded-lg">
                      <CheckCircle className="w-4 h-4 text-green-400" />
                      <span className="text-sm font-medium text-green-400">已完成</span>
                    </div>
                  )}
                </div>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                {result ? (
                  <div className="h-full">
                    <ResultPreview content={result} />
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center">
                    <div className="w-24 h-24 bg-slate-700/50 rounded-3xl flex items-center justify-center mb-6">
                      <FileText className="w-12 h-12 text-slate-500" />
                    </div>
                    <h4 className="text-lg font-medium text-slate-300 mb-2">暂无输出结果</h4>
                    <p className="text-slate-400">
                      请在上方输入任务并点击"运行任务"开始
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* 第三行：实时日志 */}
        <div className="bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50 shadow-xl overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700/50">
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <Zap className="w-4 h-4 text-blue-400" />
              实时日志
            </h3>
            <span className="text-xs text-slate-400">{logs.length} 条记录</span>
          </div>
          <div className="max-h-48 overflow-y-auto">
            <LogViewer logs={logs} />
          </div>
        </div>
      </div>
    </div>
  );
}
