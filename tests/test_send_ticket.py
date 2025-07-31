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
    def add_relay(self, url):
        self.last_relay = url
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
    assert mgr.last_event.kind == nostr_client.EventKind.EPHEMERAL_DM
    assert called["args"][0] == "11" * 32
    assert called["args"][1] == "recip_pubkey"
    # ensure the event is published from the sender and tagged with the recipient
    expected_sender = nostr_client.derive_public_key_hex("11" * 32)
    assert mgr.last_event.public_key == expected_sender
    assert mgr.last_event.tags == [["p", "recip_pubkey"]]
