#!/usr/bin/python3

"""Platform for switch integration."""
import asyncio
import logging
# Import the device class from the component that you want to support
from typing import Any

from homeassistant.components.switch import (
    SwitchEntity)
from homeassistant.const import ATTR_ATTRIBUTION

from . import DOMAIN
from .wyzeapi.client import WyzeApiClient
from .wyzeapi.devices import Switch

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Wyze Switch platform."""
    _LOGGER.debug("""Creating new WyzeApi switch component""")

    _ = config
    _ = discovery_info

    wyzeapi_client: WyzeApiClient = hass.data[DOMAIN]["wyzeapi_account"]

    # Add devices
    switches = await wyzeapi_client.list_switches()
    async_add_entities([HAWyzeSwitch(wyzeapi_client, switch) for switch in switches], True)


class HAWyzeSwitch(SwitchEntity):
    """Representation of a Wyze Switch."""

    __client: WyzeApiClient
    __switch: Switch
    __just_updated = False

    def __init__(self, client: WyzeApiClient, switch: Switch):
        """Initialize a Wyze Bulb."""
        self.__switch = switch
        self.__client = client

    @property
    def should_poll(self) -> bool:
        return True

    def turn_on(self, **kwargs: Any) -> None:
        asyncio.get_event_loop().run_until_complete(self.__client.turn_on(self.__switch))
        self.__switch.switch_state = 1
        self.__just_updated = True

    def turn_off(self, **kwargs: Any) -> None:
        asyncio.get_event_loop().run_until_complete(self.__client.turn_off(self.__switch))
        self.__switch.switch_state = 0
        self.__just_updated = True

    @property
    def name(self):
        """Return the display name of this switch."""
        return self.__switch.nick_name

    @property
    def available(self):
        """Return the connection status of this switch"""
        return self.__switch.available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.__switch.switch_state == 1

    @property
    def unique_id(self):
        return self.__switch.mac

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "device model": self.__switch.product_model,
            "ssid": self.__switch.ssid,
            "ip": self.__switch.ip,
            "rssi": self.__switch.rssi,
            "mac": self.unique_id
        }

    async def async_turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        await self.__client.turn_on(self.__switch)
        self.__switch.switch_state = 1
        self.__just_updated = True

    async def async_turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        await self.__client.turn_off(self.__switch)
        self.__switch.switch_state = 0
        self.__just_updated = True

    async def async_update(self):
        """Fetch new state data for this switch.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("Updating Switch: {}".format(self.name))
        if self.__just_updated:
            self.__just_updated = False
            return

        self.__switch = await self.__client.update(self.__switch)
