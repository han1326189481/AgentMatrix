"""file_ops — 安全沙盒文件操作（V4.5）

硬约束:
- 根目录锁定: 仅允许 {data_dir}/workspace/ 及其子目录
- 写前备份: 覆盖/修改前自动存 .bak（保留最近 1 版）
- 删除即回收站: 移入 {data_dir}/trash/{timestamp}/，不真删
- 破坏性操作需 confirm 标志（由 API 层校验）
- 体积限制: 单文件 < 20MB，目录递归上限 500 项
"""
import os
import shutil
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from shared.platform import get_data_dir

logger = logging.getLogger(__name__)

# ── 常量 ──
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
MAX_SCAN_ITEMS = 500              # 目录递归上限
TEXT_EXTS = {".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".py", ".js",
             ".ts", ".html", ".css", ".xml", ".log", ".ini", ".toml"}


class FileOpsError(Exception):
    """文件操作错误（API 层转 HTTPException）"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def get_workspace_dir() -> Path:
    """workspace 根目录（自动创建）"""
    path = Path(get_data_dir()) / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_trash_dir() -> Path:
    """回收站根目录（按时间戳建子目录）"""
    path = Path(get_data_dir()) / "trash"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_in_workspace(rel_path: str, must_exist: bool = False) -> Path:
    """把相对路径解析为 workspace 内的绝对路径，拒绝越界（路径穿越防护）"""
    if rel_path is None or rel_path.strip() in {"", "/"}:
        raise FileOpsError("路径不能为空", 400)
    ws = get_workspace_dir().resolve()
    # "." / "" / "/" 都指 workspace 根
    if rel_path.strip() in {".", "./"}:
        return ws
    target = (ws / rel_path).resolve()
    # Windows 大小写不敏感前缀比较
    if not str(target).lower().startswith(str(ws).lower() + os.sep.lower()) and target != ws:
        raise FileOpsError(f"禁止访问 workspace 之外的路径: {rel_path}", 403)
    if must_exist and not target.exists():
        raise FileOpsError(f"文件或目录不存在: {rel_path}", 404)
    return target


def _backup_if_exists(target: Path) -> Optional[Path]:
    """写前备份（同目录 .bak，保留最近 1 版）"""
    if not target.exists() or not target.is_file():
        return None
    bak = target.with_suffix(target.suffix + ".bak")
    shutil.copy2(target, bak)
    return bak


def list_dir(rel_path: str = ".") -> Dict[str, Any]:
    """列目录（含子目录树，限 MAX_SCAN_ITEMS 项）"""
    root = _resolve_in_workspace(rel_path, must_exist=True)
    if not root.is_dir():
        raise FileOpsError(f"不是目录: {rel_path}", 400)

    items: List[Dict[str, Any]] = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # 排除备份文件与隐藏目录
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in sorted(dirnames):
            count += 1
            if count > MAX_SCAN_ITEMS:
                return {"path": rel_path, "items": items, "truncated": True, "count": len(items)}
            full = Path(dirpath) / name
            items.append({
                "name": name,
                "rel_path": str(full.relative_to(get_workspace_dir())).replace("\\", "/"),
                "type": "directory",
                "size_bytes": 0,
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(full.stat().st_mtime)),
            })
        for name in sorted(filenames):
            if name.endswith(".bak") or name.startswith("."):
                continue
            count += 1
            if count > MAX_SCAN_ITEMS:
                return {"path": rel_path, "items": items, "truncated": True, "count": len(items)}
            full = Path(dirpath) / name
            items.append({
                "name": name,
                "rel_path": str(full.relative_to(get_workspace_dir())).replace("\\", "/"),
                "type": "file",
                "size_bytes": full.stat().st_size,
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(full.stat().st_mtime)),
            })
    return {"path": rel_path, "items": items, "truncated": False, "count": len(items)}


def read_file(rel_path: str) -> Dict[str, Any]:
    """读文本文件内容（限文本后缀，≤5MB）"""
    target = _resolve_in_workspace(rel_path, must_exist=True)
    if not target.is_file():
        raise FileOpsError(f"不是文件: {rel_path}", 400)
    if target.suffix.lower() not in TEXT_EXTS:
        raise FileOpsError(f"仅支持读取文本类型文件（{', '.join(sorted(TEXT_EXTS))}），当前: {target.suffix}", 400)
    if target.stat().st_size > 5 * 1024 * 1024:
        raise FileOpsError("文件过大（>5MB），不支持在线读取", 400)
    content = target.read_text(encoding="utf-8", errors="replace")
    return {"path": rel_path, "content": content, "size_bytes": target.stat().st_size}


def write_file(rel_path: str, content: str, confirm_overwrite: bool = False) -> Dict[str, Any]:
    """写/创建文件（覆盖已有文件需 confirm_overwrite，写前自动 .bak 备份）"""
    target = _resolve_in_workspace(rel_path)
    if target.exists() and target.is_file():
        if not confirm_overwrite:
            raise FileOpsError("文件已存在，需 confirm_overwrite=true 才能覆盖", 409)
        _backup_if_exists(target)
    if len(content.encode("utf-8")) > MAX_FILE_SIZE:
        raise FileOpsError("内容超过 20MB 限制", 400)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    logger.info(f"file_ops.write: {rel_path} ({len(content)} chars)")
    return {"status": "success", "path": rel_path, "size_bytes": target.stat().st_size}


def write_bytes(rel_path: str, data: bytes) -> Dict[str, Any]:
    """写二进制文件（上传 docx/pptx 等场景，内部接口不走 confirm 因为是新写入）"""
    target = _resolve_in_workspace(rel_path)
    if target.exists() and target.is_file():
        _backup_if_exists(target)
    if len(data) > MAX_FILE_SIZE:
        raise FileOpsError("文件超过 20MB 限制", 400)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    logger.info(f"file_ops.write_bytes: {rel_path} ({len(data)} bytes)")
    return {"status": "success", "path": rel_path, "size_bytes": len(data)}


def move_path(rel_path: str, new_rel_path: str, confirm_overwrite: bool = False) -> Dict[str, Any]:
    """移动/重命名（目标存在需 confirm_overwrite）"""
    src = _resolve_in_workspace(rel_path, must_exist=True)
    dst = _resolve_in_workspace(new_rel_path)
    if src == dst:
        raise FileOpsError("源路径与目标路径相同", 400)
    if dst.exists():
        if not confirm_overwrite:
            raise FileOpsError("目标已存在，需 confirm_overwrite=true 才能覆盖", 409)
        if dst.is_file():
            _backup_if_exists(dst)
        else:
            raise FileOpsError("目标是已存在的目录，拒绝覆盖", 400)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    logger.info(f"file_ops.move: {rel_path} -> {new_rel_path}")
    return {"status": "success", "from": rel_path, "to": new_rel_path}


def delete_path(rel_path: str, confirm: bool = False) -> Dict[str, Any]:
    """删除（移入回收站，必须 confirm=true）"""
    if not confirm:
        raise FileOpsError("删除是破坏性操作，必须 confirm=true", 403)
    target = _resolve_in_workspace(rel_path, must_exist=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    trash_dest = get_trash_dir() / ts / target.name
    trash_dest.parent.mkdir(parents=True, exist_ok=True)
    # 同名冲突自动追加序号
    n = 1
    while trash_dest.exists():
        trash_dest = trash_dest.with_name(f"{target.name}.{n}")
        n += 1
    shutil.move(str(target), str(trash_dest))
    logger.info(f"file_ops.delete: {rel_path} -> trash {trash_dest}")
    return {"status": "success", "path": rel_path, "trash_path": str(trash_dest)}


def search_files(pattern: str, rel_dir: str = ".") -> Dict[str, Any]:
    """按文件名子串/后缀搜索"""
    root = _resolve_in_workspace(rel_dir, must_exist=True)
    pattern_lower = pattern.lower()
    matches: List[Dict[str, Any]] = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            count += 1
            if count > MAX_SCAN_ITEMS * 4:
                return {"pattern": pattern, "matches": matches, "truncated": True, "count": len(matches)}
            if pattern_lower in name.lower():
                full = Path(dirpath) / name
                matches.append({
                    "name": name,
                    "rel_path": str(full.relative_to(get_workspace_dir())).replace("\\", "/"),
                    "size_bytes": full.stat().st_size,
                })
    return {"pattern": pattern, "matches": matches, "truncated": False, "count": len(matches)}


def resolve_workspace_path(rel_path: str) -> Path:
    """给引擎内部模块用的路径解析（同安全校验）"""
    return _resolve_in_workspace(rel_path, must_exist=True)
