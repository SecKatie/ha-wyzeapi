"""Constants for the Wyze Home Assistant Integration integration."""

DOMAIN = "wyzeapi"
CONF_CLIENT = "wyzeapi_client"

ACCESS_TOKEN = "access_token"
REFRESH_TOKEN = "refresh_token"
REFRESH_TIME = "refresh_time"
KEY_ID = "key_id"
API_KEY = "api_key"

WYZE_NOTIFICATION_TOGGLE = f"{DOMAIN}.wyze.notification.toggle"

LOCK_UPDATED = f"{DOMAIN}.lock_updated"
CAMERA_UPDATED = f"{DOMAIN}.camera_updated"
LIGHT_UPDATED = f"{DOMAIN}.light_updated"
COVER_UPDATED = f"{DOMAIN}.cover_updated"
AIR_PURIFIER_UPDATED = f"{DOMAIN}.air_purifier_updated"
RESET_BUTTON_PRESSED = f"{DOMAIN}.reset_button_pressed"
# EVENT NAMES
WYZE_CAMERA_EVENT = "wyze_camera_event"

# Cam Plus AI smart-detection object-class codes seen in ``event.tag_list``.
# Wyze publishes no official map; these are community-documented and
# cross-corroborated by two independent reverse-engineering efforts:
# shauntarves/wyze-sdk's ``AiEventType`` enum and JoshuaMulliken/ha-wyzeapi#187.
# Unknown codes fall back to ``tag_<code>`` so novel kinds still surface.
WYZE_EVENT_TAG_MAP = {
    101: "person",
    102: "vehicle",
    103: "pet",
    104: "package",
    101001: "face",
    800001: "baby_crying",
    800002: "dog_barking",
    800003: "cat_meowing",
}

BULB_LOCAL_CONTROL = "bulb_local_control"
DEFAULT_LOCAL_CONTROL = True

# Yunding (YD) is the provider for Wyze Lock Bolt
YDBLE_LOCK_STATE_UUID = "00002220-0000-6b63-6f6c-2e6b636f6f6c"
YDBLE_UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
YDBLE_UART_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
