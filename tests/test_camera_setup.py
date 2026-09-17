"""Tests for Wyze camera platform setup."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from wyzeapy.exceptions import UnknownApiError

from custom_components.wyzeapi import camera as camera_module
from custom_components.wyzeapi.camera import WyzeCamera
from custom_components.wyzeapi.const import CONF_CLIENT, DOMAIN


def _camera(mac: str, nickname: str) -> SimpleNamespace:
    """Return a representative camera device."""
    return SimpleNamespace(
        mac=mac,
        nickname=nickname,
        product_model="WYZE_CAKP2JFUS",
        available=True,
        on=True,
    )


def _hass_and_client(service: SimpleNamespace) -> tuple[SimpleNamespace, ...]:
    """Return (hass, config_entry) wired to the given camera service."""
    service_future: asyncio.Future = asyncio.Future()
    service_future.set_result(service)
    client = SimpleNamespace(camera_service=service_future)
    config_entry = SimpleNamespace(entry_id="entry-id")
    hass = SimpleNamespace(
        data={DOMAIN: {config_entry.entry_id: {CONF_CLIENT: client}}}
    )
    return hass, config_entry


@pytest.mark.asyncio
async def test_setup_entry_adds_cameras() -> None:
    """Cameras that update cleanly are added."""
    good = _camera("AA:BB:CC:DD:EE:FF", "Front Door")
    service = SimpleNamespace(
        get_cameras=AsyncMock(return_value=[good]),
        update=AsyncMock(side_effect=lambda device: device),
    )
    hass, config_entry = _hass_and_client(service)
    async_add_entities = Mock()

    await camera_module.async_setup_entry(hass, config_entry, async_add_entities)

    entities, _ = async_add_entities.call_args.args
    assert len(entities) == 1
    assert isinstance(entities[0], WyzeCamera)


@pytest.mark.asyncio
async def test_setup_entry_survives_a_camera_that_cannot_be_updated() -> None:
    """One failing camera must not stop the other cameras from loading.

    A camera removed from the Wyze account can linger in the cached device
    list, and fetching its properties then answers 3005 "unauthorized
    operation". Before this was guarded, that exception propagated out of
    async_setup_entry and the whole camera platform failed, so every camera
    on the account disappeared.
    """
    bad = _camera("11:22:33:44:55:66", "Deleted Cam")
    good = _camera("AA:BB:CC:DD:EE:FF", "Front Door")

    async def update(device: SimpleNamespace) -> SimpleNamespace:
        if device is bad:
            raise UnknownApiError("3005", "unauthorized operation")
        return device

    service = SimpleNamespace(
        get_cameras=AsyncMock(return_value=[bad, good]),
        update=AsyncMock(side_effect=update),
    )
    hass, config_entry = _hass_and_client(service)
    async_add_entities = Mock()

    await camera_module.async_setup_entry(hass, config_entry, async_add_entities)

    entities, _ = async_add_entities.call_args.args
    names = {entity.name for entity in entities}
    assert "Front Door" in names, "a healthy camera must still be added"
    assert "Deleted Cam" in names, "the failing camera is kept, just not updated"
    assert len(entities) == 2
