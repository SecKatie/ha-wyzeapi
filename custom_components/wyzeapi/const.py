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

BULB_LOCAL_CONTROL = "bulb_local_control"
DEFAULT_LOCAL_CONTROL = True

# Per-camera RTSP snapshot configuration. Stored under
# options[CONF_CAMERAS][<camera mac>] as a dict with the keys below.
CONF_CAMERAS = "cameras"
CONF_RTSP_ENABLED = "rtsp_enabled"
CONF_RTSP_USERNAME = "rtsp_username"
CONF_RTSP_PASSWORD = "rtsp_password"
CONF_RTSP_SECURE = "rtsp_secure"
RTSP_PORT = 554
RTSPS_PORT = 322

# Yunding (YD) is the provider for Wyze Lock Bolt
YDBLE_LOCK_STATE_UUID = "00002220-0000-6b63-6f6c-2e6b636f6f6c"
YDBLE_UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
YDBLE_UART_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
