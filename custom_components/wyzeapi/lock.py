#!/usr/bin/python3

"""Platform for binary_sensor integration."""
import logging
from datetime import timedelta
from .wyzeapi.wyzeapi import WyzeApi
from . import DOMAIN

import voluptuous as vol

import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED, ATTR_ATTRIBUTION
# Import the device class from the component that you want to support
from homeassistant.components.lock import LockEntity
#import homeassistant.components.lock.LockEntity
from homeassistant.core import callback

#Add to support quicker update time. Is this to Fast?
SCAN_INTERVAL = timedelta(seconds=5)

ATTRIBUTION = "Data provided by Wyze"
ATTR_STATE ="state"
ATTR_AVAILABLE = "available"
ATTR_DEVICE_MODEL = "device model"
ATTR_OPEN_CLOSE_STATE = "door"

ATTR_DOOR_STATE_OPEN = "open"
ATTR_DOOR_STATE_CLOSE = "closed"

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Wyze binary_sensor platform."""

    _LOGGER.debug("""Creating new WyzeApi Lock component""")
    async_add_entities([WyzeLock(lock) for lock in await hass.data[DOMAIN]["wyzeapi_account"].async_list_lock()], True)

class WyzeLock(LockEntity):
    """Representation of a Wyze binary_sensor."""

    def __init__(self, lock):
        """Initialize a Wyze binary_sensor."""
        self._lock = lock
        self._name = lock._friendly_name
        self._state = lock._state
        self._avaliable = True
        self._device_mac = lock._device_mac
        self._device_model = lock._device_model
        self._open_close_state = lock._open_close_state

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self._name

    @property
    def available(self):
        """Return the connection status of this sensor"""
        return self._avaliable

    @property
    def is_locked(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def unique_id(self):
        return self._device_mac

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATE : self._state,
            ATTR_AVAILABLE : self._avaliable,
            ATTR_DEVICE_MODEL : self._device_model,
            ATTR_OPEN_CLOSE_STATE : self.get_door_state()
        }
    def get_door_state(self):
        return ATTR_DOOR_STATE_OPEN if self._open_close_state == True else ATTR_DOOR_STATE_CLOSE

    @property
    def should_poll(self):
        """We always want to poll for sensors."""
        return True

#This is not working.
    async def async_lock(self, **kwargs):
        """Lock all or specified locks. A code to lock the lock with may optionally be specified."""
        await self._lock.async_lock()

#This is not working>
    async def async_unlock(self, **kwargs):
        """Unlock all or specified locks. A code to unlock the lock with may optionally be specified."""
        await self._lock.async_unlock()

    async def async_update(self):
        """Fetch new state data for this sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        _LOGGER.debug("""Binary Locks doing a update.""")
        await self._lock.async_update()
        self._state = self._lock._state
        self._open_close_state = self._lock._open_close_state
