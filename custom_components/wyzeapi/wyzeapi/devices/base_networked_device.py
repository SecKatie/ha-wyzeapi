from .base import BaseDevice


class BaseNetworkedDevice(BaseDevice):
    ip: str
    rssi: str
    ssid: str

    def __init__(self, nick_name, product_model, mac, ssid, rssi, ip):
        super().__init__(nick_name, product_model, mac)

        self.ssid = ssid
        self.rssi = rssi
        self.ip = ip
