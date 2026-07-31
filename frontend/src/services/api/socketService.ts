// ============================================================
// WebSocket 服务（原生 WebSocket，与后端规则五对齐）
// 消息格式：{ type: 'agent_status' | 'workflow_step' | 'final_result', data: {} }
// ============================================================

import type { WebSocketMessage, WorkflowStep, WorkflowOutput, VisionProgress } from '@/types';

type MessageHandler = (message: WebSocketMessage) => void;
type StatusHandler = (status: ConnectionStatus) => void;

// 连接状态：connected=已连接，reconnecting=重连中，failed=彻底失败（已超最大重连次数）
export type ConnectionStatus = 'connected' | 'reconnecting' | 'failed';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
const WS_PATH = '/ws';

class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: Set<MessageHandler> = new Set();
  private statusHandlers: Set<StatusHandler> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 2000;
  private isConnecting = false;
  private shouldReconnect = true;

  /** 建立连接 */
  connect(): void {
    if (this.isConnecting || this.ws?.readyState === WebSocket.OPEN) return;
    this.isConnecting = true;
    this.shouldReconnect = true;

    try {
      this.ws = new WebSocket(`${WS_URL}${WS_PATH}`);

      this.ws.onopen = () => {
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        console.log('[WebSocket] Connected');
        this.notifyStatus('connected');
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          if (message.type && message.data) {
            this.handlers.forEach((handler) => handler(message));
          }
        } catch (e) {
          console.warn('[WebSocket] Failed to parse message:', e);
        }
      };

      this.ws.onerror = (error: Event) => {
        console.warn('[WebSocket] Error:', error);
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        this.ws = null;
        console.log('[WebSocket] Disconnected');
        if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          this.notifyStatus('reconnecting');
          setTimeout(() => this.connect(), this.reconnectDelay * this.reconnectAttempts);
        } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          // 超过最大重连次数，彻底放弃
          this.notifyStatus('failed');
        }
      };
    } catch (e) {
      this.isConnecting = false;
      console.warn('[WebSocket] Connection failed:', e);
      this.notifyStatus('failed');
    }
  }

  /** 断开连接 */
  disconnect(): void {
    this.shouldReconnect = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /** 订阅消息，返回取消订阅函数 */
  subscribe(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  /** 订阅连接状态变化，返回取消订阅函数 */
  onStatusChange(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  private notifyStatus(status: ConnectionStatus): void {
    this.statusHandlers.forEach((handler) => handler(status));
  }

  /** 连接状态 */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// 单例
export const socketService = new WebSocketService();

// 便捷订阅方法（按消息类型分发）
export function onWorkflowStep(handler: (step: WorkflowStep) => void): () => void {
  return socketService.subscribe((msg) => {
    if (msg.type === 'workflow_step') {
      handler(msg.data as unknown as WorkflowStep);
    }
  });
}

export function onAgentStatus(handler: (statuses: Record<string, unknown>) => void): () => void {
  return socketService.subscribe((msg) => {
    if (msg.type === 'agent_status') {
      handler(msg.data as Record<string, unknown>);
    }
  });
}

export function onFinalResult(handler: (result: WorkflowOutput) => void): () => void {
  return socketService.subscribe((msg) => {
    if (msg.type === 'final_result') {
      handler(msg.data as unknown as WorkflowOutput);
    }
  });
}

// V3.2: 订阅视觉识别进度
export function onVisionProgress(handler: (progress: VisionProgress) => void): () => void {
  return socketService.subscribe((msg) => {
    if (msg.type === 'vision_progress') {
      handler(msg.data as unknown as VisionProgress);
    }
  });
}

// V3.3: 订阅知识库质检进度
import type { AuditProgress } from '@/stores/auditStore';
export function onAuditProgress(handler: (progress: AuditProgress) => void): () => void {
  return socketService.subscribe((msg) => {
    if (msg.type === 'audit_progress') {
      handler(msg.data as unknown as AuditProgress);
    }
  });
}

// V3.4: 订阅抱怨澄清请求
import type { ClarifyRequest } from '@/stores/clarifyStore';
export function onClarifyRequest(handler: (request: ClarifyRequest) => void): () => void {
  return socketService.subscribe((msg) => {
    if (msg.type === 'clarify_request') {
      handler(msg.data as unknown as ClarifyRequest);
    }
  });
}
