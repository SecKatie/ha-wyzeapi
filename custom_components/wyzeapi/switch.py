#!/usr/bin/python3

"""Platform for switch integration."""
import logging
from .wyzeapi.wyzeapi import WyzeApi

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
# Import the device class from the component that you want to support
from homeassistant.components.switch import (
	PLATFORM_SCHEMA,
	SwitchDevice
	)

from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
	vol.Required(CONF_USERNAME): cv.string,
	vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
	"""Set up the Awesome Switch platform."""
	# Assign configuration variables.
	# The configuration check takes care they are present.
	_LOGGER.debug("WYZEAPI v0.2.0")

	user_name = config[CONF_USERNAME]
	password = config.get(CONF_PASSWORD)

	# Setup connection with the WyzeApi
	wyze = WyzeApi(user_name, password)

	# Verify that passed in configuration works
	if not wyze.is_valid_login():
		_LOGGER.error("Could not connect to Wyze Api")
		return

	# Add devices
	add_entities(WyzeSwitch(switch) for switch in wyze.list_switches())

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
		"""Instruct the switch to turn on.
		"""

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
