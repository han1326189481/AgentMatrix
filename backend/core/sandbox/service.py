"""Sandbox 服务 — 多沙盒管理

架构:
- 沙盒元数据存储在全局 SQLite (agentmatrix.db) 的 sandboxes 表
- 每个沙盒拥有独立的 SQLite 数据库 (storage/sandboxes/{sandbox_id}.db)
- 对话历史和工作流记录存储在沙盒专属数据库中
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging
from sqlalchemy.orm import Session

from app.database import get_global_session, get_sandbox_session, delete_sandbox_db
from models.db_models import Sandbox, ChatMessage, WorkflowExecution, WorkflowStepRecord, ChatSession

logger = logging.getLogger(__name__)


class SandboxService:
    """沙盒管理服务"""

    @staticmethod
    def create(name: str = "新对话") -> dict:
        """创建新沙盒"""
        session = get_global_session()
        try:
            sandbox_id = str(uuid.uuid4())[:8]
            sandbox = Sandbox(
                id=sandbox_id,
                name=name,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(sandbox)
            session.commit()

            # 触发沙盒数据库创建（建表）
            get_sandbox_session(sandbox_id).close()

            logger.info(f"Sandbox created: id={sandbox_id}, name={name}")
            return {
                "id": sandbox_id,
                "name": name,
                "created_at": sandbox.created_at.isoformat(),
                "updated_at": sandbox.updated_at.isoformat(),
                "message_count": 0,
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create sandbox: {e}")
            raise
        finally:
            session.close()

    @staticmethod
    def list_sandboxes(include_inactive: bool = False) -> List[dict]:
        """列出所有沙盒"""
        session = get_global_session()
        try:
            query = session.query(Sandbox)
            if not include_inactive:
                query = query.filter(Sandbox.is_active == True)
            sandboxes = query.order_by(Sandbox.updated_at.desc()).all()
            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                    "message_count": s.message_count or 0,
                }
                for s in sandboxes
            ]
        finally:
            session.close()

    @staticmethod
    def get(sandbox_id: str) -> Optional[dict]:
        """获取沙盒详情"""
        session = get_global_session()
        try:
            sandbox = session.query(Sandbox).filter(Sandbox.id == sandbox_id).first()
            if not sandbox:
                return None
            return {
                "id": sandbox.id,
                "name": sandbox.name,
                "created_at": sandbox.created_at.isoformat() if sandbox.created_at else None,
                "updated_at": sandbox.updated_at.isoformat() if sandbox.updated_at else None,
                "message_count": sandbox.message_count or 0,
            }
        finally:
            session.close()

    @staticmethod
    def rename(sandbox_id: str, name: str) -> bool:
        """重命名沙盒"""
        session = get_global_session()
        try:
            sandbox = session.query(Sandbox).filter(Sandbox.id == sandbox_id).first()
            if not sandbox:
                return False
            sandbox.name = name
            sandbox.updated_at = datetime.utcnow()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to rename sandbox: {e}")
            raise
        finally:
            session.close()

    @staticmethod
    def delete(sandbox_id: str) -> bool:
        """删除沙盒（软删除 + 删除数据库文件）"""
        session = get_global_session()
        try:
            sandbox = session.query(Sandbox).filter(Sandbox.id == sandbox_id).first()
            if not sandbox:
                return False
            sandbox.is_active = False
            sandbox.updated_at = datetime.utcnow()
            session.commit()

            # 删除沙盒数据库文件
            delete_sandbox_db(sandbox_id)

            logger.info(f"Sandbox deleted: id={sandbox_id}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete sandbox: {e}")
            raise
        finally:
            session.close()

    @staticmethod
    def increment_message_count(sandbox_id: str) -> bool:
        """增加沙盒消息计数"""
        session = get_global_session()
        try:
            sandbox = session.query(Sandbox).filter(Sandbox.id == sandbox_id).first()
            if not sandbox:
                return False
            sandbox.message_count = (sandbox.message_count or 0) + 1
            sandbox.updated_at = datetime.utcnow()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to increment message count: {e}")
            return False
        finally:
            session.close()

    @staticmethod
    def get_chat_history(sandbox_id: str, limit: int = 20) -> List[dict]:
        """获取沙盒的对话历史（从沙盒专属数据库）"""
        try:
            session = get_sandbox_session(sandbox_id)
            try:
                messages = (
                    session.query(ChatMessage)
                    .order_by(ChatMessage.timestamp.desc())
                    .limit(limit)
                    .all()
                )
                return [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content[:500] if m.content else "",
                        "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                    }
                    for m in reversed(messages)
                ]
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Failed to get chat history for sandbox {sandbox_id}: {e}")
            return []

    @staticmethod
    def save_chat_message(sandbox_id: str, role: str, content: str) -> bool:
        """保存聊天消息到沙盒专属数据库"""
        try:
            session = get_sandbox_session(sandbox_id)
            try:
                # 确保沙盒数据库中存在 ChatSession 记录（FK 约束）
                existing = session.query(ChatSession).filter(ChatSession.id == sandbox_id).first()
                if not existing:
                    session.add(ChatSession(
                        id=sandbox_id,
                        user_id="default",
                        title=f"沙盒 {sandbox_id}",
                    ))
                    session.flush()

                msg = ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=sandbox_id,
                    role=role,
                    content=content,
                    timestamp=datetime.utcnow(),
                )
                session.add(msg)
                session.commit()
                return True
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Failed to save chat message for sandbox {sandbox_id}: {e}")
            return False

    @staticmethod
    def save_workflow_execution(
        sandbox_id: str,
        user_input: str,
        final_result: str,
        executed_locally: bool,
        complexity_score: float,
        total_duration: float,
        steps: List[dict],
    ) -> bool:
        """保存工作流执行记录到沙盒专属数据库

        Args:
            sandbox_id: 沙盒 ID
            user_input: 用户输入
            final_result: 最终结果
            executed_locally: 是否本地执行
            complexity_score: 复杂度评分
            total_duration: 总耗时（秒）
            steps: 工作流步骤列表，每个元素为 dict，包含:
                agent_id, agent_name, input, output, success, duration_seconds
        """
        try:
            session = get_sandbox_session(sandbox_id)
            try:
                # 确保沙盒数据库中存在 ChatSession 记录（FK 约束）
                existing = session.query(ChatSession).filter(
                    ChatSession.id == sandbox_id
                ).first()
                if not existing:
                    session.add(ChatSession(
                        id=sandbox_id,
                        user_id="default",
                        title=f"沙盒 {sandbox_id}",
                    ))
                    session.flush()

                execution_id = str(uuid.uuid4())
                execution = WorkflowExecution(
                    id=execution_id,
                    session_id=sandbox_id,
                    user_input=user_input,
                    final_result=final_result,
                    executed_locally=executed_locally,
                    complexity_score=complexity_score,
                    total_duration=total_duration,
                    created_at=datetime.utcnow(),
                )
                session.add(execution)
                session.flush()  # 确保 execution_id 可被 steps 引用

                # 写入每个 Agent 步骤
                for idx, step in enumerate(steps):
                    step_record = WorkflowStepRecord(
                        id=str(uuid.uuid4()),
                        execution_id=execution_id,
                        agent_id=step.get("agent_id", ""),
                        agent_name=step.get("agent_name", ""),
                        input_content=step.get("input", ""),
                        output_content=step.get("output", ""),
                        success=step.get("success", False),
                        duration=step.get("duration_seconds", 0.0),
                        step_order=idx,
                    )
                    session.add(step_record)

                session.commit()
                logger.info(
                    f"Saved workflow execution {execution_id} to sandbox "
                    f"{sandbox_id} ({len(steps)} steps)"
                )
                return True
            finally:
                session.close()
        except Exception as e:
            logger.warning(
                f"Failed to save workflow execution for sandbox {sandbox_id}: {e}"
            )
            return False

    @staticmethod
    def get_workflow_executions(sandbox_id: str, limit: int = 20) -> List[dict]:
        """获取沙盒的工作流执行记录（按时间倒序）"""
        try:
            session = get_sandbox_session(sandbox_id)
            try:
                executions = (
                    session.query(WorkflowExecution)
                    .order_by(WorkflowExecution.created_at.desc())
                    .limit(limit)
                    .all()
                )
                return [
                    {
                        "id": e.id,
                        "session_id": e.session_id,
                        "user_input": e.user_input[:200] if e.user_input else "",
                        "final_result": e.final_result[:200] if e.final_result else "",
                        "executed_locally": e.executed_locally,
                        "complexity_score": e.complexity_score,
                        "total_duration": e.total_duration,
                        "created_at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in executions
                ]
            finally:
                session.close()
        except Exception as e:
            logger.warning(
                f"Failed to get workflow executions for sandbox {sandbox_id}: {e}"
            )
            return []


# 全局单例
_sandbox_service: Optional[SandboxService] = None


def get_sandbox_service() -> SandboxService:
    global _sandbox_service
    if _sandbox_service is None:
        _sandbox_service = SandboxService()
    return _sandbox_service