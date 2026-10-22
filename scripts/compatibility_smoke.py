"""Exercise HA imports and platform setup without Wyze credentials or hardware.

Only the cloud client/device responses are synthetic. Home Assistant, registries,
config entries, platform classes, WebRTC models and entity state writes are real.
This does not verify cloud authentication, physical devices or live media.
"""

import asyncio
import importlib
import inspect
import logging
from pathlib import Path
import tempfile
from datetime import timedelta
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import EntityPlatform

from custom_components.wyzeapi import PLATFORMS, async_setup
from custom_components.wyzeapi.const import CONF_CLIENT, DOMAIN


def future(value):
    f = asyncio.get_running_loop().create_future()
    f.set_result(value)
    return f


async def main():
    for p in Path("custom_components/wyzeapi").glob("*.py"):
        importlib.import_module(
            "custom_components.wyzeapi" + ("" if p.stem == "__init__" else "." + p.stem)
        )
    with tempfile.TemporaryDirectory() as config:
        hass = HomeAssistant(config)
        loader.async_setup(hass)
        kwargs = dict(
            domain=DOMAIN,
            title="Compatibility",
            version=1,
            minor_version=1,
            data={},
            options={},
            source="user",
            unique_id="smoke",
            discovery_keys=MappingProxyType({}),
            subentries_data=[],
        )
        entry = ConfigEntry(
            **{
                k: v
                for k, v in kwargs.items()
                if k in inspect.signature(ConfigEntry).parameters
            }
        )
        hass.config_entries = ConfigEntries(hass, {})
        # Register the fixture without starting discovery or cloud login.
        hass.config_entries._entries[entry.entry_id] = entry
        assert await async_setup(hass, {})
        service = SimpleNamespace(
            **{
                name: AsyncMock(return_value=[])
                for name in [
                    "get_bulbs",
                    "get_switches",
                    "get_cameras",
                    "get_locks",
                    "get_thermostats",
                    "get_irrigations",
                    "get_air_purifiers",
                    "get_sensors",
                ]
            },
            has_hms=future(False),
            hms_id=None,
        )
        client = SimpleNamespace(
            **{
                name: future(service)
                for name in [
                    "bulb_service",
                    "switch_service",
                    "wall_switch_service",
                    "camera_service",
                    "lock_service",
                    "thermostat_service",
                    "irrigation_service",
                    "air_purifier_service",
                    "sensor_service",
                    "hms_service",
                    "switch_usage_service",
                ]
            }
        )
        hass.data[DOMAIN] = {entry.entry_id: {CONF_CLIENT: client, "coordinators": {}}}
        # Real HA device registry and config-entry types; only cloud responses are synthetic.
        if hasattr(dr, "async_setup"):
            dr.async_setup(hass)
        await dr.async_load(hass)
        if hasattr(er, "async_setup"):
            er.async_setup(hass)
        await er.async_load(hass)
        added = []

        def add(entities, update_before_add=False):
            added.extend(entities)

        for platform in PLATFORMS + ["binary_sensor"]:
            await importlib.import_module(
                "custom_components.wyzeapi." + platform
            ).async_setup_entry(hass, entry, add)
            print("SETUP PASS", platform)
        assert len(added) == 1, added
        assert added[0].unique_id
        camera = SimpleNamespace(
            mac="00:11:22:33:44:55",
            nickname="Test camera",
            product_model="HL_CAM3P",
            available=True,
            on=True,
        )
        service.get_cameras.return_value = [camera]
        service.update = AsyncMock(return_value=camera)
        service.get_stream_info = AsyncMock(return_value={"ice_servers": []})
        added.clear()
        await importlib.import_module(
            "custom_components.wyzeapi.camera"
        ).async_setup_entry(hass, entry, add)
        assert len(added) == 1
        entity = added[0]
        platform = EntityPlatform(
            hass=hass,
            logger=logging.getLogger(__name__),
            domain="camera",
            platform_name="wyzeapi",
            platform=None,
            scan_interval=timedelta(seconds=30),
            entity_namespace=None,
        )
        platform.config_entry = entry
        await platform.async_add_entities([entity])
        assert len(platform.entities) == 1
        assert entity._async_get_webrtc_client_configuration().data_channel == "data"
        entity.async_write_ha_state()
        assert hass.states.get(entity.entity_id) is not None
        await platform.async_reset()
        print("Camera creation, WebRTC configuration and HA state write passed.")
        await hass.async_stop()
    print(
        "All integration modules imported; 13 platform setup paths passed using real HA objects."
    )


if __name__ == "__main__":
    asyncio.run(main())
