import { create } from 'zustand';
import { agentService } from '@/services/api/agentService';

interface LogEntry {
  id: string;
  timestamp: Date;
  agent: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

interface WorkflowStore {
  isRunning: boolean;
  logs: LogEntry[];
  result: string | null;
  executedLocally: boolean;
  executeWorkflow: (input: string) => Promise<void>;
  addLog: (agent: string, type: LogEntry['type'], message: string) => void;
  clearLogs: () => void;
}

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  isRunning: false,
  logs: [],
  result: null,
  executedLocally: true,

  addLog: (agent, type, message) =>
    set((state) => ({
      logs: [
        ...state.logs,
        {
          id: Date.now().toString(),
          timestamp: new Date(),
          agent,
          type,
          message,
        },
      ],
    })),

  clearLogs: () => set({ logs: [] }),

  executeWorkflow: async (input) => {
    const { addLog } = get();
    set({ isRunning: true, result: null, logs: [] });

    try {
      addLog('system', 'info', `开始执行工作流: ${input.slice(0, 50)}...`);

      addLog('knowledge', 'info', '知识检索开始');
      const knowledgeResult = await agentService.executeAgent('knowledge', { content: input });
      addLog('knowledge', 'success', '知识检索完成');

      addLog('summary', 'info', '需求摘要开始');
      const summaryResult = await agentService.executeAgent('summary', { content: knowledgeResult.content });
      addLog('summary', 'success', '需求摘要完成');

      addLog('writer', 'info', '内容生成开始');
      const writerResult = await agentService.executeAgent('writer', { content: summaryResult.content });
      addLog('writer', 'success', '内容生成完成');

      addLog('review', 'info', '质量评审开始');
      const reviewResult = await agentService.executeAgent('review', { content: writerResult.content });
      addLog('review', 'success', `质量评审完成，评分: ${reviewResult.metadata?.score || 'N/A'}`);

      addLog('judge', 'info', '复杂度判断开始');
      const judgeResult = await agentService.executeAgent('judge', { content: reviewResult.content });
      const executedLocally = judgeResult.metadata?.executed_locally ?? true;
      addLog('judge', executedLocally ? 'success' : 'warning', 
             `复杂度判断完成，${executedLocally ? '本地执行' : '调用云端API'}`);

      addLog('result', 'info', '结果生成开始');
      const resultResult = await agentService.executeAgent('result', { 
        content: judgeResult.content,
        context: { writer: writerResult.content }
      });
      addLog('result', 'success', '结果生成完成');

      set({ 
        result: resultResult.content,
        executedLocally,
        isRunning: false 
      });

      addLog('system', 'success', '工作流执行完成');

    } catch (error) {
      addLog('system', 'error', `工作流执行失败: ${error instanceof Error ? error.message : '未知错误'}`);
      set({ isRunning: false });
    }
  },
}));