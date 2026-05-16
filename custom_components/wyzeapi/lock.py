#!/usr/bin/python3

"""Platform for lock integration."""

from abc import ABC
from datetime import timedelta
import logging
from typing import Any, Callable, List
from aiohttp.client_exceptions import ClientConnectionError

from wyzeapy import LockService, Wyzeapy
from wyzeapy.services.lock_service import Lock
from wyzeapy.types import DeviceTypes
from wyzeapy.exceptions import AccessTokenError, ParameterError, UnknownApiError

import homeassistant.components.lock
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_CLIENT, DOMAIN, LOCK_UPDATED
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=10)
MAX_OUT_OF_SYNC_COUNT = 5


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Any], bool], None],
) -> None:
    """
    This function sets up the config_entry

    :param hass: Home Assistant instance
    :param config_entry: The current config_entry
    :param async_add_entities: This function adds entities to the config_entry
    :return:
    """

    _LOGGER.debug("""Creating new WyzeApi lock component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    lock_service = await client.lock_service

    all_locks = await lock_service.get_locks()

    locks = [
        WyzeLock(lock_service, lock)
        for lock in all_locks
        if lock.product_model not in ["YD_BT1", "DX_LB2"]
    ]

    lock_bolts = []
    coordinators = hass.data[DOMAIN][config_entry.entry_id].get("coordinators", {})
    for lock in all_locks:
        if lock.product_model == "YD_BT1":
            coordinator = coordinators.get(lock.mac)
            if coordinator is None:
                _LOGGER.warning(
                    "No coordinator found for Lock Bolt %s (%s), skipping",
                    lock.nickname,
                    lock.mac,
                )
                continue
            lock_bolts.append(WyzeLockBolt(coordinator))

    lock_bolt_v2s = [
        WyzeLockBoltV2(lock_service, lock)
        for lock in all_locks
        if lock.product_model == "DX_LB2"
    ]

    async_add_entities(locks + lock_bolts + lock_bolt_v2s, True)


class WyzeLock(homeassistant.components.lock.LockEntity, ABC):
    """Representation of a Wyze Lock."""

    def __init__(self, lock_service: LockService, lock: Lock):
        """Initialize a Wyze lock."""
        self._lock = lock
        if self._lock.type not in [DeviceTypes.LOCK]:
            raise AttributeError("Device type not supported")

        self._lock_service = lock_service

        self._out_of_sync_count = 0

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._lock.mac)},
            "name": self._lock.nickname,
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._lock.mac,
                )
            },
            "manufacturer": "WyzeLabs",
            "model": self._lock.product_model,
        }

    def lock(self, **kwargs):
        raise NotImplementedError

    def unlock(self, **kwargs):
        raise NotImplementedError

    @property
    def should_poll(self) -> bool:
        return False

    @token_exception_handler
    async def async_lock(self, **kwargs):
        _LOGGER.debug("Turning on lock")
        try:
            await self._lock_service.lock(self._lock)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._lock.unlocked = False
            self.async_schedule_update_ha_state()

    @token_exception_handler
    async def async_unlock(self, **kwargs):
        try:
            await self._lock_service.unlock(self._lock)
        except (AccessTokenError, ParameterError, UnknownApiError) as err:
            raise HomeAssistantError(f"Wyze returned an error: {err.args}") from err
        except ClientConnectionError as err:
            raise HomeAssistantError(err) from err
        else:
            self._lock.unlocked = True
            self.async_schedule_update_ha_state()

    @property
    def is_locked(self):
        return not self._lock.unlocked

    @property
    def name(self):
        """Return the display name of this lock."""
        return self._lock.nickname

    @property
    def unique_id(self):
        return self._lock.mac

    @property
    def available(self):
        """Return the connection status of this lock"""
        return self._lock.available

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        dev_info = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "door_open": self._lock.door_open,
        }

        # Add the lock battery value if it exists
        if self._lock.raw_dict.get("power"):
            dev_info["lock_battery"] = str(self._lock.raw_dict.get("power"))

        # Add the keypad's battery value if it exists
        if self._lock.raw_dict.get("keypad", {}).get("power"):
            dev_info["keypad_battery"] = str(
                self._lock.raw_dict.get("keypad", {}).get("power")
            )

        return dev_info

    @property
    def supported_features(self):
        return None

    @token_exception_handler
    async def async_update(self):
        """
        This function updates the entity
        """
        lock = await self._lock_service.update(self._lock)
        if (
            lock.unlocked == self._lock.unlocked
            or self._out_of_sync_count >= MAX_OUT_OF_SYNC_COUNT
        ):
            self._lock = lock
            self._out_of_sync_count = 0
        else:
            self._out_of_sync_count += 1

    @callback
    def async_update_callback(self, lock: Lock):
        """Update the switch's state."""
        self._lock = lock
        async_dispatcher_send(
            self.hass,
            f"{LOCK_UPDATED}-{self._lock.mac}",
            lock,
        )
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to update events."""
        self._lock.callback_function = self.async_update_callback
        self._lock_service.register_updater(self._lock, 10)
        await self._lock_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        self._lock_service.unregister_updater(self._lock)


class WyzeLockBoltV2(homeassistant.components.lock.LockEntity):
    """Representation of a Wyze Lock Bolt v2 (DX_LB2).

    This device uses the devicemgmt API for state monitoring.
    Lock/unlock control is not yet supported.
    """

    def __init__(self, lock_service: LockService, lock: Lock):
        """Initialize a Wyze Lock Bolt v2."""
        self._lock = lock
        self._lock_service = lock_service
        self._out_of_sync_count = 0

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._lock.mac)},
            "name": self._lock.nickname,
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._lock.mac,
                )
            },
            "manufacturer": "WyzeLabs",
            "model": self._lock.product_model,
        }

    @property
    def name(self):
        """Return the display name of this lock."""
        return self._lock.nickname

    @property
    def unique_id(self):
        return self._lock.mac

    @property
    def available(self):
        """Return the connection status of this lock."""
        return self._lock.available

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return not self._lock.unlocked

    @property
    def is_locking(self):
        return self._lock.locking

    @property
    def is_unlocking(self):
        return self._lock.unlocking

    @property
    def supported_features(self):
        return None

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        dev_info = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        if self._lock.battery_level is not None:
            dev_info["battery_level"] = self._lock.battery_level
        return dev_info

    def lock(self, **kwargs):
        raise NotImplementedError

    def unlock(self, **kwargs):
        raise NotImplementedError

    async def async_lock(self, **kwargs):
        raise HomeAssistantError(
            "Lock control is not yet supported for the Wyze Lock Bolt v2."
        )

    async def async_unlock(self, **kwargs):
        raise HomeAssistantError(
            "Unlock control is not yet supported for the Wyze Lock Bolt v2."
        )

    @token_exception_handler
    async def async_update(self):
        """Update the lock state from the devicemgmt API."""
        try:
            lock = await self._lock_service.update(self._lock)
            if (
                lock.unlocked == self._lock.unlocked
                or self._out_of_sync_count >= MAX_OUT_OF_SYNC_COUNT
            ):
                self._lock = lock
                self._out_of_sync_count = 0
            else:
                self._out_of_sync_count += 1
        except Exception as err:
            _LOGGER.error("Error updating Wyze Lock Bolt v2: %s", err)

    async def async_added_to_hass(self) -> None:
        """Register update callbacks."""
        self._lock_service.register_updater(self._lock, 10)
        await self._lock_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        self._lock_service.unregister_updater(self._lock)


class WyzeLockBolt(CoordinatorEntity, homeassistant.components.lock.LockEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._lock = coordinator._lock

    @property
    def name(self):
        """Return the display name of this lock."""
        return self._lock.nickname

    @property
    def unique_id(self):
        return self._lock.mac

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._lock.mac)},
            "name": self._lock.nickname,
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self.coordinator._mac,
                ),
                ("uuid", self.coordinator._uuid),
                ("serial_number", self._lock.raw_dict["hardware_info"]["sn"]),
            },
            "manufacturer": "WyzeLabs",
            "model": self._lock.product_model,
        }

    @property
    def is_locked(self):
        return self.coordinator.data["state"] == 1

    async def async_lock(self, **kwargs):
        return await self.coordinator.lock_unlock(command="lock")

    async def async_unlock(self, **kwargs):
        return await self.coordinator.lock_unlock(command="unlock")

    @property
    def is_locking(self, **kwargs):
        return self.coordinator._current_command == "lock"

    @property
    def is_unlocking(self, **kwargs):
        return self.coordinator._current_command == "unlock"

    @property
    def state_attributes(self):
        return {"last_operated": self.coordinator.data["timestamp"]}