"""Tests for the Wyze thermostat climate entity."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.exceptions import ServiceValidationError
from wyzeapy.services.thermostat_service import HVACMode as WyzeHVACMode

from custom_components.wyzeapi.climate import WyzeThermostat

HEAT_SET_POINT = 64
COOL_SET_POINT = 76


def _entity(mode: WyzeHVACMode) -> tuple[WyzeThermostat, SimpleNamespace]:
    """Return a thermostat entity in the given Wyze mode and its service."""
    thermostat = SimpleNamespace(
        hvac_mode=mode,
        heat_set_point=HEAT_SET_POINT,
        cool_set_point=COOL_SET_POINT,
    )
    service = SimpleNamespace(
        set_heat_point=AsyncMock(),
        set_cool_point=AsyncMock(),
        set_hvac_mode=AsyncMock(),
    )
    entity = WyzeThermostat(service, thermostat)
    entity.async_schedule_update_ha_state = Mock()
    return entity, service


def _sent_set_points(service: SimpleNamespace) -> tuple[int | None, int | None]:
    """Return the (heat, cool) set points sent to Wyze, None if not sent."""

    def sent(setter: AsyncMock) -> int | None:
        if not setter.called:
            return None
        setter.assert_awaited_once()
        return setter.call_args.args[1]

    return sent(service.set_heat_point), sent(service.set_cool_point)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (WyzeHVACMode.HEAT, (70, None)),
        (WyzeHVACMode.COOL, (None, 70)),
    ],
)
@pytest.mark.asyncio
async def test_single_target_uses_the_active_mode_set_point(mode, expected) -> None:
    """A single target only sends the active mode's set point."""
    entity, service = _entity(mode)

    await entity.async_set_temperature(temperature=70)

    assert _sent_set_points(service) == expected


@pytest.mark.asyncio
async def test_single_target_does_not_revert_the_other_set_point() -> None:
    """A stale cached heat set point is not written back when cooling.

    If heat was changed in the Wyze app since the last refresh, resending the
    cached value would revert it on the thermostat.
    """
    entity, service = _entity(WyzeHVACMode.COOL)
    entity._thermostat.heat_set_point = 60  # stale: the app has since set 66

    await entity.async_set_temperature(temperature=72)

    service.set_heat_point.assert_not_called()
    assert entity._thermostat.heat_set_point == 60
    assert entity._thermostat.cool_set_point == 72


@pytest.mark.asyncio
async def test_single_target_after_mode_change_from_home_assistant() -> None:
    """A mode set from Home Assistant is used before the next refresh.

    The entity used to cache Home Assistant's HVACMode on the thermostat,
    which never compares equal to Wyze's mode, so a target set right after
    switching to cool was written to the heat set point.
    """
    entity, service = _entity(WyzeHVACMode.HEAT)

    await entity.async_set_hvac_mode(HVACMode.COOL)
    await entity.async_set_temperature(temperature=70)

    assert entity.hvac_mode == HVACMode.COOL
    assert _sent_set_points(service) == (None, 70)
    assert entity.target_temperature == 70


@pytest.mark.asyncio
async def test_hvac_mode_passed_with_the_target_is_applied_first() -> None:
    """climate.set_temperature with hvac_mode switches mode, then sets its point."""
    entity, service = _entity(WyzeHVACMode.HEAT)

    await entity.async_set_temperature(temperature=72, hvac_mode=HVACMode.COOL)

    service.set_hvac_mode.assert_awaited_once_with(
        entity._thermostat, WyzeHVACMode.COOL
    )
    assert _sent_set_points(service) == (None, 72)


@pytest.mark.parametrize("mode", [WyzeHVACMode.AUTO, WyzeHVACMode.OFF])
@pytest.mark.asyncio
async def test_single_target_outside_heat_or_cool_is_rejected(mode) -> None:
    """In auto or off there is no single set point, so nothing is written."""
    entity, service = _entity(mode)

    with pytest.raises(ServiceValidationError):
        await entity.async_set_temperature(temperature=70)

    service.set_heat_point.assert_not_called()
    service.set_cool_point.assert_not_called()


@pytest.mark.parametrize(
    "mode", [WyzeHVACMode.AUTO, WyzeHVACMode.HEAT, WyzeHVACMode.COOL]
)
@pytest.mark.asyncio
async def test_range_target_is_accepted_in_every_mode(mode) -> None:
    """Range calls keep working in heat and cool, not only in auto."""
    entity, service = _entity(mode)

    assert entity.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    await entity.async_set_temperature(target_temp_low=66, target_temp_high=74)

    assert _sent_set_points(service) == (66, 74)


@pytest.mark.asyncio
async def test_converted_targets_are_rounded() -> None:
    """21 °C arrives as 69.8 °F and must be sent as 70, not truncated to 69."""
    entity, service = _entity(WyzeHVACMode.HEAT)

    await entity.async_set_temperature(temperature=69.8)

    assert _sent_set_points(service) == (70, None)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (WyzeHVACMode.HEAT, HEAT_SET_POINT),
        (WyzeHVACMode.COOL, COOL_SET_POINT),
        (WyzeHVACMode.AUTO, None),
        (WyzeHVACMode.OFF, None),
    ],
)
def test_target_temperature_follows_the_mode(mode, expected) -> None:
    """Heat and cool expose one target; auto and off fall back to the range."""
    entity, _ = _entity(mode)

    assert entity.target_temperature == expected
    assert entity.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
