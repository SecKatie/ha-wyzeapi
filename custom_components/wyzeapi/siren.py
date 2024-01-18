#!/usr/bin/python3

"""Platform for siren integration."""
import logging
from typing import Any, Callable

from wyzeapy import CameraService, Wyzeapy
from wyzeapy.services.camera_service import Camera

from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CAMERA_UPDATED, CONF_CLIENT, DOMAIN
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"


@token_exception_handler
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities: Callable[[list[Any], bool], None]) -> None:
    """
    This function sets up the config entry

    :param hass: The Home Assistant Instance
    :param config_entry: The current config entry
    :param async_add_entities: This function adds entities to the config entry
    :return:
    """

    _LOGGER.debug("""Creating new WyzeApi siren component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    camera_service = await client.camera_service
    sirens = []
    for camera in await camera_service.get_cameras():
        # The Campan and V2 cameras don't have a siren
        if camera.product_model not in ["WYZECP1_JEF", "WYZEC1-JZ"]:
            sirens.append(WyzeCameraSiren(camera, camera_service))

    async_add_entities(sirens, True)


class WyzeCameraSiren(SirenEntity):
    """Representation of a Wyze Camera Siren."""
    _available: bool
    _just_updated = False

    def __init__(self, camera: Camera, camera_service: CameraService) -> None:
        self._device = camera
        self._service = camera_service

        self._attr_supported_features = (
            SirenEntityFeature.TURN_OFF | SirenEntityFeature.TURN_ON
        )

    @token_exception_handler
    async def async_turn_on(self, **kwargs) -> None:
        """Turn the siren on."""
        await self._service.siren_on(self._device)

        self._device.siren = True
        self._just_updated = True
        self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_turn_off(self, **kwargs):
        """Turn the siren off."""
        await self._service.siren_off(self._device)

        self._device.siren = False
        self._just_updated = True
        self.async_schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def is_on(self):
        """Return true if siren is on."""
        return self._device.siren

    @property
    def available(self):
        """Return the connection status of this switch"""
        return self._device.available

    @property
    def name(self) -> str:
        return f"{self._device.nickname} Siren"

    @property
    def unique_id(self):
        return f"{self._device.mac}-siren"

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "device model": f"{self._device.product_model}.siren",
            "mac": self.unique_id
        }

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._device.mac)
            },
            "name": self._device.nickname,
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
