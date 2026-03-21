import os
import sys
import inspect
import asyncio

import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import jsonify

import app as app_module
import nostr_utils


def test_nostr_routes_are_async_functions():
    assert inspect.iscoroutinefunction(nostr_utils._fetch_profile)
    assert inspect.iscoroutinefunction(nostr_utils._validate_profile)
    assert inspect.iscoroutinefunction(nostr_utils._send_dm)


def test_fetch_profile_route_awaits_async_helper(monkeypatch):
    async def fake_fetch_profile():
        return jsonify({"status": "ok"})

    monkeypatch.setattr(nostr_utils, "fetch_profile", fake_fetch_profile)

    with app_module.app.test_request_context("/fetch-profile", method="POST", json={"pubkey": "abc"}):
        response = asyncio.run(nostr_utils._fetch_profile())

    assert response.get_json() == {"status": "ok"}


def test_validate_profile_route_awaits_async_helper(monkeypatch):
    async def fake_fetch_and_validate_profile(pubkey, required_domain):
        assert pubkey == "abc"
        assert required_domain == app_module.REQUIRED_DOMAIN
        return True

    monkeypatch.setattr(nostr_utils, "fetch_and_validate_profile", fake_fetch_and_validate_profile)

    with app_module.app.test_request_context("/validate-profile", method="POST", json={"pubkey": "abc"}):
        response = asyncio.run(nostr_utils._validate_profile())

    assert response.get_json() == {"status": "valid"}


def test_send_dm_route_awaits_async_helper(monkeypatch):
    calls = []

    async def fake_send_dm_async(to_pubkey, content, sender_privkey):
        calls.append((to_pubkey, content, sender_privkey))

    monkeypatch.setattr(nostr_utils, "_send_dm_async", fake_send_dm_async)

    payload = {
        "to_pubkey": "abc",
        "content": "hello",
        "sender_privkey": "priv",
    }
    with app_module.app.test_request_context("/send_dm", method="POST", json=payload):
        response = asyncio.run(nostr_utils._send_dm())

    assert response.get_json() == {"message": "DM sent successfully"}
    assert calls == [("abc", "hello", "priv")]


def test_fetch_profile_uses_exponential_backoff(monkeypatch):
    sleep_calls = []

    class EmptyPool:
        def has_events(self):
            return False

        def has_eose_notices(self):
            return False

    class DummyMgr:
        connection_statuses = {"r1": True}
        message_pool = EmptyPool()

        async def add_subscription_on_all_relays(self, *args, **kwargs):
            return None

    class TimeController:
        def __init__(self):
            self.current = 0.0

        def time(self):
            return self.current

    time_controller = TimeController()

    async def fake_sleep(delay):
        sleep_calls.append(delay)
        time_controller.current += delay

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def dummy_relay_manager():
        yield DummyMgr()

    monkeypatch.setattr(nostr_utils, "relay_manager", dummy_relay_manager)
    monkeypatch.setattr(nostr_utils, "get_cached_item", lambda pubkey: None)
    monkeypatch.setattr(nostr_utils, "nprofile_encode", lambda pubkey, relays: None)
    monkeypatch.setattr(nostr_utils.time, "time", time_controller.time)
    monkeypatch.setattr(nostr_utils.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(nostr_utils, "PROFILE_FETCH_TIMEOUT", 0.4)

    with app_module.app.test_request_context("/fetch-profile", method="POST", json={"pubkey": "abc"}):
        response, status_code = asyncio.run(nostr_utils.fetch_profile())

    assert status_code == 404
    assert response.get_json() == {"error": "Profile not found"}
    assert sleep_calls == pytest.approx([0.05, 0.1, 0.2, 0.05])
