"""Platform for button integration."""

import logging
from typing import Any, Callable, List
from aiohttp.client_exceptions import ClientConnectionError

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr
from wyzeapy import Wyzeapy
from wyzeapy.services.irrigation_service import IrrigationService, Irrigation, Zone
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
            if zone.enabled:
                buttons.append(WyzeIrrigationZoneButton(irrigation_service, device, zone))
        # Add a stop all schedules button for each irrigation device, not each zone
        buttons.append(WyzeIrrigationStopAllButton(irrigation_service, device))

    async_add_entities(buttons, True)


class WyzeIrrigationZoneButton(ButtonEntity):
    """Representation of a Wyze Irrigation Zone Button."""

    def __init__(self, irrigation_service: IrrigationService, irrigation: Irrigation, zone: Zone) -> None:
        """Initialize the irrigation zone button."""
        self._irrigation_service = irrigation_service
        self._device = irrigation
        self._zone = zone

    @property
    def name(self) -> str:
        """Return the name of the zone."""
        return f"{self._zone.name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the zone."""
        return f"Start {self._device.mac}-zone-{self._zone.zone_number}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.mac)},
            name=self._device.nickname,
            manufacturer="WyzeLabs",
            model=self._device.product_model,
            connections={(dr.CONNECTION_NETWORK_MAC, self._device.mac)},
        )

    @property
    def device_class(self) -> str:
        """Return the device class of the button."""
        return ButtonDeviceClass.RESTART

    @property
    def icon(self) -> str:
        """Return the icon for the zone start button."""
        return "mdi:sprinkler"

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
            # This quickduration field doesnt exist in the Wyze API
            # It has been created in Home Assistant as a number entity
            # to conveniently trigger a zone start with a specific duration
        
            # Get the number entity ID for this zone's quickrun duration
            # Convert to lowercase, replace spaces and special chars with underscores, remove any non-alphanumeric chars
            sanitized_name = ''.join(c if c.isalnum() else '_' for c in self._zone.name.lower())
            # Remove consecutive underscores and ensure it starts with a letter
            sanitized_name = '_'.join(filter(None, sanitized_name.split('_')))
            if not sanitized_name[0].isalpha():
                sanitized_name = 'zone_' + sanitized_name
            number_entity_id = f"number.{sanitized_name}"
            
            # Get the current state of the number entity
            state = self.hass.states.get(number_entity_id)
            if state is None:
                raise HomeAssistantError(f"Could not find number entity {number_entity_id}")
            
            # Get the duration value from the state
            duration = int(float(state.state))
            
            await self._irrigation_service.start_zone(
                self._device,
                self._zone.zone_number,
                duration
            )
        except ClientConnectionError as err:
            raise HomeAssistantError(f"Failed to start zone: {err}") from err
        except Exception as err:
            _LOGGER.error("Error starting zone: %s", err)
            raise HomeAssistantError(f"Failed to start zone: {err}") from err


class WyzeIrrigationStopAllButton(ButtonEntity):
    """Representation of a Wyze Irrigation Stop All Schedules Button."""

    def __init__(self, irrigation_service: IrrigationService, irrigation: Irrigation) -> None:
        """Initialize the irrigation stop all button."""
        self._irrigation_service = irrigation_service
        self._device = irrigation

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return f"Stop All Zones"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the button."""
        return f"Stop All {self._device.mac}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.mac)},
            name=self._device.nickname,
            manufacturer="WyzeLabs",
            model=self._device.product_model,
            serial_number=self._device.sn,
            connections={(dr.CONNECTION_NETWORK_MAC, self._device.mac)},
        )

    @property
    def device_class(self) -> str:
        """Return the device class of the button."""
        return ButtonDeviceClass.RESTART

    @property
    def icon(self) -> str:
        """Return the icon for the stop allbutton."""
        return "mdi:octagon"

    async def async_press(self) -> None:
        """Stop all running irrigation schedules.
        
        This method is called when the button is pressed in Home Assistant.
        It will stop all running irrigation schedules for the device.
        
        Raises:
            HomeAssistantError: If the schedules cannot be stopped.
        """
        try:
            await self._irrigation_service.stop_running_schedule(self._device)
        except ClientConnectionError as err:
            raise HomeAssistantError(f"Failed to stop schedules: {err}") from err
        except Exception as err:
            _LOGGER.error("Error stopping schedules: %s", err)
            raise HomeAssistantError(f"Failed to stop schedules: {err}") from err
