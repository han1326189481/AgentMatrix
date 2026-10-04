"""快速测试 jCodeMunch MCP 的连接和基本操作"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "libs"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("quick_test")

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

    # Step 1: resolve_repo
    logger.info("Step 1: resolve_repo")
    result = await session.call_tool("order", {
        "action": "resolve_repo",
        "args": {"path": project_path},
    })
    for item in result.content:
        if hasattr(item, 'text'):
            data = json.loads(item.text)
            logger.info(f"resolve_repo: {json.dumps(data, indent=2)}")
            repo_id = data.get("repo", "")
            indexed = data.get("indexed", False)

    # Step 2: index_folder if not indexed
    if not indexed:
        logger.info(f"Step 2: index_folder (repo={repo_id})")
        result = await session.call_tool("order", {
            "action": "index_folder",
            "args": {"path": project_path},
            "allow_state_change": True,
        })
        for item in result.content:
            if hasattr(item, 'text'):
                logger.info(f"index_folder result: {item.text[:500]}")

    # Step 3: search_symbols
    logger.info(f"Step 3: search_symbols")
    result = await session.call_tool("order", {
        "action": "search_symbols",
        "args": {"repo": repo_id, "query": "CodeMunchPlugin"},
    })
    for item in result.content:
        if hasattr(item, 'text'):
            logger.info(f"search_symbols result: {item.text[:500]}")

    # Step 4: get_repo_map
    logger.info(f"Step 4: get_repo_map")
    result = await session.call_tool("order", {
        "action": "get_repo_map",
        "args": {"repo": repo_id},
    })
    for item in result.content:
        if hasattr(item, 'text'):
            logger.info(f"get_repo_map result: {item.text[:500]}")

    await exit_stack.aclose()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())