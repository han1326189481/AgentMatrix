'use client';

import { useWorkflowStore } from '@/stores/workflowStore';
import { COMPLEXITY_THRESHOLD, ENGINE_NAMES, ENGINE_DESCRIPTIONS } from '@/types';
import type { EngineId, StepMetadata } from '@/types';

// V3 八引擎完整列表（按 CognitiveController 定义顺序）
const ALL_ENGINES: EngineId[] = ['task', 'skill', 'decomposer', 'planner', 'cloud', 'reasoning', 'learning', 'recommendation'];

export default function DecisionCard() {
  // V3.1: 优先使用后端真实下发的 controllerEngines（来自 CognitiveController.decision.engines）
  // 移除启发式推断（基于 score > 0.5 等条件的猜测），改为真实数据驱动
  const { complexityScore, judgeMetadata, result, controllerEngines } = useWorkflowStore();
  const score = complexityScore || 0;
  const isComplex = score >= COMPLEXITY_THRESHOLD;

  // 从 Judge metadata 提取决策详情
  const meta = judgeMetadata as StepMetadata | null;
  const decision = meta?.decision || null;
  const cloudMode = meta?.cloud_mode || null;
  const difficultyThreshold = meta?.difficulty_threshold ?? null;
  const reviewScore = meta?.review_score ?? null;
  const reasons = meta?.reason || [];

  // V3.1: 真实引擎列表 — 优先使用后端下发的 controllerEngines
  // 后端 CognitiveController.decide() 返回的 engines 列表（如 ['task','skill','decomposer','planner']）
  // 当后端未启用 controller（旧版本/降级场景）时，仅保留 task + skill 作为兜底
  const getActiveEngines = (): Set<EngineId> => {
    const active = new Set<EngineId>();
    if (!result) return active;

    if (controllerEngines && controllerEngines.length > 0) {
      // V3.1: 使用后端真实调度的引擎列表
      for (const e of controllerEngines) {
        if (ALL_ENGINES.includes(e as EngineId)) {
          active.add(e as EngineId);
        }
      }
      // 兜底：后端列表为空但 result 存在时，至少标记 task + skill
      if (active.size === 0) {
        active.add('task');
        active.add('skill');
      }
      return active;
    }

    // 兜底：后端未下发 controllerEngines 时（旧版本/降级），保留最小集合
    // 不再基于 score 启发式猜测 learning/recommendation
    active.add('task');
    active.add('skill');

    // cloud 状态仍可从 Judge metadata 可靠获取（非启发式）
    if (decision === 'cloud_enhance' || cloudMode === 'polish' || cloudMode === 'full_rewrite') {
      active.add('cloud');
    }
    return active;
  };

  const activeEngines = getActiveEngines();
  // V3.1: 标记是否为真实下发（用于 UI 显示数据来源）
  const usingRealEngines = controllerEngines && controllerEngines.length > 0;

  return (
    <div className="card animate-in delay-1">
      <div className="card-title">智能调度决策</div>

      {/* 复杂度仪表盘 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <div className="complexity-gauge" style={{ position: 'relative', width: 56, height: 56 }}>
          <svg width="56" height="56" viewBox="0 0 56 56">
            <circle cx="28" cy="28" r="24" fill="none" stroke="var(--border-color)" strokeWidth="4" />
            <circle
              cx="28" cy="28" r="24"
              fill="none"
              stroke={isComplex ? 'var(--red)' : 'var(--green)'}
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={`${2 * Math.PI * 24}`}
              strokeDashoffset={`${2 * Math.PI * 24 * (1 - score)}`}
              style={{ transform: 'rotate(-90deg)', transformOrigin: '28px 28px', transition: 'stroke-dashoffset 0.8s ease' }}
            />
          </svg>
          <span style={{
            position: 'absolute', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            fontSize: 13, fontWeight: 700,
            color: isComplex ? 'var(--red)' : 'var(--green)'
          }}>
            {complexityScore ? Math.round(score * 100) : '--'}
          </span>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
            {!complexityScore ? '待执行' : isComplex ? '云端增强' : '本地执行'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {!complexityScore ? '等待任务触发决策' : isComplex ? '高复杂度 → 启用云端算力' : '低复杂度 → 本地模型处理'}
          </div>
        </div>
      </div>

      {/* 复杂度进度条 */}
      <div style={{ position: 'relative', marginBottom: 4 }}>
        <div className="progress-bar">
          <div
            className="progress-bar-fill"
            style={{
              width: `${Math.min(100, score * 100)}%`,
              background: isComplex
                ? 'linear-gradient(90deg, var(--orange), var(--red))'
                : 'linear-gradient(90deg, var(--green), var(--blue))',
              transition: 'width 0.8s ease'
            }}
          />
        </div>
        <div
          style={{
            position: 'absolute', top: -2, left: `${COMPLEXITY_THRESHOLD * 100}%`,
            width: 2, height: 10, background: 'var(--red)',
            transform: 'translateX(-50%)', borderRadius: 1, zIndex: 1
          }}
          title={`阈值: ${COMPLEXITY_THRESHOLD}`}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginBottom: 12 }}>
        <span>0.0 简单</span>
        <span style={{ color: 'var(--red)', fontWeight: 600 }}>阈值 {COMPLEXITY_THRESHOLD}</span>
        <span>1.0 复杂</span>
      </div>

      {/* V3 决策详情：Judge metadata 六字段 */}
      {meta && (
        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: 10, marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Judge 决策详情
          </div>

          {/* decision + cloud_mode */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
            {decision && (
              <span style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 10,
                background: decision === 'cloud_enhance' ? 'rgba(245,158,11,0.15)' : 'rgba(34,197,94,0.15)',
                color: decision === 'cloud_enhance' ? 'var(--orange)' : 'var(--green)',
                fontWeight: 600
              }}>
                {decision === 'cloud_enhance' ? '☁ 云端增强' : '💻 本地输出'}
              </span>
            )}
            {cloudMode && cloudMode !== 'none' && (
              <span style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 10,
                background: 'rgba(139,92,246,0.15)', color: 'var(--purple)', fontWeight: 600
              }}>
                {cloudMode === 'polish' ? '润色' : cloudMode === 'full_rewrite' ? '完整重写' : cloudMode}
              </span>
            )}
          </div>

          {/* difficulty vs review 双值对比 */}
          {(difficultyThreshold !== null || reviewScore !== null) && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 6 }}>
              {difficultyThreshold !== null && (
                <div style={{ background: 'var(--bg-secondary)', borderRadius: 6, padding: '4px 8px' }}>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>难度阈值</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: isComplex ? 'var(--red)' : 'var(--green)' }}>
                    {difficultyThreshold.toFixed(2)}
                  </div>
                </div>
              )}
              {reviewScore !== null && (
                <div style={{ background: 'var(--bg-secondary)', borderRadius: 6, padding: '4px 8px' }}>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Review 评分</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: reviewScore >= 0.7 ? 'var(--green)' : 'var(--orange)' }}>
                    {reviewScore.toFixed(2)}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* reason 列表 */}
          {reasons.length > 0 && (
            <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.5 }}>
              {reasons.slice(0, 3).map((r, i) => (
                <div key={i} style={{ display: 'flex', gap: 4, marginBottom: 2 }}>
                  <span style={{ color: 'var(--text-muted)' }}>•</span>
                  <span>{r}</span>
                </div>
              ))}
              {reasons.length > 3 && (
                <div style={{ color: 'var(--text-muted)', fontSize: 9 }}>+{reasons.length - 3} 条更多</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* V3 引擎状态区：8 引擎开关式展示（V3.1: 数据来自后端真实调度） */}
      {result && (
        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              认知引擎调度
            </div>
            {/* V3.1: 数据来源标记 — 真实下发 vs 兜底 */}
            <span
              title={usingRealEngines ? '数据来自后端 CognitiveController 真实调度' : '后端未下发 controllerEngines，显示兜底状态'}
              style={{
                fontSize: 9, padding: '1px 6px', borderRadius: 8,
                background: usingRealEngines ? 'rgba(34,197,94,0.15)' : 'rgba(148,163,184,0.15)',
                color: usingRealEngines ? 'var(--green)' : 'var(--text-muted)',
                fontWeight: 600,
              }}
            >
              {usingRealEngines ? '● 真实调度' : '○ 兜底'}
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            {ALL_ENGINES.map((engineId) => {
              const isActive = activeEngines.has(engineId);
              return (
                <div
                  key={engineId}
                  title={ENGINE_DESCRIPTIONS[engineId]}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    padding: '3px 6px', borderRadius: 4,
                    background: isActive ? 'rgba(34,197,94,0.1)' : 'var(--bg-secondary)',
                    opacity: isActive ? 1 : 0.5,
                    fontSize: 10,
                  }}
                >
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: isActive ? 'var(--green)' : 'var(--text-muted)',
                    flexShrink: 0,
                  }} />
                  <span style={{
                    color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                    fontWeight: isActive ? 600 : 400,
                  }}>
                    {ENGINE_NAMES[engineId]}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 评估说明 */}
      <div className="card-info" style={{ marginTop: 8 }}>
        <span>六维加权评估：类别·上下文·长度·关键词·知识库·历史</span>
      </div>

      {/* 部分失败提示 */}
      {result?.partial_success && result.error_summary && (
        <div style={{
          marginTop: 8, padding: '6px 8px', borderRadius: 4,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
          fontSize: 10, color: 'var(--red)'
        }}>
          ⚠ 部分Agent失败: {result.error_summary.length} 个错误
        </div>
      )}
    </div>
  );
}
