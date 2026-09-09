"""The SSL context must be built off the event loop, not on it.

wyzeapy builds its SSLContext by reading three CA bundles from disk (the system
trust store, certifi's bundle, and Wyze's own CA). That is blocking I/O, and
``_create_client_session`` reaches it from synchronous code. Doing it inline
stalls Home Assistant's event loop during login and trips the blocking-call
detector:

    Detected blocking call to load_verify_locations ... inside the event loop
    by custom integration 'wyzeapi'

These tests fail if the warm-up is removed, stops using an executor, or if
wyzeapy's memoization changes so that one warm-up no longer covers later calls.

The helper is loaded straight from its file rather than as part of the
``custom_components.wyzeapi`` package, so these tests run without Home
Assistant installed.
"""

import asyncio
import importlib.util
from pathlib import Path

import pytest
from wyzeapy.wyze_auth_lib import get_ssl_context

_HELPER = Path(__file__).resolve().parents[1] / "custom_components" / "wyzeapi" / "ssl_warmup.py"


def _load_helper():
    spec = importlib.util.spec_from_file_location("wyzeapi_ssl_warmup", _HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_hass():
    """Records what gets handed to the executor, and runs it off the loop."""

    class FakeHass:
        def __init__(self):
            self.executor_calls = []

        async def async_add_executor_job(self, func, *args):
            self.executor_calls.append(func)
            return await asyncio.to_thread(func, *args)

    return FakeHass()


def test_get_ssl_context_is_memoized():
    """One warm-up must cover every later synchronous caller."""
    assert hasattr(get_ssl_context, "cache_clear"), (
        "wyzeapy.get_ssl_context is no longer memoized; warming it once no "
        "longer prevents blocking disk reads on the event loop"
    )
    get_ssl_context.cache_clear()
    assert get_ssl_context() is get_ssl_context()


def test_warmup_dispatches_to_an_executor(fake_hass):
    get_ssl_context.cache_clear()
    asyncio.run(_load_helper().async_warm_ssl_context(fake_hass))
    assert fake_hass.executor_calls == [get_ssl_context], (
        "warm-up did not hand get_ssl_context to an executor"
    )


def test_warmup_populates_the_cache(fake_hass):
    """After warm-up, _create_client_session gets the context with no disk read."""
    get_ssl_context.cache_clear()
    assert get_ssl_context.cache_info().currsize == 0
    asyncio.run(_load_helper().async_warm_ssl_context(fake_hass))
    assert get_ssl_context.cache_info().currsize == 1, (
        "cache not populated; session creation would still read from disk"
    )
