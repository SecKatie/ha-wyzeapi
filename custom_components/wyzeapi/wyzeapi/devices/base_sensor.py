from .base import BaseDevice


class BaseSensor(BaseDevice):
    voltage: str
    rssi: str
    available: int

    def __init__(self, nick_name, product_model, mac, voltage, rssi):
        super().__init__(nick_name, product_model, mac)

        self.voltage = voltage
        self.rssi = rssi
