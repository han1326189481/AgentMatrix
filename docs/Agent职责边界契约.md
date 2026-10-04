# Agent 职责边界契约（V1）

> 代码：`backend/agents/base/contract.py`　审计：`backend/scripts/audit_agent_contracts.py`
> 测试：`backend/tests/test_agents/test_agent_contracts.py`（24 例）

## 一、为什么要有它

AgentMatrix 的 5 个 Agent 是**单例**——`agent_registry.py` 里每个 Agent 只 `new` 一次，
彼此由 `core/workflow/service.py` 串成 `knowledge → writer → review → judge → result`。

这套结构能跑，但有一条隐患：**边界全靠约定，没有任何东西在检查约定**。

本项目中真实存在的两个后果：

| 现象 | 位置 | 性质 |
|---|---|---|
| `WriterAgent` 把 `_current_system_prompt` 写在实例上，再由 `_generate_*` 读取 | 写：`writer/agent.py:801-980`；读：`:1165-1443` | 单例 + 无锁 ⇒ 两个请求并发时，后到者会覆盖前者的 system prompt |
| `JudgeAgent` 被要求「纯规则、不调模型」 | `judge/agent.py` 全文 | 这条约束没有任何代码兜底，加一行 `_call_llm` 不会有任何东西报错 |

契约把「口头约定」变成三件可执行的事：**声明、运行时校验、静态审计**。

## 二、六字段定义

| 字段 | 类型 | 回答的问题 |
|---|---|---|
| 输入类型 | `input_types` | 允许接收什么形态的输入 |
| 输出类型 | `output_types` | 必须产出什么形态的结果 |
| 是否允许调 LLM | `llm_policy` + `llm_scope` | `never` / `optional` / `required`，且限定 `local` / `cloud` / `both` |
| 是否允许外部 IO | `io_resources` | `ollama_gpu` / `cloud_api` / `web` / `local_index` / `database` / `filesystem` |
| 失败语义 | `failure_semantics` | `fatal`（向上抛）或 `degraded`（必须返回降级结果） |
| 是否有 per-request 状态 | `request_state` | `reentrant` 可并发 / `shared_mutable` 必须串行 |

**第六字段是推导出来的，不是手写的**：只要 `declared_writes` 里有一个属性被标为
`PER_REQUEST`，该 Agent 的 `request_state` 就是 `SHARED_MUTABLE`。
这样「并发安全」这一项永远不会和真实代码脱节。

## 三、五个 Agent 的契约（已与源码核对）

| Agent | 输入 | 输出 | LLM | 范围 | 外部 IO | 失败 | 请求态 |
|---|---|---|---|---|---|---|---|
| knowledge | text/context/image/document/code | 知识包 | **never** | — | web, local_index, ollama_gpu, database, filesystem | degraded | reentrant |
| writer | text/context/structured_json | text | **required** | **local** | ollama_gpu, filesystem | degraded | **shared_mutable** |
| review | text/structured_json/context | structured_json | optional | local | ollama_gpu, filesystem | degraded | reentrant |
| judge | structured_json | routing_decision | **never** | — | filesystem | degraded | reentrant |
| result | text/structured_json | text + files | optional | **both** | ollama_gpu, cloud_api, filesystem | degraded | reentrant |

四条被钉死的边界（测试中会拦住任何改动）：

1. `judge` 与 `knowledge` 的 `llm_policy = never` —— 前者纯规则，后者全 IO。
2. `writer` 的 `llm_scope = local` —— 它的 7 处 `_call_llm` **全部** `use_cloud=False`，
   越权上云会被守卫拦下。
3. 全链**只有 `result` 允许上云**（`full_rewrite` / `polish` 两条路径）。
4. 全链**只有 `writer` 有 per-request 状态**。

## 四、三条校验路径

### 1. 声明层（导入期自检）

`validate_contracts()` 在模块导入时执行：词表合法、输入输出非空、
`never` 必须配 `scope=none`、写入无重名、五个 Agent 一个不少。

### 2. 运行时（唯一咽喉）

`BaseAgent._call_llm` 的第一行就是 `guard_llm_call()`。边界校验放在 `try`
**之外**——该方法会把所有异常吞成错误字符串，放进 `try` 内的话严格模式抛出的
`ContractViolation` 会被自己兜住，越界永远传不出去。

`AgentRegistry.execute_agent` 是全部 Agent 调用的唯一入口（`service.py:562/1064`），
它按 `requires_serialization()` 给有请求态的 Agent 加锁：

```
Writer 有 per-request 状态 ⇒ 并发 execute_agent 峰值并发 = 1
Judge  无请求态        ⇒ 并发 execute_agent 峰值并发 > 1
```

锁的粒度是「该 Agent 自己」，不同 Agent 之间不受影响，链上仍可流水并行。
本项目的算力前提是单卡 8GB、Ollama 串行执行，串行化 Writer 不构成本质损失；
它换来的是「跨请求串味」从设计隐患变成**结构上不可能**。

严格模式由 `AGENT_CONTRACT_STRICT=1` 打开（测试与 CI 用），生产默认只记账 + WARNING。

### 3. 静态层（AST 审计）

`python scripts/audit_agent_contracts.py` 用 AST 扫真实代码，比对声明：

| 编号 | 检查 |
|---|---|
| C1 | 声明 `never` 的 Agent 不得存在模型调用点 |
| C2 | 类内写入的实例属性必须全部登记在 `declared_writes` |
| C3 | 声明为 `per_request` 的属性必须真的被写 |
| C3b | `per_request` 属性的写入点应落在 `execute` 可达路径上 |
| C4 | 代码用到的 IO 依赖必须已在 `io_resources` 中声明 |
| C5 | 有请求态的 Agent 会被注册表串行化（提示） |

**C2 用「全类写入」而不是「可达写入」，是踩过坑后的选择**：`WriterAgent` 的
`_generate_*` 是被 `TaskHandler` 对象以 `self.agent._generate_xxx()` 转调的，
纯 `self.` 调用图跟不到那里——只查可达集会产生**假通过**。

同理，可达性必须同时跟 `self.<method>()` **和** `self.<property>`：
本项目的懒加载都写成 `@property`，触发点是不带括号的属性访问，只跟调用会漏掉整条懒加载链。

## 五、怎么用

```bash
cd backend
.venv313\Scripts\python.exe scripts\audit_agent_contracts.py          # 人读报告
.venv313\Scripts\python.exe scripts\audit_agent_contracts.py --json   # 供 CI 消费
.venv313\Scripts\python.exe -m pytest tests\test_agents\test_agent_contracts.py -q
```

审计有 error 时退出码为 1，可直接挂进 CI。

## 六、当前审计结果

```
knowledge  llm=never/none       request_state=reentrant      类内写入 7 个（全为缓存）  调用点 0
writer     llm=required/local   request_state=shared_mutable 类内写入 7 个（3 个请求态）调用点 7
review     llm=optional/local   request_state=reentrant      类内写入 4 个（全为缓存）  调用点 1
judge      llm=never/none       request_state=reentrant      类内写入 0 个              调用点 0
result     llm=optional/both    request_state=reentrant      类内写入 0 个              调用点 2

结论: 0 error / 0 warning / 1 info
```

端到端验证：后端在 Python 3.13 上重启后 `/health`、`/openapi.json`、`/api/v1/agents`
均 200；跑通一次真实工作流（8.5s，本地模型），**无任何越界记录** —— 契约层在正常路径上完全惰性。

## 七、待办

1. **把 Writer 的请求态改为参数传递**（根治）。
   现状：`_current_skill_path` / `_current_skill_stack` / `_current_system_prompt`
   三个属性写在单例上，靠注册表加锁兜住并发。
   目标：改为局部变量并沿 `_generate_*` 入参传递，让 `writer` 也变成 `reentrant`，
   从而去掉这把锁。涉及 7 个生成方法 + 6 个 TaskHandler，属独立重构，
   **放在 40Q 基线采集之后做**（否则基线前后行为不可比）。
2. **把契约暴露给前端**：`AgentRegistry.get_contracts()` 已就绪，
   尚未挂到 `/api/v1/agents` 的响应里。
3. **把审计挂进 CI**：`--json` 输出已具备，只差一个 workflow 文件。
