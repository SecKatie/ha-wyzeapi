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
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

def setup(hass, config):
    """Set up the WyzeApi parent component."""
    _LOGGER.info("Creating new WyzeApi component")

    wyzeapi_account = WyzeApi(config[DOMAIN].get(CONF_USERNAME),
                              config[DOMAIN].get(CONF_PASSWORD))

    if not wyzeapi_account.is_valid_login():
        _LOGGER.error("Not connected to Wyze account. Unable to add devices. Check your configuration.")
        return False

    _LOGGER.info("Connected to Wyze account")
    wyzeapi_devices = wyzeapi_account.get_devices()

    # Store the logged in account object for the platforms to use.
    hass.data[DOMAIN] = {
        "wyzeapi_account": wyzeapi_account
    }

    # Start up lights and switch components
    if wyzeapi_devices:
        _LOGGER.debug("Starting WyzeApi components")
        discovery.load_platform(hass, "light", DOMAIN, {}, config)
        discovery.load_platform(hass, "switch", DOMAIN, {}, config)
    else:
        _LOGGER.error("WyzeApi authenticated but could not find any devices.")

    return True
