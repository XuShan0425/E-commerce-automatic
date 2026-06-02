"""鉴权工具 — API Key 验证 + JWT 登录 + 角色权限检查."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.config import settings
from App.core.database import get_db

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
JWT_BEARER = HTTPBearer(auto_error=False)

# ── 密码哈希 ──────────────────────────────────────
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希."""
    return _pwd_ctx.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配."""
    return _pwd_ctx.verify(plain_password, hashed_password)


# ── JWT Token ─────────────────────────────────────
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时


def create_access_token(data: dict) -> str:
    """创建 JWT access token。data 中应包含 sub (用户 ID, 转为字符串) 等字段。"""
    to_encode = data.copy()
    # jose 要求 sub 为字符串
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.now(UTC) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """解码 JWT token，返回 payload。过期 / 无效时抛出 HTTPException。"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── API Key 工具（已有）────────────────────────────


def hash_key(raw_key: str) -> str:
    """SHA-256 哈希 API Key，数据库只存哈希。"""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key() -> tuple[str, str]:
    """生成新 API Key。返回 (raw_key, key_hash) 元组。"""
    raw = "ak-" + secrets.token_urlsafe(32)
    return raw, hash_key(raw)


# ── API Key 鉴权依赖（已有）────────────────────────


async def verify_api_key(
    api_key: str | None = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> str:
    """FastAPI 依赖：验证请求中的 X-API-Key 头。返回有效的 raw key。"""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    key_hash = hash_key(api_key)

    # 动态导入避免循环依赖
    from App.models.auth import ApiKey

    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active)
    )
    record = result.scalar_one_or_none()

    if record is None:
        # fallback: 允许 ADMIN_API_KEY 作为 bootstrap key（用于创建第一条正式 API Key）
        if api_key == settings.ADMIN_API_KEY:
            return api_key
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    return api_key


# ── JWT 用户鉴权依赖（新增）────────────────────────


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(JWT_BEARER),
    db: AsyncSession = Depends(get_db),
):
    """FastAPI 依赖：从 Authorization: Bearer <token> 解析当前用户。

    返回 User ORM 对象。
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    payload = decode_access_token(credentials.credentials)
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    from App.models.auth import User

    result = await db.execute(select(User).where(User.id == user_id, User.is_active))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def require_role(*roles: str):
    """FastAPI 依赖工厂：要求当前用户拥有指定角色之一。

    用法：
        @router.get("/admin-only")
        async def admin_endpoint(_user=Depends(require_role("admin"))):
            ...
    """

    async def _role_checker(
        current_user=Depends(get_current_user),
    ):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return current_user

    return _role_checker
