import api from './agentService';
import type { SandboxInfo } from '@/types';

const SANDBOX_BASE = '/sandbox';

export const sandboxService = {
  async list(): Promise<SandboxInfo[]> {
    const response = await api.get<SandboxInfo[]>(SANDBOX_BASE);
    return response.data;
  },

  async create(name: string = '新对话'): Promise<SandboxInfo> {
    const response = await api.post<SandboxInfo>(SANDBOX_BASE, { name });
    return response.data;
  },

  async get(sandboxId: string): Promise<SandboxInfo> {
    const response = await api.get<SandboxInfo>(`${SANDBOX_BASE}/${sandboxId}`);
    return response.data;
  },

  async rename(sandboxId: string, name: string): Promise<void> {
    await api.put(`${SANDBOX_BASE}/${sandboxId}/rename`, { name });
  },

  async delete(sandboxId: string): Promise<void> {
    await api.delete(`${SANDBOX_BASE}/${sandboxId}`);
  },

  async getHistory(sandboxId: string, limit: number = 20): Promise<{ sandbox_id: string; messages: Array<{ id: string; role: string; content: string; timestamp: string }>; count: number }> {
    const response = await api.get(`${SANDBOX_BASE}/${sandboxId}/history`, { params: { limit } });
    return response.data;
  },
};