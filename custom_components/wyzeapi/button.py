#!/usr/bin/python3

"""Platform for button integration."""
import logging
from typing import Any, Callable, List
from aiohttp.client_exceptions import ClientConnectionError

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send, async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr
from wyzeapy import Wyzeapy
from wyzeapy.services.irrigation_service import IrrigationService, IrrigationDevice, Zone
from wyzeapy.types import Device, Event, DeviceTypes

from .const import DOMAIN, CONF_CLIENT
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
    This function sets up the config entry

    :param hass: The Home Assistant Instance
    :param config_entry: The current config entry
    :param async_add_entities: This function adds entities to the config entry
    :return:
    """

    _LOGGER.debug("""Creating new WyzeApi irrigation button component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    irrigation_service = await client.irrigation_service

    # Get all irrigation devices
    irrigation_devices = await irrigation_service.get_irrigations()
    
    # Create a button entity for each zone in each irrigation device
    buttons = []
    for device in irrigation_devices:
        # Update the device to get its zones
        device = await irrigation_service.update(device)
        for zone in device.zones:
            buttons.append(WyzeIrrigationZoneButton(irrigation_service, device, zone))

    async_add_entities(buttons, True)


class WyzeIrrigationZoneButton(ButtonEntity):
    """Representation of a Wyze Irrigation Zone Button."""

    def __init__(self, irrigation_service: IrrigationService, irrigation: IrrigationDevice, zone: Zone) -> None:
        """Initialize the irrigation zone button."""
        self._irrigation_service = irrigation_service
        self._irrigation = irrigation
        self._zone = zone

    @property
    def name(self) -> str:
        """Return the name of the zone."""
        return f"{self._irrigation.nickname} - {self._zone.name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the zone."""
        return f"{self._irrigation.mac}-zone-{self._zone.zone_number}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._irrigation.mac)},
            name=self._irrigation.nickname,
            manufacturer="WyzeLabs",
            model=self._irrigation.product_model,
            connections={(dr.CONNECTION_NETWORK_MAC, self._device.mac)},
        )

    @property
    def device_class(self) -> str:
        """Return the device class of the button."""
        return ButtonDeviceClass.RESTART

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "zone_number": self._zone.zone_number,
            "zone_id": self._zone.zone_id,
            "enabled": self._zone.enabled,
            "quickrun_duration": self._zone.quickrun_duration,
        }

    async def async_press(self) -> None:
        """Start the zone with its quickrun duration.
        
        This method is called when the button is pressed in Home Assistant.
        It will start the irrigation zone for the configured quickrun duration.
        
        Raises:
            HomeAssistantError: If the zone cannot be started.
        """
        try:
            await self._irrigation_service.start_zone(
                self._irrigation,
                self._zone.zone_number,
                self._zone.quickrun_duration
            )
        except ClientConnectionError as err:
            raise HomeAssistantError(f"Failed to start zone: {err}") from err
        except Exception as err:
            _LOGGER.error("Error starting zone: %s", err)
            raise HomeAssistantError(f"Failed to start zone: {err}") from err

    @callback
    def async_update_callback(self, irrigation: IrrigationDevice) -> None:
        """Update the button's state."""
        self._irrigation = irrigation
        # Find the updated zone
        for zone in irrigation.zones:
            if zone.zone_number == self._zone.zone_number:
                self._zone = zone
                break
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self._irrigation.callback_function = self.async_update_callback
        self._irrigation_service.register_updater(self._irrigation, 30)
        await self._irrigation_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed."""
        self._irrigation_service.unregister_updater(self._irrigation) 