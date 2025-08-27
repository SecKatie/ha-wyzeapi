"""Platform for the cover integration."""

from abc import ABC
import logging
from typing import Any, Callable, List

from wyzeapy import Wyzeapy, CameraService # type: ignore
from wyzeapy.services.camera_service import Camera # type: ignore
from wyzeapy.exceptions import AccessTokenError, ParameterError, UnknownApiError # type: ignore
from wyzeapy.types import DeviceTypes # type: ignore

import homeassistant.components.cover
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.cover import CoverDeviceClass, CoverEntityFeature


from .const import CAMERA_UPDATED, CONF_CLIENT, DOMAIN
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Any], bool], None],
) -> None:
    """
    This function sets up the config_entry

    :param hass: Home Assistant instance
    :param config_entry: The current config_entry
    :param async_add_entities: This function adds entities to the config_entry
    :return:
    """

    _LOGGER.debug("""Creating new WyzeApi cover component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    camera_service = await client.camera_service
    cameras: List[Camera] = await camera_service.get_cameras()
    garages = []
    for camera in cameras:
        if camera.device_params["dongle_product_model"] == "HL_CGDC":
            garages.append(WyzeGarageDoor(camera_service, camera))

    async_add_entities(garages, True)


class WyzeGarageDoor(homeassistant.components.cover.CoverEntity, ABC):
    """Representation of a Wyze Garage Door."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_has_entity_name = True

    def __init__(self, camera_service: CameraService, camera: Camera):
        """Initialize a Wyze garage door."""
        self._camera = camera
        if self._camera.type not in [DeviceTypes.CAMERA]:
            raise HomeAssistantError(f"Invalid device type: {self._camera.type}")

        self._camera_service = camera_service
        self._available = self._camera.available

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._camera.mac)},
            "name": f"{self._camera.nickname}",
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._camera.mac)},
        }

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device model": f"{self._camera.product_model}.{self._camera.device_params['dongle_product_model']}",
        }

    @property
    def should_poll(self) -> bool:
        return False

    @token_exception_handler
    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        try:
            await self._camera_service.garage_door_open(self._camera)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except Exception as err:
            raise HomeAssistantError(err) from err
        else:
            self._camera.garage = True
            self.async_write_ha_state()

    @token_exception_handler
    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        try:
            await self._camera_service.garage_door_close(self._camera)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except Exception as err:
            raise HomeAssistantError(err) from err
        else:
            self._camera.garage = False
            self.async_write_ha_state()

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return not self._camera.garage

    @property
    def available(self):
        """Return the connection status of this cover."""
        return self._camera.available

    @property
    def unique_id(self):
        """Define a unique id for this entity."""
        return f"{self._camera.mac}_GarageDoor"

    @property
    def name(self):
        """Return the name of the garage door."""
        return "Garage Door"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{CAMERA_UPDATED}-{self._camera.mac}",
                self.handle_camera_update,
            )
        )

    @callback
    def handle_camera_update(self, camera: Camera) -> None:
        """Update the cover whenever there is an update"""
        self._camera = camera
        self.async_write_ha_state()
