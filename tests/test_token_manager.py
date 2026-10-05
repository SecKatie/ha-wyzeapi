"""Tests for the Wyze token manager."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.wyzeapi.const import (
    ACCESS_TOKEN,
    API_KEY,
    KEY_ID,
    REFRESH_TIME,
    REFRESH_TOKEN,
)
from custom_components.wyzeapi.token_manager import TokenManager


@pytest.mark.asyncio
async def test_token_callback_preserves_api_credentials() -> None:
    entry = SimpleNamespace(
        data={
            "username": "user@example.com",
            "password": "hunter2",
            KEY_ID: "key-id",
            API_KEY: "api-key",
            ACCESS_TOKEN: "old-access",
            REFRESH_TOKEN: "old-refresh",
            REFRESH_TIME: "1.0",
        }
    )
    config_entries = SimpleNamespace(
        async_entries=Mock(return_value=[entry]),
        async_update_entry=Mock(),
    )
    TokenManager(SimpleNamespace(config_entries=config_entries), entry)

    await TokenManager.token_callback(
        SimpleNamespace(
            access_token="new-access",
            refresh_token="new-refresh",
            refresh_time=2.0,
        )
    )

    config_entries.async_update_entry.assert_called_once_with(
        entry,
        data={
            "username": "user@example.com",
            "password": "hunter2",
            KEY_ID: "key-id",
            API_KEY: "api-key",
            ACCESS_TOKEN: "new-access",
            REFRESH_TOKEN: "new-refresh",
            REFRESH_TIME: "2.0",
        },
    )
