import type { AgentId, AgentStatus, Metrics, WorkflowStep, WorkflowOutput, WsMessage } from '@/types';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

type EventHandler<T = unknown> = (data: T) => void;

interface SocketService {
  connect: () => void;
  disconnect: () => void;
  on: {
    agentStatus: (handler: EventHandler<Record<string, unknown>>) => void;
    workflowStep: (handler: EventHandler<WorkflowStep>) => void;
    finalResult: (handler: EventHandler<WorkflowOutput>) => void;
    metricsUpdate: (handler: EventHandler<Metrics>) => void;
    pong: (handler: EventHandler) => void;
    open: (handler: EventHandler) => void;
    close: (handler: EventHandler) => void;
    error: (handler: EventHandler) => void;
  };
  off: {
    agentStatus: (handler: EventHandler) => void;
    workflowStep: (handler: EventHandler) => void;
    finalResult: (handler: EventHandler) => void;
    metricsUpdate: (handler: EventHandler) => void;
    pong: (handler: EventHandler) => void;
    open: (handler: EventHandler) => void;
    close: (handler: EventHandler) => void;
    error: (handler: EventHandler) => void;
  };
  send: (message: Record<string, unknown>) => void;
  isConnected: () => boolean;
}

type EventName = 'agent_status' | 'workflow_step' | 'final_result' | 'metrics_update' | 'pong' | 'open' | 'close' | 'error';

let ws: WebSocket | null = null;
const listeners: Map<EventName, Set<EventHandler>> = new Map();

const typeToEvent: Record<string, EventName> = {
  agent_status: 'agent_status',
  workflow_step: 'workflow_step',
  final_result: 'final_result',
  metrics_update: 'metrics_update',
  pong: 'pong',
};

function addListener(event: EventName, handler: EventHandler) {
  if (!listeners.has(event)) {
    listeners.set(event, new Set());
  }
  listeners.get(event)!.add(handler);
}

function removeListener(event: EventName, handler: EventHandler) {
  listeners.get(event)?.delete(handler);
}

function emit(event: EventName, data?: unknown) {
  listeners.get(event)?.forEach((handler) => {
    try {
      handler(data);
    } catch (e) {
      console.error(`[WS] Error in handler for ${event}:`, e);
    }
  });
}

function handleMessage(event: MessageEvent) {
  try {
    const message: WsMessage = JSON.parse(event.data);
    const wsEvent = typeToEvent[message.type];
    if (wsEvent) {
      emit(wsEvent, message.data);
    }
  } catch (e) {
    console.warn('[WS] Failed to parse message:', e);
  }
}

export const socketService: SocketService = {
  connect: () => {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    ws = new WebSocket(`${WS_URL}/ws`);

    ws.onopen = () => {
      console.log('[WS] Connected to server');
      emit('open');
    };

    ws.onclose = (event) => {
      console.log('[WS] Disconnected:', event.code, event.reason);
      emit('close', { code: event.code, reason: event.reason });
    };

    ws.onerror = (event) => {
      console.warn('[WS] Connection error:', event);
      emit('error', event);
    };

    ws.onmessage = handleMessage;
  },

  disconnect: () => {
    if (ws) {
      ws.close();
      ws = null;
    }
  },

  on: {
    agentStatus: (handler) => addListener('agent_status', handler),
    workflowStep: (handler) => addListener('workflow_step', handler),
    finalResult: (handler) => addListener('final_result', handler),
    metricsUpdate: (handler) => addListener('metrics_update', handler),
    pong: (handler) => addListener('pong', handler),
    open: (handler) => addListener('open', handler),
    close: (handler) => addListener('close', handler),
    error: (handler) => addListener('error', handler),
  },

  off: {
    agentStatus: (handler) => removeListener('agent_status', handler),
    workflowStep: (handler) => removeListener('workflow_step', handler),
    finalResult: (handler) => removeListener('final_result', handler),
    metricsUpdate: (handler) => removeListener('metrics_update', handler),
    pong: (handler) => removeListener('pong', handler),
    open: (handler) => removeListener('open', handler),
    close: (handler) => removeListener('close', handler),
    error: (handler) => removeListener('error', handler),
  },

  send: (message) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    } else {
      console.warn('[WS] Cannot send, connection not open');
    }
  },

  isConnected: () => ws?.readyState === WebSocket.OPEN,
};
