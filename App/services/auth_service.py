"""用户认证与角色管理服务."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from App.models.auth import User, UserRole


class AuthService:
    """用户注册、登录、查询服务."""

    @staticmethod
    async def register(
        db: AsyncSession,
        username: str,
        password: str,
        role: str = UserRole.OPERATOR.value,
    ) -> User:
        """注册新用户。抛出 ValueError 如果用户名已存在。"""
        # 检查用户名是否已存在
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none() is not None:
            raise ValueError(f"Username '{username}' already exists")

        user = User(
            username=username,
            password_hash=hash_password(password),
            role=role,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate(
        db: AsyncSession,
        username: str,
        password: str,
    ) -> User | None:
        """验证用户名密码。成功返回 User，失败返回 None。"""
        result = await db.execute(
            select(User).where(User.username == username, User.is_active)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
        """根据 ID 获取用户。"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_users(db: AsyncSession) -> list[User]:
        """列出所有用户。"""
        result = await db.execute(select(User).order_by(User.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    def generate_token(user: User) -> str:
        """为用户生成 JWT access token。"""
        return create_access_token({
            "sub": user.id,
            "username": user.username,
            "role": user.role,
        })
