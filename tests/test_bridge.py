"""Tests for local bridge URL helpers."""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "wyzeapi_bridge",
    Path(__file__).parents[1] / "custom_components" / "wyzeapi" / "bridge.py",
)
bridge = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bridge)


def test_stream_name_matches_wyze_bridge():
    assert bridge.stream_name("Front Door") == "front_door"
    assert bridge.stream_name("Side Yard") == "side_yard"
    assert bridge.stream_name("Sam's Room") == "sams_room"
    assert bridge.stream_name("", "D03F27983490") == "d03f27983490"


def test_frame_url():
    assert (
        bridge.frame_url("http://127.0.0.1:1984/", "side_yard")
        == "http://127.0.0.1:1984/api/frame.jpeg?src=side_yard"
    )


def test_playback_url():
    assert (
        bridge.playback_url("rtsp://127.0.0.1:8554/{name}", "front_door")
        == "rtsp://127.0.0.1:8554/front_door"
    )


def test_clean_bridge_url():
    assert bridge.clean_bridge_url("") == ""
    assert bridge.clean_bridge_url(None) == ""
    assert bridge.clean_bridge_url(" http://127.0.0.1:1984/ ") == "http://127.0.0.1:1984"
    with pytest.raises(ValueError):
        bridge.clean_bridge_url("rtsp://127.0.0.1:8554/front_door")


def test_clean_bridge_stream_url():
    assert bridge.clean_bridge_stream_url("  ") == ""
    assert (
        bridge.clean_bridge_stream_url("rtsp://127.0.0.1:8554/{name}")
        == "rtsp://127.0.0.1:8554/{name}"
    )
    with pytest.raises(ValueError):
        bridge.clean_bridge_stream_url("rtsp://127.0.0.1:8554/front_door")
    with pytest.raises(ValueError):
        bridge.clean_bridge_stream_url("not a url {name}")
