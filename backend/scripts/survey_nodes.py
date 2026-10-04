"""全面调研知识库节点状况"""
import sys
from pathlib import Path
from collections import Counter, defaultdict
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.graphs import get_skill_graph

g = get_skill_graph()

# 1. 总体统计
print(f"=== 总体统计 ===")
print(f"总节点数: {len(g.nodes)}")
type_count = Counter(n.node_type for n in g.nodes.values())
print(f"按类型: {dict(type_count)}")

# 2. concept 节点详细分析
concepts = [n for n in g.nodes.values() if n.node_type == "concept"]
print(f"\n=== Concept 节点 ({len(concepts)} 个) ===")

# 按领域分组
domain_groups = defaultdict(list)
for n in concepts:
    top_domain = (n.domain or "none").split(".")[0]
    domain_groups[top_domain].append(n)

for domain, nodes in sorted(domain_groups.items(), key=lambda x: -len(x[1])):
    print(f"\n--- 领域: {domain} ({len(nodes)} 个) ---")
    for n in nodes[:30]:  # 每个领域展示前 30 个
        audited = "✓" if n.metadata.get("audited") else " "
        has_alias = "★" if n.aliases else " "
        print(f"  [{audited}{has_alias}] {n.name:30s} domain={n.domain}")

# 3. 已有 aliases 的节点
print(f"\n=== 已有 aliases 的节点 ===")
with_aliases = [n for n in concepts if n.aliases]
print(f"数量: {len(with_aliases)}")
for n in with_aliases:
    print(f"  {n.name}: {n.aliases}")

# 4. 命名规律分析
print(f"\n=== 命名规律分析 ===")
pure_chinese = [n for n in concepts if all('\u4e00' <= c <= '\u9fff' or c in '（）、，·-' for c in n.name if c.strip())]
pure_english = [n for n in concepts if all(c.isascii() for c in n.name)]
mixed = [n for n in concepts if n not in pure_chinese and n not in pure_english]
print(f"纯中文: {len(pure_chinese)}")
print(f"纯英文: {len(pure_english)}")
print(f"中英混合: {len(mixed)}")
print()
print("--- 纯中文样本 ---")
for n in pure_chinese[:20]:
    print(f"  {n.name} (domain={n.domain})")
print()
print("--- 纯英文样本 ---")
for n in pure_english[:20]:
    print(f"  {n.name} (domain={n.domain})")
print()
print("--- 中英混合样本 ---")
for n in mixed[:20]:
    print(f"  {n.name} (domain={n.domain})")
