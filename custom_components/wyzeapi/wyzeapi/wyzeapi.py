#!/usr/bin/python3

import datetime
from hashlib import md5
import logging

_LOGGER = logging.getLogger(__name__)

from .wyzeapi_exceptions import WyzeApiError, AccessTokenError
from .wyze_request import WyzeRequest
from .wyze_bulb import WyzeBulb
from .wyze_switch import WyzeSwitch
from .wyze_lock import WyzeLock
from .sensors.wyze_contact import WyzeContactSensor
from .sensors.wyze_motion import WyzeMotionSensor

class WyzeApi():
    def __init__(self, user_name, password):
        _LOGGER.debug("Wyze Api initializing.")
        self._user_name = user_name
        self._password = self.create_md5_md5(password)
        self._device_id = "bc151f39-787b-4871-be27-5a20fd0a1937"
        self._in_error_state = False
        self._invalid_access_tokens = []

        self._access_token = self._refresh_token = None
        
        # Create device array
        self._all_devices = []

    async def async_init(self):
        _LOGGER.debug("Wyze Api initializing async.")
        await self.async_login()

    def create_md5_md5(self, password):
        digest1 = md5(password.encode('utf-8')).hexdigest()
        digest2 = md5(digest1.encode('utf-8')).hexdigest()
        return digest2

    async def async_login(self):
        _LOGGER.debug("Wyze Api logging in async.")
        url = "https://api.wyzecam.com/app/user/login"
        payload = {
            "phone_id":self._device_id,
            "app_name":"com.hualai.WyzeCam",
            "app_version":"2.6.62",
            "sc":"9f275790cab94a72bd206c8876429f3c",
            "password":self._password,
            "sv":"41267de22d1847c8b99bfba2658f88d7",
            "user_name":self._user_name,
            "two_factor_auth":"",
            "phone_system_type":"1",
            "app_ver":"com.hualai.WyzeCam___2.6.62",
            "ts":"1575955440030",
            "access_token":""
        }

        data = await self.async_do_request(url, payload)

        try:
            self._access_token = data['data']['access_token']
            self._refresh_token = data['data']['refresh_token']
        except:
            _LOGGER.error("Failure to login")
    
    async def async_refresh_token(self):
        _LOGGER.debug("Wyze Api refreshing token.")
        url = "https://api.wyzecam.com/app/user/refresh_token"
        payload = {
            "phone_id": self._device_id,
            "app_name":"com.hualai.WyzeCam",
            "app_version":"2.6.62",
            "sc":"9f275790cab94a72bd206c8876429f3c",
            "sv":"41267de22d1847c8b99bfba2658f88d7",
            "ts":"1575955440030",
            "access_token": self._access_token,
            "refresh_token": self._refresh_token
        }

        data = await self.async_do_request(url, payload)

        try:
            self._access_token = data['data']['access_token']
            self._refresh_token = data['data']['refresh_token']
        except:
            _LOGGER.error("Failure to refresh access token with the refresh token")

    def is_valid_login(self):
        if self._access_token == None:
            return False
        return True

    async def async_get_devices(self):
        _LOGGER.debug("Wyze Api getting devices.")
        if not self._all_devices:
            url = "https://api.wyzecam.com/app/v2/home_page/get_object_list"

            payload = {
                "phone_system_type":"1",
                "app_version":"2.6.62",
                "app_ver":"com.hualai.WyzeCam___2.6.62",
                "sc":"9f275790cab94a72bd206c8876429f3c",
                "ts": datetime.datetime.now().strftime("%s"),
                "sv":"9d74946e652647e9b6c9d59326aef104",
                "access_token": self._access_token,
                "phone_id": self._device_id,
                "app_name":"com.hualai.WyzeCam"
            }

            data = await self.async_do_request(url, payload)
            self._all_devices = data['data']['device_list']

        return self._all_devices
    
    async def async_list_bulbs(self):
        _LOGGER.debug("Wyze Api listing bulbs.")
        bulbs = []

        for device in await self.async_get_devices():
            if (device['product_type'] == "Light"):
                bulbs.append(WyzeBulb(
                    self,
                    device['mac'],
                    device['nickname'],
                    ("on" if device['device_params']['switch_state'] == 1 else "off"),
                    device['device_params']['ssid'],
                    device['device_params']['ip'],
                    device['device_params']['rssi'],
                    device['product_model']
                    ))

        return bulbs

    async def async_list_switches(self):
        _LOGGER.debug("Wyze Api listing switches.")
        #This is a list. We will append later
        switches = []

        for device in await self.async_get_devices():
            if (device['product_type'] == "Plug"):
                switches.append(WyzeSwitch(
                    self,
                    device['mac'],
                    device['nickname'],
                    ("on" if device['device_params']['switch_state'] == 1 else "off"),
                    device['device_params']['ssid'],
                    device['device_params']['ip'],
                    device['device_params']['rssi'],
                    device['product_model'],
                    ))

        return switches
    async def async_list_contact_sensor(self):
        _LOGGER.debug("Wyze Api listing sensors.")
        contactsensor = []

        for device in await self.async_get_devices():
            if (device['product_type'] == "ContactSensor"):
                contactsensor.append(WyzeContactSensor(
                self,
                device['mac'],
                device['nickname'],
                ("on" if device['device_params']['open_close_state'] == 1 else "off"),
                device['device_params']['open_close_state_ts'],
                device['device_params']['voltage'],
                device['device_params']['rssi'],
                device['product_model']))

        return contactsensor
    async def async_list_motion_sensor(self):
        _LOGGER.debug("Wyze Api listing Motion Sensors.")
        motionsensor = []
        for device in await self.async_get_devices():
            if (device['product_type'] == "MotionSensor"): #MotionSensor
                motionsensor.append(WyzeMotionSensor(
                self,
                device['mac'],
                device['nickname'],
                ("on" if device['device_params']['motion_state'] == 1 else "off"),
                device['device_params']['motion_state_ts'],
                device['device_params']['voltage'],
                device['device_params']['rssi'],
                device['product_model']))
                
        return motionsensor

    async def async_list_lock(self):
        _LOGGER.debug("Wyze Api listing Lock.")
        lock = []
        for device in await self.async_get_devices():
            if (device['product_type'] == "Lock"):
                lock.append(WyzeLock(
                self,
                device['mac'],
                device['nickname'],
                ("on" if device['device_params']['switch_state'] == 0 else "off"),
                ("on" if device['device_params']['open_close_state'] == 1 else "off"),
                device['product_model']))
        return lock

    async def async_do_request(self, url, payload):
        _LOGGER.debug("Wyze Api doing request.")
        try:
            return await WyzeRequest(url, payload).async_get_response()
        except AccessTokenError:
            if payload["access_token"] not in self._invalid_access_tokens:
                self._invalid_access_tokens.append(payload["access_token"])
                await self.async_login()

            payload["access_token"] = self._access_token

            return await WyzeRequest(url, payload).async_get_response()
