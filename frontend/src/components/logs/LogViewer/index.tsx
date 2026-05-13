'use client';

import { Terminal, Filter, ChevronDown, Brain, FileText, PenTool, Eye, Scale, Cloud } from 'lucide-react';
import { useWorkflowStore } from '@/stores/workflowStore';
import type { AgentId, LogType } from '@/types';
import { useState } from 'react';

const agentIcons: Record<AgentId | 'system', typeof Brain> = {
  knowledge: Brain,
  summary: FileText,
  writer: PenTool,
  review: Eye,
  judge: Scale,
  result: Cloud,
  system: Terminal,
};

const logTypeConfig: Record<LogType, { label: string; colorClass: string }> = {
  info: { label: 'INFO', colorClass: 'text-accent-cyan' },
  success: { label: 'SUCCESS', colorClass: 'text-accent-emerald' },
  warning: { label: 'WARN', colorClass: 'text-accent-amber' },
  error: { label: 'ERROR', colorClass: 'text-accent-red' },
  system: { label: 'SYSTEM', colorClass: 'text-accent-purple' },
  judge_decision: { label: 'JUDGE', colorClass: 'text-accent-amber' },
};

export default function LogViewer() {
  const { logs } = useWorkflowStore();
  const [filter, setFilter] = useState<LogType | 'all'>('all');

  const filteredLogs = filter === 'all'
    ? logs
    : logs.filter((log) => log.type === filter);

  return (
    <div className="card-dark flex flex-col h-full">
      <div className="px-4 py-3 border-b border-border-default flex items-center justify-between flex-shrink-0">
        <h3 className="section-title">运行日志</h3>
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-text-muted" />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as LogType | 'all')}
            className="bg-transparent text-[11px] text-text-secondary outline-none cursor-pointer"
          >
            <option value="all">全部</option>
            <option value="info">信息</option>
            <option value="success">成功</option>
            <option value="warning">警告</option>
            <option value="error">错误</option>
          </select>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-1 font-mono">
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Terminal className="w-8 h-8 text-text-muted opacity-40 mb-2" />
            <p className="text-[12px] text-text-muted">暂无日志记录</p>
          </div>
        ) : (
          filteredLogs.map((log) => {
            const Icon = agentIcons[log.agent_id || 'system'] || Terminal;
            const typeConfig = logTypeConfig[log.type];
            const timeStr = new Date(log.timestamp).toLocaleTimeString('zh-CN', {
              hour12: false,
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              fractionalSecondDigits: 3,
            });

            return (
              <div key={log.id} className="group hover:bg-dark-tertiary/50 rounded-lg px-3 py-2 transition-colors -mx-1.5">
                <div className="flex items-start gap-2.5">
                  <span className="text-[10px] text-text-muted mt-0.5 w-[72px] flex-shrink-0">{timeStr}</span>
                  <Icon className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${log.agent_id ? (typeConfig.colorClass) : 'text-text-muted'}`} />
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0 ${typeConfig.colorClass} bg-current/10`}>
                    {typeConfig.label}
                  </span>
                  <p className="text-[12px] text-text-secondary leading-relaxed break-all">{log.message}</p>
                </div>
                {log.agent_id && (
                  <div className="ml-[130px] mt-1 pl-2 border-l-2 border-border-default/50">
                    <span className="text-[10px] text-text-muted">[{log.agent_id}]</span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {logs.length > 0 && (
        <div className="px-4 py-2.5 border-t border-border-default flex-shrink-0">
          <button className="w-full text-center text-[11px] text-accent-cyan hover:text-white transition-colors flex items-center justify-center gap-1.5">
            <ChevronDown className="w-3.5 h-3.5" />
            加载更多日志
          </button>
        </div>
      )}
    </div>
  );
}
