from typing import Dict
from .base_networked_device import BaseNetworkedDevice
from ..interfaces import ISwitchable
from ..interfaces import IUpdatable


class Bulb(BaseNetworkedDevice, ISwitchable, IUpdatable):
    switch_state: int
    brightness: int
    color_temp: int

    def __init__(self, nick_name, product_model, mac, switch_state, rssi, ssid, ip):
        super().__init__(nick_name, product_model, mac, ssid, rssi, ip)

        self.switch_state = switch_state
        self.brightness = 0
        self.color_temp = 0

    def prop_map(self) -> Dict:
        prop_map = {
            "P3": self.switch_state,
            "P5": self.avaliable,
            "P1612": self.rssi
        }
        if self.brightness is not None:
            prop_map["P1501"] = self.brightness
        if self.color_temp is not None:
            prop_map["P1502"] = self.color_temp

        return prop_map

    def switch_on_props(self) -> Dict:
        properties = {"P3": "1"}  # Turn on

        if self.brightness is not None:
            properties["P1501"] = str(self.brightness)

        if self.color_temp is not None:
            properties["P1502"] = str(self.color_temp)

        return properties

    @staticmethod
    def switch_off_props(**kwargs) -> Dict:
        return {"P3": "0"}  # Turn off
