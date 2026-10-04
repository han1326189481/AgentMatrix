"""首次全量校验脚本 — 对现有知识库进行一次性全面质检

用法：
    cd d:\\AgentMatrix\\backend
    python scripts/audit_knowledge_base.py

功能：
1. 对 SkillGraph 中所有自学习节点（description 含"自动提取自回答内容"）进行质检
2. 对 SQLite 知识库中所有 auto_extract 来源的条目进行质检
3. 输出详细统计：替换/删除/规则过滤的数量
4. 自动持久化到 skill_graph.yaml 和 SQLite

执行前会自动备份 skill_graph.yaml 到 backups 目录，确保可回滚。
"""
import asyncio
import os
import sys
import shutil
import logging
from datetime import datetime

# 添加 backend 到 sys.path
backend_dir = os.path.realpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("audit_script")


async def audit_skill_graph():
    """质检 SkillGraph 自学习节点"""
    from core.graphs import get_skill_graph
    from core.llm.client import get_llm_client
    from core.engines.knowledge_auditor import KnowledgeAuditor

    skill_graph = get_skill_graph()
    llm_client = get_llm_client()

    # 备份 yaml
    yaml_path = os.path.join(backend_dir, "core", "graphs", "skill_graph.yaml")
    backups_dir = os.path.join(backend_dir, "storage", "backups")
    os.makedirs(backups_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backups_dir, f"skill_graph_{timestamp}.yaml")
    if os.path.exists(yaml_path):
        shutil.copy2(yaml_path, backup_path)
        logger.info(f"[Backup] skill_graph.yaml -> {backup_path}")

    # 统计待质检节点数
    auto_count = sum(
        1 for n in skill_graph.nodes.values()
        if n.node_type == "concept" and "自动提取自回答内容" in (n.description or "")
    )
    total_count = len(skill_graph.nodes)
    logger.info(
        f"[SkillGraph] 总节点 {total_count} 个，待质检自学习节点 {auto_count} 个"
    )

    if auto_count == 0:
        logger.info("[SkillGraph] 无需质检，跳过")
        return {"total": 0, "skipped": True}

    auditor = KnowledgeAuditor(
        skill_graph, llm_client, ws_manager=None,
        batch_size=5, cloud_concurrency=2,
    )

    stats = await auditor.audit_all(only_auto_extracted=True)

    # 输出详细日志（最近 30 条）
    logger.info("\n" + "=" * 60)
    logger.info("质检日志（最近 30 条）:")
    logger.info("=" * 60)
    for entry in auditor.audit_log[-30:]:
        logger.info(
            f"  [{entry['action']}] {entry['node_name']} -> {entry['detail']}"
        )

    return stats


async def audit_sqlite_knowledge():
    """质检 SQLite 知识库（仅 source=auto_extract 的条目）"""
    from app.database import init_db
    from app.database import get_global_session
    from models.knowledge import KnowledgeItem
    from core.llm.client import get_llm_client
    from core.llm.encyclopedia import fetch_authoritative_definition

    init_db()
    session = get_global_session()
    try:
        # 查询所有 source=auto_extract 的条目
        items = (
            session.query(KnowledgeItem)
            .filter(KnowledgeItem.source == "auto_extract")
            .all()
        )
        logger.info(f"[SQLite] 待质检条目 {len(items)} 条（source=auto_extract）")

        if not items:
            return {"total": 0, "skipped": True}

        llm_client = get_llm_client()
        stats = {
            "total": len(items),
            "wiki_replaced": 0,
            "cloud_replaced": 0,
            "removed": 0,
            "skipped": 0,
            "errors": 0,
        }

        for idx, item in enumerate(items, 1):
            try:
                definition = await fetch_authoritative_definition(
                    item.keyword, llm_client, use_cloud_fallback=True
                )
                if not definition:
                    # 非权威术语 → 删除
                    session.delete(item)
                    stats["removed"] += 1
                    logger.info(
                        f"[SQLite] {idx}/{len(items)} 删除: {item.keyword} "
                        f"(非权威术语)"
                    )
                else:
                    item.content = definition
                    item.source = "wiki" if definition.startswith("[来源: 中文维基百科]") else "deepseek_verified"
                    item.confidence = 0.95
                    if item.source == "wiki":
                        stats["wiki_replaced"] += 1
                    else:
                        stats["cloud_replaced"] += 1
                    logger.info(
                        f"[SQLite] {idx}/{len(items)} 替换: {item.keyword} "
                        f"(来源={item.source})"
                    )
                # 每 5 条提交一次
                if idx % 5 == 0:
                    session.commit()
            except Exception as e:
                logger.warning(f"[SQLite] {item.keyword} 质检异常: {e}")
                stats["errors"] += 1

        session.commit()
        return stats

    finally:
        session.close()


async def main():
    print("=" * 70)
    print("AgentMatrix 知识库首次全量校验")
    print("=" * 70)
    print()

    # 1. SkillGraph 质检
    print(">>> 第 1 步: 质检 SkillGraph 自学习节点")
    print("-" * 70)
    sg_stats = await audit_skill_graph()
    print()
    print("SkillGraph 质检统计:")
    for k, v in sg_stats.items():
        print(f"  {k}: {v}")
    print()

    # 2. SQLite 知识库质检
    print(">>> 第 2 步: 质检 SQLite 知识库 auto_extract 条目")
    print("-" * 70)
    db_stats = await audit_sqlite_knowledge()
    print()
    print("SQLite 知识库质检统计:")
    for k, v in db_stats.items():
        print(f"  {k}: {v}")
    print()

    # 3. 汇总
    print("=" * 70)
    print("全量校验完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
