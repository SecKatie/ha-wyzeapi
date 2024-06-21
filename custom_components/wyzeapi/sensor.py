#!/usr/bin/python3

"""Platform for sensor integration."""

import logging
import json
from typing import Any, Callable, List
from datetime import datetime

from wyzeapy import Wyzeapy
from wyzeapy.services.camera_service import Camera
from wyzeapy.services.lock_service import Lock
from wyzeapy.services.switch_service import Switch, SwitchUsageService

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    PERCENTAGE,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
)
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.entity_registry import async_get

from .const import CONF_CLIENT, DOMAIN, LOCK_UPDATED, CAMERA_UPDATED
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
CAMERAS_WITH_BATTERIES = ["WVOD1", "HL_WCO2", "AN_RSCW", "GW_BE1"]
OUTDOOR_PLUGS = ["WLPPO"]


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
    _LOGGER.debug("""Creating new WyzeApi sensor component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]

    # Get the list of locks so that we can create lock and keypad battery sensors
    lock_service = await client.lock_service
    camera_service = await client.camera_service
    switch_usage_service = await client.switch_usage_service

    locks = await lock_service.get_locks()
    sensors = []
    for lock in locks:
        sensors.append(WyzeLockBatterySensor(lock, WyzeLockBatterySensor.LOCK_BATTERY))
        sensors.append(
            WyzeLockBatterySensor(lock, WyzeLockBatterySensor.KEYPAD_BATTERY)
        )

    cameras = await camera_service.get_cameras()
    for camera in cameras:
        if camera.product_model in CAMERAS_WITH_BATTERIES:
            sensors.append(WyzeCameraBatterySensor(camera))

    plugs = await switch_usage_service.get_switches()
    for plug in plugs:
        if plug.product_model in OUTDOOR_PLUGS:
            sensors.append(WyzePlugEnergySensor(plug, switch_usage_service))
            sensors.append(WyzePlugDailyEnergySensor(plug))

    async_add_entities(sensors, True)


class WyzeLockBatterySensor(SensorEntity):
    """Representation of a Wyze Lock or Lock Keypad Battery"""

    @property
    def enabled(self):
        return self._enabled

    LOCK_BATTERY = "lock_battery"
    KEYPAD_BATTERY = "keypad_battery"

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE



    def __init__(self, lock, battery_type):
        self._enabled = None
        self._lock = lock
        self._battery_type = battery_type
        # make the battery unavailable by default, this will be toggled after the first update from the battery entity that
        # has battery data.
        self._available = False

    @callback
    def handle_lock_update(self, lock: Lock) -> None:
        """
        Helper function to
        Enable lock when Keypad has battery and
        Make it avaliable when either the lock battery or keypad battery exists
        """
        self._lock = lock
        if self._lock.raw_dict.get("power") and self._battery_type == self.LOCK_BATTERY:
            self._available = True
        if (
            self._lock.raw_dict.get("keypad", {}).get("power")
            and self._battery_type == self.KEYPAD_BATTERY
        ):
            if self.enabled is False:
                self.enabled = True
            self._available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LOCK_UPDATED}-{self._lock.mac}",
                self.handle_lock_update,
            )
        )

    @property
    def name(self) -> str:
        battery_type = self._battery_type.replace("_", " ").title()
        return f"{self._lock.nickname} {battery_type}"

    @property
    def unique_id(self):
        return f"{self._lock.nickname}.{self._battery_type}"

    @property
    def available(self) -> bool:
        return self._available

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def entity_registry_enabled_default(self) -> bool:
        if self._battery_type == self.KEYPAD_BATTERY:
            # The keypad battery may not be available if the lock has no keypad
            return False
        # The battery voltage will always be available for the lock
        return True

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._lock.mac)
            },
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._lock.mac,
                )
            },
            "name": f"{self._lock.nickname}.{self._battery_type}"
        }

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device model": f"{self._lock.product_model}.{self._battery_type}",
        }

    @property
    def native_value(self):
        """Return the state of the device."""
        if self._battery_type == self.LOCK_BATTERY:
            return str(self._lock.raw_dict.get("power"))
        elif self._battery_type == self.KEYPAD_BATTERY:
            return str(self._lock.raw_dict.get("keypad", {}).get("power"))
        return 0

    @enabled.setter
    def enabled(self, value):
        self._enabled = value


class WyzeCameraBatterySensor(SensorEntity):
    """Representation of a Wyze Camera Battery"""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, camera):
        self._camera = camera

    @callback
    def handle_camera_update(self, camera: Camera) -> None:
        self._camera = camera
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{CAMERA_UPDATED}-{self._camera.mac}",
                self.handle_camera_update,
            )
        )

    @property
    def name(self) -> str:
        return f"{self._camera.nickname} Battery"

    @property
    def unique_id(self):
        return f"{self._camera.nickname}.battery"

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._camera.mac)
            },
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._camera.mac,
                )
            },
            "name": f"{self._camera.nickname}.battery"
        }

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device model": f"{self._camera.product_model}.battery",
        }

    @property
    def native_value(self):
        return self._camera.device_params.get("electricity")


class WyzePlugEnergySensor(RestoreSensor):
    """Respresents an Outdoor Plug Total Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3
    _previous_hour = None
    _previous_value = None
    _past_hours_previous_value = None
    _current_value = 0
    _past_hours_value = 0
    _hourly_energy_usage_added = 0

    def __init__(
        self, switch: Switch, switch_usage_service: SwitchUsageService
    ) -> None:
        """Initialize an energy sensor."""
        self._switch = switch
        self._switch_usage_service = switch_usage_service
        self._switch.usage_history = None

    @property
    def name(self) -> str:
        """Get the name of the sensor."""
        return "Total Energy Usage"

    @property
    def unique_id(self):
        """Get the unique ID of the sensor."""
        return f"{self._switch.nickname}.energy-{self._switch.mac}"

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._switch.mac)},
            "name": self._switch.nickname,
        }

    def update_energy(self):
        """Update the energy sensor."""
        _now = int(datetime.utcnow().hour)
        self._hourly_energy_usage_added = 0

        if self._switch.usage_history and len(self._switch.usage_history) > 0:  # Confirm there is data
            _raw_data = self._switch.usage_history
            _LOGGER.debug(_raw_data)
            _current_day_list = json.loads(_raw_data[0]["data"])
            if _now == 0:  # Handle rolling to the next UTC day
                self._past_hours_value = _current_day_list[23] / 1000
                if len(_raw_data) > 1:  # New Day's value
                    _next_day_list = json.loads(_raw_data[1]["data"])
                    self._current_value = _next_day_list[_now] / 1000
                else:
                    self._current_value = 0
            else:
                self._past_hours_value = _current_day_list[_now - 1] / 1000
                self._current_value = _current_day_list[_now] / 1000

            # Set inital values to current values on startup.
            # Has to be done after we check for current or next UTC day
            if self._previous_hour is None:
                self._previous_hour = _now
            if self._past_hours_previous_value is None:
                self._past_hours_previous_value = self._past_hours_value
            if self._previous_value is None:
                self._previous_value = self._current_value

            if _now != self._previous_hour:  # New Hour
                if self._past_hours_value > self._previous_value:
                    self._hourly_energy_usage_added = (
                        self._past_hours_value - self._previous_value
                    )
                self._hourly_energy_usage_added += self._current_value
                self._previous_value = self._current_value
                self._previous_hour = _now
                self._past_hours_previous_value = self._past_hours_value

            else:  # Current Hour
                if self._current_value > self._previous_value:
                    self._hourly_energy_usage_added += round(
                        self._current_value - self._previous_value, 3
                    )
                    self._previous_value = self._current_value

                if self._past_hours_value > self._past_hours_previous_value:
                    self._hourly_energy_usage_added += round(
                        self._past_hours_value - self._past_hours_previous_value, 3
                    )
                    self._past_hours_previous_value = self._past_hours_value

            _LOGGER.debug(
                "Total Value Added to device %s is %s",
                self._switch.mac,
                self._hourly_energy_usage_added,
            )

        return self._hourly_energy_usage_added

    @callback
    def async_update_callback(self, switch: Switch):
        """Update the sensor's state."""
        self._switch = switch
        self.update_energy()
        self._attr_native_value += self._hourly_energy_usage_added
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register Updater for the sensor and get previous data."""
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value
        else:
            self._attr_native_value = 0
        self._switch.callback_function = self.async_update_callback
        self._switch_usage_service.register_updater(
            self._switch, 120
        )  # Every 2 minutes seems to work fine, probably could be longer
        await self._switch_usage_service.start_update_manager()

    async def async_will_remove_from_hass(self) -> None:
        """Remove updater."""
        self._switch_usage_service.unregister_updater(self._switch)


class WyzePlugDailyEnergySensor(RestoreSensor):
    """Respresents an Outdoor Plug Daily Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    def __init__(self, switch: Switch) -> None:
        """Initialize a daily energy sensor."""
        self._switch = switch

    @property
    def name(self) -> str:
        """Get the name of the sensor."""
        return "Daily Energy Usage"

    @property
    def unique_id(self):
        """Get the unique ID of the sensor."""
        return f"{self._switch.nickname}.daily_energy-{self._switch.mac}"

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._switch.mac)},
            "name": self._switch.nickname,
        }

    @callback
    def _update_daily_sensor(self, event):
        """Update the sensor when the total sensor updates."""
        event_data = event.data
        new_state = event_data["new_state"]
        old_state = event_data["old_state"]

        if not old_state or not new_state:
            return

        updated_energy = (float(new_state.state) - float(old_state.state))
        self._attr_native_value += updated_energy
        self.async_write_ha_state()

    async def _async_reset_at_midnight(self, now: datetime):
        """Reset the daily sensor."""
        self._attr_native_value = 0
        _LOGGER.debug("Resetting daily energy sensor %s to 0", self._switch.mac)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Get previous data and add listeners."""

        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value
        else:
            self._attr_native_value = 0

        registry = async_get(self.hass)
        entity_id_total_sensor = registry.async_get_entity_id("sensor", DOMAIN, f"{self._switch.nickname}.energy-{self._switch.mac}")

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [entity_id_total_sensor],
                self._update_daily_sensor
            )
        )

        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._async_reset_at_midnight,
                hour=0, minute=0, second=0
            )
        )
