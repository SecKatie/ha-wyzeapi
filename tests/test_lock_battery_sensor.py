"""Tests for Wyze lock battery sensors."""

from types import SimpleNamespace

import pytest

from custom_components.wyzeapi.sensor import WyzeLockBatterySensor


@pytest.mark.parametrize(
    "battery_type",
    [WyzeLockBatterySensor.LOCK_BATTERY, WyzeLockBatterySensor.KEYPAD_BATTERY],
)
def test_device_info_uses_lock_nickname(battery_type: str) -> None:
    """Battery sensors must not rename the shared lock device (#946)."""
    lock = SimpleNamespace(mac="LOCK-MAC", nickname="Front Door")
    sensor = WyzeLockBatterySensor(lock, battery_type)

    assert sensor.device_info["name"] == "Front Door"
