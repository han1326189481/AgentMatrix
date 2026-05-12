export interface Agent {
  agent_id: string;
  name: string;
  status: 'idle' | 'ready' | 'processing' | 'error' | 'shutdown';
  current_task: string | null;
  last_error: string | null;
}

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

export interface WorkflowStep {
  agent: string;
  output: AgentOutput;
}

export interface WorkflowResult {
  final_result: string;
  steps: WorkflowStep[];
  executed_locally: boolean;
  total_time: number;
}

export interface Metrics {
  api_calls: number;
  cost_saved: number;
  avg_response_time: number;
  cpu_usage: number;
  gpu_usage: number;
  local_executions: number;
  cloud_executions: number;
}

export interface LogEntry {
  id: string;
  timestamp: Date;
  agent: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

export interface KnowledgeEntry {
  id: string;
  content: string;
  score: number;
  category: string;
}