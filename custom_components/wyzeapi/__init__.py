"""Wyze Bulb/Switch integration."""

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import discovery

from .wyzeapi.client import WyzeApiClient

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'wyzeapi'
CONF_SENSORS = "sensors"
CONF_LIGHT = "light"
CONF_SWITCH = "switch"
CONF_LOCK = "lock"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SENSORS, default=True): cv.boolean,
        vol.Optional(CONF_LIGHT, default=True): cv.boolean,
        vol.Optional(CONF_SWITCH, default=True): cv.boolean,
        vol.Optional(CONF_LOCK, default=True): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the WyzeApi parent component."""
    _LOGGER.debug("""
-------------------------------------------------------------------
Wyze Bulb and Switch Home Assistant Integration

Version: v0.5.2
This is a custom integration
If you have any issues with this you need to open an issue here:
https://github.com/JoshuaMulliken/ha-wyzeapi/issues
-------------------------------------------------------------------""")
    _LOGGER.debug("""Creating new WyzeApi component""")

    wyzeapi_account: WyzeApiClient = WyzeApiClient()
    await wyzeapi_account.login(config[DOMAIN].get(CONF_USERNAME), config[DOMAIN].get(CONF_PASSWORD))

    sensor_support = config[DOMAIN].get(CONF_SENSORS)
    light_support = config[DOMAIN].get(CONF_LIGHT)
    switch_support = config[DOMAIN].get(CONF_SWITCH)
    lock_support = config[DOMAIN].get(CONF_LOCK)

    if not wyzeapi_account.is_logged_in():
        _LOGGER.error("Not connected to Wyze account. Unable to add devices. Check your configuration.")
        return False

    _LOGGER.debug("Connected to Wyze account")

    # Store the logged in account object for the platforms to use.
    hass.data[DOMAIN] = {
        "wyzeapi_account": wyzeapi_account
    }

    # Start up lights and switch components
    _LOGGER.debug("Starting WyzeApi components")
    if light_support:
        await discovery.async_load_platform(hass, "light", DOMAIN, {}, config)
        _LOGGER.debug("Starting WyzeApi Lights")
    if switch_support:
        await discovery.async_load_platform(hass, "switch", DOMAIN, {}, config)
        _LOGGER.debug("Starting WyzeApi switches")
    if sensor_support:
        await discovery.async_load_platform(hass, "binary_sensor", DOMAIN, {}, config)
        _LOGGER.debug("Starting WyzeApi Sensors")
    if lock_support:
        await discovery.async_load_platform(hass, "lock", DOMAIN, {}, config)
        _LOGGER.debug("Starting WyzeApi lock")
    else:
        _LOGGER.error("WyzeApi authenticated but could not find any devices.")

    return True
