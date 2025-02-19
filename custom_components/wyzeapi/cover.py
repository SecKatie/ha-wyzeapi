"""Platform for the cover integration."""

from abc import ABC
from datetime import timedelta
import logging
from typing import Any, Callable, List

from wyzeapy import Wyzeapy, CameraService
from wyzeapy.services.camera_service import Camera
from wyzeapy.exceptions import AccessTokenError, ParameterError, UnknownApiError
from wyzeapy.types import DeviceTypes

import homeassistant.components.cover   
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.cover import CoverDeviceClass, CoverEntityFeature


from .const import CONF_CLIENT, DOMAIN, COVER_UPDATED
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=10)
MAX_OUT_OF_SYNC_COUNT = 5


@token_exception_handler
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities: Callable[[List[Any], bool], None]) -> None:
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
    _attr_supported_features = (
        CoverEntityFeature.OPEN,
        CoverEntityFeature.CLOSE
    )
    _attr_has_entity_name = True


    def __init__(self, camera_service: CameraService, camera: Camera):
        """Initialize a Wyze garage door."""
        self._camera = camera
        if self._camera.type not in [
            DeviceTypes.CAMERA
        ]:
            raise HomeAssistantError(f"Invalid device type: {self._camera.type}")
        
        self._camera_service = camera_service
        self._available = self._camera.available
        self._out_of_sync_count = 0
        
    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._camera.mac)},
            "name": f"{self._camera.nickname}.cgdc",
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._camera.mac
                )
            }
        }
    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device model": f"{self._camera.product_model}.{self._camera.device_params['dongle_product_model']}"
        }
    @property
    def entity_registry_enabled_default(self) -> bool:
        # always true because garage controllers are always connected to the cam
        return True
    
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
            self._out_of_sync_count = 0
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
            self._out_of_sync_count = 0
            self.async_write_ha_state()

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._camera.garage == False
        
    @property
    def available(self):
        """Return the connection status of this cover."""
        return self._camera.available
    
    @property
    def supported_features(self):
        """Flag supported features."""
        return CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
                
    @property
    def unique_id(self):
        return f"{self._camera.mac}_GarageDoor"
    @property
    def name(self):
        return "Garage Door"
    
    @token_exception_handler
    async def async_update(self):
        """Update the garage door status."""
        camera = await self._camera_service.update(self._camera)

        if camera.garage == self._camera.garage or MAX_OUT_OF_SYNC_COUNT <= self._out_of_sync_count:
            self._out_of_sync_count = 0
            self._camera = camera
        else:
            self._out_of_sync_count += 1

    @callback
    def async_update_callback(self, camera: Camera):
        """Update the switch's state."""
        self._camera = camera
        async_dispatcher_send(
            self.hass,
            f"{COVER_UPDATED}-{self._camera.mac}",
            garage,
        )
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to update events."""
        self._camera.callback_function = self.async_update_callback
        self._camera_service.register_updater(self._camera, 10)
        await self._camera_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        self._camera_service.unregister_updater(self._camera)