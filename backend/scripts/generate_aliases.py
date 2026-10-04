"""批量为已审计 concept 节点生成 aliases（同义词、口头语、代称、英文词）

V2.4 (2026-07-30) — 一次性脚本，生成后写回 skill_graph.yaml

策略（规则为主，零 LLM 调用）:
1. 领域同义词映射表（手工维护的高质量同义词）
2. 中英文对应（如 BM25 算法 → BM25, Best Match 25）
3. 常见缩写展开（如 K8s → Kubernetes）
4. 节点名变体（如去空格、加"算法"/"机制"后缀）

运行方式:
    cd d:\AgentMatrix\backend
    python scripts\generate_aliases.py
"""
import os
import re
import sys
import yaml
from pathlib import Path

# ============================================================
# 领域同义词映射表（手工维护）
# ============================================================
# 格式: {规范名(小写): [别名1, 别名2, ...]}
# 匹配时用节点 name 的小去掉空格后比对
DOMAIN_SYNONYMS = {
    # ===== AI / ML =====
    "bm25算法": ["BM25", "Okapi BM25", "Best Match 25", "BM25算法", "BM25 算法"],
    "tf-idf评分机制": ["TF-IDF", "TFIDF", "词频-逆文档频率", "TF-IDF 评分", "TF-IDF评分机制"],
    "transformer": ["Transformer模型", "变压器模型", "注意力网络"],
    "bert": ["BERT模型", "双向编码器表示", "Bidirectional Encoder Representations from Transformers"],
    "gpt": ["GPT模型", "生成式预训练", "Generative Pre-trained Transformer"],
    "llm": ["大语言模型", "大模型", "Large Language Model", "LLM模型"],
    "rag": ["检索增强生成", "Retrieval Augmented Generation", "RAG技术"],
    "embedding": ["嵌入", "嵌入向量", "向量化", "词嵌入"],
    "attention": ["注意力", "注意力机制", "Attention机制"],
    "cnn": ["卷积神经网络", "Convolutional Neural Network"],
    "rnn": ["循环神经网络", "Recurrent Neural Network"],
    "lstm": ["长短期记忆网络", "Long Short-Term Memory"],
    "reinforcementlearning": ["强化学习", "RL", "Reinforcement Learning"],
    "deeplearning": ["深度学习", "Deep Learning", "DL"],
    "promptengineering": ["提示工程", "Prompt工程", "Prompt Engineering"],
    "fine-tuning": ["微调", "Fine-tuning", "Finetuning", "Fine tuning"],
    "gan": ["生成对抗网络", "Generative Adversarial Network", "GAN网络"],
    "wgan": ["Wasserstein GAN", "Wasserstein生成对抗网络"],
    "multihead": ["多头注意力", "Multi-Head Attention", "MultiHead注意力"],
    "rabbitmq": ["RabbitMQ消息队列", "RabbitMQ 消息队列"],

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

    # ===== 数据库 =====
    "mysql": ["MySQL数据库", "MySQL 数据库", "My SQL"],
    "postgresql": ["Postgres", "PG数据库", "PostgreSQL数据库"],
    "sqlite": ["SQLite数据库", "轻量级数据库", "嵌入式数据库"],
    "redis": ["Redis缓存", "Redis 缓存", "内存数据库"],
    "mongodb": ["Mongo", "MongoDB数据库", "文档数据库"],
    "elasticsearch": ["ES", " elastic", "搜索引擎"],

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

    # ===== AgentMatrix 自身概念 =====
    "multi-agent": ["多智能体", "多Agent", "多agent", "Multi Agent", "Multi-Agent系统"],
    "skillgraph": ["技能图谱", "Skill Graph", "技能图"],
    "knowledgegraph": ["知识图谱", "Knowledge Graph", "KG"],
    "cognitivearchitecture": ["认知架构", "Cognitive Architecture", "认知体系"],

    # ===== 通用技术概念 =====
    "api": ["API接口", "应用程序接口", "Application Programming Interface"],
    "ci/cd": ["CICD", "CI CD", "持续集成持续部署", "Continuous Integration/Continuous Deployment"],
    "git": ["Git版本控制", "Git VCS", "版本控制工具"],
    "linux": ["Linux系统", "Linux操作系统", "GNU/Linux"],
}


def generate_aliases_for_node(node) -> list:
    """为单个节点生成 aliases 列表"""
    aliases = []
    name = node.name or ""
    name_lower = name.lower()
    name_nospace = re.sub(r'\s+', '', name_lower)

    # 1. 从领域同义词表查找
    for key, syns in DOMAIN_SYNONYMS.items():
        key_nospace = re.sub(r'\s+', '', key.lower())
        # 精确匹配（去空格后）
        if name_nospace == key_nospace:
            # 添加同义词，排除与 name 完全相同的
            for s in syns:
                if s.lower() != name_lower:
                    aliases.append(s)
            break
        # 部分匹配：仅当 key 长度 >= 4 且节点名以 key 开头或以 key 结尾时才匹配
        # （避免"评分机制"误匹配"tf-idf评分机制"——后者包含前者但不是同一概念）
        if key_nospace and len(key_nospace) >= 4:
            if name_nospace.startswith(key_nospace) or name_nospace.endswith(key_nospace):
                for s in syns:
                    if s.lower() != name_lower:
                        aliases.append(s)
                break

    # 2. 通用变体生成
    # 英文名 → 加中文后缀
    if re.match(r'^[A-Z][a-zA-Z]+$', name) and len(name) >= 3:
        # 纯英文专有名词，加常见后缀
        if name not in aliases:
            pass  # 不自动加，避免噪声

    # 3. 去重
    seen = {name.lower()}
    unique = []
    for a in aliases:
        a_lower = a.lower()
        if a_lower not in seen and a.strip():
            seen.add(a_lower)
            unique.append(a.strip())

    return unique[:6]  # 限制最多 6 个别名，避免过长


def main():
    """主函数: 批量生成 aliases 并写回 yaml"""
    # 添加 backend 到 path
    backend_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_dir))

    from core.graphs import get_skill_graph

    g = get_skill_graph()
    print(f"Total nodes: {len(g.nodes)}")

    # 找出需要生成 aliases 的节点（concept 类型 + 已审计）
    candidates = [n for n in g.nodes.values()
                  if n.node_type == "concept" and n.metadata.get("audited")]
    print(f"Candidate nodes (audited concept): {len(candidates)}")

    # 生成 aliases
    updated = 0
    for node in candidates:
        new_aliases = generate_aliases_for_node(node)
        if new_aliases and not node.aliases:
            node.aliases = new_aliases
            updated += 1
            print(f"  ✓ {node.name}: {new_aliases}")
        elif new_aliases and node.aliases:
            # 已有 aliases，合并去重
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

    print(f"\nUpdated {updated} nodes with aliases")

    # 保存
    if updated > 0:
        yaml_path = backend_dir / "core" / "graphs" / "skill_graph.yaml"
        # 备份
        import shutil
        bak_path = yaml_path.with_suffix(f".yaml.bak_aliases_{os.getpid()}")
        shutil.copy2(yaml_path, bak_path)
        print(f"Backup saved: {bak_path}")

        g.save(str(yaml_path))
        print(f"Skill graph saved with aliases to: {yaml_path}")
    else:
        print("No updates needed")


if __name__ == "__main__":
    main()
