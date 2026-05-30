"""API Key 鉴权 — 验证、生成、依赖注入."""

import hashlib
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.config import settings
from App.core.database import get_db

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_key(raw_key: str) -> str:
    """SHA-256 哈希 API Key，数据库只存哈希。"""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key() -> tuple[str, str]:
    """生成新 API Key。返回 (raw_key, key_hash) 元组。"""
    raw = "ak-" + secrets.token_urlsafe(32)
    return raw, hash_key(raw)


async def verify_api_key(
    api_key: Optional[str] = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> str:
    """FastAPI 依赖：验证请求中的 X-API-Key 头。返回有效的 raw key。"""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    key_hash = hash_key(api_key)

    # 动态导入避免循环依赖
    from App.models.auth import ApiKey

    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    record = result.scalar_one_or_none()

    if record is None:
        # fallback: 允许 ADMIN_API_KEY 作为 bootstrap key（用于创建第一条正式 API Key）
        if api_key == settings.ADMIN_API_KEY:
            return api_key
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    return api_key
