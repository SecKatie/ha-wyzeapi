# 0.1.40

## Before updating

This release requires Home Assistant **2026.10.2 or newer**, matching the project's
supported baseline. HACS now declares that minimum; update Home Assistant before
installing this release. Older Home Assistant versions have not been verified.
For development, Python **3.14.2–3.14.x** is required.

The integration now uses **wyzeapy 0.8.x**. Its published 0.8.0 release is available
on PyPI; HACS installs it automatically. New HA platforms and camera-streaming
features in separate, unmerged PRs are not part of this release.

## Changes since 0.1.39

- Preserve API key and key ID when refreshed tokens are saved, and start Home
  Assistant's reauthentication flow after token/login failures.
- Show and set a single thermostat target in heat or cool mode while retaining
  range controls; avoid overwriting the inactive setpoint.
- Reflect camera floodlight commands immediately and follow camera availability.
- Add the Duo Cam Doorbell (`GW_DBD`) battery sensor.
- Handle cameras without motion or notification properties.
- Keep completed irrigation sensor updates instead of caching a coroutine.
- Remove stale switch entities using their entity IDs.
- Update the Home Assistant development baseline and maintenance workflows.

## Validation and limitations

The integration's unit tests pass with Home Assistant 2026.10.2 and the published
wyzeapy 0.8.0 package. Live devices and camera streaming have not been validated
for this release. The development test environment does not include the complete
optional HA camera/stream dependency set.

This is not a complete dependency-security remediation. The HA development lock
retains HA's Pillow 12.3.0 pin, which is affected by
[GHSA-v9pv-5gc8-w2m6](https://github.com/advisories/GHSA-v9pv-5gc8-w2m6).
No dependency override is applied. Updating this integration does not upgrade
packages owned by the host Home Assistant installation.

[Full comparison](https://github.com/SecKatie/ha-wyzeapi/compare/v0.1.39...v0.1.40)
