'use client';

// 自学习审批面板（三层筛网产出的人工审批入口）
//
// 设计取向 —— 「极简但可取证」：
//   自学习默认全落 pending，不自动入库。人工在这里看到的是：
//     条目类型（知识/技能）、领域、触发来源、三层筛网逐层判定、权威出处命中。
//   看到证据再决定 approve / reject —— approve 才真正写图谱。
//
// 数据来源：GET /api/v1/learning/pending、/pending/{id}、/audit、/filter-config

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  approvePendingItem,
  getFilterConfig,
  listPending,
  rejectPendingItem,
  type EvidenceHit,
  type FilterConfig,
  type FilterLayerReport,
  type PendingItem,
  type PendingStats,
} from '@/services/api/learningService';

const POLL_MS = 30000;

const EMPTY_STATS: PendingStats = {
  pending: 0,
  approved: 0,
  rejected: 0,
  total: 0,
  knowledge_pending: 0,
  skill_pending: 0,
};

/** 把任意值安全转为可展示字符串 */
function asText(v: unknown): string {
  if (v === null || v === undefined) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

/** 层级徽标配色：通过=绿，未通过=红 */
function layerColor(passed: boolean): string {
  return passed ? 'var(--green, #10b981)' : 'var(--red, #ef4444)';
}

/** 证据来源分级配色：T1 权威最高 */
function tierColor(tier: number | undefined): string {
  if (tier === 1) return 'var(--green, #10b981)';
  if (tier === 2) return 'var(--blue, #3b82f6)';
  if (tier === 3) return 'var(--orange, #f59e0b)';
  return 'var(--text-muted, #888)';
}

function kindLabel(kind: string): string {
  if (kind === 'knowledge') return '知识';
  if (kind === 'skill') return '技能';
  return kind || '未知';
}

export default function LearningApprovalPanel() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string>('');
  const [items, setItems] = useState<PendingItem[]>([]);
  const [stats, setStats] = useState<PendingStats>(EMPTY_STATS);
  const [cfg, setCfg] = useState<FilterConfig | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listPending('pending', undefined, 200);
      setItems(data.items || []);
      setStats(data.stats || EMPTY_STATS);
    } catch (e) {
      setError(e instanceof Error ? e.message : '读取待审队列失败');
    } finally {
      setLoading(false);
    }
  }, []);

  // 首次挂载拉一次，用于顶栏徽标计数
  useEffect(() => {
    void refresh();
  }, [refresh]);

  // 轮询：仅在有 pending 或面板打开时保持心跳，避免空转
  useEffect(() => {
    if (!open && stats.pending === 0) return;
    const t = setInterval(() => {
      void refresh();
    }, POLL_MS);
    return () => clearInterval(t);
  }, [open, stats.pending, refresh]);

  // 面板打开时补拉一次筛网配置（答辩取证用）
  useEffect(() => {
    if (!open || cfg) return;
    void getFilterConfig()
      .then(setCfg)
      .catch(() => setCfg(null));
  }, [open, cfg]);

  const act = useCallback(
    async (id: string, action: 'approve' | 'reject') => {
      setBusyId(id);
      setError('');
      try {
        const res =
          action === 'approve' ? await approvePendingItem(id, '') : await rejectPendingItem(id, '');
        if (!res?.ok) {
          setError(res?.error || '操作失败');
        }
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : '操作失败');
      } finally {
        setBusyId(null);
      }
    },
    [refresh]
  );

  const badge = useMemo(() => (stats.pending > 0 ? String(stats.pending) : ''), [stats.pending]);

  return (
    <>
      {/* 顶栏入口 + 待审计数徽标 */}
      <button
        className="topbar-btn"
        onClick={() => setOpen((v) => !v)}
        title="自学习待审队列"
        style={{ position: 'relative' }}
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M9 11l3 3L22 4" />
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
        </svg>
        {badge && (
          <span
            style={{
              position: 'absolute',
              top: -4,
              right: -4,
              minWidth: 16,
              height: 16,
              padding: '0 4px',
              borderRadius: 8,
              background: 'var(--orange, #f59e0b)',
              color: '#fff',
              fontSize: 10,
              lineHeight: '16px',
              fontWeight: 700,
              textAlign: 'center',
            }}
          >
            {badge}
          </span>
        )}
      </button>

      {open && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            right: 0,
            bottom: 0,
            width: 520,
            maxWidth: '92vw',
            zIndex: 9998,
            background: 'var(--bg-primary, #fff)',
            borderLeft: '1px solid var(--border-color, rgba(0,0,0,0.1))',
            boxShadow: 'var(--shadow-lg, -8px 0 24px rgba(0,0,0,0.18))',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* 头部 */}
          <div
            style={{
              padding: '12px 16px',
              borderBottom: '1px solid var(--border-color, rgba(0,0,0,0.1))',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <strong style={{ fontSize: 14, color: 'var(--text-primary)' }}>自学习待审队列</strong>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              待审 {stats.pending} · 知识 {stats.knowledge_pending} · 技能 {stats.skill_pending}
            </span>
            <div style={{ flex: 1 }} />
            <button className="topbar-btn" onClick={() => void refresh()} title="刷新">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M23 4v6h-6" />
                <path d="M1 20v-6h6" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
              </svg>
            </button>
            <button className="topbar-btn" onClick={() => setOpen(false)} title="关闭">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          {/* 筛网参数条 —— 让「内容必须过筛子」这件事可见可取证 */}
          {cfg && (
            <div
              style={{
                padding: '8px 16px',
                fontSize: 11,
                color: 'var(--text-secondary)',
                background: 'var(--bg-secondary)',
                borderBottom: '1px solid var(--border-color, rgba(0,0,0,0.08))',
                lineHeight: 1.7,
              }}
            >
              <div>
                筛网 {cfg.filter_net_enabled ? '已启用' : '已关闭'} · 质量门槛{' '}
                {cfg.filter_min_quality_score ?? '-'} · 拆解上限 {cfg.filter_max_terms ?? '-'} 词
                {cfg.filter_require_tier1 ? ' · 必须命中 T1 权威源' : ''}
                {cfg.filter_recheck_enabled ? ' · 入库前二次联网复核' : ''}
              </div>
              <div>
                入库策略 {cfg.learning_auto_apply ? '自动入库（危险）' : '全进待审，人工确认'}
              </div>
            </div>
          )}

          {error && (
            <div
              style={{
                padding: '8px 16px',
                fontSize: 12,
                color: 'var(--red, #ef4444)',
                borderBottom: '1px solid var(--border-color, rgba(0,0,0,0.08))',
              }}
            >
              {error}
            </div>
          )}

          {/* 列表 */}
          <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
            {loading && items.length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: 8 }}>加载中…</div>
            )}

            {!loading && items.length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: 8 }}>
                暂无待审条目。自学习产出会先落到这里，经你确认后才写入知识图谱 / 技能书。
              </div>
            )}

            {items.map((it) => {
              const layers: FilterLayerReport[] = it.filter?.layers || [];
              const expanded = expandedId === it.id;
              const busy = busyId === it.id;
              const payloadText = asText(it.payload);
              return (
                <div
                  key={it.id}
                  style={{
                    border: '1px solid var(--border-color, rgba(0,0,0,0.1))',
                    borderRadius: 8,
                    padding: 10,
                    marginBottom: 10,
                    background: 'var(--bg-secondary)',
                  }}
                >
                  {/* 标题行 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: '1px 6px',
                        borderRadius: 4,
                        color: '#fff',
                        background:
                          it.kind === 'knowledge'
                            ? 'var(--blue, #3b82f6)'
                            : 'var(--purple, #8b5cf6)',
                      }}
                    >
                      {kindLabel(it.kind)}
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {it.domain || 'root'}
                    </span>
                    <div style={{ flex: 1 }} />
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                      {it.created_at || ''}
                    </span>
                  </div>

                  {/* 三层筛网判定 */}
                  {layers.length > 0 && (
                    <div style={{ marginBottom: 6 }}>
                      {layers.map((L, idx) => (
                        <div
                          key={`${it.id}-layer-${idx}`}
                          style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}
                        >
                          <span style={{ color: layerColor(!!L.passed), fontWeight: 700 }}>
                            {L.passed ? '通过' : '未过'}
                          </span>{' '}
                          L{L.layer} {L.name}
                          {L.reasons && L.reasons.length > 0 && (
                            <span style={{ color: 'var(--red, #ef4444)' }}>
                              {' '}
                              — {L.reasons.join('；')}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 权威出处 */}
                  {it.evidence && it.evidence.length > 0 && (
                    <div style={{ marginBottom: 6 }}>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>
                        权威出处 {it.evidence.length} 条
                      </div>
                      {it.evidence.slice(0, 4).map((ev: EvidenceHit, i) => (
                        <div key={`${it.id}-ev-${i}`} style={{ fontSize: 11, lineHeight: 1.6 }}>
                          <span style={{ color: tierColor(ev.tier), fontWeight: 700 }}>
                            T{ev.tier ?? '-'}
                          </span>{' '}
                          {ev.url ? (
                            <a
                              href={ev.url}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: 'var(--blue, #3b82f6)' }}
                            >
                              {ev.title || ev.url}
                            </a>
                          ) : (
                            <span style={{ color: 'var(--text-secondary)' }}>
                              {ev.title || ev.domain || '-'}
                            </span>
                          )}
                          {ev.term ? (
                            <span style={{ color: 'var(--text-muted)' }}> · 核验词「{ev.term}」</span>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 载荷预览 */}
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--text-secondary)',
                      background: 'var(--bg-tertiary)',
                      borderRadius: 6,
                      padding: 8,
                      maxHeight: expanded ? 260 : 62,
                      overflow: 'hidden',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {payloadText}
                  </div>

                  {/* 操作行 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                    <button
                      onClick={() => setExpandedId(expanded ? null : it.id)}
                      style={{
                        fontSize: 11,
                        padding: '3px 8px',
                        borderRadius: 4,
                        border: '1px solid var(--border-color, rgba(0,0,0,0.15))',
                        background: 'transparent',
                        color: 'var(--text-secondary)',
                        cursor: 'pointer',
                      }}
                    >
                      {expanded ? '收起' : '展开全文'}
                    </button>
                    <div style={{ flex: 1 }} />
                    <button
                      disabled={busy}
                      onClick={() => void act(it.id, 'reject')}
                      style={{
                        fontSize: 11,
                        padding: '3px 10px',
                        borderRadius: 4,
                        border: '1px solid var(--red, #ef4444)',
                        background: 'transparent',
                        color: 'var(--red, #ef4444)',
                        cursor: busy ? 'not-allowed' : 'pointer',
                        opacity: busy ? 0.5 : 1,
                      }}
                    >
                      拒绝
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => void act(it.id, 'approve')}
                      style={{
                        fontSize: 11,
                        padding: '3px 10px',
                        borderRadius: 4,
                        border: '1px solid var(--green, #10b981)',
                        background: 'var(--green, #10b981)',
                        color: '#fff',
                        cursor: busy ? 'not-allowed' : 'pointer',
                        opacity: busy ? 0.5 : 1,
                      }}
                    >
                      {busy ? '处理中…' : '通过并入库'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
