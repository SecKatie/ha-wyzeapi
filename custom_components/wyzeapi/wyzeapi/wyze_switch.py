class WyzeSwitch():
	def __init__(self, api, device_mac, friendly_name, state, device_model):
		self._api = api
		self._device_mac = device_mac
		self._device_model = device_model
		self._friendly_name = friendly_name
		self._state = state
		self._avaliable = True
		self._just_changed_state = False

	def turn_on(self):
		url = 'https://api.wyzecam.com/app/v2/device/set_property'

		payload = {
			'phone_id': self._api._device_id,
			'access_token': self._api._access_token,
			'device_model': self._device_model,
			'ts': '1575948896791',
			'sc': '01dd431d098546f9baf5233724fa2ee2',
			'sv': '107693eb44244a948901572ddab807eb',
			'device_mac': self._device_mac,
			'pvalue': "1",
			'pid': 'P3',
			'app_ver': 'com.hualai.WyzeCam___2.6.62'
		}

		self._api.do_request(url, payload)

		self._state = True
		self._just_changed_state = True
	
	async def async_turn_on(self):
		url = 'https://api.wyzecam.com/app/v2/device/set_property'

		payload = {
			'phone_id': self._api._device_id,
			'access_token': self._api._access_token,
			'device_model': self._device_model,
			'ts': '1575948896791',
			'sc': '01dd431d098546f9baf5233724fa2ee2',
			'sv': '107693eb44244a948901572ddab807eb',
			'device_mac': self._device_mac,
			'pvalue': "1",
			'pid': 'P3',
			'app_ver': 'com.hualai.WyzeCam___2.6.62'
		}

		await self._api.async_do_request(url, payload)

		self._state = True
		self._just_changed_state = True

	def turn_off(self):
		url = 'https://api.wyzecam.com/app/v2/device/set_property'

		payload = {
			'phone_id': self._api._device_id,
			'access_token': self._api._access_token,
			'device_model': self._device_model,
			'ts': '1575948896791',
			'sc': '01dd431d098546f9baf5233724fa2ee2',
			'sv': '107693eb44244a948901572ddab807eb',
			'device_mac': self._device_mac,
			'pvalue': "0",
			'pid': 'P3',
			'app_ver': 'com.hualai.WyzeCam___2.6.62'
		}

		self._api.do_request(url, payload)

		self._state = False
		self._just_changed_state = True
	
	async def async_turn_off(self):
		url = 'https://api.wyzecam.com/app/v2/device/set_property'

		payload = {
			'phone_id': self._api._device_id,
			'access_token': self._api._access_token,
			'device_model': self._device_model,
			'ts': '1575948896791',
			'sc': '01dd431d098546f9baf5233724fa2ee2',
			'sv': '107693eb44244a948901572ddab807eb',
			'device_mac': self._device_mac,
			'pvalue': "0",
			'pid': 'P3',
			'app_ver': 'com.hualai.WyzeCam___2.6.62'
		}

		await self._api.async_do_request(url, payload)

		self._state = False
		self._just_changed_state = True

	def is_on(self):
		return self._state

	def update(self):
		if self._just_changed_state == True:
			self._just_changed_state == False
		else:
			url = "https://api.wyzecam.com/app/v2/device/get_property_list"

			payload = {
				"target_pid_list":[],
				"phone_id": self._api._device_id,
				"device_model": self._device_model,
				"app_name":"com.hualai.WyzeCam",
				"app_version":"2.6.62",
				"sc":"01dd431d098546f9baf5233724fa2ee2",
				"sv":"22bd9023a23b4b0b9977e4297ca100dd",
				"device_mac": self._device_mac,
				"app_ver":"com.hualai.WyzeCam___2.6.62",
				"phone_system_type":"1",
				"ts":"1575955054511",
				"access_token": self._api._access_token
			}

			data = self._api.do_request(url, payload)

			for item in data['data']['property_list']:
				if item['pid'] == "P3":
					self._state = True if int(item['value']) == 1 else False
				elif item['pid'] == "P5":
					self._avaliable = False if int(item['value']) == 0 else True
