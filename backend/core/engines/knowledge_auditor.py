"""KnowledgeAuditor — 知识库质检引擎 V1.0

质检目标：
    确保每一项永久化知识都来自权威百科或官方资料，
    而非 AI 的"异想天开"或自动提取的碎片化片段。

质检对象：
    1. SkillGraph 自学习节点（description 含"自动提取自回答内容"）
    2. SQLite 知识库 KnowledgeItem（confidence 较低或 source=auto_extract）

质检流程（四层）：
    L1 规则预过滤 — 零 LLM 成本，过滤明显的碎片化片段、时间表噪声、变量符号
    L2 权威百科查询 — 维基百科 API（零 LLM 成本）
    L3 DeepSeek 校验 — 维基未命中时调用云端，判定是否权威术语并生成权威定义
    L4 替换/删除 — 校验通过则替换 description，未通过则删除节点

调用方式：
    - 后台任务（FastAPI BackgroundTasks / asyncio.create_task）
    - 计数触发：每新增 10 个永久化知识点
    - 定时触发：用户超过 2 分钟无请求

进度推送：
    通过 WebSocketManager.broadcast_audit_progress 推送，
    前端弹窗显示进度，完成后自动关闭。
"""
import re
import logging
import asyncio
from typing import List, Optional, Callable, Awaitable
from datetime import datetime

from core.graphs.skill_graph import SkillGraph, GraphNode

logger = logging.getLogger(__name__)


# ============================================================
# L1 规则预过滤 — 命中任意一条即判定为"非权威术语"
# ============================================================

# 碎片化片段黑名单（在节点名中出现即过滤）
_FRAGMENT_BLACKLIST = {
    # 代词/连词/介词碎片
    "它不仅", "它不", "它还", "它的", "它们", "不仅", "比如", "例如",
    "其中", "通常", "一般", "可能", "可以", "应该", "需要", "能够",
    "通过", "根据", "按照", "结合", "包括", "除外", "另外", "此外",
    "主要", "重要", "基本", "基础", "具体", "特定", "某些", "其他",
    "部分", "全部", "整体", "本身", "自动", "手动", "实时", "确保",
    "保证", "实现", "完成", "处理", "解决", "提供", "支持", "包含",
    # 单字+数字编号
    "第一天", "第二天", "第三天", "第四天", "第五天", "第六天", "第七天",
    # 标点残留
    "：", ":", "、", "，", "。", "；",
}

# 时间表噪声正则（如 "07:30___09:00_晨练与早餐" / "08:00 - 09:00 前往..."）
_TIME_NOISE_PATTERN = re.compile(
    r"\d{1,2}[:：]\d{2}\s*[_\-—–到至]\s*\d{1,2}[:：]\d{2}"
)

# 纯编号正则（如 "1._定义与初始化" / "2.3 智能客服"）
_NUMBERED_LIST_PATTERN = re.compile(r"^\d+[\.\_、]\s*[\u4e00-\u9fffa-zA-Z]")

# 纯变量符号（如 d_k、h_i、x_1、T_max — 单字母+下标）
_VARIABLE_SYMBOL_PATTERN = re.compile(r"^[a-zA-Z]\w{0,5}$")

# 含 markdown 标记（如 **特色小吃**）
_MARKDOWN_PATTERN = re.compile(r"[\*`_#]+")

# 行程/日程相关词（个人事件，非权威术语）
_PERSONAL_EVENT_PATTERN = re.compile(
    r"(行程|日程|早餐|午餐|晚餐|用餐|游览|参观|入住|抵达|前往|出发|"
    r"休闲|活动|休息|酒店|高铁|航班|景点|门票)"
)


def _rule_based_filter(node: GraphNode) -> tuple[bool, str]:
    """规则预过滤 — 返回 (是否过滤, 过滤原因)

    返回 True 表示该节点应被过滤（不是权威术语）。
    """
    name = (node.name or "").strip()
    node_id = (node.id or "").strip()
    description = (node.description or "").strip()

    # 1. 节点名为空或过短
    if len(name) < 2:
        return True, "名称过短"

    # 2. 命中碎片化黑名单
    if name in _FRAGMENT_BLACKLIST:
        return True, f"碎片化片段: {name}"

    # 3. 时间表噪声（如 07:30___09:00_xxx 或 07:30 - 09:00 xxx）
    if _TIME_NOISE_PATTERN.search(name) or _TIME_NOISE_PATTERN.search(node_id):
        return True, "时间表噪声"

    # 4. 编号列表项（如 1._定义与初始化）
    if _NUMBERED_LIST_PATTERN.match(name) or _NUMBERED_LIST_PATTERN.match(node_id):
        return True, "编号列表项"

    # 5. 纯变量符号（如 d_k, h_i, x_1）
    if _VARIABLE_SYMBOL_PATTERN.match(node_id) and len(node_id) <= 5:
        return True, "变量符号"

    # 6. 含 markdown 标记且去除后为空或过短
    clean_name = _MARKDOWN_PATTERN.sub("", name).strip()
    if len(clean_name) < 2:
        return True, "仅含 markdown 标记"
    # 去除 markdown 后命中黑名单
    if clean_name in _FRAGMENT_BLACKLIST:
        return True, f"碎片化片段(markdown): {clean_name}"

    # 7. 个人事件（行程/用餐/游览等）— 仅当名称中包含这些词且长度 > 4 时
    if len(name) > 4 and _PERSONAL_EVENT_PATTERN.search(name):
        return True, "个人事件"

    # 8. description 是默认的"自动提取自回答内容"且未经过权威校验
    #    这一类不直接过滤，但需要进入 L2/L3 校验
    if "自动提取自回答内容" in description:
        return False, ""  # 进入下一层校验

    # 9. 其他（已通过权威校验或 description 非默认）
    return False, ""


# ============================================================
# KnowledgeAuditor 主体
# ============================================================

class KnowledgeAuditor:
    """知识库质检引擎

    用法：
        auditor = KnowledgeAuditor(skill_graph, llm_client, ws_manager)
        await auditor.audit_all(progress_callback=...)

    质检是异步的，长任务应通过 asyncio.create_task 在后台运行。
    """

    def __init__(
        self,
        skill_graph: SkillGraph,
        llm_client,
        ws_manager=None,
        batch_size: int = 5,
        cloud_concurrency: int = 2,
    ):
        """
        Args:
            skill_graph: SkillGraph 实例
            llm_client: LLMClient 实例（用于 DeepSeek 校验）
            ws_manager: WebSocketManager 实例（用于推送进度），可为 None
            batch_size: 每批处理的节点数（避免一次性占用过多资源）
            cloud_concurrency: DeepSeek 并发请求数（避免触发限流）
        """
        self.skill_graph = skill_graph
        self.llm_client = llm_client
        self.ws_manager = ws_manager
        self.batch_size = batch_size
        self.cloud_concurrency = cloud_concurrency

        # 质检统计
        self.stats = {
            "total": 0,             # 总节点数
            "filtered": 0,          # L1 规则过滤
            "wiki_replaced": 0,     # L2 维基百科替换
            "cloud_replaced": 0,    # L3 DeepSeek 替换
            "removed": 0,           # 校验未通过被删除
            "skipped": 0,           # 跳过（已是权威定义）
            "errors": 0,            # 异常
        }

        # 质检日志（最近 N 条，便于排查）
        self.audit_log: List[dict] = []

        # 是否正在运行（防止并发质检）
        self._running = False

    async def audit_all(
        self,
        progress_callback: Optional[Callable[[dict], Awaitable[None]]] = None,
        only_auto_extracted: bool = True,
    ) -> dict:
        """全量质检 SkillGraph 中所有自学习节点

        Args:
            progress_callback: 进度回调（异步函数，接收 dict）
            only_auto_extracted: True=仅质检"自动提取自回答内容"的节点；
                                 False=质检所有 concept 节点

        Returns:
            质检统计 dict
        """
        if self._running:
            logger.warning("[Auditor] 已有质检任务在运行，跳过本次")
            return {"skipped": True, "reason": "already_running"}

        self._running = True
        self._reset_stats()

        try:
            # 1. 收集需要质检的节点
            candidates = self._collect_candidates(only_auto_extracted)
            self.stats["total"] = len(candidates)
            logger.info(
                f"[Auditor] 开始质检: {len(candidates)} 个候选节点 "
                f"(only_auto_extracted={only_auto_extracted})"
            )

            # V1.1 修复: 无候选节点时不广播 WebSocket 进度，避免空弹窗打扰用户
            if not candidates:
                logger.info(
                    "[Auditor] 无候选节点需要质检，跳过（不推送进度，不弹窗）"
                )
                return self.stats

            await self._notify_progress(
                progress_callback,
                phase="start",
                current=0,
                total=len(candidates),
                message=f"开始质检 {len(candidates)} 个知识点",
            )

            # 2. 分批处理
            sem = asyncio.Semaphore(self.cloud_concurrency)
            processed = 0
            for batch_start in range(0, len(candidates), self.batch_size):
                batch = candidates[batch_start: batch_start + self.batch_size]
                # 并发处理批次
                tasks = [
                    self._audit_one(node, sem, progress_callback, processed + i, len(candidates))
                    for i, node in enumerate(batch)
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                processed += len(batch)

                # 每批结束后持久化（防止中途中断丢失进度）
                self._save_skill_graph()

                # 推送批次进度
                await self._notify_progress(
                    progress_callback,
                    phase="processing",
                    current=processed,
                    total=len(candidates),
                    message=f"已处理 {processed}/{len(candidates)}",
                )

            # 3. 完成
            logger.info(f"[Auditor] 质检完成: {self.stats}")
            await self._notify_progress(
                progress_callback,
                phase="completed",
                current=len(candidates),
                total=len(candidates),
                message=(
                    f"质检完成: 替换 {self.stats['wiki_replaced'] + self.stats['cloud_replaced']} 条, "
                    f"删除 {self.stats['removed']} 条, "
                    f"规则过滤 {self.stats['filtered']} 条"
                ),
                stats=self.stats,
            )

            return self.stats

        except Exception as e:
            logger.error(f"[Auditor] 质检异常: {e}", exc_info=True)
            await self._notify_progress(
                progress_callback,
                phase="error",
                current=0,
                total=self.stats["total"],
                message=f"质检异常: {str(e)}",
            )
            return self.stats
        finally:
            self._running = False

    def _reset_stats(self):
        self.stats = {
            "total": 0, "filtered": 0, "wiki_replaced": 0,
            "cloud_replaced": 0, "removed": 0, "skipped": 0, "errors": 0,
        }
        self.audit_log = []

    def _collect_candidates(self, only_auto_extracted: bool) -> List[GraphNode]:
        """收集需要质检的节点"""
        candidates = []
        for node in self.skill_graph.nodes.values():
            # 仅质检 concept 类型（domain/skill 节点不质检）
            if node.node_type != "concept":
                continue
            if only_auto_extracted:
                # 仅质检 description 含"自动提取自回答内容"的节点
                if "自动提取自回答内容" not in (node.description or ""):
                    continue
            candidates.append(node)
        return candidates

    async def _audit_one(
        self,
        node: GraphNode,
        sem: asyncio.Semaphore,
        progress_callback: Optional[Callable[[dict], Awaitable[None]]],
        index: int,
        total: int,
    ):
        """质检单个节点"""
        try:
            # L1: 规则预过滤
            should_filter, reason = _rule_based_filter(node)
            if should_filter:
                self._remove_node(node.id, f"L1规则过滤: {reason}")
                self.stats["filtered"] += 1
                self._log_audit(node.id, node.name, "filtered", reason)
                return

            # L2 + L3: 权威百科查询（带并发控制）
            async with sem:
                from core.llm.encyclopedia import fetch_authoritative_definition
                definition = await fetch_authoritative_definition(
                    node.name, self.llm_client, use_cloud_fallback=True
                )

            if not definition:
                # 既无维基百科，DeepSeek 也判定非权威术语 → 删除
                self._remove_node(node.id, "L3非权威术语")
                self.stats["removed"] += 1
                self._log_audit(node.id, node.name, "removed", "非权威术语")
                return

            # L4: 替换 description
            old_desc = node.description
            node.description = definition
            # 在 metadata 标记已通过权威校验
            node.metadata["audited"] = True
            node.metadata["audit_time"] = datetime.now().isoformat(timespec="seconds")
            node.metadata["audit_source"] = (
                "wiki" if definition.startswith("[来源: 中文维基百科]")
                else "deepseek"
            )

            if node.metadata["audit_source"] == "wiki":
                self.stats["wiki_replaced"] += 1
                self._log_audit(node.id, node.name, "wiki_replaced", f"维基百科替换 ({len(definition)} 字)")
            else:
                self.stats["cloud_replaced"] += 1
                self._log_audit(node.id, node.name, "cloud_replaced", f"DeepSeek替换 ({len(definition)} 字)")

        except Exception as e:
            logger.warning(f"[Auditor] 节点 {node.id} 质检异常: {e}")
            self.stats["errors"] += 1
            self._log_audit(node.id, node.name, "error", str(e))

    def _remove_node(self, node_id: str, reason: str):
        """删除节点（带日志）"""
        self.skill_graph.remove_node(node_id)
        logger.info(f"[Auditor] 删除节点: {node_id} (原因: {reason})")

    def _log_audit(self, node_id: str, node_name: str, action: str, detail: str):
        """记录质检日志"""
        self.audit_log.append({
            "node_id": node_id,
            "node_name": node_name,
            "action": action,
            "detail": detail,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        # 仅保留最近 200 条
        if len(self.audit_log) > 200:
            self.audit_log = self.audit_log[-200:]

    def _save_skill_graph(self):
        """持久化 SkillGraph 到 yaml"""
        try:
            import os
            yaml_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "graphs", "skill_graph.yaml"
            )
            self.skill_graph.save(yaml_path)
        except Exception as e:
            logger.warning(f"[Auditor] SkillGraph 持久化失败: {e}")

    async def _notify_progress(
        self,
        progress_callback: Optional[Callable[[dict], Awaitable[None]]],
        phase: str,
        current: int,
        total: int,
        message: str,
        stats: Optional[dict] = None,
    ):
        """推送进度（同时通过 WebSocket 和回调）"""
        progress = {
            "phase": phase,        # start | processing | completed | error
            "current": current,
            "total": total,
            "message": message,
            "stats": stats or self.stats,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }

        # 1. 回调
        if progress_callback:
            try:
                await progress_callback(progress)
            except Exception as e:
                logger.warning(f"[Auditor] 进度回调异常: {e}")

        # 2. WebSocket 广播
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast_audit_progress(progress)
            except Exception as e:
                logger.warning(f"[Auditor] WebSocket 推送异常: {e}")


# ============================================================
# 全局单例（懒加载）
# ============================================================

_auditor_instance: Optional[KnowledgeAuditor] = None


def get_knowledge_auditor(
    skill_graph=None,
    llm_client=None,
    ws_manager=None,
) -> KnowledgeAuditor:
    """获取 KnowledgeAuditor 全局单例

    首次调用时需要传入 skill_graph 和 llm_client；
    后续调用可省略参数，返回已创建的实例。
    """
    global _auditor_instance
    if _auditor_instance is None:
        if skill_graph is None:
            from core.graphs import get_skill_graph
            skill_graph = get_skill_graph()
        if llm_client is None:
            from core.llm.client import get_llm_client
            llm_client = get_llm_client()
        _auditor_instance = KnowledgeAuditor(skill_graph, llm_client, ws_manager)
    # 更新 ws_manager（每次调用都用最新的）
    if ws_manager is not None:
        _auditor_instance.ws_manager = ws_manager
    return _auditor_instance
