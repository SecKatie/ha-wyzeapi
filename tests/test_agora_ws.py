"""Tests for the Agora stream-info websocket command."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.wyzeapi import agora


def _conn() -> Mock:
    conn = Mock()
    conn.send_result = Mock()
    conn.send_error = Mock()
    return conn


@pytest.mark.asyncio
async def test_handler_sends_credentials_for_known_camera() -> None:
    entity = Mock()
    entity.async_agora_stream_info = AsyncMock(
        return_value={"provider": "lake", "channel": "chan"}
    )
    component = Mock()
    component.get_entity = Mock(return_value=entity)
    hass = Mock()
    hass.data = {"camera": component}
    conn = _conn()

    await agora.handle_agora_stream_info(
        hass, conn, {"id": 5, "entity_id": "camera.solar"}
    )

    conn.send_result.assert_called_once_with(5, {"provider": "lake", "channel": "chan"})
    conn.send_error.assert_not_called()


@pytest.mark.asyncio
async def test_handler_errors_when_camera_missing() -> None:
    component = Mock()
    component.get_entity = Mock(return_value=None)
    hass = Mock()
    hass.data = {"camera": component}
    conn = _conn()

    await agora.handle_agora_stream_info(
        hass, conn, {"id": 6, "entity_id": "camera.nope"}
    )

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args.args[0] == 6
    conn.send_result.assert_not_called()


@pytest.mark.asyncio
async def test_handler_errors_when_service_raises() -> None:
    entity = Mock()
    entity.async_agora_stream_info = AsyncMock(side_effect=RuntimeError("boom"))
    component = Mock()
    component.get_entity = Mock(return_value=entity)
    hass = Mock()
    hass.data = {"camera": component}
    conn = _conn()

    await agora.handle_agora_stream_info(
        hass, conn, {"id": 7, "entity_id": "camera.solar"}
    )

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args.args[0] == 7


def test_register_calls_async_register_command() -> None:
    hass = Mock()
    with patch.object(agora.websocket_api, "async_register_command") as reg:
        agora.async_register_agora_ws(hass)
    reg.assert_called_once()
