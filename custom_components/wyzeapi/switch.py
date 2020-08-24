#!/usr/bin/python3

"""Platform for switch integration."""
import logging
# Import the device class from the component that you want to support
from typing import Any

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


class HAWyzeSwitch(SwitchEntity):
    """Representation of a Wyze Switch."""

    def turn_on(self, **kwargs: Any) -> None:
        # TODO implement
        pass

    def turn_off(self, **kwargs: Any) -> None:
        # TODO implement
        pass

    def __init__(self, switch: WyzeSwitch):
        """Initialize a Wyze Switch."""
        self.__switch = switch
        self.__name = switch.friendly_name
        self.__state = switch.state
        self.__available = True
        self.__ssid = switch.ssid
        self.__ip = switch.ip
        self.__rssi = switch.rssi
        self.__device_mac = switch.device_mac
        self.__device_model = switch.device_model

    @property
    def name(self):
        """Return the display name of this switch."""
        # self._name = "wyzeapi_"+self._device_mac+"_"+ self._name
        return self.__name

    @property
    def available(self):
        """Return the connection status of this switch"""
        return self.__available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.__state

    @property
    def unique_id(self):
        return self.__device_mac

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.__state,
            "available": self.__available,
            "device model": self.__device_model,
            "ssid": self.__ssid,
            "ip": self.__ip,
            "rssi": self.__rssi,
            "mac": self.__device_mac
        }

    async def async_turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        await self.__switch.async_turn_on()

    async def async_turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        await self.__switch.async_turn_off()

    async def async_update(self):
        """Fetch new state data for this switch.
        This is the only method that should fetch new data for Home Assistant.
        """
        await self.__switch.async_update()
        self.__state = self.__switch.state
        self.__rssi = self.__switch.rssi
