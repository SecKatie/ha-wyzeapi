#!/usr/bin/python3

"""Platform for switch integration."""
import logging
from .wyzeapi.wyzeapi import WyzeApi
from . import DOMAIN

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import ATTR_ATTRIBUTION
# Import the device class from the component that you want to support
from homeassistant.components.switch import (PLATFORM_SCHEMA,SwitchDevice)

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"

async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wyze Switch platform."""
    _LOGGER.debug("""Creating new WyzeApi switch component""")

    # Add devices
	add_entities(WyzeSwitch(switch) for switch in await hass.data[DOMAIN]["wyzeapi_account"].async_list_switches())

class WyzeSwitch(SwitchDevice):
    """Representation of a Wyze Switch."""

    def __init__(self, switch):
        """Initialize a Wyze Switch."""
        self._switch = switch
        self._name = switch._friendly_name
        self._state = switch._state
        self._avaliable = True
        self._ssid = switch._ssid
        self._ip = switch._ip
        self._rssi = switch._rssi
        self._device_mac = switch._device_mac
        self._device_model = switch._device_model

    @property
    def name(self):
        """Return the display name of this switch."""
        #self._name = "wyzeapi_"+self._device_mac+"_"+ self._name
        return self._name

    @property
    def available(self):
        """Return the connection status of this switch"""
        return self._avaliable

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
            "available": self._avaliable,
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
        self._state = self._switch._state
        self._rssi = self._switch._rssi
