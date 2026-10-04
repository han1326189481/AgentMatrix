# AgentMatrix 项目长期记忆

> 精炼约定，跨会话有效。流水账写在同目录 `YYYY-MM-DD.md`。

## 一、云端模型（2026-09-22 佳文定版，不可擅自更改）
- **所有云端调用统一走 `deepseek-v4.1-flash`**：云端增强、云兜底、云端视觉，全部是它。
- **`deepseek-v4-pro` 已弃用**，不得出现在任何新增代码里（历史值与弃用说明除外）。
- **视觉模型 = `deepseek-v4.1-flash`**（自带视觉）。与文本模型同源，但语义上分开配置。
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
- **★ git 仓库已死亡（2026-10-04 确认）**：`D:\AgentMatrix\.git` 目录存在但内容残缺——
  `refs/` 目录整个不存在、`objects/pack/` 只剩 `pack-*.idx` 却没有 `pack-*.pack`，
  `git` 直接报 `not a git repository`。这是 9/22「丢 .pack」事故的终局：
  **历史对象已永久丢失，本地无法回档。**
  远端 `https://github.com/han1326189481/AgentMatrix.git`（packed-refs 里
  `refs/remotes/origin/main = 0d4b6770...`）**可能仍保有完整历史**，重建方案待佳文确认。
  重建完成前：**绝不执行任何 git 写操作**（stash/commit/reset 都不行），只读。

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
- **测试侧护栏**：`backend/tests/conftest.py` 五个 autouse fixture，封住
  LearningEngine / KnowledgeAuditor / ReasoningGraph / PendingStore / 用户画像
  的写入通道。
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
