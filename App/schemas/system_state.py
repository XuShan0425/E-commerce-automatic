"""Pydantic schemas — SystemState."""

from datetime import datetime

from pydantic import BaseModel, Field


class SystemStateRead(BaseModel):
    key: str
    value: dict
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemStatus(BaseModel):
    """聚合的系统运行状态（只读端点返回）。"""
    global_stop: bool = False
    cookie_valid: bool = True
    last_cookie_check: datetime | None = None
    active_alerts: int = 0
