"""认证路由 — API Key 管理 + JWT 用户登录/注册."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import (
    generate_key,
    get_current_user,
    invalidate_scope_cache,
    require_role,
    verify_api_key,
)
from App.models.auth import ApiKey, User
from App.schemas.auth import (
    ApiKeyCreate,
    ApiKeyRead,
    ApiKeyReveal,
    TokenResponse,
    UserLogin,
    UserRead,
    UserRegister,
)
from App.services.auth_service import AuthService

# ── API Key 路由（已有逻辑）────────────────────────
api_key_router = APIRouter(prefix="/api-keys", tags=["auth"])


@api_key_router.post("/", response_model=ApiKeyReveal, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyReveal:
    """生成新 API Key。返回原始 key（仅此一次）。"""
    raw, hashed = generate_key()
    record = ApiKey(key_hash=hashed, label=body.label, scope=body.scope)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    invalidate_scope_cache(hashed)
    return ApiKeyReveal(
        id=record.id,
        key_hash=record.key_hash,
        label=record.label,
        scope=record.scope,
        is_active=record.is_active,
        created_at=record.created_at,
        revoked_at=record.revoked_at,
        raw_key=raw,
    )


@api_key_router.get("/", response_model=list[ApiKeyRead])
async def list_api_keys(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyRead]:
    """列出所有 API Key（不含原始 key）。"""
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    records = result.scalars().all()
    return [ApiKeyRead.model_validate(r) for r in records]


@api_key_router.post("/{key_id}/revoke", response_model=ApiKeyRead)
async def revoke_api_key(
    key_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyRead:
    """吊销指定 API Key。"""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    record.is_active = False
    record.revoked_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(record)
    invalidate_scope_cache(record.key_hash)
    return ApiKeyRead.model_validate(record)


# ── JWT 用户认证路由（新增）────────────────────────
user_router = APIRouter(prefix="/auth", tags=["auth"])


@user_router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    body: UserRegister,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> UserRead:
    """注册新用户（仅管理员可操作）。"""
    try:
        user = await AuthService.register(
            db, username=body.username, password=body.password, role=body.role
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return UserRead.model_validate(user)


@user_router.post("/login", response_model=TokenResponse)
async def login_user(
    body: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """用户登录，返回 JWT token。"""
    user = await AuthService.authenticate(db, username=body.username, password=body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = AuthService.generate_token(user)
    return TokenResponse(
        access_token=token,
        username=user.username,
        role=user.role,
    )


@user_router.get("/me", response_model=UserRead)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """获取当前登录用户信息。"""
    return UserRead.model_validate(current_user)


@user_router.get("/users", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[UserRead]:
    """列出所有用户（仅管理员）。"""
    users = await AuthService.list_users(db)
    return [UserRead.model_validate(u) for u in users]
