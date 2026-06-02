"""执行层 API — 触发执行 + 待确认管理 + 操作日志查询 + 活动管理."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.logging import get_logger
from App.core.security import verify_api_key

logger = get_logger(__name__)

router = APIRouter(prefix="/execution", tags=["execution"])


# ── 活动管理请求模型 ──────────────────────────────


class CampaignActionRequest(BaseModel):
    """活动管理请求体。"""
    sku_id: str


# ── 执行触发 ────────────────────────────────────

@router.post("/run")
async def execute_all(
    dry_run: bool = Query(False, description="仅记录日志，不实际操作浏览器"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """对所有商品执行 AI 分析 → 决策执行。

    先调用分析管线获取决策，再逐个执行。
    设置 dry_run=true 只记录日志不实际操作。
    """
    from App.services.analysis_pipeline import analyze_all_skus
    from App.services.execution_engine import execute_all_passed

    try:
        analysis = await analyze_all_skus(db, skip_ai=False)
        if analysis["total"] == 0:
            return {"status": "ok", "message": "没有已注册的商品", "execution": None}

        exec_result = await execute_all_passed(db, analysis["results"], dry_run=dry_run)
        return {
            "status": "ok",
            "analysis_summary": analysis["summary"],
            "execution": exec_result,
        }

    except Exception as exc:
        logger.exception("批量执行失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行失败: {exc}",
        ) from exc


@router.post("/run/{sku_id}")
async def execute_single(
    sku_id: str,
    dry_run: bool = Query(False, description="仅记录日志，不实际操作浏览器"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """对单个 SKU 执行 AI 分析 → 决策执行。"""
    from App.services.analysis_pipeline import analyze_single_sku
    from App.services.execution_engine import execute_decision

    try:
        analysis = await analyze_single_sku(db, sku_id, skip_ai=False)
        if analysis.get("error") and not analysis.get("success"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=analysis["error"],
            )

        exec_result = await execute_decision(db, analysis, dry_run=dry_run)
        return {
            "status": "ok",
            "analysis": analysis,
            "execution": exec_result,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("单品执行失败: SKU=%s", sku_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行失败: {exc}",
        ) from exc


# ── 待确认操作管理 ──────────────────────────────

@router.get("/pending")
async def list_pending(
    limit: int = Query(50, ge=1, le=200, description="返回条数上限"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """列出所有待人工确认的操作（软边界暂停的决策）。"""
    from App.services.operation_logger import get_pending_operations

    logs = await get_pending_operations(db, limit=limit)
    return [
        {
            "id": log.id,
            "sku_id": log.sku_id,
            "operation_type": log.operation_type,
            "field_name": log.field_name,
            "old_value": float(log.old_value) if log.old_value else None,
            "new_value": float(log.new_value) if log.new_value else None,
            "ai_confidence": float(log.ai_confidence) if log.ai_confidence else None,
            "ai_reasoning": log.ai_reasoning,
            "status": log.status,
            "executed_at": log.executed_at.isoformat() if log.executed_at else None,
            "details": log.details,
        }
        for log in logs
    ]


@router.post("/pending/{log_id}/confirm")
async def confirm_pending_op(
    log_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """确认一个待确认的操作，立即执行。"""
    from App.services.execution_engine import confirm_pending

    try:
        result = await confirm_pending(db, log_id)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "确认失败"),
            )
        return {"status": "ok", **result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("确认操作失败: log_id=%d", log_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"确认失败: {exc}",
        ) from exc


@router.post("/pending/{log_id}/reject")
async def reject_pending_op(
    log_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """拒绝一个待确认的操作，不执行。"""
    from App.services.execution_engine import reject_pending

    try:
        result = await reject_pending(db, log_id)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "拒绝失败"),
            )
        return {"status": "ok", **result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("拒绝操作失败: log_id=%d", log_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"拒绝失败: {exc}",
        ) from exc


# ── 操作日志查询 ────────────────────────────────

@router.get("/logs")
async def get_execution_logs(
    sku_id: str | None = Query(None, description="按 SKU 筛选"),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="按状态筛选: success/failed/pending_confirmation/rejected",
    ),
    operation_type: str | None = Query(None, description="按操作类型筛选"),
    limit: int = Query(100, ge=1, le=500, description="返回条数上限"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """查询操作日志，支持多条件筛选。"""
    from App.services.operation_logger import get_logs

    logs = await get_logs(
        db,
        sku_id=sku_id,
        status=status_filter,
        operation_type=operation_type,
        limit=limit,
    )
    return [
        {
            "id": log.id,
            "sku_id": log.sku_id,
            "operation_type": log.operation_type,
            "field_name": log.field_name,
            "old_value": float(log.old_value) if log.old_value else None,
            "new_value": float(log.new_value) if log.new_value else None,
            "ai_confidence": float(log.ai_confidence) if log.ai_confidence else None,
            "ai_reasoning": log.ai_reasoning,
            "status": log.status,
            "executed_at": log.executed_at.isoformat() if log.executed_at else None,
            "details": log.details,
        }
        for log in logs
    ]


# ── 活动管理 ──────────────────────────────────────


@router.post("/campaign/pause")
async def api_pause_campaign(
    body: CampaignActionRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """暂停指定 SKU 的推广活动。"""
    from App.services.operation_logger import log_operation

    try:
        exec_result = await _run_campaign_sync(db, "pause_campaign", body.sku_id)

        await log_operation(
            db, body.sku_id, "pause_campaign",
            status="success" if exec_result.get("success") else "failed",
            details={"adjuster_result": exec_result},
        )

        if not exec_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=exec_result.get("error", "暂停活动失败"),
            )

        return {"status": "ok", "operation": "pause_campaign", "sku_id": body.sku_id, "adjuster_result": exec_result}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("pause_campaign API 异常: SKU=%s", body.sku_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"暂停活动失败: {exc}",
        ) from exc


@router.post("/campaign/resume")
async def api_resume_campaign(
    body: CampaignActionRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """恢复指定 SKU 已暂停的推广活动。"""
    from App.services.operation_logger import log_operation

    try:
        exec_result = await _run_campaign_sync(db, "resume_campaign", body.sku_id)

        await log_operation(
            db, body.sku_id, "resume_campaign",
            status="success" if exec_result.get("success") else "failed",
            details={"adjuster_result": exec_result},
        )

        if not exec_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=exec_result.get("error", "恢复活动失败"),
            )

        return {"status": "ok", "operation": "resume_campaign", "sku_id": body.sku_id, "adjuster_result": exec_result}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("resume_campaign API 异常: SKU=%s", body.sku_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复活动失败: {exc}",
        ) from exc


@router.post("/campaign/stop")
async def api_stop_campaign(
    body: CampaignActionRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """停止指定 SKU 的推广活动（软边界操作，需要人工确认）。

    此操作会触发软边界检查，写入待确认日志并发送警报。
    人工确认后通过 POST /execution/pending/{log_id}/confirm 执行。
    """
    from App.services.operation_logger import log_operation
    from App.services.alert_service import raise_alert

    try:
        # 写入待确认操作日志（软边界暂停）
        log = await log_operation(
            db, body.sku_id, "stop_campaign",
            status="pending_confirmation",
            details={
                "boundary_type": "soft",
                "reason": "决定关闭推广活动，需要人工确认",
                "sku_id": body.sku_id,
            },
        )

        # 发送警报
        await raise_alert(
            db,
            "execution_pending",
            f"[{body.sku_id}] 关闭推广活动需要人工确认",
            severity="warning",
        )

        logger.info("stop_campaign 已暂停等待确认: SKU=%s log_id=%d", body.sku_id, log.id)

        return {
            "status": "pending_confirmation",
            "operation": "stop_campaign",
            "sku_id": body.sku_id,
            "operation_log_id": log.id,
            "message": f"关闭推广活动需要人工确认，请访问 POST /execution/pending/{log.id}/confirm 确认执行",
        }

    except Exception as exc:
        logger.exception("stop_campaign API 异常: SKU=%s", body.sku_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止活动失败: {exc}",
        ) from exc


async def _run_campaign_sync(
    db: AsyncSession,
    operation: str,
    sku_id: str,
) -> dict:
    """在后台线程中同步执行活动管理浏览器操作。"""
    from App.services.adjuster import run_executor
    from App.services.browser import BrowserService
    from App.services.cookie_manager import CookieManager

    cookie_mgr = CookieManager(db)
    cookies = await cookie_mgr.load_cookies("aliexpress.com")

    loop = asyncio.get_event_loop()

    def _sync_execute() -> dict:
        browser_svc = BrowserService(headless=True)
        try:
            return run_executor(operation, browser_svc, sku_id=sku_id, cookies=cookies)
        finally:
            browser_svc.close()

    return await loop.run_in_executor(None, _sync_execute)
