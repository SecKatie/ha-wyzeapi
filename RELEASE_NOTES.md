# 0.1.41

This release fixes thermostat setpoints, keeps lock names intact, and makes
reauthentication safer. It also updates the Wyze library to 0.8.1.

## Before updating

You need **Home Assistant 2025.2.1 or newer**. HACS installs the Wyze library
automatically. After updating, restart Home Assistant.

## What's changed

- Thermostat setpoint changes now turn on the furnace or AC. Wyze accepted the
  new target before but never acted on it (#971).
- Locks keep their own name when their battery sensor is added, instead of
  being renamed after the battery type (#946).
- Reauthentication updates only the Wyze entry that asked for it, and stops
  with a clear message if you sign in with a different Wyze account.

[Full comparison](https://github.com/SecKatie/ha-wyzeapi/compare/v0.1.40...v0.1.41)
