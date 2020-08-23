import logging

from ..wyzeapi import WyzeApi

_LOGGER = logging.getLogger(__name__)


class WyzeMotionSensor:
    def __init__(self, api: WyzeApi, device_mac,
                 friendly_name, state, open_close_state_ts,
                 voltage, rssi, device_model):
        _LOGGER.debug("Motion Sensor " + device_mac + " " + friendly_name + " " + "initializing.")
        self.__api = api
        self.device_mac = device_mac
        self.friendly_name = friendly_name
        self.state = state
        self.__available = True
        self.__just_changed_state = False
        self.device_model = device_model
        self.rssi = rssi
        self.voltage = voltage
        self.open_close_state_ts = open_close_state_ts

    def is_on(self):
        return self.state

    async def async_update(self):
        _LOGGER.debug("Motion Sensor " + self.friendly_name + " updating.")
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
            for item in data['data']['property_list']:
                if self.device_model == "PIR3U":
                    if item['pid'] == "P1302":
                        self.state = True if int(item['value']) == 1 else False
                        self.open_close_state_ts = item['ts']
                    if item['pid'] == "P1304":
                        self.rssi = item['value']
                    if item['pid'] == "P1303":
                        self.voltage = item['value']
                if self.device_model == "DWS3U":
                    if item['pid'] == "P1301":
                        self.state = True if int(item['value']) == 1 else False
                        self.open_close_state_ts = item['ts']
                    if item['pid'] == "P1304":
                        self.rssi = item['value']
                    if item['pid'] == "P1303":
                        self.voltage = item['value']
                elif item['pid'] == "P5":
                    self.__available = False if int(item['value']) == 0 else True
