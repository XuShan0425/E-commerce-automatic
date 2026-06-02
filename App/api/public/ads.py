"""Public API — 广告数据（只读）. """

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import rate_limited, require_scope
from App.models.base import AdSnapshot
from App.schemas.ad_snapshot import AdSnapshotRead

router = APIRouter(prefix="/ads")


@router.get("/", response_model=list[AdSnapshotRead])
async def list_ad_snapshots(
    sku_id: str | None = Query(None, description="Filter by SKU ID"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    api_key: str = Depends(require_scope("ads:read")),
    db: AsyncSession = Depends(get_db),
):
    """Public: 获取广告快照数据。需要 ads:read scope。"""
    rate_limited(api_key)
    stmt = select(AdSnapshot).order_by(AdSnapshot.snapshot_time.desc()).limit(limit)
    if sku_id:
        stmt = stmt.where(AdSnapshot.sku_id == sku_id)
    result = await db.execute(stmt)
    snapshots = result.scalars().all()
    return [AdSnapshotRead.model_validate(s) for s in snapshots]


@router.get("/{snapshot_id}", response_model=AdSnapshotRead)
async def get_ad_snapshot(
    snapshot_id: int,
    api_key: str = Depends(require_scope("ads:read")),
    db: AsyncSession = Depends(get_db),
):
    """Public: 获取单个广告快照详情。需要 ads:read scope。"""
    rate_limited(api_key)
    snapshot = await db.get(AdSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad snapshot not found")
    return AdSnapshotRead.model_validate(snapshot)
