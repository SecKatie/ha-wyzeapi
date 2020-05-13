#!/usr/bin/python3

"""Platform for binary_sensor integration."""
import logging
from datetime import timedelta

from .wyzeapi.wyzeapi import WyzeApi
from . import DOMAIN

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_BATTERY_LEVEL, DEVICE_CLASS_TIMESTAMP
# Import the device class from the component that you want to support
from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA,
    BinarySensorDevice,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_DOOR
    )

#Add to support quicker update time. Is this to Fast?
SCAN_INTERVAL = timedelta(seconds=5)

ATTRIBUTION = "Data provided by Wyze"

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wyze binary_sensor platform."""
    _LOGGER.debug("""FARMER: Creating new WyzeApi binary_sensor component""")

    # Add devices
    add_entities([WyzeSensor(sensor) for sensor in await hass.data[DOMAIN]["wyzeapi_account"].async_list_sensor()], True)

class WyzeSensor(BinarySensorDevice):
    """Representation of a Wyze binary_sensor."""

    def __init__(self, sensor):
        """Initialize a Wyze binary_sensor."""
        self._sensor = sensor
        self._name = sensor._friendly_name
        self._state = sensor._state
        self._avaliable = True
        self._voltage = sensor._voltage
        self._rssi = sensor._rssi
        self._device_mac = sensor._device_mac
        self._open_close_state_ts = sensor._open_close_state_ts
        self._device_model = sensor._device_model

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self._name

    @property
    def available(self):
        """Return the connection status of this sensor"""
        return self._avaliable

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def unique_id(self):
        return self._device_mac

    @property
    def device_class(self):
        """Return device class."""
        return DEVICE_CLASS_DOOR if self._device_model =="DWS3U" else DEVICE_CLASS_MOTION

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self._state,
            "available": self._avaliable,
            "mac": self._device_mac,
            ATTR_BATTERY_LEVEL: self._voltage,
            "rssi": self._rssi,
            "device model": self._device_model,
            #"""Need to Convert epoch millisecond expressed in integer"""
            "timestamp" : self._open_close_state_ts
        }

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return True

    async def async_update(self):
        """Fetch new state data for this sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("""Binary Sesnors doing a update.""")
        await self._sensor.async_update()
        self._state = self._sensor._state
        self._rssi = self._sensor._rssi
        self._voltage = self._sensor._voltage
        self._open_close_state_ts = self._sensor._open_close_state_ts
