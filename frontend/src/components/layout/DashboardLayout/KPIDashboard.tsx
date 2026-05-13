'use client';

import { TrendingUp, Clock, DollarSign, Cpu, Zap } from 'lucide-react';

interface KPIDashboardProps {
  complexityScore?: number;
  executedLocally?: boolean;
}

export default function KPIDashboard({ complexityScore = 0, executedLocally = true }: KPIDashboardProps) {
  const kpiData = [
    {
      label: '复杂度评分',
      value: complexityScore > 0 ? complexityScore.toFixed(2) : '--',
      unit: '',
      icon: Zap,
      color: complexityScore > 0.65 ? 'text-orange-400' : 'text-green-400',
      bgColor: complexityScore > 0.65 ? 'from-orange-500 to-orange-600' : 'from-green-500 to-green-600',
      description: complexityScore > 0 ? (complexityScore > 0.65 ? '云端API执行' : '本地模型执行') : '等待计算'
    },
    {
      label: '响应时间',
      value: '2.3',
      unit: 's',
      icon: Clock,
      color: 'text-cyan-400',
      bgColor: 'from-cyan-500 to-cyan-600',
      description: '平均响应时间'
    },
    {
      label: '节省成本',
      value: '¥0.113',
      unit: '',
      icon: DollarSign,
      color: 'text-green-400',
      bgColor: 'from-green-500 to-green-600',
      description: '相比纯云端方案'
    },
    {
      label: '本地算力',
      value: '34',
      unit: '%',
      icon: Cpu,
      color: 'text-purple-400',
      bgColor: 'from-purple-500 to-purple-600',
      description: 'GPU利用率'
    },
  ];

  return (
    <div className="grid grid-cols-4 gap-6">
      {kpiData.map((kpi, index) => {
        const Icon = kpi.icon;
        return (
          <div 
            key={index}
            className="bg-gradient-to-br from-slate-800/90 to-slate-800/70 backdrop-blur-xl rounded-2xl border border-slate-700/50 p-6 shadow-xl hover:shadow-2xl hover:shadow-purple-500/10 hover:border-slate-600 transition-all hover:scale-[1.02]"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${kpi.bgColor} flex items-center justify-center shadow-lg`}>
                  <Icon className="w-7 h-7 text-white" />
                </div>
                <div>
                  <span className="text-sm text-slate-400 font-medium">{kpi.label}</span>
                </div>
              </div>
              {kpi.label === '复杂度评分' && (
                <div className={`px-3 py-1 rounded-lg text-xs font-semibold ${
                  complexityScore > 0.65 
                    ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' 
                    : 'bg-green-500/20 text-green-400 border border-green-500/30'
                }`}>
                  {executedLocally ? '本地' : '云端'}
                </div>
              )}
            </div>
            
            <div className="flex items-baseline gap-2 mb-2">
              <span className={`text-4xl font-bold ${kpi.color}`}>{kpi.value}</span>
              {kpi.unit && <span className="text-xl text-slate-400">{kpi.unit}</span>}
            </div>
            
            <p className="text-sm text-slate-400">{kpi.description}</p>
          </div>
        );
      })}
    </div>
  );
}
