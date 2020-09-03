#!/usr/bin/python3

"""Platform for binary_sensor integration."""
import logging
from datetime import timedelta

# Import the device class from the component that you want to support
from homeassistant.components.lock import LockEntity
from homeassistant.const import ATTR_ATTRIBUTION

from . import DOMAIN
from .wyzeapi.client import WyzeApiClient
from .wyzeapi.devices import Lock

# Add to support quicker update time. Is this too Fast?
SCAN_INTERVAL = timedelta(seconds=5)

ATTRIBUTION = "Data provided by Wyze"
ATTR_STATE = "state"
ATTR_AVAILABLE = "available"
ATTR_DEVICE_MODEL = "device model"
ATTR_OPEN_CLOSE_STATE = "door"

ATTR_DOOR_STATE_OPEN = "open"
ATTR_DOOR_STATE_CLOSE = "closed"

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Wyze binary_sensor platform."""

    _ = config
    _ = discovery_info

    wyzeapi_client: WyzeApiClient = hass.data[DOMAIN]["wyzeapi_account"]

    _LOGGER.debug("""Creating new WyzeApi Lock component""")
    locks = await wyzeapi_client.list_locks()
    async_add_entities([HAWyzeLock(wyzeapi_client, lock, hass) for lock in locks], True)


class HAWyzeLock(LockEntity):
    """Representation of a Wyze binary_sensor."""

    def __init__(self, client: WyzeApiClient, lock: Lock, hass):
        """Initialize a Wyze binary_sensor."""
        self.__hass = hass
        self.__lock = lock
        self.__client = client

    def lock(self, **kwargs):
        # FIXME needs to be implemented
        notification = "Locking and unlocking is not supported in this integration."
        self.__hass.components.persistent_notification.create(notification, DOMAIN)
        _LOGGER.debug(notification)
        pass

    def unlock(self, **kwargs):
        # FIXME needs to be implemented
        notification = "Locking and unlocking is not supported in this integration."
        self.__hass.components.persistent_notification.create(notification, DOMAIN)
        _LOGGER.debug(notification)
        pass

    def open(self, **kwargs):
        # Cannot open on this device
        pass

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self.__lock.nick_name

    @property
    def available(self):
        """Return the connection status of this sensor"""
        return self.__lock.available

    @property
    def is_locked(self):
        """Return true if sensor is on."""
        return self.__lock.switch_state == 0

    @property
    def unique_id(self):
        return self.__lock.mac

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATE: self.is_locked,
            ATTR_AVAILABLE: self.available,
            ATTR_DEVICE_MODEL: self.unique_id,
            ATTR_OPEN_CLOSE_STATE: self.get_door_state()
        }

    def get_door_state(self):
        return ATTR_DOOR_STATE_OPEN if self.__lock.open_close_state is 1 else ATTR_DOOR_STATE_CLOSE

    @property
    def should_poll(self):
        """We always want to poll for sensors."""
        return True

    async def async_lock(self, **kwargs):
        """Lock all or specified locks. A code to lock the lock with may optionally be specified."""
        # FIXME needs to be implemented
        notification = "Locking and unlocking is not supported in this integration."
        self.__hass.components.persistent_notification.create(notification, DOMAIN)
        _LOGGER.debug(notification)

    async def async_unlock(self, **kwargs):
        """Unlock all or specified locks. A code to unlock the lock with may optionally be specified."""
        # FIXME needs to be implemented
        notification = "Locking and unlocking is not supported in this integration."
        self.__hass.components.persistent_notification.create(notification, DOMAIN)
        _LOGGER.debug(notification)

    async def async_update(self):
        """Fetch new state data for this sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("""Binary Locks doing a update.""")
        self.__lock = await self.__client.update(self.__lock)
