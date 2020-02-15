import asyncio

from .wyze_device import *

class WyzeSwitch(WyzeDevice):
    def __init__(self, api, device_mac, friendly_name, state, device_model):
        super().__init__(api, device_mac, friendly_name, state, device_model)

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

        loop = asyncio.get_running_loop()
        loop.create_task(self._api.async_do_request(url, payload))

        self._state = True
        self._just_changed_state = True

    async def async_update(self):
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

            data = await self._api.async_do_request(url, payload)

            for item in data['data']['property_list']:
                if item['pid'] == "P3":
                    self._state = True if int(item['value']) == 1 else False
                elif item['pid'] == "P5":
                    self._avaliable = False if int(item['value']) == 0 else True
