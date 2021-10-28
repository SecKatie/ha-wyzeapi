#!/usr/bin/python3

"""Platform for sensor integration."""

import logging
from typing import Any, Callable, List

from wyzeapy import Wyzeapy
from wyzeapy.services.lock_service import Lock

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_CLIENT, DOMAIN, LOCK_UPDATED
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)

@token_exception_handler
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities: Callable[[List[Any], bool], None]) -> None:

    _LOGGER.debug("""Creating new WyzeApi sensor component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]

    # Get the list of locks so that we can create lock and keypad battery sensors
    lock_service = await client.lock_service

    locks = await lock_service.get_locks()
    lock_battery_sensors = []
    for lock in locks:
        lock_battery_sensors.append(WyzeLockBatterySensor(lock, WyzeLockBatterySensor.LOCK_BATTERY))
        lock_battery_sensors.append(WyzeLockBatterySensor(lock, WyzeLockBatterySensor.KEYPAD_BATTERY))

    async_add_entities(lock_battery_sensors, True)

class WyzeLockBatterySensor(SensorEntity):

    LOCK_BATTERY = "lock_battery"
    KEYPAD_BATTERY = "keypad_battery"

    _attr_device_class = DEVICE_CLASS_BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    # make the battery unavailable by default, this will be toggled after the first upate from the battery entity that has battery data.
    _available = False

    def __init__(self, lock, battery_type):
        self._lock = lock
        self._battery_type = battery_type

    @callback
    def handle_lock_update(self, lock: Lock) -> None:
        self._lock = lock
        if self._lock.raw_dict.get("power") and self._battery_type == self.LOCK_BATTERY:
            self._available = True
        if self._lock.raw_dict.get("keypad", {}).get("power") and self._battery_type == self.KEYPAD_BATTERY:
            self._available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LOCK_UPDATED}-{self._lock.mac}",
                self.handle_lock_update,
            )
        )


    @property
    def unique_id(self):
        return f"{self._lock.nickname}.{self._battery_type}"

    @property
    def available(self) -> bool:
        return self._available

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._lock.mac)
            },
            "name": f"{self._lock.nickname}.{self._battery_type}",
            "type": f"lock.{self._battery_type}"
        }

    @property
    def native_value(self):
        """Return the state of the device."""
        if self._battery_type == self.LOCK_BATTERY:
            return str(self._lock.raw_dict.get("power"))
        elif (self._battery_type == self.KEYPAD_BATTERY):
            return str(self._lock.raw_dict.get("keypad", {}).get("power"))
        return 0

