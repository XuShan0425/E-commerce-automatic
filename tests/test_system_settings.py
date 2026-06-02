"""Test system settings API endpoints.

Tests the global-stop toggle and system settings related functions
without requiring a live database (uses unit tests with mocking).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from App.api.v1.system import GlobalStopRequest, set_global_stop
from App.models.system_state import SystemState


class TestGlobalStopRequest:
    """Test the GlobalStopRequest pydantic model."""

    def test_valid_enabled(self):
        req = GlobalStopRequest(enabled=True)
        assert req.enabled is True

    def test_valid_disabled(self):
        req = GlobalStopRequest(enabled=False)
        assert req.enabled is False


class TestSetGlobalStop:
    """Test the set_global_stop endpoint logic with mocked DB."""

    @pytest.mark.asyncio
    async def test_set_global_stop_enable_new_record(self):
        """Setting global_stop should create a new record when none exists."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        body = GlobalStopRequest(enabled=True)
        result = await set_global_stop(body, _api_key="test", db=mock_db)

        assert result["status"] == "ok"
        assert result["global_stop"] is True
        # Verify a new SystemState was added
        mock_db.add.assert_called_once()
        added_record = mock_db.add.call_args[0][0]
        assert isinstance(added_record, SystemState)
        assert added_record.key == "global_stop"
        assert added_record.value["enabled"] is True
        assert added_record.value["reason"] == "manual_toggle"
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_global_stop_enable_existing(self):
        """Setting global_stop should update existing record."""
        mock_db = AsyncMock()
        existing_record = MagicMock(spec=SystemState)
        existing_record.key = "global_stop"
        existing_record.value = {"enabled": False}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_record
        mock_db.execute.return_value = mock_result

        body = GlobalStopRequest(enabled=True)
        result = await set_global_stop(body, _api_key="test", db=mock_db)

        assert result["status"] == "ok"
        assert result["global_stop"] is True
        # Verify existing record was updated
        assert existing_record.value["enabled"] is True
        assert existing_record.value["reason"] == "manual_toggle"
        mock_db.add.assert_not_called()
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_global_stop_disable(self):
        """Setting global_stop to False should update the record."""
        mock_db = AsyncMock()
        existing_record = MagicMock(spec=SystemState)
        existing_record.key = "global_stop"
        existing_record.value = {"enabled": True}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_record
        mock_db.execute.return_value = mock_result

        body = GlobalStopRequest(enabled=False)
        result = await set_global_stop(body, _api_key="test", db=mock_db)

        assert result["status"] == "ok"
        assert result["global_stop"] is False
        assert existing_record.value["enabled"] is False
        assert existing_record.value["reason"] == "manual_toggle"
        mock_db.flush.assert_awaited_once()
