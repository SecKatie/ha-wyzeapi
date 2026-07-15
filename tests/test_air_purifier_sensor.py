"""Tests for Wyze air purifier AQI sensors."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.wyzeapi import sensor as sensor_module
from custom_components.wyzeapi.sensor import (
    WyzeAirPurifierAQISensor,
    WyzeAirPurifierHourlyMaxAQISensor,
)


@pytest.fixture
def air_purifier() -> SimpleNamespace:
    """Return a representative air purifier with air quality data."""
    return SimpleNamespace(
        mac="AA:BB:CC:DD:EE:FF",
        nickname="Office Purifier",
        product_model="CO_AP1",
        available=True,
        app_version="1.2.3",
        sn="PURIFIER123",
        wifi_mac="11:22:33:44:55:66",
        aqi=42,
        max_hourly_aqi=55,
        max_hourly_aqi_start_time=1_700_000_000,
        max_hourly_aqi_end_time=1_700_001_800,
    )


def test_current_aqi_sensor(air_purifier: SimpleNamespace) -> None:
    """The current AQI sensor exposes current library data."""
    sensor = WyzeAirPurifierAQISensor(air_purifier)

    assert sensor.unique_id == "AA:BB:CC:DD:EE:FF-aqi"
    assert sensor.available is True
    assert sensor.native_value == 42
    assert sensor.device_info["identifiers"] == {("wyzeapi", "AA:BB:CC:DD:EE:FF")}
    assert sensor.extra_state_attributes == {
        "attribution": "Data provided by Wyze",
        "device model": "CO_AP1",
    }


def test_hourly_max_aqi_sensor(air_purifier: SimpleNamespace) -> None:
    """The hourly sensor exposes its value and UTC sample window."""
    sensor = WyzeAirPurifierHourlyMaxAQISensor(air_purifier)

    assert sensor.unique_id == "AA:BB:CC:DD:EE:FF-hourly-max-aqi"
    assert sensor.native_value == 55
    assert sensor.extra_state_attributes == {
        "attribution": "Data provided by Wyze",
        "device model": "CO_AP1",
        "hour_start": "2023-11-14T22:13:20+00:00",
        "hour_end": "2023-11-14T23:13:20+00:00",
        "sampled_until": "2023-11-14T22:43:20+00:00",
    }


def test_missing_hourly_timestamps(air_purifier: SimpleNamespace) -> None:
    """Incomplete AQI responses produce stable null timestamp attributes."""
    air_purifier.max_hourly_aqi_start_time = None
    air_purifier.max_hourly_aqi_end_time = None
    sensor = WyzeAirPurifierHourlyMaxAQISensor(air_purifier)

    assert sensor.extra_state_attributes["hour_start"] is None
    assert sensor.extra_state_attributes["hour_end"] is None
    assert sensor.extra_state_attributes["sampled_until"] is None


def test_dispatcher_update_replaces_model(air_purifier: SimpleNamespace) -> None:
    """Dispatcher callbacks replace cached data and write Home Assistant state."""
    sensor = WyzeAirPurifierAQISensor(air_purifier)
    sensor.async_write_ha_state = Mock()
    updated = SimpleNamespace(**vars(air_purifier))
    updated.aqi = 73

    sensor.handle_air_purifier_update(updated)

    assert sensor.native_value == 73
    sensor.async_write_ha_state.assert_called_once_with()


@pytest.mark.asyncio
async def test_sensor_subscribes_to_air_purifier_dispatcher(
    air_purifier: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AQI sensors subscribe to fan-owned updates and retain the unsubscribe."""
    sensor = WyzeAirPurifierAQISensor(air_purifier)
    sensor.hass = Mock()
    sensor.async_on_remove = Mock()
    unsubscribe = Mock()
    dispatcher_connect = Mock(return_value=unsubscribe)
    monkeypatch.setattr(sensor_module, "async_dispatcher_connect", dispatcher_connect)

    await sensor.async_added_to_hass()

    dispatcher_connect.assert_called_once_with(
        sensor.hass,
        "wyzeapi.air_purifier_updated-AA:BB:CC:DD:EE:FF",
        sensor.handle_air_purifier_update,
    )
    sensor.async_on_remove.assert_called_once_with(unsubscribe)
