# AgentMatrix 项目长期记忆

> 精炼约定，跨会话有效。流水账写同目录 `YYYY-MM-DD.md`。

## 一、云端模型（2026-09-22 佳文定版；2026-10-04 再确认「写死」）
- ★ 所有云端调用统一走 **`DeepSeek-V4.1-Flash`**（云端增强 / 兜底 / 视觉 / 自学习概念判定）。
- ⚠️ **网关显示名 `DeepSeek-V4.1-Flash` ≠ API model id `deepseek-flash`**。配置里填的是 **`deepseek-flash`**；写成 `deepseek-v4.1-flash` 会被网关 **400 拒**。`deepseek-v4-pro` 已弃用。
  （2026-10-04 清掉了残留的错误兜底值：`core/llm/client.py:28-29`、`vision_plugin.py` 文档串、前端 `CloudModelSettingsModal.tsx:62`、`docs/云端模型与增强调用清单.md` 正文。）
- 视觉与文本同源但字段分开：`settings.deepseek_model` / `settings.deepseek_vision_model`。**禁止硬编码模型名**。
- ★ **视觉本地优先**：常规识图走本地 `qwen2.5vl:7b`，不调云。云端视觉仅服务 ① 筛网第 2 层拆解比对（离线批处理）② 本地明确失败时的显式升级。`vision_plugin.py` 内不得有隐式云端调用。
- ⚠️ **双真相源**：`generate_cloud()` 优先读 `config/app_config.json` 的云端条目（provider≠ollama），匹配不到才回退 `settings.deepseek_model`。改模型必须两处同步：`backend/.env` 的 `DEEPSEEK_MODEL` + `config/app_config.json` 的 `models[]`。
- 清单见 `docs/云端模型与增强调用清单.md`（含 B6 = `_deepseek_analyze` 及其四重护栏）。

## 二、硬约束
- 8GB VRAM 单卡，**同时只允许一个 Ollama 实例**，GPU 任务串行。
- 本地统一模型 `qwen2.5vl:7b`（文本+视觉），上下文 4K。
- 后端环境 `backend/.venv313`（Py3.13），启动 `python -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8000`。
- 脚本 `setup.ps1` / `start_all.ps1` / `stop_all.ps1`；测试配置在 `backend/pyproject.toml`（**无 pytest.ini**）。

## 三、关键路径
- `agents/base/contract.py` — Agent 职责边界契约（6 字段 + `guard_llm_call` + `guard_io` + 越界账本）
- `agents/base/agent.py` — `_call_llm`（LLM 维度守卫）/ `_guard_io`（IO 维度守卫）两个门面
- `agents/base/agent_registry.py` — `execute_agent` 按契约给请求态 Agent 加锁
- `backend/scripts/audit_agent_contracts.py` — AST 静态审计（改 Agent 后必跑）
- `core/llm/client.py` — `generate_cloud` 云端主入口；`core/llm/vision_plugin.py` — 本地视觉
- `core/context_tracker.py` — 上下文追踪/压缩编排层（三件套的唯一调用方）
- `api/v1/context/router.py` — `/api/v1/context/{usage,config,compress,{id}}`

## 四、协作约定与工具坑
- 小W 是我，佳文是用户。**不好的话 / 直观判断直接说，不美化**；关系是朋友，不客套不附和；谈作品质量给证据不给安慰。
- ⚠️ **Edit 工具：同一文件的多个 Edit 必须串行（一次消息一个）**。并行发给同一文件的多条编辑会互相覆盖丢改动（2026-10-04 实测丢了 5+2 处），不同文件之间并行是安全的。
- ⚠️ 编辑可能报 `EBUSY: resource busy or locked` → 是并发写盘的征兆，**改完必须 grep 复核**。
- 环境坑：PowerShell 的 stdout 常捕获不到 → **落盘再 Read**（见 user skill `powershell-probe`）；且本机 `cmd.exe` 被沙箱封禁、`git credential fill` 会挂住或拒答（GCM 不交存储凭据）。
- **Bash 工具实际可用**（2026-10-04 实测 grep/ls/python/重定向均正常），早先「缺 dirname 不可用」的结论过时。
- 前端生产构建必须带 `CODEBUDDY_SAFE_DELETE_ENABLED=0`，否则 `next build` 收尾删 `.next/export` 触发沙箱护栏中断、`out/` 不生成。日常开发用 `npm run dev`。
- 测试/全量回归本机必须带 `CODEBUDDY_SAFE_DELETE_ENABLED=0` + `AGENT_CONTRACT_STRICT=1`。

## 五、★ 数据安全红线（2026-09-24 知识库被清空事故）
- 事故：`tests/test_phase7.py` 用空 `SkillGraph()` 调 `apply_patches()`，全量 save 抹掉 **636 节点**（靠 `D:\AgentMatrix_backup_20260922` 恢复）。
- 生产护栏：`learning_engine.py` 的 `MIN_NODE_RETENTION=0.5` 缩水护栏 + `yaml_path`/`persist` 可注入 + 原子写 + `.bak`；`knowledge_auditor.py::_save_skill_graph` 同款。**改这两个必须保留护栏。**
- 测试护栏：`backend/tests/conftest.py` **8 个** autouse fixture 封写入/外部调用通道（LearningEngine / KnowledgeAuditor / ReasoningGraph / SkillLearner / PendingStore / 画像 / MemoryStore / **`_deepseek_analyze` 云调用**）。
- 红线：测试**不得**写 `backend/core/graphs/*.yaml` 与 `backend/storage/**` 生产文件；要落盘的新测试传 `tmp_path`。
- 验证：跑全量 → `git status` 只看得到预期改动（数据文件必须零改动）。已知 good 版本 `D:\AgentMatrix_backup_20260922`。

## 六、自学习链路
- 知识类 → `core/engines/filter_net.py` 三层筛网 → **全落待审队列**，人工审批入图。**筛网是唯一入口**：自动学习产出不得绕过筛网另开写入旁路。
- 技能类 → 不套筛网，自动生成 + 全进 pending + 空补丁不入队。
- 触发点 `core/workflow/service.py::_collect_and_trigger_skill_learning`。⚠️ 别把 trigger 塞回 `collect_feedback`。
- `_deepseek_analyze`（`learning_engine.py`）只在 `learn()` 路径生效（现仅人工调试接口 `/learning/trigger` 调），**不在自动链路里**；四重护栏见 settings 的 `learning_deepseek_*`。
- API `api/v1/learning/router.py`；前端 `LearningApprovalPanel.tsx`。
- 权威源分级 `core/engines/authority_sources.py`（T3 社区不能单独支撑结论）。维基 API 必须 `redirects=1` 且串行。

## 七、数据备份与回档
- 脚本 `scripts/backup.ps1`（缩水拦截 + 轮转）/ `restore.ps1`（预存 prerevert）/ `db_backup.py` / `graph_health.py`。
- 快照 `D:\AgentMatrix_backups\snapshots\`（保留 30）；⚠️ 含 `.env`/`.token`，机密，勿上云勿入库。
- 缩水拦截：节点 < 基线 50% → 拒绝备份 exit 2。**别习惯性加 -Force**。
- ★ SQLite 必须走 `db_backup.py`（WAL 下 `Copy-Item` 实测丢 90% 数据）。
- ⚠️ `backend/config/app_config.json` 已 `.gitignore`（含真实 API Key，模板 `app_config.example.json`）。

## 八、git 与云端（2026-10-04 对齐完成）
- origin = `https://github.com/han1326189481/AgentMatrix.git`；`main` 跟踪 `origin/main`，已 `0 0` 对齐。
- 旧 `.git` 因 9/22 丢 pack 损坏、历史对象永久丢失，2026-10-04 `git init -b main` 重建后走方案 C：bundle 备份 → tag `pre-cleanup`/`cloud-v4.3-legacy`（旧云端 `8661233`）→ `push --force-with-lease`。**本地与旧云端无共同祖先**。备份 bundle 在 `D:\AgentMatrix_backups\snapshots\`（9.74MB）。流程见 user skill `git-remote-align`。
- `.git` ~106MB（48MB exe 走 LFS）。换行符 `core.autocrlf=false`。
- 已排除跟踪：`backend/prompts/skills/_pending_patches/`、`frontend/tsconfig.tsbuildinfo`、`.workbuddy/_*`。
- ⬜ **未完成两项**（详见 `docs/项目体检与处置方案_2026-10-04.md` §4.5）：
  ① GitHub Release `v0.1.0`（57.5MB 旧安装包）**未删** —— 非交互取不到 GitHub 令牌（GCM 拒交凭据、本机 `gh` 未登录、`cmd.exe` 被封），需佳文手动点删或提供 PAT；
  ② 旧历史里泄露的 DeepSeek Key **未轮换**（force push 只移分支指针，旧 SHA 仍可取到含 Key 对象）→ 只能在 DeepSeek 控制台撤销+新建。

## 九、当前状态与待办（2026-10-04）
- ★ 总纲文档 `docs/项目体检与处置方案_2026-10-04.md`。**接手前必读。**
- 测试基线 **485 用例 / 0 失败**（459 + P1 接线 26）。CI `.github/workflows/ci.yml`（lint 口径 `ruff --select E9,F63,F7,F82`，**别改全量**否则恒红；测试 job 带 `AGENT_CONTRACT_STRICT=1`）。
- `ENGINE_POLICIES` 规范来源 `docs/V3_DEVELOPMENT_GUIDE.md` 4.1/4.4：chat = `["task","skill"]` 只 2 引擎。**别加回 chat 常驻 decomposer**。
- 已修真 bug：`ReviewEngine._calculate_difficulty` 领域路径解析（原取 `skill_path[-1]` 叶子名查路径键 → 整张嵌套难度表从未命中、base 恒 0）。控成本调 YAML 的 `domain_base_difficulty`，**不要回退**。
- 已删 1,445 行死代码（3 批）。⚠️ 教训：裁定死代码必须逐条 grep 调用点（曾误判 `_calculate_difficulty_threshold`）。
- IntentGraph 已重连软节流（`78d6349`）：图只决定排序与冷却，推荐始终发生。
- ✅ **P1 四项接线已完成**（2026-10-04 第二轮）：
  ① `TASK_TEMPLATES` → `outline`（Knowledge 按 task_type 取模板；Writer 两个 prompt 分支都拼「## 参考大纲」）
  ② 上下文三件套 → `core/context_tracker.py` + `/api/v1/context/*` + WS `context_usage` 推送 + 沙盒删除级联清理
  ③ `guard_io` → `BaseAgent._guard_io` 门面 + Knowledge 6 处 / Result 3 处
  ④ `_deepseek_analyze` 实装（四重护栏：开关 / 日额度 20 / 间隔 30s / 单次上限 3）
- ⬜ 待办：P3 code_munch 9 方法冒烟测试；前端下拉仍留 `deepseek-v4-pro`（选中即 400，建议下掉）。
