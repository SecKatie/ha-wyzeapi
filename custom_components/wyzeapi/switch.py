#!/usr/bin/python3

"""Platform for switch integration."""
import logging
# Import the device class from the component that you want to support
from typing import Any

from homeassistant.components.switch import (
    SwitchEntity)
from homeassistant.const import ATTR_ATTRIBUTION
from wyzeapy.base_client import AccessTokenError, DeviceTypes, Device, PropertyIDs
from wyzeapy.client import Client

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    _ = config
    # We only want this platform to be set up via discovery.
    if discovery_info is None:
        return

    _LOGGER.debug("""Creating new WyzeApi light component""")
    wyzeapi_client: Client = hass.data[DOMAIN]['wyzeapi_client']
    devices = hass.data[DOMAIN]['devices']

    plugs = []
    for device in devices:
        if DeviceTypes(device.product_type) == DeviceTypes.PLUG:
            plugs.append(WyzeSwitch(wyzeapi_client, device))
        if DeviceTypes(device.product_type) == DeviceTypes.OUTDOOR_PLUG:
            plugs.append(WyzeSwitch(wyzeapi_client, device))

    add_entities(plugs, True)


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

        self._on = True
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
        return self._device.mac

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
