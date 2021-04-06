#!/usr/bin/python3

"""Platform for light integration."""
import logging
# Import the device class from the component that you want to support
from typing import Any

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
from homeassistant.const import ATTR_ATTRIBUTION

from . import DOMAIN
from wyzeapy.base_client import AccessTokenError, Device, DeviceTypes, PropertyIDs
from wyzeapy.client import Client

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

    try:
        devices = wyzeapi_client.get_devices()
    except AccessTokenError as e:
        _LOGGER.warning(e)
        wyzeapi_client.reauthenticate()
        devices = wyzeapi_client.get_devices()

    lights = []
    color_lights = []
    for device in devices:
        if DeviceTypes(device.product_type) == DeviceTypes.LIGHT:
            lights.append(WyzeLight(wyzeapi_client, device))
        if DeviceTypes(device.product_type) == DeviceTypes.MESH_LIGHT:
            color_lights.append(WyzeColorLight(wyzeapi_client, device))

    add_entities(lights, True)
    add_entities(color_lights, True)


class WyzeLight(LightEntity):
    """Representation of a Wyze Bulb."""
    _brightness: int
    _color_temp: int
    _on: bool
    _available: bool

    _just_updated = False

    def __init__(self, client: Client, device: Device):
        """Initialize a Wyze Bulb."""
        self._device = device
        if DeviceTypes(self._device.product_type) not in [
            DeviceTypes.LIGHT
        ]:
            raise AttributeError("Device type not supported")

        self._client = client

    @property
    def should_poll(self) -> bool:
        return True

    @staticmethod
    def translate(value, input_min, input_max, output_min, output_max):
        if value is None:
            return None

        # Figure out how 'wide' each range is
        left_span = input_max - input_min
        right_span = output_max - output_min

        # Convert the left range into a 0-1 range (float)
        value_scaled = float(value - input_min) / float(left_span)

        # Convert the 0-1 range into a value in the right range.
        return output_min + (value_scaled * right_span)

    def turn_on(self, **kwargs: Any) -> None:
        if kwargs.get(ATTR_BRIGHTNESS) is not None:
            _LOGGER.debug("Setting brightness")
            self._brightness = self.translate(kwargs.get(ATTR_BRIGHTNESS), 1, 255, 1, 100)
            try:
                self._client.turn_on(self._device, [
                    self._client.create_pid_pair(PropertyIDs.BRIGHTNESS, str(int(self._brightness)))
                ])
            except AccessTokenError:
                self._client.reauthenticate()
                self._client.turn_on(self._device, [
                    self._client.create_pid_pair(PropertyIDs.BRIGHTNESS, str(int(self._brightness)))
                ])

        elif kwargs.get(ATTR_COLOR_TEMP) is not None:
            _LOGGER.debug("Setting color temp")
            self._color_temp = self.translate(kwargs.get(ATTR_COLOR_TEMP), 500, 140, 2700, 6500)
            try:
                self._client.turn_on(self._device, [
                    self._client.create_pid_pair(PropertyIDs.COLOR_TEMP, str(int(self._color_temp)))
                ])
            except AccessTokenError:
                self._client.reauthenticate()
                self._client.turn_on(self._device, [
                    self._client.create_pid_pair(PropertyIDs.COLOR_TEMP, str(int(self._color_temp)))
                ])
        else:
            _LOGGER.debug("Turning on color")
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
        """Return the display name of this light."""
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
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

    def update(self):
        if not self._just_updated:
            try:
                device_info = self._client.get_info(self._device)
            except AccessTokenError:
                self._client.reauthenticate()
                device_info = self._client.get_info(self._device)

            for property_id, value in device_info:
                if property_id == PropertyIDs.BRIGHTNESS:
                    self._brightness = int(value)
                elif property_id == PropertyIDs.COLOR_TEMP:
                    try:
                        self._color_temp = int(value)
                    except ValueError:
                        self._color_temp = 2700
                elif property_id == PropertyIDs.ON:
                    self._on = True if value == "1" else False
                elif property_id == PropertyIDs.AVAILABLE:
                    self._available = True if value == "1" else False

            self._just_updated = True
        else:
            self._just_updated = False


class WyzeColorLight(LightEntity):
    """Representation of a Wyze Bulb."""
    _brightness: int
    _color_temp: int
    _color: str
    _on: bool
    _available: bool

    _just_updated = False

    def __init__(self, client: Client, device: Device):
        """Initialize a Wyze Bulb."""
        self._device = device
        if DeviceTypes(self._device.product_type) not in [
            DeviceTypes.MESH_LIGHT
        ]:
            raise AttributeError("Device type not supported")

        self._client = client

    @property
    def should_poll(self) -> bool:
        return True

    @staticmethod
    def translate(value, input_min, input_max, output_min, output_max):
        if value is None:
            return None

        # Figure out how 'wide' each range is
        left_span = input_max - input_min
        right_span = output_max - output_min

        # Convert the left range into a 0-1 range (float)
        value_scaled = float(value - input_min) / float(left_span)

        # Convert the 0-1 range into a value in the right range.
        return output_min + (value_scaled * right_span)

    def turn_on(self, **kwargs: Any) -> None:
        _LOGGER.debug(kwargs)
        pairs = []
        
        if kwargs.get(ATTR_BRIGHTNESS) is not None:
            _LOGGER.debug("Setting brightness")
            self._brightness = self.translate(kwargs.get(ATTR_BRIGHTNESS), 1, 255, 1, 100)
            pairs.append(
                self._client.create_pid_pair(PropertyIDs.BRIGHTNESS, str(int(self._brightness)))
            )
        if kwargs.get(ATTR_COLOR_TEMP) is not None: 
            _LOGGER.debug("Setting color temp")
            self._color_temp = self.translate(kwargs.get(ATTR_COLOR_TEMP), 500, 140, 2700, 6500)
            pairs.append(
                self._client.create_pid_pair(PropertyIDs.COLOR_TEMP, str(int(self._color_temp)))
            )
        if kwargs.get(ATTR_HS_COLOR) is not None:
            _LOGGER.debug("Setting color")
            self._color = color_util.color_rgb_to_hex(*color_util.color_hs_to_RGB(*kwargs.get(ATTR_HS_COLOR)))
            pairs.append(
                self._client.create_pid_pair(PropertyIDs.COLOR, self._color)
            )
        
        try:
            self._client.turn_on(self._device, pairs)
        except AccessTokenError:
            self._client.reauthenticate()
            self._client.turn_on(self._device, pairs)

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
        """Return the display name of this light."""
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
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR

    def update(self):
        if not self._just_updated:
            try:
                device_info = self._client.get_info(self._device)
            except AccessTokenError:
                self._client.reauthenticate()
                device_info = self._client.get_info(self._device)

            for property_id, value in device_info:
                if property_id == PropertyIDs.BRIGHTNESS:
                    self._brightness = int(value)
                elif property_id == PropertyIDs.COLOR_TEMP:
                    try:
                        self._color_temp = int(value)
                    except ValueError:
                        self._color_temp = 2700
                elif property_id == PropertyIDs.ON:
                    self._on = True if value == "1" else False
                elif property_id == PropertyIDs.AVAILABLE:
                    self._available = True if value == "1" else False
                elif property_id == PropertyIDs.COLOR:
                    self._color = value

            self._just_updated = True
        else:
            self._just_updated = False
