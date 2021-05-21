#!/usr/bin/python3

"""Platform for light integration."""
import logging
from datetime import timedelta
from typing import List

import homeassistant.components.lock
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from wyzeapy.base_client import AccessTokenError, Device, DeviceTypes
from wyzeapy.client import Client
from wyzeapy.types import PropertyIDs

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("""Creating new WyzeApi lock component""")
    client: Client = hass.data[DOMAIN][config_entry.entry_id]

    def get_locks() -> List[Device]:
        try:
            return client.get_locks()
        except AccessTokenError as e:
            _LOGGER.warning(e)
            client.reauthenticate()
            return client.get_locks()

    locks = [WyzeLock(client, lock) for lock in await hass.async_add_executor_job(get_locks)]

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

    @property
    def should_poll(self) -> bool:
        return True

    def lock(self, **kwargs):
        _LOGGER.debug("Turning on lock")
        try:
            self._client.turn_on(self._device)
        except AccessTokenError:
            self._client.reauthenticate()
            self._client.turn_on(self._device)

        self._unlocked = False
        self._server_out_of_sync = True

    def unlock(self, **kwargs):
        try:
            self._client.turn_off(self._device)
        except AccessTokenError:
            self._client.reauthenticate()
            self._client.turn_off(self._device)

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

    def update(self):
        try:
            device_info = self._client.get_info(self._device)
        except AccessTokenError:
            self._client.reauthenticate()
            device_info = self._client.get_info(self._device)

        for property_id, value in device_info:
            if property_id == PropertyIDs.ON:
                if self._server_out_of_sync:
                    if self._unlocked != (True if value == "1" else False) and self._update_sync_count < 6:
                        self._update_sync_count += 1
                        _LOGGER.debug(f"Server is out of sync. It has been out of sync for "
                                      f"{self._update_sync_count} cycles")
                    else:
                        self._server_out_of_sync = False
                        _LOGGER.debug(f"Server is in sync. It was out of sync for {self._update_sync_count} cycles")
                        self._update_sync_count = 0
                else:
                    self._unlocked = True if value == "1" else False
            elif property_id == PropertyIDs.AVAILABLE:
                self._available = True if value == "1" else False
            elif property_id == PropertyIDs.DOOR_OPEN:
                self._door_open = True if value == "1" else False
