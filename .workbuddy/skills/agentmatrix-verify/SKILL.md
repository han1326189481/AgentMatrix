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
5. ⚠️ **改文件时同一文件的多条 Edit 必须串行发**。并行发出的同文件编辑会互相覆盖、
   改动静默丢失（实测一次丢 5 条）；`EBUSY: resource busy or locked` 就是并发写盘的征兆。
   **改完必须 grep 复核关键标记的数量**，不能只看「Successfully edited」。
   （2026-10-04 P1 接线时正是靠事后 grep 才发现漏了 7 处。）

## 一、跑测试（本机必须带这两个环境变量）

```powershell
cd D:\AgentMatrix\backend
$env:CODEBUDDY_SAFE_DELETE_ENABLED="0"   # 否则 pytest 清理 tmp 目录时被沙箱批量删除护栏打断
$env:AGENT_CONTRACT_STRICT="1"            # 契约越界即失败，与 CI 口径一致
& ".\.venv313\Scripts\python.exe" -m pytest tests -q --tb=line -p no:cacheprovider 2>&1 |
  Out-File D:\AgentMatrix\.workbuddy\_verify.txt -Encoding UTF8
```

- 基线：**485 用例 / 0 失败**（2026-10-04；449 → 455 IntentGraph → 459 知识库 → 485 P1 四项接线）。
  新增文件 `tests/test_wiring_20261004.py`（26 项）：TASK_TEMPLATES/outline、上下文三件套 + `/context` 端点 + WS 推送、`guard_io`、`_deepseek_analyze` 四重护栏。
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
先定位写入通道（`conftest.py` 现有 8 个 autouse fixture 就是历史漏网的沉淀），
补上 fixture，再回滚文件重跑验证。

⚠️ 跑测试还会消耗**云端额度**：`_deepseek_analyze` 实装后，测试里若未封住会真调 DeepSeek。
第 8 个 fixture `_forbid_deepseek_analyze_calls` 就是为此——新增任何「按条目逐个上云」的
代码路径，都要在 conftest 里同步加一条关闭开关 + 额度重置。

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

⚠️ **必须逐条 grep 调用点，不能凭「看起来属于旧路径」推断**。实例：`agents/review/agent.py`
的 `_calculate_difficulty_threshold` 从命名和位置看都像旧分支的配套方法，实则被**在役的**
`_review_with_llm_v2` 调用（一处判断失误就会删掉活代码）。同一批删除里还有反向发现：
`ReviewEngine` 与 `ReviewAgent` 各有一份同名 `_lookup_domain_difficulty`，
**测试断言的是被删的那一份** → 生产实现出错也测不出来，删完必须把测试重定向到在役实现。

## 五之二、删除批次的安全流程（佳文要求：分批 + 备份 + 门禁）

**一批一提交，每批跑完测试再进下一批**，一个失败才能定位到是哪一批引入的。

```powershell
# 0. 动手前：提交当前状态 → 打 pre-cleanup 标签 → git bundle create --all 全量备份
# 1. 取证：Grep 类名/方法名（排除 backend/libs）确认零引用
# 2. 删除后立刻全量回归（严格契约模式），再看数据污染
# 3. 通过才 git commit；不通过先修（可能要改用例或重定向测试）
```

**按行精确删除大段代码**：不要用巨大 `old_string` 硬贴。写个 Python 脚本按
`(start, end)` 行区间删，并加三重断言：① 区间末行之后是预期的方法名
② 区间内确实包含要删的 `def`
③ 删完 `ast.parse()` 语法校验 + 断言保留项仍在、已删项消失。
坑：行区间容易数错一行（`def` 前的空行），**断言会在写盘前拦下来**，不要省。

## 五之三、云端对齐

见 user 级 skill `git-remote-align`（无共同祖先仓库的 force-with-lease 安全流程）。
本项目的关键事实：本地 `.git` 于 2026-09-22 损坏后 2026-10-04 重建，
与旧云端 `8661233` **无共同祖先**；备份 bundle 在
`D:\AgentMatrix_backups\snapshots\agentmatrix-pre-cleanup-*.bundle`。

## 六、产出要求
- 结论写进 `docs/`，每条结论必须附**可复现命令或实测数字**。
- 修改代码后同步更新 `D:\AgentMatrix\.workbuddy\memory\MEMORY.md`（长期约定）与当日日志。
- 有行为变更的修复（例如改了 Judge 路由的输入）**必须显式标注「会改变运行时行为」**并说明后果。
