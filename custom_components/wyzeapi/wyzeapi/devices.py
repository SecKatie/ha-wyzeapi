class WyzeDevice:
    __nick_name: str
    product_model: str
    mac: str

    def __init__(self, nick_name, product_model, mac):
        self.__nick_name = nick_name
        self.product_model = product_model
        self.mac = mac


class WifiEnabledWyzeDevice(WyzeDevice):
    __ip: str
    rssi: str
    __ssid: str

    def __init__(self, nick_name, product_model, mac, ssid, rssi, ip):
        super().__init__(nick_name, product_model, mac)

        self.__ssid = ssid
        self.rssi = rssi
        self.__ip = ip


class WyzeBulb(WifiEnabledWyzeDevice):
    switch_state: int
    avaliable: int
    brightness: int
    color_temp: int

    def __init__(self, nick_name, product_model, mac, switch_state, rssi, ssid, ip):
        super().__init__(nick_name, product_model, mac, ssid, rssi, ip)

        self.switch_state = switch_state


class WyzeSwitch(WifiEnabledWyzeDevice):
    switch_state: int
    avaliable: int

    def __init__(self, nick_name, product_model, mac, switch_state, rssi, ssid, ip):
        super().__init__(nick_name, product_model, mac, ssid, rssi, ip)

        self.switch_state = switch_state
        self.__rssi = rssi
        self.__ssid = ssid
        self.__ip = ip


class WyzeLock(WyzeDevice):
    __open_close_state: int
    __switch_state: int

    def __init__(self, nick_name, product_model, mac, switch_state, open_close_state):
        super().__init__(nick_name, product_model, mac)

        self.__switch_state = switch_state
        self.__open_close_state = open_close_state


class WyzeSensor(WyzeDevice):
    __voltage: str
    __rssi: str

    def __init__(self, nick_name, product_model, mac, voltage, rssi):
        super().__init__(nick_name, product_model, mac)

        self.__voltage = voltage
        self.__rssi = rssi


class WyzeContactSensor(WyzeSensor):
    __open_close_state: int
    __open_close_state_ts: str

    def __init__(self, nick_name, product_model, mac, open_close_state, open_close_state_ts, voltage, rssi):
        super().__init__(nick_name, product_model, mac, voltage, rssi)

        self.__open_close_state = open_close_state
        self.__open_close_state_ts = open_close_state_ts


class WyzeMotionSensor(WyzeSensor):
    __motion_state: int
    __motion_state_ts: str

    def __init__(self, nick_name, product_model, mac, motion_state, motion_state_ts, voltage, rssi):
        super().__init__(nick_name, product_model, mac, voltage, rssi)

        self.__motion_state = motion_state
        self.__motion_state_ts = motion_state_ts
