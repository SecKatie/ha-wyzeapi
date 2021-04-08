"""Wyze Bulb/Switch integration."""

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME)
from wyzeapy.base_client import AccessTokenError
from wyzeapy.client import Client

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'wyzeapi'
VERSION = '2021.4.7'
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


def setup(hass, config):
    """Set up the WyzeApi parent component."""
    _LOGGER.debug("""-------------------------------------------------------------------
Wyze Home Assistant Integration

Version: {}
This is a custom integration
If you have any issues with this than please open an issue here:
https://github.com/JoshuaMulliken/ha-wyzeapi/issues
-------------------------------------------------------------------""".format(VERSION))
    _LOGGER.debug("""Creating new WyzeApi component""")

    light_support = config[DOMAIN].get(CONF_LIGHT)
    switch_support = config[DOMAIN].get(CONF_SWITCH)

    wyzeapi_client = Client(config[DOMAIN].get(CONF_USERNAME), config[DOMAIN].get(CONF_PASSWORD))
    _LOGGER.debug("Connected to Wyze account")

    try:
        devices = wyzeapi_client.get_devices()
    except AccessTokenError as e:
        _LOGGER.warning(e)
        wyzeapi_client.reauthenticate()
        devices = wyzeapi_client.get_devices()

    # Store the logged in account object for the platforms to use.
    hass.data[DOMAIN] = {
        "wyzeapi_client": wyzeapi_client,
        "devices": devices
    }

    # Start up lights and switch components
    _LOGGER.debug("Starting WyzeApi components")
    if light_support:
        _LOGGER.debug("Starting WyzeApi Lights")
        hass.helpers.discovery.load_platform("light", DOMAIN, {}, config)
    if switch_support:
        _LOGGER.debug("Starting WyzeApi switches")
        hass.helpers.discovery.load_platform("switch", DOMAIN, {}, config)

    return True
