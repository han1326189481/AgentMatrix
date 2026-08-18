'use client';

import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useWorkflowStore } from '@/stores/workflowStore';
import { useErrorStore } from '@/stores/errorStore';
import { exportService } from '@/services/api/agentService';
import { sandboxService } from '@/services/api/sandboxService';
import { AGENT_SVG_ICONS, getAgentColorValue } from '../constants';
import type { PromptTemplateItem } from '@/types';
import { AGENT_ORDER, AGENT_NAMES } from '@/types';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';

const ChatInterface: React.FC = () => {
  const [input, setInput] = useState('');
  const [exportingIdx, setExportingIdx] = useState<number | null>(null);
  // V3: 推荐模板卡片展开状态（记录展开的 chat 索引和模板节点ID）
  const [expandedTemplate, setExpandedTemplate] = useState<string | null>(null);
  // V3: mounted 标记
  const [mounted, setMounted] = useState(false);
  // V3.2: 图片上传中状态
  const [isUploadingImages, setIsUploadingImages] = useState(false);
  // V3.2: 图片预览
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  // V4.3: 头像切换 — 持久化到 localStorage
  const [userAvatar, setUserAvatar] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('agentmatrix_user_avatar') || null;
  });
  const [systemAvatar, setSystemAvatar] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('agentmatrix_system_avatar') || null;
  });
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const [avatarPickerTarget, setAvatarPickerTarget] = useState<'user' | 'system'>('user');
  const avatarFileRef = useRef<HTMLInputElement>(null);
  useEffect(() => { setMounted(true); }, []);
  // V3.2: ESC 键关闭图片预览
  useEffect(() => {
    if (!previewImage) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPreviewImage(null);
    };
    document.addEventListener('keydown', onKey);
    // 打开预览时禁止背景滚动
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [previewImage]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // V3.2: 隐藏的 file input 引用，支持多选图片
  const fileInputRef = useRef<HTMLInputElement>(null);

  // V3.2: 图片等比例缩小为缩略图 base64（节省传输体积，避免超过 base64 上限）
  // 设计：最大边 512px（兼顾清晰度与体积），JPEG 0.85 质量
  // 视觉模型只需识别内容，不需要原图分辨率；过大的图反而拖慢识别
  // V3.2 修复 P1-4: PNG 保留透明通道（不填白底），仅 JPEG/JPEG-XL 才填白底防变黑
  // V3.2 修复 P1-8: 添加文件大小限制（10MB），超过则拒绝，避免 Canvas 内存暴涨
  const resizeImageToBase64 = (file: File, maxSize: number = 512): Promise<string> => {
    return new Promise((resolve, reject) => {
      if (!file.type.startsWith('image/')) {
        reject(new Error('仅支持图片文件'));
        return;
      }
      // P1-8: 文件大小硬上限 10MB
      // 原图过大时 Image 对象会占用大量内存，可能卡死浏览器
      const MAX_FILE_SIZE = 10 * 1024 * 1024;  // 10MB
      if (file.size > MAX_FILE_SIZE) {
        reject(new Error(`图片过大（${(file.size / 1024 / 1024).toFixed(1)}MB），请上传小于 10MB 的图片`));
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          let { width, height } = img;
          // M3 修复：像素尺寸硬上限 50MP（约 7160×7000 或等效面积）
          // 防止极端高分辨率图片（如 10000×8000 = 80MP ≈ 305MB 内存）导致浏览器卡死
          // 即使文件大小 < 10MB，高压缩比 JPEG 也可能解码出超大像素
          const MAX_PIXELS = 50_000_000;  // 50MP
          if (width * height > MAX_PIXELS) {
            reject(new Error(
              `图片分辨率过大（${width}×${height}=${((width * height) / 1_000_000).toFixed(1)}MP），`
              + `请上传小于 50MP 的图片`
            ));
            return;
          }
          // 等比例缩小：仅当超过 maxSize 时才缩放
          if (width > height) {
            if (width > maxSize) {
              height = Math.round((height * maxSize) / width);
              width = maxSize;
            }
          } else {
            if (height > maxSize) {
              width = Math.round((width * maxSize) / height);
              height = maxSize;
            }
          }
          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          if (!ctx) {
            reject(new Error('Canvas 2D 上下文不可用'));
            return;
          }
          // P1-4 修复：根据输出格式决定是否填白底
          // PNG 保留透明通道 → 不填白底
          // 非 PNG（JPEG/WEBP 等）不支持透明或统一转 JPEG → 填白底防止透明区域变黑
          // P1-4 补丁：同时检查 MIME 和文件扩展名，避免某些浏览器未设置正确 MIME
          const isPng = file.type === 'image/png'
            || file.name.toLowerCase().endsWith('.png');
          if (!isPng) {
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, width, height);
          }
          ctx.drawImage(img, 0, 0, width, height);
          // PNG 保留透明通道，其他统一 JPEG 0.85
          const mime = isPng ? 'image/png' : 'image/jpeg';
          const quality = isPng ? undefined : 0.85;
          try {
            const dataUrl = quality !== undefined
              ? canvas.toDataURL(mime, quality)
              : canvas.toDataURL(mime);
            resolve(dataUrl);
          } catch (err) {
            reject(new Error('图片转 base64 失败'));
          }
        };
        img.onerror = () => reject(new Error('图片加载失败'));
        img.src = e.target?.result as string;
      };
      reader.onerror = () => reject(new Error('文件读取失败'));
      reader.readAsDataURL(file);
    });
  };

  // V3.2: 处理图片上传 — 多选，限制 9 张，等比例缩小后存入 store
  // P1-8: 超过 10MB 的图片会被拒绝并通过 toast 提示用户
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploadingImages(true);
    try {
      const currentCount = pendingImages.length;
      const remaining = 9 - currentCount;
      if (remaining <= 0) {
        // 已达上限，忽略
        e.target.value = '';
        return;
      }

      // 取前 remaining 个文件（超过上限的部分忽略并提示）
      const filesToProcess = Array.from(files).slice(0, remaining);
      const ignoredCount = files.length - filesToProcess.length;

      // P1-8: 收集处理失败的文件，循环结束后统一提示
      const failedFiles: Array<{ name: string; reason: string }> = [];

      for (const file of filesToProcess) {
        try {
          const base64 = await resizeImageToBase64(file);
          addPendingImage(base64);
        } catch (err) {
          const reason = err instanceof Error ? err.message : '未知错误';
          console.warn(`[ChatInterface] 图片处理失败: ${file.name}`, err);
          failedFiles.push({ name: file.name, reason });
        }
      }

      // P1-8 修复：有文件处理失败时通过项目已有的 toast 机制提示
      // 使用 errorStore.showWarning 替代 alert()，避免阻塞主线程
      if (failedFiles.length > 0) {
        if (failedFiles.length === 1) {
          showWarning(`${failedFiles[0].name}: ${failedFiles[0].reason}`);
        } else {
          const failedList = failedFiles.map(f => `${f.name}`).join('、');
          showWarning(`${failedFiles.length} 张图片处理失败：${failedList}`);
        }
      }

      if (ignoredCount > 0) {
        console.warn(`[ChatInterface] 已达 9 张上限，${ignoredCount} 张图片被忽略`);
      }
    } finally {
      setIsUploadingImages(false);
      // 清空 input，允许重复选择同一文件
      e.target.value = '';
    }
  };

  // V3.2: 触发文件选择
  const triggerImageUpload = () => {
    fileInputRef.current?.click();
  };

  // V3: 点击模板 → 填充输入框
  // 策略: 把 template_text 中的 {variable} 替换为：
  //   - 有 default_value → 用 default_value
  //   - 无 default_value → 用 【请输入variable描述】 作为占位符（中文方括号醒目）
  const applyTemplate = (template: PromptTemplateItem) => {
    if (!template.template_text) {
      // 模板内容为空（异常情况），至少填充标题作为提示
      setInput(`# ${template.title}\n\n（模板内容加载失败，请直接描述你的需求）`);
      return;
    }

    let filledText = template.template_text;

    // 替换变量占位符
    if (template.variables && template.variables.length > 0) {
      for (const v of template.variables) {
        const placeholder = `{${v.name}}`;
        const replacement = v.default_value
          ? v.default_value
          : `【请输入${v.description || v.name}】`;
        filledText = filledText.split(placeholder).join(replacement);
      }
    }

    // 在模板前面加一行标题，让用户清楚知道用了哪个模板
    const header = `【使用模板：${template.title}】\n\n`;
    setInput(header + filledText);

    // V3: 标记用户已使用模板 → 下一次问答跳过推荐（避免模板回答仍带模板影响观感）
    // 冷却期仅持续一次问答，再下一次自动恢复推荐
    markTemplateUsed();

    // 聚焦输入框并调整高度
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
        // 把光标移到末尾
        const len = inputRef.current.value.length;
        inputRef.current.setSelectionRange(len, len);
        // 触发 textarea 自动调整高度
        inputRef.current.style.height = 'auto';
        inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
      }
    }, 50);
  };

  // V4.3: 头像切换处理
  const handleAvatarChange = (target: 'user' | 'system') => {
    setAvatarPickerTarget(target);
    setShowAvatarPicker(true);
  };

  const handleAvatarFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string;
      if (avatarPickerTarget === 'user') {
        setUserAvatar(dataUrl);
        localStorage.setItem('agentmatrix_user_avatar', dataUrl);
      } else {
        setSystemAvatar(dataUrl);
        localStorage.setItem('agentmatrix_system_avatar', dataUrl);
      }
      setShowAvatarPicker(false);
    };
    reader.readAsDataURL(file);
    // 重置 input 以便同一文件可再次选择
    e.target.value = '';
  };

  const handleResetAvatar = (target: 'user' | 'system') => {
    if (target === 'user') {
      setUserAvatar(null);
      localStorage.removeItem('agentmatrix_user_avatar');
    } else {
      setSystemAvatar(null);
      localStorage.removeItem('agentmatrix_system_avatar');
    }
    setShowAvatarPicker(false);
  };

  const {
    chatHistory,
    executeWorkflow,
    isRunning,
    logs,
    workflowSteps,
    complexityScore,
    judgeDecision,
    // V3: 推荐开关 + 模板使用标记
    recommendEnabled,
    toggleRecommend,
    markTemplateUsed,
    // V3.2: 图片上传 + 视觉识别进度
    pendingImages,
    addPendingImage,
    removePendingImage,
    clearPendingImages,
    visionProgress,
  } = useWorkflowStore();

  // P1-8 修复：使用项目已有的 errorStore.showWarning 替代 alert()
  // alert() 会阻塞主线程，导致上传指示器无法更新；showWarning 是非阻塞 toast
  const { showWarning } = useErrorStore();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, logs]);

  // V3.5.1: 从用户首问提取关键词作为沙盒名称
  const extractSandboxName = (text: string): string => {
    const cleaned = text.trim().replace(/\s+/g, ' ');
    if (!cleaned) return '新对话';

    // 去除常见提问前缀
    const stripped = cleaned.replace(/^(请问|帮我|麻烦|我想|我要|如何|怎么|怎样|为什么|为何|能不能|可以不可以|能不能帮|请帮我|麻烦你|你好)[，,？?！!\s]*/i, '');

    // 去除尾部标点
    const noTail = stripped.replace(/[，,。.！!？?；;]+$/, '');

    if (noTail.length <= 12) return noTail;

    // 优先在标点处截断
    const punctSlice = noTail.slice(0, 20);
    const punctMatch = punctSlice.match(/^([^，,。.！!？?\n]{4,18})[，,。.！!？?\n]/);
    if (punctMatch) return punctMatch[1];

    // 其次在空格处截断（中英混合场景）
    const spaceSlice = noTail.slice(0, 20);
    const spaceMatch = spaceSlice.match(/^(\S{4,18})\s/);
    if (spaceMatch) return spaceMatch[1];

    // 在"的"字处截断，避免词义生硬断裂
    const deSlice = noTail.slice(0, 16);
    const deMatch = deSlice.match(/^([^的]{4,12})的/);
    if (deMatch) return deMatch[1];

    // 英文单词边界：避免在单词中间截断
    const engSlice = noTail.slice(0, 14);
    const engMatch = engSlice.match(/^([\s\S]{4,10}[a-zA-Z])/);
    if (engMatch && /[a-zA-Z][\u4e00-\u9fa5]/.test(noTail.slice(engMatch[1].length - 1, engMatch[1].length + 1))) {
      return engMatch[1];
    }

    // 兜底：取前 10 字符（避免在英文单词中间断裂）
    const fallback = noTail.slice(0, 10);
    // 若末尾是英文且后面还有英文字母，回退到上一个中文字符
    if (/[a-zA-Z]$/.test(fallback) && /[a-zA-Z]/.test(noTail[10] || '')) {
      const lastChinese = fallback.search(/[\u4e00-\u9fa5](?=[a-zA-Z])/g);
      if (lastChinese >= 4) return fallback.slice(0, lastChinese + 1);
    }
    return fallback;
  };

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isRunning) return;

    // V3.5.1: 无物理沙箱时自动创建，用首问关键词命名
    const currentSandboxId = useWorkflowStore.getState().sandboxId;
    if (!currentSandboxId) {
      try {
        const sandboxName = extractSandboxName(trimmed);
        const sb = await sandboxService.create(sandboxName);
        useWorkflowStore.getState().setSandboxId(sb.id);
        // 通知侧边栏刷新沙盒列表
        window.dispatchEvent(new CustomEvent('sandbox-created'));
      } catch (e) {
        console.error('Failed to auto-create sandbox:', e);
        return;
      }
    }

    setInput('');
    await executeWorkflow(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleAutoResize = () => {
    const el = inputRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  };

  const getAgentName = (agentId: string): string => {
    const id = agentId as typeof AGENT_ORDER[number];
    if (id in AGENT_NAMES) return AGENT_NAMES[id];
    return agentId;
  };

  // V3: 导出意图识别 — 支持模板提问 + 自然语言导出请求两种触发方式
  // 1. 模板提问：input 以【使用模板：】开头 → 显示全部 4 个格式按钮
  // 2. 自然语言导出：input 包含导出意图关键词（"做成 word/文档/稿子"、"导出 ppt/幻灯片"、"生成知识图谱/思维导图"等）
  //    → 显示按钮，并高亮用户期望的格式
  //
  // 健壮性：支持丰富的同义词识别
  //   Word: word/文档/稿子/报告/稿件/文本/写成文档/输出文档
  //   PPT:  ppt/幻灯片/演示/演示文稿/做成幻灯片/做演示/答辩ppt
  //   思维导图: 知识图谱/思维导图/导图/脑图/结构图/关系图
  //   Markdown: markdown/md/纯文本/文本格式
  const detectExportIntent = (chat: { user_input: string }): {
    shouldShow: boolean;
    highlightFormat?: 'markdown' | 'docx' | 'pptx' | 'mindmap';
  } => {
    const input = chat.user_input.toLowerCase();

    // 情况 1: 模板提问 → 显示全部按钮，不高亮
    if (chat.user_input.startsWith('【使用模板：')) {
      return { shouldShow: true };
    }

    // 情况 2: 自然语言导出意图检测
    // 导出动作词 + 格式词的组合识别（覆盖口语化表达）
    const exportActionWords = [
      '导出', '下载', '输出', '生成', '做成', '转为', '转换', '转成', '变成', '变', '弄成', '搞成', '搞个', '做个', '生成个', '给个', '给我一份', '发一份', '要一份', '帮我做', '保存为', '存为',
      // 口语化："能不能给我转成"、"能不能做成"、"可以转吗"
      '能不能', '可以吗', '帮我', '给我转', '给我做', '给我生成',
    ];
    const hasExportAction = exportActionWords.some(w => input.includes(w));

    // 格式同义词字典（小写匹配，覆盖丰富的口语表达）
    const formatSynonyms: Record<string, string[]> = {
      docx: ['word', '文档', '稿子', '报告', '稿件', '写成文档', '输出文档', '.docx', '.doc', '文本文件'],
      pptx: ['ppt', '幻灯片', '演示', '演示文稿', '做演示', '答辩ppt', '做ppt', '.pptx', '.ppt', ' slides', 'slide'],
      mindmap: ['知识图谱', '思维导图', '思维图谱', '图谱', '知识图', '导图', '脑图', '结构图', '关系图', '知识结构', '结构图谱', '树状图', '树图', '逻辑图'],
      markdown: ['markdown', 'md', '纯文本', '文本格式', '.md'],
    };

    // 上下文引用词（表明用户引用了之前的对话内容）
    const contextRefWords = ['刚刚', '刚才', '上面', '之前的', '这个', '这份', '这篇', '刚生成', '刚写的', '你写的', '回答的', '你的回答', '系统生成'];
    const hasContextRef = contextRefWords.some(w => input.includes(w));

    // 检测用户期望的格式
    let highlightFormat: 'markdown' | 'docx' | 'pptx' | 'mindmap' | undefined;
    for (const [fmt, synonyms] of Object.entries(formatSynonyms)) {
      if (synonyms.some(s => input.includes(s))) {
        highlightFormat = fmt as 'markdown' | 'docx' | 'pptx' | 'mindmap';
        break;
      }
    }

    // 触发条件：
    // a) 有导出动作词 + 格式词 → 强导出意图
    // b) 有格式词 + 上下文引用词 → 隐式导出意图（如"把这个周计划做成知识图谱"）
    // c) 仅格式词但包含"做"/"生成"等动词 → 弱导出意图（如"做个ppt"、"生成思维导图"）
    const hasFormatWord = !!highlightFormat;
    const strongIntent = hasExportAction && hasFormatWord;
    const implicitIntent = hasFormatWord && hasContextRef;
    const weakIntent = hasFormatWord && ['做', '生成', '给', '要'].some(v => input.includes(v));

    if (strongIntent || implicitIntent || weakIntent) {
      return { shouldShow: true, highlightFormat };
    }

    return { shouldShow: false };
  };

  // 导出消息 — V3: 用行内 toast 替代 alert，避免打断用户
  const [exportToast, setExportToast] = useState<{ idx: number; msg: string; type: 'success' | 'error' } | null>(null);
  const handleExport = async (idx: number, format: 'markdown' | 'docx' | 'pptx' | 'mindmap') => {
    setExportingIdx(idx);
    try {
      const chat = chatHistory[idx];
      // 去掉 input 头部的【使用模板：xxx】标记，保留实际内容
      const cleanInput = chat.user_input.replace(/^【使用模板：[^】]+】\s*\n*\s*/, '');
      const content = `# 用户问题\n\n${cleanInput}\n\n# AgentMatrix 回答\n\n${chat.response}`;
      const filename = `agentmatrix_${new Date(chat.timestamp).toISOString().slice(0, 10)}_${idx + 1}`;
      const result = await exportService.export({ content, format, filename });
      const ext = format === 'markdown' ? 'md' : format === 'mindmap' ? 'html' : format;

      // V3: 自动触发文件下载（用隐藏 a 标签，不弹新窗口）
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const downloadUrl = `${API_BASE}/api/v1/export/download/${result.filename}`;
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = result.filename;
      // 不设 target，避免新开标签页
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setExportToast({ idx, msg: `已生成 ${filename}.${ext} 并开始下载`, type: 'success' });
      setTimeout(() => setExportToast(null), 3000);
    } catch (e) {
      setExportToast({ idx, msg: `导出失败: ${e instanceof Error ? e.message : '未知错误'}`, type: 'error' });
      setTimeout(() => setExportToast(null), 4000);
    } finally {
      setExportingIdx(null);
    }
  };

  return (
    <div className="chat-interface">
      {/* Messages Area */}
      <div className="chat-messages">
        {chatHistory.length === 0 && !isRunning && (
          <div className="chat-welcome">
            <div className="welcome-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <h2>AgentMatrix 多智能体协同平台</h2>
            <p>5 个专业化 Agent 协同工作，为您提供高质量的智能回答</p>
            <div className="welcome-agents">
              {AGENT_ORDER.map((id) => (
                <div key={id} className="welcome-agent-chip">
                  <span className="agent-chip-icon" style={{ color: getAgentColorValue(id) }}>
                    {AGENT_SVG_ICONS[id]}
                  </span>
                  <span>{AGENT_NAMES[id]}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {chatHistory.map((chat, idx) => (
          <div key={idx} className="chat-message-group">
            {/* User Message */}
            <div className="chat-message chat-message-user">
              <div
                className="message-avatar user-avatar"
                title="点击更换用户头像"
                onClick={() => handleAvatarChange('user')}
                style={{ cursor: 'pointer' }}
              >
                {userAvatar ? (
                  <img src={userAvatar} alt="用户头像" className="avatar-img" />
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                )}
              </div>
              <div className="message-content">
                <p>{chat.user_input}</p>
                {/* V3.2: 显示用户上传的图片缩略图 */}
                {chat.images && chat.images.length > 0 && (
                  <div className="chat-images-grid">
                    {chat.images.map((img, imgIdx) => (
                      <img
                        key={imgIdx}
                        src={img}
                        alt={`用户上传图片 ${imgIdx + 1}`}
                        className="chat-image-thumbnail"
                        loading="lazy"
                        onClick={() => setPreviewImage(img)}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* V3: 提示词模板推荐系统消息（在 user 和 assistant 之间） */}
            {chat.prompt_templates && chat.prompt_templates.length > 0 && (
              <div className="chat-message chat-message-system-recommend">
                <div className="message-avatar recommend-avatar">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M9 18h6" />
                    <path d="M10 22h4" />
                    <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14" />
                  </svg>
                </div>
                <div className="message-content recommend-message-content">
                  {/* 头部：标题 + 说明 */}
                  <div className="recommend-header">
                    <div className="recommend-header-left">
                      <span className="recommend-icon-badge">模板</span>
                      <div className="recommend-header-text">
                        <div className="recommend-title">
                          系统已为你匹配 <strong>{chat.prompt_templates.length}</strong> 条精选提示词模板
                        </div>
                        <div className="recommend-subtitle">
                          点击「使用此模板」可自动填充输入框，{`\u00A0`}修改占位符后发送即可获得高质量回答
                        </div>
                      </div>
                    </div>
                    <span className="recommend-source">来自永久化知识库</span>
                  </div>

                  {/* 模板列表 */}
                  <div className="recommend-list">
                    {chat.prompt_templates.map((tpl, tplIdx) => {
                      const isExpanded = expandedTemplate === `${idx}-${tpl.node_id}`;
                      const difficultyLabel = tpl.difficulty === 'beginner' ? '入门'
                        : tpl.difficulty === 'intermediate' ? '进阶'
                        : tpl.difficulty === 'advanced' ? '高级' : '';
                      return (
                        <div key={tpl.node_id} className={`recommend-item ${isExpanded ? 'recommend-item-expanded' : ''}`}>
                          {/* 卡片头部：标题 + 评分 + 操作 */}
                          <div className="recommend-item-header">
                            <div className="recommend-item-title-row">
                              <span className="recommend-item-index">#{tplIdx + 1}</span>
                              <span className="recommend-item-title">{tpl.title}</span>
                            </div>
                            <div className="recommend-item-meta">
                              {tpl.quality_score > 0 && (
                                <span className="recommend-item-score">
                                  评分 {tpl.quality_score.toFixed(2)}
                                </span>
                              )}
                              {difficultyLabel && (
                                <span className={`recommend-item-difficulty recommend-difficulty-${tpl.difficulty}`}>
                                  {difficultyLabel}
                                </span>
                              )}
                            </div>
                          </div>

                          {/* 元信息行：领域 + 意图标签 */}
                          <div className="recommend-item-info">
                            {tpl.domain && (
                              <span className="recommend-item-domain">{tpl.domain}</span>
                            )}
                            {tpl.intent_tags && tpl.intent_tags.length > 0 && (
                              <div className="recommend-item-tags">
                                {tpl.intent_tags.slice(0, 6).map((tag) => (
                                  <span key={tag} className="recommend-tag">#{tag}</span>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* 推荐理由 */}
                          {tpl.reason && (
                            <div className="recommend-item-reason">
                              <span className="reason-label">推荐理由：</span>
                              {tpl.reason}
                            </div>
                          )}

                          {/* 变量提示 */}
                          {tpl.variables && tpl.variables.length > 0 && (
                            <div className="recommend-item-variables">
                              <span className="variables-label">
                                需要填写的变量（{tpl.variables.length} 个）：
                              </span>
                              <div className="variables-list">
                                {tpl.variables.map((v) => (
                                  <span key={v.name} className={`variable-chip ${v.required ? 'variable-required' : ''}`}>
                                    {`{${v.name}}`}
                                    <span className="variable-desc">{v.description}</span>
                                    {v.required && <span className="variable-star">*</span>}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* 操作按钮 */}
                          <div className="recommend-item-actions">
                            <button
                              type="button"
                              className="recommend-btn recommend-btn-primary"
                              onClick={() => applyTemplate(tpl)}
                              disabled={isRunning}
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="9 11 12 14 22 4" />
                                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                              </svg>
                              使用此模板
                            </button>
                            <button
                              type="button"
                              className="recommend-btn recommend-btn-secondary"
                              onClick={() => setExpandedTemplate(isExpanded ? null : `${idx}-${tpl.node_id}`)}
                            >
                              {isExpanded ? '收起详情' : '查看模板内容'}
                            </button>
                          </div>

                          {/* 展开后的完整模板内容 */}
                          {isExpanded && tpl.template_text && (
                            <div className="recommend-template-preview">
                              <div className="preview-header">完整模板内容（点击「使用此模板」后会自动填充到输入框）：</div>
                              <pre className="preview-content">{tpl.template_text}</pre>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* 底部提示 */}
                  <div className="recommend-footer">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="16" x2="12" y2="12" />
                      <line x1="12" y1="8" x2="12.01" y2="8" />
                    </svg>
                    <span>选择模板后修改【...】占位符即可，未填写的占位符将使用默认值</span>
                  </div>
                </div>
              </div>
            )}

            {/* Assistant Message */}
            <div className="chat-message chat-message-assistant">
              <div
                className="message-avatar assistant-avatar"
                title="点击更换系统头像"
                onClick={() => handleAvatarChange('system')}
                style={{ cursor: 'pointer' }}
              >
                {systemAvatar ? (
                  <img src={systemAvatar} alt="系统头像" className="avatar-img" />
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2a5 5 0 0 1 5 5v3a5 5 0 0 1-10 0V7a5 5 0 0 1 5-5z" />
                    <path d="M3 11v1a9 9 0 0 0 18 0v-1" />
                    <circle cx="9" cy="17" r="1" />
                    <circle cx="15" cy="17" r="1" />
                  </svg>
                )}
              </div>
              <div className="message-content">
                {/* XSS 修复：用 react-markdown + rehype-sanitize 替换 dangerouslySetInnerHTML */}
                <div className="markdown-content">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeSanitize]}
                  >
                    {chat.response}
                  </ReactMarkdown>
                </div>
                {/* V3: 导出提示 — 智能识别导出意图（模板提问 or 自然语言导出请求）*/}
                {(() => {
                  const intent = detectExportIntent(chat);
                  if (!intent.shouldShow || !chat.response) return null;
                  const highlight = intent.highlightFormat;
                  return (
                  <div className="message-export-hint">
                    <div className="export-hint-text">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      <span>
                        {highlight
                          ? `已为你匹配「${highlight === 'docx' ? 'Word' : highlight === 'pptx' ? 'PPT' : highlight === 'mindmap' ? '思维导图' : 'Markdown'}」格式，也可选择其他格式：`
                          : '此回答可导出为以下格式：'}
                      </span>
                    </div>
                    <div className="export-hint-actions">
                      <button
                        className={`export-chip export-chip-md${highlight === 'markdown' ? ' export-chip-highlight' : ''}`}
                        onClick={() => handleExport(idx, 'markdown')}
                        disabled={exportingIdx === idx}
                        title="导出为 Markdown 文件"
                      >
                        Markdown
                      </button>
                      <button
                        className={`export-chip export-chip-docx${highlight === 'docx' ? ' export-chip-highlight' : ''}`}
                        onClick={() => handleExport(idx, 'docx')}
                        disabled={exportingIdx === idx}
                        title="导出为 Word 文档"
                      >
                        Word
                      </button>
                      <button
                        className={`export-chip export-chip-pptx${highlight === 'pptx' ? ' export-chip-highlight' : ''}`}
                        onClick={() => handleExport(idx, 'pptx')}
                        disabled={exportingIdx === idx}
                        title="导出为 PowerPoint 演示文稿"
                      >
                        PPT
                      </button>
                      <button
                        className={`export-chip export-chip-mindmap${highlight === 'mindmap' ? ' export-chip-highlight' : ''}`}
                        onClick={() => handleExport(idx, 'mindmap')}
                        disabled={exportingIdx === idx}
                        title="导出为思维导图（HTML）"
                      >
                        思维导图
                      </button>
                    </div>
                    {/* 行内 toast 提示（成功/失败）— 替代 alert，不弹窗 */}
                    {exportToast && exportToast.idx === idx && (
                      <div className={`export-toast export-toast-${exportToast.type}`}>
                        {exportToast.msg}
                      </div>
                    )}
                  </div>
                  );
                })()}
              </div>
            </div>
          </div>
        ))}

        {/* Running Logs — 透明背景，逐行显示 Agent 工作状态 */}
        {isRunning && logs.length > 0 && (
          <div className="chat-message chat-message-assistant">
            <div className="message-avatar assistant-avatar">
              {systemAvatar ? (
                <img src={systemAvatar} alt="系统头像" className="avatar-img" />
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              )}
            </div>
            <div className="message-content">
              <div className="running-logs">
                {logs.map((log, idx) => (
                  <div key={idx} className="running-log-item" style={{ borderLeftColor: getAgentColorValue(log.agent) }}>
                    <span className="log-agent" style={{ color: getAgentColorValue(log.agent) }}>
                      {getAgentName(log.agent)}
                    </span>
                    <span className="log-message">{log.message}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="chat-input-area">
        {/* V3.2: 隐藏的 file input — 支持多选图片，最多 9 张 */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          style={{ display: 'none' }}
          onChange={handleImageUpload}
        />

        {/* V3.2: 视觉识别进度条弹窗 — 浮在对话框上方 */}
        {/* 当后端推送 vision_progress 时显示，识别完成或失败时自动消失 */}
        {visionProgress && (
          <div className="vision-progress-overlay" role="status" aria-live="polite">
            <div className={`vision-progress-card ${visionProgress.phase === 'error' ? 'vision-progress-card-error' : ''}`}>
              <div className="vision-progress-header">
                <div className={`vision-progress-icon ${visionProgress.phase === 'error' ? 'vision-progress-icon-error' : ''}`}>
                  {visionProgress.phase === 'completed' ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : visionProgress.phase === 'error' ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="15" y1="9" x2="9" y2="15" />
                      <line x1="9" y1="9" x2="15" y2="15" />
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="vision-spinner">
                      <circle cx="12" cy="12" r="10" strokeDasharray="32" strokeDashoffset="8" />
                    </svg>
                  )}
                </div>
                <div className="vision-progress-text">
                  <div className="vision-progress-title">
                    {visionProgress.phase === 'switching' && '正在切换至视觉模型'}
                    {visionProgress.phase === 'recognizing' && `正在识别图片 ${visionProgress.current}/${visionProgress.total}`}
                    {visionProgress.phase === 'completed' && '视觉识别完成'}
                    {visionProgress.phase === 'error' && '视觉识别失败'}
                  </div>
                  <div className="vision-progress-status">{visionProgress.status}</div>
                </div>
                <div className={`vision-progress-count ${visionProgress.phase === 'error' ? 'vision-progress-count-error' : ''}`}>
                  {visionProgress.phase === 'error' ? '!' : `${visionProgress.current}/${visionProgress.total}`}
                </div>
              </div>
              <div className="vision-progress-bar-track">
                <div
                  className={`vision-progress-bar-fill ${visionProgress.phase === 'completed' ? 'completed' : ''} ${visionProgress.phase === 'error' ? 'error' : ''}`}
                  style={{
                    width: `${visionProgress.phase === 'error' ? '100' : (visionProgress.total > 0
                      ? Math.round((visionProgress.current / visionProgress.total) * 100)
                      : 0)}%`,
                  }}
                />
              </div>
              <div className="vision-progress-hint">
                {visionProgress.phase === 'switching' && '正在释放显存并加载 MiniCPM-V 视觉模型（约需 5-10 秒）'}
                {visionProgress.phase === 'recognizing' && '逐张识别中，每张约 5-15 秒，请稍候'}
                {visionProgress.phase === 'completed' && '识别结果已注入 Knowledge Agent，继续执行工作流'}
                {visionProgress.phase === 'error' && '视觉识别失败，工作流将继续执行（无图片内容参考）'}
              </div>
            </div>
          </div>
        )}

        {/* V3.2: 缩略图预览区域 — 用户上传的图片以缩略图形式浮在对话框上方 */}
        {pendingImages.length > 0 && (
          <div className="chat-thumbnails-bar">
            <div className="chat-thumbnails-header">
              <span className="thumbnails-title">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
                待识别图片
              </span>
              <span className="thumbnails-count">{pendingImages.length}/9</span>
              <button
                type="button"
                className="thumbnails-clear-btn"
                onClick={clearPendingImages}
                disabled={isRunning}
                title="清空所有图片"
              >
                清空
              </button>
            </div>
            <div className="chat-thumbnails-list">
              {pendingImages.map((img, idx) => (
                <div key={idx} className="chat-thumbnail-item">
                  <img src={img} alt={`待识别图片 ${idx + 1}`} className="chat-thumbnail-img" />
                  <button
                    type="button"
                    className="chat-thumbnail-remove"
                    onClick={() => removePendingImage(idx)}
                    disabled={isRunning}
                    title="移除此图片"
                    aria-label={`移除图片 ${idx + 1}`}
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                  <span className="chat-thumbnail-index">{idx + 1}</span>
                </div>
              ))}
              {/* 上传按钮（在缩略图列表末尾，未达 9 张时显示） */}
              {pendingImages.length < 9 && (
                <button
                  type="button"
                  className="chat-thumbnail-add"
                  onClick={triggerImageUpload}
                  disabled={isRunning || isUploadingImages}
                  title="继续添加图片（最多 9 张）"
                >
                  {isUploadingImages ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="vision-spinner">
                      <circle cx="12" cy="12" r="10" strokeDasharray="32" strokeDashoffset="8" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19" />
                      <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                  )}
                </button>
              )}
            </div>
          </div>
        )}

        {/* V3: 推荐开关工具栏 — 默认常开，点击切换 */}
        {/* mounted 前渲染中性状态（aria-pressed=false, 无 on/off class）以避免 Hydration 警告 */}
        <div className="chat-input-toolbar">
          {/* V3.2: 左侧 — 图片上传按钮 */}
          <button
            type="button"
            className={`image-upload-toggle ${pendingImages.length > 0 ? 'has-images' : ''}`}
            onClick={triggerImageUpload}
            disabled={isRunning || isUploadingImages || pendingImages.length >= 9}
            title={pendingImages.length >= 9
              ? '已达上限 9 张'
              : `上传图片进行视觉识别（${pendingImages.length}/9）`}
            aria-label="上传图片"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <span className="image-upload-label">图片</span>
            {pendingImages.length > 0 && (
              <span className="image-upload-badge">{pendingImages.length}</span>
            )}
          </button>

          {/* 右侧 — 推荐开关 */}
          <button
            type="button"
            className={`recommend-toggle ${mounted && recommendEnabled ? 'recommend-toggle-on' : mounted && !recommendEnabled ? 'recommend-toggle-off' : ''}`}
            onClick={toggleRecommend}
            title={mounted ? (recommendEnabled ? '点击关闭提示词模板推荐' : '点击开启提示词模板推荐') : '提示词模板推荐'}
            aria-pressed={mounted ? recommendEnabled : false}
            suppressHydrationWarning
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18h6" />
              <path d="M10 22h4" />
              <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14" />
            </svg>
            <span className="recommend-toggle-label">
              模板推荐
            </span>
            <span className={`recommend-toggle-status ${mounted && recommendEnabled ? 'on' : mounted && !recommendEnabled ? 'off' : ''}`} suppressHydrationWarning>
              {mounted ? (recommendEnabled ? '已开启' : '已关闭') : '加载中'}
            </span>
          </button>
        </div>
        <div className="chat-input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={(e) => { setInput(e.target.value); handleAutoResize(); }}
            onKeyDown={handleKeyDown}
            placeholder={pendingImages.length > 0
              ? "描述你想了解的图片内容，按 Enter 发送..."
              : "输入您的问题，按 Enter 发送，Shift+Enter 换行..."}
            disabled={isRunning}
            rows={1}
          />
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={!input.trim() || isRunning}
            title="发送"
          >
            {isRunning ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="spinner">
                <circle cx="12" cy="12" r="10" strokeDasharray="32" strokeDashoffset="8" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* V3.2: 图片放大预览 Modal — 点击遮罩层或 ESC 关闭 */}
      {previewImage && typeof document !== 'undefined' && createPortal(
        <div
          className="image-preview-overlay"
          onClick={() => setPreviewImage(null)}
          role="button"
          tabIndex={0}
          aria-label="点击关闭图片预览"
        >
          <img
            src={previewImage}
            alt="图片预览"
            className="image-preview-large"
            onClick={(e) => e.stopPropagation()}
          />
          <button
            type="button"
            className="image-preview-close"
            onClick={() => setPreviewImage(null)}
            aria-label="关闭预览"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>,
        document.body
      )}

      {/* V4.3: 头像选择器弹窗 */}
      {showAvatarPicker && typeof document !== 'undefined' && createPortal(
        <div className="avatar-picker-overlay" onClick={() => setShowAvatarPicker(false)}>
          <div className="avatar-picker-modal" onClick={(e) => e.stopPropagation()}>
            <div className="avatar-picker-header">
              <h3>更换{avatarPickerTarget === 'user' ? '用户' : '系统'}头像</h3>
              <button className="avatar-picker-close" onClick={() => setShowAvatarPicker(false)}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div className="avatar-picker-body">
              <div className="avatar-picker-preview">
                <div className="avatar-picker-circle">
                  {(avatarPickerTarget === 'user' ? userAvatar : systemAvatar) ? (
                    <img
                      src={avatarPickerTarget === 'user' ? (userAvatar ?? '') : (systemAvatar ?? '')}
                      alt="当前头像"
                    />
                  ) : (
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      {avatarPickerTarget === 'user' ? (
                        <>
                          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                          <circle cx="12" cy="7" r="4" />
                        </>
                      ) : (
                        <>
                          <path d="M12 2a5 5 0 0 1 5 5v3a5 5 0 0 1-10 0V7a5 5 0 0 1 5-5z" />
                          <path d="M3 11v1a9 9 0 0 0 18 0v-1" />
                          <circle cx="9" cy="17" r="1" />
                          <circle cx="15" cy="17" r="1" />
                        </>
                      )}
                    </svg>
                  )}
                </div>
              </div>

              <div className="avatar-picker-actions">
                <button
                  className="avatar-picker-btn avatar-picker-btn--upload"
                  onClick={() => avatarFileRef.current?.click()}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  上传自定义图片
                </button>
                <button
                  className="avatar-picker-btn avatar-picker-btn--reset"
                  onClick={() => handleResetAvatar(avatarPickerTarget)}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="1 4 1 10 7 10" />
                    <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
                  </svg>
                  恢复默认头像
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* V4.3: 隐藏的头像文件上传 */}
      <input
        ref={avatarFileRef}
        type="file"
        accept="image/*"
        style={{ display: 'none' }}
        onChange={handleAvatarFileUpload}
      />
    </div>
  );
};

export default ChatInterface;
