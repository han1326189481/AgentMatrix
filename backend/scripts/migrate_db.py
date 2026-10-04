"""数据库迁移脚本 — 为已有用户添加缺失的表

用法:
    python scripts/migrate_db.py           # 检查并迁移
    python scripts/migrate_db.py --dry-run  # 仅检查，不实际执行
    python scripts/migrate_db.py --force    # 强制重建所有表

场景:
    1. 旧版本数据库缺少 sandboxes 表 → 自动添加
    2. 未来新增表 → 自动检测并添加
    3. 数据库文件损坏 → 提示备份后重建
"""
import os
import sys
import argparse
import logging
from datetime import datetime

# 添加 backend 目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_and_migrate(dry_run: bool = False, force: bool = False):
    """检查数据库状态并执行迁移"""
    import models.db_models  # noqa: F401 — 触发所有模型注册到 Base.metadata
    from app.database import get_global_engine, Base
    from shared.platform import get_db_path

    db_path = get_db_path()
    logger.info(f"数据库路径: {db_path}")

    if not os.path.exists(db_path):
        logger.info("数据库文件不存在，将在首次启动时自动创建")
        return True

    engine = get_global_engine()

    # 检查数据库中已存在的表
    from sqlalchemy import inspect
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    # 检查 Base.metadata 中定义的所有表
    expected_tables = set(Base.metadata.tables.keys())
    missing_tables = expected_tables - existing_tables

    logger.info(f"已存在的表: {sorted(existing_tables)}")
    logger.info(f"期望的表: {sorted(expected_tables)}")

    if missing_tables:
        logger.warning(f"缺失的表: {sorted(missing_tables)}")
    else:
        logger.info("所有表已存在，无需迁移")
        return True

    if dry_run:
        logger.info("[DRY RUN] 不会实际执行迁移")
        return True

    if force:
        logger.info("强制重建模式：删除所有表并重建")
        Base.metadata.drop_all(bind=engine)
        logger.info("旧表已删除")

    # 创建缺失的表（create_all 会自动跳过已存在的表）
    try:
        Base.metadata.create_all(bind=engine)
        # 再次检查
        inspector = inspect(engine)
        new_tables = set(inspector.get_table_names())
        still_missing = expected_tables - new_tables

        if still_missing:
            logger.error(f"迁移后仍缺失的表: {sorted(still_missing)}")
            return False

        logger.info(f"迁移成功！当前表: {sorted(new_tables)}")
        return True
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        return False


def backup_database():
    """备份当前数据库"""
    from shared.platform import get_db_path, get_backups_dir
    import shutil

    db_path = get_db_path()
    if not os.path.exists(db_path):
        logger.info("数据库文件不存在，跳过备份")
        return None

    backup_dir = get_backups_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"agentmatrix_pre_migrate_{timestamp}.db")
    shutil.copy2(db_path, backup_path)
    logger.info(f"数据库已备份到: {backup_path}")
    return backup_path


def main():
    parser = argparse.ArgumentParser(description="AgentMatrix 数据库迁移工具")
    parser.add_argument("--dry-run", action="store_true", help="仅检查，不执行迁移")
    parser.add_argument("--force", action="store_true", help="强制重建所有表（会删除数据）")
    parser.add_argument("--backup", action="store_true", help="迁移前备份数据库")
    args = parser.parse_args()

    if args.backup:
        backup_database()

    success = check_and_migrate(dry_run=args.dry_run, force=args.force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()