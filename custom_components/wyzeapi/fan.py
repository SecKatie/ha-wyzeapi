"""Platform for fan integration."""

from collections.abc import Callable
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectionError
from wyzeapy import Wyzeapy
from wyzeapy.exceptions import AccessTokenError, ParameterError, UnknownApiError
from wyzeapy.services.air_purifier_service import (
    AirPurifier,
    AirPurifierFanMode,
    AirPurifierService,
)

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import device_registry as dr
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import AIR_PURIFIER_UPDATED, CONF_CLIENT, DOMAIN
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"

ORDERED_NAMED_FAN_SPEEDS = [
    AirPurifierFanMode.MIN.value,
    AirPurifierFanMode.MID.value,
    AirPurifierFanMode.MAX.value,
    AirPurifierFanMode.TURBO.value,
]
PRESET_MODES = [
    AirPurifierFanMode.AUTO.value,
    AirPurifierFanMode.SLEEP.value,
]


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Any], bool], None],
) -> None:
    """Set up Wyze air purifier fan entities."""

    _LOGGER.debug("""Creating new WyzeApi fan component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    air_purifier_service = await client.air_purifier_service

    fans = [
        WyzeAirPurifierFan(air_purifier_service, air_purifier)
        for air_purifier in await air_purifier_service.get_air_purifiers()
    ]

    async_add_entities(fans, True)


class WyzeAirPurifierFan(FanEntity):
    """Representation of a Wyze Air Purifier fan."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = PRESET_MODES
    _just_updated = False

    def __init__(
        self,
        air_purifier_service: AirPurifierService,
        air_purifier: AirPurifier,
    ) -> None:
        """Initialize the air purifier fan."""
        self._air_purifier_service = air_purifier_service
        self._air_purifier = air_purifier
        self._attr_unique_id = f"{self._air_purifier.mac}-fan"

    @property
    def device_info(self):
        """Return device information about this entity."""
        device_info = {
            "identifiers": {(DOMAIN, self._air_purifier.mac)},
            "name": self._air_purifier.nickname,
            "manufacturer": "WyzeLabs",
            "model": self._air_purifier.product_model,
        }
        if self._air_purifier.app_version:
            device_info["sw_version"] = self._air_purifier.app_version
        if self._air_purifier.sn:
            device_info["serial_number"] = self._air_purifier.sn
        if self._air_purifier.wifi_mac:
            device_info["connections"] = {
                (dr.CONNECTION_NETWORK_MAC, self._air_purifier.wifi_mac)
            }
        return device_info

    @property
    def available(self) -> bool:
        """Return the connection status of this fan."""
        return self._air_purifier.available

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        return self._air_purifier.on

    @property
    def percentage(self) -> int | None:
        """Return the current fan speed percentage."""
        if not self._air_purifier.on:
            return 0
        if self._air_purifier.fan_mode in ORDERED_NAMED_FAN_SPEEDS:
            return ordered_list_item_to_percentage(
                ORDERED_NAMED_FAN_SPEEDS, self._air_purifier.fan_mode
            )
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the active fan preset mode."""
        if not self._air_purifier.on:
            return None
        if self._air_purifier.fan_mode in PRESET_MODES:
            return self._air_purifier.fan_mode
        return None

    @property
    def speed_count(self) -> int:
        """Return the number of supported speeds."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @token_exception_handler
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return

        try:
            await self._air_purifier_service.turn_on(self._air_purifier)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._air_purifier.on = True
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        try:
            await self._air_purifier_service.turn_off(self._air_purifier)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._air_purifier.on = False
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        fan_mode = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)

        try:
            if not self._air_purifier.on:
                await self._air_purifier_service.turn_on(self._air_purifier)
            await self._air_purifier_service.set_fan_mode(self._air_purifier, fan_mode)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._air_purifier.on = True
            self._air_purifier.fan_mode = fan_mode
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode not in PRESET_MODES:
            raise ValueError(f"Unsupported air purifier preset mode: {preset_mode}")

        try:
            if not self._air_purifier.on:
                await self._air_purifier_service.turn_on(self._air_purifier)
            await self._air_purifier_service.set_fan_mode(
                self._air_purifier, preset_mode
            )
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._air_purifier.on = True
            self._air_purifier.fan_mode = preset_mode
            self._just_updated = True
            self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_update(self) -> None:
        """Update the entity."""
        if not self._just_updated:
            self._air_purifier = await self._air_purifier_service.update(
                self._air_purifier
            )
        else:
            self._just_updated = False

    @callback
    def async_update_callback(self, air_purifier: AirPurifier) -> None:
        """Update the fan state."""
        self._air_purifier = air_purifier
        self._dispatch_update()
        self.async_schedule_update_ha_state()

    @callback
    def _dispatch_update(self) -> None:
        """Notify sibling air purifier entities of device updates."""
        async_dispatcher_send(
            self.hass,
            f"{AIR_PURIFIER_UPDATED}-{self._air_purifier.mac}",
            self._air_purifier,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to update events."""
        self._air_purifier.callback_function = self.async_update_callback
        self._air_purifier_service.register_updater(self._air_purifier, 30)
        await self._air_purifier_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister updater on removal."""
        self._air_purifier_service.unregister_updater(self._air_purifier)
