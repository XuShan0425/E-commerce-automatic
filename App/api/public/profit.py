"""Public API — 利润分析（只读）. """

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import rate_limited, require_scope
from App.models.base import Product, ProfitAnalysis

router = APIRouter(prefix="/profit")


class ProfitAnalysisPublic(BaseModel):
    """Public profit analysis schema with product info."""
    id: int
    sku_id: str
    product_name: str | None = None
    calc_time: datetime
    logistics_cost: float
    platform_fee: float
    true_cost: float
    gross_margin: float
    breakeven_ad_spend: float
    current_roi: float
    roi_7d_trend: list | None = None

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[ProfitAnalysisPublic])
async def list_profit_analyses(
    sku_id: str | None = Query(None, description="Filter by SKU ID"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    api_key: str = Depends(require_scope("profit:read")),
    db: AsyncSession = Depends(get_db),
):
    """Public: 获取利润分析数据。需要 profit:read scope。"""
    rate_limited(api_key)
    stmt = select(ProfitAnalysis).order_by(ProfitAnalysis.calc_time.desc()).limit(limit)
    if sku_id:
        stmt = stmt.where(ProfitAnalysis.sku_id == sku_id)
    result = await db.execute(stmt)
    analyses = result.scalars().all()

    # Enrich with product names
    sku_ids = list(set(a.sku_id for a in analyses))
    product_map: dict[str, str] = {}
    if sku_ids:
        prod_result = await db.execute(
            select(Product).where(Product.sku_id.in_(sku_ids))
        )
        for p in prod_result.scalars().all():
            product_map[p.sku_id] = p.name

    output = []
    for a in analyses:
        d = ProfitAnalysisPublic(
            id=a.id,
            sku_id=a.sku_id,
            product_name=product_map.get(a.sku_id),
            calc_time=a.calc_time,
            logistics_cost=float(a.logistics_cost),
            platform_fee=float(a.platform_fee),
            true_cost=float(a.true_cost),
            gross_margin=float(a.gross_margin),
            breakeven_ad_spend=float(a.breakeven_ad_spend),
            current_roi=float(a.current_roi),
            roi_7d_trend=a.roi_7d_trend if isinstance(a.roi_7d_trend, list) else None,
        )
        output.append(d)
    return output


@router.get("/{analysis_id}", response_model=ProfitAnalysisPublic)
async def get_profit_analysis(
    analysis_id: int,
    api_key: str = Depends(require_scope("profit:read")),
    db: AsyncSession = Depends(get_db),
):
    """Public: 获取单个利润分析详情。需要 profit:read scope。"""
    rate_limited(api_key)
    analysis = await db.get(ProfitAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profit analysis not found",
        )

    # Get product name
    prod_result = await db.execute(
        select(Product).where(Product.sku_id == analysis.sku_id)
    )
    product = prod_result.scalar_one_or_none()

    return ProfitAnalysisPublic(
        id=analysis.id,
        sku_id=analysis.sku_id,
        product_name=product.name if product else None,
        calc_time=analysis.calc_time,
        logistics_cost=float(analysis.logistics_cost),
        platform_fee=float(analysis.platform_fee),
        true_cost=float(analysis.true_cost),
        gross_margin=float(analysis.gross_margin),
        breakeven_ad_spend=float(analysis.breakeven_ad_spend),
        current_roi=float(analysis.current_roi),
        roi_7d_trend=analysis.roi_7d_trend if isinstance(analysis.roi_7d_trend, list) else None,
    )
