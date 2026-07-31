/**
 * 云端模型配置 API — 密钥管理 / 模型切换 / 连接测试
 *
 * V3.5.1: 桌面端首次启动引导和设置面板的后端接口封装
 */
import api from './agentService';

export interface CloudModelStatus {
  configured: boolean;
  api_key_masked: string;
  model: string;
  api_base: string;
  provider: string;
}

export interface CloudModelConfig {
  api_key?: string | null;
  model?: string | null;
  api_base?: string | null;
}

export interface TestResult {
  success: boolean;
  message: string;
}

/** 检查密钥是否已配置（用于首次启动检测） */
export async function isCloudModelConfigured(): Promise<boolean> {
  try {
    const res = await api.get<{ configured: boolean }>('/settings/cloud-model/configured');
    return res.data.configured;
  } catch {
    return false;
  }
}

/** 获取当前云端模型配置（密钥脱敏） */
export async function getCloudModelConfig(): Promise<CloudModelStatus> {
  const res = await api.get<CloudModelStatus>('/settings/cloud-model');
  return res.data;
}

/** 保存云端模型配置到 .env 并热重载 */
export async function saveCloudModelConfig(config: CloudModelConfig): Promise<CloudModelStatus> {
  const res = await api.post<CloudModelStatus>('/settings/cloud-model', config);
  return res.data;
}

/** 测试密钥连接是否有效 */
export async function testCloudModelConnection(config: CloudModelConfig): Promise<TestResult> {
  const res = await api.post<TestResult>('/settings/cloud-model/test', config);
  return res.data;
}
