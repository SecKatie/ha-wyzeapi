"""Websocket command exposing Agora ("lake") stream credentials to the card."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

WS_TYPE = "wyzeapi/agora_stream_info"


async def handle_agora_stream_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return Agora credentials for the requested camera entity."""
    entity_id = msg["entity_id"]
    component = hass.data.get("camera")
    entity = component.get_entity(entity_id) if component else None
    if entity is None or not hasattr(entity, "async_agora_stream_info"):
        connection.send_error(
            msg["id"], "not_found", f"Unknown Wyze camera: {entity_id}"
        )
        return
    try:
        info = await entity.async_agora_stream_info()
    except Exception as e:  # noqa: BLE001 - report any failure to the card
        _LOGGER.warning("Agora stream info failed for %s: %s", entity_id, e)
        connection.send_error(msg["id"], "stream_info_failed", str(e))
        return
    connection.send_result(msg["id"], info)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE,
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def _ws_agora_stream_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Decorated command wrapper; delegates to the testable handler."""
    await handle_agora_stream_info(hass, connection, msg)


def async_register_agora_ws(hass: HomeAssistant) -> None:
    """Register the Agora stream-info websocket command."""
    websocket_api.async_register_command(hass, _ws_agora_stream_info)
