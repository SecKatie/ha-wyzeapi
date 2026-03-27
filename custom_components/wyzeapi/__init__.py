"""The Wyze Home Assistant Integration."""

from __future__ import annotations

import logging

from aiohttp.client_exceptions import ClientConnectorError
from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady, SOURCE_IMPORT
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.check_config import HomeAssistantConfig
from homeassistant.components import bluetooth
from wyzeapy import Wyzeapy
from wyzeapy.exceptions import AccessTokenError
from wyzeapy.wyze_auth_lib import Token

from .const import (
    DOMAIN,
    CONF_CLIENT,
    ACCESS_TOKEN,
    REFRESH_TOKEN,
    REFRESH_TIME,
    WYZE_NOTIFICATION_TOGGLE,
    BULB_LOCAL_CONTROL,
    DEFAULT_LOCAL_CONTROL,
    KEY_ID,
    API_KEY,
)
from .coordinator import WyzeLockBoltCoordinator
from .iot3_coordinator import WyzeLockBoltV2Coordinator
from .iot3_service import Iot3Service
from .token_manager import TokenManager

PLATFORMS = [
    "light",
    "switch",
    "lock",
    "climate",
    "alarm_control_panel",
    "sensor",
    "siren",
    "cover",
    "number",
    "button",
]  # Fixme: Re add scene
_LOGGER = logging.getLogger(__name__)


# noinspection PyUnusedLocal
async def async_setup(
    hass: HomeAssistant, config: HomeAssistantConfig, discovery_info=None
):
    # pylint: disable=unused-argument
    """Set up the WyzeApi domain."""
    if hass.config_entries.async_entries(DOMAIN):
        _LOGGER.debug(
            "Nothing to import from configuration.yaml, loading from Integrations",
        )
        return True

    # noinspection SpellCheckingInspection
    domainconfig = config.get(DOMAIN)
    # pylint: disable=logging-not-lazy
    _LOGGER.debug(
        "Importing config information for %s from configuration.yml"
        % domainconfig[CONF_USERNAME]
    )
    if hass.config_entries.async_entries(DOMAIN):
        _LOGGER.debug("Found existing config entries")
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry:
                entry_data = entry.as_dict().get("data")
                hass.config_entries.async_update_entry(
                    entry,
                    data=entry_data,
                )
                break
    else:
        _LOGGER.debug("Creating new config entry")
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_USERNAME: domainconfig[CONF_USERNAME],
                    CONF_PASSWORD: domainconfig[CONF_PASSWORD],
                    ACCESS_TOKEN: domainconfig[ACCESS_TOKEN],
                    REFRESH_TOKEN: domainconfig[REFRESH_TOKEN],
                    REFRESH_TIME: domainconfig[REFRESH_TIME],
                    KEY_ID: domainconfig[KEY_ID],
                    API_KEY: domainconfig[API_KEY],
                },
            )
        )
    return True


# noinspection DuplicatedCode
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Wyze Home Assistant Integration from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    key_id = config_entry.data.get(KEY_ID)
    api_key = config_entry.data.get(API_KEY)

    client = await Wyzeapy.create()
    token = None
    if config_entry.data.get(ACCESS_TOKEN):
        token = Token(
            config_entry.data.get(ACCESS_TOKEN),
            config_entry.data.get(REFRESH_TOKEN),
            float(config_entry.data.get(REFRESH_TIME)),
        )
    a_tkn_manager = TokenManager(hass, config_entry)
    client.register_for_token_callback(a_tkn_manager.token_callback)
    # We should probably try/catch here to invalidate the login credentials and throw a notification if we cannot get
    # a login with the token
    try:
        await client.login(
            config_entry.data.get(CONF_USERNAME),
            config_entry.data.get(CONF_PASSWORD),
            key_id,
            api_key,
            token,
        )
    except ClientConnectorError as e:
        raise ConfigEntryNotReady("Unable to login due to network issues.") from e
    except AccessTokenError as e:
        _LOGGER.error(
            "Wyzeapi: Could not login. Please re-login through integration configuration"
        )
        _LOGGER.error(e)
        raise ConfigEntryAuthFailed("Unable to login, please re-login.") from None

    hass.data[DOMAIN][config_entry.entry_id] = {
        CONF_CLIENT: client,
        "key_id": KEY_ID,
        "api_key": API_KEY,
    }
    await setup_coordinators(hass, config_entry, client)

    options_dict = {
        BULB_LOCAL_CONTROL: config_entry.options.get(
            BULB_LOCAL_CONTROL, DEFAULT_LOCAL_CONTROL
        )
    }
    hass.config_entries.async_update_entry(config_entry, options=options_dict)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    mac_addresses = await client.unique_device_ids

    mac_addresses.add(WYZE_NOTIFICATION_TOGGLE)

    hms_service = await client.hms_service
    hms_id = hms_service.hms_id
    if hms_id is not None:
        mac_addresses.add(hms_id)

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        for identifier in device.identifiers:
            # domain has to remain here. If it is removed the integration will remove all entities for not being in
            # the mac address list each boot.
            domain, mac = identifier
            if mac not in mac_addresses:
                _LOGGER.warning(
                    "%s is not in the mac_addresses list, removing the entry", mac
                )
                device_registry.async_remove_device(device.id)
    return True


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.debug("Updated options")
    entry_data = config_entry.as_dict().get("data")
    hass.config_entries.async_update_entry(
        config_entry,
        data=entry_data,
    )
    _LOGGER.debug("Reload entry: " + config_entry.entry_id)
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def setup_coordinators(
    hass: HomeAssistant, config_entry: ConfigEntry, client: Wyzeapy
):
    """Set up coordinators for Wyze Lock Bolt devices (BLE and IoT3)."""
    from .const import IOT3_MODELS

    lock_service = await client.lock_service
    all_locks = await lock_service.get_locks()
    coordinators = hass.data[DOMAIN][config_entry.entry_id].setdefault(
        "coordinators", {}
    )

    # IoT3 devices have product_type "Common" so get_locks() won't find them.
    # Search the full device list by product_model instead.
    all_devices = await lock_service.get_object_list()
    iot3_devices = [d for d in all_devices if d.product_model in IOT3_MODELS]
    # Store them so lock.py can find them later
    hass.data[DOMAIN][config_entry.entry_id]["iot3_devices"] = iot3_devices

    # IoT3 coordinators for DX-family locks (no Bluetooth needed)
    iot3_locks = iot3_devices
    if iot3_locks:
        iot3_service = Iot3Service(hass, config_entry)
        hass.data[DOMAIN][config_entry.entry_id]["iot3_service"] = iot3_service
        for lock in iot3_locks:
            _LOGGER.info(
                "Setting up IoT3 coordinator for %s (%s)",
                lock.nickname,
                lock.product_model,
            )
            coordinators[lock.mac] = WyzeLockBoltV2Coordinator(
                hass, iot3_service, lock
            )

    # BLE coordinators for YD_BT1 Lock Bolt v1
    if bluetooth.async_scanner_count(hass, connectable=True) == 0:
        if any(l.product_model == "YD_BT1" for l in all_locks):
            _LOGGER.info(
                "Bluetooth is not active. Skipping WyzeLockBoltCoordinator setup."
            )
        return

    for lock in all_locks:
        if lock.product_model == "YD_BT1":
            coordinators[lock.mac] = WyzeLockBoltCoordinator(hass, lock_service, lock)
            await coordinators[lock.mac].update_lock_info()
