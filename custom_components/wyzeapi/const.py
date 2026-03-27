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
RESET_BUTTON_PRESSED = f"{DOMAIN}.reset_button_pressed"
# EVENT NAMES
WYZE_CAMERA_EVENT = "wyze_camera_event"

BULB_LOCAL_CONTROL = "bulb_local_control"
DEFAULT_LOCAL_CONTROL = True

# Yunding (YD) is the provider for Wyze Lock Bolt
YDBLE_LOCK_STATE_UUID = "00002220-0000-6b63-6f6c-2e6b636f6f6c"
YDBLE_UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
YDBLE_UART_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

# IoT3 API for DX-family devices (Lock Bolt v2, Palm Lock, etc.)
IOT3_BASE_URL = "https://app.wyzecam.com/app/v4/iot3"
IOT3_GET_PROPERTY_PATH = "/app/v4/iot3/get-property"
IOT3_RUN_ACTION_PATH = "/app/v4/iot3/run-action"
IOT3_APP_HOST = "https://app.wyzecam.com"
OLIVE_SIGNING_SECRET = "wyze_app_secret_key_132"
OLIVE_APP_ID = "9319141212m2ik"
OLIVE_APP_INFO = "wyze_android_3.11.0.758"
IOT3_MODELS = {"DX_LB2", "DX_PVLOC"}
