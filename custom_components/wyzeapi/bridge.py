"""Optional local bridge URLs for Wyze cameras.

Stream names follow docker-wyze-bridge: the nickname, spaces turned into
underscores, then anything that is not a letter, number, underscore, or
hyphen removed, then lowercased.
"""

from __future__ import annotations

import re
from urllib.parse import quote, urlparse

_NAME_CLEAN = re.compile(r"[^\w\-]+", re.ASCII)
_FRAME_PATH = "/api/frame.jpeg"


def stream_name(nickname: str, mac: str = "") -> str:
    """Return the bridge stream name for a camera."""
    name = (nickname or "").strip() or (mac or "")
    name = name.replace(" ", "_")
    name = _NAME_CLEAN.sub("", name)
    return name.lower()


def frame_url(bridge_url: str, name: str) -> str:
    """Return the go2rtc still URL for a stream name."""
    return f"{bridge_url.rstrip('/')}{_FRAME_PATH}?src={quote(name)}"


def playback_url(template: str, name: str) -> str:
    """Fill {name} in a stream URL template."""
    return template.replace("{name}", name)


def clean_bridge_url(value: object) -> str:
    """Accept a blank value or an http(s) bridge API URL."""
    text = "" if value is None else str(value).strip().rstrip("/")
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter an http(s) URL, or leave this blank")
    return text


def clean_bridge_stream_url(value: object) -> str:
    """Accept a blank value or a stream template containing {name}."""
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    if "{name}" not in text:
        raise ValueError("Include {name} where the camera name goes")
    parsed = urlparse(text.replace("{name}", "camera"))
    if parsed.scheme not in {"rtsp", "rtsps", "http", "https"} or not parsed.netloc:
        raise ValueError("Enter an rtsp or http URL that includes {name}")
    return text
