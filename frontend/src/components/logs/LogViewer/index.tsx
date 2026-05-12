import { useEffect, useRef } from 'react';
import { ScrollText, CheckCircle, AlertCircle, XCircle, Info } from 'lucide-react';

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

  const getAgentColor = (agent: string) => {
    const colors: Record<string, string> = {
      system: 'bg-gray-500',
      knowledge: 'bg-blue-500',
      summary: 'bg-green-500',
      writer: 'bg-purple-500',
      review: 'bg-yellow-500',
      judge: 'bg-red-500',
      result: 'bg-cyan-500',
    };
    return colors[agent] || 'bg-gray-500';
  };

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-dark-700">
        <div className="flex items-center gap-2">
          <ScrollText className="w-5 h-5 text-dark-400" />
          <h3 className="text-sm font-semibold text-dark-300 uppercase tracking-wider">执行日志</h3>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-2">
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-dark-500">
            <ScrollText className="w-12 h-12 mb-2 opacity-50" />
            <p className="text-sm">等待执行...</p>
          </div>
        ) : (
          logs.map((log) => (
            <div
              key={log.id}
              className="bg-dark-700/30 rounded-lg p-3 border border-dark-600"
            >
              <div className="flex items-start gap-2">
                {getIcon(log.type)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-2 h-2 rounded-full ${getAgentColor(log.agent)}`}></span>
                    <span className="text-xs font-medium text-dark-300 capitalize">{log.agent}</span>
                    <span className="text-xs text-dark-500">{formatTime(log.timestamp)}</span>
                  </div>
                  <p className="text-sm text-dark-300 break-words">{log.message}</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="p-3 border-t border-dark-700">
        <div className="flex items-center justify-between text-xs text-dark-500">
          <span>{logs.length} 条日志</span>
          <span>实时更新</span>
        </div>
      </div>
    </div>
  );
}