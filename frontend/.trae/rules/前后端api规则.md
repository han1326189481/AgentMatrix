---
alwaysApply: true
---
# AgentMatrix 前后端对接规则

> 本文档是前后端对接的**强制约束规则**，任何新增或修改API的行为都必须遵守本规则。
> 前端开发参考：`frontend/FE_DEVELOPMENT_SPEC.md`
> 后端开发参考：`backend/BE_DEVELOPMENT_SPEC.md`

---

## 规则一：API路径规范

### 1.1 路径格式

```
基础路径: /api/v1/{模块}/{操作}
```

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| Agent | `/api/v1/agents` | Agent状态与执行 |
| 工作流 | `/api/v1/workflow` | 工作流编排与执行 |
| 聊天 | `/api/v1/chat` | 聊天交互 |
| 指标 | `/api/v1/metrics` | 系统指标监控 |
| 知识库 | `/api/v1/knowledge` | 知识库管理 |
| 导出 | `/api/v1/export` | 文件导出 |

### 1.2 路径命名规则

- 使用小写字母和连字符：`/execute-parallel`（不使用驼峰或下划线）
- 资源用名词，操作用动词：`/agents`（资源）、`/agents/{id}/execute`（操作）
- 路径参数用花括号：`/agents/{agent_id}`

### 1.3 禁止事项

- 禁止在路径中使用大写字母
- 禁止在路径中使用中文
- 禁止跳过版本前缀直接使用 `/agents/...`

---

## 规则二：请求与响应格式规范

### 2.1 请求格式

- **Content-Type**: `application/json`
- **字段命名**: 使用 `snake_case`（与Python保持一致）

```json
{
  "user_input": "用户输入内容",
  "context": {}
}
```

### 2.2 响应格式

- **Content-Type**: `application/json`
- **字段命名**: 使用 `snake_case`
- **成功响应**: 直接返回数据对象

```json
{
  "final_result": "最终结果",
  "steps": [],
  "executed_locally": true,
  "complexity_score": 0.35
}
```

### 2.3 错误响应格式

所有错误必须返回统一格式：

```json
{
  "detail": "错误描述信息"
}
```

HTTP状态码约定：

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| 200 | 成功 | GET/POST成功 |
| 400 | 请求错误 | 参数校验失败 |
| 404 | 未找到 | 资源不存在 |
| 422 | 校验失败 | Pydantic校验错误 |
| 500 | 服务器错误 | 内部异常 |

### 2.4 禁止事项

- 禁止在响应中使用 `camelCase` 字段名
- 禁止返回没有 `detail` 字段的错误响应
- 禁止使用非标准HTTP状态码

---

## 规则三：核心数据模型约束

### 3.1 WorkflowInput（前端发送 → 后端接收）

```typescript
// 前端TypeScript定义
interface WorkflowInput {
  user_input: string;
  context?: Record<string, unknown>;
}
```

```python
# 后端Python定义
class WorkflowInput(BaseModel):
    user_input: str = Field(..., description="用户输入内容")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
```

**约束**：
- `user_input` 为必填字段，不能为空字符串
- `context` 为可选字段，默认为空对象

### 3.2 WorkflowOutput（后端返回 → 前端接收）

```typescript
// 前端TypeScript定义
interface WorkflowOutput {
  final_result: string;
  steps: WorkflowStep[];
  executed_locally: boolean;
  total_duration_seconds: number;
  start_time: string;
  end_time: string;
  complexity_score?: number;
}
```

```python
# 后端Python定义
class WorkflowOutput(BaseModel):
    final_result: str
    steps: List[WorkflowStep] = Field(default_factory=list)
    executed_locally: bool = True
    total_duration_seconds: float = 0.0
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: datetime = Field(default_factory=datetime.now)
    complexity_score: Optional[float] = None
```

**约束**：
- `steps` 数组长度必须等于6（对应6个Agent）
- `complexity_score` 范围为 0.0 ~ 1.0
- `executed_locally` 由Judge Agent的metadata决定

### 3.3 WorkflowStep

```typescript
// 前端TypeScript定义
interface WorkflowStep {
  agent_id: string;
  agent_name: string;
  input: string;
  output: string;
  success: boolean;
  duration_seconds: number;
  timestamp: string;
  metadata?: Record<string, unknown>;
}
```

**约束**：
- `agent_id` 只能是：`knowledge` | `summary` | `writer` | `review` | `judge` | `result`
- `timestamp` 必须是ISO 8601格式字符串
- `duration_seconds` 单位为秒，保留2位小数

### 3.4 Judge步骤metadata约束

Judge Agent的metadata必须包含以下字段：

```json
{
  "executed_locally": true,
  "complexity_score": 0.72
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `executed_locally` | boolean | 是 | true=本地执行, false=云端执行 |
| `complexity_score` | number | 是 | 复杂度评分(0-1) |

**复杂度阈值**: 0.65
- `complexity_score >= 0.65` → 云端执行（`executed_locally: false`）
- `complexity_score < 0.65` → 本地执行（`executed_locally: true`）

---

## 规则四：Agent ID约束

### 4.1 固定ID列表

```typescript
const AGENT_IDS = ['knowledge', 'summary', 'writer', 'review', 'judge', 'result'] as const;
type AgentId = typeof AGENT_IDS[number];
```

### 4.2 Agent名称映射

| Agent ID | 显示名称 | 职责 |
|----------|----------|------|
| `knowledge` | Knowledge Agent | 知识检索 |
| `summary` | Summary Agent | 需求摘要 |
| `writer` | Writer Agent | 内容生成 |
| `review` | Review Agent | 质量评审 |
| `judge` | Judge Agent | 复杂度判断 |
| `result` | Result Agent | 成果导出 |

### 4.3 执行顺序

```
knowledge → summary → writer → review → judge → result
```

### 4.4 禁止事项

- 禁止自定义Agent ID（必须使用上述6个ID）
- 禁止改变Agent执行顺序
- 禁止跳过任何Agent步骤

---

## 规则五：WebSocket通信规范

### 5.1 连接地址

```
ws://localhost:8000/ws
```

### 5.2 消息格式

所有WebSocket消息必须包含 `type` 和 `data` 字段：

```json
{
  "type": "消息类型",
  "data": {}
}
```

### 5.3 消息类型定义

| type | 方向 | 说明 | data结构 |
|------|------|------|----------|
| `agent_status` | 后端→前端 | Agent状态更新 | `Dict[agent_id, AgentStatus]` |
| `workflow_step` | 后端→前端 | 工作流步骤更新 | `WorkflowStep` |
| `final_result` | 后端→前端 | 最终结果 | `WorkflowOutput` |

### 5.4 禁止事项

- 禁止发送没有 `type` 字段的消息
- 禁止使用未定义的消息类型
- 禁止在前端直接轮询获取实时数据（应使用WebSocket）

---

## 规则六：环境与地址约束

### 6.1 开发环境地址

| 服务 | 地址 |
|------|------|
| 前端 | `http://localhost:3000` |
| 后端API | `http://localhost:8000` |
| 后端WebSocket | `ws://localhost:8000` |
| Ollama | `http://localhost:11434` |

### 6.2 CORS配置

后端必须允许前端域名跨域：

```python
allow_origins = ["http://localhost:3000", "http://localhost:8000"]
```

### 6.3 环境变量

前端环境变量（`NEXT_PUBLIC_` 前缀）：

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

后端环境变量：

```env
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

---

## 规则七：新增API的变更流程

### 7.1 后端新增API时

1. 在 `api/v1/{module}/router.py` 中定义路由
2. 在 `models/` 中定义请求/响应Pydantic模型
3. 在 `api/v1/router.py` 中注册路由
4. **必须同步更新** `frontend/FE_DEVELOPMENT_SPEC.md` 中的API端点清单
5. **必须同步更新** `API_CONVENTION_RULES.md` 中的数据模型定义

### 7.2 前端新增API调用时

1. 在 `services/api/` 中封装API调用
2. 在 `types/index.ts` 中定义TypeScript类型
3. **类型定义必须与后端Pydantic模型完全对应**
4. 字段名必须使用 `snake_case`（与后端一致）

### 7.3 修改现有API时

1. **禁止删除**现有字段（只能新增或标记废弃）
2. 新增字段必须设置默认值（保证向后兼容）
3. 修改字段类型必须同时更新前后端模型定义

---

## 规则八：字段命名一致性

### 8.1 命名规则

| 层 | 命名风格 | 示例 |
|----|----------|------|
| 后端Python | `snake_case` | `user_input`, `complexity_score` |
| 前端TypeScript | `snake_case` | `user_input`, `complexity_score` |
| API JSON | `snake_case` | `user_input`, `complexity_score` |

### 8.2 统一约定

**前后端JSON字段名必须完全一致**，统一使用 `snake_case`。

禁止在前端将后端的 `snake_case` 转换为 `camelCase`。

```typescript
// 正确
interface WorkflowOutput {
  final_result: string;
  total_duration_seconds: number;
}

// 错误 - 禁止转换为camelCase
interface WorkflowOutput {
  finalResult: string;
  totalDurationSeconds: number;
}
```

---

## 规则九：缓存策略约束

### 9.1 后端缓存

| 缓存 | 最大容量 | TTL | 说明 |
|------|----------|-----|------|
| workflow_cache | 100 | 300秒 | 工作流结果缓存 |
| chat_cache | 200 | 300秒 | 聊天结果缓存 |
| search_cache | 500 | 300秒 | 知识库搜索缓存 |

### 9.2 缓存规则

- 仅缓存 `executed_locally=true` 的结果
- 仅缓存 `final_result` 长度 < 5000 字符的结果
- 前端可通过 `/cache/clear` 接口清除缓存

---

## 规则十：安全约束

### 10.1 API密钥管理

- Gemini API密钥仅存储在后端 `.env` 文件中
- **禁止**将API密钥暴露给前端
- **禁止**将API密钥提交到版本控制

### 10.2 输入校验

- 后端必须使用Pydantic模型校验所有输入
- 前端必须进行基础校验（非空、长度限制等）
- `user_input` 不能为空字符串

### 10.3 CORS限制

- 生产环境必须限制 `allow_origins` 为实际前端域名
- 禁止使用 `allow_origins=["*"]` 部署生产环境

---

## 附录：完整API速查表

| 方法 | 路径 | 请求体 | 响应体 |
|------|------|--------|--------|
| GET | `/health` | - | `{status, agents, version}` |
| POST | `/api/v1/workflow/execute` | `WorkflowInput` | `WorkflowOutput` |
| POST | `/api/v1/workflow/execute/parallel` | `WorkflowInput` | `WorkflowOutput` |
| GET | `/api/v1/workflow/cache/stats` | - | `{cache_size, max_size, ttl}` |
| POST | `/api/v1/workflow/cache/clear` | - | `{status, message}` |
| GET | `/api/v1/agents` | - | `{agents, count}` |
| GET | `/api/v1/agents/{agent_id}` | - | `AgentStatus` |
| POST | `/api/v1/agents/{agent_id}/execute` | `AgentInput` | `AgentOutput` |
| GET | `/api/v1/agents/{agent_id}/status` | - | `AgentStatus` |
| POST | `/api/v1/chat/send` | `ChatRequest` | `{response, executed_locally, ...}` |
| POST | `/api/v1/chat/send/batch` | `List[ChatRequest]` | `{results}` |
| GET | `/api/v1/chat/health` | - | `{status, service, cache_size}` |
| GET | `/api/v1/metrics` | - | `{system, resources, workflow, agents}` |
| GET | `/api/v1/metrics/system` | - | `{cpu_usage, memory_usage, ...}` |
| POST | `/api/v1/metrics/increment/{metric_type}` | `value` | `{status, metric, value}` |
| GET | `/api/v1/knowledge` | - | `{knowledge_base, keywords, stats}` |
| POST | `/api/v1/knowledge` | `KnowledgeItem` | `{status, keyword}` |
| GET | `/api/v1/knowledge/keyword/{keyword}` | - | `{keyword, content}` |
| PUT | `/api/v1/knowledge/keyword/{keyword}` | `{content}` | `{status, keyword}` |
| DELETE | `/api/v1/knowledge/keyword/{keyword}` | - | `{status, keyword}` |
| GET | `/api/v1/knowledge/search` | `query, limit` | `{query, results, count}` |
| POST | `/api/v1/knowledge/enhance` | `content, keywords` | `{original, enhanced}` |
| POST | `/api/v1/export/markdown` | `ExportRequest` | `{status, format, filename, filepath}` |
| POST | `/api/v1/export/docx` | `ExportRequest` | `{status, format, filename, filepath}` |
| POST | `/api/v1/export/pptx` | `ExportRequest` | `{status, format, filename, filepath}` |
| GET | `/api/v1/export/download/{filename}` | - | FileResponse |
| GET | `/api/v1/export/list` | - | `{exports, count}` |

---

**文档版本**: v1.0
**创建日期**: 2026-05-13
**适用项目**: AgentMatrix 全栈