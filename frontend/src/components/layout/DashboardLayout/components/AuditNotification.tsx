'use client';

// V3.3: 知识库质检完成弹窗
// 接收后端 audit_progress WebSocket 消息，显示进度；
// completed 后保留 3 秒自动关闭，避免打扰用户。

import { useEffect, useRef } from 'react';
import { useAuditStore } from '@/stores/auditStore';

export default function AuditNotification() {
  const { progress, visible, hide } = useAuditStore();
  const completedTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastCompletedTsRef = useRef<string>('');

  // 监听 phase 变化：completed 后 3 秒自动关闭
  useEffect(() => {
    if (!progress) return;

    if (progress.phase === 'completed' || progress.phase === 'error') {
      // 同一个 completed 时间戳只触发一次定时器
      if (progress.timestamp !== lastCompletedTsRef.current) {
        lastCompletedTsRef.current = progress.timestamp;
        // 清理之前的定时器
        if (completedTimerRef.current) {
          clearTimeout(completedTimerRef.current);
        }
        completedTimerRef.current = setTimeout(() => {
          hide();
        }, 3000);
      }
    }

    return () => {
      if (completedTimerRef.current && progress?.phase !== 'completed' && progress?.phase !== 'error') {
        clearTimeout(completedTimerRef.current);
        completedTimerRef.current = null;
      }
    };
  }, [progress, hide]);

  // 卸载时清理定时器
  useEffect(() => {
    return () => {
      if (completedTimerRef.current) {
        clearTimeout(completedTimerRef.current);
      }
    };
  }, []);

  if (!visible || !progress) return null;

  const percent = progress.total > 0
    ? Math.min(100, Math.round((progress.current / progress.total) * 100))
    : 0;

  const isCompleted = progress.phase === 'completed';
  const isError = progress.phase === 'error';
  const isProcessing = progress.phase === 'processing' || progress.phase === 'start';

  // 颜色：处理中=蓝色，完成=绿色，错误=红色
  const accentColor = isCompleted
    ? 'var(--green, #10b981)'
    : isError
      ? 'var(--red, #ef4444)'
      : 'var(--blue, #3b82f6)';

  return (
    <div
      className="audit-notification"
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        top: 20,
        right: 20,
        zIndex: 9999,
        minWidth: 320,
        maxWidth: 380,
        background: 'var(--bg-elevated, rgba(255, 255, 255, 0.98))',
        border: `1px solid ${accentColor}`,
        borderLeft: `4px solid ${accentColor}`,
        borderRadius: 8,
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15)',
        padding: '12px 16px',
        backdropFilter: 'blur(8px)',
        animation: 'auditSlideIn 0.3s ease-out',
      }}
    >
      <style>{`
        @keyframes auditSlideIn {
          from { transform: translateX(120%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        @keyframes auditPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        .audit-icon {
          display: inline-block;
          width: 18px;
          height: 18px;
          margin-right: 8px;
          vertical-align: middle;
        }
        .audit-icon-spin {
          animation: auditPulse 1.2s ease-in-out infinite;
        }
      `}</style>

      {/* 标题行 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          fontSize: 14,
          fontWeight: 600,
          color: accentColor,
          marginBottom: 6,
        }}
      >
        {isCompleted ? (
          // 完成图标（对勾）
          <svg className="audit-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        ) : isError ? (
          // 错误图标
          <svg className="audit-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
        ) : (
          // 处理中图标（盾牌+齿轮）
          <svg className="audit-icon audit-icon-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            <circle cx="12" cy="11" r="2" />
          </svg>
        )}
        <span>
          {isCompleted
            ? '知识库质检完成'
            : isError
              ? '知识库质检异常'
              : '正在质检知识库'}
        </span>
      </div>

      {/* 进度条（仅处理中显示） */}
      {isProcessing && progress.total > 0 && (
        <div
          style={{
            width: '100%',
            height: 4,
            background: 'var(--bg-muted, rgba(0, 0, 0, 0.08))',
            borderRadius: 2,
            marginBottom: 6,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${percent}%`,
              height: '100%',
              background: accentColor,
              borderRadius: 2,
              transition: 'width 0.3s ease-out',
            }}
          />
        </div>
      )}

      {/* 消息 */}
      <div
        style={{
          fontSize: 12,
          color: 'var(--text-secondary, #666)',
          marginBottom: isCompleted && progress.stats ? 6 : 0,
        }}
      >
        {progress.message}
      </div>

      {/* 统计信息（完成时显示） */}
      {isCompleted && progress.stats && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '4px 12px',
            fontSize: 11,
            color: 'var(--text-tertiary, #888)',
            marginTop: 6,
            paddingTop: 6,
            borderTop: '1px solid var(--border-subtle, rgba(0,0,0,0.06))',
          }}
        >
          {progress.stats.total !== undefined && (
            <span>总校验: {progress.stats.total}</span>
          )}
          {progress.stats.wiki_replaced !== undefined && (
            <span style={{ color: 'var(--green, #10b981)' }}>
              维基替换: {progress.stats.wiki_replaced}
            </span>
          )}
          {progress.stats.cloud_replaced !== undefined && (
            <span style={{ color: 'var(--blue, #3b82f6)' }}>
              云端替换: {progress.stats.cloud_replaced}
            </span>
          )}
          {progress.stats.removed !== undefined && (
            <span style={{ color: 'var(--orange, #f59e0b)' }}>
              删除非权威: {progress.stats.removed}
            </span>
          )}
          {progress.stats.filtered !== undefined && (
            <span>规则过滤: {progress.stats.filtered}</span>
          )}
          {progress.stats.errors !== undefined && progress.stats.errors > 0 && (
            <span style={{ color: 'var(--red, #ef4444)' }}>
              异常: {progress.stats.errors}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
