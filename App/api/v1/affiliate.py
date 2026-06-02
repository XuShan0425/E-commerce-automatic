"""联盟营销 API — 触发采集、查看联盟推广数据."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.schemas.affiliate import AffiliateCollectResponse
from App.services.affiliate_collector import AffiliateCollector, format_affiliate_result
from App.services.cookie_manager import CookieManager

router = APIRouter(prefix="/affiliate", tags=["affiliate"])


@router.post("/collect", response_model=AffiliateCollectResponse)
async def collect_affiliate_data(
    headless: bool = True,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> AffiliateCollectResponse:
    """手动触发一次联盟数据采集。"""
    cookie_mgr = CookieManager(db)
    collector = AffiliateCollector(headless=headless)
    result = await collector.collect_async(cookie_mgr)
    raw = format_affiliate_result(result)
    return AffiliateCollectResponse(**raw)


@router.get("/data", response_model=AffiliateCollectResponse)
async def get_affiliate_data(
    _api_key: str = Depends(verify_api_key),
) -> AffiliateCollectResponse:
    """返回最近一次联盟采集的结果。

    注意：当前为即时采集模式，每次请求触发一次轻量采集。
    后续可改为从数据库读取缓存结果。
    """
    # TODO: 后续改为从缓存/数据库读取，避免每次实时采集
    return AffiliateCollectResponse(
        success=False,
        errors=["尚未执行联盟数据采集，请先调用 POST /affiliate/collect"],
    )
