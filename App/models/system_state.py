"""全局系统状态模型 — 存储运行时标志（如 global_stop）。"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from App.core.database import Base


class SystemState(AsyncAttrs, Base):
    """键值存储，用于保存全局运行时状态。"""

    __tablename__ = "system_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


async def is_global_stop_active(db: AsyncSession) -> bool:
    """Check if global_stop flag is enabled in system_state."""
    result = await db.execute(
        select(SystemState).where(SystemState.key == "global_stop")
    )
    record = result.scalar_one_or_none()
    return bool(record and record.value.get("enabled"))
