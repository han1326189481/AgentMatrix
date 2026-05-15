# AgentMatrix 后端开发规范文档

## 一、项目概述

本文档定义了 AgentMatrix 后端项目的开发规范，确保代码质量、API一致性和与前端的正确对接。

---

## 二、技术栈规范

| 分类 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 框架 | FastAPI | >=0.110.0 | 异步Web框架 |
| 语言 | Python | 3.12+ | 类型注解 |
| 数据验证 | Pydantic | >=2.6.0 | 数据模型与校验 |
| 数据库 | SQLAlchemy | >=2.0.0 | ORM框架 |
| 数据库引擎 | SQLite | - | 开发环境默认 |
| 本地模型 | Ollama | >=0.1.0 | Qwen2.5-3B |
| 云端API | Google Generative AI | >=0.5.0 | Gemini Pro |
| HTTP客户端 | aiohttp | >=3.9.0 | 异步HTTP请求 |
| 日志 | loguru | >=0.7.0 | 日志管理 |
| WebSocket | websockets | >=12.0 | 实时通信 |
| 缓存 | cachetools | - | TTL缓存 |
| 系统监控 | psutil | >=5.9.0 | 资源监控 |
| 导出 | python-pptx / python-docx | - | 文件导出 |

---

## 三、项目结构规范

```
backend/
├── agents/                        # Agent实现
│   ├── base/                      # Agent基类
│   │   ├── agent.py               # BaseAgent抽象类
│   │   └── agent_registry.py      # Agent注册中心
│   ├── knowledge/                 # Knowledge Agent
│   ├── summary/                   # Summary Agent
│   ├── writer/                    # Writer Agent
│   ├── review/                    # Review Agent
│   ├── judge/                     # Judge Agent
│   └── result/                    # Result Agent
├── api/                           # API路由
│   ├── v1/                        # V1版本API
│   │   ├── router.py              # 路由聚合
│   │   ├── agents/                # Agent相关接口
│   │   ├── workflow/              # 工作流相关接口
│   │   ├── chat/                  # 聊天相关接口
│   │   ├── metrics/               # 指标相关接口
│   │   ├── knowledge/             # 知识库相关接口
│   │   └── export/                # 导出相关接口
│   └── websocket/                 # WebSocket管理
│       └── manager.py             # WebSocket连接管理器
├── app/                           # 应用配置
│   ├── main.py                    # FastAPI应用入口
│   ├── config.py                  # 配置管理（Pydantic Settings）
│   ├── database.py                # 数据库初始化
│   └── dependencies.py            # 依赖注入
├── core/                          # 核心服务
│   ├── llm/                       # LLM客户端
│   │   └── client.py              # 本地/云端双模式LLM调用
│   ├── workflow/                  # 工作流服务
│   │   └── service.py             # 工作流编排与执行
│   ├── dynamic_router/            # 动态算力路由
│   │   └── router.py              # 复杂度判断与路由决策
│   ├── knowledge/                 # 知识库核心
│   └── export/                    # 导出核心
├── knowledge/                     # 知识库数据
│   ├── service.py                 # 知识库服务
│   └── knowledge_base.json        # 知识库数据文件
├── models/                        # 数据模型
│   ├── agent.py                   # Agent相关模型
│   ├── workflow.py                # 工作流相关模型
│   └── db_models.py               # 数据库模型（SQLAlchemy）
├── prompts/                       # Prompt模板
│   ├── template_manager.py        # 模板管理器
│   ├── rules/                     # Prompt规则
│   └── templates/                 # Prompt模板文件
├── services/                      # 业务服务
│   └── agent_service.py           # Agent业务逻辑
├── utils/                         # 工具函数
│   └── logger.py                  # 日志工具
├── tests/                         # 测试
│   ├── test_agents/               # Agent测试
│   ├── test_api/                  # API测试
│   └── test_workflow/             # 工作流测试
└── .env.example                   # 环境变量示例
```

---

## 四、环境配置规范

### 4.1 环境变量

```env
APP_NAME=AgentMatrix
APP_VERSION=0.1.0
APP_ENV=development

SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_RELOAD=true

LOG_LEVEL=INFO
LOG_FILE=logs/system.log

DATABASE_URL=sqlite:///./agentmatrix.db

OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b

GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-pro

COMPLEXITY_THRESHOLD=0.65

MAX_CONCURRENT_TASKS=10
MAX_RETRY_ATTEMPTS=3

ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 4.2 配置管理

使用 Pydantic Settings 管理配置，从 `.env` 文件读取：

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    app_name: str = "AgentMatrix"
    app_version: str = "0.1.0"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    database_url: str = "sqlite:///./agentmatrix.db"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-pro"
    complexity_threshold: float = 0.65
    allowed_origins: List[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

---

## 五、API路由规范

### 5.1 路由版本与前缀

```
所有API路径: /api/v1/{module}/{action}
健康检查: /health
根路径: /
```

### 5.2 完整API端点清单

#### 健康检查

| 路径 | 方法 | 功能 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/health` | GET | 系统健康检查 | 无 | `{status, agents, version}` |

#### Agent模块 `/api/v1/agents`

| 路径 | 方法 | 功能 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/` | GET | 获取所有Agent状态 | 无 | `{agents: Dict, count: int}` |
| `/{agent_id}` | GET | 获取单个Agent状态 | 无 | `AgentStatus` |
| `/{agent_id}/execute` | POST | 执行单个Agent | `AgentInput` | `AgentOutput` |
| `/{agent_id}/status` | GET | 获取Agent运行状态 | 无 | `AgentStatus` |

#### 工作流模块 `/api/v1/workflow`

| 路径 | 方法 | 功能 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/execute` | POST | 执行工作流（串行） | `WorkflowInput` | `WorkflowOutput` |
| `/execute/parallel` | POST | 执行工作流（并行） | `WorkflowInput` | `WorkflowOutput` |
| `/cache/stats` | GET | 获取缓存统计 | 无 | `{cache_size, max_size, ttl}` |
| `/cache/clear` | POST | 清除缓存 | 无 | `{status, message}` |

#### 聊天模块 `/api/v1/chat`

| 路径 | 方法 | 功能 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/send` | POST | 发送单条消息 | `ChatRequest` | `{response, executed_locally, complexity_score, total_duration, steps_count}` |
| `/send/batch` | POST | 批量发送消息 | `List[ChatRequest]` | `{results: List}` |
| `/health` | GET | 聊天服务健康检查 | 无 | `{status, service, cache_size}` |
| `/cache/stats` | GET | 获取缓存统计 | 无 | `{chat_cache_*, workflow_cache_*}` |
| `/cache/clear` | POST | 清除聊天缓存 | 无 | `{status, message}` |

#### 指标模块 `/api/v1/metrics`

| 路径 | 方法 | 功能 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/` | GET | 获取全部指标 | 无 | `{system, resources, workflow, agents}` |
| `/system` | GET | 获取系统资源指标 | 无 | `{cpu_usage, memory_usage, disk_usage, process_count}` |
| `/increment/{metric_type}` | POST | 递增指标 | `value: float` | `{status, metric, value}` |

#### 知识库模块 `/api/v1/knowledge`

| 路径 | 方法 | 功能 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/` | GET | 获取全部知识库 | 无 | `{knowledge_base, keywords, stats}` |
| `/` | POST | 添加知识 | `KnowledgeItem` | `{status, keyword}` |
| `/stats` | GET | 获取知识库统计 | 无 | `{total_keywords, total_items, ...}` |
| `/keyword/{keyword}` | GET | 按关键词查询 | 无 | `{keyword, content}` |
| `/keyword/{keyword}` | PUT | 更新知识 | `{content: List[str]}` | `{status, keyword}` |
| `/keyword/{keyword}` | DELETE | 删除知识 | 无 | `{status, keyword}` |
| `/search` | GET | 搜索知识 | `query, limit` | `{query, results, count}` |
| `/enhance` | POST | 知识增强 | `content, keywords` | `{original, enhanced, keywords}` |

#### 导出模块 `/api/v1/export`

| 路径 | 方法 | 功能 | 请求体 | 响应体 |
|------|------|------|--------|--------|
| `/markdown` | POST | 导出Markdown | `ExportRequest` | `{status, format, filename, filepath}` |
| `/docx` | POST | 导出Word | `ExportRequest` | `{status, format, filename, filepath}` |
| `/pptx` | POST | 导出PPT | `ExportRequest` | `{status, format, filename, filepath}` |
| `/download/{filename}` | GET | 下载文件 | 无 | FileResponse |
| `/list` | GET | 列出已导出文件 | 无 | `{exports, count}` |

---

## 六、数据模型规范

### 6.1 请求模型

#### AgentInput

```python
class AgentInput(BaseModel):
    content: str                              # 输入内容（必填）
    context: Optional[Dict[str, Any]] = None  # 上下文信息（可选）
```

#### WorkflowInput

```python
class WorkflowInput(BaseModel):
    user_input: str = Field(..., description="用户输入内容")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="上下文信息")
```

#### ChatRequest

```python
class ChatRequest(BaseModel):
    content: str                              # 消息内容（必填）
```

#### KnowledgeItem

```python
class KnowledgeItem(BaseModel):
    keyword: str                              # 关键词（必填）
    content: List[str]                        # 知识内容列表（必填）
```

#### ExportRequest

```python
class ExportRequest(BaseModel):
    content: str                              # 导出内容（必填）
    format: str                               # 导出格式（必填）
    filename: Optional[str] = None            # 文件名（可选）
```

### 6.2 响应模型

#### AgentOutput

```python
class AgentOutput(BaseModel):
    content: str                              # 输出内容
    success: bool = True                      # 是否成功
    message: Optional[str] = None             # 消息
    metadata: Optional[Dict[str, Any]] = None # 元数据
```

#### WorkflowStep

```python
class WorkflowStep(BaseModel):
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str = Field(..., description="Agent名称")
    input: str = Field(..., description="输入内容")
    output: str = Field(..., description="输出内容")
    success: bool = Field(default=True, description="是否成功")
    duration_seconds: float = Field(default=0.0, description="执行耗时")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
```

#### WorkflowOutput

```python
class WorkflowOutput(BaseModel):
    final_result: str = Field(..., description="最终结果")
    steps: List[WorkflowStep] = Field(default_factory=list, description="执行步骤")
    executed_locally: bool = Field(default=True, description="是否本地执行")
    total_duration_seconds: float = Field(default=0.0, description="总耗时")
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: datetime = Field(default_factory=datetime.now, description="结束时间")
    complexity_score: Optional[float] = Field(default=None, description="复杂度评分")
```

#### AgentStatus

```python
class AgentStatus(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    SHUTDOWN = "shutdown"
```

#### AgentInfo

```python
class AgentInfo(BaseModel):
    agent_id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent名称")
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="状态")
    current_task: Optional[str] = Field(default=None, description="当前任务")
    last_error: Optional[str] = Field(default=None, description="最后错误")
    last_active: Optional[datetime] = Field(default=None, description="最后活跃时间")
```

### 6.3 数据库模型（SQLAlchemy）

```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    role = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    user_input = Column(Text)
    final_result = Column(Text)
    executed_locally = Column(Boolean)
    complexity_score = Column(Float)
    total_duration = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class WorkflowStepRecord(Base):
    __tablename__ = "workflow_steps"
    id = Column(String, primary_key=True, index=True)
    execution_id = Column(String, ForeignKey("workflow_executions.id"))
    agent_id = Column(String)
    agent_name = Column(String)
    input_content = Column(Text)
    output_content = Column(Text)
    success = Column(Boolean)
    duration = Column(Float)
    step_order = Column(Integer)

class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, index=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MetricRecord(Base):
    __tablename__ = "metric_records"
    id = Column(Integer, primary_key=True, index=True)
    metric_type = Column(String, index=True)
    value = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
    additional_info = Column(Text)
```

---

## 七、六大Agent规范

### 7.1 Agent定义

| Agent ID | 名称 | 职责 | 执行顺序 |
|----------|------|------|----------|
| `knowledge` | Knowledge Agent | 从知识库检索相关信息 | 1 |
| `summary` | Summary Agent | 提取用户核心需求摘要 | 2 |
| `writer` | Writer Agent | 根据需求生成内容 | 3 |
| `review` | Review Agent | 审核生成内容的质量 | 4 |
| `judge` | Judge Agent | 判断任务复杂度，决定执行路径 | 5 |
| `result` | Result Agent | 输出最终结果 | 6 |

### 7.2 Agent基类

所有Agent必须继承 `BaseAgent`：

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class BaseAgent(ABC):
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.status = "idle"
        self.current_task = None
        self.last_error = None

    @abstractmethod
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        pass

    async def initialize(self) -> None:
        self.status = "ready"

    async def shutdown(self) -> None:
        self.status = "shutdown"

    def get_status(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": self.status,
            "current_task": self.current_task,
            "last_error": self.last_error,
        }
```

### 7.3 Agent注册

通过 `AgentRegistry` 统一管理：

```python
class AgentRegistry:
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        self.agents[agent.agent_id] = agent

    async def initialize_all_agents(self) -> None:
        self.register_agent(KnowledgeAgent())
        self.register_agent(SummaryAgent())
        self.register_agent(WriterAgent())
        self.register_agent(ReviewAgent())
        self.register_agent(JudgeAgent())
        self.register_agent(ResultAgent())
        for agent in self.agents.values():
            await agent.initialize()
```

---

## 八、核心服务规范

### 8.1 LLM客户端

双模式调用：本地(Ollama) / 云端(Gemini)

```python
class LLMClient:
    async def generate_local(self, prompt: str, system_prompt: str = None) -> str:
        # 调用 Ollama 本地模型

    async def generate_cloud(self, prompt: str, system_prompt: str = None) -> str:
        # 调用 Gemini 云端API

    async def generate(self, prompt: str, use_cloud: bool = False, system_prompt: str = None) -> str:
        if use_cloud:
            return await self.generate_cloud(prompt, system_prompt)
        return await self.generate_local(prompt, system_prompt)
```

### 8.2 动态算力路由

根据复杂度评分决定使用本地模型还是云端API：

```python
class DynamicRouter:
    async def route(self, complexity_score: float, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        use_cloud = complexity_score > self.threshold  # 默认阈值0.65
        result = await self.llm_client.generate(prompt, use_cloud=use_cloud, system_prompt=system_prompt)
        return {
            "complexity_score": complexity_score,
            "use_cloud": use_cloud,
            "model": "cloud" if use_cloud else "local",
            "result": result,
            "success": len(result) > 0
        }
```

### 8.3 工作流服务

编排Agent执行流程：

```python
class WorkflowService:
    agent_order = ["knowledge", "summary", "writer", "review", "judge", "result"]

    async def execute(self, input_data: WorkflowInput) -> WorkflowOutput:
        # 按顺序执行所有Agent
        # 记录每步执行状态和耗时
        # Judge步骤提取复杂度评分和执行方式
```

### 8.4 WebSocket管理

实时推送工作流状态：

```python
class WebSocketManager:
    async def broadcast_agent_status(self, agent_statuses: Dict) -> None:
        # 推送Agent状态更新

    async def broadcast_workflow_step(self, step: Dict) -> None:
        # 推送工作流步骤更新

    async def broadcast_final_result(self, result: Dict) -> None:
        # 推送最终结果
```

WebSocket消息格式：

```python
# Agent状态更新
{"type": "agent_status", "data": {...}}

# 工作流步骤更新
{"type": "workflow_step", "data": {...}}

# 最终结果
{"type": "final_result", "data": {...}}
```

---

## 九、开发规范

### 9.1 代码规范

```bash
# 代码检查
ruff check .

# 自动修复
ruff check --fix .

# 格式化
black .

# 运行测试
pytest -v
```

### 9.2 API开发规范

1. **路由定义**：在 `api/v1/{module}/router.py` 中定义
2. **路由注册**：在 `api/v1/router.py` 中聚合
3. **依赖注入**：使用 `Depends()` 注入服务
4. **错误处理**：使用 `HTTPException` 统一处理
5. **响应模型**：使用 `response_model` 指定响应类型

```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()

@router.post("/execute", response_model=WorkflowOutput)
async def execute_workflow(
    input_data: WorkflowInput,
    registry=Depends(get_agent_registry)
):
    try:
        result = await do_something(input_data)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 9.3 新增Agent规范

1. 在 `agents/` 下创建新目录
2. 继承 `BaseAgent` 抽象类
3. 实现 `execute` 方法
4. 在 `AgentRegistry.initialize_all_agents` 中注册

### 9.4 新增API模块规范

1. 在 `api/v1/` 下创建新目录
2. 创建 `router.py` 定义路由
3. 在 `api/v1/router.py` 中注册路由
4. 如需新模型，在 `models/` 中定义

---

## 十、CORS配置

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 十一、启动方式

```bash
# 安装依赖
cd backend
pip install -e .

# 启动开发服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动生产服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 十二、对接要点总结

1. **API路径统一前缀**：`/api/v1/`
2. **请求/响应模型**：严格使用Pydantic模型定义
3. **Agent ID固定**：`knowledge`, `summary`, `writer`, `review`, `judge`, `result`
4. **Judge步骤metadata**：必须包含 `executed_locally` 和 `complexity_score`
5. **复杂度阈值**：默认0.65，通过环境变量配置
6. **WebSocket消息格式**：`{type: string, data: object}`
7. **CORS允许来源**：`http://localhost:3000`
8. **错误响应格式**：`{detail: string}`

---

**文档版本**: v1.0
**创建日期**: 2026-05-13
**适用项目**: AgentMatrix Backend