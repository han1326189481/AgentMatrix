import { useState } from 'react';
import { Send, Play, RefreshCw, FileDown, MessageSquare } from 'lucide-react';
import { useWorkflowStore } from '@/stores/workflowStore';
import WorkflowCanvas from '@/components/workflow/WorkflowCanvas';
import LogViewer from '@/components/logs/LogViewer';
import ResultPreview from '@/components/result/ResultPreview';

export default function MainContent() {
  const [inputValue, setInputValue] = useState('');
  const { isRunning, executeWorkflow, logs, result } = useWorkflowStore();

  const handleSubmit = async () => {
    if (!inputValue.trim() || isRunning) return;
    await executeWorkflow(inputValue);
    setInputValue('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <main className="flex-1 flex flex-col overflow-hidden">
      <div className="p-6 border-b border-dark-700 bg-dark-800/50">
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <MessageSquare className="w-5 h-5 text-blue-400" />
              <h2 className="text-lg font-semibold text-white">工作流控制台</h2>
            </div>
            <p className="text-sm text-dark-400">输入您的需求，AgentMatrix将自动执行多智能体协同工作流</p>
          </div>
          <button
            onClick={handleSubmit}
            disabled={isRunning || !inputValue.trim()}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
              isRunning || !inputValue.trim()
                ? 'bg-dark-600 text-dark-400 cursor-not-allowed'
                : 'bg-blue-500 hover:bg-blue-600 text-white'
            }`}
          >
            {isRunning ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                执行中...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                执行工作流
              </>
            )}
          </button>
        </div>

        <div className="mt-4 bg-dark-700/50 rounded-xl border border-dark-600">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="请输入您的需求，例如：生成一个校园AI助手方案..."
            className="w-full bg-transparent p-4 text-white placeholder-dark-400 resize-none focus:outline-none"
            rows={3}
          />
          <div className="flex items-center justify-between px-4 py-2 border-t border-dark-600">
            <span className="text-xs text-dark-400">Shift + Enter 换行</span>
            <button
              onClick={handleSubmit}
              disabled={isRunning || !inputValue.trim()}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                isRunning || !inputValue.trim()
                  ? 'bg-dark-600 text-dark-400'
                  : 'bg-blue-500 hover:bg-blue-600 text-white'
              }`}
            >
              <Send className="w-4 h-4" />
              发送
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-dark-300 uppercase tracking-wider mb-4">工作流动画</h3>
            <WorkflowCanvas />
          </div>

          {result && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-dark-300 uppercase tracking-wider">执行结果</h3>
                <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-700 hover:bg-dark-600 text-sm text-dark-300 transition-colors">
                  <FileDown className="w-4 h-4" />
                  导出
                </button>
              </div>
              <ResultPreview content={result} />
            </div>
          )}
        </div>

        <div className="w-96 border-l border-dark-700 bg-dark-800/30">
          <LogViewer logs={logs} />
        </div>
      </div>
    </main>
  );
}