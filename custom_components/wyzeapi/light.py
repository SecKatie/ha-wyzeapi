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
        self.__light = light
        self.__name = light.friendly_name
        self.__state = light.state
        self.__brightness = light.brightness
        self.__color_temp = light.color_temp
        self.__available = True
        self.__ssid = light.ssid
        self.__ip = light.ip
        self.__rssi = light.rssi
        self.__device_mac = light.device_mac
        self.__device_model = light.device_model

    @property
    def name(self):
        """Return the display name of this light."""
        # self._name = "wyzeapi_"+self._device_mac+"_"+ self._name
        return self.__name

    @property
    def unique_id(self):
        return self.__device_mac

    @property
    def available(self):
        """Return the connection status of this light"""
        return self.__available

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

    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self.__brightness

    @property
    def color_temp(self):
        """Return the CT color value in mired."""
        return self.__color_temp

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.__state

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
        self.__light.brightness = kwargs.get(ATTR_BRIGHTNESS)
        self.__light.color_temp = kwargs.get(ATTR_COLOR_TEMP)
        await self.__light.async_turn_on()

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self.__light.async_turn_off()

    async def async_update(self):
        """Fetch new state data for this light.
        This is the only method that should fetch new data for Home Assistant.
        """
        await self.__light.async_update()
        self.__state = self.__light.is_on()
        self.__available = self.__light.available
        self.__brightness = self.__light.brightness
        self.__color_temp = self.__light.color_temp
