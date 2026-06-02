"""操作日志 ORM 模型 — 记录每次广告出价/价格/活动调整操作."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from App.core.database import Base


class OperationLog(AsyncAttrs, Base):
    __tablename__ = "operation_logs"
    __table_args__ = (
        Index("idx_op_logs_sku", "sku_id", "executed_at"),
        Index("idx_op_logs_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False)
    operation_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="adjust_bid"
    )
    # adjust_bid | adjust_price | switch_ad_type | stop_ad | pause_campaign | resume_campaign | stop_campaign | no_action
    field_name: Mapped[str | None] = mapped_column(String(50))
    # daily_budget | price | ad_type
    old_value: Mapped[float | None] = mapped_column(Numeric(10, 2))
    new_value: Mapped[float | None] = mapped_column(Numeric(10, 2))
    ai_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    ai_reasoning: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="success"
    )
    # success | failed | pending_confirmation | rejected
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    details: Mapped[dict | None] = mapped_column(JSONB, default=dict)
