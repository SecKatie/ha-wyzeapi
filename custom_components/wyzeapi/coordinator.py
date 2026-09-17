import asyncio
import binascii
import logging
from datetime import datetime, timedelta
from typing import Dict

from bleak import BleakClient
from bleak.exc import BleakCharacteristicNotFoundError, BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from wyzeapy.services.lock_service import LockService, Lock

from .const import (
    BOLT_COMMAND_DISCONNECT_SECONDS,
    BOLT_COMMAND_TIMEOUT_SECONDS,
    YDBLE_CON_TYPE_PLAINTEXT,
    YDBLE_CON_TYPE_UUID,
    YDBLE_LOCK_STATE_UUID,
    YDBLE_UART_RX_UUID,
    YDBLE_UART_TX_UUID,
)
from .token_manager import token_exception_handler
from .ydble_utils import (
    decrypt_ecb,
    encrypt_ecb,
    pack_l1,
    pack_l2_dict,
    pack_l2_lock_unlock,
    parse_l1,
    parse_l2_dict,
)

_LOGGER = logging.getLogger(__name__)

# Subscribed together for the duration of a lock/unlock exchange.
NOTIFY_UUIDS = (YDBLE_UART_RX_UUID, YDBLE_LOCK_STATE_UUID)


class WyzeLockBoltCoordinator(DataUpdateCoordinator):
    """Manages fetching data from BLE periodically."""

    def __init__(
        self, hass: HomeAssistant, lock_service: LockService, lock: Lock
    ) -> None:
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
        self._disconnect_task: asyncio.Task | None = None
        # Initialize data to prevent errors during setup
        self.data = {"state": None, "timestamp": None}

    @token_exception_handler
    async def update_lock_info(self):
        self._lock = await self._lock_service.update(self._lock)
        mac = self._lock.raw_dict["hardware_info"]["mac"]
        # The mac is stored reverse ordered and no colon, e.g. mac="ab8967452301"
        self._mac = ":".join(mac[i - 2 : i] for i in range(12, 0, -2)).upper()

    async def _async_update_data(self):
        """Fetch the latest data from BLE device."""
        # Skip if running a command
        if self._current_command:
            return self.data

        client = await self._get_ble_client()
        if client is None:
            raise UpdateFailed(
                f"Could not find BLE device {self._lock.nickname} with address {self._mac}. Device may not be in range."
            )

        try:
            value = await client.read_gatt_char(YDBLE_LOCK_STATE_UUID)
            return self._parse_state(value)
        except BleakCharacteristicNotFoundError as e:
            raise UpdateFailed(
                f"Characteristic {YDBLE_LOCK_STATE_UUID} not found on device {self._lock.nickname}. "
                "Device may be locked, have firmware issues, or require pairing."
            ) from e
        finally:
            await self._disconnect()

    async def lock_unlock(self, command="lock"):
        if self._current_command:
            self.async_update_listeners()
            raise Exception(f"Waiting for {self._current_command} command to complete")
        self._current_command = command
        self.async_update_listeners()
        client = await self._get_ble_client()
        if client is None:
            raise Exception(
                f"Could not find BLE device {self._lock.nickname} with address {self._mac}. Device may not be in range."
            )

        # Safety net only: if the exchange never completes, release the link so the
        # owner's phone can reach the lock. A successful command disconnects sooner,
        # from _handle_state.
        self._schedule_disconnect(BOLT_COMMAND_TIMEOUT_SECONDS)

        context = {"command": command, "stage": 0}

        async def _handle_uart_rx_context(sender, data):
            await self._handle_uart_rx(sender, data, client, context)

        # _get_ble_client() reuses a live connection, and the previous command may have
        # left its subscriptions on it, so re-subscribing blindly raises
        # "Notifications are already enabled" and the command silently never runs.
        await self._clear_notifications(client)
        # Order mirrors the Wyze app: subscribe UART RX, declare the connection type,
        # then subscribe to lock state (C21530c.java onDescriptorWrite -> m67679b).
        await client.start_notify(YDBLE_UART_RX_UUID, _handle_uart_rx_context)
        await self._send_connection_type(client)
        await client.start_notify(YDBLE_LOCK_STATE_UUID, self._handle_state)
        await self._request_challenge(client)

    async def _send_connection_type(self, client: BleakClient) -> None:
        """Tell the lock this is an interactive session so it keeps the link open.

        Without this the lock hangs up roughly 6s after connecting, measured at 6.11s
        on a YD_BT1, which silently truncates any command that is still in flight or
        that reuses the connection. With it the link stayed up past 75s. The lock's
        timer runs from connection establishment and is not extended by GATT traffic,
        so there is no keepalive alternative; the Wyze app sends exactly this write and
        has no heartbeat of its own.

        A failure here is logged rather than raised: the command may still finish
        inside the ~6s window.
        """
        try:
            value = encrypt_ecb(self._uuid[-16:].lower(), YDBLE_CON_TYPE_PLAINTEXT)
            await client.write_gatt_char(YDBLE_CON_TYPE_UUID, value, response=False)
        except (BleakError, OSError, ValueError) as err:
            _LOGGER.warning(
                "Could not declare BLE connection type for %s (%s); the lock may drop "
                "the connection ~6s after connecting",
                self._lock.nickname,
                err,
            )

    def _schedule_disconnect(self, delay: int) -> None:
        """(Re)arm the teardown timer, replacing any previous one.

        A stale timer left running would fire partway through the next command and
        clear _current_command on an operation still in flight, which makes a failed
        command look like a state that simply reverted.
        """
        if self._disconnect_task and not self._disconnect_task.done():
            self._disconnect_task.cancel()
        self._disconnect_task = asyncio.create_task(self._disconnect(delay=delay))

    async def _clear_notifications(self, client: BleakClient) -> None:
        """Drop any notification subscriptions left on this connection.

        Must run before re-subscribing rather than during teardown: in the failing
        sequence the teardown has not run yet, which is precisely why the connection is
        still alive to be reused. Clearing rather than skipping the re-subscribe also
        matters because the RX callback closes over a per-command ``context``, so a
        stale subscription would keep feeding the previous command's closure.

        ``stop_notify`` is a no-op when nothing is subscribed, so this is safe on a
        freshly opened connection and needs no subscription bookkeeping.
        """
        for uuid in NOTIFY_UUIDS:
            try:
                await client.stop_notify(uuid)
            except (BleakError, OSError) as err:
                # Never subscribed, characteristic missing, or the link died under us.
                # The start_notify calls that follow surface any real problem.
                _LOGGER.debug(
                    "Could not clear notifications on %s for %s: %s",
                    uuid,
                    self._lock.nickname,
                    err,
                )

    async def _request_challenge(self, client: BleakClient):
        l2_content = pack_l2_dict(0x91, 0, {10: b"\x27"})
        req = pack_l1(0, 1, l2_content)
        await client.write_gatt_char(YDBLE_UART_TX_UUID, req, response=False)

    async def _send_lock_unlock(self, client: BleakClient, challenge, command):
        l2_content = pack_l2_lock_unlock(
            self._lock.ble_id, self._lock.ble_token, challenge, command
        )
        req = pack_l1(0, 2, l2_content)
        await client.write_gatt_char(YDBLE_UART_TX_UUID, req, response=False)

    async def _send_ack(self, client: BleakClient, seq_no: int):
        req = pack_l1(0x08, seq_no, b"")
        await client.write_gatt_char(YDBLE_UART_TX_UUID, req, response=False)

    async def _handle_state(self, sender, data: bytearray):
        self.data = self._parse_state(data)
        self._current_command = None
        self.async_update_listeners()
        # The command is done. The lock now holds the link open indefinitely because of
        # the connection-type declaration, and it accepts only one connection at a time,
        # so release it rather than waiting for the safety-net timeout. The short delay
        # lets the closing ack in _handle_uart_rx go out first.
        self._schedule_disconnect(BOLT_COMMAND_DISCONNECT_SECONDS)

    def _parse_state(self, state_data):
        data = decrypt_ecb(self._uuid[-16:].lower(), state_data)
        result = {
            "state": data[0],
            "timestamp": datetime.fromtimestamp(int.from_bytes(data[1:5])),
        }
        return result

    async def _handle_uart_rx(
        self, sender, data: bytearray, client: BleakClient, context: Dict
    ):
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
                if cmd == 0x86 and 0xD2 in l2_dict:
                    # Got generated chanllenge
                    challenge = l2_dict[0xD2]
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
        _LOGGER.warning(
            f"Unexpected message: stage={context['stage']}"
            f" flags={l1_flags:01x}, seq_no={seq_no:02x},"
            f" l2_data={binascii.hexlify(l2_data)}"
        )

    async def _get_ble_client(self) -> BleakClient | None:
        if not self._bleak_client or not self._bleak_client.is_connected:
            if not self._mac:
                raise PlatformNotReady("Not initialized")
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self._mac, connectable=True
            )
            if ble_device is None:
                return None

            self._bleak_client = await establish_connection(
                BleakClient, ble_device, ble_device.address
            )
        return self._bleak_client

    async def _disconnect(self, delay=0):
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            # Superseded by a newer command; leave its connection alone.
            raise
        # A command still in flight here means the exchange never reported a new state.
        timed_out = self._current_command is not None
        if self._bleak_client and self._bleak_client.is_connected:
            await self._bleak_client.disconnect()
        self._current_command = None
        if timed_out:
            await self._resolve_state_after_timeout()
        else:
            self.async_update_listeners()

    async def _resolve_state_after_timeout(self) -> None:
        """Find out where the bolt actually is after a command with no confirmation.

        Simply clearing the in-flight flag would publish ``self.data``, which still
        holds the value from *before* the command. That is not merely stale, it can be
        actively wrong: a lost confirmation does not mean the bolt did not move.
        Observed on a YD_BT1 whose link dropped mid-exchange: the bolt locked, the
        notification never arrived, and the entity reported ``unlocked`` for a door that
        was locked. A wrong lock state is worse than no lock state, so re-read instead of
        guessing, and let the refresh mark the entity unavailable if the lock cannot be
        reached at all.
        """
        _LOGGER.warning(
            "Command on %s completed without a state notification; re-reading the lock "
            "rather than reporting its previous state",
            self._lock.nickname,
        )
        await self.async_refresh()
