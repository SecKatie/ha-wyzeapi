from .base_sensor import BaseSensor


class ContactSensor(BaseSensor):
    open_close_state: int
    open_close_state_ts: str

    def __init__(self, nick_name, product_model, mac, open_close_state, open_close_state_ts, voltage, rssi):
        super().__init__(nick_name, product_model, mac, voltage, rssi)

        self.open_close_state = open_close_state
        self.open_close_state_ts = open_close_state_ts
