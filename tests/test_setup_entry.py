"""Tests for login error handling in async_setup_entry."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from wyzeapy.exceptions import UnknownApiError

from custom_components import wyzeapi
from custom_components.wyzeapi.const import (
    ACCESS_TOKEN,
    API_KEY,
    KEY_ID,
    REFRESH_TIME,
    REFRESH_TOKEN,
)


def make_entry():
    return SimpleNamespace(
        entry_id="entry-id",
        data={
            "username": "user@example.com",
            "password": "hunter2",
            KEY_ID: "key-id",
            API_KEY: "api-key",
            ACCESS_TOKEN: "access",
            REFRESH_TOKEN: "refresh",
            REFRESH_TIME: "1.0",
        },
        options={},
    )


async def setup_with_login_error(error):
    client = SimpleNamespace(
        login=AsyncMock(side_effect=error),
        register_for_token_callback=Mock(),
    )
    hass = SimpleNamespace(data={})
    with (
        patch.object(wyzeapi.Wyzeapy, "create", AsyncMock(return_value=client)),
        patch.object(wyzeapi, "TokenManager"),
    ):
        return await wyzeapi.async_setup_entry(hass, make_entry())


@pytest.mark.asyncio
async def test_rejected_refresh_token_triggers_reauth() -> None:
    with pytest.raises(ConfigEntryAuthFailed):
        await setup_with_login_error(UnknownApiError("2002", "refresh token is error"))


@pytest.mark.asyncio
async def test_other_unknown_api_errors_are_not_treated_as_auth_failures() -> None:
    with pytest.raises(UnknownApiError):
        await setup_with_login_error(UnknownApiError("5000", "server error"))
