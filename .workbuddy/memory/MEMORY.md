# AgentMatrix 项目长期记忆

> 精炼约定，跨会话有效。流水账写在同目录 `YYYY-MM-DD.md`。

## 一、云端模型（2026-09-22 佳文定版；2026-10-04 再次确认「写死」，不可擅自更改）
- ★ **所有云端调用统一走 `DeepSeek-V4.1-Flash`**：云端增强、云兜底、云端视觉，全部是它。
- ⚠️ **名称与 API id 必须分清**（最容易搞错的一点）：
  - **网关显示名** = `DeepSeek-V4.1-Flash`（佳文口头/文档里说的就是它）
  - **实际 API model id** = **`deepseek-flash`** —— `.env` / `app_config.json` 里要填的是**这个**
  - 写成 `deepseek-v4.1-flash` 当 model id 用**是错的**，网关会拒。
- **`deepseek-v4-pro` 已弃用**，不得出现在任何新增代码里（历史值与弃用说明除外）。
  `README.md` 已于 2026-10-04 由 `deepseek-v4-pro` 改为 `deepseek-flash`。
- **视觉模型 = 同一个 `DeepSeek-V4.1-Flash`**（自带视觉）。与文本模型同源，但语义上分开配置。
- ★ **视觉本地优先，不每次上云**（佳文 2026-09-22 明确）：常规识图（用户传图/PPT/Word 截图）
  一律走本地 `qwen2.5vl:7b`，**不调云端 API**——成本 0、无网络延迟、数据不出本机。
  云端视觉只服务两个显式场景：① 自学习三层筛网第 2 层的名词/片段拆解比对（离线批处理，
  不在问答实时路径）② 本地识别明确失败且值得付成本时的显式升级。
  **`vision_plugin.py` 内不得有隐式云端调用**，云端入口必须由调用方显式触发。
- 配置字段：文本 `settings.deepseek_model`、视觉 `settings.deepseek_vision_model`。
- **禁止硬编码模型名**，一律读 settings。
- ⚠️ **双真相源**：`generate_cloud()` 运行时优先读 `config/app_config.json` 的云端条目
  （provider≠ollama），匹配不到才回退 `settings.deepseek_model`。
  所以改云端模型必须**两处同步**：`backend/.env` 的 `DEEPSEEK_MODEL` +
  `backend/config/app_config.json` 的 `models[]`（开发环境；打包环境为
  `%APPDATA%/AgentMatrix/config/app_config.json`）。
- 完整清单见 `docs/云端模型与增强调用清单.md`。

## 二、硬约束
- 8GB VRAM 单卡，**同时只允许一个 Ollama 实例**，GPU 任务串行，不并发加载模型。
- 本地统一模型 `qwen2.5vl:7b`（文本+视觉同模型），上下文 4K（8K 会 CPU offload）。
- 后端 Python 环境：`backend/.venv313`（Python 3.13），启动
  `python -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8000`。
- 脚本约定：`setup.ps1` / `start_all.ps1` / `stop_all.ps1`（旧脚本已归档 `scripts/archived_startups/`）。
- 测试配置在 `backend/pyproject.toml` 的 `[tool.pytest.ini_options]`（**没有 pytest.ini**）。

## 三、关键路径
- `agents/base/contract.py` —— Agent 职责边界契约（6 字段 + 运行时守卫 + 越界账本）
- `agents/base/agent_registry.py` —— `execute_agent` 按契约给请求态 Agent 加锁
- `scripts/audit_agent_contracts.py` —— AST 静态审计（改 Agent 后必跑）
- `core/llm/client.py` —— 云端调用主入口 `generate_cloud`
- `core/llm/vision_plugin.py` —— 视觉识别（本地）

## 四、协作约定（佳文明确要求）
- 称呼：我叫**小W**，用户是**佳文**。
- **不好的话、直观判断直接说，不美化**；关系是朋友，不客套、不附和。
- 谈作品质量给**证据**，不给安慰。
- 环境坑：**Bash 工具在本机不可用**（缺 dirname），一律用 PowerShell；
  PowerShell 验证 API 鉴权必须用 `curl.exe -s -L -H`，`Invoke-WebRequest` 会假 401。
  PowerShell 的 stdout 常捕获不到，需要落盘到探针文件再 Read。
- 环境坑：**前端生产构建必须带 `CODEBUDDY_SAFE_DELETE_ENABLED=0`**。
  `next build` 收尾删临时目录 `.next/export` 会触发沙箱批量删除护栏（50 文件阈值）而中断，
  导致 `out/`（Tauri `frontendDist`）压根不生成——报错是
  `SAFE_DELETE_BULK_CONFIRM_REQUIRED`，看着像删不动，其实是**后续生成步骤没跑到**。
  该变量仅对本次构建生效。日常开发用 `npm run dev`，不需要 `out/`。
- **★ git 仓库已于 2026-10-04 重建**：原 `.git` 因 9/22 丢 `.pack` 而彻底损坏
  （`refs/` 缺失、`objects/pack/` 只剩 `.idx`，git 报 `not a git repository`），
  **历史对象永久丢失**。损坏目录已留证
  `D:\AgentMatrix_backups\git_attic_20261004\.git.damaged`（含 `SALVAGED-INFO.txt`）。
  已按佳文确认的「本地重建」方案重新 `git init -b main` 并提交 2 次：
  `3c03a47` 首次快照（522 文件 / 160,280 行）、`2060f53` 修正版本控制范围。
  - ✅ **远端已于 2026-10-04 对齐完成**（佳文同意走「方案 C」）：
    `origin = https://github.com/han1326189481/AgentMatrix.git`，
    `main` 已跟踪 `origin/main`，`git rev-list --left-right --count main...origin/main = 0	0`。
    过程：`git bundle create --all` 全量备份 →
    `tag pre-cleanup` + `tag cloud-v4.3-legacy`（指向旧云端 `8661233`，已推送留痕）→
    `git push --force-with-lease`（期望值 = 拉下来的 `refs/remotes/origin/main`）。
    **本地与旧云端 `8661233` 无共同祖先**，所以是 forced update，不是 fast-forward。
    备份 bundle：`D:\AgentMatrix_backups\snapshots\agentmatrix-pre-cleanup-*.bundle`（9.74 MB，4 refs）。
    凭据由 Windows 凭据管理器的 `git:https://github.com`（user `han1326189481`）提供，
    push 无交互。流程细节见 user 级 skill `git-remote-align`。
  - ⚠️ **遗留**：旧云端曾跟踪含真实 API Key 的 `backend/config/app_config.json`，
    force push 只移动分支指针，旧对象仍可经旧 SHA 取到 → **建议轮换该 Key**。
    另外远端 Release `v0.1.0`（57.5MB 安装包）指向旧代码，force push 不动它。
  - `.git` 约 106MB（主要是 48MB 的 `agentmatrix-backend.exe`，走 LFS，库内仅 133B 指针）。
  - 换行符策略固定 `core.autocrlf=false`，避免 checkout 时批量转 CRLF 产生虚假 diff。
  - 已排除跟踪：`backend/prompts/skills/_pending_patches/`（运行时输出）、
    `frontend/tsconfig.tsbuildinfo`（构建缓存）、`.workbuddy/_*`（调试残留）。

## 五、★ 数据安全红线（2026-09-24 知识库被清空事故）
- **事故**：跑 `pytest tests` 时 `tests/test_phase7.py` 用 `LearningEngine(SkillGraph())`
  （空图）调 `apply_patches()`，把内存里仅剩的 2 个节点全量 `save()` 到
  `core/graphs/skill_graph.yaml`，一次性抹掉 **636 节点**知识库
  （靠 `D:\AgentMatrix_backup_20260922` 整目录备份恢复）。同一次还污染了
  `reasoning_graph.yaml`、`storage/pending_learning/`、`storage/profiles/test.json`。
- **根因**：三处默认落盘路径写死到仓库生产文件、构造时不可注入。
- **生产侧护栏**：`learning_engine.py` 的 `MIN_NODE_RETENTION=0.5` 缩水护栏
  （内存图 < 磁盘一半即拒绝写入）+ `yaml_path`/`persist` 可注入 + 原子写 + `.bak` 备份；
  `knowledge_auditor.py::_save_skill_graph` 同款。**改这两个文件必须保留护栏。**
- **测试侧护栏**：`backend/tests/conftest.py` **七个** autouse fixture，封住
  LearningEngine / KnowledgeAuditor / ReasoningGraph / PendingStore / 用户画像 /
  **MemoryStore(2026-10-04 补)** / **旧版 KnowledgeService(2026-10-04 补，靠新增常量
  `knowledge/service.py::DEFAULT_KNOWLEDGE_FILE`)** 的写入通道。
  验证方式：回滚数据文件 → 跑全量 → `git status` 显示零改动。
- **红线**：测试**不得**写 `backend/core/graphs/*.yaml` 与 `backend/storage/**`
  下的生产文件；需要落盘的新测试必须显式传 `tmp_path`。
- 已知 good 版本：`D:\AgentMatrix_backup_20260922`（2026-09-22 全目录快照）。

## 六、自学习链路（2026-09-24 打通）
- **知识类**（KnowledgePatch）→ `core/engines/filter_net.py` **三层筛网**
  （L1 质量门槛 + 云端/联网触发 → L2 云端拆解名词、联网核验权威源 → L3 格式 + 二次复核）
  → 默认**全落待审队列**，人工审批才入图。
- **技能类**（SkillPatch）→ 不套筛网（改的是提示词，无「权威出处」），
  走「自动生成 + 全进 pending + 本地质量约束（空补丁不入队）」。
- **触发点归位**：`core/workflow/service.py::_collect_and_trigger_skill_learning`
  （`collect_feedback` 纯收集 → `should_learn` 稳定谓词 → `trigger_learning` 入队）。
  ⚠️ **别把 trigger 塞回 `collect_feedback`**——会让 service 的 `should_learn` 变死代码。
- **API**：`api/v1/learning/router.py` → `/pending`、`/pending/{id}/approve|reject`、
  `/audit`、`/filter-config`；前端面板 `LearningApprovalPanel.tsx`（顶栏，带待审徽标）。
- **权威源分级**：`core/engines/authority_sources.py`。T1 百度百科/维基/官方/edu/gov/学术；
  T2 大型媒体/非营利；T3 社区(CSDN/知乎/GitHub) **不能单独支撑知识结论**。
- 维基 API 必须 `redirects=1` 且**串行**（并发/密集会被限流），已内建缓存与退避。

## 七、数据备份与回档（2026-10-04 建立）
- **脚本**：`scripts/backup.ps1`（含缩水拦截 + 轮转 + manifest）、
  `scripts/restore.ps1`（恢复前自动预存 `prerevert`，错了能再退回来）、
  `scripts/db_backup.py`（SQLite 一致性备份）、`scripts/graph_health.py`、
  `scripts/install_backup_task.ps1`（注册 Windows 计划任务，需管理员）。
- **快照位置**：`D:\AgentMatrix_backups\snapshots\`（轮转保留 30 份）；
  日志 `D:\AgentMatrix_backups\logs\backup-YYYY-MM.log`；基线 `state.json`。
  ⚠️ **该目录含 `.env` / `.token`，属机密，不要放云盘、不要进任何仓库。**
- **三层防线**（互相独立）：① `start_all.ps1` 启动前自动快照（`-Label startup`）
  ② WorkBuddy automation「AgentMatrix 运行时数据每日备份」每天 12:30
  ③ Windows 计划任务（`install_backup_task.ps1`，默认 21:30）。
- **缩水拦截**：图谱节点 < 上次基线 50%（或图谱读不出）→ **拒绝备份、exit 2**。
  被拦截时**不要习惯性加 `-Force`**——那会把损坏状态固化成新基线。
- ★ **SQLite 必须走 `db_backup.py`**：WAL 模式下直接 `Copy-Item .db` 会丢未 checkpoint
  的数据（实测 16,384 B vs 167,936 B，**差 90%**），且被 `.gitignore` 的 `*.db` 挡着，
  git 也管不到。
- ⚠️ `backend/config/app_config.json` **已加入 `.gitignore`**：开发环境下
  `get_config_file_path()` 返回的就是仓库内这个可写文件，前端设置页会把真实 API Key
  写进其 `api_keys` 字段。模板见 `backend/config/app_config.example.json`。
- **文档**：`docs/数据备份与回档机制.md`。

## 八、全项目审计与处置（2026-10-04，当日闭环）
- **★ 总纲文档**：`docs/项目体检与处置方案_2026-10-04.md` ——
  云端对齐结论 + 11 项废旧代码逐条裁定 + 已修项 + 待办批次。**接手前必读。**
- **git 无 remote**：`.git/config` 无 `[remote]`、`refs/remotes/` 不存在。
  本地 2 提交与**当前云端 `main=8661233`（29 提交，8-18 停在 V4.2-V4.3）无共同祖先**，
  只能 force push 或另起分支。**已确认 no push，等佳文点头。**
  旧笔记里的 `0d4b6770` 是老远端快照，现在线上是 `8661233`。
- ✅ **云端 Release `v0.1.0` 真实存在**，安装包 `AgentMatrix_0.1.0_x64-setup.exe`
  （57.5MB，2026-08-02）已上传 → README 的下载链接**有效**，不要当作失效链接删掉。
- ✅ **测试已全绿**：**459 用例 / 0 失败**（原 7 红；5 个同源于 `ENGINE_POLICIES` 被
  未文档化的 "V3.1" 改动偏离 `V3_DEVELOPMENT_GUIDE.md:660/790`）。
  基线演进：449 → 455（+6 IntentGraph 软节流用例）→ 459（知识库测试 4 → 7 项）。
- ★ **`ENGINE_POLICIES` 规范来源**：`docs/V3_DEVELOPMENT_GUIDE.md` 第 4.1 节 + 4.4 验收标准。
  chat = `["task","skill"]` 只 2 引擎；decomposer/planner 只由 `complexity>0.5` 触发
  （planning/analysis 例外）。**别再加回 chat 常驻 decomposer**，会同时打破 5 个用例 +
  「简单对话 <50ms」的对外承诺。
- ★ **修掉的真 bug（会改变运行时行为）**：`ReviewEngine._calculate_difficulty` 原来取
  `skill_path[-1]`（叶子名）去查按 `tech.ai.agent` 路径建键的 `domain_base_difficulty`，
  导致**整张嵌套难度表在生产中从未被命中**、base 恒为 0。已改为「去 root 的点分路径」，
  `_lookup_domain_difficulty` 未命中返回 `None` 而非 `0.0`。
  ⚠️ 后果：`tech.*` 深层任务难度会上调，**Judge 可能更频繁触发 cloud_enhance**。要控成本
  就调 YAML 的 `domain_base_difficulty`，**不要回退这处修复**。
- ✅ **已建 CI**：`.github/workflows/ci.yml`。门禁 lint 口径刻意收窄为
  `ruff --select E9,F63,F7,F82`（实测 0 违规）；全量规则集实测 7177 违规、其中 6149 条是
  中文注释的 RUF001/002/003 噪声，**不要**改回全量门禁，否则 CI 永远红。
  测试 job 带 `AGENT_CONTRACT_STRICT=1`（实测 449 全绿），另跑契约静态审计。
- ✅ **删除批次已全部执行完毕（2026-10-04，3 批 / 累计删 1,445 行）**，
  每批都「删前 grep 取证 → 删 → 全量 pytest（严格契约模式）→ 查数据污染 → 提交」：
  - `6a96879` 批次 1：`agents/summary/`、`services/`（373 行）
  - `ce90f7f` 批次 2：review 旧分支（`_review_content` / `_calculate_difficulty_v2` /
    `_lookup_domain_difficulty` / `_assess_risk_level` / `_calculate_confidence` /
    `_collect_issues` / `_collect_suggestions`）+ `prompt_builder` 4 个 builder（494 行）
  - `b379609` 批次 3：`knowledge/service.py` + `knowledge_base.json`，改包导出，
    重写 API 测试，移除失效护栏（578 行）
  - ⚠️ **纠错记录**：`agents/review/agent.py::_calculate_difficulty_threshold`
    **不是死代码**（被在役的 `_review_with_llm_v2` 调用），总纲文档初版误判、已修正。
    教训：裁定死代码必须逐条 grep 调用点。
  - ⚠️ **`ReviewEngine` 与 `ReviewAgent` 曾各有一份 `_lookup_domain_difficulty`**，
    测试断言的是被删的那一份 → 删完必须把测试重定向到在役实现（已改）。
- ✅ **IntentGraph 已重连为软节流**（提交 `78d6349`）：`should_intervene` 由硬开关改为
  分级信号（阈值 3→2，新增 `get_consecutive_domain_run` / `domains_related` /
  `intervention_signal`）。`reinforce` 时同域模板 priority +0.05 置顶 + 跳过冷却；
  跨领域切换退回 baseline。**推荐始终发生**，图只决定排序与冷却。
- ⬜ **待重连（P2，尚未执行，按优先级）**：
  1. `agents/knowledge/agent.py::TASK_TEMPLATES` —— 「原 Summary Agent 的 outline 功能」迁移物，
     **定义后零引用** → `summary_result["outline"]` 恒为 `[]`、Writer 永远拼到「- 无」。
     这是**能力丢失**，不是死代码，优先修。
  2. `core/context_compressor.py` + `context_round_recorder.py` + `context_token_counter.py`
     （360 行）—— V4.2 半拉子工程：前端 `ContextBar/ContextPanel/ContextOverflowModal`
     已建好，但后端**没有任何 `/context` 端点**（真实数据源缺失）。
  3. `agents/base/contract.py::guard_io` —— 全仓零调用，导致越界账本只有 LLM 维度。
  4. `learning_engine._deepseek_analyze` —— 仍是 TODO 恒返回 None，自学习「拓新」半关着。
     （实装需带三重成本护栏 + 产出仍进 pending）
  5. `code_munch_plugin` 9 个方法 —— 保留但零测试覆盖，建议把
     `scripts/validate_codemunch.py` 的断言迁进 `tests/`。
- ✅ **同名类陷阱已消除**：`knowledge/service.py`（旧 JSON 实现）已删除，
  `knowledge/__init__.py` 现在导出 `mysql_service` 的 SQLite 实现。
- ✅ 文档滞后已修：`README.md` 的 `DEEPSEEK_MODEL` 已是 `deepseek-flash`。
