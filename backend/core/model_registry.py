"""ModelRegistry — 模型注册中心（单一数据源）

设计原则:
- 所有模型名只在这里定义一次，其他地方全部从这里读
- 按 Agent ID 分配模型，未来可异构（如 Writer 用 14B，Result 用 7B）
- 模型无关：不假设任何特定厂商或模型系列
- 从 .env 读取，支持运行时配置覆盖
- 未来切换更大模型只需改 .env 或本文件
- 启动时验证模型可用性，不存在时打 warning

使用方式:
    from core.model_registry import get_model, ModelRegistry

    model = get_model("writer")  # 获取 Writer Agent 使用的本地模型
    cloud = ModelRegistry.cloud_model()  # 获取云端模型
"""

import logging
from typing import Dict, Optional, Set
import httpx

logger = logging.getLogger(__name__)


class ModelRegistry:
    """模型注册中心 — 按 Agent 分配，模型无关"""

    _instance: Optional["ModelRegistry"] = None

    def __init__(self):
        self._load_config()
        self._available_models: Set[str] = set()
        self._check_availability()

    def _load_config(self):
        """从 settings 加载模型配置（延迟导入避免循环依赖）"""
        from app.config import settings

        # 本地默认模型（所有 Agent 共用，除非单独配置）
        self._default_local = getattr(settings, "ollama_model", "qwen2.5:7b")

        # 按 Agent 分配的模型映射
        # 未来可通过 .env 的 OLLAMA_AGENT_MODELS 配置异构分配
        # 格式: OLLAMA_AGENT_MODELS=writer:qwen2.5:14b,review:deepseek-r1:7b
        self._agent_models: Dict[str, str] = {}
        agent_models_str = getattr(settings, "ollama_agent_models", "")
        if agent_models_str:
            for pair in agent_models_str.split(","):
                pair = pair.strip()
                if ":" in pair:
                    agent_id, model = pair.split(":", 1)
                    self._agent_models[agent_id.strip()] = model.strip()

        # 云端增强模型
        self._cloud_model = getattr(settings, "deepseek_model", "deepseek-v4-pro")
        # Ollama 主机地址
        self._ollama_host = getattr(settings, "ollama_host", "http://localhost:11434")

        # V3.2: 视觉模型（MiniCPM-V，插件式加载，与主模型互斥）
        # 从 .env 的 OLLAMA_VISION_MODEL 读取，默认 minicpm-v:latest (q4_0, 5.5GB)
        # 遵循规则十一：8GB VRAM 只能用 q4_0，禁止 q6_K/q8_0
        self._vision_model = getattr(settings, "ollama_vision_model", "minicpm-v:latest")

    def _check_availability(self):
        """启动时检查 Ollama 中已安装的模型列表"""
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self._ollama_host}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    self._available_models = {
                        m.get("name", "") for m in models if m.get("name")
                    }
                    logger.info(
                        f"ModelRegistry initialized: default_local={self._default_local}, "
                        f"cloud={self._cloud_model}, "
                        f"agent_overrides={self._agent_models}, "
                        f"ollama_available={len(self._available_models)} models"
                    )

                    # 检查配置的模型是否存在
                    self._warn_if_missing(self._default_local, "default_local")
                    for agent_id, model in self._agent_models.items():
                        self._warn_if_missing(model, f"agent[{agent_id}]")
                    # V3.2: 检查视觉模型
                    self._warn_if_missing(self._vision_model, "vision_model")
                else:
                    logger.warning(
                        f"ModelRegistry: Ollama 返回非 200 ({resp.status_code})，跳过模型可用性检查"
                    )
        except Exception as e:
            logger.warning(
                f"ModelRegistry: 无法连接 Ollama ({self._ollama_host})，跳过模型可用性检查。"
                f"请确认 Ollama 服务已启动。错误: {e}"
            )

    def _warn_if_missing(self, model: str, context: str):
        """模型不存在时打 warning"""
        if not model:
            return
        if model not in self._available_models:
            logger.warning(
                f"ModelRegistry: 模型 '{model}' (context={context}) 未在 Ollama 中安装。"
                f"请运行: ollama pull {model}"
            )

    @classmethod
    def get_instance(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reload(cls):
        """重新加载配置（用于运行时切换模型）"""
        cls._instance = None
        return cls.get_instance()

    # ============================================================
    # 查询接口
    # ============================================================

    @classmethod
    def get_local_model(cls, agent_id: str = "default") -> str:
        """获取指定 Agent 的本地模型名

        Args:
            agent_id: Agent ID（knowledge/writer/review/judge/result/summary/extractor）

        Returns:
            模型名（如 "qwen2.5:7b"）
        """
        instance = cls.get_instance()
        return instance._agent_models.get(agent_id, instance._default_local)

    @classmethod
    def cloud_model(cls) -> str:
        """获取云端增强模型名"""
        return cls.get_instance()._cloud_model

    @classmethod
    def vision_model(cls) -> str:
        """获取视觉模型名（MiniCPM-V，插件式加载）"""
        return cls.get_instance()._vision_model

    @classmethod
    def all_models(cls) -> Dict[str, str]:
        """获取所有模型配置（用于 /health 接口展示）"""
        instance = cls.get_instance()
        return {
            "default_local": instance._default_local,
            "cloud": instance._cloud_model,
            "vision": instance._vision_model,
            "agent_overrides": dict(instance._agent_models),
            "ollama_available": sorted(instance._available_models),
        }

    @classmethod
    def is_model_available(cls, model: str) -> bool:
        """检查指定模型是否在 Ollama 中已安装"""
        instance = cls.get_instance()
        return model in instance._available_models


def get_model(agent_id: str = "default") -> str:
    """快捷函数：获取指定 Agent 的本地模型"""
    return ModelRegistry.get_local_model(agent_id)


def get_cloud_model() -> str:
    """快捷函数：获取云端模型"""
    return ModelRegistry.cloud_model()
