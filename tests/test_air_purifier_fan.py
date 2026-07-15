"""Tests for Wyze air purifier fan entities."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from aiohttp.client_exceptions import ClientConnectionError
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
import pytest
from wyzeapy.exceptions import AccessTokenError, ParameterError, UnknownApiError

from custom_components.wyzeapi import PLATFORMS
from custom_components.wyzeapi import fan as fan_module
from custom_components.wyzeapi.const import CONF_CLIENT, DOMAIN
from custom_components.wyzeapi.fan import WyzeAirPurifierFan


@pytest.fixture
def air_purifier() -> SimpleNamespace:
    """Return a representative air purifier."""
    return SimpleNamespace(
        mac="AA:BB:CC:DD:EE:FF",
        nickname="Office Purifier",
        product_model="CO_AP1",
        available=True,
        on=True,
        fan_mode="min",
        app_version="1.2.3",
        sn="PURIFIER123",
        wifi_mac="11:22:33:44:55:66",
    )


@pytest.fixture
def service() -> SimpleNamespace:
    """Return a mocked air purifier service."""
    return SimpleNamespace(
        get_air_purifiers=AsyncMock(return_value=[]),
        register_updater=Mock(),
        unregister_updater=Mock(),
        start_update_manager=AsyncMock(),
        turn_on=AsyncMock(),
        turn_off=AsyncMock(),
        set_fan_mode=AsyncMock(),
        update=AsyncMock(),
    )


@pytest.fixture
def entity(
    service: SimpleNamespace, air_purifier: SimpleNamespace
) -> WyzeAirPurifierFan:
    """Return an air purifier fan entity."""
    fan = WyzeAirPurifierFan(service, air_purifier)
    fan.async_schedule_update_ha_state = Mock()
    return fan


def test_fan_platform_is_registered() -> None:
    """The integration loads the air purifier fan platform."""
    assert "fan" in PLATFORMS


@pytest.mark.asyncio
async def test_setup_entry_adds_air_purifier_fans(
    service: SimpleNamespace,
    air_purifier: SimpleNamespace,
) -> None:
    """The real fan platform setup creates purifier entities."""
    service.get_air_purifiers.return_value = [air_purifier]
    service_future = asyncio.Future()
    service_future.set_result(service)
    client = SimpleNamespace(air_purifier_service=service_future)
    config_entry = SimpleNamespace(entry_id="entry-id")
    hass = SimpleNamespace(
        data={DOMAIN: {config_entry.entry_id: {CONF_CLIENT: client}}}
    )
    async_add_entities = Mock()

    await fan_module.async_setup_entry(hass, config_entry, async_add_entities)

    entities, update_before_add = async_add_entities.call_args.args
    assert update_before_add is True
    assert len(entities) == 1
    assert isinstance(entities[0], WyzeAirPurifierFan)
    service.get_air_purifiers.assert_awaited_once_with()


def test_state_and_device_information(
    entity: WyzeAirPurifierFan, air_purifier: SimpleNamespace
) -> None:
    """Fan state and device metadata reflect the library model."""
    assert entity.available is True
    assert entity.is_on is True
    assert entity.percentage == 25
    assert entity.preset_mode is None
    assert entity.speed_count == 4
    assert entity.unique_id == "AA:BB:CC:DD:EE:FF-fan"
    assert entity.device_info == {
        "identifiers": {("wyzeapi", "AA:BB:CC:DD:EE:FF")},
        "name": "Office Purifier",
        "manufacturer": "WyzeLabs",
        "model": "CO_AP1",
        "sw_version": "1.2.3",
        "serial_number": "PURIFIER123",
        "connections": {("mac", "11:22:33:44:55:66")},
    }

    air_purifier.fan_mode = "auto"
    assert entity.percentage is None
    assert entity.preset_mode == "auto"

    air_purifier.on = False
    assert entity.percentage == 0
    assert entity.preset_mode is None


@pytest.mark.asyncio
async def test_set_percentage_turns_on_and_sets_mode(
    entity: WyzeAirPurifierFan,
    service: SimpleNamespace,
    air_purifier: SimpleNamespace,
) -> None:
    """Selecting a speed turns on the purifier and updates its mode."""
    air_purifier.on = False

    await entity.async_set_percentage(50)

    service.turn_on.assert_awaited_once_with(air_purifier)
    service.set_fan_mode.assert_awaited_once_with(air_purifier, "mid")
    assert air_purifier.on is True
    assert air_purifier.fan_mode == "mid"
    entity.async_schedule_update_ha_state.assert_called_once_with()


@pytest.mark.asyncio
async def test_turn_off_updates_optimistic_state(
    entity: WyzeAirPurifierFan,
    service: SimpleNamespace,
    air_purifier: SimpleNamespace,
) -> None:
    """Turning off updates the model after the API call succeeds."""
    await entity.async_turn_off()

    service.turn_off.assert_awaited_once_with(air_purifier)
    assert air_purifier.on is False
    entity.async_schedule_update_ha_state.assert_called_once_with()


@pytest.mark.asyncio
async def test_updater_lifecycle(
    entity: WyzeAirPurifierFan,
    service: SimpleNamespace,
    air_purifier: SimpleNamespace,
) -> None:
    """The fan owns updater registration and manager startup."""
    await entity.async_added_to_hass()

    assert air_purifier.callback_function == entity.async_update_callback
    service.register_updater.assert_called_once_with(air_purifier, 30)
    service.start_update_manager.assert_awaited_once_with()

    await entity.async_will_remove_from_hass()

    service.unregister_updater.assert_called_once_with(air_purifier)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_exception"),
    [
        (AccessTokenError("expired token"), ConfigEntryAuthFailed),
        (ParameterError("invalid request"), HomeAssistantError),
        (UnknownApiError("unexpected response"), HomeAssistantError),
        (ClientConnectionError("offline"), HomeAssistantError),
    ],
    ids=["authentication", "parameter", "wyze-api", "connection"],
)
async def test_api_failure_does_not_change_optimistic_state(
    entity: WyzeAirPurifierFan,
    service: SimpleNamespace,
    air_purifier: SimpleNamespace,
    error: Exception,
    expected_exception: type[HomeAssistantError],
) -> None:
    """Failures preserve confirmed state and expose the expected HA error."""
    service.turn_off.side_effect = error

    with pytest.raises(expected_exception):
        await entity.async_turn_off()

    assert air_purifier.on is True
    entity.async_schedule_update_ha_state.assert_not_called()


@pytest.mark.asyncio
async def test_rejects_unknown_preset(
    entity: WyzeAirPurifierFan, service: SimpleNamespace
) -> None:
    """Unknown presets fail before an API request is made."""
    with pytest.raises(ValueError, match="Unsupported air purifier preset mode"):
        await entity.async_set_preset_mode("wind-tunnel")

    service.set_fan_mode.assert_not_awaited()


def test_update_callback_dispatches_to_sibling_entities(
    entity: WyzeAirPurifierFan,
    air_purifier: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Library callbacks update the fan and notify AQI sensors."""
    updated = SimpleNamespace(**vars(air_purifier))
    updated.fan_mode = "turbo"
    entity.hass = Mock()
    dispatcher_send = Mock()
    monkeypatch.setattr(fan_module, "async_dispatcher_send", dispatcher_send)

    entity.async_update_callback(updated)

    assert entity.percentage == 100
    dispatcher_send.assert_called_once_with(
        entity.hass,
        "wyzeapi.air_purifier_updated-AA:BB:CC:DD:EE:FF",
        updated,
    )
    entity.async_schedule_update_ha_state.assert_called_once_with()
