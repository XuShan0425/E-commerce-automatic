"""Platform Fees CRUD — 平台费率管理."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.models.base import PlatformFee
from App.schemas.rates import PlatformFeeCreate, PlatformFeeRead, PlatformFeeUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platform-fees", tags=["platform-fees"])


# ── CRUD ────────────────────────────────────────

@router.get("/", response_model=list[PlatformFeeRead])
async def list_platform_fees(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformFeeRead]:
    """列出所有平台佣金费率。"""
    result = await db.execute(select(PlatformFee).order_by(PlatformFee.category))
    fees = result.scalars().all()
    return [PlatformFeeRead.model_validate(f) for f in fees]


@router.post("/", response_model=PlatformFeeRead, status_code=status.HTTP_201_CREATED)
async def create_platform_fee(
    body: PlatformFeeCreate,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> PlatformFeeRead:
    """手动添加单条平台费率。"""
    fee = PlatformFee(**body.model_dump())
    db.add(fee)
    await db.flush()
    await db.refresh(fee)
    return PlatformFeeRead.model_validate(fee)


@router.put("/{fee_id}", response_model=PlatformFeeRead)
async def update_platform_fee(
    fee_id: int,
    body: PlatformFeeUpdate,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> PlatformFeeRead:
    """更新单条平台费率。"""
    fee = await db.get(PlatformFee, fee_id)
    if fee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="费率记录不存在")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="没有提供需要更新的字段"
        )

    for field, value in update_data.items():
        setattr(fee, field, value)

    await db.flush()
    await db.refresh(fee)
    return PlatformFeeRead.model_validate(fee)


@router.delete("/{fee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform_fee(
    fee_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除单条平台费率。"""
    fee = await db.get(PlatformFee, fee_id)
    if fee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="费率记录不存在")
    await db.delete(fee)
    await db.flush()
