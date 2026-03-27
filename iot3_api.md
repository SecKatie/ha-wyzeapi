# Wyze IoT3 API - Lock Bolt v2 (DX_LB2) & New Device Family

> **Reverse-engineered March 26, 2026.** This API is unofficial and subject to change.
> Applies to the Wyze Lock Bolt v2 (`DX_LB2`) and likely the Wyze Palm Lock (`DX_PVLOC`) and other `DX_` prefix devices.

## Overview

Wyze introduced a new **IoT3 API** (`/app/v4/iot3/`) for their next-generation "DX" device family. This API is completely separate from the legacy APIs used by older Wyze devices:

| Legacy API | Used By | Base URL |
|------------|---------|----------|
| Ford/Yunding | Original Wyze Lock (`YD.LO1`) | `yd-saas-toc.wyzecam.com` |
| Olive/Earth | Thermostats, Switches | `wyze-earth-service.wyzecam.com` |
| Standard v2 | Cameras, Plugs, Bulbs | `api.wyzecam.com/app/v2/` |
| BLE (Bleak) | Lock Bolt v1 (`YD_BT1`) | Direct Bluetooth |
| **IoT3 (NEW)** | **Lock Bolt v2 (`DX_LB2`), Palm Lock (`DX_PVLOC`)** | **`app.wyzecam.com/app/v4/iot3/`** |

### Key Characteristics

- **Base URL**: `https://app.wyzecam.com`
- **API Path Prefix**: `/app/v4/iot3/`
- **Auth**: Olive-style HMAC-MD5 signature
- **Property Format**: `namespace::property` (e.g., `lock::lock-status`, `battery::battery-level`)
- **Action Format**: `namespace::action` (e.g., `lock::lock`, `lock::unlock`)
- **Device Targeting**: Uses `targetInfo` with device `id` (MAC) and `model`

---

## Authentication

### Step 1: Login (get access token)

```bash
curl -s -X POST "https://auth-prod.api.wyze.com/api/user/login" \
  -H "Content-Type: application/json" \
  -H "keyid: YOUR_KEY_ID" \
  -H "apikey: YOUR_API_KEY" \
  -d '{
    "email": "YOUR_EMAIL",
    "password": "TRIPLE_MD5_HASHED_PASSWORD"
  }'
```

**Password hashing** (triple MD5):
```
step1 = md5("your_plaintext_password")
step2 = md5(step1)
final = md5(step2)
```

**Get your KEY_ID and API_KEY** from https://developer-api-console.wyze.com/

**Response:**
```json
{
  "access_token": "eyJhbG...",
  "refresh_token": "eyJhbG..."
}
```

### Step 2: Compute Signature2

Every IoT3 API request requires a `Signature2` header computed as:

```
signing_secret = "wyze_app_secret_key_132"
access_key = access_token + signing_secret
secret = MD5(access_key)
Signature2 = HMAC-MD5(key=secret, message=raw_json_request_body)
```

**Python example:**
```python
import hashlib, hmac, json

def compute_signature(access_token: str, request_body: str) -> str:
    signing_secret = "wyze_app_secret_key_132"
    access_key = access_token + signing_secret
    secret = hashlib.md5(access_key.encode()).hexdigest()
    return hmac.new(secret.encode(), request_body.encode(), hashlib.md5).hexdigest()

# Usage
payload = json.dumps(your_payload_dict)
sig = compute_signature(your_access_token, payload)
```

### Required Headers

| Header | Value | Description |
|--------|-------|-------------|
| `access_token` | `eyJhbG...` | JWT from login |
| `appid` | `9319141212m2ik` | App identifier |
| `appinfo` | `wyze_android_3.11.0.758` | App info string |
| `appversion` | `3.11.0.758` | App version |
| `env` | `Prod` | Environment |
| `phoneid` | `<uuid>` | Random UUID (persist per session) |
| `requestid` | `<uuid>` | Unique per request |
| `Signature2` | `<hex>` | HMAC-MD5 signature (see above) |
| `Content-Type` | `application/json; charset=utf-8` | Content type |

---

## Device Discovery

Use the standard Wyze device list API to find DX_LB2 devices:

```bash
curl -s -X POST "https://api.wyzecam.com/app/v2/home_page/get_object_list" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_system_type": "1",
    "app_version": "2.18.43",
    "app_ver": "com.hualai.WyzeCam___2.18.43",
    "sc": "9f275790cab94a72bd206c8876429f3c",
    "ts": TIMESTAMP_SECONDS,
    "sv": "9d74946e652647e9b6c9d59326aef104",
    "access_token": "YOUR_ACCESS_TOKEN",
    "phone_id": "YOUR_PHONE_UUID",
    "app_name": "com.hualai.WyzeCam"
  }'
```

Look for devices with `"product_model": "DX_LB2"` in the response. The `mac` field (e.g., `DX_LB2_80482C9C659C`) is the device ID used in all IoT3 calls.

---

## Endpoints

### 1. Get Device Properties

Read the current state of the lock.

**Endpoint:** `POST https://app.wyzecam.com/app/v4/iot3/get-property`

**Request Body:**
```json
{
  "nonce": "1774567387005",
  "payload": {
    "cmd": "get_property",
    "props": [
      "lock::lock-status",
      "lock::door-status",
      "iot-device::iot-state",
      "battery::battery-level",
      "battery::power-source",
      "device-info::firmware-ver",
      "device-info::timezone",
      "lock::lock-install-mode",
      "lock::gyroscope-calibration-step",
      "battery::battery-state-spare"
    ],
    "tid": 7189,
    "ts": 1774567387005,
    "ver": 1
  },
  "targetInfo": {
    "id": "DX_LB2_YOUR_DEVICE_MAC",
    "model": "DX_LB2"
  }
}
```

**Response:**
```json
{
  "code": "1",
  "ts": 1774567377882,
  "msg": "SUCCESS",
  "data": {
    "props": {
      "battery::power-source": 1,
      "iot-device::iot-state": true,
      "battery::battery-level": 100,
      "lock::lock-status": true,
      "device-info::firmware-ver": "1.0.8",
      "lock::lock-install-mode": 2,
      "device-info::timezone": "EST+0500EDT+0400,M3.2.0/02:00:00,M11.1.0/02:00:00"
    }
  },
  "traceId": "6a7b7b33cc272a57b38e9e8482fb2572"
}
```

**curl example:**
```bash
BODY='{"nonce":"'$(date +%s%3N)'","payload":{"cmd":"get_property","props":["lock::lock-status","iot-device::iot-state","battery::battery-level"],"tid":'$RANDOM',"ts":'$(date +%s%3N)',"ver":1},"targetInfo":{"id":"DX_LB2_YOUR_DEVICE_MAC","model":"DX_LB2"}}'

# Compute signature (requires python)
SIG=$(python3 -c "
import hashlib, hmac
secret = hashlib.md5(('YOUR_ACCESS_TOKEN' + 'wyze_app_secret_key_132').encode()).hexdigest()
print(hmac.new(secret.encode(), '''$BODY'''.encode(), hashlib.md5).hexdigest())
")

curl -s -X POST "https://app.wyzecam.com/app/v4/iot3/get-property" \
  -H "Content-Type: application/json; charset=utf-8" \
  -H "access_token: YOUR_ACCESS_TOKEN" \
  -H "appid: 9319141212m2ik" \
  -H "appinfo: wyze_android_3.11.0.758" \
  -H "env: Prod" \
  -H "phoneid: YOUR_PHONE_UUID" \
  -H "requestid: $(uuidgen)" \
  -H "Signature2: $SIG" \
  -d "$BODY"
```

### 2. Lock

Lock the device.

**Endpoint:** `POST https://app.wyzecam.com/app/v4/iot3/run-action`

**Request Body:**
```json
{
  "nonce": "1774567407305",
  "payload": {
    "action": "lock::lock",
    "cmd": "run_action",
    "params": {
      "action_id": 34919,
      "type": 1,
      "username": "YOUR_WYZE_EMAIL"
    },
    "tid": 33646,
    "ts": 1774567407305,
    "ver": 1
  },
  "targetInfo": {
    "id": "DX_LB2_YOUR_DEVICE_MAC",
    "model": "DX_LB2"
  }
}
```

**Response:**
```json
{
  "code": "1",
  "ts": 1774568740228,
  "msg": "SUCCESS",
  "data": null,
  "traceId": "56e2a9503e20ab341fa64442f1a3b23c"
}
```

### 3. Unlock

Unlock the device.

**Endpoint:** `POST https://app.wyzecam.com/app/v4/iot3/run-action`

**Request Body:**
```json
{
  "nonce": "1774567388251",
  "payload": {
    "action": "lock::unlock",
    "cmd": "run_action",
    "params": {
      "action_id": 36604,
      "type": 1,
      "username": "YOUR_WYZE_EMAIL"
    },
    "tid": 3133,
    "ts": 1774567388250,
    "ver": 1
  },
  "targetInfo": {
    "id": "DX_LB2_YOUR_DEVICE_MAC",
    "model": "DX_LB2"
  }
}
```

**Response:**
```json
{
  "code": "1",
  "ts": 1774568688669,
  "msg": "SUCCESS",
  "data": null,
  "traceId": "226a5611d676b3f9b22c6006c8999113"
}
```

### 4. Get App Settings

**Endpoint:** `POST https://app.wyzecam.com/app/v4/iot3/get-app-setting`

*(Payload structure TBD - observed in app traffic but not fully explored)*

### 5. Event History

**Endpoint:** `POST https://app.wyzecam.com/app/v4/iot3/event-history`

*(Payload structure TBD - observed in app traffic but not fully explored)*

---

## Payload Field Reference

### Common Fields

| Field | Type | Description |
|-------|------|-------------|
| `nonce` | string | Millisecond timestamp as string |
| `payload.cmd` | string | Command: `"get_property"` or `"run_action"` |
| `payload.tid` | int | Transaction ID (random integer) |
| `payload.ts` | int | Millisecond timestamp |
| `payload.ver` | int | Always `1` |
| `targetInfo.id` | string | Device MAC (e.g., `DX_LB2_80482C9C659C`) |
| `targetInfo.model` | string | Device model (e.g., `DX_LB2`) |

### Action-Specific Fields (run-action)

| Field | Type | Description |
|-------|------|-------------|
| `payload.action` | string | Action to perform (e.g., `lock::lock`, `lock::unlock`) |
| `payload.params.action_id` | int | Random integer (unique per action invocation) |
| `payload.params.type` | int | Always `1` |
| `payload.params.username` | string | Wyze account email |

### Property Names

| Property | Type | Description |
|----------|------|-------------|
| `lock::lock-status` | bool | `true` = locked, `false` = unlocked |
| `lock::door-status` | bool | Door open/close state |
| `lock::lock-install-mode` | int | Installation mode |
| `lock::gyroscope-calibration-step` | int | Calibration state |
| `iot-device::iot-state` | bool | `true` = online |
| `battery::battery-level` | int | 0-100 percentage |
| `battery::power-source` | int | `1` = battery |
| `battery::battery-state-spare` | any | Spare battery state |
| `device-info::firmware-ver` | string | Firmware version (e.g., `"1.0.8"`) |
| `device-info::timezone` | string | Timezone string |

---

## Complete Python Example

```python
import hashlib
import hmac
import json
import random
import time
import uuid
import requests

class WyzeLockBoltV2:
    BASE_URL = "https://app.wyzecam.com"
    SIGNING_SECRET = "wyze_app_secret_key_132"
    APP_ID = "9319141212m2ik"
    APP_INFO = "wyze_android_3.11.0.758"

    def __init__(self, access_token: str, email: str, device_mac: str):
        self.access_token = access_token
        self.email = email
        self.device_mac = device_mac
        self.phone_id = str(uuid.uuid4())

        # Compute signing key
        access_key = self.access_token + self.SIGNING_SECRET
        self._secret = hashlib.md5(access_key.encode()).hexdigest()

    def _sign(self, body: str) -> str:
        return hmac.new(
            self._secret.encode(), body.encode(), hashlib.md5
        ).hexdigest()

    def _headers(self, body: str) -> dict:
        return {
            "access_token": self.access_token,
            "appid": self.APP_ID,
            "appinfo": self.APP_INFO,
            "appversion": "3.11.0.758",
            "env": "Prod",
            "phoneid": self.phone_id,
            "requestid": uuid.uuid4().hex,
            "Signature2": self._sign(body),
            "Content-Type": "application/json; charset=utf-8",
        }

    def _target(self) -> dict:
        model = self.device_mac.rsplit("_", 1)[0]  # e.g., DX_LB2
        # Handle models like DX_LB2 where the MAC is DX_LB2_XXXXXXXXXXXX
        parts = self.device_mac.split("_")
        if len(parts) >= 3:
            model = "_".join(parts[:2])  # DX_LB2
        return {"id": self.device_mac, "model": model}

    def _call(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload)
        resp = requests.post(
            f"{self.BASE_URL}{path}",
            headers=self._headers(body),
            data=body,
        )
        return resp.json()

    def get_status(self) -> dict:
        """Get lock status, battery, and online state."""
        ts = int(time.time() * 1000)
        payload = {
            "nonce": str(ts),
            "payload": {
                "cmd": "get_property",
                "props": [
                    "lock::lock-status",
                    "lock::door-status",
                    "iot-device::iot-state",
                    "battery::battery-level",
                    "battery::power-source",
                    "device-info::firmware-ver",
                ],
                "tid": random.randint(1000, 99999),
                "ts": ts,
                "ver": 1,
            },
            "targetInfo": self._target(),
        }
        return self._call("/app/v4/iot3/get-property", payload)

    def lock(self) -> dict:
        """Lock the device."""
        ts = int(time.time() * 1000)
        payload = {
            "nonce": str(ts),
            "payload": {
                "action": "lock::lock",
                "cmd": "run_action",
                "params": {
                    "action_id": random.randint(10000, 99999),
                    "type": 1,
                    "username": self.email,
                },
                "tid": random.randint(1000, 99999),
                "ts": ts,
                "ver": 1,
            },
            "targetInfo": self._target(),
        }
        return self._call("/app/v4/iot3/run-action", payload)

    def unlock(self) -> dict:
        """Unlock the device."""
        ts = int(time.time() * 1000)
        payload = {
            "nonce": str(ts),
            "payload": {
                "action": "lock::unlock",
                "cmd": "run_action",
                "params": {
                    "action_id": random.randint(10000, 99999),
                    "type": 1,
                    "username": self.email,
                },
                "tid": random.randint(1000, 99999),
                "ts": ts,
                "ver": 1,
            },
            "targetInfo": self._target(),
        }
        return self._call("/app/v4/iot3/run-action", payload)


# Usage example:
if __name__ == "__main__":
    # First, login to get an access token (see Authentication section above)
    ACCESS_TOKEN = "your_access_token_here"
    EMAIL = "your_email@example.com"
    DEVICE_MAC = "DX_LB2_XXXXXXXXXXXX"  # From device discovery

    lock = WyzeLockBoltV2(ACCESS_TOKEN, EMAIL, DEVICE_MAC)

    # Check status
    status = lock.get_status()
    print("Status:", json.dumps(status, indent=2))

    # Unlock
    result = lock.unlock()
    print("Unlock:", result)

    # Lock
    result = lock.lock()
    print("Lock:", result)
```

---

## Notes

- The `DX_LB2` (Lock Bolt v2) has built-in WiFi, unlike the `YD_BT1` (Lock Bolt v1) which is BLE-only
- The `DX_` prefix represents a new device generation; the Wyze Palm Lock (`DX_PVLOC`) likely uses the same IoT3 API
- The `action_id` and `tid` fields appear to be random integers - the server does not enforce uniqueness
- The `nonce` is a string representation of millisecond timestamp; `ts` is the same value as an integer
- Response `"code": "1"` indicates success; other codes indicate errors
- Rate limiting is enforced: `X-RateLimit-Remaining: 299` with 5-minute reset windows
- The `devicemgmt-service.wyze.com` API can also read properties but does NOT support write operations for locks
- This API was discovered by MITM-intercepting the Wyze Android app v3.11.0.758 using HTTP Toolkit + Frida on an Android 12 emulator

---

## Error Codes

| Code | Message | Meaning |
|------|---------|---------|
| `1` | `SUCCESS` | Request succeeded |
| `1001` | `INVALID_PARAMETER` | Missing or malformed request field |
| `1004` | `INVALID_SIGNATURE` | Signature2 header is wrong |
| `1000` | `internal error` | Server-side processing error |
| `2` | `404 NOT_FOUND` | Endpoint does not exist |

---

## Changelog

- **2026-03-26**: Initial discovery of IoT3 API for DX_LB2 (Lock Bolt v2). Confirmed lock, unlock, and get-property all work via cloud API.
