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
# EVENT NAMES
WYZE_CAMERA_EVENT = "wyze_camera_event"

BULB_LOCAL_CONTROL = "bulb_local_control"
DEFAULT_LOCAL_CONTROL = True

# Yunding (YD) is the provider for Wyze Lock Bolt
YD_SAAS_BASE_URL = "https://yd-saas-toc.wyzecam.com"
YD_LOCK_STATE_UUID = "00002220-0000-6b63-6f6c-2e6b636f6f6c"
YD_UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
YD_UART_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
