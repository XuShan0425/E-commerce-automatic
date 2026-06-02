"""价格快照 API — 查询价格历史、最新价格、价格变动检测."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.logging import get_logger
from App.core.security import verify_api_key
from App.schemas.price_snapshot import (
    PriceChangeResult,
    PriceSnapshotLatestRead,
    PriceSnapshotRead,
)
from App.services.price_monitor import (
    detect_price_change,
    get_latest_price_per_sku,
    get_price_history,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/price-snapshots", tags=["price-snapshots"])


@router.get("/{sku_id}/history", response_model=list[PriceSnapshotRead])
async def get_price_history_endpoint(
    sku_id: str,
    limit: int = Query(30, ge=1, le=200, description="返回条数上限"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[PriceSnapshotRead]:
    """查询指定 SKU 的价格快照历史（按时间倒序）。"""
    records = await get_price_history(db, sku_id, limit=limit)
    return [PriceSnapshotRead.model_validate(r) for r in records]


@router.get("/latest", response_model=list[PriceSnapshotLatestRead])
async def get_latest_prices(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[PriceSnapshotLatestRead]:
    """获取所有 SKU 的最新价格快照。"""
    records = await get_latest_price_per_sku(db)
    return [PriceSnapshotLatestRead.model_validate(r) for r in records]


@router.get("/{sku_id}/change", response_model=PriceChangeResult | None)
async def get_price_change(
    sku_id: str,
    threshold: float = Query(
        0.10, ge=0.0, le=1.0, description="显著变动阈值（小数，默认 0.10 即 10%）"
    ),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> PriceChangeResult | None:
    """检测指定 SKU 的最新价格变动（最近两条记录相比）。

    如果历史记录不足 2 条，返回 null。
    """
    result = await detect_price_change(db, sku_id, threshold=threshold)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SKU {sku_id} 价格历史不足（需要至少 2 条记录）",
        )
    return result
