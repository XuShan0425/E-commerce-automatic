"""费率解析 API — AI 抓取 + 解析 + 确认工作流 + 数据就绪检查."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.logging import get_logger
from App.core.security import verify_api_key
from App.models.base import Product, LogisticsRate, PlatformFee
from App.schemas.rates import (
    ConfirmFeesRequest,
    ConfirmLogisticsRequest,
    ParseResultFees,
    ParseResultLogistics,
)
from App.services.browser import BrowserService

logger = get_logger(__name__)

router = APIRouter(prefix="/rates", tags=["rates"])


# ══════════════════════════════════════════════════
# 原有端点（Playwright + 兼容保留）
# ══════════════════════════════════════════════════

@router.post("/parse-logistics", response_model=ParseResultLogistics)
async def parse_logistics(
    _api_key: str = Depends(verify_api_key),
) -> ParseResultLogistics:
    """抓取速卖通物流费率页面，AI 解析后返回预览。"""
    from App.services.rate_parser import parse_logistics_rates

    browser = BrowserService(headless=True)
    try:
        result = await parse_logistics_rates(browser)
        return result
    except Exception as exc:
        logger.exception("物流费率解析失败")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"解析失败: {exc}") from exc
    finally:
        browser.close()


@router.post("/parse-fees", response_model=ParseResultFees)
async def parse_fees(
    _api_key: str = Depends(verify_api_key),
) -> ParseResultFees:
    """抓取速卖通平台佣金页面，AI 解析后返回预览。"""
    from App.services.rate_parser import parse_platform_fees

    browser = BrowserService(headless=True)
    try:
        result = await parse_platform_fees(browser)
        return result
    except Exception as exc:
        logger.exception("平台佣金解析失败")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"解析失败: {exc}") from exc
    finally:
        browser.close()


@router.post("/confirm-logistics")
async def confirm_logistics(
    body: ConfirmLogisticsRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """确认物流费率并写入数据库。"""
    from App.services.rate_parser import confirm_logistics_rates

    if not body.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="items 不能为空")
    try:
        result = await confirm_logistics_rates(db, body)
        return {"status": "ok", **result}
    except Exception as exc:
        logger.exception("物流费率确认写入失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"写入失败: {exc}") from exc


@router.post("/confirm-fees")
async def confirm_fees(
    body: ConfirmFeesRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """确认平台佣金并写入数据库。"""
    from App.services.rate_parser import confirm_platform_fees

    if not body.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="items 不能为空")
    try:
        result = await confirm_platform_fees(db, body)
        return {"status": "ok", **result}
    except Exception as exc:
        logger.exception("平台佣金确认写入失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"写入失败: {exc}") from exc


# ══════════════════════════════════════════════════
# 新增端点：requests + AI 解析（轻量级，无需浏览器）
# ══════════════════════════════════════════════════

@router.post("/logistics/fetch")
async def fetch_logistics_rates(
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """抓取物流费率页面（requests + Claude AI），返回解析预览，不写库。"""
    from App.services.rate_parser_service import parse_logistics_rates

    try:
        raw_data = await parse_logistics_rates()
        items = []
        for item in raw_data:
            items.append({
                "destination_region": str(item.get("destination_region", "")).upper(),
                "weight_range_min": float(item.get("weight_range_min", 0)),
                "weight_range_max": float(item.get("weight_range_max", 0)),
                "cost": float(item.get("cost", 0)),
            })
        return {"status": "parsed", "count": len(items), "data": items}
    except Exception as exc:
        logger.exception("物流费率 AI 解析失败")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"解析失败: {exc}") from exc


@router.post("/logistics/confirm")
async def confirm_logistics_rates_new(
    body: ConfirmLogisticsRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """确认物流费率并写入数据库。"""
    from App.services.rate_parser import confirm_logistics_rates

    if not body.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="items 不能为空")
    try:
        result = await confirm_logistics_rates(db, body)
        return {"status": "ok", "saved": result.get("inserted", 0) + result.get("replaced", 0)}
    except Exception as exc:
        logger.exception("物流费率写入失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"写入失败: {exc}") from exc


@router.get("/logistics")
async def get_logistics_rates(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """返回当前物流费率表。"""
    result = await db.execute(select(LogisticsRate).order_by(LogisticsRate.destination_region))
    rates = result.scalars().all()
    return {
        "status": "ok",
        "count": len(rates),
        "data": [
            {
                "id": r.id,
                "destination_region": r.destination_region,
                "weight_range_min": float(r.weight_range_min),
                "weight_range_max": float(r.weight_range_max),
                "cost": float(r.cost),
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rates
        ],
    }


@router.post("/commission/fetch")
async def fetch_commission_rates(
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """抓取平台佣金页面（requests + Claude AI），返回解析预览，不写库。"""
    from App.services.rate_parser_service import parse_commission_rates

    try:
        raw_data = await parse_commission_rates()
        items = []
        for item in raw_data:
            items.append({
                "category": str(item.get("category", "")),
                "fee_rate": float(item.get("fee_rate", 0)),
            })
        return {"status": "parsed", "count": len(items), "data": items}
    except Exception as exc:
        logger.exception("平台佣金 AI 解析失败")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"解析失败: {exc}") from exc


@router.post("/commission/confirm")
async def confirm_commission_rates(
    body: ConfirmFeesRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """确认平台佣金并写入数据库。"""
    from App.services.rate_parser import confirm_platform_fees

    if not body.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="items 不能为空")
    try:
        result = await confirm_platform_fees(db, body)
        return {"status": "ok", "saved": result.get("inserted", 0) + result.get("replaced", 0)}
    except Exception as exc:
        logger.exception("平台佣金写入失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"写入失败: {exc}") from exc


@router.get("/commission")
async def get_commission_rates(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """返回当前平台佣金费率表。"""
    result = await db.execute(select(PlatformFee).order_by(PlatformFee.category))
    fees = result.scalars().all()
    return {
        "status": "ok",
        "count": len(fees),
        "data": [
            {
                "id": f.id,
                "category": f.category,
                "fee_rate": float(f.fee_rate),
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            }
            for f in fees
        ],
    }


@router.get("/readiness")
async def check_rates_readiness(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """检查成本与费率数据是否就绪，供 AI 分析引擎调用。"""
    missing: list[str] = []

    total_products = await db.scalar(select(func.count(Product.id)))
    if total_products and total_products > 0:
        no_cost = await db.scalar(
            select(func.count(Product.id)).where(
                (Product.cost_price.is_(None)) | (Product.cost_price <= 0)
            )
        )
        if no_cost and no_cost > 0:
            missing.append(f"cost_price: {no_cost} 个商品未设置成本价（共 {total_products} 个）")
    else:
        missing.append("cost_price: 暂无商品数据")

    logistics_count = await db.scalar(select(func.count(LogisticsRate.id)))
    if not logistics_count or logistics_count == 0:
        missing.append("物流费率: 未初始化（logistics_rates 表为空）")

    fee_count = await db.scalar(select(func.count(PlatformFee.id)))
    if not fee_count or fee_count == 0:
        missing.append("平台佣金: 未初始化（platform_fees 表为空）")

    return {
        "ready": len(missing) == 0,
        "missing": missing,
        "stats": {
            "total_products": total_products or 0,
            "products_without_cost": no_cost or 0,
            "logistics_rate_count": logistics_count or 0,
            "platform_fee_count": fee_count or 0,
        },
    }
