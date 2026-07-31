"""WebSearchPlugin — 联网搜索插件（可插拔，非 Agent）

设计原则（遵循规则十、规则十一）:
- 与权威知识库分离：搜索结果存入 TimelyKnowledgeService（第二持久化数据库）
- 不参与 5 Agent 执行顺序，作为 Knowledge Agent 的工具类使用
- 失败降级：搜索失败时返回空结果，不影响主流程
- 自学习入库：搜索结果经 LLM 摘要后存入时效性知识库，TTL=30天

搜索引擎选择（针对中国大陆可访问性）:
- 主：Bing（cn.bing.com）— 中国可直连，HTML 结构稳定
- 备：Sogou（sogou.com）— 中国搜索引擎，作为 Bing 失败时的备选
- 不使用 DuckDuckGo / Google（中国大陆无法直连）

使用方式:
    from core.llm.web_search_plugin import WebSearchPlugin

    plugin = WebSearchPlugin()
    result = await plugin.search_and_summarize(
        query="北京牛街美食推荐",
        user_question="北京牛街有什么好吃的",
    )
    # result: {"content": "摘要内容", "sources": [...], "raw_results": [...]}
"""
import asyncio
import logging
import re
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus, unquote

import aiohttp

logger = logging.getLogger(__name__)

# ============================================================
# 搜索引擎端点（中国大陆可访问）
# ============================================================

# Bing 中国版（主搜索引擎）
BING_SEARCH_URL = "https://cn.bing.com/search"
# Sogou 搜索（备用）
SOGOU_SEARCH_URL = "https://www.sogou.com/web"

# 默认 User-Agent（避免被搜索引擎拦截）
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 单次搜索返回的最大结果数
MAX_RESULTS = 8
# 单条结果摘要最大长度
SNIPPET_MAX_LEN = 500
# HTTP 超时（秒）
HTTP_TIMEOUT = 20


class WebSearchPlugin:
    """联网搜索插件 — 封装 Bing/Sogou 搜索 + DeepSeek 摘要

    工作流程:
    1. search(query) → 调用 Bing 获取原始搜索结果（标题+摘要+URL）
    2. search_and_summarize(query, user_question) → 搜索 + DeepSeek 摘要整合
    3. 搜索结果存入 TimelyKnowledgeService（由调用方决定何时入库）

    并发安全：无状态，可并发调用。
    失败降级：搜索或摘要失败时返回降级结果，不抛异常阻断主流程。
    """

    def __init__(
        self,
        deepseek_api_key: Optional[str] = None,
        deepseek_api_base: Optional[str] = None,
        deepseek_model: Optional[str] = None,
        enabled: bool = True,
    ):
        # 延迟读取配置
        if deepseek_api_key is None or deepseek_api_base is None or deepseek_model is None:
            from app.config import settings
            deepseek_api_key = deepseek_api_key or getattr(settings, "deepseek_api_key", "")
            deepseek_api_base = deepseek_api_base or getattr(
                settings, "deepseek_api_base", "https://api.deepseek.com/v1"
            )
            deepseek_model = deepseek_model or getattr(
                settings, "deepseek_model", "deepseek-v4-pro"
            )
            # 默认按环境变量决定是否启用
            if enabled:
                enabled = getattr(settings, "deepseek_search_enabled", True)

        self.deepseek_api_key = deepseek_api_key
        self.deepseek_api_base = deepseek_api_base.rstrip("/")
        self.deepseek_model = deepseek_model
        self.enabled = bool(enabled)

        logger.info(
            f"WebSearchPlugin initialized: enabled={self.enabled}, "
            f"model={self.deepseek_model}, api_base={self.deepseek_api_base}"
        )

    # ============================================================
    # 公开 API
    # ============================================================

    async def search(self, query: str, max_results: int = MAX_RESULTS) -> List[Dict[str, str]]:
        """执行 Web 搜索，返回原始结果列表

        Args:
            query: 搜索关键词
            max_results: 最大返回数

        Returns:
            [{"title": "...", "snippet": "...", "url": "..."}, ...]
            失败时返回空列表（不抛异常）
        """
        if not self.enabled:
            logger.debug("[WebSearch] 插件已禁用，跳过搜索")
            return []

        if not query or not query.strip():
            return []

        query = query.strip()
        logger.info(f"[WebSearch] 开始搜索: '{query[:60]}'")

        # 优先使用 Bing
        results = await self._search_bing(query, max_results)

        # Bing 失败时回退到 Sogou
        if not results:
            logger.debug("[WebSearch] Bing 无结果，尝试 Sogou")
            results = await self._search_sogou(query, max_results)

        logger.info(f"[WebSearch] 搜索完成: 获得 {len(results)} 条结果")
        return results[:max_results]

    async def search_and_summarize(
        self,
        query: str,
        user_question: str,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """搜索 + DeepSeek 摘要整合

        流程:
        1. 调用 search() 获取原始结果
        2. 将原始结果作为上下文喂给 DeepSeek，生成结构化摘要
        3. 返回摘要 + 原始来源（供入库和溯源）

        Args:
            query: 搜索关键词（用于检索）
            user_question: 用户原始问题（用于指导摘要方向）
            category: 分类提示（location/food/weather/travel/review）

        Returns:
            {
                "content": "结构化摘要（Markdown）",
                "sources": [{"title", "url"}, ...],
                "raw_results": [...],
                "summarized": bool,  # 是否成功调用 LLM 摘要
                "error": Optional[str],
            }
        """
        if not self.enabled:
            return self._empty_result("插件已禁用")

        # Step 1: 搜索
        raw_results = await self.search(query)
        if not raw_results:
            return self._empty_result("搜索无结果或搜索失败")

        # Step 2: LLM 摘要
        summarized = False
        error = None
        content = ""

        try:
            content = await self._summarize_with_llm(
                user_question=user_question,
                query=query,
                search_results=raw_results,
                category=category,
            )
            summarized = bool(content)
        except Exception as e:
            error = str(e)
            logger.warning(f"[WebSearch] LLM 摘要失败，降级使用原始片段: {e}")

        # 降级：LLM 失败时拼接原始片段
        if not content:
            content = self._fallback_concat(raw_results)

        return {
            "content": content,
            "sources": [
                {"title": r.get("title", ""), "url": r.get("url", "")}
                for r in raw_results[:5]
            ],
            "raw_results": raw_results,
            "summarized": summarized,
            "error": error,
        }

    # ============================================================
    # Bing 搜索实现
    # ============================================================

    async def _search_bing(
        self, query: str, max_results: int
    ) -> List[Dict[str, str]]:
        """Bing 中国版搜索

        Bing HTML 结构:
        - 每条结果在 <li class="b_algo">
        - 标题: <h2><a href="...">标题</a></h2>
        - 摘要: <p class="b_lineclamp..."> 或 <div class="b_caption"><p>
        """
        try:
            # 使用 cn.bing.com 并设置中文偏好
            url = f"{BING_SEARCH_URL}?q={quote_plus(query)}&ensearch=0&mkt=zh-CN&setlang=zh-CN"
            headers = {
                "User-Agent": DEFAULT_UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
            }

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
            ) as session:
                async with session.get(url, headers=headers, allow_redirects=True) as resp:
                    if resp.status != 200:
                        logger.warning(f"[WebSearch] Bing 状态码: {resp.status}")
                        return []
                    html = await resp.text(errors="ignore")

            results = self._parse_bing_html(html, max_results)
            logger.info(f"[WebSearch] Bing 解析得到 {len(results)} 条结果")
            return results
        except asyncio.TimeoutError:
            logger.warning("[WebSearch] Bing 搜索超时")
            return []
        except Exception as e:
            logger.warning(f"[WebSearch] Bing 搜索失败: {e}")
            return []

    def _parse_bing_html(
        self, html: str, max_results: int
    ) -> List[Dict[str, str]]:
        """解析 Bing HTML 结果页"""
        results: List[Dict[str, str]] = []

        # Bing 结果块在 <li class="b_algo">...</li>
        # 用正则按 b_algo 切分
        algo_blocks = re.split(r'<li[^>]+class="b_algo"', html)
        # 第一个 split 是 b_algo 之前的内容，跳过
        for block in algo_blocks[1:max_results + 1]:
            # 提取第一个 <a href="..."> 作为标题链接
            link_match = re.search(
                r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                block,
                re.DOTALL,
            )
            if not link_match:
                # 备用：直接找第一个 <a href>
                link_match = re.search(
                    r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                    block,
                    re.DOTALL,
                )
            if not link_match:
                continue

            url = link_match.group(1)
            title = self._strip_html(link_match.group(2)).strip()

            # 提取摘要：优先 b_lineclamp，否则 b_caption 中的 <p>
            snippet = ""
            snippet_match = re.search(
                r'<p[^>]+class="b_lineclamp[^"]*"[^>]*>(.*?)</p>',
                block,
                re.DOTALL,
            )
            if not snippet_match:
                snippet_match = re.search(
                    r'<div[^>]+class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>',
                    block,
                    re.DOTALL,
                )
            if not snippet_match:
                # 最后兜底：任意 <p>
                snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            if snippet_match:
                snippet = self._strip_html(snippet_match.group(1)).strip()

            if title and url:
                results.append({
                    "title": title[:200],
                    "snippet": snippet[:SNIPPET_MAX_LEN],
                    "url": url,
                })

        return results

    # ============================================================
    # Sogou 搜索实现（备用）
    # ============================================================

    async def _search_sogou(
        self, query: str, max_results: int
    ) -> List[Dict[str, str]]:
        """Sogou 搜索（备用）"""
        try:
            url = f"{SOGOU_SEARCH_URL}?query={quote_plus(query)}&ie=utf8"
            headers = {
                "User-Agent": DEFAULT_UA,
                "Accept": "text/html",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
            ) as session:
                async with session.get(url, headers=headers, allow_redirects=True) as resp:
                    if resp.status != 200:
                        logger.warning(f"[WebSearch] Sogou 状态码: {resp.status}")
                        return []
                    html = await resp.text(errors="ignore")

            results = self._parse_sogou_html(html, max_results)
            logger.info(f"[WebSearch] Sogou 解析得到 {len(results)} 条结果")
            return results
        except asyncio.TimeoutError:
            logger.warning("[WebSearch] Sogou 搜索超时")
            return []
        except Exception as e:
            logger.warning(f"[WebSearch] Sogou 搜索失败: {e}")
            return []

    def _parse_sogou_html(
        self, html: str, max_results: int
    ) -> List[Dict[str, str]]:
        """解析 Sogou HTML 结果页

        Sogou 结构:
        - 结果在 <div class="vrwrap"> 或 <div class="results">
        - 标题: <h3 class="vr-title"><a href="...">标题</a></h3>
        - 摘要: <div class="fz-mid space-txt"> 或 <p class="str-text-info">
        """
        results: List[Dict[str, str]] = []

        # 提取标题链接
        title_pattern = re.compile(
            r'<h3[^>]*class="vr-title"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        # 提取摘要
        snippet_pattern = re.compile(
            r'<div[^>]*class="fz-mid[^"]*"[^>]*>(.*?)</div>',
            re.DOTALL,
        )

        titles = title_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        for i, (url, title) in enumerate(titles):
            if i >= max_results:
                break
            clean_title = self._strip_html(title).strip()
            # Sogou 链接可能是相对路径或重定向
            if url.startswith("/link"):
                url = "https://www.sogou.com" + url
            snippet = ""
            if i < len(snippets):
                snippet = self._strip_html(snippets[i]).strip()
            if clean_title and url:
                results.append({
                    "title": clean_title[:200],
                    "snippet": snippet[:SNIPPET_MAX_LEN],
                    "url": url,
                })

        return results

    # ============================================================
    # HTML 工具方法
    # ============================================================

    def _strip_html(self, text: str) -> str:
        """移除 HTML 标签和实体"""
        if not text:
            return ""
        # 替换 <br> 为换行
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        # 移除所有标签
        text = re.sub(r"<[^>]+>", "", text)
        # 解码常见 HTML 实体
        entities = {
            "&amp;": "&", "&lt;": "<", "&gt;": ">",
            "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
            "&#x27;": "'", "&apos;": "'",
        }
        for k, v in entities.items():
            text = text.replace(k, v)
        # 压缩空白
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # ============================================================
    # DeepSeek 摘要
    # ============================================================

    async def _summarize_with_llm(
        self,
        user_question: str,
        query: str,
        search_results: List[Dict[str, str]],
        category: Optional[str] = None,
    ) -> str:
        """使用 DeepSeek 将搜索结果整合为结构化摘要

        系统提示词约束 LLM：
        - 基于搜索结果生成，不臆造
        - 输出 Markdown 格式
        - 标注信息来源
        - 针对用户问题精准回答
        """
        if not self.deepseek_api_key:
            raise RuntimeError("DeepSeek API Key 未配置")

        # 构建搜索结果上下文
        context_parts = []
        for i, r in enumerate(search_results, 1):
            context_parts.append(
                f"[{i}] {r.get('title', '')}\n"
                f"URL: {r.get('url', '')}\n"
                f"摘要: {r.get('snippet', '')}"
            )
        search_context = "\n\n".join(context_parts)

        category_hint = {
            "food": "美食推荐（含地址、人均、特色菜、口味）",
            "location": "地点推荐（含地址、开放时间、特色、交通）",
            "travel": "旅行攻略（含景点、行程、交通、住宿、预算）",
            "weather": "天气信息（含温度、降水、穿衣建议）",
            "review": "网友评价（含优点、缺点、口碑、评分）",
        }.get(category, "通用信息")

        system_prompt = (
            "你是一个信息整合助手。基于提供的互联网搜索结果，"
            "针对用户问题生成结构化、准确的回答。\n\n"
            "要求:\n"
            "1. 只基于搜索结果生成，不臆造、不补充未在搜索结果中的信息\n"
            "2. 输出 Markdown 格式，结构清晰（含小标题、列表、表格等）\n"
            "3. 在关键信息后用 [序号] 标注来源（如 [1][2]）\n"
            "4. 针对用户问题精准回答，避免无关信息\n"
            "5. 若搜索结果不足或冲突，诚实说明\n"
            f"6. 当前问题类别: {category_hint}\n"
        )

        user_prompt = (
            f"用户问题: {user_question}\n\n"
            f"搜索关键词: {query}\n\n"
            f"搜索结果:\n{search_context}\n\n"
            "请基于以上搜索结果，针对用户问题生成结构化回答。"
        )

        url = f"{self.deepseek_api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.5,
            "max_tokens": 2048,
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            ) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        logger.warning(
                            f"[WebSearch] LLM 摘要失败: status={resp.status}, body={err[:200]}"
                        )
                        raise RuntimeError(f"DeepSeek 返回 {resp.status}")
                    data = await resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        raise RuntimeError("DeepSeek 返回空 choices")
                    content = choices[0].get("message", {}).get("content", "")
                    logger.info(
                        f"[WebSearch] LLM 摘要完成: {len(content)} 字"
                    )
                    return content.strip()
        except aiohttp.ClientError as e:
            raise RuntimeError(f"网络错误: {e}")

    # ============================================================
    # 降级与辅助
    # ============================================================

    def _fallback_concat(self, results: List[Dict[str, str]]) -> str:
        """LLM 失败时降级拼接原始片段"""
        if not results:
            return ""
        parts = ["【Web Search 原始结果】"]
        for i, r in enumerate(results[:5], 1):
            parts.append(
                f"\n{i}. {r.get('title', '')}\n"
                f"   链接: {r.get('url', '')}\n"
                f"   摘要: {r.get('snippet', '')}"
            )
        return "\n".join(parts)

    def _empty_result(self, reason: str = "") -> Dict[str, Any]:
        return {
            "content": "",
            "sources": [],
            "raw_results": [],
            "summarized": False,
            "error": reason,
        }


# ============================================================
# 单例
# ============================================================

_plugin_instance: Optional[WebSearchPlugin] = None


def get_web_search_plugin() -> WebSearchPlugin:
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = WebSearchPlugin()
    return _plugin_instance
