"""AuditScheduler — 知识库质检触发器 V1.1

触发机制（V1.1 修复：AND 逻辑）：
必须**同时满足**两个条件才触发质检：
1. 计数条件：新增永久化知识点累计 >= N 个（默认 N=10）
2. 空闲条件：用户超过 T 秒无新请求（默认 T=120s，即 2 分钟）

V1.0 → V1.1 变更（2026-07-30）：
- 修复: 原逻辑为 OR（任一条件满足即触发），导致用户问了几个问题后
  空闲超时单独触发弹窗，且无候选节点时显示"0/0"。改为 AND 逻辑。
- 修复: 移除启动时立即触发的全量校验（source=initial），
  必须等待两个条件同时满足才触发。
- 修复: 无候选节点时不再广播 WebSocket 进度，避免空弹窗打扰用户。

设计要点：
- 仅在用户"空闲"时触发，避免干扰正在进行的对话
- 后台 asyncio.Task 实现，不阻塞主请求
- 同一时刻仅允许一个质检任务运行（通过 KnowledgeAuditor._running 保护）

集成位置：
- 在 WorkflowService.execute 中调用 record_user_activity()
- 在 LearningEngine.apply_patches 后调用 record_knowledge_added(count)
- 在 app.main.py lifespan 中调用 start_audit_scheduler()
"""
import asyncio
import logging
import time
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class AuditScheduler:
    """知识库质检调度器

    用法：
        scheduler = AuditScheduler(audit_func)
        await scheduler.start()  # 启动后台任务
        scheduler.record_knowledge_added(3)  # 新增 3 个知识点
        scheduler.record_user_activity()      # 用户发起新请求
        await scheduler.stop()  # 关闭时调用
    """

    def __init__(
        self,
        audit_func: Callable[[], Awaitable[None]],
        knowledge_threshold: int = 10,
        idle_timeout_seconds: float = 120.0,
        check_interval: float = 30.0,
    ):
        """
        Args:
            audit_func: 质检函数（异步，无参数；内部由 KnowledgeAuditor.audit_all 实现）
            knowledge_threshold: 新增知识点计数阈值，达到则触发
            idle_timeout_seconds: 用户空闲多久后触发定时质检
            check_interval: 后台轮询间隔（秒）
        """
        self.audit_func = audit_func
        self.knowledge_threshold = knowledge_threshold
        self.idle_timeout_seconds = idle_timeout_seconds
        self.check_interval = check_interval

        # 计数器
        self._knowledge_counter = 0
        # 最后一次用户活动时间
        self._last_activity_time = time.monotonic()
        # 后台任务
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        # 防止并发质检
        self._auditing = False
        # 首次启动是否已执行过全量校验
        self._initial_audit_done = False

    def record_knowledge_added(self, count: int = 1):
        """记录新增的永久化知识点数量"""
        if count <= 0:
            return
        self._knowledge_counter += count
        logger.info(
            f"[AuditScheduler] 新增知识点计数: {self._knowledge_counter}/"
            f"{self.knowledge_threshold}"
        )

    def record_user_activity(self):
        """记录用户活动（发起新请求）"""
        self._last_activity_time = time.monotonic()

    async def start(self, run_initial_audit: bool = True):
        """启动后台调度任务

        V1.1 修复: 移除启动时立即触发的全量校验。
        必须等待"新增知识点>=阈值 AND 用户空闲超时"两个条件同时满足才触发。

        Args:
            run_initial_audit: 已废弃（V1.1 起不再启动时触发），保留参数仅为向后兼容
        """
        if self._task is not None and not self._task.done():
            logger.warning("[AuditScheduler] 已有调度任务在运行")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        # V1.1: 不再在启动时立即触发全量校验
        # 原行为: asyncio.create_task(self._trigger_audit(source="initial"))
        # 问题: 刚启动时无候选节点，弹窗显示"0/0"，打扰用户

    async def stop(self):
        """停止后台调度任务"""
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self):
        """后台调度循环（V1.1: AND 逻辑）

        必须同时满足两个条件才触发质检：
        1. 新增知识点计数 >= knowledge_threshold
        2. 用户空闲时间 >= idle_timeout_seconds
        """
        logger.info(
            f"[AuditScheduler] 调度器已启动 (AND逻辑) "
            f"(阈值={self.knowledge_threshold}, 空闲超时={self.idle_timeout_seconds}s)"
        )
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.check_interval
                )
            except asyncio.TimeoutError:
                pass  # 正常超时，继续检查

            if self._stop_event.is_set():
                break

            # V1.1: AND 逻辑 — 两个条件同时满足才触发
            idle_seconds = time.monotonic() - self._last_activity_time
            counter_ready = self._knowledge_counter >= self.knowledge_threshold
            idle_ready = idle_seconds >= self.idle_timeout_seconds

            if counter_ready and idle_ready:
                # 重置计数器和活动时间，避免循环触发
                self._knowledge_counter = 0
                self._last_activity_time = time.monotonic()
                await self._trigger_audit(source="threshold_and_idle")
            elif counter_ready and not idle_ready:
                # 计数已满但用户仍活跃，等待空闲
                logger.debug(
                    f"[AuditScheduler] 计数已满({self._knowledge_counter}) "
                    f"但用户活跃中(空闲{idle_seconds:.0f}s/{self.idle_timeout_seconds}s)，等待空闲"
                )
            elif idle_ready and not counter_ready:
                # 用户空闲但计数不足，跳过（不弹窗）
                logger.debug(
                    f"[AuditScheduler] 用户空闲{idle_seconds:.0f}s "
                    f"但计数不足({self._knowledge_counter}/{self.knowledge_threshold})，跳过"
                )

    async def _trigger_audit(self, source: str):
        """触发一次质检（防止并发）"""
        if self._auditing:
            logger.info(f"[AuditScheduler] 质检进行中，跳过本次触发 (source={source})")
            return

        self._auditing = True
        logger.info(f"[AuditScheduler] 触发质检 (source={source})")
        try:
            await self.audit_func()
        except Exception as e:
            logger.error(f"[AuditScheduler] 质检异常: {e}", exc_info=True)
        finally:
            self._auditing = False


# ============================================================
# 全局单例
# ============================================================

_scheduler_instance: Optional[AuditScheduler] = None


def get_audit_scheduler(
    audit_func: Optional[Callable[[], Awaitable[None]]] = None,
) -> AuditScheduler:
    """获取 AuditScheduler 全局单例

    首次调用时需要传入 audit_func；后续调用可省略。
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        if audit_func is None:
            # 默认 audit_func: 调用 KnowledgeAuditor.audit_all
            async def _default_audit_func():
                from core.engines.knowledge_auditor import get_knowledge_auditor
                from app.main import app
                ws_manager = getattr(app.state, 'ws_manager', None)
                auditor = get_knowledge_auditor(ws_manager=ws_manager)
                await auditor.audit_all(only_auto_extracted=True)

            audit_func = _default_audit_func
        _scheduler_instance = AuditScheduler(audit_func)
    return _scheduler_instance
