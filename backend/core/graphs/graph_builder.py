"""从 V2.1 tree.yaml + skill.yaml 构建 V3 Skill Graph"""

import os, yaml, logging
from .skill_graph import SkillGraph, GraphNode, GraphEdge

logger = logging.getLogger(__name__)

class GraphBuilder:
    """一次性迁移工具：YAML → Graph

    迁移策略:
    1. tree.yaml 的层级结构 → domain 节点 + subdomain_of 边
    2. 各域 skill.yaml 的 ontology.concepts → concept 节点 + related_to 边
    3. 手动补充 has_part / prerequisite / next_step 边（第一批）
    """

    def __init__(self, skills_dir: str = "prompts/skills"):
        self.skills_dir = skills_dir

    def build(self) -> SkillGraph:
        graph = SkillGraph()

        # 1. 加载 tree.yaml → domain 节点
        tree = self._load_yaml("tree.yaml")
        self._build_from_tree(graph, tree.get("tree", {}))

        # 2. 遍历所有 skill.yaml → concept 节点
        self._build_from_skills(graph)

        # 3. 手动补充关键概念节点（skill.yaml 未覆盖的种子概念）
        self._add_manual_nodes(graph)

        # 4. 手动补充关键边（根据领域知识，一次性补充）
        self._add_manual_edges(graph)

        logger.info(f"GraphBuilder: {graph.stats()}")
        return graph

    def _add_manual_nodes(self, graph: SkillGraph):
        """手动补充关键概念节点（skill.yaml 未覆盖的种子概念）

        这些节点是 manual_edges 的引用目标，必须先创建。
        注意: 不修改 V2.1 的 skill.yaml 源文件，仅在 Graph 迁移层补充。
        """
        manual_nodes = [
            GraphNode(
                id="llm",
                name="LLM",
                node_type="concept",
                domain="tech.ai",
                description="大语言模型，基于Transformer架构的大规模预训练语言模型",
            ),
            GraphNode(
                id="attention",
                name="Attention",
                node_type="concept",
                domain="tech.ai",
                description="注意力机制，允许模型动态关注输入序列的不同位置，是Transformer的核心组件",
            ),
            GraphNode(
                id="neural_network",
                name="Neural Network",
                node_type="concept",
                domain="tech.ai",
                description="神经网络，由神经元组成的层次化计算模型，是深度学习的基础",
            ),
        ]
        for node in manual_nodes:
            if node.id not in graph.nodes:
                graph.add_node(node)

    def _build_from_tree(self, graph: SkillGraph, tree: dict, parent_id: str = None):
        root = tree.get("root", tree)
        if isinstance(root, dict):
            node_id = root.get("id", "root")
            node = GraphNode(
                id=node_id, name=root.get("name", node_id),
                node_type="domain", domain=node_id,
            )
            graph.add_node(node)
            if parent_id:
                graph.add_edge(GraphEdge(
                    from_node=parent_id, to_node=node_id,
                    edge_type="subdomain_of"
                ))
            for child in root.get("children", []):
                self._build_from_tree(graph, {"root": child}, node_id)

    def _build_from_skills(self, graph: SkillGraph):
        for root, dirs, files in os.walk(self.skills_dir):
            if "_pending_patches" in root:
                continue
            for f in files:
                if f == "skill.yaml" and root != self.skills_dir:
                    skill = self._load_yaml(os.path.join(root, f))
                    if not skill:
                        continue
                    domain = skill.get("meta", {}).get("skill_id", "")
                    concepts = skill.get("knowledge", {}).get("ontology", {}).get("concepts", [])
                    for concept in concepts:
                        if not isinstance(concept, dict):
                            continue
                        term = concept.get("term", "")
                        if not term:
                            continue
                        node_id = term.lower().replace(" ", "_").replace("-", "_")
                        if node_id not in graph.nodes:
                            graph.add_node(GraphNode(
                                id=node_id, name=term,
                                node_type="concept", domain=domain,
                                description=concept.get("definition", ""),
                            ))
                        for related in concept.get("related", []):
                            related_id = related.lower().replace(" ", "_").replace("-", "_")
                            if related_id in graph.nodes:
                                graph.add_edge(GraphEdge(
                                    from_node=node_id, to_node=related_id,
                                    edge_type="related_to"
                                ))

    def _add_manual_edges(self, graph: SkillGraph):
        """手动补充关键关系边（第一批种子数据）

        边 ID 使用 skill.yaml 中实际生成的节点 ID。
        严格遵循 V3_DEVELOPMENT_GUIDE.md 第 3.2 节 manual_edges 定义。
        """
        manual_edges = [
            # AI 领域 has_part 关系
            ("agent", "memory", "has_part"),
            ("agent", "tool_use", "has_part"),
            ("agent", "multi_agent", "has_part"),
            ("rag", "embedding", "has_part"),
            ("rag", "chunking", "has_part"),
            ("rag", "rerank", "has_part"),
            # 学习路径（next_step）
            ("llm", "rag", "next_step"),
            ("rag", "agent", "next_step"),
            ("agent", "multi_agent", "next_step"),
            # 前置知识（prerequisite）— 按指南: transformer→llm, attention→transformer, neural_network→attention
            ("transformer", "llm", "prerequisite"),
            ("attention", "transformer", "prerequisite"),
            ("neural_network", "attention", "prerequisite"),
            # 加密领域学习路径
            ("rsa", "aes", "next_step"),
            ("aes", "kyber", "next_step"),
        ]
        for from_id, to_id, edge_type in manual_edges:
            if from_id in graph.nodes and to_id in graph.nodes:
                graph.add_edge(GraphEdge(
                    from_node=from_id, to_node=to_id,
                    edge_type=edge_type
                ))

    def _load_yaml(self, path: str) -> dict:
        # os.walk 返回的路径已包含 skills_dir，避免重复拼接
        if os.path.isabs(path):
            full_path = path
        elif path.startswith(self.skills_dir):
            full_path = path
        else:
            full_path = os.path.join(self.skills_dir, path)
        if not os.path.exists(full_path):
            return {}
        with open(full_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}