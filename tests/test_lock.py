"""Tests for the WyzeLock entity's device-type gate."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from wyzeapy.services.lock_service import IOT3_LOCK_PRODUCT_MODELS
from wyzeapy.types import DeviceTypes

from custom_components.wyzeapi.lock import WyzeLock


def test_accepts_ford_yunding_lock() -> None:
    """Regular Ford/Yunding locks report DeviceTypes.LOCK and must still work."""
    lock = SimpleNamespace(type=DeviceTypes.LOCK, product_model="YD_BT1")

    WyzeLock(MagicMock(), lock)


@pytest.mark.parametrize("product_model", sorted(IOT3_LOCK_PRODUCT_MODELS))
def test_accepts_iot3_lock_despite_unknown_device_type(product_model: str) -> None:
    """IoT3 locks (e.g. the Palm Lock) report product_type "Common", which maps
    to DeviceTypes.UNKNOWN, not DeviceTypes.LOCK. They must still be accepted
    based on their product_model (#see companion wyzeapy PR)."""
    lock = SimpleNamespace(type=DeviceTypes.UNKNOWN, product_model=product_model)

    WyzeLock(MagicMock(), lock)


def test_rejects_unsupported_device() -> None:
    """A device that is neither a known lock type nor an IoT3 model must still
    be rejected, so this entity is never created for the wrong device."""
    lock = SimpleNamespace(type=DeviceTypes.UNKNOWN, product_model="SOME_OTHER_MODEL")

    with pytest.raises(AttributeError):
        WyzeLock(MagicMock(), lock)
