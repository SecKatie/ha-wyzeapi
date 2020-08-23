#!/usr/bin/python3

"""Platform for light integration."""
import logging
from abc import ABC

# Import the device class from the component that you want to support
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP,
    LightEntity
)
from homeassistant.const import ATTR_ATTRIBUTION

from . import DOMAIN
from .wyzeapi.wyze_bulb import WyzeBulb

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wyze Light platform."""
    _LOGGER.debug("""Creating new WyzeApi light component""")

    _ = config
    _ = discovery_info

    # Add devices
    add_entities(HAWyzeBulb(light) for light in await hass.data[DOMAIN]["wyzeapi_account"].async_list_bulbs())


class HAWyzeBulb(LightEntity, ABC):
    """Representation of a Wyze Bulb."""

    def __init__(self, light: WyzeBulb):
        """Initialize a Wyze Bulb."""
        self._light = light
        self._name = light.friendly_name
        self._state = light.state
        self._brightness = light.brightness
        self._color_temp = light.color_temp
        self._available = True
        self._ssid = light.ssid
        self._ip = light.ip
        self._rssi = light.rssi
        self._device_mac = light.device_mac
        self._device_model = light.device_model

    @property
    def name(self):
        """Return the display name of this light."""
        # self._name = "wyzeapi_"+self._device_mac+"_"+ self._name
        return self._name

    @property
    def unique_id(self):
        return self._device_mac

    @property
    def available(self):
        """Return the connection status of this light"""
        return self._available

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

    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def color_temp(self):
        """Return the CT color value in mired."""
        return self._color_temp

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
        self._light.brightness = kwargs.get(ATTR_BRIGHTNESS)
        self._light.color_temp = kwargs.get(ATTR_COLOR_TEMP)
        await self._light.async_turn_on()

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self._light.async_turn_off()

    async def async_update(self):
        """Fetch new state data for this light.
        This is the only method that should fetch new data for Home Assistant.
        """
        await self._light.async_update()
        self._state = self._light.is_on()
        self._available = self._light.available
        self._brightness = self._light.brightness
        self._color_temp = self._light.color_temp
