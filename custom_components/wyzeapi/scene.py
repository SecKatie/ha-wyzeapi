#!/usr/bin/python3

"""Platform for switch integration."""
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.scene import (Scene)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from wyzeapy.base_client import AccessTokenError
from wyzeapy.client import Client
from wyzeapy.types import Group

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("""Creating new WyzeApi group component""")
    client = hass.data[DOMAIN][config_entry.entry_id]

    groups = [WyzeGroup(client, group) for group in await client.get_groups()]

    async_add_entities(groups, True)


class WyzeGroup(Scene):
    """Representation of a Wyze Rule."""

    _client: Client
    _group: Group

    def __init__(self, client: Client, group: Group):
        """Initialize a Wyze Bulb."""
        self._group = group
        self._client = client

    def activate(self, **kwargs: Any) -> None:
        try:
            self._client.activate_group(self._group)
        except AccessTokenError:
            self._client.reauthenticate()
            self._client.activate_group(self._group)

    @property
    def name(self):
        """Return the display name of this scene."""
        return self._group.group_name

    @property
    def available(self):
        """Return the connection status of this scene"""
        return True

    @property
    def unique_id(self):
        return "{}-scene".format(self._group.group_id)

