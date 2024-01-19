#!/usr/bin/python3

"""Platform for light integration."""
import asyncio
import logging
# Import the device class from the component that you want to support
from datetime import timedelta
from typing import Any, Callable, List

import homeassistant.util.color as color_util
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    LightEntity,
    LightEntityFeature,
    ColorMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from wyzeapy import Wyzeapy, BulbService, CameraService
from wyzeapy.services.bulb_service import Bulb
from wyzeapy.types import DeviceTypes, PropertyIDs
from wyzeapy.utils import create_pid_pair
from wyzeapy.services.camera_service import Camera
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from .const import DOMAIN, CONF_CLIENT, BULB_LOCAL_CONTROL, CAMERA_UPDATED, LIGHT_UPDATED
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=30)
EFFECT_MODE = "effects mode"
EFFECT_SUN_MATCH = "sun match"
EFFECT_SHADOW = "shadow"
EFFECT_LEAP = "leap"
EFFECT_FLICKER = "flicker"


@token_exception_handler
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities: Callable[[List[Any], bool], None]) -> None:
    """
    This function sets up the entities in the config entry

    :param hass: The Home Assistant instance
    :param config_entry: The config entry
    :param async_add_entities: A function that adds entities
    """

    _LOGGER.debug("""Creating new WyzeApi light component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    camera_service = await client.camera_service

    bulb_service = await client.bulb_service

    lights = [WyzeLight(bulb_service, light, config_entry) for light in await bulb_service.get_bulbs()]


    for camera in await camera_service.get_cameras():
        # Only model that I know of that has a floodlight
        if camera.product_model == "WYZE_CAKP2JFUS":
            lights.append(WyzeCamerafloodlight(camera, camera_service))

    async_add_entities(lights, True)


class WyzeLight(LightEntity):
    """
    Representation of a Wyze Bulb.
    """

    _just_updated = False

    def __init__(self, bulb_service: BulbService, bulb: Bulb, config_entry):
        """Initialize a Wyze Bulb."""
        self._bulb = bulb
        self._device_type = DeviceTypes(self._bulb.product_type)
        self._config_entry = config_entry
        self._local_control = config_entry.options.get(BULB_LOCAL_CONTROL)
        if self._device_type not in [
            DeviceTypes.LIGHT,
            DeviceTypes.MESH_LIGHT,
            DeviceTypes.LIGHTSTRIP
        ]:
            raise AttributeError("Device type not supported")

        self._bulb_service = bulb_service

    def turn_on(self, **kwargs: Any) -> None:
        raise NotImplementedError

    def turn_off(self, **kwargs: Any) -> None:
        raise NotImplementedError

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._bulb.mac)
            },
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._bulb.product_model
        }

    @property
    def should_poll(self) -> bool:
        return False

    @token_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        options = []
        self._local_control = self._config_entry.options.get(BULB_LOCAL_CONTROL)

        if kwargs.get(ATTR_BRIGHTNESS) is not None:
            brightness = round((kwargs.get(ATTR_BRIGHTNESS) / 255) * 100)

            options.append(create_pid_pair(PropertyIDs.BRIGHTNESS, str(brightness)))

            _LOGGER.debug("Setting brightness to %s" % brightness)
            _LOGGER.debug("Options: %s" % options)

            self._bulb.brightness = brightness

        if self._bulb.sun_match:  # Turn off sun match if we're changing anything other than brightness
            if any([kwargs.get(ATTR_COLOR_TEMP, kwargs.get(ATTR_HS_COLOR))]):
                options.append(create_pid_pair(PropertyIDs.SUN_MATCH, str(0)))
                self._bulb.sun_match = False
                _LOGGER.debug("Turning off sun match")

        if kwargs.get(ATTR_COLOR_TEMP) is not None:
            _LOGGER.debug("Setting color temp")
            color_temp = color_util.color_temperature_mired_to_kelvin(kwargs.get(ATTR_COLOR_TEMP))

            options.append(create_pid_pair(PropertyIDs.COLOR_TEMP, str(color_temp)))

            if self._device_type in [DeviceTypes.MESH_LIGHT, DeviceTypes.LIGHTSTRIP]:
                options.append(create_pid_pair(PropertyIDs.COLOR_MODE, str(2)))  # Put bulb in White Mode
                self._bulb.color_mode = '2'

            self._bulb.color_temp = color_temp
            self._bulb.color = color_util.color_rgb_to_hex(*color_util.color_temperature_to_rgb(color_temp))

        if (
            kwargs.get(ATTR_HS_COLOR) is not None
            and (
                self._device_type is DeviceTypes.MESH_LIGHT
                or self._device_type is DeviceTypes.LIGHTSTRIP
            )
        ):
            _LOGGER.debug("Setting color")
            color = color_util.color_rgb_to_hex(*color_util.color_hs_to_RGB(*kwargs.get(ATTR_HS_COLOR)))

            options.extend(
                [
                    create_pid_pair(PropertyIDs.COLOR, str(color)),
                    create_pid_pair(PropertyIDs.COLOR_MODE, str(1))  # Put bulb in Color Mode
                ]
            )

            self._bulb.color = color
            self._bulb.color_mode = '1'

        if kwargs.get(ATTR_EFFECT) is not None:
            if kwargs.get(ATTR_EFFECT) == EFFECT_SUN_MATCH:
                _LOGGER.debug("Setting Sun Match")
                options.append(create_pid_pair(PropertyIDs.SUN_MATCH, str(1)))
                self._bulb.sun_match = True
            else:
                if self._bulb.type is DeviceTypes.MESH_LIGHT: # Handle mesh light effects
                    self._local_control = False
                options.append(create_pid_pair(PropertyIDs.COLOR_MODE, str(3)))
                self._bulb.color_mode = "3"
                if kwargs.get(ATTR_EFFECT) == EFFECT_SHADOW:
                    _LOGGER.debug("Setting Shadow Effect")
                    options.append(create_pid_pair(PropertyIDs.LIGHTSTRIP_EFFECTS, str(1)))
                    self._bulb.effects = "1"
                elif kwargs.get(ATTR_EFFECT) == EFFECT_LEAP:
                    _LOGGER.debug("Setting Leap Effect")
                    options.append(create_pid_pair(PropertyIDs.LIGHTSTRIP_EFFECTS, str(2)))
                    self._bulb.effects = "2"
                elif kwargs.get(ATTR_EFFECT) == EFFECT_FLICKER:
                    _LOGGER.debug("Setting Flicker Effect")
                    options.append(create_pid_pair(PropertyIDs.LIGHTSTRIP_EFFECTS, str(3)))
                    self._bulb.effects = "3"

        _LOGGER.debug("Turning on light")
        loop = asyncio.get_event_loop()
        loop.create_task(self._bulb_service.turn_on(self._bulb, self._local_control, options))

        self._bulb.on = True
        self._just_updated = True
        self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        self._local_control = self._config_entry.options.get(BULB_LOCAL_CONTROL)
        loop = asyncio.get_event_loop()
        loop.create_task(self._bulb_service.turn_off(self._bulb, self._local_control))

        self._bulb.on = False
        self._just_updated = True
        self.async_schedule_update_ha_state()

    @property
    def supported_color_modes(self):
        if self._bulb.type in [DeviceTypes.MESH_LIGHT, DeviceTypes.LIGHTSTRIP]:
            return {ColorMode.COLOR_TEMP, ColorMode.HS}
        return {ColorMode.COLOR_TEMP}

    @property
    def color_mode(self):
        if self._bulb.type is DeviceTypes.LIGHT:
            return ColorMode.COLOR_TEMP
        return ColorMode.COLOR_TEMP if self._bulb.color_mode == "2" else ColorMode.HS

    @property
    def name(self):
        """Return the display name of this light."""
        return self._bulb.nickname

    @property
    def unique_id(self):
        return self._bulb.mac

    @property
    def available(self):
        """Return the connection status of this light"""
        return self._bulb.available

    @property
    def hs_color(self):
        return color_util.color_RGB_to_hs(*color_util.rgb_hex_to_rgb_list(self._bulb.color))

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        dev_info = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "device_model": self._bulb.product_model,
            "mac": self.unique_id
        }

        # noinspection DuplicatedCode
        if self._bulb.device_params.get("ip"):
            dev_info["IP"] = str(self._bulb.device_params.get("ip"))
        if self._bulb.device_params.get("rssi"):
            dev_info["RSSI"] = str(self._bulb.device_params.get("rssi"))
        if self._bulb.device_params.get("ssid"):
            dev_info["SSID"] = str(self._bulb.device_params.get("ssid"))
        dev_info["Sun Match"] = self._bulb.sun_match
        dev_info["local_control"] = (
            self._local_control
            and not self._bulb.cloud_fallback
        )

        if (
            self._device_type is DeviceTypes.LIGHTSTRIP
            and self._bulb.color_mode == "3"
        ):
            if self._bulb.effects == "1":
                dev_info["effect_mode"] = "Shadow"
            elif self._bulb.effects == "2":
                dev_info["effect_mode"] = "Leap"
            elif self._bulb.effects == "3":
                dev_info["effect_mode"] = "Flicker"

        if (
            self._device_type is DeviceTypes.MESH_LIGHT
            or self._device_type is DeviceTypes.LIGHTSTRIP
        ):

            if self._bulb.color_mode == '1':
                dev_info["mode"] = "Color"
            elif self._bulb.color_mode == '2':
                dev_info["mode"] = "White"
            elif self._bulb.color_mode == '3':
                dev_info["mode"] = "Effect"

        return dev_info

    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return round(self._bulb.brightness * 2.55, 1)

    @property
    def color_temp(self):
        """Return the CT color value in mired."""
        return color_util.color_temperature_kelvin_to_mired(self._bulb.color_temp)

    @property
    def max_mireds(self) -> int:
        if self._device_type is DeviceTypes.MESH_LIGHT:
            return color_util.color_temperature_kelvin_to_mired(1800) - 1
        return color_util.color_temperature_kelvin_to_mired(2700) - 1

    @property
    def min_mireds(self) -> int:
        return color_util.color_temperature_kelvin_to_mired(6500) + 1

    @property
    def effect_list(self):
        if self._device_type is DeviceTypes.LIGHTSTRIP:
            return [EFFECT_SHADOW, EFFECT_LEAP, EFFECT_FLICKER, EFFECT_SUN_MATCH]
        return [EFFECT_SUN_MATCH]

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._bulb.on

    @property
    def supported_features(self):
        return LightEntityFeature.EFFECT


    @token_exception_handler
    async def async_update(self):
        """
        This function updates the lock to be up to date with the Wyze Servers
        """

        if not self._just_updated:
            self._bulb = await self._bulb_service.update(self._bulb)
        else:
            self._just_updated = False

    @callback
    def async_update_callback(self, bulb: Bulb):
        """Update the bulb's state."""
        self._bulb = bulb
        self._local_control = self._config_entry.options.get(BULB_LOCAL_CONTROL)
        async_dispatcher_send(
            self.hass,
            f"{LIGHT_UPDATED}-{self._bulb.mac}",
            bulb
        )
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to update events."""
        self._bulb.callback_function = self.async_update_callback
        self._bulb_service.register_updater(self._bulb, 30)
        await self._bulb_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        self._bulb_service.unregister_updater(self._bulb)

class WyzeCamerafloodlight(LightEntity):
    """Representation of a Wyze Camera floodlight."""
    _available: bool
    _just_updated = False

    def __init__(self, camera: Camera, camera_service: CameraService) -> None:
        self._device = camera
        self._service = camera_service
        self._is_on = False

    @token_exception_handler
    async def async_turn_on(self, **kwargs) -> None:
        """Turn the floodlight on."""
        await self._service.floodlight_on(self._device)

        self._is_on = True
        self._just_updated = True
        self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_turn_off(self, **kwargs):
        """Turn the floodlight off."""
        await self._service.floodlight_off(self._device)

        self._is_on = False
        self._just_updated = True
        self.async_schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def is_on(self):
        """Return true if floodlight is on."""
        """Get info from camera service"""
        return self._device.floodlight

    @property
    def name(self) -> str:
        return f"{self._device.nickname} floodlight"

    @property
    def unique_id(self):
        return f"{self._device.mac}-floodlight"

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "device model": f"{self._device.product_model}.floodlight",
            "mac": self.unique_id
        }

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

    @callback
    def handle_camera_update(self, camera: Camera) -> None:
        """Update the camera object whenever there is an update"""
        self._device = camera
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{CAMERA_UPDATED}-{self._device.mac}",
                self.handle_camera_update,
            )
        )

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:track-light"

    @property
    def color_mode(self):
        return ColorMode.ONOFF
