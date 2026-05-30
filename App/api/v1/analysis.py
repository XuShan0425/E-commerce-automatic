"""AI 分析 API — 触发分析 + 结果查询."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.models.base import ProfitAnalysis
from App.schemas.profit_analysis import ProfitAnalysisRead

logger = logging.getLogger(__name__)

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
    """查看某 SKU 的历史利润分析记录。"""
    result = await db.execute(
        select(ProfitAnalysis)
        .where(ProfitAnalysis.sku_id == sku_id)
        .order_by(ProfitAnalysis.calc_time.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    return [ProfitAnalysisRead.model_validate(r) for r in records]


@router.get("/latest", response_model=list[ProfitAnalysisRead])
async def get_latest_analysis(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[ProfitAnalysisRead]:
    """获取所有 SKU 的最新一次分析结果。"""
    from sqlalchemy import and_

    # 子查询：每个 sku_id 的最新 calc_time
    subq = (
        select(
            ProfitAnalysis.sku_id,
            func.max(ProfitAnalysis.calc_time).label("max_time"),
        )
        .group_by(ProfitAnalysis.sku_id)
        .subquery()
    )

    from sqlalchemy import func
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
    return [ProfitAnalysisRead.model_validate(r) for r in records]
