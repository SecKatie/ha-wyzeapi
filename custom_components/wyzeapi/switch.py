#!/usr/bin/python3

"""Platform for switch integration."""
import logging
from abc import ABC

# Import the device class from the component that you want to support
from homeassistant.components.switch import (
    SwitchEntity)
from homeassistant.const import ATTR_ATTRIBUTION

from . import DOMAIN
from .wyzeapi.wyze_switch import WyzeSwitch

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wyze Switch platform."""
    _LOGGER.debug("""Creating new WyzeApi switch component""")

    _ = config
    _ = discovery_info

    # Add devices
    add_entities(HAWyzeSwitch(switch) for switch in await hass.data[DOMAIN]["wyzeapi_account"].async_list_switches())


class HAWyzeSwitch(SwitchEntity, ABC):
    """Representation of a Wyze Switch."""

    def __init__(self, switch: WyzeSwitch):
        """Initialize a Wyze Switch."""
        self._switch = switch
        self._name = switch.friendly_name
        self._state = switch.state
        self._available = True
        self._ssid = switch.ssid
        self._ip = switch.ip
        self._rssi = switch.rssi
        self._device_mac = switch.device_mac
        self._device_model = switch.device_model

    @property
    def name(self):
        """Return the display name of this switch."""
        # self._name = "wyzeapi_"+self._device_mac+"_"+ self._name
        return self._name

    @property
    def available(self):
        """Return the connection status of this switch"""
        return self._available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def unique_id(self):
        return self._device_mac

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self._state,
            "available": self._available,
            "device model": self._device_model,
            "ssid": self._ssid,
            "ip": self._ip,
            "rssi": self._rssi,
            "mac": self._device_mac
        }

    async def async_turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        await self._switch.async_turn_on()

    async def async_turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        await self._switch.async_turn_off()

    async def async_update(self):
        """Fetch new state data for this switch.
        This is the only method that should fetch new data for Home Assistant.
        """
        await self._switch.async_update()
        self._state = self._switch.state
        self._rssi = self._switch.rssi
