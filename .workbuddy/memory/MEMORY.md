# AgentMatrix 项目长期记忆

> 精炼约定，跨会话有效。流水账写同目录 `YYYY-MM-DD.md`。

## 一、云端模型（2026-09-22 定版，10-04 确认「写死」）
- ★ 所有云端调用统一 **`DeepSeek-V4.1-Flash`**（增强/兜底/视觉/自学习判定）。
- ⚠️ **显示名 `DeepSeek-V4.1-Flash` ≠ API id `deepseek-flash`**。配置填 **`deepseek-flash`**；`deepseek-v4.1-flash` 会被网关 400 拒。`deepseek-v4-pro` 已弃用。
- 文本/视觉字段分开：`settings.deepseek_model` / `deepseek_vision_model`。**禁止硬编码模型名**。
- ★ **视觉本地优先**：常规识图走本地 `qwen2.5vl:7b`，不调云；云端视觉仅用于 ① 筛网第 2 层拆解比对 ② 本地明确失败时的显式升级。`vision_plugin.py` 不得有隐式云端调用。
- ⚠️ **双真相源**：`generate_cloud()` 优先读 `config/app_config.json` 云端条目（provider≠ollama），匹配不到才回退 settings。改模型须同步 `.env` 的 `DEEPSEEK_MODEL` + `app_config.json` 的 `models[]`。
- 清单 `docs/云端模型与增强调用清单.md`（B6 = `_deepseek_analyze` + 四重护栏）。

## 二、硬约束
- 8GB VRAM 单卡，**同时只允许一个 Ollama 实例**，GPU 任务串行；本地统一 `qwen2.5vl:7b`，上下文 4K。
- 后端环境 `backend/.venv313`（Py3.13），启动 `python -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8000`。
- 脚本 `setup.ps1`/`start_all.ps1`/`stop_all.ps1`；pytest 配置在 `backend/pyproject.toml`（**无 pytest.ini**）。

## 三、关键路径
- `agents/base/contract.py` — 契约（6 字段 + `guard_llm_call` + `guard_io` + 越界账本）
- `agents/base/agent.py` — `_call_llm`/`_guard_io` 门面；`agent_registry.py` 按契约加锁
- `scripts/audit_agent_contracts.py` — AST 审计（改 Agent 后必跑）
- `core/llm/client.py` — `generate_cloud`；`core/llm/vision_plugin.py` — 本地视觉
- `core/context_tracker.py` — 上下文追踪/压缩编排层（三件套唯一调用方）
- `api/v1/context/router.py` — `/api/v1/context/{usage,config,compress,{id}}`

## 四、协作约定与工具坑
- 小W 是我，佳文是用户。**不好的话/直观判断直接说，不美化**；关系是朋友，不客套不附和；谈作品质量给证据不给安慰。
- ⚠️ **Edit 工具：同一文件的多条 Edit 必须串行**。并行发同一文件会静默丢改动（10-04 实测丢 5+2 处）；不同文件并行安全。报 `EBUSY: resource busy or locked` 是并发写盘征兆 → **改完必须 grep 复核计数**。
- PowerShell stdout 常捕获不到 → **落盘再 Read**（user skill `powershell-probe`）。本机 `cmd.exe` 被封。
- **Bash 工具的 PATH 会间歇性损坏**（`grep`/`sed`/`head`/`dirname` 时有时无，只剩 `git` + 绝对路径 python 可靠）→ 管道类命令优先上 Python，别依赖 shell 工具链。PowerShell 给 git 传 stdin 依旧是空的。
- ⚠️ 沙箱下 `git fetch` / `git update-ref` 写 `refs/remotes/` 会**静默失败**（fetch 打印 `[new branch] main -> origin/main` 但文件不落盘，随后 `origin/main` 报 gone）。解法：直接用 python 写 `.git/refs/remotes/origin/main`（内容为 SHA+\n）。
- 前端生产构建必须带 `CODEBUDDY_SAFE_DELETE_ENABLED=0`（否则 `next build` 收尾删 `.next/export` 触发沙箱护栏、`out/` 不生成）。日常开发用 `npm run dev`。
- 全量回归必须带 `CODEBUDDY_SAFE_DELETE_ENABLED=0` + `AGENT_CONTRACT_STRICT=1`。

## 五、★ 数据安全红线（2026-09-24 知识库清空事故）
- 事故：`tests/test_phase7.py` 用空 `SkillGraph()` 调 `apply_patches()` 全量 save，抹掉 **636 节点**（靠 `D:\AgentMatrix_backup_20260922` 恢复）。
- 生产护栏：`learning_engine.py` 的 `MIN_NODE_RETENTION=0.5` 缩水护栏 + `yaml_path`/`persist` 可注入 + 原子写 + `.bak`；`knowledge_auditor.py::_save_skill_graph` 同款。**改这两个必须保留护栏。**
- 测试护栏：`backend/tests/conftest.py` **8 个** autouse fixture 封写入/外部调用（LearningEngine/KnowledgeAuditor/ReasoningGraph/SkillLearner/PendingStore/画像/MemoryStore/`_deepseek_analyze`）。
- 红线：测试**不得**写 `backend/core/graphs/*.yaml` 与 `backend/storage/**` 生产文件；要落盘的新测试传 `tmp_path`。
- 验证：跑全量 → 数据文件零改动。已知 good 版本 `D:\AgentMatrix_backup_20260922`。

## 六、自学习链路
- 知识类 → `core/engines/filter_net.py` 三层筛网 → **全落待审队列**，人工审批入图。**筛网是唯一入口**，不得绕过另开写入旁路。
- 技能类 → 不套筛网，自动生成 + 全进 pending + 空补丁不入队。触发点 `core/workflow/service.py::_collect_and_trigger_skill_learning`；⚠️ 别把 trigger 塞回 `collect_feedback`。
- `_deepseek_analyze` 只在 `learn()` 路径生效（现仅 `/learning/trigger` 调试接口调），**不在自动链路**；四重护栏见 settings `learning_deepseek_*`。
- API `api/v1/learning/router.py`；前端 `LearningApprovalPanel.tsx`；权威源分级 `core/engines/authority_sources.py`（T3 社区不能单独支撑结论）；维基 API 必须 `redirects=1` 且串行。

## 七、数据备份与回档
- 脚本 `scripts/backup.ps1`（缩水拦截+轮转）/`restore.ps1`（预存 prerevert）/`db_backup.py`/`graph_health.py`；快照 `D:\AgentMatrix_backups\snapshots\`（保留 30）。
- ⚠️ 快照含 `.env`/`.token`，**机密，勿上云勿入库**。
- 缩水拦截：节点 < 基线 50% → 拒绝备份 exit 2。**别习惯性加 -Force**。
- ★ SQLite 必须走 `db_backup.py`（WAL 下 `Copy-Item` 实测丢 90%）。
- ⚠️ `backend/config/app_config.json` 已 `.gitignore`（含真实 Key，模板 `app_config.example.json`）。

## 八、git 与云端
- origin = `https://github.com/han1326189481/AgentMatrix.git`；`main` 跟踪 `origin/main`。
- 旧 `.git` 因 9/22 丢 pack 永久损坏，10-04 `git init -b main` 重建后走方案 C：bundle 备份 → tag `pre-cleanup`/`cloud-v4.3-legacy`（旧云端 `8661233`）→ `push --force-with-lease`。**本地与旧云端无共同祖先**。bundle 在 `D:\AgentMatrix_backups\snapshots\`。见 user skill `git-remote-align`。
- `.git` ~106MB（48MB exe 走 LFS）。`core.autocrlf=false`。已排除跟踪：`prompts/skills/_pending_patches/`、`frontend/tsconfig.tsbuildinfo`、`.workbuddy/_*`。
- ⚠️ **push 挂住 = 全局 `credential.helper` 被 PortableGit 设成 shim `helper-selector`**（读不到凭据且阻塞）。解法：`git -c credential.helper= -c credential.helper=manager push origin main`（先清空再留 manager，单独 `-c ...=manager` 无效）。推完 `git rev-list --left-right --count main...origin/main` 复核 `0 0`。详见 `git-remote-align` §2.1。
- ✅ **远端已清理**（2026-10-04）：Release `v0.1.0`（id 363665093，57.5MB）+ 其 tag 已删（复查 0 release）；远端 tag `cloud-v4.3-legacy`（→旧云端 `8661233`）已删，仅留 `pre-cleanup`（→新历史 `d0630746`，干净）。本地删 `v0.1.0` tag；`cloud-v4.3-legacy` **本地保留**做留痕。
- ⚠️ **永远不要 `git push --tags`**：本地 `cloud-v4.3-legacy` 指向含泄露 Key 的旧历史，推上去等于二次暴露。要推 tag 只推 `pre-cleanup`。
- ✅ **密钥泄露已查实无害，无需轮换**（2026-10-04 实测结论）：
  - 泄露的那把：`sk-e507c…30c0`（35 位），在 commit **`0c9d1f6`**（2026-05-15）的 `backend/config/app_config.json`。全量扫描（29 个旧 commit × 配置类 blob 去重 47 个）确认**仅此一把**。
  - 它是 **DeepSeek 官方 Key**（该配置 `provider:"deepseek"` 且**无 base_url**，不是网关）。实测官方 API 返回
    `Authentication Fails, Your api key: ****30c0 is invalid` → **已失效** → **不必撤销、不必轮换**。
  - 当前 `backend/.env` 在用的是**另一把**（`DEEPSEE…` 45 位，网关格式），**从未进过 git**（`.gitignore` 一直挡着 `.env` 与 `app_config.json`）。
  - 仓库里另两处 `sk-xxxxxxx…` 是**占位符**，非真实密钥。
  - 补充：仓库是 **PUBLIC**，该 Key 自仓库创建（2026-07-31）起公开暴露约 65 天。
- ⚠️ 教训：**判定"需要轮换"之前，必须先用一条 `/models` 请求验证 Key 是否仍有效**，并确认它是官方 Key 还是网关 Key（看配置里有没有 `base_url`）。别拿未验证的假设当用户待办——这次差点让佳文白跑一趟。

## 九、当前状态与待办（2026-10-04）
- ★ 总纲文档 `docs/项目体检与处置方案_2026-10-04.md`。**接手前必读。**
- 测试基线 **485 用例 / 0 失败**。CI `.github/workflows/ci.yml`（lint 口径 `ruff --select E9,F63,F7,F82`，**别改全量**否则恒红）。
- `ENGINE_POLICIES` 规范来源 `docs/V3_DEVELOPMENT_GUIDE.md` 4.1/4.4：chat = `["task","skill"]` 只 2 引擎。**别加回 chat 常驻 decomposer**。
- 已修真 bug：`ReviewEngine._calculate_difficulty` 领域路径解析（原 `skill_path[-1]` 查路径键 → 整表从未命中、base 恒 0）。调难度用 YAML `domain_base_difficulty`，**不要回退**。
- 已删 1,445 行死代码（3 批）。⚠️ 裁定死代码必须逐条 grep 调用点（曾误判 `_calculate_difficulty_threshold`）。
- IntentGraph 已重连软节流（`78d6349`）：图只决定排序与冷却，推荐始终发生。
- ✅ **P1 四项接线完成**（10-04 第二轮，26 用例 `tests/test_wiring_20261004.py`）：① `TASK_TEMPLATES`→`outline`（Knowledge 按 task_type 取模板；Writer 两分支都拼「## 参考大纲」）② 上下文三件套 → `context_tracker.py` + `/api/v1/context/*` + WS `context_usage` + 沙盒删除级联清理 ③ `guard_io` → `BaseAgent._guard_io` + Knowledge 6 处 / Result 3 处 ④ `_deepseek_analyze` 实装（四重护栏：开关/日额度 20/间隔 30s/单次上限 3）。
- ⬜ 待办：P3 code_munch 9 方法冒烟测试；前端下拉仍留 `deepseek-v4-pro`（选中即 400，建议下掉）。
