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

export interface ExportRequest {
  content: string;
  format: string;
  filename?: string;
}

export interface ExportResponse {
  status: string;
  format: string;
  filename: string;
  filepath?: string;
}

export interface HealthResponse {
  status: string;
  agents: number;
  version: string;
}

// ==================== Chat Types ====================
export interface ChatRequest {
  content: string;
  use_cloud?: boolean;
  model_name?: string;
}

export interface ChatResponse {
  response: string;
  executed_locally: boolean;
  complexity_score: number;
  total_duration: number;
  steps_count: number;
  mode: string;
  model_used?: string;
}

// ==================== Config Types ====================
export interface ConfigUpdate {
  deepseek_api_key?: string;
  ollama_host?: string;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  details?: Record<string, string>;
}

export interface ModelConfig {
  name: string;
  provider: string;
  model: string;
  api_key?: string;
  display_name?: string;
  max_tokens: number;
  temperature: number;
}

export interface ValidateKeyRequest {
  provider: string;
  api_key: string;
  model?: string;
}

export interface ValidateKeyResponse {
  success: boolean;
  message: string;
}

export interface ConfigResponse {
  ollama_host: string;
  ollama_model: string;
  deepseek_api_key_set: boolean;
  deepseek_model: string;
  models: ModelConfig[];
}

export interface OllamaDetectResponse {
  ollama_host: string;
  message: string;
}

export interface CacheStats {
  cache_size: number;
  max_size: number;
  ttl: number;
}

export interface ChatCacheStats {
  chat_cache_size: number;
  chat_cache_max_size: number;
  chat_cache_ttl: number;
  workflow_cache_size: number;
  workflow_cache_max_size: number;
  workflow_cache_ttl: number;
}

export interface KnowledgeStats {
  total_entries: number;
  total_keywords: number;
  total_size: number;
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
