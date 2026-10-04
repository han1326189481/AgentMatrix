/**
 * 自学习审批 API — 三层筛网产出的人工审批入口
 *
 * 后端路由：backend/api/v1/learning/router.py（挂载于 /api/v1/learning）
 *
 * 链路约定：
 *   Review 反馈 / 知识提取
 *     → 三层筛网（质量门槛 → 名词拆解联网核验 → 格式+权威复核）
 *     → 默认全部落 pending 待审队列
 *     → 人工在此处 approve / reject
 *     → approve 才真正写入知识图谱 / 技能书
 *
 * 说明：鉴权与 401 重试由 agentService 的 axios 实例统一处理，此处无需重复。
 */
import api from './agentService';

// ============================================================
// 类型
// ============================================================

/** 三层筛网单层判定报告 */
export interface FilterLayerReport {
  layer: number;
  name: string;
  passed: boolean;
  reasons?: string[];
  detail?: Record<string, unknown>;
}

/** 权威出处命中记录（第 2/3 层联网核验产出） */
export interface EvidenceHit {
  term?: string;
  title?: string;
  url?: string;
  domain?: string;
  tier?: number;
  tier_name?: string;
  term_matched?: boolean;
  snippet?: string;
  [key: string]: unknown;
}

export interface PendingItem {
  id: string;
  /** knowledge = 知识补丁（过筛网）；skill = 技能补丁（本地质量约束） */
  kind: string;
  status: string;
  created_at: string;
  domain: string;
  source: string;
  trigger: Record<string, unknown>;
  filter: {
    layers?: FilterLayerReport[];
    [key: string]: unknown;
  };
  evidence: EvidenceHit[];
  payload: Record<string, unknown>;
  review: Record<string, unknown>;
}

export interface PendingStats {
  pending: number;
  approved: number;
  rejected: number;
  total: number;
  knowledge_pending: number;
  skill_pending: number;
}

export interface PendingListResponse {
  total: number;
  stats: PendingStats;
  items: PendingItem[];
}

export interface ReviewActionResponse {
  ok: boolean;
  id: string;
  kind?: string;
  error?: string;
}

export interface FilterConfig {
  filter_net_enabled?: boolean;
  filter_min_quality_score?: number;
  filter_max_terms?: number;
  filter_require_tier1?: boolean;
  filter_recheck_enabled?: boolean;
  learning_auto_apply?: boolean;
  pending_dir?: string;
  error?: string;
}

export interface AuditEntry {
  timestamp?: string;
  kind?: string;
  domain?: string;
  action?: string;
  passed?: boolean;
  reasons?: string[];
  [key: string]: unknown;
}

// ============================================================
// 读取
// ============================================================

/** 待审队列列表（默认只看 pending，按时间倒序） */
export async function listPending(
  status: string = 'pending',
  kind?: string,
  limit: number = 200
): Promise<PendingListResponse> {
  const res = await api.get<PendingListResponse>('/learning/pending', {
    params: { status, kind: kind || undefined, limit },
  });
  return res.data;
}

/** 单条待审详情 */
export async function getPendingItem(itemId: string): Promise<PendingItem> {
  const res = await api.get<PendingItem>(`/learning/pending/${encodeURIComponent(itemId)}`);
  return res.data;
}

/** 筛网审计账本 */
export async function listAudit(limit: number = 100): Promise<AuditEntry[]> {
  const res = await api.get<{ items: AuditEntry[] }>('/learning/audit', { params: { limit } });
  return res.data.items || [];
}

/** 当前三层筛网参数 */
export async function getFilterConfig(): Promise<FilterConfig> {
  const res = await api.get<FilterConfig>('/learning/filter-config');
  return res.data;
}

// ============================================================
// 审批
// ============================================================

/** 审批通过 —— 真正写入知识图谱 / 技能书 */
export async function approvePendingItem(
  itemId: string,
  note: string = ''
): Promise<ReviewActionResponse> {
  const res = await api.post<ReviewActionResponse>(
    `/learning/pending/${encodeURIComponent(itemId)}/approve`,
    { note }
  );
  return res.data;
}

/** 审批拒绝 —— 归档为 rejected，不写入任何位置 */
export async function rejectPendingItem(
  itemId: string,
  note: string = ''
): Promise<ReviewActionResponse> {
  const res = await api.post<ReviewActionResponse>(
    `/learning/pending/${encodeURIComponent(itemId)}/reject`,
    { note }
  );
  return res.data;
}

export const learningService = {
  listPending,
  getPendingItem,
  listAudit,
  getFilterConfig,
  approvePendingItem,
  rejectPendingItem,
};

export default learningService;
