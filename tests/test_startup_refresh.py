import asyncio
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from bleak_retry_connector import BleakNotFoundError
from homeassistant.helpers.update_coordinator import UpdateFailed

aiousbwatcher = types.ModuleType("aiousbwatcher")
aiousbwatcher.AIOUSBWatcher = object
aiousbwatcher.InotifyNotAvailableError = RuntimeError
sys.modules.setdefault("aiousbwatcher", aiousbwatcher)

serial = types.ModuleType("serial")
serial_tools = types.ModuleType("serial.tools")
serial_list_ports = types.ModuleType("serial.tools.list_ports")
serial_list_ports_common = types.ModuleType("serial.tools.list_ports_common")
serial_list_ports.comports = lambda: []
serial_list_ports_common.ListPortInfo = object
sys.modules.setdefault("serial", serial)
sys.modules.setdefault("serial.tools", serial_tools)
sys.modules.setdefault("serial.tools.list_ports", serial_list_ports)
sys.modules.setdefault("serial.tools.list_ports_common", serial_list_ports_common)

bluetooth = types.ModuleType("homeassistant.components.bluetooth")
bluetooth.async_ble_device_from_address = lambda *args, **kwargs: None
bluetooth.async_scanner_count = lambda *args, **kwargs: 1
sys.modules.setdefault("homeassistant.components.bluetooth", bluetooth)

from custom_components.wyzeapi import lock as lock_platform  # noqa: E402
from custom_components.wyzeapi.const import CONF_CLIENT, DOMAIN  # noqa: E402
from custom_components.wyzeapi.coordinator import WyzeLockBoltCoordinator  # noqa: E402


class AwaitableValue:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _get_value():
            return self._value

        return _get_value().__await__()


def run(coro):
    return asyncio.run(coro)


def test_lock_platform_does_not_refresh_entities_before_add(monkeypatch):
    coordinator = SimpleNamespace()
    lock_service = SimpleNamespace(
        get_locks=AsyncMock(
            return_value=[
                SimpleNamespace(
                    product_model="YD_BT1",
                    mac="lock-bolt-uuid",
                    nickname="Front Door",
                )
            ]
        )
    )
    client = SimpleNamespace(lock_service=AwaitableValue(lock_service))
    hass = SimpleNamespace(
        data={
            DOMAIN: {
                "entry-id": {
                    CONF_CLIENT: client,
                    "coordinators": {"lock-bolt-uuid": coordinator},
                }
            }
        }
    )
    config_entry = SimpleNamespace(entry_id="entry-id")
    added = {}

    monkeypatch.setattr(
        lock_platform,
        "WyzeLockBolt",
        lambda lock_bolt_coordinator: ("lock-bolt", lock_bolt_coordinator),
    )

    def async_add_entities(entities, update_before_add=False):
        added["entities"] = entities
        added["update_before_add"] = update_before_add

    run(lock_platform.async_setup_entry(hass, config_entry, async_add_entities))

    assert added["entities"] == [("lock-bolt", coordinator)]
    assert added["update_before_add"] is False


def test_lock_bolt_unknown_until_first_successful_refresh():
    entity = lock_platform.WyzeLockBolt.__new__(lock_platform.WyzeLockBolt)
    entity.coordinator = SimpleNamespace(data=None, last_update_success=False)

    assert entity.is_locked is None
    assert entity.available is False
    assert entity.state_attributes == {}


def test_lock_bolt_ble_connection_failures_become_update_failed():
    coordinator = WyzeLockBoltCoordinator.__new__(WyzeLockBoltCoordinator)
    coordinator._current_command = None
    coordinator.data = None
    coordinator._lock = SimpleNamespace(nickname="Front Door")
    coordinator._mac = "00:11:22:33:44:55"
    coordinator._get_ble_client = AsyncMock(side_effect=BleakNotFoundError("timeout"))
    coordinator._disconnect = AsyncMock()

    with pytest.raises(
        UpdateFailed, match="Could not connect to BLE device Front Door"
    ):
        run(coordinator._async_update_data())

    coordinator._disconnect.assert_awaited_once()
