"""Tests for Wyze irrigation diagnostic sensors."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.wyzeapi.sensor import WyzeIrrigationRSSI


@pytest.fixture
def irrigation() -> SimpleNamespace:
    """Return a representative irrigation device."""
    return SimpleNamespace(
        mac="AA:BB:CC:DD:EE:FF",
        nickname="Test Sprinkler",
        product_model="BS_WK1",
        sn="TEST123456",
        RSSI=-65,
        IP="192.0.2.10",
        ssid="Test Network",
    )


@pytest.fixture
def irrigation_service() -> SimpleNamespace:
    """Return the service methods used by irrigation sensors."""
    return SimpleNamespace(
        update_device_props=Mock(
            side_effect=AssertionError(
                "the callback must not start another asynchronous update"
            )
        ),
        unregister_updater=Mock(),
    )


def test_update_callback_uses_completed_irrigation_update(
    irrigation: SimpleNamespace, irrigation_service: SimpleNamespace
) -> None:
    """The updater callback caches its completed model without another API call."""
    sensor = WyzeIrrigationRSSI(irrigation_service, irrigation)
    sensor.async_schedule_update_ha_state = Mock()
    updated = SimpleNamespace(**vars(irrigation))
    updated.RSSI = -52

    sensor.async_update_callback(updated)

    assert sensor._device is updated
    assert sensor.native_value == -52
    irrigation_service.update_device_props.assert_not_called()
    sensor.async_schedule_update_ha_state.assert_called_once_with()


@pytest.mark.asyncio
async def test_remove_after_update_unregisters_device_model(
    irrigation: SimpleNamespace, irrigation_service: SimpleNamespace
) -> None:
    """Removal unregisters the device model rather than a coroutine."""
    sensor = WyzeIrrigationRSSI(irrigation_service, irrigation)
    sensor.async_schedule_update_ha_state = Mock()
    updated = SimpleNamespace(**vars(irrigation))
    sensor.async_update_callback(updated)

    await sensor.async_will_remove_from_hass()

    irrigation_service.unregister_updater.assert_called_once_with(updated)
