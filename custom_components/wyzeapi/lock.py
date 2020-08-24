#!/usr/bin/python3

"""Platform for binary_sensor integration."""
import logging
from datetime import timedelta

# Import the device class from the component that you want to support
from homeassistant.components.lock import LockEntity
from homeassistant.const import ATTR_ATTRIBUTION

from . import DOMAIN
from .wyzeapi.wyze_lock import WyzeLock

# Add to support quicker update time. Is this to Fast?
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

    _LOGGER.debug("""Creating new WyzeApi Lock component""")
    async_add_entities(
        [HAWyzeLock(lock, hass) for lock in await hass.data[DOMAIN]["wyzeapi_account"].async_list_lock()], True)


class HAWyzeLock(LockEntity):
    """Representation of a Wyze binary_sensor."""

    def lock(self, **kwargs):
        # TODO implement
        pass

    def unlock(self, **kwargs):
        # TODO implement
        pass

    def open(self, **kwargs):
        # TODO implement
        pass

    def __init__(self, lock: WyzeLock, hass):
        """Initialize a Wyze binary_sensor."""
        self.__hass = hass
        self.__lock = lock
        self.__name = lock.friendly_name
        self.__state = lock.state
        self.__available = True
        self.__device_mac = lock.device_mac
        self.__device_model = lock.device_model
        self.__open_close_state = lock.open_close_state

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self.__name

    @property
    def available(self):
        """Return the connection status of this sensor"""
        return self.__available

    @property
    def is_locked(self):
        """Return true if sensor is on."""
        return self.__state

    @property
    def unique_id(self):
        return self.__device_mac

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATE: self.__state,
            ATTR_AVAILABLE: self.__available,
            ATTR_DEVICE_MODEL: self.__device_model,
            ATTR_OPEN_CLOSE_STATE: self.get_door_state()
        }

    def get_door_state(self):
        return ATTR_DOOR_STATE_OPEN if self.__open_close_state is True else ATTR_DOOR_STATE_CLOSE

    @property
    def should_poll(self):
        """We always want to poll for sensors."""
        return True

    # This is not working.
    async def async_lock(self, **kwargs):
        """Lock all or specified locks. A code to lock the lock with may optionally be specified."""
        # await self._lock.async_lock()
        notification = "Locking and unlocking is not supported in this integration."
        self.__hass.components.persistent_notification.create(notification, DOMAIN)
        _LOGGER.debug(notification)

    # This is not working>
    async def async_unlock(self, **kwargs):
        """Unlock all or specified locks. A code to unlock the lock with may optionally be specified."""
        # await self._lock.async_unlock()
        notification = "Locking and unlocking is not supported in this integration."
        self.__hass.components.persistent_notification.create(notification, DOMAIN)
        _LOGGER.debug(notification)

    async def async_update(self):
        """Fetch new state data for this sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("""Binary Locks doing a update.""")
        await self.__lock.async_update()
        self.__state = self.__lock.state
        self.__open_close_state = self.__lock.open_close_state
