"""Platform for light integration."""
import logging
# Import the device class from the component that you want to support
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
    PRESET_SLEEP
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, TEMP_FAHRENHEIT, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from wyzeapy.client import Client
from wyzeapy.exceptions import AccessTokenError
from wyzeapy.types import Device, DeviceTypes, ThermostatProps

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("""Creating new WyzeApi thermostat component""")
    client = hass.data[DOMAIN][config_entry.entry_id]

    def get_devices() -> List[Device]:
        try:
            devices = client.get_devices()
        except AccessTokenError as e:
            _LOGGER.warning(e)
            client.reauthenticate()
            devices = client.get_devices()

        return devices

    devices = await hass.async_add_executor_job(get_devices)

    thermostats = []
    for device in devices:
        try:
            if DeviceTypes(device.product_type) == DeviceTypes.THERMOSTAT:
                thermostats.append(WyzeThermostat(client, device))
        except ValueError as e:
            _LOGGER.warning("{}: Please report this error to https://github.com/JoshuaMulliken/ha-wyzeapi".format(e))

    async_add_entities(thermostats, True)


class WyzeThermostat(ClimateEntity):
    _just_updated = False
    _available = False
    _temp_unit: str = "F"
    _cool_sp: int
    _heat_sp: int
    _fan_mode: str
    _hvac_mode: str
    _preset_mode: str
    _temperature: int
    _humidity: int

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

    def set_temperature(self, **kwargs) -> None:
        target_temp_low = kwargs['target_temp_low']
        target_temp_high = kwargs['target_temp_high']

        if target_temp_low != self.target_temperature_low:
            self._client.set_thermostat_prop(self._device, ThermostatProps.HEAT_SP, int(target_temp_low))
            self._heat_sp = int(target_temp_low)
        if target_temp_high != self.target_temperature_high:
            self._cool_sp = int(target_temp_high)
            self._client.set_thermostat_prop(self._device, ThermostatProps.COOL_SP, int(target_temp_high))

        self._just_updated = True

    def set_humidity(self, humidity: int) -> None:
        raise NotImplementedError

    def set_fan_mode(self, fan_mode: str) -> None:
        if fan_mode == FAN_ON:
            self._client.set_thermostat_prop(self._device, ThermostatProps.FAN_MODE, "on")
        elif fan_mode == FAN_AUTO:
            self._client.set_thermostat_prop(self._device, ThermostatProps.FAN_MODE, "auto")

        self._fan_mode = fan_mode
        self._just_updated = True

    def set_hvac_mode(self, hvac_mode: str) -> None:
        if hvac_mode == HVAC_MODE_OFF:
            self._client.set_thermostat_prop(self._device, ThermostatProps.MODE_SYS, "off")
        elif hvac_mode == HVAC_MODE_HEAT:
            self._client.set_thermostat_prop(self._device, ThermostatProps.MODE_SYS, "heat")
        elif hvac_mode == HVAC_MODE_COOL:
            self._client.set_thermostat_prop(self._device, ThermostatProps.MODE_SYS, "cool")
        elif hvac_mode == HVAC_MODE_AUTO:
            self._client.set_thermostat_prop(self._device, ThermostatProps.MODE_SYS, "auto")

        self._hvac_mode = hvac_mode
        self._just_updated = True

    def set_swing_mode(self, swing_mode: str) -> None:
        raise NotImplementedError

    def set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_SLEEP:
            self._client.set_thermostat_prop(self._device, ThermostatProps.CONFIG_SCENARIO, "sleep")
        elif preset_mode == PRESET_AWAY:
            self._client.set_thermostat_prop(self._device, ThermostatProps.CONFIG_SCENARIO, "away")
        if preset_mode == PRESET_HOME:
            self._client.set_thermostat_prop(self._device, ThermostatProps.CONFIG_SCENARIO, "home")

        self._preset_mode = preset_mode
        self._just_updated = True

    def turn_aux_heat_on(self) -> None:
        raise NotImplementedError

    def turn_aux_heat_off(self) -> None:
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

    def update(self):
        _LOGGER.debug(f"Updating {self._device.nickname}")
        if not self._just_updated:
            thermostat_props = self._client.get_thermostat_info(self._device)
            _LOGGER.debug(f"Got properties for {self._device.nickname}")

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

            self._just_updated = True
        else:
            self._just_updated = False
