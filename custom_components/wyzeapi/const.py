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

# Yunding (YD) is the provider for Wyze Lock Bolt
YDBLE_LOCK_STATE_UUID = "00002220-0000-6b63-6f6c-2e6b636f6f6c"
YDBLE_UART_RX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
YDBLE_UART_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
# Connection-type declaration, in the lock monitor service 00002500-0000-6b63-6f6c-2e6b636f6f6c.
# Without it the lock hangs up ~6s after connecting; with it the link stays open until we
# close it. Measured on a YD_BT1: 6.11s without, still connected at 75.32s with.
YDBLE_CON_TYPE_UUID = "00002250-0000-6b63-6f6c-2e6b636f6f6c"
# The app encrypts this fixed 16-byte plaintext with the lock key and writes the result.
# 11 payload bytes plus the "loock" marker, the same block format as lock state.
YDBLE_CON_TYPE_PLAINTEXT = b"10000000000loock"
# The lock allows only one BLE connection at a time, so the link must be released
# promptly after a command or the owner's phone app cannot reach the lock at all.
BOLT_COMMAND_DISCONNECT_SECONDS = 3
# Safety net if an exchange never completes and no state notification arrives.
BOLT_COMMAND_TIMEOUT_SECONDS = 30
