from typing import Dict

from .base_sensor import BaseSensor
from ..interfaces import IUpdatable


class MotionSensor(BaseSensor, IUpdatable):
    motion_state: int
    motion_state_ts: str

    def __init__(self, nick_name, product_model, mac, motion_state, motion_state_ts, voltage, rssi):
        super().__init__(nick_name, product_model, mac, voltage, rssi)

        self.motion_state = motion_state
        self.motion_state_ts = motion_state_ts

    def prop_map(self) -> Dict:
        prop_map = {
            "P5": ("avaliable", "int"),
            "P1304": ("rssi", "str"),
            "P1303": ("voltage", "str")
        }

        if self.product_model == "PIR3U":
            prop_map.update({
                "P1302": ("motion_state", "int")
            })
        if self.product_model == "DWS3U":
            prop_map.update({
                "P1301": ("motion_state", "int")
            })

        return prop_map
