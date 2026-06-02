"""Redis 缓存服务 — 封装 get/set/delete/expire 等操作，TTL 可配置。

提供两层 API：
  1. 模块级便捷函数：get_cache / set_cache / delete_cache / clear_pattern
  2. CacheService 类（含装饰器）：支持 expire / ping / close 等完整操作

Redis 不可用时自动静默降级，不影响业务逻辑。

用法:
    # 模块级函数（简单场景）
    from App.services.cache_service import get_cache, set_cache
    await set_cache("my_key", {"data": 123}, ttl=300)
    value = await get_cache("my_key")

    # CacheService 类（完整功能）
    from App.services.cache_service import CacheService
    cache = CacheService()
    await cache.set("my_key", {"data": 123})
    value = await cache.get("my_key")
    await cache.expire("my_key", 60)

    # 装饰器（自动缓存函数返回值）
    from App.services.cache_service import cached
    @cached(ttl=60, prefix="products:")
    async def list_products(db, tracked=None):
        ...
"""

from __future__ import annotations

import functools
import hashlib
import json
import pickle
from collections.abc import Callable
from typing import Any, TypeVar

from App.core.config import settings
from App.core.logging import get_logger

logger = get_logger(__name__)

# 默认 TTL（秒）
DEFAULT_TTL: int = 300  # 5 分钟

# 缓存键前缀
CACHE_PREFIX: str = "ad_manager:"

F = TypeVar("F", bound=Callable[..., Any])

# ── 模块级全局 Redis 客户端（延迟初始化，支持静默降级）──

_redis = None
_available = False


def _get_client():
    """延迟创建全局 Redis 连接（模块级函数使用）。"""
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


# ── 模块级便捷函数 ───────────────────────────────


async def get_cache(key: str) -> Any | None:
    """获取缓存值，返回 Python 对象或 None。

    Args:
        key: 缓存键（不含前缀）。

    Returns:
        缓存的值，不存在或 Redis 不可用时返回 None。
    """
    client = _get_client()
    if client is None:
        return None
    try:
        raw = await client.get(f"{CACHE_PREFIX}{key}")
        if raw is not None:
            return json.loads(raw)
    except Exception as exc:
        logger.debug("cache_get_failed", extra={"key": key, "error": str(exc)})
    return None


async def set_cache(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    """设置缓存，默认 TTL 5 分钟。

    Args:
        key: 缓存键（不含前缀）。
        value: 任意可 JSON 序列化的 Python 对象。
        ttl: 过期时间（秒），默认 300。
    """
    client = _get_client()
    if client is None:
        return
    try:
        raw = json.dumps(value, default=str)
        await client.setex(f"{CACHE_PREFIX}{key}", ttl, raw)
    except Exception as exc:
        logger.debug("cache_set_failed", extra={"key": key, "error": str(exc)})


async def delete_cache(key: str) -> None:
    """删除缓存。

    Args:
        key: 缓存键（不含前缀）。
    """
    client = _get_client()
    if client is None:
        return
    try:
        await client.delete(f"{CACHE_PREFIX}{key}")
    except Exception as exc:
        logger.debug("cache_delete_failed", extra={"key": key, "error": str(exc)})


async def clear_pattern(pattern: str) -> None:
    """按模式清除缓存（如 clear_pattern("products:*")）。

    Args:
        pattern: Redis glob 模式（不含前缀）。
    """
    client = _get_client()
    if client is None:
        return
    try:
        keys = await client.keys(f"{CACHE_PREFIX}{pattern}")
        if keys:
            await client.delete(*keys)
    except Exception as exc:
        logger.debug("cache_clear_pattern_failed", extra={"pattern": pattern, "error": str(exc)})


# ── CacheService 类 ─────────────────────────────


class CacheService:
    """封装 Redis 缓存操作，支持 get/set/delete/expire 等。

    Redis 连接为懒加载（首次操作时建立），调用方无需关心连接生命周期。
    支持静默降级：Redis 不可用时所有操作返回 None/False，不抛异常。

    Attributes:
        redis_url: Redis 连接字符串，默认从 settings.REDIS_URL 读取。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or settings.REDIS_URL
        self._client: Any = None
        self._available = False

    async def _get_client(self):
        """懒加载 Redis 连接。"""
        if self._available:
            return self._client
        if self._client is None:
            try:
                import redis.asyncio as aioredis

                self._client = aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                self._available = True
            except Exception as exc:
                logger.warning("CacheService: Redis 不可用，将静默降级: %s", exc)
                self._client = None
        return self._client

    def _make_key(self, key: str) -> str:
        """添加前缀，避免键冲突。"""
        return f"{CACHE_PREFIX}{key}"

    async def get(self, key: str) -> Any | None:
        """获取缓存值。自动解析 JSON -> Python 对象。

        Args:
            key: 缓存键（无需带前缀）。

        Returns:
            缓存的值，不存在或 Redis 不可用时返回 None。
        """
        client = await self._get_client()
        if client is None:
            return None
        full_key = self._make_key(key)
        try:
            raw = await client.get(full_key)
            if raw is not None:
                return json.loads(raw)
        except Exception as exc:
            logger.debug("cache_get_failed", extra={"key": full_key, "error": str(exc)})
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """设置缓存值。自动序列化 Python 对象 -> JSON。

        Args:
            key: 缓存键（无需带前缀）。
            value: 任意可 JSON 序列化的值。
            ttl: 过期时间（秒），默认 300。

        Returns:
            是否成功（Redis 不可用时返回 False）。
        """
        client = await self._get_client()
        if client is None:
            return False
        full_key = self._make_key(key)
        try:
            raw = json.dumps(value, ensure_ascii=False, default=str)
            return bool(await client.setex(full_key, ttl, raw))
        except Exception as exc:
            logger.debug("cache_set_failed", extra={"key": full_key, "error": str(exc)})
            return False

    async def delete(self, key: str) -> bool:
        """删除指定缓存键。

        Args:
            key: 缓存键（无需带前缀）。

        Returns:
            是否成功（键不存在或 Redis 不可用时返回 False）。
        """
        client = await self._get_client()
        if client is None:
            return False
        full_key = self._make_key(key)
        try:
            deleted = await client.delete(full_key)
            return bool(deleted)
        except Exception as exc:
            logger.debug("cache_delete_failed", extra={"key": full_key, "error": str(exc)})
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间。

        Args:
            key: 缓存键（无需带前缀）。
            ttl: 过期时长（秒）。

        Returns:
            是否成功。
        """
        client = await self._get_client()
        if client is None:
            return False
        full_key = self._make_key(key)
        try:
            return bool(await client.expire(full_key, ttl))
        except Exception as exc:
            logger.debug("cache_expire_failed", extra={"key": full_key, "error": str(exc)})
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """按模式清除缓存（如 clear_pattern("products:*")）。

        Args:
            pattern: Redis glob 模式（无需带前缀）。

        Returns:
            删除的键数量。
        """
        client = await self._get_client()
        if client is None:
            return 0
        full_pattern = self._make_key(pattern)
        try:
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await client.scan(
                    cursor=cursor, match=full_pattern, count=100
                )
                if keys:
                    deleted += await client.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as exc:
            logger.debug(
                "cache_clear_pattern_failed",
                extra={"pattern": full_pattern, "error": str(exc)},
            )
            return 0

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
            self._available = False

    async def ping(self) -> bool:
        """健康检查：测试 Redis 连接是否可用。

        Returns:
            True 表示连接正常；Redis 不可用时返回 False。
        """
        try:
            client = await self._get_client()
            if client is None:
                return False
            return bool(await client.ping())
        except Exception:
            return False


# ── 缓存装饰器 ─────────────────────────────────


def _make_cache_key(prefix: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """根据参数生成确定性缓存键。

    使用 pickle + md5 生成摘要，避免超长键名。
    """
    raw = pickle.dumps((args, sorted(kwargs.items())))
    digest = hashlib.md5(raw).hexdigest()
    return f"{prefix}{digest}"


def cached(
    ttl: int = DEFAULT_TTL,
    prefix: str = "",
    key_builder: Callable[..., str] | None = None,
) -> Callable[[F], F]:
    """异步函数缓存装饰器。

    用法:
        @cached(ttl=60, prefix="products:")
        async def list_products(db, tracked: bool | None = None):
            ...

    参数:
        ttl: 缓存过期时间（秒）。
        prefix: 缓存键前缀，用于按模块清理。
        key_builder: 自定义键生成函数，接收 args/kwargs 返回键名。
                     默认使用参数哈希。
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = CacheService()
            if key_builder is not None:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = _make_cache_key(prefix, args, kwargs)
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(
                    "cache_hit",
                    extra={"func": func.__name__, "cache_key": cache_key},
                )
                return cached_value
            logger.debug(
                "cache_miss",
                extra={"func": func.__name__, "cache_key": cache_key},
            )
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl=ttl)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator
