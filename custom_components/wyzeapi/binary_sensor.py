#!/usr/bin/python3

"""Platform for binary_sensor integration."""
import logging
from datetime import timedelta
import time;
import datetime
from .wyzeapi.wyzeapi import WyzeApi
from . import DOMAIN

import voluptuous as vol

import homeassistant.util.dt as dt_util

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
ATTR_STATE ="state"
ATTR_AVAILABLE = "available"
ATTR_MAC = "mac"
ATTR_RSSI = "rssi"
ATTR_DEVICE_MODEL = "device model"
ATTR_OPEN_SINCE = "Open since"
ATTR_LAST_ACTION = "last_action"
ATTR_NO_MOTION_SINCE = "No motion since"

NO_CLOSE = "no_close"
MOTION = "motion"
NO_MOTION = "no_motion"


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
            #TODO: Show only if contact
            #ATTR_OPEN_SINCE : "Open since"
            #TODO: Show only if Motion
            #ATTR_NO_MOTION_SINCE : "No motion since"
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATE : self._state,
            ATTR_AVAILABLE : self._avaliable,
            ATTR_MAC : self._device_mac,
            ATTR_BATTERY_LEVEL: self._voltage,
            ATTR_RSSI: self._rssi,
            ATTR_DEVICE_MODEL : self._device_model,
            ATTR_LAST_ACTION : self.epoch_to_UTC()

        }

    @property
    def should_poll(self):
        """We always want to poll for sensors."""
        return True

    def epoch_to_UTC(self):
        #The code below is slicing, works but not on integers. 
        #If you want to use it you can convert the number to str for slicing then convert it back to int. 
        #It is not the best practice but it can be done as the following:
        lastupdatetime1 = str(self._open_close_state_ts)
        lastupdatetime2 = lastupdatetime1[:-3]
        lastupdatetime3 = int(lastupdatetime2)
        lastupdatetime4 = dt_util.utc_from_timestamp(float(lastupdatetime3))
        return lastupdatetime4

    def time_since_last_update(self):
        #Feature use
        return True

    def no_motion_since(self):
        #Feature use
        return True

    def open_since(self):
        #Feature use
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
