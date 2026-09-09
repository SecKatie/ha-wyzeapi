"""Warm wyzeapy's cached SSL context off the event loop.

``wyzeapy.wyze_auth_lib.get_ssl_context`` builds an ``ssl.SSLContext`` by
reading three certificate bundles from disk: the system trust store via
``ssl.create_default_context()``, then certifi's bundle and Wyze's own CA
bundle. That is blocking I/O, and every request path reaches it from
synchronous code inside ``_create_client_session``.

The function is ``@cache``-decorated, so the disk read happens exactly once per
process -- but that once lands on Home Assistant's event loop during login,
which trips the blocking-call detector:

    Detected blocking call to load_verify_locations ... inside the event loop
    by custom integration 'wyzeapi'

Calling this helper before any login populates that cache from a worker thread,
so the synchronous callers afterwards get the memoized context for free.
"""

from typing import TYPE_CHECKING

from wyzeapy.wyze_auth_lib import get_ssl_context

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def async_warm_ssl_context(hass: "HomeAssistant") -> None:
    """Populate wyzeapy's cached SSL context in an executor thread."""
    await hass.async_add_executor_job(get_ssl_context)
