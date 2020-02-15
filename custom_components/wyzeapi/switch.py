#!/usr/bin/python3

"""Platform for switch integration."""
import logging
from .wyzeapi.wyzeapi import WyzeApi
from . import DOMAIN

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
# Import the device class from the component that you want to support
from homeassistant.components.switch import (
	PLATFORM_SCHEMA,
	SwitchDevice
	)

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, add_entities, discovery_info=None):
	"""Set up the Wyze Switch platform."""
	_LOGGER.debug("""Creating new WyzeApi switch component""")

	# Add devices
	add_entities(WyzeSwitch(switch) for switch in await hass.data[DOMAIN]["wyzeapi_account"].async_list_switches())

class WyzeSwitch(SwitchDevice):
	"""Representation of a Wyze Switch."""

	def __init__(self, switch):
		"""Initialize a Wyze Switch."""
		self._switch = switch
		self._name = switch._friendly_name
		self._state = switch._state
		self._avaliable = True

	@property
	def name(self):
		"""Return the display name of this switch."""
		return self._name

	@property
	def available(self):
		"""Return the connection status of this switch"""
		return self._avaliable

	@property
	def is_on(self):
		"""Return true if switch is on."""
		return self._state

	async def async_turn_on(self, **kwargs):
		"""Instruct the switch to turn on."""
		await self._switch.async_turn_on()

	async def async_turn_off(self, **kwargs):
		"""Instruct the switch to turn off."""
		await self._switch.async_turn_off()

	async def async_update(self):
		"""Fetch new state data for this switch.
		This is the only method that should fetch new data for Home Assistant.
		"""
		await self._switch.async_update()
		self._state = self._switch._state
