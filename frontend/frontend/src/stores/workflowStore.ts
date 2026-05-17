import { create } from 'zustand';
import type { AgentId, LogEntry, LogType, WorkflowOutput, WorkflowStep } from '@/types';
import { AGENT_ORDER, AGENT_NAMES } from '@/types';

interface WorkflowStore {
  isRunning: boolean;
  currentStep: AgentId | null;
  completedSteps: AgentId[];
  workflowSteps: WorkflowStep[];
  result: WorkflowOutput | null;
  judgeDecision: 'local' | 'cloud' | null;
  complexityScore: number | null;
  logs: LogEntry[];
  currentTask: string | null;
  elapsedSeconds: number;
  timerRef: ReturnType<typeof setInterval> | null;
  useMock: boolean;
  setIsRunning: (running: boolean) => void;
  setCurrentStep: (step: AgentId | null) => void;
  addCompletedStep: (step: AgentId) => void;
  addWorkflowStep: (step: WorkflowStep) => void;
  addLog: (agent: AgentId | undefined, type: LogType, message: string) => void;
  setResult: (result: WorkflowOutput) => void;
  setJudgeDecision: (decision: 'local' | 'cloud') => void;
  setComplexityScore: (score: number | null) => void;
  setCurrentTask: (task: string | null) => void;
  setUseMock: (useMock: boolean) => void;
  resetWorkflow: () => void;
  applyWorkflowOutput: (output: WorkflowOutput) => void;
}

const initialState = {
  isRunning: false,
  currentStep: null as AgentId | null,
  completedSteps: [] as AgentId[],
  workflowSteps: [] as WorkflowStep[],
  result: null as WorkflowOutput | null,
  judgeDecision: null as 'local' | 'cloud' | null,
  complexityScore: null as number | null,
  logs: [] as LogEntry[],
  currentTask: null as string | null,
  elapsedSeconds: 0,
  timerRef: null as ReturnType<typeof setInterval> | null,
  useMock: false,
};

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  ...initialState,

  setIsRunning: (running) => set((state) => {
    if (running && !state.isRunning) {
      const timer = setInterval(() => {
        set((s) => ({ elapsedSeconds: s.elapsedSeconds + 1 }));
      }, 1000);
      return { isRunning: true, timerRef: timer };
    }
    if (!running && state.isRunning && state.timerRef) {
      clearInterval(state.timerRef);
    }
    return { isRunning: false, timerRef: null };
  }),

  setCurrentStep: (step) => set({ currentStep: step }),

  addCompletedStep: (step) =>
    set((state) => ({
      completedSteps: [...new Set([...state.completedSteps, step])],
    })),

  addWorkflowStep: (step) =>
    set((state) => ({
      workflowSteps: [...state.workflowSteps, step],
    })),

  addLog: (agent, type, message) =>
    set((state) => ({
      logs: [
        ...state.logs,
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
          timestamp: new Date(),
          agent_id: agent,
          type,
          message,
        },
      ],
    })),

  setResult: (result) => set({ result }),

  setJudgeDecision: (decision) => set({ judgeDecision: decision }),

  setComplexityScore: (score) => set({ complexityScore: score }),

  setCurrentTask: (task) => set({ currentTask: task }),

  setUseMock: (useMock) => set({ useMock }),

  resetWorkflow: () => {
    const state = get();
    if (state.timerRef) {
      clearInterval(state.timerRef);
    }
    set(initialState);
  },

  applyWorkflowOutput: (output: WorkflowOutput) => {
    const state = get();

    const completedAgentIds: AgentId[] = [];
    const workflowSteps: WorkflowStep[] = [];

    for (const step of output.steps) {
      const agentId = AGENT_ORDER.find(
        (id) => step.agent_id === id || step.agent_name.includes(AGENT_NAMES[id])
      );
      if (agentId) {
        completedAgentIds.push(agentId);
      }
      workflowSteps.push(step);
    }

    let judgeDecision: 'local' | 'cloud' | null = null;
    if (output.complexity_score !== undefined) {
      judgeDecision = output.complexity_score >= 0.65 ? 'cloud' : 'local';
    }

    if (state.timerRef) {
      clearInterval(state.timerRef);
    }

    set({
      result: output,
      completedSteps: [...new Set([...state.completedSteps, ...completedAgentIds])],
      workflowSteps: [...state.workflowSteps, ...workflowSteps],
      judgeDecision: judgeDecision ?? state.judgeDecision,
      complexityScore: output.complexity_score ?? state.complexityScore,
      isRunning: false,
      currentStep: null,
      timerRef: null,
    });
  },
}));
