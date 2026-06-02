"""TASK-002-1: Tests for ai_client.py parsing logic.

Tests parse_html_to_json() with _call_claude mocked to avoid real API calls.
"""

from __future__ import annotations

from unittest import mock

import pytest

from App.services.ai_client import parse_html_to_json


@pytest.mark.asyncio
async def test_valid_json_response():
    """Verify parse_html_to_json works with a valid JSON response from Claude."""
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "number"},
        },
    }

    with mock.patch(
        "App.services.ai_client._call_claude",
        new=mock.AsyncMock(return_value='{"name": "test", "value": 42}'),
    ):
        result = await parse_html_to_json("<html>test</html>", schema, "test extraction")

    assert result == {"name": "test", "value": 42}


@pytest.mark.asyncio
async def test_markdown_wrapped_response():
    """Verify markdown-wrapped JSON is cleaned before parsing."""
    schema = {"type": "object", "properties": {"key": {"type": "string"}}}

    with mock.patch(
        "App.services.ai_client._call_claude",
        new=mock.AsyncMock(return_value="```json\n{\"key\": \"wrapped_value\"}\n```"),
    ):
        result = await parse_html_to_json("<html>data</html>", schema)

    assert result == {"key": "wrapped_value"}


@pytest.mark.asyncio
async def test_markdown_no_lang_tag():
    """Verify triple-backtick without language tag works."""
    schema = {"type": "array", "items": {"type": "string"}}

    with mock.patch(
        "App.services.ai_client._call_claude",
        new=mock.AsyncMock(return_value="```\n[\"a\", \"b\"]\n```"),
    ):
        result = await parse_html_to_json("<html>list</html>", schema)

    assert result == ["a", "b"]


@pytest.mark.asyncio
async def test_json_decode_error_raises_value_error():
    """Verify a non-JSON response raises ValueError."""
    schema = {"type": "object"}

    with mock.patch(
        "App.services.ai_client._call_claude",
        new=mock.AsyncMock(return_value="not json at all"),
    ):
        with pytest.raises(ValueError, match="AI 返回的内容无法解析为 JSON"):
            await parse_html_to_json("<html>bad</html>", schema)


@pytest.mark.asyncio
async def test_decode_error_for_markdown_wrapped_non_json():
    """Verify markdown-wrapped non-JSON also raises ValueError."""
    schema = {"type": "object"}

    with mock.patch(
        "App.services.ai_client._call_claude",
        new=mock.AsyncMock(return_value="```\nnot json\n```"),
    ):
        with pytest.raises(ValueError, match="AI 返回的内容无法解析为 JSON"):
            await parse_html_to_json("<html>bad</html>", schema)


@pytest.mark.asyncio
async def test_list_result_returned_directly():
    """Verify list results are returned directly (not wrapped in a dict)."""
    schema = {"type": "array", "items": {"type": "object"}}

    with mock.patch(
        "App.services.ai_client._call_claude",
        new=mock.AsyncMock(
            return_value='[{"item": 1}, {"item": 2}]'
        ),
    ):
        result = await parse_html_to_json("<html>list</html>", schema)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["item"] == 1
