export interface WorkflowInput {
  user_input: string;
  context?: Record<string, unknown>;
}

export interface WorkflowOutput {
  final_result: string;
  steps: WorkflowStep[];
  executed_locally: boolean;
  total_duration_seconds: number;
  start_time: string;
  end_time: string;
  complexity_score?: number;
}

export interface WorkflowStep {
  agent_id: string;
  agent_name: string;
  input: string;
  output: string;
  success: boolean;
  duration_seconds: number;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export type AgentId = 'knowledge' | 'summary' | 'writer' | 'review' | 'judge' | 'result';

export const AGENT_ORDER: AgentId[] = ['knowledge', 'summary', 'writer', 'review', 'judge', 'result'];

export const AGENT_NAMES: Record<AgentId, string> = {
  knowledge: 'Knowledge Agent',
  summary: 'Summary Agent',
  writer: 'Writer Agent',
  review: 'Review Agent',
  judge: 'Judge Agent',
  result: 'Result Agent',
};

export const AGENT_MODELS: Record<AgentId, string> = {
  knowledge: 'Qwen2.5-1.5B',
  summary: 'Qwen2.5-1.5B',
  writer: 'Qwen2.5-1.5B',
  review: 'Phi4-Mini-3.8B',
  judge: 'Qwen2.5-1.5B',
  result: 'Qwen2.5-1.5B',
};

export const AGENT_EMOJIS: Record<AgentId, string> = {
  knowledge: '📄',
  summary: '✏️',
  writer: '🏆',
  review: '⚖️',
  judge: '☁️',
  result: '📋',
};

export const AGENT_COLORS: Record<AgentId, string> = {
  knowledge: 'green',
  summary: 'green',
  writer: 'gold',
  review: 'purple',
  judge: 'blue',
  result: 'green',
};

export const AGENT_ICON_CLASSES: Record<AgentId, string> = {
  knowledge: 'blue',
  summary: 'blue',
  writer: 'gold',
  review: 'purple',
  judge: 'blue',
  result: 'blue',
};

export const AGENT_DESCRIPTIONS: Record<AgentId, string> = {
  knowledge: '知识检索与增强',
  summary: '需求摘要与关键词提取',
  writer: '内容生成与文档撰写',
  review: '质量评审与评分',
  judge: '复杂度判断与路由决策',
  result: '成果导出与格式化',
};

export type AgentStatus = 'idle' | 'ready' | 'processing' | 'error' | 'completed' | 'shutdown';

export interface AgentStatusResponse {
  agent_id: string;
  name: string;
  status: string;
  current_task?: string | null;
  last_error?: string | null;
  local_model?: string;
  cloud_model?: string;
}

export interface AgentsListResponse {
  agents: Record<string, AgentStatusResponse>;
  count: number;
}

export interface Metrics {
  total_requests: number;
  local_executions: number;
  cloud_executions: number;
  api_calls: number;
  cost_saved: number;
  avg_response_time: number;
  cpu_usage: number;
  gpu_usage: number;
  total_tasks: number;
  uptime_seconds: number;
}

export interface MetricsResponse {
  system: {
    app_name: string;
    version: string;
    uptime_seconds: number;
    uptime_formatted: string;
  };
  resources: {
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
  };
  workflow: {
    total_requests: number;
    api_calls: number;
    local_executions: number;
    cloud_executions: number;
    cost_saved: number;
  };
  agents: Record<string, AgentStatusResponse>;
}

export type LogType = 'info' | 'success' | 'warning' | 'error' | 'system' | 'judge_decision';

export interface LogEntry {
  id: string;
  timestamp: Date;
  agent_id?: AgentId;
  type: LogType;
  message: string;
  metadata?: Record<string, unknown>;
}

export interface KnowledgeItem {
  keyword: string;
  content: string[];
}

export interface KnowledgeListResponse {
  knowledge_base: Record<string, string[]>;
  keywords: string[];
  stats: {
    total_keywords: number;
    total_items: number;
    average_items_per_keyword: number;
    cache_size: number;
  };
}

export interface KnowledgeSearchResponse {
  query: string;
  results: Record<string, string[]>;
  count: number;
}

export interface JudgeDecision {
  complexity_score: number;
  threshold: number;
  route: 'local' | 'cloud';
  reason: string;
}

export interface ExportRequest {
  content: string;
  format: string;
  filename?: string;
}

export interface ExportResponse {
  status: string;
  format: string;
  filename: string;
  filepath: string;
}

export interface HealthResponse {
  status: string;
  agents: Record<string, AgentStatusResponse>;
  version: string;
}

export interface ChatRequest {
  content: string;
}

export interface ChatResponse {
  response: string;
  executed_locally: boolean;
  complexity_score?: number;
  total_duration?: number;
  steps_count?: number;
}

export const COMPLEXITY_THRESHOLD = 0.65;

export type WsMessageType = 'agent_status' | 'workflow_step' | 'final_result' | 'metrics_update' | 'pong';

export interface WsMessage {
  type: WsMessageType;
  data: unknown;
}
