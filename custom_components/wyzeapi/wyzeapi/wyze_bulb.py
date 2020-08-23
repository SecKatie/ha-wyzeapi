import asyncio
import logging

from .wyzeapi import WyzeApi

_LOGGER = logging.getLogger(__name__)


class WyzeBulb:
    def __init__(self, api: WyzeApi, device_mac, friendly_name, state, ssid, ip, rssi, device_model):
        _LOGGER.debug("Light " + friendly_name + " initializing.")

        self.__api = api
        self.device_mac = device_mac
        self.friendly_name = friendly_name
        self.state = state
        self.available = True
        self.__just_changed_state = False
        self.device_model = device_model
        self.brightness = self.color_temp = None
        self.ssid = ssid
        self.ip = ip
        self.rssi = rssi

    async def async_turn_on(self):
        _LOGGER.debug("Light " + self.friendly_name + " turning on.")
        if self.color_temp is not None or self.brightness is not None:
            url = 'https://api.wyzecam.com/app/v2/device/set_property_list'

            property_list = [{"pid": "P3", "pvalue": "1"}]

            if self.brightness:
                brightness = self.translate(self.brightness, 1, 255, 1, 100)
                property_list.append({"pid": "P1501", "pvalue": brightness})

            if self.color_temp:
                if self.color_temp >= 370:
                    color_temp = 2700
                elif self.color_temp <= 153:
                    color_temp = 6500
                else:
                    color_temp = 1000000 / self.color_temp

                property_list.append({"pid": "P1502", "pvalue": color_temp})

            payload = {
                "phone_id": self.__api.device_id,
                "property_list": property_list,
                "device_model": self.device_model,
                "app_name": "com.hualai.WyzeCam",
                "app_version": "2.6.62",
                "sc": "01dd431d098546f9baf5233724fa2ee2",
                "sv": "a8290b86080a481982b97045b8710611",
                "device_mac": self.device_mac,
                "app_ver": "com.hualai.WyzeCam___2.6.62",
                "ts": "1575951274357",
                "access_token": self.__api.access_token
            }

        else:
            url = 'https://api.wyzecam.com/app/v2/device/set_property'

            payload = {
                'phone_id': self.__api.device_id,
                'access_token': self.__api.access_token,
                'device_model': self.device_model,
                'ts': '1575948896791',
                'sc': '01dd431d098546f9baf5233724fa2ee2',
                'sv': '107693eb44244a948901572ddab807eb',
                'device_mac': self.device_mac,
                'pvalue': "1",
                'pid': 'P3',
                'app_ver': 'com.hualai.WyzeCam___2.6.62'
            }

        loop = asyncio.get_running_loop()
        loop.create_task(self.__api.async_do_request(url, payload))

        self.state = True
        self.__just_changed_state = True

    async def async_turn_off(self):
        _LOGGER.debug("Light " + self.friendly_name + " turning off.")
        url = 'https://api.wyzecam.com/app/v2/device/set_property'

        payload = {
            'phone_id': self.__api.device_id,
            'access_token': self.__api.access_token,
            'device_model': self.device_model,
            'ts': '1575948896791',
            'sc': '01dd431d098546f9baf5233724fa2ee2',
            'sv': '107693eb44244a948901572ddab807eb',
            'device_mac': self.device_mac,
            'pvalue': "0",
            'pid': 'P3',
            'app_ver': 'com.hualai.WyzeCam___2.6.62'
        }

        loop = asyncio.get_running_loop()
        loop.create_task(self.__api.async_do_request(url, payload))

        self.state = False
        self.__just_changed_state = True

    def is_on(self):
        return self.state

    async def async_update(self):
        _LOGGER.debug("Light " + self.friendly_name + " updating.")
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
                "access_token": self.__api.access_token
            }

            data = await self.__api.async_do_request(url, payload)

            for item in data['data']['property_list']:
                if item['pid'] == "P3":
                    self.state = True if int(item['value']) == 1 else False
                elif item['pid'] == "P5":
                    self.available = False if int(item['value']) == 0 else True
                elif item['pid'] == "P1501":
                    self.brightness = self.translate(int(item['value']), 0, 100, 0, 255)
                elif item['pid'] == "P1502":
                    self.color_temp = 1000000 / int(item['value'])

    @staticmethod
    def translate(value, left_min, left_max, right_min, right_max):
        # Figure out how 'wide' each range is
        left_span = left_max - left_min
        right_span = right_max - right_min

        # Convert the left range into a 0-1 range (float)
        value_scaled = float(value - left_min) / float(left_span)

        # Convert the 0-1 range into a value in the right range.
        return right_min + (value_scaled * right_span)
