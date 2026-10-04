"""全面健壮性扩展：为所有 concept 节点生成同义词/口语/英文词

V2.4 (2026-07-30) — 一次性脚本，生成后写回 skill_graph.yaml

三层生成策略:
1. 领域词典精确匹配（最高质量，覆盖技术术语）
2. 规则变体生成（通用兜底：中英互译 + 口语化）
3. 噪声节点识别（跳过时间/代码变量/碎片化内容）

每个节点目标: 至少 2-3 个别名（含 1 个口语化 + 1 个英文）

运行方式:
    cd d:\AgentMatrix\backend
    python scripts\generate_aliases_full.py
"""
import os
import re
import sys
import shutil
from pathlib import Path

# ============================================================
# Layer 1: 领域同义词映射表（大幅扩充）
# ============================================================
# 格式: {规范名(小写,去空格): [别名1, 别名2, ...]}
# 每个条目尽量包含: 英文全称/缩写 + 中文翻译 + 口语化变体
DOMAIN_SYNONYMS = {
    # ===== AI / ML 基础 =====
    # V2.5 修复: transformer 去掉"变压器模型"（字面翻译错误，AI语境下不成立）
    "transformer": ["Transformer模型", "Transformer架构", "Transformer网络"],
    "attention": ["注意力机制", "Attention机制", "attention"],
    "multihead": ["多头注意力", "Multi-Head Attention", "MultiHead注意力"],
    "llm": ["大语言模型", "大模型", "Large Language Model", "LLM模型"],
    "neuralnetwork": ["神经网络", "Neural Net", "NN", "神经元网络"],
    "embedding": ["嵌入", "嵌入向量", "向量化", "词嵌入", "Embedded Vector"],
    # V2.5 修复: ANN 在本项目语境是"近似最近邻"（RAG embedding 域），不是"人工神经网络"
    "ann": ["近似最近邻", "Approximate Nearest Neighbor", "ANN搜索"],
    "agent": ["智能体", "AI Agent", "代理"],
    "memory": ["记忆", "内存", "上下文记忆", "Context Memory"],

    # ===== AI / 训练技术 =====
    "lora": ["Low-Rank Adaptation", "低秩适配", "LoRA微调"],
    "finetuning": ["Fine-tuning", "微调", "Finetuning", "Fine tuning", "fine-tuning"],
    "微调": ["Fine-tuning", "微调", "Finetuning"],
    "few-shotprompting": ["少样本提示", "Few-shot", "少样本学习"],
    "chain-of-thought": ["CoT", "思维链", "Chain of Thought", "推理链"],
    "functioncalling": ["函数调用", "Function Call", "工具调用", "Tool Calling"],
    "promptengineering": ["提示工程", "Prompt工程", "Prompt Engineering"],

    # ===== AI / RAG =====
    "chunking": ["分块", "文本分块", "Text Chunking", "切块"],
    "rag": ["检索增强生成", "Retrieval Augmented Generation", "RAG技术"],
    "bm25算法": ["BM25", "Okapi BM25", "Best Match 25", "BM25算法", "BM25 算法"],
    "tf-idf评分机制": ["TF-IDF", "TFIDF", "词频-逆文档频率", "TF-IDF 评分", "TF-IDF评分机制"],
    "倒排索引": ["Inverted Index", "反向索引", "倒排表"],
    "关键参数": ["Key Parameter", "核心参数", "重要参数"],

    # ===== AI / Agent =====
    "mcp": ["Model Context Protocol", "模型上下文协议", "MCP协议"],
    "mcpserver": ["MCP服务器", "MCP Server", "Model Context Protocol Server"],
    "multi-agent": ["多智能体", "多Agent", "多agent", "Multi Agent", "Multi-Agent系统"],
    "multi-agentsystem": ["多智能体系统", "Multi-Agent System", "MAS", "多代理系统"],

    # ===== Kubernetes / 容器 =====
    "kubernetes": ["K8s", "Kube", "k8s"],
    "docker": ["Docker容器", "Docker 容器", "容器引擎"],
    "clusterip": ["Cluster IP", "集群IP", "集群内部IP"],
    "nodeport": ["Node Port", "节点端口", "Node Port Service"],
    "loadbalancer": ["Load Balancer", "负载均衡器", "LB Service"],
    "deployment": ["部署", "Deployment控制器", "K8s Deployment"],
    "service": ["服务", "K8s Service", "SVC", "Kubernetes Service"],
    "ingress": ["入口控制器", "Ingress Controller", "K8s Ingress"],
    "pod": ["容器组", "K8s Pod", "Kubernetes Pod"],
    "configmap": ["Config Map", "配置映射", "K8s ConfigMap"],
    "helm": ["Helm包管理", "Helm Chart", "K8s Helm"],
    "滚动更新": ["Rolling Update", "滚动升级", "Rolling Deployment"],
    "rollingupdate": ["滚动更新", "Rolling Update", "滚动升级"],
    "动态表（dynamictable）": ["Dynamic Table", "动态表", "动态表格"],
    "流id机制": ["Stream ID", "流标识符", "Stream ID Mechanism"],
    "头部压缩（hpack）": ["HPACK", "Header Compression", "头部压缩"],

    # ===== 加密 / 量子 =====
    "aes": ["Advanced Encryption Standard", "高级加密标准", "AES加密"],
    "cryptoagility": ["密码敏捷性", "Cryptographic Agility", "加密敏捷性"],
    "kyber": ["Kyber算法", "CRYSTALS-Kyber", "后量子加密Kyber"],
    "grover算法": ["Grover's Algorithm", "Grover搜索算法", "量子搜索算法"],
    "shor算法": ["Shor's Algorithm", "Shor因式分解", "量子因式分解"],
    "共享安全": ["Shared Security", "共享安全性", "共同安全"],

    # ===== 编译器 =====
    "ast": ["Abstract Syntax Tree", "抽象语法树", "语法树"],
    "llvm": ["LLVM编译器框架", "Low Level Virtual Machine", "LLVM IR"],

    # ===== 数据库 =====
    "mysql": ["MySQL数据库", "MySQL 数据库", "My SQL"],
    "postgresql": ["Postgres", "PG数据库", "PostgreSQL数据库"],
    "sqlite": ["SQLite数据库", "轻量级数据库", "嵌入式数据库"],
    "redis": ["Redis缓存", "Redis 缓存", "内存数据库"],
    "mongodb": ["Mongo", "MongoDB数据库", "文档数据库"],
    "elasticsearch": ["ES", "Elastic", "搜索引擎"],

    # ===== 框架与工具 =====
    "react": ["ReactJS", "React.js", "React框架"],
    "vue": ["VueJS", "Vue.js", "Vue框架"],
    "next.js": ["NextJS", "Next JS", "Next框架"],
    "fastapi": ["Fast API", "FastAPI框架", "Fast API框架"],
    "flask": ["Flask框架", "Flask Web框架"],
    "django": ["Django框架", "Django Web框架"],
    "pytorch": ["Torch", "PyTorch框架", "Py Torch"],
    "tensorflow": ["TF", "TensorFlow框架", "Tensor Flow"],
    "ollama": ["Ollama本地模型", "Ollama 本地模型"],
    "langchain": ["LangChain框架", "Lang Chain"],
    "javascript": ["JS", "Java Script", "JS语言"],
    "python编程": ["Python", "Python编程语言", "Python开发"],
    "rabbitmq": ["RabbitMQ消息队列", "RabbitMQ 消息队列", "消息队列"],

    # ===== 云计算 =====
    "aws": ["Amazon Web Services", "亚马逊云", "AWS云"],
    "gcp": ["Google Cloud", "Google Cloud Platform", "谷歌云"],
    "azure": ["Microsoft Azure", "微软云", "Azure云"],
    "ec2": ["Elastic Compute Cloud", "AWS EC2", "亚马逊EC2"],
    "s3": ["Amazon S3", "S3存储", "AWS S3", "Simple Storage Service"],

    # ===== 网络与协议 =====
    "http": ["HTTP协议", "超文本传输协议", "Hypertext Transfer Protocol"],
    "https": ["HTTPS协议", "HTTP over SSL", "安全HTTP"],
    "grpc": ["gRPC框架", "Google RPC", "gRPC协议"],
    "websocket": ["WS", "WebSocket协议", "Web Socket"],
    "rest": ["RESTful", "REST API", "RESTful API", "表述性状态转移"],
    "graphql": ["GraphQL查询语言", "Graph QL", "GraphQL API"],
    "tcp": ["TCP协议", "传输控制协议", "Transmission Control Protocol"],
    "udp": ["UDP协议", "用户数据报协议", "User Datagram Protocol"],
    "nginx": ["Nginx服务器", "Nginx Web服务器", "Nginx反向代理"],

    # ===== 通用技术概念 =====
    "api": ["API接口", "应用程序接口", "Application Programming Interface"],
    "ci/cd": ["CICD", "CI CD", "持续集成持续部署", "Continuous Integration/Continuous Deployment"],
    "git": ["Git版本控制", "Git VCS", "版本控制工具"],
    "linux": ["Linux系统", "Linux操作系统", "GNU/Linux"],
    "图灵测试": ["Turing Test", "图灵检验", "Turing Test"],
    "元组": ["Tuple", "元组数据", "Tuple"],
    "列表": ["List", "列表数据", "Python List"],
    "内存占用": ["Memory Usage", "内存消耗", "Memory Footprint"],
    "数据封装与保护": ["Data Encapsulation", "数据封装", "Data Protection"],

    # ===== Business / 商业 =====
    "roi": ["Return on Investment", "投资回报率", "投资回报"],
    "swot": ["SWOT分析", "SWOT", "态势分析法"],
    "swot分析": ["SWOT", "SWOT Analysis", "态势分析"],
    "价值主张": ["Value Proposition", "价值主张", "Value Prop"],
    "商业方案": ["Business Plan", "商业计划", "Business Proposal"],
    "商业模型": ["Business Model", "商业模式", "Business Model"],
    "商业策划": ["Business Planning", "商业规划", "Business Strategy"],
    "市场调研": ["Market Research", "市场调查", "Market Survey"],
    "人力需求": ["HR Requirements", "人力资源需求", "Staffing Needs"],
    "人员": ["Personnel", "人员配置", "Staff"],
    "关键指标": ["Key Metrics", "关键KPI", "Key Performance Indicators"],
    "准确性": ["Accuracy", "精确度", "Precision"],
    "效率": ["Efficiency", "效能", "Productivity"],
    "优点": ["Advantages", "优势", "Pros"],
    "成本分析": ["Cost Analysis", "费用分析", "Cost Breakdown"],
    "成本对比": ["Cost Comparison", "费用对比", "Price Comparison"],
    "成本控制": ["Cost Control", "费用控制", "Budget Control"],
    "成本效益评估": ["Cost-Benefit Analysis", "成本效益分析", "CBA"],
    "成本风险": ["Cost Risk", "费用风险", "Financial Risk"],
    "技术方案": ["Technical Solution", "技术解决方案", "Tech Plan"],
    "技术选型": ["Technology Selection", "技术选择", "Tech Stack Selection"],
    "技术风险": ["Technical Risk", "技术风险分析", "Tech Risk"],
    "实施步骤": ["Implementation Steps", "实施流程", "Execution Steps"],
    "实施风险": ["Implementation Risk", "执行风险", "Execution Risk"],
    "效果不确定性": ["Effect Uncertainty", "效果风险", "Outcome Uncertainty"],
    "应用场景匹配": ["Use Case Matching", "场景匹配", "Application Scenario"],
    "优化迭代阶段": ["Optimization Iteration", "优化阶段", "Iterative Optimization"],
    "外部知识库建设": ["External Knowledge Base", "外部知识库", "External KB"],
    "技术研发与实施": ["R&D Implementation", "技术研发", "Tech R&D"],
    "数据准备与标注": ["Data Preparation", "数据标注", "Data Labeling"],

    # ===== Daily / 日常 =====
    "业绩总结": ["Performance Summary", "业绩回顾", "Work Summary"],
    "项目回顾": ["Project Review", "项目总结", "Project Retrospective"],
    "实习证明": ["Internship Certificate", "实习证书", "Internship Proof"],
    "解决方案": ["Solution", "问题解决", "Problem Solving"],
    "预期成果": ["Expected Outcome", "预期结果", "Expected Results"],
    "毕业时间": ["Graduation Date", "毕业日期", "Graduation Time"],
    "颁发单位": ["Issuing Authority", "颁发机构", "Issuer"],
    "姓名": ["Name", "名字", "Full Name"],
    "图片": ["Image", "图像", "Picture"],
    "周六周日": ["Weekend", "周末", "Sat & Sun"],

    # ===== Creative / 创意 =====
    "保质期": ["Shelf Life", "保质期限", "Expiration Date"],
    "净含量": ["Net Weight", "净重", "Net Content"],
    "健康提示": ["Health Tip", "健康提醒", "Health Warning"],
    "品尝体验": ["Tasting Experience", "品鉴体验", "Taste Test"],
    "住宿费用": ["Accommodation Cost", "住宿费", "Lodging Cost"],
    "实际支出": ["Actual Expenditure", "实际花费", "Actual Cost"],
    "总预算": ["Total Budget", "预算总额", "Overall Budget"],
    "总计": ["Total", "合计", "Sum"],
    "地址": ["Address", "地址信息", "Location"],
    "日期": ["Date", "日期时间", "Date Time"],
    "动态数据管理": ["Dynamic Data Management", "动态数据", "Dynamic Data"],
    "具体解释": ["Detailed Explanation", "详细解释", "Specific Explanation"],

    # ===== 时间类（口语化变体） =====
    "早上": ["Morning", "早晨", "AM"],
    "上午": ["Morning", "AM", "Forenoon"],
    "中午": ["Noon", "Midday", "正午"],
    "下午": ["Afternoon", "PM", "午后"],
    "傍晚": ["Evening", "黄昏", "Dusk"],
    "晚上": ["Night", "晚间", "Evening Time"],

    # ===== V2.4 补充：完整术语映射（避免碎片化翻译） =====
    "检索增强生成": ["RAG", "Retrieval Augmented Generation", "RAG技术"],
    "混合检索": ["Hybrid Retrieval", "混合搜索", "Hybrid Search"],
    "训练时间": ["Training Time", "训练耗时", "Training Duration"],
    "索引系统": ["Index System", "索引架构", "Indexing System"],
    "服务器推送": ["Server Push", "HTTP/2 Server Push", "推送机制"],
    "多头注意力机制": ["Multi-Head Attention", "多头注意力", "MultiHead Attention"],
    "注意力机制": ["Attention Mechanism", "Attention", "注意力"],
    "容错机制": ["Fault Tolerance", "容错", "Fault Tolerant"],
    "跨注意力机制": ["Cross Attention", "跨注意力", "Cross-Attention"],
    "评分机制": ["Scoring Mechanism", "评分系统", "Scoring System"],
    "查询": ["Query", "查询语句", "Search Query"],
    "向量": ["Vector", "向量数据", "Vector Data"],
    "准确性": ["Accuracy", "精确度", "Precision"],

    # ============================================================
    # V2.5 补充：覆盖70个真实无别名节点（2026-07-30）
    # ============================================================
    # --- AI / RAG / Attention 细分 ---
    "分数": ["Score", "评分", "Relevance Score"],
    "分词器": ["Tokenizer", "分词工具", "Token切分器"],
    "单头注意力": ["Single-Head Attention", "单头注意", "Single Head Attention"],
    "自注意力": ["Self-Attention", "自注意", "Self Attention"],
    "输入序列": ["Input Sequence", "输入串", "Input Token Sequence"],
    "输出序列": ["Output Sequence", "输出串", "Output Token Sequence"],
    "应用场合": ["Use Case", "应用场景", "Application Scenario"],
    "计算复杂度": ["Computational Complexity", "计算复杂性", "Algorithm Complexity"],
    "通信协议": ["Communication Protocol", "通讯协议", "Protocol"],
    "预算估算": ["Budget Estimation", "预算评估", "Cost Estimation"],
    "词条": ["Token", "词项", "Term"],
    "语义分块": ["Semantic Chunking", "语义切块", "Semantic Segmentation"],
    "重叠窗口": ["Overlapping Window", "重叠分块", "Sliding Window"],
    "长期记忆": ["Long-term Memory", "长期存储", "Long Term Memory"],
    "短期记忆": ["Short-term Memory", "短期存储", "Short Term Memory"],
    "记忆压缩": ["Memory Compression", "记忆精简", "Context Compression"],
    "性能对比": ["Performance Comparison", "性能比较", "Performance Benchmark"],
    "性能比较": ["Performance Comparison", "性能对比", "Performance Benchmark"],

    # --- AI / LLM 通用 ---
    "定制化": ["Customization", "个性化定制", "Customization"],
    "数据集": ["Dataset", "数据集合", "Data Set"],
    "泛化能力": ["Generalization", "泛化性", "Generalization Ability"],
    "灵活性": ["Flexibility", "灵活度", "Adaptability"],
    "深度学习": ["Deep Learning", "DL", "深度神经网络"],

    # --- 加密 / 量子 ---
    "后量子密码学": ["Post-Quantum Cryptography", "PQC", "抗量子密码"],
    "哈希函数": ["Hash Function", "哈希算法", "散列函数"],

    # --- 网络 / OS ---
    "可观察性与控制": ["Observability and Control", "可观测性控制", "可观测性与可控性"],
    "并行执行": ["Parallel Execution", "并行处理", "Concurrent Execution"],
    "弹性伸缩": ["Auto Scaling", "弹性扩展", "Elastic Scaling"],
    "端口": ["Port", "端口号", "Network Port"],
    "虚拟内存": ["Virtual Memory", "虚拟存储", "VM"],
    "进程调度": ["Process Scheduling", "进程调度算法", "CPU Scheduling"],
    "负载均衡": ["Load Balancing", "LB", "负载平衡"],
    "队头阻塞问题": ["Head-of-Line Blocking", "HOL Blocking", "队头阻塞"],
    "定义": ["Definition", "定义说明", "概念定义"],

    # --- Business / 商业 ---
    "方案实施": ["Solution Implementation", "方案执行", "Implementation"],
    "时间风险": ["Time Risk", "时间风险分析", "Schedule Risk"],
    "架构设计": ["Architecture Design", "架构规划", "System Architecture"],
    "测试验证": ["Test Verification", "测试与验证", "Validation"],
    "物资": ["Materials", "物资资源", "Supplies"],
    "用户满意度": ["User Satisfaction", "客户满意度", "Customer Satisfaction"],
    "相关性": ["Relevance", "关联性", "Correlation"],
    "衡量标准": ["Measurement Standard", "评估标准", "Criteria"],
    "财务风险": ["Financial Risk", "资金风险", "Finance Risk"],
    "资源规划": ["Resource Planning", "资源计划", "Resource Allocation"],
    "资源配置": ["Resource Allocation", "资源分配", "Resource Configuration"],
    "迭代优化": ["Iterative Optimization", "迭代改进", "Iteration"],
    "项目目标": ["Project Goal", "项目目的", "Project Objective"],
    "项目背景": ["Project Background", "项目概况", "Project Context"],

    # --- Creative / 创意（美食、地名、旅行等） ---
    "小笼包": ["Xiaolongbao", "小笼馒头", "Soup Dumpling"],
    "松鹤楼": ["Songhelou", "松鹤楼饭店", "Songhe Lou Restaurant"],
    "松鼠肉圆": ["Squirrel Meatball", "松鼠形状肉圆", "Squirrel-shaped Meatball"],
    "珠穆朗玛峰": ["Mount Everest", "珠峰", "Everest"],
    "生煎包": ["Shengjianbao", "生煎馒头", "Pan-fried Bun"],
    "示例应用": ["Example Application", "示例程序", "Sample App"],
    "策划人": ["Planner", "策划者", "Event Planner"],
    "糯米红枣": ["Glutinous Rice with Dates", "红枣糯米", "Sticky Rice Dates"],
    "红烧肉": ["Braised Pork", "红烧猪肉", "Red Braised Pork"],
    "纪念品": ["Souvenir", "纪念物", "Gift"],
    "苏州工业园区": ["Suzhou Industrial Park", "SIP", "苏州园区"],
    "苏州汤包": ["Suzhou Soup Bun", "苏州小笼包", "Suzhou Tangbao"],
    "蟹壳黄": ["Crab Shell Pastry", "蟹壳黄饼", "Xiekehuan"],
    "行前准备": ["Pre-trip Preparation", "出行准备", "Trip Preparation"],
    "访问速度": ["Access Speed", "访问速率", "Access Time"],
    "豆汁": ["Douzhi", "豆汁儿", "Beijing Douzhi"],
    "返程": ["Return Trip", "回程", "Return Journey"],
    "配料": ["Ingredients", "原料", "Recipe Ingredients"],
    "酒店地址": ["Hotel Address", "酒店位置", "Hotel Location"],
    "门票": ["Ticket", "门票票务", "Admission Ticket"],
    "阳澄湖大闸蟹": ["Yangcheng Lake Hairy Crab", "阳澄湖螃蟹", "Hairy Crab"],
    "预订酒店": ["Hotel Booking", "预定酒店", "Hotel Reservation"],

    # --- V2.5 追加：补全只有1个别名的节点 ---
    "orchestration": ["编排", "Agent编排", "Multi-Agent Orchestration"],
    "rerank": ["重排序", "重排", "Re-ranking"],
    "sentence-bert": ["SBERT", "句向量模型", "Sentence BERT"],
    "tcp/ip": ["传输控制协议/网际协议", "TCP IP协议", "TCP/IP协议族"],
    "需求分析": ["Requirement Analysis", "需求评估", "Requirements Analysis"],
}


# ============================================================
# Layer 2: 通用中英技术对照表（兜底翻译）
# ============================================================
# 当节点名不在 DOMAIN_SYNONYMS 时，用此表做基础翻译
EN_CN_TECH_DICT = {
    # AI
    "model": "模型", "network": "网络", "algorithm": "算法",
    "training": "训练", "inference": "推理", "generation": "生成",
    "retrieval": "检索", "search": "搜索", "query": "查询",
    "vector": "向量", "matrix": "矩阵", "tensor": "张量",
    "encoding": "编码", "decoding": "解码", "parsing": "解析",
    # Web
    "server": "服务器", "client": "客户端", "request": "请求",
    "response": "响应", "session": "会话", "cookie": "Cookie",
    # Data
    "database": "数据库", "table": "表", "record": "记录",
    "index": "索引", "cache": "缓存", "queue": "队列",
    # Security
    "encryption": "加密", "decryption": "解密", "key": "密钥",
    "certificate": "证书", "signature": "签名",
}

CN_EN_TECH_DICT = {v: k for k, v in EN_CN_TECH_DICT.items()}


# ============================================================
# Layer 3: 噪声节点识别
# ============================================================
def is_noise_node(node) -> bool:
    """识别噪声节点（不应生成别名）

    噪声类型:
    1. 时间点: "上午10:30", "下午12:00"
    2. 代码变量: "end_time", "nested_tuple"
    3. 纯数字/符号
    4. Markdown 残留: "**特色小吃**"
    5. 碎片化短语: "球变暖的主要原因", "类型的元素"（非完整名词）
    """
    name = node.name or ""

    # Markdown 残留（含 ** 或 __ 等）
    if re.search(r'\*\*|__', name):
        return True

    # 时间点（HH:MM 格式）
    if re.search(r'\d{1,2}:\d{2}', name):
        return True

    # 纯代码变量（snake_case 且非已知技术术语）
    if re.match(r'^[a-z][a-z_]*$', name) and name.lower() not in {
        'embedding', 'memory', 'agent', 'attention', 'deployment',
        'service', 'ingress', 'pod', 'configmap', 'helm',
    }:
        # 进一步检查：若 description 含 "自动提取" 或明显是代码片段
        desc = (node.description or "").lower()
        if '自动提取' in desc or '代码' in desc or '变量' in desc:
            return True
        # 短 snake_case 名（< 10 字符）且无领域信息 → 可能是代码变量
        if len(name) < 10 and node.domain in ('creative', 'daily') and not node.metadata.get('audited'):
            return True

    # 碎片化短语（以"的"开头或包含"的"且长度 < 10，非完整术语）
    # 如 "球变暖的主要原因"、"类型的元素"
    if len(name) < 10 and "的" in name and not name.endswith("的"):
        # 检查是否是已知术语（在 DOMAIN_SYNONYMS 中）
        name_nospace = re.sub(r'\s+', '', name.lower())
        is_known = False
        for key in DOMAIN_SYNONYMS:
            if re.sub(r'\s+', '', key.lower()) == name_nospace:
                is_known = True
                break
        if not is_known:
            return True

    return False


def generate_aliases_for_node(node) -> list:
    """为单个节点生成 aliases 列表

    返回空列表表示该节点是噪声，应跳过
    """
    if is_noise_node(node):
        return []

    aliases = []
    name = node.name or ""
    name_lower = name.lower()
    name_nospace = re.sub(r'\s+', '', name_lower)

    # ============================================================
    # Layer 1: 领域词典精确匹配
    # ============================================================
    for key, syns in DOMAIN_SYNONYMS.items():
        key_nospace = re.sub(r'\s+', '', key.lower())
        # 精确匹配（去空格后）
        if name_nospace == key_nospace:
            for s in syns:
                if s.lower() != name_lower:
                    aliases.append(s)
            break
        # 部分匹配：仅当 key 长度 >= 4 且节点名以 key 开头或以 key 结尾时才匹配
        if key_nospace and len(key_nospace) >= 4:
            if name_nospace.startswith(key_nospace) or name_nospace.endswith(key_nospace):
                for s in syns:
                    if s.lower() != name_lower:
                        aliases.append(s)
                break

    # 如果 Layer 1 已匹配，直接返回（去重 + 限 6 个）
    if aliases:
        return _dedupe_aliases(aliases, name)

    # ============================================================
    # Layer 2: 规则变体生成（通用兜底）
    # ============================================================
    aliases = _generate_rule_based_aliases(name, node)

    return _dedupe_aliases(aliases, name)


def _generate_rule_based_aliases(name: str, node) -> list:
    """基于规则生成别名（兜底）"""
    aliases = []

    # 判断命名类型
    is_pure_english = bool(re.match(r'^[A-Za-z][A-Za-z\s\-/.]*$', name))
    is_pure_chinese = bool(re.match(r'^[\u4e00-\u9fff\s（）()、，·\-]+$', name))
    is_mixed = not is_pure_english and not is_pure_chinese

    if is_pure_english:
        aliases.extend(_aliases_for_english_name(name, node))
    elif is_pure_chinese:
        aliases.extend(_aliases_for_chinese_name(name, node))
    else:
        # 中英混合：拆分中英部分
        aliases.extend(_aliases_for_mixed_name(name, node))

    return aliases


def _aliases_for_english_name(name: str, node) -> list:
    """为纯英文名生成别名"""
    aliases = []
    name_lower = name.lower()

    # 1. 从通用技术词典查找中文翻译
    for en, cn in EN_CN_TECH_DICT.items():
        if en in name_lower:
            if cn not in aliases and cn != name:
                aliases.append(cn)
            break

    # 2. 加口语化后缀（中文技术语境）
    # 根据领域加不同后缀
    domain = (node.domain or "").lower()
    if "ai" in domain or "llm" in domain:
        suffixes = ["模型", "技术", "方法"]
    elif "crypto" in domain:
        suffixes = ["算法", "加密", "协议"]
    elif "network" in domain:
        suffixes = ["服务", "协议", "机制"]
    elif "compiler" in domain:
        suffixes = ["编译", "技术", "结构"]
    else:
        suffixes = ["技术", "机制", "方法"]

    for suffix in suffixes[:1]:  # 只加 1 个后缀
        candidate = f"{name}{suffix}"
        if candidate != name:
            aliases.append(candidate)

    # 3. 如果是缩写（全大写，2-6 字母），加常见展开模式
    if re.match(r'^[A-Z]{2,6}$', name):
        # 缩写通常有全称，但我们不知道具体全称，加"缩写"标记
        aliases.append(f"{name}缩写")
        # 加中文通用翻译
        aliases.append(f"{name}技术")

    # 4. 去空格变体
    if " " in name:
        nospace = name.replace(" ", "")
        if nospace != name:
            aliases.append(nospace)

    return aliases


def _aliases_for_chinese_name(name: str, node) -> list:
    """为纯中文名生成别名

    V2.4 修复: 移除碎片化翻译和粗暴的"机制→Mechanism"替换
      - 旧逻辑: "注意力机制" → "注意力Mechanism"（中英混杂怪词）
      - 新逻辑: 只做安全的变体（简化、去"的"、同义后缀），不做碎片化翻译
      - 完整术语翻译由 DOMAIN_SYNONYMS 词典负责
    """
    aliases = []

    # 1. 口语化简化（去掉"的"、简化长名）
    if "的" in name:
        simplified = name.replace("的", "")
        if simplified != name and len(simplified) >= 2:
            aliases.append(simplified)

    # 2. 同义后缀替换（安全的中文内部变体，不跨语言）
    if len(name) >= 4 and name.endswith("阶段"):
        simplified = name.replace("阶段", "期")
        if simplified != name:
            aliases.append(simplified)
    if len(name) >= 4 and name.endswith("评估"):
        simplified = name.replace("评估", "分析")
        if simplified != name:
            aliases.append(simplified)
    if len(name) >= 4 and name.endswith("分析"):
        simplified = name.replace("分析", "评估")
        if simplified != name:
            aliases.append(simplified)

    # 3. 对于以"机制"结尾的词，加去"机制"的简称
    if len(name) >= 4 and name.endswith("机制"):
        simplified = name.replace("机制", "")
        if len(simplified) >= 2:
            aliases.append(simplified)

    # 4. 对于以"算法"结尾的词，加去"算法"的简称
    if len(name) >= 4 and name.endswith("算法"):
        simplified = name.replace("算法", "")
        if len(simplified) >= 2:
            aliases.append(simplified)

    return aliases


def _aliases_for_mixed_name(name: str, node) -> list:
    """为中英混合名生成别名"""
    aliases = []

    # 拆分中英部分
    chinese_parts = re.findall(r'[\u4e00-\u9fff]+', name)
    english_parts = re.findall(r'[A-Za-z][A-Za-z\s\-/.]*', name)

    # 各部分作为别名
    for part in chinese_parts:
        if part != name and len(part) >= 2:
            aliases.append(part)
    for part in english_parts:
        part = part.strip()
        if part and part != name and len(part) >= 2:
            aliases.append(part)

    # 去括号变体
    if '（' in name or '(' in name:
        no_paren = re.sub(r'[（(][^)）]*[)）]', '', name).strip()
        if no_paren and no_paren != name:
            aliases.append(no_paren)

    return aliases


def _dedupe_aliases(aliases: list, name: str) -> list:
    """去重 + 限制数量"""
    name_lower = name.lower()
    seen = {name_lower}
    unique = []
    for a in aliases:
        a = a.strip() if isinstance(a, str) else str(a)
        a_lower = a.lower()
        if a_lower not in seen and a:
            seen.add(a_lower)
            unique.append(a)
    return unique[:6]  # 限制最多 6 个


def _is_exact_dict_match(name: str) -> bool:
    """V2.5: 判断节点名是否在 DOMAIN_SYNONYMS 中精确匹配（去空格小写比较）

    用于决定是否强制覆盖现有别名（清除历史错误，如 transformer 的"变压器模型"）
    """
    if not name:
        return False
    name_nospace = re.sub(r'\s+', '', name.lower())
    for key in DOMAIN_SYNONYMS:
        if re.sub(r'\s+', '', key.lower()) == name_nospace:
            return True
    return False


def main():
    """主函数: 批量生成 aliases 并写回 yaml"""
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

    from core.graphs import get_skill_graph

    g = get_skill_graph()
    print(f"Total nodes: {len(g.nodes)}")

    # 找出所有 concept 节点
    concepts = [n for n in g.nodes.values() if n.node_type == "concept"]
    print(f"Concept nodes: {len(concepts)}")

    # 分类处理
    updated = 0
    overwritten = 0
    skipped_noise = 0
    no_change = 0
    noise_nodes = []

    for node in concepts:
        new_aliases = generate_aliases_for_node(node)

        if not new_aliases and is_noise_node(node):
            skipped_noise += 1
            noise_nodes.append(node)
            continue

        if new_aliases:
            # V2.5: 判断是否为 DOMAIN_SYNONYMS 精确匹配（用于覆盖错误别名）
            is_exact_dict_match = _is_exact_dict_match(node.name)

            if node.aliases and not is_exact_dict_match:
                # 已有 aliases 且非词典精确匹配 → 合并去重（保留手工别名）
                existing = {a.lower() for a in node.aliases}
                merged = list(node.aliases)
                for a in new_aliases:
                    if a.lower() not in existing:
                        merged.append(a)
                        existing.add(a.lower())
                if len(merged) > len(node.aliases):
                    node.aliases = merged[:6]
                    updated += 1
                    print(f"  + {node.name}: merged → {node.aliases}")
            elif node.aliases and is_exact_dict_match:
                # V2.5: 词典精确匹配 → 强制覆盖（清除历史错误别名，如 transformer/ann）
                if {a.lower() for a in node.aliases} != {a.lower() for a in new_aliases}:
                    node.aliases = new_aliases
                    overwritten += 1
                    print(f"  ! {node.name}: OVERWRITTEN → {node.aliases}")
                else:
                    no_change += 1
            else:
                node.aliases = new_aliases
                updated += 1
                print(f"  ✓ {node.name}: {new_aliases}")
        else:
            no_change += 1

    print(f"\n=== 统计 ===")
    print(f"Updated (merged/new): {updated}")
    print(f"Overwritten (dict exact match): {overwritten}")
    print(f"Skipped (noise): {skipped_noise}")
    print(f"No change: {no_change}")

    if noise_nodes:
        print(f"\n=== 噪声节点（建议清理）===")
        for n in noise_nodes:
            print(f"  {n.name} (domain={n.domain})")

    # 保存（V2.5: overwritten > 0 时也需要保存）
    if updated > 0 or overwritten > 0:
        yaml_path = backend_dir / "core" / "graphs" / "skill_graph.yaml"
        bak_path = yaml_path.with_suffix(f".yaml.bak_full_{os.getpid()}")
        shutil.copy2(yaml_path, bak_path)
        print(f"\nBackup saved: {bak_path}")

        g.save(str(yaml_path))
        print(f"Skill graph saved to: {yaml_path}")
    else:
        print(f"\n(no changes to save)")


if __name__ == "__main__":
    main()
