#!/usr/bin/python3

import hashlib

from .wyzeapi_request import *
from .wyzeapi_config import *
from .wyzeapi_bulb import WyzeBulb

class WyzeApi():
	def __init__(self, user_name, password, no_save=False):
		self._user_name = user_name
		self._password = self.create_md5_md5(password)
		self._device_id, self._access_token = (None, None) if no_save else parseConfig()

		self._request_queue = []

		if self._access_token == None or self._device_id == None:
			self._device_id = "bc151f39-787b-4871-be27-5a20fd0a1937"
			self._access_token = self.login(self._user_name, self._password, self._device_id)

			if not no_save:
				updateConfig(self._device_id, self._access_token)

	def create_md5_md5(self, password):
		digest1 = hashlib.md5(password.encode('utf-8')).hexdigest()
		digest2 = hashlib.md5(digest1.encode('utf-8')).hexdigest()
		return digest2

	def login(self, username, password, device_id):
		url = "https://api.wyzecam.com/app/user/login"
		payload = {
			"phone_id":device_id,
			"app_name":"com.hualai.WyzeCam",
			"app_version":"2.6.62",
			"sc":"9f275790cab94a72bd206c8876429f3c",
			"password":password,
			"sv":"41267de22d1847c8b99bfba2658f88d7",
			"user_name":username,
			"two_factor_auth":"",
			"phone_system_type":"1",
			"app_ver":"com.hualai.WyzeCam___2.6.62",
			"ts":"1575955440030",
			"access_token":""
		}

		data = do_request(url, payload)

		try:
			access_token = data['data']['access_token']
			return access_token
		except:
			return None

	def is_valid_login(self):
		if self._access_token == None:
			return False
		return True

	def list_bulbs(self):
		url = "https://api.wyzecam.com/app/v2/home_page/get_object_list"

		payload = {
			"phone_system_type":"1",
			"app_version":"2.6.62",
			"app_ver":"com.hualai.WyzeCam___2.6.62",
			"sc":"9f275790cab94a72bd206c8876429f3c",
			"ts":"1575953834054",
			"sv":"9d74946e652647e9b6c9d59326aef104",
			"access_token": self._access_token,
			"phone_id": self._device_id,
			"app_name":"com.hualai.WyzeCam"
		}

		data = do_request(url, payload)

		bulbs = []

		for device in data['data']['device_list']:
			if (device['product_type'] == "Light"):
				bulbs.append(WyzeBulb(
					self._device_id,
					self._access_token,
					device['mac'],
					device['nickname'],
					("on" if device['device_params']['switch_state'] == 1 else "off")
					))

		return bulbs
