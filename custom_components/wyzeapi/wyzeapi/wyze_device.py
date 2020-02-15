import asyncio

class WyzeDevice():
    def __init__(self, api, device_mac, friendly_name, state, device_model):
        self._api = api
        self._device_mac = device_mac
        self._friendly_name = friendly_name
        self._state = state
        self._avaliable = True
        self._just_changed_state = False
        self._device_model = device_model

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

        loop = asyncio.get_running_loop()
        loop.create_task(self._api.async_do_request(url, payload))

        self._state = False
        self._just_changed_state = True

    def is_on(self):
        return self._state