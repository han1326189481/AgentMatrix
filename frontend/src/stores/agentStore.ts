import { create } from 'zustand';

interface AgentState {
  agent_id: string;
  name: string;
  status: 'idle' | 'ready' | 'processing' | 'error' | 'shutdown';
  current_task: string | null;
  last_error: string | null;
}

interface AgentStore {
  agents: Record<string, AgentState>;
  selectedAgent: string;
  setSelectedAgent: (agentId: string) => void;
  updateAgentStatus: (agentId: string, status: AgentState['status']) => void;
  updateAgentTask: (agentId: string, task: string | null) => void;
  initializeAgents: () => void;
}

const initialAgents: Record<string, AgentState> = {
  knowledge: {
    agent_id: 'knowledge',
    name: 'Knowledge Agent',
    status: 'ready',
    current_task: null,
    last_error: null,
  },
  summary: {
    agent_id: 'summary',
    name: 'Summary Agent',
    status: 'ready',
    current_task: null,
    last_error: null,
  },
  writer: {
    agent_id: 'writer',
    name: 'Writer Agent',
    status: 'ready',
    current_task: null,
    last_error: null,
  },
  review: {
    agent_id: 'review',
    name: 'Review Agent',
    status: 'ready',
    current_task: null,
    last_error: null,
  },
  judge: {
    agent_id: 'judge',
    name: 'Judge Agent',
    status: 'ready',
    current_task: null,
    last_error: null,
  },
  result: {
    agent_id: 'result',
    name: 'Result Agent',
    status: 'ready',
    current_task: null,
    last_error: null,
  },
};

export const useAgentStore = create<AgentStore>((set) => ({
  agents: initialAgents,
  selectedAgent: 'knowledge',

  setSelectedAgent: (agentId) => set({ selectedAgent: agentId }),

  updateAgentStatus: (agentId, status) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [agentId]: {
          ...state.agents[agentId],
          status,
        },
      },
    })),

  updateAgentTask: (agentId, task) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [agentId]: {
          ...state.agents[agentId],
          current_task: task,
        },
      },
    })),

  initializeAgents: () => set({ agents: initialAgents }),
}));