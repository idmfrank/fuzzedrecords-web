import os
import sys
import inspect
import asyncio

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
