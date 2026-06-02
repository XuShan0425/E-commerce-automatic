"""执行引擎 — 接收分析结果 → 边界验证 → dispatch 执行器 → 写操作日志."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.operation_log import OperationLog
from App.services.adjuster import run_executor
from App.services.alert_service import raise_alert
from App.services.boundary_checker import generate_closure_report
from App.services.browser import BrowserService
from App.services.cookie_manager import CookieManager
from App.services.operation_logger import log_operation, update_log_status

logger = get_logger(__name__)


async def execute_decision(
    db: AsyncSession,
    analysis_result: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """执行单个 SKU 的 AI 决策。

    Args:
        db: 数据库会话
        analysis_result: analyze_single_sku() 的返回结果
        dry_run: True 时只写日志不实际执行浏览器操作

    Returns:
         执行结果 dict
    """
    sku_id = analysis_result.get("sku_id", "unknown")
    decision = analysis_result.get("decision") or {}
    boundary = analysis_result.get("boundary") or {}
    profit = analysis_result.get("profit") or {}

    decision_type = decision.get("decision_type", "no_action")
    action = decision.get("action") or {}
    reasoning = decision.get("reasoning", "")
    confidence = decision.get("confidence", 0.0)

    result: dict[str, Any] = {
        "sku_id": sku_id,
        "decision_type": decision_type,
        "executed": False,
        "status": "skipped",
        "reason": "",
    }

    # ── no_action: 无需执行，记录日志即可 ─────────
    if decision_type == "no_action":
        await log_operation(
            db, sku_id, "no_action",
            ai_confidence=confidence,
            ai_reasoning=reasoning,
            status="success",
            details={"message": "AI 建议维持现状，无需调整"},
        )
        result["status"] = "success"
        result["reason"] = "no_action — 无需执行"
        return result

    # ── 硬边界：已拦截 ────────────────────────────
    if not boundary.get("passed"):
        boundary_type = boundary.get("boundary_type", "hard")
        reason_text = boundary.get("reason", "未知边界条件")

        if boundary_type == "hard":
            await log_operation(
                db, sku_id, decision_type,
                field_name=action.get("field"),
                old_value=action.get("current_value"),
                new_value=action.get("new_value"),
                ai_confidence=confidence,
                ai_reasoning=reasoning,
                status="failed",
                details={"boundary_type": "hard", "reason": reason_text},
            )
            await raise_alert(
                db,
                "execution_blocked_hard",
                f"[{sku_id}] {decision_type} 被硬边界拦截: {reason_text}",
                severity="warning",
            )
            result["reason"] = f"硬边界拦截: {reason_text}"
            return result

        # ── 软边界：待人工确认 ─────────────────────
        if boundary_type == "soft":
            # 生成关闭说明报告（如果是 stop_ad 类型）
            closure_report = None
            if decision_type == "stop_ad":
                closure_report = await generate_closure_report(
                    db, sku_id, decision,
                    profit=analysis_result.get("profit"),
                    snapshots_7d=analysis_result.get("snapshots_7d"),
                )

            log = await log_operation(
                db, sku_id, decision_type,
                field_name=action.get("field"),
                old_value=action.get("current_value"),
                new_value=action.get("new_value"),
                ai_confidence=confidence,
                ai_reasoning=reasoning,
                status="pending_confirmation",
                details={
                    "boundary_type": "soft",
                    "reason": reason_text,
                    "decision": decision,
                    "profit": profit,
                    "closure_report": closure_report,
                },
            )
            await raise_alert(
                db,
                "execution_pending",
                f"[{sku_id}] {decision_type} 需要人工确认: {reason_text}",
                severity="warning",
            )
            result["status"] = "pending_confirmation"
            result["operation_log_id"] = log.id
            result["reason"] = f"软边界 — 待确认 (log_id={log.id})"
            return result

    # ── 边界通过：执行 ────────────────────────────
    if dry_run:
        await log_operation(
            db, sku_id, decision_type,
            field_name=action.get("field"),
            old_value=action.get("current_value"),
            new_value=action.get("new_value"),
            ai_confidence=confidence,
            ai_reasoning=reasoning,
            status="success",
            details={"dry_run": True},
        )
        result["executed"] = True
        result["status"] = "success"
        result["reason"] = "dry_run — 仅记录日志"
        return result

    # 实际执行
    try:
        exec_result = await _run_adjuster(
            db, sku_id, decision_type, decision, action,
            reasoning, confidence,
        )
        result["executed"] = True
        result["status"] = "success" if exec_result.get("success") else "failed"
        result["adjuster_result"] = exec_result

        if not exec_result.get("success"):
            await raise_alert(
                db,
                "execution_failed",
                f"[{sku_id}] {decision_type} 执行失败: {exec_result.get('error', '未知错误')}",
                severity="critical",
            )

    except Exception as exc:
        logger.exception("执行异常: SKU=%s type=%s", sku_id, decision_type)
        await log_operation(
            db, sku_id, decision_type,
            field_name=action.get("field"),
            old_value=action.get("current_value"),
            new_value=action.get("new_value"),
            ai_confidence=confidence,
            ai_reasoning=reasoning,
            status="failed",
            details={"error": str(exc)},
        )
        await raise_alert(
            db,
            "execution_crash",
            f"[{sku_id}] 执行崩溃: {exc}",
            severity="critical",
            set_global_stop=True,
        )
        result["status"] = "failed"
        result["reason"] = str(exc)

    return result


async def _run_adjuster(
    db: AsyncSession,
    sku_id: str,
    decision_type: str,
    decision: dict,
    action: dict,
    reasoning: str,
    confidence: float,
) -> dict[str, Any]:
    """在后台线程中执行浏览器调整操作。"""
    cookie_mgr = CookieManager(db)
    cookies = await cookie_mgr.load_cookies("aliexpress.com")

    kwargs: dict[str, Any] = {"sku_id": sku_id, "cookies": cookies}
    if decision_type == "adjust_bid":
        kwargs["old_budget"] = action.get("current_value", 0)
        kwargs["new_budget"] = action.get("new_value", 0)
    elif decision_type == "adjust_price":
        kwargs["current_price"] = action.get("current_value", 0)
        kwargs["new_price"] = action.get("new_value", 0)
    elif decision_type == "switch_ad_type":
        kwargs["new_type"] = action.get("new_value", "standard")
    # stop_ad 不需要额外参数

    # 在后台线程中执行同步浏览器操作
    loop = asyncio.get_event_loop()

    def _sync_execute() -> dict[str, Any]:
        browser_svc = BrowserService(headless=True)
        try:
            return run_executor(decision_type, browser_svc, **kwargs)
        finally:
            browser_svc.close()

    exec_result = await loop.run_in_executor(None, _sync_execute)

    # 记录操作日志
    await log_operation(
        db, sku_id, decision_type,
        field_name=action.get("field"),
        old_value=action.get("current_value"),
        new_value=action.get("new_value"),
        ai_confidence=confidence,
        ai_reasoning=reasoning,
        status="success" if exec_result.get("success") else "failed",
        details={"adjuster_result": exec_result},
    )

    return exec_result


async def execute_all_passed(
    db: AsyncSession,
    analysis_results: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """批量执行所有分析结果中的通过决策。

    Args:
        db: 数据库会话
        analysis_results: analyze_all_skus() 返回的 results 列表
        dry_run: 仅记录日志不实际执行浏览器操作

    Returns:
        {"total": int, "executed": int, "skipped": int,
         "pending": int, "failed": int, "results": [...]}
    """
    executed = 0
    skipped = 0
    pending = 0
    failed = 0
    all_results = []

    for ar in analysis_results:
        if not ar.get("success"):
            skipped += 1
            continue

        result = await execute_decision(db, ar, dry_run=dry_run)

        if result.get("executed"):
            executed += 1
        elif result.get("status") == "pending_confirmation":
            pending += 1
        elif result.get("status") == "failed":
            failed += 1
        else:
            skipped += 1

        all_results.append(result)

    return {
        "total": len(analysis_results),
        "executed": executed,
        "skipped": skipped,
        "pending": pending,
        "failed": failed,
        "results": all_results,
    }


async def confirm_pending(
    db: AsyncSession,
    operation_log_id: int,
) -> dict[str, Any]:
    """确认一个待确认的操作并执行它。

    Args:
        db: 数据库会话
        operation_log_id: 待确认的操作日志 ID

    Returns:
         执行结果 dict
    """
    log = await db.get(OperationLog, operation_log_id)
    if log is None:
        return {"success": False, "error": f"操作日志 {operation_log_id} 不存在"}
    if log.status != "pending_confirmation":
        return {"success": False, "error": f"操作日志状态为 '{log.status}'，非待确认"}

    details = log.details or {}

    # 执行
    try:
        exec_result = await _run_adjuster(
            db, log.sku_id, log.operation_type,
            details.get("decision", {}),
            {
                "field": log.field_name,
                "current_value": float(log.old_value) if log.old_value else None,
                "new_value": float(log.new_value) if log.new_value else None,
            },
            log.ai_reasoning or "",
            float(log.ai_confidence) if log.ai_confidence else 0.0,
        )

        status = "success" if exec_result.get("success") else "failed"
        await update_log_status(db, operation_log_id, status)

        if status == "failed":
            await raise_alert(
                db,
                "execution_confirmed_failed",
                f"[{log.sku_id}] 已确认操作执行失败: {exec_result.get('error', '未知错误')}",
                severity="critical",
            )

        return {"success": True, "status": status, "adjuster_result": exec_result}

    except Exception as exc:
        await update_log_status(db, operation_log_id, "failed", error_details={"error": str(exc)})
        await raise_alert(
            db,
            "execution_confirmed_crash",
            f"[{log.sku_id}] 确认执行崩溃: {exc}",
            severity="critical",
        )
        return {"success": False, "error": str(exc)}


async def reject_pending(
    db: AsyncSession,
    operation_log_id: int,
) -> dict[str, Any]:
    """拒绝一个待确认的操作。

    Args:
        db: 数据库会话
        operation_log_id: 待确认的操作日志 ID

    Returns:
         结果 dict
    """
    log = await db.get(OperationLog, operation_log_id)
    if log is None:
        return {"success": False, "error": f"操作日志 {operation_log_id} 不存在"}
    if log.status != "pending_confirmation":
        return {"success": False, "error": f"操作日志状态为 '{log.status}'，非待确认"}

    await update_log_status(db, operation_log_id, "rejected")
    logger.info(
        "已拒绝操作: log_id=%d SKU=%s type=%s",
        operation_log_id, log.sku_id, log.operation_type,
    )

    return {"success": True, "status": "rejected", "sku_id": log.sku_id}
