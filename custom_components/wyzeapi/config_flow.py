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

from .bridge import clean_bridge_stream_url, clean_bridge_url, default_bridge_playback
from .const import (
    DOMAIN,
    ACCESS_TOKEN,
    REFRESH_TOKEN,
    REFRESH_TIME,
    BULB_LOCAL_CONTROL,
    DEFAULT_LOCAL_CONTROL,
    CONF_BRIDGE_URL,
    CONF_BRIDGE_STREAM_URL,
    CONF_BRIDGE_RTSP,
    KEY_ID,
    API_KEY,
)

_LOGGER = logging.getLogger(__name__)

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

    def __init__(self):
        """Initialize."""
        self.client: Wyzeapy | None = None
        self.user_params = {}

    def _async_finish_auth(self):
        """Complete authentication for this flow's account."""
        if self.source == config_entries.SOURCE_REAUTH:
            entry = self.hass.config_entries.async_get_entry(
                self.context.get("entry_id")
            )
            if entry is None or entry.domain != DOMAIN:
                return self.async_abort(reason="reauth_entry_missing")
            if entry.data.get(CONF_USERNAME) != self.user_params[CONF_USERNAME]:
                return self.async_abort(reason="wrong_account")
            data = dict(entry.data)
            for key in (ACCESS_TOKEN, REFRESH_TOKEN, REFRESH_TIME):
                data.pop(key, None)
            return self.async_update_reload_and_abort(
                entry, data=data | self.user_params
            )
        if self._async_current_entries(include_ignore=True):
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(title="", data=self.user_params)

    async def async_step_user(
        self, user_input: Optional[dict[str, any]] = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        self.user_params = dict(user_input)
        if self.client is None:
            self.client = await Wyzeapy.create()

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
            return await self.async_step_2fa()
        else:
            return self._async_finish_auth()

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
            return self._async_finish_auth()

        return self.async_show_form(
            step_id="2fa", data_schema=STEP_2FA_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        entry = self.hass.config_entries.async_get_entry(self.context.get("entry_id"))
        if entry is None or entry.domain != DOMAIN:
            return self.async_abort(reason="reauth_entry_missing")
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the Wyze options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle an option flow for Wyze."""

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        errors: dict[str, str] = {}
        current = dict(self.config_entry.options)
        if user_input is not None:
            try:
                user_input[CONF_BRIDGE_URL] = clean_bridge_url(
                    user_input.get(CONF_BRIDGE_URL, "")
                )
            except ValueError:
                errors[CONF_BRIDGE_URL] = "invalid_bridge_url"
            try:
                user_input[CONF_BRIDGE_STREAM_URL] = clean_bridge_stream_url(
                    user_input.get(CONF_BRIDGE_STREAM_URL, "")
                )
            except ValueError:
                errors[CONF_BRIDGE_STREAM_URL] = "invalid_bridge_stream_url"
            else:
                if user_input.get(CONF_BRIDGE_RTSP) and not user_input[
                    CONF_BRIDGE_STREAM_URL
                ]:
                    errors[CONF_BRIDGE_STREAM_URL] = "bridge_stream_required"
            if not errors:
                return self.async_create_entry(title="", data=user_input)
            current.update(user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    BULB_LOCAL_CONTROL,
                    default=current.get(BULB_LOCAL_CONTROL, DEFAULT_LOCAL_CONTROL),
                ): bool,
                vol.Optional(
                    CONF_BRIDGE_URL,
                    default=current.get(CONF_BRIDGE_URL, ""),
                ): str,
                vol.Optional(
                    CONF_BRIDGE_STREAM_URL,
                    default=current.get(CONF_BRIDGE_STREAM_URL, ""),
                ): str,
                vol.Optional(
                    CONF_BRIDGE_RTSP,
                    default=default_bridge_playback(
                        current.get(CONF_BRIDGE_RTSP),
                        current.get(CONF_BRIDGE_STREAM_URL, ""),
                    ),
                ): bool,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
