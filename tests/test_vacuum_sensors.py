"""Tests for the Wyze vacuum's last-clean sensors."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.wyzeapi.sensor import (
    WyzeVacuumLastCleanDurationSensor,
    WyzeVacuumLastCleanFinishedSensor,
    WyzeVacuumLastCleanSizeSensor,
)
from custom_components.wyzeapi.const import DOMAIN

RECORD = {
    "cleanSize": 694,
    "cleanTime": 15,
    "cleanTypeText": "House Vacuuming",
    "launchTypeText": "Manual",
    "create_time": 1785764496542,
}


@pytest.fixture
def vacuum() -> SimpleNamespace:
    """Return a representative vacuum."""
    return SimpleNamespace(
        mac="JA_RO2_ABCDEF1234567890",
        nickname="Diogee",
        product_model="JA_RO2",
    )


@pytest.fixture
def service() -> SimpleNamespace:
    """Return a mocked vacuum service holding one cleaning record."""
    return SimpleNamespace(get_last_clean=AsyncMock(return_value=RECORD))


@pytest.mark.asyncio
async def test_size_sensor_reports_the_raw_figure(service, vacuum):
    sensor = WyzeVacuumLastCleanSizeSensor(service, vacuum)
    await sensor.async_update()

    assert sensor.native_value == 694
    assert sensor.native_unit_of_measurement is None
    assert sensor.unique_id == f"{vacuum.mac}-last-clean-size"
    assert sensor.extra_state_attributes["launch_type"] == "Manual"


@pytest.mark.asyncio
async def test_duration_sensor_reports_minutes(service, vacuum):
    sensor = WyzeVacuumLastCleanDurationSensor(service, vacuum)
    await sensor.async_update()

    assert sensor.native_value == 15
    assert sensor.native_unit_of_measurement == "min"


@pytest.mark.asyncio
async def test_finished_sensor_reports_an_aware_timestamp(service, vacuum):
    sensor = WyzeVacuumLastCleanFinishedSensor(service, vacuum)
    await sensor.async_update()

    value = sensor.native_value
    assert isinstance(value, datetime.datetime)
    assert value.tzinfo is not None
    assert value == datetime.datetime.fromtimestamp(
        RECORD["create_time"] / 1000, tz=datetime.UTC
    )


@pytest.mark.asyncio
async def test_sensors_report_none_without_history(vacuum):
    """A vacuum that has never run has no record, and must not raise."""
    service = SimpleNamespace(get_last_clean=AsyncMock(return_value=None))
    for cls in (
        WyzeVacuumLastCleanSizeSensor,
        WyzeVacuumLastCleanDurationSensor,
        WyzeVacuumLastCleanFinishedSensor,
    ):
        sensor = cls(service, vacuum)
        await sensor.async_update()
        assert sensor.native_value is None


@pytest.mark.asyncio
async def test_sensors_attach_to_the_vacuum_device(service, vacuum):
    sensor = WyzeVacuumLastCleanSizeSensor(service, vacuum)

    assert sensor.device_info["identifiers"] == {(DOMAIN, vacuum.mac)}
    assert sensor.device_info["name"] == "Diogee"
