#!/usr/bin/python3

"""Platform for switch integration."""
import logging
from datetime import timedelta
from typing import Any, List

from homeassistant.components.scene import (Scene)
from homeassistant.const import ATTR_ATTRIBUTION
from wyzeapy.base_client import AccessTokenError, Group, PropertyIDs
from wyzeapy.client import Client

from . import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("""Creating new WyzeApi group component""")
    client = hass.data[DOMAIN][config_entry.entry_id]

    def get_groups() -> List[Group]:
        try:
            groups = client.get_groups()
        except AccessTokenError as e:
            _LOGGER.warning(e)
            client.reauthenticate()
            groups = client.get_groups()

        return groups

    groups = await hass.async_add_executor_job(get_groups)

    scenes = []
    for group in groups:
        try:
            scenes.append(WyzeGroup(client, group))

        except ValueError as e:
            _LOGGER.warning("{}: Please report this error to https://github.com/JoshuaMulliken/ha-wyzeapi".format(e))

    async_add_entities(scenes, True)


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

