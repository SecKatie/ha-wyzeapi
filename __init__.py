"""Wyze Bulb/Switch integration."""

import logging

import voluptuous as vol

from .wyzeapi.wyzeapi import WyzeApi

from homeassistant.const import (
    CONF_DEVICES, CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'wyzeapi'
CONF_SENSORS = "sensors"
CONF_LIGHT = "light"
CONF_SWITCH = "switch"
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SENSORS, default=False): cv.boolean,
        vol.Optional(CONF_LIGHT, default=True): cv.boolean,
        vol.Optional(CONF_SWITCH, default=True): cv.boolean

    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, config):
    """Set up the WyzeApi parent component."""
    _LOGGER.debug("""
-------------------------------------------------------------------
Wyze Bulb and Switch Home Assistant Integration

Version: v0.4.3-beta.1
This is a custom integration
If you have any issues with this you need to open an issue here:
https://github.com/JoshuaMulliken/ha-wyzeapi/issues
-------------------------------------------------------------------""")
    _LOGGER.debug("""Creating new WyzeApi component""")

    wyzeapi_account = WyzeApi(config[DOMAIN].get(CONF_USERNAME),
                              config[DOMAIN].get(CONF_PASSWORD))
    await wyzeapi_account.async_init()

    sensor_support = config[DOMAIN].get(CONF_SENSORS)
    light_support = config[DOMAIN].get(CONF_LIGHT)
    switch_support = config[DOMAIN].get(CONF_SWITCH)


    if not wyzeapi_account.is_valid_login():
        _LOGGER.error("Not connected to Wyze account. Unable to add devices. Check your configuration.")
        return False

    _LOGGER.debug("Connected to Wyze account")
    wyzeapi_devices = await wyzeapi_account.async_get_devices()

    # Store the logged in account object for the platforms to use.
    hass.data[DOMAIN] = {
        "wyzeapi_account": wyzeapi_account
    }

    # Start up lights and switch components
    if wyzeapi_devices:
        _LOGGER.debug("Starting WyzeApi components")
        if light_support == True:
            await discovery.async_load_platform(hass, "light", DOMAIN, {}, config)
        if switch_support == True:
            await discovery.async_load_platform(hass, "switch", DOMAIN, {}, config)
        if sensor_support == True:
            await discovery.async_load_platform(hass, "binary_sensor", DOMAIN, {}, config)
    else:
        _LOGGER.error("WyzeApi authenticated but could not find any devices.")

    return True
