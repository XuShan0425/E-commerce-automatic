"""Dashboard 聚合 API — GET /api/v1/dashboard/aggregate."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.services.analysis_pipeline import get_dashboard_aggregate

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/aggregate")
async def aggregate_dashboard(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """返回 Dashboard 聚合数据：商品数、今日花费/收入、平均 ROI、利润摘要、警报计数、ROI 趋势。"""
    return await get_dashboard_aggregate(db)
