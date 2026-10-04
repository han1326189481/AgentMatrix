"""探索 jCodeMunch MCP 的搜索和代码检索相关操作"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "libs"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("explore2")

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

    queries = ["symbol", "source", "repo", "map", "blast", "class", "hierarchy", "import", "dead", "diff", "file"]
    for q in queries:
        logger.info(f"\n=== Menu('{q}') ===")
        menu_result = await session.call_tool("menu", {"query": q, "limit": 5})
        for item in menu_result.content:
            if hasattr(item, 'text'):
                try:
                    data = json.loads(item.text)
                    for act in data.get("actions", [])[:3]:
                        logger.info(f"  {act['action']}: {act.get('summary', '')[:80]}")
                        logger.info(f"    required: {act.get('required', [])}")
                except:
                    logger.info(f"  raw: {item.text[:300]}")

    # Test resolve_repo
    logger.info("\n=== Test resolve_repo ===")
    result = await session.call_tool("order", {
        "action": "resolve_repo",
        "args": {"path": project_path}
    })
    for item in result.content:
        if hasattr(item, 'text'):
            logger.info(f"resolve_repo result: {item.text[:500]}")

    await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())