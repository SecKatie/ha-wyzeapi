"""Tests for TokenManager's config-entry persistence on token refresh."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.wyzeapi.const import ACCESS_TOKEN, REFRESH_TIME, REFRESH_TOKEN
from custom_components.wyzeapi.token_manager import TokenManager


@pytest.fixture
def config_entry() -> SimpleNamespace:
    """A config entry as it looks right after a fresh login, before any refresh."""
    return SimpleNamespace(
        entry_id="entry-1",
        data={
            "username": "user@example.com",
            "password": "placeholder-password",
            "key_id": "placeholder-key-id",
            "api_key": "placeholder-api-key",
            ACCESS_TOKEN: "old-access-token",
            REFRESH_TOKEN: "old-refresh-token",
            REFRESH_TIME: "1000",
        },
    )


@pytest.fixture
def hass(config_entry: SimpleNamespace) -> Mock:
    """A minimal hass double exposing only what token_callback touches."""
    hass = Mock()
    hass.config_entries.async_entries = Mock(return_value=[config_entry])
    hass.config_entries.async_update_entry = Mock()
    return hass


@pytest.mark.asyncio
async def test_token_callback_preserves_key_id_and_api_key(
    hass: Mock, config_entry: SimpleNamespace
) -> None:
    """A token refresh must not drop key_id/api_key from the stored config entry.

    Regression test: token_callback used to rebuild the entry's `data` dict
    from a hardcoded field list (username, password, access/refresh token
    only), silently discarding key_id/api_key on every refresh. That left
    the config entry unable to complete a future full re-login, since Wyze
    requires key_id/api_key on the login call (though not on plain refresh).
    """
    TokenManager(hass, config_entry)
    new_token = SimpleNamespace(
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        refresh_time=2000,
    )

    await TokenManager.token_callback(new_token)

    hass.config_entries.async_update_entry.assert_called_once()
    _, kwargs = hass.config_entries.async_update_entry.call_args
    updated_data = kwargs["data"]

    assert updated_data["key_id"] == "placeholder-key-id"
    assert updated_data["api_key"] == "placeholder-api-key"
    assert updated_data["username"] == "user@example.com"
    assert updated_data["password"] == "placeholder-password"
    assert updated_data[ACCESS_TOKEN] == "new-access-token"
    assert updated_data[REFRESH_TOKEN] == "new-refresh-token"
    assert updated_data[REFRESH_TIME] == "2000"


@pytest.mark.asyncio
async def test_token_callback_updates_all_existing_entries(hass: Mock) -> None:
    """If multiple entries exist, each gets its own fields preserved and refreshed."""
    entry_a = SimpleNamespace(
        entry_id="a",
        data={"key_id": "key-a", "api_key": "api-a"},
    )
    entry_b = SimpleNamespace(
        entry_id="b",
        data={"key_id": "key-b", "api_key": "api-b"},
    )
    hass.config_entries.async_entries = Mock(return_value=[entry_a, entry_b])
    TokenManager(hass, entry_a)
    new_token = SimpleNamespace(
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        refresh_time=2000,
    )

    await TokenManager.token_callback(new_token)

    assert hass.config_entries.async_update_entry.call_count == 2
    seen_key_ids = {
        call.kwargs["data"]["key_id"]
        for call in hass.config_entries.async_update_entry.call_args_list
    }
    assert seen_key_ids == {"key-a", "key-b"}
