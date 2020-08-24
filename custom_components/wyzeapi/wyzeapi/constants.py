from enum import Enum


class WyzeApiConstants:
    # URLs
    login_url: str = "https://api.wyzecam.com/app/user/login"
    refresh_token_url: str = "https://api.wyzecam.com/app/user/refresh_token"
    get_devices_url: str = "https://api.wyzecam.com/app/v2/home_page/get_object_list"
    set_device_property_url: str = 'https://api.wyzecam.com/app/v2/device/set_property_list'
    get_device_property_url: str = "https://api.wyzecam.com/app/v2/device/get_property_list"

    # Payload constants
    device_id: str = "bc151f39-787b-4871-be27-5a20fd0a1937"
    app_name: str = "com.hualai.WyzeCam"
    app_version: str = "2.6.62"
    sc: str = "9f275790cab94a72bd206c8876429f3c"
    sv: str = "41267de22d1847c8b99bfba2658f88d7"
    phone_system_type: str = "1"
    app_ver: str = "com.hualai.WyzeCam___2.6.62"
    base_payload: dict

    class Device(Enum):
        Light = "Light"
        Plug = "Plug"
        ContactSensor = "ContactSensor"
        MotionSensor = "MotionSensor"
        Lock = "Lock"

    def __init__(self):
        base_paylod: dict = {
            'phone_id': self.device_id,
            'app_name': self.app_name,
            'app_version': self.app_version,
            'sc': self.sc,
            'sv': self.sv,
            'phone_system_type': self.phone_system_type,
            'app_ver': self.app_ver
        }
