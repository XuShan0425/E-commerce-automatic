"""分析管线监控 API — 查询分析运行状态、SKU 级指标、管线健康。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.logging import get_logger
from App.core.security import verify_api_key
from App.models.base import ProfitAnalysis
from App.services.analysis_monitor import get_metrics

logger = get_logger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/analysis")
async def get_analysis_monitoring(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取分析管线监控概览。

    返回实时内存指标 + 数据库层面的聚合统计。
    """
    metrics = get_metrics()

    # 数据库层面的补充统计
    db_stats = await _get_db_analysis_stats(db)

    return {
        "status": "healthy" if metrics.is_healthy else "degraded",
        "pipeline": metrics.to_dict(),
        "database": db_stats,
    }


@router.get("/analysis/skus")
async def get_sku_monitoring(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """获取每个 SKU 的分析指标。"""
    metrics = get_metrics()
    sku_summaries = metrics.get_sku_summaries()

    # 补充数据库层面的 per-SKU 信息
    for s in sku_summaries:
        sku_id = s["sku_id"]
        db_info = await _get_sku_db_stats(db, sku_id)
        s.update(db_info)

    return sku_summaries


async def _get_db_analysis_stats(db: AsyncSession) -> dict:
    """从数据库获取分析统计。"""
    try:
        count_result = await db.execute(
            select(func.count(ProfitAnalysis.id))
        )
        total_records = count_result.scalar() or 0

        sku_count_result = await db.execute(
            select(func.count(func.distinct(ProfitAnalysis.sku_id)))
        )
        distinct_skus = sku_count_result.scalar() or 0

        latest_result = await db.execute(
            select(ProfitAnalysis.calc_time)
            .order_by(ProfitAnalysis.calc_time.desc())
            .limit(1)
        )
        latest_calc = latest_result.scalar_one_or_none()

        return {
            "total_profit_records": total_records,
            "distinct_skus": distinct_skus,
            "latest_calc_time": latest_calc.isoformat() if latest_calc else None,
        }
    except Exception as exc:
        logger.warning("获取数据库分析统计失败", extra={"error": str(exc)})
        return {
            "total_profit_records": 0,
            "distinct_skus": 0,
            "latest_calc_time": None,
            "db_error": str(exc),
        }


async def _get_sku_db_stats(db: AsyncSession, sku_id: str) -> dict:
    """从数据库获取单个 SKU 的分析统计。"""
    try:
        count_result = await db.execute(
            select(func.count(ProfitAnalysis.id))
            .where(ProfitAnalysis.sku_id == sku_id)
        )
        record_count = count_result.scalar() or 0

        avg_roi_result = await db.execute(
            select(func.avg(ProfitAnalysis.current_roi))
            .where(ProfitAnalysis.sku_id == sku_id)
        )
        avg_roi = avg_roi_result.scalar()

        return {
            "db_record_count": record_count,
            "db_avg_roi": round(float(avg_roi), 4) if avg_roi is not None else None,
        }
    except Exception:
        return {"db_record_count": 0, "db_avg_roi": None}
