"""Tests for Wyze Agora/lake camera handling."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

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


@patch("custom_components.wyzeapi.camera.CameraEntityFeature")
def test_lake_camera_does_not_advertise_stream(mock_feature_class) -> None:
    # Mock CameraEntityFeature: STREAM=1, calling with 0 returns 0
    mock_feature_class.STREAM = 1
    mock_feature_class.side_effect = lambda x: x  # Identity function
    mock_feature_class.return_value = 0  # When called, return 0
    entity = WyzeCamera(Mock(), _camera("ME_WCO3"))
    assert entity._is_lake is True
    assert not (entity.supported_features & 1)


@patch("custom_components.wyzeapi.camera.CameraEntityFeature")
def test_non_lake_camera_advertises_stream(mock_feature_class) -> None:
    # Mock CameraEntityFeature: STREAM=1
    mock_feature_class.STREAM = 1
    mock_feature_class.return_value = 1
    entity = WyzeCamera(Mock(), _camera("WYZECP1_JEF"))
    assert entity._is_lake is False
    assert entity.supported_features & 1
