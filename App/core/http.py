"""HTTP 客户端封装 — 统一管理 httpx.AsyncClient 的创建与超时配置。

所有 services/ 中的 HTTP 请求应通过此模块发起，避免直接 import httpx。
"""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_TIMEOUT = 30.0


def _default_client() -> httpx.AsyncClient:
    """返回一个带默认超时配置的 AsyncClient。"""
    return httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)


async def http_post(
    url: str,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> httpx.Response:
    """发送异步 POST 请求。

    封装 httpx.AsyncClient.post，统一超时管理。
    """
    async with httpx.AsyncClient(timeout=timeout or DEFAULT_TIMEOUT) as client:
        return await client.post(url, json=json, headers=headers)


async def http_get(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> httpx.Response:
    """发送异步 GET 请求。"""
    async with httpx.AsyncClient(timeout=timeout or DEFAULT_TIMEOUT) as client:
        return await client.get(url, params=params, headers=headers)


__all__ = [
    "http_get",
    "http_post",
]
