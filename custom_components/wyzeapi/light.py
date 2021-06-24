#!/usr/bin/python3

"""Platform for light integration."""
import logging
# Import the device class from the component that you want to support
from datetime import timedelta
from typing import Any, Callable, List, Optional

import homeassistant.util.color as color_util
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP,
    SUPPORT_COLOR,
    LightEntity
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from wyzeapy.client import Client
from wyzeapy.net_client import AccessTokenError, Device, DeviceTypes
from wyzeapy.types import PropertyIDs

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities: Callable[[List[Any], bool], None]) -> None:
    """
    This function sets up the entities in the config entry

    :param hass: The Home Assistant instance
    :param config_entry: The config entry
    :param async_add_entities: A function that adds entities
    """

    _LOGGER.debug("""Creating new WyzeApi light component""")
    client: Client = hass.data[DOMAIN][config_entry.entry_id]

    lights = [WyzeLight(client, light) for light in await client.get_bulbs()]

    async_add_entities(lights, True)


class WyzeLight(LightEntity):
    """
    Representation of a Wyze Bulb.
    """
    # pylint: disable=R0902
    _brightness: float
    _color_temp: float
    _color: str
    _on: bool
    _available: bool

    _just_updated = False

    def __init__(self, client: Client, device: Device):
        """Initialize a Wyze Bulb."""
        self._device = device
        self._device_type = DeviceTypes(self._device.product_type)
        if self._device_type not in [
            DeviceTypes.LIGHT,
            DeviceTypes.MESH_LIGHT
        ]:
            raise AttributeError("Device type not supported")

        self._client = client

    def turn_on(self, **kwargs: Any) -> None:
        raise NotImplementedError

    def turn_off(self, **kwargs: Any) -> None:
        raise NotImplementedError

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

    @staticmethod
    def translate(value: float, input_min: float, input_max: float, output_min: float, output_max: float) -> \
            Optional[float]:
        """
        This function maps an input minimum and maximum to the output minimum and maximum

        :param value: The value to be converted
        :param input_min: The minimum value of the input
        :param input_max: The maximum value of the input
        :param output_min: The minimum value of the output
        :param output_max: The maximum value of the output
        :return: The converted value
        """

        if value is None:
            return None

        # Figure out how 'wide' each range is
        left_span = input_max - input_min
        right_span = output_max - output_min

        # Convert the left range into a 0-1 range (float)
        value_scaled = float(value - input_min) / float(left_span)

        # Convert the 0-1 range into a value in the right range.
        return output_min + (value_scaled * right_span)

    async def async_turn_on(self, **kwargs: Any) -> None:
        pids = []
        if kwargs.get(ATTR_BRIGHTNESS) is not None:
            _LOGGER.debug("Setting brightness")
            self._brightness = self.translate(kwargs.get(ATTR_BRIGHTNESS), 1, 255, 1, 100)

            pids.append(self._client.create_pid_pair(PropertyIDs.BRIGHTNESS, str(int(self._brightness))))
        if kwargs.get(ATTR_COLOR_TEMP) is not None:
            _LOGGER.debug("Setting color temp")
            self._color_temp = self.translate(kwargs.get(ATTR_COLOR_TEMP), 500, 140, 2700, 6500)

            pids.append(self._client.create_pid_pair(PropertyIDs.COLOR_TEMP, str(int(self._color_temp))))
        if self._device_type is DeviceTypes.MESH_LIGHT and kwargs.get(ATTR_HS_COLOR) is not None:
            _LOGGER.debug("Setting color")
            self._color = color_util.color_rgb_to_hex(*color_util.color_hs_to_RGB(*kwargs.get(ATTR_HS_COLOR)))

            pids.append(self._client.create_pid_pair(PropertyIDs.COLOR, self._color))

        _LOGGER.debug("Turning on light")
        try:
            await self._client.turn_on(self._device, pids)
        except AccessTokenError:
            await self._client.reauthenticate()
            await self._client.turn_on(self._device, pids)

        self._on = True
        self._just_updated = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self._client.turn_off(self._device)
        except AccessTokenError:
            await self._client.reauthenticate()
            await self._client.turn_off(self._device)

        self._on = False
        self._just_updated = True

    @property
    def name(self):
        """Return the display name of this light."""
        return self._device.nickname

    @property
    def unique_id(self):
        return self._device.mac

    @property
    def available(self):
        """Return the connection status of this light"""
        return self._available

    @property
    def hs_color(self):
        return color_util.color_RGB_to_hs(*color_util.rgb_hex_to_rgb_list(self._color))

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

    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self.translate(self._brightness, 1, 100, 1, 255)

    @property
    def color_temp(self):
        """Return the CT color value in mired."""
        return self.translate(self._color_temp, 2700, 6500, 500, 140)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._on

    @property
    def supported_features(self):
        if self._device_type is DeviceTypes.MESH_LIGHT:
            return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

    async def async_update(self):
        """
        This function updates the lock to be up to date with the Wyze Servers
        """

        if not self._just_updated:
            try:
                device_info = await self._client.get_info(self._device)
            except AccessTokenError:
                await self._client.reauthenticate()
                device_info = await self._client.get_info(self._device)

            for property_id, value in device_info:
                if property_id == PropertyIDs.BRIGHTNESS:
                    self._brightness = int(value)
                elif property_id == PropertyIDs.COLOR_TEMP:
                    try:
                        self._color_temp = int(value)
                    except ValueError:
                        self._color_temp = 2700
                elif property_id == PropertyIDs.ON:
                    self._on = value == "1"
                elif property_id == PropertyIDs.AVAILABLE:
                    self._available = value == "1"
                elif self._device_type is DeviceTypes.MESH_LIGHT and property_id == PropertyIDs.COLOR:
                    self._color = value

        else:
            self._just_updated = False
