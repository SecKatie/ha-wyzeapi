"""Tests for Agora frontend/ws registration wiring."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.wyzeapi import (
    async_register_agora_frontend,
    AGORA_SDK_URL,
    AGORA_CARD_URL,
)


@pytest.mark.asyncio
async def test_registration_is_idempotent_and_wires_everything() -> None:
    hass = Mock()
    hass.data = {}
    hass.http = Mock()
    hass.http.async_register_static_paths = AsyncMock()

    with (
        patch("custom_components.wyzeapi.async_register_agora_ws") as reg_ws,
        patch("custom_components.wyzeapi.add_extra_js_url") as add_js,
    ):
        await async_register_agora_frontend(hass)
        await async_register_agora_frontend(hass)  # second call: no-op

    reg_ws.assert_called_once()
    assert add_js.call_count == 2
    # SDK must be registered before the card (the card references window.AgoraRTC)
    assert [call.args[1] for call in add_js.call_args_list] == [
        AGORA_SDK_URL,
        AGORA_CARD_URL,
    ]
    hass.http.async_register_static_paths.assert_awaited_once()
