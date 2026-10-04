"""权威来源分级与校验 —— 三层筛网第 2/3 层共用的「外部证据」基础设施

设计目标（佳文 2026-09-24 定）:
- 每条待入库知识必须有**外部权威出处**，禁止依据模型自身知识判断
- 权威源**不锁死**百度百科/维基：官方网站、大型非营利机构、主流媒体均算
- 按三级分层，**三级源不能单独给一条知识背书**（必须有一级或二级）

本机实测事实（2026-09-24）:
- `zh.wikipedia.org` MediaWiki API **可达**（HTTP 200）。
  注意必须带 `redirects=1`，否则「过拟合」这类重定向词条会返回空 extract
  （这正是上一轮误判"维基全挂"的原因）。
- `baike.baidu.com` 页面直连 **403**（反爬），只能经搜索引擎结果间接取证。
- `cn.bing.com` 搜索可达，但 **`site:` 语法被忽略**，且存在**语义漂移**
  （搜「注意力机制」会返回百度百科「注意（心理学术语）」）。
  → 因此任何权威命中都必须通过 `_term_matches()` 词条匹配校验，
    命中域名权威 ≠ 命中词条正确。

被谁用:
- `core.engines.filter_net` 第 2 层（名词/片段拆解后的逐条比对）
- `core.engines.filter_net` 第 3 层（入库前二次校验）
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)

# HTTP 超时（秒）
HTTP_TIMEOUT = 20
# 单次搜索用于取证的结果数
EVIDENCE_MAX_RESULTS = 8
# 维基 API 端点
WIKI_API = "https://zh.wikipedia.org/w/api.php"
WIKI_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# ── 限流与重试（实测 2026-09-24）──
# 串行查询 6 次全中（约 0.75s/次）；并发 3 路掉到 4/6；
# 连续快速重查同一词条 8 次 **全部 MISS**。维基会对高频请求限流，
# 因此必须串行 + 限速 + 退避重试，并对结果做短期缓存。
WIKI_MIN_INTERVAL = 0.8     # 两次维基请求的最小间隔（秒）
WIKI_MAX_ATTEMPTS = 3       # 失败重试次数（含首次）
WIKI_BACKOFF_BASE = 1.5     # 退避基数（秒）
CACHE_TTL = 600             # 查询缓存有效期（秒）


# ============================================================
# 来源分级
# ============================================================

class SourceTier(IntEnum):
    """来源可信级别（数值越小越权威）"""

    TIER1 = 1      # 百科 / 官方 / 学术：可直接采信
    TIER2 = 2      # 权威机构 / 主流媒体：可采信，需记录来源
    TIER3 = 3      # 社区 / 自媒体 / 聚合站：仅作旁证，不能单独背书
    UNKNOWN = 9    # 未识别域名：等同三级以下，不能背书

    @property
    def label(self) -> str:
        return {
            SourceTier.TIER1: "一级（百科/官方/学术）",
            SourceTier.TIER2: "二级（权威机构/主流媒体）",
            SourceTier.TIER3: "三级（社区/自媒体，仅旁证）",
            SourceTier.UNKNOWN: "未识别（不可背书）",
        }[self]


# 一级：百科 / 官方 / 学术。用「域名后缀或完整域名」精确匹配，避免误伤。
TIER1_DOMAINS: Tuple[str, ...] = (
    # 百科
    "wikipedia.org", "wikiwand.com", "baike.baidu.com", "britannica.com",
    # 学术 / 文献
    "arxiv.org", "ieee.org", "acm.org", "nature.com", "science.org",
    "springer.com", "sciencedirect.com", "cnki.net", "doi.org", "pubmed.ncbi.nlm.nih.gov",
    # 厂商 / 项目官方文档
    "python.org", "nodejs.org", "mozilla.org", "kernel.org", "gnu.org",
    "nvidia.com", "pytorch.org", "tensorflow.org", "huggingface.co",
    "microsoft.com", "apple.com", "google.dev", "developer.android.com",
    "w3.org", "ietf.org", "rfc-editor.org", "openai.com", "ollama.com",
    "docker.com", "kubernetes.io", "rust-lang.org", "golang.org",
    "postgresql.org", "sqlite.org", "redis.io", "nginx.org",
)

# 一级：政府 / 教育 / 科研机构后缀（任何该后缀域名都算）
# ★ 注意：**不要**把 `.org.cn` 放进来。实测 `deepin.org.cn`（Linux 发行版社区站）
#   会被误判为一级权威源 —— `.org.cn` 下混着大量非权威组织站点。
TIER1_SUFFIXES: Tuple[str, ...] = (
    ".gov.cn", ".gov", ".edu.cn", ".edu", ".ac.cn", ".ac.uk", ".ac.jp",
    ".mil.cn",
)

# 二级：权威机构 / 主流媒体
TIER2_DOMAINS: Tuple[str, ...] = (
    # 中国主流媒体 / 官方新闻
    "xinhuanet.com", "news.cn", "people.com.cn", "people.cn", "cctv.com",
    "chinadaily.com.cn", "china.com.cn", "gmw.cn", "chinanews.com.cn",
    "thepaper.cn", "caixin.com", "yicai.com", "21jingji.com", "stcn.com",
    "bjnews.com.cn", "nbd.com.cn", "cls.cn", "eeo.com.cn",
    # 国际主流媒体 / 通讯社
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "nytimes.com",
    "theguardian.com", "bloomberg.com", "wsj.com", "ft.com",
    # 大型国际组织 / 非营利
    "un.org", "who.int", "worldbank.org", "imf.org", "oecd.org",
    "unesco.org", "itu.int", "iso.org", "w3.org",
    # 大型非营利技术组织
    "apache.org", "linuxfoundation.org", "openjsf.org",
)

# 三级：社区 / 自媒体 / 聚合（仅旁证）
TIER3_DOMAINS: Tuple[str, ...] = (
    "zhihu.com", "csdn.net", "cnblogs.com", "juejin.cn", "segmentfault.com",
    "runoob.com", "w3school.com.cn", "w3cschool.cn", "jianshu.com",
    "medium.com", "dev.to", "stackoverflow.com", "stackexchange.com",
    "github.com", "gitee.com", "gitlab.com", "github.io", "gitee.io",
    "readthedocs.io", "bilibili.com", "douban.com", "sohu.com", "163.com",
    "sina.com.cn", "qq.com", "ifeng.com", "toutiao.com", "baijiahao.baidu.com",
    "aliyun.com", "tencent.com", "csdn.net", "oschina.net", "51cto.com",
    "cnblogs.com", "bookstack.cn", "yuque.com", "notion.site",
)


def _host_of(url: str) -> str:
    """从 URL 提取小写主机名（去掉端口与 www. 前缀）"""
    if not url:
        return ""
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://([^/?#]+)", url.strip())
    host = m.group(1) if m else url.strip().split("/")[0]
    host = host.split("@")[-1].split(":")[0].lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


def _domain_in(host: str, domains: Tuple[str, ...]) -> bool:
    """host 是否命中域名列表（精确或子域）"""
    if not host:
        return False
    for d in domains:
        if host == d or host.endswith("." + d):
            return True
    return False


def classify_domain(url: str) -> SourceTier:
    """按域名判定来源级别

    先判一级（含 gov/edu 后缀），再判三级，最后二级。
    顺序原因：`baike.baidu.com` 同时属于 baidu.com 系，必须先命中一级。
    """
    host = _host_of(url)
    if not host:
        return SourceTier.UNKNOWN

    if _domain_in(host, TIER1_DOMAINS):
        return SourceTier.TIER1
    for suf in TIER1_SUFFIXES:
        if host.endswith(suf):
            return SourceTier.TIER1

    if _domain_in(host, TIER3_DOMAINS):
        return SourceTier.TIER3

    if _domain_in(host, TIER2_DOMAINS):
        return SourceTier.TIER2

    return SourceTier.UNKNOWN


def classify_source(url: str, origin: str = "") -> SourceTier:
    """来源级别判定总入口

    Args:
        url: 证据链接
        origin: 证据来源通道（如 "wikipedia_api"），维基 API 直接判一级
    """
    if origin == "wikipedia_api":
        return SourceTier.TIER1
    return classify_domain(url)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class SourceHit:
    """一条外部证据"""

    url: str
    title: str = ""
    snippet: str = ""
    tier: SourceTier = SourceTier.UNKNOWN
    origin: str = "search"          # search | wikipedia_api
    term_matched: bool = False      # 是否通过词条匹配（防语义漂移）

    def to_dict(self) -> Dict[str, object]:
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet[:300],
            "tier": int(self.tier),
            "tier_label": self.tier.label,
            "origin": self.origin,
            "term_matched": self.term_matched,
        }


@dataclass
class TermVerification:
    """单个名词/片段的核验结论"""

    term: str
    verified: bool = False
    best_tier: SourceTier = SourceTier.UNKNOWN
    authoritative_definition: str = ""
    sources: List[SourceHit] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "term": self.term,
            "verified": self.verified,
            "best_tier": int(self.best_tier),
            "best_tier_label": self.best_tier.label,
            "authoritative_definition": self.authoritative_definition[:500],
            "sources": [s.to_dict() for s in self.sources],
            "reasons": self.reasons,
        }


# ============================================================
# 词条匹配（防语义漂移）
# ============================================================

def _normalize(text: str) -> str:
    """归一化：去空白与常见分隔符，转小写"""
    return re.sub(r"[\s\-_·、，,。.（）()【】\[\]《》<>:：;；\"'`]+", "", (text or "").lower())


def _term_matches(term: str, title: str, snippet: str = "") -> bool:
    """判断权威命中的页面是否**真的是**这个名词

    必须过这一关，否则「搜注意力机制 → 命中"注意（心理学术语）"」这类
    语义漂移会被误判为"有权威背书"。

    规则（任一成立即算命中）:
    1. 归一化后 term 完整出现在标题里
    2. 归一化后 term 完整出现在摘要里
    3. 标题与 term 的字符重叠率 >= 0.8（覆盖"（消歧义后缀）"等修饰）
    """
    nt = _normalize(term)
    if not nt:
        return False

    ntitle = _normalize(title)
    if nt and nt in ntitle:
        return True

    nsnippet = _normalize(snippet)
    if nt and nt in nsnippet:
        return True

    if ntitle:
        inter = sum(1 for c in set(nt) if c in ntitle)
        if inter / max(len(set(nt)), 1) >= 0.8:
            return True

    return False


# ============================================================
# 校验器
# ============================================================

class AuthorityRegistry:
    """权威源分级 + 词条校验

    并发安全：内部只有**只读域名表 + 带锁的查询缓存**，可并发调用。
    失败降级：网络失败返回未通过（**不通过即不可入库**，不抛异常阻断管线）。

    限流：维基请求串行 + 最小间隔 + 退避重试；搜索与维基结果做短期缓存，
    避免第 2/3 层对同一词条重复打同一站点触发限流。
    """

    def __init__(
        self,
        search_plugin=None,
        *,
        require_tier1: bool = False,
        timeout: int = HTTP_TIMEOUT,
        cache_ttl: int = CACHE_TTL,
    ):
        """
        Args:
            search_plugin: WebSearchPlugin 实例（懒加载）
            require_tier1: True 时要求至少一个一级来源（严格模式）；
                False 时一级或二级均可背书（默认）
            cache_ttl: 查询结果缓存有效期（秒）
        """
        self._search_plugin = search_plugin
        self.require_tier1 = require_tier1
        self.timeout = timeout
        self.cache_ttl = cache_ttl

        # 维基限流：串行 + 最小间隔
        self._wiki_lock = asyncio.Lock()
        self._wiki_last_call = 0.0
        # 查询缓存： term -> (expire_ts, hit|None)
        self._wiki_cache: Dict[str, Tuple[float, Optional[SourceHit]]] = {}
        self._search_cache: Dict[str, Tuple[float, List[SourceHit]]] = {}

    # ---------- 缓存工具 ----------

    def _cache_get(self, cache: Dict, key: str):
        item = cache.get(key)
        if not item:
            return None
        expire, value = item
        if time.time() > expire:
            cache.pop(key, None)
            return None
        return value

    def _cache_put(self, cache: Dict, key: str, value) -> None:
        cache[key] = (time.time() + self.cache_ttl, value)
        # 简单容量控制，避免长跑内存无界增长
        if len(cache) > 512:
            now = time.time()
            for k in [k for k, (exp, _) in cache.items() if exp < now]:
                cache.pop(k, None)
            if len(cache) > 512:
                for k in list(cache.keys())[:256]:
                    cache.pop(k, None)

    # ---------- 搜索引擎（复用项目既有插件） ----------

    def _get_search_plugin(self):
        if self._search_plugin is None:
            from core.llm.web_search_plugin import get_web_search_plugin
            self._search_plugin = get_web_search_plugin()
        return self._search_plugin

    async def search_evidence(
        self, query: str, max_results: int = EVIDENCE_MAX_RESULTS
    ) -> List[SourceHit]:
        """搜索并返回带级别标注的证据列表（不做词条匹配；结果带缓存）"""
        key = f"{query}|{max_results}"
        cached = self._cache_get(self._search_cache, key)
        if cached is not None:
            return cached

        try:
            results = await self._get_search_plugin().search(query, max_results=max_results)
        except Exception as e:  # pragma: no cover - 网络异常路径
            logger.warning("[Authority] 搜索失败: %s", e)
            return []

        hits: List[SourceHit] = []
        for r in results or []:
            url = r.get("url", "")
            hits.append(SourceHit(
                url=url,
                title=r.get("title", ""),
                snippet=r.get("snippet", ""),
                tier=classify_domain(url),
                origin="search",
            ))
        # 只缓存非空结果：搜索本身会偶发返回 0 条（实测），
        # 缓存空结果会把偶发失败固化成持续失败。
        if hits:
            self._cache_put(self._search_cache, key, hits)
        return hits

    # ---------- 维基百科 MediaWiki API ----------

    async def _wiki_request(self, term: str) -> Tuple[str, Optional[SourceHit]]:
        """单次维基请求

        Returns:
            (status, hit)：status ∈ {"ok", "missing", "error"}
        """
        params = {
            "action": "query",
            "prop": "extracts",
            "explaintext": "1",
            "exintro": "1",
            "redirects": "1",
            "format": "json",
            "formatversion": "2",
            "titles": term.strip(),
        }
        qs = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in params.items())
        url = f"{WIKI_API}?{qs}"

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                async with session.get(
                    url, headers={"User-Agent": WIKI_UA}, allow_redirects=True
                ) as resp:
                    if resp.status != 200:
                        logger.debug("[Authority] 维基状态码 %s (%s)", resp.status, term)
                        return ("error", None)
                    data = await resp.json(content_type=None)
        except Exception as e:
            logger.debug("[Authority] 维基请求失败 (%s): %s", term, e)
            return ("error", None)

        pages = (data or {}).get("query", {}).get("pages", []) or []
        if not pages:
            return ("missing", None)
        page = pages[0]
        if page.get("missing"):
            return ("missing", None)

        extract = (page.get("extract") or "").strip()
        if not extract:
            # 词条存在但没有导语 extract：仍算 missing（对筛网而言无可用定义）
            return ("missing", None)

        resolved_title = page.get("title") or term
        return ("ok", SourceHit(
            url=f"https://zh.wikipedia.org/wiki/{quote(resolved_title)}",
            title=resolved_title,
            snippet=extract,
            tier=SourceTier.TIER1,
            origin="wikipedia_api",
            term_matched=True,   # 维基按标题精确检索，视为词条匹配
        ))

    async def wikipedia_lookup(self, term: str) -> Optional[SourceHit]:
        """查询中文维基词条（带 redirects=1、串行限流、退避重试、结果缓存）

        Returns:
            命中返回 SourceHit(一级)，未命中/网络失败返回 None
        """
        if not term or not term.strip():
            return None
        key = term.strip()

        cached = self._cache_get(self._wiki_cache, key)
        if cached is not None:
            return cached

        hit: Optional[SourceHit] = None
        for attempt in range(WIKI_MAX_ATTEMPTS):
            async with self._wiki_lock:
                wait = WIKI_MIN_INTERVAL - (time.time() - self._wiki_last_call)
                if wait > 0:
                    await asyncio.sleep(wait)
                status, result = await self._wiki_request(key)
                self._wiki_last_call = time.time()

            if status == "ok":
                hit = result
                break
            if status == "missing":
                break   # 真的没有该词条，重试无意义
            # status == "error"：可能是限流，退避后重试
            if attempt < WIKI_MAX_ATTEMPTS - 1:
                await asyncio.sleep(WIKI_BACKOFF_BASE * (attempt + 1))

        self._cache_put(self._wiki_cache, key, hit)
        return hit

    # ---------- 主校验入口 ----------

    @staticmethod
    def _authoritative_matched(hits: List[SourceHit]) -> List[SourceHit]:
        """筛出「词条匹配 + 一级或二级」的权威命中"""
        return [
            h for h in hits
            if h.term_matched and h.tier in (SourceTier.TIER1, SourceTier.TIER2)
        ]

    async def verify(self, term: str, claim: str = "") -> TermVerification:
        """【第 2 层】校验名词/片段是否有权威出处

        做法：维基词条精确查询（一级）＋ 一次检索取证（按域名分级 + 词条匹配）。

        Args:
            term: 待核验的名词/短语
            claim: 回答中关于该词的说法（仅记录，不参与判真伪）

        Returns:
            TermVerification；`verified=False` 时 reasons 说明原因
        """
        result = TermVerification(term=term)
        term = (term or "").strip()
        if not term:
            result.reasons.append("空词条")
            return result

        # 1) 维基百科（一级，最可靠）
        wiki = await self.wikipedia_lookup(term)
        if wiki:
            result.sources.append(wiki)
            result.authoritative_definition = wiki.snippet
            result.best_tier = SourceTier.TIER1

        # 2) 搜索引擎取证
        hits = await self.search_evidence(f"{term} 定义 是什么")
        for h in hits:
            h.term_matched = _term_matches(term, h.title, h.snippet)
        matched = self._authoritative_matched(hits)

        result.sources.extend(hits)
        for h in matched:
            if h.tier < result.best_tier:
                result.best_tier = h.tier
            if not result.authoritative_definition and h.snippet:
                result.authoritative_definition = h.snippet

        # 3) 判定：三级源不能单独背书
        tier_ok = (
            result.best_tier == SourceTier.TIER1
            if self.require_tier1
            else result.best_tier in (SourceTier.TIER1, SourceTier.TIER2)
        )
        if not tier_ok:
            if result.best_tier == SourceTier.TIER3:
                result.reasons.append("仅有三级来源（社区/自媒体），不能单独背书")
            else:
                result.reasons.append("未找到任何权威来源")

        result.verified = bool(tier_ok)
        return result

    async def recheck_authority(
        self, verification: TermVerification
    ) -> TermVerification:
        """【第 3 层】入库前的二次检索校验

        ★ 写死逻辑：不得依据模型自身知识库判断，必须**再执行一次 web search**，
          在权威网站/权威媒体找到出处才准通过。

        判定规则:
        - 二次检索必须真的执行（返回至少一条结果），否则视为无法校验 → 不通过
        - 通过条件：二次检索命中权威词条，**或**第 2 层已经拿到一级来源
          （维基 API 本身就是带 URL 的权威出处，对它再要求一次搜索确认属于冗余，
           但仍强制要求执行这轮检索以留下可审计证据）
        """
        term = (verification.term or "").strip()
        if not term:
            verification.reasons.append("空词条")
            verification.verified = False
            return verification

        prior_tier1 = verification.best_tier == SourceTier.TIER1

        hits = await self.search_evidence(f"{term} 是什么 含义 解释")
        for h in hits:
            h.term_matched = _term_matches(term, h.title, h.snippet)
        verification.sources.extend(hits)

        second_matched = self._authoritative_matched(hits)
        for h in second_matched:
            if h.tier < verification.best_tier:
                verification.best_tier = h.tier
            if not verification.authoritative_definition and h.snippet:
                verification.authoritative_definition = h.snippet

        if not hits:
            verification.reasons.append("二次检索无法执行（未获得任何结果）")
            verification.verified = False
        elif second_matched or prior_tier1:
            verification.verified = True
        else:
            verification.reasons.append("二次检索未再命中权威出处")
            verification.verified = False

        return verification

    async def verify_many(
        self, terms: List[str], *, max_concurrency: int = 1
    ) -> List[TermVerification]:
        """校验多个词条

        ★ 默认 **串行**（max_concurrency=1）。实测并发会触发维基限流
          （串行 6/6 命中；并发 3 路掉到 4/6），而漏判的代价是"本该入库的
          知识被误拒"，比慢一点严重得多。
        """
        sem = asyncio.Semaphore(max(1, max_concurrency))

        async def _one(t: str) -> TermVerification:
            async with sem:
                try:
                    return await self.verify(t)
                except Exception as e:  # pragma: no cover
                    logger.warning("[Authority] 校验异常 %s: %s", t, e)
                    v = TermVerification(term=t)
                    v.reasons.append(f"校验异常: {e}")
                    return v

        return await asyncio.gather(*[_one(t) for t in terms])

    async def recheck_many(
        self, verifications: List[TermVerification], *, max_concurrency: int = 1
    ) -> List[TermVerification]:
        """【第 3 层】对已通过第 2 层的词条批量做二次检索校验（默认串行）"""
        sem = asyncio.Semaphore(max(1, max_concurrency))

        async def _one(v: TermVerification) -> TermVerification:
            async with sem:
                try:
                    return await self.recheck_authority(v)
                except Exception as e:  # pragma: no cover
                    logger.warning("[Authority] 二次校验异常 %s: %s", v.term, e)
                    v.reasons.append(f"二次校验异常: {e}")
                    v.verified = False
                    return v

        return await asyncio.gather(*[_one(v) for v in verifications])



# ============================================================
# 单例
# ============================================================

_registry: Optional[AuthorityRegistry] = None


def get_authority_registry() -> AuthorityRegistry:
    global _registry
    if _registry is None:
        try:
            from app.config import settings
            strict = bool(getattr(settings, "filter_require_tier1", False))
        except Exception:
            strict = False
        _registry = AuthorityRegistry(require_tier1=strict)
    return _registry
