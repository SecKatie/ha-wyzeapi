"""Tests for the Wyze Lock Bolt battery block decoder.

The Bolt's 0x2A19 characteristic is not a standard one-byte BLE Battery Level. It
returns a 16-byte AES-128-ECB block encrypted with the same key used for the lock
state characteristic. Layout of the decrypted block, per the Wyze app's own decode
(``C21643f.java`` battery callback plus ``C21552t.m67888k``):

    byte 0      battery percentage, valid range 1..100
    bytes 11:16 ASCII marker "loock"

These tests build blocks with the real cipher and assert the decoder recovers the
expected values, so they fail if the layout or validation is ever broken.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
import pytest

from custom_components.wyzeapi.ydble_utils import encrypt_ecb, parse_battery_block

LOCK_UUID = "YD_BT1.b38ae5ebd9864864273db2c08fab2c28"

# 16 chars, matching the lock UUID's trailing 16 used as the AES key.
KEY = "273db2c08fab2c28"


def _block(percent: int, marker: bytes = b"loock", pad: bytes = b"\x00" * 6) -> bytes:
    """Build a plaintext status block, then encrypt it the way the lock would."""
    plaintext = bytes([percent]) + b"\x00" * 4 + pad[:6] + marker
    assert len(plaintext) == 16, f"block must be one AES block, got {len(plaintext)}"
    return encrypt_ecb(KEY, plaintext)


def test_decodes_reported_percentage():
    """98% is what the Wyze app showed for this lock, so use it as the worked example."""
    assert parse_battery_block(KEY, _block(98)) == 98


def test_decodes_boundary_values():
    assert parse_battery_block(KEY, _block(1)) == 1
    assert parse_battery_block(KEY, _block(100)) == 100


def test_rejects_zero_and_out_of_range():
    """The app treats 0 and >100 as invalid rather than reporting a bogus level."""
    assert parse_battery_block(KEY, _block(0)) is None
    assert parse_battery_block(KEY, _block(101)) is None
    assert parse_battery_block(KEY, _block(255)) is None


def test_rejects_wrong_marker():
    """A wrong key decrypts to noise; the marker is what catches it."""
    assert parse_battery_block(KEY, _block(50, marker=b"xxxxx")) is None


def test_rejects_wrong_key():
    """Decrypting with a different key must not yield a plausible percentage."""
    other = "ffffffffffffffff"
    assert parse_battery_block(other, _block(98)) is None


def test_rejects_short_block():
    """A standard one-byte Battery Level read must not be misread as a status block."""
    assert parse_battery_block(KEY, b"\x62") is None


def test_ignores_padding_contents():
    """Only byte 0 and the marker are load-bearing; padding must not affect decoding."""
    assert parse_battery_block(KEY, _block(77, pad=b"\x01\x02\x03\x04\x05\x06")) == 77


# --------------------------------------------------------------------------------------
# The rest of the change: where the reading is stored, and what it must not disturb.
# --------------------------------------------------------------------------------------


def make_coordinator():
    lock = MagicMock()
    lock.mac = LOCK_UUID
    lock.nickname = "Test Bolt"

    with patch("homeassistant.helpers.frame.report_usage"):
        from custom_components.wyzeapi.coordinator import WyzeLockBoltCoordinator

        coordinator = WyzeLockBoltCoordinator(MagicMock(), MagicMock(), lock)

    coordinator.async_update_listeners = MagicMock()
    return coordinator


def test_ble_unique_id_cannot_collide_with_the_cloud_sensor():
    """The new entity must not adopt or clash with the cloud sensor's registry key.

    Guards the claim that this change needs no registry migration. The two schemes are
    unrelated: the cloud sensor keys on the nickname, this one on the MAC.
    """
    from custom_components.wyzeapi.sensor import (
        WyzeLockBoltBatterySensor,
        WyzeLockBatterySensor,
    )

    lock = MagicMock()
    lock.mac = LOCK_UUID
    lock.nickname = "Test Bolt"

    coordinator = make_coordinator()
    ble_id = WyzeLockBoltBatterySensor(coordinator).unique_id

    cloud_ids = {
        WyzeLockBatterySensor(lock, WyzeLockBatterySensor.LOCK_BATTERY).unique_id,
        WyzeLockBatterySensor(lock, WyzeLockBatterySensor.KEYPAD_BATTERY).unique_id,
    }

    assert ble_id not in cloud_ids
    assert ble_id == f"{LOCK_UUID}.ble_battery"


def test_ble_sensor_attaches_to_the_existing_lock_device():
    """A mismatched identifier would create a second device for the same lock."""
    from custom_components.wyzeapi.lock import WyzeLockBolt
    from custom_components.wyzeapi.sensor import WyzeLockBoltBatterySensor

    coordinator = make_coordinator()
    coordinator._mac = "28:68:47:E9:D0:7B"
    coordinator._lock.raw_dict = {"hardware_info": {"sn": "SN123"}}

    sensor_ids = WyzeLockBoltBatterySensor(coordinator).device_info["identifiers"]
    lock_ids = WyzeLockBolt(coordinator).device_info["identifiers"]

    assert sensor_ids == lock_ids


@pytest.mark.asyncio
async def test_state_notification_does_not_blank_the_battery():
    """Lock and unlock notifications carry no battery, so the last value must persist.

    Without the carry-forward the sensor drops to unknown on every command.
    """
    coordinator = make_coordinator()
    coordinator.data = {"state": 0, "timestamp": None, "battery": 98}

    block = encrypt_ecb(LOCK_UUID[-16:].lower(), bytes([1, 0, 0, 0, 0]) + b"\x00" * 11)
    await coordinator._handle_state(None, bytearray(block))

    assert coordinator.data["state"] == 1, "the new state must still be applied"
    assert coordinator.data["battery"] == 98


@pytest.mark.asyncio
async def test_a_failed_battery_read_keeps_the_previous_value():
    """A flaky battery read must never take the lock entity down with it."""
    coordinator = make_coordinator()
    coordinator.data = {"state": 1, "timestamp": None, "battery": 98}

    client = MagicMock()
    client.read_gatt_char = AsyncMock(side_effect=BleakError("read failed"))

    assert await coordinator._read_battery(client) == 98


@pytest.mark.asyncio
async def test_an_undecodable_battery_block_keeps_the_previous_value():
    """A block that fails the marker check must not publish a garbage percentage."""
    coordinator = make_coordinator()
    coordinator.data = {"state": 1, "timestamp": None, "battery": 98}

    client = MagicMock()
    client.read_gatt_char = AsyncMock(return_value=bytearray(b"\x00" * 16))

    assert await coordinator._read_battery(client) == 98
