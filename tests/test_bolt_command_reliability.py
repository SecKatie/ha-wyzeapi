"""Tests for Wyze Lock Bolt command reliability on a reused BLE connection.

The Bolt is driven over a single BLE connection that ``lock_unlock()`` deliberately
keeps alive for a short window after a command, so a follow-up command reuses it
instead of paying another 2-7s cold connect. Two bugs lived in that reuse path:

1. ``start_notify()`` was called unconditionally on every command. On an ESPHome
   Bluetooth proxy, ``bleak_esphome`` raises
   ``BleakError: Notifications are already enabled`` when a handle is subscribed
   twice, because ``aioesphomeapi`` stores the unsubscribe handle in a plain dict
   keyed on ``(address, handle)`` and a second subscribe would orphan the first
   callback. The command then silently never ran.

2. The teardown timer was fire-and-forget, so the previous command's timer fired
   partway through the next command and cleared ``_current_command``, making a
   failed command look like a state that simply reverted.

These tests drive the real ``lock_unlock()`` against a fake client that emulates the
proxy's strict subscription accounting, so they fail if either fix regresses.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
import pytest

from custom_components.wyzeapi.const import (
    BOLT_COMMAND_DISCONNECT_SECONDS,
    BOLT_COMMAND_TIMEOUT_SECONDS,
    YDBLE_CON_TYPE_PLAINTEXT,
    YDBLE_CON_TYPE_UUID,
    YDBLE_LOCK_STATE_UUID,
    YDBLE_UART_RX_UUID,
)
from custom_components.wyzeapi.coordinator import NOTIFY_UUIDS
from custom_components.wyzeapi.ydble_utils import decrypt_ecb, encrypt_ecb

LOCK_UUID = "YD_BT1.b38ae5ebd9864864273db2c08fab2c28"

# Protocol constants pinned as literals rather than imported, so these tests act as the
# spec for them. They were recovered from the lock's own firmware behaviour and the
# vendor SDK, and the lock silently ignores a declaration that does not match exactly,
# so a well-meaning edit to const.py must fail here rather than only on real hardware.
EXPECTED_CON_TYPE_UUID = "00002250-0000-6b63-6f6c-2e6b636f6f6c"
EXPECTED_CON_TYPE_PLAINTEXT = b"10000000000loock"


def test_protocol_constants_match_the_lock():
    """A change to either value stops the lock honouring the declaration."""
    assert YDBLE_CON_TYPE_UUID == EXPECTED_CON_TYPE_UUID
    assert YDBLE_CON_TYPE_PLAINTEXT == EXPECTED_CON_TYPE_PLAINTEXT
    # 11 payload bytes plus the 5-byte "loock" marker, one AES-128-ECB block.
    assert len(EXPECTED_CON_TYPE_PLAINTEXT) == 16
    assert EXPECTED_CON_TYPE_PLAINTEXT[11:16] == b"loock"


class FakeProxyClient:
    """Minimal BleakClient emulating bleak_esphome's notification accounting.

    ``start_notify`` raising on a double subscribe is the exact behaviour of
    ``bleak_esphome.backend.client.ESPHomeClient``, which rejects a handle already
    present in its ``_notify_cancels`` map. ``stop_notify`` silently no-ops when
    nothing is subscribed, matching that backend's documented contract.
    """

    def __init__(self):
        self.is_connected = True
        self.subscribed: set[str] = set()
        self.callbacks: dict[str, object] = {}
        self.calls: list[tuple[str, str]] = []
        self.writes: list[bytes] = []
        self.stop_notify_error: Exception | None = None
        self.con_type_error: Exception | None = None

    async def start_notify(self, uuid, callback):
        self.calls.append(("start", uuid))
        if uuid in self.subscribed:
            raise BleakError(
                f"Notifications are already enabled on characteristic:{uuid}"
            )
        self.subscribed.add(uuid)
        self.callbacks[uuid] = callback

    async def deliver(self, uuid, data):
        """Push a notification the way the lock would.

        Requires a live link and a live subscription, because a lock that has hung up
        delivers nothing. That is what makes a dropped connection observable in a test
        rather than something the test hands over anyway.
        """
        if not self.is_connected:
            raise BleakError("Not connected: the lock cannot deliver notifications")
        if uuid not in self.subscribed:
            raise BleakError(f"Not subscribed to {uuid}")
        await self.callbacks[uuid](None, bytearray(data))

    async def stop_notify(self, uuid):
        self.calls.append(("stop", uuid))
        if self.stop_notify_error is not None:
            raise self.stop_notify_error
        self.subscribed.discard(uuid)

    async def write_gatt_char(self, uuid, data, response=False):
        if uuid == YDBLE_CON_TYPE_UUID and self.con_type_error is not None:
            raise self.con_type_error
        self.calls.append(("write", uuid))
        self.writes.append((uuid, bytes(data)))

    async def disconnect(self):
        self.is_connected = False
        self.subscribed.clear()


class FakeBoltLink(FakeProxyClient):
    """A fake that also models the lock's connection lifetime.

    Encodes three facts measured on a real YD_BT1, so that a regression in the
    connection-type declaration shows up as a failing test rather than only as a
    misbehaving lock:

    1. The lock hangs up ~6s after the connection is established. Earliest observed
       drop across four cold connects was 5.92s (then 5.95s, 6.01s, 6.11s), reported
       by the proxy as ``error=19`` / ``ESP_GATT_CONN_TERMINATE_PEER_USER``.
    2. Writing the connection-type declaration removes the limit entirely. Same test
       with the write: still connected at 25.16s, and at 75.32s on a second run.
    3. The deadline runs from establishment and is *not* extended by GATT traffic.
       Last activity at +5.44s, drop at +5.95s; a command that completed at +0.13s
       was still dropped at +5.92s. So ``advance()`` deliberately ignores I/O.

    Time is virtual and driven by ``advance()``, so these tests neither sleep nor
    depend on wall-clock timing.
    """

    #: Earliest drop observed on hardware, used as the model's deadline.
    LIFETIME_SECONDS = 5.92

    def __init__(self):
        super().__init__()
        self.elapsed = 0.0
        self.declared = False
        self.dropped_at: float | None = None

    def advance(self, seconds: float) -> None:
        """Move virtual time forward, hanging up if the lock's patience ran out."""
        self.elapsed += seconds
        if (
            not self.declared
            and self.is_connected
            and self.elapsed >= self.LIFETIME_SECONDS
        ):
            self.dropped_at = self.elapsed
            self.is_connected = False
            self.subscribed.clear()

    def _require_link(self) -> None:
        if not self.is_connected:
            raise BleakError(
                "Not connected: the lock terminated the connection "
                "(ESP_GATT_CONN_TERMINATE_PEER_USER, error=19)"
            )

    async def start_notify(self, uuid, callback):
        self._require_link()
        return await super().start_notify(uuid, callback)

    async def write_gatt_char(self, uuid, data, response=False):
        self._require_link()
        result = await super().write_gatt_char(uuid, data, response=response)
        if uuid == YDBLE_CON_TYPE_UUID and self._is_valid_declaration(data):
            self.declared = True
        return result

    @staticmethod
    def _is_valid_declaration(data) -> bool:
        """The lock honours the declaration only if it decrypts to the exact plaintext.

        A wrong key or a malformed block is indistinguishable from never having sent
        it, so a regression in either still shows up as a dropped link.
        """
        try:
            return (
                decrypt_ecb(LOCK_UUID[-16:].lower(), bytes(data))
                == EXPECTED_CON_TYPE_PLAINTEXT
            )
        except (ValueError, KeyError):
            return False

    async def read_gatt_char(self, uuid):
        self._require_link()
        return bytearray(16)


def make_coordinator(client):
    """Build a real coordinator wired to a fake BLE client."""
    lock = MagicMock()
    lock.mac = LOCK_UUID
    lock.nickname = "Test Bolt"
    lock.ble_id = b"\x01\x02\x03\x04"
    lock.ble_token = b"\x05\x06\x07\x08"

    with patch("homeassistant.helpers.frame.report_usage"):
        from custom_components.wyzeapi.coordinator import WyzeLockBoltCoordinator

        coordinator = WyzeLockBoltCoordinator(MagicMock(), MagicMock(), lock)

    coordinator._mac = "28:68:47:E9:D0:7B"
    coordinator._bleak_client = client
    coordinator.async_update_listeners = MagicMock()
    return coordinator


async def finish_command(coordinator):
    """Emulate the lock reporting its new state, which ends the command."""
    coordinator._current_command = None


@pytest.mark.asyncio
async def test_back_to_back_commands_both_succeed():
    """The regression: a second command on a still-open connection must work.

    Before the fix this raised BleakError on the second unlock and the bolt never
    moved.
    """
    client = FakeProxyClient()
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("unlock")
    await finish_command(coordinator)

    # Connection is deliberately still open, exactly as it is inside the
    # teardown window on a real lock.
    assert client.is_connected

    await coordinator.lock_unlock("lock")

    assert set(client.subscribed) == set(NOTIFY_UUIDS)
    # Two commands, so two challenge writes: the command actually ran.
    challenges = [u for u, _ in client.writes if u not in (YDBLE_CON_TYPE_UUID,)]
    assert len(challenges) == 2


@pytest.mark.asyncio
async def test_notifications_cleared_before_resubscribing():
    """stop_notify must precede start_notify for every notify characteristic."""
    client = FakeProxyClient()
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("lock")

    for uuid in NOTIFY_UUIDS:
        stops = [
            i
            for i, (kind, u) in enumerate(client.calls)
            if kind == "stop" and u == uuid
        ]
        starts = [
            i
            for i, (kind, u) in enumerate(client.calls)
            if kind == "start" and u == uuid
        ]
        assert stops and starts, f"missing stop/start for {uuid}"
        assert min(stops) < min(starts), f"stop_notify must come first for {uuid}"


@pytest.mark.asyncio
async def test_clear_is_safe_on_a_fresh_connection():
    """A never-subscribed connection must not error, and must still subscribe."""
    client = FakeProxyClient()
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("lock")

    assert set(client.subscribed) == set(NOTIFY_UUIDS)


@pytest.mark.asyncio
async def test_stop_notify_failure_does_not_block_the_command():
    """A refused stop_notify is logged and ignored, not propagated.

    The link may have died between the two calls, and start_notify surfaces any
    real problem.
    """
    client = FakeProxyClient()
    client.stop_notify_error = BleakError("not connected")
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("lock")

    assert set(client.subscribed) == set(NOTIFY_UUIDS)
    challenges = [u for u, _ in client.writes if u not in (YDBLE_CON_TYPE_UUID,)]
    assert len(challenges) == 1


@pytest.mark.asyncio
async def test_new_command_cancels_previous_teardown_timer():
    """The stale timer must not fire during the next command.

    Without cancellation the first command's timer clears _current_command midway
    through the second command, so a failure looks like a spurious state revert.
    """
    client = FakeProxyClient()
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("unlock")
    first_timer = coordinator._disconnect_task
    await finish_command(coordinator)

    await coordinator.lock_unlock("lock")
    second_timer = coordinator._disconnect_task

    # cancel() only requests cancellation; let the loop deliver it.
    await asyncio.sleep(0)

    assert first_timer is not second_timer
    assert first_timer.cancelled() or first_timer.done()
    assert not second_timer.done()

    # The live command must still be marked in flight.
    assert coordinator._current_command == "lock"

    second_timer.cancel()


@pytest.mark.asyncio
async def test_teardown_timer_survives_long_enough_for_a_cold_connect():
    """A cold connect alone can eat 5.5s, so the budget must exceed the old 10s."""
    client = FakeProxyClient()
    coordinator = make_coordinator(client)

    delays = []
    original = coordinator._disconnect

    async def record(delay=0):
        delays.append(delay)
        return await original(delay=0)

    coordinator._disconnect = record
    await coordinator.lock_unlock("lock")
    await asyncio.sleep(0)

    assert delays and delays[0] > 10


@pytest.mark.asyncio
async def test_cancelling_teardown_leaves_the_connection_up():
    """Cancelling the timer must not disconnect the link the new command is using."""
    client = FakeProxyClient()
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("unlock")
    await finish_command(coordinator)
    await coordinator.lock_unlock("lock")

    # Give the cancelled timer a chance to run its except branch.
    await asyncio.sleep(0)

    assert client.is_connected
    coordinator._disconnect_task.cancel()


@pytest.mark.asyncio
async def test_second_command_rejected_while_first_in_flight():
    """Pre-existing guard must still hold: no concurrent commands."""
    client = FakeProxyClient()
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("unlock")
    # _current_command intentionally left set: the first command is mid-exchange.

    with pytest.raises(Exception, match="Waiting for unlock"):
        await coordinator.lock_unlock("lock")

    coordinator._disconnect_task.cancel()


@pytest.mark.asyncio
async def test_connection_type_declared_with_correct_payload():
    """The lock hangs up ~6s in without this, so it must be sent and be decryptable."""
    client = FakeProxyClient()
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("lock")

    sent = [data for uuid, data in client.writes if uuid == YDBLE_CON_TYPE_UUID]
    assert len(sent) == 1, "connection type must be declared exactly once per command"
    assert len(sent[0]) == 16, "must be a single AES-128-ECB block"
    assert decrypt_ecb(LOCK_UUID[-16:].lower(), sent[0]) == EXPECTED_CON_TYPE_PLAINTEXT


@pytest.mark.asyncio
async def test_connection_type_sent_after_rx_notify_before_challenge():
    """Mirrors the app: RX notify, then declare, then the exchange starts."""
    client = FakeProxyClient()
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("lock")

    seq = [(k, u) for k, u in client.calls if k in ("start", "write")]
    rx = seq.index(("start", YDBLE_UART_RX_UUID))
    declare = seq.index(("write", YDBLE_CON_TYPE_UUID))
    challenge = next(
        i for i, (k, u) in enumerate(seq) if k == "write" and u != YDBLE_CON_TYPE_UUID
    )
    assert rx < declare < challenge


@pytest.mark.asyncio
async def test_command_proceeds_if_connection_type_write_fails():
    """A refused declaration must not abort the command; it may still finish in ~6s."""
    client = FakeProxyClient()
    client.con_type_error = BleakError("write failed")
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("lock")

    challenges = [u for u, _ in client.writes if u != YDBLE_CON_TYPE_UUID]
    assert len(challenges) == 1


@pytest.mark.asyncio
async def test_link_released_promptly_after_command_completes():
    """The lock allows one connection, so a finished command must free it fast.

    With the connection-type declaration the lock no longer hangs up on its own, so
    failing to release the link would lock the owner's phone out indefinitely.
    """
    client = FakeProxyClient()
    coordinator = make_coordinator(client)

    delays = []
    orig = coordinator._disconnect  # noqa: F841

    async def record(delay=0):
        # Record the scheduled delay without actually tearing the link down.
        delays.append(delay)

    coordinator._disconnect = record

    await coordinator.lock_unlock("lock")
    await asyncio.sleep(0)  # let the scheduled task start
    assert delays == [BOLT_COMMAND_TIMEOUT_SECONDS], "safety net armed on command start"

    # The lock reports "locked": byte 0 state, bytes 1:5 timestamp, 16-byte block.
    block = encrypt_ecb(LOCK_UUID[-16:].lower(), bytes([1, 0, 0, 0, 0]) + b"\x00" * 11)
    await coordinator._handle_state(None, bytearray(block))
    await asyncio.sleep(0)

    assert delays[-1] == BOLT_COMMAND_DISCONNECT_SECONDS
    assert delays[-1] < BOLT_COMMAND_TIMEOUT_SECONDS
    assert coordinator._current_command is None


@pytest.mark.asyncio
async def test_timeout_rereads_instead_of_reporting_the_old_state():
    """A lost confirmation must never republish the pre-command value.

    Observed live: the bolt locked, the link dropped before the notification, and the
    entity reported `unlocked` for a locked door. Re-read rather than guess.
    """
    client = FakeProxyClient()
    coordinator = make_coordinator(client)
    coordinator.async_refresh = AsyncMock()

    await coordinator.lock_unlock("lock")
    assert coordinator._current_command == "lock"

    # The safety-net timer fires with the command still in flight.
    await coordinator._disconnect(delay=0)

    coordinator.async_refresh.assert_awaited_once()
    assert coordinator._current_command is None


@pytest.mark.asyncio
async def test_completed_command_does_not_trigger_a_reread():
    """The notification already gave us the truth; a re-read would be a wasted connect."""
    client = FakeProxyClient()
    coordinator = make_coordinator(client)
    coordinator.async_refresh = AsyncMock()

    await coordinator.lock_unlock("lock")
    block = encrypt_ecb(LOCK_UUID[-16:].lower(), bytes([1, 0, 0, 0, 0]) + b"\x00" * 11)
    await coordinator._handle_state(None, bytearray(block))

    await coordinator._disconnect(delay=0)

    coordinator.async_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_plain_disconnect_outside_a_command_does_not_reread():
    """The poll path disconnects constantly; it must not recurse into a refresh."""
    client = FakeProxyClient()
    coordinator = make_coordinator(client)
    coordinator.async_refresh = AsyncMock()

    await coordinator._disconnect(delay=0)

    coordinator.async_refresh.assert_not_awaited()
    coordinator.async_update_listeners.assert_called()


# --------------------------------------------------------------------------------------
# The lock's connection lifetime.
#
# The tests above prove the declaration is sent, with the right payload, in the right
# order. They cannot prove that sending it is what keeps the link open, because that is a
# property of the lock's firmware. The tests below close that gap: they drive the real
# lock_unlock() against FakeBoltLink, which models the measured hardware contract (see its
# docstring), and assert on what the integration achieves rather than on the model itself.
# --------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_declaration_keeps_the_link_alive_through_a_slow_exchange():
    """The fix, end to end: a command outliving the lock's old deadline still works.

    A lock/unlock is a multi-step challenge/response, and on a contended proxy the
    round trips can easily push it past 6s. This is the case that used to be
    truncated mid-exchange with error=19 and leave the bolt unmoved.
    """
    client = FakeBoltLink()
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("lock")

    # Far longer than the exchange really needs, and well past the old deadline.
    client.advance(20.0)

    assert client.is_connected, "the lock must not have hung up mid-exchange"
    # The next step of the exchange must still be able to reach the lock.
    await coordinator._request_challenge(client)

    coordinator._disconnect_task.cancel()


@pytest.mark.asyncio
async def test_a_slow_exchange_still_publishes_the_new_state():
    """Surviving only matters because the confirmation then arrives and is used.

    The notification is delivered through the fake, so it requires the link and the
    subscription to still be alive. On a dropped link the lock sends nothing and the
    entity is left reporting a state the bolt may have already left.
    """
    client = FakeBoltLink()
    coordinator = make_coordinator(client)

    await coordinator.lock_unlock("unlock")
    client.advance(20.0)

    # The lock finally reports "locked": byte 0 state, bytes 1:5 timestamp.
    block = encrypt_ecb(LOCK_UUID[-16:].lower(), bytes([1, 0, 0, 0, 0]) + b"\x00" * 11)
    await client.deliver(YDBLE_LOCK_STATE_UUID, block)

    assert coordinator.data["state"] == 1
    assert coordinator._current_command is None

    coordinator._disconnect_task.cancel()


@pytest.mark.asyncio
async def test_without_the_declaration_the_exchange_breaks():
    """Guards the intent: shows the pre-fix behaviour actually failing.

    Suppressing just the declaration write leaves everything else identical, so this
    isolates it as the cause. Before the fix every command took this path.
    """
    client = FakeBoltLink()
    coordinator = make_coordinator(client)
    coordinator._send_connection_type = AsyncMock()  # pre-fix: never sent

    await coordinator.lock_unlock("lock")
    assert not client.declared

    client.advance(20.0)

    assert not client.is_connected, "the lock should have hung up"
    with pytest.raises(BleakError, match="error=19"):
        await coordinator._request_challenge(client)

    # And the confirmation can never arrive, which is how a command silently
    # "did nothing" while the bolt may in fact have moved.
    block = encrypt_ecb(LOCK_UUID[-16:].lower(), bytes([1, 0, 0, 0, 0]) + b"\x00" * 11)
    with pytest.raises(BleakError):
        await client.deliver(YDBLE_LOCK_STATE_UUID, block)
    assert coordinator.data["state"] is None

    coordinator._disconnect_task.cancel()
