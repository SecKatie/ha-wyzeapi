"""Tests for the Wyze options flow, focused on per-camera RTSP config."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.wyzeapi.config_flow import OptionsFlowHandler
from custom_components.wyzeapi.const import (
    CONF_CAMERAS,
    CONF_CLIENT,
    CONF_RTSP_ENABLED,
    CONF_RTSP_PASSWORD,
    CONF_RTSP_SECURE,
    CONF_RTSP_USERNAME,
    DOMAIN,
)


@pytest.fixture
def cameras() -> list[SimpleNamespace]:
    """Return two representative camera devices."""
    return [
        SimpleNamespace(mac="AA:BB:CC:DD:EE:FF", nickname="Driveway Cam"),
        SimpleNamespace(mac="11:22:33:44:55:66", nickname="Garage Cam"),
    ]


@pytest.fixture
def config_entry() -> SimpleNamespace:
    """Return a config entry with no options configured yet."""
    return SimpleNamespace(entry_id="entry-1", domain=DOMAIN, options={})


def _flow_for(
    config_entry: SimpleNamespace, cameras: list[SimpleNamespace]
) -> OptionsFlowHandler:
    """Build an OptionsFlowHandler wired to a fake hass exposing the given cameras."""
    camera_service = SimpleNamespace(get_cameras=AsyncMock(return_value=cameras))
    camera_service_future = asyncio.Future()
    camera_service_future.set_result(camera_service)
    client = SimpleNamespace(camera_service=camera_service_future)
    hass = SimpleNamespace(
        data={DOMAIN: {config_entry.entry_id: {CONF_CLIENT: client}}},
        config_entries=SimpleNamespace(
            async_get_known_entry=lambda entry_id: config_entry
        ),
    )
    flow = OptionsFlowHandler()
    flow.hass = hass
    flow.handler = config_entry.entry_id
    return flow


@pytest.mark.asyncio
async def test_init_shows_a_menu_with_general_and_camera_options(
    config_entry: SimpleNamespace, cameras: list[SimpleNamespace]
) -> None:
    """The top-level options step is a menu, not a single form."""
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_init()

    assert result["type"] == FlowResultType.MENU
    assert set(result["menu_options"]) == {"general", "camera_rtsp"}


@pytest.mark.asyncio
async def test_general_step_still_offers_the_bulb_local_control_toggle(
    config_entry: SimpleNamespace, cameras: list[SimpleNamespace]
) -> None:
    """Moving the toggle behind a menu must not change its own behavior."""
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_general()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "general"

    result = await flow.async_step_general({"bulb_local_control": False})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {"bulb_local_control": False}


@pytest.mark.asyncio
async def test_camera_rtsp_step_shows_a_picker_of_live_cameras(
    config_entry: SimpleNamespace, cameras: list[SimpleNamespace]
) -> None:
    """The camera picker lists real cameras fetched from the live client."""
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_camera_rtsp()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "camera_rtsp"
    schema_keys = list(result["data_schema"].schema.keys())
    assert schema_keys[0] == "camera"
    selector = result["data_schema"].schema[schema_keys[0]]
    assert dict(selector.container) == {
        "AA:BB:CC:DD:EE:FF": "Driveway Cam",
        "11:22:33:44:55:66": "Garage Cam",
    }


@pytest.mark.asyncio
async def test_picking_a_camera_advances_to_its_settings_form(
    config_entry: SimpleNamespace, cameras: list[SimpleNamespace]
) -> None:
    """Submitting the picker moves straight to that camera's own field set."""
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_camera_rtsp({"camera": "AA:BB:CC:DD:EE:FF"})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "camera_rtsp_settings"


@pytest.mark.asyncio
async def test_camera_settings_default_to_disabled_when_never_configured(
    config_entry: SimpleNamespace, cameras: list[SimpleNamespace]
) -> None:
    """A camera with no prior RTSP config shows blank/disabled defaults."""
    flow = _flow_for(config_entry, cameras)
    flow._selected_camera_mac = "AA:BB:CC:DD:EE:FF"

    result = await flow.async_step_camera_rtsp_settings()

    schema = result["data_schema"].schema
    defaults = {str(k): k.default() for k in schema}
    assert defaults[CONF_RTSP_ENABLED] is False
    assert defaults[CONF_RTSP_USERNAME] == ""
    assert defaults[CONF_RTSP_SECURE] is False


@pytest.mark.asyncio
async def test_camera_settings_prefill_from_existing_config(
    cameras: list[SimpleNamespace],
) -> None:
    """Re-opening a previously configured camera shows its saved values."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={
            CONF_CAMERAS: {
                "AA:BB:CC:DD:EE:FF": {
                    CONF_RTSP_ENABLED: True,
                    CONF_RTSP_USERNAME: "wyze",
                    CONF_RTSP_PASSWORD: "hunter2",
                    CONF_RTSP_SECURE: True,
                }
            }
        },
    )
    flow = _flow_for(config_entry, cameras)
    flow._selected_camera_mac = "AA:BB:CC:DD:EE:FF"

    result = await flow.async_step_camera_rtsp_settings()

    schema = result["data_schema"].schema
    defaults = {str(k): k.default() for k in schema}
    assert defaults[CONF_RTSP_ENABLED] is True
    assert defaults[CONF_RTSP_USERNAME] == "wyze"
    assert defaults[CONF_RTSP_SECURE] is True


@pytest.mark.asyncio
async def test_saving_camera_settings_merges_without_clobbering_other_cameras(
    cameras: list[SimpleNamespace],
) -> None:
    """Saving one camera's RTSP config preserves any other camera's config."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={
            CONF_CAMERAS: {
                "11:22:33:44:55:66": {
                    CONF_RTSP_ENABLED: True,
                    CONF_RTSP_USERNAME: "wyze",
                    CONF_RTSP_PASSWORD: "existing-pass",
                    CONF_RTSP_SECURE: False,
                }
            }
        },
    )
    flow = _flow_for(config_entry, cameras)
    flow._selected_camera_mac = "AA:BB:CC:DD:EE:FF"

    result = await flow.async_step_camera_rtsp_settings(
        {
            CONF_RTSP_ENABLED: True,
            CONF_RTSP_USERNAME: "wyze",
            CONF_RTSP_PASSWORD: "new-pass",
            CONF_RTSP_SECURE: True,
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    saved = result["data"][CONF_CAMERAS]
    assert saved["11:22:33:44:55:66"][CONF_RTSP_PASSWORD] == "existing-pass"
    assert saved["AA:BB:CC:DD:EE:FF"] == {
        CONF_RTSP_ENABLED: True,
        CONF_RTSP_USERNAME: "wyze",
        CONF_RTSP_PASSWORD: "new-pass",
        CONF_RTSP_SECURE: True,
    }
