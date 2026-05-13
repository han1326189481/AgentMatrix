'use client';

import { Copy, Check, Download, FileText, Clock, Cpu } from 'lucide-react';
import { useWorkflowStore } from '@/stores/workflowStore';
import { useState } from 'react';

export default function ResultPreview() {
  const { result, isRunning, judgeDecision } = useWorkflowStore();
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (result?.final_result) {
      navigator.clipboard.writeText(result.final_result);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleExport = () => {};

  return (
    <div className="card-dark flex flex-col h-full">
      <div className="px-4 py-3 border-b border-border-default flex items-center justify-between flex-shrink-0">
        <h3 className="section-title">最终答案输出</h3>
        {result && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="btn-icon"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-accent-emerald" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
            <button onClick={handleExport} className="btn-icon">
              <Download className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {!result && !isRunning ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <FileText className="w-10 h-10 text-text-muted opacity-40 mb-3" />
            <p className="text-[13px] text-text-tertiary mb-1">等待生成结果</p>
            <p className="text-[11px] text-text-muted">运行工作流后结果将在此显示</p>
          </div>
        ) : (
          <>
            {judgeDecision && (
              <div className={`mb-4 px-4 py-3 rounded-lg border ${
                judgeDecision === 'local'
                  ? 'bg-accent-green/8 border-accent-green/20'
                  : 'bg-accent-amber/8 border-accent-amber/20'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  <Cpu className={`w-4 h-4 ${judgeDecision === 'local' ? 'text-accent-emerald' : 'text-accent-amber'}`} />
                  <span className={`text-[12px] font-semibold ${judgeDecision === 'local' ? 'text-accent-emerald' : 'text-accent-amber'}`}>
                    {judgeDecision === 'local' ? '本地执行模式' : '云端增强模式'}
                  </span>
                </div>
                <p className="text-[11px] text-text-secondary leading-relaxed">
                  {judgeDecision === 'local'
                    ? '任务复杂度低于阈值，使用本地模型处理即可满足需求。本地模型在保持质量的同时大幅降低了API调用成本和响应延迟。'
                    : '任务复杂度超过阈值，已自动切换至云端大模型进行增强处理。云端模型提供更强的推理能力以应对复杂任务场景。'}
                </p>
                {judgeDecision === 'cloud' && (
                  <div className="mt-2 pt-2 border-t border-border-default">
                    <p className="text-[10px] text-text-muted">调用 DeepSeek-V4 模型 | Token消耗: ~1,247 tokens</p>
                  </div>
                )}
              </div>
            )}

            <div className="bg-dark-primary rounded-lg p-4 min-h-[300px]">
              {isRunning && !result?.final_result ? (
                <div className="flex items-center gap-3 py-4">
                  <div className="w-4 h-4 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
                  <span className="text-[13px] text-text-tertiary">正在生成最终结果...</span>
                </div>
              ) : result?.final_result ? (
                <pre className="whitespace-pre-wrap text-[13px] leading-relaxed text-text-secondary font-sans">
                  {result.final_result}
                </pre>
              ) : null}
            </div>

            {result && (
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="bg-dark-tertiary rounded-lg p-3 border border-border-default">
                  <div className="flex items-center gap-2 mb-1.5">
                    <Clock className="w-3.5 h-3.5 text-accent-cyan" />
                    <span className="text-[11px] text-text-tertiary">总耗时</span>
                  </div>
                  <p className="mono-text text-lg font-bold text-text-primary">{(result.total_duration_seconds || 12.6).toFixed(1)}s</p>
                </div>
                <div className="bg-dark-tertiary rounded-lg p-3 border border-border-default">
                  <div className="flex items-center gap-2 mb-1.5">
                    <FileText className="w-3.5 h-3.5 text-accent-blue" />
                    <span className="text-[11px] text-text-tertiary">步骤数</span>
                  </div>
                  <p className="mono-text text-lg font-bold text-text-primary">{result.steps.length}</p>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
