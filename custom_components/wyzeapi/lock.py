#!/usr/bin/python3

"""Platform for light integration."""
import logging
from abc import ABC
from datetime import timedelta
from typing import Callable, List, Any

import homeassistant.components.lock
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from wyzeapy import Wyzeapy, LockService
from wyzeapy.services.lock_service import Lock
from wyzeapy.types import DeviceTypes

from .const import DOMAIN, CONF_CLIENT

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=10)
MAX_OUT_OF_SYNC_COUNT = 5


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities: Callable[[List[Any], bool], None]) -> None:
    """
    This function sets up the config_entry

    :param hass: Home Assistant instance
    :param config_entry: The current config_entry
    :param async_add_entities: This function adds entities to the config_entry
    :return:
    """

    _LOGGER.debug("""Creating new WyzeApi lock component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    lock_service = await client.lock_service

    locks = [WyzeLock(lock_service, lock) for lock in await lock_service.get_locks()]

    async_add_entities(locks, True)


class WyzeLock(homeassistant.components.lock.LockEntity, ABC):
    """Representation of a Wyze Lock."""

    def __init__(self, lock_service: LockService, lock: Lock):
        """Initialize a Wyze lock."""
        self._lock = lock
        if self._lock.type not in [
            DeviceTypes.LOCK
        ]:
            raise AttributeError("Device type not supported")

        self._lock_service = lock_service

        self._out_of_sync_count = 0

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._lock.mac)
            },
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._lock.product_model
        }

    def lock(self, **kwargs):
        raise NotImplementedError

    def unlock(self, **kwargs):
        raise NotImplementedError

    @property
    def should_poll(self) -> bool:
        return True

    async def async_lock(self, **kwargs):
        _LOGGER.debug("Turning on lock")
        await self._lock_service.lock(self._lock)

        self._lock.unlocked = False

    async def async_unlock(self, **kwargs):
        await self._lock_service.unlock(self._lock)

        self._lock.unlocked = True

    @property
    def is_locked(self):
        return not self._lock.unlocked

    @property
    def name(self):
        """Return the display name of this lock."""
        return self._lock.nickname

    @property
    def unique_id(self):
        return self._lock.mac

    @property
    def available(self):
        """Return the connection status of this lock"""
        return self._lock.available

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.state,
            "available": self.available,
            "door_open": self._lock.door_open,
            "device_model": self._lock.product_model,
            "mac": self.unique_id
        }

    @property
    def supported_features(self):
        return None

    async def async_update(self):
        """
        This function updates the entity
        """
        lock = await self._lock_service.update(self._lock)
        if lock.unlocked == self._lock.unlocked or self._out_of_sync_count >= MAX_OUT_OF_SYNC_COUNT:
            self._lock = lock
            self._out_of_sync_count = 0
        else:
            self._out_of_sync_count += 1
