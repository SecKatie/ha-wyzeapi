# Agora ("lake") live-view custom card for ha-wyzeapi

**Date:** 2026-08-23
**Status:** Approved (design)

## Problem

Wyze's "Gwell" cameras (product models in the `GW_`/`ME_` families) stream over
**Agora RTC**, not the TUTK/Kinesis WebRTC path the integration supports today.
Confirmed members include the Wyze Cam OG (`GW_GC1`), Doorbell Pro (`GW_BE1`),
and Solar Cam Pan (`ME_WCO3`), and the list grows as Wyze moves to Agora on newer
hardware. These cameras currently appear unavailable with no livestream in Home
Assistant.

Agora cannot be fed into HA's native WebRTC camera player: there is no SDP
offer/answer to relay. The browser must load Agora's proprietary SDK, call
`setEncryptionConfig(...)`, then `join(app_id, channel, token, uid)`. The stream
is end-to-end encrypted and rides Agora's own transport, so no RTSP/RTMP is
exposed to relay. A server-side Agora→RTSP bridge is not viable inside a
pure-Python HACS integration — Agora's Python Server SDK ships x86_64/glibc
native binaries only (no ARM, no musl), which excludes Raspberry Pi and Home
Assistant OS.

The library side is already done: `wyzeapy.CameraService.get_stream_info()`
returns `provider: "lake"` plus the Agora `app_id`, `channel`, `rtc_token`,
`uid`, `encryption_mode`, and the **decrypted** `encryption_key` and
`encryption_salt` (see wyzeapy PR #336).

## Goals

- Render live **video + audio** for Agora/"lake" cameras in Home Assistant.
- Keep the camera a first-class HA **entity** (works in dashboards, automations,
  notifications) via a thumbnail still image.
- Be **generic**: activate whenever wyzeapy reports `provider: "lake"`, never
  hardcode a model, so the whole Gwell family (current and future) is covered.
- Ship to **all** HA platforms (browser-side playback, no native binaries).

## Non-goals (deferred to follow-up PRs)

- Pan/tilt (PTZ) controls — likely needs new commands in wyzeapy first.
- Two-way talk / microphone push.
- Replacing HA's built-in camera card for these cameras.

## Design

Three cooperating pieces, all keyed off `provider == "lake"`.

### 1. WebSocket command — fresh credentials on demand

Register a `wyzeapi/agora_stream_info` websocket command (HA WS commands are
authenticated; only logged-in users reach it). Input: `entity_id`. Handler:

1. Resolve the `WyzeCamera` entity / underlying `Camera`.
2. Call `camera_service.get_stream_info(camera)`.
3. If `provider == "lake"`, return the Agora credentials
   (`app_id`, `channel`, `rtc_token` as `token`, `uid`, `encryption_mode`,
   `encryption_key`, `encryption_salt`).
4. If not a lake camera, return `{ "provider": <other> }` so the card can show a
   "use the standard camera card" message instead of failing.
5. wyzeapy errors surface as a WS error with a message.

Credentials are short-lived and fetched per view, so nothing sensitive is stored
in entity attributes or the recorder.

### 2. Custom Lovelace card + vendored Agora SDK

- `custom_components/wyzeapi/frontend/wyze-agora-card.js`: a custom element
  (`wyze-agora-card`) taking `entity` (a camera entity_id) in its card config.
- On connect it calls the WS command, loads the **vendored** Agora Web SDK,
  `setEncryptionConfig(mode, key, saltBytes)`, joins the channel, subscribes to
  video + audio, and renders into the card. This mirrors the validated
  `agora_viewer.html` flow.
- The Agora Web SDK (`AgoraRTC_N-4.24.0.js`, ~1.2 MB — the version validated in
  `agora_viewer.html`) is vendored under
  `custom_components/wyzeapi/frontend/` and served locally — no CDN, matching
  HA's offline/CSP norms.
- Lifecycle: play on card connected, stop on disconnected. On Agora
  `connection-state-change → failed/left` or token expiry (~1h), re-fetch
  credentials via the WS command and rejoin.

### 3. Native camera entity — thumbnail, no broken player

In `camera.py`:

- Implement `async_camera_image()` to fetch the camera's presigned
  `device_params["camera_thumbnails"]["thumbnails_url"]` and return the bytes,
  giving the entity a periodic still image.
- For **lake** cameras, do **not** advertise `CameraEntityFeature.STREAM`, so HA
  never attempts (and fails) the built-in WebRTC player. Live video comes from
  the custom card; the entity provides the still.
- Non-lake cameras are untouched — the existing Kinesis/WebRTC path stays exactly
  as-is.

### Auto-registration

In `async_setup_entry`, register a static path for the `frontend/` directory and
`frontend.add_extra_js_url(hass, <card_url>)` so the card module auto-loads. Users
only add `type: custom:wyze-agora-card` to a dashboard — no manual Lovelace
resource registration. Add `http` and `frontend` to `manifest.json`
`dependencies`.

## Data flow

```
Dashboard (custom:wyze-agora-card, entity)
  → card JS → WS wyzeapi/agora_stream_info
    → handler → wyzeapy get_stream_info() [lake: get-streams + wakeup +
       create-connection + XXTEA-decrypt key/salt]
    → {app_id, channel, token, uid, encryption_mode, key, salt}
  → Agora Web SDK: setEncryptionConfig → join → subscribe video+audio → render

Native entity: async_camera_image → wyzeapy thumbnail URL → still image
  (dashboards, automations, notifications)
```

## Error handling

- **WS command:** camera not found → WS error; non-lake → `{provider}` (card
  shows guidance); wyzeapy failure → WS error with message.
- **Card:** SDK load / join failure or token expiry → visible error + retry;
  auto-refetch credentials on `connection-state-change → failed/left`.
- **Thumbnail:** fetch failure → return `None` (HA shows a placeholder).

## Testing

- **Python (pytest, HA test harness, matching existing `tests/`):** WS command
  returns correct credentials for a lake camera; handles a non-lake camera;
  requires auth. `async_camera_image` fetches the URL and returns `None` on
  failure.
- **Card JS:** no in-repo unit harness; verified live against a real Gwell camera
  (the same way `agora_viewer.html` was validated).

## Dependencies & release ordering

- Requires a released **wyzeapy** containing the lake support (PR #336). Once
  released, bump the `wyzeapy` pin in `manifest.json`. This PR therefore lands
  after #336. (Same maintainer owns both repos, so the ordering is coordinated.)
- Add `http` and `frontend` to `manifest.json` `dependencies`.

## Files touched

- `custom_components/wyzeapi/__init__.py` — register static path, add card JS URL,
  register WS command.
- `custom_components/wyzeapi/camera.py` — thumbnail `async_camera_image`; gate
  `CameraEntityFeature.STREAM` off for lake cameras.
- `custom_components/wyzeapi/agora.py` (new) — WS command handler.
- `custom_components/wyzeapi/frontend/wyze-agora-card.js` (new) — the card.
- `custom_components/wyzeapi/frontend/AgoraRTC_N-4.24.0.js` (new, vendored).
- `custom_components/wyzeapi/manifest.json` — `dependencies` + version bump.
- `tests/test_agora.py` (new) — WS command + thumbnail tests.
- `README.md` — document adding the card.

## Risks / open discussion

- **Vendored JS in the repo:** there is no JS in the integration today, so a
  ~1.2 MB vendored SDK is a notable first. The PR will explain the rationale
  (Agora's proprietary transport leaves browser-side playback as the only
  all-platform option; CDN loading conflicts with HA's offline/CSP norms) and use
  the PR to open that discussion with the maintainer.
- **Custom card, not the native camera card:** an accepted tradeoff — the native
  card cannot consume Agora, and a server-side bridge is not shippable in a
  pure-Python HACS integration.
