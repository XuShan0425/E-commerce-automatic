"""备份管理 API 路由 — 列表、触发备份、恢复。

独立于 App.core 模块，不依赖数据库和安全中间件。
"""

import gzip
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/backups", tags=["backups"])

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "data/backups"))
BACKUP_SCRIPT = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "backup.py"

# 从环境变量读取 API Key 用于简单鉴权
_ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "admin-bootstrap-key-change-me")


async def _verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> str:
    """简单的 API Key 鉴权依赖 — 从 X-API-Key header 读取。"""
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key")
    if x_api_key != _ADMIN_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    return x_api_key


# ── Schema ──────────────────────────────────────────────────────────

class BackupItem(BaseModel):
    filename: str
    size_bytes: int
    size_display: str
    created_at: str | None = None


class BackupListResponse(BaseModel):
    backups: list[BackupItem]
    total: int
    backup_dir: str


class BackupTriggerResponse(BaseModel):
    success: bool
    filename: str | None = None
    error: str | None = None
    message: str | None = None


class RestoreRequest(BaseModel):
    filename: str


class RestoreResponse(BaseModel):
    success: bool
    filename: str | None = None
    error: str | None = None
    message: str | None = None


# ── 辅助函数 ────────────────────────────────────────────────────────

def _format_size(bytes_: int) -> str:
    if bytes_ < 1024:
        return f"{bytes_} B"
    elif bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    elif bytes_ < 1024 * 1024 * 1024:
        return f"{bytes_ / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_ / (1024 * 1024 * 1024):.2f} GB"


def _parse_backup_date(filename: str) -> datetime | None:
    try:
        part = filename.replace("backup_", "").replace(".sql.gz", "")
        return datetime.strptime(part, "%Y-%m-%d_%H%M%S").replace(tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def _scan_backups() -> list[BackupItem]:
    """扫描备份目录，返回备份文件列表。"""
    if not BACKUP_DIR.exists():
        return []
    items: list[BackupItem] = []
    for f in sorted(BACKUP_DIR.iterdir(), reverse=True):
        if not f.is_file() or not f.name.startswith("backup_") or not f.name.endswith(".sql.gz"):
            continue
        dt = _parse_backup_date(f.name)
        items.append(BackupItem(
            filename=f.name,
            size_bytes=f.stat().st_size,
            size_display=_format_size(f.stat().st_size),
            created_at=dt.isoformat() if dt else None,
        ))
    return items


# ── 路由 ────────────────────────────────────────────────────────────

@router.get("/", response_model=BackupListResponse)
async def list_backups() -> BackupListResponse:
    """获取备份文件列表（读取文件系统，无需鉴权）。"""
    backups = _scan_backups()
    return BackupListResponse(
        backups=backups,
        total=len(backups),
        backup_dir=str(BACKUP_DIR.resolve()),
    )


@router.post("/trigger", response_model=BackupTriggerResponse)
async def trigger_backup(
    _api_key: str = Depends(_verify_api_key),
) -> BackupTriggerResponse:
    """触发一次备份。"""
    if not BACKUP_SCRIPT.exists():
        return BackupTriggerResponse(
            success=False,
            error=f"备份脚本不存在: {BACKUP_SCRIPT}",
        )

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [sys.executable, str(BACKUP_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=600,
            env={**os.environ},
        )

        if result.returncode != 0:
            return BackupTriggerResponse(
                success=False,
                error=result.stderr[:500] or f"exit code {result.returncode}",
            )

        backups = _scan_backups()
        latest = backups[0] if backups else None

        return BackupTriggerResponse(
            success=True,
            filename=latest.filename if latest else None,
            message=f"备份成功: {latest.filename if latest else ''}",
        )

    except subprocess.TimeoutExpired:
        return BackupTriggerResponse(success=False, error="备份超时（10分钟）")
    except Exception as exc:
        return BackupTriggerResponse(success=False, error=str(exc))


@router.post("/restore", response_model=RestoreResponse)
async def restore_backup(
    body: RestoreRequest,
    _api_key: str = Depends(_verify_api_key),
) -> RestoreResponse:
    """恢复到指定备份点。"""
    backup_path = BACKUP_DIR / body.filename
    if not backup_path.exists() or not backup_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"备份文件不存在: {body.filename}",
        )

    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_user = os.environ.get("DB_USER", "ad_manager")
    db_password = os.environ.get("DB_PASSWORD", "change-me-in-production")
    db_name = os.environ.get("DB_NAME", "ad_manager")

    pg_restore = "pg_restore"
    if os.name == "nt":
        _pg_paths = [
            r"C:\Program Files\PostgreSQL\17\bin\pg_restore.exe",
            r"C:\Program Files\PostgreSQL\16\bin\pg_restore.exe",
            r"C:\Program Files\PostgreSQL\15\bin\pg_restore.exe",
            r"C:\Program Files\PostgreSQL\14\bin\pg_restore.exe",
        ]
        for _p in _pg_paths:
            if Path(_p).exists():
                pg_restore = _p
                break

    try:
        with gzip.open(backup_path, "rb") as f:
            dump_data = f.read()
    except Exception as exc:
        return RestoreResponse(success=False, error=f"读取备份文件失败: {exc}")

    cmd = [
        pg_restore,
        "--host", db_host,
        "--port", db_port,
        "--username", db_user,
        "--dbname", db_name,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--verbose",
    ]

    env = {**os.environ, "PGPASSWORD": db_password}

    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, stderr_data = proc.communicate(input=dump_data, timeout=600)

        if proc.returncode != 0:
            error_text = stderr_data.decode("utf-8", errors="replace")[:500]
            return RestoreResponse(success=False, error=error_text)

        return RestoreResponse(
            success=True,
            filename=body.filename,
            message=f"恢复成功: {body.filename}",
        )

    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return RestoreResponse(success=False, error="恢复超时（10分钟）")
    except Exception as exc:
        return RestoreResponse(success=False, error=str(exc))
