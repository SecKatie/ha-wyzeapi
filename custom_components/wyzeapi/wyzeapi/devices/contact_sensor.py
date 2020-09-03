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
            "P5": ("avaliable", "int"),
            "P1304": ("rssi", "str"),
            "P1303": ("voltage", "str")
        }

        if self.product_model == "PIR3U":
            prop_map.update({
                "P1302": ("open_close_state", "int")
            })
        if self.product_model == "DWS3U":
            prop_map.update({
                "P1301": ("open_close_state", "int")
            })

        return prop_map
