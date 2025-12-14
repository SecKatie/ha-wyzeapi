#!/usr/bin/python3

"""Platform for switch integration."""

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectionError
from wyzeapy import BulbService, CameraService, SwitchService, Wyzeapy
from wyzeapy.exceptions import AccessTokenError, ParameterError, UnknownApiError
from wyzeapy.services.bulb_service import Bulb
from wyzeapy.services.camera_service import Camera
from wyzeapy.services.switch_service import Switch
from wyzeapy.types import Device, DeviceTypes, Event

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import (
    CAMERA_UPDATED,
    CONF_CLIENT,
    DOMAIN,
    LIGHT_UPDATED,
    WYZE_CAMERA_EVENT,
    WYZE_NOTIFICATION_TOGGLE,
)
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=30)
OUTDOOR_PLUGS = "WLPPO"
OUTDOOR_PLUG_INDIVUAL_OUTLETS = "WLPPO-SUB"
MOTION_SWITCH_UNSUPPORTED = [
    "GW_BE1",
    "GW_GC1",
    "GW_GC2",
]  # Video doorbell pro, OG, OG 3x Telephoto
POWER_SWITCH_UNSUPPORTED = ["GW_BE1"]  # Video doorbell pro (device has no off function)
NOTIFICATION_SWITCH_UNSUPPORTED = {
    "GW_GC1",
    "GW_GC2",
}  # OG and OG 3x Telephoto models currently unsupported due to InvalidSignature2 error


# noinspection DuplicatedCode
@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Any], bool], None],
) -> None:
    """This function sets up the config entry.

    :param hass: The Home Assistant Instance
    :param config_entry: The current config entry
    :param async_add_entities: This function adds entities to the config entry
    :return:
    """

    _LOGGER.debug("""Creating new WyzeApi light component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    switch_service = await client.switch_service
    wall_switch_service = await client.wall_switch_service
    camera_service = await client.camera_service
    bulb_service = await client.bulb_service

    switches: list[SwitchEntity] = []

    base_switches = await switch_service.get_switches()
    # The outdoor plug has a dummy switch that doesn't control anything
    # on the device. So we add non-outdoor plug switches and then
    # the switches for each individual outlet on the outdoor plug.
    switches.extend(
        WyzeSwitch(switch_service, switch)
        for switch in base_switches
        if switch.product_model not in OUTDOOR_PLUGS
        or switch.product_model.endswith("-SUB")  # Outdoor plug individual outlet
    )

    switches.extend(
        WyzeSwitch(wall_switch_service, switch)
        for switch in await wall_switch_service.get_switches()
    )

    camera_switches = await camera_service.get_cameras()
    for switch in camera_switches:
        # Notification toggle switch
        if switch.product_model not in NOTIFICATION_SWITCH_UNSUPPORTED:
            switches.append(WyzeCameraNotificationSwitch(camera_service, switch))

        # IoT Power switch
        if switch.product_model not in POWER_SWITCH_UNSUPPORTED:
            switches.append(WyzeSwitch(camera_service, switch))

        # Motion toggle switch
        if switch.product_model not in MOTION_SWITCH_UNSUPPORTED:
            switches.append(WyzeCameraMotionSwitch(camera_service, switch))

    switches.append(WyzeNotifications(client))

    bulb_switches = await bulb_service.get_bulbs()
    switches.extend(
        WzyeLightstripSwitch(bulb_service, bulb)
        for bulb in bulb_switches
        if bulb.type is DeviceTypes.LIGHTSTRIP
    )

    async_add_entities(switches, True)


class WyzeNotifications(SwitchEntity):
    """Class for notification switch."""

    _attr_should_poll = False
    _attr_name = "Wyze Notifications"

    def __init__(self, client: Wyzeapy) -> None:
        """Initialize the switch."""
        self._client = client
        self._is_on = False
        self._uid = WYZE_NOTIFICATION_TOGGLE
        self._just_updated = False

    @property
    def is_on(self) -> bool:
        """Return if the switch is on."""
        return self._is_on

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._uid)},
            "name": "Wyze Notifications",
            "manufacturer": "WyzeLabs",
            "model": "WyzeNotificationToggle",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self._client.enable_notifications()
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._is_on = True
            self._just_updated = True
            self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self._client.disable_notifications()
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._is_on = False
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @property
    def available(self):
        """Return the connection status of this switch."""
        return True

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._uid

    async def async_update(self):
        """Update the switch."""
        if not self._just_updated:
            self._is_on = await self._client.notifications_are_on
        else:
            self._just_updated = False


class WyzeSwitch(SwitchEntity):
    """Representation of a Wyze Switch."""

    _on: bool
    _available: bool
    _just_updated = False
    _old_event_ts: int = 0  # preload with 0 so that we know when it's been updated
    _attr_should_poll = False

    def __init__(self, service: CameraService | SwitchService, device: Device) -> None:
        """Initialize a Wyze Bulb."""
        self._device = device
        self._service = service

        if type(self._device) is Camera:
            self._device = Camera(self._device.raw_dict)
        elif type(self._device) is Switch:
            self._device = Switch(self._device.raw_dict)

    @property
    def device_info(self):
        """Return the device info.

        Outdoor plug needs its own setup based on how the MAC's are
        displayed and to keep the plugs organized by device.
        """
        if self._device.product_model == OUTDOOR_PLUG_INDIVUAL_OUTLETS:
            mac = self._device.mac.split("-")[0]
            return {
                "identifiers": {(DOMAIN, mac)},
                "connections": {
                    (
                        dr.CONNECTION_NETWORK_MAC,
                        mac,
                    )
                },
                "name": f"Outdoor Plug {mac}",
                "manufacturer": "WyzeLabs",
                "model": self._device.product_model,
            }
        return {
            "identifiers": {(DOMAIN, self._device.mac)},
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._device.mac,
                )
            },
            "name": self._device.nickname,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model,
        }

    @token_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self._service.turn_on(self._device)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._device.on = True
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self._service.turn_off(self._device)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._device.on = False
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the display name of this switch."""
        if type(self._device) is Camera:
            return f"{self._device.nickname} Power"
        return self._device.nickname

    @property
    def available(self):
        """Return the connection status of this switch."""
        return self._device.available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device.on

    @property
    def unique_id(self):
        """Return the unique ID."""
        return f"{self._device.mac}-switch"

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        dev_info = {}

        if self._device.device_params.get("electricity"):
            dev_info["Battery"] = str(
                self._device.device_params.get("electricity") + "%"
            )
        # noinspection DuplicatedCode
        if self._device.device_params.get("ip"):
            dev_info["IP"] = str(self._device.device_params.get("ip"))
        if self._device.device_params.get("rssi"):
            dev_info["RSSI"] = str(self._device.device_params.get("rssi"))
        if self._device.device_params.get("ssid"):
            dev_info["SSID"] = str(self._device.device_params.get("ssid"))

        return dev_info

    @token_exception_handler
    async def async_update(self):
        """Update the entity."""
        if not self._just_updated:
            self._device = await self._service.update(self._device)
        else:
            self._just_updated = False

    @callback
    def async_update_callback(self, switch: Switch):
        """Update the switch's state."""
        self._device = switch
        async_dispatcher_send(
            self.hass,
            f"{CAMERA_UPDATED}-{switch.mac}",
            switch,
        )
        self.async_schedule_update_ha_state()
        # if the switch is from a camera, lets check for new events
        if isinstance(switch, Camera):
            if (
                self._old_event_ts > 0
                and self._old_event_ts != switch.last_event_ts
                and switch.last_event is not None
            ):
                event: Event = switch.last_event
                # The screenshot/video urls are not always in the same positions in the lists, so we have to loop
                # through them
                _screenshot_url = None
                _video_url = None
                _ai_tag_list = []
                for resource in event.file_list:
                    _ai_tag_list = _ai_tag_list + resource["ai_tag_list"]
                    if resource["type"] == 1:
                        _screenshot_url = resource["url"]
                    elif resource["type"] == 2:
                        _video_url = resource["url"]
                _LOGGER.debug("Camera: %s has a new event", switch.nickname)
                self.hass.bus.fire(
                    WYZE_CAMERA_EVENT,
                    {
                        "device_name": switch.nickname,
                        "device_mac": switch.mac,
                        "ai_tag_list": _ai_tag_list,
                        "tag_list": event.tag_list,
                        "event_screenshot": _screenshot_url,
                        "event_video": _video_url,
                    },
                )
            self._old_event_ts = switch.last_event_ts

    async def async_added_to_hass(self) -> None:
        """Subscribe to update events."""
        self._device.callback_function = self.async_update_callback
        self._service.register_updater(self._device, 30)
        await self._service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister updated on removal."""
        self._service.unregister_updater(self._device)


class WyzeCameraNotificationSwitch(SwitchEntity):
    """Representation of a Wyze Camera Notification Switch."""

    _available: bool

    def __init__(self, service: CameraService, device: Camera) -> None:
        """Initialize a Wyze Notification Switch."""
        self._service = service
        self._device = device

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device.mac)},
            "name": self._device.nickname,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self._service.turn_on_notifications(self._device)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._device.notify = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self._service.turn_off_notifications(self._device)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._device.notify = False
            self.async_write_ha_state()

    @property
    def name(self):
        """Return the display name of this switch."""
        return f"{self._device.nickname} Notifications"

    @property
    def available(self):
        """Return the connection status of this switch."""
        return self._device.available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device.notify

    @property
    def unique_id(self):
        """Add a unique ID to the switch."""
        return f"{self._device.mac}-notification_switch"

    @callback
    def handle_camera_update(self, camera: Camera) -> None:
        """Update the switch whenever there is an update."""
        self._device = camera
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Listen for camera updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{CAMERA_UPDATED}-{self._device.mac}",
                self.handle_camera_update,
            )
        )


class WyzeCameraMotionSwitch(SwitchEntity):
    """Representation of a Wyze Camera Motion Detection Switch."""

    _available: bool

    def __init__(self, service: CameraService, device: Camera) -> None:
        """Initialize a Wyze Notification Switch."""
        self._service = service
        self._device = device

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device.mac)},
            "name": self._device.nickname,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self._service.turn_on_motion_detection(self._device)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._device.motion = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self._service.turn_off_motion_detection(self._device)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._device.motion = False
            self.async_write_ha_state()

    @property
    def name(self):
        """Return the display name of this switch."""
        return f"{self._device.nickname} Motion Detection"

    @property
    def available(self):
        """Return the connection status of this switch."""
        return self._device.available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device.motion

    @property
    def unique_id(self):
        """Add a unique ID to the switch."""
        return f"{self._device.mac}-motion_switch"

    @callback
    def handle_camera_update(self, camera: Camera) -> None:
        """Update the switch whenever there is an update."""
        self._device = camera
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Listen for camera updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{CAMERA_UPDATED}-{self._device.mac}",
                self.handle_camera_update,
            )
        )


class WzyeLightstripSwitch(SwitchEntity):
    """Music Mode Switch for Wyze Light Strip."""

    def __init__(self, service: BulbService, device: Device) -> None:
        """Initialize a Wyze Music Mode Switch."""
        self._service = service
        self._device = Bulb(device.raw_dict)

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device.mac)},
            "name": self._device.nickname,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self._service.music_mode_on(self._device)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._device.music_mode = True
            self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self._service.music_mode_off(self._device)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._device.music_mode = False
            self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the display name of this switch."""
        return f"{self._device.nickname} Music Mode for Effects"

    @property
    def available(self):
        """Return the connection status of this switch."""
        return self._device.available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device.music_mode

    @property
    def unique_id(self):
        """Add a unique ID to the switch."""
        return f"{self._device.mac}-music_mode"

    @callback
    def handle_light_update(self, bulb: Bulb) -> None:
        """Update the switch whenever there is an update."""
        self._device = bulb
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Listen for light updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIGHT_UPDATED}-{self._device.mac}",
                self.handle_light_update,
            )
        )
