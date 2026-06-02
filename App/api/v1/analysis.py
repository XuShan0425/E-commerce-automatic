"""AI 分析 API — 触发分析 + 结果查询."""

from __future__ import annotations

from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.logging import get_logger
from App.core.security import verify_api_key
from App.models.base import ProfitAnalysis
from App.schemas.profit_analysis import ProfitAnalysisRead, RoiTrendItem, RoiTrendPoint
from App.services.cache_service import get_cache, set_cache

logger = get_logger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/run")
async def run_analysis_all(
    skip_ai: bool = Query(False, description="跳过 AI 决策（仅做利润计算）"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """对所有已注册商品执行 AI 分析。

    流程：利润计算 → AI 决策 → 边界检查。
    设置 skip_ai=true 则只做利润计算。
    """
    from App.services.analysis_pipeline import analyze_all_skus

    try:
        result = await analyze_all_skus(db, skip_ai=skip_ai)
        return {"status": "ok", **result}
    except Exception as exc:
        logger.exception("全量分析失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分析失败: {exc}",
        ) from exc


@router.post("/run/{sku_id}")
async def run_analysis_single(
    sku_id: str,
    skip_ai: bool = Query(False, description="跳过 AI 决策（仅做利润计算）"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """对单个 SKU 执行 AI 分析。"""
    from App.services.analysis_pipeline import analyze_single_sku

    try:
        result = await analyze_single_sku(db, sku_id, skip_ai=skip_ai)
        if result.get("error") and not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["error"],
            )
        return {"status": "ok", **result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("单品分析失败: SKU=%s", sku_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分析失败: {exc}",
        ) from exc


@router.get("/{sku_id}/history", response_model=list[ProfitAnalysisRead])
async def get_analysis_history(
    sku_id: str,
    limit: int = Query(30, ge=1, le=200, description="返回条数上限"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[ProfitAnalysisRead]:
    """查看某 SKU 的历史利润分析记录（缓存 60 秒）。"""
    cache_key = f"analysis:history:{sku_id}:{limit}"
    cached = await get_cache(cache_key)
    if cached is not None:
        return [ProfitAnalysisRead(**r) for r in cached]

    result = await db.execute(
        select(ProfitAnalysis)
        .where(ProfitAnalysis.sku_id == sku_id)
        .order_by(ProfitAnalysis.calc_time.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    serializable = [
        {
            "id": r.id,
            "sku_id": r.sku_id,
            "calc_time": r.calc_time.isoformat() if r.calc_time else None,
            "logistics_cost": float(r.logistics_cost),
            "platform_fee": float(r.platform_fee),
            "true_cost": float(r.true_cost),
            "gross_margin": float(r.gross_margin),
            "breakeven_ad_spend": float(r.breakeven_ad_spend),
            "current_roi": float(r.current_roi),
            "roi_7d_trend": r.roi_7d_trend,
        }
        for r in records
    ]
    await set_cache(cache_key, serializable, ttl=60)
    return [ProfitAnalysisRead.model_validate(r) for r in records]


@router.get("/latest", response_model=list[ProfitAnalysisRead])
async def get_latest_analysis(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[ProfitAnalysisRead]:
    """获取所有 SKU 的最新一次分析结果（缓存 30 秒）。"""
    cache_key = "analysis:latest"
    cached = await get_cache(cache_key)
    if cached is not None:
        return [ProfitAnalysisRead(**r) for r in cached]
    # 子查询：每个 sku_id 的最新 calc_time
    subq = (
        select(
            ProfitAnalysis.sku_id,
            func.max(ProfitAnalysis.calc_time).label("max_time"),
        )
        .group_by(ProfitAnalysis.sku_id)
        .subquery()
    )

    result = await db.execute(
        select(ProfitAnalysis)
        .join(
            subq,
            and_(
                ProfitAnalysis.sku_id == subq.c.sku_id,
                ProfitAnalysis.calc_time == subq.c.max_time,
            ),
        )
        .order_by(ProfitAnalysis.sku_id)
    )
    records = result.scalars().all()
    serializable = [
        {
            "id": r.id,
            "sku_id": r.sku_id,
            "calc_time": r.calc_time.isoformat() if r.calc_time else None,
            "logistics_cost": float(r.logistics_cost),
            "platform_fee": float(r.platform_fee),
            "true_cost": float(r.true_cost),
            "gross_margin": float(r.gross_margin),
            "breakeven_ad_spend": float(r.breakeven_ad_spend),
            "current_roi": float(r.current_roi),
            "roi_7d_trend": r.roi_7d_trend,
        }
        for r in records
    ]
    await set_cache(cache_key, serializable, ttl=30)
    return [ProfitAnalysisRead.model_validate(r) for r in records]


@router.get("/{sku_id}/forecast")
async def get_roi_forecast(
    sku_id: str,
    days_ahead: int = Query(7, ge=1, le=30, description="预测未来天数"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取指定 SKU 的 ROI 预测（带置信区间）。"""
    from App.services.roi_forecaster import forecast_roi as _forecast_roi

    try:
        forecast = await _forecast_roi(db, sku_id, days_ahead=days_ahead)
        return {"status": "ok", **forecast}
    except Exception as exc:
        logger.exception("ROI 预测失败: SKU=%s", sku_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ROI 预测失败: {exc}",
        ) from exc


@router.get("/roi-trend", response_model=list[RoiTrendItem])
async def get_roi_trend(
    sku_id: str | None = Query(None, description="按 SKU 过滤（可选）"),
    days: int = Query(7, ge=1, le=90, description="趋势天数"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[RoiTrendItem]:
    """获取 ROI 趋势数据（按 SKU 分组，每日一个数据点）。

    每个 SKU 返回最新的 roi_7d_trend 数据。
    若指定 sku_id 则只返回该 SKU 的趋势；否则返回所有已追踪 SKU 的趋势。
    """
    from datetime import datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=days)

    if sku_id:
        result = await db.execute(
            select(ProfitAnalysis)
            .where(
                ProfitAnalysis.sku_id == sku_id,
                ProfitAnalysis.calc_time >= since,
            )
            .order_by(ProfitAnalysis.calc_time.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None or not row.roi_7d_trend:
            return []
        trend_data = row.roi_7d_trend
        trend_points = _parse_trend_data(trend_data)
        return [RoiTrendItem(sku_id=sku_id, trend=trend_points)] if trend_points else []

    # 查询所有 SKU 的最新分析记录
    subq = (
        select(
            ProfitAnalysis.sku_id,
            func.max(ProfitAnalysis.calc_time).label("max_time"),
        )
        .group_by(ProfitAnalysis.sku_id)
        .subquery()
    )

    result = await db.execute(
        select(ProfitAnalysis)
        .join(
            subq,
            and_(
                ProfitAnalysis.sku_id == subq.c.sku_id,
                ProfitAnalysis.calc_time == subq.c.max_time,
            ),
        )
        .order_by(ProfitAnalysis.sku_id)
    )
    records = result.scalars().all()

    items: list[RoiTrendItem] = []
    for record in records:
        trend_data = record.roi_7d_trend
        if not trend_data or not isinstance(trend_data, list):
            continue
        trend_points = _parse_trend_data(trend_data)
        if trend_points:
            items.append(RoiTrendItem(sku_id=record.sku_id, trend=trend_points))

    return items


def _parse_trend_data(trend_data: list | dict | None) -> list[RoiTrendPoint]:
    """将原始 roi_7d_trend 数据解析为 RoiTrendPoint 列表。"""
    if not trend_data or not isinstance(trend_data, list):
        return []
    return [
        RoiTrendPoint(
            date=p.get("date", ""),
            roi=float(p.get("roi", 0)),
            revenue=float(p.get("revenue", 0)),
            ad_spend=float(p.get("ad_spend", 0)),
        )
        for p in trend_data
        if isinstance(p, dict) and p.get("date")
    ]
