"""Pydantic schemas — API Key."""

from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    label: str | None = Field(None, max_length=200, description="标识用途")


class ApiKeyRead(BaseModel):
    id: int
    key_hash: str
    label: str | None
    is_active: bool
    created_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyReveal(ApiKeyRead):
    """仅在创建时返回原始 key，之后不可再获取。"""

    raw_key: str
