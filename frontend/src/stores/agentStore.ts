import { create } from 'zustand';
import type { AgentId, AgentStatus } from '@/types';
import { AGENT_NAMES, AGENT_MODELS, AGENT_DESCRIPTIONS, AGENT_ICON_CLASSES } from '@/types';

interface AgentState {
  agent_id: AgentId;
  name: string;
  status: AgentStatus;
  current_task: string | null;
  last_error: string | null;
  model: string;
  description: string;
  icon_class: string;
  enabled: boolean;
}

interface AgentStore {
  agents: Record<AgentId, AgentState>;
  selectedAgent: AgentId;
  setSelectedAgent: (agentId: AgentId) => void;
  updateAgentStatus: (agentId: AgentId, status: AgentStatus) => void;
  updateAgentTask: (agentId: AgentId, task: string | null) => void;
  toggleAgentEnabled: (agentId: AgentId) => void;
  resetAllAgents: () => void;
}

const createInitialAgent = (id: AgentId): AgentState => ({
  agent_id: id,
  name: AGENT_NAMES[id],
  status: 'idle' as AgentStatus,
  current_task: null,
  last_error: null,
  model: AGENT_MODELS[id],
  description: AGENT_DESCRIPTIONS[id],
  icon_class: AGENT_ICON_CLASSES[id],
  enabled: true,
});

const createInitialAgents = (): Record<AgentId, AgentState> => {
  const agents = {} as Record<AgentId, AgentState>;
  const ids: AgentId[] = ['knowledge', 'summary', 'writer', 'review', 'judge', 'result'];
  for (const id of ids) {
    agents[id] = createInitialAgent(id);
  }
  return agents;
};

const initialAgents = createInitialAgents();

export const useAgentStore = create<AgentStore>((set) => ({
  agents: initialAgents,
  selectedAgent: 'knowledge',

  setSelectedAgent: (agentId) => set({ selectedAgent: agentId }),

  updateAgentStatus: (agentId, status) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [agentId]: { ...state.agents[agentId], status },
      },
    })),

  updateAgentTask: (agentId, task) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [agentId]: { ...state.agents[agentId], current_task: task },
      },
    })),

  toggleAgentEnabled: (agentId) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [agentId]: {
          ...state.agents[agentId],
          enabled: !state.agents[agentId].enabled,
          status: !state.agents[agentId].enabled ? 'idle' : state.agents[agentId].status,
        },
      },
    })),

  resetAllAgents: () => set({ agents: createInitialAgents() }),
}));

export const AGENT_CONFIGS = {
  knowledge: { name: AGENT_NAMES.knowledge, model: AGENT_MODELS.knowledge, description: AGENT_DESCRIPTIONS.knowledge, icon_class: AGENT_ICON_CLASSES.knowledge },
  summary: { name: AGENT_NAMES.summary, model: AGENT_MODELS.summary, description: AGENT_DESCRIPTIONS.summary, icon_class: AGENT_ICON_CLASSES.summary },
  writer: { name: AGENT_NAMES.writer, model: AGENT_MODELS.writer, description: AGENT_DESCRIPTIONS.writer, icon_class: AGENT_ICON_CLASSES.writer },
  review: { name: AGENT_NAMES.review, model: AGENT_MODELS.review, description: AGENT_DESCRIPTIONS.review, icon_class: AGENT_ICON_CLASSES.review },
  judge: { name: AGENT_NAMES.judge, model: AGENT_MODELS.judge, description: AGENT_DESCRIPTIONS.judge, icon_class: AGENT_ICON_CLASSES.judge },
  result: { name: AGENT_NAMES.result, model: AGENT_MODELS.result, description: AGENT_DESCRIPTIONS.result, icon_class: AGENT_ICON_CLASSES.result },
};
