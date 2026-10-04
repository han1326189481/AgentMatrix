"""数据库层 — 纯 SQLite 引擎（零配置，打开即用）

架构:
- 全局库: storage/agentmatrix.db（知识库、指标、沙盒元数据）
- 沙盒库: storage/sandboxes/{sandbox_id}.db（对话历史、工作流记录）
"""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from shared.platform import get_db_path, get_sandbox_db_path, get_backups_dir
import logging
import shutil
import os
from datetime import datetime

logger = logging.getLogger(__name__)

Base = declarative_base()

# ── 全局引擎（单例） ──
_global_engine = None
_global_SessionLocal = None

# ── 沙盒引擎池（sandbox_id → engine） ──
_sandbox_engines: dict = {}


def _build_sqlite_url(db_path: str) -> str:
    """构建 SQLite 连接 URL"""
    return f"sqlite:///{db_path}"


def _create_sqlite_engine(db_path: str) -> tuple:
    """创建 SQLite 引擎 + SessionLocal"""
    # V3.5.1: 打包环境首次启动时清理可能残留的 -shm/-wal 文件
    # 这些文件在非正常关闭后可能损坏，导致 disk I/O error
    for suffix in ['-shm', '-wal']:
        wal_path = db_path + suffix
        if os.path.exists(wal_path):
            try:
                os.remove(wal_path)
                logger.debug(f"Cleaned stale SQLite file: {wal_path}")
            except Exception:
                pass  # 忽略删除失败（文件可能被锁定，SQLite 会自动恢复）

    engine = create_engine(
        _build_sqlite_url(db_path),
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # 启用 WAL 模式（Write-Ahead Logging）：更好的并发 + 崩溃恢复
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


def _auto_backup():
    """自动备份全局数据库（保留最近 3 个版本）"""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return
    try:
        backup_dir = get_backups_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"agentmatrix_{timestamp}.db")
        shutil.copy2(db_path, backup_path)
        logger.info(f"Database backup created: {backup_path}")

        # 清理旧备份（保留最近 3 个）
        backups = sorted(
            [f for f in os.listdir(backup_dir) if f.startswith("agentmatrix_")],
            reverse=True
        )
        for old in backups[3:]:
            os.remove(os.path.join(backup_dir, old))
            logger.debug(f"Old backup removed: {old}")
    except Exception as e:
        logger.warning(f"Auto backup failed (non-fatal): {e}")


# ── 全局数据库 API ──

def get_global_engine():
    """获取全局数据库引擎"""
    global _global_engine, _global_SessionLocal
    if _global_engine is not None:
        return _global_engine

    db_url = settings.database_url
    if db_url and ("mysql" in db_url.lower() or "pymysql" in db_url.lower()):
        # 用户显式配置了 MySQL，保留兼容
        _global_engine = create_engine(
            db_url,
            pool_size=10, max_overflow=20,
            pool_recycle=3600, pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
        logger.info("MySQL engine created (user configured)")
    else:
        db_path = get_db_path()
        logger.info(f"Using SQLite database: {db_path}")
        _global_engine, _global_SessionLocal = _create_sqlite_engine(db_path)

    return _global_engine


def get_global_session_local():
    """获取全局 SessionLocal"""
    global _global_SessionLocal
    if _global_SessionLocal is not None:
        return _global_SessionLocal
    get_global_engine()
    return _global_SessionLocal


def get_global_session() -> Session:
    """获取全局数据库会话"""
    return get_global_session_local()()


def init_global_db():
    """初始化全局数据库表"""
    try:
        # 确保所有模型已注册到 Base.metadata（必须在 create_all 之前导入）
        import models.db_models  # noqa: F401 — 触发 Sandbox 等模型注册
        import models.timely_knowledge  # noqa: F401 — V3.5: 时效性知识库表

        engine = get_global_engine()
        Base.metadata.create_all(bind=engine)
        logger.info("Global database tables created successfully")
        _auto_backup()
    except Exception as e:
        logger.error(f"Failed to initialize global database: {e}")
        raise


# ── 沙盒数据库 API ──

def get_sandbox_engine(sandbox_id: str):
    """获取沙盒专属数据库引擎"""
    if sandbox_id in _sandbox_engines:
        return _sandbox_engines[sandbox_id]

    db_path = get_sandbox_db_path(sandbox_id)
    logger.info(f"Creating sandbox database: {db_path}")
    engine, _ = _create_sqlite_engine(db_path)

    # 在沙盒数据库中创建表
    Base.metadata.create_all(bind=engine)

    _sandbox_engines[sandbox_id] = engine
    return engine


def get_sandbox_session(sandbox_id: str) -> Session:
    """获取沙盒数据库会话"""
    engine = get_sandbox_engine(sandbox_id)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def delete_sandbox_db(sandbox_id: str):
    """删除沙盒数据库文件"""
    db_path = get_sandbox_db_path(sandbox_id)
    # 关闭引擎
    if sandbox_id in _sandbox_engines:
        _sandbox_engines[sandbox_id].dispose()
        del _sandbox_engines[sandbox_id]
    # 删除文件
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info(f"Sandbox database deleted: {db_path}")
    # 同时删除 WAL/SHM 文件
    for suffix in ['-wal', '-shm']:
        wal_path = db_path + suffix
        if os.path.exists(wal_path):
            os.remove(wal_path)


def get_engine():
    """兼容旧代码：返回全局引擎"""
    return get_global_engine()


def get_session_local():
    """兼容旧代码：返回全局 SessionLocal"""
    return get_global_session_local()


async def get_db():
    """FastAPI 依赖注入：获取全局数据库会话"""
    session = get_global_session()
    try:
        yield session
    finally:
        session.close()


def init_db():
    """兼容旧代码：初始化全局数据库"""
    init_global_db()