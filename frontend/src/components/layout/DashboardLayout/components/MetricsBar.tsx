'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { socketService } from '@/services/api/socketService';
import type { MetricsSnapshot } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface MetricsBarProps {
  /** 是否紧凑模式（topbar 中显示） */
  compact?: boolean;
}

/** 单指标卡片 */
const MetricCard: React.FC<{
  label: string;
  value: string;
  sub?: string;
  color?: 'green' | 'yellow' | 'red' | 'gray';
}> = ({ label, value, sub, color = 'gray' }) => (
  <div className="metrics-card" title={sub ? `${label}: ${sub}` : label}>
    <span className={`metrics-value metrics-value--${color}`}>{value}</span>
    <span className="metrics-label">{label}</span>
  </div>
);

/** 环状进度条 */
const RingProgress: React.FC<{ rate: number; size?: number }> = ({ rate, size = 32 }) => {
  const clamped = Math.max(0, Math.min(1, rate));
  const circumference = 2 * Math.PI * (size / 2 - 3);
  const offset = circumference * (1 - clamped);
  const color = clamped >= 0.7 ? '#22c55e' : clamped >= 0.4 ? '#eab308' : '#ef4444';

  return (
    <svg width={size} height={size} className="ring-progress">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={size / 2 - 3}
        fill="none"
        stroke="var(--metrics-ring-bg, #333)"
        strokeWidth="2.5"
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={size / 2 - 3}
        fill="none"
        stroke={color}
        strokeWidth="2.5"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 0.5s ease' }}
      />
    </svg>
  );
};

const MetricsBar: React.FC<MetricsBarProps> = ({ compact = true }) => {
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  // 从后端拉取最新指标（HTTP 轮询兜底）
  const fetchMetrics = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/metrics`);
      if (!res.ok) return;
      const data = await res.json();
      const snapshot: MetricsSnapshot = {
        timestamp: new Date().toISOString(),
        cache: data.cache || { overall_hit_rate: 0, workflow_cache_hit_rate: 0, intent_cache_hit_rate: 0 },
        cost: data.cost || {
          estimated_cost: 0,
          estimated_savings: 0,
          savings_rate: 0,
          avg_cost_per_workflow: 0,
          total_cloud_tokens: 0,
          total_local_tokens: 0,
          workflow_count: 0,
          local_workflow_count: 0,
          cloud_workflow_count: 0,
        },
      };
      setMetrics(snapshot);
      setLoading(false);
    } catch {
      // 静默失败
    }
  }, []);

  useEffect(() => {
    // 初始拉取
    fetchMetrics();

    // WebSocket 实时更新
    const unsub = socketService.subscribe((msg) => {
      if (msg.type === 'metrics_update') {
        setMetrics(msg.data as unknown as MetricsSnapshot);
        setLoading(false);
      }
    });

    // HTTP 轮询兜底（每 30 秒）
    const interval = setInterval(fetchMetrics, 30000);

    return () => {
      unsub();
      clearInterval(interval);
    };
  }, [fetchMetrics]);

  if (compact) {
    // 紧凑模式：topbar 中横排显示
    const cacheRate = metrics?.cache?.overall_hit_rate ?? 0;
    const savingsRate = metrics?.cost?.savings_rate ?? 0;
    const cost = metrics?.cost?.estimated_cost ?? 0;
    const savings = metrics?.cost?.estimated_savings ?? 0;

    return (
      <div className="metrics-bar metrics-bar--compact">
        {/* 缓存命中率 */}
        <div className="metrics-card" title={`缓存命中率: ${(cacheRate * 100).toFixed(0)}% (${metrics?.cache?.workflow_cache_hit_rate ? ((metrics.cache.workflow_cache_hit_rate * 100).toFixed(0) + '%') : '0%'})`}>
          <RingProgress rate={cacheRate} size={28} />
          <span className="metrics-label">命中</span>
        </div>

        {/* 预计成本 */}
        <MetricCard
          label="云端模型花费"
          value={`¥${cost.toFixed(4)}`}
          color={cost > 0.01 ? 'yellow' : 'gray'}
        />

        {/* 本地节省 */}
        <MetricCard
          label="本地节省"
          value={`¥${savings.toFixed(4)}`}
          sub={`节省率 ${(savingsRate * 100).toFixed(0)}%`}
          color={savings > 0 ? 'green' : 'gray'}
        />

        {/* 累计执行次数 */}
        <MetricCard
          label="执行"
          value={`${metrics?.cost?.workflow_count ?? 0}`}
          sub={`本地 ${metrics?.cost?.local_workflow_count ?? 0} / 云端 ${metrics?.cost?.cloud_workflow_count ?? 0}`}
          color="gray"
        />
      </div>
    );
  }

  // 展开模式（预留）
  if (loading) {
    return <div className="metrics-bar metrics-bar--loading">加载中...</div>;
  }

  return (
    <div className="metrics-bar metrics-bar--expanded">
      <div className="metrics-section">
        <h4 className="metrics-section-title">缓存命中率</h4>
        <div className="metrics-row">
          <div className="metrics-ring-wrap">
            <RingProgress rate={metrics?.cache?.overall_hit_rate ?? 0} size={64} />
            <span className="metrics-ring-label">
              {((metrics?.cache?.overall_hit_rate ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
          <div className="metrics-detail">
            <span>Workflow: {((metrics?.cache?.workflow_cache_hit_rate ?? 0) * 100).toFixed(0)}%</span>
            <span>Intent: {((metrics?.cache?.intent_cache_hit_rate ?? 0) * 100).toFixed(0)}%</span>
          </div>
        </div>
      </div>
      <div className="metrics-section">
        <h4 className="metrics-section-title">成本统计</h4>
        <div className="metrics-detail">
          <span>实际花费: ¥{metrics?.cost?.estimated_cost.toFixed(6) ?? '0.00'}</span>
          <span>本地节省: ¥{metrics?.cost?.estimated_savings.toFixed(6) ?? '0.00'}</span>
          <span>节省率: {((metrics?.cost?.savings_rate ?? 0) * 100).toFixed(1)}%</span>
          <span>平均/次: ¥{metrics?.cost?.avg_cost_per_workflow.toFixed(6) ?? '0.00'}</span>
        </div>
      </div>
    </div>
  );
};

export default MetricsBar;