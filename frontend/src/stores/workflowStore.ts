import { create } from 'zustand';
import { workflowService } from '@/services/api/agentService';
import { sandboxService } from '@/services/api/sandboxService';
import { socketService, onWorkflowStep, onFinalResult, onVisionProgress, onAuditProgress, onClarifyRequest } from '@/services/api/socketService';
import type { ConnectionStatus } from '@/services/api/socketService';
import { useErrorStore } from '@/stores/errorStore';
import { useAuditStore } from '@/stores/auditStore';
import { useClarifyStore } from '@/stores/clarifyStore';
import type { AgentId, WorkflowStep, WorkflowOutput, PipelineDecision, StepMetadata, PromptTemplateItem, TaskStep, VisionProgress } from '@/types';

interface LogEntry {
  id: string;
  timestamp: Date;
  agent: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
}

interface ChatHistory {
  user_input: string;
  response: string;
  timestamp: Date;
  // V3: 该轮对话收到的提示词模板推荐（若有则渲染为系统消息）
  prompt_templates?: PromptTemplateItem[];
  // V3.2: 该轮对话用户上传的图片缩略图（base64 data URL，仅内存保留不持久化）
  images?: string[];
}

interface WorkflowStore {
  isRunning: boolean;
  currentStep: AgentId | null;
  completedSteps: AgentId[];
  workflowSteps: WorkflowStep[];
  result: WorkflowOutput | null;
  judgeDecision: 'local' | 'cloud' | null;
  complexityScore: number;
  logs: LogEntry[];
  chatHistory: ChatHistory[];
  // V3 决策详情
  pipelineDecision: PipelineDecision | null;
  judgeMetadata: StepMetadata | null;
  // V3.1: 任务拆分步骤 + 真实引擎调度
  taskSteps: TaskStep[];
  controllerEngines: string[];
  taskType: string | null;
  // V3.2: 图片上传 + 视觉识别进度
  pendingImages: string[];                    // 待识别的图片 base64 列表（缩略图预览）
  visionProgress: VisionProgress | null;      // 视觉识别进度（null=未在识别中）
  // WebSocket 连接状态
  wsConnected: boolean;
  // 沙盒
  sandboxId: string;  // V3.5.1: 强制物理沙箱，空字符串表示未选中
  // V4.2: 上下文溢出后强制云端模式
  forceCloud: boolean;

  // Actions
  executeWorkflow: (input: string, extraContext?: Record<string, unknown>) => Promise<void>;
  addLog: (agent: string | undefined, type: LogEntry['type'], message: string) => void;
  clearLogs: () => void;
  setIsRunning: (running: boolean) => void;
  setCurrentStep: (step: AgentId | null) => void;
  setResult: (result: WorkflowOutput | null) => void;
  addCompletedStep: (agentId: AgentId) => void;
  addWorkflowStep: (step: WorkflowStep) => void;
  resetWorkflow: () => void;
  addChatHistory: (input: string, response: string, promptTemplates?: PromptTemplateItem[], images?: string[]) => void;
  clearChatHistory: () => void;
  getContext: () => string;
  initWebSocket: () => () => void;
  setPipelineDecision: (decision: PipelineDecision | null) => void;
  setJudgeMetadata: (meta: StepMetadata | null) => void;
  setTaskSteps: (steps: TaskStep[]) => void;
  setControllerEngines: (engines: string[]) => void;
  setTaskType: (taskType: string | null) => void;
  // V3.2: 图片上传 + 视觉识别进度
  addPendingImage: (base64: string) => void;       // 添加待识别图片
  removePendingImage: (index: number) => void;     // 移除指定图片
  clearPendingImages: () => void;                  // 清空待识别图片
  setVisionProgress: (progress: VisionProgress | null) => void;
  setSandboxId: (id: string) => void;
  loadSandboxHistory: (sandboxId: string) => Promise<void>;
  // V4.2: 上下文溢出后强制云端模式
  setForceCloud: (force: boolean) => void;
  // V3: 推荐开关 + 冷却期控制
  recommendEnabled: boolean;                       // 推荐总开关（默认 true）
  skipNextRecommend: boolean;                      // 跳过下一次推荐（使用模板后置 true）
  toggleRecommend: () => void;                     // 切换推荐开关
  markTemplateUsed: () => void;                    // 标记：用户使用了模板，下次跳过推荐
  consumeSkipFlag: () => boolean;                  // 消费跳过标记（返回 true 则本次跳过，并重置为 false）
}

// V3.5.1: 移除 localStorage 虚拟沙箱缓存层 — 聊天记录仅存后端物理沙箱
const CHAT_HISTORY_PREFIX = 'agentmatrix_chat_history';  // 仅用于清理旧数据
const MAX_HISTORY_SIZE = 50;

// V3.5.1: 清理旧的 default localStorage 聊天记录（一次性清理）
function cleanupLegacyDefaultHistory(): void {
  if (typeof window === 'undefined') return;
  try {
    const legacyKey = `${CHAT_HISTORY_PREFIX}_default`;
    if (localStorage.getItem(legacyKey)) {
      localStorage.removeItem(legacyKey);
    }
    // 清理所有带 sandboxId 的旧 localStorage 记录
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const key = localStorage.key(i);
      if (key && key.startsWith(CHAT_HISTORY_PREFIX)) {
        localStorage.removeItem(key);
      }
    }
  } catch {
    // ignore
  }
}

// V3.5.1: 启动时清理旧的 localStorage 虚拟沙箱数据
if (typeof window !== 'undefined') {
  cleanupLegacyDefaultHistory();
}

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  isRunning: false,
  currentStep: null,
  completedSteps: [],
  workflowSteps: [],
  result: null,
  judgeDecision: null,
  complexityScore: 0,
  logs: [],
  chatHistory: [],  // V3.5.1: 仅从后端物理沙箱加载，不再从 localStorage 读取
  pipelineDecision: null,
  judgeMetadata: null,
  taskSteps: [],
  controllerEngines: [],
  taskType: null,
  // V3.2: 图片上传 + 视觉识别进度
  pendingImages: [],
  visionProgress: null,
  wsConnected: false,
  sandboxId: '',  // V3.5.1: 空字符串表示未选中物理沙箱
  // V4.2: 上下文溢出后强制云端模式
  forceCloud: false,
  // V3: 推荐开关（默认常开，从 localStorage 读取）+ 冷却期标记
  recommendEnabled: typeof window !== 'undefined'
    ? localStorage.getItem('agentmatrix_recommend_enabled') !== 'false'
    : true,
  skipNextRecommend: false,

  setIsRunning: (running) => set({ isRunning: running }),
  setCurrentStep: (step) => set({ currentStep: step }),
  setResult: (result) => set({ result }),
  setPipelineDecision: (decision) => set({ pipelineDecision: decision }),
  setJudgeMetadata: (meta) => set({ judgeMetadata: meta }),
  setTaskSteps: (steps) => set({ taskSteps: steps }),
  setControllerEngines: (engines) => set({ controllerEngines: engines }),
  setTaskType: (taskType) => set({ taskType }),
  // V3.2: 图片上传 + 视觉识别进度
  addPendingImage: (base64) => set((state) => {
    if (state.pendingImages.length >= 9) return state;  // 最多 9 张
    return { pendingImages: [...state.pendingImages, base64] };
  }),
  removePendingImage: (index) => set((state) => ({
    pendingImages: state.pendingImages.filter((_, i) => i !== index),
  })),
  clearPendingImages: () => set({ pendingImages: [] }),
  setVisionProgress: (progress) => set({ visionProgress: progress }),
  setSandboxId: (id) => {
    set({ sandboxId: id });
  },
  // V4.2: 上下文溢出后强制云端模式
  setForceCloud: (force) => set({ forceCloud: force }),

  // V3: 推荐开关切换（持久化到 localStorage）
  toggleRecommend: () => {
    const next = !get().recommendEnabled;
    set({ recommendEnabled: next });
    if (typeof window !== 'undefined') {
      localStorage.setItem('agentmatrix_recommend_enabled', next ? 'true' : 'false');
    }
  },

  // V3: 标记用户已使用模板 → 下一次推荐跳过（避免连续推荐影响观感）
  markTemplateUsed: () => set({ skipNextRecommend: true }),

  // V3: 消费跳过标记（执行推荐前调用）
  // 返回 true 表示本次应跳过推荐，并自动重置标记为 false（再下一次恢复推荐）
  consumeSkipFlag: () => {
    const shouldSkip = get().skipNextRecommend;
    if (shouldSkip) {
      set({ skipNextRecommend: false });
    }
    return shouldSkip;
  },

  addLog: (agent, type, message) =>
    set((state) => ({
      logs: [
        ...state.logs,
        {
          id: Date.now().toString() + Math.random().toString(36).slice(2, 6),
          timestamp: new Date(),
          agent: agent || 'system',
          type,
          message,
        },
      ],
    })),

  clearLogs: () => set({ logs: [] }),

  addCompletedStep: (agentId) =>
    set((state) => ({
      completedSteps: state.completedSteps.includes(agentId)
        ? state.completedSteps
        : [...state.completedSteps, agentId],
    })),

  addWorkflowStep: (step) =>
    set((state) => {
      // 按 agent_id 去重：若该 Agent 步骤已存在则替换（HTTP 兜底补齐场景）
      const existingIdx = state.workflowSteps.findIndex((s) => s.agent_id === step.agent_id);
      const workflowSteps = existingIdx >= 0
        ? state.workflowSteps.map((s, i) => (i === existingIdx ? step : s))
        : [...state.workflowSteps, step];
      return {
        workflowSteps,
        // 实时更新当前步骤和已完成步骤
        currentStep: step.agent_id as AgentId,
        completedSteps: state.completedSteps.includes(step.agent_id as AgentId)
          ? state.completedSteps
          : [...state.completedSteps, step.agent_id as AgentId],
      };
    }),

  addChatHistory: (input, response, promptTemplates, images) => {
    const newEntry: ChatHistory = {
      user_input: input,
      response,
      timestamp: new Date(),
      // V3: 保存该轮的提示词模板推荐（若有则前端渲染为系统消息）
      prompt_templates: promptTemplates && promptTemplates.length > 0 ? promptTemplates : undefined,
      // V3.2: 保存该轮用户上传的图片缩略图（仅内存保留，不持久化到 localStorage）
      images: images && images.length > 0 ? images : undefined,
    };
    set((state) => {
      const newHistory = [...state.chatHistory, newEntry];
      // V3.5.1: 不再写入 localStorage，仅内存保留；后端负责持久化到物理沙箱
      return { chatHistory: newHistory };
    });
  },

  clearChatHistory: () => {
    // V3.5.1: 仅清空内存，后端数据由删除沙盒接口处理
    set({ chatHistory: [] });
  },

  loadSandboxHistory: async (sandboxId: string) => {
    // V3.5.1: 强制物理沙箱 — 空字符串或 'default' 不再加载任何历史
    if (!sandboxId || sandboxId === 'default') {
      set({ chatHistory: [] });
      return;
    }

    try {
      // 从后端物理沙盒加载历史
      const result = await sandboxService.getHistory(sandboxId, 50);
      if (result.messages && result.messages.length > 0) {
        // 将后端消息转换为 ChatHistory 格式（配对 user/assistant）
        const history: ChatHistory[] = [];
        let pendingUser = '';
        for (const msg of result.messages) {
          if (msg.role === 'user') {
            pendingUser = msg.content;
          } else if (msg.role === 'assistant' && pendingUser) {
            history.push({
              user_input: pendingUser,
              response: msg.content,
              timestamp: new Date(msg.timestamp || Date.now()),
            });
            pendingUser = '';
          }
        }
        set({ chatHistory: history });
        return;
      }
    } catch (e) {
      console.warn(`Failed to load sandbox history from backend: ${e}`);
    }

    // V3.5.1: 后端无数据则空（不再 fallback 到 localStorage）
    set({ chatHistory: [] });
  },

  getContext: () => {
    const { chatHistory } = get();
    if (chatHistory.length === 0) return '';
    return chatHistory
      .map((item) => `用户: ${item.user_input}\n助手: ${item.response}`)
      .join('\n\n');
  },

  resetWorkflow: () =>
    set({
      isRunning: false,
      currentStep: null,
      completedSteps: [],
      workflowSteps: [],
      result: null,
      judgeDecision: null,
      complexityScore: 0,
      logs: [],
      pipelineDecision: null,
      judgeMetadata: null,
      taskSteps: [],
      controllerEngines: [],
      taskType: null,
      visionProgress: null,
    }),

  initWebSocket: () => {
    const unsubscribers: Array<() => void> = [];

    // 订阅连接状态变化
    unsubscribers.push(
      socketService.onStatusChange((status: ConnectionStatus) => {
        if (status === 'connected') {
          set({ wsConnected: true });
        } else if (status === 'failed') {
          set({ wsConnected: false });
          // 5 次重连失败，提示用户已切换到 HTTP 模式
          useErrorStore.getState().showWarning('实时连接断开，已切换到 HTTP 模式');
        } else {
          // reconnecting
          set({ wsConnected: false });
        }
      })
    );

    // 订阅 workflow_step：实时添加步骤
    unsubscribers.push(
      onWorkflowStep((step) => {
        get().addWorkflowStep(step);
        const status = step.success ? 'success' : 'error';
        const msg = step.success
          ? `${step.agent_name}完成 (${step.duration_seconds.toFixed(1)}s)`
          : `${step.agent_name}失败: ${(step.metadata as StepMetadata)?.error || '未知错误'}`;
        get().addLog(step.agent_id, status, msg);
      })
    );

    // V3.2: 订阅 vision_progress：视觉识别进度
    unsubscribers.push(
      onVisionProgress((progress) => {
        get().setVisionProgress(progress);
      })
    );

    // V3.3: 订阅 audit_progress：知识库质检进度
    unsubscribers.push(
      onAuditProgress((progress) => {
        useAuditStore.getState().setProgress(progress);
      })
    );

    // V3.4: 订阅 clarify_request：抱怨澄清请求
    unsubscribers.push(
      onClarifyRequest((request) => {
        useClarifyStore.getState().setRequest(request);
      })
    );

    // 订阅 final_result：最终结果
    unsubscribers.push(
      onFinalResult((result) => {
        const executedLocally = result.executed_locally;
        const complexityScore = result.complexity_score || 0;
        const judgeDecision: 'local' | 'cloud' = executedLocally ? 'local' : 'cloud';

        // 提取 Judge 步骤的 metadata
        const judgeStep = result.steps.find((s) => s.agent_id === 'judge');
        if (judgeStep?.metadata) {
          get().setJudgeMetadata(judgeStep.metadata as StepMetadata);
        }

        // V3.1: 提取任务拆分步骤和真实引擎调度
        if (result.task_steps) {
          get().setTaskSteps(result.task_steps);
        }
        if (result.controller_engines) {
          get().setControllerEngines(result.controller_engines);
        }
        if (result.task_type) {
          get().setTaskType(result.task_type);
        }

        // V3.2 修复 P1-7: 若当前有视觉识别进度，延迟 2.5 秒再清空
        // 让用户看到绿色"完成"状态，避免进度条瞬间消失
        const currentVisionProgress = get().visionProgress;
        set({
          result,
          isRunning: false,
          complexityScore,
          judgeDecision,
          currentStep: null,
          // 若有进度且为 completed，保留进度条 2.5 秒；否则立即清空（error 也立即清空，避免误导）
          visionProgress: currentVisionProgress?.phase === 'completed' ? currentVisionProgress : null,
        });

        if (currentVisionProgress?.phase === 'completed') {
          setTimeout(() => {
            // 仅当进度仍是同一个完成态时才清空，避免被新的识别流程覆盖
            if (get().visionProgress === currentVisionProgress) {
              set({ visionProgress: null });
            }
          }, 2500);
        }

        get().addLog(
          'system',
          'success',
          `工作流执行完成 (${executedLocally ? '本地' : '云端'}, ${result.total_duration_seconds.toFixed(1)}s)`
        );
      })
    );

    // 建立连接
    socketService.connect();

    // 返回 cleanup 函数（供 useEffect 卸载时调用，防止 StrictMode 重复注册）
    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  },

  executeWorkflow: async (input, extraContext?) => {
    const { addLog } = get();
    // V3.2: 获取待识别图片（发送后清空待识别列表）
    const imagesToSend = [...get().pendingImages];
    set({
      isRunning: true,
      result: null,
      logs: [],
      completedSteps: [],
      workflowSteps: [],
      pipelineDecision: null,
      judgeMetadata: null,
      taskSteps: [],
      controllerEngines: [],
      taskType: null,
      visionProgress: imagesToSend.length > 0 ? { current: 0, total: imagesToSend.length, status: '准备中...', phase: 'switching' } : null,
      currentStep: 'knowledge', // 第一个 Agent
    });

    try {
      addLog('system', 'info', `开始执行工作流: ${input.slice(0, 50)}...${imagesToSend.length > 0 ? ` (+${imagesToSend.length}张图片)` : ''}`);

      // 调用后端 WorkflowService API
      // WebSocket 推送会实时更新 workflowSteps，HTTP 返回作为兜底
      // 传递最近 5 轮对话历史作为 context（上下文记忆）
      // V3: 同时传递推荐开关状态和冷却期标记
      //   - recommend_enabled: 总开关，由前端按钮控制
      //   - skip_next_recommend: 冷却期标记，使用模板后置 true，本次调用消费后重置
      const recentHistory = get().chatHistory.slice(-5).map((item) => ({
        user: item.user_input,
        assistant: item.response.slice(0, 500),
      }));
      // 消费冷却期标记：若为 true 表示本次问答应跳过推荐（并自动重置为 false）
      const skipNext = get().consumeSkipFlag();
      const context: Record<string, unknown> = {
        recommend_enabled: get().recommendEnabled,
        skip_next_recommend: skipNext,
      };
      // V4.2: 上下文溢出后强制使用云端模型
      if (get().forceCloud) {
        context.force_cloud = true;
      }
      // V3.4: 合并额外的 context（如抱怨澄清后传入的 complaint_type）
      // complaint_type 会让 Writer Agent 注入道歉+重答指令
      if (extraContext) {
        Object.assign(context, extraContext);
      }
      if (recentHistory.length > 0) {
        context.history = recentHistory;
      }
      // V3.2: 传递待识别图片（base64 列表）
      if (imagesToSend.length > 0) {
        context.images = imagesToSend;
      }
      const workflowResult = await workflowService.execute({
        user_input: input,
        context,
        sandbox_id: get().sandboxId || undefined,  // V3.5.1: 强制物理沙箱，正常情况一定有值
      });

      const finalResult = workflowResult.final_result;
      const executedLocally = workflowResult.executed_locally;
      const complexityScore = workflowResult.complexity_score || 0;
      const judgeDecision: 'local' | 'cloud' = executedLocally ? 'local' : 'cloud';

      // 提取 Judge 步骤的 metadata（决策详情）
      const judgeStep = workflowResult.steps.find((s) => s.agent_id === 'judge');
      if (judgeStep?.metadata) {
        get().setJudgeMetadata(judgeStep.metadata as StepMetadata);
      }

      // V3.1: 提取任务拆分步骤和真实引擎调度
      if (workflowResult.task_steps) {
        get().setTaskSteps(workflowResult.task_steps);
      }
      if (workflowResult.controller_engines) {
        get().setControllerEngines(workflowResult.controller_engines);
      }
      if (workflowResult.task_type) {
        get().setTaskType(workflowResult.task_type);
      }

      // HTTP 兜底：按 agent_id 去重补齐缺失步骤
      // 若 WS 已推送部分步骤，只补齐缺失的；若 WS 完全没推送，补齐全部
      const existingIds = new Set(get().workflowSteps.map((s) => s.agent_id));
      for (const step of workflowResult.steps) {
        if (!existingIds.has(step.agent_id)) {
          get().addWorkflowStep(step);
          const status = step.success ? 'success' : 'error';
          const msg = step.success
            ? `${step.agent_name}完成 (${step.duration_seconds.toFixed(1)}s)`
            : `${step.agent_name}失败: ${(step.metadata as StepMetadata)?.error || '未知错误'}`;
          addLog(step.agent_id, status, msg);
        }
      }

      set({
        result: workflowResult,
        isRunning: false,
        complexityScore,
        judgeDecision,
        currentStep: null,
        // V3.2: 清空待识别图片
        pendingImages: [],
        // V3.2 修复 P1-7: HTTP 兜底不应无条件清空 visionProgress
        // 若 WebSocket 已推送 completed 态，延迟清空由 onFinalResult 中的 setTimeout 负责
        // 此处仅清空非 completed 态（如 switching/recognizing/error）
        visionProgress: get().visionProgress?.phase === 'completed' ? get().visionProgress : null,
      });

      get().addChatHistory(input, finalResult, workflowResult.prompt_templates, imagesToSend);

      addLog(
        'system',
        'success',
        `工作流执行完成 (${executedLocally ? '本地' : '云端'}, ${workflowResult.total_duration_seconds.toFixed(1)}s)`
      );

      // 部分失败提示
      if (workflowResult.partial_success && workflowResult.error_summary?.length) {
        addLog('system', 'warning', `部分 Agent 失败: ${workflowResult.error_summary.join('; ')}`);
      }
    } catch (error) {
      addLog(
        'system',
        'error',
        `工作流执行失败: ${error instanceof Error ? error.message : '未知错误'}`
      );
      // V3.2: 失败时清空进度条状态（避免进度条卡住），但保留 pendingImages（用户可能想重试）
      set({ isRunning: false, currentStep: null, visionProgress: null });
    }
  },
}));
