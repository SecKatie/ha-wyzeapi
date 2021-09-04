"""The Wyze Home Assistant Integration integration."""
from __future__ import annotations

import asyncio
import configparser
import logging
import os
import uuid

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.check_config import HomeAssistantConfig
from wyzeapy import Wyzeapy

from .const import DOMAIN, CONF_CLIENT

PLATFORMS = ["light", "switch", "lock", "climate",
             "alarm_control_panel"]  # Fixme: Re add scene
_LOGGER = logging.getLogger(__name__)


# noinspection PyUnusedLocal
async def async_setup(hass: HomeAssistant, config: HomeAssistantConfig,
                      discovery_info=None):
    # pylint: disable=unused-argument
    """Set up the Alexa domain."""
    if DOMAIN not in config:
        _LOGGER.debug(
            "Nothing to import from configuration.yaml, loading from "
            "Integrations",
        )
        return True

    domainconfig = config.get(DOMAIN)
    entry_found = False
    # pylint: disable=logging-not-lazy
    _LOGGER.debug("Importing config information for %s from configuration.yml" %
                  domainconfig[CONF_USERNAME])
    if hass.config_entries.async_entries(DOMAIN):
        _LOGGER.debug("Found existing config entries")
        for entry in hass.config_entries.async_entries(DOMAIN):
            if (entry.data.get(CONF_USERNAME) == domainconfig[CONF_USERNAME] and entry.data.get(CONF_PASSWORD) ==
                    domainconfig[CONF_PASSWORD]):
                _LOGGER.debug("Updating existing entry")
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_USERNAME: domainconfig[CONF_USERNAME],
                        CONF_PASSWORD: domainconfig[CONF_PASSWORD],
                    },
                )
                entry_found = True
                break
    if not entry_found:
        _LOGGER.debug("Creating new config entry")
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_USERNAME: domainconfig[CONF_USERNAME],
                    CONF_PASSWORD: domainconfig[CONF_PASSWORD],
                },
            )
        )
    return True


# noinspection DuplicatedCode
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Wyze Home Assistant Integration from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    client = await Wyzeapy.create()
    await client.login(config_entry.data.get(CONF_USERNAME), config_entry.data.get(CONF_PASSWORD))

    hass.data[DOMAIN][config_entry.entry_id] = {
        CONF_CLIENT: client
    }

    for platform in PLATFORMS:
        hass.create_task(hass.config_entries.async_forward_entry_setup(config_entry, platform))

    mac_addresses = await client.unique_device_ids

    def get_uid():
        config_path = hass.config.path('wyze_config.ini')

        config = configparser.ConfigParser()
        config.read(config_path)
        if config.has_option("OPTIONS", "SYSTEM_ID"):
            return config["OPTIONS"]["SYSTEM_ID"]
        else:
            new_uid = uuid.uuid4().hex
            config["OPTIONS"] = {}
            config["OPTIONS"]["SYSTEM_ID"] = new_uid

            with open(config_path, 'w') as configfile:
                config.write(configfile)

            return new_uid

    uid = await hass.async_add_executor_job(get_uid)
    mac_addresses.add(uid)

    hms_service = await client.hms_service
    hms_id = hms_service.hms_id
    if hms_id is not None:
        mac_addresses.add(hms_id)

    device_registry = await dr.async_get_registry(hass)
    for device in dr.async_entries_for_config_entry(device_registry, config_entry.entry_id):
        for identifier in device.identifiers:
            domain, mac = identifier
            if mac not in mac_addresses:
                _LOGGER.warning(f"{mac} is not in the mac_addresses list. Removing the entry...")
                device_registry.async_remove_device(device.id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
