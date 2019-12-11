#!/usr/bin/python3

import json
import requests
import hashlib
from configparser import ConfigParser

headers = {
	'Host': 'api.wyzecam.com:443',
	'User-Agent': 'Wyze/2.6.62 (iPhone; iOS 13.2.3; Scale/2.00)',
	'Content-Type': 'application/json'
}

def translate(value, leftMin, leftMax, rightMin, rightMax):
    # Figure out how 'wide' each range is
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin

    # Convert the left range into a 0-1 range (float)
    valueScaled = float(value - leftMin) / float(leftSpan)

    # Convert the 0-1 range into a value in the right range.
    return rightMin + (valueScaled * rightSpan)

class WyzeApi():
	class WyzeBulb():
		def __init__(self, device_id, access_token, device_mac, friendly_name, state):
			self._device_id = device_id
			self._access_token = access_token
			self._device_mac = device_mac
			self._friendly_name = friendly_name
			self._state = state
			self._brightness = None
			self._colortemp = None

		def turn_on(self):
			url = 'https://api.wyzecam.com/app/v2/device/set_property_list'

			if (self._brightness != None and self._colortemp != None):

				brightness = translate(self._brightness, 0, 255, 1, 100)
				colortemp = translate(self._colortemp, 500, 153, 2700, 6500)

				bulb_on = {
					"phone_id": self._device_id,
					"property_list": [
						{"pid": "P3", "pvalue": "1"},
						{"pid": "P1501", "pvalue": brightness},
						{"pid": "P1502", "pvalue": colortemp}
					],
					"device_model": "WLPA19",
					"app_name": "com.hualai.WyzeCam",
					"app_version": "2.6.62",
					"sc": "01dd431d098546f9baf5233724fa2ee2",
					"sv": "a8290b86080a481982b97045b8710611",
					"device_mac": self._device_mac,
					"app_ver": "com.hualai.WyzeCam___2.6.62",
					"ts": "1575951274357",
					"access_token": self._access_token
				}

			elif (self._brightness == None and self._colortemp != None):
				colortemp = translate(self._colortemp, 500, 153, 2700, 6500)

				bulb_on = {
					"phone_id": self._device_id,
					"property_list": [
						{"pid": "P3", "pvalue": "1"},
						{"pid": "P1502", "pvalue": colortemp}
					],
					"device_model": "WLPA19",
					"app_name": "com.hualai.WyzeCam",
					"app_version": "2.6.62",
					"sc": "01dd431d098546f9baf5233724fa2ee2",
					"sv": "a8290b86080a481982b97045b8710611",
					"device_mac": self._device_mac,
					"app_ver": "com.hualai.WyzeCam___2.6.62",
					"ts": "1575951274357",
					"access_token": self._access_token
				}
			elif (self._brightness != None and self._colortemp == None):
				brightness = translate(self._brightness, 0, 255, 1, 100)

				bulb_on = {
					"phone_id": self._device_id,
					"property_list": [
						{"pid": "P3", "pvalue": "1"},
						{"pid": "P1501", "pvalue": brightness}
					],
					"device_model": "WLPA19",
					"app_name": "com.hualai.WyzeCam",
					"app_version": "2.6.62",
					"sc": "01dd431d098546f9baf5233724fa2ee2",
					"sv": "a8290b86080a481982b97045b8710611",
					"device_mac": self._device_mac,
					"app_ver": "com.hualai.WyzeCam___2.6.62",
					"ts": "1575951274357",
					"access_token": self._access_token
				}
			else:
				url = 'https://api.wyzecam.com/app/v2/device/set_property_list'
				bulb_on = {
					'phone_id': 'D01C09DE-FC02-4A45-8967-845DDB8E15A2',
					'access_token': self._access_token,
					'device_model': 'WLPA19',
					'ts': '1575948896791',
					'sc': '01dd431d098546f9baf5233724fa2ee2',
					'sv': '107693eb44244a948901572ddab807eb',
					'device_mac': self._device_mac,
					'pvalue': "1",
					'pid': 'P3',
					'app_ver': 'com.hualai.WyzeCam___2.6.62'
				}

			requests.post(url, headers=headers, data=json.dumps(bulb_on))

		def turn_off(self):
			url = 'https://api.wyzecam.com/app/v2/device/set_property'

			bulb_on = {
				'phone_id': self._device_id,
				'access_token': self._access_token,
				'device_model': 'WLPA19',
				'ts': '1575948896791',
				'sc': '01dd431d098546f9baf5233724fa2ee2',
				'sv': '107693eb44244a948901572ddab807eb',
				'device_mac': self._device_mac,
				'pvalue': "0",
				'pid': 'P3',
				'app_ver': 'com.hualai.WyzeCam___2.6.62'
			}

			requests.post(url, headers=headers, data=json.dumps(bulb_on))

			self._state = "off"

		def is_on(self):
			return self._state == 'on'

		def update(self):
			url = "https://api.wyzecam.com/app/v2/device/get_property_list"

			payload = {
				"target_pid_list":[],
				"phone_id": self._device_id,
				"device_model":"WLPA19",
				"app_name":"com.hualai.WyzeCam",
				"app_version":"2.6.62",
				"sc":"01dd431d098546f9baf5233724fa2ee2",
				"sv":"22bd9023a23b4b0b9977e4297ca100dd",
				"device_mac": self._device_mac,
				"app_ver":"com.hualai.WyzeCam___2.6.62",
				"phone_system_type":"1",
				"ts":"1575955054511",
				"access_token": self._access_token
			}

			r = requests.post(url, headers=headers, data=json.dumps(payload))

			data = r.json()

			for item in data['data']['property_list']:
				if item['pid'] == "P3":
					self._state = int(item['value'])
				elif item['pid'] == "P1501":
					self._brightness = translate(int(item['value']), 1, 100, 0, 255)
				elif item['pid'] == "P1502":
					self._colortemp = translate(int(item['value']), 2700, 6500, 500, 153)

	def __init__(self, user_name, password):
		self._user_name = user_name
		self._password = self.create_md5_md5(password)
		self._device_id = None
		self._access_token = None
		self.parseConfig()

		if self._access_token == None or self._device_id == None:
			self._device_id = "bc151f39-787b-4871-be27-5a20fd0a1937"
			self._access_token = self.login(self._user_name, self._password, self._device_id)

			self.updateConfig()

		self._bulbs = None

	def parseConfig(self):
		config = ConfigParser()
		config.read('wyzeconfig.ini')

		try:
			self._access_token = config.get('auth', 'access_token')
			self._device_id = config.get('auth', 'device_id')
		except:
			pass

	def updateConfig(self):
		config = ConfigParser()
		config.read('wyzeconfig.ini')
		config.add_section('auth')
		config.set('auth', 'access_token', str(self._access_token))
		config.set('auth', 'device_id', str(self._device_id))
		with open('wyzeconfig.ini', 'w') as f:
			config.write(f)

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

		r = requests.post(url, headers=headers, data=json.dumps(payload))

		data = r.json()
		print(data)

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

		devices = {
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

		r = requests.post(url, headers=headers, data=json.dumps(devices))

		data = r.json()

		self._bulbs = []
		for device in data['data']['device_list']:
			if (device['product_type'] == "Light"):
				self._bulbs.append(WyzeApi.WyzeBulb(
					self._device_id,
					self._access_token,
					device['mac'],
					device['nickname'],
					("on" if device['device_params']['switch_state'] == 1 else "off")
					))

		return self._bulbs
