"""报告服务 Pydantic schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReportRead(BaseModel):
    id: int
    sku_id: str
    report_type: str
    title: str
    content: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListItem(BaseModel):
    id: int
    sku_id: str
    report_type: str
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateReportRequest(BaseModel):
    report_type: str = "scheduled"
    sku_id: str = ""
    title: str = ""
    output_format: str = "pdf"


class ScheduleReportRequest(BaseModel):
    report_type: str = "scheduled"
    sku_id: str
    cron_expr: str
    output_format: str = "pdf"
    channels: list[str] = []
    title: str = ""


class ReportFileInfo(BaseModel):
    name: str
    format: str
    size_bytes: int
    modified_at: str


class ReportScheduleInfo(BaseModel):
    job_id: str
    report_type: str
    sku_id: str
    cron_expr: str
    output_format: str
    channels: list[str]
    title: str
    enabled: bool
    created_at: str
