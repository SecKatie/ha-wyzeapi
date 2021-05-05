#!/usr/bin/python3

"""Platform for switch integration."""
import logging
# Import the device class from the component that you want to support
from datetime import timedelta
from typing import Any, List

from homeassistant.components.switch import (
    SwitchEntity)
from homeassistant.const import ATTR_ATTRIBUTION
from wyzeapy.base_client import AccessTokenError, DeviceTypes, Device, PropertyIDs
from wyzeapy.client import Client

from . import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("""Creating new WyzeApi light component""")
    client = hass.data[DOMAIN][config_entry.entry_id]

    def get_devices() -> List[Device]:
        try:
            devices = client.get_devices()
        except AccessTokenError as e:
            _LOGGER.warning(e)
            client.reauthenticate()
            devices = client.get_devices()

        return devices

    devices = await hass.async_add_executor_job(get_devices)

    plugs = []
    for device in devices:
        try:
            device_type = DeviceTypes(device.product_type)
            if device_type == DeviceTypes.PLUG or \
                    device_type == DeviceTypes.OUTDOOR_PLUG or \
                    device_type == DeviceTypes.CAMERA:
                plugs.append(WyzeSwitch(client, device))

        except ValueError as e:
            _LOGGER.warning("{}: Please report this error to https://github.com/JoshuaMulliken/ha-wyzeapi".format(e))

    async_add_entities(plugs, True)


class WyzeSwitch(SwitchEntity):
    """Representation of a Wyze Switch."""

    _client: Client
    _device: Device
    _on: bool
    _available: bool
    _just_updated = False

    def __init__(self, client: Client, device: Device):
        """Initialize a Wyze Bulb."""
        self._device = device
        self._client = client

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self.unique_id)
            },
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model
        }

    @property
    def should_poll(self) -> bool:
        return True

    def turn_on(self, **kwargs: Any) -> None:
        try:
            self._client.turn_on(self._device)
        except AccessTokenError:
            self._client.reauthenticate()
            self._client.turn_on(self._device)

        self._on = True
        self._just_updated = True

    def turn_off(self, **kwargs: Any) -> None:
        try:
            self._client.turn_off(self._device)
        except AccessTokenError:
            self._client.reauthenticate()
            self._client.turn_off(self._device)

        self._on = False
        self._just_updated = True

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._device.nickname

    @property
    def available(self):
        """Return the connection status of this switch"""
        return self._available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._on

    @property
    def unique_id(self):
        return "{}-switch".format(self._device.mac)

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "device model": self._device.product_model,
            "mac": self.unique_id
        }

    def update(self):
        if not self._just_updated:
            try:
                device_info = self._client.get_info(self._device)
            except AccessTokenError:
                self._client.reauthenticate()
                device_info = self._client.get_info(self._device)

            for property_id, value in device_info:
                if property_id == PropertyIDs.ON:
                    self._on = True if value == "1" else False
                elif property_id == PropertyIDs.AVAILABLE:
                    self._available = True if value == "1" else False

            self._just_updated = True
        else:
            self._just_updated = False
