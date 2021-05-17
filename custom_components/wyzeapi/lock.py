#!/usr/bin/python3

"""Platform for light integration."""
import logging
# Import the device class from the component that you want to support
from datetime import timedelta
from typing import List

import homeassistant.components.lock
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from wyzeapy.base_client import AccessTokenError, Device, DeviceTypes, PropertyIDs
from wyzeapy.client import Client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("""Creating new WyzeApi lock component""")
    client = hass.data[DOMAIN][config_entry.entry_id]["wyze_client"]

    def get_devices() -> List[Device]:
        try:
            devices = client.get_devices()
        except AccessTokenError as e:
            _LOGGER.warning(e)
            client.reauthenticate()
            devices = client.get_devices()

        return devices

    devices = await hass.async_add_executor_job(get_devices)

    locks = []
    for device in devices:
        try:
            if DeviceTypes(device.product_type) == DeviceTypes.LOCK:
                locks.append(WyzeLock(client, device))
        except ValueError as e:
            _LOGGER.warning("{}: Please report this error to https://github.com/JoshuaMulliken/ha-wyzeapi".format(e))

    async_add_entities(locks, True)


class WyzeLock(homeassistant.components.lock.LockEntity):
    """Representation of a Wyze Lock."""
    _unlocked: bool
    _available: bool
    _door_open: bool

    _just_updated = False

    def __init__(self, client: Client, device: Device):
        """Initialize a Wyze lock."""
        self._device = device
        if DeviceTypes(self._device.product_type) not in [
            DeviceTypes.LOCK
        ]:
            raise AttributeError("Device type not supported")

        self._client = client

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
        self._just_updated = True

    def unlock(self, **kwargs):
        try:
            self._client.turn_off(self._device)
        except AccessTokenError:
            self._client.reauthenticate()
            self._client.turn_off(self._device)

        self._unlocked = True
        self._just_updated = True

    def open(self, **kwargs):
        raise NotImplementedError

    @property
    def name(self):
        """Return the display name of this lock."""
        # self._name = "wyzeapi_"+self._device_mac+"_"+ self._name
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
        return homeassistant.components.lock.STATE_UNLOCKED if self._unlocked else homeassistant.components.lock.STATE_LOCKED

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self._unlocked,
            "available": self.available,
            "door_open": self._door_open,
            "device_model": self._device.product_model,
            "mac": self.unique_id
        }

    @property
    def supported_features(self):
        return None

    def update(self):
        if not self._just_updated:
            try:
                device_info = self._client.get_info(self._device)
            except AccessTokenError:
                self._client.reauthenticate()
                device_info = self._client.get_info(self._device)

            for property_id, value in device_info:
                if property_id == PropertyIDs.ON:
                    self._unlocked = True if value == "1" else False
                elif property_id == PropertyIDs.AVAILABLE:
                    self._available = True if value == "1" else False
                elif property_id == PropertyIDs.DOOR_OPEN:
                    self._door_open = True if value == "1" else False

            self._just_updated = True
        else:
            self._just_updated = False
