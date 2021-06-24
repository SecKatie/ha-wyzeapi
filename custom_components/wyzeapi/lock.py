#!/usr/bin/python3

"""Platform for light integration."""
import logging
from datetime import timedelta
from typing import Callable, List, Any

import homeassistant.components.lock
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from wyzeapy.client import Client
from wyzeapy.net_client import AccessTokenError, Device, DeviceTypes
from wyzeapy.types import PropertyIDs

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=10)


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
    client: Client = hass.data[DOMAIN][config_entry.entry_id]

    locks = [WyzeLock(client, lock) for lock in await client.get_locks()]

    async_add_entities(locks, True)


class WyzeLock(homeassistant.components.lock.LockEntity):
    """Representation of a Wyze Lock."""
    _unlocked: bool
    _available: bool
    _door_open: bool
    _update_sync_count: int

    _server_out_of_sync = False

    def __init__(self, client: Client, device: Device):
        """Initialize a Wyze lock."""
        self._device = device
        if DeviceTypes(self._device.product_type) not in [
            DeviceTypes.LOCK
        ]:
            raise AttributeError("Device type not supported")

        self._client = client
        self._update_sync_count = 0

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._device.mac)
            },
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model
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
        try:
            await self._client.turn_on(self._device)
        except AccessTokenError:
            await self._client.reauthenticate()
            await self._client.turn_on(self._device)

        self._unlocked = False
        self._server_out_of_sync = True

    async def async_unlock(self, **kwargs):
        try:
            await self._client.turn_off(self._device)
        except AccessTokenError:
            await self._client.reauthenticate()
            await self._client.turn_off(self._device)

        self._unlocked = True
        self._server_out_of_sync = True

    def open(self, **kwargs):
        raise NotImplementedError

    @property
    def name(self):
        """Return the display name of this lock."""
        return self._device.nickname

    @property
    def unique_id(self):
        return self._device.mac

    @property
    def available(self):
        """Return the connection status of this light"""
        return self._available

    @property
    def state(self):
        return homeassistant.components.lock.STATE_UNLOCKED if self._unlocked else \
            homeassistant.components.lock.STATE_LOCKED

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.state,
            "available": self.available,
            "door_open": self._door_open,
            "device_model": self._device.product_model,
            "mac": self.unique_id
        }

    @property
    def supported_features(self):
        return None

    async def async_update(self):
        """
        This function updates the entity
        """

        try:
            device_info = await self._client.get_info(self._device)
        except AccessTokenError:
            await self._client.reauthenticate()
            device_info = await self._client.get_info(self._device)

        for property_id, value in device_info:
            if property_id == PropertyIDs.ON:
                if self._server_out_of_sync:
                    if self._unlocked != (value == "1") and self._update_sync_count < 6:
                        self._update_sync_count += 1
                        # pylint: disable=logging-not-lazy
                        _LOGGER.debug("Server is out of sync. It has been out of sync for %s cycles" %
                                      self._update_sync_count)
                    else:
                        self._server_out_of_sync = False
                        # pylint: disable=logging-not-lazy
                        _LOGGER.debug('Server is in sync. It was out of sync for %s cycles' %
                                      self._update_sync_count)
                        self._update_sync_count = 0
                else:
                    self._unlocked = value == "1"
            elif property_id == PropertyIDs.AVAILABLE:
                self._available = value == "1"
            elif property_id == PropertyIDs.DOOR_OPEN:
                self._door_open = value == "1"
