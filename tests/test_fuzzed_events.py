import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import nostr_utils
from app import app
from nostr_client import MessagePool

class DummyMgr:
    def __init__(self, status=True):
        self.prepared = False
        self.subscribed = False
        self.closed = False
        self._status = status
        self.message_pool = MessagePool()
    async def prepare_relays(self):
        self.prepared = True
    async def add_subscription_on_all_relays(self, sub_id, filt):
        self.subscribed = True
    async def close_connections(self):
        self.closed = True
    @property
    def connection_statuses(self):
        return {"r1": self._status}


def test_fuzzed_events_success(monkeypatch):
    mgr = DummyMgr(True)
    monkeypatch.setattr(nostr_utils, "initialize_client", lambda: mgr)
    monkeypatch.setattr(nostr_utils, "fetch_and_validate_profile", lambda *a, **k: True)
    with app.test_client() as client:
        resp = client.get("/fuzzed_events")
        assert resp.status_code == 200
        assert resp.get_json() == {"events": []}
        assert mgr.prepared
        assert mgr.subscribed
        assert mgr.closed


def test_fuzzed_events_returns_503(monkeypatch):
    mgr = DummyMgr(False)
    monkeypatch.setattr(nostr_utils, "initialize_client", lambda: mgr)
    with app.test_client() as client:
        resp = client.get("/fuzzed_events")
        assert resp.status_code == 503
        assert "Unable to connect" in resp.get_json()["error"]
