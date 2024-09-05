"""Platform for light integration."""
import logging
# Import the device class from the component that you want to support
from datetime import timedelta
from typing import List, Optional, Callable, Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_ON,
    PRESET_HOME,
    PRESET_AWAY,
    PRESET_SLEEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from wyzeapy import Wyzeapy, ThermostatService
from wyzeapy.exceptions import AccessTokenError, ParameterError, UnknownApiError
from wyzeapy.services.thermostat_service import Thermostat, TemperatureUnit, Preset, FanMode, HVACState, HVACMode as WyzeHVACMode
from .token_manager import token_exception_handler

from .const import DOMAIN, CONF_CLIENT

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=30)


@token_exception_handler
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities: Callable[[List[Any], bool], None]):
    """
    This function sets up the config entry so that it is available to Home Assistant

    :param hass: The Home Assistant instance
    :param config_entry: The current config entry
    :param async_add_entities: A function to add entities
    :return:
    """

    _LOGGER.debug("""Creating new WyzeApi thermostat component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]

    thermostat_service = await client.thermostat_service
    thermostats = [WyzeThermostat(thermostat_service, thermostat) for thermostat in
                   await thermostat_service.get_thermostats()]

    async_add_entities(thermostats, True)


class WyzeThermostat(ClimateEntity):
    """
    This class defines a representation of a Wyze Thermostat that can be used for Home Assistant
    """

    # pylint: disable=R0902
    _server_out_of_sync = False

    def __init__(self, thermostat_service: ThermostatService, thermostat: Thermostat):
        self._thermostat_service = thermostat_service
        self._thermostat = thermostat

    def set_temperature(self, **kwargs) -> None:
        raise NotImplementedError

    def set_humidity(self, humidity: int) -> None:
        raise NotImplementedError

    def set_fan_mode(self, fan_mode: str) -> None:
        raise NotImplementedError

    def set_hvac_mode(self, hvac_mode: str) -> None:
        raise NotImplementedError

    def set_swing_mode(self, swing_mode: str) -> None:
        raise NotImplementedError

    def set_preset_mode(self, preset_mode: str) -> None:
        raise NotImplementedError

    def turn_aux_heat_on(self) -> None:
        raise NotImplementedError

    def turn_aux_heat_off(self) -> None:
        raise NotImplementedError

    @property
    def current_temperature(self) -> float:
        return self._thermostat.temperature

    @property
    def current_humidity(self) -> Optional[int]:
        return self._thermostat.humidity

    @property
    def temperature_unit(self) -> str:
        #if self._thermostat.temp_unit == TemperatureUnit.FAHRENHEIT:
        return UnitOfTemperature.FAHRENHEIT
        #return TEMP_CELSIUS

    @property
    def unit_of_measurement(self) -> str:
        if self._thermostat.temp_unit == TemperatureUnit.FAHRENHEIT:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_mode(self) -> str:
        # pylint: disable=R1705
        if self._thermostat.hvac_mode == WyzeHVACMode.AUTO:
            return HVACMode.AUTO
        elif self._thermostat.hvac_mode == WyzeHVACMode.HEAT:
            return HVACMode.HEAT
        elif self._thermostat.hvac_mode == WyzeHVACMode.COOL:
            return HVACMode.COOL
        else:
            return HVACMode.OFF

    @property
    def hvac_modes(self) -> List[str]:
        return [HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]

    @property
    def target_temperature_high(self) -> Optional[float]:
        return self._thermostat.cool_set_point

    @property
    def target_temperature_low(self) -> Optional[float]:
        return self._thermostat.heat_set_point

    @property
    def preset_mode(self) -> Optional[str]:
        match self._thermostat.preset:
            case Preset.HOME:
                return PRESET_HOME
            case Preset.AWAY:
                return PRESET_AWAY
            case Preset.SLEEP:
                return PRESET_SLEEP
            case _:
                raise NotImplementedError

    @property
    def preset_modes(self) -> Optional[List[str]]:
        return [PRESET_HOME, PRESET_AWAY, PRESET_SLEEP]

    @property
    def is_aux_heat(self) -> Optional[bool]:
        raise NotImplementedError

    @property
    def fan_mode(self) -> Optional[str]:
        if self._thermostat.fan_mode == FanMode.AUTO:
            return FAN_AUTO
        else:
            return FAN_ON

    @property
    def fan_modes(self) -> Optional[List[str]]:
        return [FAN_AUTO, FAN_ON]

    @property
    def swing_mode(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def swing_modes(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def hvac_action(self) -> str:
        # pylint: disable=R1705
        if self._thermostat.hvac_state == HVACState.IDLE:
            return HVACAction.IDLE
        elif self._thermostat.hvac_state == HVACState.HEATING:
            return HVACAction.HEATING
        elif self._thermostat.hvac_state == HVACState.COOLING:
            return HVACAction.COOLING
        else:
            return HVACAction.OFF

    @token_exception_handler
    async def async_set_temperature(self, **kwargs) -> None:
        target_temp_low = kwargs['target_temp_low']
        target_temp_high = kwargs['target_temp_high']

        try:
            if target_temp_low != self._thermostat.heat_set_point:
                await self._thermostat_service.set_heat_point(self._thermostat, int(target_temp_low))
                self._thermostat.heat_set_point = int(target_temp_low)
            if target_temp_high != self._thermostat.cool_set_point:
                await self._thermostat_service.set_cool_point(self._thermostat, int(target_temp_high))
                self._thermostat.cool_set_point = int(target_temp_high)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        else:
            self._server_out_of_sync = True
            self.async_schedule_update_ha_state()

    async def async_set_humidity(self, humidity: int) -> None:
        raise NotImplementedError

    @token_exception_handler
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        try:
            if fan_mode == FAN_ON:
                await self._thermostat_service.set_fan_mode(self._thermostat, FanMode.ON)
                self._thermostat.fan_mode = FanMode.ON
            elif fan_mode == FAN_AUTO:
                await self._thermostat_service.set_fan_mode(self._thermostat, FanMode.AUTO)
                self._thermostat.fan_mode = FanMode.AUTO
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        else:
            self._server_out_of_sync = True
            self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        try:
            if hvac_mode == HVACMode.OFF:
                await self._thermostat_service.set_hvac_mode(self._thermostat, WyzeHVACMode.OFF)
                self._thermostat.hvac_mode = HVACMode.OFF
            elif hvac_mode == HVACMode.HEAT:
                await self._thermostat_service.set_hvac_mode(self._thermostat, WyzeHVACMode.HEAT)
                self._thermostat.hvac_mode = HVACMode.HEAT
            elif hvac_mode == HVACMode.COOL:
                await self._thermostat_service.set_hvac_mode(self._thermostat, WyzeHVACMode.COOL)
                self._thermostat.hvac_mode = HVACMode.COOL
            elif hvac_mode == HVACMode.AUTO:
                await self._thermostat_service.set_hvac_mode(self._thermostat, WyzeHVACMode.AUTO)
                self._thermostat.hvac_mode = HVACMode.AUTO
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        else:
            self._server_out_of_sync = True
            self.async_schedule_update_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        raise NotImplementedError

    @token_exception_handler
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        try:
            if preset_mode == PRESET_SLEEP:
                await self._thermostat_service.set_preset(self._thermostat, Preset.SLEEP)
                self._thermostat.preset = Preset.SLEEP
            elif preset_mode == PRESET_AWAY:
                await self._thermostat_service.set_preset(self._thermostat, Preset.AWAY)
                self._thermostat.preset = Preset.AWAY
            elif preset_mode == PRESET_HOME:
                await self._thermostat_service.set_preset(self._thermostat, Preset.HOME)
                self._thermostat.preset = Preset.HOME
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        else:
            self._server_out_of_sync = True
            self.async_schedule_update_ha_state()

    async def async_turn_aux_heat_on(self) -> None:
        raise NotImplementedError

    async def async_turn_aux_heat_off(self) -> None:
        raise NotImplementedError

    @property
    def supported_features(self) -> int:
        return ClimateEntityFeature.TARGET_TEMPERATURE_RANGE | ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.PRESET_MODE

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {
                (DOMAIN, self._thermostat.mac)
            },
            "name": self._thermostat.nickname,
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._thermostat.mac,
                )
            },
            "manufacturer": "WyzeLabs",
            "model": self._thermostat.product_model
        }

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def name(self) -> str:
        """Return the display name of this lock."""
        return self._thermostat.nickname

    @property
    def unique_id(self) -> str:
        return self._thermostat.mac

    @property
    def available(self) -> bool:
        """Return the connection status of this light"""
        return self._thermostat.available

    @token_exception_handler
    async def async_update(self) -> None:
        """
        This function updates the state of the Thermostat

        :return: None
        """

        if not self._server_out_of_sync:
            self._thermostat = await self._thermostat_service.update(self._thermostat)
        else:
            self._server_out_of_sync = False

    @callback
    def async_update_callback(self, thermostat: Thermostat):
        """Update the thermostat's state."""
        self._thermostat = thermostat
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to update events."""
        self._thermostat.callback_function = self.async_update_callback
        self._thermostat_service.register_updater(self._thermostat, 30)
        await self._thermostat_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        self._thermostat_service.unregister_updater(self._thermostat)
