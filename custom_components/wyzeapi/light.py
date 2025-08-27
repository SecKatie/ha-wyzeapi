"""Platform for light integration."""
# pyright: reportMissingTypeStubs=false

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectionError
from wyzeapy import BulbService, CameraService, Wyzeapy  # type: ignore
from wyzeapy.exceptions import AccessTokenError, ParameterError, UnknownApiError  # type: ignore
from wyzeapy.services.bulb_service import Bulb  # type: ignore
from wyzeapy.services.camera_service import Camera  # type: ignore
from wyzeapy.types import DeviceTypes, PropertyIDs  # type: ignore
from wyzeapy.utils import create_pid_pair  # type: ignore

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
import homeassistant.util.color as color_util

from .const import (
    BULB_LOCAL_CONTROL,
    CAMERA_UPDATED,
    CONF_CLIENT,
    DOMAIN,
    LIGHT_UPDATED,
)
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
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Any], bool], None],
) -> None:
    """Set up the entities in the config entry."""

    _LOGGER.debug("""Creating new WyzeApi light component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    camera_service = await client.camera_service

    bulb_service = await client.bulb_service

    lights: list[LightEntity] = [
        WyzeLight(bulb_service, light, config_entry)
        for light in await bulb_service.get_bulbs()
    ]

    for camera in await camera_service.get_cameras():
        if (
            camera.product_model == "WYZE_CAKP2JFUS"
            and camera.device_params["dongle_product_model"] == "HL_CFL"
            or camera.product_model in ("LD_CFP", "HL_CFL2")  # Floodlight v2
        ):
            lights.append(WyzeCamerafloodlight(camera, camera_service, "floodlight"))

        elif (
            camera.product_model in ("WYZE_CAKP2JFUS", "HL_CAM4")
        ) and camera.device_params[
            "dongle_product_model"
        ] == "HL_CAM3SS":  # Cam v3 with lamp socket accessory
            lights.append(WyzeCamerafloodlight(camera, camera_service, "lampsocket"))

        elif (
            camera.product_model == "AN_RSCW"
        ):  # Battery cam pro (integrated spotlight)
            lights.append(WyzeCamerafloodlight(camera, camera_service, "spotlight"))

    async_add_entities(lights, True)


class WyzeLight(LightEntity):
    """Representation of a Wyze Bulb."""

    _just_updated = False
    _attr_should_poll = False

    def __init__(self, bulb_service: BulbService, bulb: Bulb, config_entry) -> None:
        """Initialize a Wyze Bulb."""
        self._bulb = bulb
        self._device_type = DeviceTypes(self._bulb.product_type)
        self._config_entry = config_entry
        self._local_control = config_entry.options.get(BULB_LOCAL_CONTROL)
        if self._device_type not in [
            DeviceTypes.LIGHT,
            DeviceTypes.MESH_LIGHT,
            DeviceTypes.LIGHTSTRIP,
        ]:
            raise AttributeError("Device type not supported")

        self._bulb_service = bulb_service
        self._attr_min_color_temp_kelvin = (
            1800
            if self._device_type in [DeviceTypes.MESH_LIGHT, DeviceTypes.LIGHTSTRIP]
            else 2700
        )
        self._attr_max_color_temp_kelvin = 6500
        self._attr_name = self._bulb.nickname
        self._attr_unique_id = self._bulb.mac
        self._attr_supported_features = LightEntityFeature.EFFECT

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._bulb.mac)},
            "name": self._bulb.nickname,
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._bulb.mac,
                )
            },
            "manufacturer": "WyzeLabs",
            "model": self._bulb.product_model,
        }

    @token_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        options = []
        self._local_control = self._config_entry.options.get(BULB_LOCAL_CONTROL)

        brightness_val = kwargs.get(ATTR_BRIGHTNESS)
        if brightness_val is not None:
            brightness = round((int(brightness_val) / 255) * 100)

            options.append(create_pid_pair(PropertyIDs.BRIGHTNESS, str(brightness)))

            _LOGGER.debug("Setting brightness to %s", brightness)
            _LOGGER.debug("Options: %s", options)

            self._bulb.brightness = brightness

        if (
            self._bulb.sun_match
        ):  # Turn off sun match if we're changing anything other than brightness
            if any([kwargs.get(ATTR_COLOR_TEMP_KELVIN, kwargs.get(ATTR_HS_COLOR))]):
                options.append(create_pid_pair(PropertyIDs.SUN_MATCH, str(0)))
                self._bulb.sun_match = False
                _LOGGER.debug("Turning off sun match")

        color_temp_val = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        if color_temp_val is not None:
            _LOGGER.debug("Setting color temp")
            color_temp = int(color_temp_val)

            options.append(create_pid_pair(PropertyIDs.COLOR_TEMP, str(color_temp)))

            if self._device_type in [DeviceTypes.MESH_LIGHT, DeviceTypes.LIGHTSTRIP]:
                options.append(
                    create_pid_pair(PropertyIDs.COLOR_MODE, str(2))
                )  # Put bulb in White Mode
                self._bulb.color_mode = "2"

            self._bulb.color_temp = color_temp
            r, g, b = color_util.color_temperature_to_rgb(float(color_temp))
            self._bulb.color = color_util.color_rgb_to_hex(int(r), int(g), int(b))

        if kwargs.get(ATTR_HS_COLOR) is not None and (
            self._device_type is DeviceTypes.MESH_LIGHT
            or self._device_type is DeviceTypes.LIGHTSTRIP
        ):
            _LOGGER.debug("Setting color")
            hs = kwargs[ATTR_HS_COLOR]
            h, s = float(hs[0]), float(hs[1])
            r, g, b = color_util.color_hs_to_RGB(h, s)
            color = color_util.color_rgb_to_hex(int(r), int(g), int(b))

            options.extend(
                [
                    create_pid_pair(PropertyIDs.COLOR, str(color)),
                    create_pid_pair(
                        PropertyIDs.COLOR_MODE, str(1)
                    ),  # Put bulb in Color Mode
                ]
            )

            self._bulb.color = color
            self._bulb.color_mode = "1"

        if kwargs.get(ATTR_EFFECT) is not None:
            if kwargs.get(ATTR_EFFECT) == EFFECT_SUN_MATCH:
                _LOGGER.debug("Setting Sun Match")
                options.append(create_pid_pair(PropertyIDs.SUN_MATCH, str(1)))
                self._bulb.sun_match = True
            else:
                if (
                    self._bulb.type is DeviceTypes.MESH_LIGHT
                ):  # Handle mesh light effects
                    self._local_control = False
                options.append(create_pid_pair(PropertyIDs.COLOR_MODE, str(3)))
                self._bulb.color_mode = "3"
                if kwargs.get(ATTR_EFFECT) == EFFECT_SHADOW:
                    _LOGGER.debug("Setting Shadow Effect")
                    options.append(
                        create_pid_pair(PropertyIDs.LIGHTSTRIP_EFFECTS, str(1))
                    )
                    self._bulb.effects = "1"
                elif kwargs.get(ATTR_EFFECT) == EFFECT_LEAP:
                    _LOGGER.debug("Setting Leap Effect")
                    options.append(
                        create_pid_pair(PropertyIDs.LIGHTSTRIP_EFFECTS, str(2))
                    )
                    self._bulb.effects = "2"
                elif kwargs.get(ATTR_EFFECT) == EFFECT_FLICKER:
                    _LOGGER.debug("Setting Flicker Effect")
                    options.append(
                        create_pid_pair(PropertyIDs.LIGHTSTRIP_EFFECTS, str(3))
                    )
                    self._bulb.effects = "3"

        _LOGGER.debug("Turning on light")
        try:
            await self._bulb_service.turn_on(self._bulb, self._local_control, options)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._bulb.on = True
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self._local_control = self._config_entry.options.get(BULB_LOCAL_CONTROL)
        try:
            await self._bulb_service.turn_off(self._bulb, self._local_control)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._bulb.on = False
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @property
    def supported_color_modes(self):
        """Return the supported color modes."""
        if self._bulb.type in [DeviceTypes.MESH_LIGHT, DeviceTypes.LIGHTSTRIP]:
            return {ColorMode.COLOR_TEMP, ColorMode.HS}
        return {ColorMode.COLOR_TEMP}

    @property
    def color_mode(self):
        """Return the current color mode."""
        if self._bulb.type is DeviceTypes.LIGHT:
            return ColorMode.COLOR_TEMP
        return ColorMode.COLOR_TEMP if self._bulb.color_mode == "2" else ColorMode.HS

    @property
    def available(self):
        """Return the connection status of this light."""
        return self._bulb.available

    @property
    def hs_color(self):
        """Return the HS color."""
        return color_util.color_RGB_to_hs(
            *color_util.rgb_hex_to_rgb_list(self._bulb.color)
        )

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        dev_info = {}

        # noinspection DuplicatedCode
        if self._bulb.device_params.get("ip"):
            dev_info["IP"] = str(self._bulb.device_params.get("ip"))
        if self._bulb.device_params.get("rssi"):
            dev_info["RSSI"] = str(self._bulb.device_params.get("rssi"))
        if self._bulb.device_params.get("ssid"):
            dev_info["SSID"] = str(self._bulb.device_params.get("ssid"))
        dev_info["Sun Match"] = self._bulb.sun_match
        dev_info["local_control"] = (
            self._local_control and not self._bulb.cloud_fallback
        )

        if self._device_type is DeviceTypes.LIGHTSTRIP and self._bulb.color_mode == "3":
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
            if self._bulb.color_mode == "1":
                dev_info["mode"] = "Color"
            elif self._bulb.color_mode == "2":
                dev_info["mode"] = "White"
            elif self._bulb.color_mode == "3":
                dev_info["mode"] = "Effect"

        return dev_info

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return round(self._bulb.brightness * 2.55, 1)

    @property
    def color_temp_kelvin(self):
        """Return the color temp in Kelvin."""
        return self._bulb.color_temp

    @property
    def effect_list(self):
        """Return the list of effects."""
        if self._device_type is DeviceTypes.LIGHTSTRIP:
            return [EFFECT_SHADOW, EFFECT_LEAP, EFFECT_FLICKER, EFFECT_SUN_MATCH]
        return [EFFECT_SUN_MATCH]

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._bulb.on

    @token_exception_handler
    async def async_update(self):
        """Update the lock to be up to date with the Wyze Servers."""
        if not self._just_updated:
            self._bulb = await self._bulb_service.update(self._bulb)
        else:
            self._just_updated = False

    @callback
    def async_update_callback(self, bulb: Bulb):
        """Update the bulb's state."""
        self._bulb = bulb
        self._local_control = self._config_entry.options.get(BULB_LOCAL_CONTROL)
        async_dispatcher_send(self.hass, f"{LIGHT_UPDATED}-{self._bulb.mac}", bulb)
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to update events."""
        self._bulb.callback_function = self.async_update_callback
        self._bulb_service.register_updater(self._bulb, 30)
        await self._bulb_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister the updater."""
        self._bulb_service.unregister_updater(self._bulb)


class WyzeCamerafloodlight(LightEntity):
    """Representation of a Wyze Camera floodlight."""

    _available: bool
    _just_updated = False
    _attr_should_poll = False

    def __init__(
        self, camera: Camera, camera_service: CameraService, light_type: str
    ) -> None:
        """Initialize the camera floodlight."""
        self._device = camera
        self._service = camera_service
        self._light_type = light_type
        self._attr_unique_id = f"{self._device.mac}-{self._light_type}"
        self._is_on = self._device.floodlight

    @token_exception_handler
    async def async_turn_on(self, **kwargs) -> None:
        """Turn the floodlight on."""
        try:
            await self._service.floodlight_on(self._device)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._is_on = True
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_turn_off(self, **kwargs):
        """Turn the floodlight off."""
        try:
            await self._service.floodlight_off(self._device)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._is_on = False
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if floodlight is on."""
        return self._device.floodlight

    @property
    def name(self) -> str:
        """Return the device name."""
        return f"{self._device.nickname} {'Lamp Socket' if self._light_type == 'lampsocket' else ('Floodlight' if self._light_type == 'floodlight' else 'Spotlight')}"

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device.mac)},
            "name": self._device.nickname,
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._device.mac,
                )
            },
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model,
        }

    @callback
    def handle_camera_update(self, camera: Camera) -> None:
        """Update the camera object whenever there is an update."""
        self._device = camera
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add listener on startup."""
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

        return (
            "mdi:lightbulb"
            if self._light_type == "lampsocket"
            else (
                "mdi:track-light"
                if self._light_type == "floodlight"
                else "mdi:spotlight"
            )
        )

    @property
    def color_mode(self):
        """Return the color mode."""
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self):
        """Return the supported color mode."""
        return ColorMode.ONOFF
