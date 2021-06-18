import logging
import time
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_DOOR
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from wyzeapy.base_client import Device
from wyzeapy.client import Client
from wyzeapy.types import Sensor, DeviceTypes, Event

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=1)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    _LOGGER.debug("""Creating new WyzeApi binary sensor component""")
    client: Client = hass.data[DOMAIN][config_entry.entry_id]

    cameras = [WyzeCameraMotion(client, camera) for camera in await client.get_cameras()]
    sensors = [WyzeSensor(client, sensor) for sensor in await client.get_sensors()]

    async_add_entities(cameras, True)
    async_add_entities(sensors, True)


class WyzeSensor(BinarySensorEntity):
    def __init__(self, wyzeapi_client: Client, device: Sensor):
        self._client = wyzeapi_client
        self._device = device
        self._last_event = int(str(int(time.time())) + "000")

    async def async_added_to_hass(self) -> None:
        await self._client.register_for_sensor_updates(self.process_update, self._device)

    def process_update(self, sensor: Sensor):
        if self._device != sensor:
            self._device = sensor

            self.schedule_update_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self.unique_id)
            },
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model
        }

    @property
    def available(self) -> bool:
        return True

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._device.nickname

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return True if self._device.activity_detected == 1 else False

    @property
    def unique_id(self):
        return "{}-motion".format(self._device.mac)

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "device model": self._device.product_model,
            "mac": self.unique_id
        }

    @property
    def device_class(self):
        if self._device.type is DeviceTypes.MOTION_SENSOR:
            return DEVICE_CLASS_MOTION
        elif self._device.type is DeviceTypes.CONTACT_SENSOR:
            return DEVICE_CLASS_DOOR
        else:
            raise RuntimeError(f"The device type {self._device.type} is not supported by this class")

    # async def async_update(self):
    #     self._device = await self._client.get_sensor_state(self._device)


class WyzeCameraMotion(BinarySensorEntity):
    def __init__(self, wyzeapi_client: Client, device: Device):
        self._client = wyzeapi_client
        self._device = device
        self._available = True
        self._on = False
        self._last_event = int(str(int(time.time())) + "000")

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._device.mac)
            },
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model
        }

    @property
    def available(self) -> bool:
        return self._available

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._device.nickname

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._on

    @property
    def unique_id(self):
        return "{}-motion".format(self._device.mac)

    @property
    def device_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "state": self.is_on,
            "available": self.available,
            "device model": self._device.product_model,
            "mac": self.unique_id
        }

    @property
    def device_class(self):
        return DEVICE_CLASS_MOTION

    # async def async_update(self):
    #     latest_event = await self._client.get_cached_latest_event(self._device)
    #     if latest_event is not None:
    #         if latest_event.event_ts > self._last_event:
    #             self._on = True
    #             self._last_event = latest_event.event_ts
    #         else:
    #             self._on = False
    #             self._last_event = latest_event.event_ts
    #     else:
    #         self._on = False

    async def async_added_to_hass(self) -> None:
        await self._client.register_for_event_updates(self.process_update, self._device)

    def process_update(self, event: Event):
        if event.event_ts > self._last_event:
            self._on = True
            self._last_event = event.event_ts
        else:
            self._on = False
            self._last_event = event.event_ts

        self.schedule_update_ha_state()
