import logging
import time
from datetime import timedelta

from homeassistant.const import ATTR_ATTRIBUTION
from wyzeapy.base_client import DeviceTypes, Device, AccessTokenError, PropertyIDs
from wyzeapy.client import Client
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    DEVICE_CLASS_MOTION
)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SCAN_INTERVAL = timedelta(seconds=10)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    _ = config
    # We only want this platform to be set up via discovery.
    if discovery_info is None:
        return

    _LOGGER.debug("""Creating new WyzeApi binary_sensor component""")
    wyzeapi_client: Client = hass.data[DOMAIN]['wyzeapi_client']
    devices = hass.data[DOMAIN]['devices']

    cameras = []
    for device in devices:
        try:
            device_type = DeviceTypes(device.product_type)
            if device_type == DeviceTypes.CAMERA:
                cameras.append(WyzeCameraMotion(wyzeapi_client, device))
        except ValueError as e:
            _LOGGER.warning("{}: Please report this error to https://github.com/JoshuaMulliken/ha-wyzeapi".format(e))

    add_entities(cameras, True)


class WyzeCameraMotion(BinarySensorEntity):
    _on: bool
    _available: bool

    def __init__(self, wyzeapi_client: Client, device: Device):
        self._client = wyzeapi_client
        self._device = device
        self._last_event = int(str(int(time.time())) + "000")

    @property
    def available(self) -> bool:
        return self._available

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._device.nickname

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._on

    @property
    def unique_id(self):
        return self._device.mac

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

    def update(self):
        try:
            device_info = self._client.get_info(self._device)
        except AccessTokenError:
            self._client.reauthenticate()
            device_info = self._client.get_info(self._device)

        for property_id, value in device_info:
            if property_id == PropertyIDs.AVAILABLE:
                self._available = True if value == "1" else False

        latest_event = self._client.get_latest_event(self._device)
        if latest_event is not None:
            if latest_event.event_ts > self._last_event:
                self._on = True
                self._last_event = latest_event.event_ts
            else:
                self._on = False
                self._last_event = latest_event.event_ts
        else:
            self._on = False


