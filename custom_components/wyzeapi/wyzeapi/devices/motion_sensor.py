from .base_sensor import BaseSensor


class MotionSensor(BaseSensor):
    motion_state: int
    motion_state_ts: str

    def __init__(self, nick_name, product_model, mac, motion_state, motion_state_ts, voltage, rssi):
        super().__init__(nick_name, product_model, mac, voltage, rssi)

        self.motion_state = motion_state
        self.motion_state_ts = motion_state_ts
