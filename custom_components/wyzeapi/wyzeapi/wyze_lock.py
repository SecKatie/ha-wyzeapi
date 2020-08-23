import asyncio
import logging

from .wyzeapi import WyzeApi

_LOGGER = logging.getLogger(__name__)


class WyzeLock:
    def __init__(self, api: WyzeApi, device_mac, friendly_name, state, open_close_state, device_model):
        _LOGGER.debug("Lock " + device_mac + " " + friendly_name + " " + "initializing.")

        self.__api = api
        self.device_mac = device_mac
        self.friendly_name = friendly_name
        self.state = state
        self.__available = True
        self.__just_changed_state = False
        self.device_model = device_model
        self.open_close_state = open_close_state

    async def async_lock(self):
        _LOGGER.debug("Lock " + self.friendly_name + " Locking.")
        url = 'https://beta-api.wyzecam.com/app/v2/auto/run_action'

        payload = {
            'phone_id': self.__api.device_id,
            'action_params': {},
            'provider_key': self.device_model,
            'app_name': 'com.hualai.WyzeCam',
            'app_version': '2.6.62',
            'action_key': 'unlock',
            ' ': '',
            'sc': '01dd431d098546f9baf5233724fa2ee2',
            'sv': '22bd9023a23b4b0b9977e4297ca100dd',
            'phone_system_type': '1',
            'app_ver': 'com.hualai.WyzeCam___2.6.62',
            'ts': '1575948896791',
            'instance_id': self.device_mac,
            'access_token': self.__api.access_token,
            'refresh_token': self.__api.refresh_token
        }

        loop = asyncio.get_running_loop()
        loop.create_task(self.__api.async_do_request(url, payload))

        self.state = False
        self.__just_changed_state = True

    async def async_unlock(self):
        _LOGGER.debug("Lock " + self.friendly_name + " Unlocking.")
        url = 'https://beta-api.wyzecam.com/app/v2/auto/run_action'

        payload = {
            'phone_id': self.__api.device_id,
            'action_params': {},
            'provider_key': self.device_model,
            'app_name': 'com.hualai.WyzeCam',
            'app_version': '2.6.62',
            'action_key': 'unlock',
            ' ': '',
            'sc': '01dd431d098546f9baf5233724fa2ee2',
            'sv': '22bd9023a23b4b0b9977e4297ca100dd',
            'phone_system_type': '1',
            'app_ver': 'com.hualai.WyzeCam___2.6.62',
            'ts': '1575948896791',
            'instance_id': self.device_mac,
            'access_token': self.__api.access_token,
            'refresh_token': self.__api.refresh_token
        }

        loop = asyncio.get_running_loop()
        loop.create_task(self.__api.async_do_request(url, payload))

        self.state = False
        self.__just_changed_state = True

    def is_locked(self):
        return self.state

    async def async_update(self):
        _LOGGER.debug("Lock " + self.friendly_name + " updating.")
        if self.__just_changed_state:
            self.__just_changed_state = False
        else:
            url = "https://api.wyzecam.com/app/v2/device/get_property_list"

            payload = {
                "target_pid_list": [],
                "phone_id": self.__api.device_id,
                "device_model": self.device_model,
                "app_name": "com.hualai.WyzeCam",
                "app_version": "2.6.62",
                "sc": "01dd431d098546f9baf5233724fa2ee2",
                "sv": "22bd9023a23b4b0b9977e4297ca100dd",
                "device_mac": self.device_mac,
                "app_ver": "com.hualai.WyzeCam___2.6.62",
                "phone_system_type": "1",
                "ts": "1575955054511",
                "access_token": self.__api.access_token,
                "refresh_token": self.__api.refresh_token
            }

            data = await self.__api.async_do_request(url, payload)
            # P3 0 = Locked
            # p3 1 = Unlocked
            for item in data['data']['property_list']:
                if self.device_model == "YD.LO1":
                    if item['pid'] == "P3":  # I don't know if this is correct
                        self.state = True if int(item['value']) == 0 else False
                    if item['pid'] == "P2001":
                        self.open_close_state = True if int(item['value']) == 1 else False
                elif item['pid'] == "P5":
                    self.__available = False if int(item['value']) == 0 else True
