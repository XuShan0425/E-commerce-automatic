"""Pydantic schemas — Alert."""

from datetime import datetime

from pydantic import BaseModel


class AlertRead(BaseModel):
    id: int
    alert_type: str
    severity: str
    message: str
    is_resolved: bool
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}
