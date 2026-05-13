'use client';

import { FileText, PenTool, Trophy, Scale, Cloud, Download } from 'lucide-react';
import { useAgentStore, AGENT_CONFIGS } from '@/stores/agentStore';
import { useWorkflowStore } from '@/stores/workflowStore';
import { AGENT_ORDER, AGENT_EMOJIS } from '@/types';
import type { AgentId } from '@/types';
import { useState } from 'react';

const agentIconMap: Record<AgentId, typeof FileText> = {
  knowledge: FileText,
  summary: PenTool,
  writer: Trophy,
  review: Scale,
  judge: Cloud,
  result: Download,
};

function ProgressRing({ percentage, color }: { percentage: number; color: string }) {
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="progress-ring">
      <svg width="48" height="48" viewBox="0 0 48 48">
        <circle className="progress-ring-bg" cx="24" cy="24" r={radius} />
        <circle
          className="progress-ring-fill"
          cx="24"
          cy="24"
          r={radius}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <span className="progress-ring-text" style={{ color }}>{percentage}%</span>
    </div>
  );
}

function ResourceChart({ color, gradientId, pathD, fillPathD }: {
  color: string;
  gradientId: string;
  pathD: string;
  fillPathD: string;
}) {
  return (
    <svg width="100%" height="32" viewBox="0 0 240 32" preserveAspectRatio="none">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={fillPathD} fill={`url(#${gradientId})`} />
      <path d={pathD} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

export default function SidePanel() {
  const { agents } = useAgentStore();
  const { completedSteps, isRunning } = useWorkflowStore();
  const [threshold, setThreshold] = useState(0.65);

  const apiCallCount = completedSteps.includes('judge') ? 1 : 0;
  const apiCallTotal = 1;
  const apiCallPercent = apiCallTotal > 0 ? Math.round((apiCallCount / apiCallTotal) * 100) : 0;

  const costSaved = completedSteps.length > 0 ? (completedSteps.length * 0.02).toFixed(3) : '0.000';
  const costSavedPercent = completedSteps.length > 0 ? Math.min(62, completedSteps.length * 10) : 0;

  return (
    <aside className="sidebar-left">
      <div className="card animate-in delay-1">
        <div className="card-title">API调用次数</div>
        <div className="card-value">{apiCallCount} / {apiCallTotal}次</div>
        <div className="progress-ring-container">
          <ProgressRing percentage={apiCallPercent} color="var(--blue)" />
          <div style={{ flex: 1 }}>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: `${apiCallPercent}%`, background: 'var(--blue)' }} />
            </div>
          </div>
        </div>
        <div className="card-info" style={{ marginTop: 8 }}>
          <span>纯API模式基准：1次</span>
        </div>
      </div>

      <div className="card animate-in delay-2">
        <div className="card-title">预估节省成本</div>
        <div className="card-value green">¥{costSaved}</div>
        <div className="progress-ring-container">
          <ProgressRing percentage={costSavedPercent} color="var(--green)" />
          <div style={{ flex: 1 }}>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: `${costSavedPercent}%`, background: 'var(--green)' }} />
            </div>
          </div>
        </div>
        <div className="card-info" style={{ marginTop: 8 }}>
          <span>纯API成本：¥0.18</span>
          <span className="highlight green">节省{costSavedPercent}%</span>
        </div>
      </div>

      <div className="card animate-in delay-3">
        <div className="card-title">本地算力负载</div>
        <div className="stats-row">
          <div className="stat-item">
            <div className="stat-label">CPU</div>
            <div className="stat-value">34%</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">显存</div>
            <div className="stat-value">1.2GB</div>
          </div>
        </div>
        <div className="progress-ring-container">
          <ProgressRing percentage={34} color="var(--green)" />
          <div style={{ flex: 1 }}>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: '34%', background: 'var(--green)' }} />
            </div>
          </div>
        </div>
      </div>

      <div className="card animate-in delay-4">
        <div className="card-title">响应时间</div>
        <div className="card-value">2.3s</div>
        <div className="progress-ring-container">
          <ProgressRing percentage={56} color="var(--blue)" />
          <div style={{ flex: 1 }}>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: '56%', background: 'var(--blue)' }} />
            </div>
          </div>
        </div>
        <div className="card-info" style={{ marginTop: 8 }}>
          <span>纯API模式：4.1s</span>
          <span className="highlight">更快</span>
        </div>
      </div>

      <div className="card animate-in delay-5">
        <div className="agent-fleet-header">
          <span className="agent-fleet-title">Agent舰队</span>
          <span className="agent-fleet-status">全部启用</span>
        </div>

        {AGENT_ORDER.map((agentId) => {
          const agent = agents[agentId];
          const config = AGENT_CONFIGS[agentId];
          const Icon = agentIconMap[agentId];
          const isActive = agent.status === 'processing';
          const isCompleted = agent.status === 'completed';

          return (
            <div key={agentId} className="agent-item">
              <div className={`agent-icon ${config.icon_class}`}>
                <Icon size={16} />
              </div>
              <div className="agent-info">
                <div className="agent-name">{config.name}</div>
                <div className="agent-model">{config.model}</div>
                <div className="agent-desc">{config.description}</div>
              </div>
              <div className="agent-status">
                {isCompleted && (
                  <span className="status-badge completed">已完成</span>
                )}
                {isActive && (
                  <span className="status-badge working">
                    <span className="spinner" /> 工作中
                  </span>
                )}
                {!isActive && !isCompleted && (
                  <span className="status-badge idle">空闲</span>
                )}
                <div className="toggle-switch" />
              </div>
            </div>
          );
        })}
      </div>

      <div className="card animate-in delay-5">
        <div className="card-title">资源监控</div>
        <div className="resource-item">
          <div className="resource-header">
            <span className="resource-label">CPU使用率</span>
            <span className="resource-value" style={{ color: 'var(--blue)' }}>34%</span>
          </div>
          <div className="resource-chart">
            <ResourceChart
              color="var(--blue)"
              gradientId="cpuGrad"
              pathD="M0,20 Q20,18 40,22 T80,16 T120,20 T160,14 T200,18 T240,22"
              fillPathD="M0,20 Q20,18 40,22 T80,16 T120,20 T160,14 T200,18 T240,22 V32 H0 Z"
            />
          </div>
        </div>
        <div className="resource-item">
          <div className="resource-header">
            <span className="resource-label">内存占用</span>
            <span className="resource-value" style={{ color: 'var(--blue)' }}>4.2GB / 16GB</span>
          </div>
          <div className="resource-chart">
            <ResourceChart
              color="var(--green)"
              gradientId="memGrad"
              pathD="M0,16 Q30,14 60,18 T120,12 T180,16 T240,14"
              fillPathD="M0,16 Q30,14 60,18 T120,12 T180,16 T240,14 V32 H0 Z"
            />
          </div>
        </div>
        <div className="resource-item">
          <div className="resource-header">
            <span className="resource-label">显存占用</span>
            <span className="resource-value" style={{ color: 'var(--blue)' }}>1.2GB / 8GB</span>
          </div>
          <div className="resource-chart">
            <ResourceChart
              color="var(--purple)"
              gradientId="gpuGrad"
              pathD="M0,24 Q40,20 80,24 T160,18 T240,22"
              fillPathD="M0,24 Q40,20 80,24 T160,18 T240,22 V32 H0 Z"
            />
          </div>
        </div>
      </div>

      <div className="card animate-in delay-5">
        <div className="card-title">系统设置</div>
        <div className="setting-item">
          <div className="setting-label">本地模型路径</div>
          <select className="setting-input">
            <option>/models</option>
          </select>
        </div>
        <div className="setting-item">
          <div className="setting-label">API Key</div>
          <input type="password" className="setting-input" defaultValue="sk-******-******-******-demo" readOnly />
        </div>
        <div className="setting-item">
          <div className="setting-label">难度阈值 (置信度)</div>
          <div className="slider-container">
            <input
              type="range"
              className="slider"
              min={30}
              max={90}
              value={threshold * 100}
              onChange={(e) => setThreshold(Number(e.target.value) / 100)}
            />
            <div className="slider-labels">
              <span className="slider-label">0.3</span>
              <span className="slider-label">0.9</span>
            </div>
            <div className="slider-value">{threshold.toFixed(2)}</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
