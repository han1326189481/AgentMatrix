# AgentMatrix 项目长期记忆

> 精炼约定，跨会话有效。流水账写同目录 `YYYY-MM-DD.md`。

## 一、云端模型
- ★ 所有云端调用统一 **`deepseek-flash`**（显示名 DeepSeek-V4.1-Flash）。
  ⚠️ 显示名 ≠ API id：配置填 `deepseek-flash`；`deepseek-v4.1-flash` 会被网关 400 拒，`deepseek-v4-pro` 已弃用。
- 文本/视觉字段分开：`settings.deepseek_model` / `deepseek_vision_model`。**禁止硬编码模型名**。
- ★ **视觉本地优先**：常规识图走本地 `qwen2.5vl:7b`；云端视觉仅用于 ① 筛网第 2 层 ② 本地明确失败时的显式升级。`vision_plugin.py` 不得有隐式云端调用。
- ⚠️ **双真相源**：`generate_cloud()` 优先读 `config/app_config.json` 云端条目（provider≠ollama），匹配不到才回退 settings。改模型须同步 `.env` 的 `DEEPSEEK_MODEL` + `app_config.json` 的 `models[]`。
- 清单 `docs/云端模型与增强调用清单.md`。

## 二、硬约束
- 8GB VRAM 单卡，**同时只允许一个 Ollama 实例**，GPU 任务串行；本地统一 `qwen2.5vl:7b`，上下文 4K。
- 后端环境 `backend/.venv313`（Py3.13），启动 `python -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8000`。
- pytest 配置在 `backend/pyproject.toml`（**仓库根另有 pytest.ini，别信它**）。

## 三、关键路径
- `agents/base/contract.py` — 契约（6 字段 + `guard_llm_call` + `guard_io` + 越界账本）
- `agents/base/agent.py` — `_call_llm`/`_guard_io` 门面；`agent_registry.py` 按契约加锁
- `scripts/audit_agent_contracts.py` — AST 审计（改 Agent 后必跑）
- `core/llm/client.py` — `generate_cloud`；`core/llm/vision_plugin.py` — 本地视觉
- `core/context_tracker.py` — 上下文追踪/压缩编排层（三件套唯一调用方）
- `agents/judge/agent.py:301-384` — **四级判据链**（见下）

## 四、★ Judge 路由（改前必读，两个 0.50 别混）
优先级从高到低：`risk_level=="critical"` > 质量补救兜底 `s<0.50` > 难度区间分档 > 信号词抬档。
- **难度分界 d**：0.35→0.50（拓宽本地覆盖），决定落在哪个区间
- **评审得分 s**：兜底阈值 0.50，命中已审计技能时 →0.40（信任加成）
- ⚠️ **兜底优先级高于难度分档**：`d<0.50` 且 `s<0.50` 走 `cloud_enhance/full_rewrite`，不是本地直出。
  「降 d 更省」是错的 —— 两个变量，降 d 反而减少本地直出。
- 六维真实权重（规则引擎路径）：accuracy .25 / professional .20 / completeness .20 /
  reasoning .15 / structure .10 / actionable .10。⚠️ LLM 路径只 5 项，别混用。
- `ENGINE_POLICIES`：chat = `["task","skill"]` 只 2 引擎（来源 `docs/V3_DEVELOPMENT_GUIDE.md` 4.1/4.4）。**别加回 chat 常驻 decomposer**。

## 五、数据安全红线（2026-09-24 知识库清空事故）
- 事故：`tests/test_phase7.py` 用空 `SkillGraph()` 调 `apply_patches()` 全量 save，抹掉 **636 节点**（靠 `D:\AgentMatrix_backup_20260922` 恢复）。
- 生产护栏：`learning_engine.py` 的 `MIN_NODE_RETENTION=0.5` + 原子写 + `.bak`；`knowledge_auditor.py::_save_skill_graph` 同款。**改这两个必须保留护栏。**
- 测试护栏：`backend/tests/conftest.py` **9 个** autouse fixture 封写入/外部调用。
- ★ **设计约定（10-10 确立）**：图谱类（`capability_graph` / `intent_graph`）**只做 dict ↔ 对象，不碰文件 I/O**；落盘留在 `PersonalBrain` / `shared/platform.py`。这样 conftest 既有 fixture 天然覆盖，不新增「新路径忘记隔离」的漏网口（同 9/24 事故）。
- 红线：测试**不得**写 `backend/core/graphs/*.yaml` 与 `backend/storage/**`；要落盘的新测试传 `tmp_path` 或用可注入 `storage_dir`。
- 验证：跑全量 → 数据文件零改动（`skill_graph.yaml` 应为 938188 B / 636 节点 / 435 边）。

## 六、测试基础设施
- ★ **pytest 必须带 `--basetemp`**（已固化进 `pyproject.toml` addopts，别覆盖）。
  原因：收尾 `rm_rf` 删 `%TEMP%\pytest-of-*`，`\\?\` 长路径让 WorkBuddy 删除护栏
  trash 失败 → `SAFE_DELETE_FAIL_CLOSED` → 管道读端不关 → `join()` 死锁。
  **症状：用例全 PASSED 但进程不退出**（10-09 误诊成「图谱加载慢」，实际加载仅 0.74s）。
  ⚠️ `CODEBUDDY_SAFE_DELETE_ENABLED=0` 单独设**没用** —— 护栏在 `sitecustomize.py:35`
  导入时读一次并缓存成常量。
- 全量回归带 `CODEBUDDY_SAFE_DELETE_ENABLED=0` + `AGENT_CONTRACT_STRICT=1`。基线 **485 用例 / 0 失败**（212s）。
- ⚠️ **别用 `tail` 跑 pytest**（全缓冲、看不到进度、误判卡死）→ `> logfile 2>&1` 落盘再看。
- CI `.github/workflows/ci.yml`（lint 口径 `ruff --select E9,F63,F7,F82`，**别改全量**否则恒红）。
- `conftest.py` 里 `pytest-timeout` **未安装**，`--timeout=` 会报 unrecognized。

## 七、协作约定与工具坑
- 小W 是我，佳文是用户。**不好的话/直观判断直接说，不美化**；朋友关系，不客套不附和；谈作品质量给证据不给安慰。
- ⚠️ **Edit 同一文件必须串行**（并行会静默丢改动）；不同文件并行安全。改完必须 grep 复核计数。
- ⚠️ **反引号内容一律用 Write/Edit 写文件再执行**，绝不走 bash `python -c` 内联（反引号被 shell 吃掉，已踩 4 次）。
- 写完内容必须**回读原文验证**，不能只信脚本 print 的「已修改」。
- PowerShell stdout 常捕获不到 / 输出 UTF-16 → **落盘再 Read**（user skill `powershell-probe`）。本机 `cmd.exe` 被封。
- **Bash 工具 PATH 会间歇性损坏**（grep/sed/head 时有时无）→ 管道类命令优先上 Python 绝对路径。
- PowerShell 里调 `python -c` 会被混合引号解析搞坏 → 写临时 .py 跑。
- `.ps1` 脚本用 PowerShell tool 跑（Bash 里调 powershell 会被安全策略拦）。
- 校验脚本断言**必须带上下文限定**，不能只 match 关键词（首版误报率高比没脚本更危险）。

## 八、自学习链路
- 知识类 → `core/engines/filter_net.py` 三层筛网 → **全落待审队列**，人工审批入图。**筛网是唯一入口**。
- 技能类 → 不套筛网，自动生成 + 全进 pending + 空补丁不入队。触发点 `core/workflow/service.py::_collect_and_trigger_skill_learning`。
- `_deepseek_analyze` 只在 `learn()` 路径生效（**不在自动链路**）；四重护栏见 settings `learning_deepseek_*`。
- API `api/v1/learning/router.py`；前端 `LearningApprovalPanel.tsx`；权威源分级 `core/engines/authority_sources.py`（T3 社区不能单独支撑结论）；维基 API 必须 `redirects=1` 且串行。

## 九、备份与回档
- 脚本 `scripts/backup.ps1`（缩水拦截+轮转）/`restore.ps1`/`db_backup.py`/`graph_health.py`；快照 `D:\AgentMatrix_backups\snapshots\`（保留 30）。
- ⚠️ 快照含 `.env`/`.token`，**机密，勿上云勿入库**。缩水拦截：节点 < 基线 50% → 拒绝备份 exit 2。
- ★ SQLite 必须走 `db_backup.py`（WAL 下 `Copy-Item` 实测丢 90%）。
- ⚠️ `backend/config/app_config.json` 已 `.gitignore`（含真实 Key，模板 `app_config.example.json`）。

## 十、git 与云端
- origin = `https://github.com/han1326189481/AgentMatrix.git`；`main` 跟踪 `origin/main`。
- 旧 `.git` 9/22 丢 pack 永久损坏，10-04 重建走方案 C（bundle 备份 + tag + `--force-with-lease`）。**本地与旧云端无共同祖先**。见 user skill `git-remote-align`。
- ⚠️ **push 挂住 = 全局 `credential.helper` 被 PortableGit 设成 shim `helper-selector`**。
  解法：`git -c credential.helper= -c credential.helper=manager push origin main`（先清空再留 manager，单独 `-c ...=manager` 无效）。
  推完必查 `git rev-list --left-right --count main...origin/main` = `0 0`。
- ⚠️ 沙箱下 `git fetch` / `update-ref` 写 `refs/remotes/` 会**静默失败** → 用 python 直接写 `.git/refs/remotes/origin/main`（SHA+\n）。
- ⚠️ **永远不要 `git push --tags`**：本地 `cloud-v4.3-legacy` 指向含泄露 Key 的旧历史。要推 tag 只推 `pre-cleanup`。
- ✅ 远端已清理（10-04）：Release `v0.1.0` 已删，仅留 tag `pre-cleanup`。
- ✅ 密钥泄露已查实无害（10-04）：泄露的 `sk-e507c…30c0` 是 DeepSeek 官方 Key，实测 `/models` 返回 invalid → **已失效，不必轮换**。当前在用的另一把从未进 git。教训：**判定"需要轮换"前必须先发一条 `/models` 请求验证**。

## 十一、图谱现状（2026-10-10）
| 图谱 | 持久化 | 数据 |
|---|---|---|
| SkillGraph | `core/graphs/skill_graph.yaml` | **636 节点 / 435 边**（唯一有真实数据） |
| ReasoningGraph | `core/graphs/reasoning_graph.yaml` | 5 个 `PRESET_PATTERNS` 预置，自学习 0 |
| CapabilityGraph | `storage/profiles/{uid}.json` 的 `capability` 子键 | 10-10 已修落盘（原 PATCH 无效写入，GET 恒 total=0） |
| IntentGraph | `storage/intents/{uid}.json` | 10-10 已修落盘（原重启即清零，软节流信号恒 0） |
- ⚠️ **372 个 `node_type=skill` 节点的 `metadata.node_kind` 全是 `prompt_template`**（提示词模板），不是「人类技能」。派生为 CapabilityGraph 的「用户已掌握技能」= **造假**。能力数据只能靠真实 `update_from_session` 积累，或改用 215 个 concept / 49 个 domain 节点。
- 前端**零图谱可视化**（`frontend/src` 下无 graph/intent/capability/reasoning 文件）。
- 其它真 bug（已记录未修）：`service.py:410` / `learning/router.py:33` 的 `ReasoningGraph()` 新建即丢 ⇒ `usage_count` 跨进程恒 0。

## 十二、★ 交付物（文档/PPT/报告）撰写铁律
> 背景：开题材料经 Claude 四轮外部审稿、六轮迭代才过关。**硬伤全部由外部发现，
> 没有一条是我自己查出来的。** 每条都对应一次实际翻车。

### 1. 核实纪律（最严重的一次）
- ⚠️ **禁止用「我查过了」代替「我查全了」**。宣称已核实时，作者 / 标题 / arXiv 编号 /
  会议或期刊性质 / 年份 **五项逐项确认，缺一不算核实**。
  翻车实录：AutoGen 第一作者是 **Qingyun Wu**（我写 Chen Q）、Qwen2.5-VL 是 **Shuai Bai**（我写 Bai Y）、
  `2409.12191` 是 **Qwen2-VL** 而标题写 Qwen2（真 Qwen2 报告是 `2407.10671`）。
- ★ 文献类型：`TMLR/JMLR/TOIS` = 期刊 → `[J]`；`NeurIPS/ICLR/ACL/AAAI` = 会议 → `[C]`；arXiv 纯预印本 → `[EB/OL]`。判不准就查官方页。
- ★ **引用他人结论不得强于原文**。写「以模型自评为判据不可靠」前必须读摘要结论 ——
  arXiv:2306.05685 原文明确说 GPT-4 与人类一致率 **>80%**。我写强了，被打回。

### 2. 跨文档一致性（PPT / 报告 / 任务书 三份必须同步）
- ⚠️ 任何编号、术语、指标、口径改动**必须同时落到全部载体**，改完跑脚本比对，**不能靠眼看**。
  翻车实录：PPT 与报告的 9 项文献编号**完全不同**，外部审稿第一轮就抓出来。
- ★ 改编号/换引用顺序用**占位符两段式替换**（先写 `[@A@]` 再二次替换），直接 swap 会被连锁污染；
  且**对调编号必漏改正文里的其他引用点**（实测漏改 1 处，下一轮才自查发现）。
- ★ 校验断言**必须带上下文限定**，不能只 match 关键词（查「系统性偏差」误伤了项目内实测的文案 → 误报）。
- 脚本 `D:\gotothegraduate\ppt_workspace\check_materials.py`（19 项校验）；清单 `提交前自检清单.md`。

### 3. 逻辑优先于细节（★ 最贵的教训）
- ⚠️ **发现底层逻辑矛盾时，绝不能在错的基础上加细节**。
  翻车实录：阈值表第一行写反了（`if/elif` 优先级搞错），我的反应却是**在错逻辑上又补三条脚注** ——
  把错的东西写得更详细、更像对的。
- ★ 改条件分支前先画**完整执行链**：有哪些分支、谁优先级最高、变量作用对象是哪个。
- ★ 同一个数字可能**有多个含义**（judge 里两个 0.50：难度 d / 评审得分 s，混用必错）。
- ★ **识别出问题后必须回头改执行表，不能只在正文加注** —— 10-10 扫出 372 节点语义错配，
  却在方案执行表里仍写「从 372 skill 生成」，方案自身矛盾。

### 4. 立场污染自查
- ⚠️ **先为已有写法找理由、再去核实 = 已经被污染了**。正确顺序：先核实，再决定留不留。
- ⚠️ 绝对表述默认删（跑不动 / 必然 OOM / 成本不可控 / 完全不可用 / 零幻觉 / 均已实测），
  除非有实测数据 + 限定范围。替换为程度副词。
- ★ **区分「工程验证」与「有效性验证」**，不可互相替代：测试通过数、打包成功都是工程证据，
  **不能证明编排机制有效**。这条要显式写出来，不是藏起来。
- ★ **README / 文档与代码不符也是硬伤**。10-10 查出 README 的 Judge 路由表漏了 critical
  与质量补救兜底两层，还暗示 `d<0.50` 一定本地直出 —— 与 `judge/agent.py` 实际分支矛盾。

### 5. 实验设计的三类自评陷阱
- ⚠️ **不能用被消融的模块给自己打分**（关掉 Review 后就没有六维分数了）。
  Review 消融 → 单独抽 30 题人工盲评；路由/信号词消融 → 用路由准确率、云端调用率衡量。
- ⚠️ **消融组若退回「系统评分 + 人工抽检」= 又绕回自评**。回退链只能是：
  细化细则 → 复评 → 引入第三评分者仲裁。
- ⚠️ **对照必须剥离变量**：A（裸模型）/ A+（同A + 同样检索，不经编排）/ B1（全本地编排）/
  B2（本地+云端路由）/ C（云端直接提问，帕累托质量上界端点）。**B1−A+ 才是编排净贡献**。
- ⚠️ **评分工作量要算过再写**（120 题 × 5 组 × 3 次 = 1800 份，两人评不完）。
  抽样口径：每题每组只评 1 次；20%–30% 双评做 Krippendorff α。
- ⚠️ 阈值标定防泄漏：开发集与评测集不重叠，另做 ±0.05 敏感性分析。
- ★ **必须有「结论不显著怎么办」的预案**。写进去加分，不写是硬伤。

### 6. 版式与渲染复核（本机唯一可靠路径）
- ★ Office 复核走 COM：`Word/PowerPoint.Application` → `SaveAs([ref]$path,[ref]17)` 出 PDF /
  `Slides.Item(i).Export()` 出 PNG。本机无 LibreOffice。
- ⚠️ **每改完版面必渲染看图**，不能只看坐标算术。溢出压页脚是高频问题。
- ⚠️ 页码别信脚本注释里的 `# ==== N ====`，以 footer 的 `N / TOTAL` 为准。
- ⚠️ `header()` 类公共 helper 改动影响全局所有页 —— 改完必须全量抽检（本轮修掉一个波及 23 页的版式 bug）。
- python-docx：`insert_paragraph_before` 是**逆序插入** → 顺序错乱 + 标题重复。
  批量改单元格必须「删光全部段落再 `cell.add_paragraph()` 按序重建」。
  `add_table` 行数 = 表头 1 + 数据行数，写少直接 `IndexError`。

### 7. 外部审稿的正确用法
- ★ 把每条意见当**待验证假设**，逐条落地核实，成立就改，不成立就**带证据反驳**。既不盲从也不盲拒。
- ★ **反驳必须带证据**：代码行号、arXiv 摘要原文、官方页字段。只说「我觉得不对」不算。
- ★ 审稿人也会误读，但**先核自己的实物再反驳**。
- ★ 别把外部审稿当终点。连续多轮靠外部发现问题 = 缺**自检机制**，应固化成脚本 + 清单。

### 8. 备份命名
- 版本备份用**可识别名**：`_旧版N_第N轮前_XXXX字.docx`，不用 `bak`/`bak2`。

## 十三、答辩材料归档（2026-10-10 已提交）
- 目录 `D:\gotothegraduate\`，三份正本 + 8 份具名旧版 + `check_materials.py`。
- **PPT 已提交答辩（10-14），佳文明确不再改动材料** —— 后续只改代码与 README。
  若日后要改材料，先跑 `check_materials.py` 跨文档比对。
