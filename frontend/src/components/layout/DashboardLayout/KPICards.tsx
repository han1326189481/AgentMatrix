'use client';

import { Activity, TrendingDown, Cpu, Clock } from 'lucide-react';
import { useMetricsStore } from '@/stores/metricsStore';
import { useWorkflowStore } from '@/stores/workflowStore';

function ProgressRing({ value, size = 56, strokeWidth = 4, colorClass }: { value: number; size?: number; strokeWidth?: number; colorClass: string }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;

  return (
    <svg width={size} height={size} className="progress-ring">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth={strokeWidth}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        className={`progress-ring-circle ${colorClass}`}
      />
    </svg>
  );
}

export default function KPICards() {
  const { metrics } = useMetricsStore();
  const { isRunning, completedSteps, judgeDecision } = useWorkflowStore();

  const apiPercent = metrics.total_tasks > 0 ? Math.round((metrics.api_calls / metrics.total_tasks) * 100) : 100;
  const savePercent = 62;
  const cpuPercent = metrics.cpu_usage;
  const speedPercent = 56;

  return (
    <div className="grid grid-cols-4 gap-3 px-5 py-3">
      <div className="card-dark p-3.5 flex items-center gap-4">
        <div className="relative flex-shrink-0">
          <ProgressRing value={apiPercent} colorClass="text-accent-cyan" />
          <span className="absolute inset-0 flex items-center justify-center mono-text text-[13px] font-bold text-text-primary">
            {apiPercent}%
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-[11px] text-text-tertiary mb-0.5">API调用次数</p>
          <p className="mono-text text-xl font-bold text-text-primary leading-none">{metrics.api_calls}</p>
          <p className="text-[10px] text-text-muted mt-1">纯AI模式基准：{metrics.api_calls}次</p>
        </div>
      </div>

      <div className="card-dark p-3.5 flex items-center gap-4">
        <div className="relative flex-shrink-0">
          <ProgressRing value={savePercent} colorClass="text-accent-emerald" />
          <span className="absolute inset-0 flex items-center justify-center mono-text text-[13px] font-bold text-accent-emerald">
            {savePercent}%
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-[11px] text-text-tertiary mb-0.5">预估节省成本</p>
          <p className="mono-text text-xl font-bold text-accent-emerald leading-none">¥{metrics.cost_saved.toFixed(3)}</p>
          <p className="text-[10px] text-text-muted mt-1">纯AI成本：¥{(metrics.cost_saved * 1.62).toFixed(2)}</p>
        </div>
      </div>

      <div className="card-dark p-3.5 flex items-center gap-4">
        <div className="relative flex-shrink-0">
          <ProgressRing value={cpuPercent} colorClass="text-accent-cyan" />
          <span className="absolute inset-0 flex items-center justify-center mono-text text-[13px] font-bold text-text-primary">
            {cpuPercent}%
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-[11px] text-text-tertiary mb-0.5">本地算力负载</p>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className="mono-text text-lg font-bold text-text-primary">CPU</span>
            <span className="mono-text text-sm font-semibold text-accent-cyan">{metrics.cpu_usage.toFixed(0)}%</span>
          </div>
          <p className="text-[10px] text-text-muted mt-1">显存 {(metrics.gpu_usage * 0.05).toFixed(1)}GB</p>
        </div>
      </div>

      <div className="card-dark p-3.5 flex items-center gap-4">
        <div className="relative flex-shrink-0">
          <ProgressRing value={speedPercent} colorClass="text-accent-blue" />
          <span className="absolute inset-0 flex items-center justify-center mono-text text-[13px] font-bold text-text-primary">
            {speedPercent}%
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-[11px] text-text-tertiary mb-0.5">响应时间</p>
          <p className="mono-text text-xl font-bold text-text-primary leading-none">{metrics.avg_response_time.toFixed(1)}s</p>
          <p className="text-[10px] text-text-muted mt-1">纯AI模式：{metrics.avg_response_time * 2}s</p>
        </div>
      </div>
    </div>
  );
}
