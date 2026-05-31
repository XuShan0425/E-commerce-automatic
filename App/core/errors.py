"""统一错误码定义 — 后端和前端共享的语义错误分类."""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """业务错误码枚举。前端根据 error.code 决定展示策略。"""

    # ── Cookie / 认证 ──────────────────────────
    COOKIE_MISSING = "COOKIE_MISSING"
    COOKIE_EXPIRED = "COOKIE_EXPIRED"
    AUTH_INVALID = "AUTH_INVALID"

    # ── 系统状态 ────────────────────────────────
    GLOBAL_STOP = "GLOBAL_STOP"

    # ── 网络 / 代理 ─────────────────────────────
    NETWORK_ERROR = "NETWORK_ERROR"
    RATE_LIMIT = "RATE_LIMIT"

    # ── 页面抓取 ────────────────────────────────
    PAGE_CHANGED = "PAGE_CHANGED"
    PAGE_TIMEOUT = "PAGE_TIMEOUT"

    # ── AI / LLM ───────────────────────────────
    AI_FAILED = "AI_FAILED"
    AI_PARSE_ERROR = "AI_PARSE_ERROR"

    # ── 数据 ────────────────────────────────────
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"

    # ── 通用 ────────────────────────────────────
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN = "UNKNOWN"


# ── 错误码对应的用户引导文案 ──────────────────────
_SUGGESTIONS: dict[ErrorCode, str] = {
    ErrorCode.COOKIE_MISSING: "请先在「系统设置」中执行首次登录，获取速卖通 Cookie",
    ErrorCode.COOKIE_EXPIRED: "速卖通登录已过期，请在「系统设置」中重新登录",
    ErrorCode.AUTH_INVALID: "API Key 无效或已过期，请重新输入",
    ErrorCode.GLOBAL_STOP: "系统已暂停自动操作，请检查「警报中心」并清除全局停止",
    ErrorCode.NETWORK_ERROR: "网络连接异常，请检查代理设置或稍后重试",
    ErrorCode.RATE_LIMIT: "请求频率过高，请稍后重试（建议间隔 ≥ 30 分钟）",
    ErrorCode.PAGE_CHANGED: "速卖通页面结构已变化，自动抓取可能受影响，请联系管理员更新",
    ErrorCode.PAGE_TIMEOUT: "速卖通页面加载超时，请检查网络或代理连接",
    ErrorCode.AI_FAILED: "AI 服务不可用，请检查 LLM API Key 配置和额度",
    ErrorCode.AI_PARSE_ERROR: "AI 返回内容解析失败，请稍后重试或检查模型配置",
    ErrorCode.VALIDATION_ERROR: "输入数据格式不正确，请检查后重试",
    ErrorCode.NOT_FOUND: "请求的资源不存在",
    ErrorCode.CONFLICT: "数据冲突，可能已存在相同的记录",
    ErrorCode.INTERNAL_ERROR: "系统内部错误，请查看后端日志排查",
    ErrorCode.UNKNOWN: "未知错误，请查看后端日志或联系管理员",
}


def error_response(
    code: ErrorCode,
    message: str = "",
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建统一错误响应格式。包含 success: False 用于前端兼容。"""
    return {
        "success": False,
        "status": "error",
        "error": {
            "code": code.value,
            "message": message or _SUGGESTIONS.get(code, ""),
            "suggestion": _SUGGESTIONS.get(code, ""),
            **(details or {}),
        },
    }
