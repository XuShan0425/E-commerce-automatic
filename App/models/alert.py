"""警报模型 — 记录系统异常事件."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from App.core.database import Base


class Alert(AsyncAttrs, Base):
    """系统警报 — Cookie 失效、采集异常等。"""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        doc="cookie_expired / collection_error / rate_limit / etc."
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="warning",
        doc="critical / warning / info"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
