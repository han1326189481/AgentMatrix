"""Decomposer — 基于 Skill Graph 的问题分解器（零 LLM）

策略:
1. 关键词提取（正则，非 LLM）
2. SkillGraph.search_by_name() 节点匹配
3. SkillGraph.get_children("has_part") 邻居扩展
4. SkillGraph.get_prerequisites() 前置检测
"""

import re, logging
from typing import List

logger = logging.getLogger(__name__)


class Decomposer:
    """将用户问题分解为相关 Skill 节点"""

    # ============================================================
    # 技术术语别名表（V2.2 — 2026-07-30 扩充）
    # ------------------------------------------------------------
    # 作用:
    #   1. 识别多词/缩写形式的技术术语为单个语义单元
    #      （如 "K8s" → "Kubernetes"、"ClusterIP" 整词识别）
    #   2. 同义词归一化，避免同一概念因写法不同匹配不到 Skill Graph 节点
    #
    # 格式: {规范名: [别名1, 别名2, ...]}
    # 别名匹配不区分大小写（见 _extract_keywords 中的 lower() 比较）
    # ============================================================
    _TECH_TERM_ALIASES = {
        # 容器与编排
        "Kubernetes": ["k8s", "kube", "kubernetes"],
        "Docker": ["docker", "containerd"],
        "ClusterIP": ["clusterip", "cluster ip"],
        "NodePort": ["nodeport", "node port"],
        "LoadBalancer": ["loadbalancer", "load balancer"],
        "Ingress": ["ingress"],
        "Pod": ["pod"],
        # V2.4 (2026-07-30): 移除过通用的 "Service": ["svc", "service"]
        #   原因: "service" 在英文中极常见（非技术语境也会出现），
        #         易误匹配；"svc" 作为缩写保留意义不大（K8s context 已被 ClusterIP/NodePort 覆盖）。
        #   若需匹配 K8s Service，用户输入 "Service" 大写时会被英文专有名词正则捕获。
        "ConfigMap": ["configmap", "config map"],
        "Helm": ["helm"],
        "Istio": ["istio"],
        # 云计算
        "AWS": ["aws", "amazon web services"],
        "GCP": ["gcp", "google cloud"],
        "Azure": ["azure", "microsoft azure"],
        "Amazon S3": ["amazon s3", "s3 bucket"],  # V2.4: "S3"→"Amazon S3"，移除单独 "s3"（过短易误匹配）
        "EC2": ["ec2"],
        "AWS Lambda": ["aws lambda"],  # V2.4: "Lambda"→"AWS Lambda"，避免与 Python lambda 混淆
        # AI / ML
        "Transformer": ["transformer"],
        "BERT": ["bert"],
        "GPT": ["gpt"],
        "LLM": ["llm", "large language model"],
        "RAG": ["rag", "retrieval augmented generation"],
        "Embedding": ["embedding"],
        "Attention": ["attention", "attention mechanism", "注意力机制"],
        "CNN": ["cnn", "convolutional neural network"],
        "RNN": ["rnn"],
        "LSTM": ["lstm"],
        "Reinforcement Learning": ["reinforcement learning", "强化学习", "rl"],
        "Deep Learning": ["deep learning", "深度学习"],
        "Prompt Engineering": ["prompt engineering", "提示工程"],
        "Fine-tuning": ["fine-tuning", "finetuning", "fine tuning", "微调"],
        # 框架与工具
        "React": ["react", "reactjs"],
        "Vue": ["vue", "vuejs"],
        "Next.js": ["nextjs", "next.js"],
        "FastAPI": ["fastapi", "fast api"],
        "Flask": ["flask"],
        "Django": ["django"],
        "PyTorch": ["pytorch", "torch"],
        "TensorFlow": ["tensorflow", "tf"],
        "Ollama": ["ollama"],
        "LangChain": ["langchain"],
        # 数据库
        "MySQL": ["mysql"],
        "PostgreSQL": ["postgresql", "postgres"],
        "SQLite": ["sqlite"],
        "Redis": ["redis"],
        "MongoDB": ["mongodb", "mongo"],
        "Elasticsearch": ["elasticsearch"],  # V2.4: 移除 "es"（过短，易误匹配中文拼音）
        # 网络与协议
        "HTTP": ["http"],
        "HTTPS": ["https"],
        "gRPC": ["grpc"],
        "WebSocket": ["websocket", "ws"],
        "REST": ["rest", "restful"],
        "GraphQL": ["graphql"],
        "TCP": ["tcp"],
        "UDP": ["udp"],
        # 操作系统/底层
        "Linux": ["linux"],
        "Nginx": ["nginx"],
        # V2.4 (2026-07-30): 移除 "Git": ["git"]
        #   原因: "git" 可能是动词或普通名词，单义性差。
        #         用户输入 "Git" 大写时会被英文专有名词正则捕获，无需别名表。
        "CI/CD": ["ci/cd", "cicd", "ci cd"],
        # AgentMatrix 自身概念
        "Multi-Agent": ["multi-agent", "multi agent", "多智能体", "多agent"],
        "Skill Graph": ["skill graph", "技能图谱"],
        "Knowledge Graph": ["knowledge graph", "知识图谱"],
        "Cognitive Architecture": ["cognitive architecture", "认知架构"],
    }

    # 中文停用词 — 用户提问级噪声过滤
    # 这些词在 2-3 字滑动窗口中会被切出来，但无语义价值，
    # 会污染 Skill Graph 匹配（如 "什么"、"区别"、"中" 误匹配节点）
    _CN_STOPWORDS = frozenset({
        # 疑问/指示词
        "什么", "怎么", "怎样", "如何", "为什么", "为何", "哪里", "哪个", "哪些",
        "是不是", "有没有", "能不能", "可不可以", "的话",
        # 关系/比较词（提问中的连接词，非实体）
        "区别", "差异", "不同", "相同", "类似", "对比", "比较", "关系", "联系",
        "区分", "辨别", "分辨",
        # 介词/连词/助词
        "中的", "中有", "中和", "和与", "与的", "和的", "和有",
        "以及", "或者", "并且", "但是", "因为", "所以", "虽然", "尽管",
        "如果", "的话", "不是", "还有", "还有", "以及",
        # 单字/双字虚词
        "的中", "中的", "中有", "和", "与", "或", "及", "的", "是", "有",
        "在", "中", "上", "下", "里", "外", "内", "间",
        # 常见动词（提问动作，非实体）
        "介绍", "说明", "解释", "阐述", "描述", "讲解", "告诉", "列出",
        "举例", "总结", "归纳", "整理", "分析", "评估",
        # 量词/泛指
        "一个", "一种", "一些", "一点", "一下", "这种", "那种", "这种",
        "哪些", "哪个", "哪些",
    })

    # 英文停用词 — 过滤提问常见虚词
    _EN_STOPWORDS = frozenset({
        "what", "how", "why", "when", "where", "who", "which",
        "is", "are", "was", "were", "be", "been", "being",
        "the", "a", "an", "and", "or", "but", "of", "in", "on", "at",
        "to", "for", "with", "by", "from", "as", "that", "this", "these", "those",
        "difference", "between", "vs", "versus", "and", "or",
        "does", "do", "did", "can", "could", "should", "would",
        "tell", "explain", "describe", "compare",
    })

    def __init__(self, graph):
        self.graph = graph
        # 预编译技术术语匹配正则（最长匹配优先）
        # 按长度降序排列，确保 "Kubernetes" 优先于 "Kube"
        self._tech_term_pattern = self._build_tech_term_pattern()

    def _build_tech_term_pattern(self):
        """构建技术术语匹配正则（最长匹配优先）"""
        # 收集所有别名+规范名，按长度降序
        all_terms = set()
        for canonical, aliases in self._TECH_TERM_ALIASES.items():
            all_terms.add(canonical)
            all_terms.update(aliases)
        # 转义并按长度降序拼接
        sorted_terms = sorted(all_terms, key=len, reverse=True)
        escaped = [re.escape(t) for t in sorted_terms]
        # 不区分大小写匹配，词边界用非字母断言
        pattern = r'(?<![a-zA-Z])(?:' + '|'.join(escaped) + r')(?![a-zA-Z])'
        return re.compile(pattern, re.IGNORECASE)

    def decompose(self, query: str, max_depth: int = 2) -> dict:
        """分解用户问题

        Returns:
            {
                "topic": "Multi-Agent",
                "matched_nodes": [GraphNode, ...],
                "sub_topics": [{"node": GraphNode, "relation": "has_part"}, ...],
                "prerequisites": [GraphNode, ...],
                "related": [GraphNode, ...],
                "confidence": 0.85
            }
        """
        # 1. 关键词提取
        keywords = self._extract_keywords(query)

        # 2. Graph 节点匹配
        matched = []
        for kw in keywords:
            nodes = self.graph.search_by_name(kw, top_k=3)
            matched.extend(nodes)

        # 去重
        seen = set()
        unique = []
        for n in matched:
            if n.id not in seen:
                seen.add(n.id)
                unique.append(n)

        if not unique:
            return {"topic": query, "matched_nodes": [], "sub_topics": [],
                    "prerequisites": [], "related": [], "confidence": 0.0}

        # 3. 邻居扩展（has_part）
        sub_topics = []
        for node in unique[:3]:
            for child in self.graph.get_children(node.id, "has_part"):
                sub_topics.append({"node": child, "relation": "has_part",
                                   "parent": node.name})

        # 4. 前置知识
        prerequisites = []
        for node in unique[:3]:
            prerequisites.extend(self.graph.get_prerequisites(node.id))

        # 5. 关联知识
        related = []
        for node in unique[:3]:
            neighbors = self.graph.get_neighbors(node.id, "related_to", depth=1)
            related.extend(neighbors[:5])

        confidence = min(0.95, 0.5 + len(unique) * 0.15)

        return {
            "topic": unique[0].name if unique else query,
            "matched_nodes": unique,
            "sub_topics": sub_topics,
            "prerequisites": prerequisites,
            "related": related,
            "confidence": round(confidence, 2)
        }

    def _extract_keywords(self, query: str) -> List[str]:
        """关键词提取（规则，零 LLM）

        V2.2 (2026-07-30) 升级:
        1. 技术术语词典优先匹配（K8s→Kubernetes、ClusterIP 整词识别）
        2. 同义词归一化（K8s/Kube → Kubernetes，统一指向同一 Skill 节点）
        3. 中文停用词过滤（去除「什么/区别/中/和」等提问噪声）
        4. 英文停用词过滤（去除 what/how/difference/between 等）
        5. 保留原有英文专有名词 + 驼峰命名 + 中文 2-3 字滑动窗口

        注意: Python 3.x 中 \\b 对中文字符不生效，
        使用 (?<![a-zA-Z]) 和 (?![a-zA-Z]) 替代。
        """
        keywords = []
        normalized = set()  # 归一化后的关键词集合（用于去重）

        # ============================================================
        # Step 1: 技术术语词典匹配（最长匹配优先）+ 同义词归一化
        # ============================================================
        for m in self._tech_term_pattern.finditer(query):
            matched_term = m.group(0)
            canonical = self._normalize_to_canonical(matched_term)
            if canonical:
                keywords.append(canonical)
                normalized.add(canonical.lower())
                # 同时保留原始匹配形式（如用户写 "K8s" 也加入，便于精确节点匹配）
                normalized.add(matched_term.lower())

        # ============================================================
        # Step 2: 英文专有名词 + 驼峰命名（保留原逻辑，补充停用词过滤）
        # ============================================================
        # 英文专有名词（大写开头，前后不能是英文字母）
        # 放宽: 允许中间有大写字母（如 ClusterIP、NodePort、FastAPI）
        en_propers = re.findall(r'(?<![a-zA-Z])[A-Z][a-zA-Z]+(?![a-zA-Z])', query)
        for term in en_propers:
            if term.lower() not in self._EN_STOPWORDS and term.lower() not in normalized:
                keywords.append(term)
                normalized.add(term.lower())

        # 驼峰命名（如 dataSource、skillGraph）
        camel_cases = re.findall(r'(?<![a-zA-Z])[a-z]+(?:[A-Z][a-z]+)+(?![a-zA-Z])', query)
        for term in camel_cases:
            if term.lower() not in self._EN_STOPWORDS and term.lower() not in normalized:
                keywords.append(term)
                normalized.add(term.lower())

        # 英文全大写缩略词（LLM、RAG、CNN、K8S 等，2-6 字母）
        acronyms = re.findall(r'(?<![a-zA-Z])[A-Z]{2,6}(?![a-zA-Z])', query)
        for term in acronyms:
            canonical = self._normalize_to_canonical(term)
            if canonical:
                if canonical.lower() not in normalized:
                    keywords.append(canonical)
                    normalized.add(canonical.lower())
            elif term.lower() not in self._EN_STOPWORDS and term.lower() not in normalized:
                keywords.append(term)
                normalized.add(term.lower())

        # ============================================================
        # Step 3: 中文 2-3 字滑动窗口（停用词过滤）
        # ============================================================
        # 先切出连续中文字符段，再从每段中提取所有 2-3 字子串
        chinese_segments = re.findall(r'[\u4e00-\u9fff]+', query)
        for seg in chinese_segments:
            # 2 字词
            for i in range(len(seg) - 1):
                sub = seg[i:i + 2]
                if sub not in self._CN_STOPWORDS and sub.lower() not in normalized:
                    keywords.append(sub)
                    normalized.add(sub.lower())
            # 3 字词
            for i in range(len(seg) - 2):
                sub = seg[i:i + 3]
                if sub not in self._CN_STOPWORDS and sub.lower() not in normalized:
                    keywords.append(sub)
                    normalized.add(sub.lower())

        return keywords

    def _normalize_to_canonical(self, term: str) -> str:
        """将术语别名归一化为规范名

        例如: "k8s" → "Kubernetes", "kube" → "Kubernetes"
        返回规范名；若不是已知别名则返回空字符串。
        """
        term_lower = term.lower()
        for canonical, aliases in self._TECH_TERM_ALIASES.items():
            if canonical.lower() == term_lower:
                return canonical
            if term_lower in [a.lower() for a in aliases]:
                return canonical
        return ""
