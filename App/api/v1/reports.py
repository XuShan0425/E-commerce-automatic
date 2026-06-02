"""报告查询 & 生成 & 调度 API 端点."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.schemas.report import ReportListItem, ReportRead
from App.services.report_generator import get_report_generator
from App.services.report_service import get_report, list_reports
from App.services.scheduler import (
    ReportSchedule,
    get_report_scheduler,
    init_report_scheduler,
)

router = APIRouter(prefix="/reports", tags=["reports"])


# ── Schemas ──────────────────────────────────────


class GenerateRequest(BaseModel):
    """手动生成报告请求。"""
    report_type: str = "scheduled"
    sku_id: str = ""
    title: str = ""
    output_format: str = "pdf"  # "pdf" | "csv"


class ScheduleRequest(BaseModel):
    """定时报告请求。"""
    report_type: str = "scheduled"
    sku_id: str
    cron_expr: str  # e.g. "0 8 * * *"
    output_format: str = "pdf"
    channels: list[str] = []
    title: str = ""


# ── 查询端点 ─────────────────────────────────────


@router.get("/", response_model=list[ReportListItem])
async def list_reports_endpoint(
    sku_id: str | None = Query(None, description="按 SKU ID 筛选"),
    report_type: str | None = Query(
        None, description="按报告类型筛选 (roi_negative / campaign_close)"
    ),
    limit: int = Query(50, ge=1, le=200, description="返回条数上限"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[ReportListItem]:
    """获取报告列表，支持按 sku_id 和 report_type 筛选。"""
    reports = await list_reports(db, sku_id=sku_id, report_type=report_type, limit=limit)
    return [ReportListItem.model_validate(r) for r in reports]


@router.get("/{report_id}", response_model=ReportRead)
async def get_report_endpoint(
    report_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ReportRead:
    """获取单个报告的完整内容。"""
    report = await get_report(db, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    return ReportRead.model_validate(report)


# ── 生成端点 ─────────────────────────────────────


@router.post("/generate")
async def generate_report(
    req: GenerateRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """手动生成并保存报告。"""
    generator = get_report_generator()

    # 构建报告数据
    if req.sku_id:
        reports = await list_reports(
            db, sku_id=req.sku_id, report_type=req.report_type, limit=1
        )
        if reports:
            report_data = dict(reports[0].content)
            report_data["sku_id"] = req.sku_id
            report_data["report_type"] = req.report_type
            report_data["title"] = req.title or reports[0].title
        else:
            report_data = {
                "sku_id": req.sku_id,
                "report_type": req.report_type,
                "title": req.title or f"Report - {req.sku_id}",
                "generated_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
                "summary": {},
            }
    else:
        report_data = {
            "report_type": req.report_type,
            "title": req.title or "Manual Report",
            "generated_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
            "summary": {},
        }

    filepath = generator.generate(report_data, output_format=req.output_format)
    return {
        "status": "ok",
        "filename": filepath.name,
        "format": req.output_format,
        "size_bytes": filepath.stat().st_size,
    }


# ── 文件管理端点 ────────────────────────────────


@router.get("/files/list")
async def list_report_files(
    _api_key: str = Depends(verify_api_key),
) -> list[dict[str, Any]]:
    """列出已生成的报告文件。"""
    generator = get_report_generator()
    return generator.list_files()


@router.get("/files/{filename:path}")
async def download_report(
    filename: str,
    _api_key: str = Depends(verify_api_key),
) -> Response:
    """下载报告文件（PDF/CSV）。"""
    generator = get_report_generator()
    try:
        filepath = generator.get_file_path(filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    media_type = "application/pdf" if filename.endswith(".pdf") else "text/csv"
    return FileResponse(
        path=str(filepath),
        media_type=media_type,
        filename=filename,
    )


# ── 调度管理端点 ────────────────────────────────


@router.post("/schedule")
async def schedule_report(
    req: ScheduleRequest,
    _api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """添加定时报告生成任务。"""
    sched = get_report_scheduler()
    if sched is None:
        sched = init_report_scheduler()

    job_id = f"report_{req.sku_id}_{req.report_type}_{len(sched.list_jobs())}"

    schedule = ReportSchedule(
        job_id=job_id,
        report_type=req.report_type,
        sku_id=req.sku_id,
        cron_expr=req.cron_expr,
        output_format=req.output_format,
        channels=req.channels,
        title=req.title or f"Report - {req.sku_id}",
    )

    sched.add_job(schedule)
    return {
        "status": "ok",
        "job_id": job_id,
        "schedule": schedule.to_dict(),
    }


@router.get("/schedule/list")
async def list_schedules(
    _api_key: str = Depends(verify_api_key),
) -> list[dict[str, Any]]:
    """列出所有定时报告配置。"""
    sched = get_report_scheduler()
    if sched is None:
        return []
    return sched.list_jobs()


@router.delete("/schedule/{job_id}")
async def delete_schedule(
    job_id: str,
    _api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """删除定时报告任务。"""
    sched = get_report_scheduler()
    if sched is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduler not initialized",
        )
    ok = sched.remove_job(job_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule not found: {job_id}",
        )
    return {"status": "ok", "job_id": job_id}
