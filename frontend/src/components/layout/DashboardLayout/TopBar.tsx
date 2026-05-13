'use client';

import { Zap, Brain, Cpu } from 'lucide-react';

export default function TopBar() {
  return (
    <header className="bg-slate-800/80 backdrop-blur-xl border-b border-slate-700/50 px-6 py-4 sticky top-0 z-50">
      <div className="flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-600 via-purple-600 to-cyan-600 rounded-2xl flex items-center justify-center shadow-2xl shadow-purple-500/30">
            <Zap className="w-7 h-7 text-white fill-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-white via-blue-100 to-purple-100 bg-clip-text text-transparent">
              AgentMatrix
            </h1>
            <p className="text-sm text-slate-400">多智能体动态协同平台</p>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 px-4 py-2 bg-slate-700/50 rounded-xl border border-slate-600/50">
            <Cpu className="w-5 h-5 text-purple-400" />
            <div>
              <span className="text-sm text-slate-300">本地算力</span>
              <span className="ml-2 text-lg font-bold text-purple-400">34%</span>
            </div>
          </div>
          <div className="flex items-center gap-3 px-4 py-2 bg-green-500/10 rounded-xl border border-green-500/30">
            <Brain className="w-5 h-5 text-green-400" />
            <div>
              <span className="text-sm text-green-300">6个Agent在线</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
