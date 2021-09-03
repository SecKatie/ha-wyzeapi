#!/usr/bin/python3

"""Platform for switch integration."""
import configparser
import logging
# Import the device class from the component that you want to support
import os
import uuid
from datetime import timedelta
from typing import Any, Callable, List, Union

from homeassistant.components.switch import (
    SwitchEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from wyzeapy import Wyzeapy, CameraService, SwitchService
from wyzeapy.services.camera_service import Camera
from wyzeapy.services.switch_service import Switch
from wyzeapy.types import Device

from . import DOMAIN, CONF_CLIENT

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=30)


# noinspection DuplicatedCode
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities: Callable[[List[Any], bool], None]) -> None:
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
    camera_service = await client.camera_service

    switches: List[SwitchEntity] = [WyzeSwitch(switch_service, switch) for switch in
                                    await switch_service.get_switches()]
    switches.extend([WyzeSwitch(camera_service, switch) for switch in await camera_service.get_cameras()])

    def get_uid():
        config = configparser.ConfigParser()
        config_path = hass.config.path('wyze_config.ini')
        config.read(config_path)
        if config.has_option("OPTIONS", "SYSTEM_ID"):
            return config["OPTIONS"]["SYSTEM_ID"]
        else:
            new_uid = uuid.uuid4().hex
            config["OPTIONS"] = {}
            config["OPTIONS"]["SYSTEM_ID"] = new_uid

            with open(config_path, 'w') as configfile:
                config.write(configfile)

            return new_uid

    uid = await hass.async_add_executor_job(get_uid)

    switches.append(WyzeNotifications(client, uid))

    async_add_entities(switches, True)


class WyzeNotifications(SwitchEntity):
    def __init__(self, client: Wyzeapy, uid):
        self._client = client
        self._is_on = False
        self._uid = uid
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
            "identifiers": {
                (DOMAIN, self._uid)
            },
            "name": "Wyze Notifications",
            "manufacturer": "WyzeLabs"
        }

    @property
    def should_poll(self) -> bool:
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._client.enable_notifications()

        self._is_on = True
        self._just_updated = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._client.disable_notifications()

        self._is_on = False
        self._just_updated = True

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

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "mac": self.unique_id
        }

    async def async_update(self):
        if not self._just_updated:
            self._is_on = await self._client.notifications_are_on
        else:
            self._just_updated = False


class WyzeSwitch(SwitchEntity):
    """Representation of a Wyze Switch."""

    def turn_on(self, **kwargs: Any) -> None:
        pass

    def turn_off(self, **kwargs: Any) -> None:
        pass

    _on: bool
    _available: bool
    _just_updated = False

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._service.turn_on(self._device)

        self._device.on = True
        self._just_updated = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._service.turn_off(self._device)

        self._device.on = False
        self._just_updated = True

    @property
    def name(self):
        """Return the display name of this switch."""
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
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "device model": self._device.product_model,
            "mac": self.unique_id
        }

    async def async_update(self):
        """
        This function updates the entity
        """

        if not self._just_updated:
            self._device = await self._service.update(self._device)
        else:
            self._just_updated = False
