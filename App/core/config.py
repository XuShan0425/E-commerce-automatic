"""应用配置 — 从 .env / 环境变量加载."""

from functools import lru_cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_PORT: int = 8000
    SECRET_KEY: str = "change-me"
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "ad_manager"
    DB_PASSWORD: str = "change-me-in-production"
    DB_NAME: str = "ad_manager"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    ADMIN_API_KEY: str = "admin-bootstrap-key-change-me"

    # Claude API
    ANTHROPIC_API_KEY: str = ""

    # Email Notification (SMTP)
    # 用哪个邮箱发信就填哪组。收件人可以填多个，逗号分隔。
    # ── Gmail (发件) ──
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""      # Gmail 需用 App Password，不是登录密码
    SMTP_FROM: str = ""
    SMTP_USE_TLS: bool = True
    # ── 收件人（多个用逗号分隔）──
    ALERT_EMAIL_TO: str = ""     # e.g. "you@gmail.com, you@outlook.com"

    @property
    def alert_recipients(self) -> list[str]:
        """解析收件人列表。"""
        if not self.ALERT_EMAIL_TO:
            return []
        return [addr.strip() for addr in self.ALERT_EMAIL_TO.split(",") if addr.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
