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
from .wyzeapi.client import WyzeApiClient
from .wyzeapi.devices import WyzeMotionSensor, WyzeContactSensor

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

    wyzeapi_client: WyzeApiClient = hass.data[DOMAIN]["wyzeapi_account"]

    # Add devices
    contact_sensors = await wyzeapi_client.list_contact_sensors()
    async_add_entities([HAWyzeContactSensor(wyzeapi_client, sensor) for sensor in contact_sensors], True)
    motion_sensors = await wyzeapi_client.list_motion_sensors()
    async_add_entities([HAWyzeMotionSensor(wyzeapi_client, motion_sensor) for motion_sensor in motion_sensors], True)


class HAWyzeContactSensor(BinarySensorEntity):
    """Representation of a Wyze binary_sensor."""
    __sensor: WyzeContactSensor
    __client: WyzeApiClient

    def __init__(self, client: WyzeApiClient, sensor: WyzeContactSensor):
        """Initialize a Wyze binary_sensor."""
        self.__sensor = sensor
        self.__client = client

    @property
    def name(self) -> str:
        """Return the display name of this sensor."""
        return self.__sensor.nick_name

    @property
    def available(self) -> bool:
        """Return the connection status of this sensor"""
        return self.__sensor.avaliable == 1

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self.__sensor.open_close_state == 1

    @property
    def unique_id(self) -> str:
        return self.__sensor.mac

    @property
    def device_class(self) -> str:
        """Return device class."""
        return DEVICE_CLASS_DOOR

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATE: self.is_on,
            ATTR_AVAILABLE: self.available,
            ATTR_MAC: self.unique_id,
            ATTR_BATTERY_LEVEL: self.__sensor.voltage,
            ATTR_RSSI: self.__sensor.rssi,
            ATTR_DEVICE_MODEL: self.__sensor.product_model,
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
        last_update_time_1 = str(self.__sensor.open_close_state_ts)
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
        await self.__client.update_contact_sensor(self.__sensor)


class HAWyzeMotionSensor(BinarySensorEntity):
    """Representation of a Wyze binary_sensor."""
    __sensor: WyzeMotionSensor
    __client: WyzeApiClient

    def __init__(self, client: WyzeApiClient, motion_sensor: WyzeMotionSensor):
        """Initialize a Wyze binary_sensor."""
        self.__sensor = motion_sensor
        self.__client = client

    @property
    def name(self) -> str:
        """Return the display name of this sensor."""
        return self.__sensor.nick_name

    @property
    def available(self) -> bool:
        """Return the connection status of this sensor"""
        return self.__sensor.avaliable == 1

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self.__sensor.motion_state == 1

    @property
    def unique_id(self) -> str:
        return self.__sensor.mac

    @property
    def device_class(self):
        """Return device class."""
        return DEVICE_CLASS_MOTION

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATE: self.is_on,
            ATTR_AVAILABLE: self.available,
            ATTR_MAC: self.unique_id,
            ATTR_BATTERY_LEVEL: self.__sensor.voltage,
            ATTR_RSSI: self.__sensor.rssi,
            ATTR_DEVICE_MODEL: self.__sensor.product_model,
            ATTR_LAST_ACTION: self.epoch_to_utc()
        }

    @property
    def should_poll(self):
        """We always want to poll for motion_sensor."""
        return True

    def epoch_to_utc(self):
        last_update_time_1 = str(self.__sensor.motion_state_ts)
        last_update_time_2 = last_update_time_1[:-3]
        last_update_time_3 = int(last_update_time_2)
        return dt_util.utc_from_timestamp(float(last_update_time_3))

    async def async_update(self):
        """Fetch new state data for this sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("""Binary Sensors doing a update.""")
        await self.__client.update_motion_sensor(self.__sensor)
