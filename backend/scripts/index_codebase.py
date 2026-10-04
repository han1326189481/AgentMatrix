"""索引 AgentMatrix 代码库 — 通过 jCodeMunch MCP 建立代码符号索引

运行方式:
    cd d:\AgentMatrix\backend
    $env:PYTHONPATH = "D:\AgentMatrix\backend\libs;D:\AgentMatrix\backend\libs\win32;D:\AgentMatrix\backend\libs\win32\lib"
    py -3.11 scripts\index_codebase.py
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "libs"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
# Enable debug for MCP communication
logging.getLogger("core.llm.code_munch_plugin").setLevel(logging.DEBUG)
logger = logging.getLogger("index_codebase")


async def main():
    from core.llm.code_munch_plugin import CodeMunchPlugin

    project_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    logger.info(f"项目路径: {project_path}")

    plugin = CodeMunchPlugin(project_path=project_path)

    # Step 1: 初始化 MCP 会话
    logger.info("Step 1: 初始化 jCodeMunch MCP 会话...")
    if not await plugin.initialize():
        logger.error("初始化失败，退出")
        return False

    # Step 2: 索引项目代码库
    logger.info("Step 2: 索引项目代码库...")
    if not await plugin.index_project():
        logger.error("索引失败，退出")
        return False

    # Step 3: 验证 — 获取代码库结构概览
    logger.info("Step 3: 验证索引 — 获取代码库结构概览...")
    repo_map = await plugin.get_repo_map(max_symbols=20)
    if repo_map:
        logger.info(f"代码库概览: 共 {len(repo_map)} 个关键符号")
        for sym in repo_map[:10]:
            logger.info(
                f"  [{sym.get('kind', '?')}] {sym.get('name', '?')} "
                f"  @ {sym.get('file', '?')}"
            )
    else:
        logger.warning("未获取到代码库概览（可能索引正在进行中）")

    # Step 4: 测试搜索
    logger.info("Step 4: 测试符号搜索...")
    symbols = await plugin.search_symbols("CodeMunchPlugin", max_results=3)
    if symbols:
        logger.info(f"搜索 'CodeMunchPlugin' 找到 {len(symbols)} 个符号:")
        for sym in symbols:
            logger.info(f"  [{sym.get('kind', '?')}] {sym.get('name', '?')}")
    else:
        logger.warning("搜索未返回结果")

    logger.info("索引完成！")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)