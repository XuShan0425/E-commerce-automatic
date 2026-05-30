"""API Key 管理路由 — 仅管理员可访问."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import generate_key, hash_key, verify_api_key
from App.models.auth import ApiKey
from App.schemas.auth import ApiKeyCreate, ApiKeyRead, ApiKeyReveal

router = APIRouter(prefix="/api-keys", tags=["auth"])


@router.post("/", response_model=ApiKeyReveal, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyReveal:
    """生成新 API Key。返回原始 key（仅此一次）。"""
    raw, hashed = generate_key()
    record = ApiKey(key_hash=hashed, label=body.label)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return ApiKeyReveal(
        id=record.id,
        key_hash=record.key_hash,
        label=record.label,
        is_active=record.is_active,
        created_at=record.created_at,
        revoked_at=record.revoked_at,
        raw_key=raw,
    )


@router.get("/", response_model=list[ApiKeyRead])
async def list_api_keys(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyRead]:
    """列出所有 API Key（不含原始 key）。"""
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    records = result.scalars().all()
    return [ApiKeyRead.model_validate(r) for r in records]


@router.post("/{key_id}/revoke", response_model=ApiKeyRead)
async def revoke_api_key(
    key_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyRead:
    """吊销指定 API Key。"""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    record.is_active = False
    record.revoked_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(record)
    return ApiKeyRead.model_validate(record)
