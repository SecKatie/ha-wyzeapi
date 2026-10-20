import logging
from inspect import iscoroutinefunction

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from wyzeapy.exceptions import AccessTokenError, LoginError
from wyzeapy.wyze_auth_lib import Token

from .const import DOMAIN, ACCESS_TOKEN, REFRESH_TOKEN, REFRESH_TIME

_LOGGER = logging.getLogger(__name__)


class TokenManager:
    hass: HomeAssistant = None
    config_entry: ConfigEntry = None

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        TokenManager.hass = hass
        TokenManager.config_entry = config_entry

    @staticmethod
    async def token_callback(token: Token = None):
        _LOGGER.debug("TokenManager: Received new token, updating config entry.")
        if TokenManager.hass.config_entries.async_entries(DOMAIN):
            for entry in TokenManager.hass.config_entries.async_entries(DOMAIN):
                TokenManager.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        ACCESS_TOKEN: token.access_token,
                        REFRESH_TOKEN: token.refresh_token,
                        REFRESH_TIME: str(token.refresh_time),
                    },
                )


def token_exception_handler(func):
    async def inner_function(*args, **kwargs):
        try:
            if iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
        except (AccessTokenError, LoginError) as err:
            _LOGGER.error("TokenManager detected a login issue please re-login.")
            # Home Assistant only starts reauth on its own for
            # ConfigEntryAuthFailed raised from the entry setup or a
            # coordinator. Raised from a platform setup or an entity action it
            # is just logged, so start the reauth flow here. Home Assistant
            # ignores the call if a reauth flow is already in progress.
            if TokenManager.hass is not None and TokenManager.config_entry is not None:
                TokenManager.config_entry.async_start_reauth(TokenManager.hass)
            raise ConfigEntryAuthFailed("Unable to login, please re-login.") from err

    return inner_function
