from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field
from typing import List, Dict, Optional
import httpx
from shared.platform import get_log_file_path, get_env_file_path


async def detect_ollama_port() -> str:
    """自动检测 Ollama 服务端口"""
    ports = ["11434", "11435", "8080"]
    for port in ports:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://localhost:{port}/api/tags", timeout=2)
                if response.status_code == 200:
                    return f"http://localhost:{port}"
        except:
            continue
    return "http://localhost:11434"


class ModelConfig(BaseSettings):
    name: str
    provider: str
    host: str = ""
    api_key: str = ""
    parameters: Dict[str, float] = {}


class AgentModelMapping(BaseSettings):
    agent_id: str
    local_model: str
    cloud_model: str


class Settings(BaseSettings):
    app_name: str = "AgentMatrix"
    app_version: str = "0.1.0"
    app_env: str = "development"

    # P0: 桌面应用默认只监听回环，避免同网段任意主机访问全部接口。
    # 如需局域网/跨机演示，在 .env 中显式覆盖为 0.0.0.0。
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    server_reload: bool = True

    log_level: str = "INFO"
    log_file: str = get_log_file_path()

    # 默认使用 SQLite（零配置，打开即用），用户可通过 .env 覆盖为 MySQL
    database_url: str = ""  # 空字符串表示使用 SQLite 默认路径

    ollama_host: str = "http://localhost:11434"
    # V4.4: 统一模型 — qwen2.5vl:7b 同时承担文本生成与视觉识别
    # 文本/视觉同模型，消除互斥切换延迟；8GB VRAM 约束下上下文设 4K（100% GPU）
    ollama_model: str = "qwen2.5vl:7b"
    # 按 Agent 分配模型（可选，格式: "writer:qwen2.5:14b,review:deepseek-r1:7b"）
    ollama_agent_models: str = ""
    # V4.4: 视觉模型与主模型统一（qwen2.5vl 原生支持图文输入）
    ollama_vision_model: str = "qwen2.5vl:7b"

    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com/v1"
    # 2026-09-22 佳文定版 / 2026-09-24 修正模型 id：
    # 全部云端调用（云端增强 / 兜底 / 视觉）统一走 **DeepSeek-V4.1-Flash**。
    # ★ 注意命名：该模型的 **API 模型 id 是 `deepseek-flash`**，
    #   "DeepSeek-V4.1-Flash" 是网关 /v1/models 返回的 display_name。
    #   传显示名会直接 400（实测：The supported API model names are
    #   deepseek-flash, deepseek-v4-pro）。所以此处必须写 **id**。
    # 旧值 deepseek-v4-pro 已弃用，任何新增云端调用点都必须读本字段，不得硬编码模型名。
    deepseek_model: str = "deepseek-flash"
    # 云端视觉模型：id 同样是 `deepseek-flash`（/v1/models 显示该 id 的
    #   input_modalities = ["text", "image"]，即自带视觉）。
    # ★ 分流策略（2026-09-22 佳文定版）：**常规识图一律走本地 qwen2.5vl（ollama_vision_model），
    #   不调云端**。本字段只在少数显式场景使用 —— 自学习三层筛网第 2 层的名词/片段拆解比对，
    #   以及本地识别明确失败且值得付成本时的显式升级。不得在常规识别路径上隐式调用。
    deepseek_vision_model: str = "deepseek-flash"

    # ── 自学习三层筛网（2026-09-24 佳文定）──
    # 自学习存入的内容必须过筛子：任何自动学习产出的知识/补丁，
    # 未通过筛网一律不得入库（也不得进入待审队列）。
    filter_net_enabled: bool = True
    # 第 1 层质量门槛：回答质量分下限。佳文口述为"0.85 或 0.8 以上"，
    # 取 0.80 为默认（偏宽松侧），需要收紧改环境变量 FILTER_MIN_QUALITY_SCORE 即可。
    filter_min_quality_score: float = 0.80
    # 第 2/3 层单次校验的最大词条数（限制联网+云端的成本上限）
    filter_max_terms: int = 6
    # 严格模式：True 时要求至少一个**一级**来源（百科/官方/学术），
    # False 时一级或二级（权威机构/主流媒体）均可背书。三级源任何时候都不能单独背书。
    filter_require_tier1: bool = False
    # 第 3 层入库前的二次检索校验（佳文要求写死：不得依据本地知识库判断）
    filter_recheck_enabled: bool = True
    # 自学习知识是否自动并入知识图谱。默认 False = 全部落到待审队列由人工审批；
    # True 才恢复"过筛即自动入库"的旧行为。
    learning_auto_apply: bool = False
    # ── LearningEngine._deepseek_analyze 的三重成本护栏（2026-10-04）──
    # 场景：概念在本地图谱里找不到任何可关联父节点时，请云端判断「是否值得学习」
    # 并给出定义。这是唯一一处「按概念逐条上云」的路径，必须封顶：
    #   ① 总开关：关掉即完全不调云端（本地退回独立节点策略）
    #   ② 日额度：跨进程运行期内的硬上限，防止异常循环把额度烧穿
    #   ③ 最小间隔：两次云调用之间的冷却，避免短时间批量打满
    learning_deepseek_enabled: bool = True
    learning_deepseek_max_per_day: int = 20
    learning_deepseek_min_interval_seconds: int = 30
    # 单次 learn() 最多分析几个概念（防止一次长回答触发 N 次云调用）
    learning_deepseek_max_concepts_per_run: int = 3

    # V3.5 (2026-07-31): Web Search 插件 — 时效性知识库（地点/美食/天气/旅行/评价）
    # 启用后 Knowledge Agent 检测到时效性场景时调用 DuckDuckGo + DeepSeek 摘要
    deepseek_search_enabled: bool = True
    # 时效性知识库 TTL（天）：默认 30 天，过期标记 is_stale=True，再次提问触发刷新
    timely_knowledge_ttl_days: int = 30

    gemini_api_key: str = ""
    gemini_model: str = "gemini-pro"

    complexity_threshold: float = 0.65

    # V4.2: 上下文管理 — 共享上下文窗口上限（token 数）
    # V4.4: qwen2.5vl:7b 统一模型，8GB VRAM 实测 4K 上下文 100% GPU（8K 会 CPU offload）
    context_max_tokens: int = 4096
    # 触发自动压缩的阈值（使用率百分比）
    context_compress_threshold: float = 0.80
    # 触发溢出弹窗的阈值（使用率百分比）
    context_overflow_threshold: float = 0.90

    max_concurrent_tasks: int = 10
    max_retry_attempts: int = 3

    # P0: 默认收敛为显式 localhost 白名单（原默认为 "*" 通配）。
    # 若显式配置为 "*"，main.py 会自动关闭 allow_credentials，
    # 以避免 "通配来源 + 携带凭证" 这一不安全组合。
    #
    # 键名兼容：字段名默认映射为 ALLOWED_ORIGINS_LIST，但历史 .env 用的是
    # ALLOWED_ORIGINS。因 SettingsConfigDict(extra="ignore")，旧键曾被静默丢弃，
    # 导致该项配置从未生效、一直回落到默认的 "*"。此处显式接受两种键名。
    allowed_origins_list: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ALLOWED_ORIGINS_LIST", "ALLOWED_ORIGINS"),
    )

    # ── P0: 本地 API 鉴权 ──
    # 开启后，除 /health、/docs、/static 外，所有 /api/** 与 /ws 均需
    # Authorization: Bearer <token>（WebSocket 用 ?token=）。
    # 仅在本机调试且明确知道风险时才建议关闭。
    auth_enabled: bool = True
    # 开发环境专用：暴露 GET /api/v1/auth/dev-token 供浏览器直连 next dev 时
    # 取令牌（仅接受回环来源）。打包环境下该端点不注册，此开关无效。
    allow_dev_token_endpoint: bool = True

    model_config = SettingsConfigDict(env_file=get_env_file_path(), env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins(self) -> List[str]:
        if self.allowed_origins_list == "*":
            return ["*"]
        if self.allowed_origins_list:
            return [origin.strip() for origin in self.allowed_origins_list.split(",")]
        return ["http://localhost:3000", "http://localhost:8000", "http://localhost:8080"]


settings = Settings()