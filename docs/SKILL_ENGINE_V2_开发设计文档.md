# AgentMatrix Skill Engine V2 — 开发设计文档

> **版本**: v1.0-draft
> **日期**: 2026-07-19
> **基线**: 当前 V1 架构（5 Agent 串行 + 模板 Prompt + 规则引擎）
> **目标**: 从"Prompt Engineering"升级到"Skill Engineering"，核心差异：Skill 是结构化数据，Prompt 是最终产物

---

## 目录

1. [架构总览](#一架构总览)
2. [核心数据模型](#二核心数据模型)
3. [Skill Tree 技能树设计](#三skill-tree-技能树设计)
4. [Skill Engine 核心组件](#四skill-engine-核心组件)
5. [Agent 改造方案](#五agent-改造方案)
6. [Skill Learning 自学习机制](#六skill-learning-自学习机制)
7. [Intent Cache 意图缓存融合](#七intent-cache-意图缓存融合)
8. [实施路线图](#八实施路线图)
9. [风险评估与缓解](#九风险评估与缓解)
10. [验收标准](#十验收标准)

---

## 一、架构总览

### 1.1 核心理念

```
V1 架构（当前）：
  Prompt 模板 → LLM 调用 → 输出

V2 架构（目标）：
  Skill Engine → Prompt Builder → LLM 调用 → 输出
       ↑
  结构化数据（SkillBook）
  可查询、可组合、可进化
```

### 1.2 系统架构图

```
                              ┌─────────────────────┐
                              │   Intent Analyzer    │
                              │  ├─ 意图识别          │
                              │  ├─ 领域检测          │
                              │  ├─ 历史意图匹配      │
                              │  └─ 缓存命中判断      │
                              └────────┬────────────┘
                                       │
                              ┌────────▼────────────┐
                              │   Skill Selector     │
                              │  ├─ 技能树遍历        │
                              │  ├─ 技能叠加合并      │
                              │  └─ 能力检查          │
                              └────────┬────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
     ┌────────▼───────┐     ┌─────────▼────────┐    ┌─────────▼────────┐
     │ SkillBook Store │     │  Prompt Builder   │    │  Intent Cache    │
     │ ├─ base/        │     │ ├─ Role组装       │    │ ├─ 意图→路径映射  │
     │ ├─ domains/     │     │ ├─ Knowledge注入  │    │ ├─ 结果缓存      │
     │ ├─ capabilities │     │ ├─ Examples注入   │    │ └─ TTL管理       │
     │ └─ tree.yaml    │     │ └─ Constraints注入│    └─────────────────┘
     └────────┬───────┘     └─────────┬────────┘
              │                       │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │   Agent Pipeline      │
              │                       │
              │  Knowledge → Writer   │
              │     → Review → Judge  │
              │        → Result       │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │   Skill Learner       │
              │  ├─ Review反馈收集    │
              │  ├─ 置信度过滤        │
              │  └─ Skill增量更新     │
              └───────────────────────┘
```

### 1.3 模型角色重新定义

| 模型 | 角色 | 职责 | Skill Book 侧重 |
|------|------|------|----------------|
| **qwen2.5:1.5b** | 语言引擎 | 中文理解、知识检索、内容生成、结果格式化 | Keywords, Ontology, Examples, Templates |
| **phi4-mini:3.8b** | 逻辑引擎 | 质量评审、多维评分、难度评估 | Scoring Rules, Dimension Weights, Risk Matrix |
| **rule-engine** | 决策引擎 | 路由决策（不使用LLM） | Decision Matrix, Override Rules |

**关键约束**：两类模型各有明确的"能力边界"，Skill Book 设计必须尊重这个边界：
- qwen2.5 的 Skill 侧重**语言资源**（词汇、模板、示例）
- phi4-mini 的 Skill 侧重**判断规则**（评分标准、权重、阈值）

---

## 二、核心数据模型

### 2.1 SkillBook（技能书）

这是整个系统的核心数据结构。**不是 Prompt 文本，而是结构化数据对象**。

```yaml
# 文件: prompts/skills/tech/ai/agent.yaml
# SkillBook 完整数据模型

meta:
  skill_id: "tech.ai.agent"
  name: "AI Agent 开发"
  version: "1.0.0"
  parent: "tech.ai"                    # 父技能节点
  model: "qwen2.5:1.5b"               # 目标模型
  created: "2026-07-19"
  updated: "2026-07-19"

# ========== 角色定义 ==========
role:
  title: "AI Agent 技术专家"
  description: "专注于多智能体系统、工具调用、记忆管理等 Agent 技术栈"
  tone: "technical"
  language: "zh-CN"

# ========== 能力声明 ==========
capabilities:
  - markdown
  - mermaid
  - json_output
  - code_generation
  - architecture_design
  # 没有 latex → Agent 代码层可以判断不支持

# ========== 领域知识库 ==========
knowledge:
  keywords:
    primary:
      - Agent: ["多智能体", "Agent协作", "Agent通信", "Agent框架"]
      - RAG: ["检索增强生成", "向量数据库", "知识库", "文档检索"]
      - Memory: ["记忆管理", "短期记忆", "长期记忆", "上下文窗口"]
      - Tool: ["工具调用", "Function Call", "API集成", "MCP协议"]
      - Planning: ["任务规划", "任务分解", "ReAct", "思维链"]
    secondary:
      - ["LangChain", "AutoGen", "CrewAI", "MetaGPT", "Semantic Kernel"]
    weight: 1.0

  ontology:
    concepts:
      - term: "Agent"
        definition: "能够感知环境并采取行动以实现目标的自主实体"
        related: ["智能体", "自治系统", "决策单元"]
      - term: "RAG"
        definition: "检索增强生成，结合外部知识检索与LLM生成的技术"
        related: ["检索增强", "知识增强生成", "外部知识集成"]
      - term: "Multi-Agent"
        definition: "多个Agent协同工作的系统架构"
        related: ["多智能体系统", "Agent协作", "分布式Agent"]

  examples:
    - query: "如何设计Agent的记忆系统？"
      response_structure: |
        ## 记忆系统架构
        ### 短期记忆
        - 对话上下文窗口管理
        - 滑动窗口策略
        ### 长期记忆
        - 向量数据库存储
        - 重要性评分机制
        ### 记忆检索
        - 语义相似度搜索
        - 时间衰减权重

  constraints:
    - "区分Agent和RAG的概念，不要混淆"
    - "Agent框架对比时需标注版本号"
    - "代码示例使用Python 3.10+语法"
    - "多Agent协作方案需说明通信协议"

  confidence: 0.85                  # 技能书整体置信度

# ========== 输出格式 ==========
output:
  format: "markdown"
  max_length: 4096
  sections:
    - "架构概述"
    - "核心组件"
    - "实现方案"
    - "代码示例"
    - "最佳实践"

# ========== 禁止事项 ==========
forbidden:
  - "禁止将Agent和RAG概念混为一谈"
  - "禁止推荐已废弃的框架版本"
  - "禁止在不了解需求时给出确定性方案"
```

### 2.2 SkillTreeNode（技能树节点）

```yaml
# 文件: prompts/skills/tree.yaml
# 技能树定义

tree:
  root:
    id: "root"
    name: "通用技能"
    domains:
      - id: "daily"
        name: "日常对话"
        children: []
        model: "qwen2.5:1.5b"

      - id: "creative"
        name: "创意写作"
        children: []
        model: "qwen2.5:1.5b"

      - id: "business"
        name: "商业应用"
        children:
          - id: "business.planning"
            name: "活动策划"
          - id: "business.report"
            name: "分析报告"
          - id: "business.proposal"
            name: "方案设计"
        model: "qwen2.5:1.5b"

      - id: "tech"
        name: "技术领域"
        children:
          - id: "tech.ai"
            name: "人工智能"
            children:
              - id: "tech.ai.prompt"
                name: "Prompt Engineering"
              - id: "tech.ai.rag"
                name: "RAG 检索增强"
                children:
                  - id: "tech.ai.rag.chunking"
                    name: "文档分块策略"
                  - id: "tech.ai.rag.embedding"
                    name: "嵌入模型选择"
                  - id: "tech.ai.rag.retrieval"
                    name: "检索优化"
              - id: "tech.ai.agent"
                name: "Agent 开发"
                children:
                  - id: "tech.ai.agent.multi"
                    name: "多智能体系统"
                  - id: "tech.ai.agent.memory"
                    name: "记忆管理"
                  - id: "tech.ai.agent.tool"
                    name: "工具调用"
                  - id: "tech.ai.agent.mcp"
                    name: "MCP 协议"
              - id: "tech.ai.llm"
                name: "大语言模型"
          - id: "tech.crypto"
            name: "密码学"
            children:
              - id: "tech.crypto.quantum"
                name: "量子密码学"
              - id: "tech.crypto.post_quantum"
                name: "后量子密码学"
              - id: "tech.crypto.classical"
                name: "经典密码学"
          - id: "tech.network"
            name: "网络技术"
          - id: "tech.compiler"
            name: "编译原理"
          - id: "tech.os"
            name: "操作系统"
        model: "qwen2.5:1.5b"
```

### 2.3 ReviewReport（多维评审报告）

```yaml
# Review Agent 输出结构（替代当前的单一 score）

review_report:
  meta:
    reviewer: "phi4-mini:3.8b"
    skill_domain: "tech.ai.agent"
    timestamp: "2026-07-19T17:51:52"

  dimensions:
    accuracy:                     # 准确性（事实是否正确）
      score: 0.82
      weight: 0.25
      issues:
        - severity: "minor"
          description: "Agent定义中'自主实体'表述可更精确"
      suggestion: "补充Agent的'目标导向'特征"

    professional:                 # 专业性（术语、表达是否专业）
      score: 0.74
      weight: 0.20
      issues:
        - severity: "medium"
          description: "部分术语使用不够规范"
      suggestion: "统一使用'多智能体系统'替代'多Agent系统'"

    completeness:                 # 完整性（是否覆盖所有需求点）
      score: 0.63
      weight: 0.20
      issues:
        - severity: "high"
          description: "缺少Agent间通信协议的详细说明"
        - severity: "medium"
          description: "未涉及Agent故障恢复机制"
      suggestion: "补充通信协议和容错机制章节"

    reasoning:                    # 逻辑性（推理是否严密）
      score: 0.88
      weight: 0.15
      issues: []

    structure:                    # 结构性（组织是否清晰）
      score: 0.80
      weight: 0.10
      issues: []

    actionable:                   # 可执行性（方案是否可落地）
      score: 0.71
      weight: 0.10
      issues:
        - severity: "low"
          description: "代码示例缺少依赖安装说明"

  # 综合指标
  overall:
    weighted_score: 0.76          # 加权平均
    pass: false                   # 加权平均 < 0.80 → 不通过

  # 风险评估
  risk:
    level: "low"                  # low / medium / high / critical
    factors:
      - "专业领域内容，事实性错误影响较大"
      - "结构完整性不足，但核心逻辑正确"
    mitigation: "云端润色专业表达 + 补充缺失章节"

  # 评审置信度
  confidence: 0.91                # Review Agent 对自己评分的自信程度

  # 难度评估
  difficulty:
    threshold: 0.62               # 0-1，基于内容复杂度 + 专业度
    level: "medium-high"          # simple / medium / complex / expert
    reason: "涉及多智能体架构设计，属于中等偏上难度"
```

### 2.4 IntentCache（意图缓存）

```yaml
# 意图缓存条目

intent_cache_entry:
  intent_id: "abc123"
  fingerprint: "sha256_hash_of_normalized_input"
  original_query: "如何设计多Agent系统的记忆模块？"
  normalized_query: "多智能体系统 记忆模块 设计"
  detected_domain: "tech.ai.agent.memory"
  skill_path: ["tech", "tech.ai", "tech.ai.agent", "tech.ai.agent.memory"]
  result:
    final_output: "## 多智能体记忆系统设计\n..."
    complexity_score: 0.62
    executed_locally: false
    model_used: "deepseek-chat"
    review_report: { ... }
  created_at: "2026-07-19T17:51:52"
  ttl: 300                          # 秒
  hit_count: 3
  confidence: 0.91
```

---

## 三、Skill Tree 技能树设计

### 3.1 技能叠加机制

当 Knowledge Agent 检测到用户问题属于某领域后，沿技能树从根到叶加载所有经过的 SkillBook，**叠加合并**：

```
用户问："RAG系统中Memory模块如何设计？"

Knowledge Agent 检测路径：
  tech → tech.ai → tech.ai.agent → tech.ai.agent.memory

加载技能栈：
  Layer 1: base.yaml              (通用技能，所有任务共享)
  Layer 2: tech.yaml              (技术领域通用)
  Layer 3: tech.ai.yaml           (AI领域通用)
  Layer 4: tech.ai.agent.yaml     (Agent开发通用)
  Layer 5: tech.ai.agent.memory.yaml  (Memory专项)

叠加规则：
  - keywords: 合并去重，子节点权重更高
  - ontology: 合并，子节点定义覆盖父节点
  - constraints: 合并，子节点约束追加
  - examples: 合并，子节点示例优先
  - forbidden: 合并去重
  - capabilities: 交集（所有层都支持的能力才保留）
```

### 3.2 领域检测算法

```python
# Knowledge Agent 中的领域检测逻辑

def detect_domain_path(user_input: str, knowledge_items: list) -> List[str]:
    """
    返回技能树路径，如 ["tech", "tech.ai", "tech.ai.agent"]
    
    检测策略（优先级从高到低）：
    1. 精确关键词匹配（ontology 中的 primary keywords）
    2. 语义相似度匹配（qwen embedding 计算）
    3. 意图缓存命中（相同意图→复用路径）
    4. Fallback → "daily"
    """
    
    # Step 1: 关键词匹配
    tree = SkillTreeLoader.load()
    candidates = []
    
    for domain in tree.get_all_domains():
        skill = SkillManager.load_skill(domain)
        matched = count_keyword_matches(user_input, skill.knowledge.keywords)
        if matched > 0:
            candidates.append((domain, matched, skill.knowledge.confidence))
    
    # Step 2: 排序取最佳路径
    if candidates:
        candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
        best_domain = candidates[0][0]
        return tree.get_path_to(best_domain)
    
    # Step 3: 检查意图缓存
    if cached := IntentCache.lookup(user_input):
        return cached.skill_path
    
    # Step 4: Fallback
    return ["daily"]
```

### 3.3 能力检查机制

Writer Agent 在生成内容前，先检查当前 Skill Stack 是否具备所需能力：

```python
def check_capability(skill_stack: List[SkillBook], required: str) -> bool:
    """检查能力栈是否支持某项能力"""
    for skill in skill_stack:
        if required not in skill.capabilities:
            return False
    return True

# 使用示例
if "mermaid" in user_request:
    if check_capability(skill_stack, "mermaid"):
        # 生成 Mermaid 图表
        generate_mermaid()
    else:
        # 降级：用文字描述替代
        generate_text_description()
```

---

## 四、Skill Engine 核心组件

### 4.1 文件结构

```
backend/
├── core/
│   └── skill_engine/
│       ├── __init__.py
│       ├── skill_manager.py       # 技能书加载、缓存、查询
│       ├── skill_tree.py          # 技能树加载、遍历、路径查找
│       ├── prompt_builder.py      # 从 Skill 数据构建 System Prompt
│       ├── intent_analyzer.py     # 意图识别 + 领域检测
│       ├── intent_cache.py        # 意图缓存管理
│       └── skill_learner.py       # 技能自学习（Phase 4）
│
├── prompts/
│   └── skills/                    # 技能书数据目录
│       ├── tree.yaml              # 技能树定义
│       ├── base.yaml              # 通用技能（所有Agent共享）
│       │
│       ├── daily/
│       │   └── skill.yaml
│       ├── creative/
│       │   └── skill.yaml
│       ├── business/
│       │   ├── skill.yaml
│       │   ├── planning.yaml
│       │   ├── report.yaml
│       │   └── proposal.yaml
│       ├── tech/
│       │   ├── skill.yaml
│       │   ├── ai/
│       │   │   ├── skill.yaml
│       │   │   ├── prompt.yaml
│       │   │   ├── rag/
│       │   │   │   ├── skill.yaml
│       │   │   │   ├── chunking.yaml
│       │   │   │   ├── embedding.yaml
│       │   │   │   └── retrieval.yaml
│       │   │   ├── agent/
│       │   │   │   ├── skill.yaml
│       │   │   │   ├── multi.yaml
│       │   │   │   ├── memory.yaml
│       │   │   │   ├── tool.yaml
│       │   │   │   └── mcp.yaml
│       │   │   └── llm.yaml
│       │   ├── crypto/
│       │   │   ├── skill.yaml
│       │   │   ├── quantum.yaml
│       │   │   ├── post_quantum.yaml
│       │   │   └── classical.yaml
│       │   ├── network.yaml
│       │   ├── compiler.yaml
│       │   └── os.yaml
│       │
│       └── review/                # Review Agent 专属技能书
│           ├── base_scoring.yaml  # 通用评分标准
│           ├── tech_scoring.yaml  # 技术领域评分标准
│           ├── business_scoring.yaml
│           ├── creative_scoring.yaml
│           ├── daily_scoring.yaml
│           └── difficulty_matrix.yaml  # 难度分级矩阵
│
└── prompts/
    └── templates/                 # 保留现有模板（作为 fallback）
        ├── knowledge/
        ├── writer/
        ├── review/
        ├── judge/
        └── result/
```

### 4.2 SkillManager 接口

```python
class SkillManager:
    """技能书管理器 — 核心组件"""

    def __init__(self, skills_dir: str):
        self._skills_dir = skills_dir
        self._cache: Dict[str, SkillBook] = {}
        self._tree: SkillTree = None

    # ===== 加载 =====
    def load_skill(self, skill_id: str) -> SkillBook:
        """加载单个技能书（带缓存）"""
        if skill_id in self._cache:
            return self._cache[skill_id]
        
        filepath = self._resolve_path(skill_id)
        skill = SkillBook.from_yaml(filepath)
        self._cache[skill_id] = skill
        return skill

    def load_skill_stack(self, skill_path: List[str]) -> List[SkillBook]:
        """沿技能树路径加载技能栈（从根到叶）"""
        return [self.load_skill(sid) for sid in skill_path]

    def load_skill_stack_merged(self, skill_path: List[str]) -> SkillBook:
        """加载并合并技能栈（子节点覆盖父节点）"""
        stack = self.load_skill_stack(skill_path)
        return SkillBook.merge(stack)

    # ===== 查询 =====
    def get_capabilities(self, skill_path: List[str]) -> Set[str]:
        """获取技能栈支持的能力集合（交集）"""
        capabilities = None
        for skill in self.load_skill_stack(skill_path):
            if capabilities is None:
                capabilities = set(skill.capabilities)
            else:
                capabilities &= set(skill.capabilities)
        return capabilities or set()

    def get_keywords(self, skill_path: List[str]) -> Dict:
        """获取技能栈的关键词库（合并）"""
        merged = {}
        for skill in self.load_skill_stack(skill_path):
            for category, kws in skill.knowledge.keywords.items():
                if category not in merged:
                    merged[category] = {}
                merged[category].update(kws)
        return merged

    # ===== 领域检测 =====
    def detect_domain(self, user_input: str) -> List[str]:
        """检测用户输入对应的技能树路径"""
        return self._tree.detect_path(user_input)

    # ===== 缓存管理 =====
    def invalidate_cache(self, skill_id: str = None):
        """清除缓存"""
        if skill_id:
            self._cache.pop(skill_id, None)
        else:
            self._cache.clear()
```

### 4.3 PromptBuilder（Prompt 构建器）

```python
class PromptBuilder:
    """从 SkillBook 数据构建最终的 System Prompt"""

    @staticmethod
    def build_system_prompt(agent_id: str, skill_stack: List[SkillBook]) -> str:
        """将技能栈拼接为 LLM 可读的 System Prompt"""
        merged = SkillBook.merge(skill_stack)
        
        sections = []
        
        # 1. 角色定义
        sections.append(f"# 角色\n你是 {merged.role.title}。{merged.role.description}")
        
        # 2. 能力声明
        sections.append(f"\n# 能力\n支持: {', '.join(merged.capabilities)}")
        
        # 3. 领域知识
        sections.append("\n# 领域知识")
        for term, definition in merged.knowledge.ontology.items():
            sections.append(f"- **{term}**: {definition}")
        
        # 4. 写作约束
        sections.append("\n# 约束")
        for c in merged.constraints:
            sections.append(f"- {c}")
        
        # 5. 示例
        if merged.knowledge.examples:
            sections.append("\n# 示例")
            for i, ex in enumerate(merged.knowledge.examples[:2], 1):
                sections.append(f"\n## 示例{i}: {ex['query']}")
                sections.append(ex['response_structure'])
        
        # 6. 禁止事项
        sections.append("\n# 禁止")
        for f in merged.forbidden:
            sections.append(f"- {f}")
        
        # 7. 输出格式
        sections.append(f"\n# 输出格式\n{merged.output.format}")
        if merged.output.sections:
            sections.append(f"章节结构: {' → '.join(merged.output.sections)}")
        
        return "\n".join(sections)

    @staticmethod
    def build_review_prompt(skill_stack: List[SkillBook], content: str) -> str:
        """构建 Review Agent 的评审 Prompt（含领域权重）"""
        merged = SkillBook.merge(skill_stack)
        
        weights = merged.scoring.dimensions  # 领域特定的评分权重
        
        prompt = f"""你是 Review Agent，请按以下标准评审内容质量。

## 评审维度及权重
"""
        for dim, weight in weights.items():
            prompt += f"- {dim}: 权重 {weight}\n"
        
        prompt += f"""
## 难度参考矩阵
{merged.scoring.difficulty_matrix}

## 待评审内容
{content[:3000]}

## 输出格式（严格 JSON）
{{
  "dimensions": {{
    "accuracy": {{"score": 0.0, "issues": [], "suggestion": ""}},
    "professional": {{"score": 0.0, "issues": [], "suggestion": ""}},
    "completeness": {{"score": 0.0, "issues": [], "suggestion": ""}},
    "reasoning": {{"score": 0.0, "issues": []}},
    "structure": {{"score": 0.0, "issues": []}},
    "actionable": {{"score": 0.0, "issues": []}}
  }},
  "overall": {{"weighted_score": 0.0, "pass": false}},
  "risk": {{"level": "low", "factors": [], "mitigation": ""}},
  "confidence": 0.0,
  "difficulty": {{"threshold": 0.0, "level": "medium", "reason": ""}}
}}
"""
        return prompt
```

---

## 五、Agent 改造方案

### 5.1 Knowledge Agent 改造

**改造点**：从硬编码关键词 → Skill Book 驱动

```python
class KnowledgeAgent(BaseAgent):
    def __init__(self, settings=None):
        super().__init__("knowledge", "Knowledge Agent", settings=settings)
        self.local_model = "qwen2.5:1.5b"
        self._skill_manager = None
        self._intent_analyzer = None

    @property
    def skill_manager(self):
        if self._skill_manager is None:
            from core.skill_engine.skill_manager import SkillManager
            self._skill_manager = SkillManager()
        return self._skill_manager

    @property
    def intent_analyzer(self):
        if self._intent_analyzer is None:
            from core.skill_engine.intent_analyzer import IntentAnalyzer
            self._intent_analyzer = IntentAnalyzer()
        return self._intent_analyzer

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        # 1. 意图分析 + 领域检测
        intent = self.intent_analyzer.analyze(input_data.content)
        skill_path = intent.skill_path  # e.g. ["tech", "tech.ai", "tech.ai.agent"]
        
        # 2. 加载技能栈
        skill_stack = self.skill_manager.load_skill_stack(skill_path)
        
        # 3. 从 Skill 数据提取关键词（不是硬编码）
        keywords = self._extract_keywords_from_skill(input_data.content, skill_stack)
        
        # 4. 知识库检索（使用 Skill 中的 ontology 辅助匹配）
        knowledge_items = self._search_with_ontology(keywords, skill_stack)
        
        # 5. 任务类型判断（从 Skill 元数据）
        task_type = skill_stack[-1].meta.name  # 最深层技能名
        
        # 6. 生成结构化摘要（注入 Skill 知识）
        summary = self._generate_summary_with_skill(
            input_data.content, keywords, knowledge_items, skill_stack
        )
        
        return AgentOutput(
            content=json.dumps(summary, ensure_ascii=False),
            metadata={
                "skill_path": skill_path,
                "skill_domain": skill_path[-1],
                "knowledge_count": len(knowledge_items),
                "matched_keywords": keywords,
                "task_type": task_type,
            }
        )

    def _extract_keywords_from_skill(self, content: str, skill_stack: List[SkillBook]) -> List[str]:
        """从 Skill Book 的关键词库中匹配（替代硬编码 common_keywords）"""
        keywords = []
        for skill in skill_stack:
            for category, kw_map in skill.knowledge.keywords.items():
                for kw, aliases in kw_map.items():
                    all_terms = [kw] + aliases
                    if any(term in content for term in all_terms):
                        if kw not in keywords:
                            keywords.append(kw)
        return keywords[:12]
```

### 5.2 Writer Agent 改造

**改造点**：能力检查 + Skill 引导生成

```python
class WriterAgent(BaseAgent):
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        parsed = self._parse_knowledge_output(input_data.content)
        
        # 获取上游 Knowledge Agent 检测到的技能路径
        skill_path = parsed.get("skill_path", ["daily"])
        skill_stack = self.skill_manager.load_skill_stack(skill_path)
        
        # 能力检查：如果用户要求 Mermaid 但 Skill 不支持，提前降级
        if "mermaid" in parsed.get("original_question", "").lower():
            if not self._check_capability(skill_stack, "mermaid"):
                # 在 prompt 中明确告知不要生成 Mermaid
                parsed["_no_mermaid"] = True
        
        # 使用 Skill 引导的责任链（每个 Handler 注入 Skill 上下文）
        chain = self._build_handler_chain(skill_stack)
        result = await chain.handle(parsed)
        
        return result

    async def _generate_with_skill(self, parsed: dict, skill_stack: List[SkillBook]) -> str:
        """使用 Skill 数据引导生成"""
        merged = SkillBook.merge(skill_stack)
        
        prompt = self._build_writer_prompt(parsed, merged)
        response = await self._call_llm(
            prompt, 
            model=self.local_model, 
            system_prompt=PromptBuilder.build_system_prompt("writer", skill_stack),
            temperature=0.3
        )
        return response
```

### 5.3 Review Agent 改造

**改造点**：从单一 score → 多维 ReviewReport

```python
class ReviewAgent(BaseAgent):
    def __init__(self, settings=None):
        super().__init__("review", "Review Agent", settings=settings)
        self.local_model = "phi4-mini:3.8b"
        self._skill_manager = None

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        input_dict = safe_json_parse(input_data.content)
        user_task = input_dict.get("user_task", "")
        writer_output = input_dict.get("writer_output", "")
        skill_path = input_dict.get("skill_path", ["daily"])
        
        # 加载领域特定的评分标准
        review_skill = self.skill_manager.load_review_skill(skill_path)
        
        if input_data.use_llm:
            # 使用领域权重构建评审 prompt
            review_report = await self._review_with_skill_llm(
                user_task, writer_output, review_skill
            )
        else:
            # 规则引擎评审（也使用领域权重）
            review_report = self._review_with_skill_rules(
                user_task, writer_output, review_skill
            )
        
        return AgentOutput(
            content=json.dumps(review_report, ensure_ascii=False),
            metadata={
                "weighted_score": review_report["overall"]["weighted_score"],
                "difficulty_threshold": review_report["difficulty"]["threshold"],
                "risk_level": review_report["risk"]["level"],
                "confidence": review_report["confidence"],
                "dimensions": review_report["dimensions"],
            }
        )

    def _review_with_skill_rules(self, user_task: str, writer_output: str,
                                  review_skill: SkillBook) -> dict:
        """使用领域评分权重进行规则引擎评审"""
        weights = review_skill.scoring.dimensions
        
        # 每个维度独立评分
        dims = {}
        for dim_name, dim_weight in weights.items():
            score = self._score_dimension(dim_name, user_task, writer_output, review_skill)
            dims[dim_name] = score
        
        # 加权平均
        weighted_score = sum(
            dims[d]["score"] * weights[d] for d in dims
        ) / sum(weights.values())
        
        # 难度评估（使用领域难度矩阵）
        difficulty = self._calculate_difficulty_with_matrix(
            user_task, writer_output, review_skill
        )
        
        return {
            "dimensions": dims,
            "overall": {
                "weighted_score": round(weighted_score, 2),
                "pass": weighted_score >= 0.65
            },
            "risk": self._assess_risk(dims, review_skill),
            "confidence": self._calculate_confidence(dims),
            "difficulty": difficulty
        }
```

### 5.4 Judge Agent 改造

**改造点**：从只看 score → 看 ReviewReport 的多维数据做精确决策

```python
class JudgeAgent(BaseAgent):
    def _make_routing_decision(self, user_task: str, review_report: dict,
                                 writer_output: str) -> dict:
        """基于 ReviewReport 的多维决策（替代只看 score）"""
        
        dims = review_report.get("dimensions", {})
        overall = review_report.get("overall", {})
        risk = review_report.get("risk", {})
        difficulty = review_report.get("difficulty", {})
        
        weighted_score = overall.get("weighted_score", 0.7)
        diff_threshold = difficulty.get("threshold", 0.5)
        risk_level = risk.get("level", "low")
        
        reason = []
        
        # 精确决策：哪个维度弱就针对性处理
        if risk_level == "critical":
            decision = "cloud_enhance"
            cloud_mode = "full_rewrite"
            reason.append(f"风险等级 {risk_level}，云端完整重写")
        
        elif diff_threshold < 0.35:
            decision = "local_output"
            cloud_mode = "none"
            reason.append(f"难度 {diff_threshold:.2f} < 0.35，本地处理")
        
        elif diff_threshold < 0.65:
            # 中等难度 → 看具体维度
            professional = dims.get("professional", {}).get("score", 0.7)
            completeness = dims.get("completeness", {}).get("score", 0.7)
            accuracy = dims.get("accuracy", {}).get("score", 0.7)
            
            if professional < 0.70:
                # 专业度不足 → 云端润色专业表达
                decision = "cloud_enhance"
                cloud_mode = "polish"
                reason.append(f"专业度 {professional:.2f} < 0.70，云端润色")
            elif completeness < 0.65:
                # 完整性不足 → 云端补充内容
                decision = "cloud_enhance"
                cloud_mode = "polish"  # 先润色，严重时改写
                reason.append(f"完整性 {completeness:.2f} < 0.65，云端补充")
            elif accuracy < 0.75:
                # 准确性不足 → 云端修正
                decision = "cloud_enhance"
                cloud_mode = "full_rewrite"
                reason.append(f"准确性 {accuracy:.2f} < 0.75，云端重写修正")
            else:
                decision = "local_output"
                cloud_mode = "none"
                reason.append(f"所有维度达标，本地处理")
        
        elif diff_threshold < 0.80:
            if weighted_score >= 0.80:
                decision = "local_output"
                cloud_mode = "none"
            else:
                decision = "cloud_enhance"
                cloud_mode = "full_rewrite"
                reason.append(f"高难度 {diff_threshold:.2f} + 评分不足 {weighted_score:.2f}")
        
        else:
            decision = "cloud_enhance"
            cloud_mode = "full_rewrite"
            reason.append(f"极高难度 {diff_threshold:.2f}，云端完整重写")
        
        return {
            "decision": decision,
            "cloud_mode": cloud_mode,
            "difficulty_threshold": round(diff_threshold, 2),
            "review_score": round(weighted_score, 2),
            "reason": reason
        }
```

### 5.5 Result Agent 改造

**改造点**：基于 Review Report 的精确增强

```python
class ResultAgent(BaseAgent):
    async def _cloud_polish_with_report(self, user_task: str, writer_output: str,
                                          review_report: dict) -> str:
        """基于 Review Report 的针对性云端润色"""
        
        dims = review_report.get("dimensions", {})
        
        # 只针对评分低的维度进行润色
        weak_dims = [
            name for name, data in dims.items()
            if data.get("score", 1.0) < 0.70
        ]
        
        focus = ""
        if "professional" in weak_dims:
            focus += "- 提升专业术语的准确性和一致性\n"
        if "completeness" in weak_dims:
            focus += "- 补充缺失的关键内容章节\n"
        if "accuracy" in weak_dims:
            focus += "- 修正事实性错误\n"
        
        prompt = f"""请对以下内容进行定向润色优化。

【用户需求】{user_task}

【原始内容】{writer_output[:2000]}

【重点改进方向】
{focus}

【润色要求】
1. 保持原有结构和核心内容
2. 重点改进以上标注的薄弱维度
3. 直接输出润色后的内容，不要添加解释

请直接输出："""
        
        response = await self._call_llm(
            prompt, model=self.cloud_model, use_cloud=True,
            temperature=0.3, max_tokens=4096
        )
        return response if response else writer_output
```

---

## 六、Skill Learning 自学习机制

### 6.1 学习闭环

```
用户请求 → Agent Pipeline → Review Report
                                  │
                    ┌─────────────┘
                    ▼
             confidence > 0.85 ?
              │            │
             是            否
              │            │
              ▼            ▼
        Skill Learner   丢弃反馈
              │
              ▼
        生成 Skill Patch
              │
              ▼
        人工审核（Phase 1）
        自动审核（Phase 2）
              │
              ▼
        更新 Skill Book
        版本号 +1
```

### 6.2 SkillLearner 实现

```python
class SkillLearner:
    """技能自学习器"""

    def __init__(self, min_confidence: float = 0.85, min_samples: int = 3):
        self.min_confidence = min_confidence
        self.min_samples = min_samples
        self._feedback_buffer: Dict[str, List[ReviewReport]] = {}

    def collect_feedback(self, skill_path: List[str], review_report: dict):
        """收集 Review 反馈"""
        domain = skill_path[-1]
        confidence = review_report.get("confidence", 0)
        
        # 只有高置信度反馈才纳入学习
        if confidence < self.min_confidence:
            return
        
        if domain not in self._feedback_buffer:
            self._feedback_buffer[domain] = []
        self._feedback_buffer[domain].append(review_report)

    def should_learn(self, domain: str) -> bool:
        """判断是否应该触发学习"""
        if domain not in self._feedback_buffer:
            return False
        return len(self._feedback_buffer[domain]) >= self.min_samples

    def generate_patch(self, domain: str) -> SkillPatch:
        """生成技能补丁"""
        feedbacks = self._feedback_buffer[domain]
        
        patch = SkillPatch(domain=domain)
        
        # 分析常见问题
        weak_dimensions = self._analyze_weak_dimensions(feedbacks)
        common_issues = self._extract_common_issues(feedbacks)
        
        # 生成改进
        if weak_dimensions:
            patch.add_constraints(self._generate_dimension_fixes(weak_dimensions))
        
        if common_issues:
            patch.add_examples(self._generate_corrective_examples(common_issues))
            patch.add_forbidden(self._extract_forbidden_patterns(common_issues))
        
        # 清除缓冲区
        self._feedback_buffer[domain] = []
        
        return patch

    def apply_patch(self, skill_id: str, patch: SkillPatch, auto_approve: bool = False):
        """应用技能补丁（Phase 1 需要人工审核）"""
        if not auto_approve:
            # 保存为待审核补丁
            patch.save_pending(skill_id)
            return
        
        # 自动应用
        skill = SkillManager().load_skill(skill_id)
        skill.apply_patch(patch)
        skill.meta.version = self._bump_version(skill.meta.version)
        skill.save()
```

### 6.3 学习效果示例

```
初始 skill: tech.ai.agent.yaml (v1.0.0)
  - 关键词: ["Agent", "RAG", "Memory"]
  - 约束: ["区分Agent和RAG的概念"]

第1次反馈: 用户问"Agent通信协议"，Review 发现缺少相关内容
  → Patch: 添加关键词 "通信协议", "消息队列"
  → v1.0.1

第2次反馈: 用户问"Agent故障恢复"，Review 发现未涉及
  → Patch: 添加关键词 "容错", "故障恢复", "熔断"
  → v1.0.2

第3次反馈: 用户问"Agent评估指标"，Review 评分低
  → Patch: 添加 ontology.tasks: 任务成功率, 响应时间, Token消耗
  → v1.0.3

v1.0.3 的 tech.ai.agent.yaml 已比 v1.0.0 丰富很多
```

---

## 七、Intent Cache 意图缓存融合

### 7.1 缓存架构

```python
class IntentCache:
    """意图缓存 — 两层缓存结构"""

    def __init__(self):
        # L1: 意图→技能路径映射（轻量，命中率高）
        self._skill_path_cache: Dict[str, CacheEntry] = {}
        # L2: 完整结果缓存（重量，仅缓存 executed_locally=true 的结果）
        self._result_cache: Dict[str, CacheEntry] = {}
        
        self._max_size = 200
        self._ttl = 300  # 秒

    def lookup_skill_path(self, query: str) -> Optional[List[str]]:
        """L1 缓存：查询意图对应的技能路径"""
        fingerprint = self._fingerprint(query)
        entry = self._skill_path_cache.get(fingerprint)
        if entry and not entry.is_expired():
            entry.hit()
            return entry.data
        return None

    def lookup_result(self, query: str) -> Optional[dict]:
        """L2 缓存：查询完整结果"""
        fingerprint = self._fingerprint(query)
        entry = self._result_cache.get(fingerprint)
        if entry and not entry.is_expired():
            entry.hit()
            return entry.data
        return None

    def store_skill_path(self, query: str, skill_path: List[str]):
        """存储意图→技能路径映射"""
        self._skill_path_cache[self._fingerprint(query)] = CacheEntry(
            data=skill_path, ttl=self._ttl
        )

    def store_result(self, query: str, result: dict):
        """存储完整结果（仅本地执行的结果）"""
        if not result.get("executed_locally"):
            return  # 只缓存本地结果
        if len(result.get("final_result", "")) > 5000:
            return  # 过长不缓存
        
        self._result_cache[self._fingerprint(query)] = CacheEntry(
            data=result, ttl=self._ttl
        )

    def _fingerprint(self, query: str) -> str:
        """生成查询指纹（归一化后哈希）"""
        normalized = self._normalize(query)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _normalize(self, query: str) -> str:
        """归一化查询文本"""
        # 去标点、去空格、小写
        import re
        cleaned = re.sub(r'[^\w\s]', '', query)
        return ' '.join(cleaned.lower().split())

    def get_stats(self) -> dict:
        return {
            "skill_path_cache_size": len(self._skill_path_cache),
            "result_cache_size": len(self._result_cache),
            "total_hits": sum(e.hit_count for e in self._skill_path_cache.values()),
            "max_size": self._max_size,
            "ttl": self._ttl
        }
```

### 7.2 缓存集成到 Workflow

```python
# workflow/service.py 中的改动

async def execute_workflow(self, user_input: str) -> WorkflowOutput:
    intent_cache = IntentCache()
    
    # Step 0: 检查结果缓存（L2）
    if cached_result := intent_cache.lookup_result(user_input):
        return WorkflowOutput(**cached_result)
    
    # Step 1: 检查技能路径缓存（L1）
    skill_path = intent_cache.lookup_skill_path(user_input)
    
    if not skill_path:
        # 未命中 → Knowledge Agent 做领域检测
        knowledge_result = await self.knowledge_agent.execute(user_input)
        skill_path = knowledge_result.metadata["skill_path"]
        intent_cache.store_skill_path(user_input, skill_path)
    
    # Step 2-6: 执行 Agent Pipeline
    result = await self._run_pipeline(user_input, skill_path)
    
    # Step 7: 更新缓存
    intent_cache.store_result(user_input, result)
    
    return result
```

---

## 八、实施路线图

### 总览

```
Phase 1: 基础设施     (3-4天)  核心数据模型 + SkillManager + PromptBuilder
Phase 2: 技能树       (2-3天)  SkillTree + 技能叠加 + 领域检测
Phase 3: Agent改造    (3-4天)  5个Agent逐一接入 Skill Engine
Phase 4: 多维评审     (2-3天)  Review Report + Judge 精确决策
Phase 5: 技能书编写   (3-5天)  编写 tech/ai/agent/crypto 等技能书
Phase 6: 自学习       (2-3天)  Skill Learner + 反馈收集
Phase 7: 意图缓存     (1-2天)  Intent Cache 集成
Phase 8: 集成测试     (2-3天)  三轮测试 + 调优
```

### Phase 1: 基础设施（3-4天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 1.1 | `core/skill_engine/__init__.py` | 模块初始化 |
| 1.2 | `core/skill_engine/skill_manager.py` | SkillBook 加载、缓存、合并 |
| 1.3 | `core/skill_engine/prompt_builder.py` | Skill → Prompt 转换 |
| 1.4 | `core/skill_engine/models.py` | SkillBook, SkillTree等数据类 |
| 1.5 | `prompts/skills/base.yaml` | 通用技能书 |
| 1.6 | 单元测试 | 测试 SkillBook 加载、合并、Prompt 生成 |

**验收标准**：
- `SkillManager.load_skill("base")` 返回正确的 SkillBook 对象
- `SkillBook.merge([s1, s2, s3])` 正确合并
- `PromptBuilder.build_system_prompt("writer", stack)` 输出可读 prompt

### Phase 2: 技能树（2-3天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 2.1 | `core/skill_engine/skill_tree.py` | 技能树加载、遍历、路径检测 |
| 2.2 | `prompts/skills/tree.yaml` | 技能树定义 |
| 2.3 | `core/skill_engine/intent_analyzer.py` | 意图分析 + 领域检测 |
| 2.4 | 测试 | 各领域检测准确率 |

**验收标准**：
- "量子计算" → 检测到 `["tech", "tech.crypto", "tech.crypto.quantum"]`
- "写一首诗" → 检测到 `["creative"]`
- "活动策划" → 检测到 `["business", "business.planning"]`

### Phase 3: Agent 改造（3-4天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 3.1 | `agents/knowledge/agent.py` | 接入 SkillManager + 领域检测 |
| 3.2 | `agents/writer/agent.py` | 能力检查 + Skill 引导生成 |
| 3.3 | `agents/review/agent.py` | 领域评分权重 |
| 3.4 | `agents/judge/agent.py` | 多维决策 |
| 3.5 | `agents/result/agent.py` | 针对性云端增强 |

**验收标准**：5个Agent都能从 Skill 数据工作，而非硬编码逻辑

### Phase 4: 多维评审（2-3天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 4.1 | `prompts/skills/review/base_scoring.yaml` | 通用评分标准 |
| 4.2 | `prompts/skills/review/tech_scoring.yaml` | 技术领域评分标准 |
| 4.3 | `prompts/skills/review/difficulty_matrix.yaml` | 难度分级矩阵 |
| 4.4 | Review Agent 改造 | 输出 ReviewReport 而非单一 score |
| 4.5 | Judge Agent 改造 | 基于 ReviewReport 精确决策 |

**验收标准**：
- Review Agent 输出包含6个维度 + risk + confidence
- Judge Agent 能根据"专业度低"精确触发 polish
- Judge Agent 能根据"准确性低"精确触发 rewrite

### Phase 5: 技能书编写（3-5天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 5.1 | `tech/ai/skill.yaml` | AI 通用技能 |
| 5.2 | `tech/ai/agent/*.yaml` | Agent 开发技能树 |
| 5.3 | `tech/ai/rag/*.yaml` | RAG 技能树 |
| 5.4 | `tech/crypto/*.yaml` | 密码学技能树 |
| 5.5 | `business/*.yaml` | 商业技能 |
| 5.6 | `creative/skill.yaml` | 创意写作技能 |
| 5.7 | `daily/skill.yaml` | 日常对话技能 |

**验收标准**：至少覆盖 tech/ai 完整技能树 + business + creative + daily

### Phase 6: 自学习（2-3天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 6.1 | `core/skill_engine/skill_learner.py` | 学习器 + 反馈收集 |
| 6.2 | 反馈收集集成 | Review → SkillLearner |
| 6.3 | Patch 生成 + 应用 | 半自动模式 |

**验收标准**：
- 3次相同领域反馈后，能生成合理的 Skill Patch
- Patch 人工审核后可正确应用到 Skill Book

### Phase 7: 意图缓存（1-2天）

| 任务 | 文件 | 说明 |
|------|------|------|
| 7.1 | `core/skill_engine/intent_cache.py` | 两层缓存实现 |
| 7.2 | Workflow 集成 | 缓存检查 + 更新 |

**验收标准**：
- 相同意图第二次查询命中 L2 缓存，跳过整个 Pipeline
- 相似意图命中 L1 缓存，跳过领域检测

### Phase 8: 集成测试（2-3天）

| 任务 | 说明 |
|------|------|
| 8.1 | 简单问题测试（问候、闲聊） |
| 8.2 | 中等复杂度测试（创意写作、方案策划） |
| 8.3 | 高复杂度测试（量子计算、多智能体架构） |
| 8.4 | Skill 叠加测试（多层技能合并正确性） |
| 8.5 | 能力检查测试（Mermaid 支持/不支持） |
| 8.6 | 缓存命中测试 |
| 8.7 | 自学习测试 |

---

## 九、风险评估与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| phi4-mini 无法稳定输出多维 JSON | 中 | 高 | Review 默认走规则引擎，LLM 评审为可选增强 |
| 技能树领域检测准确率低 | 中 | 中 | 多层检测（关键词+语义+缓存），低置信度 fallback 到 daily |
| 技能叠加后 Prompt 过长 | 中 | 中 | 限制最大叠加层数（5层），超过则截断 |
| Skill Learning 学坏 | 中 | 高 | 高置信度过滤 + 半自动审核 + 版本回滚 |
| 技能书编写工作量大 | 高 | 中 | Phase 5 只写核心领域，其他按需扩展 |
| 向后兼容性问题 | 低 | 中 | 保留 templates/ 目录作为 fallback |

---

## 十、验收标准

### 功能验收

- [ ] SkillManager 能正确加载、缓存、合并 SkillBook
- [ ] SkillTree 能正确遍历和检测领域路径
- [ ] PromptBuilder 能从 Skill 数据生成正确的 System Prompt
- [ ] 5个 Agent 全部接入 Skill Engine
- [ ] Knowledge Agent 能检测技术/商业/创意/日常四大领域
- [ ] Writer Agent 能进行能力检查（Mermaid/LaTeX等）
- [ ] Review Agent 能输出 6维 ReviewReport
- [ ] Judge Agent 能基于 ReviewReport 精确决策
- [ ] Intent Cache 两层缓存正常工作
- [ ] Skill Learner 能收集反馈并生成 Patch

### 性能验收

- [ ] 技能书加载带缓存，首次加载 < 100ms，后续 < 5ms
- [ ] 意图缓存命中时，Pipeline 跳过耗时 < 50ms
- [ ] Prompt 构建 < 20ms
- [ ] 整体 Workflow 延迟相比 V1 增加不超过 15%

### 质量验收（三轮测试）

- [ ] 简单问候正确识别为 daily，本地处理
- [ ] 创意写作正确识别为 creative，能力检查通过
- [ ] 技术问题正确识别到具体子领域（如 tech.ai.agent.memory）
- [ ] 量子计算问题 difficulty >= 0.60（相比 V1 的 0.44 有显著提升）
- [ ] 专业领域问题的 Review 评分有明显分化（不再都是 0.44~0.64）

---

**文档版本**: v1.0-draft
**编写日期**: 2026-07-19
**下一步**: 评审通过后，按 Phase 1 开始实施