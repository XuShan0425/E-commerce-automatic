"""报告 ORM 模型 — 存储自动生成的 ROI 分析和活动关闭说明."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from App.core.database import Base


class Report(AsyncAttrs, Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("idx_reports_sku_type", "sku_id", "report_type"),
        Index("idx_reports_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False)
    report_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="roi_negative"
    )
    # roi_negative | campaign_close
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
