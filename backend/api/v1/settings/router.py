"""云端模型配置 API — 密钥管理 / 模型切换 / 连接测试

V3.5.1 (2026-07-31): 为桌面端首次启动引导和设置面板提供后端支持
- 配置持久化到 .env 文件（打包环境: %APPDATA%/AgentMatrix/.env）
- 热重载: 保存后立即更新 settings 和 LLMClient 实例
- 密钥脱敏: 读取时只返回前6位 + *** + 后4位
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import aiohttp
import os
import logging

from shared.platform import get_env_file_path
from app.config import settings
from core.llm.client import get_llm_client

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 请求/响应模型 ──

class CloudModelConfig(BaseModel):
    """云端模型配置"""
    api_key: Optional[str] = None          # 新密钥（为 None 表示不修改）
    model: Optional[str] = None            # 模型名称
    api_base: Optional[str] = None         # API 基础地址


class CloudModelStatus(BaseModel):
    """云端模型配置状态（密钥脱敏）"""
    configured: bool                       # 密钥是否已配置
    api_key_masked: str = ""               # 脱敏密钥（sk-123***5678）
    model: str = ""                        # 当前模型
    api_base: str = ""                     # API 基础地址
    provider: str = "deepseek"             # 服务商


class TestResult(BaseModel):
    """连接测试结果"""
    success: bool
    message: str


# ── 工具函数 ──

def _mask_api_key(key: str) -> str:
    """密钥脱敏：前6位 + *** + 后4位"""
    if not key:
        return ""
    if len(key) <= 10:
        return key[:2] + "***"
    return key[:6] + "***" + key[-4:]


def _update_env_file(key: str, value: str) -> None:
    """更新 .env 文件中的指定字段（保留其他字段不变）

    Args:
        key: 环境变量名（如 DEEPSEEK_API_KEY）
        value: 新值
    """
    env_path = get_env_file_path()
    lines = []
    found = False

    # 读取现有内容
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    # 替换或追加目标行
    new_lines = []
    for line in lines:
        # 匹配 KEY=... 格式（忽略注释和空行）
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            k = stripped.split('=', 1)[0].strip()
            if k == key:
                new_lines.append(f"{key}={value}\n")
                found = True
                continue
        new_lines.append(line)

    # 如果没找到该字段，追加到末尾
    if not found:
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines.append('\n')
        new_lines.append(f"{key}={value}\n")

    # 写回文件
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    logger.info(f"[Settings] .env 已更新: {key}={_mask_api_key(value) if 'KEY' in key else value}")


def _reload_settings(config: CloudModelConfig) -> None:
    """热重载 settings 和 LLMClient 实例"""
    client = get_llm_client()

    if config.api_key is not None:
        settings.deepseek_api_key = config.api_key
        client.deepseek_api_key = config.api_key
    if config.model is not None:
        settings.deepseek_model = config.model
        client.deepseek_model = config.model
    if config.api_base is not None:
        settings.deepseek_api_base = config.api_base
        client.deepseek_api_base = config.api_base

    logger.info(
        f"[Settings] 热重载完成: model={settings.deepseek_model}, "
        f"key_configured={bool(settings.deepseek_api_key)}"
    )


# ── API 端点 ──

@router.get("/cloud-model", response_model=CloudModelStatus)
async def get_cloud_model_config():
    """获取当前云端模型配置（密钥脱敏）"""
    api_key = settings.deepseek_api_key
    return CloudModelStatus(
        configured=bool(api_key),
        api_key_masked=_mask_api_key(api_key),
        model=settings.deepseek_model,
        api_base=settings.deepseek_api_base,
        provider="deepseek",
    )


@router.get("/cloud-model/configured")
async def is_cloud_model_configured():
    """检查密钥是否已配置（用于首次启动检测）"""
    return {"configured": bool(settings.deepseek_api_key)}


@router.post("/cloud-model", response_model=CloudModelStatus)
async def save_cloud_model_config(config: CloudModelConfig):
    """保存云端模型配置到 .env 文件并热重载

    - api_key 为 None 或空字符串时不修改（空字符串视为清除密钥）
    - 其他字段为 None 时不修改
    """
    # 写入 .env 文件
    if config.api_key is not None:
        _update_env_file("DEEPSEEK_API_KEY", config.api_key)
    if config.model is not None:
        _update_env_file("DEEPSEEK_MODEL", config.model)
    if config.api_base is not None:
        _update_env_file("DEEPSEEK_API_BASE", config.api_base)

    # 热重载
    _reload_settings(config)

    api_key = settings.deepseek_api_key
    return CloudModelStatus(
        configured=bool(api_key),
        api_key_masked=_mask_api_key(api_key),
        model=settings.deepseek_model,
        api_base=settings.deepseek_api_base,
        provider="deepseek",
    )


@router.post("/cloud-model/test", response_model=TestResult)
async def test_cloud_model_connection(config: CloudModelConfig):
    """测试密钥连接是否有效

    使用传入的临时配置测试，不需要先保存。
    V3.5.1: 改用 aiohttp（与 generate_cloud 一致），避免 httpx 在 uvicorn 事件循环中的兼容性问题。
    """
    api_key = config.api_key or settings.deepseek_api_key
    model = config.model or settings.deepseek_model
    api_base = config.api_base or settings.deepseek_api_base

    if not api_key:
        return TestResult(success=False, message="API 密钥未设置")

    url = f"{api_base}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    return TestResult(success=True, message="连接成功，密钥有效")
                elif response.status == 401:
                    return TestResult(success=False, message="密钥无效，请检查密钥是否正确")
                elif response.status == 403:
                    return TestResult(success=False, message="密钥无权限访问该模型")
                else:
                    error_text = await response.text()
                    logger.warning(f"[Settings] Test connection failed: {response.status} - {error_text[:200]}")
                    return TestResult(
                        success=False,
                        message=f"连接失败（状态码: {response.status}）",
                    )
    except aiohttp.ClientError as e:
        logger.error(f"[Settings] Test connection aiohttp error: {e}")
        return TestResult(success=False, message=f"连接失败: {str(e)}")
    except Exception as e:
        logger.error(f"[Settings] Test connection unexpected error: {e}")
        return TestResult(success=False, message=f"连接失败: {str(e)}")
