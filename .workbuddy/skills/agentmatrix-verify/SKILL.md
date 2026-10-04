---
name: agentmatrix-verify
description: AgentMatrix 项目的验证与体检标准流程 —— 跑测试/契约审计/lint 门禁/数据污染检查/死代码裁定的准确命令与坑。当需要验证 AgentMatrix 的改动、跑回归、检查测试是否污染生产数据、或裁定死代码该删还是该重连时使用。
agent_created: true
---

# AgentMatrix 验证与体检流程

## 何时用
- 改完 AgentMatrix 的代码，要跑回归 / 确认没打破东西
- 要判断某个模块是「死代码」还是「链路断了」
- 要检查测试有没有偷偷写生产数据
- 要给佳文一份「有证据、不猜测」的结论

## 铁律
1. **不要相信文档自述，只相信实跑**。结论必须能给出可复现命令。
2. **不要用 `Invoke-WebRequest` 验 API 鉴权**（假 401），用 `curl.exe -s -L -H`。
3. **Bash 工具不可靠**（缺 `dirname`），优先 PowerShell；PowerShell 的 stdout 常捕获不到，
   **一律 `Out-File -Encoding UTF8` 落盘再 Read**（`*>` 会产出 UTF-16，被判成二进制读不了）。
4. **不要用 `%` 字符出现在 PowerShell 命令里**（会被当成 cmd.exe 变量语法而拦命令）。
   需要 git 格式化输出时用 `--pretty=fuller` 之类，别用 `--format="%H"`。

## 一、跑测试（本机必须带这两个环境变量）

```powershell
cd D:\AgentMatrix\backend
$env:CODEBUDDY_SAFE_DELETE_ENABLED="0"   # 否则 pytest 清理 tmp 目录时被沙箱批量删除护栏打断
$env:AGENT_CONTRACT_STRICT="1"            # 契约越界即失败，与 CI 口径一致
& ".\.venv313\Scripts\python.exe" -m pytest tests -q --tb=line -p no:cacheprovider 2>&1 |
  Out-File D:\AgentMatrix\.workbuddy\_verify.txt -Encoding UTF8
```

- 基线：**449 用例 / 0 失败**（2026-10-04）。
- `exit code` 可能是 1 而测试全过——看**输出文件**而不是退出码（护栏会打断收尾）。
  判定看 `grep -c FAILED` 和最后的 `=== N passed ===`。
- 只要跑测试，**必做**下面第二步。

## 二、数据污染检查（每次跑测试后强制）

```powershell
git -C D:\AgentMatrix status --porcelain -- `
  backend/knowledge/knowledge_base.json `
  backend/storage/memory/default.json
```

输出为空 = 没污染。**非空就是有新护栏漏网**，不要 `git checkout --` 了事——
先定位写入通道（`conftest.py` 现有 7 个 autouse fixture 就是历史漏网的沉淀），
补上 fixture，再回滚文件重跑验证。

**新增护栏的正确做法**：把默认落盘路径抽成模块级常量（如
`knowledge/service.py::DEFAULT_KNOWLEDGE_FILE`）或函数（如 `get_memory_dir`），
再在 conftest 里 `monkeypatch.setattr` 重定向到 `tmp_path`。
不要去 patch 实例属性——`__init__` 里就落盘了，来不及。

## 三、契约静态审计

```powershell
cd D:\AgentMatrix\backend
& ".\.venv313\Scripts\python.exe" scripts\audit_agent_contracts.py
```
改过任何 Agent 后必跑。当前基线 **0 error / 0 warning**。

## 四、lint 门禁（口径刻意收窄，别改回全量）

```powershell
cd D:\AgentMatrix\backend
ruff check --isolated --select E9,F63,F7,F82 agents core api app shared knowledge models scripts
```
基线违规数 = **0**。

**为什么不用全量规则集**：实测 7,177 条违规里 6,149 条是 RUF001/002/003
（中文注释的全角标点「歧义」），对中文项目是纯噪声。全量门禁 = CI 永远红 = 等于没 CI。

## 五、死代码裁定方法（先取证，再决定）

不要只看「有没有被调用」就下结论——**要区分「废弃」和「链路断了」**。四步：

1. **量**：`vulture agents core api app shared knowledge models scripts --min-confidence 60`
   （`--min-confidence 80` 漏太多）。注意 FastAPI 路由会被误报成 unused function。
2. **找引用**：`Grep` 搜类名/方法名，**排除 `backend/libs/`**（那是 vendored 第三方，会淹没结果）。
3. **读职责**：读代码 + 它的 docstring/注释。重点看两个信号：
   - **注释里说「X 功能已迁移到 Y」** → 职责搬走了，是废弃 → 可删
   - **接口字段与真实调用方对得上** → 设计时对过链路 → 是断线 → 该重连
4. **交叉核对规范**：查 `docs/V3_DEVELOPMENT_GUIDE.md`。
   代码偏离规范且规范+测试都同意时 → **改代码**；
   代码有意改进且 docstring 记录了理由、旧断言只依据规范初版 → **改用例**并把漂移写进文档。

**判据口诀**：职责被在役代码覆盖 → 删除；职责仍在但调用断 → 重连；是真实可用的能力面
（有脚本能验证）→ 保留 + 补冒烟测试。

## 六、产出要求
- 结论写进 `docs/`，每条结论必须附**可复现命令或实测数字**。
- 修改代码后同步更新 `D:\AgentMatrix\.workbuddy\memory\MEMORY.md`（长期约定）与当日日志。
- 有行为变更的修复（例如改了 Judge 路由的输入）**必须显式标注「会改变运行时行为」**并说明后果。
