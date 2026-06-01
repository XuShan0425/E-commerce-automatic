"""Redis 缓存服务 — 可选依赖，Redis 不可用时静默降级."""

from __future__ import annotations

import json
from typing import Any

from App.core.config import settings
from App.core.logging import get_logger

logger = get_logger(__name__)

_redis = None
_available = False


def _get_client():
    """延迟创建 Redis 连接。"""
    global _redis, _available
    if _available:
        return _redis
    if _redis is None:
        try:
            import redis.asyncio as aioredis
            _redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            _available = True
        except Exception as exc:
            logger.warning("Redis 不可用，缓存将静默降级: %s", exc)
            _redis = None
    return _redis


async def get_cache(key: str) -> Any | None:
    """获取缓存值，返回 Python 对象或 None。"""
    client = _get_client()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as exc:
        logger.debug("缓存读取失败 (key=%s): %s", key, exc)
    return None


async def set_cache(key: str, value: Any, ttl: int = 300) -> None:
    """设置缓存，默认 TTL 5 分钟。"""
    client = _get_client()
    if client is None:
        return
    try:
        raw = json.dumps(value, default=str)
        await client.setex(key, ttl, raw)
    except Exception as exc:
        logger.debug("缓存写入失败 (key=%s): %s", key, exc)


async def delete_cache(key: str) -> None:
    """删除缓存。"""
    client = _get_client()
    if client is None:
        return
    try:
        await client.delete(key)
    except Exception as exc:
        logger.debug("缓存删除失败 (key=%s): %s", key, exc)


async def clear_pattern(pattern: str) -> None:
    """按模式清除缓存 (e.g. "rates:*")。"""
    client = _get_client()
    if client is None:
        return
    try:
        keys = await client.keys(pattern)
        if keys:
            await client.delete(*keys)
    except Exception as exc:
        logger.debug("缓存清理失败 (pattern=%s): %s", pattern, exc)
