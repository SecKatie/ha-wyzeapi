"""The Wyze Home Assistant Integration integration."""
from __future__ import annotations

import asyncio
import configparser
import logging
import os
import uuid
from homeassistant import config_entries

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.check_config import HomeAssistantConfig
from homeassistant.exceptions import ConfigEntryAuthFailed
from wyzeapy import Wyzeapy
from wyzeapy.wyze_auth_lib import Token
from .token_manager import TokenManager

from .const import DOMAIN, CONF_CLIENT, ACCESS_TOKEN, REFRESH_TOKEN, REFRESH_TIME

PLATFORMS = [
    "light",
    "switch",
    "lock",
    "climate",
    "alarm_control_panel",
]  # Fixme: Re add scene
_LOGGER = logging.getLogger(__name__)

# noinspection PyUnusedLocal
async def async_setup(
    hass: HomeAssistant, config: HomeAssistantConfig, discovery_info=None
):
    # pylint: disable=unused-argument
    """Set up the WyzeApi domain."""
    if hass.config_entries.async_entries(DOMAIN):
        _LOGGER.debug(
            "Nothing to import from configuration.yaml, loading from Integrations",
        )
        return True

    domainconfig = config.get(DOMAIN)
    # pylint: disable=logging-not-lazy
    _LOGGER.debug(
        "Importing config information for %s from configuration.yml"
        % domainconfig[CONF_USERNAME]
    )
    if hass.config_entries.async_entries(DOMAIN):
        _LOGGER.debug("Found existing config entries")
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry:
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_USERNAME: entry.data.get(CONF_USERNAME),
                        CONF_PASSWORD: entry.data.get(CONF_PASSWORD),
                        ACCESS_TOKEN: entry.data.get(ACCESS_TOKEN),
                        REFRESH_TOKEN: entry.data.get(REFRESH_TOKEN),
                        REFRESH_TIME: entry.data.get(REFRESH_TIME),
                    },
                )
                break
    else:
        _LOGGER.debug("Creating new config entry")
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_USERNAME: domainconfig[CONF_USERNAME],
                    CONF_PASSWORD: domainconfig[CONF_PASSWORD],
                    ACCESS_TOKEN: domainconfig[ACCESS_TOKEN],
                    REFRESH_TOKEN: domainconfig[REFRESH_TOKEN],
                    REFRESH_TIME: domainconfig[REFRESH_TIME],
                },
            )
        )
    return True


# noinspection DuplicatedCode
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Wyze Home Assistant Integration from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    client = await Wyzeapy.create()
    token = None
    if config_entry.data.get(ACCESS_TOKEN):
        token = Token(
            config_entry.data.get(ACCESS_TOKEN),
            config_entry.data.get(REFRESH_TOKEN),
            float(config_entry.data.get(REFRESH_TIME)),
        )
    token_manager = TokenManager(hass, config_entries)
    client.register_for_token_callback(token_manager.token_callback)
    # We should probably try/catch here to invalidate the login credentials and throw a notification if we cannot get a login with the token
    try:
        await client.login(
            config_entry.data.get(CONF_USERNAME),
            config_entry.data.get(CONF_PASSWORD),
            token,
        )
    except:
        _LOGGER.error("Wyzeapi: Could not login. Please re-login through integration configuration.")
        raise ConfigEntryAuthFailed("Unable to login, please re-login.")

    hass.data[DOMAIN][config_entry.entry_id] = {CONF_CLIENT: client}

    for platform in PLATFORMS:
        hass.create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    mac_addresses = await client.unique_device_ids

    def get_uid():
        config_path = hass.config.path("wyze_config.ini")

        config = configparser.ConfigParser()
        config.read(config_path)
        if config.has_option("OPTIONS", "SYSTEM_ID"):
            return config["OPTIONS"]["SYSTEM_ID"]
        else:
            new_uid = uuid.uuid4().hex
            config["OPTIONS"] = {}
            config["OPTIONS"]["SYSTEM_ID"] = new_uid

            with open(config_path, "w") as configfile:
                config.write(configfile)

            return new_uid

    uid = await hass.async_add_executor_job(get_uid)
    mac_addresses.add(uid)

    hms_service = await client.hms_service
    hms_id = hms_service.hms_id
    if hms_id is not None:
        mac_addresses.add(hms_id)

    device_registry = await dr.async_get_registry(hass)
    for device in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        for identifier in device.identifiers:
            domain, mac = identifier
            if mac not in mac_addresses:
                _LOGGER.warning(
                    f"{mac} is not in the mac_addresses list. Removing the entry..."
                )
                device_registry.async_remove_device(device.id)
    return True

async def options_update_listener(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    _LOGGER.debug("Updated options")
    hass.config_entries.async_update_entry(
                    config_entry,
                    data={
                        CONF_USERNAME: config_entry.options.get(CONF_USERNAME),
                        CONF_PASSWORD: config_entry.options.get(CONF_PASSWORD),
                        ACCESS_TOKEN: config_entry.options.get(ACCESS_TOKEN),
                        REFRESH_TOKEN: config_entry.options.get(REFRESH_TOKEN),
                        REFRESH_TIME: config_entry.options.get(REFRESH_TIME),
                    },
                )
    _LOGGER.debug("Reload entry: " + config_entry.entry_id)
    await hass.config_entries.async_reload(config_entry.entry_id)


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
