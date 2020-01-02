#!/usr/bin/python3

import hashlib
import logging

_LOGGER = logging.getLogger(__name__)

from .wyzeapi_exceptions import WyzeApiError
from .wyzeapi_bulb import WyzeBulb
from .wyzeapi_switch import WyzeSwitch
from .wyzeapi_request_manager import RequestManager

class WyzeApi():
	def __init__(self, user_name, password):
		self._user_name = user_name
		self._password = self.create_md5_md5(password)
		self._device_id = "bc151f39-787b-4871-be27-5a20fd0a1937"
		self._request_man = RequestManager(self)
		self._access_token = None
		self.initialize()

		# Create device array
		self._all_devices = []

	def initialize(self):
		self._access_token = self.login(self._user_name, self._password, self._device_id)
		_LOGGER.info("Retrieved access token")

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

		data = self._request_man.do_single_threaded_request(url, payload)

		try:
			access_token = data['data']['access_token']
			return access_token
		except:
			return None

	def is_valid_login(self):
		if self._access_token == None:
			return False
		return True


	def get_devices(self):
		if not self._all_devices:
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

			data = self._request_man.do_blocking_request(url, payload)
			self._all_devices = data['data']['device_list']

		return self._all_devices

	def list_bulbs(self):
		bulbs = []

		for device in self.get_devices():
			if (device['product_type'] == "Light"):
				bulbs.append(WyzeBulb(
					self,
					device['mac'],
					device['nickname'],
					("on" if device['device_params']['switch_state'] == 1 else "off")
					))

		return bulbs

	def list_switches(self):
		switches = []

		for device in self.get_devices():
			if (device['product_type'] == "Plug"):
				switches.append(WyzeSwitch(
					self,
					device['mac'],
					device['nickname'],
					("on" if device['device_params']['switch_state'] == 1 else "off"),
                    device['product_model']
					))

		return switches

	""" def request_helper(self, url, payload):
		r = requests.post(url, headers=self.headers, data=json.dumps(payload))

		data = r.json()

		if data['code'] != '1':
			if data['msg'] == 'AccessTokenError':
				_LOGGER.info("Recieved AccessTokenError attempting to regenerate the AccessToken")

				self._access_token = None
				self.initialize()
			else:
				raise WyzeApiError(data['msg'])

		return data

	def do_request(self, url, payload, no_return=False):
		if no_return:
			x = threading.Thread(target=self.request_helper, args=(url, payload))
			x.start()
		else:
			return self.request_helper(url, payload)
 """
