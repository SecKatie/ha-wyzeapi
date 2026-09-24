"""Pytest configuration and fixtures."""

import sys
from unittest.mock import MagicMock

# Mock turbojpeg before any imports from homeassistant
sys.modules["turbojpeg"] = MagicMock()
