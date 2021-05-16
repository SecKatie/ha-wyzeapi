"""The Wyze Home Assistant Integration integration."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.check_config import HomeAssistantConfig
from wyzeapy.client import Client

from .const import DOMAIN, CONF_CAM_MOTION, CONF_CAM_SOUND
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

PLATFORMS = ["light", "switch", "binary_sensor", "lock"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: HomeAssistantConfig, discovery_info=None):
    # pylint: disable=unused-argument
    """Set up the Alexa domain."""
    if DOMAIN not in config:
        _LOGGER.debug(
            "Nothing to import from configuration.yaml, loading from Integrations",
        )
        return True

    domainconfig = config.get(DOMAIN)
    entry_found = False
    _LOGGER.debug(
        "Importing config information for {} from configuration.yml".format(domainconfig[CONF_USERNAME])
    )
    
    if CONF_USERNAME and CONF_PASSWORD in domainconfig:
        _LOGGER.debug("Username = {} {}".format(domainconfig[CONF_USERNAME], domainconfig[CONF_PASSWORD]))
    else:
        _LOGGER.error("Missing username and/or passport")
        return False

    if CONF_CAM_MOTION in domainconfig:
        cam_motion = domainconfig[CONF_CAM_MOTION]
    else:
        cam_motion = True # Default ON for backward compatibility

    if CONF_CAM_SOUND in domainconfig:
        cam_sound = domainconfig[CONF_CAM_SOUND]
    else:
        cam_sound = False # Default OFF for backward compatibility

    if hass.config_entries.async_entries(DOMAIN):
        _LOGGER.debug("Found existing config entries")
        for entry in hass.config_entries.async_entries(DOMAIN):
            if (
                    entry.data.get(CONF_USERNAME) == domainconfig[CONF_USERNAME]
                    and entry.data.get(CONF_PASSWORD) == domainconfig[CONF_PASSWORD]
            ):
                _LOGGER.debug("Updating existing entry")
                hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_USERNAME: domainconfig[CONF_USERNAME],
                        CONF_PASSWORD: domainconfig[CONF_PASSWORD],
                        CONF_CAM_MOTION: cam_motion,
                        CONF_CAM_SOUND: cam_sound
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
                    CONF_CAM_MOTION: cam_motion,
                    CONF_CAM_SOUND: cam_sound
            },
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wyze Home Assistant Integration from a config entry."""

    def setup_hass_data():
        hass.data[DOMAIN][entry.entry_id] = Client(entry.data.get(CONF_USERNAME), entry.data.get(CONF_PASSWORD))

    hass.data.setdefault(DOMAIN, {})
    await hass.async_add_executor_job(setup_hass_data)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

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
