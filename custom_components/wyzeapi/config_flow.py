"""Config flow for Wyze Home Assistant Integration integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_ACCESS_TOKEN
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from wyzeapy import Wyzeapy, exceptions

from .const import (
    DOMAIN,
    ACCESS_TOKEN,
    REFRESH_TOKEN,
    REFRESH_TIME,
    BULB_LOCAL_CONTROL,
    CONF_CAMERAS,
    CONF_CLIENT,
    CONF_RTSP_ENABLED,
    CONF_RTSP_PASSWORD,
    CONF_RTSP_PROFILE,
    CONF_RTSP_PROFILES,
    CONF_RTSP_SECURE,
    CONF_RTSP_USERNAME,
    DEFAULT_LOCAL_CONTROL,
    KEY_ID,
    API_KEY,
)

_LOGGER = logging.getLogger(__name__)

# Sentinel stored nowhere -- picking it on a camera's profile selector means
# "no profile", which async_step_camera_rtsp_settings turns into fully
# removing that camera's entry rather than saving the sentinel itself.
NONE_PROFILE_SENTINEL = "__none__"

# Sentinel step-id for the "+ Add new profile" choice in the profile picker.
_NEW_PROFILE_SENTINEL = "__new__"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(KEY_ID): str,
        vol.Required(API_KEY): str,
    }
)
STEP_2FA_DATA_SCHEMA = vol.Schema({CONF_ACCESS_TOKEN: str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wyze Home Assistant Integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    client: Wyzeapy = None
    user_params = {}

    def __init__(self):
        """Initialize."""
        self.email = None
        self.password = None
        self.key_id = None
        self.api_key = None

    async def get_client(self):
        if not self.client:
            self.client = await Wyzeapy.create()

    async def async_step_user(
        self, user_input: Optional[dict[str, any]] = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        await self.get_client()

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        # noinspection PyBroadException
        try:
            await self.client.login(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[KEY_ID],
                user_input[API_KEY],
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except exceptions.AccessTokenError:
            errors["base"] = "invalid_auth"
        except exceptions.TwoFactorAuthenticationEnabled:
            self.user_params[CONF_USERNAME] = user_input[CONF_USERNAME]
            self.user_params[CONF_PASSWORD] = user_input[CONF_PASSWORD]
            self.user_params[KEY_ID] = user_input[KEY_ID]
            self.user_params[API_KEY] = user_input[API_KEY]
            return await self.async_step_2fa()
        else:
            if self.hass.config_entries.async_entries(DOMAIN):
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    self.hass.config_entries.async_update_entry(entry, data=user_input)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_2fa(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        if user_input is None:
            return self.async_show_form(step_id="2fa", data_schema=STEP_2FA_DATA_SCHEMA)

        errors = {}

        try:
            token = await self.client.login_with_2fa(
                user_input[CONF_ACCESS_TOKEN],
            )
        except exceptions.LoginError:
            errors["base"] = "invalid_auth"
        else:
            self.user_params[ACCESS_TOKEN] = token.access_token
            self.user_params[REFRESH_TOKEN] = token.refresh_token
            self.user_params[REFRESH_TIME] = token.refresh_time
            if self.hass.config_entries.async_entries(DOMAIN):
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    self.hass.config_entries.async_update_entry(
                        entry, data=self.user_params
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
            else:
                return self.async_create_entry(title="", data=self.user_params)

        return self.async_show_form(
            step_id="2fa", data_schema=STEP_2FA_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the Wyze options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an option flow for Wyze."""

    _selected_camera_mac: str | None = None
    _editing_profile_name: str | None = None

    async def async_step_init(self, user_input=None):
        """Show the top-level menu: general settings, RTSP credentials, or per-camera RTSP."""
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "general": "General settings",
                "rtsp_profiles": "Manage RTSP credentials",
                "camera_rtsp": "Configure camera RTSP snapshots",
            },
        )

    async def async_step_general(self, user_input=None):
        """Handle the general-settings step (was the whole flow before RTSP)."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    BULB_LOCAL_CONTROL,
                    default=self.config_entry.options.get(
                        BULB_LOCAL_CONTROL, DEFAULT_LOCAL_CONTROL
                    ),
                ): bool
            }
        )
        return self.async_show_form(step_id="general", data_schema=data_schema)

    async def async_step_rtsp_profiles(self, user_input=None):
        """Pick an existing RTSP credential profile to edit, or add a new one.

        Wyze RTSP logins are commonly reused across multiple cameras, so
        credentials live here as named profiles instead of being retyped
        on every camera's own settings form. With nothing saved yet there
        is nothing to pick, so this skips straight to a blank create form.
        """
        profiles = self.config_entry.options.get(CONF_RTSP_PROFILES, {})
        if not profiles:
            self._editing_profile_name = None
            return await self.async_step_rtsp_profile_edit()

        if user_input is not None:
            chosen = user_input["profile"]
            self._editing_profile_name = (
                None if chosen == _NEW_PROFILE_SENTINEL else chosen
            )
            return await self.async_step_rtsp_profile_edit()

        options = {name: name for name in profiles}
        options[_NEW_PROFILE_SENTINEL] = "+ Add new profile"
        data_schema = vol.Schema({vol.Required("profile"): vol.In(options)})
        return self.async_show_form(step_id="rtsp_profiles", data_schema=data_schema)

    async def async_step_rtsp_profile_edit(self, user_input=None):
        """Create a new RTSP credential profile, or edit/delete an existing one.

        A profile's name is its identity in options[CONF_RTSP_PROFILES] and
        in every camera that references it, so renaming isn't offered here
        -- only new profiles get a name field. Editing an existing one adds
        a delete checkbox instead.
        """
        name = self._editing_profile_name
        existing = (
            self.config_entry.options.get(CONF_RTSP_PROFILES, {}).get(name, {})
            if name
            else {}
        )

        if user_input is not None:
            updated_options = dict(self.config_entry.options)
            updated_profiles = dict(updated_options.get(CONF_RTSP_PROFILES, {}))
            if name is None:
                name = user_input.pop("name")
            elif user_input.pop("delete"):
                del updated_profiles[name]
                updated_options[CONF_RTSP_PROFILES] = updated_profiles
                return self.async_create_entry(title="", data=updated_options)
            updated_profiles[name] = user_input
            updated_options[CONF_RTSP_PROFILES] = updated_profiles
            return self.async_create_entry(title="", data=updated_options)

        schema_dict = {}
        if name is None:
            schema_dict[vol.Required("name", default="")] = str
        schema_dict[
            vol.Optional(
                CONF_RTSP_USERNAME, default=existing.get(CONF_RTSP_USERNAME, "")
            )
        ] = str
        schema_dict[
            vol.Optional(
                CONF_RTSP_PASSWORD, default=existing.get(CONF_RTSP_PASSWORD, "")
            )
        ] = str
        schema_dict[
            vol.Optional(
                CONF_RTSP_SECURE, default=existing.get(CONF_RTSP_SECURE, False)
            )
        ] = bool
        if name is not None:
            schema_dict[vol.Optional("delete", default=False)] = bool

        return self.async_show_form(
            step_id="rtsp_profile_edit", data_schema=vol.Schema(schema_dict)
        )

    async def async_step_camera_rtsp(self, user_input=None):
        """Show a picker for which camera's RTSP settings to configure."""
        profiles = self.config_entry.options.get(CONF_RTSP_PROFILES, {})
        if not profiles:
            return self.async_abort(reason="no_rtsp_profiles")

        if user_input is not None:
            self._selected_camera_mac = user_input["camera"]
            return await self.async_step_camera_rtsp_settings()

        client = self.hass.data[DOMAIN][self.config_entry.entry_id][CONF_CLIENT]
        camera_service = await client.camera_service
        cameras = await camera_service.get_cameras()

        data_schema = vol.Schema(
            {
                vol.Required("camera"): vol.In(
                    {camera.mac: camera.nickname for camera in cameras}
                )
            }
        )
        return self.async_show_form(step_id="camera_rtsp", data_schema=data_schema)

    async def async_step_camera_rtsp_settings(self, user_input=None):
        """Show (or save) which RTSP profile this camera should use.

        "Enabled" isn't a separate toggle -- picking a real profile means
        enabled, picking None removes the camera's entry entirely (fully
        unlinked, same end state as never having configured it).
        """
        mac = self._selected_camera_mac
        existing = self.config_entry.options.get(CONF_CAMERAS, {}).get(mac, {})
        profiles = self.config_entry.options.get(CONF_RTSP_PROFILES, {})

        if user_input is not None:
            updated_options = dict(self.config_entry.options)
            updated_cameras = dict(updated_options.get(CONF_CAMERAS, {}))
            chosen_profile = user_input[CONF_RTSP_PROFILE]
            if chosen_profile == NONE_PROFILE_SENTINEL:
                updated_cameras.pop(mac, None)
            else:
                updated_cameras[mac] = {
                    CONF_RTSP_ENABLED: True,
                    CONF_RTSP_PROFILE: chosen_profile,
                }
            updated_options[CONF_CAMERAS] = updated_cameras
            return self.async_create_entry(title="", data=updated_options)

        options = {NONE_PROFILE_SENTINEL: "None (disable RTSP for this camera)"}
        options.update({name: name for name in profiles})
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_RTSP_PROFILE,
                    default=existing.get(CONF_RTSP_PROFILE, NONE_PROFILE_SENTINEL),
                ): vol.In(options)
            }
        )
        return self.async_show_form(
            step_id="camera_rtsp_settings", data_schema=data_schema
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
