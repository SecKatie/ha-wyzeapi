"""Tests for Wyze camera battery sensors."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.wyzeapi import sensor as sensor_module
from custom_components.wyzeapi.const import CONF_CLIENT, DOMAIN
from custom_components.wyzeapi.sensor import WyzeCameraBatterySensor


def _camera(product_model: str, electricity: int = 87) -> SimpleNamespace:
    """Return a representative camera."""
    return SimpleNamespace(
        mac=f"MAC-{product_model}",
        nickname=f"Cam {product_model}",
        product_model=product_model,
        device_params={"electricity": electricity},
    )


def _service(**methods: AsyncMock) -> asyncio.Future:
    """Return a resolved future holding a mocked service."""
    future = asyncio.Future()
    future.set_result(SimpleNamespace(**methods))
    return future


async def _setup_with_cameras(cameras: list[SimpleNamespace]) -> list:
    """Run the sensor platform setup and return the created entities."""
    client = SimpleNamespace(
        lock_service=_service(get_locks=AsyncMock(return_value=[])),
        camera_service=_service(get_cameras=AsyncMock(return_value=cameras)),
        switch_usage_service=_service(get_switches=AsyncMock(return_value=[])),
        irrigation_service=_service(get_irrigations=AsyncMock(return_value=[])),
        air_purifier_service=_service(get_air_purifiers=AsyncMock(return_value=[])),
    )
    config_entry = SimpleNamespace(entry_id="entry-id")
    hass = SimpleNamespace(
        data={DOMAIN: {config_entry.entry_id: {CONF_CLIENT: client}}}
    )
    async_add_entities = Mock()

    await sensor_module.async_setup_entry(hass, config_entry, async_add_entities)

    entities, _ = async_add_entities.call_args.args
    return entities


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "product_model",
    [
        "GW_BE1",  # Video Doorbell Pro
        "GW_DBD",  # Duo Cam Doorbell
    ],
)
async def test_setup_entry_adds_doorbell_battery_sensor(product_model: str) -> None:
    """Battery-powered doorbells get a battery sensor fed by `electricity`."""
    entities = await _setup_with_cameras([_camera(product_model, electricity=87)])

    assert len(entities) == 1
    assert isinstance(entities[0], WyzeCameraBatterySensor)
    assert entities[0].native_value == 87


@pytest.mark.asyncio
async def test_setup_entry_skips_wired_cameras() -> None:
    """Cameras without a battery get no battery sensor."""
    entities = await _setup_with_cameras([_camera("WYZE_CAKP2JFUS")])

    assert entities == []
