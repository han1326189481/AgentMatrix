import { Activity, Zap, Cloud, Cpu, TrendingUp, Wallet } from 'lucide-react';
import { useMetricsStore } from '@/stores/metricsStore';

export default function TopBar() {
  const { metrics } = useMetricsStore();

  const kpiCards = [
    {
      icon: Activity,
      label: 'API调用',
      value: metrics.api_calls,
      unit: '次',
      color: 'text-blue-400',
      bgColor: 'bg-blue-500/10',
    },
    {
      icon: Wallet,
      label: '成本节省',
      value: metrics.cost_saved.toFixed(2),
      unit: '元',
      color: 'text-green-400',
      bgColor: 'bg-green-500/10',
    },
    {
      icon: Zap,
      label: '响应时间',
      value: metrics.avg_response_time.toFixed(2),
      unit: '秒',
      color: 'text-yellow-400',
      bgColor: 'bg-yellow-500/10',
    },
    {
      icon: Cpu,
      label: 'CPU占用',
      value: metrics.cpu_usage.toFixed(1),
      unit: '%',
      color: 'text-purple-400',
      bgColor: 'bg-purple-500/10',
    },
    {
      icon: Cloud,
      label: 'GPU占用',
      value: metrics.gpu_usage.toFixed(1),
      unit: '%',
      color: 'text-orange-400',
      bgColor: 'bg-orange-500/10',
    },
    {
      icon: TrendingUp,
      label: '本地执行',
      value: metrics.local_executions,
      unit: '次',
      color: 'text-cyan-400',
      bgColor: 'bg-cyan-500/10',
    },
  ];

  return (
    <header className="bg-dark-800 border-b border-dark-700 px-6 py-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-green-500 rounded-lg flex items-center justify-center">
            <Zap className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">AgentMatrix</h1>
            <p className="text-sm text-dark-400">多智能体动态协同平台</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-dark-400">系统状态:</span>
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            <span className="text-sm text-green-400">运行中</span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-6 gap-4">
        {kpiCards.map((card, index) => (
          <div
            key={index}
            className={`${card.bgColor} rounded-xl p-4 border border-dark-600 hover:border-dark-500 transition-colors`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-dark-400">{card.label}</span>
              <card.icon className={`w-4 h-4 ${card.color}`} />
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-bold text-white">{card.value}</span>
              <span className="text-sm text-dark-400">{card.unit}</span>
            </div>
          </div>
        ))}
      </div>
    </header>
  );
}