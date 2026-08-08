"""Tests for the Wyze robot vacuum entity."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from aiohttp.client_exceptions import ClientConnectionError
from homeassistant.components.vacuum import VacuumActivity, VacuumEntityFeature
from homeassistant.exceptions import HomeAssistantError
import pytest
from wyzeapy.exceptions import ParameterError, UnknownApiError
from wyzeapy.services.vacuum_service import (
    VacuumFaultCode,
    VacuumMode,
    VacuumSuctionLevel,
)

from custom_components.wyzeapi import PLATFORMS
from custom_components.wyzeapi import vacuum as vacuum_module
from custom_components.wyzeapi.const import CONF_CLIENT, DOMAIN
from custom_components.wyzeapi.vacuum import WyzeVacuum


@pytest.fixture
def vacuum() -> SimpleNamespace:
    """Return a representative vacuum, docked and charged."""
    return SimpleNamespace(
        mac="JA_RO2_ABCDEF1234567890",
        nickname="Diogee",
        product_model="JA_RO2",
        available=True,
        mode=VacuumMode.IDLE,
        battery=100,
        charging=True,
        clean_size=0,
        clean_time=0,
        suction_level=VacuumSuctionLevel.QUIET,
        fault_code=2105,
        fault=None,
        current_map_id=None,
        filter_remaining=461,
        side_brush_remaining=445,
        main_brush_remaining=461,
        callback_function=None,
    )


@pytest.fixture
def service() -> SimpleNamespace:
    """Return a mocked vacuum service."""
    return SimpleNamespace(
        get_vacuums=AsyncMock(return_value=[]),
        register_updater=Mock(),
        unregister_updater=Mock(),
        start_update_manager=AsyncMock(),
        sweep=AsyncMock(),
        pause=AsyncMock(),
        return_to_charge=AsyncMock(),
        stop=AsyncMock(),
        set_suction_level=AsyncMock(),
        sweep_rooms=AsyncMock(),
        get_rooms=AsyncMock(return_value={}),
        update=AsyncMock(),
    )


@pytest.fixture
def entity(service, vacuum) -> WyzeVacuum:
    """Return a vacuum entity wired to the mocked service."""
    entity = WyzeVacuum(service, vacuum)
    entity.async_schedule_update_ha_state = Mock()
    entity.hass = Mock()
    return entity


def test_vacuum_is_a_registered_platform():
    assert "vacuum" in PLATFORMS


@pytest.mark.asyncio
async def test_async_setup_entry_creates_one_entity_per_vacuum(service, vacuum):
    """The real vacuum platform setup creates one entity per discovered vacuum."""
    service.get_vacuums.return_value = [vacuum]
    service_future = asyncio.Future()
    service_future.set_result(service)
    client = SimpleNamespace(vacuum_service=service_future)
    config_entry = SimpleNamespace(entry_id="entry-id")
    hass = SimpleNamespace(
        data={DOMAIN: {config_entry.entry_id: {CONF_CLIENT: client}}}
    )
    async_add_entities = Mock()

    await vacuum_module.async_setup_entry(hass, config_entry, async_add_entities)

    entities, update_before_add = async_add_entities.call_args.args
    assert update_before_add is True
    assert len(entities) == 1
    assert isinstance(entities[0], WyzeVacuum)
    assert entities[0].unique_id == f"{vacuum.mac}-vacuum"


def test_supported_features_cover_the_venus_command_set(entity):
    for feature in (
        VacuumEntityFeature.START,
        VacuumEntityFeature.PAUSE,
        VacuumEntityFeature.STOP,
        VacuumEntityFeature.RETURN_HOME,
        VacuumEntityFeature.FAN_SPEED,
        VacuumEntityFeature.BATTERY,
        VacuumEntityFeature.STATE,
    ):
        assert entity.supported_features & feature


def test_device_info_identifies_the_vacuum(entity, vacuum):
    info = entity.device_info

    assert info["identifiers"] == {(DOMAIN, vacuum.mac)}
    assert info["name"] == "Diogee"
    assert info["model"] == "JA_RO2"
    assert info["manufacturer"] == "WyzeLabs"


@pytest.mark.parametrize(
    ("mode", "charging", "expected"),
    [
        (VacuumMode.IDLE, True, VacuumActivity.DOCKED),
        (VacuumMode.IDLE, False, VacuumActivity.IDLE),
        (VacuumMode.CLEANING, False, VacuumActivity.CLEANING),
        (VacuumMode.SWEEPING, False, VacuumActivity.CLEANING),
        (VacuumMode.MAPPING, False, VacuumActivity.CLEANING),
        (VacuumMode.PAUSED, False, VacuumActivity.PAUSED),
        (VacuumMode.MAPPING_PAUSED, False, VacuumActivity.PAUSED),
        (VacuumMode.RETURNING_TO_CHARGE, False, VacuumActivity.RETURNING),
        (VacuumMode.FINISHED_RETURNING_TO_CHARGE, False, VacuumActivity.RETURNING),
        (VacuumMode.DOCKED_NOT_COMPLETE, True, VacuumActivity.DOCKED),
        (VacuumMode.UNKNOWN, False, VacuumActivity.IDLE),
    ],
)
def test_activity_maps_every_mode(entity, vacuum, mode, charging, expected):
    vacuum.mode = mode
    vacuum.charging = charging

    assert entity.activity is expected


def test_a_fault_wins_over_the_reported_mode(entity, vacuum):
    """A vacuum stuck mid-clean still reports CLEANING; the fault is the real state."""
    vacuum.mode = VacuumMode.CLEANING
    vacuum.fault_code = 510
    vacuum.fault = VacuumFaultCode.COLLISION_EXCEPTION

    assert entity.activity is VacuumActivity.ERROR


def test_an_undocumented_fault_code_is_not_an_error(entity, vacuum):
    """The real device reports 2105 while healthy and docked, on every read."""
    vacuum.mode = VacuumMode.CLEANING
    vacuum.charging = False
    vacuum.fault_code = 2105
    vacuum.fault = None

    assert entity.activity is VacuumActivity.CLEANING


def test_battery_and_fan_speed_are_reported(entity):
    assert entity.battery_level == 100
    assert entity.fan_speed == "Quiet"
    assert entity.fan_speed_list == ["Quiet", "Standard", "Strong"]


def test_extra_attributes_expose_consumable_life(entity):
    attributes = entity.extra_state_attributes

    assert attributes["filter_remaining"] == 461
    assert attributes["side_brush_remaining"] == 445
    assert attributes["main_brush_remaining"] == 461
    assert attributes["fault_code"] == 2105
    assert attributes["fault"] is None


def test_availability_follows_the_device(entity, vacuum):
    assert entity.available is True
    vacuum.available = False
    assert entity.available is False


def test_a_sleeping_vacuum_stays_unavailable_though_its_state_still_reads(
    entity, vacuum
):
    """Sleep is unavailability here, deliberately, and this pins that down.

    A docked JA_RO2 reports `iot_state: disconnected` while the cloud keeps
    answering reads, so battery and mode are still populated and it is tempting to
    call the entity available. Wyze refuses every command in that state with code
    3000, so availability has to follow the device, not the readability of state.
    """
    vacuum.available = False

    assert entity.available is False
    assert entity.battery_level == 100
    assert entity.activity is VacuumActivity.DOCKED


@pytest.mark.asyncio
async def test_start_sweeps(entity, service, vacuum):
    await entity.async_start()

    service.sweep.assert_awaited_once_with(vacuum)


@pytest.mark.asyncio
async def test_pause_pauses(entity, service, vacuum):
    await entity.async_pause()

    service.pause.assert_awaited_once_with(vacuum)


@pytest.mark.asyncio
async def test_return_to_base_docks(entity, service, vacuum):
    await entity.async_return_to_base()

    service.return_to_charge.assert_awaited_once_with(vacuum)


@pytest.mark.asyncio
async def test_stop_cancels_the_return(entity, service, vacuum):
    await entity.async_stop()

    service.stop.assert_awaited_once_with(vacuum)


@pytest.mark.asyncio
async def test_set_fan_speed_sets_the_suction_level(entity, service, vacuum):
    await entity.async_set_fan_speed("Strong")

    service.set_suction_level.assert_awaited_once_with(
        vacuum, VacuumSuctionLevel.STRONG
    )
    assert vacuum.suction_level is VacuumSuctionLevel.STRONG


@pytest.mark.asyncio
async def test_set_fan_speed_rejects_an_unknown_speed(entity, service):
    with pytest.raises(HomeAssistantError):
        await entity.async_set_fan_speed("Turbo")

    service.set_suction_level.assert_not_awaited()


@pytest.mark.parametrize(
    "error", [ParameterError("boom"), UnknownApiError("boom"), ClientConnectionError()]
)
@pytest.mark.asyncio
async def test_a_service_error_surfaces_as_a_home_assistant_error(
    entity, service, error
):
    service.sweep.side_effect = error

    with pytest.raises(HomeAssistantError):
        await entity.async_start()


@pytest.mark.asyncio
async def test_an_offline_refusal_says_the_vacuum_is_asleep(entity, service):
    """The poll/command race gets a sentence, not the raw Wyze error dict.

    Availability normally stops a command to a sleeping vacuum before it is sent,
    so this fires when it falls asleep between the two.
    """
    service.sweep.side_effect = UnknownApiError(
        {"code": 3000, "message": "Device is offline", "data": None}
    )

    with pytest.raises(HomeAssistantError) as raised:
        await entity.async_start()

    assert "Diogee is asleep" in str(raised.value)


@pytest.mark.asyncio
async def test_a_non_offline_error_keeps_the_raw_detail(entity, service):
    """Only code 3000 is translated; anything else must not lose its detail."""
    service.sweep.side_effect = UnknownApiError(
        {"code": 1004, "message": "Signature2 is invalid"}
    )

    with pytest.raises(HomeAssistantError) as raised:
        await entity.async_start()

    assert "Signature2 is invalid" in str(raised.value)
    assert "asleep" not in str(raised.value)


@pytest.mark.asyncio
async def test_update_skips_the_poll_right_after_a_command(entity, service):
    await entity.async_start()
    service.update.reset_mock()

    await entity.async_update()

    service.update.assert_not_awaited()

    await entity.async_update()

    service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_command_cleans_rooms_by_name(entity, service, vacuum):
    entity._rooms = {"Kitchen": 16, "Laundry": 14}

    await entity.async_send_command("clean_rooms", {"rooms": ["Kitchen", "Laundry"]})

    service.sweep_rooms.assert_awaited_once_with(vacuum, [16, 14])


@pytest.mark.asyncio
async def test_send_command_accepts_room_ids(entity, service, vacuum):
    entity._rooms = {"Kitchen": 16}

    await entity.async_send_command("clean_rooms", {"rooms": [16]})

    service.sweep_rooms.assert_awaited_once_with(vacuum, [16])


@pytest.mark.asyncio
async def test_send_command_accepts_a_bare_room_name(entity, service, vacuum):
    entity._rooms = {"Kitchen": 16}

    await entity.async_send_command("clean_rooms", {"rooms": "Kitchen"})

    service.sweep_rooms.assert_awaited_once_with(vacuum, [16])


@pytest.mark.asyncio
async def test_send_command_matches_a_room_name_case_insensitively(
    entity, service, vacuum
):
    entity._rooms = {"Master Bedroom": 12}

    await entity.async_send_command("clean_rooms", {"rooms": ["master bedroom"]})

    service.sweep_rooms.assert_awaited_once_with(vacuum, [12])


@pytest.mark.asyncio
async def test_send_command_names_the_known_rooms_when_one_is_wrong(entity, service):
    entity._rooms = {"Kitchen": 16, "Laundry": 14}

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_send_command("clean_rooms", {"rooms": ["Kitchn"]})

    assert "Kitchen" in str(err.value)
    service.sweep_rooms.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_command_rejects_an_empty_room_list(entity, service):
    entity._rooms = {"Kitchen": 16}

    with pytest.raises(HomeAssistantError):
        await entity.async_send_command("clean_rooms", {"rooms": []})

    service.sweep_rooms.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_command_rejects_an_unknown_command(entity, service):
    with pytest.raises(HomeAssistantError):
        await entity.async_send_command("mow_the_lawn", {})

    service.sweep_rooms.assert_not_awaited()


def test_rooms_are_exposed_as_an_attribute(entity):
    entity._rooms = {"Kitchen": 16, "Laundry": 14}

    assert entity.extra_state_attributes["rooms"] == ["Kitchen", "Laundry"]


@pytest.mark.asyncio
async def test_added_to_hass_registers_the_updater(entity, service, vacuum):
    await entity.async_added_to_hass()

    service.register_updater.assert_called_once_with(vacuum, 30)
    service.start_update_manager.assert_awaited_once()
    assert vacuum.callback_function == entity.async_update_callback


@pytest.mark.asyncio
async def test_removal_unregisters_the_updater(entity, service, vacuum):
    await entity.async_will_remove_from_hass()

    service.unregister_updater.assert_called_once_with(vacuum)
