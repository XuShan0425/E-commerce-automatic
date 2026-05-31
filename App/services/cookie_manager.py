"""Cookie 管理服务 — 存储、读取、序列化/反序列化."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.models.cookie import CookieStore


class CookieManager:
    """管理 Cookie 的数据库持久化。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save_cookies(self, domain: str, cookies: list[dict]) -> CookieStore:
        """保存 Cookie 列表到指定域名。已存在则更新。"""
        result = await self._db.execute(
            select(CookieStore).where(CookieStore.domain == domain)
        )
        record = result.scalar_one_or_none()

        if record is not None:
            record.cookies_json = cookies  # type: ignore[assignment]
            record.is_valid = True
            record.updated_at = datetime.now(timezone.utc)
        else:
            record = CookieStore(
                domain=domain,
                cookies_json=cookies,  # type: ignore[arg-type]
                is_valid=True,
            )
            self._db.add(record)

        await self._db.flush()
        await self._db.refresh(record)
        return record

    async def load_cookies(self, domain: str) -> list[dict]:
        """读取指定域名的已保存 Cookie。返回空列表如果不存在或已失效。

        增加容错处理：cookies_json 可能为损坏数据，返回空列表而非崩溃。
        """
        result = await self._db.execute(
            select(CookieStore).where(
                CookieStore.domain == domain,
                CookieStore.is_valid == True,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return []
        try:
            cookies = record.cookies_json
            if isinstance(cookies, list):
                return cookies
        except Exception:
            pass
        return []

    async def mark_invalid(self, domain: str) -> None:
        """标记 Cookie 为失效。"""
        result = await self._db.execute(
            select(CookieStore).where(CookieStore.domain == domain)
        )
        record = result.scalar_one_or_none()
        if record is not None:
            record.is_valid = False
            record.last_check_at = datetime.now(timezone.utc)
            record.updated_at = datetime.now(timezone.utc)
            await self._db.flush()

    async def mark_valid(self, domain: str) -> None:
        """标记 Cookie 为有效，更新检查时间。"""
        result = await self._db.execute(
            select(CookieStore).where(CookieStore.domain == domain)
        )
        record = result.scalar_one_or_none()
        if record is not None:
            record.is_valid = True
            record.last_check_at = datetime.now(timezone.utc)
            record.updated_at = datetime.now(timezone.utc)
            await self._db.flush()

    @staticmethod
    def serialize_cookies(cookies: list) -> list[dict]:
        """将 Playwright Cookie 对象列表转为可 JSON 序列化的字典列表。"""
        result: list[dict] = []
        for c in cookies:
            if isinstance(c, dict):
                result.append(c)
            else:
                result.append({
                    "name": c.get("name", getattr(c, "name", "")),
                    "value": c.get("value", getattr(c, "value", "")),
                    "domain": c.get("domain", getattr(c, "domain", "")),
                    "path": c.get("path", getattr(c, "path", "/")),
                    "expires": c.get("expires", getattr(c, "expires", -1)),
                    "httpOnly": c.get("httpOnly", getattr(c, "httpOnly", False)),
                    "secure": c.get("secure", getattr(c, "secure", False)),
                    "sameSite": c.get("sameSite", getattr(c, "sameSite", "Lax")),
                })
        return result
