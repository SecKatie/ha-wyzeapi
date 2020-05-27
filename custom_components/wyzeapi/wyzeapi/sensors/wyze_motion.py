import asyncio
import logging

_LOGGER = logging.getLogger(__name__)

class WyzeMotionSensor():
    def __init__(self, api, device_mac, friendly_name, state, open_close_state_ts, voltage, rssi, device_model):
        _LOGGER.debug("Motion Sensor " + device_mac + " " +friendly_name + " " + "initializing.")
        self._api = api
        self._device_mac = device_mac
        self._friendly_name = friendly_name
        self._state = state
        self._avaliable = True
        self._just_changed_state = False
        self._device_model = device_model
        self._rssi = rssi
        self._voltage = voltage
        self._open_close_state_ts = open_close_state_ts
    def is_on(self):
        return self._state
    async def async_update(self):
        _LOGGER.debug("Motion Sensor " + self._friendly_name + " updating.")
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
                "access_token": self._api._access_token,
                "refresh_token": self._api._refresh_token
            }
            data = await self._api.async_do_request(url, payload)
            for item in data['data']['property_list']:
                if self._device_model =="PIR3U":
                    if item['pid'] == "P1302":
                        self._state = True if int(item['value']) == 1 else False
                        self._open_close_state_ts = item['ts']
                    if item['pid'] == "P1304":
                       self._rssi = item['value']
                    if item['pid'] == "P1303":
                       self._voltage = item['value']
                if self._device_model == "DWS3U":
                    if item['pid'] == "P1301":
                        self._state = True if int(item['value']) == 1 else False
                        self._open_close_state_ts = item['ts']
                    if item['pid'] == "P1304":
                       self._rssi = item['value']
                    if item['pid'] == "P1303":
                       self._voltage = item['value']
                elif item['pid'] == "P5":
                    self._avaliable = False if int(item['value']) == 0 else True
