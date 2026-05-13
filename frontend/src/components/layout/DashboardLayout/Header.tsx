'use client';

import { Play, Zap, Brain, Cpu, Activity } from 'lucide-react';
import { useState } from 'react';
import { agentService } from '@/services/api/agentService';

interface HeaderProps {
  onTaskSubmit?: (input: string) => void;
  isRunning?: boolean;
}

export default function Header({ onTaskSubmit, isRunning = false }: HeaderProps) {
  const [taskInput, setTaskInput] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);

  const handleSubmit = async () => {
    if (!taskInput.trim() || isExecuting) return;
    
    setIsExecuting(true);
    if (onTaskSubmit) {
      onTaskSubmit(taskInput);
    }
    setIsExecuting(false);
  };

  return (
    <header className="bg-slate-800/80 backdrop-blur-xl border-b border-slate-700 px-8 py-5 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between gap-6">
          {/* Logo & Brand */}
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-600 via-purple-600 to-cyan-600 rounded-2xl flex items-center justify-center shadow-2xl shadow-purple-500/30">
              <Zap className="w-7 h-7 text-white fill-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-white via-blue-100 to-purple-100 bg-clip-text text-transparent">
                AgentMatrix
              </h1>
              <p className="text-sm text-slate-400">多智能体动态协同平台 - 国产算力优化</p>
            </div>
          </div>

          {/* Task Input Section */}
          <div className="flex-1 max-w-3xl">
            <div className="bg-slate-700/70 rounded-2xl border border-slate-600/50 flex items-center p-2 gap-3 hover:border-slate-500 transition-all">
              <div className="px-4 py-3 bg-gradient-to-r from-blue-600/20 to-purple-600/20 rounded-xl border border-blue-500/30">
                <Brain className="w-5 h-5 text-blue-400" />
              </div>
              <input
                type="text"
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                placeholder="请输入您的任务，例如：帮我写一份校园活动策划方案..."
                className="flex-1 bg-transparent px-4 py-3 text-white placeholder-slate-400 focus:outline-none text-base"
                onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
              />
              <button
                onClick={handleSubmit}
                disabled={isExecuting || !taskInput.trim()}
                className={`flex items-center gap-3 px-8 py-4 rounded-xl font-bold text-base transition-all shadow-lg ${
                  isExecuting || !taskInput.trim()
                    ? 'bg-slate-600 text-slate-400 cursor-not-allowed shadow-none'
                    : 'bg-gradient-to-r from-green-500 via-emerald-500 to-green-600 hover:from-green-400 hover:via-emerald-400 hover:to-green-500 text-white hover:shadow-2xl hover:shadow-green-500/40 hover:scale-105 active:scale-95'
                }`}
              >
                {isExecuting ? (
                  <>
                    <Activity className="w-5 h-5 animate-spin" />
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

          {/* Quick Stats */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-4 py-2 bg-slate-700/50 rounded-xl border border-slate-600/50">
              <Cpu className="w-4 h-4 text-purple-400" />
              <span className="text-sm font-medium text-slate-300">本地算力</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
