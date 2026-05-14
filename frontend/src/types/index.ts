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
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

export type AgentId = 'knowledge' | 'summary' | 'writer' | 'review' | 'judge' | 'result';

export const AGENT_ORDER: AgentId[] = ['knowledge', 'summary', 'writer', 'review', 'judge', 'result'];

export const AGENT_NAMES: Record<AgentId, string> = {
  knowledge: 'A 摘要 Agent',
  summary: 'B 撰写 Agent',
  writer: 'C 评审 Agent',
  review: '评委 Agent',
  judge: 'API 网关',
  result: '导出 Agent',
};

export const AGENT_MODELS: Record<AgentId, string> = {
  knowledge: 'Qwen2.5-3B',
  summary: 'Qwen2.5-7B',
  writer: 'Qwen2.5-3B',
  review: 'Qwen2.5-3B',
  judge: 'DeepSeek-V4',
  result: 'Local',
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
  knowledge: '摘要提取与关键信息',
  summary: '需求撰写与内容生成',
  writer: '难度评估与质量评审',
  review: '综合决策与路径裁定',
  judge: '云端兜底与增强生成',
  result: '结果格式化输出',
};

export type AgentStatus = 'idle' | 'ready' | 'processing' | 'error' | 'completed' | 'shutdown';

export interface AgentStatusResponse {
  agent_id: string;
  name: string;
  status: 'idle' | 'ready' | 'running' | 'shutdown';
  current_task?: string;
  last_error?: string;
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

export type LogType = 'info' | 'success' | 'warning' | 'error' | 'system' | 'judge_decision';

export interface LogEntry {
  id: string;
  timestamp: Date;
  agent_id?: AgentId;
  type: LogType;
  message: string;
  metadata?: Record<string, unknown>;
}

export interface KnowledgeEntry {
  id: string;
  content: string;
  tags: string[];
  score?: number;
}

export interface KnowledgeInput {
  content: string;
  tags: string[];
}

export interface JudgeDecision {
  complexity_score: number;
  threshold: number;
  route: 'local' | 'cloud';
  reason: string;
}

export interface ExportInput {
  content: string;
  format: 'markdown' | 'json' | 'pdf' | 'docx';
}

export interface HealthResponse {
  status: string;
  agents: number;
  version: string;
}

export interface SocketEvents {
  'workflow:step_start': (data: { agent_id: AgentId; agent_name: string }) => void;
  'workflow:step_complete': (data: WorkflowStep) => void;
  'workflow:step_error': (data: { agent_id: AgentId; error: string }) => void;
  'workflow:complete': (data: WorkflowOutput) => void;
  'agent:status_update': (data: { agent_id: AgentId; status: AgentStatus; task?: string }) => void;
  'metrics:update': (data: Metrics) => void;
  'log:new': (data: LogEntry) => void;
}

export const COMPLEXITY_THRESHOLD = 0.65;
