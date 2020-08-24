#!/usr/bin/python3

"""Platform for binary_sensor integration."""
import logging
from datetime import timedelta

import homeassistant.util.dt as dt_util
# Import the device class from the component that you want to support
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_DOOR
)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_BATTERY_LEVEL

from . import DOMAIN
from .wyzeapi.sensors.wyze_contact import WyzeContactSensor
from .wyzeapi.sensors.wyze_motion import WyzeMotionSensor

# Add to support quicker update time. Is this to Fast?
SCAN_INTERVAL = timedelta(seconds=5)

ATTRIBUTION = "Data provided by Wyze"
ATTR_STATE = "state"
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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Wyze binary_sensor platform."""
    _LOGGER.debug("""Creating new WyzeApi binary_sensor component""")

    _ = config
    _ = discovery_info

    # Add devices
    async_add_entities([HAWyzeContactSensor(sensor) for sensor in
                        await hass.data[DOMAIN]["wyzeapi_account"].async_list_contact_sensor()], True)
    async_add_entities([HAWyzeMotionSensor(motion_sensor) for motion_sensor in
                        await hass.data[DOMAIN]["wyzeapi_account"].async_list_motion_sensor()], True)


class HAWyzeContactSensor(BinarySensorEntity):
    """Representation of a Wyze binary_sensor."""

    def __init__(self, sensor: WyzeContactSensor):
        """Initialize a Wyze binary_sensor."""
        self.__sensor = sensor
        self.__name = sensor.friendly_name
        self.__state = sensor.state
        self.__available = True
        self.__voltage = sensor.voltage
        self.__rssi = sensor.rssi
        self.__device_mac = sensor.device_mac
        self.__open_close_state_ts = sensor.open_close_state_ts
        self.__device_model = sensor.device_model

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self.__name

    @property
    def available(self):
        """Return the connection status of this sensor"""
        return self.__available

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self.__state

    @property
    def unique_id(self):
        return self.__device_mac

    @property
    def device_class(self):
        """Return device class."""
        return DEVICE_CLASS_DOOR

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATE: self.__state,
            ATTR_AVAILABLE: self.__available,
            ATTR_MAC: self.__device_mac,
            ATTR_BATTERY_LEVEL: self.__voltage,
            ATTR_RSSI: self.__rssi,
            ATTR_DEVICE_MODEL: self.__device_model,
            ATTR_LAST_ACTION: self.epoch_to_utc()
        }

    @property
    def should_poll(self):
        """We always want to poll for sensors."""
        return True

    def epoch_to_utc(self):
        # The code below is slicing, works but not on integers.
        # If you want to use it you can convert the number to str for slicing then convert it back to int.
        # It is not the best practice but it can be done as the following:
        last_update_time_1 = str(self.__open_close_state_ts)
        last_update_time_2 = last_update_time_1[:-3]
        last_update_time_3 = int(last_update_time_2)
        return dt_util.utc_from_timestamp(float(last_update_time_3))

    @staticmethod
    def time_since_last_update():
        # Feature use
        return True

    @staticmethod
    def no_motion_since():
        # Feature use
        return True

    @staticmethod
    def open_since():
        # Feature use
        return True

    async def async_update(self):
        """Fetch new state data for this sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("""Binary Sensors doing a update.""")
        await self.__sensor.async_update()
        self.__state = self.__sensor.state
        self.__rssi = self.__sensor.rssi
        self.__voltage = self.__sensor.voltage
        self.__open_close_state_ts = self.__sensor.open_close_state_ts


class HAWyzeMotionSensor(BinarySensorEntity):
    """Representation of a Wyze binary_sensor."""

    def __init__(self, motion_sensor: WyzeMotionSensor):
        """Initialize a Wyze binary_sensor."""
        self.__motion_sensor = motion_sensor
        self._name = motion_sensor.friendly_name
        self._state = motion_sensor.state
        self._available = True
        self._voltage = motion_sensor.voltage
        self._rssi = motion_sensor.rssi
        self._device_mac = motion_sensor.device_mac
        self._open_close_state_ts = motion_sensor.open_close_state_ts
        self._device_model = motion_sensor.device_model

    @property
    def name(self):
        """Return the display name of this motion_sensor."""
        return self._name

    @property
    def available(self):
        """Return the connection status of this motion_sensor"""
        return self._available

    @property
    def is_on(self):
        """Return true if motion_sensor is on."""
        return self._state

    @property
    def unique_id(self):
        return self._device_mac

    @property
    def device_class(self):
        """Return device class."""
        return DEVICE_CLASS_MOTION

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATE: self._state,
            ATTR_AVAILABLE: self._available,
            ATTR_MAC: self._device_mac,
            ATTR_BATTERY_LEVEL: self._voltage,
            ATTR_RSSI: self._rssi,
            ATTR_DEVICE_MODEL: self._device_model,
            ATTR_LAST_ACTION: self.epoch_to_utc()
        }

    @property
    def should_poll(self):
        """We always want to poll for motion_sensor."""
        return True

    def epoch_to_utc(self):
        last_update_time_1 = str(self._open_close_state_ts)
        last_update_time_2 = last_update_time_1[:-3]
        last_update_time_3 = int(last_update_time_2)
        return dt_util.utc_from_timestamp(float(last_update_time_3))

    async def async_update(self):
        """Fetch new state data for this sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("""Binary Sensors doing a update.""")
        await self.__motion_sensor.async_update()
        self._state = self.__motion_sensor.state
        self._rssi = self.__motion_sensor.rssi
        self._voltage = self.__motion_sensor.voltage
        self._open_close_state_ts = self.__motion_sensor.open_close_state_ts
