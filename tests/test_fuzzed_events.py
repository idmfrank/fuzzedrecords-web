import os, sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import nostr_utils
from app import app
from nostr_client import MessagePool, Event, EventKind

class DummyMgr:
    def __init__(self, status=True):
        self.added = []
        self.prepared = False
        self.subscribed = False
        self.closed = False
        self._status = status
        self.message_pool = MessagePool()

    def add_relay(self, url):
        self.added.append(url)

    async def prepare_relays(self):
        self.prepared = True

    async def add_subscription_on_all_relays(self, sub_id, filt):
        self.subscribed = True
        self.sub_id = sub_id
        self.filt = filt

    async def close_connections(self):
        self.closed = True

    @property
    def connection_statuses(self):
        return {self.added[0] if self.added else "r": self._status}


def test_fuzzed_events_success(monkeypatch, tmp_path):
    """Should use default relay when no good-relays file is present."""
    monkeypatch.chdir(tmp_path)
    mgr = DummyMgr(True)
    monkeypatch.setattr(nostr_utils, "RelayManager", lambda timeout=0: mgr)
    with app.test_client() as client:
        resp = client.get("/fuzzed_events")
        assert resp.status_code == 200
        assert resp.get_json() == {"events": []}
    assert mgr.added == [nostr_utils.EVENTS_RELAY]
    assert mgr.prepared
    assert mgr.subscribed
    assert mgr.closed


def test_fuzzed_events_returns_events(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    mgr = DummyMgr(True)
    ev = Event(public_key=nostr_utils.EVENTS_PUBKEY_HEX, content="x", kind=EventKind.CALENDAR_EVENT)
    mgr.message_pool.add_event("fuzzed", ev)
    monkeypatch.setattr(nostr_utils, "RelayManager", lambda timeout=0: mgr)
    with app.test_client() as client:
        resp = client.get("/fuzzed_events")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["events"]) == 1
        assert data["events"][0]["content"] == "x"


def test_fuzzed_events_returns_503(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    mgr = DummyMgr(False)
    monkeypatch.setattr(nostr_utils, "RelayManager", lambda timeout=0: mgr)
    with app.test_client() as client:
        resp = client.get("/fuzzed_events")
        assert resp.status_code == 503


def test_fuzzed_events_uses_good_relays(monkeypatch, tmp_path):
    """Relays should be loaded from good-relays.txt when available."""
    monkeypatch.chdir(tmp_path)
    good_file = tmp_path / "good-relays.txt"
    good_file.write_text("wss://a.com\nwss://b.com\n")
    mgr = DummyMgr(True)
    monkeypatch.setattr(nostr_utils, "RelayManager", lambda timeout=0: mgr)
    with app.test_client() as client:
        resp = client.get("/fuzzed_events")
        assert resp.status_code == 200
    assert mgr.added == ["wss://a.com", "wss://b.com"]
