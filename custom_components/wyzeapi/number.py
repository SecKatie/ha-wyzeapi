"""Platform for number integration."""

import logging
from typing import Any, Callable, List

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send
)
from wyzeapy import Wyzeapy
from wyzeapy.services.irrigation_service import IrrigationService, IrrigationDevice, Zone

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
            entities.append(WyzeIrrigationQuickrunDuration(irrigation_service, device, zone))

    async_add_entities(entities, True)

class WyzeIrrigationQuickrunDuration(NumberEntity):
    """Representation of a Wyze Irrigation Zone Quickrun Duration."""

    def __init__(self, irrigation_service: IrrigationService, irrigation: IrrigationDevice, zone: Zone) -> None:
        """Initialize the irrigation zone quickrun duration."""
        self._irrigation_service = irrigation_service
        self._irrigation = irrigation
        self._zone = zone

    @property
    def name(self) -> str:
        """Return the name of the zone quickrun duration."""
        return f"{self._irrigation.nickname} - {self._zone.name} Quickrun Duration"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the zone quickrun duration."""
        return f"{self._irrigation.mac}-zone-{self._zone.zone_number}-quickrun-duration"

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
    def native_value(self) -> float:
        """Return the current value."""
        return float(self._zone.quickrun_duration)

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return 1.0

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return 3600.0  # 1 hour

    @property
    def native_step(self) -> float:
        """Return the step value."""
        return 1.0

    @property
    def mode(self) -> str:
        """Return the mode of the number entity."""
        return "box"

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "s"

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self._irrigation_service.set_zone_quickrun_duration(
            self._irrigation,
            self._zone.zone_number,
            int(value)
        )
        self._zone.quickrun_duration = int(value)
        self.async_write_ha_state()

    @callback
    def async_update_callback(self, irrigation: IrrigationDevice) -> None:
        """Update the number's state."""
        self._irrigation = irrigation
        # Find the updated zone
        for zone in irrigation.zones:
            if zone.zone_number == self._zone.zone_number:
                self._zone = zone
                break
        async_dispatcher_send(self.hass, f"{DOMAIN}-irrigation-{self._irrigation.mac}", irrigation)
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