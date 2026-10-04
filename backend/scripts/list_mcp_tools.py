"""列出 jCodeMunch MCP 服务器的所有可用工具及其参数"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "libs"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("list_tools")


async def main():
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp import ClientSession
    from contextlib import AsyncExitStack

    project_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    libs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "libs")
    win32_path = os.path.join(libs_path, "win32")
    win32_lib_path = os.path.join(win32_path, "lib")

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

    # List all tools
    tools_result = await session.list_tools()
    logger.info(f"\n=== Available Tools ({len(tools_result.tools)}) ===")
    for tool in tools_result.tools:
        logger.info(f"\nTool: {tool.name}")
        logger.info(f"  Description: {tool.description[:100]}...")
        if hasattr(tool, 'inputSchema') and tool.inputSchema:
            props = tool.inputSchema.get('properties', {})
            required = tool.inputSchema.get('required', [])
            logger.info(f"  Required params: {required}")
            for pname, pinfo in props.items():
                req_mark = " [REQUIRED]" if pname in required else ""
                logger.info(f"    - {pname}: {pinfo.get('type', '?')} — {pinfo.get('description', '')[:80]}{req_mark}")

    await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())