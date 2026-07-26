"""Tests for Wyze Scale refresh button."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.wyzeapi.button import WyzeScaleRefreshButton
from custom_components.wyzeapi.const import SCALE_UPDATED


@pytest.fixture
def scale() -> SimpleNamespace:
    """Return a representative scale device."""
    return SimpleNamespace(
        mac="AA:BB:CC:DD:EE:FF",
        nickname="Bathroom Scale",
        product_model="WL_SC2",
        firmware_ver="1.0.0",
    )


@pytest.fixture
def scale_service(scale: SimpleNamespace) -> Mock:
    """Return a mock scale service that returns the scale on update."""
    service = Mock()
    service.update = AsyncMock(return_value=scale)
    return service


async def test_refresh_button_fetches_and_dispatches(
    scale: SimpleNamespace, scale_service: Mock
) -> None:
    """Pressing refresh should call Wyze and notify scale sensors."""
    button = WyzeScaleRefreshButton(scale_service, scale)
    button.hass = Mock()

    with patch(
        "custom_components.wyzeapi.button.async_dispatcher_send"
    ) as mock_dispatch:
        await button.async_press()

    scale_service.update.assert_awaited_once_with(scale)
    mock_dispatch.assert_called_once_with(
        button.hass,
        f"{SCALE_UPDATED}-{scale.mac}",
        scale,
    )


async def test_refresh_button_raises_on_failure(
    scale: SimpleNamespace, scale_service: Mock
) -> None:
    """Refresh failures should surface as HomeAssistantError."""
    from homeassistant.exceptions import HomeAssistantError

    scale_service.update = AsyncMock(side_effect=RuntimeError("cloud down"))
    button = WyzeScaleRefreshButton(scale_service, scale)
    button.hass = Mock()

    with pytest.raises(HomeAssistantError, match="Failed to refresh scale"):
        await button.async_press()
