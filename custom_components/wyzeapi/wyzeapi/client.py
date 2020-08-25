#!/usr/bin/python3

import asyncio
import logging
import threading
import time
from typing import List
from hashlib import md5

import aiohttp

from .constants import WyzeApiConstants
from .devices import *

_LOGGER = logging.getLogger(__name__)


class WyzeApiClient:
    __access_token: str
    __refresh_token: str
    __logged_in: bool = False
    __user_name: str
    __password: str

    __bulbs: List[WyzeBulb] = []
    __switches: List[WyzeSwitch] = []
    __contact_sensors: List[WyzeContactSensor] = []
    __motion_sensors: List[WyzeMotionSensor] = []
    __locks: List[WyzeLock] = []

    __logged_in_event = threading.Event()

    def __init__(self):
        self.__devices = None

    @staticmethod
    async def __post_to_server(url: str, payload: dict):
        _LOGGER.debug("Running __post_to_server")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response_json = await response.json()
                # _LOGGER.debug("Response recieved from server: {0}".format(response_json))
                return response_json

    async def __post_and_recover(self, url: str, payload: dict):
        _LOGGER.debug("Running __post_and_recover")
        response_json = await self.__post_to_server(url, payload)

        if response_json['code'] != 1 and response_json['msg'] == 'AccessTokenError':
            self.__logged_in_event.clear()
            await self.refresh_tokens()

            payload = await self.__create_authenticated_payload(payload)

            return await self.__post_without_waiting(url, payload)
        elif response_json['code'] != 1:
            raise ConnectionError("Failed to connect to the Wyze Service")

        return response_json

    @staticmethod
    async def __create_payload(extras: dict = None) -> dict:
        _LOGGER.debug("Running __create_payload")
        updated_payload = WyzeApiConstants.base_payload.copy()
        updated_payload['ts'] = str(int(time.time()))
        if extras:
            updated_payload.update(extras)
        return updated_payload

    async def __create_authenticated_payload(self, extras: dict = None) -> dict:
        _LOGGER.debug("Running __create_authenticated_payload")
        updated_payload = await self.__create_payload()
        self.__logged_in_event.wait()
        updated_payload['access_token'] = self.__access_token
        if extras:
            updated_payload.update(extras)
        return updated_payload

    # region Session Management
    async def is_logged_in(self):
        return self.__logged_in

    @staticmethod
    def create_md5_md5(password):
        _LOGGER.debug("Running __create_md5_md5")
        digest1 = md5(password.encode('utf-8')).hexdigest()
        digest2 = md5(digest1.encode('utf-8')).hexdigest()
        return digest2

    async def login(self, user_name: str, password: str):
        _LOGGER.debug("Running login")
        self.__user_name = user_name
        self.__password = self.create_md5_md5(password)

        payload = await self.__create_payload({
            "password": self.__password,
            "user_name": self.__user_name,
            "two_factor_auth": "",
            "access_token": ""
        })

        response_json = await self.__post_to_server(WyzeApiConstants.login_url, payload)

        if response_json['msg'] == "UserIsLocked":
            _LOGGER.error("The user account is locked")
            raise ConnectionError("Failed to login with response: {0}".format(response_json))
        elif response_json['msg'] == "UserNameOrPasswordError":
            _LOGGER.error("The username or password is incorrect")
            raise ConnectionError("Failed to login with response: {0}".format(response_json))

        try:
            self.__access_token = response_json['data']['access_token']
            self.__refresh_token = response_json['data']['refresh_token']

            self.__logged_in = True
            self.__logged_in_event.set()
        except KeyError:
            _LOGGER.error("Failure to login with supplied credentials")
            self.__logged_in = False
            self.__logged_in_event.clear()

            _LOGGER.error(response_json)
            raise ConnectionError("Failed to login with response: {0}".format(response_json))

    async def refresh_tokens(self):
        _LOGGER.debug("Running refresh_tokens")
        payload = await self.__create_payload({
            "access_token": "",
            "refresh_token": self.__refresh_token
        })

        response_json = await self.__post_to_server(WyzeApiConstants.refresh_token_url, payload)

        try:
            self.__access_token = response_json['data']['access_token']
            self.__refresh_token = response_json['data']['refresh_token']
            self.__logged_in = True
            self.__logged_in_event.set()
        except KeyError:
            _LOGGER.error("Failed to refresh access token. Must login again.")
            self.__logged_in = False
            self.__logged_in_event.clear()
            await self.login(self.__user_name, self.__password)

    async def logout(self):
        _LOGGER.debug("Running logout")
        self.__access_token = ""
        self.__refresh_token = ""
        self.__logged_in = False
        self.__logged_in_event.clear()

    # endregion

    # region Getting Devices
    async def refresh_devices(self) -> None:
        _LOGGER.debug("Running refresh_devices")
        self.__devices = None
        await self.get_devices()

    async def get_devices(self) -> list:
        _LOGGER.debug("Running get_devices")
        if self.__devices is None:
            payload = await self.__create_authenticated_payload()

            response_json = await self.__post_to_server(WyzeApiConstants.get_devices_url, payload)

            self.__devices = response_json['data']['device_list']

            for device in self.__devices:
                if device['product_type'] == "Light":
                    self.__bulbs.append(WyzeBulb(device['nickname'], device['product_model'], device['mac'],
                                                 device['device_params']['switch_state'],
                                                 device['device_params']['rssi'], device['device_params']['ssid'],
                                                 device['device_params']['ip']))
                elif device['product_type'] == "Plug":
                    self.__switches.append(WyzeSwitch(device['nickname'], device['product_model'], device['mac'],
                                                      device['device_params']['switch_state'],
                                                      device['device_params']['rssi'], device['device_params']['ssid'],
                                                      device['device_params']['ip']))
                elif device['product_type'] == "Lock":
                    self.__locks.append(WyzeLock(device['nickname'], device['product_model'], device['mac'],
                                                 device['device_params']['switch_state'],
                                                 device['device_params']['open_close_state']))
                elif device['product_type'] == "ContactSensor":
                    self.__contact_sensors.append(WyzeContactSensor(
                        device['nickname'], device['product_model'], device['mac'],
                        device['device_params']['open_close_state'],
                        device['device_params']['open_close_state_ts'],
                        device['device_params']['voltage'],
                        device['device_params']['rssi'],
                    ))
                elif device['product_type'] == "MotionSensor":
                    self.__motion_sensors.append(WyzeMotionSensor(
                        device['nickname'], device['product_model'], device['mac'],
                        device['device_params']['motion_state'],
                        device['device_params']['motion_state_ts'],
                        device['device_params']['voltage'],
                        device['device_params']['rssi'],
                    ))

        return self.__devices

    async def list_bulbs(self):
        _LOGGER.debug("Running list_bulbs")
        await self.get_devices()
        return self.__bulbs

    async def list_switches(self):
        _LOGGER.debug("Running list_switches")
        await self.get_devices()
        return self.__switches

    async def list_locks(self):
        _LOGGER.debug("Running list_locks")
        await self.get_devices()
        return self.__locks

    async def list_contact_sensors(self):
        _LOGGER.debug("Running list_contact_sensors")
        await self.get_devices()
        return self.__contact_sensors

    async def list_motion_sensors(self):
        _LOGGER.debug("Running list_motion_sensors")
        await self.get_devices()
        return self.__motion_sensors

    # endregion

    # region Bulb Operations
    @staticmethod
    def translate(value, left_min, left_max, right_min, right_max):
        # Figure out how 'wide' each range is
        left_span = left_max - left_min
        right_span = right_max - right_min

        # Convert the left range into a 0-1 range (float)
        value_scaled = float(value - left_min) / float(left_span)

        # Convert the 0-1 range into a value in the right range.
        return right_min + (value_scaled * right_span)

    async def turn_on_bulb(self, bulb: WyzeBulb):
        _LOGGER.debug("Turning on bulb: " + bulb.mac)
        if bulb.color_temp is not None or bulb.brightness is not None:
            property_list = [{"pid": "P3", "pvalue": "1"}]

            if bulb.brightness:
                brightness = self.translate(bulb.brightness, 1, 255, 1, 100)
                property_list.append({"pid": "P1501", "pvalue": brightness})

            if bulb.color_temp:
                if bulb.color_temp >= 370:
                    color_temp = 2700
                elif bulb.color_temp <= 153:
                    color_temp = 6500
                else:
                    color_temp = 1000000 / bulb.color_temp

                property_list.append({"pid": "P1502", "pvalue": color_temp})

            payload = await self.__create_authenticated_payload({
                "property_list": property_list,
                "device_model": bulb.product_model,
                "device_mac": bulb.mac
            })

            asyncio.get_running_loop().create_task(
                self.__post_and_recover(WyzeApiConstants.set_device_property_url, payload))
        else:
            payload = await self.__create_authenticated_payload({
                "device_model": bulb.product_model,
                "device_mac": bulb.mac,
                'pvalue': "1",
                'pid': 'P3',
            })

            asyncio.get_running_loop().create_task(
                self.__post_and_recover(WyzeApiConstants.set_device_property_url, payload))

    async def turn_off_bulb(self, bulb: WyzeBulb):
        payload = await self.__create_authenticated_payload({
            "device_model": bulb.product_model,
            "device_mac": bulb.mac,
            'pvalue': "0",
            'pid': 'P3',
        })

        asyncio.get_running_loop().create_task(
            self.__post_and_recover(WyzeApiConstants.set_device_property_url, payload))

    async def update_bulb(self, bulb: WyzeBulb):
        payload = await self.__create_authenticated_payload({
            "target_pid_list": [],
            "device_model": bulb.product_model,
            "device_mac": bulb.mac
        })

        response_json = await self.__post_and_recover(WyzeApiConstants.get_device_property_url, payload)

        for item in response_json['data']['property_list']:
            if item['pid'] == "P3":
                bulb.switch_state = int(item['value'])
            elif item['pid'] == "P5":
                bulb.available = int(item['value'])
            elif item['pid'] == "P1501":
                bulb.brightness = self.translate(int(item['value']), 0, 100, 0, 255)
            elif item['pid'] == "P1502":
                bulb.color_temp = 1000000 / int(item['value'])
            elif item['pid'] == "P1612":
                switch.rssi = item['value']

    # endregion

    # region Switch Operations
    async def turn_on_switch(self, switch: WyzeSwitch):
        payload = await self.__create_authenticated_payload({
            'device_model': switch.product_model,
            'device_mac': switch.mac,
            'pvalue': "1",
            'pid': 'P3',
        })

        asyncio.get_running_loop().create_task(
            self.__post_and_recover(WyzeApiConstants.set_device_property_url, payload))

    async def turn_off_switch(self, switch: WyzeSwitch):
        payload = await self.__create_authenticated_payload({
            'device_model': switch.product_model,
            'device_mac': switch.mac,
            'pvalue': "0",
            'pid': 'P3',
        })

        asyncio.get_running_loop().create_task(
            self.__post_and_recover(WyzeApiConstants.set_device_property_url, payload))

    async def update_switch(self, switch: WyzeSwitch):
        payload = await self.__create_authenticated_payload({
            "target_pid_list": [],
            "device_model": switch.product_model,
            "device_mac": switch.mac
        })

        response_json = await self.__post_and_recover(WyzeApiConstants.get_device_property_url, payload)

        for item in response_json['data']['property_list']:
            if item['pid'] == "P3":
                switch.switch_state = int(item['value'])
            elif item['pid'] == "P5":
                switch.avaliable = int(item['value'])
            elif item['pid'] == "P1612":
                switch.rssi = item['value']

    # endregion

    # region Lock Operations
    async def update_lock(self, lock: WyzeLock):
        payload = await self.__create_authenticated_payload({
            "target_pid_list": [],
            "device_model": lock.product_model,
            "device_mac": lock.mac,
        })

        response_json = await self.__post_and_recover(WyzeApiConstants.get_device_property_url, payload)

        for item in response_json['data']['property_list']:
            if lock.product_model == "YD.LO1":
                if item['pid'] == "P3":  # I don't know if this is correct
                    lock.switch_state = int(item['value'])
                if item['pid'] == "P2001":
                    lock.open_close_state = int(item['value'])
            if item['pid'] == "P5":
                lock.avaliable = int(item['value'])

    # endregion

    # region Contact Sensor Operations
    async def update_contact_sensor(self, contact_sensor: WyzeContactSensor):
        payload = await self.__create_authenticated_payload({
            "target_pid_list": [],
            "device_model": contact_sensor.product_model,
            "device_mac": contact_sensor.mac,
        })

        response_json = await self.__post_and_recover(WyzeApiConstants.get_device_property_url, payload)

        for item in response_json['data']['property_list']:
            if contact_sensor.product_model == "PIR3U":
                if item['pid'] == "P1302":
                    contact_sensor.open_close_state = int(item['value'])
                    contact_sensor.open_close_state_ts = item['ts']
            if contact_sensor.product_model == "DWS3U":
                if item['pid'] == "P1301":
                    contact_sensor.open_close_state = int(item['value'])
                    contact_sensor.open_close_state_ts = item['ts']
            if item['pid'] == "P5":
                contact_sensor.avaliable = int(item['value'])
            if item['pid'] == "P1304":
                contact_sensor.rssi = item['value']
            if item['pid'] == "P1303":
                contact_sensor.voltage = item['value']

    # endregion

    # region Motion Sensor Operations
    async def update_motion_sensor(self, motion_sensor: WyzeMotionSensor):
        payload = await self.__create_authenticated_payload({
            "target_pid_list": [],
            "device_model": motion_sensor.product_model,
            "device_mac": motion_sensor.mac,
        })

        response_json = await self.__post_and_recover(WyzeApiConstants.get_device_property_url, payload)

        for item in response_json['data']['property_list']:
            if motion_sensor.product_model == "PIR3U":
                if item['pid'] == "P1302":
                    motion_sensor.motion_state = int(item['value'])
                    motion_sensor.motion_state_ts = item['ts']
            if motion_sensor.product_model == "PIR3U":
                if item['pid'] == "P1301":
                    motion_sensor.motion_state = int(item['value'])
                    motion_sensor.motion_state_ts = item['ts']
            if item['pid'] == "P5":
                motion_sensor.avaliable = int(item['value'])
            if item['pid'] == "P1304":
                motion_sensor.rssi = item['value']
            if item['pid'] == "P1303":
                motion_sensor.voltage = item['value']
    # endregion
