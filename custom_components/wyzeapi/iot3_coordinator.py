"""DataUpdateCoordinator for Wyze DX-family devices via IoT3 API."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .iot3_service import Iot3Service

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class WyzeLockBoltV2Coordinator(DataUpdateCoordinator):
    """Coordinator for Wyze Lock Bolt v2 (DX_LB2) via IoT3 cloud API."""

    def __init__(
        self,
        hass: HomeAssistant,
        iot3_service: Iot3Service,
        lock,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=f"Wyze Lock Bolt V2 {lock.nickname}",
            update_interval=UPDATE_INTERVAL,
        )
        self._iot3_service = iot3_service
        self._lock = lock
        self._current_command: str | None = None

    async def _async_update_data(self) -> dict:
        """Poll IoT3 get-property for current lock state."""
        if self._current_command is not None:
            return self.data or {}

        try:
            result = await self._iot3_service.get_properties(self._lock.mac)
        except Exception as exc:
            raise UpdateFailed(f"Error fetching lock state: {exc}") from exc

        if result.get("code") != "1":
            raise UpdateFailed(
                f"IoT3 API returned error: {result.get('msg', 'unknown')}"
            )

        props = result.get("data", {}).get("props", {})
        return {
            "locked": props.get("lock::lock-status", None),
            "door_open": not props.get("lock::door-status", True),
            "online": props.get("iot-device::iot-state", False),
            "battery_level": props.get("battery::battery-level", None),
            "power_source": props.get("battery::power-source", None),
            "firmware_ver": props.get("device-info::firmware-ver", None),
        }

    async def lock_unlock(self, command: str):
        """Execute lock or unlock command."""
        self._current_command = command
        self.async_update_listeners()
        try:
            if command == "lock":
                result = await self._iot3_service.lock(self._lock.mac)
            else:
                result = await self._iot3_service.unlock(self._lock.mac)

            if result.get("code") != "1":
                _LOGGER.error(
                    "Lock %s command failed: %s",
                    command,
                    result.get("msg", "unknown"),
                )
        except Exception:
            _LOGGER.exception("Failed to %s lock %s", command, self._lock.nickname)
        finally:
            self._current_command = None
            await self.async_request_refresh()
