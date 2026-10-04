#!/usr/bin/env python
"""SQLite 一致性备份工具（供 scripts/backup.ps1 调用）。

用法:
    python db_backup.py <src.db> <dst.db>

为什么不能直接 Copy-Item 复制 .db：
    运行时 SQLite 处于 WAL 模式，未 checkpoint 的数据只存在于
    `-wal` 文件里。直接复制 .db 会得到一个残缺（甚至损坏）的快照。
    sqlite3 的 backup API 在事务一致性点上完成拷贝，自动包含 WAL，
    且不需要停服、不阻塞写入。

退出码:
    0 成功 / 1 异常 / 2 参数错误 / 3 源文件不存在 / 4 完整性校验失败
"""

from __future__ import annotations

import os
import sqlite3
import sys


def backup(src: str, dst: str) -> int:
    if not os.path.exists(src):
        print(f"src-not-found: {src}", file=sys.stderr)
        return 3

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)

    # 以只读方式打开源库，杜绝备份过程意外写入生产库
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        dst_conn = sqlite3.connect(dst)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    size = os.path.getsize(dst)

    # 对备份结果做完整性自检，不合格不算成功
    chk = sqlite3.connect(dst)
    try:
        row = chk.execute("PRAGMA integrity_check").fetchone()
        ok = bool(row) and row[0] == "ok"
    finally:
        chk.close()

    print(f"ok bytes={size} integrity={'ok' if ok else 'FAIL'}")
    return 0 if ok else 4


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        return backup(sys.argv[1], sys.argv[2])
    except Exception as exc:  # noqa: BLE001 - 工具脚本，异常统一转退出码
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
