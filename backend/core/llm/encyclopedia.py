"""权威百科查询模块 — 知识库质检 V1.0

提供两条获取权威释义的路径：
1. 维基百科 API（zh.wikipedia.org）— 优先，零 LLM 调用
2. DeepSeek 兜底生成 — 维基查不到时调用，prompt 约束"基于权威百科风格"

维基百科 API：
- 端点: https://zh.wikipedia.org/w/api.php
- 使用 action=query + prop=extracts 获取纯文本摘要
- 使用 explaintint=1 去除 wiki 标记
- 限制 excerpt 长度，避免过长

注意：
- 仅用于 KnowledgeAuditor 调用，不直接暴露为 API
- 网络失败时返回 None，由调用方决定是否走 DeepSeek 兜底
"""
from typing import Optional
import aiohttp
import asyncio
import logging
import re

logger = logging.getLogger(__name__)

WIKI_API = "https://zh.wikipedia.org/w/api.php"
WIKI_TIMEOUT = 8  # 秒，避免长时间阻塞质检流程
MAX_EXCERPT_CHARS = 600  # 摘要最大字符数


async def fetch_wiki_summary(term: str) -> Optional[str]:
    """从中文维基百科获取术语的权威释义

    Args:
        term: 术语名（中英文均可）

    Returns:
        纯文本摘要（去除 wiki 标记），最多 MAX_EXCERPT_CHARS 字符；
        若未找到条目或网络失败，返回 None
    """
    if not term or not term.strip():
        return None

    term = term.strip()
    # 去除节点名中可能残留的 markdown 符号
    clean_term = re.sub(r"[*_`#:\-]+", "", term).strip()
    if not clean_term or len(clean_term) < 2:
        return None

    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "exintro": 1,          # 仅取首段（infobox 摘要）
        "redirects": 1,        # 跟随重定向
        "format": "json",
        "titles": clean_term,
        "formatversion": 2,
    }

    headers = {
        "User-Agent": "AgentMatrix/1.0 (knowledge-auditor; contact@local)",
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=WIKI_TIMEOUT)) as session:
            async with session.get(WIKI_API, params=params, headers=headers) as resp:
                if resp.status != 200:
                    logger.debug(f"[Wiki] {clean_term}: HTTP {resp.status}")
                    return None
                data = await resp.json()
                pages = data.get("query", {}).get("pages", [])
                if not pages:
                    return None
                page = pages[0]
                # missing=True 表示条目不存在
                if page.get("missing") or page.get("invalid"):
                    return None
                extract = page.get("extract", "")
                if not extract or len(extract) < 20:
                    return None
                # 截断到最大长度（按句号优先截断）
                if len(extract) > MAX_EXCERPT_CHARS:
                    cut = extract[:MAX_EXCERPT_CHARS]
                    # 尝试在最后一个句号处截断
                    last_period = max(cut.rfind("。"), cut.rfind(". "))
                    if last_period > 100:
                        cut = cut[: last_period + 1]
                    extract = cut
                logger.info(f"[Wiki] 命中: {clean_term} ({len(extract)} 字)")
                return extract
    except asyncio.TimeoutError:
        logger.debug(f"[Wiki] {clean_term}: 超时")
        return None
    except Exception as e:
        logger.debug(f"[Wiki] {clean_term}: 异常 {e}")
        return None


async def fetch_authoritative_definition(
    term: str,
    llm_client,
    use_cloud_fallback: bool = True,
) -> Optional[str]:
    """获取术语的权威定义

    优先级：
    1. 维基百科 API（无 LLM 成本）
    2. DeepSeek 兜底（prompt 强制要求权威百科风格 + 标注来源）

    Args:
        term: 术语名
        llm_client: LLMClient 实例（用于读取 DeepSeek API key/base）
        use_cloud_fallback: 是否启用 DeepSeek 兜底

    Returns:
        权威定义文本；若两条路径都失败，返回 None

    注意：
        DeepSeek 兜底强制使用真正的云端 DeepSeek API，不走用户配置的 ollama。
        原因：本地 qwen2.5:7b 无法准确判定术语权威性，会污染知识库。
    """
    # 1. 维基百科优先
    wiki_summary = await fetch_wiki_summary(term)
    if wiki_summary:
        return f"[来源: 中文维基百科]\n{wiki_summary}"

    # 2. DeepSeek 兜底
    if not use_cloud_fallback:
        return None

    # 强制使用真正的 DeepSeek 云端 API（绕过用户配置中可能存在的 ollama）
    api_key = getattr(llm_client, 'deepseek_api_key', '')
    api_base = getattr(llm_client, 'deepseek_api_base', 'https://api.deepseek.com/v1')
    model = getattr(llm_client, 'deepseek_model', 'deepseek-v4-pro')

    if not api_key:
        logger.warning(f"[Encyclopedia] DeepSeek API key 未配置，跳过兜底: {term}")
        return None

    system_prompt = (
        "你是权威百科名词解释助手。任务：为给定术语撰写一段严谨、客观、"
        "可被百科收录的定义。要求：\n"
        "1. 仅写定义本身，不写'根据…'、'根据百度百科…'等套话\n"
        "2. 长度 100-300 字\n"
        "3. 内容必须基于公开公认的权威资料（维基百科/百度百科/官方文档/教科书）\n"
        "4. 不得编造、不得臆测、不得加入个人观点\n"
        "5. 末尾以 [来源: <来源名>] 标注主要依据\n"
        "若该术语并非公认的标准名词（如碎片化片段、变量符号、私人事件、代码示例变量名），"
        "请回复：NOT_AN_AUTHORITY_TERM"
    )
    prompt = f"术语：{term}\n\n请给出权威百科风格的定义。"

    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,    # 降低温度，提高一致性
        "max_tokens": 600,
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.warning(
                        f"[Encyclopedia] DeepSeek 兜底 HTTP {response.status}: {term} - {error_text[:200]}"
                    )
                    return None
                data = await response.json()
                choices = data.get("choices", [])
                if not choices:
                    logger.warning(f"[Encyclopedia] DeepSeek 返回空 choices: {term}")
                    return None
                result = choices[0].get("message", {}).get("content", "").strip()
                if not result:
                    return None
                if "NOT_AN_AUTHORITY_TERM" in result:
                    logger.info(f"[Encyclopedia] DeepSeek 判定非权威术语: {term}")
                    return None
                logger.info(f"[Encyclopedia] DeepSeek 兜底成功: {term} ({len(result)} 字)")
                return result
    except asyncio.TimeoutError:
        logger.warning(f"[Encyclopedia] DeepSeek 兜底超时: {term}")
        return None
    except Exception as e:
        logger.warning(f"[Encyclopedia] DeepSeek 兜底异常: {term} - {e}")
        return None
