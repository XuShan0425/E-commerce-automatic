"""费率解析 API — AI 抓取 + 解析 + 确认工作流."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.logging import get_logger
from App.core.security import verify_api_key
from App.schemas.rates import (
    ConfirmFeesRequest,
    ConfirmLogisticsRequest,
    ParseResultFees,
    ParseResultLogistics,
)
from App.services.browser import BrowserService

logger = get_logger(__name__)

router = APIRouter(prefix="/rates", tags=["rates"])


# ── 解析（抓取 + AI 解析，返回预览）───────────────

@router.post("/parse-logistics", response_model=ParseResultLogistics)
async def parse_logistics(
    _api_key: str = Depends(verify_api_key),
) -> ParseResultLogistics:
    """抓取速卖通物流费率页面，AI 解析后返回预览。

    返回的数据为未确认状态，需要调用 /confirm-logistics 确认后才会写入数据库。
    """
    from App.services.rate_parser import parse_logistics_rates

    browser = BrowserService(headless=True)
    try:
        result = await parse_logistics_rates(browser)
        return result
    except Exception as exc:
        logger.exception("物流费率解析失败")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"解析失败: {exc}",
        ) from exc
    finally:
        browser.close()


@router.post("/parse-fees", response_model=ParseResultFees)
async def parse_fees(
    _api_key: str = Depends(verify_api_key),
) -> ParseResultFees:
    """抓取速卖通平台佣金页面，AI 解析后返回预览。

    返回的数据为未确认状态，需要调用 /confirm-fees 确认后才会写入数据库。
    """
    from App.services.rate_parser import parse_platform_fees

    browser = BrowserService(headless=True)
    try:
        result = await parse_platform_fees(browser)
        return result
    except Exception as exc:
        logger.exception("平台佣金解析失败")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"解析失败: {exc}",
        ) from exc
    finally:
        browser.close()


# ── 确认写入 ────────────────────────────────────

@router.post("/confirm-logistics")
async def confirm_logistics(
    body: ConfirmLogisticsRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """确认物流费率并写入数据库。

    将 AI 解析（或手动编辑后）的物流费率数据正式写入 logistics_rates 表。
    设置 overwrite=True 会清空已有数据再写入。
    """
    from App.services.rate_parser import confirm_logistics_rates

    if not body.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="items 不能为空",
        )

    try:
        result = await confirm_logistics_rates(db, body)
        return {"status": "ok", **result}
    except Exception as exc:
        logger.exception("物流费率确认写入失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"写入失败: {exc}",
        ) from exc


@router.post("/confirm-fees")
async def confirm_fees(
    body: ConfirmFeesRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """确认平台佣金并写入数据库。

    将 AI 解析（或手动编辑后）的平台佣金数据正式写入 platform_fees 表。
    设置 overwrite=True 会清空已有数据再写入。
    """
    from App.services.rate_parser import confirm_platform_fees

    if not body.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="items 不能为空",
        )

    try:
        result = await confirm_platform_fees(db, body)
        return {"status": "ok", **result}
    except Exception as exc:
        logger.exception("平台佣金确认写入失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"写入失败: {exc}",
        ) from exc
