"""Platform for light integration."""
import logging
# Import the device class from the component that you want to support
from datetime import timedelta
from typing import List, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE
)
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_OFF,
    FAN_AUTO,
    FAN_ON,
    PRESET_HOME,
    PRESET_AWAY,
    PRESET_SLEEP,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_OFF
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, TEMP_FAHRENHEIT, TEMP_CELSIUS
from homeassistant.core import HomeAssistant

from wyzeapy.client import Client
from wyzeapy.types import ThermostatProps
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("""Creating new WyzeApi thermostat component""")
    client: Client = hass.data[DOMAIN][config_entry.entry_id]

    thermostats = [WyzeThermostat(client, thermostat) for thermostat in
                   await client.get_thermostats()]

    async_add_entities(thermostats, True)


class WyzeThermostat(ClimateEntity):
    _server_out_of_sync = False
    _available = False
    _temp_unit: str = "F"
    _cool_sp: int
    _heat_sp: int
    _fan_mode: str
    _hvac_mode: str
    _preset_mode: str
    _temperature: int
    _humidity: int
    _working_state: str

    def __init__(self, client: Client, device):
        self._client = client
        self._device = device

    @property
    def current_temperature(self) -> float:
        return float(self._temperature)

    @property
    def current_humidity(self) -> Optional[int]:
        return int(self._humidity)

    @property
    def temperature_unit(self) -> str:
        if self._temp_unit == "F":
            return TEMP_FAHRENHEIT

        return TEMP_CELSIUS

    @property
    def hvac_mode(self) -> str:
        if self._hvac_mode == "auto":
            return HVAC_MODE_AUTO
        elif self._hvac_mode == "heat":
            return HVAC_MODE_HEAT
        elif self._hvac_mode == "cool":
            return HVAC_MODE_COOL
        else:
            return HVAC_MODE_OFF

    @property
    def hvac_modes(self) -> List[str]:
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF]

    @property
    def target_temperature_high(self) -> Optional[float]:
        return float(self._cool_sp)

    @property
    def target_temperature_low(self) -> Optional[float]:
        return float(self._heat_sp)

    @property
    def preset_mode(self) -> Optional[str]:
        if self._preset_mode == "home":
            return PRESET_HOME
        elif self._preset_mode == "away":
            return PRESET_AWAY
        else:
            return PRESET_SLEEP

    @property
    def preset_modes(self) -> Optional[List[str]]:
        return [PRESET_HOME, PRESET_AWAY, PRESET_SLEEP]

    @property
    def is_aux_heat(self) -> Optional[bool]:
        raise NotImplementedError

    @property
    def fan_mode(self) -> Optional[str]:
        if self._fan_mode == "auto":
            return FAN_AUTO
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
        if self._working_state == "idle":
            return CURRENT_HVAC_IDLE
        elif self._working_state == "heating":
            return CURRENT_HVAC_HEAT
        elif self._working_state == "cooling":
            return CURRENT_HVAC_COOL
        else:
            return CURRENT_HVAC_OFF

    async def async_set_temperature(self, **kwargs) -> None:
        target_temp_low = kwargs['target_temp_low']
        target_temp_high = kwargs['target_temp_high']

        if target_temp_low != self._heat_sp:
            await self._client.set_thermostat_prop(self._device, ThermostatProps.HEAT_SP, int(target_temp_low))
            self._heat_sp = int(target_temp_low)
        if target_temp_high != self._cool_sp:
            self._cool_sp = int(target_temp_high)
            await self._client.set_thermostat_prop(self._device, ThermostatProps.COOL_SP, int(target_temp_high))

        self._server_out_of_sync = True

    async def async_set_humidity(self, humidity: int) -> None:
        raise NotImplementedError

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        if fan_mode == FAN_ON:
            await self._client.set_thermostat_prop(self._device, ThermostatProps.FAN_MODE, "on")
        elif fan_mode == FAN_AUTO:
            await self._client.set_thermostat_prop(self._device, ThermostatProps.FAN_MODE, "auto")

        self._fan_mode = fan_mode
        self._server_out_of_sync = True

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        if hvac_mode == HVAC_MODE_OFF:
            await self._client.set_thermostat_prop(self._device, ThermostatProps.MODE_SYS, "off")
        elif hvac_mode == HVAC_MODE_HEAT:
            await self._client.set_thermostat_prop(self._device, ThermostatProps.MODE_SYS, "heat")
        elif hvac_mode == HVAC_MODE_COOL:
            await self._client.set_thermostat_prop(self._device, ThermostatProps.MODE_SYS, "cool")
        elif hvac_mode == HVAC_MODE_AUTO:
            await self._client.set_thermostat_prop(self._device, ThermostatProps.MODE_SYS, "auto")

        self._hvac_mode = hvac_mode
        self._server_out_of_sync = True

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        raise NotImplementedError

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_SLEEP:
            await self._client.set_thermostat_prop(self._device, ThermostatProps.CONFIG_SCENARIO, "sleep")
        elif preset_mode == PRESET_AWAY:
            await self._client.set_thermostat_prop(self._device, ThermostatProps.CONFIG_SCENARIO, "away")
        elif preset_mode == PRESET_HOME:
            await self._client.set_thermostat_prop(self._device, ThermostatProps.CONFIG_SCENARIO, "home")

        self._preset_mode = preset_mode
        self._server_out_of_sync = True

    async def async_turn_aux_heat_on(self) -> None:
        raise NotImplementedError

    async def async_turn_aux_heat_off(self) -> None:
        raise NotImplementedError

    @property
    def supported_features(self) -> int:
        return SUPPORT_TARGET_TEMPERATURE_RANGE | SUPPORT_FAN_MODE | \
               SUPPORT_PRESET_MODE

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {
                (DOMAIN, self._device.mac)
            },
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model
        }

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def name(self) -> str:
        """Return the display name of this lock."""
        return self._device.nickname

    @property
    def unique_id(self) -> str:
        return self._device.mac

    @property
    def available(self) -> bool:
        """Return the connection status of this light"""
        return self._available

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.state,
            "available": self.available,
            "device_model": self._device.product_model,
            "mac": self.unique_id
        }

    async def async_update(self):
        if not self._server_out_of_sync:
            thermostat_props = await self._client.get_thermostat_info(self._device)

            for prop, value in thermostat_props:
                if prop == ThermostatProps.TEMP_UNIT:
                    self._temp_unit = value
                elif prop == ThermostatProps.COOL_SP:
                    self._cool_sp = value
                elif prop == ThermostatProps.HEAT_SP:
                    self._heat_sp = value
                elif prop == ThermostatProps.FAN_MODE:
                    self._fan_mode = value
                elif prop == ThermostatProps.MODE_SYS:
                    self._hvac_mode = value
                elif prop == ThermostatProps.CONFIG_SCENARIO:
                    self._preset_mode = value
                elif prop == ThermostatProps.TEMPERATURE:
                    self._temperature = value
                elif prop == ThermostatProps.IOT_STATE:
                    self._available = False if value != 'connected' else True
                elif prop == ThermostatProps.HUMIDITY:
                    self._humidity = value
                elif prop == ThermostatProps.WORKING_STATE:
                    self._working_state = value
        else:
            self._server_out_of_sync = False
