"""Tests for Wyze Agora/lake camera handling."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest

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


def _camera_with_thumb(url: str | None) -> SimpleNamespace:
    cam = _camera("ME_WCO3")
    cam.device_params = {"camera_thumbnails": {"thumbnails_url": url}} if url else {}
    return cam


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def read(self) -> bytes:
        return self._body


@pytest.mark.asyncio
async def test_camera_image_returns_thumbnail_bytes() -> None:
    entity = WyzeCamera(Mock(), _camera_with_thumb("https://thumb/x.jpg"))
    entity.hass = Mock()
    session = Mock()
    session.get = Mock(return_value=_FakeResponse(200, b"JPEGBYTES"))
    with patch(
        "custom_components.wyzeapi.camera.async_get_clientsession",
        return_value=session,
    ):
        result = await entity.async_camera_image()
    assert result == b"JPEGBYTES"
    session.get.assert_called_once_with("https://thumb/x.jpg")


@pytest.mark.asyncio
async def test_camera_image_none_when_no_thumbnail() -> None:
    entity = WyzeCamera(Mock(), _camera_with_thumb(None))
    entity.hass = Mock()
    assert await entity.async_camera_image() is None


@pytest.mark.asyncio
async def test_camera_image_none_on_http_error() -> None:
    entity = WyzeCamera(Mock(), _camera_with_thumb("https://thumb/x.jpg"))
    entity.hass = Mock()
    session = Mock()
    session.get = Mock(return_value=_FakeResponse(403, b""))
    with patch(
        "custom_components.wyzeapi.camera.async_get_clientsession",
        return_value=session,
    ):
        assert await entity.async_camera_image() is None
