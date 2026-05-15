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
  knowledge: 'Knowledge Agent',
  summary: 'A摘要Agent',
  writer: 'B撰写Agent',
  review: 'Review Agent',
  judge: 'Judge Agent',
  result: 'Result Agent',
};

export const AGENT_MODELS: Record<AgentId, string> = {
  knowledge: 'Qwen2.5-3B',
  summary: 'Qwen2.5-3B',
  writer: 'Qwen2.5-7B',
  review: 'Qwen2.5-3B',
  judge: 'Qwen2.5-3B',
  result: 'Local',
};

export const AGENT_EMOJIS: Record<AgentId, string> = {
  knowledge: '📚',
  summary: '📝',
  writer: '✍️',
  review: '🔍',
  judge: '⚖️',
  result: '📋',
};

export const AGENT_COLORS: Record<AgentId, string> = {
  knowledge: 'purple',
  summary: 'emerald',
  writer: 'blue',
  review: 'orange',
  judge: 'violet',
  result: 'green',
};

export const AGENT_ICON_CLASSES: Record<AgentId, string> = {
  knowledge: 'purple',
  summary: 'emerald',
  writer: 'blue',
  review: 'orange',
  judge: 'violet',
  result: 'blue',
};

export const AGENT_DESCRIPTIONS: Record<AgentId, string> = {
  knowledge: '知识库检索与上下文增强',
  summary: '需求摘要与关键信息提取',
  writer: '内容生成与初稿撰写',
  review: '质量评估与修改建议生成',
  judge: '最终决策与路径选择',
  result: '成果导出与格式化',
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
