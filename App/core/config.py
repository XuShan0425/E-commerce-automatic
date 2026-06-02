"""应用配置 — 从 .env / 环境变量加载."""

from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env 在项目根目录（config.py 向上 3 级）
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=str(_ENV_FILE),
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

    # LLM API (支持 Anthropic 原生 Messages 格式的兼容服务)
    LLM_API_KEY: str = ""
    LLM_API_BASE_URL: str = "https://api.jmrai.com"
    LLM_MODEL: str = "claude-opus-4-7"
    LLM_API_TIMEOUT_CONNECT: int = 30      # 连接超时（秒）
    LLM_API_TIMEOUT_READ: int = 180        # 读取超时（秒）
    LLM_API_TIMEOUT_TOTAL: int = 300       # 总硬截止时间（秒）

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
    # ── SOCKS5 代理（国内访问 Gmail SMTP 需要）──
    SMTP_PROXY_HOST: str = "127.0.0.1"
    SMTP_PROXY_PORT: int = 7890

    @property
    def alert_recipients(self) -> list[str]:
        """解析收件人列表。"""
        if not self.ALERT_EMAIL_TO:
            return []
        return [addr.strip() for addr in self.ALERT_EMAIL_TO.split(",") if addr.strip()]

    # ── Multi-Channel Notification ──────────────────
    # 企业微信机器人 Webhook URL（用于发送 Markdown 消息）
    WECHAT_WEBHOOK_URL: str = ""
    # Telegram Bot Token（从 @BotFather 获取）
    TELEGRAM_BOT_TOKEN: str = ""
    # Telegram 目标聊天 ID（用户或群组）
    TELEGRAM_CHAT_ID: str = ""
    # Slack Incoming Webhook URL
    SLACK_WEBHOOK_URL: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
