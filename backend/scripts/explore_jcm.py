"""探索 jCodeMunch MCP 的目录操作和指南"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "libs"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("explore")

project_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
libs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "libs")
win32_path = os.path.join(libs_path, "win32")
win32_lib_path = os.path.join(win32_path, "lib")


async def main():
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp import ClientSession
    from contextlib import AsyncExitStack

    env = os.environ.copy()
    python_path_parts = [libs_path, win32_path, win32_lib_path]
    existing = env.get("PYTHONPATH", "")
    if existing:
        python_path_parts.append(existing)
    env["PYTHONPATH"] = ";".join(python_path_parts)
    code_index_path = os.path.join(project_path, ".code-index")
    os.makedirs(code_index_path, exist_ok=True)
    env["CODE_INDEX_PATH"] = code_index_path

    exit_stack = AsyncExitStack()

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "jcodemunch_mcp"],
        env=env,
        cwd=project_path,
    )

    logger.info("Connecting to jCodeMunch MCP...")
    stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
    read_stream, write_stream = stdio_transport

    session = await exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
    await session.initialize()
    logger.info("Connected!")

    # 1. Get the guide
    logger.info("\n=== jCodeMunch Guide ===")
    guide_result = await session.call_tool("jcodemunch_guide", {})
    for item in guide_result.content:
        if hasattr(item, 'text'):
            logger.info(item.text)

    # 2. Get full menu
    logger.info("\n=== Full Menu (no query) ===")
    menu_result = await session.call_tool("menu", {"limit": 50})
    for item in menu_result.content:
        if hasattr(item, 'text'):
            text = item.text
            logger.info(f"Menu raw: {text[:2000]}")
            try:
                data = json.loads(text)
                logger.info(f"Menu parsed: {json.dumps(data, indent=2, ensure_ascii=False)[:3000]}")
            except:
                pass

    # 3. Search for specific actions
    logger.info("\n=== Menu for 'index' ===")
    menu_result = await session.call_tool("menu", {"query": "index", "limit": 10})
    for item in menu_result.content:
        if hasattr(item, 'text'):
            logger.info(f"Menu('index'): {item.text[:1000]}")

    logger.info("\n=== Menu for 'search' ===")
    menu_result = await session.call_tool("menu", {"query": "search", "limit": 10})
    for item in menu_result.content:
        if hasattr(item, 'text'):
            logger.info(f"Menu('search'): {item.text[:1000]}")

    await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())