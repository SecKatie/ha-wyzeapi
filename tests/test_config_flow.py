"""Tests for the Wyze options flow: general settings, RTSP credential
profiles, and per-camera RTSP configuration."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.wyzeapi.config_flow import (
    NONE_PROFILE_SENTINEL,
    OptionsFlowHandler,
)
from custom_components.wyzeapi.const import (
    CONF_CAMERAS,
    CONF_CLIENT,
    CONF_RTSP_ENABLED,
    CONF_RTSP_PASSWORD,
    CONF_RTSP_PROFILE,
    CONF_RTSP_PROFILES,
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
async def test_init_shows_a_menu_with_all_three_options(
    config_entry: SimpleNamespace, cameras: list[SimpleNamespace]
) -> None:
    """The top-level options step is a menu with all three areas."""
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_init()

    assert result["type"] == FlowResultType.MENU
    assert set(result["menu_options"]) == {"general", "rtsp_profiles", "camera_rtsp"}


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


# --- RTSP credential profile lifecycle: list/pick -> add or edit -> save/delete ---


@pytest.mark.asyncio
async def test_rtsp_profiles_with_none_existing_skips_straight_to_a_blank_edit_form(
    config_entry: SimpleNamespace, cameras: list[SimpleNamespace]
) -> None:
    """With nothing to pick from yet, go straight to creating the first profile."""
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_rtsp_profiles()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rtsp_profile_edit"
    defaults = {str(k): k.default() for k in result["data_schema"].schema}
    assert defaults["name"] == ""


@pytest.mark.asyncio
async def test_rtsp_profiles_with_existing_ones_shows_a_picker(
    cameras: list[SimpleNamespace],
) -> None:
    """With profiles already saved, offer a pick-one-or-add-new picker."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={CONF_RTSP_PROFILES: {"Wyze Account": {}, "Guest Account": {}}},
    )
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_rtsp_profiles()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rtsp_profiles"
    selector = result["data_schema"].schema[next(iter(result["data_schema"].schema))]
    assert selector.container["Wyze Account"] == "Wyze Account"
    assert selector.container["Guest Account"] == "Guest Account"
    assert selector.container["__new__"] == "+ Add new profile"


@pytest.mark.asyncio
async def test_picking_new_from_the_profile_picker_opens_a_blank_edit_form(
    cameras: list[SimpleNamespace],
) -> None:
    """Choosing "+ Add new profile" opens a blank create form."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={CONF_RTSP_PROFILES: {"Wyze Account": {}}},
    )
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_rtsp_profiles({"profile": "__new__"})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rtsp_profile_edit"
    schema = result["data_schema"].schema
    defaults = {str(k): k.default() for k in schema}
    assert defaults["name"] == ""
    assert "delete" not in {str(k) for k in schema}


@pytest.mark.asyncio
async def test_picking_an_existing_profile_opens_it_prefilled_with_a_delete_option(
    cameras: list[SimpleNamespace],
) -> None:
    """Choosing an existing profile opens it for editing, name fixed, deletable."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={
            CONF_RTSP_PROFILES: {
                "Wyze Account": {
                    CONF_RTSP_USERNAME: "wyze",
                    CONF_RTSP_PASSWORD: "hunter2",
                    CONF_RTSP_SECURE: True,
                }
            }
        },
    )
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_rtsp_profiles({"profile": "Wyze Account"})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "rtsp_profile_edit"
    schema = result["data_schema"].schema
    keys = {str(k) for k in schema}
    assert "name" not in keys  # identity is fixed once created, no silent rename
    assert "delete" in keys
    defaults = {str(k): k.default() for k in schema}
    assert defaults[CONF_RTSP_USERNAME] == "wyze"
    assert defaults[CONF_RTSP_PASSWORD] == "hunter2"
    assert defaults[CONF_RTSP_SECURE] is True
    assert defaults["delete"] is False


@pytest.mark.asyncio
async def test_saving_a_new_profile_creates_it_and_preserves_others(
    cameras: list[SimpleNamespace],
) -> None:
    """Saving a new profile keeps any existing profiles and other options."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={
            "bulb_local_control": False,
            CONF_RTSP_PROFILES: {
                "Existing": {
                    CONF_RTSP_USERNAME: "old",
                    CONF_RTSP_PASSWORD: "old-pass",
                    CONF_RTSP_SECURE: False,
                }
            },
        },
    )
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_rtsp_profile_edit(
        {
            "name": "Wyze Account",
            CONF_RTSP_USERNAME: "wyze",
            CONF_RTSP_PASSWORD: "hunter2",
            CONF_RTSP_SECURE: True,
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["bulb_local_control"] is False
    profiles = result["data"][CONF_RTSP_PROFILES]
    assert profiles["Existing"][CONF_RTSP_USERNAME] == "old"
    assert profiles["Wyze Account"] == {
        CONF_RTSP_USERNAME: "wyze",
        CONF_RTSP_PASSWORD: "hunter2",
        CONF_RTSP_SECURE: True,
    }


@pytest.mark.asyncio
async def test_saving_edits_to_an_existing_profile_updates_it_in_place(
    cameras: list[SimpleNamespace],
) -> None:
    """Editing an existing profile's password updates just that profile."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={
            CONF_RTSP_PROFILES: {
                "Wyze Account": {
                    CONF_RTSP_USERNAME: "wyze",
                    CONF_RTSP_PASSWORD: "old-pass",
                    CONF_RTSP_SECURE: False,
                },
                "Other": {
                    CONF_RTSP_USERNAME: "other",
                    CONF_RTSP_PASSWORD: "other-pass",
                    CONF_RTSP_SECURE: False,
                },
            }
        },
    )
    flow = _flow_for(config_entry, cameras)
    flow._editing_profile_name = "Wyze Account"

    result = await flow.async_step_rtsp_profile_edit(
        {
            CONF_RTSP_USERNAME: "wyze",
            CONF_RTSP_PASSWORD: "new-pass",
            CONF_RTSP_SECURE: True,
            "delete": False,
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    profiles = result["data"][CONF_RTSP_PROFILES]
    assert profiles["Wyze Account"][CONF_RTSP_PASSWORD] == "new-pass"
    assert profiles["Wyze Account"][CONF_RTSP_SECURE] is True
    assert profiles["Other"][CONF_RTSP_PASSWORD] == "other-pass"


@pytest.mark.asyncio
async def test_deleting_a_profile_removes_only_that_one(
    cameras: list[SimpleNamespace],
) -> None:
    """Checking delete removes the profile being edited, keeps the rest."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={
            CONF_RTSP_PROFILES: {
                "Wyze Account": {CONF_RTSP_USERNAME: "wyze"},
                "Other": {CONF_RTSP_USERNAME: "other"},
            }
        },
    )
    flow = _flow_for(config_entry, cameras)
    flow._editing_profile_name = "Wyze Account"

    result = await flow.async_step_rtsp_profile_edit(
        {
            CONF_RTSP_USERNAME: "wyze",
            CONF_RTSP_PASSWORD: "",
            CONF_RTSP_SECURE: False,
            "delete": True,
        }
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    profiles = result["data"][CONF_RTSP_PROFILES]
    assert "Wyze Account" not in profiles
    assert "Other" in profiles


# --- Camera picker + per-camera settings, including unlinking ---


@pytest.mark.asyncio
async def test_camera_rtsp_aborts_when_no_profiles_exist_yet(
    config_entry: SimpleNamespace, cameras: list[SimpleNamespace]
) -> None:
    """Configuring a camera before any credential profile exists is a dead end."""
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_camera_rtsp()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_rtsp_profiles"


@pytest.mark.asyncio
async def test_camera_rtsp_step_shows_a_picker_of_live_cameras(
    cameras: list[SimpleNamespace],
) -> None:
    """The camera picker lists real cameras fetched from the live client."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={CONF_RTSP_PROFILES: {"Wyze Account": {}}},
    )
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
    cameras: list[SimpleNamespace],
) -> None:
    """Submitting the picker moves straight to that camera's own field set."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={CONF_RTSP_PROFILES: {"Wyze Account": {}}},
    )
    flow = _flow_for(config_entry, cameras)

    result = await flow.async_step_camera_rtsp({"camera": "AA:BB:CC:DD:EE:FF"})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "camera_rtsp_settings"


@pytest.mark.asyncio
async def test_camera_settings_profile_picker_includes_an_unlink_option(
    cameras: list[SimpleNamespace],
) -> None:
    """The per-camera profile picker offers a "None" choice to unlink."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={
            CONF_RTSP_PROFILES: {
                "Wyze Account": {},
                "Guest Account": {},
            }
        },
    )
    flow = _flow_for(config_entry, cameras)
    flow._selected_camera_mac = "AA:BB:CC:DD:EE:FF"

    result = await flow.async_step_camera_rtsp_settings()

    schema = result["data_schema"].schema
    profile_key = next(k for k in schema if str(k) == CONF_RTSP_PROFILE)
    container = dict(schema[profile_key].container)
    assert container == {
        NONE_PROFILE_SENTINEL: "None (disable RTSP for this camera)",
        "Wyze Account": "Wyze Account",
        "Guest Account": "Guest Account",
    }


@pytest.mark.asyncio
async def test_camera_settings_default_to_unlinked_when_never_configured(
    cameras: list[SimpleNamespace],
) -> None:
    """A camera with no prior RTSP config defaults its picker to unlinked."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={CONF_RTSP_PROFILES: {"Wyze Account": {}}},
    )
    flow = _flow_for(config_entry, cameras)
    flow._selected_camera_mac = "AA:BB:CC:DD:EE:FF"

    result = await flow.async_step_camera_rtsp_settings()

    schema = result["data_schema"].schema
    defaults = {str(k): k.default() for k in schema}
    assert defaults[CONF_RTSP_PROFILE] == NONE_PROFILE_SENTINEL


@pytest.mark.asyncio
async def test_camera_settings_prefill_from_existing_config(
    cameras: list[SimpleNamespace],
) -> None:
    """Re-opening a previously configured camera shows its saved profile."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={
            CONF_RTSP_PROFILES: {"Wyze Account": {}},
            CONF_CAMERAS: {
                "AA:BB:CC:DD:EE:FF": {
                    CONF_RTSP_ENABLED: True,
                    CONF_RTSP_PROFILE: "Wyze Account",
                }
            },
        },
    )
    flow = _flow_for(config_entry, cameras)
    flow._selected_camera_mac = "AA:BB:CC:DD:EE:FF"

    result = await flow.async_step_camera_rtsp_settings()

    schema = result["data_schema"].schema
    defaults = {str(k): k.default() for k in schema}
    assert defaults[CONF_RTSP_PROFILE] == "Wyze Account"


@pytest.mark.asyncio
async def test_saving_a_profile_choice_merges_without_clobbering_other_cameras(
    cameras: list[SimpleNamespace],
) -> None:
    """Linking one camera to a profile preserves any other camera's config."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={
            CONF_RTSP_PROFILES: {"Wyze Account": {}},
            CONF_CAMERAS: {
                "11:22:33:44:55:66": {
                    CONF_RTSP_ENABLED: True,
                    CONF_RTSP_PROFILE: "Wyze Account",
                }
            },
        },
    )
    flow = _flow_for(config_entry, cameras)
    flow._selected_camera_mac = "AA:BB:CC:DD:EE:FF"

    result = await flow.async_step_camera_rtsp_settings(
        {CONF_RTSP_PROFILE: "Wyze Account"}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    saved = result["data"][CONF_CAMERAS]
    assert saved["11:22:33:44:55:66"] == {
        CONF_RTSP_ENABLED: True,
        CONF_RTSP_PROFILE: "Wyze Account",
    }
    assert saved["AA:BB:CC:DD:EE:FF"] == {
        CONF_RTSP_ENABLED: True,
        CONF_RTSP_PROFILE: "Wyze Account",
    }


@pytest.mark.asyncio
async def test_choosing_none_fully_unlinks_the_camera(
    cameras: list[SimpleNamespace],
) -> None:
    """Picking the None option removes the camera's entry entirely."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain=DOMAIN,
        options={
            CONF_RTSP_PROFILES: {"Wyze Account": {}},
            CONF_CAMERAS: {
                "AA:BB:CC:DD:EE:FF": {
                    CONF_RTSP_ENABLED: True,
                    CONF_RTSP_PROFILE: "Wyze Account",
                },
                "11:22:33:44:55:66": {
                    CONF_RTSP_ENABLED: True,
                    CONF_RTSP_PROFILE: "Wyze Account",
                },
            },
        },
    )
    flow = _flow_for(config_entry, cameras)
    flow._selected_camera_mac = "AA:BB:CC:DD:EE:FF"

    result = await flow.async_step_camera_rtsp_settings(
        {CONF_RTSP_PROFILE: NONE_PROFILE_SENTINEL}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    saved = result["data"][CONF_CAMERAS]
    assert "AA:BB:CC:DD:EE:FF" not in saved
    assert "11:22:33:44:55:66" in saved
