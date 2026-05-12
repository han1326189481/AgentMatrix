import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface AgentInput {
  content: string;
  context?: Record<string, unknown>;
}

export interface AgentOutput {
  content: string;
  success: boolean;
  message?: string;
  metadata?: Record<string, unknown>;
}

export const agentService = {
  async executeAgent(agentId: string, input: AgentInput): Promise<AgentOutput> {
    const response = await api.post<AgentOutput>(`/agents/${agentId}/execute`, input);
    return response.data;
  },

  async getAllAgents() {
    const response = await api.get('/agents');
    return response.data;
  },

  async getAgentStatus(agentId: string) {
    const response = await api.get(`/agents/${agentId}`);
    return response.data;
  },

  async executeWorkflow(userInput: string) {
    const response = await api.post('/workflow/execute', { user_input: userInput });
    return response.data;
  },

  async getMetrics() {
    const response = await api.get('/metrics/dashboard');
    return response.data;
  },

  async getAgentPerformance() {
    const response = await api.get('/metrics/agent-performance');
    return response.data;
  },

  async queryKnowledge(query: string, topK: number = 5) {
    const response = await api.post('/knowledge/query', { query, top_k: topK });
    return response.data;
  },

  async exportContent(content: string, format: string = 'markdown') {
    const response = await api.post('/export', { content, format });
    return response.data;
  },
};