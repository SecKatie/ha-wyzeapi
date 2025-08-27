"""Platform for number integration."""

import logging
from typing import Any, Callable, List

from homeassistant.components.number import RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr
from wyzeapy import Wyzeapy
from wyzeapy.services.irrigation_service import IrrigationService, Irrigation, Zone

from .const import DOMAIN, CONF_CLIENT
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)

@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Any], bool], None],
) -> None:
    """Set up the WyzeApi number platform."""
    _LOGGER.debug("Creating new WyzeApi number component")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    irrigation_service = await client.irrigation_service

    # Get all irrigation devices
    irrigation_devices = await irrigation_service.get_irrigations()
    
    # Create a number entity for each zone in each irrigation device
    entities = []
    for device in irrigation_devices:
        # Update the device to get its zones
        device = await irrigation_service.update(device)
        for zone in device.zones:
            if zone.enabled:
                entities.append(WyzeIrrigationQuickrunDuration(irrigation_service, device, zone))

    async_add_entities(entities, True)

class WyzeIrrigationQuickrunDuration(RestoreNumber):
    """Representation of a Wyze Irrigation Zone Quickrun Duration."""

    _attr_has_entity_name = True

    def __init__(self, irrigation_service: IrrigationService, irrigation: Irrigation, zone: Zone) -> None:
        """Initialize the irrigation zone quickrun duration."""
        self._irrigation_service = irrigation_service
        self._device = irrigation
        self._zone = zone

    @property
    def name(self) -> str:
        """Return the name of the zone quickrun duration."""
        return f"{self._zone.name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the zone quickrun duration."""
        return f"{self._device.mac}-zone-{self._zone.zone_number}-quickrun-duration"

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
    def native_value(self) -> float:
        """Return the current value in minutes."""
        return float(self._zone.quickrun_duration) / 60.0

    @property
    def native_min_value(self) -> float:
        """Return the minimum value in minutes."""
        return 1.0  # 1 minute

    @property
    def native_max_value(self) -> float:
        """Return the maximum value in minutes."""
        return 180.0  # 3 hours in minutes

    @property
    def native_step(self) -> float:
        """Return the step value in minutes."""
        return 1.0  # 1 minute steps

    @property
    def mode(self) -> str:
        """Return the mode of the number entity."""
        return "box"

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "min"

    @property
    def icon(self) -> str:
        """Return the icon for the quickrun duration number."""
        return "mdi:timer"

    async def async_set_native_value(self, value: float) -> None:
        """Set the value in minutes."""
        # Convert minutes to seconds for the API
        seconds = int(value * 60)
        await self._irrigation_service.set_zone_quickrun_duration(
            self._device,
            self._zone.zone_number,
            seconds
        )
        self._zone.quickrun_duration = seconds
        self.async_write_ha_state()

    async def _async_load_value(self) -> None:
        """Load the value from Home Assistant state or update from irrigation service."""
        # Try to get the last number data from Home Assistant
        state = await self.async_get_last_number_data()
        if state and state.native_value is not None:
            try:
                # Convert minutes to seconds for storage
                self._zone.quickrun_duration = int(state.native_value * 60)
                return
            except (ValueError, TypeError):
                pass
        
        # If no valid state exists, update from irrigation service
        self._device = await self._irrigation_service.update(self._device)
        for zone in self._device.zones:
            if zone.zone_number == self._zone.zone_number:
                self._zone = zone
                break

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        await self._async_load_value()
        return await super().async_added_to_hass()
