"""清理对话历史数据，保留知识库"""
import sqlite3
import os
from shared.platform import get_db_path

db_path = get_db_path()
print(f"数据库路径: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查看所有表及记录数
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f"\n现有表:")
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {t}")
    count = cursor.fetchone()[0]
    print(f"  {t}: {count} 条记录")

# 要清空的表（对话历史 + 工作流执行记录）
chat_tables = ["chat_messages", "chat_sessions", "sandboxes", "workflow_executions", "workflow_steps"]

print(f"\n--- 清空对话历史表 ---")
for table in chat_tables:
    if table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        cursor.execute(f"DELETE FROM {table}")
        print(f"清空 {table}: 删除 {count} 条记录")

# 验证知识库保留
print(f"\n--- 知识库保留 ---")
for kb_table in ["knowledge_entries", "knowledge_base"]:
    if kb_table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {kb_table}")
        count = cursor.fetchone()[0]
        print(f"保留 {kb_table}: {count} 条记录")

conn.commit()
conn.close()

# 显式清理 IntentCache（内存缓存，避免返回旧模型生成的结果）
print(f"\n--- 清理 IntentCache 内存缓存 ---")
try:
    from core.skill_engine.intent_cache import get_intent_cache
    cache = get_intent_cache()
    stats_before = cache.get_stats()
    cache.clear()  # 清除 L1 + L2
    print(f"IntentCache 已清除 (L1: {stats_before['l1_skill_path']['size']} 条, L2: {stats_before['l2_result']['size']} 条)")
except Exception as e:
    print(f"IntentCache 清理跳过: {e}")

print("\n对话历史清理完成")