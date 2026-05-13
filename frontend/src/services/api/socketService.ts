import { io, Socket } from 'socket.io-client';
import type { AgentId, AgentStatus, Metrics, WorkflowStep, WorkflowOutput, LogEntry } from '@/types';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

type EventHandler<T = unknown> = (data: T) => void;

interface SocketService {
  connect: () => void;
  disconnect: () => void;
  on: {
    stepStart: (handler: EventHandler<{ agent_id: AgentId; agent_name: string }>) => void;
    stepComplete: (handler: EventHandler<WorkflowStep>) => void;
    stepError: (handler: EventHandler<{ agent_id: AgentId; error: string }>) => void;
    workflowComplete: (handler: EventHandler<WorkflowOutput>) => void;
    agentStatusUpdate: (handler: EventHandler<{ agent_id: AgentId; status: AgentStatus; task?: string }>) => void;
    metricsUpdate: (handler: EventHandler<Metrics>) => void;
    newLog: (handler: EventHandler<LogEntry>) => void;
    connect: (handler: EventHandler) => void;
    disconnect: (handler: EventHandler) => void;
  };
  off: {
    stepStart: (handler: EventHandler) => void;
    stepComplete: (handler: EventHandler) => void;
    stepError: (handler: EventHandler) => void;
    workflowComplete: (handler: EventHandler) => void;
    agentStatusUpdate: (handler: EventHandler) => void;
    metricsUpdate: (handler: EventHandler) => void;
    newLog: (handler: EventHandler) => void;
    connect: (handler: EventHandler) => void;
    disconnect: (handler: EventHandler) => void;
  };
  isConnected: () => boolean;
}

let socket: Socket | null = null;

const eventMap = {
  stepStart: 'workflow:step_start',
  stepComplete: 'workflow:step_complete',
  stepError: 'workflow:step_error',
  workflowComplete: 'workflow:complete',
  agentStatusUpdate: 'agent:status_update',
  metricsUpdate: 'metrics:update',
  newLog: 'log:new',
  connect: 'connect',
  disconnect: 'disconnect',
} as const;

export const socketService: SocketService = {
  connect: () => {
    if (socket?.connected) return;

    socket = io(WS_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 10000,
    });

    socket.on('connect', () => {
      console.log('[Socket] Connected to server');
    });

    socket.on('disconnect', (reason) => {
      console.log('[Socket] Disconnected:', reason);
    });

    socket.on('connect_error', (error) => {
      console.warn('[Socket] Connection error:', error.message);
    });
  },

  disconnect: () => {
    if (socket) {
      socket.disconnect();
      socket = null;
    }
  },

  on: {
    stepStart: (handler) => socket?.on(eventMap.stepStart, handler as (...args: unknown[]) => void),
    stepComplete: (handler) => socket?.on(eventMap.stepComplete, handler as (...args: unknown[]) => void),
    stepError: (handler) => socket?.on(eventMap.stepError, handler as (...args: unknown[]) => void),
    workflowComplete: (handler) => socket?.on(eventMap.workflowComplete, handler as (...args: unknown[]) => void),
    agentStatusUpdate: (handler) => socket?.on(eventMap.agentStatusUpdate, handler as (...args: unknown[]) => void),
    metricsUpdate: (handler) => socket?.on(eventMap.metricsUpdate, handler as (...args: unknown[]) => void),
    newLog: (handler) => socket?.on(eventMap.newLog, handler as (...args: unknown[]) => void),
    connect: (handler) => socket?.on(eventMap.connect, handler as (...args: unknown[]) => void),
    disconnect: (handler) => socket?.on(eventMap.disconnect, handler as (...args: unknown[]) => void),
  },

  off: {
    stepStart: (handler) => socket?.off(eventMap.stepStart, handler as (...args: unknown[]) => void),
    stepComplete: (handler) => socket?.off(eventMap.stepComplete, handler as (...args: unknown[]) => void),
    stepError: (handler) => socket?.off(eventMap.stepError, handler as (...args: unknown[]) => void),
    workflowComplete: (handler) => socket?.off(eventMap.workflowComplete, handler as (...args: unknown[]) => void),
    agentStatusUpdate: (handler) => socket?.off(eventMap.agentStatusUpdate, handler as (...args: unknown[]) => void),
    metricsUpdate: (handler) => socket?.off(eventMap.metricsUpdate, handler as (...args: unknown[]) => void),
    newLog: (handler) => socket?.off(eventMap.newLog, handler as (...args: unknown[]) => void),
    connect: (handler) => socket?.off(eventMap.connect, handler as (...args: unknown[]) => void),
    disconnect: (handler) => socket?.off(eventMap.disconnect, handler as (...args: unknown[]) => void),
  },

  isConnected: () => socket?.connected ?? false,
};
