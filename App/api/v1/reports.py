"""报告查询端点 — 查看和管理系统报告."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.schemas.report import ReportListItem, ReportRead
from App.services.report_service import get_report, list_reports

router = APIRouter(prefix="/reports", tags=["reports"])


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
