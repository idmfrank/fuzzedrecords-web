import os
import sys
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import nostr_utils
import app

class DummyMgr:
    def __init__(self):
        self.published = False
        self.prepared = False
    def add_relay(self, url):
        pass
    async def prepare_relays(self):
        self.prepared = True
    async def publish_event(self, ev):
        self.published = True
    async def close_connections(self):
        pass

async def _false(*args, **kwargs):
    return False

async def _true(*args, **kwargs):
    return True


def _basic_event_data():
    return {
        "pubkey": "00" * 32,
        "sig": "sig",
        "id": "11" * 32,
        "kind": 1,
        "created_at": 0,
        "tags": [],
        "content": "x",
    }


def test_create_event_requires_valid_admin(monkeypatch):
    mgr = DummyMgr()
    monkeypatch.setattr(nostr_utils, "initialize_client", lambda: mgr)
    monkeypatch.setattr(nostr_utils.Event, "verify", lambda self: True)
    class DummyEK(int):
        SET_METADATA = 0
        TEXT_NOTE = 1
        ENCRYPTED_DM = 4
        CALENDAR_EVENT = 31922  # NIP-52 calendar events
    monkeypatch.setattr(nostr_utils, "EventKind", DummyEK)

    # invalid admin -> 403
    monkeypatch.setattr(nostr_utils, "fetch_and_validate_profile", _false)
    with app.app.test_client() as client:
        resp = client.post("/create_event", json=_basic_event_data())
        assert resp.status_code == 403
        assert not mgr.published
        assert not mgr.prepared

    # valid admin -> 200
    monkeypatch.setattr(nostr_utils, "fetch_and_validate_profile", _true)
    with app.app.test_client() as client:
        data = _basic_event_data()
        resp = client.post("/create_event", json=data)
        assert resp.status_code == 200
        assert mgr.published
        assert mgr.prepared
        resp_data = resp.get_json()
        assert resp_data["id"] == data["id"]

