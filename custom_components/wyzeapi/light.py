#!/usr/bin/python3

"""Platform for light integration."""
import logging
from .wyzeapi.wyzeapi import WyzeApi
from . import DOMAIN

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

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, add_entities, discovery_info=None):
	"""Set up the Wyze Light platform."""
	_LOGGER.debug("""Creating new WyzeApi light component""")

	# Add devices
	add_entities(WyzeBulb(light) for light in hass.data[DOMAIN]["wyzeapi_account"].list_bulbs())

class WyzeBulb(Light):
	"""Representation of a Wyze Bulb."""

	def __init__(self, light):
		"""Initialize a Wyze Bulb."""
		self._light = light
		self._name = light._friendly_name
		self._state = light._state
		self._brightness = light._brightness
		self._colortemp = light._colortemp
		self._avaliable = True

	@property
	def name(self):
		"""Return the display name of this light."""
		return self._name

	@property
	def available(self):
		"""Return the connection status of this light"""
		return self._avaliable

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

	async def async_turn_on(self, **kwargs):
		"""Instruct the light to turn on.

		You can skip the brightness part if your light does not support
		brightness control.
		"""
		self._light._brightness = kwargs.get(ATTR_BRIGHTNESS)
		self._light._colortemp = kwargs.get(ATTR_COLOR_TEMP)
		self._state = await self._light.turn_on()

	async def async_turn_off(self, **kwargs):
		"""Instruct the light to turn off."""
		self._state = await self._light.turn_off()

	async def async_update(self):
		"""Fetch new state data for this light.
		This is the only method that should fetch new data for Home Assistant.
		"""
		self._state = await self._light.update()
		self._avaliable = self._light._avaliable
		self._brightness = self._light._brightness
		self._colortemp = self._light._colortemp
