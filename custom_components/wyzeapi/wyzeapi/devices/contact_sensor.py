from typing import Dict

from .base_sensor import BaseSensor
from ..interfaces import IUpdatable


class ContactSensor(BaseSensor, IUpdatable):
    open_close_state: int
    open_close_state_ts: str

    def __init__(self, nick_name, product_model, mac, open_close_state, open_close_state_ts, voltage, rssi):
        super().__init__(nick_name, product_model, mac, voltage, rssi)

        self.open_close_state = open_close_state
        self.open_close_state_ts = open_close_state_ts

    def prop_map(self) -> Dict:
        prop_map = {
            "P5": self.available,
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
