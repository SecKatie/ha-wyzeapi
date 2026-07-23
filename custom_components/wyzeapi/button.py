"""Platform for button integration."""

from collections.abc import Callable
import logging
from typing import Any

from aiohttp.client_exceptions import ClientConnectionError
from wyzeapy import Wyzeapy
from wyzeapy.services.irrigation_service import Irrigation, IrrigationService
from wyzeapy.services.switch_service import Switch

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import EntityCategory

from .const import CONF_CLIENT, DOMAIN, IRRIGATION_UPDATED, RESET_BUTTON_PRESSED
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
OUTDOOR_PLUGS = ["WLPPO"]


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Any], bool], None],
) -> None:
    """This function sets up the config entry.

    :param hass: The Home Assistant Instance
    :param config_entry: The current config entry
    :param async_add_entities: This function adds entities to the config entry
    :return:
    """

    _LOGGER.debug("""Creating new Wyze button component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    irrigation_service = await client.irrigation_service
    switch_service = await client.switch_service

    # Get all irrigation devices
    irrigation_devices = await irrigation_service.get_irrigations()

    buttons = []
    for device in irrigation_devices:
        device = await irrigation_service.update(device)
        buttons.append(WyzeIrrigationStopAllButton(irrigation_service, device))

    plugs = await switch_service.get_switches()
    buttons.extend(
        [
            WyzePowerSensorResetButton(plug)
            for plug in plugs
            if plug.product_model in OUTDOOR_PLUGS
        ]
    )

    async_add_entities(buttons, True)


class WyzeIrrigationStopAllButton(ButtonEntity):
    """Representation of a Wyze Irrigation Stop All Schedules Button."""

    _attr_name = "Stop All Zones"

    def __init__(
        self, irrigation_service: IrrigationService, irrigation: Irrigation
    ) -> None:
        """Initialize the irrigation stop all button."""
        self._irrigation_service = irrigation_service
        self._device = irrigation

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the button."""
        return f"Stop All {self._device.mac}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.mac)},
            name=self._device.nickname,
            manufacturer="WyzeLabs",
            model=self._device.product_model,
            serial_number=self._device.sn,
            connections={(dr.CONNECTION_NETWORK_MAC, self._device.mac)},
        )

    @property
    def device_class(self) -> str:
        """Return the device class of the button."""
        return ButtonDeviceClass.RESTART

    @property
    def icon(self) -> str:
        """Return the icon for the stop all button."""
        return "mdi:octagon"

    async def async_press(self) -> None:
        """Stop all running irrigation schedules.

        This method is called when the button is pressed in Home Assistant.
        It will stop all running irrigation schedules for the device.

        Raises:
            HomeAssistantError: If the schedules cannot be stopped.
        """
        try:
            await self._irrigation_service.stop_running_schedule(self._device)
            async_dispatcher_send(
                self.hass,
                f"{IRRIGATION_UPDATED}-{self._device.mac}",
                None,
            )
        except ClientConnectionError as err:
            raise HomeAssistantError(f"Failed to stop schedules: {err}") from err
        except Exception as err:
            _LOGGER.error("Error stopping schedules: %s", err)
            raise HomeAssistantError(f"Failed to stop schedules: {err}") from err


class WyzePowerSensorResetButton(ButtonEntity):
    """Wyze Power Sensor Reset Button."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Energy Usage Reset"

    def __init__(self, switch: Switch) -> None:
        """Initialize a power sensor reset button."""
        self._switch = switch

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._switch.mac)},
            name=self._switch.nickname,
        )

    @property
    def unique_id(self) -> str:
        """Create a unique ID for the button."""
        return f"{self._switch.mac} Reset button"

    async def async_press(self) -> None:
        """Reset the sensor usage."""
        async_dispatcher_send(
            self.hass,
            f"{RESET_BUTTON_PRESSED}-{self._switch.mac}",
            self._switch,
        )
