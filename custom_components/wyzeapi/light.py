#!/usr/bin/python3

"""Platform for light integration."""
import asyncio
import logging
# Import the device class from the component that you want to support
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP,
    LightEntity
)
from homeassistant.const import ATTR_ATTRIBUTION
from .wyzeapi.client import WyzeApiClient, WyzeBulb

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wyze Light platform."""
    _LOGGER.debug("""Creating new WyzeApi light component""")

    _ = config
    _ = discovery_info

    wyzeapi_client: WyzeApiClient = hass.data[DOMAIN]["wyzeapi_account"]

    # Add devices
    add_entities(HAWyzeBulb(wyzeapi_client, light) for light in await wyzeapi_client.list_bulbs())


class HAWyzeBulb(LightEntity):
    """Representation of a Wyze Bulb."""
    __client: WyzeApiClient
    __light: WyzeBulb
    __just_updated = False

    def __init__(self, client: WyzeApiClient, light: WyzeBulb):
        """Initialize a Wyze Bulb."""
        self.__light = light
        self.__client = client

    def turn_on(self, **kwargs: Any) -> None:
        asyncio.get_event_loop().run_until_complete(self.__client.turn_on_bulb(self.__light))
        self.__light.switch_state = 1
        self.__just_updated = True

    def turn_off(self, **kwargs: Any) -> None:
        asyncio.get_event_loop().run_until_complete(self.__client.turn_off_bulb(self.__light))
        self.__light.switch_state = 0
        self.__just_updated = True

    @property
    def name(self):
        """Return the display name of this light."""
        # self._name = "wyzeapi_"+self._device_mac+"_"+ self._name
        return self.__light.nick_name

    @property
    def unique_id(self):
        return self.__light.mac

    @property
    def available(self):
        """Return the connection status of this light"""
        return self.__light.avaliable

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "device model": self.__light.product_model,
            "ssid": self.__light.ssid,
            "ip": self.__light.ip,
            "rssi": self.__light.rssi,
            "mac": self.unique_id
        }

    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self.__light.brightness

    @property
    def color_temp(self):
        """Return the CT color value in mired."""
        return self.__light.color_temp

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.__light.switch_state == 1

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
        await self.__client.turn_on_bulb(self.__light)
        self.__light.switch_state = 1
        self.__just_updated = True

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self.__client.turn_off_bulb(self.__light)
        self.__light.switch_state = 1
        self.__just_updated = True

    async def async_update(self):
        """Fetch new state data for this light.
        This is the only method that should fetch new data for Home Assistant.
        """
        if self.__just_updated:
            self.__just_updated = False
            return

        await self.__client.update_bulb(self.__light)
