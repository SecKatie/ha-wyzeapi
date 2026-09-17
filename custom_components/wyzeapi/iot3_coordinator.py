"""DataUpdateCoordinator for Wyze DX-family locks over the IoT3 API.

Originally written by @zrikzlok for PR #809. A lock or unlock the API rejects
raises HomeAssistantError, so a service call fails visibly instead of returning
success while the door never moved.
"""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .iot3_service import Iot3Service

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class WyzeIot3LockCoordinator(DataUpdateCoordinator):
    """Polls one DX-family lock (DX_LB2, DX_PVLOC) through the IoT3 cloud API."""

    def __init__(self, hass: HomeAssistant, iot3_service: Iot3Service, lock):
        super().__init__(
            hass,
            _LOGGER,
            name=f"Wyze {lock.product_model} {lock.nickname}",
            update_interval=UPDATE_INTERVAL,
        )
        self._iot3_service = iot3_service
        self._lock = lock
        self._current_command: str | None = None

    @property
    def device(self):
        """The wyzeapy Device this coordinator drives."""
        return self._lock

    async def _async_update_data(self) -> dict:
        if self._current_command is not None:
            # a command is in flight; keep the optimistic state until it settles
            return self.data or {}

        try:
            result = await self._iot3_service.get_properties(
                self._lock.mac, self._lock.product_model
            )
        except Exception as exc:  # noqa: BLE001
            raise UpdateFailed(f"IoT3 poll failed: {exc}") from exc

        if str(result.get("code")) != "1":
            raise UpdateFailed(
                f"IoT3 returned code={result.get('code')} msg={result.get('msg', 'unknown')}"
            )

        props = result.get("data", {}).get("props", {}) or {}
        return {
            "locked": props.get("lock::lock-status"),
            "door_open": (
                None
                if props.get("lock::door-status") is None
                else not props.get("lock::door-status")
            ),
            "online": props.get("iot-device::iot-state", False),
            "battery_level": props.get("battery::battery-level"),
            "power_source": props.get("battery::power-source"),
            "firmware_ver": props.get("device-info::firmware-ver"),
        }

    async def lock_unlock(self, command: str) -> None:
        """Lock or unlock.

        A request the API rejects raises, so a service call fails visibly
        instead of reporting success while the bolt never moved.

        On success the commanded state is written straight into the coordinator's
        data so the entity flips at once. Without that the entity keeps its old
        state until the next scheduled poll - about 30 s on my locks - with no
        in-progress hint in between. The poll that follows confirms it, or
        corrects it if the bolt did not actually move (a jam or a tight strike
        plate), so the optimistic value is never the last word.
        """
        if command not in ("lock", "unlock"):
            raise HomeAssistantError(f"Unknown lock command {command!r}")

        self._current_command = command
        self.async_update_listeners()
        try:
            call = self._iot3_service.lock if command == "lock" else self._iot3_service.unlock
            result = await call(self._lock.mac, self._lock.product_model)
        except HomeAssistantError:
            self._current_command = None
            await self.async_request_refresh()
            raise
        except Exception as exc:  # noqa: BLE001
            self._current_command = None
            await self.async_request_refresh()
            raise HomeAssistantError(
                f"Wyze {command} request failed for {self._lock.nickname}: {exc}"
            ) from exc

        self._current_command = None

        if str(result.get("code")) != "1":
            await self.async_request_refresh()
            raise HomeAssistantError(
                f"Wyze rejected the {command} request for {self._lock.nickname}: "
                f"code={result.get('code')} msg={result.get('msg', 'unknown')}"
            )

        # accepted: reflect it now; the next scheduled poll reconciles with the device
        data = dict(self.data or {})
        data["locked"] = command == "lock"
        self.async_set_updated_data(data)
