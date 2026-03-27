"""IoT3 API service for Wyze DX-family devices (Lock Bolt v2, Palm Lock, etc.)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import random
import time
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ACCESS_TOKEN,
    IOT3_APP_HOST,
    IOT3_GET_PROPERTY_PATH,
    IOT3_RUN_ACTION_PATH,
    OLIVE_APP_ID,
    OLIVE_APP_INFO,
    OLIVE_SIGNING_SECRET,
)

_LOGGER = logging.getLogger(__name__)


class Iot3Service:
    """Client for the Wyze IoT3 API (DX-family devices)."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        self._hass = hass
        self._config_entry = config_entry
        self._phone_id = str(uuid.uuid4())
        self._session = async_get_clientsession(hass)

    @property
    def _access_token(self) -> str:
        return self._config_entry.data.get(ACCESS_TOKEN, "")

    @property
    def username(self) -> str:
        return self._config_entry.data.get(CONF_USERNAME, "")

    def _compute_signature(self, body: str) -> str:
        access_key = self._access_token + OLIVE_SIGNING_SECRET
        secret = hashlib.md5(access_key.encode()).hexdigest()
        return hmac.new(secret.encode(), body.encode(), hashlib.md5).hexdigest()

    def _build_headers(self, body: str) -> dict:
        return {
            "access_token": self._access_token,
            "appid": OLIVE_APP_ID,
            "appinfo": OLIVE_APP_INFO,
            "appversion": "3.11.0.758",
            "env": "Prod",
            "phoneid": self._phone_id,
            "requestid": uuid.uuid4().hex,
            "Signature2": self._compute_signature(body),
            "Content-Type": "application/json; charset=utf-8",
        }

    @staticmethod
    def _extract_model(device_mac: str) -> str:
        """Extract model from MAC (e.g., DX_LB2_80482C9C659C -> DX_LB2)."""
        parts = device_mac.split("_")
        if len(parts) >= 3:
            return "_".join(parts[:2])
        return device_mac

    async def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload)
        headers = self._build_headers(body)
        url = f"{IOT3_APP_HOST}{path}"
        try:
            async with self._session.post(url, headers=headers, data=body) as resp:
                result = await resp.json()
                if result.get("code") != "1":
                    _LOGGER.warning(
                        "IoT3 API error on %s: code=%s msg=%s",
                        path,
                        result.get("code"),
                        result.get("msg"),
                    )
                return result
        except Exception as exc:
            _LOGGER.error("IoT3 API request failed for %s: %s", path, exc)
            raise

    async def get_properties(
        self,
        device_mac: str,
        props: list[str] | None = None,
    ) -> dict:
        """Get device properties via IoT3 get-property endpoint."""
        if props is None:
            props = [
                "lock::lock-status",
                "lock::door-status",
                "iot-device::iot-state",
                "battery::battery-level",
                "battery::power-source",
                "device-info::firmware-ver",
            ]

        ts = int(time.time() * 1000)
        payload = {
            "nonce": str(ts),
            "payload": {
                "cmd": "get_property",
                "props": props,
                "tid": random.randint(1000, 99999),
                "ts": ts,
                "ver": 1,
            },
            "targetInfo": {
                "id": device_mac,
                "model": self._extract_model(device_mac),
            },
        }
        return await self._post(IOT3_GET_PROPERTY_PATH, payload)

    async def run_action(
        self,
        device_mac: str,
        action: str,
    ) -> dict:
        """Run an action (e.g., lock::lock, lock::unlock) via IoT3 run-action endpoint."""
        ts = int(time.time() * 1000)
        payload = {
            "nonce": str(ts),
            "payload": {
                "action": action,
                "cmd": "run_action",
                "params": {
                    "action_id": random.randint(10000, 99999),
                    "type": 1,
                    "username": self.username,
                },
                "tid": random.randint(1000, 99999),
                "ts": ts,
                "ver": 1,
            },
            "targetInfo": {
                "id": device_mac,
                "model": self._extract_model(device_mac),
            },
        }
        return await self._post(IOT3_RUN_ACTION_PATH, payload)

    async def lock(self, device_mac: str) -> dict:
        """Lock the device."""
        return await self.run_action(device_mac, "lock::lock")

    async def unlock(self, device_mac: str) -> dict:
        """Unlock the device."""
        return await self.run_action(device_mac, "lock::unlock")
