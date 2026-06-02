"""Pydantic schemas — API Key + 用户与角色."""

from datetime import datetime

from pydantic import BaseModel, Field

# ── API Key ───────────────────────────────────────

class ApiKeyCreate(BaseModel):
    label: str | None = Field(None, max_length=200, description="标识用途")
    scope: str = Field(
        "admin",
        max_length=500,
        description="Comma-separated permission scopes, e.g. "
        "'products:read,ads:read,profit:read'. 'admin' grants full access.",
    )


class ApiKeyRead(BaseModel):
    id: int
    key_hash: str
    label: str | None
    scope: str
    is_active: bool
    created_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyReveal(ApiKeyRead):
    """仅在创建时返回原始 key，之后不可再获取。"""

    raw_key: str


# ── 用户与角色 ────────────────────────────────────

class UserRegister(BaseModel):
    """用户注册请求体。"""

    username: str = Field(..., min_length=2, max_length=100, description="登录用户名")
    password: str = Field(..., min_length=6, max_length=128, description="登录密码")
    role: str = Field("operator", pattern=r"^(admin|operator)$", description="用户角色")


class UserLogin(BaseModel):
    """用户登录请求体。"""

    username: str = Field(..., description="登录用户名")
    password: str = Field(..., description="登录密码")


class TokenResponse(BaseModel):
    """登录成功返回的 JWT token。"""

    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserRead(BaseModel):
    """用户信息（不暴露密码哈希）。"""

    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
