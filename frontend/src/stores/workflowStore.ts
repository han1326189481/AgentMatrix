import { create } from 'zustand';
import { agentService, workflowService } from '@/services/api/agentService';
import type { AgentId, WorkflowStep, WorkflowOutput } from '@/types';

interface LogEntry {
  id: string;
  timestamp: Date;
  agent: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

interface ChatHistory {
  user_input: string;
  response: string;
  timestamp: Date;
}

interface WorkflowStore {
  isRunning: boolean;
  currentTask: string;
  currentStep: AgentId | null;
  elapsedSeconds: number;
  useMock: boolean;
  completedSteps: AgentId[];
  workflowSteps: WorkflowStep[];
  result: WorkflowOutput | null;
  judgeDecision: 'local' | 'cloud' | null;
  complexityScore: number;
  logs: LogEntry[];
  chatHistory: ChatHistory[];

  // Actions
  executeWorkflow: (input: string) => Promise<void>;
  addLog: (agent: string | undefined, type: LogEntry['type'], message: string) => void;
  clearLogs: () => void;
  setCurrentTask: (task: string) => void;
  setIsRunning: (running: boolean) => void;
  setCurrentStep: (step: AgentId | null) => void;
  setResult: (result: WorkflowOutput | null) => void;
  setJudgeDecision: (decision: 'local' | 'cloud' | null) => void;
  setComplexityScore: (score: number) => void;
  addCompletedStep: (agentId: AgentId) => void;
  addWorkflowStep: (step: WorkflowStep) => void;
  resetWorkflow: () => void;
  setUseMock: (useMock: boolean) => void;
  addChatHistory: (input: string, response: string) => void;
  clearChatHistory: () => void;
  getContext: () => string;
}

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  isRunning: false,
  currentTask: '',
  currentStep: null,
  elapsedSeconds: 0,
  useMock: false,
  completedSteps: [],
  workflowSteps: [],
  result: null,
  judgeDecision: null,
  complexityScore: 0,
  logs: [],
  chatHistory: [],

  setCurrentTask: (task) => set({ currentTask: task }),
  setIsRunning: (running) => set({ isRunning: running }),
  setCurrentStep: (step) => set({ currentStep: step }),
  setResult: (result) => set({ result }),
  setJudgeDecision: (decision) => set({ judgeDecision: decision }),
  setComplexityScore: (score) => set({ complexityScore: score }),
  setUseMock: (useMock) => set({ useMock }),

  addLog: (agent, type, message) =>
    set((state) => ({
      logs: [
        ...state.logs,
        {
          id: Date.now().toString(),
          timestamp: new Date(),
          agent: agent || 'system',
          type,
          message,
        },
      ],
    })),

  clearLogs: () => set({ logs: [] }),

  addCompletedStep: (agentId) =>
    set((state) => ({
      completedSteps: state.completedSteps.includes(agentId)
        ? state.completedSteps
        : [...state.completedSteps, agentId],
    })),

  addWorkflowStep: (step) =>
    set((state) => ({
      workflowSteps: [...state.workflowSteps, step],
    })),

  addChatHistory: (input, response) =>
    set((state) => ({
      chatHistory: [...state.chatHistory, { user_input: input, response, timestamp: new Date() }],
    })),

  clearChatHistory: () => set({ chatHistory: [] }),

  getContext: () => {
    const { chatHistory } = get();
    if (chatHistory.length === 0) return '';
    return chatHistory
      .map((item) => `用户: ${item.user_input}\n助手: ${item.response}`)
      .join('\n\n');
  },

  resetWorkflow: () =>
    set({
      isRunning: false,
      currentTask: '',
      currentStep: null,
      elapsedSeconds: 0,
      completedSteps: [],
      workflowSteps: [],
      result: null,
      judgeDecision: null,
      complexityScore: 0,
      logs: [],
      chatHistory: [],
    }),

  executeWorkflow: async (input) => {
    const { addLog } = get();
    set({ isRunning: true, result: null, logs: [], completedSteps: [], workflowSteps: [] });

    try {
      addLog('system', 'info', `开始执行工作流: ${input.slice(0, 50)}...`);

      addLog('knowledge', 'info', '知识检索开始');
      const knowledgeResult = await agentService.executeAgent('knowledge', { content: input });
      addLog('knowledge', 'success', '知识检索完成');

      addLog('summary', 'info', '需求摘要开始');
      const summaryResult = await agentService.executeAgent('summary', {
        content: knowledgeResult.content,
      });
      addLog('summary', 'success', '需求摘要完成');

      addLog('writer', 'info', '内容生成开始');
      const writerResult = await agentService.executeAgent('writer', {
        content: summaryResult.content,
      });
      addLog('writer', 'success', '内容生成完成');

      addLog('review', 'info', '质量评审开始');
      const reviewResult = await agentService.executeAgent('review', {
        content: writerResult.content,
      });
      addLog('review', 'success', `质量评审完成，评分: ${reviewResult.metadata?.score || 'N/A'}`);

      addLog('judge', 'info', '复杂度判断开始');
      const judgeResult = await agentService.executeAgent('judge', {
        content: reviewResult.content,
      });
      const executedLocally = judgeResult.metadata?.executed_locally ?? true;
      addLog(
        'judge',
        executedLocally ? 'success' : 'warning',
        `复杂度判断完成，${executedLocally ? '本地执行' : '调用云端API'}`
      );

      addLog('result', 'info', '结果生成开始');
      const resultResult = await agentService.executeAgent('result', {
        content: judgeResult.content,
        context: { writer: writerResult.content },
      });
      addLog('result', 'success', '结果生成完成');

      const finalResult = resultResult.content;

      get().addChatHistory(input, finalResult);

      set({
        result: {
          final_result: finalResult,
          steps: [],
          executed_locally: executedLocally,
          total_duration_seconds: 0,
          start_time: new Date().toISOString(),
          end_time: new Date().toISOString(),
          complexity_score: 0,
        },
        isRunning: false,
      });

      addLog('system', 'success', '工作流执行完成');
    } catch (error) {
      addLog(
        'system',
        'error',
        `工作流执行失败: ${error instanceof Error ? error.message : '未知错误'}`
      );
      set({ isRunning: false });
    }
  },
}));
