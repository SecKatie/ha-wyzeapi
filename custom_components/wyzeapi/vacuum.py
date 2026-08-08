"""Platform for robot vacuum integration."""

from collections.abc import Callable
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectionError
from wyzeapy import Wyzeapy
from wyzeapy.exceptions import ParameterError, UnknownApiError
from wyzeapy.services.vacuum_service import (
    Vacuum,
    VacuumMode,
    VacuumService,
    VacuumSuctionLevel,
)

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_CLIENT, DOMAIN
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"

FAN_SPEEDS = [level.description for level in VacuumSuctionLevel]

ACTIVITY_BY_MODE = {
    VacuumMode.IDLE: VacuumActivity.IDLE,
    VacuumMode.CLEANING: VacuumActivity.CLEANING,
    VacuumMode.SWEEPING: VacuumActivity.CLEANING,
    VacuumMode.MAPPING: VacuumActivity.CLEANING,
    VacuumMode.PAUSED: VacuumActivity.PAUSED,
    VacuumMode.MAPPING_PAUSED: VacuumActivity.PAUSED,
    VacuumMode.BREAK_POINT: VacuumActivity.PAUSED,
    VacuumMode.RETURNING_TO_CHARGE: VacuumActivity.RETURNING,
    VacuumMode.FINISHED_RETURNING_TO_CHARGE: VacuumActivity.RETURNING,
    VacuumMode.MAPPING_FINISHED_RETURNING_TO_CHARGE: VacuumActivity.RETURNING,
    VacuumMode.DOCKED_NOT_COMPLETE: VacuumActivity.DOCKED,
    VacuumMode.MAPPING_DOCKED_NOT_COMPLETE: VacuumActivity.DOCKED,
}


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Any], bool], None],
) -> None:
    """Set up Wyze robot vacuum entities."""

    _LOGGER.debug("""Creating new WyzeApi vacuum component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    vacuum_service = await client.vacuum_service

    vacuums = [
        WyzeVacuum(vacuum_service, vacuum)
        for vacuum in await vacuum_service.get_vacuums()
    ]

    async_add_entities(vacuums, True)


class WyzeVacuum(StateVacuumEntity):
    """Representation of a Wyze robot vacuum."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.STATE
    )
    _attr_fan_speed_list = FAN_SPEEDS
    _just_updated = False

    def __init__(self, vacuum_service: VacuumService, vacuum: Vacuum) -> None:
        """Initialize the vacuum."""
        self._vacuum_service = vacuum_service
        self._vacuum = vacuum
        self._attr_unique_id = f"{self._vacuum.mac}-vacuum"

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._vacuum.mac)},
            "name": self._vacuum.nickname,
            "manufacturer": "WyzeLabs",
            "model": self._vacuum.product_model,
        }

    @property
    def available(self) -> bool:
        """Return the connection status of this vacuum."""
        return self._vacuum.available

    @property
    def activity(self) -> VacuumActivity:
        """Return what the vacuum is doing.

        A recognised fault outranks the reported mode: a vacuum wedged under a
        couch keeps reporting CLEANING, so trusting the mode alone hides the one
        state the owner needs to act on. Only a recognised one, though. Wyze
        publishes a fault code on every read, and a healthy docked vacuum reports
        an undocumented non-zero code steadily; treating that as a fault would
        pin the entity to ERROR forever.
        """
        if self._vacuum.fault is not None:
            return VacuumActivity.ERROR
        if self._vacuum.charging:
            return VacuumActivity.DOCKED
        return ACTIVITY_BY_MODE.get(self._vacuum.mode, VacuumActivity.IDLE)

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum."""
        return self._vacuum.battery

    @property
    def fan_speed(self) -> str | None:
        """Return the current suction level."""
        if self._vacuum.suction_level is None:
            return None
        return self._vacuum.suction_level.description

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the consumable life and last-clean detail."""
        return {
            "fault_code": self._vacuum.fault_code,
            "fault": self._vacuum.fault.description if self._vacuum.fault else None,
            "clean_size": self._vacuum.clean_size,
            "clean_time": self._vacuum.clean_time,
            "current_map_id": self._vacuum.current_map_id,
            "filter_remaining": self._vacuum.filter_remaining,
            "side_brush_remaining": self._vacuum.side_brush_remaining,
            "main_brush_remaining": self._vacuum.main_brush_remaining,
        }

    @token_exception_handler
    async def async_start(self) -> None:
        """Start or resume a cleaning run."""
        await self._command(self._vacuum_service.sweep)

    @token_exception_handler
    async def async_pause(self) -> None:
        """Pause the cleaning run."""
        await self._command(self._vacuum_service.pause)

    @token_exception_handler
    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Send the vacuum back to its dock."""
        await self._command(self._vacuum_service.return_to_charge)

    @token_exception_handler
    async def async_stop(self, **kwargs: Any) -> None:
        """Cancel a return-to-dock, leaving the vacuum where it stands."""
        await self._command(self._vacuum_service.stop)

    @token_exception_handler
    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the suction level."""
        level = VacuumSuctionLevel.parse(fan_speed)
        if level is None:
            raise HomeAssistantError(f"Unsupported vacuum suction level: {fan_speed}")

        await self._command(self._vacuum_service.set_suction_level, level)
        self._vacuum.suction_level = level

    async def _command(self, method: Callable, *args: Any) -> None:
        """Issue a vacuum command, translating Wyze failures for the UI."""
        try:
            await method(self._vacuum, *args)
        except (ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_update(self) -> None:
        """Update the entity."""
        if not self._just_updated:
            self._vacuum = await self._vacuum_service.update(self._vacuum)
        else:
            self._just_updated = False

    @callback
    def async_update_callback(self, vacuum: Vacuum) -> None:
        """Update the vacuum state."""
        self._vacuum = vacuum
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to update events."""
        self._vacuum.callback_function = self.async_update_callback
        self._vacuum_service.register_updater(self._vacuum, 30)
        await self._vacuum_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister updater on removal."""
        self._vacuum_service.unregister_updater(self._vacuum)
