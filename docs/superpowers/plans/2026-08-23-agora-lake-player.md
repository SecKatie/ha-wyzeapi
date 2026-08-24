# Agora "lake" Live-View Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render live video+audio for Wyze Agora/"lake" cameras (the Gwell family) in Home Assistant via a custom Lovelace card, with the native camera entity serving a thumbnail still.

**Architecture:** wyzeapy's `get_stream_info()` returns `provider: "lake"` plus Agora credentials for these cameras. A websocket command hands those credentials to a custom Lovelace card that runs Agora's Web SDK in the browser to play the encrypted stream. The native camera entity stops advertising the (unusable) WebRTC STREAM feature for lake cameras and instead serves a thumbnail via `async_camera_image`. Everything branches on `provider == "lake"` / `LAKE_API_MODELS`, never on a specific model.

**Tech Stack:** Home Assistant custom integration (Python 3.13), `homeassistant.components.websocket_api`, `homeassistant.components.http.StaticPathConfig`, `homeassistant.components.frontend.add_extra_js_url`, Agora Web SDK (`AgoraRTC_N-4.24.0.js`, vendored), vanilla-JS custom element.

## Global Constraints

- Python `>=3.13.2,<3.14`; ruff `line-length = 88`, double quotes.
- Tests: lightweight style only — direct class instantiation + `unittest.mock`, no `hass` fixture / `pytest-homeassistant-custom-component` (not a dependency). `pytest` + `pytest-asyncio` only. Async tests use `@pytest.mark.asyncio`.
- CI runs `uv run pytest` and `ruff`. Run `uv run ruff format` and `uv run ruff check` before each commit.
- Branch: `agora-lake-player`. Lake detection uses `from wyzeapy.services.camera_service import LAKE_API_MODELS`.
- Depends on a released wyzeapy containing lake support (wyzeapy PR #336). The `manifest.json` / `pyproject.toml` `wyzeapy` pin bump is the final task and may need the release to exist first.
- Never hardcode `ME_WCO3`; branch on `LAKE_API_MODELS` / `provider == "lake"`.

---

### Task 1: Gate the WebRTC STREAM feature off for lake cameras

**Files:**
- Modify: `custom_components/wyzeapi/camera.py` (imports; `WyzeCamera.__init__`; `async_setup_entry` config_fetch loop)
- Test: `tests/test_camera_lake.py` (create)

**Interfaces:**
- Consumes: `wyzeapy.services.camera_service.LAKE_API_MODELS` (list of product_model strings), `Camera.product_model`.
- Produces: `WyzeCamera._is_lake: bool` attribute; `WyzeCamera` for a lake model has `supported_features` without `CameraEntityFeature.STREAM`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_camera_lake.py`:

```python
"""Tests for Wyze Agora/lake camera handling."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from homeassistant.components.camera import CameraEntityFeature

from custom_components.wyzeapi.camera import WyzeCamera


def _camera(product_model: str) -> SimpleNamespace:
    return SimpleNamespace(
        mac="AA:BB:CC:DD:EE:FF",
        nickname="Test Cam",
        product_model=product_model,
        available=True,
        on=True,
        device_params={},
    )


def test_lake_camera_does_not_advertise_stream() -> None:
    entity = WyzeCamera(Mock(), _camera("ME_WCO3"))
    assert entity._is_lake is True
    assert not (entity.supported_features & CameraEntityFeature.STREAM)


def test_non_lake_camera_advertises_stream() -> None:
    entity = WyzeCamera(Mock(), _camera("WYZECP1_JEF"))
    assert entity._is_lake is False
    assert entity.supported_features & CameraEntityFeature.STREAM
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_camera_lake.py -v`
Expected: FAIL (`AttributeError: ... _is_lake`, or STREAM asserted for lake).

- [ ] **Step 3: Add the import**

In `custom_components/wyzeapi/camera.py`, add to the wyzeapy imports block (near `from wyzeapy.services.camera_service import Camera`):

```python
from wyzeapy.services.camera_service import Camera, LAKE_API_MODELS
```

(Replace the existing `from wyzeapy.services.camera_service import Camera` line.)

- [ ] **Step 4: Set the flag and gate the feature in `WyzeCamera.__init__`**

In `WyzeCamera.__init__`, replace:

```python
        self.supported_features = CameraEntityFeature.STREAM
```

with:

```python
        self._is_lake = camera.product_model in LAKE_API_MODELS
        # Lake (Agora) cameras cannot use HA's native WebRTC player; live view
        # is provided by the custom wyze-agora-card. Only advertise STREAM for
        # cameras that actually work with the built-in player.
        self.supported_features = (
            CameraEntityFeature(0) if self._is_lake else CameraEntityFeature.STREAM
        )
```

- [ ] **Step 5: Skip the WebRTC pre-seed for lake cameras**

In `async_setup_entry`, change the pre-seed loop so lake cameras are skipped (their `config_fetch` runs the heavy lake flow and has no ICE servers):

```python
    for camera in cameras:
        if camera._is_lake:
            # Lake cameras fetch Agora credentials on demand from the card;
            # there is no WebRTC config to pre-seed.
            continue
        # Pre-seed the ICE server config by fetching it during setup, so the
        # frontend can collect ICE servers before the offer
        try:
            await camera.config_fetch()
        except Exception as e:
            # Don't block startup if the config fetch fails, but log the error
            _LOGGER.warning(
                "Error fetching WebRTC session configuration for camera %s: %s",
                camera.name,
                e,
            )
```

- [ ] **Step 6: Run tests + lint**

Run: `uv run pytest tests/test_camera_lake.py -v && uv run ruff format custom_components/wyzeapi/camera.py tests/test_camera_lake.py && uv run ruff check custom_components/wyzeapi/camera.py tests/test_camera_lake.py`
Expected: PASS, no lint errors.

- [ ] **Step 7: Commit**

```bash
git add custom_components/wyzeapi/camera.py tests/test_camera_lake.py
git commit -m "feat(camera): gate WebRTC STREAM off for Agora/lake cameras"
```

---

### Task 2: Thumbnail still image for the native entity

**Files:**
- Modify: `custom_components/wyzeapi/camera.py` (imports; `WyzeCamera.async_camera_image`)
- Test: `tests/test_camera_lake.py` (extend)

**Interfaces:**
- Consumes: `Camera.device_params["camera_thumbnails"]["thumbnails_url"]` (presigned URL string, may be absent), `homeassistant.helpers.aiohttp_client.async_get_clientsession`.
- Produces: `WyzeCamera.async_camera_image(width, height) -> bytes | None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_camera_lake.py`:

```python
from unittest.mock import AsyncMock, patch


def _camera_with_thumb(url: str | None) -> SimpleNamespace:
    cam = _camera("ME_WCO3")
    cam.device_params = (
        {"camera_thumbnails": {"thumbnails_url": url}} if url else {}
    )
    return cam


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def read(self) -> bytes:
        return self._body


@pytest.mark.asyncio
async def test_camera_image_returns_thumbnail_bytes() -> None:
    entity = WyzeCamera(Mock(), _camera_with_thumb("https://thumb/x.jpg"))
    entity.hass = Mock()
    session = Mock()
    session.get = Mock(return_value=_FakeResponse(200, b"JPEGBYTES"))
    with patch(
        "custom_components.wyzeapi.camera.async_get_clientsession",
        return_value=session,
    ):
        result = await entity.async_camera_image()
    assert result == b"JPEGBYTES"
    session.get.assert_called_once_with("https://thumb/x.jpg")


@pytest.mark.asyncio
async def test_camera_image_none_when_no_thumbnail() -> None:
    entity = WyzeCamera(Mock(), _camera_with_thumb(None))
    entity.hass = Mock()
    assert await entity.async_camera_image() is None


@pytest.mark.asyncio
async def test_camera_image_none_on_http_error() -> None:
    entity = WyzeCamera(Mock(), _camera_with_thumb("https://thumb/x.jpg"))
    entity.hass = Mock()
    session = Mock()
    session.get = Mock(return_value=_FakeResponse(403, b""))
    with patch(
        "custom_components.wyzeapi.camera.async_get_clientsession",
        return_value=session,
    ):
        assert await entity.async_camera_image() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_camera_lake.py -v -k camera_image`
Expected: FAIL (current `async_camera_image` returns `None` unconditionally, so the bytes test fails).

- [ ] **Step 3: Add the import**

In `custom_components/wyzeapi/camera.py`, add with the other `homeassistant.helpers` imports:

```python
from homeassistant.helpers.aiohttp_client import async_get_clientsession
```

- [ ] **Step 4: Implement `async_camera_image`**

Replace the existing `async_camera_image` method body:

```python
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the latest thumbnail still for this camera, if available."""
        params = self._camera.device_params or {}
        url = params.get("camera_thumbnails", {}).get("thumbnails_url")
        if not url:
            return None
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url) as response:
                if response.status != 200:
                    _LOGGER.debug(
                        "Thumbnail fetch for %s returned %s",
                        self.name,
                        response.status,
                    )
                    return None
                return await response.read()
        except Exception as e:  # noqa: BLE001 - never break the entity on fetch
            _LOGGER.debug("Thumbnail fetch failed for %s: %s", self.name, e)
            return None
```

- [ ] **Step 5: Run tests + lint**

Run: `uv run pytest tests/test_camera_lake.py -v && uv run ruff format custom_components/wyzeapi/camera.py tests/test_camera_lake.py && uv run ruff check custom_components/wyzeapi/camera.py tests/test_camera_lake.py`
Expected: PASS, no lint errors.

- [ ] **Step 6: Commit**

```bash
git add custom_components/wyzeapi/camera.py tests/test_camera_lake.py
git commit -m "feat(camera): serve thumbnail still via async_camera_image"
```

---

### Task 3: Entity method that returns Agora credentials

**Files:**
- Modify: `custom_components/wyzeapi/camera.py` (`WyzeCamera.async_agora_stream_info`)
- Test: `tests/test_camera_lake.py` (extend)

**Interfaces:**
- Consumes: `self._camera_service.get_stream_info(camera)` (async) returning a dict with `provider` and, for lake, `app_id/channel/rtc_token/uid/encryption_mode/encryption_key/encryption_salt`.
- Produces: `async WyzeCamera.async_agora_stream_info() -> dict`. For a lake camera returns keys `provider, app_id, channel, token, uid, encryption_mode, encryption_key, encryption_salt`. For a non-lake camera returns `{"provider": <other>}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_camera_lake.py`:

```python
@pytest.mark.asyncio
async def test_agora_stream_info_maps_lake_config() -> None:
    service = Mock()
    service.get_stream_info = AsyncMock(
        return_value={
            "provider": "lake",
            "app_id": "app",
            "channel": "chan",
            "rtc_token": "tok",
            "uid": 42,
            "encryption_mode": 7,
            "encryption_key": "k",
            "encryption_salt": "s",
        }
    )
    entity = WyzeCamera(service, _camera("ME_WCO3"))
    info = await entity.async_agora_stream_info()
    assert info == {
        "provider": "lake",
        "app_id": "app",
        "channel": "chan",
        "token": "tok",
        "uid": 42,
        "encryption_mode": 7,
        "encryption_key": "k",
        "encryption_salt": "s",
    }


@pytest.mark.asyncio
async def test_agora_stream_info_non_lake_returns_provider_only() -> None:
    service = Mock()
    service.get_stream_info = AsyncMock(return_value={"provider": "webrtc"})
    entity = WyzeCamera(service, _camera("WYZECP1_JEF"))
    info = await entity.async_agora_stream_info()
    assert info == {"provider": "webrtc"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_camera_lake.py -v -k agora_stream_info`
Expected: FAIL (`AttributeError: ... async_agora_stream_info`).

- [ ] **Step 3: Implement the method**

Add to `WyzeCamera` (place it after `config_fetch`):

```python
    async def async_agora_stream_info(self) -> dict:
        """Return Agora ("lake") streaming credentials for the card.

        Non-lake cameras return only their provider so the card can show
        guidance instead of attempting an Agora join.
        """
        config = await self._camera_service.get_stream_info(self._camera)
        if config.get("provider") != "lake":
            return {"provider": config.get("provider")}
        return {
            "provider": "lake",
            "app_id": config["app_id"],
            "channel": config["channel"],
            "token": config["rtc_token"],
            "uid": config["uid"],
            "encryption_mode": config.get("encryption_mode"),
            "encryption_key": config.get("encryption_key"),
            "encryption_salt": config.get("encryption_salt"),
        }
```

- [ ] **Step 4: Run tests + lint**

Run: `uv run pytest tests/test_camera_lake.py -v && uv run ruff format custom_components/wyzeapi/camera.py tests/test_camera_lake.py && uv run ruff check custom_components/wyzeapi/camera.py tests/test_camera_lake.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/wyzeapi/camera.py tests/test_camera_lake.py
git commit -m "feat(camera): add async_agora_stream_info credential mapper"
```

---

### Task 4: Websocket command handler

**Files:**
- Create: `custom_components/wyzeapi/agora.py`
- Test: `tests/test_agora_ws.py` (create)

**Interfaces:**
- Consumes: `WyzeCamera.async_agora_stream_info()` (Task 3); the camera `EntityComponent` at `hass.data["camera"]` with `.get_entity(entity_id)`.
- Produces: `async_register_agora_ws(hass)` which registers command type `wyzeapi/agora_stream_info` (payload `{type, entity_id}`); the handler `handle_agora_stream_info(hass, connection, msg)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_agora_ws.py`:

```python
"""Tests for the Agora stream-info websocket command."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.wyzeapi import agora


def _conn() -> Mock:
    conn = Mock()
    conn.send_result = Mock()
    conn.send_error = Mock()
    return conn


@pytest.mark.asyncio
async def test_handler_sends_credentials_for_known_camera() -> None:
    entity = Mock()
    entity.async_agora_stream_info = AsyncMock(
        return_value={"provider": "lake", "channel": "chan"}
    )
    component = Mock()
    component.get_entity = Mock(return_value=entity)
    hass = Mock()
    hass.data = {"camera": component}
    conn = _conn()

    await agora.handle_agora_stream_info(
        hass, conn, {"id": 5, "entity_id": "camera.solar"}
    )

    conn.send_result.assert_called_once_with(
        5, {"provider": "lake", "channel": "chan"}
    )
    conn.send_error.assert_not_called()


@pytest.mark.asyncio
async def test_handler_errors_when_camera_missing() -> None:
    component = Mock()
    component.get_entity = Mock(return_value=None)
    hass = Mock()
    hass.data = {"camera": component}
    conn = _conn()

    await agora.handle_agora_stream_info(
        hass, conn, {"id": 6, "entity_id": "camera.nope"}
    )

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args.args[0] == 6
    conn.send_result.assert_not_called()


@pytest.mark.asyncio
async def test_handler_errors_when_service_raises() -> None:
    entity = Mock()
    entity.async_agora_stream_info = AsyncMock(side_effect=RuntimeError("boom"))
    component = Mock()
    component.get_entity = Mock(return_value=entity)
    hass = Mock()
    hass.data = {"camera": component}
    conn = _conn()

    await agora.handle_agora_stream_info(
        hass, conn, {"id": 7, "entity_id": "camera.solar"}
    )

    conn.send_error.assert_called_once()
    assert conn.send_error.call_args.args[0] == 7


def test_register_calls_async_register_command() -> None:
    hass = Mock()
    with patch.object(agora.websocket_api, "async_register_command") as reg:
        agora.async_register_agora_ws(hass)
    reg.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agora_ws.py -v`
Expected: FAIL (`ModuleNotFoundError: ... agora`).

- [ ] **Step 3: Implement `agora.py`**

Create `custom_components/wyzeapi/agora.py`:

```python
"""Websocket command exposing Agora ("lake") stream credentials to the card."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

WS_TYPE = "wyzeapi/agora_stream_info"


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE,
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def handle_agora_stream_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return Agora credentials for the requested camera entity."""
    entity_id = msg["entity_id"]
    component = hass.data.get("camera")
    entity = component.get_entity(entity_id) if component else None
    if entity is None or not hasattr(entity, "async_agora_stream_info"):
        connection.send_error(
            msg["id"], "not_found", f"Unknown Wyze camera: {entity_id}"
        )
        return
    try:
        info = await entity.async_agora_stream_info()
    except Exception as e:  # noqa: BLE001 - report any failure to the card
        _LOGGER.warning("Agora stream info failed for %s: %s", entity_id, e)
        connection.send_error(msg["id"], "stream_info_failed", str(e))
        return
    connection.send_result(msg["id"], info)


def async_register_agora_ws(hass: HomeAssistant) -> None:
    """Register the Agora stream-info websocket command."""
    websocket_api.async_register_command(hass, handle_agora_stream_info)
```

- [ ] **Step 4: Run tests + lint**

Run: `uv run pytest tests/test_agora_ws.py -v && uv run ruff format custom_components/wyzeapi/agora.py tests/test_agora_ws.py && uv run ruff check custom_components/wyzeapi/agora.py tests/test_agora_ws.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/wyzeapi/agora.py tests/test_agora_ws.py
git commit -m "feat(agora): websocket command for Agora stream credentials"
```

---

### Task 5: Vendor the Agora Web SDK and write the card

**Files:**
- Create: `custom_components/wyzeapi/frontend/AgoraRTC_N-4.24.0.js` (vendored, downloaded)
- Create: `custom_components/wyzeapi/frontend/wyze-agora-card.js`

**Interfaces:**
- Consumes: global `window.AgoraRTC` (loaded via `add_extra_js_url` in Task 6); the websocket command `wyzeapi/agora_stream_info` (Task 4) via `this.hass.connection.sendMessagePromise`.
- Produces: custom element `wyze-agora-card` taking config `{ entity: "camera.<id>" }`.

This task has no in-repo unit test (browser JS). It is verified live in Task 7.

- [ ] **Step 1: Download and integrity-check the Agora SDK**

Run:

```bash
mkdir -p custom_components/wyzeapi/frontend
curl -sSL https://download.agora.io/sdk/release/AgoraRTC_N-4.24.0.js \
  -o custom_components/wyzeapi/frontend/AgoraRTC_N-4.24.0.js
openssl dgst -sha384 -binary custom_components/wyzeapi/frontend/AgoraRTC_N-4.24.0.js \
  | openssl base64 -A; echo
```

Expected: the printed sha384 equals `esPXY1puO5R4B+EOGrljUrSMdEV8DDEvv/yAmdhd8HTTOHGcoVgxj4em53wke60X`. If it differs, stop and do not commit the file.

- [ ] **Step 2: Write the card**

Create `custom_components/wyzeapi/frontend/wyze-agora-card.js`:

```javascript
// Wyze Agora ("lake") live-view card. Plays the browser-side Agora RTC stream
// for Gwell cameras (Solar Cam Pan, Cam OG, Doorbell Pro, ...). Credentials
// come from the wyzeapi/agora_stream_info websocket command.

const ENCRYPTION_MODES = {
  1: "aes-128-xts",
  2: "aes-128-ecb",
  3: "aes-256-xts",
  4: "sm4-128-ecb",
  5: "aes-128-gcm",
  6: "aes-256-gcm",
  7: "aes-128-gcm2",
  8: "aes-256-gcm2",
};

function b64ToBytes(b64) {
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

class WyzeAgoraCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("wyze-agora-card: 'entity' is required");
    }
    this._config = config;
    if (!this._built) {
      this._build();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config && !this._started) {
      this._start();
    }
  }

  getCardSize() {
    return 5;
  }

  _build() {
    this._built = true;
    this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; }
      .wrap { position: relative; width: 100%; background: #000; border-radius: var(--ha-card-border-radius, 12px); overflow: hidden; }
      .player { width: 100%; aspect-ratio: 16 / 9; }
      .msg { color: #ddd; font: 14px system-ui, sans-serif; padding: 12px; }
    `;
    this._wrap = document.createElement("div");
    this._wrap.className = "wrap";
    this._player = document.createElement("div");
    this._player.className = "player";
    this._msg = document.createElement("div");
    this._msg.className = "msg";
    this._wrap.appendChild(this._player);
    this._wrap.appendChild(this._msg);
    this.shadowRoot.appendChild(style);
    this.shadowRoot.appendChild(this._wrap);
  }

  _log(text) {
    this._msg.textContent = text;
  }

  async _start() {
    if (this._started) return;
    this._started = true;
    if (!window.AgoraRTC) {
      this._log("Agora SDK not loaded.");
      return;
    }
    try {
      const info = await this._hass.connection.sendMessagePromise({
        type: "wyzeapi/agora_stream_info",
        entity_id: this._config.entity,
      });
      if (info.provider !== "lake") {
        this._log("This camera uses the standard camera card, not this one.");
        return;
      }
      await this._join(info);
    } catch (e) {
      this._log("Failed to start stream: " + (e && e.message ? e.message : e));
    }
  }

  async _join(info) {
    const client = window.AgoraRTC.createClient({ mode: "rtc", codec: "h264" });
    this._client = client;

    if (info.encryption_key && info.encryption_salt) {
      const mode = ENCRYPTION_MODES[info.encryption_mode] || "aes-128-gcm2";
      client.setEncryptionConfig(
        mode,
        info.encryption_key,
        b64ToBytes(info.encryption_salt),
      );
    }

    client.on("user-published", async (user, mediaType) => {
      await client.subscribe(user, mediaType);
      if (mediaType === "video") {
        this._msg.textContent = "";
        user.videoTrack.play(this._player);
      } else if (mediaType === "audio") {
        user.audioTrack.play();
      }
    });
    client.on("connection-state-change", (cur) => {
      if (cur === "DISCONNECTED" || cur === "FAILED") {
        this._rejoin();
      }
    });

    this._log("Connecting…");
    await client.join(info.app_id, info.channel, info.token, info.uid);
  }

  async _rejoin() {
    if (this._rejoining || !this.isConnected) return;
    this._rejoining = true;
    try {
      await this._stop();
      this._started = false;
      await this._start();
    } finally {
      this._rejoining = false;
    }
  }

  async _stop() {
    try {
      if (this._client) {
        await this._client.leave();
        this._client = null;
      }
    } catch (e) {
      // ignore leave errors
    }
  }

  disconnectedCallback() {
    this._stop();
    this._started = false;
  }
}

customElements.define("wyze-agora-card", WyzeAgoraCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "wyze-agora-card",
  name: "Wyze Agora Camera",
  description: "Live view for Wyze Agora/lake cameras (Solar Cam, OG, ...).",
});
```

- [ ] **Step 3: Lint check the Python tree is unaffected**

Run: `uv run ruff check custom_components/wyzeapi`
Expected: no errors (JS files are ignored by ruff).

- [ ] **Step 4: Commit**

```bash
git add custom_components/wyzeapi/frontend/AgoraRTC_N-4.24.0.js custom_components/wyzeapi/frontend/wyze-agora-card.js
git commit -m "feat(frontend): vendor Agora SDK and add wyze-agora-card"
```

---

### Task 6: Register the WS command, static path, and card JS at setup

**Files:**
- Modify: `custom_components/wyzeapi/__init__.py` (imports; `async_setup_entry`)
- Modify: `custom_components/wyzeapi/manifest.json` (`dependencies`)
- Test: `tests/test_agora_setup.py` (create)

**Interfaces:**
- Consumes: `async_register_agora_ws(hass)` (Task 4); `homeassistant.components.http.StaticPathConfig`; `homeassistant.components.frontend.add_extra_js_url`.
- Produces: `async_register_agora_frontend(hass)` in `__init__.py` (idempotent registration of WS command + static path + card JS URL).

- [ ] **Step 1: Write the failing test**

Create `tests/test_agora_setup.py`:

```python
"""Tests for Agora frontend/ws registration wiring."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.wyzeapi import async_register_agora_frontend


@pytest.mark.asyncio
async def test_registration_is_idempotent_and_wires_everything() -> None:
    hass = Mock()
    hass.data = {}
    hass.http = Mock()
    hass.http.async_register_static_paths = AsyncMock()

    with (
        patch("custom_components.wyzeapi.async_register_agora_ws") as reg_ws,
        patch("custom_components.wyzeapi.add_extra_js_url") as add_js,
    ):
        await async_register_agora_frontend(hass)
        await async_register_agora_frontend(hass)  # second call: no-op

    reg_ws.assert_called_once()
    add_js.assert_called_once()
    hass.http.async_register_static_paths.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agora_setup.py -v`
Expected: FAIL (`ImportError: cannot import name 'async_register_agora_frontend'`).

- [ ] **Step 3: Add imports to `__init__.py`**

Add near the other `homeassistant` imports in `custom_components/wyzeapi/__init__.py`:

```python
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig

from .agora import async_register_agora_ws
```

- [ ] **Step 4: Add the registration function**

Add to `custom_components/wyzeapi/__init__.py` (module level):

```python
AGORA_STATIC_URL = "/wyzeapi_frontend"
AGORA_CARD_URL = f"{AGORA_STATIC_URL}/wyze-agora-card.js"
AGORA_SDK_URL = f"{AGORA_STATIC_URL}/AgoraRTC_N-4.24.0.js"
_AGORA_REGISTERED = "agora_frontend_registered"


async def async_register_agora_frontend(hass: HomeAssistant) -> None:
    """Register the Agora websocket command, static assets, and card JS once."""
    if hass.data.get(_AGORA_REGISTERED):
        return
    hass.data[_AGORA_REGISTERED] = True

    async_register_agora_ws(hass)

    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(AGORA_STATIC_URL, str(frontend_dir), cache_headers=False)]
    )
    # The card references window.AgoraRTC, so load the SDK first, then the card.
    add_extra_js_url(hass, AGORA_SDK_URL)
    add_extra_js_url(hass, AGORA_CARD_URL)
```

- [ ] **Step 5: Call it from `async_setup_entry`**

In `custom_components/wyzeapi/__init__.py`, inside `async_setup_entry` (after `hass.data[DOMAIN]` is populated and before/after forwarding platforms — anywhere in the entry setup body), add:

```python
    await async_register_agora_frontend(hass)
```

- [ ] **Step 6: Update `manifest.json` dependencies**

In `custom_components/wyzeapi/manifest.json`, change the `dependencies` line to include `http` and `frontend`:

```json
  "dependencies": ["bluetooth_adapters", "http", "frontend"],
```

- [ ] **Step 7: Run tests + lint**

Run: `uv run pytest tests/ -v && uv run ruff format custom_components/wyzeapi/__init__.py tests/test_agora_setup.py && uv run ruff check custom_components/wyzeapi`
Expected: PASS, no lint errors.

- [ ] **Step 8: Commit**

```bash
git add custom_components/wyzeapi/__init__.py custom_components/wyzeapi/manifest.json tests/test_agora_setup.py
git commit -m "feat: register Agora ws command, static assets, and card"
```

---

### Task 7: Live verification against a real camera

**Files:** none (manual verification)

This task confirms the browser card works end to end. It requires a running HA instance with this branch installed and a real lake camera (e.g., ME_WCO3).

- [ ] **Step 1: Install the branch into a test HA instance**

Copy `custom_components/wyzeapi` into the test instance's `config/custom_components/`, ensure its `wyzeapy` provides lake support (install the wyzeapy branch/build with PR #336), and restart HA.

- [ ] **Step 2: Add the card to a dashboard**

Add a manual card:

```yaml
type: custom:wyze-agora-card
entity: camera.<your_solar_cam_entity>
```

- [ ] **Step 3: Verify**

Expected: within a few seconds the card shows live video and plays audio. Confirm the native camera entity shows a thumbnail still in a standard Picture Entity card. Check the browser console for Agora `join channel ... success` and no encryption errors.

- [ ] **Step 4: Record the result**

Note the outcome (working / issues) in the PR description. No commit.

---

### Task 8: Documentation and dependency pin

**Files:**
- Modify: `README.md`
- Modify: `custom_components/wyzeapi/manifest.json` (`version`, `wyzeapy` pin)
- Modify: `pyproject.toml` (`wyzeapy` pin)

**Interfaces:** none (docs + metadata).

- [ ] **Step 1: Document the card in `README.md`**

Add a section:

```markdown
### Agora / Gwell cameras (Solar Cam Pan, Cam OG, Doorbell Pro, ...)

Some newer Wyze cameras stream over Agora RTC and cannot use Home Assistant's
built-in WebRTC camera player. This integration ships a custom card for them.
The camera entity itself shows a thumbnail still (usable in dashboards,
automations, and notifications); for live video+audio, add the bundled card to
a dashboard:

    type: custom:wyze-agora-card
    entity: camera.<your_camera>

The card and its Agora SDK are registered automatically — no manual Lovelace
resource is required.
```

- [ ] **Step 2: Bump the version and wyzeapy pin**

In `custom_components/wyzeapi/manifest.json`: bump `version` (e.g. `0.1.40`) and set the `wyzeapy` requirement to the released version containing lake support (e.g. `wyzeapy>=0.6.2,<0.7`). In `pyproject.toml`, update the matching `wyzeapy` dependency pin.

(If that wyzeapy release does not exist yet, leave this step pending until it does — see Global Constraints.)

- [ ] **Step 3: Run the full suite + lint**

Run: `uv run pytest && uv run ruff check custom_components/wyzeapi`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md custom_components/wyzeapi/manifest.json pyproject.toml
git commit -m "docs: document wyze-agora-card and bump wyzeapy pin"
```

---

## Self-Review

**Spec coverage:**
- WS command (spec §Design.1) → Task 4. ✓
- Custom card + vendored SDK (§Design.2) → Task 5. ✓
- Native entity thumbnail + STREAM gating (§Design.3) → Tasks 1, 2. ✓
- Auto-registration + manifest deps (§Auto-registration) → Task 6. ✓
- Credential mapping shape (§Data flow) → Task 3. ✓
- Error handling (§Error handling) → Task 3 (non-lake), Task 4 (not-found/failure), Task 2 (thumbnail None). ✓
- Testing plan (§Testing) → Tasks 1–4, 6 unit tests; Task 7 live. ✓
- Dependencies & release ordering (§Dependencies) → Task 8. ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. Task 8 Step 2 leaves the exact released wyzeapy version to fill at execution — this is an external dependency, not a plan placeholder, and is flagged in Global Constraints.

**Type consistency:** `async_agora_stream_info` returns `token` (from `rtc_token`) consistently in Task 3 (definition), Task 4 (passed through untouched), and Task 5 (`info.token` in `client.join`). `_is_lake` set in Task 1, reused in Task 1 Step 5. `async_register_agora_ws` defined in Task 4, imported in Task 6. Static URLs defined once in Task 6.
