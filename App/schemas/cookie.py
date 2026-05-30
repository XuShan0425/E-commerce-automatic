"""Pydantic schemas — Cookie."""

from datetime import datetime

from pydantic import BaseModel, Field


class CookieStoreCreate(BaseModel):
    domain: str = Field(..., max_length=255)
    cookies_json: list[dict] = []
    is_valid: bool = True


class CookieStoreRead(BaseModel):
    id: int
    domain: str
    is_valid: bool
    last_check_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
