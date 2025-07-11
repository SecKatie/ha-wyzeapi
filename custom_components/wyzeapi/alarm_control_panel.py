"""
This module handles the Wyze Home Monitoring system
"""

import logging
from datetime import timedelta
from typing import Optional, Callable, List, Any
from aiohttp.client_exceptions import ClientConnectionError

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelState,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from wyzeapy import Wyzeapy, HMSService
from wyzeapy.services.hms_service import HMSMode
from wyzeapy.exceptions import AccessTokenError, ParameterError, UnknownApiError
from .token_manager import token_exception_handler
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_CLIENT

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=15)


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Any], bool], None],
):
    """
    This function sets up the integration

    :param hass: Reference to the HomeAssistant instance
    :param config_entry: Reference to the config entry we are setting up
    :param async_add_entities:
    """

    _LOGGER.debug("""Creating new WyzeApi Home Monitoring System component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]

    hms_service = await client.hms_service
    if await hms_service.has_hms:
        async_add_entities([WyzeHomeMonitoring(hms_service)], True)


class WyzeHomeMonitoring(AlarmControlPanelEntity):
    """
    A representation of the Wyze Home Monitoring system that works for wyze
    """

    DEVICE_MODEL = "HMS"
    MANUFACTURER = "WyzeLabs"
    NAME = "Wyze Home Monitoring System"
    AVAILABLE = True
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, hms_service: HMSService):
        self._attr_unique_id = hms_service.hms_id

        self._hms_service = hms_service
        self._state = AlarmControlPanelState.DISARMED
        self._server_out_of_sync = False

    @property
    def alarm_state(self) -> str:
        return self._state

    # NotImplemented Methods
    def alarm_arm_vacation(self, code: Optional[str] = None) -> None:
        raise NotImplementedError

    def alarm_arm_night(self, code: Optional[str] = None) -> None:
        raise NotImplementedError

    def alarm_trigger(self, code: Optional[str] = None) -> None:
        raise NotImplementedError

    def alarm_arm_custom_bypass(self, code: Optional[str] = None) -> None:
        raise NotImplementedError

    # Implemented Methods
    @token_exception_handler
    async def async_alarm_disarm(self, code: Optional[str] = None) -> None:
        """Send disarm command."""
        try:
            await self._hms_service.set_mode(HMSMode.DISARMED)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._state = "disarmed"
            self._server_out_of_sync = True

    @token_exception_handler
    async def async_alarm_arm_home(self, code: Optional[str] = None) -> None:
        try:
            await self._hms_service.set_mode(HMSMode.HOME)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._state = "armed_home"
            self._server_out_of_sync = True

    @token_exception_handler
    async def async_alarm_arm_away(self, code: Optional[str] = None) -> None:
        try:
            await self._hms_service.set_mode(HMSMode.AWAY)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._state = "armed_away"
            self._server_out_of_sync = True

    @property
    def supported_features(self) -> int:
        return (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.NAME,
            manufacturer=self.MANUFACTURER,
            model=self.DEVICE_MODEL,
        )

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return device attributes of the entity."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION, "mac": self.unique_id}

    @token_exception_handler
    async def async_update(self) -> None:
        """Update the entity with data from the Wyze servers"""

        if not self._server_out_of_sync:
            state = await self._hms_service.update(self._hms_service.hms_id)
            if state is HMSMode.DISARMED:
                self._state = AlarmControlPanelState.DISARMED
            elif state is HMSMode.AWAY:
                self._state = AlarmControlPanelState.ARMED_AWAY
            elif state is HMSMode.HOME:
                self._state = AlarmControlPanelState.ARMED_HOME
            elif state is HMSMode.CHANGING:
                self._state = AlarmControlPanelState.DISARMED
            else:
                _LOGGER.warning(f"Received {state} from server")

        self._server_out_of_sync = False
