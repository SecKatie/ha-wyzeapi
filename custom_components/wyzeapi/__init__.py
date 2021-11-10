"""The Wyze Home Assistant Integration integration."""
from __future__ import annotations

import asyncio
import configparser
import logging
import os
from homeassistant import config_entries

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_registry import async_get as er_get
from homeassistant.helpers.check_config import HomeAssistantConfig
from homeassistant.exceptions import ConfigEntryAuthFailed
from wyzeapy import Wyzeapy
from wyzeapy.wyze_auth_lib import Token
from .token_manager import TokenManager

from .const import DOMAIN, CONF_CLIENT, ACCESS_TOKEN, REFRESH_TOKEN, REFRESH_TIME, WYZE_NOTIFICATION_TOGGLE

PLATFORMS = [
    "light",
    "switch",
    "lock",
    "climate",
    "alarm_control_panel",
    "sensor"
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
                entry_data = entry.as_dict().get("data")
                hass.config_entries.async_update_entry(
                    entry,
                    data=entry_data,
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
        _LOGGER.error("Wyzeapi: Could not login. Please re-login through integration configuration")
        raise ConfigEntryAuthFailed("Unable to login, please re-login.") from None

    hass.data[DOMAIN][config_entry.entry_id] = {CONF_CLIENT: client}

    for platform in PLATFORMS:
        hass.create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    mac_addresses = await client.unique_device_ids

    mac_addresses.add(WYZE_NOTIFICATION_TOGGLE)

    hms_service = await client.hms_service
    hms_id = hms_service.hms_id
    if hms_id is not None:
        mac_addresses.add(hms_id)

    await cleanup_registries(hass, config_entry, mac_addresses)

    return True

async def options_update_listener(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    _LOGGER.debug("Updated options")
    entry_data = config_entry.as_dict().get("data")
    hass.config_entries.async_update_entry(
        config_entry,
        data=entry_data,
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

async def cleanup_registries(hass, config_entry, mac_addresses):
    device_registry = await dr.async_get_registry(hass)
    entity_registry = er_get(hass)
    entity_registry_list = entity_registry.entities.copy()
    for entity in entity_registry_list:
        ent = entity_registry.async_get(entity)
        # IMPORTANT!
        # restrict this to our integration/platform so as not to remove other entities for other integrations
        #
        # Note: Home Assistant stores the integration domain as "platform" in the entity properties. This is misleading.
        if ent.platform != DOMAIN:
            continue
        #
        # continue on to general cleanup
        #
        # get rid of any entities that do not belong to a current/valid device
        if device_registry.async_get(hass.helpers.template.device_id(hass, ent.entity_id)) is None:
            _LOGGER.warning(
                "%s does not belong to a current device, removing the entity: ", ent.entity_id
                )
            entity_registry.async_remove(ent.entity_id)
            continue
        # remove platforms that are no longer supported
        if ent.domain not in PLATFORMS:
            _LOGGER.warning(
                '%s is no longer a supported platform, removing the entity', ent.entity_id
            )
            await entity_registry.async_remove(ent.entity_id)

        # get rid of the old notification toggle entity
        if "switch.wyze_notifications" in ent.entity_id and ent.unique_id != "wyzeapi.wyze.notification.toggle":
            _LOGGER.warning(
                '%s - wyze notifcation toggle UUID has been changed so this is now a defunt entity, removing the entity', ent.entity_id
            )
            await entity_registry.async_remove(ent.entity_id)

    for device in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        for identifier in device.identifiers:
            # domain has to remain here. If it is removed the integration will remove all entities for not being in the mac address list each boot.
            domain, mac = identifier
            if mac not in mac_addresses:
                _LOGGER.warning(
                    '%s is not in the mac_addresses list, removing the entry', mac
                )
                await device_registry.async_remove_device(device.id)
