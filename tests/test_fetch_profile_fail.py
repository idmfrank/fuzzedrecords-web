import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import nostr_utils
from app import app
from contextlib import asynccontextmanager

class DummyMgr:
    connection_statuses = {"r1": False, "r2": False}
    async def add_subscription_on_all_relays(self, *args, **kwargs):
        pass
    message_pool = type("MP", (), {"has_events": lambda self: False, "has_eose_notices": lambda self: False})()

def test_fetch_profile_returns_503(monkeypatch):
    @asynccontextmanager
    async def dummy_cm():
        yield DummyMgr()
    monkeypatch.setattr(nostr_utils, "relay_manager", dummy_cm)
    with app.test_client() as client:
        resp = client.post("/fetch-profile", json={"pubkey": "abc"})
        assert resp.status_code == 503
        assert resp.get_json()["error"] == "Unable to connect to Nostr relays"
