#!/usr/bin/env python3
"""自动 pg_dump 备份脚本 — 保留 30 天，超期自动清理。

用法:
    python scripts/backup.py                  # 执行备份
    python scripts/backup.py --dry-run        # 模拟执行，不实际备份
    python scripts/backup.py --list           # 列出已有备份文件
    python scripts/backup.py --clean-only     # 仅清理过期备份

环境变量:
    BACKUP_DIR   备份文件存储路径（默认: ./data/backups）
    DB_HOST      数据库主机
    DB_PORT      数据库端口
    DB_USER      数据库用户
    DB_PASSWORD  数据库密码
    DB_NAME      数据库名称

依赖:
    pg_dump (PostgreSQL 客户端工具) 需在 PATH 中可用。
"""

from __future__ import annotations

import gzip
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
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
RETENTION_DAYS = 30

# pg_dump 路径检测
PG_DUMP = "pg_dump"
if os.name == "nt":
    # Windows 上尝试常见安装路径
    _pg_paths = [
        r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\14\bin\pg_dump.exe",
    ]
    for _p in _pg_paths:
        if Path(_p).exists():
            PG_DUMP = _p
            break


# ── 工具函数 ─────────────────────────────────────────────────────────

def log(msg: str) -> None:
    """统一日志输出。"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}")


def get_pg_env() -> dict[str, str]:
    """返回 pg_dump 所需的环境变量（注入密码）。"""
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASSWORD
    return env


def backup_filename() -> str:
    """生成备份文件名: backup_YYYY-MM-DD_HHMMSS.sql.gz"""
    ts = time.strftime("%Y-%m-%d_%H%M%S")
    return f"backup_{ts}.sql.gz"


def parse_backup_date(filename: str) -> datetime | None:
    """从备份文件名中解析出日期时间。"""
    # backup_2026-06-02_143022.sql.gz
    try:
        part = filename.replace("backup_", "").replace(".sql.gz", "")
        return datetime.strptime(part, "%Y-%m-%d_%H%M%S").replace(tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


# ── 核心功能 ─────────────────────────────────────────────────────────

def list_backups() -> list[dict]:
    """列出所有备份文件，返回排序后的列表（最新在前）。"""
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


def _format_size(bytes_: int) -> str:
    """可读的文件大小。"""
    if bytes_ < 1024:
        return f"{bytes_} B"
    elif bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    elif bytes_ < 1024 * 1024 * 1024:
        return f"{bytes_ / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_ / (1024 * 1024 * 1024):.2f} GB"


def do_backup() -> dict:
    """执行一次 pg_dump 备份。返回结果信息。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    filename = backup_filename()
    filepath = BACKUP_DIR / filename

    log(f"开始备份数据库: {DB_NAME} -> {filepath}")

    # 构建 pg_dump 命令
    cmd = [
        PG_DUMP,
        "--host", DB_HOST,
        "--port", DB_PORT,
        "--username", DB_USER,
        "--dbname", DB_NAME,
        "--format", "c",          # custom format (压缩，可恢复)
        "--verbose",
    ]

    start = time.time()
    try:
        # 执行 pg_dump，输出到文件
        result = subprocess.run(
            cmd,
            env=get_pg_env(),
            capture_output=True,
            text=True,
            timeout=600,  # 10 分钟超时
        )

        # gzip 压缩
        with gzip.open(filepath, "wb") as f_out:
            f_out.write(result.stdout.encode("utf-8") if result.stdout else b"")

        elapsed = time.time() - start
        size = filepath.stat().st_size if filepath.exists() else 0

        if result.returncode != 0:
            log(f"pg_dump 返回非零退出码: {result.returncode}")
            log(f"stderr: {result.stderr[:500]}")
            # 删除不完整的备份文件
            if filepath.exists():
                filepath.unlink()
            return {
                "success": False,
                "filename": filename,
                "error": result.stderr[:500] or f"pg_dump exit code {result.returncode}",
                "elapsed_seconds": round(elapsed, 1),
            }

        log(f"备份完成: {filename} ({_format_size(size)})")
        return {
            "success": True,
            "filename": filename,
            "filepath": str(filepath),
            "size_bytes": size,
            "size_display": _format_size(size),
            "elapsed_seconds": round(elapsed, 1),
        }

    except FileNotFoundError:
        log(f"错误: 找不到 pg_dump ({PG_DUMP})，请确认 PostgreSQL 客户端已安装并在 PATH 中")
        return {"success": False, "filename": filename, "error": f"pg_dump not found: {PG_DUMP}"}
    except subprocess.TimeoutExpired:
        log("错误: pg_dump 超时（10分钟）")
        return {"success": False, "filename": filename, "error": "pg_dump timeout after 600s"}
    except Exception as exc:
        log(f"备份异常: {exc}")
        return {"success": False, "filename": filename, "error": str(exc)}


def clean_expired(dry_run: bool = False) -> list[dict]:
    """清理超过 RETENTION_DAYS 的旧备份。返回清理记录。"""
    if not BACKUP_DIR.exists():
        return []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    cleaned: list[dict] = []

    for f in sorted(BACKUP_DIR.iterdir()):
        if not f.is_file() or not f.name.startswith("backup_") or not f.name.endswith(".sql.gz"):
            continue
        dt = parse_backup_date(f.name)
        if dt is None:
            continue
        if dt < cutoff:
            age_days = (now - dt).days
            if dry_run:
                log(f"[dry-run] 将删除过期备份: {f.name} ({age_days} 天前)")
                cleaned.append({"filename": f.name, "age_days": age_days, "action": "would_delete"})
            else:
                size = f.stat().st_size
                f.unlink()
                log(f"已删除过期备份: {f.name} ({age_days} 天前, {_format_size(size)})")
                cleaned.append({"filename": f.name, "age_days": age_days, "action": "deleted"})

    return cleaned


# ── CLI 入口 ─────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="PostgreSQL 自动备份脚本（pg_dump）")
    parser.add_argument("--dry-run", action="store_true", help="模拟执行，不实际备份")
    parser.add_argument("--list", action="store_true", help="列出已有备份文件")
    parser.add_argument("--clean-only", action="store_true", help="仅清理过期备份")
    args = parser.parse_args()

    # 创建备份目录
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        log(f"创建备份目录: {BACKUP_DIR}")

    # --list: 列出已有备份
    if args.list:
        backups = list_backups()
        if not backups:
            print("暂无备份文件")
            return
        print(f"{'文件名':<45} {'大小':<12} {'创建时间'}")
        print("-" * 75)
        for b in backups:
            created = b["created_at"][:19] if b["created_at"] else "未知"
            print(f"{b['filename']:<45} {b['size_display']:<12} {created}")
        return

    # --clean-only: 仅清理
    if args.clean_only:
        cleaned = clean_expired(dry_run=False)
        if not cleaned:
            log("没有需要清理的过期备份")
        return

    # --dry-run: 模拟模式
    if args.dry_run:
        log("[dry-run] 模拟备份流程:")
        log(f"  备份目录: {BACKUP_DIR.resolve()}")
        log(f"  数据库: {DB_NAME}@{DB_HOST}:{DB_PORT}")
        log(f"  备份文件名: {backup_filename()}")
        log(f"  保留天数: {RETENTION_DAYS}")
        clean_expired(dry_run=True)
        log("[dry-run] 模拟完成")
        return

    # 正常执行: 备份 + 清理
    result = do_backup()
    if result["success"]:
        log(f"备份成功: {result['filename']} ({result['size_display']}, {result['elapsed_seconds']}s)")
    else:
        log(f"备份失败: {result.get('error', '未知错误')}")
        sys.exit(1)

    # 清理过期备份
    cleaned = clean_expired(dry_run=False)
    if cleaned:
        log(f"已清理 {len(cleaned)} 个过期备份")
    else:
        log("无过期备份需要清理")


if __name__ == "__main__":
    main()
