"""Exercise real HA config flows with fake Wyze authentication."""

import asyncio
import inspect
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from homeassistant import config_entries, loader
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from wyzeapy import exceptions

from custom_components.wyzeapi import config_flow
from custom_components.wyzeapi.const import (
    ACCESS_TOKEN,
    API_KEY,
    DOMAIN,
    KEY_ID,
    REFRESH_TIME,
    REFRESH_TOKEN,
)


def credentials(username="account@example.com", password="password"):
    return {
        CONF_USERNAME: username,
        CONF_PASSWORD: password,
        KEY_ID: f"key-id:{username}",
        API_KEY: f"api-key:{username}",
    }


def tokens(username):
    return {
        ACCESS_TOKEN: f"access:{username}",
        REFRESH_TOKEN: f"refresh:{username}",
        REFRESH_TIME: 123.0,
    }


class FakeWyzeAuth:
    """Retain an account-specific challenge across invalid MFA codes."""

    def __init__(self):
        self.credentials = None
        self.challenge = None
        self.codes = []

    async def login(self, username, password, key_id, api_key):
        self.credentials = (username, password, key_id, api_key)
        await asyncio.sleep(0)
        if password == "invalid":
            raise exceptions.AccessTokenError
        if password == "offline":
            raise config_flow.CannotConnect
        if password == "mfa":
            self.challenge = object()
            raise exceptions.TwoFactorAuthenticationEnabled

    async def login_with_2fa(self, code):
        assert self.challenge is not None
        self.codes.append(code)
        if code != f"valid:{self.credentials[0]}":
            raise exceptions.LoginError
        return SimpleNamespace(**tokens(self.credentials[0]))


@pytest_asyncio.fixture
async def env(tmp_path, monkeypatch):
    hass = HomeAssistant(str(tmp_path))
    loader.async_setup(hass)
    # Register the real integration manifest and already imported flow, without
    # installing dependencies or starting platforms/cloud access during tests.
    path = Path(config_flow.__file__).parent
    hass.data[loader.DATA_INTEGRATIONS][DOMAIN] = loader.Integration(
        hass,
        "custom_components.wyzeapi",
        path,
        json.loads((path / "manifest.json").read_text()),
    )
    hass.data[loader.DATA_COMPONENTS][f"{DOMAIN}.config_flow"] = config_flow
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    setup = AsyncMock(return_value=True)
    reload = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_setup", setup)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)
    clients = []

    async def create():
        client = FakeWyzeAuth()
        clients.append(client)
        return client

    monkeypatch.setattr(config_flow.Wyzeapy, "create", create)
    yield SimpleNamespace(hass=hass, clients=clients, setup=setup, reload=reload)
    await hass.async_block_till_done()
    await hass.async_stop()


def add_entry(env, username, *, domain=DOMAIN, **data):
    """Register real entries without running integration setup, as in smoke tests."""
    kwargs = dict(
        domain=domain,
        title=username,
        version=1,
        minor_version=1,
        data={**credentials(username), **data},
        options={"unrelated_option": True},
        source=config_entries.SOURCE_USER,
        unique_id=None,
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )
    entry = config_entries.ConfigEntry(
        **{
            key: value
            for key, value in kwargs.items()
            if key in inspect.signature(config_entries.ConfigEntry).parameters
        }
    )
    env.hass.config_entries._entries[entry.entry_id] = entry
    return entry


async def start(env, source=config_entries.SOURCE_USER, **context):
    return await env.hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source, **context}
    )


async def authenticate(env, result, data, *, mfa=False):
    result = await env.hass.config_entries.flow.async_configure(result["flow_id"], data)
    if mfa:
        assert result["step_id"] == "2fa"
        result = await env.hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: f"valid:{data[CONF_USERNAME]}"}
        )
    await env.hass.async_block_till_done()
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["user", "import"])
@pytest.mark.parametrize("mfa", [False, True])
async def test_new_entry(env, source, mfa):
    data = credentials(password="mfa" if mfa else "password")
    result = await authenticate(env, await start(env, source), data, mfa=mfa)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    expected = {**data, **(tokens(data[CONF_USERNAME]) if mfa else {})}
    assert dict(result["result"].data) == expected
    assert env.hass.config_entries.async_entries(DOMAIN) == [result["result"]]
    env.setup.assert_awaited_once_with(result["result"].entry_id)
    env.reload.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mfa", [False, True])
async def test_parallel_flows_keep_credentials_and_challenges_independent(env, mfa):
    first, second = await asyncio.gather(start(env), start(env))
    flow_a = env.hass.config_entries.flow._progress[first["flow_id"]]
    flow_b = env.hass.config_entries.flow._progress[second["flow_id"]]
    assert flow_a.user_params is not flow_b.user_params
    data_a = credentials("a@example.com", "mfa" if mfa else "password")
    data_b = credentials("b@example.com", "mfa" if mfa else "password")
    first, second = await asyncio.gather(
        authenticate(env, first, data_a), authenticate(env, second, data_b)
    )
    assert flow_a.client is not flow_b.client
    assert flow_a.client.credentials == tuple(data_a.values())
    assert flow_b.client.credentials == tuple(data_b.values())
    assert flow_a.user_params == data_a
    assert flow_b.user_params == data_b
    if mfa:
        challenge = flow_a.client.challenge
        first = await env.hass.config_entries.flow.async_configure(
            first["flow_id"], {CONF_ACCESS_TOKEN: "valid:b@example.com"}
        )
        assert first["errors"] == {"base": "invalid_auth"}
        assert flow_a.client.challenge is challenge
        second = await env.hass.config_entries.flow.async_configure(
            second["flow_id"], {CONF_ACCESS_TOKEN: "valid:b@example.com"}
        )
        first = await env.hass.config_entries.flow.async_configure(
            first["flow_id"], {CONF_ACCESS_TOKEN: "valid:a@example.com"}
        )
        assert second["type"] is FlowResultType.CREATE_ENTRY
        assert dict(second["result"].data) == {**data_b, **tokens("b@example.com")}
        assert first["reason"] == "already_configured"
    else:
        assert {first["type"], second["type"]} == {
            FlowResultType.CREATE_ENTRY,
            FlowResultType.ABORT,
        }
    assert len(env.hass.config_entries.async_entries(DOMAIN)) == 1
    env.reload.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mfa", [False, True])
async def test_reauth_targets_b_when_a_is_first_and_preserves_other_data(env, mfa):
    first = add_entry(env, "a@example.com", unrelated="keep A", **tokens("old A"))
    target = add_entry(
        env, "b@example.com", unrelated={"nested": "keep B"}, **tokens("old B")
    )
    before_a = dict(first.data)
    result = await start(env, "reauth", entry_id=target.entry_id)
    data = credentials("b@example.com", "mfa" if mfa else "updated")
    result = await authenticate(env, result, data, mfa=mfa)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert dict(first.data) == before_a
    assert dict(target.data) == {
        **credentials("b@example.com"),
        "unrelated": {"nested": "keep B"},
        **data,
        **(tokens("b@example.com") if mfa else {}),
    }
    assert target.options == {"unrelated_option": True}
    env.reload.assert_awaited_once_with(target.entry_id)
    env.setup.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("target_kind", ["empty", "missing", "other_domain"])
async def test_missing_reauth_target_never_writes(env, monkeypatch, target_kind):
    first = add_entry(env, "a@example.com")
    other = add_entry(env, "b@example.com", domain="other")
    entry_id = {"empty": None, "missing": "missing", "other_domain": other.entry_id}
    update = Mock(wraps=env.hass.config_entries.async_update_entry)
    monkeypatch.setattr(env.hass.config_entries, "async_update_entry", update)
    result = await start(env, "reauth", entry_id=entry_id[target_kind])
    assert result["reason"] == "reauth_entry_missing"
    assert first.data == credentials("a@example.com")
    assert other.data == credentials("b@example.com")
    update.assert_not_called()
    env.reload.assert_not_called()
    env.setup.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mfa", [False, True])
async def test_reauth_target_removed_before_completion_never_writes(
    env, monkeypatch, mfa
):
    first = add_entry(env, "a@example.com")
    target = add_entry(env, "b@example.com")
    result = await start(env, "reauth", entry_id=target.entry_id)
    data = credentials("b@example.com", "mfa" if mfa else "new")
    if mfa:
        result = await authenticate(env, result, data)
        assert result["step_id"] == "2fa"
    del env.hass.config_entries._entries[target.entry_id]
    update = Mock(wraps=env.hass.config_entries.async_update_entry)
    monkeypatch.setattr(env.hass.config_entries, "async_update_entry", update)
    submission = {CONF_ACCESS_TOKEN: "valid:b@example.com"} if mfa else data
    result = await env.hass.config_entries.flow.async_configure(
        result["flow_id"], submission
    )
    assert result["reason"] == "reauth_entry_missing"
    assert first.data == credentials("a@example.com")
    assert target.data == credentials("b@example.com")
    update.assert_not_called()
    env.reload.assert_not_called()
    env.setup.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mfa", [False, True])
@pytest.mark.parametrize(
    "username", ["a@example.com", "B@example.com", "b@example.com "]
)
async def test_reauth_requires_exact_stored_username(env, monkeypatch, mfa, username):
    first = add_entry(env, "a@example.com")
    target = add_entry(env, "b@example.com")
    result = await start(env, "reauth", entry_id=target.entry_id)
    update = Mock(wraps=env.hass.config_entries.async_update_entry)
    monkeypatch.setattr(env.hass.config_entries, "async_update_entry", update)
    result = await authenticate(
        env, result, credentials(username, "mfa" if mfa else "new"), mfa=mfa
    )
    assert result["reason"] == "wrong_account"
    assert first.data == credentials("a@example.com")
    assert target.data == credentials("b@example.com")
    update.assert_not_called()
    env.reload.assert_not_called()
    env.setup.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["user", "import"])
@pytest.mark.parametrize("username", ["a@example.com", "b@example.com"])
@pytest.mark.parametrize("mfa", [False, True])
async def test_new_flow_does_not_overwrite_existing_account(
    env, monkeypatch, source, username, mfa
):
    entry = add_entry(env, "a@example.com", unrelated="keep")
    before = dict(entry.data)
    result = await start(env, source)
    update = Mock(wraps=env.hass.config_entries.async_update_entry)
    monkeypatch.setattr(env.hass.config_entries, "async_update_entry", update)
    result = await authenticate(
        env, result, credentials(username, "mfa" if mfa else "new"), mfa=mfa
    )
    assert result["reason"] == "already_configured"
    assert dict(entry.data) == before
    assert env.hass.config_entries.async_entries(DOMAIN) == [entry]
    update.assert_not_called()
    env.reload.assert_not_called()
    env.setup.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password,error", [("invalid", "invalid_auth"), ("offline", "cannot_connect")]
)
async def test_password_errors_allow_retry(env, password, error):
    result = await start(env)
    result = await authenticate(env, result, credentials(password=password))
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}
    data = credentials("retry@example.com")
    result = await authenticate(env, result, data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == data
    assert len(env.clients) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mfa", [False, True])
@pytest.mark.parametrize("existing", [False, True])
async def test_import_accepts_initial_yaml_data(env, existing, mfa):
    entry = add_entry(env, "existing@example.com") if existing else None
    data = credentials(password="mfa" if mfa else "password")
    result = await env.hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=data
    )
    if mfa:
        assert result["step_id"] == "2fa"
        result = await env.hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: f"valid:{data[CONF_USERNAME]}"}
        )
    if existing:
        assert result["reason"] == "already_configured"
        assert entry.data == credentials("existing@example.com")
    else:
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].data == {
            **data,
            **(tokens(data[CONF_USERNAME]) if mfa else {}),
        }
