"""提示词模板收录脚本 — 通过自学习系统将精选模板收录到永久化知识库

用法:
    python scripts/import_prompt_templates.py               # 执行收录
    python scripts/import_prompt_templates.py --dry-run     # 仅校验，不写入
    python scripts/import_prompt_templates.py --source-dir "prompt example"

流程:
    1. 读取 prompt example/ 下的所有 YAML 模板文件
    2. 为每个模板创建 KnowledgePatch (source=user_confirmed)
    3. 通过 PatchValidator 校验（重复/长度/有效性/定义/来源/冲突）
    4. 通过的 patch 应用到 SkillGraph（作为 skill 节点，完整模板存入 metadata）
    5. 在 MemoryStore 记录元记忆（供 build_context 注入系统提示）
    6. 保存 SkillGraph 到 skill_graph.yaml
"""
import os
import sys
import argparse
import logging
from pathlib import Path

# 添加 backend 目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# 模板源目录（相对于项目根目录）
DEFAULT_SOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "prompt example"
)

# SkillGraph 数据文件路径
SKILL_GRAPH_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core", "graphs", "skill_graph.yaml"
)


def load_templates(source_dir: str):
    """加载所有 YAML 模板文件"""
    import yaml
    templates = []
    yaml_files = sorted(Path(source_dir).rglob("*.yaml"))
    if not yaml_files:
        logger.error(f"未找到 YAML 文件: {source_dir}")
        return templates

    for yfile in yaml_files:
        try:
            with open(yfile, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or []
            if isinstance(data, list):
                for item in data:
                    item["_source_file"] = str(yfile.name)
                    templates.append(item)
                logger.info(f"加载 {yfile.name}: {len(data)} 条模板")
        except Exception as e:
            logger.error(f"加载失败 {yfile}: {e}")
    return templates


def build_domain_hierarchy(templates):
    """从模板中提取 domain/sub_domain 层级结构"""
    domains = set()
    sub_domains = set()
    for t in templates:
        domains.add(t.get("domain", ""))
        sub_domains.add((t.get("domain", ""), t.get("sub_domain", "")))
    return domains, sub_domains


def template_to_patch(template):
    """将提示词模板转换为 KnowledgePatch

    注意: concept_name 使用 template_id（如 ppt_structure_001）而非 title，
    因为部分 title（如"市场调研报告"）与已有 concept 节点（如"市场调研"）
    高度相似会触发 PatchValidator 的冲突检查。
    实际写入 SkillGraph 的节点 name 仍保留 title（人类可读）。
    """
    from core.skill_engine.models import KnowledgePatch

    template_id = template.get("id", "").strip()
    title = template.get("title", "").strip()
    tpl_text = template.get("template", "").strip()
    domain = template.get("domain", "")
    sub_domain = template.get("sub_domain", "")
    quality_score = float(template.get("quality_score", 0.85))

    # definition: 标题 + 模板摘要（前 80 字）+ 意图标签
    intent_tags = template.get("intent_tags", [])
    intent_str = "、".join(intent_tags[:5]) if intent_tags else ""
    definition = f"[提示词模板] {title}（领域: {domain}/{sub_domain}）"
    if intent_str:
        definition += f" | 意图标签: {intent_str}"
    definition += f" | 模板摘要: {tpl_text[:80]}..."

    return KnowledgePatch(
        concept_name=template_id,
        definition=definition,
        domain=f"{domain}.{sub_domain}",
        related_concepts=[sub_domain],
        confidence=quality_score,
        source="user_confirmed",
    )


def ensure_domain_nodes(skill_graph, domains, sub_domains):
    """确保 SkillGraph 中存在 ppt/speech 域及其子域节点"""
    from core.graphs.skill_graph import GraphNode, GraphEdge

    # 根域节点（ppt, speech, writing, daily）
    domain_display = {
        "ppt": "PPT 设计",
        "speech": "演讲口才",
        "writing": "写作创作",
        "daily": "日常效率",
    }
    for d in domains:
        if not d:
            continue
        node_id = d
        if node_id not in skill_graph.nodes:
            skill_graph.add_node(GraphNode(
                id=node_id,
                name=domain_display.get(d, d.upper()),
                node_type="domain",
                domain=d,
                description=f"{domain_display.get(d, d)} 领域知识",
            ))
            # 连接到 root
            if "root" in skill_graph.nodes:
                skill_graph.add_edge(GraphEdge(
                    from_node="root", to_node=node_id,
                    edge_type="subdomain_of", weight=1.0,
                ))
            logger.info(f"新增域节点: {node_id}")

    # 子域节点（ppt.ppt_structure 等）
    for d, sd in sub_domains:
        if not d or not sd:
            continue
        node_id = f"{d}.{sd}"
        if node_id not in skill_graph.nodes:
            skill_graph.add_node(GraphNode(
                id=node_id,
                name=sd.replace("_", " ").title(),
                node_type="domain",
                domain=node_id,
                description=f"{d}/{sd} 子领域",
            ))
            # 连接到父域
            if d in skill_graph.nodes:
                skill_graph.add_edge(GraphEdge(
                    from_node=d, to_node=node_id,
                    edge_type="subdomain_of", weight=1.0,
                ))
            logger.info(f"新增子域节点: {node_id}")


def apply_template_to_graph(skill_graph, template):
    """将模板作为 skill 节点写入 SkillGraph（完整模板存入 metadata）"""
    from core.graphs.skill_graph import GraphNode, GraphEdge

    template_id = template.get("id", "")
    title = template.get("title", "")
    domain = template.get("domain", "")
    sub_domain = template.get("sub_domain", "")

    node_id = template_id  # 如 ppt_structure_001
    if node_id in skill_graph.nodes:
        return False

    # 构造 metadata（保留完整模板信息）
    metadata = {
        "template_id": template_id,
        "template_text": template.get("template", ""),
        "variables": template.get("variables", []),
        "intent_tags": template.get("intent_tags", []),
        "difficulty": template.get("difficulty", ""),
        "quality_score": float(template.get("quality_score", 0.85)),
        "source_file": template.get("_source_file", ""),
        "node_kind": "prompt_template",
    }

    skill_graph.add_node(GraphNode(
        id=node_id,
        name=title,
        node_type="skill",
        domain=f"{domain}.{sub_domain}",
        description=f"[提示词模板] {title}（{domain}/{sub_domain}）",
        metadata=metadata,
    ))

    # 连接到子域节点（subdomain_of 关系）
    parent_id = f"{domain}.{sub_domain}"
    if parent_id in skill_graph.nodes:
        skill_graph.add_edge(GraphEdge(
            from_node=parent_id, to_node=node_id,
            edge_type="subdomain_of", weight=1.0,
        ))
    elif domain in skill_graph.nodes:
        skill_graph.add_edge(GraphEdge(
            from_node=domain, to_node=node_id,
            edge_type="subdomain_of", weight=1.0,
        ))

    return True


def record_meta_memory(templates_count, domains, sub_domains):
    """在 MemoryStore 中记录元记忆，供 build_context 注入系统提示"""
    from core.memory_store.store import get_memory_store

    store = get_memory_store("default")
    domain_list = sorted(domains)
    sub_domain_list = sorted([f"{d}.{s}" for d, s in sub_domains])

    content = (
        f"用户已整理 {templates_count} 条精选提示词模板并收录到 SkillGraph 永久化知识库。"
        f"领域覆盖: {', '.join(domain_list)}。"
        f"子领域: {', '.join(sub_domain_list)}。"
        f"模板存储在 SkillGraph 的 skill 节点中（node_type=skill, metadata.node_kind=prompt_template），"
        f"可通过 Knowledge Recommendation 引用。"
        f"当用户询问 PPT 制作、演讲稿撰写等场景时，应优先参考这些模板。"
    )

    mem_id = store.add(
        content=content,
        importance=0.95,
        source="manual",
        category="fact",
    )
    logger.info(f"元记忆已记录: id={mem_id}")
    return mem_id


def main():
    parser = argparse.ArgumentParser(description="将精选提示词模板收录到永久化知识库")
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR,
                        help=f"模板源目录 (默认: {DEFAULT_SOURCE_DIR})")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅校验，不实际写入")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("提示词模板收录脚本")
    logger.info(f"源目录: {args.source_dir}")
    logger.info(f"SkillGraph: {SKILL_GRAPH_PATH}")
    logger.info(f"模式: {'dry-run (仅校验)' if args.dry_run else '写入'}")
    logger.info("=" * 60)

    # 1. 加载模板
    templates = load_templates(args.source_dir)
    if not templates:
        logger.error("未加载到任何模板，终止")
        return 1
    logger.info(f"共加载 {len(templates)} 条模板")

    # 2. 加载 SkillGraph
    from core.graphs.skill_graph import SkillGraph
    skill_graph = SkillGraph.load(SKILL_GRAPH_PATH)
    logger.info(f"SkillGraph 加载完成: {len(skill_graph.nodes)} 节点, {len(skill_graph.edges)} 边")

    # 3. 初始化 PatchValidator
    from core.engines.patch_validator import PatchValidator
    validator = PatchValidator(skill_graph)

    # 4. 确保域节点存在
    domains, sub_domains = build_domain_hierarchy(templates)
    logger.info(f"领域: {sorted(domains)}")
    logger.info(f"子领域数: {len(sub_domains)}")
    if not args.dry_run:
        ensure_domain_nodes(skill_graph, domains, sub_domains)

    # 5. 逐条校验并应用
    validated = 0
    rejected = 0
    applied = 0
    rejection_reasons = []

    for tpl in templates:
        patch = template_to_patch(tpl)
        result = validator.validate_knowledge(patch)
        if result.passed:
            validated += 1
            if not args.dry_run:
                if apply_template_to_graph(skill_graph, tpl):
                    applied += 1
        else:
            rejected += 1
            rejection_reasons.append({
                "id": tpl.get("id", ""),
                "title": tpl.get("title", ""),
                "errors": result.errors,
                "warnings": result.warnings,
            })
            logger.warning(
                f"模板被拒: {tpl.get('id', '')} - {tpl.get('title', '')} | "
                f"错误: {result.errors}"
            )

    logger.info("-" * 60)
    logger.info(f"校验结果: 通过 {validated} / 拒绝 {rejected} / 总计 {len(templates)}")
    if not args.dry_run:
        logger.info(f"应用结果: 新增 {applied} 个 skill 节点")
    if rejection_reasons:
        logger.warning(f"被拒模板详情:")
        for r in rejection_reasons:
            logger.warning(f"  - {r['id']}: {r['errors']}")

    # 6. 保存 SkillGraph
    if not args.dry_run and applied > 0:
        skill_graph.save(SKILL_GRAPH_PATH)
        logger.info(f"SkillGraph 已保存: {SKILL_GRAPH_PATH}")
        logger.info(f"当前节点数: {len(skill_graph.nodes)}, 边数: {len(skill_graph.edges)}")

    # 7. 记录元记忆
    if not args.dry_run and applied > 0:
        record_meta_memory(applied, domains, sub_domains)

    # 8. 统计
    stats = skill_graph.stats()
    logger.info("-" * 60)
    logger.info(f"SkillGraph 统计: {stats}")

    if rejected > 0:
        logger.warning(f"有 {rejected} 条模板被拒，请检查后重新运行")
        return 1

    logger.info("收录完成！")
    return 0


if __name__ == "__main__":
    sys.exit(main())
