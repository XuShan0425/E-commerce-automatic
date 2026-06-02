"""Pydantic schemas — Report."""

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
