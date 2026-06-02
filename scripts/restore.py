#!/usr/bin/env python3
"""一键恢复到指定备份点。

用法:
    python scripts/restore.py --list                   # 列出可用备份
    python scripts/restore.py --latest                 # 恢复到最新备份
    python scripts/restore.py --file <filename>        # 恢复到指定备份
    python scripts/restore.py --date 2026-06-01        # 恢复到指定日期（最近的一个备份）

环境变量:
    BACKUP_DIR   备份文件存储路径（默认: ./data/backups）
    DB_HOST      数据库主机
    DB_PORT      数据库端口
    DB_USER      数据库用户
    DB_PASSWORD  数据库密码
    DB_NAME      数据库名称

依赖:
    pg_restore (PostgreSQL 客户端工具) 需在 PATH 中可用。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ── 配置 ────────────────────────────────────────────────────────────

def _env_or(key: str, default: str) -> str:
    return os.environ.get(key, default)


BACKUP_DIR = Path(_env_or("BACKUP_DIR", "data/backups"))
DB_HOST = _env_or("DB_HOST", "localhost")
DB_PORT = _env_or("DB_PORT", "5432")
DB_USER = _env_or("DB_USER", "ad_manager")
DB_PASSWORD = _env_or("DB_PASSWORD", "change-me-in-production")
DB_NAME = _env_or("DB_NAME", "ad_manager")

# pg_restore 路径检测
PG_RESTORE = "pg_restore"
if os.name == "nt":
    _pg_paths = [
        r"C:\Program Files\PostgreSQL\17\bin\pg_restore.exe",
        r"C:\Program Files\PostgreSQL\16\bin\pg_restore.exe",
        r"C:\Program Files\PostgreSQL\15\bin\pg_restore.exe",
        r"C:\Program Files\PostgreSQL\14\bin\pg_restore.exe",
    ]
    for _p in _pg_paths:
        if Path(_p).exists():
            PG_RESTORE = _p
            break


# ── 工具函数 ─────────────────────────────────────────────────────────

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}")


def get_pg_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD
    return env


def parse_backup_date(filename: str) -> datetime | None:
    try:
        part = filename.replace("backup_", "").replace(".sql.gz", "")
        return datetime.strptime(part, "%Y-%m-%d_%H%M%S").replace(tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def _format_size(bytes_: int) -> str:
    if bytes_ < 1024:
        return f"{bytes_} B"
    elif bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    elif bytes_ < 1024 * 1024 * 1024:
        return f"{bytes_ / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_ / (1024 * 1024 * 1024):.2f} GB"


def list_backups() -> list[dict]:
    """列出可用备份文件。"""
    if not BACKUP_DIR.exists():
        return []
    backups: list[dict] = []
    for f in sorted(BACKUP_DIR.iterdir(), reverse=True):
        if not f.is_file() or not f.name.startswith("backup_") or not f.name.endswith(".sql.gz"):
            continue
        size_bytes = f.stat().st_size
        dt = parse_backup_date(f.name)
        backups.append({
            "filename": f.name,
            "path": str(f.resolve()),
            "size_bytes": size_bytes,
            "size_display": _format_size(size_bytes),
            "created_at": dt.isoformat() if dt else None,
        })
    return backups


# ── 恢复功能 ─────────────────────────────────────────────────────────

def resolve_backup_file(identifier: str) -> Path | None:
    """根据标识符解析备份文件路径。

    支持:
      - 完整的文件名: backup_2026-06-02_143022.sql.gz
      - 部分日期: 2026-06-01 (自动匹配该日期最近备份)
      - --latest: 最新备份
    """
    backups = list_backups()
    if not backups:
        return None

    # --latest: 返回最新的
    if identifier == "__latest__":
        b = backups[0]
        return Path(b["path"])

    # 完整文件名
    filepath = BACKUP_DIR / identifier
    if filepath.exists():
        return filepath

    # 部分日期: 查找日期前缀
    matching = [b for b in backups if b["filename"].startswith(f"backup_{identifier}")]
    if matching:
        b = matching[0]
        return Path(b["path"])

    return None


def do_restore(backup_path: Path, dry_run: bool = False) -> dict:
    """执行恢复操作。"""
    log(f"开始恢复: {backup_path.name} -> {DB_NAME}@{DB_HOST}:{DB_PORT}")

    if dry_run:
        log("[dry-run] 跳过实际恢复")
        return {
            "success": True,
            "filename": backup_path.name,
            "filepath": str(backup_path),
            "dry_run": True,
        }

    # 读取 gzip 备份文件
    import gzip
    try:
        with gzip.open(backup_path, "rb") as f:
            dump_data = f.read()
    except Exception as exc:
        return {"success": False, "filename": backup_path.name, "error": f"读取备份文件失败: {exc}"}

    # 构建 pg_restore 命令（先清理再恢复，避免冲突）
    cmd = [
        PG_RESTORE,
        "--host", DB_HOST,
        "--port", DB_PORT,
        "--username", DB_USER,
        "--dbname", DB_NAME,
        "--clean",              # 重建前先清理（DROP）
        "--if-exists",          # 仅 DROP 存在的对象，不报错
        "--no-owner",           # 不设置 owner
        "--verbose",
    ]

    start = time.time()
    try:
        proc = subprocess.Popen(
            cmd,
            env=get_pg_env(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stdout_data, stderr_data = proc.communicate(
            input=dump_data,
            timeout=600,  # 10 分钟
        )

        elapsed = time.time() - start

        if proc.returncode != 0:
            stderr_text = stderr_data.decode("utf-8", errors="replace")[:1000]
            log(f"pg_restore 返回非零退出码: {proc.returncode}")
            log(f"stderr: {stderr_text}")
            return {
                "success": False,
                "filename": backup_path.name,
                "error": stderr_text or f"pg_restore exit code {proc.returncode}",
                "elapsed_seconds": round(elapsed, 1),
            }

        log(f"恢复完成 ({_format_size(backup_path.stat().st_size)}, {elapsed:.1f}s)")
        return {
            "success": True,
            "filename": backup_path.name,
            "filepath": str(backup_path),
            "elapsed_seconds": round(elapsed, 1),
        }

    except FileNotFoundError:
        return {"success": False, "filename": backup_path.name, "error": f"pg_restore not found: {PG_RESTORE}"}
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return {"success": False, "filename": backup_path.name, "error": "pg_restore timeout after 600s"}
    except Exception as exc:
        return {"success": False, "filename": backup_path.name, "error": str(exc)}


def backup_info(b: dict) -> str:
    """格式化备份信息。"""
    created = b["created_at"][:19] if b["created_at"] else "未知"
    return f"  {b['filename']:<45} {b['size_display']:<12} {created}"


# ── CLI 入口 ─────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="PostgreSQL 一键恢复脚本")
    parser.add_argument("--list", action="store_true", help="列出可用备份")
    parser.add_argument("--latest", action="store_true", help="恢复到最新备份")
    parser.add_argument("--file", help="恢复到指定备份文件")
    parser.add_argument("--date", help="恢复到指定日期 (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="模拟执行，不实际恢复")
    args = parser.parse_args()

    # --list: 列出可用备份
    if args.list:
        backups = list_backups()
        if not backups:
            print("暂无可用备份")
            return
        print(f"{'文件名':<45} {'大小':<12} {'创建时间'}")
        print("-" * 75)
        for b in backups:
            print(backup_info(b))
        print(f"\n共计 {len(backups)} 个备份")
        return

    # 检查备份目录
    if not BACKUP_DIR.exists():
        print(f"错误: 备份目录不存在: {BACKUP_DIR}")
        print("请先执行 python scripts/backup.py 创建备份")
        sys.exit(1)

    # 解析备份文件
    backup_path: Path | None = None

    if args.latest:
        backup_path = resolve_backup_file("__latest__")
    elif args.file:
        backup_path = resolve_backup_file(args.file)
    elif args.date:
        backup_path = resolve_backup_file(args.date)
    else:
        parser.print_help()
        sys.exit(1)

    if backup_path is None:
        print(f"错误: 未找到匹配的备份文件")
        if args.file:
            print(f"  查找: {args.file}")
        elif args.date:
            print(f"  查找: backup_{args.date}_*")
        print("可用备份:")
        for b in list_backups():
            print(backup_info(b))
        sys.exit(1)

    # 确认恢复
    log(f"备份文件: {backup_path.name}")
    log(f"目标数据库: {DB_NAME}@{DB_HOST}:{DB_PORT}")
    log(f"用户: {DB_USER}")

    if not args.dry_run and not args.list:
        confirm = input(f"\n警告: 恢复将覆盖 {DB_NAME} 中的所有数据！\n确认继续? (yes/no): ")
        if confirm.lower() not in ("yes", "y"):
            log("已取消恢复")
            sys.exit(0)

    # 执行恢复
    result = do_restore(backup_path, dry_run=args.dry_run)

    if result["success"]:
        elapsed = result.get("elapsed_seconds", "?")
        log(f"恢复成功 ({elapsed}s)")
    else:
        log(f"恢复失败: {result.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
