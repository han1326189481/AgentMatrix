'use client';

// V3.4: 抱怨澄清弹窗
// 当用户触发抱怨机制后，后端生成2-5个澄清问题推送到前端
// 弹窗显示在输入框上方，每个问题有2个系统猜测方向供用户选择
// 用户也可以在输入框中自行输入理解和想法
// 提交后，系统会将用户的选择+自定义输入作为新的上下文重新回答

import { useState, useEffect, useRef } from 'react';
import { useClarifyStore, type ClarifyQuestion } from '@/stores/clarifyStore';
import { useWorkflowStore } from '@/stores/workflowStore';

export default function ClarifyNotification() {
  const {
    request,
    visible,
    answers,
    customInput,
    webSearchEnabled,
    setAnswer,
    setCustomInput,
    setWebSearchEnabled,
    hide,
    reset,
  } = useClarifyStore();
  const { executeWorkflow } = useWorkflowStore();
  const [submitting, setSubmitting] = useState(false);
  const customInputRef = useRef<HTMLTextAreaElement | null>(null);

  // ESC 键关闭
  useEffect(() => {
    if (!visible) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        hide();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [visible, hide]);

  if (!visible || !request) return null;

  const questions: ClarifyQuestion[] = request.questions || [];

  // 提交：将用户选择+自定义输入拼接成新的 user_input 重新提交
  const handleSubmit = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      // 构建澄清后的新输入
      const parts: string[] = [];

      // 添加用户选择的答案
      for (const q of questions) {
        const ans = answers[q.id];
        if (ans) {
          parts.push(`【${q.question}】我选择：${ans}`);
        }
      }

      // 添加自定义输入
      const custom = customInput.trim();
      if (custom) {
        parts.push(`【补充说明】${custom}`);
      }

      // 如果用户什么都没选也没输入，给个默认提示
      if (parts.length === 0) {
        parts.push('（用户未选择具体方向，请根据我之前的反馈重新理解并回答）');
      }

      const newInput = parts.join('\n');

      // 关闭弹窗
      hide();

      // 调用 workflow 重新执行（携带原始抱怨的complaint_type）
      // V3.4 BUGFIX: 必须传入 complaint_type，否则新输入不含抱怨关键词，
      // Writer Agent 不会注入道歉+重答指令
      // V3.5: 传入 force_web_search 让 Knowledge Agent 强制联网搜索最新信息
      await executeWorkflow(newInput, {
        complaint_type: request.complaint_type,
        is_clarification: true,  // 标记这是澄清后的重答，后端可据此跳过抱怨检测
        force_web_search: webSearchEnabled,  // 用户选择是否网络搜索再回答
      });
    } finally {
      setSubmitting(false);
      reset();
    }
  };

  // 跳过：直接关闭弹窗，用户继续手动输入
  const handleSkip = () => {
    hide();
  };

  // 检查是否所有问题都已回答（可选，允许部分回答）
  const answeredCount = questions.filter((q) => answers[q.id]).length;
  const allAnswered = answeredCount === questions.length;

  return (
    <div
      className="clarify-notification"
      role="dialog"
      aria-modal="false"
      aria-labelledby="clarify-title"
      style={{
        position: 'fixed',
        bottom: 180,  // 位于输入框上方
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 9999,
        minWidth: 480,
        maxWidth: 640,
        maxHeight: '70vh',
        overflowY: 'auto',
        background: 'var(--bg-elevated, rgba(255, 255, 255, 0.98))',
        border: '1px solid var(--orange, #f59e0b)',
        borderTop: '4px solid var(--orange, #f59e0b)',
        borderRadius: 12,
        boxShadow: '0 12px 32px rgba(0, 0, 0, 0.2)',
        padding: '16px 20px',
        backdropFilter: 'blur(8px)',
        animation: 'clarifySlideUp 0.3s ease-out',
      }}
    >
      <style>{`
        @keyframes clarifySlideUp {
          from { transform: translateX(-50%) translateY(20px); opacity: 0; }
          to { transform: translateX(-50%) translateY(0); opacity: 1; }
        }
        .clarify-question-block {
          margin-bottom: 14px;
          padding: 10px 12px;
          background: var(--bg-secondary, rgba(0, 0, 0, 0.03));
          border-radius: 6px;
        }
        .clarify-option-btn {
          display: block;
          width: 100%;
          text-align: left;
          padding: 8px 12px;
          margin-top: 6px;
          background: var(--bg-elevated, #fff);
          border: 1px solid var(--border-color, #e5e7eb);
          border-radius: 6px;
          cursor: pointer;
          font-size: 13px;
          line-height: 1.5;
          transition: all 0.15s ease;
          color: var(--text-primary, #1f2937);
        }
        .clarify-option-btn:hover {
          border-color: var(--orange, #f59e0b);
          background: var(--bg-hover, rgba(245, 158, 11, 0.05));
        }
        .clarify-option-btn.selected {
          border-color: var(--orange, #f59e0b);
          background: var(--bg-selected, rgba(245, 158, 11, 0.1));
          font-weight: 500;
        }
        .clarify-custom-input {
          width: 100%;
          min-height: 60px;
          padding: 8px 12px;
          margin-top: 8px;
          background: var(--bg-elevated, #fff);
          border: 1px solid var(--border-color, #e5e7eb);
          border-radius: 6px;
          font-size: 13px;
          font-family: inherit;
          resize: vertical;
          color: var(--text-primary, #1f2937);
        }
        .clarify-custom-input:focus {
          outline: none;
          border-color: var(--orange, #f59e0b);
        }
        .clarify-action-btn {
          padding: 8px 16px;
          border-radius: 6px;
          font-size: 13px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s ease;
          border: 1px solid transparent;
        }
        .clarify-submit-btn {
          background: var(--orange, #f59e0b);
          color: white;
        }
        .clarify-submit-btn:hover:not(:disabled) {
          background: var(--orange-dark, #d97706);
        }
        .clarify-submit-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .clarify-skip-btn {
          background: transparent;
          color: var(--text-secondary, #6b7280);
          border-color: var(--border-color, #e5e7eb);
        }
        .clarify-skip-btn:hover {
          background: var(--bg-hover, rgba(0, 0, 0, 0.05));
        }
      `}</style>

      {/* 标题区 */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 18, marginRight: 8 }}>🤔</span>
        <h3 id="clarify-title" style={{ margin: 0, fontSize: 15, fontWeight: 600, color: 'var(--text-primary, #1f2937)' }}>
          抱歉理解有偏差，请帮我确认您的真实需求
        </h3>
        <button
          onClick={handleSkip}
          aria-label="关闭"
          style={{
            marginLeft: 'auto',
            background: 'transparent',
            border: 'none',
            fontSize: 18,
            color: 'var(--text-secondary, #6b7280)',
            cursor: 'pointer',
            padding: '0 4px',
          }}
        >
          ×
        </button>
      </div>

      {/* 用户输入摘要 */}
      {request.user_input_summary && (
        <div style={{
          padding: '6px 10px',
          marginBottom: 12,
          background: 'var(--bg-secondary, rgba(0, 0, 0, 0.03))',
          borderRadius: 4,
          fontSize: 12,
          color: 'var(--text-secondary, #6b7280)',
          borderLeft: '3px solid var(--orange, #f59e0b)',
        }}>
          您的输入：{request.user_input_summary}
        </div>
      )}

      {/* 问题列表 */}
      <div>
        {questions.map((q, idx) => (
          <div key={q.id} className="clarify-question-block">
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 6, color: 'var(--text-primary, #1f2937)' }}>
              {idx + 1}. {q.question}
            </div>
            {q.options.map((opt, optIdx) => {
              const isSelected = answers[q.id] === opt;
              return (
                <button
                  key={optIdx}
                  className={`clarify-option-btn ${isSelected ? 'selected' : ''}`}
                  onClick={() => setAnswer(q.id, opt)}
                >
                  {opt}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* V3.5: 网络搜索选项 — 抱怨场景下让用户选择是否联网搜索最新信息 */}
      <div
        className="clarify-question-block"
        style={{
          borderColor: webSearchEnabled
            ? 'var(--orange, #f59e0b)'
            : 'var(--border-color, #e5e7eb)',
          background: webSearchEnabled
            ? 'var(--bg-selected, rgba(245, 158, 11, 0.06))'
            : 'var(--bg-secondary, rgba(0, 0, 0, 0.03))',
        }}
      >
        <label
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            cursor: 'pointer',
            fontSize: 13,
            color: 'var(--text-primary, #1f2937)',
          }}
        >
          <input
            type="checkbox"
            checked={webSearchEnabled}
            onChange={(e) => setWebSearchEnabled(e.target.checked)}
            disabled={submitting}
            style={{
              marginTop: 2,
              marginRight: 8,
              width: 16,
              height: 16,
              cursor: 'pointer',
              accentColor: 'var(--orange, #f59e0b)',
            }}
          />
          <span>
            <span style={{ fontWeight: 500 }}>🌐 启用网络搜索再回答</span>
            <span
              style={{
                display: 'block',
                marginTop: 2,
                fontSize: 12,
                color: 'var(--text-secondary, #6b7280)',
              }}
            >
              系统将联网检索最新信息后再重新回答（适用于信息过时、数据错误、
              时效性问题如旅游/美食/天气等场景）
            </span>
          </span>
        </label>
      </div>

      {/* 自定义输入框 */}
      <div style={{ marginTop: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4, color: 'var(--text-primary, #1f2937)' }}>
          您的补充说明（可选）：
        </div>
        <textarea
          ref={customInputRef}
          className="clarify-custom-input"
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          placeholder="请输入您的理解和想法，帮助我更准确地回答..."
          rows={3}
          disabled={submitting}
        />
      </div>

      {/* 操作按钮 */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14 }}>
        <button
          className="clarify-action-btn clarify-skip-btn"
          onClick={handleSkip}
          disabled={submitting}
        >
          跳过
        </button>
        <button
          className="clarify-action-btn clarify-submit-btn"
          onClick={handleSubmit}
          disabled={submitting || (answeredCount === 0 && !customInput.trim())}
        >
          {submitting ? '提交中...' : '提交并重新回答'}
        </button>
      </div>

      {/* 状态提示 */}
      <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-tertiary, #9ca3af)', textAlign: 'right' }}>
        已回答 {answeredCount}/{questions.length} 个问题
        {allAnswered && ' ✓'}
      </div>
    </div>
  );
}
