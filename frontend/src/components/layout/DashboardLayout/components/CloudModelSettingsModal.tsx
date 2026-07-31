/**
 * 云端模型设置弹窗 — 首次启动引导 + 日常密钥/模型切换
 *
 * V3.5.1 (2026-07-31):
 * - mode="onboarding": 首次启动检测到无密钥时自动弹出，不可关闭
 * - mode="settings": 日常设置，可关闭，可切换模型和更改密钥
 */
'use client';

import { useState, useEffect } from 'react';
import {
  getCloudModelConfig,
  saveCloudModelConfig,
  testCloudModelConnection,
  type CloudModelStatus,
} from '@/services/api/settingsService';

interface CloudModelSettingsModalProps {
  mode: 'onboarding' | 'settings';
  onClose?: () => void;
  onSaved?: () => void;
}

// DeepSeek 可用模型列表
const DEEPSEEK_MODELS = [
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro（推荐，推理能力强）' },
  { value: 'deepseek-chat', label: 'DeepSeek Chat（标准对话）' },
  { value: 'deepseek-reasoner', label: 'DeepSeek Reasoner（深度推理）' },
];

export default function CloudModelSettingsModal({
  mode,
  onClose,
  onSaved,
}: CloudModelSettingsModalProps) {
  const isOnboarding = mode === 'onboarding';

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('deepseek-v4-pro');
  const [apiBase, setApiBase] = useState('https://api.deepseek.com/v1');
  const [currentMasked, setCurrentMasked] = useState('');
  const [isConfigured, setIsConfigured] = useState(false);

  // 加载当前配置
  useEffect(() => {
    loadConfig();
  }, []);

  async function loadConfig() {
    try {
      setLoading(true);
      const config = await getCloudModelConfig();
      setModel(config.model || 'deepseek-v4-pro');
      setApiBase(config.api_base || 'https://api.deepseek.com/v1');
      setCurrentMasked(config.api_key_masked || '');
      setIsConfigured(config.configured);
    } catch (err) {
      // 后端未启动时静默处理
      console.warn('Failed to load cloud model config:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setError('');
    setSuccess('');

    if (!apiKey && !isConfigured) {
      setError('请输入 API 密钥');
      return;
    }

    setSaving(true);
    try {
      const config = await saveCloudModelConfig({
        api_key: apiKey || null,  // 空字符串表示不修改
        model,
        api_base: apiBase,
      });
      setCurrentMasked(config.api_key_masked || '');
      setIsConfigured(config.configured);
      setApiKey('');  // 清空输入框（已保存）
      setSuccess('配置已保存');
      onSaved?.();
      if (isOnboarding) {
        // 引导模式下保存成功后关闭
        setTimeout(() => onClose?.(), 800);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || '保存失败，请检查后端是否运行');
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setError('');
    setSuccess('');

    if (!apiKey && !isConfigured) {
      setError('请先输入 API 密钥');
      return;
    }

    setTesting(true);
    try {
      const result = await testCloudModelConnection({
        api_key: apiKey || null,
        model,
        api_base: apiBase,
      });
      if (result.success) {
        setSuccess(result.message);
      } else {
        setError(result.message);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || '测试失败，请检查网络连接');
    } finally {
      setTesting(false);
    }
  }

  function handleClose() {
    // 引导模式下，未配置密钥时不允许关闭
    if (isOnboarding && !isConfigured) {
      setError('请先输入并保存 API 密钥以完成首次配置');
      return;
    }
    onClose?.();
  }

  if (loading) {
    return (
      <div className="modal-overlay" style={overlayStyle}>
        <div className="modal-content" style={modalStyle}>
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <div className="loading-spinner" />
            <p style={{ marginTop: 16, color: 'var(--text-secondary)' }}>正在加载配置...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" style={overlayStyle} onClick={handleClose}>
      <div
        className="modal-content"
        style={modalStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题 */}
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
            {isOnboarding ? '🔑 首次启动 — 配置云端模型密钥' : '⚙️ 云端模型设置'}
          </h2>
          <p style={{ margin: '8px 0 0', fontSize: 13, color: 'var(--text-secondary)' }}>
            {isOnboarding
              ? '检测到尚未配置 DeepSeek API 密钥。请输入密钥以启用云端增强功能（复杂任务由云端大模型处理）。'
              : '管理云端模型的 API 密钥、模型和接口地址。密钥保存在本地 .env 文件中。'}
          </p>
        </div>

        {/* 当前状态 */}
        {currentMasked && (
          <div style={statusBannerStyle}>
            <span style={{ fontSize: 13 }}>
              ✅ 当前密钥: <code style={codeStyle}>{currentMasked}</code>
            </span>
          </div>
        )}

        {/* API 密钥输入 */}
        <div style={fieldStyle}>
          <label style={labelStyle}>
            DeepSeek API 密钥
            {isConfigured && <span style={hintStyle}>（留空表示不修改当前密钥）</span>}
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={isConfigured ? 'sk-***（已配置，输入新密钥可替换）' : 'sk-xxxxxxxxxxxxxxxxxxxxxxxx'}
            style={inputStyle}
            autoComplete="off"
          />
          <p style={helpTextStyle}>
            获取密钥: <a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener noreferrer" style={linkStyle}>platform.deepseek.com/api_keys</a>
          </p>
        </div>

        {/* 模型选择 */}
        <div style={fieldStyle}>
          <label style={labelStyle}>云端模型</label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            style={selectStyle}
          >
            {DEEPSEEK_MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        {/* API 地址 */}
        <div style={fieldStyle}>
          <label style={labelStyle}>API 基础地址</label>
          <input
            type="text"
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
            placeholder="https://api.deepseek.com/v1"
            style={inputStyle}
          />
        </div>

        {/* 错误/成功提示 */}
        {error && (
          <div style={errorBannerStyle}>
            <span>⚠️ {error}</span>
          </div>
        )}
        {success && (
          <div style={successBannerStyle}>
            <span>✅ {success}</span>
          </div>
        )}

        {/* 按钮区 */}
        <div style={{ display: 'flex', gap: 10, marginTop: 24, justifyContent: 'flex-end' }}>
          <button
            onClick={handleTest}
            disabled={testing || saving}
            style={secondaryBtnStyle(testing || saving)}
          >
            {testing ? '测试中...' : '测试连接'}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || testing}
            style={primaryBtnStyle(saving || testing)}
          >
            {saving ? '保存中...' : '保存配置'}
          </button>
          {!isOnboarding && (
            <button
              onClick={handleClose}
              style={closeBtnStyle}
            >
              关闭
            </button>
          )}
        </div>

        {/* 引导模式下底部提示 */}
        {isOnboarding && !isConfigured && (
          <p style={{ ...helpTextStyle, textAlign: 'center', marginTop: 16 }}>
            💡 配置密钥后即可开始使用 AgentMatrix
          </p>
        )}
      </div>
    </div>
  );
}

// ── 样式 ──

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: 'rgba(0, 0, 0, 0.5)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 9999,
  backdropFilter: 'blur(4px)',
};

const modalStyle: React.CSSProperties = {
  background: 'var(--bg-primary, #fff)',
  borderRadius: 12,
  padding: 28,
  width: '90%',
  maxWidth: 480,
  maxHeight: '90vh',
  overflowY: 'auto',
  boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
  border: '1px solid var(--border-color, #e5e7eb)',
};

const statusBannerStyle: React.CSSProperties = {
  background: 'rgba(34, 197, 94, 0.08)',
  border: '1px solid rgba(34, 197, 94, 0.2)',
  borderRadius: 8,
  padding: '10px 14px',
  marginBottom: 16,
};

const fieldStyle: React.CSSProperties = {
  marginBottom: 16,
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 13,
  fontWeight: 500,
  marginBottom: 6,
  color: 'var(--text-primary)',
};

const hintStyle: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--text-tertiary, #9ca3af)',
  marginLeft: 6,
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: 8,
  border: '1px solid var(--border-color, #e5e7eb)',
  background: 'var(--bg-secondary, #f9fafb)',
  color: 'var(--text-primary)',
  fontSize: 14,
  outline: 'none',
  boxSizing: 'border-box',
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: 'pointer',
};

const helpTextStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-tertiary, #9ca3af)',
  margin: '4px 0 0',
};

const linkStyle: React.CSSProperties = {
  color: 'var(--accent-primary, #3b82f6)',
  textDecoration: 'none',
};

const codeStyle: React.CSSProperties = {
  background: 'var(--bg-tertiary, #f3f4f6)',
  padding: '2px 6px',
  borderRadius: 4,
  fontSize: 12,
  fontFamily: 'monospace',
};

const errorBannerStyle: React.CSSProperties = {
  background: 'rgba(239, 68, 68, 0.08)',
  border: '1px solid rgba(239, 68, 68, 0.2)',
  borderRadius: 8,
  padding: '10px 14px',
  marginTop: 12,
  fontSize: 13,
  color: 'var(--error, #ef4444)',
};

const successBannerStyle: React.CSSProperties = {
  background: 'rgba(34, 197, 94, 0.08)',
  border: '1px solid rgba(34, 197, 94, 0.2)',
  borderRadius: 8,
  padding: '10px 14px',
  marginTop: 12,
  fontSize: 13,
  color: 'var(--success, #22c55e)',
};

function primaryBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    padding: '10px 20px',
    borderRadius: 8,
    border: 'none',
    background: disabled ? 'var(--btn-disabled, #9ca3af)' : 'var(--accent-primary, #3b82f6)',
    color: '#fff',
    fontSize: 14,
    fontWeight: 500,
    cursor: disabled ? 'not-allowed' : 'pointer',
  };
}

function secondaryBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    padding: '10px 20px',
    borderRadius: 8,
    border: '1px solid var(--border-color, #e5e7eb)',
    background: 'transparent',
    color: 'var(--text-primary)',
    fontSize: 14,
    cursor: disabled ? 'not-allowed' : 'pointer',
  };
}

const closeBtnStyle: React.CSSProperties = {
  padding: '10px 20px',
  borderRadius: 8,
  border: '1px solid var(--border-color, #e5e7eb)',
  background: 'transparent',
  color: 'var(--text-secondary)',
  fontSize: 14,
  cursor: 'pointer',
};
