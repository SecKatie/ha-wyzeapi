"""Tests for Wyze Agora/lake camera handling."""

from types import SimpleNamespace
from unittest.mock import Mock

from homeassistant.components.camera import CameraEntityFeature

from custom_components.wyzeapi.camera import WyzeCamera


def _camera(product_model: str) -> SimpleNamespace:
    return SimpleNamespace(
        mac="AA:BB:CC:DD:EE:FF",
        nickname="Test Cam",
        product_model=product_model,
        available=True,
        on=True,
        device_params={},
    )


def test_lake_camera_does_not_advertise_stream() -> None:
    entity = WyzeCamera(Mock(), _camera("ME_WCO3"))
    assert entity._is_lake is True
    assert not (entity.supported_features & CameraEntityFeature.STREAM)


def test_non_lake_camera_advertises_stream() -> None:
    entity = WyzeCamera(Mock(), _camera("WYZECP1_JEF"))
    assert entity._is_lake is False
    assert entity.supported_features & CameraEntityFeature.STREAM
