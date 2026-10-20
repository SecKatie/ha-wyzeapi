"""Tests for the Wyze token manager."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from wyzeapy.exceptions import AccessTokenError, LoginError

from custom_components.wyzeapi.const import (
    ACCESS_TOKEN,
    API_KEY,
    KEY_ID,
    REFRESH_TIME,
    REFRESH_TOKEN,
)
from custom_components.wyzeapi.token_manager import (
    TokenManager,
    token_exception_handler,
)


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


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [AccessTokenError, LoginError])
async def test_token_exception_handler_starts_reauth(error, monkeypatch) -> None:
    """A login failure starts Home Assistant's reauth flow, then raises.

    Home Assistant only starts reauth by itself for ConfigEntryAuthFailed
    raised from the entry setup or a coordinator. From a platform setup or an
    entity action it is just logged, so the handler starts the flow itself.
    """
    hass = SimpleNamespace()
    entry = SimpleNamespace(async_start_reauth=Mock())
    monkeypatch.setattr(TokenManager, "hass", hass)
    monkeypatch.setattr(TokenManager, "config_entry", entry)

    @token_exception_handler
    async def platform_setup() -> None:
        raise error("Authentication failed")

    with pytest.raises(ConfigEntryAuthFailed):
        await platform_setup()

    entry.async_start_reauth.assert_called_once_with(hass)


@pytest.mark.asyncio
async def test_token_exception_handler_without_entry_still_raises(monkeypatch) -> None:
    """With no config entry registered yet, the handler still raises."""
    monkeypatch.setattr(TokenManager, "hass", None)
    monkeypatch.setattr(TokenManager, "config_entry", None)

    @token_exception_handler
    async def platform_setup() -> None:
        raise AccessTokenError("Authentication failed")

    with pytest.raises(ConfigEntryAuthFailed):
        await platform_setup()
