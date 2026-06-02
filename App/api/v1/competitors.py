"""Competitors API — 竞品数据查询与对比."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.models.base import CompetitorSnapshot, Product
from App.schemas.competitor import (
    CompetitorCompareItem,
    CompetitorCompareResponse,
    CompetitorSnapshotRead,
)

router = APIRouter(prefix="/competitors", tags=["competitors"])


@router.get("/", response_model=list[CompetitorSnapshotRead])
async def list_competitors(
    source_sku_id: str | None = Query(None, description="按来源 SKU 筛选"),
    limit: int = Query(50, ge=1, le=200, description="返回条数上限"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[CompetitorSnapshotRead]:
    """获取竞品数据列表。

    默认返回最近 7 天内的竞品快照（竞品数据过时快，周 TTL）。
    """
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    stmt = (
        select(CompetitorSnapshot)
        .where(CompetitorSnapshot.snapshot_time >= seven_days_ago)
        .order_by(CompetitorSnapshot.snapshot_time.desc())
        .limit(limit)
    )

    if source_sku_id:
        stmt = stmt.where(CompetitorSnapshot.source_sku_id == source_sku_id)

    result = await db.execute(stmt)
    snapshots = result.scalars().all()
    return [CompetitorSnapshotRead.model_validate(s) for s in snapshots]


@router.get("/compare", response_model=CompetitorCompareResponse)
async def compare_competitors(
    sku_id: str = Query(..., description="本店商品 SKU ID"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> CompetitorCompareResponse:
    """并排对比自有商品与竞品（价格/评分/销量）。

    返回自有商品信息和最近 7 天内的竞品快照。
    """
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    # 1. 查询本店商品
    prod_result = await db.execute(select(Product).where(Product.sku_id == sku_id))
    product = prod_result.scalar_one_or_none()

    self_product = None
    if product:
        self_product = CompetitorCompareItem(
            sku_id=product.sku_id,
            name=product.name,
            price=product.cost_price,
            rating=None,
            sales=None,
            is_self=True,
        )

    # 2. 查询竞品快照
    comp_result = await db.execute(
        select(CompetitorSnapshot)
        .where(
            CompetitorSnapshot.source_sku_id == sku_id,
            CompetitorSnapshot.snapshot_time >= seven_days_ago,
        )
        .order_by(CompetitorSnapshot.snapshot_time.desc())
        .limit(50)
    )
    competitors_raw = comp_result.scalars().all()

    # 去重 (按 sku_id 取最新一条)
    seen: dict[str, CompetitorSnapshot] = {}
    for c in competitors_raw:
        if c.sku_id not in seen or c.snapshot_time > seen[c.sku_id].snapshot_time:
            seen[c.sku_id] = c

    competitors = [
        CompetitorCompareItem(
            sku_id=c.sku_id,
            name=c.name,
            price=c.price,
            rating=c.rating,
            sales=c.sales,
            is_self=False,
            snapshot_time=c.snapshot_time,
        )
        for c in seen.values()
    ]

    return CompetitorCompareResponse(
        self_product=self_product,
        competitors=competitors,
    )
