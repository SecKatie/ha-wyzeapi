#!/usr/bin/python3

"""Platform for switch integration."""

import logging
from datetime import timedelta
from typing import Any, Callable, List, Union
from aiohttp.client_exceptions import ClientConnectionError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send,
    async_dispatcher_connect,
)
from homeassistant.helpers import device_registry as dr
from wyzeapy import CameraService, SwitchService, Wyzeapy, BulbService
from wyzeapy.exceptions import AccessTokenError, ParameterError, UnknownApiError
from wyzeapy.services.camera_service import Camera
from wyzeapy.services.switch_service import Switch
from wyzeapy.services.bulb_service import Bulb
from wyzeapy.types import Device, Event, DeviceTypes

from .const import CAMERA_UPDATED, LIGHT_UPDATED
from .const import DOMAIN, CONF_CLIENT, WYZE_CAMERA_EVENT, WYZE_NOTIFICATION_TOGGLE
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=30)
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
    async_add_entities: Callable[[List[Any], bool], None],
) -> None:
    """
    This function sets up the config entry

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

    switches: List[SwitchEntity] = [
        WyzeSwitch(switch_service, switch)
        for switch in await switch_service.get_switches()
    ]

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
            switches.extend([WyzeSwitch(camera_service, switch)])

        # Motion toggle switch
        if switch.product_model not in MOTION_SWITCH_UNSUPPORTED:
            switches.extend([WyzeCameraMotionSwitch(camera_service, switch)])

    switches.append(WyzeNotifications(client))

    bulb_switches = await bulb_service.get_bulbs()
    for bulb in bulb_switches:
        if bulb.type is DeviceTypes.LIGHTSTRIP:
            switches.extend([WzyeLightstripSwitch(bulb_service, bulb)])

    async_add_entities(switches, True)


class WyzeNotifications(SwitchEntity):
    def __init__(self, client: Wyzeapy):
        self._client = client
        self._is_on = False
        self._uid = WYZE_NOTIFICATION_TOGGLE
        self._just_updated = False

    @property
    def is_on(self) -> bool:
        return self._is_on

    def turn_on(self, **kwargs: Any) -> None:
        pass

    def turn_off(self, **kwargs: Any) -> None:
        pass

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._uid)},
            "name": "Wyze Notifications",
            "manufacturer": "WyzeLabs",
            "model": "WyzeNotificationToggle",
        }

    @property
    def should_poll(self) -> bool:
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
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
    def name(self):
        """Return the display name of this switch."""
        return "Wyze Notifications"

    @property
    def available(self):
        """Return the connection status of this switch"""
        return True

    @property
    def unique_id(self):
        return self._uid

    async def async_update(self):
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

    def __init__(self, service: Union[CameraService, SwitchService], device: Device):
        """Initialize a Wyze Bulb."""
        self._device = device
        self._service = service

        if type(self._device) is Camera:
            self._device = Camera(self._device.raw_dict)
        elif type(self._device) is Switch:
            self._device = Switch(self._device.raw_dict)

    @property
    def device_info(self):
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

    @property
    def should_poll(self) -> bool:
        return False

    @token_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
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
        else:
            return self._device.nickname

    @property
    def available(self):
        """Return the connection status of this switch"""
        return self._device.available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device.on

    @property
    def unique_id(self):
        return "{}-switch".format(self._device.mac)

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
        self._service.unregister_updater(self._device)


class WyzeCameraNotificationSwitch(SwitchEntity):
    """Representation of a Wyze Camera Notification Switch."""

    _available: bool

    def __init__(self, service: CameraService, device: Camera):
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
        return "{}-notification_switch".format(self._device.mac)

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
        return "{}-motion_switch".format(self._device.mac)

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
        return "{}-music_mode".format(self._device.mac)

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
