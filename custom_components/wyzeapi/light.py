#!/usr/bin/python3

"""Platform for light integration."""
import logging
from .wyzeapi.wyzeapi import WyzeApi

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
# Import the device class from the component that you want to support
from homeassistant.components.light import (
	ATTR_BRIGHTNESS,
	ATTR_COLOR_TEMP,
	PLATFORM_SCHEMA,
	SUPPORT_BRIGHTNESS,
	SUPPORT_COLOR_TEMP,
	Light
	)

from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
	vol.Required(CONF_USERNAME): cv.string,
	vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
	"""Set up the Awesome Light platform."""
	# Assign configuration variables.
	# The configuration check takes care they are present.
	_LOGGER.debug("""
-------------------------------------------------------------------
Wyze Bulb and Switch Home Assistant Integration

Version: v0.3.2
This is a custom integration
If you have any issues with this you need to open an issue here:
https://github.com/JoshuaMulliken/ha-wyzeapi/issues
-------------------------------------------------------------------""")

	user_name = config[CONF_USERNAME]
	password = config.get(CONF_PASSWORD)

	# Setup connection with the WyzeApi
	wyze = WyzeApi(user_name, password)

	# Verify that passed in configuration works
	if not wyze.is_valid_login():
		_LOGGER.error("Could not connect to Wyze Api")
		return

	# Add devices
	add_entities(WyzeBulb(light) for light in wyze.list_bulbs())

class WyzeBulb(Light):
	"""Representation of a Wyze Bulb."""

	def __init__(self, light):
		"""Initialize a Wyze Bulb."""
		self._light = light
		self._name = light._friendly_name
		self._state = light._state
		self._brightness = light._brightness
		self._colortemp = light._colortemp

	@property
	def name(self):
		"""Return the display name of this light."""
		return self._name

	@property
	def brightness(self):
		"""Return the brightness of the light.

		This method is optional. Removing it indicates to Home Assistant
		that brightness is not supported for this light.
		"""
		return self._brightness

	@property
	def color_temp(self):
		"""Return the CT color value in mireds."""
		return self._colortemp

	@property
	def is_on(self):
		"""Return true if light is on."""
		return self._state

	@property
	def supported_features(self):
		return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

	def turn_on(self, **kwargs):
		"""Instruct the light to turn on.

		You can skip the brightness part if your light does not support
		brightness control.
		"""
		self._light._brightness = kwargs.get(ATTR_BRIGHTNESS)
		self._light._colortemp = kwargs.get(ATTR_COLOR_TEMP)
		self._light.turn_on()
		self._state = True

	def turn_off(self, **kwargs):
		"""Instruct the light to turn off."""
		self._light.turn_off()
		self._state = False

	def update(self):
		"""Fetch new state data for this light.

		This is the only method that should fetch new data for Home Assistant.
		"""
		self._light.update()
		self._state = self._light.is_on()
		self._brightness = self._light._brightness
		self._colortemp = self._light._colortemp
