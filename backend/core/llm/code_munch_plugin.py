"""CodeMunchPlugin — 代码检索插件（可插拔，非 Agent）

设计原则:
- 作为 Knowledge Agent 的工具类使用，不参与 5 Agent 执行顺序
- 通过 MCP SDK 的 stdio_client 与 jCodeMunch MCP 服务器通信
- jCodeMunch 使用"前门"模式：所有 91 个目录操作通过 `order` 工具统一分发
- 提供符号搜索、代码提取、结构分析等功能
- 失败降级：调用失败时返回空结果，不影响主流程

jCodeMunch MCP 核心能力:
- search_symbols: 搜索函数/类/方法等符号
- get_symbol_source: 获取符号的精确源代码
- get_blast_radius: 分析修改影响范围
- find_importers: 查找文件的导入者
- get_class_hierarchy: 遍历类继承链
- find_dead_code: 检测死代码
- get_repo_map: 代码库结构概览

使用方式:
    from core.llm.code_munch_plugin import CodeMunchPlugin

    plugin = CodeMunchPlugin()
    await plugin.initialize()
    symbols = await plugin.search_symbols("用户认证")
    source = await plugin.get_symbol_source(symbols[0]["symbol_id"])
"""
import asyncio
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Dict, Any, List, Optional

# V4.0: 确保 libs 目录在 Python 路径中（jcodemunch_mcp 等依赖安装在此处）
_libs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "libs")
if os.path.isdir(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)
# pywin32: 确保 win32 和 win32/lib 子目录也在路径中（.pth 文件在 --target 安装时不会自动处理）
_win32_path = os.path.join(_libs_path, "win32")
if os.path.isdir(_win32_path) and _win32_path not in sys.path:
    sys.path.insert(0, _win32_path)
_win32_lib_path = os.path.join(_libs_path, "win32", "lib")
if os.path.isdir(_win32_lib_path) and _win32_lib_path not in sys.path:
    sys.path.insert(0, _win32_lib_path)

logger = logging.getLogger(__name__)

# MCP 工具调用超时（秒）
MCP_CALL_TIMEOUT = 60

# 代码相关查询关键词（用于检测用户问题是否适合 CodeMunch）
CODE_QUERY_KEYWORDS = [
    "代码", "函数", "类", "方法", "实现", "源码", "逻辑",
    "怎么写", "调用", "参数", "返回", "接口", "模块", "导入",
    "定义", "声明", "变量", "异常", "错误处理", "重构",
    "function", "class", "method", "implement", "source",
    "code", "import", "export", "def ", "async ", "await",
]


class CodeMunchPlugin:
    """代码检索插件 — 通过 MCP SDK 与 jCodeMunch MCP 服务器通信

    jCodeMunch 使用"前门"模式，所有目录操作通过 `order` 工具统一分发。
    工作流程:
    1. 初始化：启动 jcodemunch-mcp 子进程，通过 MCP SDK 建立连接
    2. 解析仓库：调用 resolve_repo 获取仓库标识符
    3. 索引：调用 order(action="index_folder", args={path}, allow_state_change=true)
    4. 搜索：order(action="search_symbols", args={repo, query}) → 获取匹配的符号列表
    5. 提取：order(action="get_symbol_source", args={repo, symbol_id}) → 获取符号源代码

    并发安全：使用 asyncio.Lock 串行化 MCP 调用（stdio 管道不支持并发读写）。
    失败降级：任何步骤失败返回空结果，不抛异常阻断主流程。
    """

    def __init__(
        self,
        project_path: Optional[str] = None,
    ):
        """
        Args:
            project_path: 要索引的项目路径，默认自动检测为 AgentMatrix 根目录
        """
        self.project_path = project_path or self._detect_project_path()

        # MCP SDK 会话管理
        self._session = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._lock = asyncio.Lock()
        self._initialized = False
        self._indexed = False
        self._repo_id: Optional[str] = None  # 仓库标识符（resolve_repo 返回）

        logger.info(f"CodeMunchPlugin created: project_path={self.project_path}")

    def _detect_project_path(self) -> str:
        """自动检测项目根目录"""
        current = os.path.dirname(os.path.abspath(__file__))
        for _ in range(8):
            if os.path.exists(os.path.join(current, ".git")) or \
               os.path.exists(os.path.join(current, "pyproject.toml")):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        return os.getcwd()

    def _build_env(self) -> dict:
        """构建子进程环境变量"""
        env = os.environ.copy()
        python_path_parts = [_libs_path, _win32_path, _win32_lib_path]
        existing = env.get("PYTHONPATH", "")
        if existing:
            python_path_parts.append(existing)
        env["PYTHONPATH"] = ";".join(python_path_parts)
        # 设置 CODE_INDEX_PATH 到项目内的可写目录
        code_index_path = os.path.join(self.project_path, ".code-index")
        os.makedirs(code_index_path, exist_ok=True)
        env["CODE_INDEX_PATH"] = code_index_path
        return env

    # ============================================================
    # 生命周期管理
    # ============================================================

    async def initialize(self) -> bool:
        """启动 MCP 子进程并建立会话，解析仓库标识符

        Returns:
            True=初始化成功，False=失败
        """
        if self._initialized and self._session is not None:
            return True

        async with self._lock:
            if self._initialized:
                return True

            try:
                from mcp.client.stdio import stdio_client, StdioServerParameters
                from mcp import ClientSession

                self._exit_stack = AsyncExitStack()

                # 构建服务器参数
                server_params = StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "jcodemunch_mcp"],
                    env=self._build_env(),
                    cwd=self.project_path,
                )

                # 通过 MCP SDK 建立 stdio 连接
                logger.info("[CodeMunch] 通过 MCP SDK 建立 stdio 连接...")
                stdio_transport = await self._exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                read_stream, write_stream = stdio_transport

                # 创建客户端会话
                self._session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )

                # 初始化会话
                await self._session.initialize()
                logger.info("[CodeMunch] MCP 会话初始化成功")

                self._initialized = True

            except FileNotFoundError:
                logger.error(
                    "[CodeMunch] 找不到 jcodemunch-mcp，"
                    "请确保已安装: pip install jcodemunch-mcp"
                )
                await self._cleanup()
                return False
            except Exception as e:
                logger.error(f"[CodeMunch] 初始化失败: {e}", exc_info=True)
                await self._cleanup()
                return False

        # 锁外：解析仓库标识符
        # （_call_mcp_tool 内部也会获取锁，asyncio.Lock 不可重入）
        repo_info = await self._resolve_repo()
        if repo_info:
            self._repo_id = repo_info.get("repo", "")
            self._indexed = repo_info.get("indexed", False)
            logger.info(
                f"[CodeMunch] 仓库已解析: repo={self._repo_id}, "
                f"indexed={self._indexed}"
            )
        return True

    async def _resolve_repo(self) -> Optional[Dict[str, Any]]:
        """解析项目路径到仓库标识符

        Returns:
            {"found": bool, "indexed": bool, "repo": str, "hint": str}
            失败返回 None
        """
        try:
            result = await self._call_mcp_tool("order", {
                "action": "resolve_repo",
                "args": {"path": self.project_path},
            })
            if isinstance(result, dict):
                return result
            if isinstance(result, str):
                return json.loads(result)
            return None
        except Exception as e:
            logger.warning(f"[CodeMunch] resolve_repo 失败: {e}")
            return None

    async def index_project(self, path: Optional[str] = None) -> bool:
        """索引项目代码库

        Args:
            path: 项目路径，默认使用初始化时的 project_path

        Returns:
            True=索引成功，False=失败
        """
        if not await self._ensure_initialized():
            return False

        target = path or self.project_path
        if not os.path.isdir(target):
            logger.error(f"[CodeMunch] 项目路径不存在: {target}")
            return False

        try:
            logger.info(f"[CodeMunch] 开始索引项目: {target}")
            # 使用 order 工具分发 index_folder 操作，allow_state_change=true
            result = await self._call_mcp_tool("order", {
                "action": "index_folder",
                "args": {"path": target},
                "allow_state_change": True,
            })
            if result:
                self._indexed = True
                # index_folder 返回的 repo 可能与 resolve_repo 不同
                # （例如 GitHub 仓库名 vs 本地路径哈希名）
                if isinstance(result, dict) and result.get("repo"):
                    new_repo = result["repo"]
                    if new_repo != self._repo_id:
                        logger.info(
                            f"[CodeMunch] 仓库名已更新: "
                            f"{self._repo_id} → {new_repo}"
                        )
                        self._repo_id = new_repo
                else:
                    # 回退：重新解析
                    repo_info = await self._resolve_repo()
                    if repo_info:
                        self._repo_id = repo_info.get("repo", self._repo_id)
                logger.info(f"[CodeMunch] 项目索引完成: {target}, repo={self._repo_id}")
                return True
            else:
                logger.warning("[CodeMunch] 项目索引返回空结果")
                return False
        except Exception as e:
            logger.error(f"[CodeMunch] 索引失败: {e}")
            return False

    async def _cleanup(self):
        """清理 MCP 会话资源"""
        self._initialized = False
        self._indexed = False
        self._repo_id = None
        self._session = None
        if self._exit_stack:
            try:
                # 给 MCP 子进程足够时间完成清理
                await asyncio.wait_for(self._exit_stack.aclose(), timeout=5.0)
            except (asyncio.TimeoutError, Exception):
                pass
            self._exit_stack = None

    async def close(self):
        """显式关闭 MCP 会话（推荐在应用关闭时调用）"""
        await self._cleanup()

    async def _ensure_initialized(self) -> bool:
        """确保 MCP 会话已初始化"""
        if self._initialized and self._session is not None:
            return True
        return await self.initialize()

    # ============================================================
    # 公开 API — 代码检索
    # ============================================================

    async def search_symbols(
        self,
        query: str,
        symbol_type: Optional[str] = None,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """搜索代码符号

        Args:
            query: 搜索关键词（函数名、类名等）
            symbol_type: 符号类型过滤（function/class/method/constant 等）
            max_results: 最大返回数

        Returns:
            [{"symbol_id": "...", "name": "...", "kind": "...", "file": "...", ...}, ...]
            失败时返回空列表
        """
        if not await self._ensure_initialized():
            return []

        if not self._repo_id:
            logger.warning("[CodeMunch] 仓库 ID 未解析，请先调用 initialize()")
            return []

        args = {"repo": self._repo_id, "query": query}
        if symbol_type:
            args["kind"] = symbol_type

        try:
            result = await self._call_mcp_tool("order", {
                "action": "search_symbols",
                "args": args,
            })
            return self._parse_list_result(result, max_results)
        except Exception as e:
            logger.warning(f"[CodeMunch] search_symbols 失败: {e}")
            return []

    async def get_symbol_source(self, symbol_id: str) -> str:
        """获取符号的源代码

        Args:
            symbol_id: 符号ID（从 search_symbols 返回的 symbol_id 字段）

        Returns:
            源代码字符串，失败时返回空字符串
        """
        if not await self._ensure_initialized():
            return ""

        if not self._repo_id:
            logger.warning("[CodeMunch] 仓库 ID 未解析")
            return ""

        try:
            result = await self._call_mcp_tool("order", {
                "action": "get_symbol_source",
                "args": {
                    "repo": self._repo_id,
                    "symbol_id": symbol_id,
                },
            })
            return self._parse_text_result(result)
        except Exception as e:
            logger.warning(f"[CodeMunch] get_symbol_source 失败: {e}")
            return ""

    async def get_repo_map(self, max_symbols: int = 50) -> List[Dict[str, Any]]:
        """获取代码库结构概览（按 PageRank 重要性排序）

        Returns:
            符号列表
        """
        if not await self._ensure_initialized():
            return []

        if not self._repo_id:
            return []

        try:
            result = await self._call_mcp_tool("order", {
                "action": "get_repo_map",
                "args": {"repo": self._repo_id},
            })
            return self._parse_list_result(result, max_symbols)
        except Exception as e:
            logger.warning(f"[CodeMunch] get_repo_map 失败: {e}")
            return []

    async def get_blast_radius(self, symbol_id: str) -> Dict[str, Any]:
        """分析修改符号的影响范围

        Returns:
            {"importers": [...], "risk_score": 0.5, ...}
        """
        if not await self._ensure_initialized():
            return {}

        if not self._repo_id:
            return {}

        try:
            result = await self._call_mcp_tool("order", {
                "action": "get_blast_radius",
                "args": {
                    "repo": self._repo_id,
                    "symbol": symbol_id,
                },
            })
            if isinstance(result, dict):
                return result
            return {}
        except Exception as e:
            logger.warning(f"[CodeMunch] get_blast_radius 失败: {e}")
            return {}

    async def find_importers(self, file_path: str) -> List[Dict[str, Any]]:
        """查找导入指定文件的所有文件

        Args:
            file_path: 文件路径

        Returns:
            导入者列表
        """
        if not await self._ensure_initialized():
            return []

        if not self._repo_id:
            return []

        try:
            result = await self._call_mcp_tool("order", {
                "action": "find_importers",
                "args": {
                    "repo": self._repo_id,
                    "file": file_path,
                },
            })
            return self._parse_list_result(result, 50)
        except Exception as e:
            logger.warning(f"[CodeMunch] find_importers 失败: {e}")
            return []

    async def get_class_hierarchy(self, class_name: str) -> Dict[str, Any]:
        """获取类的继承层次结构

        Returns:
            {"ancestors": [...], "descendants": [...], ...}
        """
        if not await self._ensure_initialized():
            return {}

        if not self._repo_id:
            return {}

        try:
            result = await self._call_mcp_tool("order", {
                "action": "get_class_hierarchy",
                "args": {
                    "repo": self._repo_id,
                    "class_name": class_name,
                },
            })
            if isinstance(result, dict):
                return result
            return {}
        except Exception as e:
            logger.warning(f"[CodeMunch] get_class_hierarchy 失败: {e}")
            return {}

    async def find_dead_code(self) -> List[Dict[str, Any]]:
        """检测死代码

        Returns:
            死代码符号列表
        """
        if not await self._ensure_initialized():
            return []

        if not self._repo_id:
            return []

        try:
            result = await self._call_mcp_tool("order", {
                "action": "find_dead_code",
                "args": {"repo": self._repo_id},
            })
            return self._parse_list_result(result, 100)
        except Exception as e:
            logger.warning(f"[CodeMunch] find_dead_code 失败: {e}")
            return []

    async def get_file_content(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        """获取文件内容（从缓存）

        Args:
            file_path: 文件路径
            start_line: 起始行号（可选）
            end_line: 结束行号（可选）

        Returns:
            文件内容字符串
        """
        if not await self._ensure_initialized():
            return ""

        if not self._repo_id:
            return ""

        args = {"repo": self._repo_id, "file_path": file_path}
        if start_line is not None and end_line is not None:
            args["line_range"] = f"{start_line}-{end_line}"

        try:
            result = await self._call_mcp_tool("order", {
                "action": "get_file_content",
                "args": args,
            })
            return self._parse_text_result(result)
        except Exception as e:
            logger.warning(f"[CodeMunch] get_file_content 失败: {e}")
            return ""

    async def get_file_outline(self, file_path: str) -> List[Dict[str, Any]]:
        """获取文件的所有符号（函数、类、方法）及其签名

        Args:
            file_path: 文件路径

        Returns:
            符号列表
        """
        if not await self._ensure_initialized():
            return []

        if not self._repo_id:
            return []

        try:
            result = await self._call_mcp_tool("order", {
                "action": "get_file_outline",
                "args": {
                    "repo": self._repo_id,
                    "file": file_path,
                },
            })
            return self._parse_list_result(result, 100)
        except Exception as e:
            logger.warning(f"[CodeMunch] get_file_outline 失败: {e}")
            return []

    async def get_symbol_importance(self, max_symbols: int = 20) -> List[Dict[str, Any]]:
        """获取最重要的架构符号（按 PageRank 排名）

        Returns:
            符号列表
        """
        if not await self._ensure_initialized():
            return []

        if not self._repo_id:
            return []

        try:
            result = await self._call_mcp_tool("order", {
                "action": "get_symbol_importance",
                "args": {"repo": self._repo_id},
            })
            return self._parse_list_result(result, max_symbols)
        except Exception as e:
            logger.warning(f"[CodeMunch] get_symbol_importance 失败: {e}")
            return []

    # ============================================================
    # MCP 工具调用
    # ============================================================

    async def _call_mcp_tool(self, tool_name: str, arguments: dict) -> Any:
        """通过 MCP SDK 调用工具

        Args:
            tool_name: MCP 工具名称（order, menu, route, jcodemunch_guide 等）
            arguments: 工具参数

        Returns:
            工具执行结果（解析后的内容），失败返回 None
        """
        if self._session is None:
            logger.error("[CodeMunch] MCP 会话未初始化")
            return None

        async with self._lock:
            try:
                result = await asyncio.wait_for(
                    self._session.call_tool(tool_name, arguments),
                    timeout=MCP_CALL_TIMEOUT,
                )
                # 解析 MCP 响应: CallToolResult.content[0].text
                if result and hasattr(result, 'content') and result.content:
                    text = None
                    for item in result.content:
                        if hasattr(item, 'text'):
                            text = item.text
                            break
                    if text:
                        logger.debug(f"[CodeMunch] {tool_name} 原始响应: {text[:200]}")
                        try:
                            return json.loads(text)
                        except (json.JSONDecodeError, TypeError):
                            return text
                    # 非文本内容（图片等），返回原始 content
                    logger.debug(f"[CodeMunch] {tool_name} 非文本响应: {type(result.content)}")
                    return result.content
                logger.debug(f"[CodeMunch] {tool_name} 空响应: {type(result)}")
                return result
            except asyncio.TimeoutError:
                logger.warning(f"[CodeMunch] 工具调用超时: {tool_name}")
                return None
            except Exception as e:
                logger.warning(f"[CodeMunch] 工具调用失败: {tool_name}, error={e}")
                return None

    @staticmethod
    def _parse_list_result(result: Any, max_items: int) -> List[Dict[str, Any]]:
        """解析工具结果为列表

        支持两种格式:
        1. JSON: {"results": [...], "symbols": [...], ...}
        2. #MUNCH/1 紧凑编码: @1=path, @2=path, result_count=N, __tables=s:results:id|name|kind|
        """
        if result is None:
            return []
        if isinstance(result, list):
            return result[:max_items]
        if isinstance(result, dict):
            # 尝试多种可能的键名
            for key in ("symbols", "results", "content", "items", "data"):
                val = result.get(key, [])
                if isinstance(val, list) and len(val) > 0:
                    return val[:max_items]
            # 如果 result 本身有 id/name/kind 等字段，可能是单个符号
            if any(k in result for k in ("id", "name", "kind")):
                return [result]
            # 检查是否有 error 字段（表示搜索失败）
            if "error" in result:
                logger.debug(f"[CodeMunch] 搜索返回错误: {result.get('error')}")
                return []
            return []
        if isinstance(result, str):
            # 尝试解析 #MUNCH/1 紧凑编码格式
            if result.startswith("#MUNCH/"):
                return CodeMunchPlugin._parse_munch1(result, max_items)
            # 尝试 JSON 解析
            try:
                data = json.loads(result)
                return CodeMunchPlugin._parse_list_result(data, max_items)
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    @staticmethod
    def _parse_munch1(text: str, max_items: int) -> List[Dict[str, Any]]:
        """解析 #MUNCH/1 紧凑编码格式

        格式示例:
        #MUNCH/1 tool=search_symbols enc=ss1
        @1=backend/core/llm/code_munch_plugin.py
        @2=backend/libs/jcodemunch_mcp/org/license.py
        result_count=10 __stypes=result_count:int __tables=s:results:id|name|kind|file|line
        """
        lines = text.strip().split("\n")
        results = []
        table_header = None
        table_keys = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#MUNCH/"):
                continue
            if line.startswith("@") and "=" in line:
                # @N=value → 这是紧凑编码的文件引用
                # 提取文件名
                _, value = line.split("=", 1)
                value = value.strip()
                if value:
                    results.append({"name": value, "kind": "file", "file": value})
            elif line.startswith("__tables="):
                # 解析表头: __tables=s:results:id|name|kind|file|line
                table_part = line.split(":", 2)
                if len(table_part) >= 3:
                    table_header = table_part[2]  # results:id|name|kind|file|line
                    table_keys = table_header.split("|")
            elif line.startswith("result_count="):
                pass  # 元数据，跳过

        return results[:max_items]

    @staticmethod
    def _parse_text_result(result: Any) -> str:
        """解析工具结果为文本

        支持格式:
        1. 纯文本字符串
        2. JSON: {"source": "...", "text": "...", "content": "..."}
        3. #MUNCH/1 紧凑编码（源码格式）
        """
        if result is None:
            return ""
        if isinstance(result, str):
            # 尝试解析 #MUNCH/1 格式的源码
            if result.startswith("#MUNCH/"):
                return CodeMunchPlugin._parse_munch_source(result)
            return result
        if isinstance(result, dict):
            return result.get("source", result.get("text", result.get("content", str(result))))
        return str(result)

    @staticmethod
    def _parse_munch_source(text: str) -> str:
        """解析 #MUNCH/1 格式的源码

        格式示例:
        #MUNCH/1 tool=get_symbol_source enc=src1
        @1=def foo():
        @1=    pass
        """
        lines = text.strip().split("\n")
        source_lines = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#MUNCH/") or line.startswith("result_count=") or line.startswith("__"):
                continue
            if line.startswith("@") and "=" in line:
                _, value = line.split("=", 1)
                source_lines.append(value)
        return "\n".join(source_lines)

    # ============================================================
    # 便捷方法 — 供 Knowledge Agent 调用
    # ============================================================

    @staticmethod
    def detect_code_query(user_input: str) -> bool:
        """检测用户输入是否为代码相关查询"""
        input_lower = user_input.lower()
        for kw in CODE_QUERY_KEYWORDS:
            if kw.lower() in input_lower:
                return True
        return False

    async def search_and_extract(
        self,
        query: str,
        max_symbols: int = 3,
    ) -> Dict[str, Any]:
        """一站式搜索 + 提取：搜索符号并获取源代码

        供 Knowledge Agent 直接调用的高层 API。

        Args:
            query: 搜索关键词
            max_symbols: 最多提取的符号数

        Returns:
            {
                "used": bool,
                "symbols": [...],
                "sources": [...],
                "knowledge_items": [...],
                "error": Optional[str],
            }
        """
        result = {
            "used": False,
            "symbols": [],
            "sources": [],
            "knowledge_items": [],
            "error": None,
        }

        if not await self._ensure_initialized():
            result["error"] = "CodeMunch MCP 未初始化"
            return result

        if not self._repo_id:
            result["error"] = "仓库 ID 未解析"
            return result

        # Step 1: 搜索符号
        try:
            symbols = await self.search_symbols(query, max_results=max_symbols)
        except Exception as e:
            result["error"] = f"搜索失败: {e}"
            return result

        if not symbols:
            result["error"] = "未找到匹配的代码符号"
            return result

        result["symbols"] = symbols

        # Step 2: 提取每个符号的源代码
        sources = []
        knowledge_items = []
        for sym in symbols[:max_symbols]:
            sym_id = sym.get("symbol_id", sym.get("id", ""))
            sym_name = sym.get("name", "unknown")
            sym_kind = sym.get("kind", "symbol")
            sym_file = sym.get("file", "")

            if not sym_id:
                continue

            try:
                source = await self.get_symbol_source(sym_id)
                if source:
                    sources.append({
                        "name": sym_name,
                        "kind": sym_kind,
                        "file": sym_file,
                        "source": source,
                    })
                    lang = self._guess_language(sym_file)
                    knowledge_items.append({
                        "keyword": sym_name,
                        "content": (
                            f"[CodeMunch 代码检索] 符号: {sym_name} ({sym_kind})\n"
                            f"文件: {sym_file}\n"
                            f"```{lang}\n{source}\n```\n"
                        ),
                        "source": "code_munch",
                        "domain": "coding",
                    })
            except Exception as e:
                logger.warning(f"[CodeMunch] 提取符号 {sym_name} 源代码失败: {e}")

        result["sources"] = sources
        result["knowledge_items"] = knowledge_items
        result["used"] = len(sources) > 0

        if result["used"]:
            logger.info(
                f"[CodeMunch] search_and_extract 完成: "
                f"搜索到 {len(symbols)} 个符号，提取 {len(sources)} 个源码"
            )
        return result

    @staticmethod
    def _guess_language(filepath: str) -> str:
        """根据文件扩展名猜测编程语言"""
        ext = os.path.splitext(filepath)[1].lower()
        lang_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".tsx": "tsx", ".jsx": "jsx", ".java": "java", ".go": "go",
            ".rs": "rust", ".cpp": "cpp", ".c": "c", ".h": "c",
            ".cs": "csharp", ".rb": "ruby", ".php": "php",
            ".swift": "swift", ".kt": "kotlin", ".scala": "scala",
            ".vue": "vue", ".sql": "sql", ".yaml": "yaml", ".yml": "yaml",
            ".json": "json", ".toml": "toml", ".md": "markdown",
            ".css": "css", ".html": "html",
        }
        return lang_map.get(ext, "")


# ============================================================
# 单例
# ============================================================

_plugin_instance: Optional[CodeMunchPlugin] = None


def get_code_munch_plugin() -> CodeMunchPlugin:
    """获取 CodeMunchPlugin 单例"""
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = CodeMunchPlugin()
    return _plugin_instance