"""Logistics Rates CRUD — 物流费率管理."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.logging import get_logger
from App.core.security import verify_api_key
from App.models.base import LogisticsRate
from App.schemas.rates import (
    BatchLogisticsWriteResult,
    LogisticsRateCreate,
    LogisticsRateRead,
    LogisticsRateUpdate,
    ParsedLogisticsRate,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/logistics-rates", tags=["logistics-rates"])


# ── CRUD ────────────────────────────────────────

@router.get("/", response_model=list[LogisticsRateRead])
async def list_logistics_rates(
    region: str | None = Query(None, description="按目的地区筛选，如 US, EU"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[LogisticsRateRead]:
    """列出物流费率，可按目的地区筛选。"""
    stmt = select(LogisticsRate).order_by(
        LogisticsRate.destination_region,
        LogisticsRate.weight_range_min,
    )
    if region:
        stmt = stmt.where(LogisticsRate.destination_region == region.upper())
    result = await db.execute(stmt)
    rates = result.scalars().all()
    return [LogisticsRateRead.model_validate(r) for r in rates]


@router.post("/", response_model=LogisticsRateRead, status_code=status.HTTP_201_CREATED)
async def create_logistics_rate(
    body: LogisticsRateCreate,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> LogisticsRateRead:
    """手动添加单条物流费率。"""
    rate = LogisticsRate(**body.model_dump())
    db.add(rate)
    await db.flush()
    await db.refresh(rate)
    return LogisticsRateRead.model_validate(rate)


@router.put("/{rate_id}", response_model=LogisticsRateRead)
async def update_logistics_rate(
    rate_id: int,
    body: LogisticsRateUpdate,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> LogisticsRateRead:
    """更新单条物流费率。"""
    rate = await db.get(LogisticsRate, rate_id)
    if rate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="费率记录不存在")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有提供需要更新的字段")

    for field, value in update_data.items():
        setattr(rate, field, value)

    await db.flush()
    await db.refresh(rate)
    return LogisticsRateRead.model_validate(rate)


@router.delete("/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_logistics_rate(
    rate_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除单条物流费率。"""
    rate = await db.get(LogisticsRate, rate_id)
    if rate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="费率记录不存在")
    await db.delete(rate)
    await db.flush()


# ── 批量写入（确认后使用）────────────────────────

@router.post("/batch", response_model=BatchLogisticsWriteResult)
async def batch_write_logistics_rates(
    body: list[ParsedLogisticsRate],
    overwrite: bool = Query(False, description="是否覆盖已有数据"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> BatchLogisticsWriteResult:
    """批量写入物流费率（用于 AI 解析确认后保存）。

    如果 overwrite=True，会先清空所有已有记录再写入。
    否则仅插入新记录（不覆盖已有数据）。
    """
    inserted = 0
    replaced = 0
    errors: list[dict] = []

    if overwrite:
        await db.execute(sql_delete(LogisticsRate))
        await db.flush()

    for item in body:
        try:
            rate = LogisticsRate(**item.model_dump())
            db.add(rate)
            await db.flush()
            if overwrite:
                replaced += 1
            else:
                inserted += 1
        except Exception as exc:
            errors.append({
                "item": item.model_dump(),
                "error": str(exc),
            })

    return BatchLogisticsWriteResult(
        inserted=inserted,
        replaced=replaced,
        errors=errors,
    )
