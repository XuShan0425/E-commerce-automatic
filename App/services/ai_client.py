"""Claude API 客户端 — 使用 httpx 调用 Anthropic Messages API 进行 HTML 结构化解析."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from App.core.config import settings

logger = logging.getLogger(__name__)

# URL 和模型从 settings 读取，硬编码仅作为 fallback
ANTHROPIC_API_VERSION = "2023-06-01"

RATE_PARSING_SYSTEM_PROMPT = """\
你是一个数据提取专家。我会给你一段来自速卖通(AliExpress)卖家帮助中心的 HTML 页面内容。
请从中提取所有物流费率或平台佣金费率数据，以 JSON 格式返回。

要求：
1. 仔细阅读 HTML 中的表格、列表和文本内容
2. 提取所有费率条目，不要遗漏任何数据
3. 数值必须是数字类型，不要带单位或货币符号
4. 如果某个字段在页面中找不到，用 null 代替
5. 返回纯 JSON，不要包含 markdown 代码块标记
"""


async def _call_claude(
    prompt: str,
    system_prompt: str = RATE_PARSING_SYSTEM_PROMPT,
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> str:
    """调用 Claude API，返回文本响应。

    Args:
        prompt: 用户消息内容（包含待解析的 HTML）
        system_prompt: 系统提示词
        max_tokens: 最大输出 token 数
        temperature: 生成温度（低温度 = 更确定的输出）

    Returns:
        Claude 的文本响应

    Raises:
        ValueError: API Key 未配置
        httpx.HTTPError: API 调用失败
    """
    if not settings.LLM_API_KEY:
        raise ValueError("LLM_API_KEY 未配置，请在 .env 中设置")

    headers = {
        "x-api-key": settings.LLM_API_KEY,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "content-type": "application/json",
    }

    body: dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.LLM_API_BASE_URL}/v1/messages",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        data = response.json()

    # 提取文本响应
    content_blocks = data.get("content", [])
    text_parts: list[str] = []
    for block in content_blocks:
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))

    return "\n".join(text_parts)


async def parse_html_to_json(
    html: str,
    output_schema: dict[str, Any],
    extraction_goal: str = "提取所有费率数据",
) -> dict[str, Any]:
    """将 HTML 页面解析为结构化 JSON。

    Args:
        html: 待解析的 HTML 内容（可以是完整页面或片段）
        output_schema: 期望的 JSON Schema 描述，用于引导 Claude 输出格式。
                       例如: {"type": "array", "items": {"type": "object", "properties": {...}}}
        extraction_goal: 中文描述提取目标，用于构建 prompt

    Returns:
        解析后的结构化数据（dict）

    Raises:
        ValueError: AI 返回的内容无法解析为 JSON
    """
    schema_str = json.dumps(output_schema, ensure_ascii=False, indent=2)

    prompt = f"""\
提取目标：{extraction_goal}

请严格按照以下 JSON Schema 返回数据：
{schema_str}

以下是页面 HTML 内容：
---
{html[:80000]}
---
"""

    raw_response = await _call_claude(prompt)
    logger.debug("Claude raw response (first 500 chars): %s", raw_response[:500])

    # Claude 可能返回带 ```json ... ``` 包裹的 JSON，去掉包裹标记
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        # 找到第一个换行后的内容
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Claude response as JSON: %s", exc)
        logger.debug("Raw response (full): %s", raw_response)
        raise ValueError(
            f"AI 返回的内容无法解析为 JSON。原始响应: {raw_response[:500]}"
        ) from exc


async def parse_logistics_html(html: str) -> list[dict[str, Any]]:
    """解析物流费率 HTML 为结构化数据。

    返回格式：
    [
        {
            "destination_region": "US",
            "weight_range_min": 0.0,
            "weight_range_max": 100.0,
            "cost": 2.50
        },
        ...
    ]
    """
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["destination_region", "weight_range_min", "weight_range_max", "cost"],
            "properties": {
                "destination_region": {
                    "type": "string",
                    "description": "目的地区代码，如 US, EU, AU, RU, BR 等",
                },
                "weight_range_min": {
                    "type": "number",
                    "description": "重量范围下限（克），如果无下限则为 0",
                },
                "weight_range_max": {
                    "type": "number",
                    "description": "重量范围上限（克），如果无上限则用一个很大的数如 99999",
                },
                "cost": {
                    "type": "number",
                    "description": "物流费用（美元 USD）",
                },
            },
        },
    }

    result = await parse_html_to_json(
        html,
        schema,
        extraction_goal="提取速卖通物流费率表中的所有条目，包括目的地区、重量范围、费用",
    )

    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        # 有些情况下 Claude 可能返回 {"rates": [...]} 这样的包装
        for value in result.values():
            if isinstance(value, list):
                return value
        return [result]
    return []


async def parse_fees_html(html: str) -> list[dict[str, Any]]:
    """解析平台佣金费率 HTML 为结构化数据。

    返回格式：
    [
        {
            "category": "Electronics",
            "fee_rate": 0.05
        },
        ...
    ]
    """
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["category", "fee_rate"],
            "properties": {
                "category": {
                    "type": "string",
                    "description": "商品类目名称，如 Electronics, Clothing, Home & Garden 等",
                },
                "fee_rate": {
                    "type": "number",
                    "description": "平台佣金费率，以小数表示。如 5% 则值为 0.05",
                },
            },
        },
    }

    result = await parse_html_to_json(
        html,
        schema,
        extraction_goal="提取速卖通平台佣金费率表中的所有条目，包括商品类目和对应的佣金费率",
    )

    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for value in result.values():
            if isinstance(value, list):
                return value
        return [result]
    return []
