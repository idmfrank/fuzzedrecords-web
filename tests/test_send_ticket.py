import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import ticket_utils
import app
import nostr_client


class DummyEvent:
    def __init__(self):
        self.id = "dummy_event_id"
    def sign(self, priv):
        self.priv = priv


class DummyRelayManager:
    def __init__(self):
        self.publish_count = 0
        self.last_event = None
        self.prepared = False
    def add_relay(self, url):
        self.last_relay = url
    async def prepare_relays(self):
        self.prepared = True
    async def publish_event(self, ev):
        self.publish_count += 1
        self.last_event = ev
    async def close_connections(self):
        self.closed = True


def test_send_ticket_as_dm(monkeypatch):
    mgr = DummyRelayManager()
    monkeypatch.setattr(ticket_utils, "initialize_client", lambda: mgr)
    monkeypatch.setattr(app, "initialize_client", lambda: mgr)
    monkeypatch.setattr(app, "RelayManager", DummyRelayManager)

    called = {}
    def fake_encrypt(priv, pub, text):
        called["args"] = (priv, pub, text)
        return "cipher"

    monkeypatch.setattr(nostr_client, "nip17_encrypt", fake_encrypt)

    ev_id = ticket_utils.send_ticket_as_dm(
        "Concert", "recip_pubkey", "11" * 32, timestamp=123
    )

    assert mgr.publish_count == 1
    assert mgr.prepared
    assert mgr.last_event.kind == nostr_client.EventKind.EPHEMERAL_DM
    assert called["args"][0] == "11" * 32
    assert called["args"][1] == "recip_pubkey"
    # ensure the event is published from the sender and tagged with the recipient
    expected_sender = nostr_client.derive_public_key_hex("11" * 32)
    assert mgr.last_event.public_key == expected_sender
    assert mgr.last_event.tags == [["p", "recip_pubkey"]]


def test_publish_signed_ticket_dm(monkeypatch):
    mgr = DummyRelayManager()
    monkeypatch.setattr(ticket_utils, "initialize_client", lambda: mgr)

    event_data = {
        "id": "123",
        "pubkey": "abcd",
        "content": "cipher",
        "kind": nostr_client.EventKind.EPHEMERAL_DM,
        "tags": [["p", "abcd"]],
        "created_at": 111,
        "sig": "deadbeef",
    }

    ev_id = ticket_utils.publish_signed_ticket_dm(event_data)

    assert ev_id == "123"
    assert mgr.publish_count == 1
    assert mgr.last_event.content == "cipher"
