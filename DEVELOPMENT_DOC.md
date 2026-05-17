# AgentMatrix 完整开发文档

> **项目名称**: AgentMatrix — 多智能体动态协同与国产算力优化平台
> **文档版本**: v2.0
> **编写日期**: 2026-05-17
> **适用版本**: AgentMatrix 0.1.0

---

## 目录

1. [项目概述](#一项目概述)
2. [技术架构总览](#二技术架构总览)
3. [模型配置说明](#三模型配置说明)
4. [核心Agent系统详解](#四核心agent系统详解)
5. [工作流系统详解](#五工作流系统详解)
6. [评审系统详解（Review + Judge）](#六评审系统详解)
7. [LLM客户端架构](#七llm客户端架构)
8. [知识库系统](#八知识库系统)
9. [提词系统（Prompt工程）](#九提词系统prompt工程)
10. [前端界面说明](#十前端界面说明)
11. [API接口完整清单](#十一api接口完整清单)
12. [启动方式（评委调试指南）](#十二启动方式评委调试指南)
13. [项目目录结构](#十三项目目录结构)

---

## 一、项目概述

AgentMatrix 是一个**多智能体动态协同与国产算力优化平台**，核心设计思路为：

- **简单任务**：由本地轻量模型（Ollama 部署的 qwen2.5:1.5b / phi4-mini:3.8b）在本地处理，零成本、低延迟
- **复杂任务**：动态调用云端大模型（DeepSeek API）进行增强生成，保证输出质量
- **智能调度**：由 Judge Agent 评估任务复杂度，自动决策任务执行路径（本地 / 云端）

### 1.1 核心特点

| 特性 | 说明 |
|------|------|
| 多智能体协同 | 6个专业Agent按固定流水线协作完成任务 |
| 端云协同 | 本地模型与云端API动态切换，成本可控 |
| 知识库增强 | 内置知识库和领域知识文件，提升回答质量 |
| 流式输出 | 支持SSE流式响应，实时展示每个Agent的进展 |
| 可视化仪表盘 | React前端实时展示Agent状态、评审决策、API调用明细 |

### 1.2 六Agent流水线

```
用户输入 → Knowledge Agent → Summary Agent → Writer Agent → Review Agent → Judge Agent → Result Agent → 最终输出
```

| 序号 | Agent ID | 名称 | 职责 | 使用模型 |
|------|----------|------|------|----------|
| 1 | `knowledge` | Knowledge Agent | 知识检索与上下文增强 | qwen2.5:1.5b |
| 2 | `summary` | Summary Agent | 需求摘要与关键信息提取 | qwen2.5:1.5b |
| 3 | `writer` | Writer Agent | 内容生成与初稿撰写 | qwen2.5:1.5b |
| 4 | `review` | Review Agent | 质量评估与修改建议 | phi4-mini:3.8b |
| 5 | `judge` | Judge Agent | 复杂度判断与路径决策 | 规则引擎 |
| 6 | `result` | Result Agent | 成果整合与格式化输出 | qwen2.5:1.5b / DeepSeek |

---

## 二、技术架构总览

### 2.1 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Next.js 14 + TypeScript + Tailwind CSS | React SPA，仪表盘界面 |
| 前端状态管理 | Zustand | 轻量级状态管理 |
| 前端通信 | Axios + SSE + Socket.IO | REST调用 + 流式响应 + WebSocket |
| 后端框架 | FastAPI (Python) | 异步Web框架 |
| 后端验证 | Pydantic v2 | 请求/响应模型校验 |
| 本地模型 | Ollama (qwen2.5:1.5b, phi4-mini:3.8b) | 本地推理引擎 |
| 云端模型 | DeepSeek API (deepseek-r1-distill) | 复杂任务增强 |
| 数据库 | SQLite | 轻量级数据持久化 |
| 实时通信 | python-socketio | WebSocket服务 |

### 2.2 系统架构图（文字描述）

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Next.js :3000)                      │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Dashboard   │ │ Agent Store  │ │ Workflow Store       │ │
│  │ Layout      │ │ (Zustand)    │ │ (Zustand)            │ │
│  └─────────────┘ └──────────────┘ └──────────────────────┘ │
│         │                │                   │               │
│         └────────────────┼───────────────────┘               │
│                          │ HTTP/SSE/WebSocket               │
└──────────────────────────┼──────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────┐
│                    后端 (FastAPI :8000)                      │
│                          │                                   │
│  ┌───────────────────────┼───────────────────────────────┐  │
│  │                  API Layer (/api/v1)                   │  │
│  │  agents | workflow | chat | metrics | knowledge        │  │
│  │  config | export                                       │  │
│  └───────────────────────┼───────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────┼───────────────────────────────┐  │
│  │              Workflow Service (工作流编排)              │  │
│  │  • 顺序执行6个Agent                                    │  │
│  │  • 数据传递与上下文管理                                  │  │
│  │  • SSE流式输出                                          │  │
│  └───────────────────────┼───────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────┼───────────────────────────────┐  │
│  │                  Agent Registry (Agent注册中心)         │  │
│  │  Knowledge │ Summary │ Writer │ Review │ Judge │ Result│  │
│  └───────────────────────┼───────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────┼───────────────────────────────┐  │
│  │                   LLM Client (模型客户端)               │  │
│  │  ┌──────────────┐         ┌──────────────────────┐    │  │
│  │  │ Ollama Client│         │ DeepSeek Client      │    │  │
│  │  │ (本地推理)   │         │ (云端API调用)         │    │  │
│  │  └──────────────┘         └──────────────────────┘    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     Ollama 服务      DeepSeek API      SQLite
     (localhost:      (api.deepseek     (agentmatrix
      11434)           .com)             .db)
```

### 2.3 数据流说明

1. **用户输入** → 前端通过 POST `/api/v1/workflow/execute` 或流式接口发送 `WorkflowInput`
2. **工作流引擎** → 按 `knowledge → summary → writer → review → judge → result` 顺序执行
3. **Agent间数据传递** → 每个Agent的输出存入 `current_context` 字典，后续Agent通过构造特定的输入JSON获取前序Agent的结果
4. **流式输出** → 通过 SSE (Server-Sent Events) 逐个返回每个Agent的执行结果
5. **最终结果** → Result Agent 整合所有Agent输出，生成最终内容返回前端

---

## 三、模型配置说明

### 3.1 本地模型配置

项目使用 **Ollama** 作为本地模型推理引擎，部署了两个模型：

| 模型名称 | 参数量 | 用途 | 分配的Agent |
|----------|--------|------|-------------|
| `qwen2.5:1.5b` | 1.5B | 轻量级任务处理 | Knowledge, Summary, Writer, Result |
| `phi4-mini:3.8b` | 3.8B | 评审任务（需更强推理能力） | Review, Judge |

#### 各Agent使用的本地模型（定义在各Agent的 `__init__` 中）

在 [agents/base/agent.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/agents/base/agent.py#L29) 中，BaseAgent基类定义了默认的本地模型：

```python
# BaseAgent.__init__ (agent.py:29-30)
self.local_model = "qwen2.5:1.5b"   # 默认本地模型
self.cloud_model = "deepseek-r1-distill"  # 默认云端模型
```

各子类Agent会覆盖此配置：

```python
# ReviewAgent (review/agent.py:10) - 使用更强的模型进行评审
self.local_model = "phi4-mini:3.8b"

# JudgeAgent (judge/agent.py:91) - 同样使用更强模型
self.local_model = "phi4-mini:3.8b"
```

#### Ollama连接配置

Ollama服务地址在 [app/config.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/app/config.py#L48) 中配置，并支持自动端口检测：

```python
# app/config.py:48-50
ollama_host: str = "http://localhost:11435"
ollama_model: str = "qwen2.5:1.5b"
ollama_review_model: str = "phi4-mini:3.8b"
```

自动端口检测函数 [app/config.py:6-17](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/app/config.py#L6-L17) 会依次尝试 `11434`, `11435`, `8080` 端口：

```python
async def detect_ollama_port() -> str:
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
```

### 3.2 云端模型配置（DeepSeek API）

DeepSeek API的配置在 [app/config.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/app/config.py#L52-L54) 中：

```python
deepseek_api_key: str = ""
deepseek_api_base: str = "https://api.deepseek.com/v1"
deepseek_model: str = "deepseek-r1-distill"
```

支持运行时动态设置API Key（通过前端配置界面或API），存储在 `api/v1/config/router.py` 的 `_runtime_config` 中。

### 3.3 模型选择逻辑

在 [agents/base/agent.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/agents/base/agent.py#L63-L95) 的 `_call_llm` 方法中：

```python
async def _call_llm(self, prompt: str, model: str = None, use_cloud: bool = False, **kwargs) -> str:
    if use_cloud:
        # 检查运行时配置的API Key
        from api.v1.config.router import _runtime_config
        runtime_api_key = _runtime_config.get("deepseek_api_key")
        if runtime_api_key:
            self.llm_client.deepseek_api_key = runtime_api_key
        llm_model = self.cloud_model  # deepseek-r1-distill
    else:
        llm_model = model or self.local_model  # qwen2.5:1.5b 或 phi4-mini:3.8b

    response = await self.llm_client.generate(prompt, use_cloud=use_cloud, ...)
```

核心逻辑：`use_cloud=True` → 调用DeepSeek API，`use_cloud=False` → 调用Ollama本地模型。

---

## 四、核心Agent系统详解

### 4.1 Agent基类设计

所有Agent继承自 `BaseAgent`（位于 [backend/agents/base/agent.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/agents/base/agent.py)），采用抽象基类模式。

#### 数据模型

```python
class AgentInput(BaseModel):
    content: str                              # 输入内容（必填）
    context: Optional[Dict[str, Any]] = None  # 上下文
    use_llm: bool = False                     # 是否使用LLM
    use_cloud: bool = False                   # 是否使用云端API


class AgentOutput(BaseModel):
    content: str                           # 输出内容
    success: bool = True                   # 是否成功
    message: Optional[str] = None          # 状态消息
    metadata: Optional[Dict[str, Any]] = None  # 元数据（评分、模型等）
    model_used: Optional[str] = None       # 使用的模型名称
```

#### BaseAgent核心属性

```python
class BaseAgent(ABC):
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id         # Agent唯一标识
        self.name = name                 # 显示名称
        self.status = "idle"             # 状态: idle/ready/processing/error/shutdown
        self.current_task = None         # 当前任务描述
        self.last_error = None           # 最近错误
        self.local_model = "qwen2.5:1.5b"      # 本地模型
        self.cloud_model = "deepseek-r1-distill"  # 云端模型
        self.llm_client = get_llm_client() # LLM客户端单例
```

#### 关键方法

| 方法 | 说明 |
|------|------|
| `execute(input_data)` | **抽象方法**，每个Agent必须实现的核心执行逻辑 |
| `initialize()` | 初始化Agent，设置状态为 `ready` |
| `shutdown()` | 关闭Agent，设置状态为 `shutdown` |
| `get_status()` | 获取Agent当前状态（ID、名称、状态、任务、模型等） |
| `_call_llm(prompt, model, use_cloud)` | 调用LLM（本地或云端），所有Agent共用此方法 |
| `_call_llm_chat(messages, model)` | 调用LLM聊天接口 |

### 4.2 Agent注册中心 (AgentRegistry)

位于 [backend/agents/base/agent_registry.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/agents/base/agent_registry.py)。

`AgentRegistry` 负责管理所有Agent实例，在应用启动时一次性注册并初始化：

```python
class AgentRegistry:
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}  # agent_id → Agent实例

    async def initialize_all_agents(self):
        # 按固定顺序注册6个Agent
        self.register_agent(KnowledgeAgent())
        self.register_agent(SummaryAgent())
        self.register_agent(WriterAgent())
        self.register_agent(ReviewAgent())
        self.register_agent(JudgeAgent())
        self.register_agent(ResultAgent())

        # 逐一初始化（设置status为ready）
        for agent in self.agents.values():
            await agent.initialize()

    async def execute_agent(self, agent_id: str, input_data: AgentInput) -> AgentOutput:
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        return await agent.execute(input_data)
```

### 4.3 Knowledge Agent（知识检索Agent）

**文件位置**: [backend/agents/knowledge/agent.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/agents/knowledge/agent.py)

**核心职责**: 接收用户输入，从知识库（`knowledge_base.json`）和领域知识文件（`roletxt/knowledge.txt`）中检索相关知识，增强原始输入内容。

**执行流程**:
1. 检测是否为身份查询（"你是谁"等），如果是则直接返回平台身份信息
2. 从用户输入中提取关键词（匹配预定义关键词列表和知识库关键词）
3. 在领域知识文件（`roletxt/knowledge.txt`）中搜索匹配的领域知识条目
4. 在知识库（`knowledge_base.json`）中搜索通用知识条目
5. 检测是否为跨角色请求（如让Knowledge Agent去"写"内容），如果是且无知识命中则拒绝执行
6. 将检索到的知识以 `【知识增强】` 格式包裹原始输入，传给下游Agent

**输出格式**:
```
【知识增强】
用户查询: 原始输入

【领域知识】
1. [definition] 知识内容
   来源: roletxt/knowledge.txt | 置信度: 0.9

【通用知识】
1. 通用知识内容

【匹配关键词】AI, 系统, 方案
```

**元数据字段说明**:
- `knowledge_count`: 检索到的知识总数
- `domain_knowledge_count`: 领域知识数量
- `general_knowledge_count`: 通用知识数量
- `matched_keywords`: 匹配到的关键词列表
- `enhanced`: 是否成功增强（有知识命中）

### 4.4 Summary Agent（需求摘要Agent）

**文件位置**: [backend/agents/summary/agent.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/agents/summary/agent.py)

**核心职责**: 解析Knowledge Agent的输出，提取用户任务、关键词、需求点，生成结构化大纲。

**执行流程**:
1. 解析Knowledge Agent的结构化输出，从中提取 `original_question` 和 `knowledge_points`
2. 判断任务类型（创意类 vs 正常任务类）— 创意类跳过方案大纲生成
3. 提取关键词：从预定义的100+关键词列表中匹配
4. 提取需求点：使用正则匹配"需要/必须/应该/包含"等模式
5. 根据任务类型生成方案大纲

**大纲生成逻辑**:
```python
def _generate_outline(self, question, keywords, requirements):
    task_type = self._determine_task_type(question, keywords)

    if task_type == "活动策划":
        return ["一、活动概述", "二、活动目标", "三、活动流程安排",
                "四、人员分工", "五、预算规划", "六、安全保障措施", "七、应急预案"]
    elif task_type == "方案设计":
        return ["一、需求分析", "二、方案目标", "三、方案设计",
                "四、实施步骤", "五、风险评估", "六、预期成果"]
    elif task_type == "分析报告":
        return ["一、问题描述", "二、现状分析", "三、解决方案", "四、实施建议"]
    # ...更多任务类型
```

**输出格式（JSON）**:
```json
{
  "task": "核心任务描述",
  "original_question": "用户原始问题",
  "keywords": ["关键词1", "关键词2"],
  "knowledge_points": [...],
  "requirements": ["需求点1", ...],
  "outline": ["一、概述", "二、内容", ...],
  "summary": "用户需求：... | 关键词：... | 需求点：N项"
}
```

### 4.5 Writer Agent（内容生成Agent）

**文件位置**: [backend/agents/writer/agent.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/agents/writer/agent.py)

**核心职责**: 接收Summary Agent的结构化输出，根据任务类型选择对应的写作模板，调用LLM生成完整内容。

**模板系统**: Writer Agent内置了8种文档模板（定义在 `WRITER_TEMPLATES` 字典中）：

| 模板名称 | 适用场景 | 章节数 |
|----------|----------|--------|
| 发言稿 | 演讲、致辞 | 6章 |
| 竞选稿 | 竞选、竞聘 | 6章 |
| 工作报告 | 工作总结、述职 | 7章 |
| 操作指南 | 使用手册、教程 | 6章 |
| 策划案 | 活动策划、项目方案 | 7章 |
| 会议纪要 | 会议记录 | 6章 |
| 方案设计 | 系统方案、技术方案 | 6章 |
| 通用任务 | 其他所有任务 | 4章 |

**模板匹配逻辑** (`TEMPLATE_KEYWORD_MAP`):
```python
TEMPLATE_KEYWORD_MAP = [
    (["发言稿", "演讲稿", "讲话稿", "发言", "致辞"], "发言稿"),
    (["竞选稿", "竞选", "选举", "竞聘"], "竞选稿"),
    (["工作报告", "工作汇报", "工作总结", "述职报告"], "工作报告"),
    (["操作指南", "使用指南", "用户手册", "教程"], "操作指南"),
    (["策划案", "策划方案", "活动方案", "项目方案"], "策划案"),
    (["会议纪要", "会议记录", "会谈纪要"], "会议纪要"),
    (["方案设计", "设计方案", "系统方案", "技术方案"], "方案设计"),
]
```

**执行流程**:
1. 解析Summary Agent的JSON输出
2. 检测是否为简单对话（问候/身份询问/感谢等），如果是则生成简短回复
3. 检测是否为简单事实问答（有知识库命中且问题简单），如果是则生成知识问答回复
4. 确定任务类型，选择对应模板
5. 将模板、知识、需求组合成Prompt，调用本地LLM生成内容

**简单对话检测逻辑** (`_detect_simple_conversation`):
使用正则表达式匹配模式：
- `^(你好|您好|hi|hello|嗨|hey|早上好|下午好|晚上好)` — 问候
- `^(在吗|在不在|有人吗|你在吗)` — 试探
- `^(你是谁|你叫什么|你的名字|自我介绍|你是什么)` — 身份询问
- `^(谢谢|感谢|辛苦|多谢|thanks)` — 感谢

### 4.6 Review Agent（质量评审Agent）— 详见第六章

### 4.7 Judge Agent（复杂度判断Agent）— 详见第六章

### 4.8 Result Agent（结果导出Agent）

**文件位置**: [backend/agents/result/agent.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/agents/result/agent.py)

**核心职责**: 整合所有Agent的输出，根据Judge决策决定是否需要云端增强，生成最终结果。

**执行流程**:
1. 解析输入数据（包含所有前序Agent的输出）
2. 检查是否需要云端增强（`judge_decision == "cloud_enhance" AND cloud_mode != "none" AND 有API Key`）
3. 如果需要云端增强，调用DeepSeek API重新生成更高质量的内容
4. 格式化最终结果（清理JSON包装、去除知识增强标记）
5. 返回干净的最终内容

**云端增强逻辑** (`_enhance_with_cloud`):
```python
async def _enhance_with_cloud(self, user_task, summary_result, writer_output, cloud_mode):
    # 提取摘要信息（关键词、需求点）
    summary_text = self._extract_summary_text(summary_result)

    prompt = f"""
请根据以下信息，重新生成一份高质量、专业的完整回复。

【用户问题】{user_task}
【需求摘要】{summary_text}
【重写要求】
1. 内容必须专业、准确、有深度
2. 直接回应用户的问题，不要偏离
3. 使用清晰的 Markdown 格式
...
"""
    # 调用DeepSeek API
    response = await self._call_llm(prompt, use_cloud=True, ...)
    return response
```

---

## 五、工作流系统详解

工作流系统是 AgentMatrix 的核心编排引擎，位于两个关键文件中：

| 文件 | 说明 |
|------|------|
| [backend/core/workflow/service.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/core/workflow/service.py) | 工作流服务类（核心业务逻辑） |
| [backend/api/v1/workflow/router.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/api/v1/workflow/router.py) | 工作流API路由（HTTP接口 + SSE流式接口） |

### 5.1 WorkflowService 类

#### 核心属性

```python
class WorkflowService:
    def __init__(self, agent_registry: AgentRegistry):
        self.agent_registry = agent_registry
        self.agent_order = ["knowledge", "summary", "writer", "review", "judge", "result"]
        self.agent_names = {
            "knowledge": "Knowledge Agent",
            "summary": "Summary Agent",
            ...
        }
```

#### execute 方法 — 工作流核心执行逻辑

这是整个系统最核心的方法（`workflow/service.py:30-176`），按顺序驱动6个Agent完成任务。以下是完整流程的逐行解析：

**阶段一：初始化**

```python
async def execute(self, input_data: WorkflowInput) -> WorkflowOutput:
    steps: List[WorkflowStep] = []         # 记录所有步骤
    current_context = input_data.context or {}  # 上下文（Agent间数据传递）
    executed_locally = True                # 默认本地执行
    complexity_score = 0.0                 # 复杂度评分
    review_score = 0.0                     # 评审评分
    judge_decision = "local_output"        # Judge决策
    cloud_mode = "none"                    # 云端模式
    knowledge_found = False                # 知识库是否命中
    start_time = time.time()
```

**阶段二：串行执行6个Agent**

```python
for i, agent_id in enumerate(self.agent_order):
    agent_start = time.time()
    agent_name = self.agent_names.get(agent_id, agent_id)
```

**Agent间数据传递的关键设计** — 每个Agent的输入是不同的：

```python
if agent_id == "review":
    # Review Agent 需要：用户任务 + 摘要 + Writer输出
    review_input = json.dumps({
        "user_task": original_user_input,
        "summary": summary_result,
        "writer_output": writer_output
    })
    agent_input = AgentInput(content=review_input, use_llm=True, use_cloud=False)

elif agent_id == "judge":
    # Judge Agent 需要：用户任务 + 摘要 + 评审结果 + Writer输出 + 知识命中状态
    judge_input = json.dumps({
        "user_task": original_user_input,
        "summary_result": summary_result,
        "review_result": review_result,
        "writer_output": writer_output,
        "knowledge_found": knowledge_found
    })
    agent_input = AgentInput(content=judge_input, use_llm=False, use_cloud=False)

elif agent_id == "result":
    # Result Agent 需要：所有前序Agent的输出
    result_input = json.dumps({
        "user_task": original_user_input,
        "summary_result": summary_result,
        "review_result": review_result,
        "judge_result": current_context.get("judge", "{}"),
        "writer_output": writer_output,
        "executed_locally": executed_locally,
        "complexity_score": complexity_score,
        "judge_decision": judge_decision,
        "cloud_mode": cloud_mode
    })
    need_cloud = judge_decision == "cloud_enhance" and cloud_mode != "none"
    agent_input = AgentInput(content=result_input, use_llm=True, use_cloud=need_cloud)

else:
    # Knowledge / Summary / Writer 直接使用上一步的输出
    agent_input = AgentInput(content=current_input, use_llm=True, use_cloud=False)
```

**阶段三：调用Agent并记录步骤**

```python
output = await self.agent_registry.execute_agent(agent_id, agent_input)
agent_duration = time.time() - agent_start

step = WorkflowStep(
    agent_id=agent_id,
    agent_name=agent_name,
    input=current_input,
    output=output.content,
    success=output.success,
    duration_seconds=agent_duration,
    metadata=output.metadata or {}
)
steps.append(step)

current_context[agent_id] = output.content  # 存入上下文供后续Agent使用
```

**阶段四：提取关键Agent的输出**

这是工作流中关键的决策链路：

```python
if agent_id == "knowledge":
    # 检查知识库是否命中（knowledge_count > 0）
    knowledge_found = output.metadata.get("knowledge_count", 0) > 0

if agent_id == "summary":
    summary_result = output.content  # 保存摘要供Review/Judge/Result使用

if agent_id == "writer":
    writer_output = output.content   # 保存Writer输出

if agent_id == "review":
    review_result = output.content
    review_data = json.loads(output.content)
    review_score = review_data.get("review_score", 0.0)  # 提取评审分数

if agent_id == "judge":
    judge_data = json.loads(output.content)
    complexity_score = judge_data.get("complexity_score", 0.0)
    judge_decision = judge_data.get("decision", "local_output")
    cloud_mode = judge_data.get("cloud_mode", "none")
    executed_locally = judge_decision == "local_output"
    # ↑ 决定最终是否本地执行
```

**阶段五：确定最终结果**

```python
# 默认使用Writer的输出
final_result = writer_output

# 如果Judge决定云端增强，使用Result Agent的云端输出
if judge_decision == "cloud_enhance" and cloud_mode != "none":
    final_result = output.content if steps else writer_output
```

**最终返回**:
```python
return WorkflowOutput(
    final_result=final_result,
    steps=steps,
    executed_locally=executed_locally,
    total_duration_seconds=total_duration,
    start_time=workflow_start,
    end_time=workflow_end,
    complexity_score=complexity_score
)
```

### 5.2 流式执行接口 (SSE)

位于 `workflow/router.py:407-618` 的 `execute_workflow_stream` 函数，是一个异步生成器，通过 SSE 逐个推送每个Agent的执行状态到前端。

**流式消息类型**:

| type | 触发时机 | 关键字段 |
|------|----------|----------|
| `start` | 工作流开始 | message, timestamp |
| `agent_start` | 每个Agent开始执行 | agent_id, agent_name |
| `agent_complete` | 每个Agent执行完成 | agent_id, duration, success, output_length |
| `judge_decision` | Judge决策完成 | complexity_score, executed_locally, decision, category, reason |
| `agent_error` | Agent执行出错 | agent_id, error |
| `complete` | 工作流全部完成 | final_result, executed_locally, complexity_score, total_duration |
| `error` | 工作流执行失败 | error |

前端 (`DashboardLayout/index.tsx:337-447`) 的 `executeWithAPI` 函数使用 `fetch` + `ReadableStream` 消费SSE流，根据不同 `type` 更新UI：
- `agent_start` → 更新Agent状态为 `processing`，高亮当前节点
- `agent_complete` → 更新Agent状态为 `completed`，记录日志
- `judge_decision` → 更新复杂度评分和决策，更新流水线分支显示
- `complete` → 显示最终结果

### 5.3 并行执行接口

`workflow/router.py:272-389` 的 `execute_workflow_parallel` 接口与串行执行的主要区别在于使用辅助函数 `execute_agent_with_timing` 封装了Agent调用，但仍然是按顺序执行的。这个接口的输入格式不同（没有为Review/Judge构造特殊的JSON输入），可以看作是简化版的执行方式。

### 5.4 缓存机制

工作流结果缓存 (`SimpleCache` 类，定义在 `workflow/router.py:17-48`):

```python
class SimpleCache:
    def __init__(self, maxsize: int = 100, ttl: int = 300):
        self.maxsize = maxsize  # 最大容量
        self.ttl = ttl          # 过期时间（秒）
        self.cache: Dict[str, Tuple[Any, float]] = {}
```

缓存规则（`workflow/router.py:261-262`）:
```python
# 仅缓存本地执行且结果长度 < 5000 的结果
if executed_locally and len(final_result) < 5000:
    workflow_cache[cache_key] = result
```

---

## 六、评审系统详解

评审系统由两个Agent组成，形成完整的质量评估和决策链路：

```
Writer输出 → Review Agent（质量评审）→ Judge Agent（复杂度判断 + 最终决策）→ Result Agent
```

### 6.1 Review Agent（质量评审Agent）

**文件位置**: [backend/agents/review/agent.py](file:///d:/AAAtask%20backend/fin/AgentMatrix/AgentMatrix/backend/agents/review/agent.py)

Review Agent使用 **phi4-mini:3.8b** 模型（比其他Agent的qwen2.5:1.5b更强），因为评审需要更强的语义理解和判断能力。

#### 评审维度（五维评估体系）

| 维度 | 说明 | 评估方式 |
|------|------|----------|
| `structure` (结构完整性) | 检查是否有清晰的章节、标题、逻辑层次 | 检测 `# `、`一、`、`1.` 等标记 |
| `relevance` (需求相关性) | 检查是否符合用户原始需求 | 关键词匹配度 |
| `richness` (内容丰富度) | 检查内容是否详细、全面 | 长度检查 + 内容深度 |
| `professional` (专业性) | 检查语言表达是否专业、正式 | 是否有总结/结论 |
| `actionable`