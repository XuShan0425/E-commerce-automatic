"""分析管线 — 串联 profit_calculator → decision_engine → boundary_checker → roi_forecaster."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import async_session_factory
from App.core.logging import get_logger
from App.models.base import PriceSnapshot, Product
from App.services.analysis_monitor import get_metrics
from App.services.boundary_checker import check_boundaries
from App.services.decision_engine import generate_decision
from App.services.feedback_service import get_decision_history
from App.services.profit_calculator import (
    _get_ad_snapshots_7d,
    _get_platform_fee_rate,
    _get_product,
    compute_profit,
)
from App.services.roi_forecaster import forecast_roi

logger = get_logger(__name__)

# 并发控制：AI 分析的最大并发数，避免 API 限流
_MAX_CONCURRENT_AI = 5


async def analyze_single_sku(
    db: AsyncSession,
    sku_id: str,
    *,
    skip_ai: bool = False,
) -> dict[str, Any]:
    """分析单个 SKU：计算利润 → AI 决策 → 边界检查。

    Args:
        db: 数据库会话
        sku_id: 商品 SKU ID
        skip_ai: 跳过 AI 决策（仅做利润计算和边界检查）

    Returns:
        完整分析结果 dict
    """
    _start = time.monotonic()

    result: dict[str, Any] = {
        "sku_id": sku_id,
        "analyzed_at": datetime.now(UTC).isoformat(),
        "success": False,
        "profit": None,
        "forecast": None,
        "decision": None,
        "boundary": None,
        "error": None,
    }

    # ── Step 1: 利润计算 ──────────────────────────
    product = await _get_product(db, sku_id)
    if product is None:
        result["error"] = f"SKU '{sku_id}' 不存在"
        _record_metrics(sku_id, result, _start)
        return result

    try:
        profit = await compute_profit(db, sku_id)
        result["profit"] = {
            "id": profit.id,
            "cost_price": float(product.cost_price),
            "logistics_cost": float(profit.logistics_cost),
            "platform_fee": float(profit.platform_fee),
            "true_cost": float(profit.true_cost),
            "gross_margin": float(profit.gross_margin),
            "breakeven_ad_spend": float(profit.breakeven_ad_spend),
            "current_roi": float(profit.current_roi),
            "roi_7d_trend": profit.roi_7d_trend,
        }

        # ── Step 1.5: ROI 预测 ───────────────────────
        try:
            forecast = await forecast_roi(db, sku_id, days_ahead=7)
            result["forecast"] = forecast
        except Exception as exc:
            result["forecast"] = {
                "sku_id": sku_id,
                "warning": f"ROI 预测失败: {exc}",
                "forecast": [],
                "historical": [],
                "trend_direction": "unknown",
                "regression": None,
            }
            logger.warning("ROI 预测异常 (SKU=%s): %s", sku_id, exc)

    except Exception as exc:
        result["error"] = f"利润计算失败: {exc}"
        logger.exception("利润计算失败", extra={"sku_id": sku_id})
        return result

    # ── Step 2: AI 决策生成 ────────────────────────
    if skip_ai:
        result["decision"] = {
            "decision_type": "no_action",
            "reasoning": "AI 分析已跳过（skip_ai=True）",
            "confidence": 0.0,
            "risk_level": "low",
        }
        result["boundary"] = {"passed": True}
        result["success"] = True
        _record_metrics(sku_id, result, _start)
        return result

    snapshots_7d = await _get_ad_snapshots_7d(db, sku_id)
    result["snapshots_7d"] = snapshots_7d  # 传递给执行层用于生成关闭报告
    fee_rate = await _get_platform_fee_rate(db, product.category)

    # ── 反馈闭环：查询决策历史 ────────────────
    decision_history = await get_decision_history(db, sku_id)
    result["decision_history"] = decision_history

    price_result = await db.execute(
        select(PriceSnapshot.current_price)
        .where(PriceSnapshot.sku_id == sku_id)
        .order_by(PriceSnapshot.snapshot_time.desc())
        .limit(1)
    )
    price_row = price_result.scalar_one_or_none()
    current_price = float(price_row) if price_row else float(product.cost_price)

    used_ai = True
    try:
        decision = await generate_decision(
            db, sku_id,
            cost_price=float(product.cost_price),
            current_price=current_price,
            logistics_cost=float(profit.logistics_cost),
            platform_fee_rate=fee_rate,
            profit=profit,
            snapshots_7d=snapshots_7d,
            decision_history=decision_history,
        )
        result["decision"] = decision
    except ValueError as exc:
        # API key 未配置
        used_ai = False
        result["decision"] = {
            "decision_type": "no_action",
            "reasoning": f"AI 决策跳过（API key 未配置）: {exc}",
            "confidence": 0.0,
            "risk_level": "low",
        }
        result["boundary"] = {"passed": True}
        result["success"] = True
        _record_metrics(sku_id, result, _start)
        return result
    except Exception as exc:
        result["decision"] = {
            "decision_type": "no_action",
            "reasoning": f"AI 调用失败: {exc}",
            "confidence": 0.0,
            "risk_level": "high",
        }
        result["boundary"] = {"passed": False, "boundary_type": "hard", "reason": str(exc)}
        result["success"] = True  # 利润已计算，只是 AI 失败了
        _record_metrics(sku_id, result, _start, used_ai=True)
        return result

    # ── Step 3: 边界检查 ──────────────────────────
    try:
        boundary = await check_boundaries(db, sku_id, decision, profit)
        result["boundary"] = {
            "passed": boundary.passed,
            "boundary_type": boundary.boundary_type,
            "reason": boundary.reason,
        }
    except Exception as exc:
        result["boundary"] = {
            "passed": False,
            "boundary_type": "hard",
            "reason": f"边界检查异常: {exc}",
        }
        logger.exception("边界检查异常", extra={"sku_id": sku_id})

    result["success"] = True
    decision_type = (
        result["decision"].get("decision_type", "?")
        if result.get("decision") else "?"
    )
    boundary_status = (
        "passed" if result.get("boundary", {}).get("passed") else "blocked"
    )
    logger.info(
        "分析完成",
        extra={
            "sku_id": sku_id,
            "decision_type": decision_type,
            "boundary": boundary_status,
        },
    )
    _record_metrics(sku_id, result, _start, used_ai=used_ai)
    return result


def _record_metrics(
    sku_id: str,
    result: dict[str, Any],
    start: float,
    *,
    used_ai: bool = False,
) -> None:
    """将分析结果记录到监控指标。"""
    duration_ms = (time.monotonic() - start) * 1000
    metrics = get_metrics()
    success = result.get("success", False)
    decision_type = (result.get("decision") or {}).get("decision_type")
    boundary = result.get("boundary") or {}
    boundary_passed = boundary.get("passed")
    error = result.get("error")
    metrics.record_run(
        sku_id=sku_id,
        duration_ms=duration_ms,
        success=success,
        decision_type=decision_type,
        boundary_passed=boundary_passed,
        error=error,
        used_ai=used_ai,
    )


async def analyze_all_skus(
    db: AsyncSession,
    *,
    skip_ai: bool = False,
) -> dict[str, Any]:
    """对所有已注册商品执行分析。

    Returns:
        {"total": int, "analyzed": int, "results": list[dict], "summary": dict}
    """
    result = await db.execute(select(Product).where(Product.is_tracked))
    products = list(result.scalars().all())

    if not products:
        return {
            "total": 0,
            "analyzed": 0,
            "results": [],
            "summary": {"message": "没有已注册的商品"},
        }

    all_results = []

    sem = asyncio.Semaphore(_MAX_CONCURRENT_AI)

    async def _analyze_one(product: Product) -> dict[str, Any]:
        async with sem:
            async with async_session_factory() as task_db:
                try:
                    return await analyze_single_sku(task_db, product.sku_id, skip_ai=skip_ai)
                finally:
                    await task_db.commit()

    tasks = [_analyze_one(product) for product in products]
    for coro in asyncio.as_completed(tasks):
        all_results.append(await coro)

    # 汇总
    passed_count = sum(
        1 for r in all_results
        if r.get("boundary") and r["boundary"].get("passed")
    )
    ai_decisions = {}
    for r in all_results:
        d = r.get("decision") or {}
        dt = d.get("decision_type", "unknown")
        ai_decisions[dt] = ai_decisions.get(dt, 0) + 1

    return {
        "total": len(products),
        "analyzed": sum(1 for r in all_results if r.get("success")),
        "results": all_results,
        "summary": {
            "boundary_passed": passed_count,
            "decisions": ai_decisions,
        },
    }
