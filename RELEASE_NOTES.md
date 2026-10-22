# 0.1.40

This release improves authentication recovery, thermostat controls, and camera
and sensor state updates. It also updates the Wyze library to 0.8.0.

## Before updating

You need **Home Assistant 2025.2.1 or newer**. If you use an older version, update
Home Assistant first: its aiohttp dependency is too old for the required Wyze
library. HACS installs the library automatically.

After updating, restart Home Assistant. If Wyze asks you to sign in again, follow
the reauthentication prompt with your Wyze credentials and API key.

## What's changed

- Refreshed tokens no longer erase your API key and key ID. Login failures now
  open Home Assistant's reauthentication flow.
- Thermostats show a single target in heat or cool mode. Setting that target
  leaves the other mode's setpoint unchanged.
- Camera floodlights reflect commands immediately and become unavailable when
  their camera is offline.
- Duo Cam Doorbell devices now have a battery sensor.
- Cameras without motion or notification settings no longer fail when those
  properties are read.
- Irrigation sensors retain completed updates, and stale switch entities are
  removed correctly.

The new camera-streaming features and additional platforms proposed in other
pull requests are not included in this release. Live-device and streaming
validation is still outstanding.

[Full comparison](https://github.com/SecKatie/ha-wyzeapi/compare/v0.1.39...v0.1.40)
