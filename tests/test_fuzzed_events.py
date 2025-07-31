import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import nostr_utils
from app import app
from nostr_client import MessagePool, Event, EventKind

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


def test_fuzzed_events_skips_validation_for_allowed(monkeypatch):
    mgr = DummyMgr(True)
    ev = Event(public_key="aa", content="x", kind=EventKind.CALENDAR_EVENT)
    mgr.message_pool.add_event("fuzzed", ev)
    monkeypatch.setattr(nostr_utils, "initialize_client", lambda: mgr)

    called = False
    async def fake_validate(*args, **kwargs):
        nonlocal called
        called = True
        return False

    monkeypatch.setattr(nostr_utils, "fetch_and_validate_profile", fake_validate)
    monkeypatch.setattr(nostr_utils, "VALID_PUBKEYS", ["aa"])

    with app.test_client() as client:
        resp = client.get("/fuzzed_events")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["events"]) == 1
        assert data["events"][0]["pubkey"] == "aa"
        assert not called


def test_fuzzed_events_filters_invalid(monkeypatch):
    mgr = DummyMgr(True)
    ev = Event(public_key="bb", content="x", kind=EventKind.CALENDAR_EVENT)
    mgr.message_pool.add_event("fuzzed", ev)
    monkeypatch.setattr(nostr_utils, "initialize_client", lambda: mgr)

    calls = []
    async def fake_validate(pk, domain):
        calls.append(pk)
        return False

    monkeypatch.setattr(nostr_utils, "fetch_and_validate_profile", fake_validate)
    monkeypatch.setattr(nostr_utils, "VALID_PUBKEYS", [])

    with app.test_client() as client:
        resp = client.get("/fuzzed_events")
        assert resp.status_code == 200
        assert resp.get_json() == {"events": []}
        assert calls == ["bb"]
