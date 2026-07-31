'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { sandboxService } from '@/services/api/sandboxService';
import { useWorkflowStore } from '@/stores/workflowStore';
import type { SandboxInfo } from '@/types';

interface SandboxSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const SandboxSidebar: React.FC<SandboxSidebarProps> = ({ collapsed, onToggle }) => {
  const [sandboxes, setSandboxes] = useState<SandboxInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const { sandboxId, setSandboxId, loadSandboxHistory } = useWorkflowStore();

  const loadSandboxes = useCallback(async () => {
    try {
      setLoading(true);
      const list = await sandboxService.list();
      setSandboxes(list);

      // V3.5.1: 如果没有选中沙盒且有历史沙盒，自动选中第一个（最新的）
      const currentSandboxId = useWorkflowStore.getState().sandboxId;
      if (!currentSandboxId && list.length > 0) {
        switchToSandbox(list[0].id);
      }
      // V3.5.1: 无沙盒时不自动创建，保持干净系统，由用户点击"新对话"创建
    } catch (e) {
      console.error('Failed to load sandboxes:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSandboxes();
  }, [loadSandboxes]);

  // V3.5.1: 监听 ChatInterface 自动创建沙盒的事件，刷新列表
  useEffect(() => {
    const handler = () => loadSandboxes();
    window.addEventListener('sandbox-created', handler);
    return () => window.removeEventListener('sandbox-created', handler);
  }, [loadSandboxes]);

  const handleCreate = async () => {
    try {
      const sb = await sandboxService.create('新对话');
      setSandboxes((prev) => [sb, ...prev]);
      switchToSandbox(sb.id);
    } catch (e) {
      console.error('Failed to create sandbox:', e);
    }
  };

  const switchToSandbox = (id: string) => {
    setSandboxId(id);
    // 从后端加载该沙盒的聊天历史
    loadSandboxHistory(id);
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('确定要删除这个对话吗？')) return;
    try {
      await sandboxService.delete(id);
      const remaining = sandboxes.filter((s) => s.id !== id);
      setSandboxes(remaining);
      // V3.5.1: 删除后选中剩余的最新沙盒，没有则清空
      if (sandboxId === id) {
        if (remaining.length > 0) {
          switchToSandbox(remaining[0].id);
        } else {
          setSandboxId('');
          loadSandboxHistory('');
        }
      }
    } catch (e) {
      console.error('Failed to delete sandbox:', e);
    }
  };

  const handleRename = async (id: string) => {
    if (!editName.trim()) {
      setEditingId(null);
      return;
    }
    try {
      await sandboxService.rename(id, editName.trim());
      setSandboxes((prev) =>
        prev.map((s) => (s.id === id ? { ...s, name: editName.trim() } : s))
      );
    } catch (e) {
      console.error('Failed to rename sandbox:', e);
    } finally {
      setEditingId(null);
    }
  };

  const startRename = (id: string, currentName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(id);
    setEditName(currentName);
  };

  return (
    <div className={`sandbox-sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sandbox-sidebar-header">
        {!collapsed && <span className="sandbox-title">对话列表</span>}
        <button className="sandbox-toggle-btn" onClick={onToggle} title={collapsed ? '展开' : '收起'}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {collapsed ? (
              <polyline points="9 18 15 12 9 6" />
            ) : (
              <polyline points="15 18 9 12 15 6" />
            )}
          </svg>
        </button>
      </div>

      {!collapsed && (
        <>
          <button className="sandbox-create-btn" onClick={handleCreate}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            新对话
          </button>

          <div className="sandbox-list">
            {loading && sandboxes.length === 0 && (
              <div className="sandbox-loading">加载中...</div>
            )}
            {sandboxes.map((sb) => (
              <div
                key={sb.id}
                className={`sandbox-item ${sandboxId === sb.id ? 'active' : ''}`}
                onClick={() => switchToSandbox(sb.id)}
              >
                {editingId === sb.id ? (
                  <input
                    className="sandbox-rename-input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    onBlur={() => handleRename(sb.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleRename(sb.id);
                      if (e.key === 'Escape') setEditingId(null);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    autoFocus
                  />
                ) : (
                  <>
                    <div className="sandbox-item-info">
                      <span className="sandbox-item-name">{sb.name}</span>
                      <span className="sandbox-item-count">{sb.message_count} 条消息</span>
                    </div>
                    <div className="sandbox-item-actions">
                      <button
                        className="sandbox-action-btn"
                        onClick={(e) => startRename(sb.id, sb.name, e)}
                        title="重命名"
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                        </svg>
                      </button>
                      <button
                        className="sandbox-action-btn sandbox-delete-btn"
                        onClick={(e) => handleDelete(sb.id, e)}
                        title="删除"
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default SandboxSidebar;