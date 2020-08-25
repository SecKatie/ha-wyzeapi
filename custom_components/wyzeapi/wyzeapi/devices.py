class WyzeDevice:
    nick_name: str
    product_model: str
    mac: str
    avaliable: int

    def __init__(self, nick_name, product_model, mac):
        self.nick_name = nick_name
        self.product_model = product_model
        self.mac = mac


class WifiEnabledWyzeDevice(WyzeDevice):
    ip: str
    rssi: str
    ssid: str

    def __init__(self, nick_name, product_model, mac, ssid, rssi, ip):
        super().__init__(nick_name, product_model, mac)

        self.ssid = ssid
        self.rssi = rssi
        self.ip = ip


class WyzeBulb(WifiEnabledWyzeDevice):
    switch_state: int
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
    open_close_state: int
    switch_state: int
    avaliable: int

    def __init__(self, nick_name, product_model, mac, switch_state, open_close_state):
        super().__init__(nick_name, product_model, mac)

        self.switch_state = switch_state
        self.open_close_state = open_close_state


class WyzeSensor(WyzeDevice):
    voltage: str
    rssi: str
    avaliable: int

    def __init__(self, nick_name, product_model, mac, voltage, rssi):
        super().__init__(nick_name, product_model, mac)

        self.voltage = voltage
        self.rssi = rssi


class WyzeContactSensor(WyzeSensor):
    open_close_state: int
    open_close_state_ts: str

    def __init__(self, nick_name, product_model, mac, open_close_state, open_close_state_ts, voltage, rssi):
        super().__init__(nick_name, product_model, mac, voltage, rssi)

        self.open_close_state = open_close_state
        self.open_close_state_ts = open_close_state_ts


class WyzeMotionSensor(WyzeSensor):
    motion_state: int
    motion_state_ts: str

    def __init__(self, nick_name, product_model, mac, motion_state, motion_state_ts, voltage, rssi):
        super().__init__(nick_name, product_model, mac, voltage, rssi)

        self.motion_state = motion_state
        self.motion_state_ts = motion_state_ts
