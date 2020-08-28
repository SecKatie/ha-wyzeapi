from .base import BaseDevice
from ..interfaces import IUpdatable
from typing import Dict


class BaseSensor(BaseDevice, IUpdatable):
    voltage: str
    rssi: str
    avaliable: int

    def __init__(self, nick_name, product_model, mac, voltage, rssi):
        super().__init__(nick_name, product_model, mac)

        self.voltage = voltage
        self.rssi = rssi

    def prop_map(self) -> Dict:
        prop_map = {
            "P5": self.avaliable,
            "P1304": self.rssi,
            "P1303": self.voltage,
        }

        if self.product_model == "PIR3U":
            prop_map.update({
                "P1302": self.open_close_state
            })
        if self.product_model == "DWS3U":
            prop_map.update({
                "P1301": self.open_close_state
            })

        return prop_map
