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

def setup_platform(hass, config, add_entities, discovery_info=None):
	"""Set up the Wyze Switch platform."""
	_LOGGER.debug("""Creating new WyzeApi light component""")

	# Add devices
	add_entities(WyzeSwitch(switch) for switch in hass.data[DOMAIN]["wyzeapi_account"].list_switches())

class WyzeSwitch(SwitchDevice):
	"""Representation of a Wyze Switch."""

	def __init__(self, switch):
		"""Initialize a Wyze Switch."""
		self._switch = switch
		self._name = switch._friendly_name
		self._state = switch._state

	@property
	def name(self):
		"""Return the display name of this switch."""
		return self._name

	@property
	def is_on(self):
		"""Return true if switch is on."""
		return self._state

	def turn_on(self, **kwargs):
		"""Instruct the switch to turn on."""

		self._switch.turn_on()
		self._state = True

	def turn_off(self, **kwargs):
		"""Instruct the switch to turn off."""
		self._switch.turn_off()
		self._state = False

	def update(self):
		"""Fetch new state data for this switch.
		This is the only method that should fetch new data for Home Assistant.
		"""
		self._switch.update()
		self._state = self._switch.is_on()
