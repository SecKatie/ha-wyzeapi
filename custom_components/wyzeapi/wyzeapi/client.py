#!/usr/bin/python3

import asyncio
import logging
import time
from hashlib import md5
from typing import List, Any

import aiohttp

from .constants import WyzeApiConstants
from .devices import *
from .interfaces.ISwitchable import ISwitchable

_LOGGER = logging.getLogger(__name__)


class WyzeApiClient:
    __access_token: str = ""
    __refresh_token: str = ""
    __logged_in: bool = False
    __user_name: str
    __password: str
    __hashed_password: str

    __bulbs: List[Bulb] = []
    __switches: List[Switch] = []
    __contact_sensors: List[ContactSensor] = []
    __motion_sensors: List[MotionSensor] = []
    __locks: List[Lock] = []

    # Control flow on loading devices
    __devices_have_loaded = False
    __load_devices_lock = asyncio.Lock()

    # Control flow on recovering logged in status
    __logging_in_lock = asyncio.Lock()
    __fixed_access_token = False

    async def __reset_fixed_access_token(self):
        await asyncio.sleep(300)
        self.__fixed_access_token = False
        _LOGGER.debug("Allowed the app to login again")

    @staticmethod
    async def __post_to_server(url: str, payload: dict):
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response_json = await response.json()
                return response_json

    async def __post_and_recover(self, url: str, payload: dict):
        response_json = await self.__post_to_server(url, payload)

        response_code = response_json['code']

        if response_code != '1' and response_json['msg'] == 'AccessTokenError':
            _LOGGER.error("AccessTokenError occurred. Will attempt to login again.")
            async with self.__logging_in_lock:
                if not self.__fixed_access_token:
                    await self.login(self.__user_name, self.__password)
                    _LOGGER.debug("Logged in again")
                    self.__fixed_access_token = True

                    asyncio.get_running_loop().create_task(
                        self.__reset_fixed_access_token())

            payload = await self.__create_authenticated_payload(payload)

            return await self.__post_and_recover(url, payload)
        if response_code == '1001':
            _LOGGER.debug("Request to: {} does not respond to parameters in payload {} and gave a result of {}".format(
                url, payload, response_json))
            raise AttributeError("Parameters passed to Wyze Service do not fit the endpoint")
        if response_code != '1':
            _LOGGER.debug("Request to: {} failed with payload: {} with result of {}".format(
                url, payload, response_json))
            raise ConnectionError("Failed to connect to the Wyze Service")

        return response_json

    @staticmethod
    async def __create_payload(extras: dict = None) -> dict:
        updated_payload = WyzeApiConstants.base_payload.copy()
        updated_payload['ts'] = str(int(time.time()))
        if extras:
            updated_payload.update(extras)
        return updated_payload

    async def __create_authenticated_payload(self, extras: dict = None) -> dict:
        updated_payload = await self.__create_payload()
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
        self.__password = password
        self.__hashed_password = self.create_md5_md5(password)

        payload = await self.__create_payload({
            "password": self.__hashed_password,
            "user_name": self.__user_name,
            "two_factor_auth": "",
            "access_token": ""
        })

        response_json = await self.__post_to_server(WyzeApiConstants.login_url, payload)

        if response_json['msg'] == "UserIsLocked":
            _LOGGER.error("The user account is locked")
            raise ConnectionError("Failed to login with response: {0}".format(response_json))
        if response_json['msg'] == "UserNameOrPasswordError":
            _LOGGER.error("The username or password is incorrect")
            raise ConnectionError("Failed to login with response: {0}".format(response_json))

        try:
            self.__access_token = response_json['data']['access_token']
            self.__refresh_token = response_json['data']['refresh_token']

            self.__logged_in = True
        except KeyError:
            _LOGGER.error("Failure to login with supplied credentials")
            self.__logged_in = False

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
        except KeyError:
            _LOGGER.error("Failed to refresh access token. Must login again.")
            await self.login(self.__user_name, self.__password)

    async def logout(self):
        _LOGGER.debug("Running logout")
        self.__access_token = ""
        self.__refresh_token = ""
        self.__logged_in = False

    # endregion

    # region Switch Operations
    async def turn_on(self, switch_device: ISwitchable) -> ISwitchable:
        _LOGGER.debug("Turning on: " + switch_device.nick_name)
        props = switch_device.switch_on_props()

        if len(props) > 1:
            url = WyzeApiConstants.set_device_property_list_url
            property_list = []
            for prop in props:
                property_list.append({"pid": prop, "pvalue": props[prop]})

            payload = await self.__create_authenticated_payload({
                "property_list": property_list,
                "device_model": switch_device.product_model,
                "device_mac": switch_device.mac
            })

        elif len(props) == 1:
            url = WyzeApiConstants.set_device_property_url

            prop = props.popitem()
            payload = await self.__create_authenticated_payload({
                'pid': prop[0],
                'pvalue': prop[1],
                "device_model": switch_device.product_model,
                "device_mac": switch_device.mac
            })
        else:
            raise ValueError("switch_on_props() must return at least on property.")

        asyncio.get_running_loop().create_task(
            self.__post_and_recover(url, payload))

        return switch_device

    async def turn_off(self, switch_device: ISwitchable) -> ISwitchable:
        _LOGGER.debug("Turning off: " + switch_device.nick_name)
        props = switch_device.switch_off_props()
        url = WyzeApiConstants.set_device_property_url

        if len(props) == 1:
            prop = props.popitem()
            payload = await self.__create_authenticated_payload({
                'pid': prop[0],
                'pvalue': prop[1],
                "device_model": switch_device.product_model,
                "device_mac": switch_device.mac
            })

            asyncio.get_running_loop().create_task(
                self.__post_and_recover(url, payload))
        else:
            raise ValueError("switch_off_props() must return at least one property.")

        return switch_device

    # endregion

    # region Update Operations
    async def update(self, device: IUpdatable) -> Any:
        _LOGGER.debug("Updating: {}".format(device.nick_name))

        payload = await self.__create_authenticated_payload({
            "target_pid_list": [],
            "device_model": device.product_model,
            "device_mac": device.mac
        })

        response_json = await self.__post_and_recover(WyzeApiConstants.get_device_property_url, payload)

        prop_map = device.prop_map()

        for item in response_json['data']['property_list']:
            if item['pid'] in prop_map.keys():
                value = item['value']
                device_prop = prop_map[item['pid']][0]
                prop_type = prop_map[item['pid']][1]

                if prop_type == "str":
                    vars(device)[device_prop] = str(value)
                elif prop_type == "int":
                    vars(device)[device_prop] = int(value)

                if 'ts' in item:
                    vars(device)[device_prop + "_ts"] = int(item['ts'])

        return device

    # endregion

    # region Getting Devices
    async def refresh_devices(self) -> None:
        _LOGGER.debug("Running refresh_devices")
        self.__devices_have_loaded = False
        self.__bulbs = []
        self.__switches = []
        self.__locks = []
        self.__contact_sensors = []
        self.__motion_sensors = []
        await self.get_devices()

    async def get_devices(self):
        _LOGGER.debug("Running get_devices")
        async with self.__load_devices_lock:
            if not self.__devices_have_loaded:
                payload = await self.__create_authenticated_payload()

                response_json = await self.__post_and_recover(WyzeApiConstants.get_devices_url, payload)

                devices = response_json['data']['device_list']

                for device in devices:
                    if device['product_type'] == "Light":
                        self.__bulbs.append(Bulb(device['nickname'], device['product_model'], device['mac'],
                                                 device['device_params']['switch_state'],
                                                 device['device_params']['rssi'], device['device_params']['ssid'],
                                                 device['device_params']['ip']))
                    elif device['product_type'] == "Plug":
                        self.__switches.append(Switch(device['nickname'], device['product_model'], device['mac'],
                                                      device['device_params']['switch_state'],
                                                      device['device_params']['rssi'],
                                                      device['device_params']['ssid'],
                                                      device['device_params']['ip']))
                    elif device['product_type'] == "Lock":
                        self.__locks.append(Lock(device['nickname'], device['product_model'], device['mac'],
                                                 device['device_params']['switch_state'],
                                                 device['device_params']['open_close_state']))
                    elif device['product_type'] == "ContactSensor":
                        self.__contact_sensors.append(ContactSensor(
                            device['nickname'], device['product_model'], device['mac'],
                            device['device_params']['open_close_state'],
                            device['device_params']['open_close_state_ts'],
                            device['device_params']['voltage'],
                            device['device_params']['rssi'],
                        ))
                    elif device['product_type'] == "MotionSensor":
                        self.__motion_sensors.append(MotionSensor(
                            device['nickname'], device['product_model'], device['mac'],
                            device['device_params']['motion_state'],
                            device['device_params']['motion_state_ts'],
                            device['device_params']['voltage'],
                            device['device_params']['rssi'],
                        ))
                self.__devices_have_loaded = True

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
