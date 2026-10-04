"""端到端验证 CodeMunchPlugin 集成"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "libs"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logging.getLogger("core.llm.code_munch_plugin").setLevel(logging.DEBUG)
logger = logging.getLogger("validate")


async def main():
    from core.llm.code_munch_plugin import CodeMunchPlugin

    project_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    logger.info(f"项目路径: {project_path}")

    plugin = CodeMunchPlugin(project_path=project_path)

    # Step 1: 初始化
    logger.info("=== Step 1: 初始化 ===")
    if not await plugin.initialize():
        logger.error("初始化失败")
        return
    logger.info(f"repo_id={plugin._repo_id}, indexed={plugin._indexed}")

    # Step 2: 索引（如果未索引）
    if not plugin._indexed:
        logger.info("=== Step 2: 索引 ===")
        if not await plugin.index_project():
            logger.error("索引失败")
            return
    else:
        logger.info("=== Step 2: 索引（已跳过，已索引）===")

    # Step 3: get_repo_map
    logger.info("=== Step 3: get_repo_map ===")
    repo_map = await plugin.get_repo_map(max_symbols=20)
    if repo_map:
        logger.info(f"代码库概览: 共 {len(repo_map)} 个关键符号")
        for sym in repo_map[:5]:
            logger.info(f"  [{sym.get('kind', '?')}] {sym.get('name', '?')} @ {sym.get('file', '?')}")

    # Step 4: search_symbols
    logger.info("=== Step 4: search_symbols ===")
    for q in ["CodeMunchPlugin", "search_symbols", "WorkflowInput"]:
        symbols = await plugin.search_symbols(q, max_results=3)
        if symbols:
            logger.info(f"搜索 '{q}': {len(symbols)} 个结果")
            for sym in symbols[:2]:
                logger.info(f"  [{sym.get('kind', '?')}] {sym.get('name', '?')} id={sym.get('symbol_id', sym.get('id', '?'))[:40]}")
        else:
            logger.warning(f"搜索 '{q}': 无结果")

    # Step 5: get_symbol_source
    logger.info("=== Step 5: get_symbol_source ===")
    symbols = await plugin.search_symbols("CodeMunchPlugin", max_results=1)
    if symbols:
        sym_id = symbols[0].get("symbol_id", symbols[0].get("id", ""))
        if sym_id:
            source = await plugin.get_symbol_source(sym_id)
            if source:
                logger.info(f"获取源码成功: {len(source)} 字符")
                logger.info(f"代码预览:\n{source[:300]}")
            else:
                logger.warning("获取源码失败")

    # Step 6: search_and_extract
    logger.info("=== Step 6: search_and_extract ===")
    result = await plugin.search_and_extract("CodeMunchPlugin", max_symbols=1)
    logger.info(f"used={result['used']}, symbols={len(result['symbols'])}, sources={len(result['sources'])}, knowledge_items={len(result['knowledge_items'])}")
    if result.get("error"):
        logger.warning(f"error: {result['error']}")

    logger.info("=== 验证完成 ===")


if __name__ == "__main__":
    asyncio.run(main())