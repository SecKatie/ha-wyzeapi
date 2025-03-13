import asyncio
import binascii
import logging
from datetime import datetime, timedelta
from typing import Dict

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import YDBLE_LOCK_STATE_UUID, YDBLE_UART_RX_UUID, YDBLE_UART_TX_UUID
from .ydble_utils import decrypt_ecb, pack_l1, pack_l2_dict, pack_l2_lock_unlock, parse_l1, parse_l2_dict

_LOGGER = logging.getLogger(__name__)


class WyzeLockBoltCoordinator(DataUpdateCoordinator):
    """Manages fetching data from BLE periodically."""

    def __init__(self, hass, lock_service, lock) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Wyze Lock State Updater",
            update_interval=timedelta(seconds=300),
        )
        self._lock_service = lock_service
        self._lock = lock
        # The `mac` in the original response should be UUID. 
        # The actual MAC address should be retrieved from another API.
        self._uuid = lock.mac
        self._mac = None
        self._bleak_client = None
        self._current_command = None
        
    async def update_lock_info(self):
        self._lock = await self._lock_service.update(self._lock)
        mac = self._lock.raw_dict["hardware_info"]["mac"]
        # The mac is stored reverse ordered and no colon, e.g. mac="ab8967452301"
        self._mac = ":".join(mac[i-2:i] for i in range(12, 0, -2)).upper()

    async def _async_update_data(self):
        """Fetch the latest data from BLE device."""
        # Skip if running a command
        if self._current_command:
            return self.data

        client = await self._get_ble_client()
        try:
            value = await client.read_gatt_char(YDBLE_LOCK_STATE_UUID)
            return self._parse_state(value)
        finally:
            await self._disconnect()

    async def lock_unlock(self, command="lock"):
        self._current_command = command
        self.async_update_listeners()
        client = await self._get_ble_client()

        # disconnect in 10 seconds in case of error
        asyncio.create_task(self._disconnect(delay=10))

        context = {"command": command, "stage": 0}
        async def _handle_uart_rx_context(sender, data):
            await self._handle_uart_rx(sender, data, client, context)

        await client.start_notify(YDBLE_UART_RX_UUID, _handle_uart_rx_context)
        await client.start_notify(YDBLE_LOCK_STATE_UUID, self._handle_state)
        await self._request_challenge(client)

    async def _request_challenge(self, client: BleakClient):
        l2_content = pack_l2_dict(0x91, 0, {10: b'\x27'})
        req = pack_l1(0, 1, l2_content)
        await client.write_gatt_char(YDBLE_UART_TX_UUID, req, response=False)

    async def _send_lock_unlock(self, client: BleakClient, challenge, command):
        l2_content = pack_l2_lock_unlock(self._lock.ble_id, self._lock.ble_token, challenge, command)
        req = pack_l1(0, 2, l2_content)
        await client.write_gatt_char(YDBLE_UART_TX_UUID, req, response=False)

    async def _send_ack(self, client:BleakClient, seq_no: int):
        req = pack_l1(0x08, seq_no, b'')
        await client.write_gatt_char(YDBLE_UART_TX_UUID, req, response=False)

    async def _handle_state(self, sender, data: bytearray):
        self.data = self._parse_state(data)
        self._current_command = None
        self.async_update_listeners()

    def _parse_state(self, state_data):
        data = decrypt_ecb(self._uuid[-16:].lower(), state_data)
        result = {
            "state": data[0],
            "timestamp": datetime.fromtimestamp(int.from_bytes(data[1:5]))
        }
        return result

    async def _handle_uart_rx(self, sender, data: bytearray, client: BleakClient, context: Dict):
        # Process for unfinished data
        if "l1_unfinished" in context:
            data = context["l1_unfinished"] + data
            del context["l1_unfinished"]
        l2_data, l1_flags, seq_no, remain = parse_l1(data)
        if remain:
            context["l1_unfinished"] = data
            return
        
        # Process messages
        if context["stage"] == 0:
            # Ack for request chanllenge
            if seq_no == 1 and l1_flags == 0x48:
                context["stage"] = 1
                return
        if context["stage"] == 1:
            if l1_flags == 0x40:
                # Process L2 dict
                cmd, l2_flags, l2_dict = parse_l2_dict(l2_data)
                if cmd == 0x86 and 0xd2 in l2_dict:
                    # Got generated chanllenge
                    challenge = l2_dict[0xd2]
                    await self._send_ack(client, seq_no=seq_no)
                    await self._send_lock_unlock(client, challenge, context["command"])
                    context["stage"] = 2
                    return
        if context["stage"] == 2:
            # Ack for send_lock_unlock
            if seq_no == 2 and l1_flags == 0x48:
                context["stage"] = 3
                return
        if context["stage"] == 3:
            if l1_flags == 0x40:
                cmd, l2_flags, l2_dict = parse_l2_dict(l2_data)
                if cmd == 0x04:
                    await self._send_ack(client, seq_no=seq_no)
                    return
        _LOGGER.warning(f"Unexpected message: stage={context['stage']}"
                        f" flags={l1_flags:01x}, seq_no={seq_no:02x},"
                        f" l2_data={binascii.hexlify(l2_data)}")
        

    async def _get_ble_client(self) -> BleakClient:
        if not self._bleak_client or not self._bleak_client.is_connected:
            if not self._mac:
                raise PlatformNotReady("Not initialized")
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self._mac, connectable=True
            )
            self._bleak_client = await establish_connection(BleakClient, ble_device, ble_device.address)
        return self._bleak_client

    async def _disconnect(self, delay=0):
        await asyncio.sleep(delay)
        if self._bleak_client and self._bleak_client.is_connected:
            await self._bleak_client.disconnect()
        self._current_command = None