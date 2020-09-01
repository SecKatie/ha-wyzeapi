from typing import Dict

from .base_networked_device import BaseNetworkedDevice
from ..interfaces import ISwitchable, IUpdatable


class Switch(BaseNetworkedDevice, ISwitchable, IUpdatable):
    switch_state: int

    def __init__(self, nick_name, product_model, mac, switch_state, rssi, ssid, ip):
        super().__init__(nick_name, product_model, mac, ssid, rssi, ip)

        self.switch_state = switch_state
        self.__rssi = rssi
        self.__ssid = ssid
        self.__ip = ip

    @staticmethod
    def switch_on_props(**kwargs) -> Dict:
        return {"P3": "1"}

    @staticmethod
    def switch_off_props(**kwargs) -> Dict:
        return {"P3": "0"}

    def prop_map(self) -> Dict:
        return {
            "P3": self.switch_state,
            "P5": self.available,
            "P1612": self.rssi
        }
