"""
This module describes the connection between Home Assistant and Wyze for the Sensors
"""

import logging
import time
from typing import Callable, List, Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_change
from datetime import datetime
from wyzeapy import Wyzeapy, CameraService, SensorService
from wyzeapy.services.camera_service import Camera
from wyzeapy.services.sensor_service import Sensor
from wyzeapy.services.irrigation_service import IrrigationService, Irrigation
from wyzeapy.types import DeviceTypes
from .token_manager import token_exception_handler

from .const import DOMAIN, CONF_CLIENT

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Any], bool], None],
):
    """
    This function sets up the config entry for use in Home Assistant

    :param hass: Home Assistant instance
    :param config_entry: The current config_entry
    :param async_add_entities: This function adds entities to the config_entry
    :return:
    """

    _LOGGER.debug("""Creating new WyzeApi binary sensor component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]

    sensor_service = await client.sensor_service
    camera_service = await client.camera_service
    irrigation_service = await client.irrigation_service

    cameras = [
        WyzeCameraMotion(camera_service, camera)
        for camera in await camera_service.get_cameras()
    ]
    sensors = [
        WyzeSensor(sensor_service, sensor)
        for sensor in await sensor_service.get_sensors()
    ]

    # Get all irrigation devices and create zone running binary sensors
    irrigation_devices = await irrigation_service.get_irrigations()
    irrigation_sensors = []
    for device in irrigation_devices:
        # Update the device to get its zones
        device = await irrigation_service.update(device)
        # Add zone running sensors for each zone
        for zone in device.zones:
            zone_sensor = WyzeIrrigationZoneRunning(
                irrigation_service, 
                device, 
                zone.zone_number, 
                zone.name
            )
            irrigation_sensors.append(zone_sensor)

    async_add_entities(cameras, True)
    async_add_entities(sensors, True)
    async_add_entities(irrigation_sensors, True)


class WyzeSensor(BinarySensorEntity):
    """
    A representation of the WyzeSensor for use in Home Assistant
    """

    def __init__(self, sensor_service: SensorService, sensor: Sensor):
        """Initializes the class"""
        self._sensor_service = sensor_service
        self._sensor = sensor
        self._last_event = int(str(int(time.time())) + "000")

    async def async_added_to_hass(self) -> None:
        """Registers for updates when the entity is added to Home Assistant"""
        await self._sensor_service.register_for_updates(
            self._sensor, self.process_update
        )

    async def async_will_remove_from_hass(self) -> None:
        await self._sensor_service.deregister_for_updates(self._sensor)

    def process_update(self, sensor: Sensor):
        """
        This function processes an update for the Wyze Sensor

        :param sensor: The sensor with the updated values
        """
        self._sensor = sensor
        self.schedule_update_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._sensor.mac)},
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._sensor.product_model,
        }

    @property
    def available(self) -> bool:
        return True

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._sensor.nickname

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def is_on(self):
        """Return true if sensor detects motion"""
        return self._sensor.detected

    @property
    def unique_id(self):
        return "{}-motion".format(self._sensor.mac)

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device model": self._sensor.product_model,
            "mac": self.unique_id,
        }

    @property
    def device_class(self):
        # pylint: disable=R1705
        if self._sensor.type is DeviceTypes.MOTION_SENSOR:
            return BinarySensorDeviceClass.MOTION
        elif self._sensor.type is DeviceTypes.CONTACT_SENSOR:
            return BinarySensorDeviceClass.DOOR
        else:
            raise RuntimeError(
                f"The device type {self._sensor.type} is not supported by this class"
            )


class WyzeCameraMotion(BinarySensorEntity):
    """
    A representation of the Wyze Camera for use as a binary sensor in Home Assistant
    """

    _is_on = False
    _last_event = time.time() * 1000

    def __init__(self, camera_service: CameraService, camera: Camera):
        self._camera_service = camera_service
        self._camera = camera

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._camera.mac)},
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._camera.product_model,
        }

    @property
    def available(self) -> bool:
        return self._camera.available

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._camera.nickname

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def is_on(self):
        """Return true if the binary sensor is on"""
        return self._is_on

    @property
    def unique_id(self):
        return "{}-motion".format(self._camera.mac)

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device model": self._camera.product_model,
            "mac": self.unique_id,
        }

    @property
    def device_class(self):
        return BinarySensorDeviceClass.MOTION

    async def async_added_to_hass(self) -> None:
        await self._camera_service.register_for_updates(
            self._camera, self.process_update
        )

    async def async_will_remove_from_hass(self) -> None:
        await self._camera_service.deregister_for_updates(self._camera)

    @token_exception_handler
    def process_update(self, camera: Camera) -> None:
        """
        Is called by the update worker for events to update the values in this sensor

        :param camera: An updated version of the current camera
        """
        self._camera = camera

        if camera.last_event_ts > self._last_event:
            self._is_on = True
            self._last_event = camera.last_event_ts
        else:
            self._is_on = False
            self._last_event = camera.last_event_ts

        self.schedule_update_ha_state()


class WyzeIrrigationZoneRunning(BinarySensorEntity):
    """Representation of a Wyze Irrigation Zone Running binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, irrigation_service: IrrigationService, irrigation: Irrigation, zone_number: int, zone_name: str) -> None:
        """Initialize the irrigation zone running sensor."""
        self._irrigation_service = irrigation_service
        self._device = irrigation
        self._zone_number = zone_number
        self._zone_name = zone_name
        self._running = False

    @property
    def name(self) -> str:
        """Return the name of the zone."""
        return f"{self._zone_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the zone."""
        return f"Running {self._device.mac}-zone-{self._zone_number}"

    @property
    def is_on(self) -> bool:
        """Return true if the zone is running."""
        return self._running

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.mac)},
            name=self._device.nickname,
            manufacturer="WyzeLabs",
            model=self._device.product_model,
            serial_number=self._device.sn,
            connections={(dr.CONNECTION_NETWORK_MAC, self._device.mac)},
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        return {
            "zone_number": self._zone_number,
            "zone_name": self._zone_name,
        }

    async def async_update(self) -> None:
        """Update the sensor state."""
        try:
            schedule_data = await self._irrigation_service.get_schedule_runs(self._device)
            # Check if this specific zone is running
            if schedule_data.get("running", False):
                running_zone_number = schedule_data.get("zone_number")
                self._running = running_zone_number == self._zone_number
            else:
                self._running = False
        except Exception as e:
            _LOGGER.error("Failed to update zone running status for device %s zone %s: %s", 
                         self._device.mac, self._zone_number, str(e))
            self._running = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates and set up periodic updates."""
        # Set up periodic updates every minute for zone running status
        self._unsub_periodic = async_track_time_change(
            self.hass, 
            self._async_periodic_update, 
            second=0  # Update every minute at second 0
        )
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed."""
        if hasattr(self, '_unsub_periodic') and self._unsub_periodic:
            self._unsub_periodic()
        return await super().async_will_remove_from_hass()

    @callback
    def _async_periodic_update(self, now: datetime) -> None:
        """Handle periodic updates."""
        self.hass.async_create_task(self.async_update())
        self.async_schedule_update_ha_state()
