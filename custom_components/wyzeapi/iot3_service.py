"""IoT3 API service for Wyze DX-family devices (Lock Bolt v2, Palm Lock).

Originally written by @zrikzlok for PR #809. The access token is taken from
wyzeapy's auth layer and refreshed before every request, so it keeps working
once the cached token ages out.

DX-family devices report product_type "Common", so wyzeapy's get_locks() never
returns them. They are found by product_model in the full device list and driven
through Wyze's IoT3 cloud API rather than the Yunding lock endpoints.
"""

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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    IOT3_APP_HOST,
    IOT3_APP_VERSION,
    IOT3_GET_PROPERTY_PATH,
    IOT3_RUN_ACTION_PATH,
    OLIVE_APP_ID,
    OLIVE_APP_INFO,
    OLIVE_SIGNING_SECRET,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_PROPS = [
    "lock::lock-status",
    "lock::door-status",
    "iot-device::iot-state",
    "battery::battery-level",
    "battery::power-source",
    "device-info::firmware-ver",
]


class Iot3Service:
    """Client for the Wyze IoT3 API used by DX-family devices."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, client):
        self._hass = hass
        self._config_entry = config_entry
        self._client = client  # wyzeapy.Wyzeapy - owns auth and token refresh
        self._phone_id = str(uuid.uuid4())
        self._session = async_get_clientsession(hass)

    @property
    def username(self) -> str:
        return self._config_entry.data.get(CONF_USERNAME, "")

    async def _get_access_token(self) -> str:
        """Always go through wyzeapy's auth layer so an aged-out token is
        refreshed rather than used and rejected."""
        auth_lib = getattr(self._client, "_auth_lib", None)
        if auth_lib is None or getattr(auth_lib, "token", None) is None:
            raise HomeAssistantError(
                "Wyze IoT3: no authenticated client available; reload the integration"
            )
        await auth_lib.refresh_if_should()
        return auth_lib.token.access_token

    @staticmethod
    def _compute_signature(access_token: str, body: str) -> str:
        access_key = access_token + OLIVE_SIGNING_SECRET
        secret = hashlib.md5(access_key.encode()).hexdigest()
        return hmac.new(secret.encode(), body.encode(), hashlib.md5).hexdigest()

    def _build_headers(self, access_token: str, body: str) -> dict:
        return {
            "access_token": access_token,
            "appid": OLIVE_APP_ID,
            "appinfo": OLIVE_APP_INFO,
            "appversion": IOT3_APP_VERSION,
            "env": "Prod",
            "phoneid": self._phone_id,
            "requestid": uuid.uuid4().hex,
            "Signature2": self._compute_signature(access_token, body),
            "Content-Type": "application/json; charset=utf-8",
        }

    async def _post(self, path: str, payload: dict) -> dict:
        access_token = await self._get_access_token()
        body = json.dumps(payload)
        headers = self._build_headers(access_token, body)
        url = f"{IOT3_APP_HOST}{path}"
        try:
            async with self._session.post(url, headers=headers, data=body) as resp:
                result = await resp.json()
        except Exception as exc:  # noqa: BLE001 - surfaced by the caller
            _LOGGER.error("IoT3 request to %s failed: %s", path, exc)
            raise
        if str(result.get("code")) != "1":
            _LOGGER.debug(
                "IoT3 %s returned code=%s msg=%s",
                path,
                result.get("code"),
                result.get("msg"),
            )
        return result

    async def get_properties(
        self, device_mac: str, model: str, props: list[str] | None = None
    ) -> dict:
        """Read device properties. `model` comes from the device's product_model
        rather than being parsed out of the MAC, so a device whose MAC is not
        prefixed with its model still works."""
        ts = int(time.time() * 1000)
        payload = {
            "nonce": str(ts),
            "payload": {
                "cmd": "get_property",
                "props": list(props or DEFAULT_PROPS),
                "tid": random.randint(1000, 99999),
                "ts": ts,
                "ver": 1,
            },
            "targetInfo": {"id": device_mac, "model": model},
        }
        return await self._post(IOT3_GET_PROPERTY_PATH, payload)

    async def run_action(self, device_mac: str, model: str, action: str) -> dict:
        """Run an action such as `lock::lock` or `lock::unlock`."""
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
            "targetInfo": {"id": device_mac, "model": model},
        }
        return await self._post(IOT3_RUN_ACTION_PATH, payload)

    async def lock(self, device_mac: str, model: str) -> dict:
        return await self.run_action(device_mac, model, "lock::lock")

    async def unlock(self, device_mac: str, model: str) -> dict:
        return await self.run_action(device_mac, model, "lock::unlock")
