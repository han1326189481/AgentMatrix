'use client';

import { useEffect, useRef } from 'react';
import { ScrollText, CheckCircle, AlertCircle, XCircle, Info, ChevronDown } from 'lucide-react';

interface LogEntry {
  id: string;
  timestamp: Date;
  agent: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

interface LogViewerProps {
  logs: LogEntry[];
}

const agentConfig = {
  system: { name: '系统', color: 'text-gray-400', bgColor: 'bg-gray-500' },
  knowledge: { name: 'Knowledge', color: 'text-blue-400', bgColor: 'bg-blue-500' },
  summary: { name: '摘要 Agent', color: 'text-blue-400', bgColor: 'bg-blue-500' },
  writer: { name: '撰写 Agent', color: 'text-green-400', bgColor: 'bg-green-500' },
  review: { name: '评审 Agent', color: 'text-yellow-400', bgColor: 'bg-yellow-500' },
  judge: { name: '评委 Agent', color: 'text-purple-400', bgColor: 'bg-purple-500' },
  result: { name: '结果 Agent', color: 'text-cyan-400', bgColor: 'bg-cyan-500' },
};

export default function LogViewer({ logs }: LogViewerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const getIcon = (type: LogEntry['type']) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'warning':
        return <AlertCircle className="w-4 h-4 text-yellow-400" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Info className="w-4 h-4 text-blue-400" />;
    }
  };

  const getAgentInfo = (agent: string) => {
    return agentConfig[agent as keyof typeof agentConfig] || { name: agent, color: 'text-gray-400', bgColor: 'bg-gray-500' };
  };

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const groupedLogs = logs.reduce((acc, log) => {
    const agent = log.agent;
    if (!acc[agent]) {
      acc[agent] = [];
    }
    acc[agent].push(log);
    return acc;
  }, {} as Record<string, LogEntry[]>);

  return (
    <div className="p-4 space-y-4">
      {logs.length === 0 ? (
        <div className="text-center py-8">
          <ScrollText className="w-12 h-12 text-dark-600 mx-auto mb-3" />
          <p className="text-sm text-dark-500">等待任务执行...</p>
        </div>
      ) : (
        Object.entries(groupedLogs).map(([agent, agentLogs]) => {
          const agentInfo = getAgentInfo(agent);
          const hasSuccess = agentLogs.some(l => l.type === 'success');
          
          return (
            <div key={agent} className="bg-dark-700/50 rounded-lg border border-dark-600 overflow-hidden">
              <div className={`flex items-center justify-between px-3 py-2 ${hasSuccess ? 'bg-green-500/10 border-b border-green-500/20' : 'bg-dark-600/50 border-b border-dark-600'}`}>
                <div className="flex items-center gap-2">
                  <div className={`w-6 h-6 rounded ${agentInfo.bgColor}/30 flex items-center justify-center`}>
                    {hasSuccess ? <CheckCircle className="w-4 h-4 text-green-400" /> : <Info className="w-4 h-4 text-dark-400" />}
                  </div>
                  <span className={`text-sm font-medium ${agentInfo.color}`}>{agentInfo.name}</span>
                </div>
                <span className="text-xs text-dark-500">{agentLogs.length} 条</span>
              </div>
              
              <div className="divide-y divide-dark-600">
                {agentLogs.map((log) => (
                  <div key={log.id} className="px-3 py-2 hover:bg-dark-600/30 transition-colors">
                    <div className="flex items-start gap-2">
                      {getIcon(log.type)}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs text-dark-500 font-mono">{formatTime(log.timestamp)}</span>
                        </div>
                        <p className={`text-sm ${
                          log.type === 'success' ? 'text-green-300' : 
                          log.type === 'error' ? 'text-red-300' : 
                          log.type === 'warning' ? 'text-yellow-300' : 'text-dark-300'
                        }`}>
                          {log.message}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}