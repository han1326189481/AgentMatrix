// ============================================================
// AgentMatrix 前端类型定义（v1.1 — 与后端 Pydantic 模型对齐）
// 规则：全部 snake_case，与后端 JSON 字段名完全一致
// ============================================================

export interface WorkflowInput {
  user_input: string;
  context?: Record<string, unknown>;
  sandbox_id?: string;               // 沙盒ID（多沙盒隔离）
}

// 沙盒类型
export interface SandboxInfo {
  id: string;
  name: string;
  created_at?: string;
  updated_at?: string;
  message_count: number;
}

// v1.1: 补齐 partial_success / error_summary
export interface WorkflowOutput {
  final_result: string;
  steps: WorkflowStep[];
  executed_locally: boolean;
  total_duration_seconds: number;
  start_time: string;
  end_time: string;
  complexity_score?: number;
  partial_success: boolean;          // v1.1 新增：部分 Agent 失败
  error_summary?: string[];          // v1.1 新增：错误信息列表
  prompt_templates?: PromptTemplateItem[];  // V3: 提示词模板推荐
  task_steps?: TaskStep[];           // V3.1: 任务拆分步骤（取代工作流动画图）
  controller_engines?: string[];     // V3.1: CognitiveController 真实调度的引擎列表
  task_type?: string;                // V3.1: 任务类型（chat/qa/coding/writing/planning/analysis）
}

// V3.1: 任务拆分步骤（与后端 TaskStep 对齐）
export interface TaskStep {
  step_id: number;                   // 步骤序号（从 1 开始）
  title: string;                     // 任务标题（来自 plan_steps）
  agent_id: string;                  // 主导该任务的 Agent ID（knowledge/writer/result）
  agent_name: string;                // Agent 显示名称
  status: string;                    // 任务状态：pending/running/completed/error
  duration_seconds: number;          // 该步骤耗时（秒）
}

// V3: 提示词模板推荐项（与后端 PromptTemplateItem 对齐）
export interface PromptTemplateItem {
  node_id: string;                   // 模板节点 ID（如 speech_opening_009）
  title: string;                     // 模板标题
  domain: string;                    // 所属领域（如 speech.speech_opening）
  quality_score: number;             // 质量评分（0.0-1.0）
  intent_tags: string[];             // 意图标签
  reason: string;                    // 推荐理由
  // 完整模板内容（供点击后填充输入框使用）
  template_text: string;             // 完整模板文本（含 {占位符}）
  variables: PromptTemplateVariable[]; // 变量定义
  difficulty: string;                // 难度等级
}

export interface PromptTemplateVariable {
  name: string;
  description: string;
  required: boolean;
  default_value?: string;
}

// v1.1: timestamp 改为必填（后端规则 3.3 要求 ISO 8601）
export interface WorkflowStep {
  agent_id: string;
  agent_name: string;
  input: string;
  output: string;
  success: boolean;
  duration_seconds: number;
  timestamp: string;                 // v1.1: 必填
  metadata?: StepMetadata;           // v1.1: 强类型替换 Record<string, unknown>
}

// v1.1 规则 3.4: Judge 步骤 metadata 六字段
// 其他 Agent 步骤 metadata 可能包含 model_used / error / task_type_v2 / reasoning_pattern 等
export interface StepMetadata {
  // Judge Agent 专属（规则 3.4）
  decision?: 'local_output' | 'cloud_enhance';
  cloud_mode?: 'none' | 'polish' | 'full_rewrite';
  difficulty_threshold?: number;
  review_score?: number;
  executed_locally?: boolean;
  reason?: string[];
  // 通用字段
  model_used?: string;
  error?: string;
  task_type_v2?: string;
  reasoning_pattern?: string;
  content_length?: number;
  knowledge_count?: number;
  [key: string]: unknown;           // 允许后端扩展字段
}

// V3: CognitiveController PipelineDecision
export interface PipelineDecision {
  task_type: string;                 // chat/qa/coding/writing/planning/analysis
  engines: string[];                 // task/skill/decomposer/planner/cloud/reasoning/learning/recommendation
  use_cloud: boolean;
  use_learning: boolean;
  use_recommendation: boolean;
  use_reasoning: boolean;
  complexity: number;
  reason: string[];
}

export type AgentId = 'knowledge' | 'writer' | 'review' | 'judge' | 'result';

export const AGENT_ORDER: AgentId[] = ['knowledge', 'writer', 'review', 'judge', 'result'];

export const AGENT_NAMES: Record<AgentId, string> = {
  knowledge: 'Knowledge Agent',
  writer: 'Writer Agent',
  review: 'Review Agent',
  judge: 'Judge Agent',
  result: 'Result Agent',
};

// 统一颜色定义（消除 constants.tsx 的重复）
export const AGENT_COLORS: Record<AgentId, string> = {
  knowledge: 'purple',
  writer: 'blue',
  review: 'orange',
  judge: 'violet',
  result: 'green',
};

// V3: 八引擎定义（CognitiveController 可调度的引擎）
export type EngineId = 'task' | 'skill' | 'decomposer' | 'planner' | 'cloud' | 'reasoning' | 'learning' | 'recommendation';

export const ENGINE_NAMES: Record<EngineId, string> = {
  task: 'Task Engine',
  skill: 'Skill Engine',
  decomposer: 'Decomposer',
  planner: 'Local Planner',
  cloud: 'Cloud Enhance',
  reasoning: 'Reasoning Graph',
  learning: 'Learning Engine',
  recommendation: 'Knowledge Recommend',
};

export const ENGINE_DESCRIPTIONS: Record<EngineId, string> = {
  task: '任务类型分类',
  skill: '技能路径导航',
  decomposer: '问题分解（零LLM）',
  planner: '任务规划（零LLM）',
  cloud: '云端增强（DeepSeek）',
  reasoning: '推理模式匹配',
  learning: '知识自学习',
  recommendation: '个性化推荐',
};

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

// 后端 /health 返回的 agents 字段是状态对象/数组（非数量），与后端 get_all_agent_statuses() 对齐
export interface HealthResponse {
  status: string;
  agents: Record<string, unknown> | unknown[];
  version: string;
}

export interface OllamaDetectResponse {
  ollama_host: string;
  message: string;
}

// V3: WebSocket 消息类型（与后端规则五对齐 — 原生 WebSocket，非 socket.io）
// V3.2: 新增 vision_progress 类型（视觉识别进度推送）
// V3.3: 新增 audit_progress 类型（知识库质检进度推送）
// V4.1: 新增 metrics_update 类型（成本 & 缓存指标推送）
export type WebSocketMessageType = 'agent_status' | 'workflow_step' | 'final_result' | 'vision_progress' | 'audit_progress' | 'clarify_request' | 'metrics_update' | 'context_usage';

export interface WebSocketMessage {
  type: WebSocketMessageType;
  data: Record<string, unknown>;
}

// V3.2: 视觉识别进度（前端缩略图弹窗进度条）
export interface VisionProgress {
  current: number;       // 当前第几张（0=切换模型中，1..total=识别中）
  total: number;         // 总图片数
  status: string;        // 状态描述
  phase: 'switching' | 'recognizing' | 'completed' | 'error';  // 阶段（error=识别失败）
}

// 统一复杂度阈值（消除 constants.tsx 重复定义）
export const COMPLEXITY_THRESHOLD = 0.65;

// V4.1: 指标快照（WebSocket metrics_update 推送 + 轮询兜底）
export interface CacheMetrics {
  workflow_cache_hit_rate: number;
  intent_cache_hit_rate: number;
  overall_hit_rate: number;
}

export interface CostMetrics {
  estimated_cost: number;
  estimated_savings: number;
  savings_rate: number;
  avg_cost_per_workflow: number;
  total_cloud_tokens: number;
  total_local_tokens: number;
  workflow_count: number;
  local_workflow_count: number;
  cloud_workflow_count: number;
}

export interface MetricsSnapshot {
  timestamp: string;
  cache: CacheMetrics;
  cost: CostMetrics;
}

// V4.2: 上下文使用量快照
export interface ContextUsage {
  total_tokens: number;
  limit: number;
  remaining: number;
  usage_ratio: number;
  system_tokens: number;
  history_tokens: number;
  kb_tokens: number;
  user_input_tokens: number;
}
