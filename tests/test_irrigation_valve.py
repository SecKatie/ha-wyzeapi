"""Tests for Wyze sprinkler zone valve entities."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

from aiohttp.client_exceptions import ClientConnectionError
from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntityFeature,
)
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.wyzeapi import PLATFORMS
from custom_components.wyzeapi.valve import (
    WyzeIrrigationRuntimeData,
    WyzeIrrigationZoneValve,
)


@pytest.fixture
def irrigation() -> SimpleNamespace:
    """Return a representative sprinkler controller."""
    return SimpleNamespace(
        mac="AA:BB:CC:DD:EE:FF",
        nickname="Backyard Sprinkler",
        product_model="BS_WK1",
        sn="SPRINKLER123",
        available=True,
    )


@pytest.fixture
def zone() -> SimpleNamespace:
    """Return a representative sprinkler zone."""
    return SimpleNamespace(
        zone_number=2,
        name="Back Lawn",
        enabled=True,
        zone_id="zone-2",
        quickrun_duration=600,
    )


@pytest.fixture
def service() -> SimpleNamespace:
    """Return a mocked irrigation service."""
    return SimpleNamespace(
        start_zone=AsyncMock(),
        stop_running_schedule=AsyncMock(),
    )


@pytest.fixture
def coordinator(
    irrigation: SimpleNamespace,
    service: SimpleNamespace,
) -> Mock:
    """Return a mocked irrigation coordinator."""
    coordinator = Mock()
    coordinator.device = irrigation
    coordinator.data = WyzeIrrigationRuntimeData(irrigation, None)
    coordinator.last_update_success = True
    coordinator.irrigation_service = service
    coordinator.command_lock = asyncio.Lock()

    def set_running_zone(zone_number: int | None) -> None:
        coordinator.data = WyzeIrrigationRuntimeData(irrigation, zone_number)

    coordinator.set_running_zone.side_effect = set_running_zone
    return coordinator


@pytest.fixture
def entity(coordinator: Mock, zone: SimpleNamespace) -> WyzeIrrigationZoneValve:
    """Return a sprinkler zone valve."""
    valve = WyzeIrrigationZoneValve(coordinator, zone)
    valve._quickrun_duration = Mock(return_value=900)
    return valve


def test_valve_platform_is_registered() -> None:
    """The integration loads the valve platform."""
    assert "valve" in PLATFORMS


def test_state_and_device_information(
    entity: WyzeIrrigationZoneValve,
    coordinator: Mock,
) -> None:
    """Valve state and metadata reflect the controller and active zone."""
    assert entity.device_class is ValveDeviceClass.WATER
    assert entity.supported_features == (
        ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    )
    assert entity.unique_id == "AA:BB:CC:DD:EE:FF-zone-2-valve"
    assert entity.name == "Back Lawn"
    assert entity.is_closed is True
    assert entity.available is True
    assert entity.extra_state_attributes == {
        "zone_number": 2,
        "zone_id": "zone-2",
        "enabled": True,
    }

    coordinator.data = WyzeIrrigationRuntimeData(coordinator.device, 2)
    assert entity.is_closed is False

    coordinator.data = WyzeIrrigationRuntimeData(coordinator.device, 1)
    assert entity.is_closed is True


@pytest.mark.asyncio
async def test_open_valve_uses_configured_duration(
    entity: WyzeIrrigationZoneValve,
    coordinator: Mock,
    service: SimpleNamespace,
) -> None:
    """Opening a zone starts it for the configured quick-run duration."""
    await entity.async_open_valve()

    service.stop_running_schedule.assert_not_awaited()
    service.start_zone.assert_awaited_once_with(coordinator.device, 2, 900)
    coordinator.set_running_zone.assert_called_once_with(2)
    assert entity.is_closed is False


@pytest.mark.asyncio
async def test_open_valve_stops_another_running_zone_first(
    entity: WyzeIrrigationZoneValve,
    coordinator: Mock,
    service: SimpleNamespace,
) -> None:
    """Only one zone runs at a time."""
    coordinator.data = WyzeIrrigationRuntimeData(coordinator.device, 1)

    await entity.async_open_valve()

    service.stop_running_schedule.assert_awaited_once_with(coordinator.device)
    service.start_zone.assert_awaited_once_with(coordinator.device, 2, 900)
    assert coordinator.set_running_zone.call_args_list == [call(None), call(2)]


@pytest.mark.asyncio
async def test_close_active_valve_uses_global_stop(
    entity: WyzeIrrigationZoneValve,
    coordinator: Mock,
    service: SimpleNamespace,
) -> None:
    """Closing the active zone uses the controller's global stop operation."""
    coordinator.data = WyzeIrrigationRuntimeData(coordinator.device, 2)

    await entity.async_close_valve()

    service.stop_running_schedule.assert_awaited_once_with(coordinator.device)
    coordinator.set_running_zone.assert_called_once_with(None)
    assert entity.is_closed is True


@pytest.mark.asyncio
async def test_close_inactive_valve_is_a_noop(
    entity: WyzeIrrigationZoneValve,
    coordinator: Mock,
    service: SimpleNamespace,
) -> None:
    """Closing an inactive zone does not stop the active zone."""
    coordinator.data = WyzeIrrigationRuntimeData(coordinator.device, 1)

    await entity.async_close_valve()

    service.stop_running_schedule.assert_not_awaited()
    coordinator.set_running_zone.assert_not_called()


@pytest.mark.asyncio
async def test_api_failure_preserves_confirmed_state(
    entity: WyzeIrrigationZoneValve,
    coordinator: Mock,
    service: SimpleNamespace,
) -> None:
    """A failed start does not publish optimistic running state."""
    service.start_zone.side_effect = ClientConnectionError("offline")

    with pytest.raises(HomeAssistantError):
        await entity.async_open_valve()

    coordinator.set_running_zone.assert_not_called()
    assert entity.is_closed is True
